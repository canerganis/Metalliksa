#!/usr/bin/env python3
"""Sensitivity-only trend comparison of the LPBF screening kernels with NIST mds2-2716 camera-signal metrics.

COMPARISON, NOT VALIDATION. The NIST staring camera (AMB2022-03, bare IN718, 21 single tracks in 7
cases x 3 repeats) gives raw signal in digital levels (DL). No temperature conversion exists (the stored
calibration model is malformed and gives no emissivity), so the 4095 DL saturation isotherm and the
100/1000/2000 DL thresholds have UNKNOWN temperatures. The application's Rosenthal, Eagar-Tsai and Goldak
kernels report the liquidus isotherm (IN718 liquidus of the repo material table). These are different
isotherms, so absolute lengths and dwell times are never compared. What is reported:

1. Normalised trends: case / baseline ratios (baseline = case 0: 285 W, 960 mm/s, D4s 67 um) of the
   measured saturated-region length and time above 4095/2000/1000 DL, next to the model ratio of the
   liquidus length and liquidus dwell (length / speed). Ratios cancel the inferred pixel pitch; they do
   not cancel the isotherm mismatch. Sign agreement and the ratio difference are reported, never a pass.
2. Rank agreement: Spearman rank correlation over the 7 cases for each metric against each kernel.

Every comparison row has status ``sensitivity-only`` or ``unavailable`` (with a reason). Nothing is fitted.

Measured input is the committed derived table
data/benchmark/nist-amb2022-03/derived/thermography-signal-metrics-v1.json, pinned here by size and
SHA-256 independently of the loader; the run is refused on mismatch. The 550 MB raw file is not needed.

Usage (from python/, locked interpreter, PYTHONDONTWRITEBYTECODE=1):
    python -B tools/lpbf_nist_2716_thermography_comparison.py \
        --out ../docs/LPBF_NIST_2716_THERMOGRAPHY_COMPARISON_2026-10-06.json
    python -B tools/lpbf_nist_2716_thermography_comparison.py --quick --out <json>
Options: --quick (Eagar-Tsai kernel only, fingerprint test not run), --generated-at, --data-dir (directory
holding the derived table and its manifest). The companion .md is written next to the JSON.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

SCHEMA = "lpbf-nist-2716-thermography-comparison-1"
GENERATED_AT_DEFAULT = "2026-10-06"
DATA_DIR = PYTHON_DIR.parent / "data" / "benchmark" / "nist-amb2022-03" / "derived"
DERIVED_NAME = "thermography-signal-metrics-v1.json"
MANIFEST_NAME = "manifest.json"
ALLOWED_STATUS = ("sensitivity-only", "unavailable")
KERNELS = ("rosenthal", "eagar-tsai", "goldak")
QUICK_KERNELS = ("eagar-tsai",)
BASELINE_CASE = "0"
MATERIAL = "IN718"
PREHEAT_ASSUMED_C = 20.0
NOMINAL_LAYER_FOR_BARE_UM = 30.0
HATCH_UM = 100.0
RUNTIME_LIMIT_S = 300.0

# Pins of the committed derived table (independent of the loader). Refuse to run on mismatch.
PINNED = {DERIVED_NAME: ("7b34b3b304a95aab0dccd9481d8d944d066bfddb087bd05bd409a949b021d76a", 182588)}
# The raw NIST inputs the derived table was built from (NIST NERDm record v1.3.1).
RAW_INPUT_PINS = {
    "AMB2022-03-718-AMMT-StaringCamera_Signal.h5": ("f6fe21ec911707f72e7efda2932c77eae2b75d84765848878fe5beb6b728cd43", 549979044),
    "AMB2022-03-AMMT-718-Pad_XYPT.h5": ("7b7004753e150bc26632e9ce356e0440429160fa92cbff8fc8559202fdce2103", 406992),
    "README.txt": ("ba44076ed51b69c0e4ca80ff0e2568eed2dc6459e85c9ad83b85860bee5760f2", 12573),
}

TEMPERATURE_MISSING_REASON = (
    "No temperature conversion executed: the stored /Calibration/ThermalCal Model string has unbalanced "
    "parentheses and an unspecified emissivity e, its Celsius/Kelvin convention is not determinable from "
    "the file, and the melt-pool region is saturated at 4095 DL. A reviewed equation, a cited emissivity "
    "and the valid calibration range are required.")

LABELS = {
    "experimentalValidation": False,
    "temperatureConversion": None,
    "temperatureConversionMissingReason": TEMPERATURE_MISSING_REASON,
    "opticalOperatorMatched": False,
    "modelAcceptance": False,
    "nistResidual": None,
    "evidenceKindMeasuredFor": "NIST experiment only (raw camera signal, DL)",
    "appOutputs": "screening, unvalidated",
}

HONESTY_STATEMENT = (
    "comparison, not validation; raw camera signal in digital levels (DL); no temperature conversion "
    "executed; application outputs are screening and unvalidated; measured and model quantities refer to "
    "different isotherms, so only normalised trends and ranks are shown (sensitivity-only); nothing tuned")
HEADER_MD = ("**Sensitivity-only trend comparison of the screening kernels against NIST mds2-2716 raw "
             "camera-signal metrics; not experimental validation; no temperature conversion; application "
             "outputs are screening and unvalidated; nothing was tuned.**")

# measured metric -> (derived case metric key, model quantity, description)
PAIRS = (
    ("lsatTemporal_um", "liquidusLength_um", "saturated-region length, temporal (TAT_4095 x v)"),
    ("lsatSpatial_um", "liquidusLength_um", "saturated-region length, spatial (blob extent x inferred pitch)"),
    ("tat4095_frames", "liquidusDwell_s", "time at 4095 DL saturation"),
    ("tat2000_frames", "liquidusDwell_s", "time above 2000 DL"),
    ("tat1000_frames", "liquidusDwell_s", "time above 1000 DL"),
)
MODEL_QUANTITY_TEXT = {
    "liquidusLength_um": "kernel liquidus-isotherm length (meltPoolGeometry.length_um)",
    "liquidusDwell_s": "kernel liquidus dwell = liquidus length / scan speed",
}


# ---------------------------------------------------------------------------------------------
# input hash gate
# ---------------------------------------------------------------------------------------------
def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_verified(root: Path = DATA_DIR) -> Dict[str, Any]:
    """Derived table + manifest after checking the pinned size/SHA-256 and the raw-input pins."""
    sha, size = PINNED[DERIVED_NAME]
    path = Path(root) / DERIVED_NAME
    if not path.is_file():
        raise FileNotFoundError(f"pinned derived table missing: {path}")
    data = path.read_bytes()
    if len(data) != size or sha256_hex(data) != sha:
        raise ValueError(f"NIST mds2-2716 derived table {DERIVED_NAME}: size or SHA-256 mismatch; refusing to run")
    manifest = json.loads((Path(root) / MANIFEST_NAME).read_text(encoding="utf-8"))
    if manifest.get("derived", {}).get("sha256") != sha or manifest["derived"].get("bytes") != size:
        raise ValueError("NIST mds2-2716 derived manifest does not pin the derived table; refusing to run")
    got = {i["name"]: (i["sha256"], i["bytes"]) for i in manifest.get("inputs", [])}
    if got != RAW_INPUT_PINS:
        raise ValueError("NIST mds2-2716 derived manifest raw-input pins differ from the NERDm v1.3.1 pins; refusing to run")
    record = json.loads(data.decode("utf-8"))
    return {"record": record, "manifest": manifest, "sha256": sha, "bytes": size}


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def _round(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return float(f"{value:.6g}") if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(v) for v in value]
    return value


def unavailable(reason: str, **extra: Any) -> Dict[str, Any]:
    out = {"status": "unavailable", "reason": reason}
    out.update(extra)
    return out


def read_fingerprint() -> str:
    return (PYTHON_DIR / "lpbf_implementation_fingerprint.expected").read_text(encoding="utf-8").strip()


def run_fingerprint_test() -> bool:
    proc = subprocess.run([sys.executable, "-B", "test_lpbf_implementation_fingerprint.py"],
                          cwd=str(PYTHON_DIR), capture_output=True, text=True, timeout=600)
    return proc.returncode == 0


def _ranks(values: Sequence[float]) -> List[float]:
    """Average ranks (1-based), ties share the mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    """Spearman rank correlation (Pearson on average ranks); None when undefined (n < 3 or no rank spread)."""
    if len(x) != len(y) or len(x) < 3:
        return None
    rx, ry = _ranks(x), _ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _sign(x: float, tol: float = 1e-12) -> int:
    return 0 if abs(x) <= tol else (1 if x > 0 else -1)


TEMPERATURE_KEY = re.compile(r"temperature|coolingrate|_C$|_K$|_K_s$", re.I)


def measured_temperature_keys(obj: Any, prefix: str = "") -> List[str]:
    """Keys that look like a temperature in measured (DL-derived) content (check A9)."""
    found: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if TEMPERATURE_KEY.search(k) and k not in ("temperatureConversion", "temperatureConversionMissingReason"):
                found.append(prefix + k)
            found.extend(measured_temperature_keys(v, prefix + k + "."))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(measured_temperature_keys(v, f"{prefix}{i}."))
    return found


# ---------------------------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------------------------
def model_inputs() -> Dict[str, Any]:
    from four_alloy_materials import thermal_props
    props = thermal_props(MATERIAL)
    return {
        "material": MATERIAL,
        "liquidus_C": float(props["liquidus_C"]), "solidus_C": float(props["solidus_C"]),
        "absorptivityOfRecord": float(props["absorptivity_IR"]),
        "absorptivityOrigin": "four_alloy_materials.thermal_props('IN718')['absorptivity_IR'] (assumed constant, not measured)",
        "preheat_C": PREHEAT_ASSUMED_C,
        "preheatBasis": "assumption: ambient plate; the NIST plate temperature is not stated in the files in hand",
        "layerThickness_um": NOMINAL_LAYER_FOR_BARE_UM,
        "layerBasis": "nominal value passed for a bare plate (no powder), as in tools/lpbf_dataset_comparison.py",
        "hatch_um": HATCH_UM,
        "beamDiameter": ("NIST spot_size (D4s) passed as the kernel beam diameter: for a Gaussian beam D4s equals the "
                         "1/e^2 diameter (assumption about the kernel's beam-size convention)"),
        "absorptionPath": ("flat-plate absorptivity: the optional powder-bed ray tracer is pinned off (bare plate, no "
                           "powder) via tools/lpbf_dataset_comparison.pin_flat_plate"),
        "propOverrides": None,
    }


def run_kernel(case: Dict[str, Any], kernel: str) -> Dict[str, Any]:
    from lpbf_dataset_comparison import pin_flat_plate
    pin_flat_plate(False)
    from lpbf_thermal_solver import calculate_meltpool_physics
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            res = calculate_meltpool_physics(MATERIAL, case["laserPower_W"], case["scanSpeed_mm_s"], case["spotD4s_um"],
                                             PREHEAT_ASSUMED_C, NOMINAL_LAYER_FOR_BARE_UM, HATCH_UM, heat_source=kernel)
    except Exception as exc:  # recorded as data
        return unavailable(f"kernel raised {type(exc).__name__}: {str(exc)[:200]}")
    g = res["meltPoolGeometry"]
    if g.get("extentStatus") != "computed":
        return unavailable(f"kernel extentStatus {g.get('extentStatus')!r}: {g.get('extentNote')}")
    length = float(g["length_um"])
    return {"status": "computed-screening", "liquidusLength_um": length,
            "liquidusDwell_s": length * 1e-3 / case["scanSpeed_mm_s"],
            "width_um": float(g["width_um"]), "depth_um": float(g["depth_um"]), "extentStatus": g["extentStatus"]}


# ---------------------------------------------------------------------------------------------
# document
# ---------------------------------------------------------------------------------------------
def _varied(case: Dict[str, Any], base: Dict[str, Any]) -> List[str]:
    out = []
    for key, label in (("laserPower_W", "power"), ("scanSpeed_mm_s", "speed"), ("spotD4s_um", "spot D4s")):
        if case[key] != base[key]:
            out.append(f"{label} {base[key]:g} -> {case[key]:g}")
    return out


FRAME_RATE_HZ = 30000.0


def measurement_quantum(metric: str, case: Dict[str, Any], pitch_um: Optional[float]) -> Optional[float]:
    """Smallest resolvable step of a metric: one camera frame, one frame of travel, or one pixel."""
    if metric.startswith("tat"):
        return 1.0
    if metric == "lsatTemporal_um":
        return case["scanSpeed_mm_s"] * 1000.0 / FRAME_RATE_HZ
    if metric == "lsatSpatial_um":
        return pitch_um
    return None


def _measured_ratio(case_stat: Dict[str, Any], base_stat: Dict[str, Any], quantum: Optional[float]) -> Dict[str, Any]:
    r = case_stat["mean"] / base_stat["mean"]
    rel = 0.0
    for st in (case_stat, base_stat):
        if st.get("sd") is not None:
            rel += (st["sd"] / st["mean"]) ** 2
    sd = r * math.sqrt(rel)
    q_rel = quantum / base_stat["mean"] if quantum else 0.0
    return {"ratio": r, "ratioSd": sd, "quantumRel": q_rel, "changeResolved": abs(r - 1.0) > max(sd, q_rel),
            "changeResolvedRule": ("|ratio - 1| > max(repeat SD of the ratio (k=1, n=3, first-order propagation), one "
                                   "measurement quantum / baseline mean); an SD of 0 means identical integer-frame "
                                   "values in the three repeats, not zero uncertainty")}


def build_core(quick: bool, generated_at: str, root: Path = DATA_DIR) -> Dict[str, Any]:
    src = read_verified(root)
    rec = src["record"]
    cases = {c["caseId"]: c for c in rec["cases"]}
    if BASELINE_CASE not in cases:
        raise ValueError("derived table has no baseline case 0")
    base = cases[BASELINE_CASE]
    kernels = QUICK_KERNELS if quick else KERNELS
    model = {cid: {k: run_kernel(c, k) for k in kernels} for cid, c in cases.items()}

    measured = {cid: {"laserPower_W": c["laserPower_W"], "scanSpeed_mm_s": c["scanSpeed_mm_s"],
                      "spotD4s_um": c["spotD4s_um"], "repeats": c["repeats"],
                      "metrics": {m: c["metrics"].get(m) for m, _, _ in PAIRS}}
                for cid, c in cases.items()}

    trend_rows: List[Dict[str, Any]] = []
    for cid, c in cases.items():
        if cid == BASELINE_CASE:
            continue
        for metric, quantity, desc in PAIRS:
            cs, bs = c["metrics"].get(metric), base["metrics"].get(metric)
            row: Dict[str, Any] = {"id": f"trend-{cid}-{metric}", "caseId": cid, "varied": _varied(c, base),
                                   "measuredMetric": metric, "measuredDescription": desc,
                                   "modelQuantity": quantity}
            if not cs or not bs or not bs.get("mean"):
                row.update(unavailable("measured case or baseline metric missing in the derived table"))
                trend_rows.append(row)
                continue
            pitch = (rec.get("pixelPitchConsistency") or {}).get("pooledMedian_um")
            mr = _measured_ratio(cs, bs, measurement_quantum(metric, c, pitch))
            row["measured"] = mr
            row["models"] = {}
            for k in kernels:
                mc, mb = model[cid][k], model[BASELINE_CASE][k]
                if mc["status"] != "computed-screening" or mb["status"] != "computed-screening":
                    row["models"][k] = unavailable(mc.get("reason") or mb.get("reason"))
                    continue
                ratio = mc[quantity] / mb[quantity]
                row["models"][k] = {"ratio": ratio, "ratioDifference": ratio - mr["ratio"],
                                    "ratioDifferenceDefinition": "model ratio - measured ratio",
                                    "signAgreement": _sign(ratio - 1.0) == _sign(mr["ratio"] - 1.0)}
            row["status"] = "sensitivity-only"
            row["reason"] = ("normalised to case 0; the measured isotherm (DL threshold, temperature unknown) differs from "
                             "the model liquidus isotherm, so the ratio difference is not an error of the model")
            trend_rows.append(row)

    rank_rows: List[Dict[str, Any]] = []
    order = sorted(cases)
    for metric, quantity, desc in PAIRS:
        meas = [cases[cid]["metrics"].get(metric) for cid in order]
        for k in kernels:
            row = {"id": f"rank-{metric}-{k}", "measuredMetric": metric, "measuredDescription": desc,
                   "modelQuantity": quantity, "kernel": k, "cases": order}
            mod = [model[cid][k] for cid in order]
            if any(m is None for m in meas) or any(m["status"] != "computed-screening" for m in mod):
                row.update(unavailable("a case lacks the measured metric or a computed kernel value"))
            else:
                rho = spearman([m["mean"] for m in meas], [m[quantity] for m in mod])
                row.update({"n": len(order), "spearmanRho": rho, "status": "sensitivity-only",
                            "reason": ("rank agreement over 7 cases (n = 7, no significance claimed); different "
                                       "isotherms, ranks only")})
                if rho is None:
                    row.update(unavailable("Spearman undefined (no rank spread)"))
            rank_rows.append(row)

    unavailable_rows = [
        {"id": "absolute-length-or-dwell", "quantity": "absolute saturated length / time above threshold vs model liquidus length / dwell",
         **unavailable("the temperature of the 4095 DL saturation isotherm and of the DL thresholds is unknown (no "
                       "temperature conversion), so absolute values refer to different isotherms")},
        {"id": "cooling-rate", "quantity": "cooling rate (K/s); NIST TSCR, TLCR, PSCR",
         **unavailable("the camera signal is not converted to temperature, so no K/s exists on the measured side; "
                       "signal-decay frames are not cooling rates")},
        {"id": "time-above-melting", "quantity": "time above melting; NIST TTAM, PTAM",
         **unavailable("needs T(DL) at solidus/liquidus, i.e. the missing temperature conversion")},
        {"id": "peak-temperature", "quantity": "peak temperature",
         **unavailable("saturated at 4095 DL in every laser-on frame and uncalibrated")},
        {"id": "transient-enthalpy-reference", "quantity": "lpbf_simulation reference transient (enthalpy) backend",
         **unavailable("not run in v1: the local-history observer is restricted to reference powder-layer runs, the "
                       "10 mm bare-plate tracks need the corridor geometry, and the 20 um mesh is about one camera "
                       "pixel and not converged")},
        {"id": "pads-vs-kernels", "quantity": "pad thermography vs kernels",
         **unavailable("single-track analytic kernels do not represent multi-track heat accumulation; pad camera "
                       "videos are not analysed in v1 (only the commanded XYPT track table is derived)")},
        {"id": "radiance-temperature-bracket", "quantity": "radiance-temperature bracket (spec Phase 2)",
         **unavailable("gated: needs a confirmed calibration equation and unit plus a cited emissivity; not implemented")},
    ]
    if quick:
        for k in KERNELS:
            if k not in kernels:
                unavailable_rows.append({"id": f"kernel-{k}", "quantity": f"{k} kernel",
                                         **unavailable("--quick runs the Eagar-Tsai kernel only")})

    limits = [
        "Measured and model quantities refer to different isotherms: the camera saturation level and DL thresholds "
        "have unknown temperatures; the kernels report the IN718 liquidus of the repo material table.",
        "Measured lengths use a pixel pitch inferred from the commanded scan speed (README +/-2.5 % k=1); ratios cancel "
        "the pitch but the temporal length also carries the commanded speed.",
        "Kernel inputs are assumptions: absorptivity of record (not measured), ambient preheat, D4s taken as the beam "
        "diameter, flat-plate absorption; nothing was tuned to the data.",
        "Each case has 3 repeats; the measured ratio SD is a first-order repeat-scatter propagation, not an "
        "uncertainty budget; Spearman correlations are over 7 cases with no significance claimed.",
        "Single tracks on bare IN718 only; no powder-bed claim and no pad comparison.",
    ]

    return {
        "schema": SCHEMA, "generatedAt": generated_at, "quick": quick,
        "implementationFingerprint": read_fingerprint(),
        "honesty": HONESTY_STATEMENT,
        "dataset": {"id": rec["datasetId"], "sourceDatasetId": rec["sourceDatasetId"],
                    "derivedTable": {"path": "data/benchmark/nist-amb2022-03/derived/" + DERIVED_NAME,
                                     "sha256": src["sha256"], "bytes": src["bytes"]},
                    "rawInputs": {n: {"sha256": s, "bytes": b, "committed": False} for n, (s, b) in RAW_INPUT_PINS.items()},
                    "source": rec["source"]},
        "labels": dict(LABELS),
        "derivability": [
            {"quantity": "time above DL thresholds, saturated-region length", "status": "measured-signal (NIST)"},
            {"quantity": "pixel pitch, temporal/spatial length", "status": "derived-inferred (NIST)"},
            {"quantity": "case/baseline trend and Spearman rank vs kernels", "status": "sensitivity-only"},
            {"quantity": "absolute temperature, cooling rate, time above melting", "status": "unavailable"},
        ],
        "measured": {"baselineCase": BASELINE_CASE, "cases": measured,
                     "pixelPitchConsistency": rec.get("pixelPitchConsistency")},
        "modelInputs": model_inputs(),
        "kernels": list(kernels),
        "model": model,
        "modelQuantities": MODEL_QUANTITY_TEXT,
        "comparison": {"trendRows": trend_rows, "rankRows": rank_rows, "unavailableRows": unavailable_rows},
        "limits": limits,
    }


def build_document(quick: bool, generated_at: str, root: Path = DATA_DIR,
                   fingerprint_test: Optional[bool] = None) -> Dict[str, Any]:
    t0 = time.perf_counter()
    doc = _round(build_core(quick, generated_at, root))
    again = _round(build_core(quick, generated_at, root))
    deterministic = serialize(doc) == serialize(again)
    elapsed = time.perf_counter() - t0
    run_fp = (not quick) if fingerprint_test is None else fingerprint_test
    fp_passed = run_fingerprint_test() if run_fp else None
    rows = doc["comparison"]["trendRows"] + doc["comparison"]["rankRows"] + doc["comparison"]["unavailableRows"]
    statuses_ok = all(r["status"] in ALLOWED_STATUS and (r["status"] != "unavailable" or r.get("reason")) for r in rows)
    labels_ok = (doc["labels"] == LABELS and doc["labels"]["experimentalValidation"] is False
                 and doc["labels"]["modelAcceptance"] is False and doc["labels"]["nistResidual"] is None)
    temp_keys = measured_temperature_keys(doc["measured"]) + measured_temperature_keys(doc["comparison"])
    doc["checks"] = [
        {"id": "A1-input-pins", "result": "pass",
         "detail": "derived table size and SHA-256 equal the tool pin; manifest raw-input pins equal NERDm v1.3.1"},
        {"id": "A2-physics-fingerprint",
         "result": "skipped" if fp_passed is None else ("pass" if fp_passed else "fail"),
         "detail": ("fingerprint test not run (--quick)" if fp_passed is None else
                    "test_lpbf_implementation_fingerprint.py run; recorded fingerprint read from "
                    "lpbf_implementation_fingerprint.expected")},
        {"id": "A9-no-temperature", "result": "pass" if not temp_keys else "fail",
         "detail": (f"measured and comparison blocks scanned for temperature/cooling-rate keys: {len(temp_keys)} found "
                    "(model inputs such as the liquidus are model assumptions, not DL-derived)")},
        {"id": "A10-labels", "result": "pass" if (labels_ok and statuses_ok) else "fail",
         "detail": ("labels equal LABELS (experimentalValidation false, modelAcceptance false, nistResidual null); "
                    f"every row status in {list(ALLOWED_STATUS)} and every unavailable row has a reason")},
        {"id": "A11-determinism", "result": "pass" if deterministic else "fail",
         "detail": "document built twice in this run with the same --generated-at; serialised bytes compared"},
        {"id": "A12-runtime", "result": "pass" if elapsed < RUNTIME_LIMIT_S else "flag",
         "detail": (f"both builds finished within the {RUNTIME_LIMIT_S:g} s limit; the exact wall time is printed to "
                    "stdout only, so the record stays byte-deterministic") if elapsed < RUNTIME_LIMIT_S else
                   f"builds exceeded the {RUNTIME_LIMIT_S:g} s limit"},
    ]
    doc["_elapsed_s"] = elapsed
    return doc


def serialize(doc: Dict[str, Any]) -> str:
    return json.dumps({k: v for k, v in doc.items() if not k.startswith("_")}, sort_keys=True, indent=1,
                      ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------------------------
def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def render_markdown(doc: Dict[str, Any]) -> str:
    out: List[str] = []
    a = out.append
    a(f"# LPBF NIST mds2-2716 thermography trend comparison ({doc['generatedAt']})")
    a("")
    a(HEADER_MD)
    a("")
    a(f"Schema `{doc['schema']}`; implementation fingerprint `{doc['implementationFingerprint']}`; quick mode: "
      f"{doc['quick']}; kernels: {', '.join(doc['kernels'])}. Honesty: {doc['honesty']}. "
      "`experimentalValidation` = false, `opticalOperatorMatched` = false, `modelAcceptance` = false, "
      "`nistResidual` = null, `temperatureConversion` = null.")
    a("")
    a("## Inputs")
    a("")
    d = doc["dataset"]
    a(f"Citation: {d['source']['citation']}")
    a("")
    a("| File | Bytes | SHA-256 | Committed |")
    a("| --- | ---: | --- | --- |")
    a(f"| {d['derivedTable']['path']} | {d['derivedTable']['bytes']} | `{d['derivedTable']['sha256']}` | yes |")
    for n, f in d["rawInputs"].items():
        a(f"| {n} (raw NIST input) | {f['bytes']} | `{f['sha256']}` | no |")
    a("")
    mi = doc["modelInputs"]
    a(f"Model inputs: {mi['material']}, liquidus {mi['liquidus_C']:g} C, absorptivity {mi['absorptivityOfRecord']:g} "
      f"({mi['absorptivityOrigin']}), preheat {mi['preheat_C']:g} C ({mi['preheatBasis']}), layer "
      f"{mi['layerThickness_um']:g} um ({mi['layerBasis']}), hatch {mi['hatch_um']:g} um. {mi['beamDiameter']}. "
      f"{mi['absorptionPath']}.")
    a("")
    a("## Derivability")
    a("")
    a("| Quantity | Status |")
    a("| --- | --- |")
    for r in doc["derivability"]:
        a(f"| {r['quantity']} | {r['status']} |")
    a("")
    a("## Measured case means (3 repeats each; raw signal units)")
    a("")
    a("| Case | P (W) | v (mm/s) | D4s (um) | " + " | ".join(m for m, _, _ in PAIRS) + " |")
    a("| --- | ---: | ---: | ---: | " + " | ".join("---:" for _ in PAIRS) + " |")
    for cid, c in sorted(doc["measured"]["cases"].items()):
        cells = []
        for m, _, _ in PAIRS:
            st = c["metrics"].get(m)
            cells.append("-" if not st else f"{_fmt(st['mean'])} +/- {_fmt(st['sd'])}")
        a(f"| {cid} | {_fmt(c['laserPower_W'])} | {_fmt(c['scanSpeed_mm_s'])} | {_fmt(c['spotD4s_um'])} | "
          + " | ".join(cells) + " |")
    a("")
    a("## Kernel liquidus length (screening, unvalidated)")
    a("")
    a("| Case | " + " | ".join(doc["kernels"]) + " |")
    a("| --- | " + " | ".join("---:" for _ in doc["kernels"]) + " |")
    for cid in sorted(doc["model"]):
        cells = []
        for k in doc["kernels"]:
            r = doc["model"][cid][k]
            cells.append(f"{_fmt(r['liquidusLength_um'])} um" if r["status"] == "computed-screening" else "unavailable")
        a(f"| {cid} | " + " | ".join(cells) + " |")
    a("")
    a("## Normalised trend vs case 0 (sensitivity-only)")
    a("")
    a("| Case | Varied | Metric | Measured ratio +/- SD | Resolved | " +
      " | ".join(f"{k} ratio (sign agrees)" for k in doc["kernels"]) + " |")
    a("| --- | --- | --- | ---: | --- | " + " | ".join("---:" for _ in doc["kernels"]) + " |")
    for r in doc["comparison"]["trendRows"]:
        if r["status"] == "unavailable":
            a(f"| {r['caseId']} | {'; '.join(r['varied'])} | {r['measuredMetric']} | unavailable: {r['reason']} | | "
              + " | ".join("" for _ in doc["kernels"]) + " |")
            continue
        m = r["measured"]
        cells = []
        for k in doc["kernels"]:
            mk = r["models"][k]
            cells.append("unavailable" if mk.get("status") == "unavailable"
                         else f"{_fmt(mk['ratio'])} ({_fmt(mk['signAgreement'])})")
        a(f"| {r['caseId']} | {'; '.join(r['varied'])} | {r['measuredMetric']} | {_fmt(m['ratio'])} +/- "
          f"{_fmt(m['ratioSd'])} | {_fmt(m['changeResolved'])} | " + " | ".join(cells) + " |")
    a("")
    a("Resolved = |ratio - 1| exceeds both the repeat SD of the measured ratio and one measurement quantum (one "
      "frame, one frame of travel or one pixel) relative to the baseline. An SD of 0 means the three repeats gave "
      "identical integer-frame values, not zero uncertainty. Sign agreement is reported for every row; where the "
      "measured change is not resolved it carries no weight.")
    a("")
    a("## Spearman rank over the 7 cases (sensitivity-only)")
    a("")
    a("| Measured metric | Model quantity | " + " | ".join(doc["kernels"]) + " |")
    a("| --- | --- | " + " | ".join("---:" for _ in doc["kernels"]) + " |")
    by_metric: Dict[str, Dict[str, Any]] = {}
    for r in doc["comparison"]["rankRows"]:
        by_metric.setdefault(r["measuredMetric"], {"q": r["modelQuantity"]})[r["kernel"]] = r
    for metric, rows in by_metric.items():
        cells = [(_fmt(rows[k].get("spearmanRho"), 3) if rows[k]["status"] == "sensitivity-only" else "unavailable")
                 for k in doc["kernels"]]
        a(f"| {metric} | {rows['q']} | " + " | ".join(cells) + " |")
    a("")
    a("## Unavailable")
    a("")
    a("| Item | Reason |")
    a("| --- | --- |")
    for r in doc["comparison"]["unavailableRows"]:
        a(f"| {r['quantity']} | {r['reason']} |")
    a("")
    a("## Checks")
    a("")
    a("| Check | Result | Detail |")
    a("| --- | --- | --- |")
    for c in doc["checks"]:
        a(f"| {c['id']} | {c['result']} | {c['detail']} |")
    a("")
    a("## Limits")
    a("")
    for item in doc["limits"]:
        a(f"- {item}")
    a("")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="JSON output path (companion .md written next to it)")
    ap.add_argument("--quick", action="store_true", help="Eagar-Tsai kernel only; fingerprint test not run")
    ap.add_argument("--generated-at", default=GENERATED_AT_DEFAULT)
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    args = ap.parse_args(argv)
    out = Path(args.out)
    if "golden" in out.resolve().parts:
        raise SystemExit("refusing to write under golden/")
    doc = build_document(args.quick, args.generated_at, Path(args.data_dir))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(serialize(doc), encoding="utf-8", newline="\n")
    out.with_suffix(".md").write_text(render_markdown(doc), encoding="utf-8", newline="\n")
    print(f"wrote {out} and {out.with_suffix('.md')} (wall time {doc['_elapsed_s']:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
