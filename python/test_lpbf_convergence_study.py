"""Focused checks for frozen CPU numerical convergence reporting."""

import copy
import unittest
from unittest.mock import patch

from lpbf_convergence_study import ACCEPTANCE, study
from lpbf_verification import convergence


CASE = {"mode": "standard", "backend": "reference", "material": "Inconel 718",
        "power_W": 40, "mesh_um": 20, "maxDt_s": 1e-7,
        "trackLength_um": 200, "cooling_s": .0001, "dwell_s": 0}


def fake_solver(payload):
    mesh = payload["mesh_um"]
    dt = payload["maxDt_s"]
    index = ({80: 0, 40: 1, 20: 2}[mesh] if dt == CASE["maxDt_s"]
             else {4e-7: 0, 2e-7: 1, 1e-7: 2}[dt])
    width = [120., 105., 101.25][index]
    depth = [60., 52.5, 50.625][index]
    return {"effectiveMode": "standard", "solver": {"id": "enthalpy-fv-6", "version": "enthalpy-fv-6"},
            "coreContract": {"modelId": (
                                 "stationary-enthalpy-conduction-layer-conforming-v1"
                                 if payload.get("powderGridPolicy") == "layer-conforming"
                                 else "stationary-enthalpy-conduction-v1"),
                             "actualBackend": "numpy-reference", "solverId": "enthalpy-fv-6"},
            "discretization": {"mesh_m": mesh * 1e-6, "cells": 1000,
                               "meanDt_s": dt, "minimumDt_s": dt, "steps": 50},
            "energyBalance": {"input_J": 1., "losses_J": .2, "stored_J": .8},
            "metrics": {"width_um": width, "depth_um": depth, "peakTemperature_K": 2000.},
            "material": {"name": "Inconel 718", "materialId": "in718",
                         "materialRevisionSha256": "a" * 64, "version": "materials-1"},
            "provenance": {"inputHash": "input", "implementationHash": "code"}}


class ConvergenceStudy(unittest.TestCase):
    def test_roundoff_plateau_is_not_a_converging_width_trend(self):
        # Real 80 W IN718 mesh pilot: the finest width differs only by roundoff.
        widths = [73.33333333333331, 48.88888888888889, 48.88888888888887]
        spacings = [36.666666666666664e-6, 24.444444444444443e-6,
                    16.296296296296294e-6]
        self.assertEqual(convergence(widths, spacings)["status"], "inconclusive")
        self.assertEqual(convergence([120., 105., 101.25], [4., 2., 1.])["status"],
                         "numerically-converging")

    def test_two_independent_axes_and_frozen_targets(self):
        original = copy.deepcopy(CASE)
        with patch("lpbf_convergence_study.run", side_effect=fake_solver) as solver:
            report = study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["status"], "pass")
        self.assertFalse(report["experimentalValidation"])
        self.assertEqual(report["acceptance"], ACCEPTANCE)
        self.assertEqual(CASE, original)
        self.assertEqual([call.args[0]["mesh_um"] for call in solver.call_args_list[:3]], [80, 40, 20])
        self.assertEqual([call.args[0]["maxDt_s"] for call in solver.call_args_list[:3]], [1e-7] * 3)
        self.assertEqual([call.args[0]["mesh_um"] for call in solver.call_args_list[3:]], [20] * 3)
        self.assertEqual([call.args[0]["maxDt_s"] for call in solver.call_args_list[3:]], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["meshStudy"]["levels"][0]["material"]["materialId"], "in718")
        self.assertEqual(report["meshStudy"]["levels"][0]["model"]["actualBackend"], "numpy-reference")
        self.assertEqual(report["meshStudy"]["assessment"]["metrics"]["width_um"]["convergence"]["status"], "numerically-converging")

    def test_layer_conforming_model_is_accepted_only_under_its_own_identity(self):
        with patch("lpbf_convergence_study.run", side_effect=fake_solver):
            report = study({**CASE, "powderGridPolicy": "layer-conforming"},
                           [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["meshStudy"]["levels"][0]["model"]["modelId"],
                         "stationary-enthalpy-conduction-layer-conforming-v1")

    def test_flat_geometry_is_inconclusive(self):
        def flat(payload):
            result = fake_solver(payload)
            result["metrics"]["width_um"] = 100.
            return result
        with patch("lpbf_convergence_study.run", side_effect=flat):
            report = study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["meshStudy"]["assessment"]["metrics"]["width_um"]["status"], "inconclusive")

    def test_large_finest_change_fails(self):
        def drift(payload):
            result = fake_solver(payload)
            if payload["mesh_um"] == 20 and payload["maxDt_s"] == 1e-7:
                result["metrics"]["depth_um"] = 40.
            return result
        with patch("lpbf_convergence_study.run", side_effect=drift):
            report = study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["status"], "failed")
        self.assertGreater(report["meshStudy"]["assessment"]["metrics"]["depth_um"]["finestPairRelativeChange"], .05)

    def test_run_failure_remains_visible(self):
        def broken(payload):
            if payload["mesh_um"] == 40:
                raise ValueError("layer unresolved")
            return fake_solver(payload)
        with patch("lpbf_convergence_study.run", side_effect=broken):
            report = study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["meshStudy"]["assessment"]["status"], "failed")
        self.assertIn("layer unresolved", report["meshStudy"]["levels"][1]["reason"])

    def test_actual_resolution_and_energy_gate(self):
        def capped(payload):
            result = fake_solver(payload)
            if payload["maxDt_s"] == 2e-7:
                result["discretization"]["meanDt_s"] = 4e-7
            if payload["mesh_um"] == 40:
                result["energyBalance"]["stored_J"] = .7
            return result
        with patch("lpbf_convergence_study.run", side_effect=capped):
            report = study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["meshStudy"]["assessment"]["energyStatus"], "failed")
        self.assertEqual(report["timestepStudy"]["assessment"]["status"], "inconclusive")
        self.assertIn("Actual resolution", report["timestepStudy"]["assessment"]["reason"])

    def test_nonconstant_actual_ratio_is_inconclusive(self):
        def uneven(payload):
            result = fake_solver(payload)
            if payload["mesh_um"] == 40:
                result["discretization"]["mesh_m"] = 45e-6
            return result
        with patch("lpbf_convergence_study.run", side_effect=uneven):
            report = study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["meshStudy"]["assessment"]["status"], "inconclusive")
        self.assertIn("constant refinement ratio",
                      report["meshStudy"]["assessment"]["metrics"]["width_um"]["reason"])

    def test_backend_and_material_revision_consistency(self):
        def drift(payload):
            result = fake_solver(payload)
            if payload["mesh_um"] == 40:
                result["material"]["materialRevisionSha256"] = "b" * 64
            return result
        with patch("lpbf_convergence_study.run", side_effect=drift):
            report = study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["meshStudy"]["assessment"]["status"], "failed")
        self.assertIn("material revision", report["meshStudy"]["assessment"]["reason"])

        def wrong_backend(payload):
            result = fake_solver(payload)
            result["coreContract"]["actualBackend"] = "openfoam-thermal"
            return result
        with patch("lpbf_convergence_study.run", side_effect=wrong_backend):
            report = study(CASE, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        self.assertEqual(report["status"], "failed")
        self.assertIn("CPU transient reference backend", report["meshStudy"]["levels"][0]["reason"])

    def test_rejects_non_reference_or_invalid_levels(self):
        for scenario in ({**CASE, "backend": "auto"}, {**CASE, "mode": "screening"},
                         {**CASE, "measurements": []}):
            with self.assertRaises(ValueError):
                study(scenario, [80, 40, 20], [4e-7, 2e-7, 1e-7])
        for levels in ([40, 20], [20, 40, 10], [80, 80, 20]):
            with self.assertRaises(ValueError):
                study(CASE, levels, [4e-7, 2e-7, 1e-7])


if __name__ == "__main__":
    unittest.main()
