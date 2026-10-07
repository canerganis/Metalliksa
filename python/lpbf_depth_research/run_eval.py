#!/usr/bin/env python3
"""Pre-declared evaluation harness (docs/research/PREDECLARED_fv_evap.md).

usage: python -B lpbf_depth_research/run_eval.py <depth_tdep_results.json> <out.json> [workers=4] [--dry]

Subset: 3 rows per source x layer x band stratum (first, middle, last by rowId) of the non-balling rows,
plus 3 Cunningham vapour-depth rows per spot. Arms at 20 um: evap-sf, evap-v40, ref-sf, ref-v40.
Mesh: evap-sf at 10 um on the convergence subset; 5 um on 3 shallow cases at the first track length
(600 -> 400 -> 300 -> 200 um) whose cell count is <= 1.2e6, with 20 and 10 um repeated at that track length.
Results are checkpointed to <out.json> after every finished case. Wall time is recorded, never enforced."""
from __future__ import annotations

import json
import multiprocessing
import os
import sys
import time
from pathlib import Path

_PY = Path(__file__).resolve().parent.parent
if str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

ARMS = {"evap-sf": dict(evaporation=True, source_mode="surface-flux", boiling_stop=False),
        "evap-v40": dict(evaporation=True, source_mode="volumetric", boiling_stop=False),
        "ref-sf": dict(evaporation=False, source_mode="surface-flux", boiling_stop=True),
        "ref-v40": dict(evaporation=False, source_mode="volumetric", boiling_stop=True)}
BANDS = ("cond<15", "15-20", "20-30", ">=30")
PER_STRATUM = 3
CELL_LIMIT = 1_200_000
TRACK_SEQUENCE = (600.0, 400.0, 300.0, 200.0)
CONVERGENCE_STRATA = [("hofmann-316l-2026", 0.0, b) for b in BANDS] + [
    ("hofmann-316l-2026", 30.0, "cond<15"), ("hofmann-316l-2026", 30.0, ">=30"),
    ("totis-ti64-2021", 25.0, "cond<15"), ("totis-ti64-2021", 25.0, ">=30"),
    ("lane-in625-2020", 0.0, "cond<15"), ("nist-amb2022-03", 0.0, ">=30"),
    ("trapp-316l-2017", 0.0, "cond<15"), ("ku-leuven-316l-2021", 60.0, ">=30")]
FINE_STRATA = [("hofmann-316l-2026", 0.0, "cond<15"), ("totis-ti64-2021", 25.0, "cond<15"),
               ("trapp-316l-2017", 0.0, "cond<15")]


def band(dh):
    return "cond<15" if dh < 15 else "15-20" if dh < 20 else "20-30" if dh < 30 else ">=30"


def pick(rows):
    rows = sorted(rows, key=lambda r: r["rowId"])
    n = len(rows)
    if n <= PER_STRATUM:
        return rows
    idx = sorted({0, (n - 1) // 2, n - 1})
    return [rows[i] for i in idx]


def build_rows(base):
    strata = {}
    for r in base["rows"]:
        if r.get("balling") == 1 or r.get("dH") is None:
            continue
        layer = r.get("layer_um") or 0.0
        if r["dataset"].startswith("ku-leuven"):
            layer = 60.0
        strata.setdefault((r["dataset"], layer, band(r["dH"])), []).append(r)
    out = []
    for key in sorted(strata):
        for r in pick(strata[key]):
            out.append(dict(rowId=r["rowId"], dataset=r["dataset"], material=r["material"], power_W=r["power_W"],
                            speed_mm_s=r["speed_mm_s"], beamDiameter_um=r["beamDiameter_um"], preheat_C=r["preheat_C"],
                            width_um=r["width_um"], depth_um=r["depth_um"], vapor_um=None, t_um=key[1], band=key[2],
                            dH=r["dH"], stratum=list(key),
                            kernels={k: r["pred"].get(f"{k}|C0") for k in ("eagar-tsai", "goldak", "rosenthal")}))
    cun = {}
    for r in base.get("cunningham", []):
        cun.setdefault(r["dataset"], []).append(r)
    for ds in sorted(cun):
        for r in pick(cun[ds]):
            out.append(dict(rowId=r["rowId"], dataset=ds, material=r["material"], power_W=r["power_W"],
                            speed_mm_s=r["speed_mm_s"], beamDiameter_um=r["beamDiameter_um"], preheat_C=r["preheat_C"],
                            width_um=None, depth_um=None, vapor_um=r["vapor_um"], t_um=0.0, band=band(r["dH"]),
                            dH=r["dH"], stratum=[ds, 0.0, band(r["dH"])], kernels={}, fabbro=r.get("fabbro")))
    return out


def cells_for(row, mesh_um, track_um):
    from lpbf_depth_research.fv_evap import frozen_input
    from lpbf_simulation import validate
    from lpbf_core_physics import calculate_mesh_domain
    p, _ = validate(frozen_input(row, mesh_um=mesh_um, track_um=track_um))
    d = calculate_mesh_domain(p)
    return d["nx"] * d["ny"] * d["nz"], d["dx"] * 1e6


def build_tasks(rows):
    """Ordered task list: (taskId, rowIndex, arm, mesh_um, track_um, purpose)."""
    tasks = []
    first = {}
    for i, r in enumerate(rows):
        key = tuple(r["stratum"])
        if key not in first:
            first[key] = i
    for i, r in enumerate(rows):
        tasks.append((i, "evap-sf", 20.0, 600.0, "main"))
    for key in CONVERGENCE_STRATA:
        if key in first:
            tasks.append((first[key], "evap-sf", 10.0, 600.0, "mesh10"))
    fine = []
    for key in FINE_STRATA:
        if key not in first:
            continue
        i = first[key]
        chosen = None
        for track in TRACK_SEQUENCE:
            n, _ = cells_for(rows[i], 5.0, track)
            if n <= CELL_LIMIT:
                chosen = track
                break
        fine.append((i, chosen))
        if chosen is not None:
            tasks.append((i, "evap-sf", 5.0, chosen, "mesh5"))
            if chosen != 600.0:
                tasks.append((i, "evap-sf", 20.0, chosen, "mesh5-repeat20"))
                tasks.append((i, "evap-sf", 10.0, chosen, "mesh5-repeat10"))
    for arm in ("evap-v40", "ref-sf", "ref-v40"):
        for i, r in enumerate(rows):
            tasks.append((i, arm, 20.0, 600.0, "main"))
    return [(n, *t) for n, t in enumerate(tasks)], fine


def worker(args):
    task_id, row, arm, mesh_um, track_um, purpose = args
    import contextlib
    import io
    from lpbf_depth_research.fv_evap import run_case, frozen_input
    kw = ARMS[arm]
    t0 = time.perf_counter()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            res = run_case(frozen_input(row, mesh_um=mesh_um, track_um=track_um), cell_limit=CELL_LIMIT, **kw)
    except Exception as exc:  # recorded, never hidden
        msg = str(exc)
        res = dict(status="boiling-stop" if "boiling" in msg.lower() else "error", message=msg[:300],
                   wall_s=time.perf_counter() - t0)
    res.update(taskId=task_id, rowId=row["rowId"], arm=arm, mesh_um=mesh_um, track_um=track_um, purpose=purpose)
    return res


def main():
    base_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 4
    dry = "--dry" in sys.argv
    base = json.loads(base_path.read_text("utf-8"))
    rows = build_rows(base)
    tasks, fine = build_tasks(rows)
    print(f"rows {len(rows)} tasks {len(tasks)} fine {fine}", flush=True)
    if dry:
        for t in tasks[:5] + tasks[-3:]:
            print(t)
        from collections import Counter
        print(Counter((t[2], t[3], t[5]) for t in tasks))
        return
    out = dict(predeclared="docs/research/PREDECLARED_fv_evap.md", arms=ARMS, perStratum=PER_STRATUM,
               cellLimit=CELL_LIMIT, fineTracks=fine, rows=rows, results=[], startedAt=time.strftime("%Y-%m-%dT%H:%M:%S"))
    done = {}
    if out_path.exists():  # resume: keep finished tasks
        prev = json.loads(out_path.read_text("utf-8"))
        if prev.get("rows") == rows:
            done = {r["taskId"]: r for r in prev["results"]}
            out["results"] = list(done.values())
            print(f"resuming, {len(done)} finished tasks kept", flush=True)
    todo = [(t[0], rows[t[1]], t[2], t[3], t[4], t[5]) for t in tasks if t[0] not in done]
    ctx = multiprocessing.get_context("spawn")
    t0 = time.perf_counter()
    with ctx.Pool(workers) as pool:
        for n, res in enumerate(pool.imap_unordered(worker, todo, chunksize=1)):
            out["results"].append(res)
            out_path.write_text(json.dumps(out), encoding="utf-8")
            print(f"  [{n + 1}/{len(todo)} {time.perf_counter() - t0:.0f}s] {res['rowId']} {res['arm']} {res['mesh_um']:g}um "
                  f"{res['purpose']}: {res['status']} {res.get('wall_s', 0):.0f}s "
                  + (f"envMid W {res['operators']['envMid']['width_um']:.0f} D {res['operators']['envMid']['depthPlate_um']:.0f} "
                     f"Tsurf {res['maxSurfaceTemperature_K']:.0f} evap {res['energy']['evaporatedFraction']:.2f} "
                     f"res {res['energy']['relativeResidual']:.1e}" if res["status"] == "completed" else res.get("message", "")[:90]),
                  flush=True)
    out["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    out_path.write_text(json.dumps(out), encoding="utf-8")
    print("done", flush=True)


if __name__ == "__main__":
    main()
