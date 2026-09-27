"""Manufactured forcing through the production moving-source transient loop."""

import math
import unittest
from unittest.mock import patch

import numpy as np

import lpbf_heat_source
import lpbf_simulation
from lpbf_core_physics import GAUSS_NODES, scan_segments
from lpbf_evidence import FieldRecorder
from lpbf_simulation import (calculate_mesh_domain, conduction_rate, enthalpy_table,
                             property_at, run, thermal_si_inputs, validate)


CASE = {
    "mode": "standard",
    "backend": "reference",
    "material": "Inconel 718",
    "power_W": 60,
    "speed_mm_s": 1200,
    "mesh_um": 40,
    "maxDt_s": 1e-5,
    "layer_um": 80,
    "trackLength_um": 200,
    "cooling_s": 2e-5,
    "dwell_s": 0,
}


class ProductionTransientManufactured(unittest.TestCase):
    def test_uniform_enthalpy_ramp_is_time_step_independent_and_conservative(self):
        """A manufactured volumetric source exactly drives a uniform T(t) ramp."""
        slope_K_s = 3.5e5
        results = []

        for dt_cap in (1e-5, 5e-6, 2.5e-6):
            request = {**CASE, "maxDt_s": dt_cap}
            settings, material = validate(request)
            end = scan_segments(settings)[1]
            thermal = thermal_si_inputs(settings, material)
            initial_temperature = thermal["preheat_K"]
            tt, hh = enthalpy_table(material)

            source_context = {}

            def manufactured_source(axis, z, dx, segment, time, dt, surface,
                                    radius, penetration, power, *, axis_y=None,
                                    incidence_angle_deg=0.0,
                                    incidence_azimuth_deg=0.0):
                passive_rate = source_context["passive_rate"]
                capacity = source_context["capacity"]
                t_now = initial_temperature + slope_K_s * time
                t_next = initial_temperature + slope_K_s * (time + dt)
                h_now = float(np.interp(t_now, tt, hh))
                h_next = float(np.interp(t_next, tt, hh))
                specific_cp = float(property_at(material, t_now, 3))
                density = capacity / specific_cp
                rate = density * ((h_next - h_now) / dt)
                source = rate - passive_rate
                return source, 1.0

            original_step = lpbf_heat_source.source_limited_step

            def source_limited(*args, **kwargs):
                # Let the production source-limited step/retry logic run. Swap
                # only its Gaussian integral for the manufactured exact source.
                source_context["passive_rate"] = args[10]
                source_context["capacity"] = args[11]
                return original_step(*args, **kwargs)

            with patch("lpbf_heat_source.integrated_source", side_effect=manufactured_source), \
                    patch("lpbf_simulation.source_limited_step", side_effect=source_limited):
                result = run(request)

            expected_final = initial_temperature + slope_K_s * end
            final = result["thermalHistory"][-1]
            results.append((result, expected_final, final, end, material["boiling_K"]))

        steps = [result["discretization"]["steps"] for result, _, _, _, _ in results]
        self.assertEqual(len(set(steps)), 3)
        for result, expected_final, final, end, boiling_temperature in results:
            self.assertAlmostEqual(final["time_s"], end, places=14)
            self.assertAlmostEqual(final["peak_K"], expected_final, delta=1e-7)
            self.assertAlmostEqual(final["center_K"], expected_final, delta=1e-7)
            self.assertLessEqual(result["energyBalance"]["relativeError"], 1e-10)
            self.assertLess(result["metrics"]["peakTemperature_K"], boiling_temperature)

    def test_nonuniform_enthalpy_solution_matches_independent_production_operator(self):
        """Compare production passive flux with an independent face-flux oracle."""
        amplitude_K = 45.0
        slope_multiplier = 1.0
        results = []

        for dt_cap in (1e-5, 5e-6, 2.5e-6):
            request = {**CASE, "maxDt_s": dt_cap}
            settings, material = validate(request)
            end = scan_segments(settings)[1]
            thermal = thermal_si_inputs(settings, material)
            t0 = thermal["preheat_K"]
            domain = calculate_mesh_domain(settings)
            nx, ny, nz = domain["nx"], domain["ny"], domain["nz"]
            dx, span, substrate = domain["dx"], domain["span"], domain["substrate_depth"]
            axis = (np.arange(nx) + .5) * dx - span / 2
            axis_y = (np.arange(ny) + .5) * dx - ny * dx / 2
            z = (np.arange(nz) + .5) * dx - substrate
            xx, yy, zz = np.meshgrid(axis, axis_y, z, indexing="ij")
            phi = (.25 + .2 * (xx / max(abs(axis)))**2
                   + .15 * (yy / max(abs(axis_y)))**2
                   + .4 * (zz - z.min()) / max(z.max() - z.min(), dx))
            density = float(property_at(material, t0, 1)) * np.where(
                zz > 0, settings["packingFraction"], 1.0)
            tt, hh = enthalpy_table(material)
            top_index = int(np.flatnonzero(z < thermal["layer_m"])[-1])
            oracle_checks = 0

            def exact_temperature(time):
                return t0 + amplitude_K * slope_multiplier * (time / end) * phi

            def oracle_passive(time, surface):
                temp = exact_temperature(time)
                k = property_at(material, temp, 2) * np.where(
                    zz > 0, settings["powderConductivityRatio"], 1.0)
                active = zz < surface
                rate = np.zeros_like(temp)
                for axis_id in range(3):
                    lo, hi = [slice(None)] * 3, [slice(None)] * 3
                    lo[axis_id], hi[axis_id] = slice(None, -1), slice(1, None)
                    lo, hi = tuple(lo), tuple(hi)
                    face_k = 2 * k[lo] * k[hi] / (k[lo] + k[hi])
                    face_rate = (face_k * (temp[hi] - temp[lo]) / dx**2
                                 * (active[lo] & active[hi]))
                    rate[lo] += face_rate
                    rate[hi] -= face_rate
                bottom = 2 * k[:, :, 0] * (temp[:, :, 0] - t0) / dx**2
                rate[:, :, 0] -= bottom
                surface_temperature = temp[:, :, top_index]
                surface_loss = (settings["convection_W_m2K"]
                    * (surface_temperature - t0)
                    + material["emissivity"] * 5.670374419e-8
                    * (surface_temperature**4 - t0**4)) / dx
                rate[:, :, top_index] -= surface_loss
                return rate

            source_context = {}

            def manufactured_source(axis_arg, z_arg, dx_arg, segment, time, dt,
                                    surface, radius, penetration, power, *,
                                    axis_y=None, incidence_angle_deg=0.0,
                                    incidence_azimuth_deg=0.0):
                t_next = min(end, time + dt)
                current_t, next_t = exact_temperature(time), exact_temperature(t_next)
                h_now, h_next = np.interp(current_t, tt, hh), np.interp(next_t, tt, hh)
                rate = density * (h_next - h_now) / dt
                return rate - source_context["passive_rate"], 1.0

            original_step = lpbf_heat_source.source_limited_step

            def source_limited(*args, **kwargs):
                nonlocal oracle_checks
                time, surface = args[4], args[6]
                passive_rate = args[10]
                expected_rate = oracle_passive(time, surface)
                np.testing.assert_allclose(passive_rate, expected_rate, rtol=2e-12, atol=1e-7)
                oracle_checks += 1
                source_context["passive_rate"] = passive_rate
                return original_step(*args, **kwargs)

            with patch("lpbf_heat_source.integrated_source", side_effect=manufactured_source), \
                    patch("lpbf_simulation.source_limited_step", side_effect=source_limited):
                result = run(request)

            final = result["thermalHistory"][-1]
            center_i, center_j = nx // 2, ny // 2
            expected_peak = float(exact_temperature(end).max())
            expected_center = float(exact_temperature(end)[center_i, center_j, top_index])
            results.append((result, final, expected_peak, expected_center, end,
                            oracle_checks, material["boiling_K"]))

        steps = [item[0]["discretization"]["steps"] for item in results]
        self.assertEqual(len(set(steps)), 3)
        for result, final, expected_peak, expected_center, end, checks, boiling in results:
            self.assertGreater(checks, 0)
            self.assertAlmostEqual(final["time_s"], end, places=14)
            self.assertAlmostEqual(final["peak_K"], expected_peak, delta=1e-7)
            self.assertAlmostEqual(final["center_K"], expected_center, delta=1e-7)
            self.assertLessEqual(result["energyBalance"]["relativeError"], 1e-10)
            self.assertLess(result["metrics"]["peakTemperature_K"], boiling)


class _CapturingFieldRecorder(FieldRecorder):
    """Capture final production fields without changing recorder behavior."""

    instances = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_temperature = None
        self.instances.append(self)

    def record(self, time, temperature, surface):
        self.last_temperature = np.array(temperature, dtype=np.float64, copy=True)
        return super().record(time, temperature, surface)


class ProductionTransientManufacturedDiffusion(unittest.TestCase):
    def test_mixed_boundary_eigenmode_converges_on_three_fixed_levels(self):
        # Fixed 160 um depth; constant x/y fields match the insulated side faces.
        levels = (8, 16, 32)
        depth_m = 160e-6
        initial_K, amplitude_K = 300.0, 1.0
        rho, cp, conductivity = 8000.0, 500.0, 15.0
        raw = {
            "mode": "standard", "backend": "reference", "surfaceMode": "bare-plate",
            "sourcePenetration_um": 40, "material": "Inconel 718", "power_W": 80,
            "speed_mm_s": 1200, "mesh_um": 20, "maxDt_s": 2e-7,
            "trackLength_um": 200, "cooling_s": 2e-5, "dwell_s": 0,
            "preheat_C": initial_K - 273.15, "convection_W_m2K": 0,
        }
        errors, energy_balance_errors = [], []

        for nz in levels:
            dx = depth_m / nz
            # Refining dt with dx^2 keeps Euler and spatial errors comparable.
            level_raw = {**raw, "maxDt_s": 1.0e4 * dx**2}
            validated_p, validated_material = lpbf_simulation.validate(level_raw)
            end_time = scan_segments(validated_p)[1]
            lam = math.pi / (2.0 * depth_m)
            emissivity = float(validated_material["emissivity"])

            # u=A(t/t_end)sin(lam(z+L)); u=0 at the bottom and du/dz=0
            # at the top. The forcing is rho*cp*u_t-k*lap(u), GL2 integrated.
            def manufactured_source(axis, z, spacing, segment, time, dt, surface,
                                    radius, penetration, power, axis_y=None,
                                    incidence_angle_deg=0.0,
                                    incidence_azimuth_deg=0.0):
                del segment, radius, penetration, power, incidence_angle_deg, incidence_azimuth_deg
                y_axis = axis if axis_y is None else np.asarray(axis_y)
                phi = np.sin(lam * (np.asarray(z)[None, None, :] + depth_m))
                phi = np.broadcast_to(phi, (len(axis), len(y_axis), len(z)))
                source = np.zeros_like(phi, dtype=np.float64)
                for node in GAUSS_NODES:
                    tau = time + float(node) * dt
                    exact = initial_K + amplitude_K * (tau / end_time) * phi
                    source += 0.5 * phi * amplitude_K * (
                        rho * cp / end_time + conductivity * lam**2 * tau / end_time
                    )
                    # Retain production radiation; balance it in the exact
                    # manufactured input at the boundary cell and in the ledger.
                    source[:, :, -1] += 0.5 * emissivity * 5.670374419e-8 * (
                        exact[:, :, -1]**4 - initial_K**4
                    ) / spacing
                return source, 1.0

            def fixed_domain(_p):
                return {"radius": dx, "span": 3 * dx, "nx": 3, "ny": 3,
                        "nz": nz, "dx": dx, "substrate_depth": depth_m}

            original_validate = lpbf_simulation.validate

            def validated_material(value):
                return original_validate(value)

            def constant_property(_material, temperature, column):
                value = {1: rho, 2: conductivity, 3: cp, 4: 1.0e-3}[column]
                values = np.asarray(temperature)
                return value if values.ndim == 0 else np.full(values.shape, value)

            def constant_enthalpy(_material):
                temperatures = np.array([0.0, 5000.0])
                return temperatures, cp * temperatures

            _CapturingFieldRecorder.instances = []
            with (
                patch.object(lpbf_simulation, "validate", side_effect=validated_material),
                patch.object(lpbf_simulation, "calculate_mesh_domain", side_effect=fixed_domain),
                patch.object(lpbf_simulation, "property_at", side_effect=constant_property),
                patch.object(lpbf_simulation, "enthalpy_table", side_effect=constant_enthalpy),
                patch.object(lpbf_simulation, "FieldRecorder", _CapturingFieldRecorder),
                patch.object(lpbf_heat_source, "integrated_source", side_effect=manufactured_source),
            ):
                result = lpbf_simulation.run(level_raw)

            self.assertGreater(result["energyBalance"]["input_J"], 0.0)
            self.assertGreater(result["energyBalance"]["losses_J"], 0.0)
            self.assertLess(result["energyBalance"]["relativeError"], 1.0e-10)
            energy_balance_errors.append(result["energyBalance"]["relativeError"])
            self.assertEqual(len(_CapturingFieldRecorder.instances), 1)
            numerical = _CapturingFieldRecorder.instances[0].last_temperature
            self.assertIsNotNone(numerical)

            z = (np.arange(nz) + 0.5) * dx - depth_m
            phi = np.sin(lam * (z + depth_m))
            exact = np.broadcast_to(initial_K + amplitude_K * phi[None, None, :], numerical.shape)
            errors.append(float(np.sqrt(np.mean((numerical - exact) ** 2))))

        observed_orders = [math.log(errors[i] / errors[i + 1], 2.0)
                           for i in range(len(errors) - 1)]
        self.convergence_diagnostics = {
            "levels_cells_z": levels,
            "field_rms_error_K": tuple(errors),
            "observed_order": tuple(observed_orders),
            "energy_balance_relative_error": tuple(energy_balance_errors),
        }
        self.assertTrue(all(math.isfinite(error) and error > 0 for error in errors), errors)
        self.assertGreater(errors[0], errors[1], errors)
        self.assertGreater(errors[1], errors[2], errors)
        self.assertTrue(all(order > 1.0 for order in observed_orders),
                        (errors, observed_orders))


if __name__ == "__main__":
    unittest.main()
