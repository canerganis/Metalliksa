#!/usr/bin/env python3
"""Published-track error bands of the frozen LPBF melt-pool screening kernels (``npm run lpbf:bands``).

REPORTING ONLY; SCREENING ONLY; NOT VALIDATION. Every published single track the repo ingests is run through the
public entry point ``lpbf_thermal_solver.calculate_meltpool_physics(heat_source=<kernel>,
absorption_model="flat-plate")`` at the material default absorptivity (read-only, no override), and the relative
depth / width error is summarised per kernel x alloy family x screening regime class with equal source weight and a
leave-one-source-out (LOSO) coverage check (statistics and eligibility in ``python/lpbf_error_bands.py``,
pre-declared in PREDECLARED_depth_bands_machinecal.md section A). No physics is added or changed.

Outputs (written together, byte-deterministic for one row table):
  data/calibration/lpbf-meltpool-error-bands-v1.json          full artefact (hashed; LOSO bands per held-out source)
  data/calibration/lpbf-meltpool-error-bands-v1.summary.json  what the frontend imports
  data/calibration/lpbf-meltpool-error-bands-v1.rows.json     the solved row table the cells are computed from, so
                                                              --check needs no solver run (hashed in the artefact)

Usage (from the repo root; PYTHONDONTWRITEBYTECODE=1):
    python -B python/tools/lpbf_error_bands.py --date 2026-10-07 [--jobs 1]   # solve every row, then write
    python -B python/tools/lpbf_error_bands.py --check                        # recompute from the row table; fail on drift
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import io
import json
import multiprocessing
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PYTHON_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PYTHON_DIR.parent
sys.path.insert(0, str(PYTHON_DIR))

import lpbf_error_bands as eb  # noqa: E402

TOOL_REL_PATH = "python/tools/lpbf_error_bands.py"
NIST_TABLE_REL = "data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json"
DEFAULT_LAYER_UM = 30.0
DEFAULT_HATCH_UM = 100.0

WHAT_THIS_DOES_NOT_SHOW = [
    "The bands describe the model's error on these published sources only. They are not a tolerance, not a "
    "prediction interval for any other machine and not experimental validation.",
    "The leave-one-source-out coverage shows the bands do not transfer between sources: the between-source offset "
    "is as large as the band half-width and its sign depends on the regime class in a source-dependent way.",
    "No source reports per-row measurement uncertainty; there are at most three sources per alloy family, Trapp and "
    "Ghosh rest on digitized or transcribed figures, NIST AMB2022-03 IN718 is a development sentinel (used while the "
    "physics was developed, so not blind), KU Leuven's beam diameter is an unverified 37.5 um, and there is no "
    "AlSi10Mg data.",
    "Vapour-depression depths (keyhole benchmark) measure a different quantity and are never pooled into depth bands.",
]


# ---------------------------------------------------------------------------------------------
# rows and solver
# ---------------------------------------------------------------------------------------------
def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_input_rows() -> Dict[str, Any]:
    """{'rows': [...], 'provenance': {source: {...}}} from the pinned loaders (no solver)."""
    import lpbf_literature_datasets as ld
    import lpbf_public_datasets as pd

    rows: List[Dict[str, Any]] = []
    prov: Dict[str, Dict[str, Any]] = {}
    h = pd.load_hofmann_316l()
    t = pd.load_totis_ti64()
    ku = pd.load_ku_leuven_316l_ti64()
    lane = pd.load_lane_in625()
    ghosh = ld.load_ghosh_in625()
    trapp = ld.load_trapp_316l_tracks()
    for src in (h, t, ku, lane, ghosh, trapp):
        rows += src["rows"]
    for sid, d in (("hofmann-316l-2026", h), ("totis-ti64-2021", t), ("lane-in625-2020", lane),
                   ("ghosh-in625-2018", ghosh), ("trapp-316l-2017", trapp)):
        p = d["provenance"]
        prov[sid] = {"doi": p["doi"], "tableSha256": p["fileSha256"]}
    for sid, alloy in (("ku-leuven-316l-2021", "316L"), ("ku-leuven-ti64-2021", "Ti-6Al-4V")):
        files = [f for f in ku["provenance"]["sourceFiles"] if f["alloy"] == alloy]
        prov[sid] = {"doi": " + ".join(f["doi"] for f in files), "tableSha256": ku["provenance"]["fileSha256"]}
    nist_path = REPO_ROOT / NIST_TABLE_REL
    nist = json.loads(nist_path.read_text(encoding="utf-8"))
    for c in nist["cases"]:
        rows.append({"dataset": "nist-amb2022-03", "rowId": f"nist-{c['caseNumber']}", "material": "Inconel 718",
                     "power_W": float(c["laserPower_W"]), "speed_mm_s": float(c["scanSpeed_mm_s"]),
                     "beamDiameter_um": float(c["beamDiameterD4sigma_um"]), "layer_um": 0.0,
                     "preheat_C": float(nist["experiment"]["substrateAndChamberTemperature_C"]),
                     "width_um": float(c["widthMean_um"]), "depth_um": float(c["depthMean_um"]),
                     "balling": None, "hatch_um": None})
    prov["nist-amb2022-03"] = {"doi": nist["doi"], "tableSha256": _file_sha256(nist_path)}
    return {"rows": rows, "provenance": prov}


def solve_one(task: Dict[str, Any]) -> Dict[str, Any]:
    """One frozen-kernel call at the material default absorptivity (flat-plate), exactly as the app serves it."""
    from lpbf_thermal_solver import calculate_meltpool_physics
    row, kernel = task["row"], task["kernel"]
    layer = row["layer_um"] if row.get("layer_um") else DEFAULT_LAYER_UM
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            res = calculate_meltpool_physics(row["material"], row["power_W"], row["speed_mm_s"],
                                             row["beamDiameter_um"], row["preheat_C"], layer, DEFAULT_HATCH_UM,
                                             heat_source=kernel, prop_overrides=None, absorption_model="flat-plate")
        g = res["meltPoolGeometry"]
        return {"W": g["width_um"], "D": g["depth_um"], "status": g["extentStatus"],
                "enthalpy": res["processParameters"]["normalizedEnthalpy"]}
    except Exception as exc:  # recorded, never silently dropped: the row is excluded and counted
        return {"W": None, "D": None, "status": f"error: {exc}"[:120], "enthalpy": None}


def solve_rows(inputs: List[Dict[str, Any]], solver: Callable[[Dict[str, Any]], Dict[str, Any]] = solve_one,
               jobs: int = 1) -> List[Dict[str, Any]]:
    tasks = [{"row": r, "kernel": k} for r in inputs for k in eb.KERNELS]
    if jobs > 1 and solver is solve_one:
        with multiprocessing.get_context("spawn").Pool(jobs) as pool:
            results = pool.map(solve_one, tasks, chunksize=16)
    else:
        results = [solver(t) for t in tasks]
    out: List[Dict[str, Any]] = []
    i = 0
    for r in inputs:
        pred: Dict[str, Any] = {}
        enthalpy = None
        for k in eb.KERNELS:
            res = results[i]
            i += 1
            pred[k] = {"W": res["W"], "D": res["D"], "status": res["status"]}
            if enthalpy is None and res.get("enthalpy") is not None:
                enthalpy = res["enthalpy"]
        out.append({"source": r["dataset"], "rowId": r["rowId"], "material": r["material"],
                    "power_W": r["power_W"], "speed_mm_s": r["speed_mm_s"], "beamDiameter_um": r["beamDiameter_um"],
                    "preheat_C": r["preheat_C"], "layer_um": r.get("layer_um"), "width_um": r.get("width_um"),
                    "depth_um": r.get("depth_um"), "balling": r.get("balling"), "enthalpy": enthalpy, "pred": pred})
    return eb.round_sig(out)


# ---------------------------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------------------------
def _git(args: List[str]) -> Optional[str]:
    try:
        res = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(PYTHON_DIR), timeout=30)
        return res.stdout.strip() if res.returncode == 0 else None
    except Exception:
        return None


def code_revision() -> Dict[str, Any]:
    status = _git(["status", "--porcelain", "-uno", "--", "python", "data/calibration"])
    return {"gitHead": _git(["rev-parse", "HEAD"]), "gitBranch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "dirtyTrackedPaths": None if status is None else len([ln for ln in status.splitlines() if ln.strip()]),
            "python": platform.python_version()}


def tool_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rows_document(rows: List[Dict[str, Any]], impl_hash: str) -> Dict[str, Any]:
    return {"schema": eb.ROWS_SCHEMA, "implementationHash": impl_hash,
            "note": "solved published tracks (frozen kernels at the material default absorptivity) the error-band "
                    "cells are computed from; written only by python/tools/lpbf_error_bands.py",
            "rows": rows}


def rows_sha256(doc: Dict[str, Any]) -> str:
    return eb.canonical_sha256({"schema": doc["schema"], "implementationHash": doc["implementationHash"],
                                "rows": doc["rows"]})


def sources_info(rows: List[Dict[str, Any]], prov: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    cfg = eb.BANDS_CONFIG
    out = []
    for sid in sorted({r["source"] for r in rows}):
        rr = [r for r in rows if r["source"] == sid]
        out.append({"source": sid, "name": cfg["sourceNames"].get(sid, sid),
                    "materials": sorted({r["material"] for r in rr}), "doi": prov.get(sid, {}).get("doi"),
                    "role": cfg["sourceRoles"].get(sid), "digitized": sid in cfg["digitizedSources"],
                    "sentinel": sid in cfg["sentinelSources"], "rows": len(rr),
                    "sets": len({(r["power_W"], r["speed_mm_s"], r["beamDiameter_um"]) for r in rr}),
                    "tableSha256": prov.get(sid, {}).get("tableSha256")})
    return out


def build_artefact(rows: List[Dict[str, Any]], prov: Dict[str, Dict[str, Any]], *, impl_hash: str, date: str,
                   revision: Optional[Dict[str, Any]] = None, tool_hash: Optional[str] = None) -> Dict[str, Any]:
    rdoc = rows_document(rows, impl_hash)
    res = eb.build_cells(rows)
    art: Dict[str, Any] = {
        "schema": eb.BANDS_SCHEMA, "bandsId": "", "generatedAt": date, "implementationHash": impl_hash,
        "codeRevision": revision or code_revision(), "toolSha256": tool_hash or tool_sha256(),
        "configSha256": eb.config_sha256(), "config": eb.BANDS_CONFIG, "sources": sources_info(rows, prov),
        "rowsSha256": rows_sha256(rdoc), "rowCount": len(rows), "excluded": res["excluded"], "cells": res["cells"],
        "evidenceKind": eb.EVIDENCE_KIND, "evidenceLabel": eb.EVIDENCE_LABEL, "experimentalValidation": False,
        "labelPromotionProposed": "none", "honesty": eb.HONESTY, "whatThisDoesNotShow": WHAT_THIS_DOES_NOT_SHOW,
        "contentSha256": ""}
    sha = eb.artefact_content_sha256(art)
    art["contentSha256"] = sha
    art["bandsId"] = f"lpbf-meltpool-error-bands-{date}-{sha[:12]}"
    return art


def dump_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False) + "\n"


def dump_rows(doc: Dict[str, Any]) -> str:
    """One row per line so the committed table stays reviewable; still canonical (sorted keys)."""
    head = {k: v for k, v in doc.items() if k != "rows"}
    lines = [json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
             for r in doc["rows"]]
    head_json = json.dumps(head, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False)
    return head_json[:-2] + ',\n "rows": [\n' + ",\n".join(lines) + "\n ]\n}\n"


def render_outputs(art: Dict[str, Any], rdoc: Dict[str, Any]) -> Dict[str, str]:
    return {eb.ARTEFACT_REL_PATH: dump_json(art), eb.SUMMARY_REL_PATH: dump_json(eb.summary_of(art)),
            eb.ROWS_REL_PATH: dump_rows(rdoc)}


def write_outputs(repo_root: Path, outputs: Dict[str, str]) -> None:
    for rel, body in outputs.items():
        p = repo_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)


def check_outputs(repo_root: Path, *, expected_impl_hash: Optional[str] = None) -> List[str]:
    """Problems found when recomputing everything from the committed row table (empty list = clean)."""
    problems: List[str] = []
    try:
        art = json.loads((repo_root / eb.ARTEFACT_REL_PATH).read_text(encoding="utf-8"))
        rdoc = json.loads((repo_root / eb.ROWS_REL_PATH).read_text(encoding="utf-8"))
        summary = json.loads((repo_root / eb.SUMMARY_REL_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read the committed outputs: {exc}"]
    if rows_sha256(rdoc) != art.get("rowsSha256"):
        problems.append("rowsSha256 does not match the row table")
    if rdoc.get("implementationHash") != art.get("implementationHash"):
        problems.append("row table and artefact carry different implementation hashes")
    try:
        eb.load_bands(repo_root / eb.ARTEFACT_REL_PATH, expected_impl_hash=expected_impl_hash or art.get("implementationHash"))
    except eb.BandsError as exc:
        problems.append(f"artefact does not load: {exc}")
    if expected_impl_hash is not None and art.get("implementationHash") != expected_impl_hash:
        problems.append("artefact implementationHash differs from the live fingerprint (regenerate after a physics bump)")
    res = eb.build_cells(rdoc["rows"])
    if res["cells"] != art.get("cells"):
        problems.append("cells differ from the cells recomputed from the row table")
    if res["excluded"] != art.get("excluded"):
        problems.append("excluded counts differ from the recomputed ones")
    if eb.config_sha256() != art.get("configSha256"):
        problems.append("BANDS_CONFIG differs from the artefact's config")
    if summary != eb.summary_of(art):
        problems.append("summary file differs from summary_of(artefact)")
    for rel, body in ((eb.ARTEFACT_REL_PATH, dump_json(art)), (eb.SUMMARY_REL_PATH, dump_json(summary)),
                      (eb.ROWS_REL_PATH, dump_rows(rdoc))):
        if (repo_root / rel).read_bytes().replace(b"\r\n", b"\n") != body.encode("utf-8"):
            problems.append(f"{rel} is not in the tool's canonical byte form")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="record date (default: today for a fresh run)")
    ap.add_argument("--jobs", type=int, default=1, help="solver worker processes (default 1)")
    ap.add_argument("--check", action="store_true", help="recompute from the committed row table and fail on drift")
    ap.add_argument("--from-rows", action="store_true",
                    help="re-derive the artefact and summary from the committed row table without a solver run "
                         "(for a statistics or wording change only; refuses when the row table is not at the live fingerprint)")
    args = ap.parse_args(argv)
    if args.check:
        from lpbf_simulation import implementation_fingerprint
        problems = check_outputs(REPO_ROOT, expected_impl_hash=implementation_fingerprint())
        if problems:
            print("error-band check FAILED:\n  " + "\n  ".join(problems), file=sys.stderr)
            return 1
        print("error-band check OK (row table, cells, summary and byte form reproduce; artefact matches the live fingerprint)")
        return 0
    from lpbf_simulation import implementation_fingerprint
    if args.from_rows:
        rdoc = json.loads((REPO_ROOT / eb.ROWS_REL_PATH).read_text(encoding="utf-8"))
        fp = implementation_fingerprint()
        if rdoc.get("implementationHash") != fp:
            print("the committed row table was solved at a different fingerprint; run the full tool", file=sys.stderr)
            return 1
        old = json.loads((REPO_ROOT / eb.ARTEFACT_REL_PATH).read_text(encoding="utf-8"))
        prov = {s["source"]: {"doi": s["doi"], "tableSha256": s["tableSha256"]} for s in old["sources"]}
        art = build_artefact(rdoc["rows"], prov, impl_hash=fp, date=args.date or old["generatedAt"])
        write_outputs(REPO_ROOT, render_outputs(art, rdoc))
        print(f"re-derived {eb.ARTEFACT_REL_PATH} ({art['bandsId']}) from the committed row table; cells {len(art['cells'])}")
        return 0
    date = args.date or datetime.date.today().isoformat()
    t0 = time.time()
    loaded = load_input_rows()
    print(f"rows {len(loaded['rows'])}; solving {len(loaded['rows']) * len(eb.KERNELS)} kernel calls "
          f"(jobs={args.jobs}) ...", flush=True)
    fp_before = implementation_fingerprint()
    rows = solve_rows(loaded["rows"], jobs=args.jobs)
    fp = implementation_fingerprint()
    if fp != fp_before:
        print("the implementation fingerprint moved during the run; refusing to write", file=sys.stderr)
        return 1
    art = build_artefact(rows, loaded["provenance"], impl_hash=fp, date=date)
    write_outputs(REPO_ROOT, render_outputs(art, rows_document(rows, fp)))
    print(f"wrote {eb.ARTEFACT_REL_PATH} ({art['bandsId']}) in {time.time() - t0:.0f} s; cells {len(art['cells'])}, "
          f"excluded {art['excluded']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
