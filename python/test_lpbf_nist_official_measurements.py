"""Direct source audit for the NIST AMB2022-03 BP1 optical workbook."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from lpbf_nist_official_measurements import (
    CASES, OFFICIAL_BYTES, OFFICIAL_SHA256, WORKBOOK_PATH, recompute_bp1_table4,
)


TABLE_PATH = WORKBOOK_PATH.parents[1] / "table4-aggregate-v2.json"


class NistOfficialMeasurements(unittest.TestCase):
    def test_bp1_rows_reproduce_published_table4_at_one_decimal(self):
        report = recompute_bp1_table4()
        published = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(OFFICIAL_BYTES, WORKBOOK_PATH.stat().st_size)
        self.assertEqual(OFFICIAL_SHA256, report["workbookSha256"])
        self.assertEqual(42, report["observationCount"])
        self.assertEqual(list(CASES), [case["caseNumber"] for case in report["cases"]])
        for case, reference in zip(report["cases"], published["cases"]):
            with self.subTest(case=case["caseNumber"]):
                self.assertEqual(case["caseNumber"], reference["caseNumber"])
                self.assertEqual(6, case["observationCount"])
                self.assertEqual(case["laserPower_W"], reference["laserPower_W"])
                self.assertEqual(case["scanSpeed_mm_s"], reference["scanSpeed_mm_s"])
                self.assertEqual(case["beamDiameterGaussAvg_um"], reference["beamDiameterD4sigma_um"])
                for quantity in ("depth", "width"):
                    for statistic in ("Mean", "StdDev"):
                        field = f"{quantity}{statistic}_um"
                        self.assertEqual(reference[field], round(case[field], 1))

    def test_two_positions_per_line_and_case_21_part_number_transition(self):
        observations = recompute_bp1_table4()["observations"]
        for case in CASES:
            for line in (1, 2, 3):
                selected = [row for row in observations if row["caseNumber"] == case
                            and row["lineNumber"] == line]
                self.assertEqual([4.9, 6.0], [row["position_mm"] for row in selected])
        case_21 = [row for row in observations if row["caseNumber"] == "2.1"]
        self.assertEqual(["P3", "P4", "P3", "P4", "P1", "P2"],
                         [row["partNumber"] for row in case_21])

    def test_case_zero_retains_the_six_raw_source_observations(self):
        observations = [row for row in recompute_bp1_table4()["observations"]
                        if row["caseNumber"] == "0"]
        identity = [(row["row"], row["lineNumber"], row["position_mm"], row["partNumber"])
                    for row in observations]
        self.assertEqual(identity, [
            (2, 1, 4.9, "P3"), (3, 1, 6.0, "P4"),
            (4, 2, 4.9, "P3"), (5, 2, 6.0, "P4"),
            (6, 3, 4.9, "P3"), (7, 3, 6.0, "P4"),
        ])
        for row, depth_um, width_um in zip(
                observations,
                (139.863, 138.483, 142.209, 138.138, 141.864, 137.724),
                (141.795, 134.619, 133.653, 136.482, 135.792, 135.378)):
            with self.subTest(workbookRow=row["row"]):
                self.assertEqual(row["laserPower_W"], 285.0)
                self.assertEqual(row["scanSpeed_mm_s"], 960.0)
                self.assertEqual(row["beamDiameterGaussAvg_um"], 67.0)
                self.assertAlmostEqual(row["depth_um"], depth_um)
                self.assertAlmostEqual(row["width_um"], width_um)

    def test_digest_and_size_are_required_before_parsing(self):
        original = WORKBOOK_PATH.read_bytes()
        with patch.object(Path, "read_text", return_value="0" * 64):
            with self.assertRaisesRegex(ValueError, "sidecar SHA-256"):
                recompute_bp1_table4()
        with patch.object(Path, "read_bytes", return_value=original[:-1] + bytes([original[-1] ^ 1])):
            with self.assertRaisesRegex(ValueError, "size or SHA-256"):
                recompute_bp1_table4()


if __name__ == "__main__":
    unittest.main()
