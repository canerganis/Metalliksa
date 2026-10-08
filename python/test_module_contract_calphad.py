"""Bounded contract checks against the rendered route inventory and Python authority."""
from pathlib import Path
import ast
import inspect
import re
import unittest
from unittest.mock import patch

import calphad_solver
from module_contract import contract_from_dict
from module_contracts_calphad import build_calphad_contract
from module_registry import load_seed, contract_ref_problems

ROOT = Path(__file__).resolve().parent.parent


def product_source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def ts_return_keys(source):
    """Read keys at the top level of the final TS return literal, not nested keys."""
    block = source.rsplit("return {", 1)[1]
    depth = 0
    keys = set()
    for line in block.splitlines():
        if depth == 0:
            match = re.match(r"\s*(\w+)\s*(?::|,)", line)
            if match:
                keys.add(match.group(1))
        depth += line.count("{") - line.count("}")
        if depth < 0:
            break
    return keys


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
        })
        database = self.operations["calphad-databases"]
        self.assertEqual((database.method, database.route, database.authority.script,
                          database.authority.timeout_ms, database.authority.warm),
                         ("GET", "/api/python/calphad-databases", "python/calphad_solver.py", 15000, True))
        minimize = self.operations["calphad-minimize"]
        self.assertEqual((minimize.method, minimize.route, minimize.authority.timeout_ms),
                         ("POST", "/api/python/calphad-minimize", 240000))
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
        self.assertIn("max(0.05 degC, requested value)", fields["minRefineStep"].note)
        self.assertFalse(self.operations["client-screening"].input[0].default)
        self.assertIn("Python request failure does not enter this path",
                      self.operations["client-screening"].input[0].note)
        self.assertTrue(all(field.min is None and field.max is None
                            for field in self.operations["client-screening"].input[1:]))
        self.assertIn("Al 400–750 degC", " ".join(field.note for field in op.input))

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
        self.assertFalse(set(result) - set(solver_contract.output.fields))
        self.assertIn(result["databaseStatus"], {"assessment", "test-fixture"})
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["unavailableKind"], "pycalphad-not-installed")
        self.assertEqual(result["temperatureRangeC"], [200, 1800])
        self.assertEqual(result["temperatureStepC"], 5)
        self.assertNotIn("equilibriumProfile", result)
        self.assertNotIn("criticalTemperatures", result)
        self.assertNotIn("evidenceStatus", result)

    def test_scalar_provenance_and_scheil_statuses_are_real_transport_values(self):
        output = self.operations["calphad-minimize"].output
        transport = dict(output.transport_values)
        self.assertEqual(set(transport["databaseStatus"]),
                         {"assessment", "test-fixture", "user-supplied"})
        self.assertEqual(set(transport["multiElementScheilStatus"]),
                         {"pycalphad-scheil-gulliver", "incomplete", "unavailable"})
        # Exercise the real formatting path with a deliberately unavailable path;
        # this checks transport/absence semantics, not a numerical oracle.
        points, block, rows = calphad_solver._scheil_outputs(
            None, "contract transport test", {"Ni": 100}, "test label", ["NI"])
        self.assertEqual(points, [])
        self.assertIn(block["status"], transport["multiElementScheilStatus"])
        self.assertIsNone(rows[0]["partitionCoefficient_k"])
        self.assertEqual(self.contract.evidence.emits, ())
        # Synthetic formatter inputs cover complete/incomplete branches without
        # running equilibrium or claiming a thermodynamic numerical oracle.
        path = dict(points=[dict(fractionSolid=0.0, temperatureC=900,
                                liquidX={}, solidX={}, solidPhases=[])],
                    firstAppearance={}, terminationReason="temperature-floor",
                    terminalTemperatureC=900, terminalBracketC=None,
                    remainingLiquidFraction=1.0, stepC=5, steps=1, phaseAmounts={},
                    clampedSteps=0, massBalanceMaxAbsError=0.0, elapsedMs=0.0)
        for state, expected in (("complete", "pycalphad-scheil-gulliver"),
                                ("incomplete", "incomplete")):
            _, formatted, _ = calphad_solver._scheil_outputs(
                {**path, "status": state}, None, {"Ni": 100}, "synthetic formatter", ["NI"])
            self.assertEqual(formatted["status"], expected)
            self.assertIn(formatted["status"], transport["multiElementScheilStatus"])

    def test_actual_critical_temperature_map_is_structured_and_numbers_remain_unavailable(self):
        values, statuses = calphad_solver.derive_critical_temperatures([], None, None, None, None)
        self.assertTrue(values)
        self.assertEqual(set(values), set(statuses))
        self.assertTrue(all(value is None for value in values.values()))
        for field, entry in statuses.items():
            with self.subTest(field=field):
                self.assertIsInstance(entry, dict)
                self.assertEqual(entry["status"], "unavailable")
                self.assertTrue(entry["reason"])
        output = self.operations["calphad-minimize"].output
        self.assertIn("criticalTemperatureStatus", output.fields)
        self.assertNotIn("criticalTemperatureStatus", dict(output.transport_values))
        leaves = dict(dict(output.transport_objects)["criticalTemperatureStatus"])
        self.assertEqual(set(leaves), {f"{field}.status" for field in statuses})
        for field, entry in statuses.items():
            self.assertIn(entry["status"], leaves[f"{field}.status"])
        self.assertIn("per-temperature object map", " ".join(self.contract.legacy_notes))

    def test_success_output_inventory_covers_literal_python_return(self):
        tree = ast.parse(inspect.getsource(calphad_solver._solve_with_runner))
        returns = [node.value for node in ast.walk(tree)
                   if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)]
        successful = [value for value in returns
                      if any(isinstance(key, ast.Constant) and key.value == "criticalTemperatureStatus"
                             for key in value.keys)]
        self.assertEqual(len(successful), 1)
        keys = {key.value for key in successful[0].keys if isinstance(key, ast.Constant)}
        self.assertFalse(keys - set(self.operations["calphad-minimize"].output.fields))

    def test_client_output_inventory_covers_actual_solver_and_service_return(self):
        solver_keys = ts_return_keys(product_source("src/physics/calphadMultiComponentSolver.ts"))
        service = product_source("src/services/pythonComputationService.ts")
        service_block = service.split("// Client-side TypeScript Fallback", 1)[1].split(
            "async ", 1)[0]
        keys = solver_keys | ts_return_keys(service_block)
        self.assertTrue({"alloyName", "nominalComposition", "computeTimeMs",
                         "thermodynamicStabilityIndex", "tcpEmbrittlementRisk"} <= keys)
        self.assertFalse(keys - set(self.operations["client-screening"].output.fields))

    def test_lifecycle_records_actual_cleanup_and_client_model_selection_limits(self):
        notes = " ".join(self.contract.legacy_notes)
        studio = product_source("src/components/CALPHADMultiComponentStudio.tsx")
        self.assertIn("clearTimeout(timer)", studio)
        self.assertIn("controller.abort()", studio)
        self.assertIn("clearInterval(id)", studio)
        self.assertIn("80 ms", notes)
        self.assertIn("250 ms", notes)
        self.assertIn("no cleanup guard", notes)
        self.assertIn("PRELOADED_MULTI_COMPONENT_TDB[0]", notes)
        self.assertIn("500/1450/20", notes)


if __name__ == "__main__":
    unittest.main()
