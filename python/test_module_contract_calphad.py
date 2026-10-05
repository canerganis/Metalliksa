"""Bounded contract checks against the rendered route inventory and Python authority."""
import unittest
from unittest.mock import patch

import calphad_solver
from module_contract import contract_from_dict
from module_contracts_calphad import build_calphad_contract
from module_registry import load_seed, contract_ref_problems


class CalphadContractTests(unittest.TestCase):
    def setUp(self):
        self.seed = next(row for row in load_seed() if row["id"] == "phase-diagram")
        self.contract = build_calphad_contract(self.seed)
        self.operations = {op.id: op for op in self.contract.operations}

    def test_identity_round_trip_and_sources(self):
        original = dict(self.seed)
        self.assertEqual(self.contract.id, "phase-diagram")
        self.assertEqual(self.contract.view.component, "src/components/PhaseDiagramViewer.tsx")
        self.assertEqual(self.contract.view.export, "PhaseDiagramViewer")
        self.assertEqual(contract_from_dict(self.contract.to_dict()), self.contract)
        self.assertEqual(self.seed, original)
        self.assertEqual(contract_ref_problems(
            self.contract, generated=frozenset({"docs/modules/phase-diagram.md"})), [])
        with self.assertRaises(ValueError):
            build_calphad_contract({**self.seed, "id": "composition"})

    def test_actual_independent_operations_and_deadlines(self):
        self.assertEqual(set(self.operations), {
            "calphad-databases", "calphad-minimize", "client-screening",
            "binary-browser-analysis", "ai-consult",
        })
        database = self.operations["calphad-databases"]
        self.assertEqual((database.method, database.route, database.authority.script,
                          database.authority.timeout_ms, database.authority.warm),
                         ("GET", "/api/python/calphad-databases", "python/calphad_solver.py", 15000, True))
        minimize = self.operations["calphad-minimize"]
        self.assertEqual((minimize.method, minimize.route, minimize.authority.timeout_ms),
                         ("POST", "/api/python/calphad-minimize", 40000))
        self.assertEqual(self.operations["ai-consult"].authority.timeout_ms, 60000)
        self.assertEqual(self.contract.lifecycle.background_work, "none")
        self.assertEqual(set(self.contract.lifecycle.resources), {"fetch", "interval"})

    def test_dynamic_payloads_and_temperature_window_is_not_a_backend_bound(self):
        op = self.operations["calphad-minimize"]
        self.assertEqual({field.key for field in op.input}, {
            "tMin", "tMax", "tStep", "unit", "adaptiveGrid", "boundaryRefinement", "minRefineStep",
        })
        self.assertEqual(set(op.undeclared_input), {"name", "elements", "databaseId", "customTdbText", "supersedeKey"})
        fields = {field.key: field for field in op.input}
        self.assertEqual((fields["tMin"].default, fields["tMax"].default, fields["tStep"].default),
                         (500.0, 1450.0, 20.0))
        self.assertEqual((fields["tMin"].min, fields["tMin"].max,
                          fields["tMax"].min, fields["tMax"].max,
                          fields["tStep"].min, fields["tStep"].max,
                          fields["minRefineStep"].min, fields["minRefineStep"].max),
                         (None, None, None, None, None, None, None, None))
        self.assertEqual((fields["adaptiveGrid"].value_type, fields["adaptiveGrid"].default), ("boolean", False))
        self.assertEqual((fields["boundaryRefinement"].value_type, fields["boundaryRefinement"].default),
                         ("boolean", True))
        # These are valid direct solver inputs despite lying outside the UI's
        # element-selected windows and tolerance dropdown options.
        self.assertEqual(op.input_problems({
            "tMin": 200.0, "tMax": 1800.0, "tStep": 5.0, "unit": "wt_pct",
            "adaptiveGrid": False, "boundaryRefinement": True, "minRefineStep": 0.1,
        }), [])
        self.assertIn("not restricted to those options", fields["minRefineStep"].note)
        self.assertIn("max(0.05 °C, requested value)", fields["minRefineStep"].note)
        self.assertFalse(self.operations["client-screening"].input[0].default)
        self.assertIn("Python request failure does not enter this path",
                      self.operations["client-screening"].input[0].note)
        self.assertTrue(all(field.min is None and field.max is None
                            for field in self.operations["client-screening"].input[1:]))
        self.assertIn("Al 400–750 °C", " ".join(field.note for field in op.input))

    def test_transport_status_is_not_emitted_evidence(self):
        op = self.operations["calphad-minimize"]
        self.assertIsNone(op.output.status_key)
        self.assertEqual(dict(op.output.transport_values)["status"], ("unavailable",))
        self.assertEqual(self.contract.evidence.emits, ())
        self.assertEqual(self.contract.tests.oracle.status, "pending")
        self.assertEqual(self.contract.evidence.ceiling, "screening-only")
        self.assertIn("explicitly", " ".join(self.contract.legacy_notes))
        self.assertIn("not the fallback for failure", " ".join(self.contract.legacy_notes))

    def test_real_database_inventory_and_missing_pycalphad_envelope(self):
        db_result = calphad_solver.list_available_databases()
        db_contract = self.operations["calphad-databases"]
        self.assertFalse(set(db_result) - set(db_contract.output.fields))
        self.assertIsInstance(db_result["databases"], list)
        self.assertIsInstance(db_result["systemCoverage"], list)

        with patch.object(calphad_solver, "PYCALPHAD_AVAILABLE", False):
            result = calphad_solver.compute_multi_component_equilibrium(
                name="contract availability path", elements={"Ni": 80, "Al": 20},
                unit="wt_pct", t_min_c=200, t_max_c=1800, t_step_c=5,
                database_id="alni_dupin_2001",
                adaptive_grid=False, boundary_refinement=True, min_refine_step_c=0.5,
            )
        solver_contract = self.operations["calphad-minimize"]
        # This nested provenance state is intentionally outside OutputSchema: its
        # values are assessment/test-fixture, not the SDK's available/unavailable transport pair.
        self.assertEqual(set(result) - set(solver_contract.output.fields), {"databaseStatus"})
        self.assertIn(result["databaseStatus"], {"assessment", "test-fixture"})
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["unavailableKind"], "pycalphad-not-installed")
        self.assertEqual(result["temperatureRangeC"], [200, 1800])
        self.assertEqual(result["temperatureStepC"], 5)
        self.assertNotIn("equilibriumProfile", result)
        self.assertNotIn("criticalTemperatures", result)
        self.assertNotIn("evidenceStatus", result)


if __name__ == "__main__":
    unittest.main()
