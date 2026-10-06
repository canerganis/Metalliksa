"""Check the local NIST Table 4 transcription against the pinned publisher XLSX."""
import hashlib
import json
import math
import statistics
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "data/benchmark/nist-amb2022-03-optical/official"
WORKBOOK = OFFICIAL / "AMB2022-718-SH1-MeltPool_Cross-Section_Measurement_Results.xlsx"
AGGREGATE = ROOT / "data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json"
NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def workbook_rows(path):
    with ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(part.text or "" for part in item.findall(".//m:t", NS))
                      for item in root.findall("m:si", NS)]
        sheet = workbook.find("m:sheets/m:sheet", NS)
        target = targets[sheet.attrib[f"{{{NS['r']}}}id"]].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ET.fromstring(archive.read(target))
        rows = []
        for row in root.findall(".//m:sheetData/m:row", NS):
            values = {}
            for cell in row.findall("m:c", NS):
                column = "".join(char for char in cell.attrib["r"] if char.isalpha())
                value = cell.find("m:v", NS)
                text = value.text if value is not None else ""
                if cell.attrib.get("t") == "s" and text:
                    text = shared[int(text)]
                values[column] = text
            rows.append(values)
        return rows


class NistOpticalTranscriptionTests(unittest.TestCase):
    def test_complete_publisher_cases_match_the_local_aggregate(self):
        manifest = json.loads((OFFICIAL / "manifest.json").read_text(encoding="utf-8"))
        workbook_entry = manifest["files"][0]
        workbook_bytes = WORKBOOK.read_bytes()
        digest = hashlib.sha256(workbook_bytes).hexdigest()
        publisher_checksum = (OFFICIAL / (WORKBOOK.name + ".sha256")).read_text(encoding="utf-8").strip()
        self.assertEqual(len(workbook_bytes), workbook_entry["bytes"])
        self.assertEqual(digest, workbook_entry["sha256"])
        self.assertEqual(digest, publisher_checksum)

        rows = workbook_rows(WORKBOOK)
        header = rows[0]
        labels = {value: column for column, value in header.items()}
        required = ("Sample", "Part No.", "Position (mm)", "Case and Line No.",
                    "Velocity (mm/s)", "Power (W)", "Beam diameter (gauss, avg) (µm)",
                    "Depth (µm)", "Width (µm)")
        self.assertTrue(all(label in labels for label in required), labels)
        aggregate = json.loads(AGGREGATE.read_text(encoding="utf-8"))

        complete_cases = set()
        for case in aggregate["cases"]:
            prefix = f"Line {case['caseNumber']}_"
            selected = [row for row in rows[1:]
                        if row.get(labels["Sample"]) == "AMB2022-718-SH1-BP1"
                        and row.get(labels["Part No."]) in {"P3", "P4"}
                        and row.get(labels["Case and Line No."], "").startswith(prefix)]
            if len(selected) != 6:
                continue
            complete_cases.add(case["caseNumber"])
            self.assertEqual({row[labels["Part No."]] for row in selected}, {"P3", "P4"})
            self.assertEqual({round(float(row[labels["Position (mm)"]]), 1) for row in selected}, {4.9, 6.0})
            for field, column in (("Velocity (mm/s)", "scanSpeed_mm_s"),
                                  ("Power (W)", "laserPower_W"),
                                  ("Beam diameter (gauss, avg) (µm)", "beamDiameterD4sigma_um")):
                values = {float(row[labels[field]]) for row in selected}
                self.assertEqual(values, {float(case[column])}, (case["caseNumber"], field))

            for quantity, source_column, mean_key, std_key in (
                ("depth", "Depth (µm)", "depthMean_um", "depthStdDev_um"),
                ("width", "Width (µm)", "widthMean_um", "widthStdDev_um"),
            ):
                observations = [float(row[labels[source_column]]) for row in selected]
                self.assertTrue(math.isclose(statistics.mean(observations), case[mean_key], abs_tol=0.051),
                                (case["caseNumber"], quantity, "mean"))
                self.assertTrue(math.isclose(statistics.stdev(observations), case[std_key], abs_tol=0.051),
                                (case["caseNumber"], quantity, "sample standard deviation"))

        # This workbook release fully exposes these three Table 4 conditions;
        # the remaining conditions are incomplete/missing in this artifact.
        self.assertEqual(complete_cases, {"0", "1.1", "1.2"})

    def test_case0_original_micrographs_match_publisher_hashes_and_rows(self):
        image_root = OFFICIAL / "single-track-case0"
        manifest = json.loads((image_root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["datasetId"], "nist-amb2022-03-optical-case0-micrographs-v1")
        self.assertEqual(manifest["material"], "IN718")
        self.assertEqual(manifest["processScope"], "bare-plate-single-track")
        self.assertEqual(manifest["processConditions"], {
            "laserPower_W": 285, "scanSpeed_mm_s": 960, "beamDiameterD4sigma_um": 67,
        })
        self.assertEqual(manifest["measurementMethod"]["pixelScale_um_per_pixel"], 0.069)
        self.assertEqual(len(manifest["files"]), 6)
        self.assertEqual(len(manifest["measurements"]), 6)

        rows = workbook_rows(WORKBOOK)
        labels = {value: column for column, value in rows[0].items()}
        publisher_rows = {
            (row[labels["Case and Line No."]], row[labels["Part No."]]): row
            for row in rows[1:]
            if row.get(labels["Sample"]) == "AMB2022-718-SH1-BP1"
            and row.get(labels["Part No."]) in {"P3", "P4"}
            and row.get(labels["Case and Line No."], "").startswith("Line 0_")
        }
        self.assertEqual(set(publisher_rows), {
            (item["caseAndLine"], item["part"]) for item in manifest["measurements"]
        })

        for artifact, measurement in zip(manifest["files"], manifest["measurements"], strict=True):
            relative = Path(artifact["path"])
            self.assertFalse(relative.is_absolute())
            image_path = OFFICIAL / relative
            publisher_hash = (OFFICIAL / artifact["publisherSha256Sidecar"]).read_text(encoding="ascii").strip()
            image_bytes = image_path.read_bytes()
            digest = hashlib.sha256(image_bytes).hexdigest()
            self.assertEqual(len(image_bytes), artifact["bytes"])
            self.assertEqual(digest, artifact["sha256"])
            self.assertEqual(digest, publisher_hash)
            self.assertNotIn("_m.tif", image_path.name)

            row = publisher_rows[(measurement["caseAndLine"], measurement["part"])]
            self.assertEqual(measurement["imagePath"], artifact["path"])
            self.assertEqual(measurement["part"], row[labels["Part No."]])
            self.assertEqual(measurement["laserPower_W"], float(row[labels["Power (W)"]]))
            self.assertEqual(measurement["scanSpeed_mm_s"], float(row[labels["Velocity (mm/s)"]]))
            self.assertEqual(measurement["beamDiameterD4sigma_um"], float(row[labels["Beam diameter (gauss, avg) (µm)"]]))
            self.assertEqual(measurement["measuredDepth_um"], float(row[labels["Depth (µm)"]]))
            self.assertEqual(measurement["measuredWidth_um"], float(row[labels["Width (µm)"]]))


if __name__ == "__main__":
    unittest.main()
