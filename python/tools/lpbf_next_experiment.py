#!/usr/bin/env python3
"""LPBF next-experiment kit CLI: ``plan`` proposes tracks, ``import`` reads the user's measurements back.

Screening: experiment proposal; not a print recommendation. Nothing here changes the frozen physics.

  python -B python/tools/lpbf_next_experiment.py plan --material "316L Stainless Steel" --power 100 400 \
      --speed 400 1600 --spots 70,100 --layer-um 40 --preheat-c 80 --n 12 --seed 1 \
      --plate-x-mm 120 --plate-y-mm 120 --out-dir .runtime/next-experiment/run1
  python -B python/tools/lpbf_next_experiment.py import --plan <dir>/plan.json \
      --measurements <dir>/measurement_template.csv --source-id user-my-run
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import List, Optional

PYTHON_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PYTHON_DIR.parent
sys.path.insert(0, str(PYTHON_DIR))

import lpbf_next_experiment as ne  # noqa: E402
import lpbf_user_measurements as um  # noqa: E402


def refuse_record_dir(out_dir: Path, root: Path = REPO_ROOT) -> None:
    """Never write into a committed record location (docs/, data/calibration/) or the repo root itself."""
    o = out_dir.resolve()
    r = root.resolve()
    for forbidden in (r, r / "docs", r / "data" / "calibration"):
        if o == forbidden or (forbidden != r and forbidden in o.parents):
            raise SystemExit(f"--out-dir {out_dir} is a committed record location; pick a scratch directory "
                             "(for example under .runtime/)")


def read_existing(path: str) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    need = {"power_W", "speed_mm_s", "spot_um"}
    if not rows or not need <= set(rows[0]):
        raise SystemExit(f"--existing needs a CSV with the columns {sorted(need)}")
    return [{"power_W": float(r["power_W"]), "speed_mm_s": float(r["speed_mm_s"]),
             "beamDiameter_um": float(r["spot_um"])} for r in rows]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="propose n tracks and a plate layout")
    p.add_argument("--material", required=True)
    p.add_argument("--power", nargs=2, type=float, required=True, metavar=("MIN_W", "MAX_W"))
    p.add_argument("--speed", nargs=2, type=float, required=True, metavar=("MIN_MM_S", "MAX_MM_S"))
    p.add_argument("--spots", required=True, help="comma-separated spot diameters in um")
    p.add_argument("--layer-um", type=float, required=True)
    p.add_argument("--preheat-c", type=float, required=True)
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--plate-x-mm", type=float, default=None, help="required: there is no default plate")
    p.add_argument("--plate-y-mm", type=float, default=None, help="required: there is no default plate")
    p.add_argument("--grid", type=int, default=ne.NEXT_EXPERIMENT_CONFIG["gridDefaultPerAxis"])
    p.add_argument("--existing", default=None, help="CSV (power_W, speed_mm_s, spot_um) of points already measured")
    p.add_argument("--for-machine-calibration", action="store_true",
                   help="plan for the machine depth calibration: needs n >= 6, sets plan.purpose, adds the fit "
                        "command and the five method columns to the measurement template")
    p.add_argument("--out-dir", required=True)
    i = sub.add_parser("import", help="import the filled measurement template as a user source")
    i.add_argument("--plan", required=True)
    i.add_argument("--measurements", required=True)
    i.add_argument("--source-id", required=True)
    i.add_argument("--out-root", default=None, help="default: .runtime/user-calibration")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "plan":
            out = Path(a.out_dir)
            refuse_record_dir(out)
            plate = None if a.plate_x_mm is None or a.plate_y_mm is None else {"x_mm": a.plate_x_mm, "y_mm": a.plate_y_mm}
            spec = {"material": a.material, "power_W": a.power, "speed_mm_s": a.speed,
                    "spots_um": [float(s) for s in a.spots.split(",") if s.strip()], "layer_um": a.layer_um,
                    "preheat_C": a.preheat_c, "n": a.n, "seed": a.seed, "plate": plate, "grid": a.grid,
                    "existing": read_existing(a.existing) if a.existing else [],
                    "purpose": ne.PURPOSE_MACHINE_CALIBRATION if a.for_machine_calibration else None}
            plan = ne.plan_experiment(spec)
            paths = ne.write_outputs(plan, out)
            print(f"wrote {', '.join(paths)} to {out}", file=sys.stderr)
            for w in plan.get("warnings", []):
                print(f"warning: {w}", file=sys.stderr)
            return 0
        doc = um.import_measurements(a.plan, a.measurements, a.source_id, out_root=a.out_root)
        print(f"imported {doc['nRows']} rows ({doc['nExcluded']} excluded) as {doc['sourceId']}", file=sys.stderr)
        for e in doc["excluded"]:
            print(f"  excluded {e['trackId']}: {e['reason']}", file=sys.stderr)
        return 0
    except (ne.PlanError, um.UserMeasurementError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
