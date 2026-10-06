"""Wave 2 (2026-10-06) open LPBF datasets: hash pins, measured-columns-only parsing, citation fields,
missing-file behaviour, the comparison tool's wave2 block (build_wave2_block / wave2_limits / build_limits /
render_wave2_markdown) on three committed rows with the solver replaced by a fixed +10 % / -10 % stub, and the
committed 2026-10-06 record (which ships with this module: the record tests fail, not skip, when it is missing).

Fixtures: the four KU Leuven Figshare CSVs (CC0) are committed under
data/benchmark/ku-leuven-316l-ti64-2021/source/ with their SHA-256 pinned in lpbf_public_datasets.KU_WAVE2_FILES.
The Lane / NIST / Simonds tables are committed transcriptions (data/benchmark/*/LICENSE-ATTRIBUTION.md state
their origin); their source documents are not committed, so the rebuild-from-source tests skip with a reason
unless METALLIX_LPBF_WAVE2_SOURCE_DIR points at a folder holding them. No solver is run here.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import lpbf_public_datasets as pds  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RECORD = REPO / "docs" / "LPBF_DATASET_COMPARISON_2026-10-06.json"
SOURCE_DIR_ENV = "METALLIX_LPBF_WAVE2_SOURCE_DIR"
SOURCE_NAMES = {"lane": "pmc8194244.xml", "simonds": "pmc7047776.xml", "nist": "AMB2022-03_results_v1.0.pdf"}


def _processed_text(alloy):
    spec = next(s for s in pds.KU_WAVE2_FILES if s["alloy"] == alloy and s["role"] == "processed")
    return pds._ku_text((pds.KU_WAVE2_SOURCE_DIR / spec["file"]).read_bytes())


class KuLeuvenWave2Tests(unittest.TestCase):
    def test_committed_source_files_match_their_pins(self):
        hashes = pds.verify_ku_wave2_sources()
        self.assertEqual(len(hashes), 4)
        for spec in pds.KU_WAVE2_FILES:
            self.assertEqual(hashes[spec["file"]], spec["sha256"])
            self.assertTrue(spec["doi"].startswith("10.6084/m9.figshare."))
            self.assertTrue(spec["url"].startswith("https://ndownloader.figshare.com/files/"))

    def test_changed_source_file_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            for spec in pds.KU_WAVE2_FILES:
                (Path(td) / spec["file"]).write_bytes((pds.KU_WAVE2_SOURCE_DIR / spec["file"]).read_bytes())
            victim = Path(td) / pds.KU_WAVE2_FILES[1]["file"]
            victim.write_bytes(victim.read_bytes().replace(b"119,7142857", b"119,7142858"))
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                pds.verify_ku_wave2_sources(td)

    def test_missing_source_file_is_reported_not_skipped_silently(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                pds.verify_ku_wave2_sources(td)

    def test_processed_parser_reads_exp_columns_only(self):
        for alloy in ("316L", "Ti-6Al-4V"):
            text = _processed_text(alloy)
            parsed = pds.parse_ku_leuven_processed(text)
            self.assertIn("w model", parsed["excludedColumns"])
            self.assertIn("d model", parsed["excludedColumns"])
            self.assertIn("R model", parsed["excludedColumns"])
            keys = {k for r in parsed["rows"] for k in r}
            self.assertFalse(any("model" in k or "error" in k for k in keys), keys)
            # Overwrite every model/error cell with garbage: the parsed measured rows must not change.
            lines = text.splitlines()
            header = lines[0].split(";")
            model_idx = [i for i, h in enumerate(header) if "model" in h or "error" in h]
            mutated = [lines[0]]
            for line in lines[1:]:
                cells = line.split(";")
                if cells and cells[0].strip().isdigit():
                    for i in model_idx:
                        if i < len(cells):
                            cells[i] = "999999"
                mutated.append(";".join(cells))
            again = pds.parse_ku_leuven_processed("\n".join(mutated) + "\n")
            self.assertEqual(again["rows"], parsed["rows"])

    def test_processed_parser_rejects_a_file_without_model_columns(self):
        with self.assertRaisesRegex(ValueError, "no model/error columns"):
            pds.parse_ku_leuven_processed("Sample;P;v;w exp;d exp;R exp;melting regime\n1;100;400;1;1;1;keyhole\n")

    def test_316l_exp_values_are_the_raw_section_means(self):
        k = pds.load_ku_leuven_316l_ti64()
        table = pds._load_pinned_csv(pds.KU_WAVE2_TABLE, pds.KU_WAVE2_TABLE_SHA256, pds.KU_WAVE2_TABLE_COLUMNS, "t")
        for item in table:
            if item["alloy"] == "316L" and item["w_exp_um"]:
                self.assertAlmostEqual(float(item["w_exp_um"]), float(item["raw_mean_width_um"]), places=3)
                self.assertAlmostEqual(float(item["d_exp_um"]), float(item["raw_mean_depth_um"]), places=3)
        self.assertEqual(len(k["rows"]), 58)  # 44 of 48 316L conditions + 14 Ti-6Al-4V conditions
        self.assertEqual(sorted(x["rowId"] for x in k["provenance"]["notCompared"]),
                         ["ku-leuven-316l-2021-41", "ku-leuven-316l-2021-42", "ku-leuven-316l-2021-47",
                          "ku-leuven-316l-2021-48"])

    def test_table_rebuild_reproduces_the_pin(self):
        with tempfile.TemporaryDirectory() as td:
            digest = pds.build_ku_wave2_table(out=Path(td) / "conditions.csv")
        self.assertEqual(digest, pds.KU_WAVE2_TABLE_SHA256)

    def test_loader_rows_units_labels_and_unresolved_beam(self):
        k = pds.load_ku_leuven_316l_ti64()
        rows = k["rows"]
        self.assertEqual({r["dataset"] for r in rows}, {"ku-leuven-316l-2021", "ku-leuven-ti64-2021"})
        self.assertTrue(all(r["beamDiameter_um"] == 37.5 for r in rows))
        self.assertIn("unverified", k["provenance"]["beamDiameterStatus"])
        self.assertTrue(all(r["publishedRegime"] in ("conduction", "transition", "keyhole") for r in rows))
        first = next(r for r in rows if r["rowId"] == "ku-leuven-316l-2021-01")
        self.assertEqual((first["power_W"], first["speed_mm_s"], first["width_um"], first["depth_um"]),
                         (100.0, 400.0, 119.7142857, 129.2857143))
        ti = next(r for r in rows if r["rowId"] == "ku-leuven-ti64-2021-08")
        self.assertEqual((ti["power_W"], ti["speed_mm_s"], ti["width_um"], ti["depth_um"], ti["publishedRegime"]),
                         (200.0, 800.0, 123.29, 252.14, "keyhole"))
        self.assertEqual(k["provenance"]["license"], "CC0")
        self.assertEqual(k["provenance"]["fileSha256"], pds.KU_WAVE2_TABLE_SHA256)

    def test_changed_conditions_table_is_refused(self):
        original = pds.KU_WAVE2_TABLE
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "conditions.csv"
            path.write_bytes(original.read_bytes().replace(b"119.7142857", b"119.7142858"))
            pds.KU_WAVE2_TABLE = path
            try:
                with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                    pds.load_ku_leuven_316l_ti64()
            finally:
                pds.KU_WAVE2_TABLE = original


class LiteratureTableTests(unittest.TestCase):
    def test_lane_rows_flags_and_power_question(self):
        d = pds.load_lane_in625()
        rows = d["rows"]
        self.assertEqual(len(rows), 23)
        self.assertEqual(sum(r["machine"] == "CBM" for r in rows), 10)
        ammt = [r for r in rows if r["machine"] == "AMMT"]
        self.assertTrue(all(r["coolingRateUse"].startswith("do-not-use") for r in ammt))
        self.assertEqual({r["power_W"] for r in ammt}, {137.9, 179.2})
        self.assertEqual({r["power_W"] for r in pds.load_lane_in625(use_nominal_power=True)["rows"]
                          if r["machine"] == "AMMT"}, {150.0, 195.0})
        self.assertTrue(any("UNRESOLVED" in c for c in d["provenance"]["caveats"]))
        power_caveat = next(c for c in d["provenance"]["caveats"] if c.startswith("AMMT power"))
        self.assertIn("Fig. 2 caption: 'Laser power values indicated are the applied laser power'", power_caveat)
        self.assertIn("Fig. 2 image was not read", power_caveat)
        cbm3 = rows[0]
        self.assertEqual((cbm3["rowId"], cbm3["width_um"], cbm3["depth_um"], cbm3["beamDiameter_um"]),
                         ("lane-in625-cbm40-t03-A", 173.82, 154.4, 100.0))
        # Table 4 CBM class width/depth are the means of the Table 3 track means (consistency of the transcription)
        t4 = {c["class"]: c for c in d["provenance"]["table4"]}
        for case in "ABC":
            cbm = [r for r in rows if r["machine"] == "CBM" and r["case"] == case]
            self.assertAlmostEqual(sum(r["width_um"] for r in cbm) / len(cbm), float(t4[f"CBM-{case}"]["width_mean_um"]),
                                   delta=0.6)
            self.assertAlmostEqual(sum(r["depth_um"] for r in cbm) / len(cbm), float(t4[f"CBM-{case}"]["depth_mean_um"]),
                                   delta=0.6)

    def test_lane_table4_ammt_cooling_rates_are_flagged_do_not_use(self):
        d = pds.load_lane_in625()
        t4 = {c["class"]: c for c in d["provenance"]["table4"]}
        self.assertEqual(sorted(t4), ["AMMT-A", "AMMT-B", "AMMT-C", "CBM-A", "CBM-B", "CBM-C"])
        ammt20 = {r["case"]: r for r in pds._load_pinned_csv(pds.LANE_TRACKS_TABLE, pds.LANE_TRACKS_TABLE_SHA256,
                                                              pds.LANE_TRACK_COLUMNS, "t")
                  if r["machine"] == "AMMT" and r["integration_time_us"] == "20"}
        for case in "ABC":
            ammt = t4[f"AMMT-{case}"]
            self.assertTrue(ammt["cooling_rate_use"].startswith("do-not-use"))
            self.assertIn("footnote c", ammt["cooling_rate_use"])
            # the flag rests on this identity: Table 4 AMMT cooling rate == the AMMT-20us Table 3 track value
            self.assertEqual(ammt["cr_1290_1190_mean_C_s"], ammt20[case]["cr_1290_1190_mean_C_s"])
            self.assertTrue(t4[f"CBM-{case}"]["cooling_rate_use"].startswith("exemplar"))

    def test_nist_caveat_page_references(self):
        caveat = next(c for c in pds.NIST_THERMAL_PROVENANCE["caveats"] if "undercooling" in c)
        self.assertIn("page 1", caveat)
        self.assertIn("page 7 belongs to the pad PTAM/PSCR processing", caveat)
        self.assertIn("Page 3", caveat)
        self.assertNotIn("TTAM threshold assumed", caveat)

    def test_ku_layer_statement_matches_the_in718_record(self):
        self.assertIn("60 um", pds.KU_WAVE2_LAYER_STATUS)
        self.assertTrue(any("60 um powder layer" in c for c in pds.KU_LEUVEN_PROVENANCE["caveats"]))
        self.assertTrue(all(r["layer_um"] is None for r in pds.load_ku_leuven_316l_ti64()["rows"]))

    def test_lane_table3_keeps_footnote_flags_and_blank_cells(self):
        recs = pds._load_pinned_csv(pds.LANE_TRACKS_TABLE, pds.LANE_TRACKS_TABLE_SHA256, pds.LANE_TRACK_COLUMNS, "t")
        ammt_c100 = [r for r in recs if r["machine"] == "AMMT" and r["integration_time_us"] == "100" and r["case"] == "C"]
        self.assertTrue(all(r["footnotes"] == "abc" and r["effective_emittance_sigma"] == "" for r in ammt_c100))
        self.assertTrue(all(r["cr_1290_1000_mean_C_s"] == "" for r in recs if r["machine"] == "AMMT"))

    def test_nist_thermal_cases_match_the_app_in718_cases(self):
        from lpbf_nist_in718_comparison import CASE_PROCESS
        d = pds.load_nist_amb2022_03_thermal()
        self.assertEqual(len(d["rows"]), 7)
        for r in d["rows"]:
            self.assertEqual(CASE_PROCESS[r["case"]], (r["power_W"], r["speed_mm_s"], r["d4sigma_um"]))
        base = next(r for r in d["rows"] if r["case"] == "0")
        self.assertEqual((base["TTAM_s"], base["TSCR_C_s"], base["TLCR_C_s"], base["TTCR_C_s"]),
                         (1.22e-3, 6.99e5, 4.14e5, 1.93e5))
        self.assertTrue(any("undercooling" in c for c in d["provenance"]["caveats"]))

    def test_simonds_table_iii(self):
        d = pds.load_simonds_316l()
        self.assertEqual(len(d["rows"]), 10)
        self.assertEqual([r["eta_coupling"] for r in d["rows"]][::9], [0.31, 0.86])
        self.assertIsNone(d["rows"][0]["time_to_keyhole_ms"])
        self.assertEqual(d["rows"][2]["time_to_keyhole_ms"], 2.1)

    def test_every_source_has_citation_licence_hash_and_evidence_kind(self):
        provs = [pds.load_ku_leuven_316l_ti64()["provenance"], pds.load_lane_in625()["provenance"],
                 pds.load_nist_amb2022_03_thermal()["provenance"], pds.load_simonds_316l()["provenance"]]
        for p in provs:
            self.assertTrue(p["citation"])
            self.assertTrue(p["evidenceKind"].startswith("published measurement"))
            self.assertRegex(p["fileSha256"], r"^[0-9a-f]{64}$")
        for src in (pds.LANE_SOURCE, pds.SIMONDS_SOURCE, pds.NIST_THERMAL_SOURCE):
            self.assertEqual(src["retrieved"], "2026-10-06")
            self.assertRegex(src["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(src["bytes"], 0)
        self.assertIn("license", pds.NIST_THERMAL_SOURCE)
        for p in (pds.LANE_PROVENANCE, pds.SIMONDS_PROVENANCE):
            self.assertTrue(p["license"])
        for spec in pds.KU_WAVE2_FILES:
            self.assertRegex(spec["md5"], r"^[0-9a-f]{32}$")

    def test_reference_targets_are_marked_unavailable_with_reason(self):
        targets = pds.wave2_reference_targets()
        self.assertEqual([t["dataset"] for t in targets], ["nist-amb2022-03-thermal-2022", "simonds-316l-2018"])
        for t in targets:
            self.assertEqual(t["comparison"]["status"], "unavailable")
            self.assertGreater(len(t["comparison"]["reason"]), 80)
        # Published TTAM digits survive the record's 4-decimal rounding (carried in ms).
        self.assertEqual([r["TTAM_ms"] for r in targets[0]["rows"]], [1.22, 1.3, 1.04, 0.896, 1.59, 1.38, 1.03])

    def test_changed_literature_table_is_refused(self):
        original = pds.SIMONDS_TABLE
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "t.csv"
            path.write_bytes(original.read_bytes().replace(b"0.86", b"0.87"))
            pds.SIMONDS_TABLE = path
            try:
                with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                    pds.load_simonds_316l()
            finally:
                pds.SIMONDS_TABLE = original


class SourceRebuildTests(unittest.TestCase):
    """Rebuild the transcriptions from their (uncommitted) source documents when they are supplied."""

    def _source(self, key):
        folder = os.environ.get(SOURCE_DIR_ENV)
        if not folder:
            self.skipTest(f"{SOURCE_DIR_ENV} is not set: the {SOURCE_NAMES[key]} source document is not committed "
                          "(see the dataset's LICENSE-ATTRIBUTION.md for URL and SHA-256)")
        path = Path(folder) / SOURCE_NAMES[key]
        if not path.is_file():
            self.skipTest(f"{path} not found; download it from the URL in LICENSE-ATTRIBUTION.md")
        return path

    def test_lane_rebuild(self):
        src = self._source("lane")
        with tempfile.TemporaryDirectory() as td:
            got = pds.build_lane_tables(src, Path(td) / "a.csv", Path(td) / "b.csv")
        self.assertEqual(got, (pds.LANE_TRACKS_TABLE_SHA256, pds.LANE_SUMMARY_TABLE_SHA256))

    def test_simonds_rebuild(self):
        src = self._source("simonds")
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(pds.build_simonds_table(src, Path(td) / "s.csv"), pds.SIMONDS_TABLE_SHA256)

    def test_nist_rebuild(self):
        src = self._source("nist")
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest("pypdf is not installed: it is only needed to rebuild the NIST table from the PDF")
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(pds.build_nist_thermal_table(src, Path(td) / "n.csv"), pds.NIST_THERMAL_TABLE_SHA256)

    def test_wrong_source_bytes_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "x.xml"
            bad.write_bytes(b"<article/>")
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                pds.build_lane_tables(bad, Path(td) / "a.csv", Path(td) / "b.csv")
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                pds.build_simonds_table(bad, Path(td) / "s.csv")


class ScreeningPropsTests(unittest.TestCase):
    def test_in625_uses_the_solver_secondary_table_and_unknown_raises(self):
        from lpbf_thermal_solver import SECONDARY_THERMOPHYSICAL_DB
        self.assertIs(pds.screening_props("Inconel 625"), SECONDARY_THERMOPHYSICAL_DB["Inconel 625"])
        r = pds.classify_regime("Inconel 625", 150, 400, 100, 20.0, None)
        self.assertIn(r["label"], ("conduction", "transition", "keyhole"))
        with self.assertRaisesRegex(ValueError, "Unsupported material"):
            pds.classify_regime("Unobtainium", 150, 400, 100, 20.0, None)


def _stub_prediction(row):
    """Fixed stand-in for one kernel call: +10 % width, -10 % depth, one counted flat-plate call."""
    return {"width_um": round(row["width_um"] * 1.1, 6), "depth_um": round(row["depth_um"] * 0.9, 6),
            "length_um": 100.0, "extentStatus": "computed", "extentNote": None, "included": True,
            "_flatPlateCalls": 1}


class Wave2BlockStubTests(unittest.TestCase):
    """build_wave2_block and its helpers on three committed rows; the solver is replaced by _stub_prediction."""

    def setUp(self):
        import lpbf_dataset_comparison as cmp
        self.cmp = cmp
        self.calls = []

        def fake_map(tasks, jobs):
            self.calls.append(len(tasks))
            return [_stub_prediction(t["row"]) for t in tasks]

        self._orig_map = cmp._map
        cmp._map = fake_map
        self.w2 = cmp.load_wave2(pds)
        picked = {"ku-leuven-316l-2021-01", "ku-leuven-ti64-2021-08"}
        rows = [r for r in self.w2["rows"] if r["rowId"] in picked]
        rows.append(next(r for r in self.w2["lane"]["rows"] if r["machine"] == "AMMT"))
        self.out_rows = []
        for r in rows:
            regime = pds.classify_regime(r["material"], r["power_W"], r["speed_mm_s"], r["beamDiameter_um"],
                                         r["preheat_C"], r["balling"])
            pred = {kk: v for kk, v in _stub_prediction(r).items() if kk != "_flatPlateCalls"}
            self.out_rows.append({
                "dataset": r["dataset"], "rowId": r["rowId"],
                "inputs": {"power_W": r["power_W"], "speed_mm_s": r["speed_mm_s"],
                           "beamDiameter_um": r["beamDiameter_um"], "layer_um": r["layer_um"]},
                "measured": {"width_um": r["width_um"], "depth_um": r["depth_um"]}, "regime": regime,
                "predictions": {k: dict(pred) for k in cmp.KERNELS}})

    def tearDown(self):
        self.cmp._map = self._orig_map

    def test_scorecard_sensitivities_accounting_and_crosstab(self):
        cmp = self.cmp
        w = cmp.build_wave2_block(pds, self.w2, self.out_rows, jobs=1, allow_raytracer=False)
        self.assertEqual(set(w["scorecard"]), {"ku-leuven-316l-2021", "ku-leuven-ti64-2021", "lane-in625-2020"})
        for ds, s in w["scorecard"].items():
            for k in cmp.KERNELS:
                self.assertEqual(s[k]["all"]["n"], 1, (ds, k))
                self.assertAlmostEqual(s[k]["all"]["width"]["bias_pct"], 10.0, places=3)
                self.assertAlmostEqual(s[k]["all"]["depth"]["bias_pct"], -10.0, places=3)
        # sensitivity re-runs: 2 KU rows at 75 um + 1 Lane AMMT row at nominal power, every kernel each
        self.assertEqual(w["kuBeamDiameterSensitivity"]["rows"], 2)
        self.assertEqual(w["laneNominalPowerSensitivity"]["rows"], 1)
        acct = w["sensitivityRunAccounting"]
        self.assertEqual(acct["solverCalls"], 3 * len(cmp.KERNELS))
        self.assertEqual(acct["flatPlateCalls"], 3 * len(cmp.KERNELS))
        self.assertEqual(sum(self.calls), acct["solverCalls"])
        counts = w["kuRegimeLabelCrosstab"]["counts"]
        self.assertEqual(sum(n for v in counts.values() for n in v.values()), 2)
        self.assertIn("keyhole", counts)  # ku-leuven-ti64-2021-08 is published as keyhole
        self.assertTrue(all(c["cooling_rate_use"] for c in w["laneTable4"]))
        self.assertFalse(w["evidence"]["experimentalValidation"])
        self.assertFalse(w["evidence"]["opticalOperatorMatched"])
        text = "\n".join(cmp.render_wave2_markdown(w))
        self.assertIn("cooling-rate use", text)
        self.assertIn("do-not-use (same AMMT-20us values as Table 3, footnote c)", text)
        self.assertIn("Tables 5-7 give the uncertainty budgets", text)
        self.assertIn(f"Sensitivity re-runs: {acct['solverCalls']} solver calls", text)

    def test_limits_state_power_question_and_summary_scope(self):
        joined = " ".join(self.cmp.wave2_limits(pds, self.w2, self.out_rows))
        self.assertIn("Fig. 2 caption", joined)
        self.assertNotIn("without an explanation", joined)
        self.assertIn("exclude the 3 wave 2 rows", joined)
        self.assertIn("wave2.scorecard", joined)

    def test_uncertainty_limit_wording_follows_scope(self):
        cmp = self.cmp
        summary = cmp.summarize(self.out_rows)
        cmp.add_common_cells(summary, self.out_rows)
        absorption = {"path": "flat-plate", "pinned": True, "absorptivity_by_material": {"316L": 0.42}}
        old = " ".join(cmp.build_limits(self.out_rows, summary, absorption))
        new = " ".join(cmp.build_limits(self.out_rows, summary, absorption, include_wave2=True))
        self.assertIn("neither dataset provides per-row measurement uncertainty", old)
        self.assertNotIn("neither dataset", new)
        self.assertIn("spread of N = 3 microscopy measurements, not an uncertainty", new)


class Wave2RecordTests(unittest.TestCase):
    """The committed 2026-10-06 record ships with this module: a missing record is a failure, not a skip."""

    def setUp(self):
        self.assertTrue(RECORD.is_file(), f"{RECORD} is committed with the wave 2 change and must be present")
        self.doc = json.loads(RECORD.read_text(encoding="utf-8"))

    def test_pooled_headline_keeps_the_2026_10_05_scope(self):
        old = json.loads((REPO / "docs" / "LPBF_DATASET_COMPARISON_2026-10-05.json").read_text(encoding="utf-8"))
        scope = self.doc["summaryScope"]
        self.assertEqual(scope["excludedWave2Datasets"],
                         ["ku-leuven-316l-2021", "ku-leuven-ti64-2021", "lane-in625-2020"])
        self.assertEqual(scope["rows"], len(old["rows"]))
        self.assertEqual(self.doc["summary"], old["summary"])
        self.assertEqual(self.doc["absorptivitySensitivity"]["rows"], old["absorptivitySensitivity"]["rows"])
        text = json.dumps({k: self.doc[k] for k in ("limits", "regimeFilter", "assumptions")})
        self.assertNotIn("neither dataset", text)
        self.assertNotIn("not given by either dataset", text)
        self.assertIn("KU Leuven IN718 (ku-leuven-in718-2021)", self.doc["regimeFilter"]["rule"])
        self.assertIn("IN625 0.38", self.doc["assumptions"]["absorptivity"])
        self.assertNotIn("without an explanation", json.dumps(self.doc))
        lane = next(d for d in self.doc["datasets"] if d["id"] == "lane-in625-2020")
        self.assertTrue(any("Fig. 2 caption" in n for n in lane["notes"]))
        self.assertTrue(all(c["cooling_rate_use"] for c in self.doc["wave2"]["laneTable4"]))
        self.assertGreater(self.doc["wave2"]["sensitivityRunAccounting"]["solverCalls"], 0)

    def test_record_honesty_and_wave2_block(self):
        doc = self.doc
        self.assertEqual(doc["generatedAt"], "2026-10-06")
        self.assertFalse(doc["honesty"]["experimentalValidation"])
        w = doc["wave2"]
        self.assertFalse(w["evidence"]["experimentalValidation"])
        self.assertFalse(w["evidence"]["opticalOperatorMatched"])
        self.assertEqual(set(w["scorecard"]), {"ku-leuven-316l-2021", "ku-leuven-ti64-2021", "lane-in625-2020"})
        self.assertEqual([t["comparison"]["status"] for t in w["referenceTargets"]], ["unavailable", "unavailable"])
        ids = {d["id"] for d in doc["datasets"]}
        self.assertTrue({"ku-leuven-316l-2021", "ku-leuven-ti64-2021", "lane-in625-2020"} <= ids)
        for d in doc["datasets"]:
            self.assertEqual(d["rows"], sum(1 for r in doc["rows"] if r["dataset"] == d["id"]), d["id"])
        rows = [r for r in doc["rows"] if r["dataset"] == "ku-leuven-316l-2021"]
        self.assertEqual(len(rows), 44)
        self.assertTrue(all("publishedLabel" in r["regime"] for r in rows))
        self.assertEqual(doc["implementationHash"][:8], "11b04b8f")

    def test_wave2_markdown_renders_from_the_record(self):
        import lpbf_dataset_comparison as cmp
        text = "\n".join(cmp.render_wave2_markdown(self.doc["wave2"]))
        self.assertIn("Comparison: unavailable.", text)
        self.assertIn("SENSITIVITY on an unresolved input", text)
        md = RECORD.with_suffix(".md").read_text(encoding="utf-8")
        self.assertIn("## Wave 2 datasets (2026-10-06)", md)

    def test_2026_10_05_record_is_untouched_by_wave2(self):
        old = json.loads((REPO / "docs" / "LPBF_DATASET_COMPARISON_2026-10-05.json").read_text(encoding="utf-8"))
        self.assertNotIn("wave2", old)
        self.assertEqual(old["generatedAt"], "2026-10-05")


if __name__ == "__main__":
    unittest.main()
