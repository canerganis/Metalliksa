"""Offline tests of tools/lpbf_calibration_fit_v2.py (calibration v2) on synthetic rows and an injected synthetic
solver, plus guards on the committed v2 record. No dataset solver run, no GPU.
HELD-OUT CALIBRATION OF NUISANCE PARAMETERS, NOT EXPERIMENTAL VALIDATION."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(PYTHON_DIR / "tools"))

import calibration_synth_support as sy  # noqa: E402
import lpbf_calibration_config as C1  # noqa: E402
import lpbf_calibration_config_v2 as V  # noqa: E402
import lpbf_calibration_fit as F  # noqa: E402
import lpbf_calibration_fit_v2 as T  # noqa: E402
import lpbf_calibration_layer as layer  # noqa: E402
import lpbf_calibration_stats as st  # noqa: E402

REPO_ROOT = PYTHON_DIR.parent
REVISION = {"gitHead": "synthetic", "gitBranch": "synthetic", "dirtyTrackedPaths": 0, "python": "3"}
PREREG = {"doc": V.PREREGISTRATION_DOC, "config": "python/lpbf_calibration_config_v2.py", "configCommit": "synthetic",
          "statement": "synthetic"}
FP = "f" * 64
SMALL_V2 = sy.small_cfg(V.CALIBRATION_CONFIG_V2)


def synth_test_only():
    m625, m316 = "Inconel 625", "316L Stainless Steel"
    rows = {"ghosh-in625-2018": {}, "trapp-316l-2017": {}}
    for spot in (140.0, 100.0):
        rr = sy.synth_rows("ghosh-in625-2018", m625, 7, 0.40, 0.30, 0.38, 0.1, -0.2, seed=11)
        for r in rr:
            r.update(beamDiameter_um=spot, testOnly=True, digitized=False)
        rows["ghosh-in625-2018"][f"{spot:g}"] = rr
    tr = sy.synth_rows("trapp-316l-2017", m316, 10, 0.55, 0.60, 0.42, -0.05, 0.15, seed=12)
    for r in tr:
        r.update(testOnly=True, digitized=True)
    rows["trapp-316l-2017"]["stated"] = tr
    prov = {s: {"doi": "10.0000/synthetic", "tableSha256": "0" * 64, "license": "synthetic", "citation": "synthetic",
                "loaderRows": 7 if s.startswith("ghosh") else 11, "loaderExcluded": [], "role": T.TEST_ONLY_ROLE}
            for s in rows}
    return {"rows": rows, "excluded": [], "provenance": prov}


def loads():
    return {37.5: sy.synth_loads(37.5), 75.0: sy.synth_loads(75.0)}


def run_v1_doc():
    saved = F.CFG
    F.CFG = sy.small_cfg(C1.CALIBRATION_CONFIG)
    try:
        return json.loads(F.dump_json(F.build_document(False, 1, "2026-10-07", solver=sy.synth_solver(sy.DEFAULT_ETA),
                                                       rows_override=loads(), fp_override=FP, revision=REVISION)))
    finally:
        F.CFG = saved


def v1_override(v1doc):
    return {"record": "docs/LPBF_CALIBRATION_SCORECARD_2026-10-07.json", "configSha256": v1doc["configSha256"],
            "calibrationId": "synthetic", "cells": {(c["kernel"], c["material"], c["quantity"]): c for c in v1doc["cells"]}}


def run_doc(v1=None, test=None):
    return T.build_document(False, 1, "2026-10-07", solver=sy.synth_solver(sy.DEFAULT_ETA), rows_override=loads(),
                            test_override=test or synth_test_only(), fp_override=FP, revision=REVISION,
                            v1_override=v1, prereg_override=PREREG, cfg=SMALL_V2)


class V2ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1doc = run_v1_doc()
        cls.doc = json.loads(F.dump_json(run_doc(v1_override(cls.v1doc))))

    def test_schema_evidence_and_config(self):
        d = self.doc
        self.assertEqual(d["schema"], V.SCORECARD_SCHEMA_V2)
        self.assertEqual(d["calibrationVersion"], "v2")
        self.assertEqual(d["configSha256"], C1.config_sha256(SMALL_V2))
        self.assertFalse(d["evidence"]["experimentalValidation"])
        self.assertEqual(d["evidence"]["labelPromotionProposed"], "none")
        self.assertEqual(len(d["cells"]), 3 * 5 * 2)

    def test_trainable_only_reproduces_v1(self):
        self.assertTrue(self.doc["reproducesV1TrainableOnly"])
        for x in self.doc["v1Comparison"]:
            self.assertEqual(x["v1"], x["v2TrainableOnly"])

    def test_test_only_rows_are_scored_never_trained(self):
        roles = {s["source"]: s["role"] for s in self.doc["sources"]}
        for sid in V.TEST_ONLY_SOURCES:
            self.assertEqual(roles[sid], T.TEST_ONLY_ROLE)
        seen = set()
        for c in self.doc["cells"]:
            self.assertFalse(set(c["trainSources"]) & set(V.TEST_ONLY_SOURCES))
            for r in c["p2"]:
                self.assertFalse(set(r["trainedOn"]) & set(V.TEST_ONLY_SOURCES))
                if r["role"] == "test-only":
                    seen.add((c["material"], r["heldOut"]))
                    self.assertEqual(sorted(r["trainedOn"]), sorted(c["trainSources"]))
        self.assertEqual(seen, {("Inconel 625", "ghosh-in625-2018"), ("316L Stainless Steel", "trapp-316l-2017")})

    def test_no_test_only_row_reaches_any_fit(self):
        seen = []
        original = st.fit_ladder

        def spy(fk, idx, *a, **k):
            seen.append({fk.sources[s] for s in set(fk.source_idx[idx].tolist())})
            return original(fk, idx, *a, **k)

        st.fit_ladder = spy
        try:
            run_doc()
        finally:
            st.fit_ladder = original
        self.assertTrue(seen)
        banned = set(V.TEST_ONLY_SOURCES) | set(C1.CATALOG_SOURCES)
        for pool in seen:
            self.assertFalse(pool & banned, pool & banned)

    def test_test_only_can_only_block(self):
        for c in self.doc["cells"]:
            if c["status"] == "enabled":
                self.assertEqual(c["statusTrainableOnly"], "enabled")
            if c["material"] == "Inconel 625" and c["status"] != "no-data":
                self.assertEqual(c["secondSourceCredit"], [])
                self.assertTrue(any("single source" in r for r in c["reasons"]) or c["status"] == "rejected")
                self.assertEqual(sorted(c["readingStatuses"]), ["ku37.5|ghosh100", "ku37.5|ghosh140"])

    def test_gate_rules_on_crafted_evidence(self):
        ok = {"noData": False, "hasSecondSource": True, "servedRung": "eta2", "flags": {}, "etaConsistent": True,
              "unresolvedWorse": False, "p1": [],
              "p2": [{"source": "a", "skillLb95": 0.05, "skill": 0.1, "coverage90N": 20, "coverage90WilsonUpper": 0.97,
                      "unresolvedRung": 0, "unresolvedDefault": 0},
                     {"source": "b", "skillLb95": 0.01, "skill": 0.1, "coverage90N": 20, "coverage90WilsonUpper": 0.97,
                      "unresolvedRung": 0, "unresolvedDefault": 0}]}
        self.assertEqual(T.v2_gate(ok, [])["status"], "enabled")
        bad = {"source": "trapp-316l-2017", "skillLb95": -0.3, "skill": -0.1, "coverage90N": 10,
               "coverage90WilsonUpper": 0.95, "unresolvedRung": 0, "unresolvedDefault": 0, "nRows": 10}
        g = T.v2_gate(ok, [bad])
        self.assertNotEqual(g["status"], "enabled")
        self.assertTrue(any("trapp-316l-2017" in r for r in g["reasons"]))
        good = dict(bad, skillLb95=0.1)
        self.assertEqual(T.v2_gate(ok, [good])["status"], "enabled")
        single = dict(ok, hasSecondSource=False, p2=[], p1=[{"source": "a", "lb": 0.1, "skill": 0.2}])
        g = T.v2_gate(single, [dict(good, source="ghosh-in625-2018", nRows=1000)])
        self.assertEqual(g["status"], "within-source-only")
        self.assertEqual(g["secondSourceCredit"], [])
        worse = dict(good, unresolvedRung=2)
        self.assertEqual(T.v2_gate(ok, [worse])["status"], "rejected")
        comb = T.combine_readings({"ku37.5|ghosh140": {"status": "enabled", "reasons": []},
                                   "ku37.5|ghosh100": {"status": "within-source-only", "reasons": ["x"]}}, "ku37.5|ghosh140")
        self.assertEqual(comb["status"], "rejected")
        self.assertIn("unresolvedInput", comb["reasons"][0])

    def test_foreign_rows_are_refused(self):
        test = synth_test_only()
        test["rows"]["trapp-316l-2017"]["stated"][0]["testOnly"] = False
        with self.assertRaises(AssertionError):
            run_doc(test=test)

    def test_envelope_block_and_outputs(self):
        rows = self.doc["absorptivityEnvelope"]["rows"]
        self.assertTrue(rows)
        self.assertEqual({r["material"] for r in rows}, {"316L Stainless Steel", "Ti-6Al-4V", "Inconel 625"})
        root = Path(tempfile.mkdtemp())
        paths = T.write_all(self.doc, root)
        self.assertEqual(T.check_outputs(root, "2026-10-07", SMALL_V2), [])
        self.assertFalse((root / C1.ARTEFACT_REL_PATH).exists(), "v2 must never write the v1 artefact")
        self.assertFalse((root / "docs" / "LPBF_CALIBRATION_SCORECARD_2026-10-07.json").exists())
        art = json.loads(paths["artefact"].read_text(encoding="utf-8"))
        self.assertTrue(T.verify_artefact_hash(art))
        self.assertIsNone(art["proposedEvidenceKind"])
        self.assertFalse(art["servedByRuntime"])
        self.assertFalse(art["experimentalValidation"])
        self.assertFalse({t["source"] for t in art["trainingData"]} & set(V.TEST_ONLY_SOURCES))
        md = paths["md"].read_text(encoding="utf-8")
        for needle in ("v1 -> v2 per cell", "Test-only held-out sources", "measured envelope", "label promotion proposed: **none**"):
            self.assertIn(needle, md)
        view = json.loads(paths["view"].read_text(encoding="utf-8"))
        self.assertEqual(view["schema"], C1.SCORECARD_VIEW_SCHEMA)
        self.assertEqual(view["calibrationVersion"], "v2")
        md_path = paths["md"]
        md_path.write_text(md + "\nedited\n", encoding="utf-8", newline="\n")
        self.assertTrue(any("md" in p for p in T.check_outputs(root, "2026-10-07", SMALL_V2)))
        T.write_all(self.doc, root)
        art["cells"][0]["status"] = "enabled"
        paths["artefact"].write_text(F.dump_json(art), encoding="utf-8", newline="\n")
        self.assertTrue(any("artefact" in p for p in T.check_outputs(root, "2026-10-07", SMALL_V2)))


class CommittedV2RecordTests(unittest.TestCase):
    """Guards on the committed v2 record (written by `npm run lpbf:calibration:v2`)."""

    @classmethod
    def setUpClass(cls):
        cls.art_path = REPO_ROOT / V.ARTEFACT_V2_REL_PATH
        if not cls.art_path.is_file():
            raise unittest.SkipTest("no committed v2 artefact")
        cls.art = json.loads(cls.art_path.read_text(encoding="utf-8"))
        cls.doc = json.loads((REPO_ROOT / cls.art["scorecardRecord"]).read_text(encoding="utf-8"))

    def test_record_verifies_and_uses_the_pre_registered_config(self):
        self.assertEqual(T.check_outputs(REPO_ROOT, self.art["generatedAt"]), [])
        self.assertEqual(self.art["configSha256"], V.config_v2_sha256())
        self.assertEqual(self.doc["config"], json.loads(json.dumps(V.CALIBRATION_CONFIG_V2)))
        self.assertFalse(self.doc["quick"])

    def test_honesty_and_roles(self):
        self.assertEqual(self.art["evidenceKind"], "screening-only")
        self.assertIsNone(self.art["proposedEvidenceKind"])
        self.assertFalse(self.art["experimentalValidation"])
        self.assertFalse(self.art["servedByRuntime"])
        self.assertEqual({t["source"] for t in self.art["trainingData"]}, set(C1.TRAINABLE_SOURCES))
        self.assertEqual({t["source"] for t in self.art["testOnlySources"]}, set(V.TEST_ONLY_SOURCES))
        self.assertTrue(self.doc["reproducesV1TrainableOnly"])
        for c in self.doc["cells"]:
            self.assertFalse(set(c["trainSources"]) & set(V.TEST_ONLY_SOURCES))
            if c["status"] == "enabled":
                self.assertEqual(c["statusTrainableOnly"], "enabled")

    def test_runtime_layer_refuses_the_v2_artefact(self):
        with self.assertRaises(layer.CalibrationError):
            layer.load_calibration(self.art_path, expected_impl_hash=self.art["implementationHash"])

    def test_v1_record_is_untouched(self):
        v1 = json.loads((REPO_ROOT / C1.ARTEFACT_REL_PATH).read_text(encoding="utf-8"))
        self.assertEqual(F.check_outputs(REPO_ROOT, v1["generatedAt"]), [])
        self.assertEqual(self.art["supersedes"]["configSha256"], v1["configSha256"])
        self.assertEqual(self.art["supersedes"]["calibrationId"], v1["calibrationId"])


if __name__ == "__main__":
    unittest.main()
