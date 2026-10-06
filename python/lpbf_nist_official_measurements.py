"""Recompute AMB2022-03 BP1 optical aggregates from the official NIST XLSX.

This is a source audit, not a model-to-experiment validation operator.
"""

from collections import defaultdict
import hashlib
from pathlib import Path
import re
from statistics import mean, stdev
import xml.etree.ElementTree as ET
from zipfile import ZipFile


SOURCE_DIR = (Path(__file__).resolve().parents[1] / "data" / "benchmark" /
              "nist-amb2022-03-optical" / "official")
WORKBOOK_NAME = "AMB2022-718-SH1-MeltPool_Cross-Section_Measurement_Results.xlsx"
WORKBOOK_PATH = SOURCE_DIR / WORKBOOK_NAME
OFFICIAL_SHA256 = "2cfaac96aaca3dabb77b7029f842cdcc7e75c5a2cf3577d0734823246364a931"
OFFICIAL_BYTES = 25_811
SAMPLE = "AMB2022-718-SH1-BP1"
CASES = ("0", "1.1", "1.2", "2.1", "2.2", "3.1", "3.2")
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
LINE_RE = re.compile(r"Line (0|1\.1|1\.2|2\.1|2\.2|3\.1|3\.2)_([123])\Z")


def _verified_bytes(workbook_path, sidecar_path):
    workbook_path = Path(workbook_path)
    sidecar_path = Path(sidecar_path)
    expected = sidecar_path.read_text(encoding="ascii").strip()
    if expected != OFFICIAL_SHA256:
        raise ValueError("NIST workbook sidecar SHA-256 differs from pinned official digest")
    data = workbook_path.read_bytes()
    if len(data) != OFFICIAL_BYTES or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("NIST workbook size or SHA-256 mismatch")
    return data


def _sheet_rows(workbook_bytes):
    """Read only the needed OOXML types using the Python standard library."""
    from io import BytesIO

    with ZipFile(BytesIO(workbook_bytes)) as archive:
        shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(node.itertext()) for node in shared.findall("x:si", NS)]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    for row in sheet.findall("x:sheetData/x:row", NS):
        cells = {}
        for cell in row.findall("x:c", NS):
            value = cell.find("x:v", NS)
            if value is None:
                continue
            column = re.match(r"[A-Z]+", cell.attrib["r"]).group()
            cells[column] = strings[int(value.text)] if cell.get("t") == "s" else float(value.text)
        yield int(row.attrib["r"]), cells


def recompute_bp1_table4(workbook_path=WORKBOOK_PATH, sidecar_path=None):
    """Return all 42 BP1 source rows and seven six-observation sample aggregates.

    Each condition must have three line numbers, each measured at 4.9 and
    6.0 mm. Part identifiers are retained as source metadata; they vary even
    within case 2.1 and are not used to define measurement groups.
    """
    workbook_path = Path(workbook_path)
    if sidecar_path is None:
        sidecar_path = workbook_path.with_name(workbook_path.name + ".sha256")
    workbook_bytes = _verified_bytes(workbook_path, sidecar_path)
    groups = defaultdict(list)
    observations = []
    seen = set()
    for row_number, cells in _sheet_rows(workbook_bytes):
        if cells.get("A") != SAMPLE:
            continue
        line_label = cells.get("D", "")
        match = LINE_RE.fullmatch(line_label)
        if match is None:
            raise ValueError(f"Unexpected BP1 line at workbook row {row_number}")
        case, line = match.group(1), int(match.group(2))
        position = cells["C"]
        if position not in (4.9, 6.0):
            raise ValueError(f"Unexpected BP1 optical position at workbook row {row_number}")
        key = (case, line, position)
        if key in seen:
            raise ValueError(f"Duplicate BP1 optical section at workbook row {row_number}")
        seen.add(key)
        observation = {
            "row": row_number, "caseNumber": case, "lineNumber": line,
            "position_mm": position, "partNumber": cells["B"],
            "scanSpeed_mm_s": cells["E"], "laserPower_W": cells["F"],
            "beamDiameterGaussAvg_um": cells["G"],
            "depth_um": cells["H"], "width_um": cells["I"],
        }
        observations.append(observation)
        groups[case].append(observation)
    expected_keys = {(case, line, position) for case in CASES
                     for line in (1, 2, 3) for position in (4.9, 6.0)}
    if seen != expected_keys or len(observations) != 42:
        raise ValueError("BP1 workbook does not contain seven complete 3-by-2 conditions")
    cases = []
    for case in CASES:
        rows = groups[case]
        if len({(row["scanSpeed_mm_s"], row["laserPower_W"],
                 row["beamDiameterGaussAvg_um"]) for row in rows}) != 1:
            raise ValueError(f"BP1 process parameters vary within case {case}")
        first = rows[0]
        cases.append({
            "caseNumber": case, "observationCount": len(rows),
            "scanSpeed_mm_s": first["scanSpeed_mm_s"],
            "laserPower_W": first["laserPower_W"],
            "beamDiameterGaussAvg_um": first["beamDiameterGaussAvg_um"],
            "depthMean_um": mean(row["depth_um"] for row in rows),
            "depthStdDev_um": stdev(row["depth_um"] for row in rows),
            "widthMean_um": mean(row["width_um"] for row in rows),
            "widthStdDev_um": stdev(row["width_um"] for row in rows),
        })
    return {"sample": SAMPLE, "workbookSha256": OFFICIAL_SHA256,
            "observationCount": len(observations), "observations": observations,
            "cases": cases}
