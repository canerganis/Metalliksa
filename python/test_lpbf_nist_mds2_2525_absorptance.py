"""Source audit tests for the NIST mds2-2525 absorptance archive."""

import json
import unittest
from unittest.mock import patch

import lpbf_nist_mds2_2525_absorptance as source


class NistMds22525Absorptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.series = source.load_ti64_spot_series()
        cls.summary = source.summarize_ti64_spot(cls.series)
        cls.al = source.load_al_tables()

    def test_all_present_files_verify(self):
        for name, entry in source.OFFICIAL_FILES.items():
            with self.subTest(name=name):
                data = source.verified_bytes(name)
                self.assertEqual(entry["bytes"], len(data))

    def test_ti64_spot_summary_is_in_the_documented_range(self):
        summary = self.summary
        self.assertEqual(source.SPOT_ROWS, len(self.series["time_s"]))
        self.assertAlmostEqual(101.9, summary["input_power_median_W"], delta=0.5)
        self.assertAlmostEqual(32.5, summary["pre_keyhole_mean_pct"], delta=0.5)
        self.assertGreater(summary["keyhole_mean_pct"], 60.0)
        self.assertLess(summary["keyhole_mean_pct"], 66.0)
        self.assertGreaterEqual(summary["transition_time_ms"], 0.80)
        self.assertLessEqual(summary["transition_time_ms"], 0.90)
        self.assertGreaterEqual(summary["laser_on_end_s"], 0.00200)
        self.assertLessEqual(summary["laser_on_end_s"], 0.00202)
        self.assertGreater(summary["energy_coupling_fraction"], 0.4)
        self.assertLess(summary["energy_coupling_fraction"], 0.6)
        self.assertIn("not NIST-published", summary["window_definition"])
        self.assertTrue(all(len(item) == 3 and item[2] > 0 for item in summary["bins_50us"]))
        self.assertIn(None, self.series["absorbed_uncertainty_W"])

    def test_al_tables_reproduce_published_numbers(self):
        spot = {row["description"]: row for row in self.al["spot_average_absorption"]["rows"]}
        scan = {row["description"]: row for row in self.al["scan_average_absorption"]["rows"]}
        pairs = [
            (spot["Average Absorption before keyhole"], 23.9, 0.3),
            (spot["Average Absorption during keyhole"], 64.1, 3.9),
            (spot["Solidification Rate"], 0.46, 0.03),
            (scan["Average Absorption before keyhole"], 23.8, 0.08),
            (scan["Average Absorption during keyhole"], 43.3, 1.5),
            (scan["Melt Pool Depth - Maximum"], 88.8, 0.4),
            (scan["Melt Pool Width - Maximum"], 326.0, 16.08),
            (scan["Solidification Rate"], 0.191, 0.019),
        ]
        for row, value, deviation in pairs:
            with self.subTest(description=row["description"]):
                self.assertEqual(value, row["value"])
                self.assertEqual(deviation, row["std_dev"])
        self.assertEqual(source.AL_MATERIAL, self.al["material"])
        width = self.al["spot_melt_pool_width"]
        self.assertEqual(source.AL_MATERIAL, width["material"])
        self.assertEqual(0.0, width["time_s"][0])
        self.assertEqual(2e-5, width["time_s"][1])
        self.assertEqual(107.1803, width["melt_pool_width_um"][1])
        self.assertEqual(99, len(width["time_s"]))
        self.assertEqual(40, width["placeholder_rows"])
        self.assertEqual([505.28323], width["untimed_width_um"])
        self.assertEqual("190613_Al2g_065_CW90", self.al["spot_tda_summary"]["datafile_name"])
        self.assertEqual(51750, self.al["spot_tda_summary"]["row_count"])
        self.assertEqual("190613_Al2c_061_CW85", self.al["scan_tda_summary"]["datafile_name"])
        self.assertEqual(58131, self.al["scan_tda_summary"]["row_count"])

    def test_derived_json_matches_fresh_build(self):
        on_disk = source.DERIVED_PATH.read_bytes()
        fresh = source.serialize_summary(source.build_derived_summary()).encode("utf-8")
        self.assertEqual(fresh, on_disk)
        self.assertNotIn(b"\r", on_disk)
        document = json.loads(on_disk)
        self.assertFalse(document["evidence"]["experimentalValidation"])
        self.assertFalse(document["evidence"]["modelAcceptance"])
        self.assertTrue(document["ti64_spot"]["bins_50us"])

    def test_hash_mismatch_is_rejected(self):
        name = "Al_Spot_AA_ASR_Results.csv"
        good = source.verified_bytes(name)
        real_read = source.Path.read_bytes
        with patch.object(source.Path, "read_bytes",
                          lambda self: good[:-1] + bytes([good[-1] ^ 1]) if self.name == name else real_read(self)):
            with self.assertRaisesRegex(ValueError, "size or SHA-256 mismatch"):
                source.verified_bytes(name)
        with patch.object(source.Path, "read_bytes",
                          lambda self: good + b" " if self.name == name else real_read(self)):
            with self.assertRaisesRegex(ValueError, "size or SHA-256 mismatch"):
                source.verified_bytes(name)

    def test_malformed_files_are_rejected(self):
        good = source.verified_bytes(source.SPOT_NAME)
        lines = good.decode("utf-8").split("\r\n")
        header = lines[0].replace(",CameraTrigger", "")
        with patch.object(source, "verified_bytes", return_value="\r\n".join([header] + lines[1:]).encode()):
            with self.assertRaisesRegex(ValueError, "malformed"):
                source.load_ti64_spot_series()
        row = lines[100].split(",")
        row[5] = "not-a-number"
        bad = lines[:100] + [",".join(row)] + lines[101:]
        with patch.object(source, "verified_bytes", return_value="\r\n".join(bad).encode()):
            with self.assertRaisesRegex(ValueError, "malformed"):
                source.load_ti64_spot_series()
        with patch.object(source, "verified_bytes", return_value="\r\n".join(lines[:-3] + [""]).encode()):
            with self.assertRaisesRegex(ValueError, "malformed"):
                source.load_ti64_spot_series()
        row = lines[100].split(",")[:-1]
        short = lines[:100] + [",".join(row)] + lines[101:]
        with patch.object(source, "verified_bytes", return_value="\r\n".join(short).encode()):
            with self.assertRaisesRegex(ValueError, "malformed"):
                source.load_ti64_spot_series()

    def test_malformed_al_table_is_rejected(self):
        with patch.object(source, "verified_bytes",
                          return_value=b"Description,Value,Unit,StDev,Unit\r\nx,abc,%,0.3,%\r\n"):
            with self.assertRaisesRegex(ValueError, "malformed"):
                source.load_al_tables()

    def test_absent_files_are_unavailable_not_errors(self):
        with self.assertRaises(FileNotFoundError):
            source.load_ti64_scan_series()
        unavailable = {item["file"]: item for item in source.build_derived_summary()["unavailable"]}
        self.assertEqual(set(source.ABSENT_FILES), set(unavailable))
        for name, entry in source.ABSENT_FILES.items():
            self.assertEqual(entry["sha256"], unavailable[name]["sha256"])
            self.assertEqual("unavailable", unavailable[name]["status"])
        self.assertEqual("1c64f24e84c274d9f9ae27fb09e79b86cda2fda5bee4b67da3567c8a59ca499d",
                         unavailable[source.SCAN_NAME]["sha256"])


if __name__ == "__main__":
    unittest.main()
