import json
import re
import unittest
from pathlib import Path

from module_contract import ContractError, ModuleContract, contract_from_dict
from module_contracts_electrochem import ELECTROCHEM_OPERATIONS, build_electrochem_contract


ROOT = Path(__file__).resolve().parents[1]


class ElectrochemContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = json.loads((ROOT / "python" / "module_registry_seed.json").read_text(encoding="utf-8"))
        cls.seed = next(row for row in rows if row["id"] == "electrochem-suite")
        cls.contract = build_electrochem_contract(cls.seed)
        cls.operations = {operation.id: operation for operation in ELECTROCHEM_OPERATIONS}

    def test_identity_round_trip_and_pending_evidence_ceiling(self):
        contract = self.contract
        self.assertIsInstance(contract, ModuleContract)
        self.assertEqual((contract.id, contract.workspace, contract.maturity),
                         ("electrochem-suite", "materials", "Research"))
        self.assertEqual(contract.seed_derived, ("label", "description", "next", "maturity"))
        self.assertEqual(contract.view.component, "src/components/CorrosionEngineeringLab.tsx")
        self.assertEqual(contract.migration_state, "contracted")
        self.assertEqual(contract.evidence.emits, ())
        self.assertEqual(contract.evidence.ceiling, "screening-only")
        self.assertEqual(contract.tests.oracle.status, "pending")
        self.assertTrue(any("Independent Pourbaix brute-force oracle" in note for note in contract.legacy_notes))
        self.assertEqual(contract_from_dict(contract.to_dict()).to_dict(), contract.to_dict())
        self.assertEqual(contract.lifecycle.resources, ("fetch",))
        self.assertEqual(contract.lifecycle.background_work, "none")

    def test_reachable_views_and_solver_routes_are_distinct_and_exact(self):
        self.assertEqual(set(self.operations), {
            "select-corrosion-view", "calculate-pren", "apply-pren-alloy-preset",
            "import-tafel-dataset", "estimate-tafel-locally", "export-tafel-csv",
            "copy-tafel-summary", "sync-tafel-to-digital-twin", "fit-tafel-python", "calculate-annual-corrosion-rate",
            "manage-pourbaix-test-points", "select-pourbaix-alloy-element", "set-pourbaix-overlay-display",
            "solve-pourbaix", "simulate-corrosion-eis",
        })
        self.assertEqual(self.operations["solve-pourbaix"].route, "/api/python/pourbaix-diagram")
        self.assertEqual(self.operations["solve-pourbaix"].method, "POST")
        self.assertEqual(self.operations["solve-pourbaix"].authority.kind, "python-ipc")
        self.assertEqual(self.operations["solve-pourbaix"].authority.script, "python/pourbaix_solver.py")
        self.assertEqual(self.operations["solve-pourbaix"].authority.timeout_ms, 25000)
        self.assertTrue(self.operations["solve-pourbaix"].authority.warm)
        for operation_id, script in (
            ("fit-tafel-python", "python/tafel_corrosion_rate_solver.py"),
            ("calculate-annual-corrosion-rate", "python/tafel_corrosion_rate_solver.py"),
            ("simulate-corrosion-eis", "python/battery_corrosion_eis_solver.py"),
        ):
            operation = self.operations[operation_id]
            self.assertEqual(operation.method, "POST")
            self.assertEqual(operation.authority.kind, "python-ipc")
            self.assertEqual(operation.authority.script, script)
            self.assertEqual(operation.authority.timeout_ms, 15000)
            self.assertTrue(operation.authority.warm)
        for operation_id in ("select-corrosion-view", "calculate-pren", "estimate-tafel-locally"):
            operation = self.operations[operation_id]
            self.assertIsNone(operation.route)
            self.assertEqual(operation.authority.kind, "browser-local")

    def test_real_solver_run_states_are_transport_not_evidence(self):
        for operation_id in ("calculate-annual-corrosion-rate", "simulate-corrosion-eis"):
            operation = self.operations[operation_id]
            self.assertIsNone(operation.output.status_key)
            self.assertIn("status", dict(operation.output.transport_values))
        self.assertIn("fitStatus", dict(self.operations["fit-tafel-python"].output.transport_values))
        self.assertIn("partial", dict(self.operations["simulate-corrosion-eis"].output.transport_values)["status"])
        self.assertIn("unavailable", dict(self.operations["calculate-annual-corrosion-rate"].output.transport_values)["status"])
        self.assertTrue(any("supported-25C-only" in note and "unavailable-no-sourced-epit" in note
                            for note in self.contract.legacy_notes))
        self.assertEqual(self.contract.evidence.emits, ())

    def test_activity_and_chloride_inputs_keep_the_actual_mapping_and_limits_unclaimed(self):
        pourbaix = {field.key: field for field in self.operations["solve-pourbaix"].input}
        self.assertEqual(pourbaix["temperature_C"].default, 25.0)
        self.assertIn("effectiveIonActivity", self.operations["solve-pourbaix"].undeclared_input)
        self.assertIn("experimentalPoints", self.operations["solve-pourbaix"].undeclared_input)
        self.assertIn("chlorideActivity", self.operations["solve-pourbaix"].undeclared_input)
        self.assertIsNone(pourbaix["temperature_C"].min)
        self.assertIsNone(pourbaix["temperature_C"].max)

    def test_contract_references_and_route_source_coupling_resolve(self):
        refs = self.contract.source_refs
        self.assertGreaterEqual(len(refs), 12)
        for ref in refs:
            match = re.fullmatch(r"([^:]+):(\d+)-(\d+)#(.+)", ref)
            self.assertIsNotNone(match, ref)
            rel, start, end, _label = match.groups()
            lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
            self.assertTrue(1 <= int(start) <= int(end) <= len(lines), ref)

        lab = (ROOT / "src/components/CorrosionEngineeringLab.tsx").read_text(encoding="utf-8")
        self.assertIn("<DynamicPourbaixStudio />", lab)
        self.assertIn("<CorrosionEISKineticsStudio />", lab)
        self.assertIn("<TafelPolarizationLab />", lab)
        self.assertIn('setActiveTab("pren")', lab)
        self.assertIn('setActiveTab("polarization")', lab)

        pourbaix = (ROOT / "src/components/DynamicPourbaixStudio.tsx").read_text(encoding="utf-8")
        self.assertIn('solvePourbaixDiagram(', pourbaix)
        self.assertIn("effectiveIonActivity", pourbaix)
        self.assertIn("signal.aborted", pourbaix)
        self.assertIn("chloride_ppm: Math.round(inputs.chlorideActivity * 35453)",
                      (ROOT / "src/utils/pourbaixRequest.ts").read_text(encoding="utf-8"))
        tafel = (ROOT / "src/utils/tafelPythonService.ts").read_text(encoding="utf-8")
        self.assertIn('action: "fit_curve"', tafel)
        self.assertIn("tryAutoFitTafel(", tafel)
        self.assertIn('"/api/python/tafel-corrosion-rate"', tafel)
        tafel_component = (ROOT / "src/components/TafelPolarizationLab.tsx").read_text(encoding="utf-8")
        self.assertNotIn("TAFEL_BENCHMARK_DATASETS", tafel_component)
        self.assertIn("No benchmark curves are bundled", tafel_component)
        self.assertIn("manualBetaA", tafel_component)
        self.assertIn("manualBetaC", tafel_component)
        eis = (ROOT / "src/components/CorrosionEISKineticsStudio.tsx").read_text(encoding="utf-8")
        self.assertIn('action: "corrosion_kinetics"', eis)
        self.assertNotIn("coatingType,", eis[eis.index("body: JSON.stringify({"):eis.index("}),\n      });")])
        characterization = (ROOT / "routes/characterization.ts").read_text(encoding="utf-8")
        self.assertIn('"python/tafel_corrosion_rate_solver.py"', characterization)
        self.assertIn('"python/battery_corrosion_eis_solver.py"', characterization)
        physics_route = (ROOT / "routes/physics.ts").read_text(encoding="utf-8")
        self.assertIn('"python/pourbaix_solver.py"', physics_route)

    def test_other_valid_module_identity_is_rejected(self):
        with self.assertRaises(ContractError):
            build_electrochem_contract({**self.seed, "id": "other-module"})


if __name__ == "__main__":
    unittest.main()
