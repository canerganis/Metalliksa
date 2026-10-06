"""Focused correctness coverage for the opt-in Warp thermal candidate."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import lpbf_gpu_thermal_warp as candidate


CASE = {
    "mode": "standard", "backend": "reference", "material": "Inconel 718",
    "power_W": 60, "speed_mm_s": 1200, "mesh_um": 10, "maxDt_s": 2e-7,
    "layer_um": 80, "trackLength_um": 200, "cooling_s": 2e-5, "dwell_s": 0,
    "powderGridPolicy": "layer-conforming",
}


class WarpThermalCandidate(unittest.TestCase):
    def test_energy_step_uses_boundary_fluxes_and_checks_internal_conservation(self):
        # Rates are W/m^3. Internal face terms cancel; the explicit boundary
        # terms are the negative bottom and top surface losses.
        total_rate = [-3.0, -9.0]
        boundary_rate = [-5.0, -7.0]
        loss = candidate._boundary_loss_for_step(total_rate, boundary_rate, 2.0, .5)
        self.assertEqual(loss, 12.0)
        self.assertEqual(-sum(total_rate) * 2.0 * .5, loss)

        with self.assertRaisesRegex(ValueError, "internal conductive rates do not cancel"):
            candidate._boundary_loss_for_step([1.0, 2.0], [0.0, 0.0], 1.0, 1.0)

        # Fail closed for invalid rate arrays and preserve zero-flux steps.
        self.assertEqual(candidate._boundary_loss_for_step([-2.0, 2.0], [0.0, 0.0], 1.0, 1.0), 0.0)
        with self.assertRaisesRegex(ValueError, "invalid step rates"):
            candidate._boundary_loss_for_step([float("nan")], [0.0], 1.0, 1.0)
        self.assertEqual(candidate._energy_closure(100.0, 0.0, 99.0), .01)
        with self.assertRaisesRegex(ValueError, "energy balance failed"):
            candidate._energy_closure(100.0, 0.0, 98.99)

    def test_candidate_rejects_evaporation_model(self):
        # Wave B LT-7: the candidate kernels use table k only; evaporationModel physics is CPU-only.
        with self.assertRaisesRegex(ValueError, "evaporationModel"):
            candidate._validate_candidate({**CASE, "evaporationModel": True})
        candidate._validate_candidate({**CASE, "marangoniMultiplier": 3.0})

    def test_explicit_device_and_dependency_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Explicit cuda:N"):
            candidate._require_warp_cuda("cpu")
        with patch.object(candidate, "wp", None):
            with self.assertRaisesRegex(RuntimeError, "Warp is unavailable"):
                candidate._require_warp_cuda("cuda:0")

    def test_device_validation_uses_warp_without_torch_and_rejects_wrong_device(self):
        from unittest.mock import Mock
        selected = SimpleNamespace(is_cuda=True, ordinal=0)
        api = SimpleNamespace(init=Mock(), get_device=Mock(return_value=selected))
        with patch.object(candidate, "wp", api), patch.dict("sys.modules", {"torch": None}):
            self.assertIs(candidate._require_warp_cuda("cuda:0"), selected)
            api.init.assert_called_once_with()
            api.get_device.assert_called_once_with("cuda:0")
            selected.ordinal = 1
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                candidate._require_warp_cuda("cuda:0")
            selected.ordinal, selected.is_cuda = 0, False
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                candidate._require_warp_cuda("cuda:0")

    def test_exact_pilot_case_matches_cpu_full_temperature_field(self):
        available = candidate.wp is not None and candidate.wp.is_cuda_available()
        if not available:
            self.skipTest("Warp/CUDA unavailable; explicit candidate parity unverified")

        result = candidate.compare_with_cpu(CASE, "cuda:0")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["gpu"]["solver"]["id"], candidate.WARP_SOLVER_ID)
        self.assertEqual(result["gpu"]["solver"]["thermalEvolutionDevice"], "cuda:0")
        self.assertEqual(result["gpu"]["solver"]["sourceIntegrationDevice"], "cpu")
        self.assertEqual(result["gpu"]["discretization"]["cells"], 73_568)
        self.assertEqual(result["gpu"]["discretization"]["steps"], 934)
        self.assertEqual(result["comparisons"]["finalSampling"]["status"], "pass")
        field = result["comparisons"]["finalTemperatureField"]
        self.assertEqual(field["status"], "pass")
        self.assertLessEqual(field["relativeRiseL2"], .01)
        self.assertLessEqual(field["relativeRiseMax"], .01)
        self.assertLessEqual(result["gpu"]["energyBalance"]["relativeError"], .01)

    def test_four_registry_alloys_match_cpu_under_same_warp_model(self):
        available = candidate.wp is not None and candidate.wp.is_cuda_available()
        if not available:
            self.skipTest("Warp/CUDA unavailable; four-alloy parity unverified")

        from lpbf_simulation import validate
        alloys = (("Inconel 718", "in718"),
                  ("316L Stainless Steel", "ss316l"),
                  ("AlSi10Mg", "alsi10mg"),
                  ("Ti-6Al-4V", "ti6al4v"))
        for name, expected_id in alloys:
            with self.subTest(alloy=name):
                case = {**CASE, "material": name}
                _, material = validate(case)
                self.assertEqual(material["materialId"], expected_id)
                self.assertEqual(material["quality"], "estimated")
                result = candidate.compare_with_cpu(case, "cuda:0")
                self.assertEqual(result["status"], "pass")
                self.assertEqual(result["gpu"]["material"]["materialRevisionSha256"],
                                 material["materialRevisionSha256"])
                self.assertEqual(result["gpu"]["solver"]["modelId"],
                                 result["cpu"]["coreContract"]["modelId"])
                self.assertEqual(result["gpu"]["discretization"]["steps"],
                                 result["cpu"]["discretization"]["steps"])
                self.assertEqual(result["comparisons"]["finalTemperatureField"]["status"], "pass")
                self.assertLessEqual(result["gpu"]["energyBalance"]["relativeError"], .01)
                self.assertFalse(result["experimentalValidation"])


if __name__ == "__main__":
    unittest.main()
