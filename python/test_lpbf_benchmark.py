"""Offline tests for the open LPBF screening benchmark (python/lpbf_benchmark.py and
python/tools/lpbf_benchmark_score.py). SCREENING BENCHMARK, NOT VALIDATION.

No solver and no network: the kernel table is a stub built through the scorecard's own ``build_table`` with an
injected deterministic function; truth comes from the pinned dataset loaders (committed local tables).
"""

import copy
import json
import math
import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import lpbf_benchmark as bm  # noqa: E402
import lpbf_benchmark_score as cli  # noqa: E402
import lpbf_calibration_fit as fit  # noqa: E402
import lpbf_calibration_stats as st  # noqa: E402
import lpbf_public_datasets as pd  # noqa: E402
from lpbf_calibration_config import CATALOG_SOURCES, KERNELS, TRAINABLE_SOURCES  # noqa: E402

FP = "stub-implementation-fingerprint"
SCALE = {"rosenthal": 0.9, "eagar-tsai": 1.0, "goldak": 1.1}


def stub_solver(args, kernel, eta):
    material, P, v, d = args[0], args[1], args[2], args[3]
    w = SCALE[kernel] * 400.0 * math.sqrt(0.4 * P / v) * (d / 50.0) ** 0.3
    return w, 0.6 * w, "computed"


def stub_table(loaded, fp=FP):
    inputs = {fit.input_key(r): fit.input_args(r) for r in loaded["trainable"] + loaded["catalog"]}
    table = fit.build_table(inputs, KERNELS, [], 1, stub_solver, None)
    table["implementationHash"] = fp
    return table


def csv_for(rows, scale_w=1.0, scale_d=1.0, intervals=False, drop=()):
    cols = "row_id,width_um,depth_um" + (",width_lo90,width_hi90,depth_lo90,depth_hi90" if intervals else "")
    lines = [cols]
    for r in rows:
        if r["rowId"] in drop:
            continue
        w, d = r["width_um"] * scale_w, r["depth_um"] * scale_d
        line = f"{r['rowId']},{w!r},{d!r}"
        if intervals:
            line += f",{r['width_um']!r},{r['width_um']!r},{r['depth_um']!r},{r['depth_um']!r}"
        lines.append(line)
    return "\n".join(lines) + "\n"


META = {"name": "Test model", "version": "1.0", "author": "Tester", "description": "synthetic", "url": "example.org/x",
        "trainedOnSources": []}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = bm.load_truth()
        cls.table = stub_table(cls.loaded)
        cls.rows_t = bm._ordered(cls.loaded["trainable"], TRAINABLE_SOURCES)
        cls.rows_c = bm._ordered(cls.loaded["catalog"], CATALOG_SOURCES)
        cls.known = [r["rowId"] for r in cls.rows_t + cls.rows_c]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lpbf-bench-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        bm.export_inputs(self.tmp, self.loaded)

    def score(self, text, meta=None):
        return bm.score_submission(self.tmp, text.encode("utf-8"), meta or dict(META), self.table, FP, self.loaded)[1]

    @staticmethod
    def cell(doc, material, source, q):
        hits = [c for c in doc["entry"]["cells"] if (c["material"], c["heldOutSource"], c["quantity"]) == (material, source, q)]
        assert len(hits) == 1
        return hits[0]


class InputsAndManifestTests(Base):
    def test_inputs_file_has_no_width_or_depth(self):
        header = (bm.bench_dir(self.tmp) / bm.INPUTS_NAME).read_text(encoding="utf-8").splitlines()[0].split(",")
        self.assertEqual(header, ["row_id", "source", "material", "P", "v", "beam", "preheat", "layer", "hatch", "regime_class_input"])
        for name in (bm.INPUTS_NAME, bm.SENTINEL_NAME):
            head = (bm.bench_dir(self.tmp) / name).read_text(encoding="utf-8").splitlines()[0].lower()
            self.assertNotIn("width", head)
            self.assertNotIn("depth", head)
        manifest = json.loads((bm.bench_dir(self.tmp) / bm.MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(manifest["truthColumnsInInputs"], [])
        # the published rows carry exactly the input columns (a numeric coincidence with a measured value is not a leak)
        import csv as _csv
        with open(bm.bench_dir(self.tmp) / bm.INPUTS_NAME, encoding="utf-8", newline="") as fh:
            for rec in _csv.DictReader(fh):
                self.assertEqual(list(rec), list(bm.INPUT_COLUMNS))

    def test_manifest_shas_equal_the_loader_pins(self):
        manifest = json.loads((bm.bench_dir(self.tmp) / bm.MANIFEST_NAME).read_text(encoding="utf-8"))
        prov = self.loaded["provenance"]
        for s in TRAINABLE_SOURCES:
            self.assertEqual(manifest["tableSha256"][s], prov[s]["tableSha256"])
        self.assertEqual(manifest["tableSha256"]["hofmann-316l-2026"], pd.HOFMANN_TABLE_SHA256)
        self.assertEqual(manifest["tableSha256"]["totis-ti64-2021"], pd.TOTIS_TABLE_SHA256)
        self.assertEqual(manifest["tableSha256"]["ku-leuven-316l-2021"], pd.KU_WAVE2_TABLE_SHA256)
        self.assertEqual(manifest["tableSha256"]["ku-leuven-ti64-2021"], pd.KU_WAVE2_TABLE_SHA256)
        self.assertEqual(manifest["tableSha256"]["lane-in625-2020"], pd.LANE_TRACKS_TABLE_SHA256)
        self.assertEqual(sum(manifest["rowsPerSource"].values()), len(self.rows_t))
        self.assertEqual(manifest["configSha256"], fit.config_sha256())

    def test_committed_inputs_match_the_loaders(self):
        self.assertEqual(bm.export_inputs(bm.REPO_ROOT, self.loaded, check=True), [])

    def test_sentinels_are_a_separate_file(self):
        sent_ids = {r["rowId"] for r in self.rows_c}
        train_ids = {r["rowId"] for r in self.rows_t}
        self.assertFalse(sent_ids & train_ids)
        self.assertEqual({r["source"] for r in self.rows_c}, set(CATALOG_SOURCES))
        text = (bm.bench_dir(self.tmp) / bm.INPUTS_NAME).read_text(encoding="utf-8")
        for sid in sent_ids:
            self.assertNotIn(sid, text)

    def test_manifest_drift_is_refused(self):
        (bm.bench_dir(self.tmp) / bm.INPUTS_NAME).write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(bm.BenchmarkError):
            bm.verify_manifest(self.tmp, self.loaded)


class SubmissionTests(Base):
    def test_perfect_submission_has_zero_mape_and_full_coverage(self):
        doc = self.score(csv_for(self.rows_t + self.rows_c, intervals=True))
        scored = [c for c in doc["entry"]["cells"] if c["status"] == "scored"]
        self.assertEqual(len(scored), len({(r["material"], r["source"]) for r in self.rows_t}) * 2)
        for c in scored:
            self.assertEqual(c["mapePct"], 0.0)
            self.assertEqual(c["meanAbsLn"], 0.0)
            self.assertEqual(c["unresolved"], 0)
            self.assertEqual(c["mapeUnresolvedAsFailPct"], 0.0)
            self.assertEqual(c["coverage90"]["coverage"], 1.0)
            self.assertEqual(c["skill"], 1.0)
        for c in doc["entry"]["sentinels"]:
            self.assertEqual(c["mapePct"], 0.0)
        self.assertEqual(doc["entry"]["provenance"]["rowsSubmitted"], len(self.known))

    def test_scaled_submission_error_is_exact(self):
        doc = self.score(csv_for(self.rows_t + self.rows_c, scale_w=1.1, scale_d=0.8))
        c = self.cell(doc, "Inconel 625", "lane-in625-2020", "width")
        self.assertAlmostEqual(c["mapePct"], 10.0, places=6)
        self.assertAlmostEqual(c["meanAbsLn"], math.log(1.1), places=9)
        c = self.cell(doc, "Inconel 625", "lane-in625-2020", "depth")
        self.assertAlmostEqual(c["mapePct"], 20.0, places=6)
        self.assertIsNone(c["coverage90"])

    def test_missing_rows_count_as_unresolved(self):
        lane = [r["rowId"] for r in self.rows_t if r["source"] == "lane-in625-2020"]
        drop = set(lane[:5])
        doc = self.score(csv_for(self.rows_t + self.rows_c, drop=drop))
        c = self.cell(doc, "Inconel 625", "lane-in625-2020", "width")
        self.assertEqual(c["unresolved"], 5)
        self.assertEqual(c["nResolved"], len(lane) - 5)
        self.assertEqual(c["nRows"], len(lane))
        self.assertAlmostEqual(c["mapeUnresolvedAsFailPct"], 100.0 * 5 / len(lane), places=6)
        self.assertEqual(c["mapePct"], 0.0)  # MAPE of the resolved rows only; the failure is reported next to it
        whole = self.score("row_id,width_um,depth_um\n")
        c0 = self.cell(whole, "Inconel 625", "lane-in625-2020", "width")
        self.assertEqual(c0["unresolved"], len(lane))
        self.assertIsNone(c0["mapePct"])
        self.assertEqual(c0["mapeUnresolvedAsFailPct"], 100.0)
        self.assertIsNone(c0["skill"])

    def test_blank_value_is_unresolved_not_an_error(self):
        first = self.rows_t[0]["rowId"]
        text = f"row_id,width_um,depth_um\n{first},,{self.rows_t[0]['depth_um']!r}\n"
        doc = self.score(text)
        c = self.cell(doc, self.rows_t[0]["material"], self.rows_t[0]["source"], "width")
        self.assertEqual(c["nResolved"], 0)

    def test_trained_on_source_is_excluded_and_marked(self):
        meta = dict(META, trainedOnSources=["hofmann-316l-2026"])
        doc = self.score(csv_for(self.rows_t + self.rows_c), meta)
        for q in ("width", "depth"):
            c = self.cell(doc, "316L Stainless Steel", "hofmann-316l-2026", q)
            self.assertEqual(c["status"], "excluded-trained-on")
            self.assertNotIn("mapePct", c)
            self.assertIn("not held out", c["reason"])
            ok = self.cell(doc, "316L Stainless Steel", "ku-leuven-316l-2021", q)
            self.assertEqual(ok["status"], "scored")
        self.assertEqual(doc["entry"]["trainedOnSources"], ["hofmann-316l-2026"])
        guo = self.score(csv_for(self.rows_t + self.rows_c), dict(META, trainedOnSources=["guo-316l-2024"]))
        self.assertTrue(any(c["status"] == "excluded-trained-on" and c["heldOutSource"] == "guo-316l-2024" for c in guo["entry"]["sentinels"]))

    def test_unknown_trained_on_source_is_refused(self):
        with self.assertRaises(bm.BenchmarkError):
            self.score(csv_for(self.rows_t), dict(META, trainedOnSources=["not-a-source"]))

    def test_duplicate_ids_are_refused(self):
        text = csv_for(self.rows_t) + f"{self.rows_t[0]['rowId']},100.0,50.0\n"
        with self.assertRaisesRegex(bm.BenchmarkError, "duplicate"):
            self.score(text)

    def test_unknown_ids_and_bad_values_are_refused(self):
        rid = self.rows_t[0]["rowId"]
        for body, pattern in (("nope-1,1.0,1.0\n", "unknown row_id"), (f"{rid},-1.0,1.0\n", "positive"),
                              (f"{rid},0,1.0\n", "positive"), (f"{rid},nan,1.0\n", "positive"),
                              (f"{rid},inf,1.0\n", "positive"), (f"{rid},abc,1.0\n", "not a number")):
            with self.assertRaisesRegex(bm.BenchmarkError, pattern):
                self.score("row_id,width_um,depth_um\n" + body)
        with self.assertRaisesRegex(bm.BenchmarkError, "required column"):
            self.score("row_id,width_um\n")
        with self.assertRaisesRegex(bm.BenchmarkError, "together"):
            self.score("row_id,width_um,depth_um,width_lo90\n")
        with self.assertRaisesRegex(bm.BenchmarkError, "exceeds"):
            self.score(f"row_id,width_um,depth_um,width_lo90,width_hi90\n{rid},1,1,5,2\n")

    def test_meta_is_validated(self):
        for bad in ({k: v for k, v in META.items() if k != "name"}, dict(META, extra=1), dict(META, name=""),
                    dict(META, trainedOnSources="all"), dict(META, url="x" * 400)):
            with self.assertRaises(bm.BenchmarkError):
                self.score(csv_for(self.rows_t[:3]), bad)

    def test_skill_baseline_is_the_rosenthal_default(self):
        base = bm._default_arrays(self.table, self.rows_t, "rosenthal")
        lines = ["row_id,width_um,depth_um"] + [f"{r['rowId']},{w!r},{d!r}" for r, w, d in zip(self.rows_t, base["width"], base["depth"])]
        doc = self.score("\n".join(lines) + "\n")
        for c in doc["entry"]["cells"]:
            self.assertEqual(c["skill"], 0.0)
            self.assertEqual(c["skillCi95"], [0.0, 0.0])

    def test_matches_scorecard_statistics_primitives(self):
        doc = self.score(csv_for(self.rows_t + self.rows_c, scale_w=1.3))
        c = self.cell(doc, "316L Stainless Steel", "hofmann-316l-2026", "width")
        rows = [r for r in self.rows_t if r["source"] == "hofmann-316l-2026"]
        import numpy as np
        meas = np.array([r["width_um"] for r in rows])
        pred = meas * 1.3
        self.assertAlmostEqual(c["mapePct"], st.metrics(pred, meas, np.ones(len(rows), bool))["mapePct"], places=6)
        self.assertEqual(c["nSets"], len({st.set_key(r) for r in rows}))


class NoNetworkTests(Base):
    def test_no_socket_is_used(self):
        def boom(*a, **k):
            raise AssertionError("network access attempted")
        with mock.patch.object(socket, "socket", boom), mock.patch.object(socket, "create_connection", boom), \
                mock.patch.object(socket, "getaddrinfo", boom):
            self.score(csv_for(self.rows_t + self.rows_c))
            doc = bm.build_leaderboard(self.tmp, self.loaded, self.table, FP, "2026-10-07")
            self.assertEqual(len(doc["entries"]), 3)


class LeaderboardTests(Base):
    def build(self, date="2026-10-07"):
        return bm.build_leaderboard(self.tmp, self.loaded, self.table, FP, date)

    def test_builtin_aggregation_is_deterministic_and_check_mode_detects_drift(self):
        a, b = bm.dumps(self.build()), bm.dumps(self.build())
        self.assertEqual(a, b)
        doc = self.build()
        bm.write_leaderboard(self.tmp, doc)
        self.assertEqual(bm.check_leaderboard(self.tmp, self.loaded, FP), [])
        self.assertEqual(bm.check_leaderboard(self.tmp, self.loaded, FP, self.table), [])
        # a different implementation fingerprint: the record is stale
        self.assertEqual(len(bm.check_leaderboard(self.tmp, self.loaded, "another-fp")), 1)
        # hand-edited committed record
        p = bm.newest_leaderboard(self.tmp)
        edited = json.loads(p.read_text(encoding="utf-8"))
        edited["honesty"] = "edited"
        p.write_text(bm.dumps(edited), encoding="utf-8")
        self.assertTrue(bm.check_leaderboard(self.tmp, self.loaded, FP))
        # a hand-edited built-in number is only visible when the kernel table is supplied (stated in the docs)
        edited = json.loads(bm.dumps(doc))
        edited["entries"][0]["cells"][0]["mapePct"] = 0.123
        p.write_text(bm.dumps(edited), encoding="utf-8")
        self.assertEqual(bm.check_leaderboard(self.tmp, self.loaded, FP), [])
        self.assertTrue(bm.check_leaderboard(self.tmp, self.loaded, FP, self.table))
        # a changed kernel table disagrees with the committed built-in entries
        bm.write_leaderboard(self.tmp, doc)
        other = copy.deepcopy(self.table)
        for per_k in other["entries"].values():
            per_k["goldak"]["dW"] *= 1.5
        self.assertTrue(bm.check_leaderboard(self.tmp, self.loaded, FP, other))

    def test_structure_has_three_builtin_kernels_and_no_calibrated_entry(self):
        doc = self.build()
        ids = [e["id"] for e in doc["entries"]]
        self.assertEqual(ids, [f"builtin:{k}" for k in sorted(KERNELS)])
        self.assertEqual(doc["calibratedRung"]["enabledCells"], 0)
        self.assertEqual(doc["evidence"]["kind"], "screening-only")
        self.assertEqual(doc["evidence"]["labelPromotionProposed"], "none")
        self.assertFalse(doc["evidence"]["experimentalValidation"])
        self.assertIn("never combined into one cross-material rank", doc["honesty"])
        for e in doc["entries"]:
            self.assertEqual(e["kind"], "built-in-kernel")
            self.assertEqual(e["trainedOnSources"], [])
            self.assertEqual(len(e["provenance"]["predictionsSha256"]), 64)
            self.assertTrue(all(c["status"] == "scored" for c in e["cells"]))
        ros = next(e for e in doc["entries"] if e["id"] == "builtin:rosenthal")
        self.assertTrue(all(c["skill"] == 0.0 for c in ros["cells"]))
        def keys(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    yield k
                    yield from keys(v)
            elif isinstance(o, list):
                for v in o:
                    yield from keys(v)
        self.assertFalse({"rank", "overallRank", "score"} & set(keys(doc)))

    def test_submissions_are_aggregated_and_stale_ones_refused(self):
        slug, sdoc = bm.score_submission(self.tmp, csv_for(self.rows_t + self.rows_c).encode(), dict(META), self.table, FP, self.loaded)
        bm.write_text(bm.bench_dir(self.tmp) / bm.SUBMISSIONS_DIR / f"{slug}.score.json", bm.dumps(sdoc))
        doc = self.build()
        self.assertEqual([e["kind"] for e in doc["entries"]], ["built-in-kernel"] * 3 + ["local-submission"])
        sub = doc["entries"][-1]
        self.assertEqual(sub["provenance"]["submissionCsvSha256"], bm.sha256_bytes(csv_for(self.rows_t + self.rows_c).encode()))
        with self.assertRaisesRegex(bm.BenchmarkError, "stale"):
            bm.build_leaderboard(self.tmp, self.loaded, self.table, "other-fp", "2026-10-07")

    def test_committed_record_is_current_when_present(self):
        p = bm.newest_leaderboard(bm.REPO_ROOT)
        if p is None:
            self.skipTest("no leaderboard record committed")
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], bm.LEADERBOARD_SCHEMA)
        self.assertEqual(doc["manifestSha256"], bm.sha256_text(bm.dumps(bm.build_inputs(self.loaded)[2])))
        self.assertEqual(doc["configSha256"], fit.config_sha256())
        self.assertEqual(doc["calibratedRung"]["enabledCells"], 0)
        import lpbf_simulation
        fp = lpbf_simulation.implementation_fingerprint()
        self.assertEqual(doc["implementationHash"], fp, "record is stale: kernels changed, regenerate the leaderboard")
        self.assertEqual(bm.check_leaderboard(bm.REPO_ROOT, self.loaded, fp), [])


class CliTests(Base):
    def test_score_and_builtin_commands_end_to_end(self):
        import lpbf_simulation
        fp = lpbf_simulation.implementation_fingerprint()
        cache = self.tmp / "table.json"
        cache.write_text(json.dumps(stub_table(self.loaded, fp)), encoding="utf-8")
        sub, meta = self.tmp / "s.csv", self.tmp / "s.json"
        sub.write_text(csv_for(self.rows_t + self.rows_c, scale_w=1.2), encoding="utf-8")
        meta.write_text(json.dumps(META), encoding="utf-8")
        common = ["--table-cache", str(cache), "--repo-root", str(self.tmp)]
        self.assertEqual(cli.main(["score", "--submission", str(sub), "--meta", str(meta)] + common), 0)
        out = bm.bench_dir(self.tmp) / bm.SUBMISSIONS_DIR / "test-model-1-0.score.json"
        self.assertTrue(out.is_file())
        self.assertEqual(cli.main(["builtin", "--date", "2026-10-07"] + common), 0)
        self.assertEqual(cli.main(["builtin", "--check"] + common), 0)
        self.assertEqual(cli.main(["builtin", "--check", "--repo-root", str(self.tmp)]), 0)
        sub.write_text("row_id,width_um,depth_um\nzzz,1,1\n", encoding="utf-8")
        self.assertEqual(cli.main(["score", "--submission", str(sub), "--meta", str(meta)] + common), 2)
        doc = json.loads(bm.newest_leaderboard(self.tmp).read_text(encoding="utf-8"))
        self.assertEqual(len(doc["entries"]), 4)

    def _env(self):
        import lpbf_simulation
        fp = lpbf_simulation.implementation_fingerprint()
        cache = self.tmp / "table.json"
        cache.write_text(json.dumps(stub_table(self.loaded, fp)), encoding="utf-8")
        meta = self.tmp / "s.json"
        meta.write_text(json.dumps(META), encoding="utf-8")
        return ["--table-cache", str(cache), "--repo-root", str(self.tmp)], meta

    def test_bom_csv_is_accepted(self):
        common, meta = self._env()
        sub = self.tmp / "s.csv"
        sub.write_bytes(b"\xef\xbb\xbf" + csv_for(self.rows_t + self.rows_c).encode("utf-8"))
        self.assertEqual(cli.main(["score", "--submission", str(sub), "--meta", str(meta)] + common), 0)

    def test_non_utf8_csv_and_bad_meta_are_refused_not_tracebacks(self):
        common, meta = self._env()
        sub = self.tmp / "s.csv"
        sub.write_bytes(b"row_id,width_um,depth_um\n\xff\xfe,1,1\n")
        self.assertEqual(cli.main(["score", "--submission", str(sub), "--meta", str(meta)] + common), 2)
        sub.write_text(csv_for(self.rows_t + self.rows_c), encoding="utf-8")
        meta.write_text("{not json", encoding="utf-8")
        self.assertEqual(cli.main(["score", "--submission", str(sub), "--meta", str(meta)] + common), 2)
        meta.write_bytes(b"\xff\xfe\x00")
        self.assertEqual(cli.main(["score", "--submission", str(sub), "--meta", str(meta)] + common), 2)

    def test_same_slug_different_submission_is_refused_unless_overwrite(self):
        common, meta = self._env()
        sub = self.tmp / "s.csv"
        base = ["score", "--submission", str(sub), "--meta", str(meta)] + common
        sub.write_text(csv_for(self.rows_t + self.rows_c, scale_w=1.2), encoding="utf-8")
        self.assertEqual(cli.main(base), 0)
        self.assertEqual(cli.main(base), 0, "re-scoring the identical file is idempotent")
        sub.write_text(csv_for(self.rows_t + self.rows_c, scale_w=1.3), encoding="utf-8")
        self.assertEqual(cli.main(base), 2)
        self.assertEqual(cli.main(base + ["--overwrite"]), 0)


if __name__ == "__main__":
    unittest.main()
