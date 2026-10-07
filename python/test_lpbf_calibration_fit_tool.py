"""End-to-end offline tests for tools/lpbf_calibration_fit.py on synthetic rows and an injected synthetic solver (no
dataset, no frozen-physics run, no GPU). HELD-OUT CALIBRATION OF NUISANCE PARAMETERS, NOT EXPERIMENTAL VALIDATION."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import calibration_synth_support as sy  # noqa: E402
import lpbf_calibration_config as C  # noqa: E402
import lpbf_calibration_fit as T  # noqa: E402
import lpbf_calibration_layer as layer  # noqa: E402
import lpbf_calibration_stats as st  # noqa: E402

REVISION = {"gitHead": "synthetic", "gitBranch": "synthetic", "dirtyTrackedPaths": 0, "python": "3"}
FP = "f" * 64


def run_doc(cache=None, loads=None):
    return T.build_document(False, 1, "2026-10-07", table_cache=cache, solver=sy.synth_solver(sy.DEFAULT_ETA),
                            rows_override=loads or {37.5: sy.synth_loads(37.5), 75.0: sy.synth_loads(75.0)},
                            fp_override=FP, revision=REVISION)


class FitToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._cfg = T.CFG
        T.CFG = sy.small_cfg(C.CALIBRATION_CONFIG)  # small bootstrap sizes only; every threshold is the production one
        cls.tmp = Path(tempfile.mkdtemp())
        cls.cache = cls.tmp / "table.json"
        cls.doc = json.loads(T.dump_json(run_doc(cls.cache)))

    @classmethod
    def tearDownClass(cls):
        T.CFG = cls._cfg

    def test_document_schema_statuses_and_evidence(self):
        d = self.doc
        self.assertEqual(d["schema"], C.SCORECARD_SCHEMA)
        self.assertEqual(d["evidence"]["kind"], "screening-only")
        self.assertEqual(d["evidence"]["labelPromotionProposed"], "none")
        self.assertFalse(d["evidence"]["experimentalValidation"])
        self.assertFalse(d["evidence"]["opticalOperatorMatched"])
        self.assertEqual(d["configSha256"], C.config_sha256(T.CFG))
        self.assertEqual(d["implementationHash"], FP)
        self.assertEqual(len(d["cells"]), 3 * 5 * 2)  # 3 kernels x (3 trainable alloys + 2 no-data alloys) x 2 quantities
        for c in d["cells"]:
            self.assertIn(c["status"], st.STATUSES)
        no_data = {(c["kernel"], c["material"]) for c in d["cells"] if c["status"] == "no-data"}
        self.assertEqual({m for _, m in no_data}, {"Inconel 718", "AlSi10Mg"})
        self.assertEqual(sum(d["gateSummary"].values()), len(d["cells"]))
        text = json.dumps(d)
        self.assertNotIn("Calibrated simulation", text)

    def test_catalog_sentinels_are_a_separate_test_only_block_with_n01_for_every_kernel(self):  # T-SENT-1
        s = self.doc["catalogSentinels"]
        self.assertIn("not blind", s["title"])
        self.assertEqual(sorted(n["kernel"] for n in s["n01"]), sorted(C.KERNELS))
        for n in s["n01"]:
            self.assertEqual(n["measured"]["depth_um"], 180.0)
            self.assertIn("not fitted", n["statement"])
            self.assertEqual(sorted(n["rungs"]), sorted(T.RUNG_LIST))
        roles = {x["source"]: x["role"] for x in self.doc["sources"]}
        for sid in C.CATALOG_SOURCES:
            self.assertIn("test-only", roles[sid])
        for c in self.doc["cells"]:
            self.assertFalse(set(c["trainSources"]) & set(C.CATALOG_SOURCES))

    def test_no_catalog_row_reaches_any_fit_or_s_source(self):  # T-LEAK-3
        seen = []
        original = st.fit_ladder

        def spy(fk, idx, *a, **k):
            seen.append({fk.sources[s] for s in set(fk.source_idx[idx].tolist())} | {r["rowId"] for r in (fk.rows[i] for i in idx) if r.get("catalog")})
            return original(fk, idx, *a, **k)

        st.fit_ladder = spy
        try:
            run_doc(None)
        finally:
            st.fit_ladder = original
        self.assertTrue(seen)
        banned = set(C.CATALOG_SOURCES) | {"guo-316l-n01"}
        for pool in seen:
            self.assertFalse(pool & banned, pool & banned)

    def test_unresolved_accounting_has_no_silent_drops(self):
        u = self.doc["unresolved"]
        self.assertTrue(u["perKernelSource"])
        for r in u["perKernelSource"]:
            self.assertEqual(r["resolvedAtDefault"] + r["unresolvedAtDefault"], r["rowsUsed"])
        self.assertTrue(any(x["role"] == "catalog-sentinel" for x in u["perKernelSource"]))
        self.assertIn("count as failures", u["rule"])

    def test_markdown_view_and_artefact(self):
        md = T.render_markdown(self.doc)
        for needle in ("Gate outcome", "Guo N01", "Screening only", "not validation", "Unresolved-row accounting",
                       "Regime confusion", "What this does not show", "label promotion proposed: **none**"):
            self.assertIn(needle, md)
        view = T.make_view(self.doc)
        self.assertEqual(view["schema"], C.SCORECARD_VIEW_SCHEMA)
        self.assertEqual(len(view["headline"]), len(self.doc["cells"]))
        raw = T.dump_json(self.doc)
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        art = T.build_artefact(self.doc, "docs/x.json", sha)
        self.assertTrue(T.verify_artefact_hash(art))
        self.assertFalse(set(art) - layer.ARTEFACT_KEYS)
        self.assertEqual(art["evidenceKind"], "screening-only")
        self.assertIsNone(art["proposedEvidenceKind"])
        self.assertEqual(art["scorecardSha256"], sha)
        self.assertEqual(art["configSha256"], C.config_sha256(T.CFG))
        self.assertIn("envelope", art)
        self.assertTrue(art["calibrationId"].endswith(art["contentSha256"][:12]))

    def test_check_detects_drift(self):
        root = Path(tempfile.mkdtemp())
        paths = T.write_all(self.doc, root)
        self.assertEqual(T.check_outputs(root, "2026-10-07"), [])
        md = paths["md"]
        md.write_text(md.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8", newline="\n")
        self.assertTrue(any("md" in p for p in T.check_outputs(root, "2026-10-07")))
        T.write_all(self.doc, root)
        self.assertEqual(T.check_outputs(root, "2026-10-07"), [])
        art = json.loads(paths["artefact"].read_text(encoding="utf-8"))
        art["cells"][0]["status"] = "enabled"
        paths["artefact"].write_text(T.dump_json(art), encoding="utf-8", newline="\n")
        self.assertTrue(any("artefact" in p for p in T.check_outputs(root, "2026-10-07")))
        T.write_all(self.doc, root)
        full = json.loads(paths["json"].read_text(encoding="utf-8"))
        full["cells"][0]["status"] = "enabled"
        paths["json"].write_text(T.dump_json(full), encoding="utf-8", newline="\n")
        self.assertTrue(T.check_outputs(root, "2026-10-07"))

    def test_double_run_is_byte_identical(self):  # T-DET-1
        a = run_doc(self.cache)  # second run reads the table cache written by the first
        b = run_doc(None)        # third computes the table again
        self.assertEqual(T.dump_json(a), T.dump_json(self.doc))
        self.assertEqual(T.dump_json(a), T.dump_json(b))
        r1, r2 = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        p1, p2 = T.write_all(a, r1), T.write_all(b, r2)
        for k in p1:
            self.assertEqual(p1[k].read_bytes(), p2[k].read_bytes(), k)

    def test_cache_with_a_different_fingerprint_is_refused(self):
        with self.assertRaises(SystemExit) as cm:
            T.build_document(False, 1, "2026-10-07", table_cache=self.cache, solver=sy.synth_solver(sy.DEFAULT_ETA),
                             rows_override={37.5: sy.synth_loads(37.5), 75.0: sy.synth_loads(75.0)},
                             fp_override="e" * 64, revision=REVISION)
        self.assertIn("refused", str(cm.exception))

    def test_quick_mode_refuses_to_overwrite_records(self):
        with self.assertRaises(SystemExit):
            T.main(["--quick"])


class TableTests(unittest.TestCase):
    def test_table_values_are_rounded_and_unresolved_nodes_are_counted(self):
        def solver(args, kernel, eta):
            e = 0.42 if eta is None else eta
            status = "computed" if e >= 0.3 else "heuristic-width-fallback"
            return 123.456789 * e, 98.7654321 * e, status

        row = sy.synth_rows("hofmann-316l-2026", "316L Stainless Steel", 3, 0.5, 0.5, 0.42, seed=1)[0]
        nodes = T.node_grid([0.42])
        table = T.build_table({T.input_key(row): T.input_args(row)}, ["eagar-tsai"], nodes, 1, solver)
        e = table["entries"][T.input_key(row)]["eagar-tsai"]
        self.assertEqual(len(e["W"]), len(nodes))
        self.assertEqual(e["W"][nodes.index(0.5)], st.round_sig(123.456789 * 0.5, 6))
        statuses = [table["statuses"][i] for i in e["s"]]
        self.assertEqual(statuses.count("heuristic-width-fallback"), sum(1 for n in nodes if n < 0.3))
        table["implementationHash"] = FP
        table["kernels"] = ["eagar-tsai"]
        # a node pair with a non-computed status makes the interpolated eta unresolved
        T_kernels = T.KERNELS
        try:
            T.KERNELS = ("eagar-tsai",)
            fk = T.fine_kernel([row], "eagar-tsai", table)
        finally:
            T.KERNELS = T_kernels
        self.assertFalse(fk.ok[0, fk.eta < 0.30 - 1e-9].any())
        self.assertTrue(fk.ok[0, fk.eta >= 0.30].all())
        self.assertTrue(fk.defOk[0])
        self.assertEqual(fk.default_status, ["computed"])

    def test_config_defaults_match_the_synthetic_fixture_assumptions(self):
        self.assertEqual(sorted(C.CALIBRATION_CONFIG["materialDefaults"]), sorted(sy.DEFAULT_ETA))
        self.assertEqual(C.config_sha256(C.CALIBRATION_CONFIG), C.config_sha256(json.loads(json.dumps(C.CALIBRATION_CONFIG))))


if __name__ == "__main__":
    unittest.main()
