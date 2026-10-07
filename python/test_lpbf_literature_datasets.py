"""Wave 5 literature datasets (Ghosh 2018, Trapp 2017, Rubenchik 2015, Heigel 2020, Ye 2019): hash pins, row counts,
units, a locator and a digitized flag on every committed row, separation of digitized and printed values, refusal of
changed bytes, and that none of these sources entered the frozen calibration config.

Self-contained: only the committed CSVs under data/benchmark/ are read. The source PDFs are not in the repository
and are not needed (no network, no solver).
"""

import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lpbf_literature_datasets as lit  # noqa: E402
import lpbf_public_datasets as pds  # noqa: E402

ALL_LOADERS = {**lit.MELTPOOL_LOADERS, **lit.REFERENCE_LOADERS}


def _csv_rows(path):
    return list(csv.DictReader(io.StringIO(Path(path).read_text(encoding="utf-8"), newline="")))


class PinsAndProvenanceTests(unittest.TestCase):
    def test_every_committed_table_matches_its_pin(self):
        self.assertEqual(len(lit.PINNED_TABLES), 7)
        for path, digest in lit.PINNED_TABLES.items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(pds.sha256_file(path), digest, path.name)

    def test_every_row_has_a_locator_and_a_boolean_digitized_flag(self):
        for path in lit.PINNED_TABLES:
            rows = _csv_rows(path)
            self.assertTrue(rows, path.name)
            for r in rows:
                self.assertTrue(r["locator"].strip(), path.name)
                self.assertRegex(r["locator"], r"^(Fig\.|Table) ", path.name)
                self.assertIn(r["digitized"], ("true", "false"), path.name)

    def test_digitized_rows_live_only_in_files_named_digitized(self):
        for path in lit.PINNED_TABLES:
            flags = {r["digitized"] for r in _csv_rows(path)}
            if "digitized" in path.name:
                self.assertEqual(flags, {"true"}, path.name)
            else:
                self.assertEqual(flags, {"false"}, path.name)

    def test_every_dataset_has_citation_doi_licence_source_hash_and_caveats(self):
        for name, loader in ALL_LOADERS.items():
            prov = loader()["provenance"]
            for key in ("id", "doi", "citation", "license", "evidenceKind", "caveats", "fileSha256", "rows"):
                self.assertTrue(prov.get(key), (name, key))
            self.assertTrue(prov["doi"].startswith("10."), name)
            self.assertIn("article not redistributed", prov["license"], name)
            self.assertRegex(prov["source"]["sha256"], r"^[0-9a-f]{64}$", name)
            self.assertTrue(prov["source"]["file"].endswith(".pdf"), name)
            self.assertNotIn("validated", prov["evidenceKind"].lower(), name)

    def test_no_pdf_or_image_is_committed_in_the_dataset_folders(self):
        for folder in {p.parent for p in lit.PINNED_TABLES}:
            for f in folder.iterdir():
                self.assertNotIn(f.suffix.lower(), (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"), f)
            self.assertTrue((folder / "LICENSE-ATTRIBUTION.md").is_file(), folder)

    def test_changed_bytes_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            for name, table, loader in (("ghosh", "GHOSH_TRACKS_TABLE", lit.load_ghosh_in625),
                                        ("trapp", "TRAPP_ABS_TABLE", lit.load_trapp_absorptivity),
                                        ("heigel", "HEIGEL_TABLE", lit.load_heigel_in625_cooling)):
                src = getattr(lit, table)
                victim = Path(td) / f"{name}.csv"
                data = src.read_bytes()
                victim.write_bytes(data.replace(b"\n", b"\r\n", 1))
                with mock.patch.object(lit, table, victim):
                    with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                        loader()

    def test_sources_are_not_in_the_frozen_calibration_config(self):
        import lpbf_calibration_config as cc
        trainable = set(cc.CALIBRATION_CONFIG["dataRoles"]["trainable"]) | set(cc.TRAINABLE_SOURCES)
        sentinels = set(cc.CATALOG_SOURCES)
        for name in ALL_LOADERS:
            self.assertNotIn(name, trainable)
            self.assertNotIn(name, sentinels)


class MeltPoolRowTests(unittest.TestCase):
    def test_ghosh_tracks(self):
        d = lit.load_ghosh_in625()
        rows = d["rows"]
        self.assertEqual(len(rows), 7)
        self.assertTrue(all(r["material"] == "Inconel 625" and r["layer_um"] == 0.0 and r["preheat_C"] == 20.0
                            and r["beamDiameter_um"] == 140.0 for r in rows))
        self.assertEqual(sorted({r["power_W"] for r in rows}), [49.0, 122.0, 195.0])
        self.assertEqual(sorted({r["speed_mm_s"] for r in rows}), [200.0, 500.0, 800.0])
        self.assertTrue(all(r["digitized"] is False and "printed" in r["valueOrigin"] for r in rows))
        case7 = next(r for r in rows if r["case"] == 7)
        self.assertEqual((case7["power_W"], case7["speed_mm_s"], case7["width_um"], case7["depth_um"]),
                         (195.0, 800.0, 133.0, 38.0))
        case5 = next(r for r in rows if r["case"] == 5)
        self.assertEqual((case5["power_W"], case5["speed_mm_s"], case5["width_um"], case5["depth_um"]),
                         (195.0, 200.0, 259.0, 109.0))
        self.assertTrue(all(r["widthSigma_um"] == 1.0 for r in rows))
        self.assertEqual(len({r["rowId"] for r in rows}), 7)
        self.assertEqual(lit.load_ghosh_in625(beam_diameter_um=100.0)["rows"][0]["beamDiameter_um"], 100.0)
        self.assertIn("lane-in625-2020", d["provenance"]["overlap"])

    def test_ghosh_lengths_are_digitized_and_separate(self):
        rows = lit.load_ghosh_in625_lengths()["rows"]
        self.assertEqual(len(rows), 7)
        self.assertTrue(all(r["digitized"] is True and r["readUncertainty_um"] == 5.0 for r in rows))
        self.assertTrue(all(150.0 < r["length_um"] < 1000.0 and r["lengthSd_um"] > 0 for r in rows))
        self.assertNotIn("length_um", lit.load_ghosh_in625()["rows"][0])

    def test_trapp_tracks(self):
        rows = lit.load_trapp_316l_tracks()["rows"]
        self.assertEqual(len(rows), 11)
        self.assertTrue(all(r["material"] == "316L Stainless Steel" and r["speed_mm_s"] == 500.0
                            and r["beamDiameter_um"] == 60.0 and r["digitized"] is True for r in rows))
        self.assertEqual(sum(1 for r in rows if r["depth_um"] is None), 1)
        self.assertIsNone(next(r for r in rows if r["power_W"] == 117.0)["depth_um"])
        self.assertTrue(all(40.0 < r["width_um"] < 200.0 for r in rows))
        self.assertTrue(all(r["depth_um"] is None or 10.0 < r["depth_um"] < 500.0 for r in rows))
        labelled = [r for r in rows if r["powerLabel_W"] is not None]
        self.assertEqual(len(labelled), 9)
        self.assertTrue(all(abs(r["power_W"] - r["powerLabel_W"]) <= r["readUncertaintyPower_W"] for r in labelled))

    def test_all_meltpool_rows_have_kernel_inputs(self):
        rows = lit.all_meltpool_rows()
        self.assertEqual(len(rows), 18)
        for r in rows:
            for k in ("power_W", "speed_mm_s", "beamDiameter_um", "layer_um", "preheat_C", "width_um"):
                self.assertIsInstance(r[k], float, (r["rowId"], k))
            self.assertTrue(r["locator"])
            self.assertIn(r["digitized"], (True, False))


class ReferenceDataTests(unittest.TestCase):
    def test_trapp_absorptivity_series(self):
        rows = lit.load_trapp_absorptivity()["rows"]
        self.assertEqual(len(rows), 107)
        counts = {}
        for r in rows:
            counts[r["series"]] = counts.get(r["series"], 0) + 1
        self.assertEqual(counts, {"316L-disc-v100": 14, "316L-disc-v500": 15, "316L-disc-v1500": 14,
                                  "316L-powder-v100": 12, "316L-powder-v1500": 18, "W-disc-v1500": 18,
                                  "Al1100-disc-v1500": 16})
        self.assertTrue(all(0.0 < r["absorptivity"] < 1.0 and r["digitized"] is True for r in rows))
        self.assertTrue(all(r["wavelength_nm"] == 1070.0 and r["spot_1e2_diameter_um"] == 60.0 for r in rows))
        penetrated = [r for r in rows if r["flag"] and r["flag"].startswith("initially penetrated")]
        self.assertEqual(sorted(r["power_W"] for r in penetrated), [311.0, 356.0, 445.0, 534.0])
        self.assertTrue(all(r["series"] == "316L-disc-v1500" for r in penetrated))
        sat500 = max(r["absorptivity"] for r in rows if r["series"] == "316L-disc-v500")
        self.assertAlmostEqual(sat500, 0.79, delta=0.01)

    def test_rubenchik_powder_absorptivity(self):
        rows = lit.load_rubenchik_powder_absorptivity()["rows"]
        self.assertEqual(len(rows), 49)
        self.assertTrue(all(r["wavelength_nm"] == 970.0 and r["digitized"] is True for r in rows))
        self.assertTrue(all(r["absorptivityP05"] <= r["absorptivity"] <= r["absorptivityP95"] for r in rows))
        by_mat = {}
        for r in rows:
            by_mat.setdefault(r["material"], []).append(r["absorptivity"])
        self.assertEqual(sorted(by_mat), ["316 Stainless Steel", "Aluminium (99.9 %)", "Ti-6Al-4V"])
        self.assertTrue(all(0.58 < a < 0.68 for a in by_mat["316 Stainless Steel"]))
        self.assertTrue(all(0.62 < a < 0.74 for a in by_mat["Ti-6Al-4V"]))
        self.assertTrue(all(0.48 < a < 0.56 for a in by_mat["Aluminium (99.9 %)"]))
        self.assertFalse(any(r["series"] == "Ti64-A-8.9-1st" for r in rows))

    def test_heigel_table2(self):
        d = lit.load_heigel_in625_cooling()
        self.assertEqual(d["provenance"]["tableRows"], 10)
        rows = d["rows"]
        self.assertEqual(len(rows), 20)
        self.assertTrue(all(r["digitized"] is False and r["locator"].startswith("Table 2") for r in rows))
        bridge_odd = next(r for r in rows if r["feature"] == "Bridge" and r["layerParity"] == "odd")
        self.assertEqual((bridge_odd["n"], bridge_odd["mean_C_s"], bridge_odd["sd_C_s"]), (30329, 4.79e5, 1.81e5))
        self.assertTrue(all(1e4 < r["mean_C_s"] < 1e6 for r in rows))

    def test_ye_table1(self):
        rows = lit.load_ye_min_absorptivity()["rows"]
        self.assertEqual({r["material"]: r["absorptivity"] for r in rows},
                         {"Ti-6Al-4V": 0.26, "Inconel 625": 0.28, "316L Stainless Steel": 0.28})
        self.assertTrue(all(r["digitized"] is False for r in rows))

    def test_not_ingested_reasons_are_recorded(self):
        for key in ("levine2020", "yadroitsev2010", "lass2017", "keller2017", "simonds2021"):
            self.assertTrue(lit.NOT_INGESTED[key])


if __name__ == "__main__":
    unittest.main()
