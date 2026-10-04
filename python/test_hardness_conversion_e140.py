"""ASTM E140 Table 1 HRC -> HV in Python (hardness_conversion_e140) and its use in the kinetics solver.

The Python table must equal, row for row, both TypeScript copies:
- src/utils/hardnessConversion.ts E140_TABLE1 (the shared UI util), and
- tests/fixtures/hardness-tables-sources.ts E140_T1_ANDERSON (independently transcribed fixture).
"""

import json
import math
import re
import unittest
from pathlib import Path

import alloy_data_kinetics_uq_fatigue as kin_data
import hardness_conversion_e140 as e140
import kinetics_ttt_cct_solver as kin

REPO = Path(__file__).resolve().parent.parent
UTIL_TS = REPO / "src" / "utils" / "hardnessConversion.ts"
FIXTURE_TS = REPO / "tests" / "fixtures" / "hardness-tables-sources.ts"
ROW = re.compile(r"\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+|null)\s*,\s*(\d+)\s*\]")


def _ts_rows(path, const_name):
    text = path.read_text(encoding="utf-8")
    start = text.index(f"const {const_name}")
    body = text[text.index("= [", start):text.index("];", start)]
    return [(int(m.group(1)), int(m.group(2))) for m in ROW.finditer(body)]


class TableEqualsTypeScriptTest(unittest.TestCase):
    def test_equals_the_shared_ts_util(self):
        rows = _ts_rows(UTIL_TS, "E140_TABLE1")
        self.assertEqual(len(rows), 49)
        self.assertEqual(tuple(rows), e140.E140_TABLE1_HRC_HV)

    def test_equals_the_independent_ts_fixture(self):
        rows = _ts_rows(FIXTURE_TS, "E140_T1_ANDERSON")
        self.assertEqual(len(rows), 49)
        self.assertEqual(tuple(rows), e140.E140_TABLE1_HRC_HV)

    def test_table_shape(self):
        hrc = [r[0] for r in e140.E140_TABLE1_HRC_HV]
        hv = [r[1] for r in e140.E140_TABLE1_HRC_HV]
        self.assertEqual(hrc, list(range(20, 69)))
        self.assertTrue(all(b > a for a, b in zip(hv, hv[1:])), "HV strictly increasing")
        self.assertEqual((e140.HRC_MIN, e140.HRC_MAX), (20.0, 68.0))


class ConversionTest(unittest.TestCase):
    def test_tabulated_rows_are_exact(self):
        for hrc, hv in e140.E140_TABLE1_HRC_HV:
            self.assertEqual(e140.hrc_to_hv_non_austenitic_steel(float(hrc)), (float(hv), e140.STATUS_CONVERTED))
            self.assertEqual(e140.hrc_to_hv_non_austenitic_steel(hrc), (float(hv), e140.STATUS_CONVERTED))

    def test_interpolation_between_rows(self):
        self.assertAlmostEqual(e140.interpolate_hv_from_hrc(57.5), 643.0)
        self.assertAlmostEqual(e140.interpolate_hv_from_hrc(20.5), 240.5)
        # half up, like Math.round in the TS util: 240.5 -> 241
        self.assertEqual(e140.hrc_to_hv_non_austenitic_steel(20.5), (241.0, e140.STATUS_CONVERTED))

    def test_unavailable_outside_range_no_extrapolation_or_clamp(self):
        for hrc in (18.0, 19.99, 68.01, 70.0, -5.0, float("nan"), float("inf"), None, "58", True):
            with self.subTest(hrc=hrc):
                self.assertEqual(e140.hrc_to_hv_non_austenitic_steel(hrc), (None, e140.STATUS_UNAVAILABLE_RANGE))
        self.assertEqual(e140.hrc_to_hv_non_austenitic_steel(20.0)[0], 238.0)
        self.assertEqual(e140.hrc_to_hv_non_austenitic_steel(68.0)[0], 940.0)

    def test_statuses(self):
        self.assertEqual(len(set(e140.STATUSES)), 3)
        prov = e140.provenance()
        self.assertIn("ASTM E140 Table 1", prov["table"])
        self.assertEqual(prov["validRange_HRC"], [20.0, 68.0])


class KineticsSolverHardnessTest(unittest.TestCase):
    STUDIO_DEFAULT_AUST = {"AISI 4140": 860.0, "AISI 4340": 845.0, "AISI D2": 1020.0,
                           "Inconel 718": 980.0, "Ti-6Al-4V": 1050.0, "Al 7075": 475.0}

    def test_every_kinetics_alloy_is_classified_explicitly(self):
        steels = kin.E140_NON_AUSTENITIC_STEEL_IDS
        self.assertEqual(steels, {"aisi4140", "aisi4340", "aisid2"})
        self.assertEqual(set(kin_data.KINETICS_LEGACY_NAMES) - steels, {"in718", "ti6al4v", "al7075"})
        for rid in steels:
            self.assertIn("Steel", kin_data.KINETICS_DESCRIPTORS[rid]["type"])

    def _rows(self, name):
        res = kin.solve_phase_transformation_kinetics(name, 10.0, 25.0, self.STUDIO_DEFAULT_AUST[name], 8.0, 720.0)
        return res["cctContinuousCoolingMap"]

    def test_steels_use_e140_and_null_below_hrc_20(self):
        for name in ("AISI 4140", "AISI 4340", "AISI D2"):
            for row in self._rows(name):
                with self.subTest(alloy=name, cr=row["coolingRate_C_s"]):
                    hrc, hv, status = (row["predictedHardness_HRC"], row["predictedHardness_HV"],
                                       row["predictedHardness_HV_status"])
                    if hrc < 20.0:
                        self.assertIsNone(hv)
                        self.assertEqual(status, e140.STATUS_UNAVAILABLE_RANGE)
                    else:
                        self.assertEqual(hv, float(dict(e140.E140_TABLE1_HRC_HV)[int(hrc)]))
                        self.assertIsInstance(hv, float)
                        self.assertEqual(status, e140.STATUS_CONVERTED)

    def test_non_steels_are_unavailable(self):
        for name in ("Inconel 718", "Ti-6Al-4V", "Al 7075"):
            for row in self._rows(name):
                with self.subTest(alloy=name, cr=row["coolingRate_C_s"]):
                    self.assertIsNone(row["predictedHardness_HV"])
                    self.assertEqual(row["predictedHardness_HV_status"], e140.STATUS_UNAVAILABLE_ALLOY_CLASS)
                    # fx-kinetics: the steel lookup HRC is not reported for non-steels either.
                    self.assertIsNone(row["predictedHardness_HRC"])
                    self.assertEqual(row["predictedHardness_HRC_status"], "unavailable-kinetics-model-steel-only")

    def test_old_formula_is_gone_and_key_order_is_kept(self):
        src = (Path(kin.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("10.5 + 40", src)
        self.assertNotIn("* 10.5", src)
        keys = list(self._rows("AISI 4140")[0])
        # the HV keys keep their place; fx-kinetics appended four status keys after them
        self.assertEqual(keys[-7:], ["predictedHardness_HRC", "predictedHardness_HV", "predictedHardness_HV_status",
                                     "transformedStart_status", "phaseFractions_status",
                                     "predictedHardness_HRC_status", "unavailableReason"])

    def test_json_null_and_provenance(self):
        res = kin.solve_phase_transformation_kinetics("Ti-6Al-4V")
        text = json.dumps(res)
        self.assertIn('"predictedHardness_HV": null', text)
        prov = kin.provenance("ti6al4v")["hardnessConversion"]
        self.assertFalse(prov["appliedToThisAlloy"])
        self.assertTrue(kin.provenance("aisid2")["hardnessConversion"]["appliedToThisAlloy"])
        self.assertEqual(prov["appliesToRegistryIds"], ["aisi4140", "aisi4340", "aisid2"])

    def test_no_nan_in_output(self):
        for name in self.STUDIO_DEFAULT_AUST:
            for row in self._rows(name):
                hv = row["predictedHardness_HV"]
                self.assertTrue(hv is None or math.isfinite(hv))


if __name__ == "__main__":
    unittest.main()
