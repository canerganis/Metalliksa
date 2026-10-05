#!/usr/bin/env python3
"""Typed loaders for two public single-track melt-pool datasets (comparison inputs only).

Datasets (both CC BY 4.0, measured; nothing here is a calibration or a validation):

* Hofmann et al. 2026, 316L single tracks (Zenodo 10.5281/zenodo.16979848), 677 rows.
* Totis / Vaglio et al. 2021, Ti-6Al-4V single tracks (Mendeley Data
  10.17632/s9438vb5xd.1), 80 rows (8 powers x 10 speeds, n = 1 per cell).

The committed small derived tables live in ``data/benchmark/``; the loaders read them by
default and verify their SHA-256 against the pinned values below. The raw Hofmann CSV and the
Totis ``Allegati.zip`` / ``Data.xlsx`` can be parsed too (stdlib only: csv, zipfile, xml.etree;
no new dependency) and ``build`` regenerates the committed tables from them.

Units are normalised to the repo's process inputs: power W, speed mm/s, lengths um.
``preheat_C`` is an ASSUMPTION (20 C room temperature): neither dataset states a build-plate
temperature in the files read here.

Regime screening (``classify_regime``) is an a-priori classifier from process inputs and the
dataset's own balling flag. It is NOT the papers' regime definition.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

REPO_ROOT = Path(__file__).resolve().parent.parent
HOFMANN_DIR = REPO_ROOT / "data" / "benchmark" / "hofmann-316l-2026"
TOTIS_DIR = REPO_ROOT / "data" / "benchmark" / "totis-ti64-2021"
HOFMANN_TABLE = HOFMANN_DIR / "meltpool_geometry.csv"
TOTIS_TABLE = TOTIS_DIR / "tracks.csv"

# SHA-256 of the committed derived tables (verified at load) -- see build_*_table().
HOFMANN_TABLE_SHA256 = "d4bbc7a60b536118586f44b64beb0fa20f94133f6d1a8d0fdcf726003720c3d8"
TOTIS_TABLE_SHA256 = "3b5794f3a25a5f67fa0d8d1ab006834205ef820b046c24deb15836025825d623"
CMU_DIR = REPO_ROOT / "data" / "benchmark" / "cmu-ti64-2026"
CMU_ST_TABLE = CMU_DIR / "st_measurements.csv"
CMU_MT_TABLE = CMU_DIR / "mt_measurements.csv"
KU_LEUVEN_DIR = REPO_ROOT / "data" / "benchmark" / "ku-leuven-in718-2021"
KU_LEUVEN_TABLE = KU_LEUVEN_DIR / "measurements.csv"
# SHA-256 pins for the compact committed derivative files (set by build_*_table).
CMU_ST_TABLE_SHA256 = "7f415afb20cd8e1698efcbc4948654ed4b95bb4fc1854b5c1e7f45e9874a1f90"
CMU_MT_TABLE_SHA256 = "d8d318fd673c69ad250a9d44cc7b37b71d3706cde7ad93539049454aedf09c57"
KU_LEUVEN_TABLE_SHA256 = "d8731ecc5cd027e697e4fbd7f9dabb634c197f0325f4282eb3c86ce9ff9d512b"

ASSUMED_PREHEAT_C = 20.0

HOFMANN_SOURCE = {
    "raw_file": "MeltpoolGeometryData.csv",
    "raw_bytes": 29660,
    "raw_md5": "2c107f3ac12cd38a0f1eb9f75a469000",
    "raw_sha256": "5dd0629b3add839997fd54c3e4d89f90c1f2e4e5e717bede2c72e0c58cefd417",
}
TOTIS_SOURCE = {
    "raw_file": "Allegati.zip :: Allegati/Data.xlsx",
    "raw_bytes": 20097,
    "raw_sha256": "3211cbaa9fe29f1126ea25666cb6de902335aa4cd974dc0918d1c247a31c1e42",
}

HOFMANN_PROVENANCE = {
    "id": "hofmann-316l-2026",
    "doi": "10.5281/zenodo.16979848",
    "url": "https://zenodo.org/records/16979848",
    "license": "CC BY 4.0",
    "citation": ("Hofmann et al., melt-pool geometry data for 316L single tracks (Aconity Midi), Zenodo "
                 "10.5281/zenodo.16979848 (v1, 2025-08-28); associated paper Materials & Design 262 (2026) "
                 "115459, doi:10.1016/j.matdes.2026.115459."),
    "material": "316L Stainless Steel",
    "caveats": [
        "Measured cross-sections from micrographs; the uncertainty budget is not stated in the files read.",
        "The d_laser column is the laser spot DIAMETER in mm; the diameter definition (1/e^2 or other) is not "
        "stated on the Zenodo record and was not confirmed from the paper: treated as 1/e^2 by assumption.",
        "Absorptivity is not measured; the comparison uses the repo's estimated 316L absorptivity.",
        "Build-plate temperature is not given: 20 C is an assumption.",
        "t_powder = 0 rows are bare plate; t_powder 30/60 um are powder layers (the packing is not stated).",
        "The CSV header calls the area column 'um' although the values are um^2 (width x depth scale confirms).",
        "677 rows contain repeated parameter sets (623 distinct) -- replicates are kept as separate rows.",
        "Where the width/depth are taken along the track and whether the section is at steady state is not "
        "stated in the files read.",
        "316L thermophysical properties used by the models are estimated, not measured.",
    ],
}
TOTIS_PROVENANCE = {
    "id": "totis-ti64-2021",
    "doi": "10.17632/s9438vb5xd.1",
    "url": "https://data.mendeley.com/datasets/s9438vb5xd/1",
    "license": "CC BY 4.0",
    "citation": ("Totis, Vaglio et al., single-track Ti6Al4V SEM images and geometrical data (Concept Laser M2, "
                 "50 um laser spot), Mendeley Data, 10.17632/s9438vb5xd.1 (v1, 2021-04-26); related article "
                 "Data in Brief, doi:10.1016/j.dib.2020.106443."),
    "material": "Ti-6Al-4V",
    "caveats": [
        "Tracks were made on a 25 um powder layer over a printed Ti-6Al-4V base (not a bare plate, not a "
        "semi-infinite wrought substrate); the 50 um spot is taken as 1/e^2 from the research note.",
        "The workbook does not state the depth reference line (original substrate surface vs powder surface): "
        "depth is used 'as found'; the Mendeley page and the workbook do not say.",
        "One track per (power, speed) cell: no replicates, no scatter estimate.",
        "Absorptivity is not measured; the comparison uses the repo's estimated Ti-6Al-4V absorptivity.",
        "Build-plate temperature is not given: 20 C is an assumption.",
        "No balling flag in the workbook: the regime classifier uses inputs only for this dataset.",
        "Width, depth and height are SEM-derived values read from the workbook sheets 'Track width (W)', "
        "'Track depth (D)', 'Track height (H)', 'Contact angle' (microhardness sheet not used).",
        "Ti-6Al-4V thermophysical properties used by the models are estimated, not measured.",
    ],
}

ENTHALPY_TRANSITION = 15.0
ENTHALPY_KEYHOLE = 30.0
REGIME_RULE = (
    "Screening classifier, not the papers' regime definition. Inputs: normalised enthalpy "
    "dH/h_s = eta*P / (rho*cp_s*max(50, T_liq-T0)*sqrt(pi*alpha_s*v*r^3)) (same form as "
    "lpbf_thermal_solver.py, flat-plate absorptivity_IR of the material authority, solid k/cp, r = d/2) "
    "and the dataset's own balling flag. balling == 1 -> 'balling-flagged' (Hofmann only); otherwise "
    "dH/h_s < 15 -> 'conduction', 15 <= dH/h_s < 30 -> 'transition', >= 30 -> 'keyhole'. "
    "Measured D/W is recorded next to the label but not used for it."
)
REGIME_PARAMETERS = {"transitionEnthalpy": ENTHALPY_TRANSITION, "keyholeEnthalpy": ENTHALPY_KEYHOLE,
                     "balledLabel": "balling-flagged", "assumedPreheat_C": ASSUMED_PREHEAT_C}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Union[str, Path]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------
# Hofmann 316L
# ---------------------------------------------------------------------------------------------
HOFMANN_TABLE_COLUMNS = ["index", "P_laser_W", "v_scan_mm_s", "d_laser_mm", "t_powder_um",
                         "weld_width_um", "penetration_depth_um", "molten_area_um2", "balling"]


def _read_hofmann_raw_rows(text: str) -> List[List[str]]:
    """Parse either the raw Zenodo CSV (quoted header with a blank first column) or the committed table."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    first = lines[0]
    if first.startswith("index,"):
        body = lines[1:]
    else:
        body = lines[1:]  # raw header is one quoted pseudo-field; the data rows are plain
    return [row for row in csv.reader(body)]


def _hofmann_rows(rows: List[List[str]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        if len(r) != 9:
            raise ValueError(f"Hofmann row has {len(r)} fields, expected 9: {r}")
        idx = int(r[0])
        d_mm = float(r[3])
        t_powder = float(r[4])
        out.append({
            "dataset": HOFMANN_PROVENANCE["id"],
            "rowId": f"hofmann-{idx:04d}",
            "material": HOFMANN_PROVENANCE["material"],
            "power_W": float(r[1]),
            "speed_mm_s": float(r[2]),
            "beamDiameter_um": round(d_mm * 1000.0, 6),
            "layer_um": t_powder,
            "preheat_C": ASSUMED_PREHEAT_C,
            "width_um": float(r[5]),
            "depth_um": float(r[6]),
            "area_um2": float(r[7]),
            "balling": int(float(r[8])),
            "height_um": None,
            "hatch_um": None,
        })
    return out


def load_hofmann_316l(path: Optional[Union[str, Path]] = None, verify: bool = True) -> Dict[str, Any]:
    """Return {"rows": [...], "provenance": {...}}. Default: committed derived table, sha256 verified."""
    src = Path(path) if path is not None else HOFMANN_TABLE
    data = src.read_bytes()
    digest = sha256_bytes(data)
    is_committed = Path(src).resolve() == HOFMANN_TABLE.resolve()
    if verify and is_committed and digest != HOFMANN_TABLE_SHA256:
        raise ValueError(f"Hofmann table sha256 mismatch: {digest} != {HOFMANN_TABLE_SHA256}")
    rows = _hofmann_rows(_read_hofmann_raw_rows(data.decode("utf-8-sig")))
    prov = dict(HOFMANN_PROVENANCE)
    prov.update(file=str(src.name), fileSha256=digest, rows=len(rows), source=dict(HOFMANN_SOURCE),
                columns={"P_laser_W": "W", "v_scan_mm_s": "mm/s",
                         "d_laser_mm": "mm (spot diameter; definition unconfirmed)",
                         "t_powder_um": "um", "weld_width_um": "um", "penetration_depth_um": "um",
                         "molten_area_um2": "um^2 (source header says um)", "balling": "0/1 flag from the dataset"})
    return {"rows": rows, "provenance": prov}


def build_hofmann_table(raw_csv: Union[str, Path], out: Union[str, Path] = HOFMANN_TABLE) -> str:
    """Rewrite the raw CSV as a clean table (values copied verbatim as text). Returns its sha256."""
    text = Path(raw_csv).read_bytes().decode("utf-8-sig")
    rows = _read_hofmann_raw_rows(text)
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HOFMANN_TABLE_COLUMNS)
    for r in rows:
        w.writerow(r)
    data = buf.getvalue().encode("utf-8")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(data)
    return sha256_bytes(data)


# ---------------------------------------------------------------------------------------------
# Totis Ti-6Al-4V (xlsx via stdlib)
# ---------------------------------------------------------------------------------------------
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
TOTIS_SHEETS = {"Track width (W)": "width_um", "Track depth (D)": "depth_um", "Track height (H)": "height_um",
                "Contact angle (ϑ)": "contactAngle_deg"}
TOTIS_TABLE_COLUMNS = ["power_W", "speed_mm_s", "width_um", "depth_um", "height_um", "contact_angle_deg"]
TOTIS_BEAM_UM = 50.0
TOTIS_LAYER_UM = 25.0


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


def _read_xlsx_grids(xlsx_bytes: bytes) -> Dict[str, Dict[str, str]]:
    """{sheet name: {cell ref: text value}} using only zipfile + ElementTree."""
    zf = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    shared = []
    if "xl/sharedStrings.xml" in zf.namelist():
        for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    target = {rel.get("Id"): rel.get("Target") for rel in rels}
    sheets: Dict[str, Dict[str, str]] = {}
    for sh in wb.find("m:sheets", _NS):
        name = sh.get("name")
        rid = sh.get("{%s}id" % _NS["r"])
        root = ET.fromstring(zf.read("xl/" + target[rid]))
        cells: Dict[str, str] = {}
        for c in root.iter("{%s}c" % _NS["m"]):
            v = c.find("m:v", _NS)
            if v is None or v.text is None:
                continue
            cells[c.get("r")] = shared[int(v.text)] if c.get("t") == "s" else v.text
        sheets[name] = cells
    return sheets


def _totis_rows_from_xlsx(xlsx_bytes: bytes) -> List[Dict[str, Any]]:
    grids = _read_xlsx_grids(xlsx_bytes)
    rows: Dict[tuple, Dict[str, Any]] = {}
    for sheet, field in TOTIS_SHEETS.items():
        if sheet not in grids:
            raise ValueError(f"Totis workbook lacks sheet {sheet!r}; found {sorted(grids)}")
        cells = grids[sheet]
        speeds = {}  # column letter -> speed
        for ref, val in cells.items():
            m = re.fullmatch(r"([A-Z]+)4", ref)
            if m and _col_index(ref) >= 3:
                speeds[m.group(1)] = float(val)
        for r in range(5, 13):
            power = float(cells[f"B{r}"])
            for col, speed in speeds.items():
                ref = f"{col}{r}"
                if ref in cells:
                    rows.setdefault((power, speed), {})[field] = float(cells[ref])
    out = []
    for (power, speed) in sorted(rows):
        v = rows[(power, speed)]
        out.append({"power_W": power, "speed_mm_s": speed, **v})
    if len(out) != 80 or any(len(v) != 6 for v in out):
        raise ValueError(f"Totis workbook parse produced {len(out)} cells; expected 80 complete")
    return out


def _totis_typed(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    typed = []
    for i, r in enumerate(rows, 1):
        typed.append({
            "dataset": TOTIS_PROVENANCE["id"],
            "rowId": f"totis-{int(r['power_W']):03d}W-{int(r['speed_mm_s']):04d}mms",
            "material": TOTIS_PROVENANCE["material"],
            "power_W": r["power_W"],
            "speed_mm_s": r["speed_mm_s"],
            "beamDiameter_um": TOTIS_BEAM_UM,
            "layer_um": TOTIS_LAYER_UM,
            "preheat_C": ASSUMED_PREHEAT_C,
            "width_um": r["width_um"],
            "depth_um": r["depth_um"],
            "area_um2": None,
            "balling": None,
            "height_um": r["height_um"],
            "contactAngle_deg": r["contactAngle_deg"],
            "hatch_um": None,
        })
    return typed


def _totis_rows_from_csv(text: str) -> List[Dict[str, Any]]:
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        out.append({"power_W": float(r["power_W"]), "speed_mm_s": float(r["speed_mm_s"]),
                    "width_um": float(r["width_um"]), "depth_um": float(r["depth_um"]),
                    "height_um": float(r["height_um"]), "contactAngle_deg": float(r["contact_angle_deg"])})
    return out


def load_totis_ti64(path_or_zip: Optional[Union[str, Path]] = None, verify: bool = True) -> Dict[str, Any]:
    """Return {"rows": [...], "provenance": {...}}. Accepts the committed CSV (default), Data.xlsx or Allegati.zip."""
    src = Path(path_or_zip) if path_or_zip is not None else TOTIS_TABLE
    suffix = src.suffix.lower()
    data = src.read_bytes()
    digest = sha256_bytes(data)
    if suffix == ".zip":
        with zipfile.ZipFile(src) as zf:
            xbytes = zf.read("Allegati/Data.xlsx")
        raw_rows = _totis_rows_from_xlsx(xbytes)
    elif suffix == ".xlsx":
        raw_rows = _totis_rows_from_xlsx(data)
    else:
        if verify and src.resolve() == TOTIS_TABLE.resolve() and digest != TOTIS_TABLE_SHA256:
            raise ValueError(f"Totis table sha256 mismatch: {digest} != {TOTIS_TABLE_SHA256}")
        raw_rows = _totis_rows_from_csv(data.decode("utf-8-sig"))
    rows = _totis_typed(raw_rows)
    prov = dict(TOTIS_PROVENANCE)
    prov.update(file=src.name, fileSha256=digest, rows=len(rows), source=dict(TOTIS_SOURCE),
                columns={"power_W": "W", "speed_mm_s": "mm/s", "width_um": "um (SEM cross-section)",
                         "depth_um": "um (reference line not stated)", "height_um": "um",
                         "contactAngle_deg": "deg"})
    return {"rows": rows, "provenance": prov}


def build_totis_table(zip_or_xlsx: Union[str, Path], out: Union[str, Path] = TOTIS_TABLE) -> str:
    src = Path(zip_or_xlsx)
    if src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src) as zf:
            xbytes = zf.read("Allegati/Data.xlsx")
    else:
        xbytes = src.read_bytes()
    rows = _totis_rows_from_xlsx(xbytes)
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(TOTIS_TABLE_COLUMNS)
    for r in rows:
        w.writerow([int(r["power_W"]),
                    int(r["speed_mm_s"]), repr(r["width_um"]), repr(r["depth_um"]),
                    repr(r["height_um"]), repr(r["contactAngle_deg"])])
    data = buf.getvalue().encode("utf-8")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(data)
    return sha256_bytes(data)


# ---------------------------------------------------------------------------------------------
# CMU Ti-6Al-4V variability and KU Leuven IN718 (comparison-only source records)
# ---------------------------------------------------------------------------------------------
CMU_DOI = "10.1184/R1/25696293.v1"
CMU_FILES = {
    "STMeasurements.csv": {
        "header": ["Slice", "Orientation (degrees)", "Velocity (mm/s)", "Width (um)", "Depth (um)", "Cap (um)"],
        "id": "cmu-ti64-st-2026", "sha256": "2e6db89484a91b8c8c5112bc1f68dbe7388dfddea19d92428e4ae160e0372e5c",
        "rows": 216, "has_power": False,
    },
    "MTMeasurements.csv": {
        "header": ["Slice", "Orientation (degrees)", "Power (W)", "Velocity (mm/s)", "Width (um)", "Depth (um)", "Cap (um)"],
        "id": "cmu-ti64-mt-2026", "sha256": "871a915a3850754af3174c2cd14295d3351ab745bed4f3a9a4bc31d8dd693743",
        "rows": 410, "has_power": True,
    },
}
KU_LEUVEN_PROVENANCE = {
    "id": "ku-leuven-in718-2021", "doi": "10.6084/m9.figshare.15035706.v1",
    "url": "https://doi.org/10.6084/m9.figshare.15035706.v1", "license": "CC0",
    "citation": "KU Leuven IN718 melt-pool measurements, Figshare, 10.6084/m9.figshare.15035706.v1.",
    "material": "Inconel 718",
    "caveats": ["Source CSV does not state units for w exp/d exp; article describes half-width, so dimensions are retained as source values and excluded from numeric comparison until resolved.",
                 "48 numbered conditions; 38 contain both dimensions and 10 have missing dimensions.",
                 "Condition means, not individual cross-sections; source sample counts vary.",
                 "Paper reports 37.5 um spot and 60 um powder layer; preheat and measured absorptivity are not reported."],
}
CMU_PROVENANCE = {
    "id": "cmu-ti64-2026", "doi": CMU_DOI, "url": "https://doi.org/" + CMU_DOI,
    "license": "CC BY 4.0", "citation": "CMU KiltHub, Ti-6Al-4V melt-pool variability, 10.1184/R1/25696293.v1.",
    "material": "Ti-6Al-4V",
    "caveats": ["STMeasurements.csv has no power column; power is not inferred.",
                 "Neither CMU table reports beam diameter, layer thickness, preheat or absorptivity; rows are source measurements only and excluded from kernel prediction.",
                 "Slice is an index and does not establish independent process conditions; ST measurements were not used in the manuscript."],
}
CMU_TABLE_COLUMNS = ["dataset", "source_file", "source_row", "slice", "orientation_deg", "power_W", "speed_mm_s", "width_um", "depth_um", "cap_um"]
KU_TABLE_COLUMNS = ["sample", "power_W", "speed_mm_s", "source_width", "source_depth", "sample_count"]


def _finite_or_none(value: str, label: str) -> Optional[float]:
    if not value.strip():
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"invalid numeric {label}") from exc
    if not math.isfinite(number):
        raise ValueError(f"nonfinite numeric {label}")
    return None if number == -1 else number


def parse_cmu_table(text: str, filename: str) -> List[Dict[str, Any]]:
    """Parse the publisher CSV strictly; ST genuinely lacks power, so it stays missing."""
    spec = CMU_FILES.get(filename)
    if spec is None or len(text) > 2_000_000:
        raise ValueError(f"unsupported CMU table: {filename}")
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if reader.fieldnames != spec["header"]:
        raise ValueError(f"unexpected CMU columns or units in {filename}")
    out = []
    for line, item in enumerate(reader, 2):
        def value(column): return _finite_or_none(item[column], f"{filename}:{line}:{column}")
        sl, orient = value("Slice"), value("Orientation (degrees)")
        power = value("Power (W)") if spec["has_power"] else None
        speed, width, depth, cap = (value(name) for name in ("Velocity (mm/s)", "Width (um)", "Depth (um)", "Cap (um)"))
        if sl is None or sl < 1 or not sl.is_integer() or orient is None or not 0 <= orient < 360:
            raise ValueError(f"invalid slice/orientation at {filename}:{line}")
        if speed is None or speed <= 0 or (spec["has_power"] and (power is None or power <= 0)):
            raise ValueError(f"invalid process input at {filename}:{line}")
        if width is None or width <= 0 or depth is None or depth <= 0 or cap is None or cap < 0:
            raise ValueError(f"invalid measured geometry at {filename}:{line}")
        out.append({"source_file": filename, "source_row": line, "slice": int(sl), "orientation_deg": orient,
                    "power_W": power, "speed_mm_s": speed, "width_um": width, "depth_um": depth, "cap_um": cap})
    return out


def parse_ku_leuven_table(text: str) -> List[Dict[str, Any]]:
    """Parse numbered observations while preserving ambiguous geometry as source values."""
    if len(text) > 2_000_000:
        raise ValueError("KU Leuven table is oversized")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=";", strict=True)
    header = next(reader, None)
    if not header or header[:7] != ["Sample", "P", "v", "", "w exp", "d exp", "R exp"]:
        raise ValueError("unexpected KU Leuven columns")
    out = []
    for line, cells in enumerate(reader, 2):
        if len(cells) < 7 or not cells[0].strip().isdigit():
            continue  # source summary/model rows are not numbered observations
        if len(cells) < 6:
            raise ValueError(f"invalid KU Leuven field count at row {line}")
        sample = _finite_or_none(cells[0], f"row:{line}:Sample")
        if sample is None:
            continue
        if not sample.is_integer() or sample < 1:
            raise ValueError(f"invalid sample number at row {line}")
        power, speed = _finite_or_none(cells[1], "P"), _finite_or_none(cells[2], "v")
        if power is None or power <= 0 or speed is None or speed <= 0:
            raise ValueError(f"invalid process input at row {line}")
        w = _finite_or_none(cells[4].replace(",", "."), "w exp")
        d = _finite_or_none(cells[5].replace(",", "."), "d exp")
        # The source has ragged trailing summary columns; sample count is not used as an observation.
        n = int(cells[-1]) if cells[-1].strip().isdigit() else None
        out.append({"sample": int(sample), "power_W": power, "speed_mm_s": speed,
                    "source_width": w, "source_depth": d, "sample_count": int(n) if n is not None else None})
    return out


def _write_table(columns: List[str], rows: List[Dict[str, Any]], out: Path) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if row.get(c) is None else row.get(c) for c in columns])
    payload = buf.getvalue().encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    return sha256_bytes(payload)


def build_cmu_table(st_csv: Union[str, Path], mt_csv: Union[str, Path], st_out: Path = CMU_ST_TABLE,
                    mt_out: Path = CMU_MT_TABLE) -> tuple:
    st, mt = parse_cmu_table(Path(st_csv).read_text(encoding="utf-8-sig"), "STMeasurements.csv"), parse_cmu_table(Path(mt_csv).read_text(encoding="utf-8-sig"), "MTMeasurements.csv")
    for rows, dataset in ((st, "cmu-ti64-st-2026"), (mt, "cmu-ti64-mt-2026")):
        for row in rows:
            row["dataset"] = dataset
    return (_write_table(CMU_TABLE_COLUMNS, st, st_out), _write_table(CMU_TABLE_COLUMNS, mt, mt_out))


def build_ku_leuven_table(source: Union[str, Path], out: Path = KU_LEUVEN_TABLE) -> str:
    return _write_table(KU_TABLE_COLUMNS, parse_ku_leuven_table(Path(source).read_text(encoding="utf-8-sig")), out)


def _load_pinned_csv(path: Union[str, Path], expected: str, columns: List[str], label: str) -> List[Dict[str, str]]:
    src = Path(path)
    data = src.read_bytes()
    digest = sha256_bytes(data)
    if not expected:
        raise ValueError(f"{label} table sha256 pin is not configured")
    if digest != expected:
        raise ValueError(f"{label} table sha256 mismatch: {digest} != {expected}")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != columns:
        raise ValueError(f"unexpected {label} derived table columns")
    return list(reader)


def load_cmu_ti64(verify: bool = True) -> Dict[str, Any]:
    """Return strict ST/MT records; missing power/beam inputs remain missing."""
    rows = []
    hashes = {}
    for path, digest, file in ((CMU_ST_TABLE, CMU_ST_TABLE_SHA256, "STMeasurements.csv"),
                               (CMU_MT_TABLE, CMU_MT_TABLE_SHA256, "MTMeasurements.csv")):
        records = _load_pinned_csv(path, digest if verify else "", CMU_TABLE_COLUMNS, file)
        hashes[path.name] = sha256_file(path)
        for index, item in enumerate(records, 1):
            power = float(item["power_W"]) if item["power_W"] else None
            rows.append({"dataset": item["dataset"], "rowId": f"{item['dataset']}-{index:04d}", "material": CMU_PROVENANCE["material"],
                         "power_W": power, "speed_mm_s": float(item["speed_mm_s"]), "beamDiameter_um": None,
                         "layer_um": None, "preheat_C": None, "width_um": float(item["width_um"]),
                         "depth_um": float(item["depth_um"]), "area_um2": None, "balling": None,
                         "height_um": float(item["cap_um"]), "hatch_um": None, "slice": int(item["slice"]),
                         "orientation_deg": float(item["orientation_deg"]), "sourceFile": file})
    prov = dict(CMU_PROVENANCE)
    prov.update(file="STMeasurements.csv + MTMeasurements.csv", fileSha256=None, fileSha256ByName=hashes,
                rows=len(rows), source={"raw_sha256": dict((f, CMU_FILES[f]["sha256"]) for f in CMU_FILES)},
                columns={"power_W": "W (absent for ST)", "speed_mm_s": "mm/s", "width_um": "um", "depth_um": "um", "beamDiameter_um": "not reported"})
    return {"rows": rows, "provenance": prov}


def load_ku_leuven_in718(verify: bool = True) -> Dict[str, Any]:
    records = _load_pinned_csv(KU_LEUVEN_TABLE, KU_LEUVEN_TABLE_SHA256 if verify else "", KU_TABLE_COLUMNS, "KU Leuven")
    rows = []
    for item in records:
        w = float(item["source_width"]) if item["source_width"] else None
        d = float(item["source_depth"]) if item["source_depth"] else None
        rows.append({"dataset": KU_LEUVEN_PROVENANCE["id"], "rowId": f"ku-leuven-{int(item['sample']):02d}",
                     "material": KU_LEUVEN_PROVENANCE["material"], "power_W": float(item["power_W"]),
                     "speed_mm_s": float(item["speed_mm_s"]), "beamDiameter_um": 37.5, "layer_um": 60.0,
                     "preheat_C": ASSUMED_PREHEAT_C, "width_um": None, "depth_um": None,
                     "sourceWidthValue": w, "sourceDepthValue": d, "sourceDimensionUnits": "unresolved",
                     "sampleCount": int(item["sample_count"]) if item["sample_count"] else None,
                     "area_um2": None, "balling": None, "height_um": None, "hatch_um": None})
    prov = dict(KU_LEUVEN_PROVENANCE)
    prov.update(file=KU_LEUVEN_TABLE.name, fileSha256=sha256_file(KU_LEUVEN_TABLE), rows=len(rows),
                source={"raw_sha256": "029f5c6992bd261891b30966d3bcc01ff327cd2cf1c7a6963e94de075766e1e5"},
                columns={"P": "W", "v": "mm/s", "w exp": "units unresolved; half-width operator unresolved", "d exp": "units unresolved"})
    return {"rows": rows, "provenance": prov}


# ---------------------------------------------------------------------------------------------
# Regime screening
# ---------------------------------------------------------------------------------------------
def normalized_enthalpy(material: str, power_W: float, speed_mm_s: float, beam_diameter_um: float,
                        preheat_C: float) -> float:
    """dH/h_s with flat-plate absorptivity (same formula as lpbf_thermal_solver.py, King/Rubenchik)."""
    from four_alloy_materials import thermal_props
    props = thermal_props(material)
    if props is None:
        raise ValueError(f"Unsupported material {material!r}")
    v = speed_mm_s * 1e-3
    r = beam_diameter_um * 1e-6 / 2.0
    rho = props["density_kg_m3"]
    k_s = props["thermal_conductivity_W_mK"]
    cp_s = props["specific_heat_J_kgK"]
    alpha_s = k_s / (rho * cp_s)
    denom = rho * cp_s * max(50.0, props["liquidus_C"] - preheat_C) * math.sqrt(math.pi * alpha_s * v * r ** 3)
    return props["absorptivity_IR"] * power_W / max(1e-9, denom)


def classify_regime(material: str, power_W: float, speed_mm_s: float, beam_diameter_um: float,
                    preheat_C: float, balling: Optional[int] = None) -> Dict[str, Any]:
    h = normalized_enthalpy(material, power_W, speed_mm_s, beam_diameter_um, preheat_C)
    if balling == 1:
        label = "balling-flagged"
    elif h < ENTHALPY_TRANSITION:
        label = "conduction"
    elif h < ENTHALPY_KEYHOLE:
        label = "transition"
    else:
        label = "keyhole"
    return {"label": label, "normalizedEnthalpy": h}


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Rebuild the committed small derived tables from the raw downloads.")
    ap.add_argument("--hofmann-raw", help="MeltpoolGeometryData.csv")
    ap.add_argument("--totis-raw", help="Allegati.zip or Data.xlsx")
    a = ap.parse_args(argv)
    if a.hofmann_raw:
        print("hofmann table sha256", build_hofmann_table(a.hofmann_raw), "raw sha256", sha256_file(a.hofmann_raw))
    if a.totis_raw:
        print("totis table sha256", build_totis_table(a.totis_raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
