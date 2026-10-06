"""Source audit for NIST mds2-2525 (time-resolved laser absorptance).

Reads the publisher files archived under
``data/benchmark/nist-mds2-2525-ti64-absorptance/official`` after verifying
their pinned byte counts and SHA-256 digests, and derives a small deterministic
summary.

Evidence rules:
- Spot/Scan "Bare Metal" tables are Ti-6Al-4V (NIST SRM 654b), ~300 um thin
  polished coupons without powder. They are measured values for NIST's
  experiment only.
- ``Al_*`` challenge tables are aluminium (NIST SRM 1241c), not Ti-6Al-4V.
- Window boundaries used here are local analysis choices, not NIST-published
  phase boundaries. Nothing here validates the application or any model.
"""

import csv
import hashlib
import io
import json
from pathlib import Path
from statistics import mean, median, stdev
import sys


DATASET_ID = "nist-mds2-2525-ti64-absorptance-v1"
DATASET_DIR = (Path(__file__).resolve().parents[1] / "data" / "benchmark" /
               "nist-mds2-2525-ti64-absorptance")
SOURCE_DIR = DATASET_DIR / "official"
DERIVED_PATH = DATASET_DIR / "derived" / "ti64-spot-absorptance-summary-v1.json"

_BASE = "https://data.nist.gov/od/ds/ark:/88434/mds2-2525/"
_BASE_SHORT = "https://data.nist.gov/od/ds/mds2-2525/"

SPOT_NAME = "Spot on Bare Metal_Calibrated Absorption Data.csv"
SCAN_NAME = "Scan on Bare Metal_Calibrated Absorption Data.csv"
AL_SPOT_AA = "Al_Spot_AA_ASR_Results.csv"
AL_SCAN_AA = "Al_Scan_AA_MWD_ASR_Results.csv"
AL_SPOT_TDW = "Al_Spot_TDW_Results.csv"
AL_SPOT_TDA = "Al_Spot_TDA_Results.csv"
AL_SCAN_TDA = "Al_Scan_TDA_v2_Results.csv"

AL_MATERIAL = "aluminium (NIST SRM 1241c)"
TI64_MATERIAL = "Ti-6Al-4V (NIST SRM 654b)"

OFFICIAL_FILES = {
    "2525_README_v200.txt": {
        "sha256": "936f4c166b448f4b5a27d1e2b2465f9c2db1be073a7bffd54d45eb4259120a65",
        "bytes": 21907, "source_url": _BASE + "2525_README_v200.txt",
        "wayback_timestamp": "20241217170746", "kind": "readme"},
    SPOT_NAME: {
        "sha256": "0e96b220852d762fde846e406cc44c6fc874cef22e7e41db7f4025dbcc9ca274",
        "bytes": 6497288,
        "source_url": _BASE_SHORT + "Spot%20on%20Bare%20Metal_Calibrated%20Absorption%20Data.csv",
        "wayback_timestamp": "20241217170645", "kind": "ti64-spot-absorptance-timeseries"},
    AL_SPOT_TDA: {
        "sha256": "3f0b6812f98535f5ffbb0e2fed31f084ad9a7f9cc393c04a43ed57f0bb14bf69",
        "bytes": 2292050, "source_url": _BASE + AL_SPOT_TDA,
        "wayback_timestamp": "20241217170821", "kind": "al-challenge-table"},
    AL_SCAN_TDA: {
        "sha256": "3af3478b463b867ed3c78ef6e60c75f9d613607b236933f3f9df08113884a6a8",
        "bytes": 2493685, "source_url": _BASE + AL_SCAN_TDA,
        "wayback_timestamp": "20241217170831", "kind": "al-challenge-table"},
    AL_SPOT_TDW: {
        "sha256": "06b280222eab5f82eb9dcfb0689f20a5011c16e115548cd94ce120e5a97b4f5c",
        "bytes": 2169, "source_url": _BASE + AL_SPOT_TDW,
        "wayback_timestamp": "20241217170826", "kind": "al-challenge-table"},
    AL_SPOT_AA: {
        "sha256": "4429f08ff3f571ab871fdbaf072e0c67aaef346259a3f2ca8744927ad6419ffb",
        "bytes": 242, "source_url": _BASE + AL_SPOT_AA,
        "wayback_timestamp": "20241217170715", "kind": "al-challenge-table"},
    AL_SCAN_AA: {
        "sha256": "d3732fcddaaee046105aa90eb82547ffd0fe61edb425fc1e8f019c6f73ed0b4d",
        "bytes": 364, "source_url": _BASE + AL_SCAN_AA,
        "wayback_timestamp": "20241217170730", "kind": "al-challenge-table"},
    "NIST SRM 654b Ti64 data sheet.pdf": {
        "sha256": "57a8295d6db46e723cb3f0eb63844a98527dc8c61bedfa934dba549bffe13740",
        "bytes": 67521,
        "source_url": _BASE_SHORT + "NIST%20SRM%20654b%20Ti64%20data%20sheet.pdf",
        "wayback_timestamp": "20241217170629", "kind": "srm-datasheet"},
    "nerdm-record-mds2-2525.json": {
        "sha256": "8388c6a21a7e4432ee23bfca17a45d3cd160ddfaf194d9607e5961d2eff03695",
        "bytes": 39359,
        "source_url": "https://data.nist.gov/rmm/records?@id=ark:/88434/mds2-2525",  # local file is a re-serialisation (sorted keys, indent 1)
        "wayback_timestamp": None, "kind": "nerdm-record"},
}

_ABSENT_REASON = ("NIST download timed out; no Internet Archive snapshot with the "
                  "official SHA-256 was available on 2026-10-06")
ABSENT_FILES = {
    SCAN_NAME: {
        "sha256": "1c64f24e84c274d9f9ae27fb09e79b86cda2fda5bee4b67da3567c8a59ca499d",
        "bytes": 6657476,
        "source_url": _BASE_SHORT + "Scan%20on%20Bare%20Metal_Calibrated%20Absorption%20Data.csv",
        "wayback_timestamp": None, "kind": "ti64-scan-absorptance-timeseries",
        "reason": _ABSENT_REASON},
    "Absorption_Uncertainty_Analysis.pdf": {
        "sha256": "98ead678e3a8f6696650302dbf29660f2a886a62ba677453dd130c222755e28d",
        "bytes": 388131,
        "source_url": _BASE_SHORT + "Absorption_Uncertainty_Analysis.pdf",
        "wayback_timestamp": None, "kind": "uncertainty-analysis-pdf",
        "reason": _ABSENT_REASON},
}

TI64_COLUMNS = ["", "Time", "InputLaser", "AbsoluteAbsorption", "AbsAbsorptionUncertainty",
                "RelativeAbsorption", "CameraTrigger", "FrameTrigger", "FrameNumber"]
SPOT_ROWS = 113_508
WINDOW_DEFINITION = (
    "Windows are measured from the first sample with input power above the laser-on threshold. "
    "They are local analysis windows chosen in this module, not NIST-published phase boundaries; "
    "NIST publishes before/during-keyhole averages only for the aluminium challenge tables."
)


def _entry(name):
    if name in OFFICIAL_FILES:
        return OFFICIAL_FILES[name]
    if name in ABSENT_FILES:
        return ABSENT_FILES[name]
    raise ValueError(f"unknown NIST mds2-2525 file: {name}")


def verified_bytes(name, root=SOURCE_DIR):
    """Return the file bytes after checking size and SHA-256 against the pins."""
    entry = _entry(name)
    path = Path(root) / name
    if not path.is_file():
        if name in ABSENT_FILES:
            raise FileNotFoundError(
                f"{name} is a known NIST mds2-2525 file that has not been acquired "
                f"(official SHA-256 {entry['sha256']}); treat as unavailable")
        raise FileNotFoundError(f"NIST mds2-2525 source file is missing: {path}")
    data = path.read_bytes()
    if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError(f"NIST mds2-2525 file {name}: size or SHA-256 mismatch")
    return data


def _text(data):
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("malformed NIST mds2-2525 table: not UTF-8") from error


def _float(value, what):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"malformed {what}: {value!r}") from error
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"malformed {what}: {value!r}")
    return number


def _rows(data):
    return list(csv.reader(io.StringIO(_text(data), newline="")))


def parse_absorptance_series(data, expected_rows=None):
    """Parse the nine-column NIST calibrated absorption CSV bytes."""
    rows = _rows(data)
    if not rows or rows[0] != TI64_COLUMNS:
        raise ValueError("malformed absorptance header")
    body = rows[1:]
    if not body or (expected_rows is not None and len(body) != expected_rows):
        raise ValueError(f"malformed absorptance row count: {len(body)}")
    series = {key: [] for key in ("time_s", "input_power_W", "absorbed_power_W",
                                  "absorbed_uncertainty_W", "relative_absorption_pct", "frame_number")}
    for number, row in enumerate(body):
        if len(row) != 9:
            raise ValueError(f"malformed absorptance row {number}: expected 9 columns")
        series["time_s"].append(_float(row[1], f"time at row {number}"))
        series["input_power_W"].append(_float(row[2], f"input power at row {number}"))
        series["absorbed_power_W"].append(_float(row[3], f"absorbed power at row {number}"))
        uncertainty = row[4].strip()
        series["absorbed_uncertainty_W"].append(
            None if uncertainty in ("--", "") else _float(uncertainty, f"uncertainty at row {number}"))
        series["relative_absorption_pct"].append(_float(row[5], f"relative absorption at row {number}"))
        frame = _float(row[8], f"frame number at row {number}")
        if frame != int(frame):
            raise ValueError(f"malformed frame number at row {number}: {row[8]!r}")
        series["frame_number"].append(int(frame))
    return series


def load_ti64_spot_series(root=SOURCE_DIR):
    return parse_absorptance_series(verified_bytes(SPOT_NAME, root), SPOT_ROWS)


def load_ti64_scan_series(root=SOURCE_DIR):
    """Raises FileNotFoundError until the NIST scan CSV is acquired and pinned."""
    return parse_absorptance_series(verified_bytes(SCAN_NAME, root))


def _percentile(sorted_values, fraction):
    position = (len(sorted_values) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def _trapezoid(time_s, values, first, last):
    return sum((time_s[k + 1] - time_s[k]) * (values[k] + values[k + 1]) / 2.0
               for k in range(first, last))


def _window_stats(time_s, relative, first, last, start_s, window_ms):
    lo, hi = window_ms
    values = [relative[k] for k in range(first, last + 1)
              if lo <= (time_s[k] - start_s) * 1e3 < hi]
    if not values:
        raise ValueError(f"malformed series: no samples in window {window_ms} ms")
    return {"mean": mean(values), "std": stdev(values) if len(values) > 1 else 0.0, "n": len(values)}


def _laser_on(time_s, input_power, threshold):
    indices = [k for k, value in enumerate(input_power) if value > threshold]
    if not indices:
        raise ValueError("malformed series: laser never exceeds the on threshold")
    return indices[0], indices[-1]


def _bins(time_s, relative, first, last, start_s, width_ms=0.05):
    sums = {}
    for k in range(first, last + 1):
        index = int(((time_s[k] - start_s) * 1e3) // width_ms)
        total, count = sums.get(index, (0.0, 0))
        sums[index] = (total + relative[k], count + 1)
    return [{"start_ms": index * width_ms, "mean_pct": total / count, "n": count}
            for index, (total, count) in sorted(sums.items()) if index >= 0]


def _transition(bins, baseline, rise_pp=10.0):
    for item in bins:
        if item["mean_pct"] > baseline + rise_pp:
            return item["start_ms"]
    return None


def summarize_ti64_spot(series, laser_on_threshold_W=50.0, pre_keyhole_window_ms=(0.05, 0.80),
                        keyhole_window_ms=(0.90, 2.00)):
    """Summarize a calibrated absorption series (Ti-6Al-4V spot or scan)."""
    time_s, power = series["time_s"], series["input_power_W"]
    absorbed, relative = series["absorbed_power_W"], series["relative_absorption_pct"]
    first, last = _laser_on(time_s, power, laser_on_threshold_W)
    start_s = time_s[first]
    on_power = sorted(power[first:last + 1])
    pre = _window_stats(time_s, relative, first, last, start_s, pre_keyhole_window_ms)
    key = _window_stats(time_s, relative, first, last, start_s, keyhole_window_ms)
    bins = _bins(time_s, relative, first, last, start_s)
    input_energy = _trapezoid(time_s, power, first, last)
    absorbed_energy = _trapezoid(time_s, absorbed, first, last)
    uncertainties = [value for value in series["absorbed_uncertainty_W"][first:last + 1]
                     if value is not None]
    return {
        "laser_on_threshold_W": laser_on_threshold_W,
        "laser_on_start_s": start_s, "laser_on_end_s": time_s[last],
        "input_power_median_W": _percentile(on_power, 0.5),
        "input_power_p10_W": _percentile(on_power, 0.10),
        "input_power_p90_W": _percentile(on_power, 0.90),
        "input_energy_J": input_energy, "absorbed_energy_J": absorbed_energy,
        "energy_coupling_fraction": absorbed_energy / input_energy,
        "pre_keyhole_window_ms": list(pre_keyhole_window_ms),
        "pre_keyhole_mean_pct": pre["mean"], "pre_keyhole_std_pct": pre["std"], "pre_keyhole_n": pre["n"],
        "keyhole_window_ms": list(keyhole_window_ms),
        "keyhole_mean_pct": key["mean"], "keyhole_std_pct": key["std"], "keyhole_n": key["n"],
        "transition_time_ms": _transition(bins, pre["mean"]),
        "transition_rule": "first 50 us bin whose mean relative absorption exceeds the pre-keyhole mean by 10 percentage points",
        "bins_50us": [[item["start_ms"], item["mean_pct"], item["n"]] for item in bins],
        "absorbed_uncertainty_median_W": median(uncertainties) if uncertainties else None,
        "window_definition": WINDOW_DEFINITION,
    }


def _description_rows(data):
    rows = _rows(data)
    header = [cell.strip().replace(" ", "").lower() for cell in rows[0][:5]] if rows else []
    if header not in (["description", "value", "unit", "stdev", "unit"],
                      ["description", "value", "unit", "stddev", "unit"]):
        raise ValueError("malformed Al results header")
    out = []
    for number, row in enumerate(rows[1:], start=1):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) < 5 or not row[0].strip():
            raise ValueError(f"malformed Al results row {number}")
        out.append({"description": row[0].strip(), "value": _float(row[1], f"Al value row {number}"),
                    "unit": row[2].strip(), "std_dev": _float(row[3], f"Al std dev row {number}"),
                    "std_dev_unit": row[4].strip()})
    if not out:
        raise ValueError("malformed Al results: no rows")
    return out


def _tdw(data):
    rows = _rows(data)
    if not rows or [cell.strip() for cell in rows[0]] != ["Time(s)", "MeltPoolWidth(um)"]:
        raise ValueError("malformed Al TDW header")
    time_s, width, untimed, placeholders = [], [], [], 0
    for number, row in enumerate(rows[1:], start=1):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != 2:
            raise ValueError(f"malformed Al TDW row {number}")
        if not row[0].strip():
            # The publisher file ends with one width value that has no time stamp
            # and then '--' filler rows; neither belongs to the timed series.
            if row[1].strip() == "--":
                placeholders += 1
            else:
                untimed.append(_float(row[1], f"Al TDW untimed width row {number}"))
            continue
        time_s.append(_float(row[0], f"Al TDW time row {number}"))
        width.append(_float(row[1], f"Al TDW width row {number}"))
    if len(time_s) < 2:
        raise ValueError("malformed Al TDW: too few timed rows")
    return {"time_s": time_s, "melt_pool_width_um": width,
            "untimed_width_um": untimed, "placeholder_rows": placeholders}


def _tda_series(data):
    rows = _rows(data)
    header = [cell.strip() for cell in rows[0]] if rows else []
    if header[:4] != ["Time(s)", "PowerInput(W)", "AbsoluteAbsorption(W)", "RelativeAbsorption(%)"] \
            or not ({"FileName", "Datafile"} & set(header)):
        raise ValueError("malformed Al TDA header")
    name_column = header.index("FileName") if "FileName" in header else header.index("Datafile")
    series = {"time_s": [], "input_power_W": [], "absorbed_power_W": [], "relative_absorption_pct": []}
    filename = None
    for number, row in enumerate(rows[1:], start=1):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) <= name_column:
            raise ValueError(f"malformed Al TDA row {number}")
        series["time_s"].append(_float(row[0], f"Al TDA time row {number}"))
        series["input_power_W"].append(_float(row[1], f"Al TDA power row {number}"))
        series["absorbed_power_W"].append(_float(row[2], f"Al TDA absorbed row {number}"))
        series["relative_absorption_pct"].append(_float(row[3], f"Al TDA relative row {number}"))
        if filename is None and row[name_column].strip():
            filename = row[name_column].strip()
    if not series["time_s"]:
        raise ValueError("malformed Al TDA: no rows")
    return series, filename


def _summarize_al_tda(data, threshold=50.0, baseline_window_ms=(0.05, 0.10), end_ms=2.00):
    """Before/during-keyhole means for an aluminium TDA trace.

    The transition is found from the data (50 us bins), then the before window
    ends one bin ahead of it and the during window starts 0.10 ms after it. This
    is a local analysis choice and is not NIST's published phase boundary.
    """
    series, filename = _tda_series(data)
    time_s, power = series["time_s"], series["input_power_W"]
    relative = series["relative_absorption_pct"]
    first, last = _laser_on(time_s, power, threshold)
    start_s = time_s[first]
    baseline = _window_stats(time_s, relative, first, last, start_s, baseline_window_ms)["mean"]
    bins = _bins(time_s, relative, first, last, start_s)
    transition = _transition(bins, baseline)
    if transition is None:
        raise ValueError("malformed Al TDA: no keyhole transition found")
    before_window = (baseline_window_ms[0], max(baseline_window_ms[1], transition - 0.05))
    during_window = (transition + 0.10, end_ms)
    before = _window_stats(time_s, relative, first, last, start_s, before_window)
    during = _window_stats(time_s, relative, first, last, start_s, during_window)
    on_power = power[first:last + 1]
    return {"material": AL_MATERIAL, "row_count": len(time_s), "datafile_name": filename,
            "laser_on_start_s": start_s, "laser_on_end_s": time_s[last],
            "input_power_median_W": median(on_power),
            "transition_time_ms": transition,
            "before_keyhole_window_ms": list(before_window), "before_keyhole_mean_pct": before["mean"],
            "before_keyhole_std_pct": before["std"], "before_keyhole_n": before["n"],
            "during_keyhole_window_ms": list(during_window), "during_keyhole_mean_pct": during["mean"],
            "during_keyhole_std_pct": during["std"], "during_keyhole_n": during["n"],
            "window_definition": WINDOW_DEFINITION}


def load_al_tables(root=SOURCE_DIR):
    return {
        "material": AL_MATERIAL,
        "spot_average_absorption": {"material": AL_MATERIAL,
                                    "rows": _description_rows(verified_bytes(AL_SPOT_AA, root))},
        "scan_average_absorption": {"material": AL_MATERIAL,
                                    "rows": _description_rows(verified_bytes(AL_SCAN_AA, root))},
        "spot_melt_pool_width": dict(_tdw(verified_bytes(AL_SPOT_TDW, root)), material=AL_MATERIAL),
        "spot_tda_summary": _summarize_al_tda(verified_bytes(AL_SPOT_TDA, root)),
        "scan_tda_summary": _summarize_al_tda(verified_bytes(AL_SCAN_TDA, root)),
    }


def _round(value):
    if isinstance(value, float):
        return float(f"{value:.6g}")
    if isinstance(value, dict):
        return {key: _round(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(item) for item in value]
    return value


def build_derived_summary(root=SOURCE_DIR):
    spot = summarize_ti64_spot(load_ti64_spot_series(root))
    al = load_al_tables(root)
    width = al["spot_melt_pool_width"]
    al["spot_melt_pool_width"] = {
        "material": AL_MATERIAL, "row_count": len(width["time_s"]),
        "time_step_s": width["time_s"][1] - width["time_s"][0],
        "max_width_um": max(width["melt_pool_width_um"]),
        "untimed_width_um": width["untimed_width_um"], "placeholder_rows": width["placeholder_rows"],
        "time_s": width["time_s"], "melt_pool_width_um": width["melt_pool_width_um"]}
    unavailable = []
    for name, entry in ABSENT_FILES.items():
        try:
            verified_bytes(name, root)
        except FileNotFoundError:
            unavailable.append({"file": name, "status": "unavailable", "sha256": entry["sha256"],
                                "bytes": entry["bytes"], "source_url": entry["source_url"],
                                "reason": entry["reason"]})
    used = [name for name in OFFICIAL_FILES if name.endswith(".csv")]
    return _round({
        "schemaVersion": 1, "datasetId": DATASET_ID,
        "kind": "locally-derived-summary-of-publisher-absorptance-tables",
        "sourceFiles": {name: OFFICIAL_FILES[name]["sha256"] for name in sorted(used)},
        "ti64_spot": dict(spot, material=TI64_MATERIAL,
                          case="stationary beam, ~2 ms pulse, ~102 W, bare polished metal, argon"),
        "aluminium_challenge": al,
        "unavailable": unavailable,
        "evidence": {"measured_for": "NIST experiment only", "experimentalValidation": False,
                     "modelAcceptance": False},
    })


def serialize_summary(summary):
    return json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_derived_summary(path=DERIVED_PATH, root=SOURCE_DIR):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = serialize_summary(build_derived_summary(root))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


if __name__ == "__main__":
    if "--write" in sys.argv[1:]:
        print(write_derived_summary())
    else:
        sys.stdout.write(serialize_summary(build_derived_summary()))
