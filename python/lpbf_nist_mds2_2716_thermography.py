"""Signal-unit metrics from NIST mds2-2716 (AMB2022-03 IN718 in-situ thermography).

Reads the publisher HDF5 files only after verifying their pinned byte counts
and SHA-256 digests (NIST NERDm record v1.3.1) and derives small, deterministic
tables in raw camera signal units (digital levels, DL).

Honesty rules enforced here:
- The camera signal is NOT converted to temperature. The stored calibration
  ``Model`` string has unbalanced parentheses and an unspecified emissivity
  ``e``, and its Celsius/Kelvin convention is not determinable from the file,
  so every temperature, cooling rate (K/s) and time-above-melting quantity is
  reported as ``unavailable`` with a reason.
- Values >= 4095 DL are saturated (12-bit) and values < 100 DL were stored as
  0 by NIST (``threshold_zeros``), so peak signal is upper-censored and the
  floor is lower-censored. Zero is not zero temperature.
- Pixel pitch and the camera-axis to machine-axis mapping are inferred from the
  hot-spot speed against the commanded scan speed (README: +/-2.5 % k=1); they
  are labelled ``derived-inferred``.
- X/Y/P in the scan-strategy file are commanded galvo positions and power
  (GalvoCal_Applied/LaserCal_Applied 'false'); T is a trigger command, not
  time. The 10 us sample interval is not stored and is inferred.
- Comparison, not validation: nothing here validates the application.

Raw files are never committed. Resolution order for the data directory:
explicit ``data_dir`` argument, ``$METALLIKSA_NIST_2716_DIR``,
``$METALLIKSA_EXTERNAL_DATA/nist-mds2-2716`` (external-data-manifest.json
convention), then ``<repo>/data/benchmark/nist-amb2022-03/raw`` (git-ignored).

CLI (writes the committed derived table and its manifest):
    python python/lpbf_nist_mds2_2716_thermography.py --data-dir DIR [--out-dir DIR]
"""

import argparse
import hashlib
import json
import os
import platform
import re
import sys
from pathlib import Path

DATASET_ID = "nist-mds2-2716-thermography-signal-v1"
SOURCE_DATASET_ID = "nist-mds2-2716"
SCHEMA = "lpbf-nist-2716-thermography-signal-metrics-1"
REPO = Path(__file__).resolve().parents[1]
DATASET_DIR = REPO / "data" / "benchmark" / "nist-amb2022-03"
DEFAULT_RAW_DIR = DATASET_DIR / "raw"
DERIVED_DIR = DATASET_DIR / "derived"
DERIVED_NAME = "thermography-signal-metrics-v1.json"
EXTERNAL_ID = "nist-mds2-2716"

THERMO_NAME = "AMB2022-03-718-AMMT-StaringCamera_Signal.h5"
XYPT_NAME = "AMB2022-03-AMMT-718-Pad_XYPT.h5"

_BASE = "https://data.nist.gov/od/ds/ark:/88434/mds2-2716/"
PINNED = {
    THERMO_NAME: {"bytes": 549979044,
                  "sha256": "f6fe21ec911707f72e7efda2932c77eae2b75d84765848878fe5beb6b728cd43",
                  "source_url": _BASE + "Thermography/" + THERMO_NAME, "required": True},
    XYPT_NAME: {"bytes": 406992,
                "sha256": "7b7004753e150bc26632e9ce356e0440429160fa92cbff8fc8559202fdce2103",
                "source_url": _BASE + "ScanStrategy/" + XYPT_NAME, "required": True},
    "README.txt": {"bytes": 12573,
                   "sha256": "ba44076ed51b69c0e4ca80ff0e2568eed2dc6459e85c9ad83b85860bee5760f2",
                   "source_url": "https://data.nist.gov/od/ds/mds2-2716/2716_README.txt", "required": False},
}

FRAME_RATE_HZ = 30000.0
SAT_DL = 4095
FLOOR_DL = 100
CHUNK_FRAMES = 25
TAT_THRESHOLDS_DL = (100, 500, 1000, 2000, 4095)
DECAY_TARGETS_DL = (2000, 1000, 500, 100)
SPEED_UNCERTAINTY_REL_K1 = 0.025
XYPT_DT_ASSUMED_S = 1e-5
STATUSES = ("measured-signal", "derived-commanded", "derived-inferred", "sensitivity-only", "unavailable")

TEMPERATURE_UNAVAILABLE_REASON = (
    "No temperature conversion executed: the stored /Calibration/ThermalCal Model string has unbalanced "
    "parentheses and an unspecified emissivity e, its Celsius/Kelvin convention is not determinable from "
    "the file, and the melt-pool region is saturated at 4095 DL. A reviewed equation, a cited emissivity "
    "and the valid calibration range are required.")
COOLING_RATE_UNAVAILABLE_REASON = (
    "Cooling rate (K/s) and time above solidus/liquidus need T(DL) at the solidus/liquidus, which needs "
    "the unavailable temperature conversion; signal-decay times below are not cooling rates.")


class H5pyUnavailable(RuntimeError):
    pass


def _h5py():
    try:
        import h5py  # noqa: PLC0415 - optional dependency, imported lazily
    except ImportError as exc:  # pragma: no cover - depends on interpreter
        raise H5pyUnavailable("h5py not installed in this interpreter (%s)" % sys.executable) from exc
    return h5py


def _np():
    import numpy  # noqa: PLC0415
    return numpy


# ---------------------------------------------------------------- locating data

def resolve_data_dir(data_dir=None):
    """Return the directory holding the raw files, or None when none is configured/present."""
    if data_dir:
        return Path(data_dir)
    env = os.environ.get("METALLIKSA_NIST_2716_DIR")
    if env:
        return Path(env)
    ext = os.environ.get("METALLIKSA_EXTERNAL_DATA")
    candidates = []
    if ext:
        candidates.append(Path(ext) / EXTERNAL_ID)
    candidates.append(REPO / "external-data" / EXTERNAL_ID)
    candidates.append(DEFAULT_RAW_DIR)
    for cand in candidates:
        if (cand / THERMO_NAME).is_file() and (cand / XYPT_NAME).is_file():
            return cand
    return None


def raw_absent_reason(data_dir=None):
    """None when both pinned HDF5 files exist, else an explicit reason string."""
    d = resolve_data_dir(data_dir)
    if d is None:
        return ("NIST mds2-2716 raw HDF5 files not found: set METALLIKSA_NIST_2716_DIR or place them under "
                "$METALLIKSA_EXTERNAL_DATA/nist-mds2-2716 or data/benchmark/nist-amb2022-03/raw "
                "(549,979,044 B + 406,992 B, not committed to git)")
    missing = [n for n in (THERMO_NAME, XYPT_NAME) if not (d / n).is_file()]
    if missing:
        return "NIST mds2-2716 raw file(s) missing in %s: %s" % (d, ", ".join(missing))
    return None


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def verify_inputs(data_dir=None):
    """Size + SHA-256 check of the pinned files. Raises ValueError on any mismatch."""
    d = resolve_data_dir(data_dir)
    reason = raw_absent_reason(d)
    if reason:
        raise ValueError(reason)
    out = {}
    for name, pin in PINNED.items():
        path = d / name
        if name == "README.txt" and not path.is_file():
            alt = d / "2716_README.txt"
            path = alt if alt.is_file() else path
        if not path.is_file():
            if pin["required"]:
                raise ValueError("NIST mds2-2716 pinned file missing: %s" % name)
            out[name] = {"status": "absent", "reason": "optional README not present in data directory",
                         "bytes": pin["bytes"], "sha256": pin["sha256"], "source_url": pin["source_url"]}
            continue
        size = path.stat().st_size
        if size != pin["bytes"]:
            raise ValueError("NIST mds2-2716 size mismatch for %s: %d != %d" % (name, size, pin["bytes"]))
        digest = sha256_file(path)
        if digest != pin["sha256"]:
            raise ValueError("NIST mds2-2716 SHA-256 mismatch for %s: %s" % (name, digest))
        out[name] = {"status": "verified", "bytes": size, "sha256": digest, "source_url": pin["source_url"]}
    return out


# ---------------------------------------------------------------- group names

_LINE0 = re.compile(r"^Line_0_([1-3])$")
_LINE = re.compile(r"^Line_([1-3])_([12])_([1-3])$")
_PAD = re.compile(r"^([XY])_pad([12])(_SS)?$")


def parse_group_name(name):
    """Parse a /ThermalData group name. Raises ValueError for anything unexpected."""
    m = _LINE0.match(name)
    if m:
        return {"name": name, "kind": "line", "set": 0, "subset": None, "repeat": int(m.group(1)),
                "caseId": "0", "challenge": True}
    m = _LINE.match(name)
    if m:
        return {"name": name, "kind": "line", "set": int(m.group(1)), "subset": int(m.group(2)),
                "repeat": int(m.group(3)), "caseId": "%s.%s" % (m.group(1), m.group(2)), "challenge": True}
    m = _PAD.match(name)
    if m:
        ss = bool(m.group(3))
        return {"name": name, "kind": "pad_ss" if ss else "pad", "axis": m.group(1), "pad": int(m.group(2)),
                "caseId": None, "challenge": not ss}
    raise ValueError("unexpected NIST mds2-2716 ThermalData group name: %r" % name)


def _scalar(attrs, key, where):
    if key not in attrs:
        raise ValueError("missing attribute %s on %s" % (key, where))
    val = attrs[key]
    try:
        return float(_np().asarray(val).reshape(-1)[0])
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError("non-numeric attribute %s on %s" % (key, where)) from exc


def _text(attrs, key):
    val = attrs.get(key)
    if isinstance(val, bytes):
        return val.decode("utf-8")
    return None if val is None else str(val)


def check_thermal_attrs(f):
    """Assert the constants used below against the file attributes (A3)."""
    td = f["ThermalData"]
    rate = _scalar(td.attrs, "frame_rate", "/ThermalData")
    if rate != FRAME_RATE_HZ:
        raise ValueError("frame_rate attribute %r != %r" % (rate, FRAME_RATE_HZ))
    for name in td:
        ds = td[name]["Signal"]
        bit = _scalar(ds.attrs, "bit_depth", name)
        thr = _scalar(ds.attrs, "threshold_level", name)
        if bit != 12 or (2 ** int(bit) - 1) != SAT_DL:
            raise ValueError("bit_depth %r on %s does not give saturation %d" % (bit, name, SAT_DL))
        if thr != FLOOR_DL:
            raise ValueError("threshold_level %r on %s != %d" % (thr, name, FLOOR_DL))
        if _text(ds.attrs, "threshold_zeros") != "true":
            raise ValueError("threshold_zeros on %s is not 'true'" % name)
        if ds.dtype.kind != "u" or ds.ndim != 3:
            raise ValueError("unexpected Signal dtype/shape on %s: %s %s" % (name, ds.dtype, ds.shape))
    return {"frameRate_Hz": rate, "saturation_DL": SAT_DL, "floor_DL": FLOOR_DL, "datasets": len(td)}


def list_signal_groups(f):
    out = []
    td = f["ThermalData"]
    for name in sorted(td):
        info = parse_group_name(name)
        g = td[name]
        info.update({
            "laserPower_W": _scalar(g.attrs, "laser_power", name),
            "scanSpeed_mm_s": _scalar(g.attrs, "scan_speed", name),
            "spotD4s_um": _scalar(g.attrs, "spot_size", name),
            "spotMeasure": _text(g.attrs, "spot_size_measure"),
            "nFrames": int(g["Signal"].shape[0]),
            "frameShape": [int(x) for x in g["Signal"].shape[1:]],
        })
        out.append(info)
    return out


def iter_frames(ds, start=0, stop=None, block=CHUNK_FRAMES):
    """Chunk-aligned streaming over frames; never reads more than ``block`` frames at once.

    For long videos (pads, 10,001-40,001 frames); single-line videos (700 frames) are read whole.
    """
    stop = ds.shape[0] if stop is None else min(stop, ds.shape[0])
    i = start
    while i < stop:
        j = min(stop, (i // block + 1) * block)
        yield i, ds[i:j]
        i = j


# ---------------------------------------------------------------- scan strategy

def _vec(ds, where):
    np = _np()
    arr = np.asarray(ds[()])
    if arr.ndim == 2 and 1 in arr.shape:
        arr = arr.reshape(-1)
    if arr.ndim != 1:
        raise ValueError("XYPT %s has unexpected shape %s" % (where, arr.shape))
    return arr


def read_xypt(data_dir=None, verify=True, path=None):
    """Return {pad: {X, Y, P, T, galvoCalApplied, laserCalApplied}}. T is a trigger command, NOT time."""
    if path is None:
        if verify:
            verify_inputs(data_dir)
        path = resolve_data_dir(data_dir) / XYPT_NAME
    out = {}
    with _h5py().File(path, "r") as f:
        cal = f["Calibration"].attrs
        galvo = _text(cal, "GalvoCal_Applied")
        laser = _text(cal, "LaserCal_Applied")
        for pad in sorted(f["XYPT"]):
            g = f["XYPT"][pad]
            vecs = {k: _vec(g[k], "%s/%s" % (pad, k)) for k in ("X", "Y", "P", "T")}
            n = {len(v) for v in vecs.values()}
            if len(n) != 1:
                raise ValueError("XYPT %s channels have different lengths: %s" % (pad, sorted(n)))
            vecs.update({"galvoCalApplied": galvo, "laserCalApplied": laser})
            out[pad] = vecs
    return out


def camera_trigger_index(xypt_pad, bit=2):
    """Index of the first rising edge of trigger bit ``bit`` (2 = StaringCamera), or None."""
    np = _np()
    t = (np.asarray(xypt_pad["T"]).astype(np.int64) >> bit) & 1
    rise = np.flatnonzero((t[1:] == 1) & (t[:-1] == 0))
    if t.size and t[0] == 1:
        return 0
    return int(rise[0] + 1) if rise.size else None


def segment_tracks(xypt_pad, dt_s=XYPT_DT_ASSUMED_S, commanded_speed_mm_s=None):
    """Laser-on runs (P > 0) as tracks. Positions/power are commanded; dt is an inferred sample period."""
    np = _np()
    p = np.asarray(xypt_pad["P"], dtype=float)
    x = np.asarray(xypt_pad["X"], dtype=float)
    y = np.asarray(xypt_pad["Y"], dtype=float)
    on = p > 0
    edges = np.diff(np.concatenate([[0], on.astype(np.int8), [0]]))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1) - 1
    tracks = []
    for k, (s, e) in enumerate(zip(starts, ends)):
        dx, dy = x[e] - x[s], y[e] - y[s]
        length = float(np.hypot(dx, dy))
        n_on = int(e - s + 1)
        axis = "X" if abs(dx) >= abs(dy) else "Y"
        sign = (dx if axis == "X" else dy)
        v = length / ((n_on - 1) * dt_s) if n_on > 1 else None
        tracks.append({
            "index": k, "startSample": int(s), "endSample": int(e), "onSamples": n_on,
            "startX_mm": float(x[s]), "startY_mm": float(y[s]), "endX_mm": float(x[e]), "endY_mm": float(y[e]),
            "length_mm": length, "direction": ("+" if sign >= 0 else "-") + axis,
            "power_W": float(np.median(p[s:e + 1])),
            "vImplied_mm_s": v,
            "gapToNext_s": float((starts[k + 1] - e - 1) * dt_s) if k + 1 < len(starts) else None,
        })
    if commanded_speed_mm_s:
        for t in tracks:
            if t["vImplied_mm_s"] is not None:
                t["vResidualRel"] = t["vImplied_mm_s"] / commanded_speed_mm_s - 1.0
    return tracks


def summarize_pad_tracks(tracks, commanded_speed_mm_s):
    np = _np()
    if not tracks:
        return {"status": "unavailable", "reason": "no laser-on samples"}
    v = np.array([t["vImplied_mm_s"] for t in tracks if t["vImplied_mm_s"] is not None])
    lengths = np.array([t["length_mm"] for t in tracks])
    starts_perp = []
    for t in tracks:
        starts_perp.append(t["startY_mm"] if t["direction"].endswith("X") else t["startX_mm"])
    hatch = np.abs(np.diff(starts_perp)) if len(starts_perp) > 1 else np.array([])
    gaps = np.array([t["gapToNext_s"] for t in tracks if t["gapToNext_s"] is not None])
    med_v = float(np.median(v))
    return {
        "nTracks": len(tracks),
        "medianLength_mm": float(np.median(lengths)),
        "medianHatch_mm": float(np.median(hatch)) if hatch.size else None,
        "medianImpliedSpeed_mm_s": med_v,
        "impliedSpeedResidualRel": med_v / commanded_speed_mm_s - 1.0,
        "impliedSpeedWithinReadmeUncertainty": abs(med_v / commanded_speed_mm_s - 1.0) <= SPEED_UNCERTAINTY_REL_K1,
        "inferredSamplePeriod_s": float(np.median(lengths / commanded_speed_mm_s /
                                                  np.array([t["onSamples"] - 1 for t in tracks]))),
        "minGap_s": float(gaps.min()) if gaps.size else None,
        "maxGap_s": float(gaps.max()) if gaps.size else None,
        "status": "derived-commanded",
        "note": ("Commanded galvo positions (no galvo calibration applied) at an inferred 10 us sample period; "
                 "implied speed = first-to-last laser-on sample distance / ((onSamples-1) * dt)."),
    }


# ---------------------------------------------------------------- line metrics

def _unavailable(reason, **extra):
    d = {"status": "unavailable", "reason": reason}
    d.update(extra)
    return d


def _robust_line_fit(x, y, iterations=5, floor_px=3.0):
    """Least-squares line with iterative rejection of residuals > max(floor_px, 4 * 1.4826 * MAD)."""
    np = _np()
    keep = np.ones(x.size, dtype=bool)
    for _ in range(iterations):
        coef = np.polyfit(x[keep], y[keep], 1)
        res = y - np.polyval(coef, x)
        mad = float(np.median(np.abs(res[keep] - np.median(res[keep]))))
        new_keep = np.abs(res) <= max(floor_px, 4.0 * 1.4826 * mad)
        if (new_keep == keep).all():
            break
        keep = new_keep
    coef = np.polyfit(x[keep], y[keep], 1)
    res = y[keep] - np.polyval(coef, x[keep])
    ss_tot = float(((y[keep] - y[keep].mean()) ** 2).sum())
    r2 = 1.0 - float((res ** 2).sum()) / ss_tot if ss_tot > 0 else 0.0
    return coef, r2, keep


def locate_track(signal, min_sat_frames=50, min_r2=0.999, max_rejected_fraction=0.1):
    """Locate the scanned track in a [frame, a1, a2] signal array from its saturated hot spot.

    The track column (a2) is the saturated-count-weighted centre of the columns within 5 px of the column
    with the most saturated pixel-frames; the hot spot is followed
    in that column +/-1 px. Laser-on frame is defined operationally as the first frame with a saturated
    pixel in that band. The leading edge is fitted with a robust line (frames whose leading edge is an
    outlier, e.g. a saturated spatter pixel, are rejected and counted). Returns status
    'measured-signal' or 'unavailable' with a reason.
    """
    np = _np()
    sat_all = signal >= SAT_DL
    counts = sat_all.sum(axis=(0, 1)).astype(float)
    peak = int(np.argmax(counts))
    near = np.arange(max(peak - 5, 0), min(peak + 6, counts.size))
    col = int(np.floor((near * counts[near]).sum() / counts[near].sum() + 0.5)) if counts[near].sum() else peak
    cols = [c for c in (col - 1, col, col + 1) if 0 <= c < signal.shape[2]]
    sat = sat_all[:, :, cols]
    del sat_all
    frames = np.flatnonzero(sat.reshape(sat.shape[0], -1).any(axis=1))
    if frames.size < min_sat_frames:
        return _unavailable("only %d frames contain saturated pixels in the track band (< %d required)"
                            % (frames.size, min_sat_frames), nSaturatedFrames=int(frames.size))
    centroid = np.empty(frames.size)
    hi = np.empty(frames.size)
    lo = np.empty(frames.size)
    for i, fr in enumerate(frames):
        rows = np.flatnonzero(sat[fr].any(axis=1))
        centroid[i] = rows.mean()
        hi[i], lo[i] = rows.max(), rows.min()
    slope_c = np.polyfit(frames, centroid, 1)[0]
    lead = hi if slope_c >= 0 else lo
    coef, r2, keep = _robust_line_fit(frames.astype(float), lead)
    rejected = int((~keep).sum())
    if rejected > max_rejected_fraction * frames.size:
        return _unavailable("%d of %d leading-edge frames rejected as outliers (> %d %%)"
                            % (rejected, frames.size, round(max_rejected_fraction * 100)),
                            nSaturatedFrames=int(frames.size))
    if r2 < min_r2:
        return _unavailable("leading-edge motion is not linear (R^2 %.5f < %.3f)" % (r2, min_r2),
                            nSaturatedFrames=int(frames.size), r2=r2)
    ever = np.flatnonzero(sat.any(axis=(0, 2)))
    kept = frames[keep]
    first_rows = np.flatnonzero(sat[kept[0]].any(axis=1))
    last_rows = np.flatnonzero(sat[kept[-1]].any(axis=1))
    if coef[0] >= 0:
        start, end = int(first_rows.min()), int(last_rows.max())
    else:
        start, end = int(first_rows.max()), int(last_rows.min())
    return {
        "status": "measured-signal",
        "laserOnFrame": int(frames[0]), "lastSaturatedFrame": int(frames[-1]),
        "nSaturatedFrames": int(frames.size), "nLeadingEdgeOutlierFrames": rejected,
        "pxPerFrame": float(abs(coef[0])), "motionSign": 1 if coef[0] >= 0 else -1, "leadingEdgeR2": r2,
        "a2Column": col, "a1TrackStart": start, "a1TrackEnd": end,
        "a1TrackExtent_px": abs(end - start) + 1,
        "a1TrackDefinition": ("trailing edge of the saturated region in the first non-outlier saturated frame to "
                              "the leading edge in the last non-outlier saturated frame (track column band)"),
        "a1EverSaturatedInBand": [int(ever.min()), int(ever.max())],
        "a1EverSaturatedNote": ("range of all pixels saturated at any time in the track column band; it can "
                                "include short-lived saturated pixels away from the hot spot (e.g. spatter)"),
        "_lead": lead[keep], "_frames": kept,
    }


def _pixel_metrics(trace):
    """Per-pixel signal metrics on one time series (frames)."""
    np = _np()
    out = {"tat": {}, "decay": {}}
    for thr in TAT_THRESHOLDS_DL:
        out["tat"][thr] = int((trace >= thr).sum())
    sat_idx = np.flatnonzero(trace >= SAT_DL)
    out["saturated"] = bool(sat_idx.size)
    out["gap"] = False
    if sat_idx.size:
        last = int(sat_idx[-1])
        tail = trace[last + 1:]
        for t in DECAY_TARGETS_DL:
            below = np.flatnonzero(tail < t)
            out["decay"][t] = int(below[0] + 1) if below.size else None
        zero = np.flatnonzero(tail == 0)
        if zero.size and (tail[zero[0]:] > 0).any():
            out["gap"] = True
    return out


def _stats(values):
    np = _np()
    vals = np.array([v for v in values if v is not None], dtype=float)
    if vals.size == 0:
        return None
    return {"median": float(np.median(vals)), "p25": float(np.percentile(vals, 25)),
            "p75": float(np.percentile(vals, 75)), "n": int(vals.size)}


def line_metrics(signal, scan_speed_mm_s, frame_rate_hz=FRAME_RATE_HZ, steady_fraction=0.6):
    """All signal-unit metrics for one single-track video. Never returns a temperature."""
    np = _np()
    loc = locate_track(signal)
    if loc["status"] != "measured-signal":
        return {"track": loc}
    lead, frames = loc.pop("_lead"), loc.pop("_frames")
    pitch_um = scan_speed_mm_s / (frame_rate_hz * loc["pxPerFrame"]) * 1000.0
    loc["pixelPitch_um"] = {"value": pitch_um, "relUncertaintyK1": SPEED_UNCERTAINTY_REL_K1,
                            "status": "derived-inferred",
                            "basis": "commanded scan speed / (frame rate * fitted leading-edge px per frame)"}
    loc["trackExtent_mm"] = {"value": loc["a1TrackExtent_px"] * pitch_um / 1000.0, "status": "derived-inferred",
                             "basis": "a1TrackExtent_px * inferred pixel pitch"}
    lo, hi = sorted((loc["a1TrackStart"], loc["a1TrackEnd"]))
    margin = (1.0 - steady_fraction) / 2.0 * (hi - lo)
    s_lo, s_hi = int(np.ceil(lo + margin)), int(np.floor(hi - margin))
    col = loc["a2Column"]
    cols = [c for c in (col - 1, col, col + 1) if 0 <= c < signal.shape[2]]
    pix = [_pixel_metrics(signal[:, a1, a2]) for a1 in range(s_lo, s_hi + 1) for a2 in cols]
    n = len(pix)
    dt = 1.0 / frame_rate_hz
    tat = {}
    for thr in TAT_THRESHOLDS_DL:
        st = _stats([p["tat"][thr] for p in pix])
        tat[str(thr)] = {"frames": st, "seconds_median": st["median"] * dt if st else None,
                         "status": "measured-signal",
                         "upperCensored": thr == SAT_DL,
                         "note": ("frames at the 12-bit saturation level; the true peak is not observed"
                                  if thr == SAT_DL else "frames with signal >= threshold")}
    decay = {}
    for t in DECAY_TARGETS_DL:
        st = _stats([p["decay"][t] for p in pix if p["saturated"]])
        decay["4095to%d" % t] = ({"frames": st, "seconds_median": st["median"] * dt, "status": "measured-signal",
                                  "note": "frames from the last saturated frame to the first frame below the target "
                                          "(relative signal-decay metric, NOT a cooling rate)"}
                                 if st else _unavailable("no saturated steady-state pixel"))
    # Spatial saturated length in steady frames (leading edge inside the steady window).
    sat = signal[:, :, cols] >= SAT_DL
    steady_frames = [int(fr) for fr, ld in zip(frames, lead) if s_lo <= ld <= s_hi]
    blob = []
    for fr in steady_frames:
        rows = np.flatnonzero(sat[fr].any(axis=1))
        if rows.size:
            blob.append(int(rows.max() - rows.min() + 1))
    tat_sat = tat[str(SAT_DL)]["frames"]
    l_temporal = tat_sat["median"] * dt * scan_speed_mm_s * 1000.0 if tat_sat else None
    l_spatial = float(np.median(blob)) * pitch_um if blob else None
    lsat = {
        "temporal_um": l_temporal, "spatial_um": l_spatial,
        "ratioSpatialToTemporal": (l_spatial / l_temporal) if (l_temporal and l_spatial) else None,
        "nSteadyFrames": len(blob), "status": "derived-inferred",
        "note": ("Length of the region at the 4095 DL saturation level. Its isotherm temperature is unknown "
                 "(no calibration applied), so it is not a melt-pool length."),
    }
    return {
        "track": loc,
        "steadyWindow": {"a1From": s_lo, "a1To": s_hi, "a2Columns": cols, "nPixels": n,
                         "definition": "track column +/-1 px, a1 inside the middle %d %% of the track extent"
                                       % round(steady_fraction * 100)},
        "timeAboveThreshold": tat,
        "decayFromSaturation": decay,
        "saturatedLength": lsat,
        "censoring": {"nPixelsSaturated": int(sum(p["saturated"] for p in pix)),
                      "nPixelsReenteringAboveFloor": int(sum(p["gap"] for p in pix)),
                      "upperCensoredAt_DL": SAT_DL, "lowerCensoredBelow_DL": FLOOR_DL,
                      "gapNote": ("pixels whose signal fell to 0 (< 100 DL, zeroed by NIST) after saturation and later rose to "
                                  ">= 100 DL again within the video (e.g. flicker near the floor); counted, not smoothed")},
    }


# ---------------------------------------------------------------- aggregation

def _mean_sd(values):
    np = _np()
    vals = np.array([v for v in values if v is not None], dtype=float)
    if vals.size == 0:
        return None
    sd = float(vals.std(ddof=1)) if vals.size > 1 else None
    m = float(vals.mean())
    return {"mean": m, "sd": sd, "cv": (sd / m) if (sd is not None and m) else None, "n": int(vals.size)}


def _get(d, path):
    for key in path:
        if d is None:
            return None
        d = d.get(key) if isinstance(d, dict) else None
    return d


CASE_METRICS = {
    "pxPerFrame": ("track", "pxPerFrame"),
    "pixelPitch_um": ("track", "pixelPitch_um", "value"),
    "trackExtent_mm": ("track", "trackExtent_mm", "value"),
    "laserOnFrame": ("track", "laserOnFrame"),
    "tat100_frames": ("timeAboveThreshold", "100", "frames", "median"),
    "tat500_frames": ("timeAboveThreshold", "500", "frames", "median"),
    "tat1000_frames": ("timeAboveThreshold", "1000", "frames", "median"),
    "tat2000_frames": ("timeAboveThreshold", "2000", "frames", "median"),
    "tat4095_frames": ("timeAboveThreshold", "4095", "frames", "median"),
    "decay4095to1000_frames": ("decayFromSaturation", "4095to1000", "frames", "median"),
    "decay4095to100_frames": ("decayFromSaturation", "4095to100", "frames", "median"),
    "lsatTemporal_um": ("saturatedLength", "temporal_um"),
    "lsatSpatial_um": ("saturatedLength", "spatial_um"),
}


def aggregate_cases(lines):
    """Mean/SD/CV over the three repeats per case; repeats are never split or dropped."""
    cases = {}
    for row in lines:
        cases.setdefault(row["caseId"], []).append(row)
    out = []
    for cid in sorted(cases, key=lambda c: (c != "0", c)):
        rows = sorted(cases[cid], key=lambda r: r["repeat"])
        first = rows[0]
        metrics = {k: _mean_sd([_get(r["metrics"], p) for r in rows]) for k, p in CASE_METRICS.items()}
        out.append({"caseId": cid, "laserPower_W": first["laserPower_W"], "scanSpeed_mm_s": first["scanSpeed_mm_s"],
                    "spotD4s_um": first["spotD4s_um"], "repeats": [r["name"] for r in rows],
                    "nRepeatsWithMetrics": sum(1 for r in rows if r["metrics"]["track"]["status"] != "unavailable"),
                    "metrics": metrics, "status": "measured-signal"})
    return out


def pitch_consistency(lines):
    np = _np()
    by_speed = {}
    for r in lines:
        p = _get(r["metrics"], ("track", "pixelPitch_um", "value"))
        if p is not None:
            by_speed.setdefault(r["scanSpeed_mm_s"], []).append(p)
    medians = {str(int(k)): float(np.median(v)) for k, v in sorted(by_speed.items())}
    vals = list(medians.values())
    if not vals:
        return _unavailable("no line produced a pixel pitch")
    pooled = float(np.median([p for v in by_speed.values() for p in v]))
    spread = (max(vals) - min(vals)) / pooled
    return {"medianPitchBySpeed_um": medians, "pooledMedian_um": pooled, "betweenSpeedSpreadRel": spread,
            "withinReadmeSpeedUncertainty": spread <= SPEED_UNCERTAINTY_REL_K1, "status": "derived-inferred"}


# ---------------------------------------------------------------- build

def _round(value, sig=6):
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return float("%.*g" % (sig, value)) if value != 0 else 0.0
    if isinstance(value, dict):
        return {k: _round(v, sig) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(v, sig) for v in value]
    return value


UNAVAILABLE = [
    {"quantity": "surface temperature / radiance temperature", "status": "unavailable",
     "reason": TEMPERATURE_UNAVAILABLE_REASON},
    {"quantity": "peak temperature or peak signal", "status": "unavailable",
     "reason": "Melt-pool pixels saturate at 4095 DL in every laser-on frame (upper-censored) and no "
               "temperature conversion is available."},
    {"quantity": "cooling rate (K/s); NIST TSCR, TLCR, PSCR", "status": "unavailable",
     "reason": COOLING_RATE_UNAVAILABLE_REASON},
    {"quantity": "time above melting; NIST TTAM, PTAM", "status": "unavailable",
     "reason": COOLING_RATE_UNAVAILABLE_REASON},
    {"quantity": "melt-pool width/depth", "status": "unavailable",
     "reason": "The staring camera records surface signal only; cross-section geometry is in mds2-2718, not here."},
    {"quantity": "pad thermography metrics (re-heating, revisit, residual signal)", "status": "unavailable",
     "reason": "Not computed in v1: the X_pad videos are 40,001 frames (~15.6 GB uncompressed each); pad camera "
               "analysis is an opt-in follow-up. Only the commanded XYPT track table is derived here."},
]


REFERENCE_TRACK_LENGTH = {
    "value_mm": 10.0, "toleranceAbs_mm": 0.5,
    "source": ("data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json experiment.trackLength_mm "
               "(repo transcription citing AMB2022-03 Measurement and Challenge Descriptions v1.01)"),
}


def build_checks(attrs, lines, pads):
    """Acceptance checks A3-A9 of the lane spec, each with an explicit result."""
    measured = [r for r in lines if r["metrics"]["track"]["status"] == "measured-signal"]
    pc = pitch_consistency(lines)
    extents = [r["metrics"]["track"]["trackExtent_mm"]["value"] for r in measured]
    ref = REFERENCE_TRACK_LENGTH
    checks = [
        {"id": "A3-attributes", "result": "pass",
         "detail": "frame_rate %g, 12-bit saturation %d DL, threshold %d DL on %d datasets"
                   % (attrs["frameRate_Hz"], SAT_DL, FLOOR_DL, attrs["datasets"])},
        {"id": "lines-located", "result": "pass" if len(measured) == len(lines) else "fail",
         "detail": "%d of %d single-track videos located" % (len(measured), len(lines))},
    ]
    if pc.get("status") == "unavailable":
        checks.append({"id": "A4-speed-pitch-consistency", "result": "skipped", "detail": pc["reason"]})
    else:
        checks.append({"id": "A4-speed-pitch-consistency",
                       "result": "pass" if pc["withinReadmeSpeedUncertainty"] else "flag",
                       "detail": "between-speed pitch spread %.4f (limit %.3f, README speed uncertainty k=1)"
                                 % (pc["betweenSpeedSpreadRel"], SPEED_UNCERTAINTY_REL_K1)})
    if extents:
        worst = float(max(abs(e - ref["value_mm"]) for e in extents))
        checks.append({"id": "A5-track-length", "result": "pass" if worst <= ref["toleranceAbs_mm"] else "flag",
                       "detail": "max |extent - %g mm| = %.3f mm over %d lines (tolerance %g mm); reference: %s"
                                 % (ref["value_mm"], worst, len(extents), ref["toleranceAbs_mm"], ref["source"])})
    else:
        checks.append({"id": "A5-track-length", "result": "skipped", "detail": "no line located"})
    cases = {}
    for r in lines:
        cases.setdefault(r["caseId"], []).append(r["repeat"])
    complete = all(sorted(v) == [1, 2, 3] for v in cases.values())
    checks.append({"id": "A6-repeats", "result": "pass" if complete else "fail",
                   "detail": "%d cases, repeats per case %s; none dropped"
                             % (len(cases), sorted({len(v) for v in cases.values()}))})
    if pads:
        n = {k: v["summary"].get("nTracks") for k, v in pads.items()}
        within = all(v["summary"].get("impliedSpeedWithinReadmeUncertainty") for v in pads.values())
        flags = all(v["galvoCalApplied"] == "false" and v["laserCalApplied"] == "false" for v in pads.values())
        checks.append({"id": "A7-xypt", "result": "pass" if (n == {"Xpad": 47, "Ypad": 24} and within and flags)
                       else "flag",
                       "detail": "tracks %s; implied speed within 2.5 %% of 960 mm/s: %s; galvo/laser calibration "
                                 "applied flags 'false': %s" % (n, within, flags)})
    checks.append({"id": "A8-pad-alignment", "result": "skipped",
                   "detail": "pad camera analysis not run in v1 (see unavailable list)"})
    checks.append({"id": "A9-no-temperature", "result": "pass",
                   "detail": "no DL-to-temperature conversion is implemented in this module"})
    return checks


def build_metrics(data_dir=None, lines_only=None, verify=True):
    """Build the derived record. ``lines_only`` restricts to a list of group names (tests)."""
    np = _np()
    h5py = _h5py()
    pins = verify_inputs(data_dir) if verify else {}
    d = resolve_data_dir(data_dir)
    lines = []
    with h5py.File(d / THERMO_NAME, "r") as f:
        attrs = check_thermal_attrs(f)
        groups = list_signal_groups(f)
        for g in groups:
            if g["kind"] != "line" or (lines_only and g["name"] not in lines_only):
                continue
            sig = f["ThermalData"][g["name"]]["Signal"][()]
            m = line_metrics(sig, g["scanSpeed_mm_s"], attrs["frameRate_Hz"])
            del sig
            row = {k: g[k] for k in ("name", "caseId", "set", "subset", "repeat", "laserPower_W",
                                     "scanSpeed_mm_s", "spotD4s_um", "spotMeasure", "nFrames", "challenge")}
            row["metrics"] = m
            lines.append(row)
        group_table = [{k: g[k] for k in ("name", "kind", "caseId", "challenge", "laserPower_W", "scanSpeed_mm_s",
                                          "spotD4s_um", "nFrames")} for g in groups]
    xypt = read_xypt(path=d / XYPT_NAME)
    pads = {}
    for pad, ch in xypt.items():
        tracks = segment_tracks(ch, commanded_speed_mm_s=960.0)
        pads[pad] = {"nSamples": int(len(ch["P"])), "cameraTriggerIndex": camera_trigger_index(ch),
                     "firstLaserOnIndex": tracks[0]["startSample"] if tracks else None,
                     "galvoCalApplied": ch["galvoCalApplied"], "laserCalApplied": ch["laserCalApplied"],
                     "powerLevels_W": sorted({float(v) for v in np.unique(ch["P"])}),
                     "triggerValues": sorted({int(v) for v in np.unique(ch["T"])}),
                     "summary": summarize_pad_tracks(tracks, 960.0), "tracks": tracks}
    record = {
        "checks": build_checks(attrs, lines, pads),
        "schema": SCHEMA, "schemaVersion": 1, "datasetId": DATASET_ID, "sourceDatasetId": SOURCE_DATASET_ID,
        "source": {"doi": "10.18434/mds2-2716", "nerdmVersion": "1.3.1", "license": "https://www.nist.gov/open/license",
                   "citation": ("Deisenroth, D., Lane, B., et al. (2022). AM Bench 2022 in-situ thermography and scan "
                                "strategy for laser-scanned single tracks and pads on bare IN718 (AMB2022-03). "
                                "https://doi.org/10.18434/mds2-2716")},
        "headline": ("Comparison, not validation: raw camera signal in digital levels (DL); no temperature conversion "
                     "executed; derived values are signal-unit metrics for NIST's experiment only; nothing tuned."),
        "evidence": {"experimentalValidation": False, "opticalOperatorMatched": False, "modelAcceptance": False,
                     "temperatureConversion": None, "temperatureConversionMissingReason": TEMPERATURE_UNAVAILABLE_REASON,
                     "evidenceKindMeasuredFor": "NIST experiment only (raw camera signal, DL)",
                     "statusVocabulary": list(STATUSES)},
        "inputs": {name: {k: v for k, v in pin.items() if k != "required"} for name, pin in PINNED.items()},
        "inputVerification": {k: v["status"] for k, v in pins.items()} if pins else "not-run",
        "fileAttributes": attrs,
        "conventions": {
            "frameRate_Hz": FRAME_RATE_HZ, "framePeriod_s": 1.0 / FRAME_RATE_HZ,
            "saturation_DL": SAT_DL, "floor_DL": FLOOR_DL,
            "laserOnFrame": "first frame containing a saturated pixel (operational definition)",
            "axisMapping": ("Line hot spots move along camera axis a1 at a speed proportional to the commanded "
                            "scan speed; a1 is taken as the line scan direction (derived-inferred)."),
            "beamDiameter": "spot_size attribute, measure 'D4s' as stored by NIST",
            "xyptSamplePeriod_s": XYPT_DT_ASSUMED_S,
            "xyptSamplePeriodStatus": "derived-inferred (not stored in the file)",
        },
        "groups": group_table,
        "lines": lines,
        "cases": aggregate_cases(lines),
        "pixelPitchConsistency": pitch_consistency(lines),
        "scanStrategy": pads,
        "unavailable": UNAVAILABLE,
    }
    return _round(record)


def serialize(record):
    return json.dumps(record, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


NERDM_PATH = DATASET_DIR / "official" / "nerdm-record-mds2-2716.json"


def nerdm_record_pin(path=NERDM_PATH):
    data = Path(path).read_bytes()
    return {"path": "../official/nerdm-record-mds2-2716.json", "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "source_url": "https://data.nist.gov/rmm/records?@id=ark:/88434/mds2-2716",
            "note": ("ResultData[0] of the NIST RMM query, re-serialised locally (sorted keys, indent 1, UTF-8); "
                     "the bytes served at source_url will not match, the SHA-256 is locally authoritative only.")}


def nerdm_component_pins(path=NERDM_PATH):
    """{filepath: (size, sha256)} for the NERDm components that carry a checksum."""
    rec = json.loads(Path(path).read_text(encoding="utf-8"))
    return {c["filepath"]: (c.get("size"), c["checksum"]["hash"]) for c in rec.get("components", [])
            if c.get("filepath") and isinstance(c.get("checksum"), dict) and c["checksum"].get("hash")}


def build_derived_manifest(derived_bytes, record):
    import numpy  # noqa: PLC0415
    h5py = _h5py()
    return {
        "schemaVersion": 1, "datasetId": DATASET_ID, "sourceDatasetId": SOURCE_DATASET_ID,
        "derived": {"path": DERIVED_NAME, "bytes": len(derived_bytes),
                    "sha256": hashlib.sha256(derived_bytes).hexdigest()},
        "inputs": [{"name": name, "bytes": pin["bytes"], "sha256": pin["sha256"], "source_url": pin["source_url"]}
                   for name, pin in PINNED.items()],
        "sourceRecord": nerdm_record_pin(),
        "tool": "python/lpbf_nist_mds2_2716_thermography.py",
        "runtime": {"python": platform.python_version(), "h5py": h5py.__version__, "numpy": numpy.__version__},
        "rawStorage": ("Raw HDF5 files are not committed. Canonical local copy: data/benchmark/nist-amb2022-03/raw/ "
                       "(git-ignored), or $METALLIKSA_EXTERNAL_DATA/nist-mds2-2716/ per external-data-manifest.json."),
        "evidence": record["evidence"],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-dir")
    ap.add_argument("--out-dir", default=str(DERIVED_DIR))
    args = ap.parse_args(argv)
    reason = raw_absent_reason(args.data_dir)
    if reason:
        print("ERROR: " + reason, file=sys.stderr)
        return 2
    record = build_metrics(args.data_dir)
    data = serialize(record).encode("utf-8")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / DERIVED_NAME).write_bytes(data)
    manifest = build_derived_manifest(data, record)
    (out / "manifest.json").write_bytes((json.dumps(manifest, sort_keys=True, indent=1) + "\n").encode("utf-8"))
    print("wrote %s (%d bytes)" % (out / DERIVED_NAME, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
