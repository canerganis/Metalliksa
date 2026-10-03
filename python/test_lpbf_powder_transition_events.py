"""Synthetic hybrid-state oracle; this is not experimental LPBF validation.

An isolated solid/powder pair uses the production conservative face operator.
Its independent exponential solution shows why locating a liquidus crossing
inside a frozen Euler step does not remove Euler error or guarantee a better
terminal field. No production physics or default settings are modified here.
"""

import math
import unittest
from unittest.mock import patch

import numpy as np

import lpbf_simulation
import lpbf_heat_source
from lpbf_material_registry import material as make_material


def _exact_pair(end=4.0):
    # Capacities are 2 and 1 J/(m3 K); dx=1 m; k_s=1 and k_p=.1 W/(m K).
    # Adiabatic pair: M=(Cs*Ts+Cp*Tp)/(Cs+Cp) is conserved and
    # Tp(t)=M+(Tp(0)-M)*exp(-k_face*(1/Cs+1/Cp)*t).
    mean = (2.0*650.0+450.0)/3.0
    threshold = 500.0
    before_face = 2.0*.1/(1.0+.1)
    event = -math.log((mean-threshold)/(mean-450.0))/(1.5*before_face)
    final = mean+(threshold-mean)*math.exp(-1.5*(end-event))
    return event, final


def _euler_pair(max_dt, localize=False):
    temperature = np.array([650.0, 450.0]).reshape(2, 1, 1)
    capacity = np.array([2.0, 1.0]).reshape(2, 1, 1)
    active = np.ones_like(temperature, dtype=bool)
    initial_energy = float(np.sum(capacity*temperature))
    time, event, ever, steps, switches, defect = 0.0, None, False, 0, 0, 0.0
    while time < 4.0-1e-12:
        conductivity = np.array([1.0, 1.0 if ever else .1]).reshape(2, 1, 1)
        rate, diagonal = lpbf_simulation._conduction_rate_and_diagonal(
            temperature, conductivity, active, 1.0)
        dt = min(max_dt, 4.0-time)
        assert dt <= float(np.min(.9*capacity/diagonal))
        slope = float((rate/capacity)[1, 0, 0])
        if localize and not ever and float(temperature[1, 0, 0])+dt*slope > 500.0:
            dt = (500.0-float(temperature[1, 0, 0]))/slope
        temperature += dt*rate/capacity
        time += dt
        steps += 1
        if not ever and float(temperature[1, 0, 0]) >= 500.0-1e-12:
            ever, event = True, time
            switches += 1
        defect = max(defect, abs(float(np.sum(capacity*temperature))-initial_energy))
    return {"event": event, "final": float(temperature[1, 0, 0]),
            "maximumEnergyDefect": defect, "steps": steps, "switches": switches}


class PowderTransitionHybridOracleTests(unittest.TestCase):
    def test_endpoint_transition_and_frozen_rate_localization_are_first_order(self):
        event, final = _exact_pair()
        levels = (.2, .1, .05, .025)
        baseline = [_euler_pair(dt) for dt in levels]
        localized = [_euler_pair(dt, localize=True) for dt in levels]
        for row in baseline+localized:
            self.assertEqual(row["switches"], 1)
            self.assertLess(row["maximumEnergyDefect"], 1e-10)
        errors = [abs(row["event"]-event) for row in localized]
        orders = [math.log(errors[i]/errors[i+1], 2) for i in range(3)]
        self.assertTrue(all(.9 < order < 1.1 for order in orders), (errors, orders))
        self.assertGreater(errors[-1], 1e-3)
        # Endpoint scheduling is not necessarily late relative to the true ODE:
        # explicit Euler overestimates heating for this concave trajectory.
        self.assertGreater(baseline[0]["event"], event)
        self.assertLess(baseline[1]["event"], event)
        for family in (baseline, localized):
            temperature_errors = [abs(row["final"]-final) for row in family]
            self.assertTrue(all(temperature_errors[i+1] < temperature_errors[i]
                                for i in range(3)), temperature_errors)

    def test_more_accurate_transition_time_can_worsen_terminal_temperature(self):
        event, final = _exact_pair()
        for dt in (.2, .05):
            with self.subTest(max_dt=dt):
                endpoint = _euler_pair(dt)
                localized = _euler_pair(dt, localize=True)
                self.assertLess(abs(localized["event"]-event),
                                abs(endpoint["event"]-event))
                self.assertGreater(abs(localized["final"]-final),
                                   abs(endpoint["final"]-final))
                self.assertEqual(localized["steps"], endpoint["steps"]+1)

    def test_localization_can_also_worsen_true_transition_time(self):
        event, _ = _exact_pair()
        endpoint, localized = _euler_pair(.025), _euler_pair(.025, localize=True)
        self.assertGreater(abs(localized["event"]-event), abs(endpoint["event"]-event))


class ProductionPowderTransitionTests(unittest.TestCase):
    def test_manufactured_heating_cooling_exposes_endpoint_delay_and_irreversible_k(self):
        """Drive exact H(t); keep production conduction/state/enthalpy updates.

        The manufactured source cancels the physical passive rate, so this test
        isolates state scheduling. It cannot establish coupled field accuracy.
        """
        request = {
            "mode": "standard", "backend": "reference", "material": "Inconel 718",
            "power_W": 60, "speed_mm_s": 1000, "mesh_um": 40,
            "layer_um": 80, "trackLength_um": 100, "cooling_s": 0,
            "dwell_s": 0, "maxDt_s": 1e-6, "convection_W_m2K": 0,
        }
        base_settings, original = lpbf_simulation.validate(request)
        material = make_material(original["name"], supplied={
            "source": "synthetic transition-clock oracle; no experimental claim",
            "solidus_K": 400.0, "liquidus_K": 500.0, "boiling_K": 5000.0,
            "latentHeat_J_kg": 100_000.0, "absorptivity": .35,
            "emissivity": 0.0, "dGamma_dT": original["dGamma_dT"],
            "table": [[273.15, 8000.0, 15.0, 500.0, 1e-3],
                      [5000.0, 8000.0, 15.0, 500.0, 1e-3]],
        })
        end = lpbf_simulation.scan_segments(base_settings)[1]
        t0 = lpbf_simulation.thermal_si_inputs(base_settings, material)["preheat_K"]

        def analytic_h(temperature):
            return 500.0*(temperature-273.15)+1000.0*np.clip(temperature-400.0, 0, 100)

        h0, h_peak, h_final = map(float, map(analytic_h, (t0, 560.0, 450.0)))
        exact_crossing = .5*end*(float(analytic_h(500.0))-h0)/(h_peak-h0)

        def enthalpy_at(time):
            if time <= .5*end:
                return h0+(h_peak-h0)*time/(.5*end)
            return h_peak+(h_final-h_peak)*(time-.5*end)/(.5*end)

        small_domain = dict(radius=50e-6, span=80e-6, nx=2, ny=1, nz=4,
                            nxy=2, dx=40e-6, substrate_depth=80e-6)
        for max_dt in (1e-6, 5e-7, 2.5e-7):
            with self.subTest(max_dt=max_dt):
                settings = {**base_settings, "maxDt_s": max_dt}
                context, records = {}, []
                original_step = lpbf_heat_source.source_limited_step

                def limited(*args, **kwargs):
                    context["passive"] = args[10]
                    # cp is constant and the physical reference density is fixed.
                    context["rho"] = args[11]/500.0
                    return original_step(*args, **kwargs)

                def forcing(axis, z, dx, segment, time, dt, surface, radius,
                            penetration, power, **kwargs):
                    target = context["rho"]*((enthalpy_at(time+dt)-enthalpy_at(time))/dt)
                    return target-context["passive"], 1.0

                with patch.object(lpbf_simulation, "calculate_mesh_domain", return_value=small_domain), \
                        patch.object(lpbf_simulation, "source_limited_step", side_effect=limited), \
                        patch.object(lpbf_heat_source, "integrated_source", side_effect=forcing):
                    result = lpbf_simulation.transient(
                        settings, material, local_history_observer=records.append,
                        local_history_indices_ijk=((0, 0, 2),))

                transitions = [i for i, record in enumerate(records)
                               if not record["cells"][0]["everLiquidusBefore"]
                               and record["cells"][0]["everLiquidusAfter"]]
                self.assertEqual(len(transitions), 1)
                index = transitions[0]
                delay = records[index]["time_s"]-exact_crossing
                self.assertGreaterEqual(delay, -1e-13)
                self.assertLessEqual(delay, max_dt+1e-13)
                self.assertGreater(delay, 1e-9)
                ratio = settings["powderConductivityRatio"]
                self.assertAlmostEqual(records[index]["cells"][0]["effectiveConductivity_W_mK"], 15.0*ratio)
                for record in records[index+1:]:
                    cell = record["cells"][0]
                    self.assertTrue(cell["everLiquidusBefore"])
                    self.assertTrue(cell["everLiquidusAfter"])
                    self.assertAlmostEqual(cell["effectiveConductivity_W_mK"], 15.0)
                self.assertAlmostEqual(records[-1]["cells"][0]["temperature_K"], 450.0, delta=1e-8)
                self.assertLess(result["energyBalance"]["relativeError"], 1e-10)
                self.assertEqual(result["discretization"]["cells"], 8)
                self.assertLessEqual(result["discretization"]["steps"], 401)


if __name__ == "__main__":
    unittest.main()
