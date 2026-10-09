#!/usr/bin/env python3
"""LPBF machine depth calibration CLI: ``fit`` the user's tracks, ``check`` an artefact, print the ``eligibility`` list.

SCREENING ONLY, NOT VALIDATION. Scope: only Rosenthal depth for 316L Stainless Steel is eligible. The fitted quantity is
an empirical machine offset (a plain depth factor), never an absorptivity or a physical quantity. The artefact stays on
this computer; nothing here changes the global calibration, the scorecard or the frozen physics.

  python -B python/tools/lpbf_machine_calibration.py fit --user-source .runtime/user-calibration/user-my-run/rows.json \
      --out-dir .runtime/machine-calibration/user-my-run
  python -B python/tools/lpbf_machine_calibration.py check --artefact <out-dir>/machine-calibration.json \
      --user-source .runtime/user-calibration/user-my-run/rows.json
  python -B python/tools/lpbf_machine_calibration.py eligibility

``fit`` runs the frozen Rosenthal kernel at the material default absorptivity on each of your tracks (a few dozen
milliseconds each) and writes ``machine-calibration.json`` and ``report.md`` into ``--out-dir``. ``check`` re-fits from
your rows and fails unless the artefact reproduces byte for byte (same content hash).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PYTHON_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PYTHON_DIR.parent
sys.path.insert(0, str(PYTHON_DIR))

import lpbf_machine_calibration as mc  # noqa: E402
import lpbf_machine_calibration_config as mcfg  # noqa: E402
import lpbf_user_measurements as um  # noqa: E402

ARTEFACT_NAME = "machine-calibration.json"
REPORT_NAME = "report.md"
PRIVACY = ("Your measurements stay on this computer (.runtime/machine-calibration/), are not sent anywhere, do not "
           "change the published-track calibration or the scorecard, and do not become validation evidence.")


def refuse_record_dir(out_dir: Path, root: Path = REPO_ROOT) -> None:
    """Never write into a committed record location (docs/, data/calibration/) or the repo root itself."""
    o = out_dir.resolve()
    r = root.resolve()
    for forbidden in (r, r / "docs", r / "data" / "calibration"):
        if o == forbidden or (forbidden != r and forbidden in o.parents):
            raise SystemExit(f"--out-dir {out_dir} is a committed record location; pick a scratch directory "
                             "(for example under .runtime/machine-calibration/)")


def _git_head() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(PYTHON_DIR), timeout=30)
        return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def tool_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _fmt_band(cell: Dict[str, Any]) -> str:
    b = cell.get("band")
    if not b:
        return "n/a"
    lo, hi = b["factors"]
    return f"x{lo:.2f} to x{hi:.2f}" + ("" if b["informative"] else " (not informative)")


def render_report(art: Dict[str, Any]) -> str:
    """Plain-text report of the artefact; English; no claim beyond screening."""
    L: List[str] = ["# Machine depth calibration (user data)", "",
                    f"Artefact {art['machineCalibrationId']} for source {art['userSourceId']}, material {art['material']}.",
                    f"Tracks: {art['nTracks']} ({art['nResolved']} resolved). Regime classes: "
                    + ", ".join(f"{k} {v}" for k, v in art["regimeClasses"].items()) + ".",
                    f"Nuisance: {art['nuisance']['name']} ({art['nuisance']['form']}). {art['nuisance']['note']}.", ""]
    miss = art["methodFields"]["missing"]
    if miss:
        L.append("Method fields missing (a served cell stays screening-only until every track has all five):")
        for m in miss:
            L.append(f"- {', '.join(m['trackIds'])}: {', '.join(m['fields'])}")
        L.append("")
    for c in art["cells"]:
        head = f"## {c['kernel']} {c['quantity']}: {c['status']}"
        L += [head, f"Evidence: {c['evidenceKind']}" + (f" ({c['evidenceScope']})" if c["evidenceScope"] else ""),
              c["evidenceLabel"]]
        for t in c["reasonText"] or []:
            L.append(f"- {t}")
        if c["status"] != "not-eligible" and c["factor"] is not None:
            g = c["gate"]
            L.append(f"Machine factor f = {c['factor']:.3f} (90 % bootstrap {c['factorCi90'][0]:.3f} to "
                     f"{c['factorCi90'][1]:.3f}); mean |ln residual| {c['lossDefault']:.3f} default, {c['lossCal']:.3f} "
                     "calibrated.")
            L.append(f"Gate: {g['nOver']} over, {g['nUnder']} under, mean ln residual {g['meanLnResidualDefault']:+.3f}, "
                     f"LOO skill {g['looSkill'] if g['looSkill'] is None else format(g['looSkill'], '.3f')}.")
            L.append(f"80 % band: {_fmt_band(c)}. {art and mcfg.MACHINE_CALIBRATION_CONFIG['band']['statement']}.")
        L.append("")
    L += [art["honesty"] + ".", PRIVACY, "Screening only: not validation.", ""]
    return "\n".join(L)


def cmd_fit(a: argparse.Namespace, solver_call: Optional[mc.SolverCall]) -> int:
    out = Path(a.out_dir)
    refuse_record_dir(out)
    doc = um.load_user_rows(a.user_source)
    art = mc.build_artefact(doc, solver_call=solver_call, code_revision=_git_head(), tool_sha256=tool_sha256())
    out.mkdir(parents=True, exist_ok=True)
    path = mc.write_artefact(art, out / ARTEFACT_NAME)
    (out / REPORT_NAME).write_text(render_report(art), encoding="utf-8", newline="\n")
    print(f"wrote {path} and {out / REPORT_NAME}", file=sys.stderr)
    for c in art["cells"]:
        if c["kernel"] == mcfg.CELL_DESIGN_KERNEL and c["quantity"] == "depth":
            print(f"rosenthal depth: {c['status']} ({c['evidenceKind']})", file=sys.stderr)
            for t in c["reasonText"] or []:
                print(f"  {t}", file=sys.stderr)
    return 0


def cmd_check(a: argparse.Namespace, solver_call: Optional[mc.SolverCall]) -> int:
    """Re-fit from the user rows with the artefact's own timestamp, revision and fingerprint; the content hash must match."""
    art = mc.load_machine_calibration(a.artefact)  # hash, config, evidence and fingerprint checks (stale refuses)
    doc = um.load_user_rows(a.user_source)
    if art["userRowsSha256"] != mc.st.canonical_sha256(doc):
        print("check FAILED: the user rows differ from the ones the artefact was fitted on (userRowsSha256)",
              file=sys.stderr)
        return 1
    again = mc.build_artefact(doc, solver_call=solver_call, implementation_hash=art["implementationHash"],
                              code_revision=art["codeRevision"], tool_sha256=art["toolSha256"],
                              generated_at=art["generatedAt"])
    if again["contentSha256"] != art["contentSha256"]:
        diff = [c["kernel"] + "|" + c["quantity"] for c, d in zip(art["cells"], again["cells"]) if c != d]
        print(f"check FAILED: re-fit differs from the artefact (cells: {', '.join(diff) or 'header only'})",
              file=sys.stderr)
        return 1
    note = "" if art["toolSha256"] == tool_sha256() else " (the CLI file changed since the fit; numbers reproduce)"
    print(f"check OK: {art['machineCalibrationId']} reproduces{note}", file=sys.stderr)
    return 0


def cmd_eligibility(_a: argparse.Namespace, _s: Optional[mc.SolverCall]) -> int:
    cfg = mcfg.MACHINE_CALIBRATION_CONFIG
    print("Eligible cells (committed list in MACHINE_CALIBRATION_CONFIG; a maintainer decision, not computed from "
          "your data):")
    for e in cfg["eligibleCells"]:
        print(f"  {e['kernel']} | {e['material']} | {e['quantity']}")
    print("Every other cell is reported as not-eligible with a reason:")
    for k, v in cfg["notEligibleReasons"].items():
        print(f"  {k}: {v}")
    print(f"config sha256: {mcfg.config_sha256()}")
    return 0


def main(argv: Optional[List[str]] = None, solver_call: Optional[mc.SolverCall] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit", help="fit the machine depth factor on your tracks and write the artefact")
    f.add_argument("--user-source", required=True, help="rows.json written by lpbf_next_experiment.py import")
    f.add_argument("--out-dir", required=True, help="scratch directory, for example .runtime/machine-calibration/<id>")
    c = sub.add_parser("check", help="re-fit from your rows and require the artefact to reproduce")
    c.add_argument("--artefact", required=True)
    c.add_argument("--user-source", required=True)
    sub.add_parser("eligibility", help="print the committed eligibility list")
    a = ap.parse_args(argv)
    handler: Dict[str, Callable] = {"fit": cmd_fit, "check": cmd_check, "eligibility": cmd_eligibility}[a.cmd]
    try:
        return handler(a, solver_call)
    except (mc.MachineCalibrationError, um.UserMeasurementError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
