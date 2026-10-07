"""Open LPBF melt-pool screening benchmark: published inputs, submission scoring and leaderboard aggregation.

SCREENING BENCHMARK, NOT VALIDATION. Anyone can predict the melt-pool width and depth of the published trainable
single tracks from process inputs only (``data/benchmark/leaderboard/inputs-v1.csv``: no width, no depth), and have
the predictions scored with the SAME protocol as the calibration scorecard:

  * held out per (material, source) block of the trainable sources; a source the submission declares it trained on is
    excluded from that submission's score and marked as such (never silently dropped);
  * set-grouped clusters (``lpbf_calibration_stats.set_key``), MAPE on resolved rows, mean |ln(pred / meas)|;
  * paired skill against the frozen ROSENTHAL kernel at its default absorptivity (the solver's default heat source),
    ``1 - MAPE_A / MAPE_B`` on the common resolved rows, paired cluster bootstrap with B and seed from
    ``CALIBRATION_CONFIG``;
  * 90 % interval coverage with a Wilson 95 % interval when the submission supplies intervals;
  * a missing, blank or invalid prediction is UNRESOLVED; ``mapeUnresolvedAsFail`` scores it as a 100 % error.

Truth (width, depth) is never written to the inputs file: it is read at scoring time from the pinned dataset loaders
through ``lpbf_calibration_fit.load_rows`` and the manifest pins the loader table hashes. The 11 catalog sentinels
(Guo, NIST IN718; used while the physics was developed, so NOT blind) live in a separate inputs file and are scored in
a separate block.

This module reuses ``lpbf_calibration_stats`` and ``lpbf_calibration_fit`` read-only and edits neither. No network is
used anywhere. Every output stays ``screening-only``; nothing here promotes an evidence label.

CLI: ``python -B python/lpbf_benchmark.py export_inputs [--check]`` (scoring/leaderboard CLI:
``python/tools/lpbf_benchmark_score.py``).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

PYTHON_DIR = Path(__file__).resolve().parent
REPO_ROOT = PYTHON_DIR.parent
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(PYTHON_DIR / "tools"))

import lpbf_calibration_stats as st  # noqa: E402
from lpbf_calibration_config import (  # noqa: E402
    ARTEFACT_REL_PATH, CALIBRATION_CONFIG as CFG, CATALOG_SOURCES, KERNELS, TRAINABLE_SOURCES, canonical_json,
    config_sha256)

BENCH_DIR_REL = "data/benchmark/leaderboard"
INPUTS_NAME = "inputs-v1.csv"
SENTINEL_NAME = "inputs-sentinels-v1.csv"
MANIFEST_NAME = "manifest-v1.json"
SUBMISSIONS_DIR = "submissions"
LEADERBOARD_STEM = "LPBF_LEADERBOARD_"
MANIFEST_SCHEMA = "lpbf-benchmark-manifest-1"
SCORE_SCHEMA = "lpbf-benchmark-score-1"
LEADERBOARD_SCHEMA = "lpbf-leaderboard-1"
BENCHMARK_VERSION = "v1"
BASELINE_KERNEL = "rosenthal"
INPUT_COLUMNS = ("row_id", "source", "material", "P", "v", "beam", "preheat", "layer", "hatch", "regime_class_input")
QUANTITIES = ("width", "depth")
KERNEL_NAMES = {"rosenthal": "Rosenthal screening kernel", "eagar-tsai": "Eagar-Tsai v2 kernel",
                "goldak": "Goldak v3 kernel"}
EVIDENCE_KIND = "screening-only"
EVIDENCE_LABEL = "Screening benchmark: predictions scored on published single tracks; not validation"
HONESTY = ("Screening benchmark of melt-pool width and depth predictions against published single tracks; not "
           "experimental validation; no per-row measurement uncertainty exists in any source; the built-in entries "
           "are the frozen screening kernels at their default absorptivity; scores are per (material, source) block "
           "and are never combined into one cross-material rank; experimentalValidation=false")
MAX_SUBMISSION_ROWS = 5000


class BenchmarkError(ValueError):
    """Malformed submission, manifest drift or any other refusal; never swallowed into a silent result."""


# ---------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def dumps(obj: Any) -> str:
    """Byte-stable JSON text (sorted keys, 1-space indent, trailing newline)."""
    return json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def bench_dir(root: Path) -> Path:
    return Path(root) / BENCH_DIR_REL


def slugify(name: str, version: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{name}-{version}".lower()).strip("-")[:80].strip("-")
    if not slug:
        raise BenchmarkError("meta name/version give an empty slug")
    return slug


# ---------------------------------------------------------------------------------------------
# truth loaders (pinned) and the published inputs
# ---------------------------------------------------------------------------------------------
def load_truth(quick: bool = False) -> Dict[str, Any]:
    """{'trainable': [...], 'catalog': [...], 'provenance': {...}} from the pinned loaders (the scorecard's loader)."""
    import lpbf_calibration_fit as fit
    return fit.load_rows(quick)


def _num(x: Any) -> str:
    return "" if x is None else repr(float(x))


def inputs_csv(rows: Sequence[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(INPUT_COLUMNS)
    for r in rows:
        w.writerow([r["rowId"], r["source"], r["material"], _num(r["power_W"]), _num(r["speed_mm_s"]),
                    _num(r["beamDiameter_um"]), _num(r["preheat_C"]), _num(r.get("layer_um")),
                    _num(r.get("hatch_um")), r["regimeClass"]])
    return buf.getvalue()


def _ordered(rows: Sequence[Dict[str, Any]], source_order: Sequence[str]) -> List[Dict[str, Any]]:
    rank = {s: i for i, s in enumerate(source_order)}
    return [r for _, r in sorted(enumerate(rows), key=lambda t: (rank.get(t[1]["source"], 99), t[0]))]


def build_inputs(loaded: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """(inputs csv text, sentinel csv text, manifest). No width/depth column exists in either file."""
    tr = _ordered(loaded["trainable"], TRAINABLE_SOURCES)
    ca = _ordered(loaded["catalog"], CATALOG_SOURCES)
    ids = [r["rowId"] for r in tr + ca]
    if len(set(ids)) != len(ids):
        raise BenchmarkError("duplicate row ids across the trainable and sentinel rows")
    inputs, sentinels = inputs_csv(tr), inputs_csv(ca)
    prov = loaded["provenance"]
    per_source = {s: sum(1 for r in tr if r["source"] == s) for s in TRAINABLE_SOURCES}
    sentinel_per_source = {s: sum(1 for r in ca if r["source"] == s) for s in CATALOG_SOURCES}
    manifest = {
        "schema": MANIFEST_SCHEMA, "version": BENCHMARK_VERSION,
        "inputsFile": INPUTS_NAME, "inputsSha256": sha256_text(inputs),
        "sentinelsFile": SENTINEL_NAME, "sentinelsSha256": sha256_text(sentinels),
        "columns": list(INPUT_COLUMNS),
        "truthColumnsInInputs": [],
        "truthSource": "read at scoring time from the pinned loaders (lpbf_calibration_fit.load_rows); never published here",
        "tableSha256": {s: prov[s]["tableSha256"] for s in TRAINABLE_SOURCES},
        "rowsPerSource": per_source, "sentinelRowsPerSource": sentinel_per_source,
        "trainableSources": list(TRAINABLE_SOURCES), "sentinelSources": list(CATALOG_SOURCES),
        "sentinelNote": CFG["dataRoles"]["catalogSentinelNote"],
        "configSha256": config_sha256(),
        "protocol": protocol_block(),
        "evidence": {"kind": EVIDENCE_KIND, "statement": EVIDENCE_LABEL, "experimentalValidation": False},
    }
    return inputs, sentinels, manifest


def protocol_block() -> Dict[str, Any]:
    boot = CFG["bootstrap"]
    return {
        "heldOut": "per (material, source) block of the trainable sources; sources a submission declares in "
                   "trainedOnSources are excluded and marked as such",
        "clusters": "parameter set via lpbf_calibration_stats.set_key = (source, material, power_W, speed_mm_s, beamDiameter_um)",
        "metrics": ["mapePct on resolved rows", "meanAbsLn = mean |ln(pred / meas)| on resolved rows",
                    "mapeUnresolvedAsFailPct (an unresolved row counts as a 100 % error)"],
        "skill": {"baselineKernel": BASELINE_KERNEL, "baseline": "frozen Rosenthal kernel at its default absorptivity",
                  "statistic": "1 - MAPE_A / MAPE_B on the common resolved rows",
                  "bootstrap": {"B": boot["skillReplicates"], "seed": boot["seed"],
                                "unit": "test parameter set (cluster), predictions fixed"}},
        "coverage": {"nominal": 0.9, "interval": "Wilson 95 %", "columns": "width_lo90,width_hi90,depth_lo90,depth_hi90 (absolute um)"},
        "unresolved": "a missing, blank row counts as unresolved; mapeUnresolvedAsFail scores it as a 100 % error",
        "noCrossMaterialRank": True,
    }


def export_inputs(root: Path = REPO_ROOT, loaded: Optional[Dict[str, Any]] = None, check: bool = False) -> List[str]:
    """Write (or with ``check`` only compare) inputs-v1.csv, inputs-sentinels-v1.csv and manifest-v1.json."""
    loaded = loaded or load_truth()
    inputs, sentinels, manifest = build_inputs(loaded)
    out = {INPUTS_NAME: inputs, SENTINEL_NAME: sentinels, MANIFEST_NAME: dumps(manifest)}
    problems: List[str] = []
    for name, text in out.items():
        p = bench_dir(root) / name
        if check:
            if not p.is_file():
                problems.append(f"{name} is missing")
            elif read_text(p) != text:
                problems.append(f"{name} differs from the pinned loaders")
        else:
            write_text(p, text)
    return problems


def verify_manifest(root: Path, loaded: Dict[str, Any]) -> Dict[str, Any]:
    """Refuse to score when the committed inputs/manifest no longer match the pinned loaders or the config."""
    inputs, sentinels, manifest = build_inputs(loaded)
    d = bench_dir(root)
    for name, text in ((INPUTS_NAME, inputs), (SENTINEL_NAME, sentinels), (MANIFEST_NAME, dumps(manifest))):
        p = d / name
        if not p.is_file():
            raise BenchmarkError(f"{p} is missing; run python python/lpbf_benchmark.py export_inputs")
        if read_text(p) != text:
            raise BenchmarkError(f"{name} drifted from the pinned loaders or the calibration config; "
                                 f"re-export and review before scoring anything")
    return manifest


def read_input_rows(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------------------------
# default-eta kernel table (baseline and built-in entries)
# ---------------------------------------------------------------------------------------------
def _all_input_rows(loaded: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(loaded["trainable"]) + list(loaded["catalog"])


def load_default_table(loaded: Dict[str, Any], fp: str, cache: Optional[Path] = None, jobs: int = 1,
                       solver: Optional[Callable] = None) -> Dict[str, Any]:
    """Kernel table holding at least the default-eta geometry (``dW``/``dD``/``ds``) of every input for every frozen
    kernel. Accepts the scorecard's cache (same schema) or builds a default-only table (nodes = []) on the frozen
    CPU flat-plate path. A cache that exists is never written when it already carries an absorptivity grid."""
    import lpbf_calibration_fit as fit
    inputs = {fit.input_key(r): fit.input_args(r) for r in _all_input_rows(loaded)}
    existing = None
    if cache and cache.is_file():
        cand = json.loads(cache.read_text(encoding="utf-8"))
        if cand.get("implementationHash") != fp:
            raise BenchmarkError(f"kernel table cache {cache} was built for implementation hash "
                                 f"{cand.get('implementationHash')}, current {fp}: refused (delete it to rebuild)")
        if cand.get("kernels") != list(KERNELS):
            raise BenchmarkError(f"kernel table cache {cache} has a different kernel set: refused")
        existing = cand
    missing = {k: v for k, v in inputs.items() if not existing or k not in existing["entries"]}
    if not missing:
        return existing  # type: ignore[return-value]
    nodes = existing["nodes"] if existing else []
    if existing is not None and nodes:
        # a scorecard grid cache with gaps: compute the gap default-only in memory, never write into that cache
        extra = fit.build_table(missing, KERNELS, [], jobs, solver, None)
        merged = dict(existing)
        merged["statuses"] = list(existing["statuses"])
        merged["entries"] = dict(existing["entries"])
        remap = {i: _status_code(merged["statuses"], s) for i, s in enumerate(extra["statuses"])}
        for key, per_k in extra["entries"].items():
            merged["entries"][key] = {k: dict(v, ds=remap[v["ds"]]) for k, v in per_k.items()}
        return merged
    table = fit.build_table(missing, KERNELS, [], jobs, solver, existing)
    table["implementationHash"] = fp
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(table, sort_keys=True, separators=(",", ":")), encoding="utf-8", newline="\n")
    return table


def _status_code(statuses: List[str], s: str) -> int:
    if s not in statuses:
        statuses.append(s)
    return statuses.index(s)


def default_geometry(table: Dict[str, Any], row: Dict[str, Any], kernel: str) -> Tuple[Optional[float], Optional[float]]:
    """(W, D) of ``kernel`` at the material default absorptivity, or (None, None) when it did not compute."""
    import lpbf_calibration_fit as fit
    e = table["entries"][fit.input_key(row)][kernel]
    if table["statuses"][e["ds"]] != "computed":
        return None, None
    w, d = e.get("dW"), e.get("dD")
    if w is None or d is None or not (math.isfinite(w) and math.isfinite(d)) or w <= 0 or d <= 0:
        return None, None
    return float(w), float(d)


def _default_arrays(table: Dict[str, Any], rows: Sequence[Dict[str, Any]], kernel: str) -> Dict[str, List[Optional[float]]]:
    pairs = [default_geometry(table, r, kernel) for r in rows]
    return {"width": [p[0] for p in pairs], "depth": [p[1] for p in pairs]}


# ---------------------------------------------------------------------------------------------
# scoring one set of predictions
# ---------------------------------------------------------------------------------------------
def _arr(xs: Sequence[Optional[float]]) -> Tuple[np.ndarray, np.ndarray]:
    a = np.array([np.nan if x is None else float(x) for x in xs], dtype=float)
    ok = np.isfinite(a) & (a > 0)
    return np.where(ok, a, 1.0), ok


def _cluster_ids(rows: Sequence[Dict[str, Any]]) -> np.ndarray:
    keys: Dict[tuple, int] = {}
    return np.array([keys.setdefault(st.set_key(r), len(keys)) for r in rows], dtype=int)


def score_block(rows: Sequence[Dict[str, Any]], q: str, pred: Sequence[Optional[float]],
                base: Sequence[Optional[float]], lo: Optional[Sequence[Optional[float]]] = None,
                hi: Optional[Sequence[Optional[float]]] = None, cfg: Dict[str, Any] = CFG) -> Dict[str, Any]:
    """Metrics of one (material, source, quantity) block. ``base`` is the frozen baseline kernel prediction."""
    meas = np.array([float(r[f"{q}_um"]) for r in rows], dtype=float)
    p, ok = _arr(pred)
    b, bok = _arr(base)
    cluster = _cluster_ids(rows)
    m = st.metrics(p, meas, ok)
    n = int(meas.size)
    mean_abs_ln = float(np.mean(np.abs(np.log(p[ok] / meas[ok])))) if ok.any() else None
    fail = st.mape_unresolved_as_fail(p, meas, ok)
    common = ok & bok
    sk = st.paired_skill(p, b, meas, common, cluster, cfg["bootstrap"]["skillReplicates"], cfg["bootstrap"]["seed"])
    cov = None
    if lo is not None and hi is not None:
        lo_a, lo_ok = _arr(lo)
        hi_a, hi_ok = _arr(hi)
        have = ok & lo_ok & hi_ok
        k_n = int(have.sum())
        if k_n:
            k = int(((meas[have] >= lo_a[have]) & (meas[have] <= hi_a[have])).sum())
            cov = {"k": k, "n": k_n, "coverage": k / k_n, "wilson95": st.wilson(k, k_n, 0.95),
                   "nResolvedWithoutInterval": int((ok & ~(lo_ok & hi_ok)).sum())}
    return {
        "status": "scored", "nRows": n, "nSets": int(len(np.unique(cluster))), "nResolved": m["n"],
        "unresolved": m["unresolved"], "mapePct": m["mapePct"], "meanAbsLn": mean_abs_ln,
        "mapeUnresolvedAsFailPct": fail, "biasPct": m["biasPct"],
        "skill": sk["skill"], "skillCi95": sk["ci95"], "nCommon": sk["n"], "baselineMapePct": sk["mapeB"],
        "coverage90": cov,
    }


def _blocks(rows: Sequence[Dict[str, Any]]) -> List[Tuple[str, str, List[int]]]:
    order: Dict[Tuple[str, str], List[int]] = {}
    for i, r in enumerate(rows):
        order.setdefault((r["material"], r["source"]), []).append(i)
    return [(m, s, idx) for (m, s), idx in sorted(order.items())]


def score_rows(rows: Sequence[Dict[str, Any]], preds: Dict[str, Dict[str, Any]], base: Dict[str, List[Optional[float]]],
               trained_on: Sequence[str], cfg: Dict[str, Any] = CFG) -> List[Dict[str, Any]]:
    """Cells for every (material, source, quantity) block of ``rows``. ``preds`` maps rowId to
    ``{width, depth, width_lo90, ...}`` (absent = unresolved). ``base`` holds baseline arrays aligned with ``rows``."""
    cells: List[Dict[str, Any]] = []
    trained = set(trained_on)
    for material, source, idx in _blocks(rows):
        sub = [rows[i] for i in idx]
        for q in QUANTITIES:
            head = {"material": material, "quantity": q, "heldOutSource": source}
            if source in trained:
                cluster = _cluster_ids(sub)
                cells.append(dict(head, status="excluded-trained-on", nRows=len(sub), nSets=int(len(np.unique(cluster))),
                                  reason="the submission declares it trained on this source; not held out, so not scored"))
                continue
            get = lambda key: [preds.get(r["rowId"], {}).get(key) for r in sub]  # noqa: E731
            lo = get(f"{q}_lo90")
            hi = get(f"{q}_hi90")
            has_iv = any(x is not None for x in lo) and any(x is not None for x in hi)
            cell = score_block(sub, q, get(q), [base[q][i] for i in idx], lo if has_iv else None,
                               hi if has_iv else None, cfg)
            cells.append(dict(head, **cell))
    return cells


def entry_for(entry_id: str, kind: str, meta: Dict[str, Any], rows_t: Sequence[Dict[str, Any]],
              rows_c: Sequence[Dict[str, Any]], preds: Dict[str, Dict[str, Any]], table: Dict[str, Any],
              manifest: Dict[str, Any], fp: str, provenance_extra: Dict[str, Any]) -> Dict[str, Any]:
    base_t = _default_arrays(table, rows_t, BASELINE_KERNEL)
    base_c = _default_arrays(table, rows_c, BASELINE_KERNEL)
    trained = list(meta.get("trainedOnSources", []))
    prov = {"manifestSha256": sha256_text(dumps(manifest)), "configSha256": config_sha256(), "implementationHash": fp,
            "baselineKernel": BASELINE_KERNEL}
    prov.update(provenance_extra)
    return {
        "id": entry_id, "kind": kind, "name": meta["name"], "version": meta["version"], "author": meta["author"],
        "description": meta["description"], "url": meta.get("url", ""), "trainedOnSources": trained,
        "provenance": prov,
        "cells": score_rows(rows_t, preds, base_t, trained),
        "sentinels": score_rows(rows_c, preds, base_c, trained),
    }


# ---------------------------------------------------------------------------------------------
# submissions
# ---------------------------------------------------------------------------------------------
META_FIELDS = ("name", "version", "author", "description", "url", "trainedOnSources")


def check_meta(meta: Any) -> Dict[str, Any]:
    if not isinstance(meta, dict):
        raise BenchmarkError("meta must be a JSON object")
    extra = sorted(set(meta) - set(META_FIELDS))
    if extra:
        raise BenchmarkError(f"unknown meta field(s): {', '.join(extra)}")
    out: Dict[str, Any] = {}
    for f, limit in (("name", 80), ("version", 40), ("author", 120), ("description", 600), ("url", 300)):
        v = meta.get(f, "" if f in ("url", "description") else None)
        if not isinstance(v, str) or (f in ("name", "version", "author") and not v.strip()):
            raise BenchmarkError(f"meta.{f} must be a{' non-empty' if f in ('name', 'version', 'author') else ''} string")
        if len(v) > limit or any(ord(c) < 32 for c in v):
            raise BenchmarkError(f"meta.{f} is too long or contains control characters")
        out[f] = v.strip()
    trained = meta.get("trainedOnSources")
    if not isinstance(trained, list) or not all(isinstance(x, str) for x in trained):
        raise BenchmarkError("meta.trainedOnSources must be a list of source names (use [] for none)")
    known = set(TRAINABLE_SOURCES) | set(CATALOG_SOURCES)
    unknown = sorted(set(trained) - known)
    if unknown:
        raise BenchmarkError(f"meta.trainedOnSources names unknown source(s): {', '.join(unknown)}")
    out["trainedOnSources"] = sorted(set(trained))
    slugify(out["name"], out["version"])
    return out


def _parse_value(text: str, where: str) -> Optional[float]:
    t = (text or "").strip()
    if t == "":
        return None
    try:
        v = float(t)
    except ValueError:
        raise BenchmarkError(f"{where}: {t!r} is not a number") from None
    if not (math.isfinite(v) and v > 0):
        raise BenchmarkError(f"{where}: {t!r} must be finite and positive")
    return v


def parse_submission(csv_text: str, known_ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """{rowId: {width, depth, width_lo90, ...}} from a submission CSV. Raises on unknown or duplicate ids, a
    non-finite / non-positive value, or a missing required column; a blank cell is an unresolved prediction."""
    reader = csv.DictReader(io.StringIO(csv_text))
    cols = list(reader.fieldnames or [])
    for need in ("row_id", "width_um", "depth_um"):
        if need not in cols:
            raise BenchmarkError(f"submission is missing the required column {need!r}")
    known_cols = {"row_id", "width_um", "depth_um", "width_lo90", "width_hi90", "depth_lo90", "depth_hi90"}
    unknown_cols = [c for c in cols if c not in known_cols]
    if unknown_cols:
        raise BenchmarkError(f"unknown submission column(s): {', '.join(unknown_cols)}")
    for q in QUANTITIES:
        if (f"{q}_lo90" in cols) != (f"{q}_hi90" in cols):
            raise BenchmarkError(f"{q}_lo90 and {q}_hi90 must be given together")
    known = set(known_ids)
    out: Dict[str, Dict[str, Any]] = {}
    for n, rec in enumerate(reader, start=2):
        rid = (rec.get("row_id") or "").strip()
        if rid == "":
            raise BenchmarkError(f"line {n}: empty row_id")
        if rid not in known:
            raise BenchmarkError(f"line {n}: unknown row_id {rid!r}")
        if rid in out:
            raise BenchmarkError(f"line {n}: duplicate row_id {rid!r}")
        if len(out) >= MAX_SUBMISSION_ROWS:
            raise BenchmarkError("submission has more rows than the benchmark")
        vals: Dict[str, Any] = {}
        for q in QUANTITIES:
            vals[q] = _parse_value(rec.get(f"{q}_um", ""), f"line {n} {q}_um")
            if f"{q}_lo90" in cols:
                lo = _parse_value(rec.get(f"{q}_lo90", ""), f"line {n} {q}_lo90")
                hi = _parse_value(rec.get(f"{q}_hi90", ""), f"line {n} {q}_hi90")
                if (lo is None) != (hi is None):
                    raise BenchmarkError(f"line {n}: {q}_lo90 and {q}_hi90 must both be filled or both blank")
                if lo is not None and hi is not None and lo > hi:
                    raise BenchmarkError(f"line {n}: {q}_lo90 exceeds {q}_hi90")
                vals[f"{q}_lo90"], vals[f"{q}_hi90"] = lo, hi
        out[rid] = vals
    return out


def score_submission(root: Path, csv_bytes: bytes, meta_raw: Any, table: Dict[str, Any], fp: str,
                     loaded: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
    """(slug, score document) of one submission against the committed inputs and the pinned truth loaders."""
    loaded = loaded or load_truth()
    manifest = verify_manifest(root, loaded)
    meta = check_meta(meta_raw)
    rows_t = _ordered(loaded["trainable"], TRAINABLE_SOURCES)
    rows_c = _ordered(loaded["catalog"], CATALOG_SOURCES)
    preds = parse_submission(csv_bytes.decode("utf-8").replace("\r\n", "\n"), [r["rowId"] for r in rows_t + rows_c])
    slug = slugify(meta["name"], meta["version"])
    entry = entry_for(f"submission:{slug}", "local-submission", meta, rows_t, rows_c, preds, table, manifest, fp,
                      {"submissionCsvSha256": sha256_bytes(csv_bytes),
                       "metaSha256": sha256_text(canonical_json(meta)),
                       "rowsSubmitted": len(preds)})
    doc = {"schema": SCORE_SCHEMA, "slug": slug, "evidence": {"kind": EVIDENCE_KIND, "statement": EVIDENCE_LABEL},
           "entry": entry}
    return slug, doc


# ---------------------------------------------------------------------------------------------
# built-in entries and the leaderboard
# ---------------------------------------------------------------------------------------------
def calibrated_rung_status(root: Path) -> Dict[str, Any]:
    """Number of gate-enabled cells in the committed calibration artefact. The calibrated rung is only ever scored for
    enabled cells; today there are none, which is stated in the record and no calibrated entry is invented."""
    p = Path(root) / ARTEFACT_REL_PATH
    if not p.is_file():
        return {"enabledCells": 0, "artefact": None, "note": "no calibration artefact committed; no calibrated entry"}
    doc = json.loads(p.read_text(encoding="utf-8"))
    enabled = [c for c in doc.get("cells", []) if c.get("status") == "enabled"]
    if enabled:
        raise BenchmarkError(f"{len(enabled)} calibration cell(s) are gate-enabled but the leaderboard does not yet "
                             f"score the calibrated rung; refusing to publish a record that silently omits them")
    return {"enabledCells": 0, "artefact": ARTEFACT_REL_PATH,
            "note": "No calibration cell is enabled by the gate, so no calibrated entry exists; built-in entries are "
                    "the frozen kernels at default absorptivity"}


def builtin_entries(loaded: Dict[str, Any], table: Dict[str, Any], manifest: Dict[str, Any], fp: str) -> List[Dict[str, Any]]:
    rows_t = _ordered(loaded["trainable"], TRAINABLE_SOURCES)
    rows_c = _ordered(loaded["catalog"], CATALOG_SOURCES)
    out = []
    for k in KERNELS:
        preds: Dict[str, Dict[str, Any]] = {}
        for r in rows_t + rows_c:
            w, d = default_geometry(table, r, k)
            preds[r["rowId"]] = {"width": w, "depth": d}
        digest = sha256_text(canonical_json({"kernel": k, "implementationHash": fp,
                                             "predictions": {i: [st.round_sig(v["width"], 6), st.round_sig(v["depth"], 6)]
                                                             for i, v in sorted(preds.items())}}))
        meta = {"name": KERNEL_NAMES[k], "version": "frozen-default-eta", "author": "Metalliksa frozen screening kernels",
                "description": f"{KERNEL_NAMES[k]} at the material default absorptivity on the CPU flat-plate path; "
                               "no fit, no calibration.",
                "url": "", "trainedOnSources": []}
        out.append(entry_for(f"builtin:{k}", "built-in-kernel", meta, rows_t, rows_c, preds, table, manifest, fp,
                             {"predictionsSha256": digest, "kernel": k}))
    return out


def load_submission_entries(root: Path, manifest: Dict[str, Any], fp: str) -> List[Dict[str, Any]]:
    d = bench_dir(root) / SUBMISSIONS_DIR
    entries = []
    want = {"manifestSha256": sha256_text(dumps(manifest)), "configSha256": config_sha256(), "implementationHash": fp}
    for p in sorted(d.glob("*.score.json")) if d.is_dir() else []:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if doc.get("schema") != SCORE_SCHEMA:
            raise BenchmarkError(f"{p.name}: unexpected schema {doc.get('schema')!r}")
        prov = doc["entry"]["provenance"]
        stale = [k for k, v in want.items() if prov.get(k) != v]
        if stale:
            raise BenchmarkError(f"{p.name} is stale ({', '.join(stale)} changed): re-score the submission")
        entries.append(doc["entry"])
    return sorted(entries, key=lambda e: e["id"])


def build_leaderboard(root: Path, loaded: Dict[str, Any], table: Optional[Dict[str, Any]], fp: str, date: str,
                      committed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The aggregate record. Built-in entries come from ``table`` (or, in re-check mode without a table, from the
    committed record itself); local submissions come from submissions/*.score.json."""
    manifest = verify_manifest(root, loaded)
    if table is not None:
        builtin = builtin_entries(loaded, table, manifest, fp)
    elif committed is not None:
        builtin = [e for e in committed["entries"] if e["kind"] == "built-in-kernel"]
    else:
        raise BenchmarkError("built-in entries need a kernel table")
    subs = load_submission_entries(root, manifest, fp)
    doc = {
        "schema": LEADERBOARD_SCHEMA, "generatedAt": date, "implementationHash": fp,
        "configSha256": config_sha256(), "manifestSha256": sha256_text(dumps(manifest)),
        "benchmarkVersion": BENCHMARK_VERSION, "protocol": protocol_block(),
        "evidence": {"kind": EVIDENCE_KIND, "statement": EVIDENCE_LABEL, "experimentalValidation": False,
                     "labelPromotionProposed": "none"},
        "honesty": HONESTY,
        "calibratedRung": calibrated_rung_status(root),
        "entries": sorted(builtin, key=lambda e: e["id"]) + subs,
    }
    return json.loads(canonical_json(st.round_sig(doc, 6)))


def leaderboard_path(root: Path, date: str) -> Path:
    return Path(root) / "docs" / f"{LEADERBOARD_STEM}{date}.json"


def newest_leaderboard(root: Path) -> Optional[Path]:
    found = sorted((Path(root) / "docs").glob(f"{LEADERBOARD_STEM}*.json"))
    return found[-1] if found else None


def write_leaderboard(root: Path, doc: Dict[str, Any]) -> Path:
    p = leaderboard_path(root, doc["generatedAt"])
    write_text(p, dumps(doc))
    return p


def check_leaderboard(root: Path, loaded: Dict[str, Any], fp: str, table: Optional[Dict[str, Any]] = None) -> List[str]:
    """Problems found when re-deriving the newest committed leaderboard: input/manifest drift, a changed config or
    implementation, edited or stale submission scores, and (with a table) any difference in the built-in entries."""
    problems: List[str] = []
    p = newest_leaderboard(root)
    if p is None:
        return ["no committed leaderboard record"]
    committed = json.loads(read_text(p))
    try:
        fresh = build_leaderboard(root, loaded, table, fp, committed["generatedAt"], committed)
    except BenchmarkError as exc:
        return [str(exc)]
    if committed.get("schema") != LEADERBOARD_SCHEMA:
        problems.append(f"{p.name}: unexpected schema")
    if read_text(p) != dumps(fresh):
        problems.append(f"{p.name} differs from the re-derived record "
                        f"({'built-in entries recomputed from the table' if table is not None else 'built-in entries taken from the record'})")
    return problems


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export_inputs", help="write the published inputs, sentinel inputs and manifest")
    ex.add_argument("--check", action="store_true", help="compare with the pinned loaders and fail on drift")
    ex.add_argument("--repo-root", default=str(REPO_ROOT))
    a = ap.parse_args(argv)
    problems = export_inputs(Path(a.repo_root).resolve(), check=a.check)
    for p in problems:
        print("DRIFT:", p, file=sys.stderr)
    if a.check:
        print("check", "FAILED" if problems else "PASSED", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
