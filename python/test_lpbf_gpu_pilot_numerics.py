"""Focused consistency tests for captured GPU-pilot numerical evidence."""

import copy
import math
import unittest

import numpy as np

from lpbf_gpu_pilot_numerics import validate_pilot_numerics
from lpbf_core_physics import scan_segments


TARGETS = {
    "integralRelativeMax": 0.01,
    "widthDepthAbsoluteCellsMax": 1.0,
    "fieldRiseL2RelativeMax": 0.01,
    "fieldRiseMaxRelativeMax": 0.01,
    "peakMeltVolumeRelativeMax": 0.01,
    "source": "test frozen targets",
}


def _state(*, cells=4, steps=2, time_s=0.2, mesh_m=1e-6, enthalpy=None,
           temperatures=None, coordinates=None):
    if coordinates is None:
        coordinates = np.column_stack((np.arange(cells, dtype=np.float64),
                                       np.zeros(cells), np.zeros(cells))) * mesh_m
    if temperatures is None:
        temperatures = np.full(cells, 300.0) + np.arange(cells, dtype=np.float64)
    if enthalpy is None:
        enthalpy = np.full(cells, 10.0)
    dt = time_s / steps
    return {
        "coordinates_m": np.asarray(coordinates, dtype=np.float64),
        "temperature_K": np.asarray(temperatures, dtype=np.float64),
        "enthalpy_J_m3": np.asarray(enthalpy, dtype=np.float64),
        "density_kg_m3": np.full(cells, 8000.0, dtype=np.float64),
        "accepted_dt_s": np.full(steps, dt, dtype=np.float64),
        "time_s": time_s,
        "initial_temperature_K": 300.0,
        "cell_volume_m3": mesh_m ** 3,
    }


def _disc(state, mesh_m=1e-6):
    dt = state["accepted_dt_s"]
    return {
        "cells": len(state["coordinates_m"]), "steps": len(dt), "mesh_m": mesh_m,
        "minimumDt_s": float(np.min(dt)), "maximumDt_s": float(np.max(dt)),
        "meanDt_s": state["time_s"] / len(dt),
    }


def _comparison(cpu, gpu, *, status="pass"):
    diff = abs(cpu - gpu)
    return {"cpu": cpu, "gpu": gpu, "relativeDifference": diff / max(abs(cpu), 1e-30),
            "status": status}


def _fixture(*, cpu=None, gpu=None, metrics=None, scalar_changes=None):
    cpu = cpu or _state()
    gpu = gpu or _state()
    cpu_mesh = cpu["cell_volume_m3"] ** (1.0 / 3.0)
    gpu_mesh = gpu["cell_volume_m3"] ** (1.0 / 3.0)
    # Use a synthetic settings tuple whose physical endpoint matches the states.
    settings = {
        "preheat_C": 26.85, "trackLength_um": 200.0, "speed_mm_s": 1.0, "layers": 1,
        "scanAngle_deg": 0.0, "layerRotation_deg": 0.0, "tracks": 1,
        "strategy": "serpentine", "hatch_um": 100.0, "stripeWidth_um": 100.0,
        "islandSize_um": 100.0, "dwell_s": 0.0, "cooling_s": 0.0,
    }
    expected_end = scan_segments(settings)[1]
    stored_cpu = float(cpu["cell_volume_m3"]) * math.fsum(map(float, cpu["enthalpy_J_m3"]))
    stored_gpu = float(gpu["cell_volume_m3"]) * math.fsum(map(float, gpu["enthalpy_J_m3"]))
    metrics = metrics or {"peakTemperature_K": 400.0, "width_um": 100.0,
                          "depth_um": 50.0, "length_um": 100.0, "volume_um3": 20.0}
    comparisons = {
        "finalSampling": {
            "status": "pass", "cpuFinalTime_s": cpu["time_s"], "cpuFrameTime_s": cpu["time_s"],
            "gpuFinalTime_s": gpu["time_s"], "expectedEnd_s": expected_end,
            "cpuSteps": len(cpu["accepted_dt_s"]), "gpuSteps": len(gpu["accepted_dt_s"]),
            "cellCount": len(cpu["coordinates_m"]),
        },
        "finalTemperatureField": {"status": "pass", "relativeRiseL2": 0.0,
                                   "relativeRiseMax": 0.0,
                                   "cpuEncoding": "float64 final state observer",
                                   "gpuEncoding": "float64 final state"},
    }
    for key, value in (("peakTemperature_K", metrics["peakTemperature_K"]),
                       ("input_J", 10.0), ("losses_J", 1.0), ("stored_J", stored_gpu)):
        cpu_value = value if key != "stored_J" else stored_cpu
        comparisons[key] = _comparison(cpu_value, value)
    for key in ("width_um", "depth_um", "length_um"):
        value = metrics[key]
        comparisons[key] = {"cpu": value, "gpu": value, "absoluteDifference_um": 0.0,
                            "status": "pass"}
    comparisons["volume_um3"] = {"cpu": metrics["volume_um3"], "gpu": metrics["volume_um3"],
                                 "relativeDifference": 0.0, "status": "pass"}
    if scalar_changes:
        scalar_changes(comparisons, metrics)
    result = {
        "settings": settings,
        "metrics": metrics,
        "discretization": _disc(gpu, gpu_mesh),
        "energyBalance": {"input_J": 10.0, "losses_J": 1.0, "stored_J": stored_gpu},
        "gpuPilot": {"targets": dict(TARGETS), "status": "pass", "comparisons": comparisons,
                     "cpu": {"discretization": _disc(cpu, cpu_mesh)}},
        "gpuFieldArtifacts": {"states": {
            backend: {"cells": len(state["coordinates_m"]), "steps": len(state["accepted_dt_s"]),
                      "time_s": state["time_s"], "initial_temperature_K": state["initial_temperature_K"],
                      "cell_volume_m3": state["cell_volume_m3"]}
            for backend, state in (("cpu", cpu), ("gpu", gpu))}},
    }
    if not np.array_equal(cpu["coordinates_m"], gpu["coordinates_m"]):
        result["gpuPilot"]["comparisons"]["finalSampling"]["status"] = "failed"
        result["gpuPilot"]["comparisons"]["finalTemperatureField"] = {
            "status": "failed", "reason": "Grid, accepted steps, or final sampling time differs"}
        result["gpuPilot"]["status"] = "failed"
    return result, {"cpu": cpu, "gpu": gpu}


class GpuPilotNumericsTests(unittest.TestCase):
    def test_matching_fields_recompute_energy_and_temperature_norms(self):
        result, states = _fixture()
        proof = validate_pilot_numerics(result, states, TARGETS)
        self.assertEqual(proof["status"], "pass")
        self.assertTrue(proof["samplingAligned"])
        self.assertTrue(proof["temperatureField"]["normsRecomputed"])
        self.assertEqual(proof["states"]["gpu"]["integral_J"], result["energyBalance"]["stored_J"])

    def test_rehashed_changed_temperature_and_enthalpy_are_rejected_numerically(self):
        result, states = _fixture()
        states["gpu"]["temperature_K"] = states["gpu"]["temperature_K"].copy()
        states["gpu"]["temperature_K"][0] += 2.0
        with self.assertRaisesRegex(ValueError, "stored temperature norms"):
            validate_pilot_numerics(result, states, TARGETS)

        result, states = _fixture()
        states["gpu"]["enthalpy_J_m3"] = states["gpu"]["enthalpy_J_m3"].copy()
        states["gpu"]["enthalpy_J_m3"][0] += 1.0
        with self.assertRaisesRegex(ValueError, "enthalpy integral"):
            validate_pilot_numerics(result, states, TARGETS)

    def test_scalar_report_is_checked_even_when_overall_status_is_failed(self):
        def fail_one_scalar(comparisons, metrics):
            item = comparisons["peakTemperature_K"]
            item.update(gpu=410.0, relativeDifference=0.025, status="failed")
            metrics["peakTemperature_K"] = 410.0

        result, states = _fixture(scalar_changes=fail_one_scalar)
        result["gpuPilot"]["status"] = "failed"
        self.assertEqual(validate_pilot_numerics(result, states, TARGETS)["status"], "failed")
        result["gpuPilot"]["comparisons"]["input_J"]["relativeDifference"] = 0.125
        with self.assertRaisesRegex(ValueError, "relative difference changed"):
            validate_pilot_numerics(result, states, TARGETS)

    def test_boolean_values_cannot_impersonate_numeric_differences_or_targets(self):
        result, states = _fixture()
        result["gpuPilot"]["comparisons"]["input_J"]["relativeDifference"] = False
        with self.assertRaisesRegex(ValueError, "relative difference"):
            validate_pilot_numerics(result, states, TARGETS)

        result, states = _fixture()
        result["gpuPilot"]["comparisons"]["width_um"]["absoluteDifference_um"] = False
        with self.assertRaisesRegex(ValueError, "absolute difference"):
            validate_pilot_numerics(result, states, TARGETS)

        result, states = _fixture()
        result["gpuPilot"]["targets"]["widthDepthAbsoluteCellsMax"] = True
        with self.assertRaisesRegex(ValueError, "targets differ"):
            validate_pilot_numerics(result, states, TARGETS)

    def test_cancellation_uses_sum_of_absolute_enthalpy_for_roundoff_bound(self):
        state = _state(enthalpy=np.array([1e12, 1.0, -1e12, 1.0]))
        result, states = _fixture(cpu=state, gpu=copy.deepcopy(state))
        integral = math.fsum(map(float, state["enthalpy_J_m3"])) * state["cell_volume_m3"]
        result["energyBalance"]["stored_J"] = integral
        item = result["gpuPilot"]["comparisons"]["stored_J"]
        item["cpu"] = item["gpu"] = integral
        item["relativeDifference"] = 0.0
        proof = validate_pilot_numerics(result, states, TARGETS)
        self.assertAlmostEqual(proof["states"]["gpu"]["integral_J"], 2e-18)

    def test_different_valid_mesh_and_step_sampling_remains_failed_without_norms(self):
        cpu = _state()
        gpu = _state(cells=3, steps=4, time_s=0.2, mesh_m=2e-6)
        result, states = _fixture(cpu=cpu, gpu=gpu)
        result["discretization"] = _disc(gpu, 2e-6)
        result["gpuPilot"]["cpu"]["discretization"] = _disc(cpu)
        sampling = result["gpuPilot"]["comparisons"]["finalSampling"]
        sampling.update(status="failed", gpuSteps=4, cellCount=4)
        result["gpuPilot"]["comparisons"]["finalTemperatureField"] = {
            "status": "failed", "reason": "Grid, accepted steps, or final sampling time differs"}
        field = result["gpuPilot"]["comparisons"]["finalTemperatureField"]
        field["reason"] = ""
        with self.assertRaisesRegex(ValueError, "without fabricated norms"):
            validate_pilot_numerics(result, states, TARGETS)
        field["reason"] = "Grid, accepted steps, or final sampling time differs"
        result["gpuFieldArtifacts"]["states"]["gpu"].update(
            cells=3, steps=4, cell_volume_m3=(2e-6) ** 3)
        result["gpuPilot"]["comparisons"]["stored_J"]["gpu"] = result["energyBalance"]["stored_J"] = (
            (2e-6) ** 3 * math.fsum(map(float, gpu["enthalpy_J_m3"])))
        result["gpuPilot"]["comparisons"]["stored_J"]["relativeDifference"] = abs(
            result["gpuPilot"]["comparisons"]["stored_J"]["cpu"]
            - result["gpuPilot"]["comparisons"]["stored_J"]["gpu"]
        ) / max(abs(result["gpuPilot"]["comparisons"]["stored_J"]["cpu"]), 1e-30)
        result["gpuPilot"]["comparisons"]["stored_J"]["status"] = "failed"
        result["gpuPilot"]["status"] = "failed"
        proof = validate_pilot_numerics(result, states, TARGETS)
        self.assertEqual(proof["status"], "failed")
        self.assertFalse(proof["samplingAligned"])
        self.assertFalse(proof["temperatureField"]["normsRecomputed"])

    def test_timestep_metadata_must_match_each_backend(self):
        result, states = _fixture()
        result["gpuPilot"]["cpu"]["discretization"]["minimumDt_s"] *= 1.1
        with self.assertRaisesRegex(ValueError, "minimumDt_s changed"):
            validate_pilot_numerics(result, states, TARGETS)

    def test_cpu_minimum_and_maximum_timestep_are_optional_if_absent(self):
        result, states = _fixture()
        cpu_disc = result["gpuPilot"]["cpu"]["discretization"]
        cpu_disc.pop("minimumDt_s")
        cpu_disc.pop("maximumDt_s")
        self.assertEqual(validate_pilot_numerics(result, states, TARGETS)["status"], "pass")

    def test_field_threshold_uses_integrity_checked_stored_norm_without_slack(self):
        baseline = np.full(20, 1300.0)
        cpu = _state(cells=20, temperatures=baseline)
        gpu = copy.deepcopy(cpu)
        gpu["temperature_K"][-1] = np.nextafter(1310.0, np.inf)
        result, states = _fixture(cpu=cpu, gpu=gpu)
        actual_difference = abs(states["gpu"]["temperature_K"][-1] - 1300.0)
        actual_l2 = actual_difference / np.sqrt(20.0 * 1000.0 ** 2)
        actual_max = actual_difference / 1000.0
        self.assertGreater(actual_max, TARGETS["fieldRiseMaxRelativeMax"])
        self.assertLess(actual_max - TARGETS["fieldRiseMaxRelativeMax"], 2.5e-16)
        field = result["gpuPilot"]["comparisons"]["finalTemperatureField"]
        field["relativeRiseL2"] = float(actual_l2)
        field["relativeRiseMax"] = TARGETS["fieldRiseMaxRelativeMax"]
        self.assertEqual(validate_pilot_numerics(result, states, TARGETS)["status"], "pass")

        field["relativeRiseMax"] = float(np.nextafter(
            TARGETS["fieldRiseMaxRelativeMax"], np.inf))
        field["status"] = "failed"
        result["gpuPilot"]["status"] = "failed"
        self.assertEqual(validate_pilot_numerics(result, states, TARGETS)["status"], "failed")

    def test_exact_threshold_and_signed_zero_geometry_statuses(self):
        result, states = _fixture()
        item = result["gpuPilot"]["comparisons"]["width_um"]
        item.update(cpu=100.0, gpu=101.0, absoluteDifference_um=1.0, status="pass")
        result["metrics"]["width_um"] = 101.0
        proof = validate_pilot_numerics(result, states, TARGETS)
        self.assertEqual(proof["scalarComparisons"]["width_um"]["status"], "pass")

        result, states = _fixture()
        for key in ("width_um", "depth_um", "length_um"):
            result["metrics"][key] = 0.0
            result["gpuPilot"]["comparisons"][key] = {
                "cpu": -0.0, "gpu": 0.0, "absoluteDifference_um": 0.0,
                "status": "inconclusive"}
        result["gpuPilot"]["status"] = "inconclusive"
        self.assertEqual(validate_pilot_numerics(result, states, TARGETS)["status"], "inconclusive")

    def test_nonfinite_and_unsupported_integral_underflow_are_rejected(self):
        result, states = _fixture()
        states["gpu"]["enthalpy_J_m3"][0] = np.inf
        with self.assertRaisesRegex(ValueError, "decoded enthalpy"):
            validate_pilot_numerics(result, states, TARGETS)

        tiny = float(np.nextafter(0.0, 1.0))
        state = _state(mesh_m=1e-3, enthalpy=np.full(4, tiny))
        result, states = _fixture(cpu=state, gpu=copy.deepcopy(state))
        with self.assertRaisesRegex(ValueError, "underflow"):
            validate_pilot_numerics(result, states, TARGETS)


if __name__ == "__main__":
    unittest.main()
