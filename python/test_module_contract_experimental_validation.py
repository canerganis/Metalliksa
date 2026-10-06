"""Source-linked checks for the experimental measurement comparison contract."""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

import module_contract as mc
import module_registry as mr
from module_contracts_experimental_validation import (
    MEASUREMENT_ROUTE,
    build_experimental_validation_contract,
)


ROOT = Path(__file__).resolve().parent.parent


def read_source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class ExperimentalValidationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seeds = json.loads((ROOT / "python" / "module_registry_seed.json").read_text(encoding="utf-8"))
        cls.seed = next(row for row in seeds if row["id"] == "experimental-validation")
        cls.contract = build_experimental_validation_contract(cls.seed)
        cls.operations = {operation.id: operation for operation in cls.contract.operations}

    def test_seed_view_and_actual_measurement_route_are_exact(self):
        contract = self.contract
        self.assertEqual(contract.id, "experimental-validation")
        self.assertEqual(contract.workspace, "lpbf")
        self.assertEqual(contract.view.component, "src/components/ExperimentalValidationLab.tsx")
        self.assertEqual(contract.view.export, "ExperimentalValidationLab")
        self.assertEqual(contract.seed_derived, ("label", "description", "next", "maturity"))

        load = self.operations["load-cmu-ti64-measurements"]
        self.assertEqual((load.method, load.route), ("GET", MEASUREMENT_ROUTE))
        self.assertEqual(load.authority.kind, "node-provider")
        self.assertIsNone(load.authority.timeout_ms)
        self.assertEqual(load.input, ())  # Fixed dataset URL; the UI exposes no selector.
        route = read_source("routes/lpbfSources.ts")
        service = read_source("server/lpbfSourceArchiveService.ts")
        client = read_source("src/services/lpbfSourceService.ts")
        self.assertIn("router.get(`${prefix}/:datasetId/measurements`, handle(req => service.measurements(req.params.datasetId)))", route)
        self.assertIn("/api/lpbf/sources/${encodeURIComponent(datasetId)}/measurements", client)
        self.assertIn("sourceMeasurements('cmu-ti64-meltpool-v1', controller.signal)", read_source("src/components/ExperimentalValidationLab.tsx"))
        self.assertIn("if (!current) throw new LpbfSourceArchiveError(404, 'Source dataset has not been imported.')", service)
        self.assertIn("return { datasetId, scope: CMU_MT_SCOPE, data: parseCmuMeasurementsCsv(csv) };", service)
        self.assertIn("return { datasetId, data: [] };", service)

    def test_builder_rejects_a_different_seed_identity(self):
        with self.assertRaisesRegex(ValueError, "canonical module identity"):
            build_experimental_validation_contract({**self.seed, "id": "some-other-module"})

    def test_response_shape_and_plotted_measurement_fields_follow_sources(self):
        load = self.operations["load-cmu-ti64-measurements"]
        self.assertEqual(set(load.output.fields), {"datasetId", "scope", "data", "error"})
        self.assertIsNone(load.output.status_key)
        service = read_source("server/lpbfSourceArchiveService.ts")
        parser = read_source("server/cmuMeasurements.ts")
        for key in ("slice", "orientation", "power_W", "velocity_mms", "width_um", "depth_um", "cap_um"):
            self.assertRegex(parser, rf"\b{key}: ")
        self.assertIn("raw/MTMeasurements.csv", service)
        self.assertIn("multi-track-powder-entrained", parser)
        view = read_source("src/components/ExperimentalValidationLab.tsx")
        self.assertNotIn("d.power_W === 370", view)  # no client power filter
        self.assertIn("dataKey=\"velocity_mms\"", view)
        self.assertIn("setData(res.data)", view)
        self.assertIn("unresolved.join", view)
        self.assertIn("unit=\" mm/s\"", view)
        self.assertIn("unit=\" µm\"", view)
        self.assertNotIn("citation", view)
        self.assertNotIn("sha256", view)
        self.assertNotIn("provenance", service[service.index("  measurements(datasetId: string)"):])

    def test_local_overlay_is_a_stored_job_juxtaposition_not_a_validation_metric(self):
        render = self.operations["render-measurement-comparison"]
        self.assertIsNone(render.route)
        self.assertEqual(render.authority.kind, "browser-local")
        self.assertEqual(set(render.undeclared_input), {"measurementData", "job"})
        self.assertEqual(
            set(render.output.fields),
            {
                "widthSeries", "remeltDepthSeries", "perVelocityAggregates", "overlayGate",
                "simulationReferenceDots", "widthResidual", "remeltDepthContext",
                "unresolvedScope", "loadingMessage", "emptyMessage", "errorMessage",
            },
        )
        view = read_source("src/components/ExperimentalValidationLab.tsx")
        store = read_source("src/store/useLpbfEngineeringStore.ts")
        self.assertIn("const job = useLpbfEngineeringStore(state => state.job)", view)
        self.assertIn("const simResult = job?.result?.metrics", view)
        self.assertIn("const simInput = job?.result?.settings", view)
        self.assertIn("const gate = overlayGate(simInput)", view)
        self.assertIn("residualAt(aggregates, simInput?.speed_mm_s, simResult)", view)
        helper = read_source("src/utils/experimentalValidation.ts")
        self.assertIn("material: 'ti6al4v'", helper)
        self.assertIn("power_W: 370", helper)
        self.assertIn("beamDiameter_um: 100", helper)
        self.assertIn("x={simInput.speed_mm_s} y={simResult.width_um}", view)
        self.assertIn("x={simInput.speed_mm_s} y={simResult.depth_um}", view)
        self.assertIn("job: SimulationJob | undefined", store)
        notes = " ".join(self.contract.legacy_notes)
        for limitation in ("overlayGate", "result freshness/signature", "juxtaposition", "not calculated agreement", "quantity definitions differ", "no interpolation"):
            self.assertIn(limitation, notes)
        self.assertEqual(self.contract.evidence.emits, ())
        self.assertEqual(self.contract.evidence.ceiling, "screening-only")
        self.assertEqual(self.contract.tests.oracle.status, "pending")
        self.assertIn("No independent oracle", self.contract.evidence.note)

    def test_fetch_lifecycle_failure_and_empty_success_are_not_conflated_in_contract(self):
        load = self.operations["load-cmu-ti64-measurements"]
        self.assertEqual(self.contract.lifecycle.background_work, "none")
        self.assertEqual(self.contract.lifecycle.resources, ("fetch",))
        self.assertEqual(self.contract.migration_state, "legacy")  # No source-declared deadline to satisfy routed contract gate.
        client = read_source("src/services/lpbfSourceService.ts")
        view = read_source("src/components/ExperimentalValidationLab.tsx")
        route = read_source("routes/lpbfSources.ts")
        self.assertIn("{ signal, cache: 'no-store' }", client)
        self.assertIn("return () => controller.abort()", view)
        self.assertNotRegex(client, re.compile(r"AbortSignal\.timeout|setTimeout|timeoutMs"))
        # A not-imported 404 is its own error; every other failure keeps its message (or the generic one).
        self.assertIn("if (response.status === 404 && message === 'Source dataset has not been imported.') throw new SourceNotImportedError(datasetId);", client)
        self.assertIn("throw new Error(message || 'Failed to load experimental measurements');", client)
        self.assertIn("catch (error) {", route)
        self.assertIn("res.status(503).json({ error:", route)
        self.assertIn("!loaded", view)
        self.assertIn("data.length === 0", view)
        self.assertIn("No measurement rows were returned", view)
        self.assertIn("Loading experimental data...", view)
        self.assertNotIn("Retry", view)
        notes = " ".join(self.contract.legacy_notes)
        self.assertIn("No request deadline", notes)
        self.assertIn("explicit empty message", notes)
        self.assertNotIn("indefinitely", notes)
        self.assertIn("without a retry control", notes)
        self.assertTrue(load.route.startswith("/api/lpbf/sources/"))

    def test_references_round_trip_and_existing_regression_tests_are_linked(self):
        self.assertEqual(mc.contract_from_dict(self.contract.to_dict()), self.contract)
        self.assertEqual(mr.contract_ref_problems(self.contract, root=ROOT), [])
        refs = set(self.contract.source_refs)
        self.assertTrue({
            "tests/lpbf-source-api.test.ts",
            "tests/lpbf-experimental-evidence.test.tsx",
            "tests/lpbf-experimental-validation-logic.test.ts",
            "src/utils/experimentalValidation.ts",
            "server/cmuMeasurements.ts",
            "tests/lpbf-phase4-e2e.test.ts",
            "docs/MODULE_EVIDENCE_INVENTORY.md",
        } <= refs)
        evidence_test = read_source("tests/lpbf-experimental-evidence.test.tsx")
        e2e_test = read_source("tests/lpbf-phase4-e2e.test.ts")
        inventory = read_source("docs/MODULE_EVIDENCE_INVENTORY.md")
        self.assertIn("ExperimentalValidationLab", evidence_test)
        self.assertIn("sourceService.measurements(datasetId)", e2e_test)
        self.assertIn("GET /api/lpbf/sources/:datasetId/measurements", inventory)
        self.assertIn("no model-vs-experiment qualification", inventory)


if __name__ == "__main__":
    unittest.main()
