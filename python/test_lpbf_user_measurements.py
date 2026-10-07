"""Offline tests for the user-measurement import and the additive scorecard user-source hook (synthetic rows, injected
solver, no dataset, no frozen-physics run). The user's own data is labelled 'Measured (user-supplied)'; the scorecard
evidence stays screening-only."""

import csv
import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_DIR))
sys.path.append(str(PYTHON_DIR / "tools"))  # appended: tools/lpbf_next_experiment.py must not shadow the module

import calibration_synth_support as sy  # noqa: E402
import lpbf_calibration_config as C  # noqa: E402
import lpbf_calibration_fit as T  # noqa: E402
import lpbf_next_experiment as ne  # noqa: E402
import lpbf_user_measurements as um  # noqa: E402

MATERIAL = "316L Stainless Steel"
REPO_ROOT = PYTHON_DIR.parent
REVISION = {"gitHead": "synthetic", "gitBranch": "synthetic", "dirtyTrackedPaths": 0, "python": "3"}
FP = "f" * 64


def stub_solver(args, kernel, eta):
    P, v = args[1], args[2]
    w = 800.0 * math.sqrt(P / v)
    return w * {"eagar-tsai": 1.0, "goldak": 1.2, "rosenthal": 0.9}[kernel], 0.5 * w, "computed"


def make_plan(n=6):
    return ne.plan_experiment(
        {"material": MATERIAL, "power_W": [100.0, 400.0], "speed_mm_s": [400.0, 1600.0], "spots_um": [100.0],
         "layer_um": 40.0, "preheat_C": 80.0, "n": n, "seed": 1, "plate": {"x_mm": 150.0, "y_mm": 100.0}, "grid": 5},
        calibration=None, solver_call=stub_solver, training_loader=lambda m: [], regime_fn=lambda *a: "conduction")


def fill_template(plan_dir, widths=None, depths=None, drop=()):
    """Read measurement_template.csv, fill widths/depths (unless dropped) and return (path, rows)."""
    tpl = plan_dir / "measurement_template.csv"
    rows = list(csv.DictReader(io.StringIO(tpl.read_text(encoding="utf-8"))))
    for i, r in enumerate(rows):
        if r["track_id"] in drop:
            continue
        r["width_um"] = repr(100.0 + 5 * i) if widths is None else widths[i]
        r["depth_um"] = repr(50.0 + 2 * i) if depths is None else depths[i]
    out = plan_dir / "filled.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return out, rows


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.plan = make_plan()
        ne.write_outputs(self.plan, self.tmp)
        self.root = self.tmp / "uc"

    def imp(self, csv_path, sid="user-round-trip", **kw):
        return um.import_measurements(self.tmp / "plan.json", csv_path, sid, out_root=self.root, **kw)

    def test_round_trip_plan_to_template_to_import(self):
        filled, rows = fill_template(self.tmp)
        doc = self.imp(filled)
        self.assertEqual(doc["nRows"], 6)
        self.assertEqual(doc["nExcluded"], 0)
        on_disk = json.loads((self.root / "user-round-trip" / "rows.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk, doc)
        by_id = {p["trackId"]: p for p in self.plan["points"]}
        for r in doc["rows"]:
            p = by_id[r["trackId"]]
            self.assertEqual((r["power_W"], r["speed_mm_s"], r["beamDiameter_um"]),
                             (p["power_W"], p["speed_mm_s"], p["beamDiameter_um"]))
            self.assertEqual(r["material"], MATERIAL)
            self.assertEqual(r["source"], "user-round-trip")
            self.assertIs(r["catalog"], False)
        self.assertEqual(doc["evidenceKind"], "screening-only")
        self.assertEqual(len(doc["provenance"]["planSha256"]), 64)
        again = um.load_user_rows(self.root / "user-round-trip" / "rows.json")
        self.assertEqual(again["sourceId"], "user-round-trip")

    def test_row_label_is_exactly_measured_user_supplied(self):
        doc = self.imp(fill_template(self.tmp)[0])
        self.assertEqual(um.ROW_LABEL, "Measured (user-supplied)")
        self.assertEqual(doc["label"], "Measured (user-supplied)")
        self.assertTrue(all(r["label"] == "Measured (user-supplied)" for r in doc["rows"]))

    def test_power_speed_or_spot_mismatch_is_rejected_and_nothing_is_written(self):
        filled, rows = fill_template(self.tmp)
        for col, bad in (("power_W", "999.0"), ("speed_mm_s", "1.0"), ("spot_um", "90.0")):
            text = filled.read_text(encoding="utf-8").splitlines()
            head = text[0].split(",")
            cells = text[1].split(",")
            cells[head.index(col)] = bad
            text[1] = ",".join(cells)
            bad_path = self.tmp / f"bad_{col}.csv"
            bad_path.write_text("\n".join(text) + "\n", encoding="utf-8")
            with self.assertRaises(um.UserMeasurementError) as cm:
                self.imp(bad_path, sid="user-mismatch")
            self.assertIn("differs from the plan", str(cm.exception))
        self.assertFalse((self.root / "user-mismatch").exists())

    def test_blank_rows_are_excluded_with_a_reason_and_never_imputed(self):
        drop = {self.plan["points"][0]["trackId"], self.plan["points"][3]["trackId"]}
        filled, _ = fill_template(self.tmp, drop=drop)
        doc = self.imp(filled, sid="user-blanks")
        self.assertEqual(doc["nRows"], 4)
        self.assertEqual({e["trackId"] for e in doc["excluded"]}, drop)
        for e in doc["excluded"]:
            self.assertIn("never imputed", e["reason"])
            self.assertIn("missing", e["reason"])
        self.assertFalse({r["trackId"] for r in doc["rows"]} & drop)
        # a half-filled row (width only) is excluded too
        rows = list(csv.DictReader(io.StringIO((self.tmp / "measurement_template.csv").read_text(encoding="utf-8"))))
        widths = ["100"] * len(rows)
        depths = ["50" if i != 1 else "" for i in range(len(rows))]
        half, _ = fill_template(self.tmp, widths=widths, depths=depths)
        doc2 = self.imp(half, sid="user-half")
        self.assertIn("missing depth_um", [e for e in doc2["excluded"] if e["trackId"] == rows[1]["track_id"]][0]["reason"])

    def test_non_positive_or_non_finite_width_is_refused(self):
        for bad in ("0", "-3", "nan", "inf", "abc"):
            widths = [bad] + ["100"] * 5
            filled, _ = fill_template(self.tmp, widths=widths, depths=["50"] * 6)
            with self.assertRaises(um.UserMeasurementError):
                self.imp(filled, sid="user-badnum")
        self.assertFalse((self.root / "user-badnum").exists())

    def test_all_blank_import_is_refused(self):
        with self.assertRaises(um.UserMeasurementError):
            self.imp(self.tmp / "measurement_template.csv", sid="user-allblank")

    def test_unknown_or_repeated_track_ids_are_refused(self):
        filled, rows = fill_template(self.tmp)
        text = filled.read_text(encoding="utf-8")
        dup = self.tmp / "dup.csv"
        dup.write_text(text + text.splitlines()[1] + "\n", encoding="utf-8")
        with self.assertRaises(um.UserMeasurementError):
            self.imp(dup, sid="user-dup")
        unk = self.tmp / "unk.csv"
        unk.write_text(text.replace("T01", "T99", 1), encoding="utf-8")
        with self.assertRaises(um.UserMeasurementError):
            self.imp(unk, sid="user-unk")

    def test_source_id_pattern_and_collisions_are_refused(self):
        filled, _ = fill_template(self.tmp)
        for bad in ("hofmann-316l-2026", "guo-316l-2024", "user-", "user-ab", "User-Abc", "user-" + "a" * 41,
                    "user-with space", "lane-in625-2020"):
            with self.assertRaises(um.UserMeasurementError):
                self.imp(filled, sid=bad)
        with self.assertRaises(um.UserMeasurementError):
            self.imp(filled, sid="user-taken", existing_sources=["user-taken"])
        self.imp(filled, sid="user-once")
        with self.assertRaises(um.UserMeasurementError) as cm:
            self.imp(filled, sid="user-once")
        self.assertIn("already exists", str(cm.exception))

    def test_cli_plan_and_import_paths(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("lpbf_next_experiment_cli", PYTHON_DIR / "tools" / "lpbf_next_experiment.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        filled, _ = fill_template(self.tmp)
        rc = cli.main(["import", "--plan", str(self.tmp / "plan.json"), "--measurements", str(filled),
                       "--source-id", "user-via-cli", "--out-root", str(self.root)])
        self.assertEqual(rc, 0)
        self.assertTrue((self.root / "user-via-cli" / "rows.json").is_file())
        self.assertEqual(cli.main(["import", "--plan", str(self.tmp / "plan.json"), "--measurements", str(filled),
                                   "--source-id", "hofmann-316l-2026", "--out-root", str(self.root)]), 2)
        for forbidden in (REPO_ROOT / "docs" / "x", REPO_ROOT / "data" / "calibration", REPO_ROOT):
            with self.assertRaises(SystemExit):
                cli.main(["plan", "--material", MATERIAL, "--power", "100", "400", "--speed", "400", "1600",
                          "--spots", "100", "--layer-um", "40", "--preheat-c", "80", "--n", "3", "--seed", "1",
                          "--plate-x-mm", "100", "--plate-y-mm", "100", "--out-dir", str(forbidden)])
        # no default plate size: the CLI refuses a plan without one (exit 2, nothing written)
        out = self.tmp / "noplate"
        self.assertEqual(cli.main(["plan", "--material", MATERIAL, "--power", "100", "400", "--speed", "400", "1600",
                                   "--spots", "100", "--layer-um", "40", "--preheat-c", "80", "--n", "3",
                                   "--seed", "1", "--out-dir", str(out)]), 2)
        self.assertFalse(out.exists())


# ---------------------------------------------------------------------------------------------
# scorecard hook (additive; every threshold, rung and interval rule is the production one)
# ---------------------------------------------------------------------------------------------
def user_doc(source_id="user-synth-a", n_sets=22, material=MATERIAL, seed=11):
    rows = sy.synth_rows(source_id, material, n_sets, 0.55, 0.50, 0.42, offset_w=0.03, seed=seed)
    return {"sourceId": source_id, "label": um.ROW_LABEL, "material": material, "nRows": len(rows), "nExcluded": 0,
            "provenance": {"statement": "synthetic fixture"}, "rows": rows}


def run_doc(user_sources=None):
    loads = {37.5: sy.synth_loads(37.5), 75.0: sy.synth_loads(75.0)}
    return T.build_document(False, 1, "2026-10-07", table_cache=None, solver=sy.synth_solver(sy.DEFAULT_ETA),
                            rows_override=loads, fp_override=FP, revision=REVISION, user_sources=user_sources)


class ScorecardHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._cfg = T.CFG
        T.CFG = sy.small_cfg(C.CALIBRATION_CONFIG)
        cls.plain = run_doc()
        cls.with_user = json.loads(T.dump_json(run_doc([user_doc()])))

    @classmethod
    def tearDownClass(cls):
        T.CFG = cls._cfg

    def test_no_flag_output_matches_the_pre_hook_golden_sha(self):
        # sha256 of dump_json(build_document(no user sources)) on the synthetic fixtures with tool.sha256 masked,
        # taken from the code at base b0dbdc59 (before the hook existed): the hook must not change it.
        d = json.loads(T.dump_json(self.plain))
        d["tool"]["sha256"] = "0" * 64
        import hashlib
        self.assertEqual(hashlib.sha256(T.dump_json(d).encode()).hexdigest(),
                         "5c6ac5fafd340983b5eecbb88d4c260d1911d9bf33665a248c6d33c4e0bf5e58")

    def test_no_flag_output_is_byte_identical(self):
        self.assertEqual(T.dump_json(run_doc()), T.dump_json(self.plain))
        self.assertEqual(T.dump_json(run_doc([])), T.dump_json(self.plain))
        self.assertNotIn("userSources", self.plain)
        self.assertEqual(self.plain["configSha256"], C.config_sha256(T.CFG))

    def test_committed_records_still_check_clean(self):
        T.CFG = self._cfg
        try:
            self.assertEqual(T.main(["--check"]), 0)
        finally:
            T.CFG = sy.small_cfg(C.CALIBRATION_CONFIG)

    def test_user_source_becomes_a_held_out_fold_and_never_a_sentinel(self):
        d = self.with_user
        sid = "user-synth-a"
        held = {r["heldOut"] for c in d["cells"] if c["material"] == MATERIAL for r in c["p2"]}
        self.assertIn(sid, held)
        self.assertTrue(any(sid in c["trainSources"] for c in d["cells"] if c["material"] == MATERIAL))
        roles = {s["source"]: s["role"] for s in d["sources"]}
        self.assertEqual(roles[sid], "trainable")
        self.assertNotIn(sid, json.dumps(d["catalogSentinels"]))
        self.assertEqual(d["config"]["dataRoles"]["userSources"], [sid])
        self.assertNotIn(sid, d["config"]["dataRoles"]["catalogSentinels"])
        self.assertEqual(d["userSources"][0]["source"], sid)
        self.assertEqual(d["userSources"][0]["label"], "Measured (user-supplied)")

    def test_new_config_sha_is_recorded_and_everything_else_is_unchanged(self):
        d = self.with_user
        want = C.config_sha256(C.config_with_user_sources(T.CFG, ["user-synth-a"]))
        self.assertEqual(d["configSha256"], want)
        self.assertNotEqual(d["configSha256"], self.plain["configSha256"])
        a, b = json.loads(json.dumps(d["config"])), json.loads(json.dumps(self.plain["config"]))
        for k in ("userSources", "userSourceNote"):
            a["dataRoles"].pop(k, None)
        a["dataRoles"]["trainable"] = [s for s in a["dataRoles"]["trainable"] if s != "user-synth-a"]
        self.assertEqual(a, b)  # thresholds, rungs, bootstrap, gate, intervals: identical
        self.assertEqual(d["evidence"]["kind"], "screening-only")
        self.assertEqual(d["evidence"]["labelPromotionProposed"], "none")
        md = T.render_markdown(d)
        self.assertIn("User-supplied sources (private run)", md)
        self.assertNotIn("User-supplied sources", T.render_markdown(json.loads(T.dump_json(self.plain))))

    def test_user_source_with_no_same_alloy_partner_is_refused(self):
        with self.assertRaises(SystemExit):
            run_doc([user_doc("user-orphan", material="AlSi10Mg")])

    def test_artefact_of_a_private_run_is_refused_by_the_runtime_loader(self):
        import hashlib
        import lpbf_calibration_layer as layer
        raw = T.dump_json(self.with_user)
        art = T.build_artefact(self.with_user, "docs/x.json", hashlib.sha256(raw.encode("utf-8")).hexdigest())
        self.assertEqual(art["configSha256"], self.with_user["configSha256"])
        p = Path(tempfile.mkdtemp()) / "a.json"
        p.write_text(T.dump_json(art), encoding="utf-8", newline="\n")
        with self.assertRaises(layer.CalibrationError):
            layer.load_calibration(p, expected_impl_hash=FP)

    def test_out_dir_refuses_record_locations_and_is_required(self):
        rows = Path(tempfile.mkdtemp()) / "rows.json"
        rows.write_text("{}", encoding="utf-8")
        for bad in (REPO_ROOT / "docs", REPO_ROOT / "docs" / "sub", REPO_ROOT / "data" / "calibration",
                    REPO_ROOT / "data" / "calibration" / "x", REPO_ROOT):
            with self.assertRaises(SystemExit) as cm:
                T.main(["--user-source", str(rows), "--out-dir", str(bad)])
            self.assertIn("committed record location", str(cm.exception), str(bad))
        with self.assertRaises(SystemExit) as cm:
            T.main(["--user-source", str(rows)])
        self.assertEqual(cm.exception.code, 2)
        with self.assertRaises(SystemExit):
            T.main(["--out-dir", str(Path(tempfile.mkdtemp()))])

    def test_config_helper_refuses_bad_or_colliding_ids(self):
        for bad in (["hofmann-316l-2026"], ["guo-316l-2024"], ["user-aa"], ["user-ok-1", "user-ok-1"], ["User-X"]):
            with self.assertRaises(ValueError):
                C.config_with_user_sources(C.CALIBRATION_CONFIG, bad)


if __name__ == "__main__":
    unittest.main()
