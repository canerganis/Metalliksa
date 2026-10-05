"""Focused parser and pin checks for the added open LPBF datasets."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_public_datasets as pds  # noqa: E402


class AdditionalDatasetParserTests(unittest.TestCase):
    def test_cmu_st_preserves_absent_power_and_si_units(self):
        header = "Slice,Orientation (degrees),Velocity (mm/s),Width (um),Depth (um),Cap (um)\n"
        rows = "1,0,1300,147.5,148.0,20.0\n" * 216
        parsed = pds.parse_cmu_table(header + rows, "STMeasurements.csv")
        self.assertEqual(len(parsed), 216)
        self.assertIsNone(parsed[0]["power_W"])
        self.assertEqual((parsed[0]["speed_mm_s"], parsed[0]["width_um"], parsed[0]["depth_um"]),
                         (1300.0, 147.5, 148.0))
        with self.assertRaisesRegex(ValueError, "unexpected CMU columns"):
            pds.parse_cmu_table(header.replace("Velocity (mm/s)", "Velocity (m/s)") + rows,
                                "STMeasurements.csv")

    def test_cmu_mt_keeps_power_and_rejects_nonpositive_inputs(self):
        header = "Slice,Orientation (degrees),Power (W),Velocity (mm/s),Width (um),Depth (um),Cap (um)\n"
        rows = "1,90,370,1300,269.676,283.296,32.688\n" * 410
        parsed = pds.parse_cmu_table(header + rows, "MTMeasurements.csv")
        self.assertEqual(len(parsed), 410)
        self.assertEqual((parsed[0]["power_W"], parsed[0]["orientation_deg"]), (370.0, 90.0))
        with self.assertRaisesRegex(ValueError, "invalid process input"):
            pds.parse_cmu_table(header + rows.replace("370,1300", "0,1300", 1), "MTMeasurements.csv")

    def test_ku_parser_keeps_unresolved_geometry_and_skips_summary_rows(self):
        columns = ["Sample", "P", "v", "", "w exp", "d exp", "R exp", "", "R model", "w model",
                   "d model", "", "R error", "w error", "d error", "", "melting regime", "",
                   "av. error", "R", "w", "d", "", "nb. of samples"]
        row = [""] * len(columns)
        for key, value in {0: "1", 1: "100", 2: "400", 4: "113,7142857", 5: "142,7142857",
                           6: "1,255", 16: "keyhole", 23: "4"}.items():
            row[key] = value
        summary = [""] * len(columns)
        summary[16] = "summary"
        text = ";".join(columns) + "\n" + (";".join(row) + "\n") * 48 + ";".join(summary) + "\n"
        parsed = pds.parse_ku_leuven_table(text)
        self.assertEqual(len(parsed), 48)
        self.assertEqual((parsed[0]["power_W"], parsed[0]["speed_mm_s"]), (100.0, 400.0))
        self.assertIsInstance(parsed[0]["source_width"], float)
        self.assertIsInstance(parsed[0]["source_depth"], float)
        self.assertEqual(parsed[0]["sample_count"], 4)


class AdditionalDatasetPinTests(unittest.TestCase):
    def test_committed_tables_match_pins_and_loaders_keep_exclusions_honest(self):
        cmu = pds.load_cmu_ti64()
        ku = pds.load_ku_leuven_in718()
        self.assertEqual(len(cmu["rows"]), 626)
        self.assertEqual(len(ku["rows"]), 48)
        self.assertEqual(cmu["provenance"]["fileSha256ByName"], {
            pds.CMU_ST_TABLE.name: pds.CMU_ST_TABLE_SHA256,
            pds.CMU_MT_TABLE.name: pds.CMU_MT_TABLE_SHA256,
        })
        self.assertEqual(ku["provenance"]["fileSha256"], pds.KU_LEUVEN_TABLE_SHA256)
        self.assertEqual(sum(r["power_W"] is None for r in cmu["rows"]), 216)
        self.assertTrue(all(r["beamDiameter_um"] is None for r in cmu["rows"]))
        self.assertTrue(all(r["width_um"] is None and r["depth_um"] is None for r in ku["rows"]))
        self.assertEqual(sum(r["sourceWidthValue"] is None or r["sourceDepthValue"] is None
                             for r in ku["rows"]), 10)

    def test_hash_mismatch_is_refused(self):
        original = pds.KU_LEUVEN_TABLE
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "changed.csv"
            path.write_text("sample,power_W,speed_mm_s,source_width,source_depth,sample_count\n"
                            "1,100,400,10,20,1\n", encoding="utf-8")
            pds.KU_LEUVEN_TABLE = path
            try:
                with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                    pds.load_ku_leuven_in718()
            finally:
                pds.KU_LEUVEN_TABLE = original


if __name__ == "__main__":
    unittest.main()
