"""Kernel grid for the machine-calibration simulation: the frozen kernels (eagar-tsai, goldak, rosenthal) at
absorptivity 0.20..0.90 step 0.05, flat-plate, layer 30 um, hatch 100 um, for every row of calib-proto/rows.json.
Writes calib-proto/grid.json (about 2.7 MB, not committed). Uses the python/ package of this checkout; prints the
implementation fingerprint first so the grid can be tied to it. 38 205 solver calls, about 16 min on 15 processes.

Run: <repo>/.runtime/lpbf-win-py312/Scripts/python.exe docs/research/machcal/build_grid.py
Reference: on fingerprint ec7e1f7a the output sha256 is 25e993083a20259c0552b65744c4c340703b455f96087ed8b5e080bfeac87cc8,
byte-identical to the grid first built on d92d1a3a (2026-10-07)."""
import contextlib, io, json, multiprocessing, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "python"))
KERNELS = ("eagar-tsai", "goldak", "rosenthal")
GRID = [round(0.20 + 0.05 * i, 2) for i in range(15)]


def work(task):
    sys.modules["powder_bed_raytracer"] = None
    from lpbf_thermal_solver import calculate_meltpool_physics as calc
    row, k, a = task
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            res = calc(row["material"], row["power_W"], row["speed_mm_s"], row["beamDiameter_um"], row["preheat_C"],
                       30.0, 100.0, heat_source=k, prop_overrides={"absorptivity_IR": a}, absorption_model="flat-plate")
        g = res["meltPoolGeometry"]
        return [row["rowId"], k, a, g["width_um"], g["depth_um"], g.get("extentStatus"),
                res["processParameters"]["normalizedEnthalpy"]]
    except Exception as e:
        return [row["rowId"], k, a, None, None, "error:" + type(e).__name__, None]


if __name__ == "__main__":
    from lpbf_simulation import implementation_fingerprint
    print("fingerprint", implementation_fingerprint(), flush=True)
    rows = json.load(open(HERE / "calib-proto" / "rows.json", encoding="utf-8"))
    tasks = [(r, k, a) for r in rows for k in KERNELS for a in GRID]
    print(len(rows), len(tasks), flush=True)
    t = time.time()
    with multiprocessing.get_context("spawn").Pool(15) as p:
        out = p.map(work, tasks, chunksize=16)
    json.dump(out, open(HERE / "calib-proto" / "grid.json", "w"))
    print("done", time.time() - t, flush=True)
