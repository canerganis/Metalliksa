"""Micrograph measurement authority (numpy + scipy only).

Measures a user-supplied 8-bit greyscale image (row-major bytes, base64) inside a region of
interest (ROI) with user-set grey thresholds and a user-supplied calibration:

1. Area fraction of a "dark" class (grey <= darkMaxGrey) and an optional "bright" class
   (grey >= brightMinGrey). Point-count/areal analysis in the spirit of ASTM E562/E1245:
   A_A = V_V holds only for isotropic, uniform random sections. Uncertainty:
   field-to-field 95 % CI from a k x k tile split (t_{0.975,n-1} s / sqrt(n)) and a
   threshold-sensitivity band (fraction at T -/+ delta grey levels).
2. Particles/pores of each class: scipy.ndimage.label with 8-connectivity; components smaller
   than minAreaPx are not counted (detection limit, reported). Equivalent circle diameter (ECD),
   Cauchy-Crofton perimeter estimate (4 directions), circularity 4 pi A / P^2, second-moment
   aspect ratio, a descriptive shape class and the mean free path lambda = (1 - V_V) / N_L from
   the mask crossings of every ROI row and column.
3. Grain size by the ASTM E112 lineal intercept (intersection) method on test lines at 0 and
   90 degrees: one intersection P per contiguous boundary run, 1/2 for a run touching a line end;
   l_bar = L / P, G = -6.643856 log10(l_bar in mm) - 3.288; line-to-line 95 % CI and %RA.
   Automatic counting only for "boundaries darker than grains" images; a manual mode takes
   per-line intersection counts clicked by the user on the same test lines (any image type).

Calibration is required for every length, area, density and G value; without it those
values are null with a reason, while fractions and counts are still returned.

Limitations: synthetic oracle tests only (python/test_micrograph_measure.py); no comparison
with real SEM/optical images or with manual counts by a metallographer exists yet. Threshold
segmentation cannot separate classes with overlapping grey levels; triple-point (1 1/2)
scoring of E112 is not implemented; the CIs are within one image (lines/tiles of one field are
not independent specimens). Nothing here infers phases, processing history or properties.
"""
from __future__ import annotations

import base64
import hashlib
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage
from scipy import stats

METHOD_VERSION = "micrograph-measure-1.0.0"
SCHEMA = "micrograph-measure/1"
MAX_SIDE_PX = 4096
MIN_ROI_SIDE_PX = 8
MAX_LABEL_CHARS = 60
MAX_PARTICLES_LISTED = 5000
MAX_LINES_PER_DIRECTION = 50
# Shape-class conventions (descriptive, not a standard): circularity uses the Crofton
# perimeter estimate below, unreliable for components smaller than SHAPE_MIN_AREA_PX.
SHAPE_MIN_AREA_PX = 20
NEAR_CIRCULAR_MIN_CIRCULARITY = 0.80
NEAR_CIRCULAR_MAX_ASPECT = 1.5
ELONGATED_MIN_ASPECT = 2.0
FEW_INTERCEPTS = 50
HIGH_RELATIVE_ACCURACY_PCT = 10.0
E112_SLOPE = -6.643856
E112_OFFSET = -3.288

LIMITATIONS = (
    "Measurement software verified only against synthetic images with a known answer "
    "(python/test_micrograph_measure.py); no real-image validation exists.",
    "Grey-level threshold segmentation: classes whose grey levels overlap cannot be separated.",
    "A_A = V_V and the intercept relations assume isotropic, uniform random sections.",
    "The 95 % intervals are within one image (tiles or test lines of one field), not between specimens.",
    "E112 triple-point (1 1/2) scoring is not implemented; boundary runs at junctions count 1.",
    "Nothing is inferred about phase identity, processing history, hardness or strength.",
)

_EIGHT = np.ones((3, 3), dtype=bool)


class MeasureInputError(ValueError):
    """Invalid request (bad image, ROI, thresholds or calibration)."""


# --- helpers -----------------------------------------------------------------

def _finite(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise MeasureInputError(f"{name} must be a finite number")
    return float(value)


def _int(name: str, value: Any, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) != int(value):
        raise MeasureInputError(f"{name} must be an integer")
    value = int(value)
    if not lo <= value <= hi:
        raise MeasureInputError(f"{name} must be within [{lo}, {hi}]")
    return value


def _label(name: str, value: Any, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_LABEL_CHARS:
        raise MeasureInputError(f"{name} must be a non-empty string of at most {MAX_LABEL_CHARS} characters")
    return value.strip()


def _unavailable(reason: str, unit: Optional[str] = None) -> Dict[str, Any]:
    return {"value": None, "unit": unit, "reason": reason}


def _quantity(value: float, unit: Optional[str], method: str, ci95=None) -> Dict[str, Any]:
    out = {"value": float(value), "unit": unit, "method": method}
    if ci95 is not None:
        out["ci95"] = [None if v is None else float(v) for v in ci95]
    return out


def _t975(n: int) -> Optional[float]:
    return float(stats.t.ppf(0.975, n - 1)) if n >= 2 else None


def _mean_ci(values: np.ndarray) -> Dict[str, Any]:
    """Mean, sample SD (ddof 1) and the Student-t 95 % half-width t_{0.975,n-1} s / sqrt(n)."""
    n = int(values.size)
    mean = float(values.mean()) if n else float("nan")
    sd = float(values.std(ddof=1)) if n >= 2 else None
    t = _t975(n)
    half = None if sd is None else t * sd / math.sqrt(n)
    return {"n": n, "mean": mean, "sd": sd, "tCritical": t, "halfWidth": half}


# --- request parsing ---------------------------------------------------------
#
# The request is a flat object (the module contract describes scalar keys only):
#   imageWidth, imageHeight, imageData   8-bit greyscale bytes (row-major), base64
#   cropTopPx/cropBottomPx/cropLeftPx/cropRightPx   margins excluded from the ROI (e.g. the SEM data bar)
#   barLengthUm + barLengthPx (scale-bar caliper)  or  umPerPx + calibrationNote (stated pixel size)
#   darkMaxGrey (-1 = off), darkLabel, brightMinGrey (256 = off), brightLabel
#   boundaryMaxGrey (-1 = automatic E112 counting off), manualCounts, manualClicks
#   tiles, sensitivityDeltaGrey, minAreaPx, linesPerDirection, returnMasks
# The off-values are not thresholds: grey <= -1 and grey >= 256 select no pixel.

REQUEST_KEYS = frozenset((
    "imageWidth", "imageHeight", "imageData", "cropTopPx", "cropBottomPx", "cropLeftPx", "cropRightPx",
    "umPerPx", "barLengthUm", "barLengthPx", "calibrationNote", "darkMaxGrey", "darkLabel", "brightMinGrey",
    "brightLabel", "boundaryMaxGrey", "manualCounts", "manualClicks", "tiles", "sensitivityDeltaGrey",
    "minAreaPx", "linesPerDirection", "returnMasks",
))


def read_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Every request key, read once with its default (the contract test checks these against the registry)."""
    return {
        "imageWidth": payload.get("imageWidth"),
        "imageHeight": payload.get("imageHeight"),
        "imageData": payload.get("imageData"),
        "cropTopPx": payload.get("cropTopPx", 0),
        "cropBottomPx": payload.get("cropBottomPx", 0),
        "cropLeftPx": payload.get("cropLeftPx", 0),
        "cropRightPx": payload.get("cropRightPx", 0),
        "umPerPx": payload.get("umPerPx", 0.0),
        "barLengthUm": payload.get("barLengthUm", 0.0),
        "barLengthPx": payload.get("barLengthPx", 0.0),
        "calibrationNote": payload.get("calibrationNote"),
        "darkMaxGrey": payload.get("darkMaxGrey", -1),
        "darkLabel": payload.get("darkLabel"),
        "brightMinGrey": payload.get("brightMinGrey", 256),
        "brightLabel": payload.get("brightLabel"),
        "boundaryMaxGrey": payload.get("boundaryMaxGrey", -1),
        "manualCounts": payload.get("manualCounts"),
        "manualClicks": payload.get("manualClicks"),
        "tiles": payload.get("tiles", 4),
        "sensitivityDeltaGrey": payload.get("sensitivityDeltaGrey", 10),
        "minAreaPx": payload.get("minAreaPx", 4),
        "linesPerDirection": payload.get("linesPerDirection", 8),
        "returnMasks": payload.get("returnMasks", True),
    }


def decode_image(width: Any, height: Any, data: Any) -> np.ndarray:
    width = _int("imageWidth", width, 1, MAX_SIDE_PX)
    height = _int("imageHeight", height, 1, MAX_SIDE_PX)
    if not isinstance(data, str):
        raise MeasureInputError("imageData must be a base64 string of 8-bit greyscale bytes (row-major)")
    try:
        raw = base64.b64decode(data, validate=True)
    except (ValueError, TypeError) as exc:
        raise MeasureInputError("imageData is not valid base64") from exc
    if len(raw) != width * height:
        raise MeasureInputError(f"imageData holds {len(raw)} bytes; imageWidth x imageHeight = {width * height}")
    return np.frombuffer(raw, dtype=np.uint8).reshape(height, width)


def parse_roi(req: Dict[str, Any], shape: Tuple[int, int]) -> Dict[str, int]:
    height, width = shape
    top = _int("cropTopPx", req["cropTopPx"], 0, MAX_SIDE_PX - 1)
    bottom = _int("cropBottomPx", req["cropBottomPx"], 0, MAX_SIDE_PX - 1)
    left = _int("cropLeftPx", req["cropLeftPx"], 0, MAX_SIDE_PX - 1)
    right = _int("cropRightPx", req["cropRightPx"], 0, MAX_SIDE_PX - 1)
    roi = {"x0": left, "y0": top, "x1": width - right, "y1": height - bottom}
    if roi["x1"] - roi["x0"] < MIN_ROI_SIDE_PX or roi["y1"] - roi["y0"] < MIN_ROI_SIDE_PX:
        raise MeasureInputError(f"the region of interest left after cropping must be at least {MIN_ROI_SIDE_PX} x "
                                f"{MIN_ROI_SIDE_PX} pixels")
    return roi


# Accepted image scale: 1e-6 um/px (1 pm per pixel, below any electron microscope) to 1e4 um/px (1 cm per pixel).
# A validation bound against overflow/underflow and typos, not a property of any instrument.
MIN_UM_PER_PX, MAX_UM_PER_PX = 1e-6, 1e4


def _checked_scale(um_per_px: float) -> float:
    if not (math.isfinite(um_per_px) and MIN_UM_PER_PX <= um_per_px <= MAX_UM_PER_PX):
        raise MeasureInputError(f"the image scale {um_per_px!r} um/px is outside the accepted range "
                                f"[{MIN_UM_PER_PX:g}, {MAX_UM_PER_PX:g}] um/px; check the calibration")
    return um_per_px


def parse_calibration(req: Dict[str, Any]) -> Dict[str, Any]:
    """Scale-bar caliper (barLengthUm, barLengthPx) or a stated pixel size (umPerPx with calibrationNote)."""
    bar_um = _finite("barLengthUm", req["barLengthUm"])
    bar_px = _finite("barLengthPx", req["barLengthPx"])
    um_per_px = _finite("umPerPx", req["umPerPx"])
    note = req["calibrationNote"]
    if note is not None and (not isinstance(note, str) or len(note) > 200):
        raise MeasureInputError("calibrationNote must be a string of at most 200 characters")
    if min(bar_um, bar_px, um_per_px) < 0:
        raise MeasureInputError("barLengthUm, barLengthPx and umPerPx must not be negative")
    bar = bar_um > 0 or bar_px > 0
    if bar and um_per_px > 0:
        raise MeasureInputError("give either a scale bar (barLengthUm, barLengthPx) or umPerPx, not both")
    if bar:
        if bar_um <= 0 or bar_px < 2:
            raise MeasureInputError("a scale-bar calibration needs barLengthUm > 0 and barLengthPx >= 2")
        return {"calibrated": True, "method": "scale-bar", "barLengthUm": bar_um, "barLengthPx": bar_px,
                "umPerPx": _checked_scale(bar_um / bar_px), "note": note,
                "derivation": "umPerPx = barLengthUm / barLengthPx (caliper drawn by the user over the image scale bar)"}
    if um_per_px > 0:
        _checked_scale(um_per_px)
        if not note or not note.strip():
            raise MeasureInputError("umPerPx needs a calibrationNote stating where the pixel size comes from")
        return {"calibrated": True, "method": "pixel-size", "umPerPx": um_per_px, "note": note,
                "derivation": "umPerPx entered by the user (source stated in note)"}
    return {"calibrated": False, "method": None, "umPerPx": None,
            "reason": "uncalibrated: no scale bar or pixel size was supplied"}


def parse_classes(req: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    dark = _int("darkMaxGrey", req["darkMaxGrey"], -1, 254)
    bright = _int("brightMinGrey", req["brightMinGrey"], 1, 256)
    if dark >= 0:
        out["dark"] = {"label": _label("darkLabel", req["darkLabel"], "dark class"), "maxGrey": dark,
                       "rule": "grey <= maxGrey"}
    if bright <= 255:
        out["bright"] = {"label": _label("brightLabel", req["brightLabel"], "bright class"), "minGrey": bright,
                         "rule": "grey >= minGrey"}
    if "dark" in out and "bright" in out and dark >= bright:
        raise MeasureInputError("classes overlap: darkMaxGrey must be below brightMinGrey")
    return out


def class_mask(grey: np.ndarray, key: str, cls: Dict[str, Any], shift: int = 0) -> np.ndarray:
    if key == "dark":
        return grey <= min(255, max(-1, cls["maxGrey"] + shift))
    return grey >= min(256, max(0, cls["minGrey"] + shift))


# --- area fraction -------------------------------------------------------------

def tile_fractions(mask: np.ndarray, k: int) -> np.ndarray:
    rows = np.array_split(np.arange(mask.shape[0]), k)
    cols = np.array_split(np.arange(mask.shape[1]), k)
    return np.array([mask[r[0]:r[-1] + 1, c[0]:c[-1] + 1].mean() for r in rows for c in cols], dtype=float)


def area_fraction(grey: np.ndarray, key: str, cls: Dict[str, Any], tiles: int, delta: int,
                  um_per_px: Optional[float]) -> Dict[str, Any]:
    mask = class_mask(grey, key, cls)
    fraction = float(mask.mean())
    per_tile = tile_fractions(mask, tiles)
    ci = _mean_ci(per_tile)
    half = ci["halfWidth"]
    method = ("pixel count of the class inside the ROI (A_A; equals V_V only for isotropic uniform random "
              "sections, ASTM E1245 practice)")
    interval = None if half is None else (max(0.0, fraction - half), min(1.0, fraction + half))
    sensitivity = {
        "deltaGrey": delta,
        "fractionAtThresholdMinusDelta": float(class_mask(grey, key, cls, -delta).mean()),
        "fractionAtThresholdPlusDelta": float(class_mask(grey, key, cls, +delta).mean()),
        "note": "fraction with the class threshold moved by -/+deltaGrey grey levels",
    }
    area = (_quantity(mask.sum() * um_per_px ** 2, "µm²", "pixel count x (µm/px)²")
            if um_per_px else _unavailable("uncalibrated: no area in µm² without a scale", "µm²"))
    return {
        "pixelFraction": _quantity(fraction, "1", method, interval),
        "fieldToField": {
            "tiles": f"{tiles}x{tiles}", "n": ci["n"], "tileFractions": [float(v) for v in per_tile],
            "mean": ci["mean"], "sd": ci["sd"], "tCritical": ci["tCritical"], "halfWidth": half,
            "note": "Student-t 95 % half-width of the tile fractions (t_{0.975,n-1} s / sqrt(n)), "
                    "applied around the whole-ROI fraction; tiles of one image are not independent specimens",
        },
        "thresholdSensitivity": sensitivity,
        "classArea": area,
        "pixelCount": int(mask.sum()),
    }


# --- particles -----------------------------------------------------------------

def _run_starts(lab: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Pixels of a component whose predecessor along direction (dy, dx) is not the same component."""
    padded = np.pad(lab, 1)
    h, w = lab.shape
    prev = padded[1 - dy:1 - dy + h, 1 - dx:1 - dx + w]
    return (lab > 0) & (prev != lab)


def crossings_per_line(mask: np.ndarray, axis: int) -> np.ndarray:
    """Number of runs of True along each row (axis=1) or column (axis=0)."""
    m = mask if axis == 1 else mask.T
    starts = m[:, 1:] & ~m[:, :-1]
    return starts.sum(axis=1) + m[:, 0]


def particles(grey: np.ndarray, key: str, cls: Dict[str, Any], min_area_px: int,
              um_per_px: Optional[float], fraction: float) -> Dict[str, Any]:
    mask = class_mask(grey, key, cls)
    lab, n_all = ndimage.label(mask, structure=_EIGHT)
    areas = np.bincount(lab.ravel(), minlength=n_all + 1).astype(float)
    keep = np.flatnonzero(areas >= min_area_px)
    keep = keep[keep > 0]
    count = int(keep.size)
    h, w = mask.shape
    roi_area_px = float(h * w)
    # Cauchy-Crofton perimeter with 4 line directions (0, 90, 45, 135 degrees):
    # P ~ (pi/4) (R0 + R90 + (R45 + R135)/sqrt(2)), R = number of runs (chords) per direction.
    runs = [np.bincount(lab[_run_starts(lab, dy, dx)], minlength=n_all + 1).astype(float)
            for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1))]
    perimeter = (math.pi / 4.0) * (runs[0] + runs[1] + (runs[2] + runs[3]) / math.sqrt(2.0))
    ys, xs = np.nonzero(lab)
    owner = lab[ys, xs]
    xs, ys = xs.astype(float), ys.astype(float)
    sums = {name: np.bincount(owner, weights=wt, minlength=n_all + 1) for name, wt in
            (("x", xs), ("y", ys), ("xx", xs * xs), ("yy", ys * ys), ("xy", xs * ys))}
    # Per-component moments, vectorised (a noisy 4096 x 4096 image can hold about a million components).
    a = areas[keep]
    cx, cy = sums["x"][keep] / a, sums["y"][keep] / a
    sxx = sums["xx"][keep] / a - cx * cx + 1.0 / 12.0
    syy = sums["yy"][keep] / a - cy * cy + 1.0 / 12.0
    sxy = sums["xy"][keep] / a - cx * cy
    tr, det = sxx + syy, sxx * syy - sxy * sxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    aspect = np.sqrt((tr / 2.0 + disc) / np.maximum(tr / 2.0 - disc, 1e-12))
    per = perimeter[keep]
    with np.errstate(divide="ignore", invalid="ignore"):
        circ = np.where(per > 0, 4.0 * math.pi * a / np.where(per > 0, per, 1.0) ** 2, np.nan)
    shape = np.select(
        [(a < SHAPE_MIN_AREA_PX) | ~np.isfinite(circ), aspect >= ELONGATED_MIN_ASPECT,
         (circ >= NEAR_CIRCULAR_MIN_CIRCULARITY) & (aspect <= NEAR_CIRCULAR_MAX_ASPECT)],
        ["too-small-to-classify", "elongated", "near-circular"], "irregular")
    border = np.unique(np.concatenate((lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1])))
    edge = np.isin(keep, border)
    ecd_px_all = 2.0 * np.sqrt(a / math.pi)
    listed = keep[:MAX_PARTICLES_LISTED]
    objects = ndimage.find_objects(lab, max_label=int(listed[-1])) if listed.size else []
    items: List[Dict[str, Any]] = []
    for j, i in enumerate(listed):
        sl = objects[i - 1]
        items.append({
            "id": int(i), "areaPx": int(a[j]), "centroidX": float(cx[j]), "centroidY": float(cy[j]),
            "bbox": [int(sl[1].start), int(sl[0].start), int(sl[1].stop), int(sl[0].stop)],
            "ecdPx": float(ecd_px_all[j]), "ecdUm": float(ecd_px_all[j] * um_per_px) if um_per_px else None,
            "perimeterPx": float(per[j]), "circularity": float(circ[j]) if np.isfinite(circ[j]) else None,
            "aspectRatio": float(aspect[j]), "shapeClass": str(shape[j]), "touchesRoiEdge": bool(edge[j]),
        })
    shape_counts = {name: int(np.count_nonzero(shape == name))
                    for name in ("near-circular", "irregular", "elongated", "too-small-to-classify")}
    n_interior = int(np.count_nonzero(~edge))
    out: Dict[str, Any] = {
        "connectivity": 8, "minAreaPx": min_area_px,
        "componentsBelowMinArea": int(n_all - count),
        "count": count, "countTouchingRoiEdge": count - n_interior,
        "numberPerMegapixel": count / roi_area_px * 1e6,
        "shapeClasses": shape_counts,
        "shapeClassRule": (f"too-small-to-classify: area < {SHAPE_MIN_AREA_PX} px; elongated: aspect >= "
                           f"{ELONGATED_MIN_ASPECT}; near-circular: circularity >= {NEAR_CIRCULAR_MIN_CIRCULARITY} and "
                           f"aspect <= {NEAR_CIRCULAR_MAX_ASPECT}; otherwise irregular. Descriptive convention, "
                           "not a cause (gas pore / lack of fusion) assignment. Circularity = 4 pi A / P^2 with the "
                           "4-direction Cauchy-Crofton perimeter estimate."),
        "sizeStatisticsBasis": "particles not touching the ROI edge (edge particles are truncated)",
        "particleList": items[:MAX_PARTICLES_LISTED],
        "particleListTruncated": count > MAX_PARTICLES_LISTED,
    }
    ecd_px = ecd_px_all[~edge]
    if um_per_px:
        out["detectionLimitEcdUm"] = _quantity(2.0 * math.sqrt(min_area_px / math.pi) * um_per_px, "µm",
                                               "ECD of a component of minAreaPx pixels")
        out["numberDensity"] = _quantity(count / (roi_area_px * (um_per_px / 1000.0) ** 2), "1/mm²",
                                         "count / ROI area")
    else:
        reason = "uncalibrated: no length without a scale"
        out["detectionLimitEcdUm"] = _unavailable(reason, "µm")
        out["numberDensity"] = _unavailable("uncalibrated: no density per mm² without a scale", "1/mm²")
    if ecd_px.size == 0:
        none = "no particle above the detection limit away from the ROI edge"
        for name in ("meanEcd", "medianEcd", "maxEcd", "sdEcd"):
            out[name] = _unavailable(none, "µm")
    elif not um_per_px:
        for name in ("meanEcd", "medianEcd", "maxEcd", "sdEcd"):
            out[name] = _unavailable("uncalibrated: no length without a scale", "µm")
        out["meanEcdPx"] = float(ecd_px.mean())
    else:
        e = ecd_px * um_per_px
        out["meanEcd"] = _quantity(e.mean(), "µm", "mean equivalent circle diameter 2 sqrt(A/pi)")
        out["medianEcd"] = _quantity(np.median(e), "µm", "median ECD")
        out["maxEcd"] = _quantity(e.max(), "µm", "largest ECD")
        out["sdEcd"] = (_quantity(e.std(ddof=1), "µm", "sample SD of ECD") if e.size >= 2
                        else _unavailable("fewer than two particles", "µm"))
    # Mean free path from the mask crossings along every ROI row and column.
    intercepts = float(crossings_per_line(mask, 1).sum() + crossings_per_line(mask, 0).sum())
    line_px = float(h * w + w * h)
    out["interceptsPerPixelLine"] = intercepts / line_px
    if intercepts == 0:
        out["meanFreePath"] = _unavailable("no class intercepts on the ROI rows and columns", "µm")
    elif not um_per_px:
        out["meanFreePath"] = _unavailable("uncalibrated: no length without a scale", "µm")
        out["meanFreePathPx"] = (1.0 - fraction) / (intercepts / line_px)
    else:
        n_l = intercepts / (line_px * um_per_px)
        out["meanFreePath"] = _quantity((1.0 - fraction) / n_l, "µm",
                                        "lambda = (1 - V_V) / N_L; N_L = runs of the class mask on every ROI row and "
                                        "column per unit line length (every run counts 1, including runs cut by the ROI "
                                        "edge); V_V taken as the pixel area fraction (isotropic assumption)")
    return out


# --- grain size (E112 intercept) ------------------------------------------------

def intercept_test_lines(roi_h: int, roi_w: int, per_direction: int) -> List[Dict[str, Any]]:
    """Horizontal rows round(i H/(m+1)) and vertical columns round(i W/(m+1)), i = 1..m (ROI coordinates).
    Rejects a line count the cropped ROI cannot hold as distinct in-range lines (no repeated observations)."""
    for name, size in (("rows", roi_h), ("columns", roi_w)):
        pos = [int(round(i * size / (per_direction + 1))) for i in range(1, per_direction + 1)]
        if len(set(pos)) != len(pos) or min(pos) < 0 or max(pos) > size - 1:
            raise MeasureInputError(f"linesPerDirection {per_direction} does not fit the {size} {name} of the region of "
                                    "interest as distinct test lines; use fewer lines or a larger region")
    lines = []
    for i in range(1, per_direction + 1):
        lines.append({"index": len(lines), "orientation": "h", "position": int(round(i * roi_h / (per_direction + 1))),
                      "lengthPx": roi_w})
    for i in range(1, per_direction + 1):
        lines.append({"index": len(lines), "orientation": "v", "position": int(round(i * roi_w / (per_direction + 1))),
                      "lengthPx": roi_h})
    return lines


def count_line(profile: np.ndarray) -> Tuple[float, List[Tuple[float, float]], bool]:
    """E112 intersections on one line: each boundary run counts 1, 1/2 when it touches a line end.
    Returns (P, [(position, weight)], along_boundary)."""
    b = profile.astype(np.int8)
    edges = np.diff(np.concatenate(([0], b, [0])))
    starts, stops = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    n = profile.size
    points, total, along = [], 0.0, False
    for s, e in zip(starts, stops):
        at_start, at_end = s == 0, e == n
        if at_start and at_end:
            along = True
            continue
        weight = 0.5 if (at_start or at_end) else 1.0
        points.append(((s + e - 1) / 2.0, weight))
        total += weight
    return total, points, along


def _e112_g(lbar_um: float) -> float:
    return E112_SLOPE * math.log10(lbar_um / 1000.0) + E112_OFFSET


def intercept_statistics(lines: List[Dict[str, Any]], counts: List[float], um_per_px: Optional[float],
                         mode: str, excluded: Tuple[int, ...] = ()) -> Dict[str, Any]:
    """Pooled P_L = sum(P) / sum(L) over the usable lines, l_bar = 1 / P_L, with the ratio-estimator
    standard error se = sqrt(sum((P_i - P_L L_i)^2) / (n (n - 1))) / mean(L) (lines as clusters). The same
    estimator gives the value and its interval, so the interval always contains the value, also for lines
    of unequal length (rectangular ROI). Lines in ``excluded`` (lying on a boundary) are dropped from both."""
    dropped = set(excluded)
    use = [i for i in range(len(lines)) if i not in dropped]
    lengths = np.array([lines[i]["lengthPx"] for i in use], dtype=float)
    p = np.array([counts[i] for i in use], dtype=float)
    total_p, total_l = float(p.sum()), float(lengths.sum())
    out: Dict[str, Any] = {
        "mode": mode, "lines": len(use), "excludedLines": list(excluded), "totalLengthPx": total_l,
        "totalIntersections": total_p, "warnings": [],
        "countingRule": ("ASTM E112 intersection count P: one per contiguous boundary run crossed, 1/2 when a run "
                         "touches a line end; test lines at 0 and 90 degrees; triple points are not scored 1 1/2; a "
                         "line lying entirely on boundary pixels is excluded from both P and L"),
    }
    if excluded:
        out["warnings"].append(f"test line(s) {list(excluded)} lie entirely on boundary pixels and were excluded "
                               "from P and L; consider another line count or crop")
    unavailable = None
    if len(use) < 2:
        unavailable = "fewer than two usable test lines"
    elif total_p <= 0:
        unavailable = "no boundary intersections on the test lines"
    if unavailable:
        out.update(meanInterceptPx=None, meanIntercept=_unavailable(unavailable, "µm"),
                   astmG=_unavailable(unavailable, None), relativeAccuracyPct=None)
        return out
    n = len(use)
    p_l = total_p / total_l
    se = math.sqrt(float(np.sum((p - p_l * lengths) ** 2)) / (n * (n - 1))) / float(lengths.mean())
    t = _t975(n)
    half = t * se
    lbar_px = 1.0 / p_l
    out["meanInterceptPx"] = lbar_px
    out["intersectionsPerPx"] = {"pooled": p_l, "standardError": se, "n": n, "tCritical": t, "halfWidth": half,
                                 "estimator": "ratio estimator over test lines (sum P / sum L)"}
    ra = 100.0 * half / p_l
    out["relativeAccuracyPct"] = ra
    if total_p < FEW_INTERCEPTS:
        out["warnings"].append(f"only {total_p:g} intersections counted (E112 recommends at least {FEW_INTERCEPTS} per field; "
                               "add lines or fields)")
    if ra > HIGH_RELATIVE_ACCURACY_PCT:
        out["warnings"].append(f"relative accuracy {ra:.1f} % exceeds {HIGH_RELATIVE_ACCURACY_PCT:g} %")
    if not um_per_px:
        reason = "uncalibrated: no length or ASTM G without a scale"
        out["meanIntercept"] = _unavailable(reason, "µm")
        out["astmG"] = _unavailable(reason, None)
        return out
    lbar_um = lbar_px * um_per_px
    lbar_hi = None if p_l - half <= 0 else um_per_px / (p_l - half)
    lbar_lo = um_per_px / (p_l + half)
    out["meanIntercept"] = _quantity(lbar_um, "µm", "l_bar = total line length / total intersections",
                                     (lbar_lo, lbar_hi))
    out["astmG"] = _quantity(_e112_g(lbar_um), None, "G = -6.643856 log10(l_bar / mm) - 3.288 (ASTM E112)",
                             (None if lbar_hi is None else _e112_g(lbar_hi), _e112_g(lbar_lo)))
    out["ciNote"] = ("95 % interval over the test lines of this one image (ratio-estimator standard error, "
                     "t_{0.975,n-1}), mapped to l_bar and G; lines of one image are not independent fields or specimens")
    return out


def grain_size_auto(grey: np.ndarray, boundary_max_grey: int, lines: List[Dict[str, Any]],
                    um_per_px: Optional[float]) -> Dict[str, Any]:
    boundary = grey <= boundary_max_grey
    counts, points, along = [], [], []
    for ln in lines:
        profile = boundary[ln["position"], :] if ln["orientation"] == "h" else boundary[:, ln["position"]]
        total, pts, on_boundary = count_line(profile)
        counts.append(total)
        if on_boundary:
            along.append(ln["index"])
        for pos, weight in pts:
            x, y = (pos, ln["position"]) if ln["orientation"] == "h" else (ln["position"], pos)
            points.append({"line": ln["index"], "x": float(x), "y": float(y), "weight": weight})
    out = intercept_statistics(lines, counts, um_per_px, "automatic: boundaries darker than grains", tuple(along))
    out["boundaryMaxGrey"] = boundary_max_grey
    out["perLineIntersections"] = counts
    out["intersections"] = points
    # Diagnostic: grain boundaries form a connected network; isolated dark features (pores, particles) do not.
    lab, n = ndimage.label(boundary, structure=_EIGHT)
    if n:
        sizes = np.bincount(lab.ravel())[1:]
        largest = float(sizes.max() / sizes.sum())
        out["boundaryNetworkLargestComponentShare"] = largest
        if largest < 0.5:
            out["warnings"].append("dark pixels do not form a connected network (largest component holds "
                                   f"{100 * largest:.0f} %); check that the image shows grain boundaries, not pores")
    out["boundaryFractionOfRoi"] = float(boundary.mean())
    return out


def grain_size_manual(counts: Any, clicks: Any, lines: List[Dict[str, Any]],
                      um_per_px: Optional[float], roi: Dict[str, int]) -> Dict[str, Any]:
    if not isinstance(counts, list):
        raise MeasureInputError("manualCounts must be a list with one intersection count per test line")
    if len(counts) != len(lines):
        raise MeasureInputError(f"manualCounts needs {len(lines)} entries (one per test line)")
    values = []
    for i, c in enumerate(counts):
        v = _finite(f"manualCounts[{i}]", c)
        if v < 0 or v * 2 != int(v * 2):
            raise MeasureInputError(f"manualCounts[{i}] must be a non-negative multiple of 0.5")
        values.append(v)
    checked = None
    if clicks is not None:
        if not isinstance(clicks, list) or len(clicks) > 20000:
            raise MeasureInputError("manualClicks must be a list of at most 20000 points")
        if not all(isinstance(c, dict) for c in clicks):
            raise MeasureInputError("manualClicks entries must be objects {line, x, y, weight}")
        checked = [{"line": _int("manualClicks.line", c.get("line"), 0, len(lines) - 1),
                    "x": _finite("manualClicks.x", c.get("x")), "y": _finite("manualClicks.y", c.get("y")),
                    "weight": _finite("manualClicks.weight", c.get("weight", 1))} for c in clicks]
        sums = [0.0] * len(lines)
        for k, c in enumerate(checked):
            ln = lines[c["line"]]
            if c["weight"] not in (0.5, 1.0):
                raise MeasureInputError(f"manualClicks[{k}].weight must be 1 or 0.5")
            # Image coordinates: the line lies at ROI offset + position; the click must sit on it, inside the ROI.
            if ln["orientation"] == "h":
                across, along = c["y"] - roi["y0"], c["x"] - roi["x0"]
            else:
                across, along = c["x"] - roi["x0"], c["y"] - roi["y0"]
            if abs(across - ln["position"]) > 0.5 or not 0 <= along <= ln["lengthPx"] - 1:
                raise MeasureInputError(f"manualClicks[{k}] does not lie on test line {c['line']} of the current region "
                                        "of interest; recount after changing the crop or line count")
            sums[c["line"]] += c["weight"]
        if sums != values:
            raise MeasureInputError("manualCounts must equal the per-line sums of manualClicks weights")
    out = intercept_statistics(lines, values, um_per_px, "manual: intersections clicked by the user")
    out["perLineIntersections"] = values
    if checked is not None:
        out["clicks"] = checked
    return out


# --- entry point -----------------------------------------------------------------

def measure(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise MeasureInputError("payload must be an object")
    unknown = sorted(set(payload) - REQUEST_KEYS)
    if unknown:
        raise MeasureInputError(f"unknown request keys: {unknown}")
    req = read_request(payload)
    image = decode_image(req["imageWidth"], req["imageHeight"], req["imageData"])
    roi = parse_roi(req, image.shape)
    calibration = parse_calibration(req)
    um_per_px = calibration["umPerPx"]
    classes = parse_classes(req)
    tiles = _int("tiles", req["tiles"], 2, 10)
    delta = _int("sensitivityDeltaGrey", req["sensitivityDeltaGrey"], 1, 64)
    min_area = _int("minAreaPx", req["minAreaPx"], 1, 100000)
    per_direction = _int("linesPerDirection", req["linesPerDirection"], 1, MAX_LINES_PER_DIRECTION)
    boundary_max = _int("boundaryMaxGrey", req["boundaryMaxGrey"], -1, 254)
    if not isinstance(req["returnMasks"], bool):
        raise MeasureInputError("returnMasks must be a boolean")
    if not classes and boundary_max < 0 and req["manualCounts"] is None:
        raise MeasureInputError("nothing to measure: set darkMaxGrey, brightMinGrey, boundaryMaxGrey or manualCounts")

    roi_grey = image[roi["y0"]:roi["y1"], roi["x0"]:roi["x1"]]
    h, w = roi_grey.shape
    if classes and 2 * tiles > min(h, w):
        raise MeasureInputError(f"tiles {tiles} x {tiles} need at least {2 * tiles} px per side of the region of interest "
                                f"(it is {w} x {h}); use fewer tiles")
    lines = intercept_test_lines(h, w, per_direction)
    result: Dict[str, Any] = {
        "schema": SCHEMA,
        "methodVersion": METHOD_VERSION,
        "record": {
            "generatedBy": "python/micrograph_measure.py",
            "pixelSha256": hashlib.sha256(image.tobytes()).hexdigest(),
            "pixelSha256Basis": "sha256 of the received 8-bit greyscale bytes (row-major, width x height)",
            "width": int(image.shape[1]), "height": int(image.shape[0]), "roi": roi,
            "roiAreaPx": int(h * w),
            "calibration": calibration,
            "classes": classes,
            "options": {"tiles": tiles, "sensitivityDeltaGrey": delta, "minAreaPx": min_area,
                        "linesPerDirection": per_direction, "connectivity": 8,
                        "boundaryMaxGrey": boundary_max if boundary_max >= 0 else None},
        },
        "calibrationRequired": None if calibration["calibrated"] else calibration["reason"],
        "testLines": [dict(ln, roiOffset=[roi["x0"], roi["y0"]]) for ln in lines],
        "classes": {},
        "grainSize": None,
        "grainSizeManual": None,
        "limitations": list(LIMITATIONS),
    }
    for key, cls in classes.items():
        af = area_fraction(roi_grey, key, cls, tiles, delta, um_per_px)
        entry = {"label": cls["label"], "threshold": cls, "areaFraction": af,
                 "particles": particles(roi_grey, key, cls, min_area, um_per_px, af["pixelFraction"]["value"])}
        if req["returnMasks"]:
            entry["maskPackedBase64"] = base64.b64encode(np.packbits(class_mask(roi_grey, key, cls), axis=None)).decode("ascii")
            entry["maskEncoding"] = "numpy packbits (big bit order) of the ROI mask, row-major, ROI width x height"
        result["classes"][key] = entry
    if boundary_max >= 0:
        result["grainSize"] = grain_size_auto(roi_grey, boundary_max, lines, um_per_px)
    if req["manualCounts"] is not None:
        result["grainSizeManual"] = grain_size_manual(req["manualCounts"], req["manualClicks"], lines, um_per_px, roi)
    elif req["manualClicks"] is not None:
        raise MeasureInputError("manualClicks needs manualCounts")
    return result


def main() -> None:
    import json
    import sys
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        result = measure(payload)
    except MeasureInputError as exc:
        print(json.dumps({"success": False, "errorKind": "validation",
                          "error": {"code": "INVALID_INPUT", "field": "request", "message": str(exc), "detail": {}}}))
        sys.exit(2)
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "errorKind": "validation",
                          "error": {"code": "INVALID_INPUT", "field": "request", "message": f"invalid request: {exc}",
                                    "detail": {}}}))
        sys.exit(2)
    except Exception as exc:  # pragma: no cover - reported, never hidden
        print(json.dumps({"success": False, "errorKind": "internal", "error": f"{type(exc).__name__}: {exc}"}))
        sys.exit(1)
    try:
        text = json.dumps(result, allow_nan=False)  # a non-finite number is an internal error, never published
    except ValueError as exc:
        print(json.dumps({"success": False, "errorKind": "internal", "error": f"non-finite result value: {exc}"}))
        sys.exit(1)
    sys.stdout.write(text)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
