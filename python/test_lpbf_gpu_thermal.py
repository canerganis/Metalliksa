"""Numerical GPU parity checks with targets fixed before execution."""

import unittest
from unittest.mock import patch
import copy

import numpy as np

from lpbf_gpu_thermal import (PARITY_TARGETS, _integrated_source_torch,
                              _source_limited_step_torch, compare_with_cpu,
                              require_cuda, run_gpu, validate_pilot_request)
from lpbf_simulation import validate
from lpbf_core_physics import calculate_mesh_domain, scan_segments, thermal_si_inputs
from lpbf_heat_source import (MINIMUM_SOURCE_CAPTURE_FRACTION, integrated_source,
                              source_limited_step)
from lpbf_material_registry import property_at


CASE = {"mode": "standard", "backend": "reference", "material": "Inconel 718",
        "power_W": 60, "speed_mm_s": 1200, "mesh_um": 40, "maxDt_s": 2e-7,
        "layer_um": 80, "trackLength_um": 200, "cooling_s": 2e-5, "dwell_s": 0}


class GpuThermal(unittest.TestCase):
    def test_pilot_accepts_layer_conforming_grid_for_shared_model(self):
        request = {**CASE, "jobType": "gpu-thermal-pilot", "backend": "cuda:0",
                   "powderGridPolicy": "layer-conforming"}
        with patch("lpbf_gpu_thermal.require_cuda") as require_device, \
             patch("lpbf_gpu_thermal.calculate_mesh_domain",
                   return_value={"nxy": 1, "nz": 1}) as calculate_domain:
            settings, material = validate_pilot_request(request)
        require_device.assert_called_once_with("cuda:0")
        calculate_domain.assert_called_once()
        self.assertEqual(settings["powderGridPolicy"], "layer-conforming")
        self.assertEqual(material["materialId"], "in718")

    def test_pilot_accepts_standard_reference_request(self):
        request = {**CASE, "jobType": "gpu-thermal-pilot", "backend": "cuda:0"}
        with patch("lpbf_gpu_thermal.require_cuda") as require_device:
            settings, material = validate_pilot_request(request)
        require_device.assert_called_once_with("cuda:0")
        self.assertEqual(settings["backend"], "cuda:0")
        self.assertEqual(settings["mode"], "standard")
        self.assertEqual(settings["study"], "none")
        self.assertEqual(settings["powderGridPolicy"], "layer-conforming")
        self.assertEqual(material["materialId"], "in718")

    def test_cuda_source_field_capture_and_limited_dt_match_shared_cpu_source(self):
        try:
            import torch
            available = torch.cuda.is_available()
        except ImportError:
            available = False
        if not available:
            self.skipTest("CUDA runtime unavailable; source/limiter parity unverified")

        settings, material = validate(CASE)
        domain = calculate_mesh_domain(settings)
        dx = domain["dx"]
        radius = domain["radius"]
        layer_m = settings["layer_um"] * 1e-6
        axis = (np.arange(domain["nxy"])+.5)*dx-domain["span"]/2
        z = (np.arange(domain["nz"])+.5)*dx-domain["substrate_depth"]
        segments, _ = scan_segments(settings)
        segment = segments[0]
        time = segment["start_s"]
        initial_dt = 10e-6
        power = thermal_si_inputs(settings, material)["absorbed_power_W"]

        source_cpu, capture_cpu = integrated_source(
            axis, z, dx, segment, time, initial_dt, layer_m, radius, layer_m,
            power, axis_y=axis)
        axis_cuda = torch.as_tensor(axis, dtype=torch.float64, device="cuda:0")
        z_cuda = torch.as_tensor(z, dtype=torch.float64, device="cuda:0")
        source_cuda, capture_cuda = _integrated_source_torch(
            torch, axis_cuda, z_cuda, dx, segment, time, initial_dt, layer_m,
            radius, layer_m, power)
        np.testing.assert_allclose(source_cuda.cpu().numpy(), source_cpu,
                                   rtol=1e-10, atol=1e-8)
        self.assertAlmostEqual(capture_cuda, capture_cpu, delta=1e-12)
        self.assertGreaterEqual(capture_cuda, MINIMUM_SOURCE_CAPTURE_FRACTION)

        _, _, zz = np.meshgrid(axis, axis, z, indexing="ij")
        rho = float(property_at(material, thermal_si_inputs(settings, material)["preheat_K"], 1))
        cp = float(property_at(material, thermal_si_inputs(settings, material)["preheat_K"], 3))
        rho_field = rho*np.where(zz > 0.0, settings["packingFraction"], 1.0)
        capacity_cpu = rho_field * cp
        passive_cpu = np.zeros_like(source_cpu)
        cpu_result = source_limited_step(
            axis, z, dx, segment, time, initial_dt, layer_m, radius, layer_m,
            power, passive_cpu, capacity_cpu, axis_y=axis)
        passive_cuda = torch.zeros_like(source_cuda)
        capacity_cuda = torch.as_tensor(capacity_cpu, dtype=torch.float64, device="cuda:0")
        cuda_result = _source_limited_step_torch(
            torch, axis_cuda, z_cuda, dx, segment, time, initial_dt, layer_m,
            radius, layer_m, power, passive_cuda, capacity_cuda)
        self.assertLess(cpu_result[0], initial_dt, "frozen source case must exercise the 25 K limiter")
        self.assertAlmostEqual(cuda_result[0], cpu_result[0], delta=1e-15)
        self.assertEqual(cuda_result[4], cpu_result[4])
        self.assertAlmostEqual(cuda_result[3], cpu_result[3], delta=1e-12)
        np.testing.assert_allclose(cuda_result[1].cpu().numpy(), cpu_result[1],
                                   rtol=1e-10, atol=1e-8)
        np.testing.assert_allclose(cuda_result[2].cpu().numpy(), cpu_result[2],
                                   rtol=1e-10, atol=1e-8)

    def test_cuda_source_path_preserves_frozen_cpu_parity(self):
        try:
            import torch
            available = torch.cuda.is_available()
        except ImportError:
            available = False
        if not available:
            self.skipTest("CUDA runtime unavailable; real GPU parity unverified")
        result = compare_with_cpu(CASE, "cuda:0", use_cuda_source=True)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["gpu"]["solver"]["sourceIntegrationDevice"], "cuda:0")
        self.assertEqual(result["gpu"]["solver"]["sourceTimestepLimiterDevice"], "cuda:0")
        self.assertEqual(result["comparisons"]["finalTemperatureField"]["status"], "pass")

    def test_gpu_path_rejects_truncated_source_capture(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch unavailable for GPU-path driver test")
        import lpbf_gpu_thermal
        from lpbf_simulation import MINIMUM_SOURCE_CAPTURE_FRACTION

        settings, _ = validate(CASE)
        domain = lpbf_gpu_thermal.calculate_mesh_domain(settings)
        n = domain["nxy"]
        z_count = domain["nz"]
        capture = MINIMUM_SOURCE_CAPTURE_FRACTION - 1e-3
        with patch("lpbf_gpu_thermal.require_cuda", return_value=(torch, torch.device("cpu"))), \
             patch("lpbf_gpu_thermal.source_limited_step",
                   return_value=(settings["maxDt_s"], np.zeros((n, n, z_count)), None, capture, 0)):
            with self.assertRaisesRegex(ValueError, "Gaussian source capture .* below the 99% minimum"):
                run_gpu(CASE, "cuda:0")

    def test_equal_summaries_cannot_hide_wrong_final_field(self):
        settings, _ = validate(CASE)
        end = scan_segments(settings)[1]
        coords = np.array([[0., 0., 0.], [1e-5, 0., 0.]])
        metrics = {"peakTemperature_K": 1500., "width_um": 40., "depth_um": 40.,
                   "length_um": 100., "volume_um3": 1000.}
        energy = {"input_J": 1., "losses_J": .2, "stored_J": .8}
        disc = {"cells": 2, "mesh_m": 1e-5, "steps": 1}
        cpu = {"coreContract": {"modelId": "stationary-enthalpy-conduction-layer-conforming-v1"},
               "material": {"name": "Inconel 718", "materialId": "in718",
                            "materialRevisionSha256": "a" * 64, "version": "lpbf-materials-1"},
               "settings": settings, "metrics": metrics, "energyBalance": energy,
               "discretization": disc, "thermalHistory": [{"time_s": end}],
               "solver": {"id": "enthalpy-fv-6"}}
        gpu = {"solver": {"modelId": "stationary-enthalpy-conduction-layer-conforming-v1"},
               "material": copy.deepcopy(cpu["material"]), "metrics": copy.deepcopy(metrics),
               "energyBalance": copy.deepcopy(energy), "discretization": copy.deepcopy(disc)}
        frame = {"time_s": end, "surface_m": settings["layer_um"] * 1e-6}
        # Same peak and total temperature, but the hot cells are in wrong places.
        field = {"temperature_K": np.array([1500., 1000.]), "coordinates_m": coords,
                 "time_s": end, "surface_m": frame["surface_m"], "steps": 1}
        with patch("lpbf_gpu_thermal.run_gpu", return_value=(gpu, field)), \
             patch("lpbf_gpu_thermal._run_cpu_with_final",
                   return_value=(cpu, frame, np.array([1000., 1500.]), coords)):
            result = compare_with_cpu(CASE)
        self.assertEqual(result["comparisons"]["peakTemperature_K"]["status"], "pass")
        self.assertEqual(result["comparisons"]["stored_J"]["status"], "pass")
        self.assertEqual(result["comparisons"]["finalSampling"]["status"], "pass")
        self.assertEqual(result["comparisons"]["finalTemperatureField"]["status"], "failed")
        self.assertEqual(result["status"], "failed")

    def test_device_is_explicit_and_never_falls_back(self):
        for device in ("cpu", "cuda", "auto", "cuda:-1", "cuda:abc"):
            with self.assertRaisesRegex(ValueError, "no CPU fallback"):
                require_cuda(device)
        with patch("torch.cuda.is_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "no CPU fallback"):
                require_cuda("cuda:0")

    def test_cuda_reference_parity_for_molten_track(self):
        try:
            import torch
            available = torch.cuda.is_available()
        except ImportError:
            available = False
        if not available:
            self.skipTest("CUDA runtime unavailable; real GPU parity unverified")
        self.assertEqual(PARITY_TARGETS["integralRelativeMax"], .01)
        self.assertEqual(PARITY_TARGETS["widthDepthAbsoluteCellsMax"], 1.)
        self.assertEqual(PARITY_TARGETS["fieldRiseL2RelativeMax"], .01)
        self.assertEqual(PARITY_TARGETS["fieldRiseMaxRelativeMax"], .01)
        self.assertEqual(PARITY_TARGETS["peakMeltVolumeRelativeMax"], .01)
        result = compare_with_cpu(CASE, "cuda:0")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["gpu"]["solver"]["thermalEvolutionDevice"], "cuda:0")
        self.assertEqual(result["gpu"]["solver"]["sourceIntegrationDevice"], "cpu")
        self.assertEqual(result["gpu"]["solver"]["modelId"], result["cpu"]["coreContract"]["modelId"])
        self.assertEqual(result["gpu"]["material"]["materialRevisionSha256"],
                         result["cpu"]["material"]["materialRevisionSha256"])
        self.assertGreater(result["gpu"]["metrics"]["width_um"], 0)
        self.assertGreater(result["gpu"]["metrics"]["depth_um"], 0)
        self.assertLessEqual(result["gpu"]["energyBalance"]["relativeError"], .01)
        self.assertEqual(result["comparisons"]["finalSampling"]["status"], "pass")
        self.assertEqual(result["comparisons"]["finalTemperatureField"]["status"], "pass")
        self.assertEqual(result["comparisons"]["volume_um3"]["status"], "pass")
        self.assertEqual(result["comparisons"]["length_um"]["status"], "pass")
        self.assertFalse(result["experimentalValidation"])

    def test_cuda_final_time_roundoff_preserves_reference_sampling(self):
        """Reproduce the UI pilot's extra CUDA endpoint step on actual hardware."""
        try:
            import torch
            available = torch.cuda.is_available()
        except ImportError:
            available = False
        if not available:
            self.skipTest("CUDA runtime unavailable; endpoint parity unverified")
        case = {
            "mode": "standard", "backend": "reference", "material": "Inconel 718",
            "power_W": 40., "speed_mm_s": 800., "beamDiameter_um": 80.,
            "preheat_C": 80., "layer_um": 40., "hatch_um": 100.,
            "mesh_um": 40., "maxDt_s": 1e-6, "trackLength_um": 600.,
            "tracks": 1, "layers": 1, "dwell_s": .0002, "cooling_s": .0005,
            "scanAngle_deg": 0., "layerRotation_deg": 67., "strategy": "stripe",
            "stripeWidth_um": 500., "islandSize_um": 200.,
            "packingFraction": .55, "powderConductivityRatio": .12,
            "convection_W_m2K": 20., "absorptivity": .38, "emissivity": .35,
            "study": "none", "surfaceMode": "powder-layer",
            "powderGridPolicy": "layer-conforming", "barePlateGeometry": "square",
        }
        result = compare_with_cpu(case, "cuda:0")
        sampling = result["comparisons"]["finalSampling"]
        with self.subTest(check="accepted step count"):
            self.assertEqual(sampling["gpuSteps"], sampling["cpuSteps"], sampling)
        for check in ("finalSampling", "finalTemperatureField"):
            with self.subTest(check=check):
                self.assertEqual(result["comparisons"][check]["status"], "pass",
                                 result["comparisons"][check])
        with self.subTest(check="full frozen parity gate"):
            self.assertEqual(result["status"], "pass")
        self.assertFalse(result["experimentalValidation"])

    def test_cuda_reference_parity_for_316l_registry_material(self):
        """Check CUDA parity only for the existing estimated-legacy 316L snapshot."""
        try:
            import torch
            available = torch.cuda.is_available()
        except ImportError:
            available = False
        if not available:
            self.skipTest("CUDA runtime unavailable; real 316L GPU parity unverified")

        case = {**CASE, "material": "316L Stainless Steel"}
        _, material = validate(case)
        self.assertEqual(material["materialId"], "ss316l")
        self.assertEqual(material["quality"], "estimated")
        self.assertEqual(material["provenanceClass"], "estimated-legacy")

        self.assertEqual(PARITY_TARGETS["integralRelativeMax"], .01)
        self.assertEqual(PARITY_TARGETS["widthDepthAbsoluteCellsMax"], 1.)
        self.assertEqual(PARITY_TARGETS["fieldRiseL2RelativeMax"], .01)
        self.assertEqual(PARITY_TARGETS["fieldRiseMaxRelativeMax"], .01)
        self.assertEqual(PARITY_TARGETS["peakMeltVolumeRelativeMax"], .01)
        result = compare_with_cpu(case, "cuda:0")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["scope"], "same-model CPU/GPU numerical parity only")
        self.assertFalse(result["experimentalValidation"])
        self.assertEqual(result["gpu"]["validationStatus"], "unvalidated")
        self.assertFalse(result["gpu"]["productionReady"])
        self.assertEqual(result["gpu"]["material"]["materialId"], "ss316l")
        self.assertEqual(result["gpu"]["material"]["materialRevisionSha256"],
                         material["materialRevisionSha256"])
        self.assertEqual(result["gpu"]["solver"]["thermalEvolutionDevice"], "cuda:0")
        self.assertEqual(result["gpu"]["solver"]["sourceIntegrationDevice"], "cpu")
        self.assertLessEqual(result["gpu"]["energyBalance"]["relativeError"], .01)
        self.assertEqual(result["comparisons"]["finalSampling"]["status"], "pass")
        self.assertEqual(result["comparisons"]["finalTemperatureField"]["status"], "pass")
        self.assertEqual(result["comparisons"]["volume_um3"]["status"], "pass")
        self.assertEqual(result["comparisons"]["length_um"]["status"], "pass")

    def test_cuda_reference_parity_for_al_and_ti_registry_materials(self):
        """Check same-model CUDA parity for estimated AlSi10Mg and Ti-6Al-4V snapshots."""
        try:
            import torch
            available = torch.cuda.is_available()
        except ImportError:
            available = False
        if not available:
            self.skipTest("CUDA runtime unavailable; Al/Ti GPU parity unverified")

        for name, material_id in (("AlSi10Mg", "alsi10mg"), ("Ti-6Al-4V", "ti6al4v")):
            with self.subTest(material=name):
                case = {**CASE, "material": name}
                _, material = validate(case)
                self.assertEqual(material["materialId"], material_id)
                self.assertEqual(material["quality"], "estimated")

                result = compare_with_cpu(case, "cuda:0")
                self.assertEqual(result["status"], "pass")
                self.assertEqual(result["gpu"]["solver"]["thermalEvolutionDevice"], "cuda:0")
                self.assertEqual(result["gpu"]["solver"]["sourceIntegrationDevice"], "cpu")
                self.assertEqual(result["gpu"]["solver"]["modelId"],
                                 result["cpu"]["coreContract"]["modelId"])
                self.assertEqual(result["gpu"]["material"]["materialRevisionSha256"],
                                 result["cpu"]["material"]["materialRevisionSha256"])
                self.assertEqual(result["comparisons"]["finalTemperatureField"]["status"], "pass")
                self.assertEqual(result["comparisons"]["volume_um3"]["status"], "pass")
                self.assertFalse(result["experimentalValidation"])


if __name__ == "__main__":
    unittest.main()
