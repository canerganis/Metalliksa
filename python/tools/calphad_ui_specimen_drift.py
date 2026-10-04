#!/usr/bin/env python3
"""
Phase 6a design step (b), calphad: drift of the UI specimens that contain P, S, Sn,
Pb or Be, between the pre-migration solver (git blob 7f3f803: 50.0 g/mol stand-in for
every element outside its 28-symbol table) and the working tree (CIAAW 2021 weights).

These 14 compositions (src/data/materialsDatabase.ts, sent as-is by
CALPHADMultiComponentStudio) are outside the 5-case golden set, so their drift is
not recorded in python/golden/phase6a. This tool recomputes it on demand, key by
key (old, new, abs, rel), with the same payload as
test_phase6a_t2a_migration.CalphadElementTest (500-1600 degC, 50 degC step).

Usage (from python/, needs git with revision 7f3f803):
    python -B tools/calphad_ui_specimen_drift.py            # summary + non-profile rows
    python -B tools/calphad_ui_specimen_drift.py --full     # every differing key
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import capture_phase6a_golden as golden  # noqa: E402
import drift_report  # noqa: E402

BASE = "7f3f803"


def specimen_payloads():
    import test_phase6a_t2a_migration as t2a  # the same parser and selection as the test
    return [{"name": "specimen", "elements": comp, "tMin": 500.0, "tMax": 1600.0, "tStep": 50.0}
            for comp in t2a.UI_SPECIMENS_P_S_SN_PB_BE]


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--full", action="store_true", help="print every differing key")
    args = parser.parse_args(argv)
    summary = ["| specimen elements (wt%) | exit old/new | differing keys | equilibriumProfile keys "
               "| max abs rel |", "|---|---|---|---|---|"]
    details = []
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "calphad_solver.py"
        script.write_bytes(golden.solver_bytes("calphad_solver", BASE))
        for payload in specimen_payloads():
            old = golden.run_solver("calphad_solver", payload, script=script)
            new = golden.run_solver("calphad_solver", payload)
            rows = drift_report.diff(old["stdout"], new["stdout"])
            profile = [r for r in rows if r["key"].startswith("equilibriumProfile")]
            rels = [abs(r["rel"]) for r in rows if r.get("rel") is not None]
            title = json.dumps(payload["elements"])
            summary.append(f"| {title} | {old['exitCode']}/{new['exitCode']} | {len(rows)} | {len(profile)} "
                           f"| {max(rels):.3g} |" if rels else f"| {title} | {old['exitCode']}/{new['exitCode']} "
                           f"| {len(rows)} | {len(profile)} | - |")
            shown = rows if args.full else [r for r in rows if not r["key"].startswith("equilibriumProfile")]
            details.append(drift_report.render(title, shown))
    print("\n".join(summary))
    print()
    for block in details:
        print(block)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
