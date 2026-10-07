"""Keyhole literature datasets (Cunningham 2019, Zhao 2020, Gan 2021, Huang 2022, Hann 2011): hash pins, row counts, a
locator and a digitized flag on every row, read uncertainty on every digitized row, refusal of changed bytes, no double
counting of re-plotted data, the published-relation constants and the relation implementations.

Self-contained: only the committed CSVs under data/benchmark/ are read (no network, no PDF, no solver).
"""

import csv
import io
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_keyhole_literature as kl  # noqa: E402
import lpbf_public_datasets as pds  # noqa: E402

LOCATOR_RE = r"^(Fig\. |Table |Eq\.|Eqs\.|Section |Methods |p\. |Supplementary Data )"


def _rows(path):
    return list(csv.DictReader(io.StringIO(Path(path).read_text(encoding="utf-8"), newline="")))


class PinsRowsLocators(unittest.TestCase):
    def test_every_table_matches_its_pin_and_row_count(self):
        self.assertEqual(len(kl.PINNED_TABLES), 9)
        for path, digest in kl.PINNED_TABLES.items():
            self.assertEqual(pds.sha256_file(path), digest, path.name)
            self.assertEqual(len(_rows(path)), kl.EXPECTED_ROWS[path], path.name)

    def test_every_row_has_a_locator_and_a_boolean_digitized_flag(self):
        for path in kl.PINNED_TABLES:
            for r in _rows(path):
                self.assertRegex(r["locator"], LOCATOR_RE, path.name)
                self.assertIn(r["digitized"], ("true", "false"), path.name)

    def test_figure_reads_live_only_in_digitized_files_with_a_read_uncertainty(self):
        for path in kl.PINNED_TABLES:
            rows = _rows(path)
            flags = {r["digitized"] for r in rows}
            if "digitized" in path.name:
                self.assertEqual(flags, {"true"}, path.name)
                unc_cols = [c for c in rows[0] if "uncertainty" in c]
                self.assertTrue(unc_cols, path.name)
                for r in rows:
                    self.assertTrue(r["locator"].startswith("Fig. "), path.name)
                    for c in unc_cols:
                        if r[c] != "":
                            self.assertGreater(float(r[c]), 0, (path.name, c))
                    self.assertTrue(any(r[c] != "" for c in unc_cols), path.name)
            else:
                self.assertEqual(flags, {"false"}, path.name)

    def test_changed_bytes_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / kl.CUN_DEPTH_TABLE.name
            shutil.copy(kl.CUN_DEPTH_TABLE, bad)
            bad.write_bytes(bad.read_bytes().replace(b",86,", b",87,", 1))
            with mock.patch.object(kl, "CUN_DEPTH_TABLE", bad):
                with self.assertRaises(ValueError):
                    kl.load_cunningham_depths()
            self.assertEqual(len(kl.load_cunningham_depths(verify=True)["rows"]), 69)

    def test_no_pdf_or_image_is_committed(self):
        for folder in kl.DATASET_DIRS:
            for f in folder.iterdir():
                self.assertNotIn(f.suffix.lower(), (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".gif"), f)

    def test_every_dataset_has_doi_licence_source_hash_si_note_caveats_overlap(self):
        for name, fn in kl.LOADERS.items():
            p = fn()["provenance"]
            for key in ("id", "doi", "citation", "license", "evidenceKind", "caveats", "overlap", "supplementaryNeeded",
                        "fileSha256", "rows"):
                self.assertTrue(p.get(key), (name, key))
            self.assertTrue(p["doi"].startswith("10."), name)
            self.assertIn("article not redistributed", p["license"], name)
            self.assertRegex(p["source"]["sha256"], r"^[0-9a-f]{64}$", name)
            self.assertTrue(p["source"]["file"].endswith(".pdf"), name)


class ContentAndOverlap(unittest.TestCase):
    def test_row_counts_and_regime_label_counts(self):
        cun = kl.load_cunningham_depths()["rows"]
        self.assertEqual(sum(r["beamDiameter_um"] == 95 for r in cun), 46)
        self.assertEqual(sum(r["beamDiameter_um"] == 140 for r in cun), 23)
        labels = [r["regimeReported"] for r in cun if r["beamDiameter_um"] == 95]
        self.assertEqual((labels.count("conduction"), labels.count("transition"), labels.count("keyhole")), (1, 4, 41))
        self.assertTrue(all(r["regimeReported"] is None for r in cun if r["beamDiameter_um"] == 140))
        zb = kl.load_zhao_boundary()["rows"]
        self.assertEqual(sum(r["setting"] == "bare" for r in zb), 9)
        self.assertEqual(sum(r["keyholeDepth_um"] is not None for r in zb), 19)
        zp = kl.load_zhao_pores()["rows"]
        self.assertEqual((sum(r["barePlatePores"] for r in zp), sum(r["powderBedPores"] for r in zp)), (22, 31))
        self.assertTrue(all(r["barePlatePores"] or r["powderBedPores"] for r in zp))

    def test_only_ti64_rows_are_app_evaluable_and_replotted_ti64_is_not_ingested_twice(self):
        for name in ("gan-keyhole-2021", "huang-al7a77-2022", "hann-ss304-2011"):
            rows = kl.LOADERS[name]()["rows"]
            self.assertTrue(rows)
            self.assertFalse(any(r["appEvaluable"] for r in rows), name)
            self.assertFalse(any("Ti" in r["material"] for r in rows), name)
        for name in ("cunningham-ti64-2019", "zhao-ti64-2020-boundary", "zhao-ti64-2020-pores"):
            self.assertTrue(all(r["appEvaluable"] and r["material"] == "Ti-6Al-4V" for r in kl.LOADERS[name]()["rows"]))
        cun = {(r["power_W"], r["speed_mm_s"], r["beamDiameter_um"]) for r in kl.load_cunningham_depths()["rows"]}
        zhao = {(r["power_W"], r["speed_mm_s"], r["beamDiameter_um"])
                for n in ("zhao-ti64-2020-boundary", "zhao-ti64-2020-pores") for r in kl.LOADERS[n]()["rows"]}
        self.assertFalse(cun & zhao)
        ids = [r["rowId"] for fn in kl.LOADERS.values() for r in fn()["rows"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_not_in_the_frozen_calibration_config(self):
        import lpbf_calibration_config as cc
        trainable = set(cc.CALIBRATION_CONFIG["dataRoles"]["trainable"]) | set(cc.TRAINABLE_SOURCES)
        for name, fn in kl.LOADERS.items():
            self.assertNotIn(name, trainable)
            self.assertNotIn(fn()["provenance"]["id"], trainable)

    def test_cunningham_regime_from_lines(self):
        lines = kl.cunningham_lines()
        self.assertEqual(set(lines), {"blue-dashed", "red-dashed"})
        self.assertAlmostEqual(lines["red-dashed"]["slope"] * 400 + lines["red-dashed"]["intercept"], 135.922, places=3)
        self.assertEqual(kl.cunningham_regime(104, 700, lines)["label"], "conduction")
        self.assertEqual(kl.cunningham_regime(130, 400, lines)["label"], "transition")
        self.assertEqual(kl.cunningham_regime(156, 400, lines)["label"], "keyhole")


class Relations(unittest.TestCase):
    def setUp(self):
        self.rel = {r["relation"]: r for r in kl.load_relations()["rows"]}

    def test_constants_match_the_transcribed_relations(self):
        c = self.rel
        self.assertEqual(c["gan2021-aspect-ratio"]["constants"], {"k1": kl.GAN_ASPECT_SLOPE, "k0": kl.GAN_ASPECT_OFFSET})
        self.assertEqual(c["gan2021-regimes"]["constants"],
                         {"conduction_max": kl.GAN_KE_CONDUCTION_MAX, "keyhole_min": kl.GAN_KE_KEYHOLE_MIN})
        self.assertEqual(c["gan2021-stability"]["constants"],
                         {"stable_max": kl.GAN_KE_STABLE_MAX, "chaotic_min": kl.GAN_KE_CHAOTIC_MIN})
        self.assertEqual(c["gan2021-absorptivity"]["constants"], {"eta_max": kl.GAN_ETA_MAX, "c": kl.GAN_ETA_RATE})
        self.assertEqual(c["huang2022-definitions"]["constants"]["hm_Ti64_J_mm3"], kl.HUANG_HM_TI64_J_MM3)
        self.assertEqual(c["huang2022-ti64-threshold"]["constants"],
                         {"center": kl.HUANG_TI64_THRESHOLD, "halfwidth": kl.HUANG_TI64_THRESHOLD_HALFWIDTH})
        self.assertEqual(c["hann2011-vaporization-ratio"]["constants"]["ti64"], kl.HANN_HV_HS_TI64)
        self.assertEqual(c["gan2021-porosity"]["constants"], {"a": 0.10, "b": 1.51, "c": 0.01, "d": 2.32, "e": 0.055})
        self.assertEqual(c["huang2022-front-wall-angle"]["constants"], {"a": 0.29, "b": -0.2})

    def test_king_table3_relation_and_conversion_constants(self):
        k = self.rel["king2014-keyhole-threshold-316l"]
        self.assertEqual(k["constants"], {"A": 0.4, "rho_kg_m3": 7980.0, "hs_J_kg": 1.2e6, "D_m2_s": 5.38e-6,
                                          "center": 30.0, "halfwidth": 4.0})
        self.assertRegex(k["locator"], r"^Table 3")

    def test_gan_data1_ti64_rows_as_published(self):
        d = kl.load_gan_data1_ti64()
        rows = d["rows"]
        self.assertEqual(len(rows), 71)
        self.assertEqual(sum(r["beamDiameter_um"] == 95.0 for r in rows), 48)
        self.assertEqual(sum(r["beamDiameter_um"] == 140.0 for r in rows), 23)
        self.assertTrue(all(r["r0_um"] * 2 == r["beamDiameter_um"] for r in rows))
        r = rows[0]
        self.assertEqual((r["power_W"], r["speed_mm_s"], r["keyholeDepth_um"]), (103.198, 400.0, 33.008))
        self.assertEqual(r["ganTable1"]["rho_kg_m3"], 3920.0)
        self.assertEqual(d["provenance"]["source"]["sha256"], kl.GAN_DATA1_XLSX_SHA256)
        self.assertEqual(d["provenance"]["rows"], 71)

    def test_gan_keyhole_number_by_hand(self):
        # Ti-6Al-4V-like inputs: rho 4430, cp 526, k 6.7, Tl 1660, T0 20, eta_m 0.26, 300 W, 700 mm/s, 95 um
        g = kl.gan_keyhole_number(300, 700, 95, 4430, 526, 6.7, 1660, 20, 0.26)
        r0, v, dT = 47.5e-6, 0.7, 1640.0
        kml = 0.26 * 300 / (dT * math.pi * 4430 * 526 * v * r0 ** 2)
        eta = 0.7 * (1 - math.exp(-0.6 * kml))
        ke = eta * 300 / (dT * math.pi * 4430 * 526 * math.sqrt(6.7 / (4430 * 526) * v * r0 ** 3))
        self.assertAlmostEqual(g["KemLd"], kml, places=9)
        self.assertAlmostEqual(g["Ke"], ke, places=9)
        self.assertAlmostEqual(g["Ke"], 34.52, places=1)
        self.assertEqual(kl.gan_regime(1.0), "conduction")
        self.assertEqual(kl.gan_regime(6.0), "transition")
        self.assertEqual(kl.gan_regime(6.01), "keyhole")
        self.assertAlmostEqual(kl.gan_keyhole_depth_um(6.4, 100), 0.4 * 5.0 * 50, places=9)
        self.assertEqual(kl.gan_keyhole_depth_um(1.0, 100), 0.0)

    def test_huang_product_and_hann_relation(self):
        # beta P / (sqrt(pi) hm v r^2): 0.26*561/(sqrt(pi)*6.26e9*0.6*(50e-6)^2)
        self.assertAlmostEqual(kl.huang_enthalpy_product(561, 600, 100, 0.26),
                               0.26 * 561 / (math.sqrt(math.pi) * 6.26e9 * 0.6 * 2.5e-9), places=9)
        self.assertAlmostEqual(kl.hann_depth_relation_as_printed(5.0), 2.0, places=12)
        self.assertAlmostEqual(kl.hann_depth_relation_as_printed(26.0), 4.0, places=12)
        self.assertEqual(kl.hann_depth_relation_as_printed(0.5), 0.0)
        self.assertEqual(kl.hann_regime(12.0), "not-keyhole")
        self.assertEqual(kl.hann_regime(12.5), "keyhole")


if __name__ == "__main__":
    unittest.main()
