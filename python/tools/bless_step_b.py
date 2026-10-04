#!/usr/bin/env python3
"""
Phase 6a value step (b): re-bless one solver's golden expectations and print the drift.

Design step (b) changes solver outputs on purpose (exact SI R/F, CIAAW atomic weights,
registry-computed equivalent weights). The d33b6f5 goldens stay untouched as the
pre-migration record; this tool writes the new expectation for every case of ONE
solver into ``python/golden/phase6a/<solver>/step_b/<case>.json``:

- the case is run from the working tree exactly like the regression test does
  (capture_phase6a_golden.run_solver with the CASES payload);
- cases that now give the validation envelope (exit 2) are skipped: they belong in
  EXPECTED_BEHAVIOUR_CHANGES, not in a re-blessed golden;
- a case whose stdout equals the d33b6f5 golden gets no step_b file (a stale one
  is removed);
- otherwise the file records the stdout, the exit code, the provenance block, the
  working-tree solver sha256 (CRLF->LF), git HEAD and ``driftVsBase``: the full
  drift_report.diff rows (old, new, abs, rel) against the d33b6f5 golden.

The printed Markdown table is the drift of THIS re-bless against the previous
expectation (step_b file if one existed, else the d33b6f5 golden). It goes into the
commit body (design section 3: golden files are re-blessed only with the report).

Usage (from python/):
    python -B tools/bless_step_b.py --solver tafel_corrosion_rate_solver [--dry-run]
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_phase6a_golden as golden  # noqa: E402
import drift_report  # noqa: E402


def _is_validation_envelope(result: Dict[str, Any]) -> bool:
    out = result["stdout"]
    return result["exitCode"] == 2 and isinstance(out, dict) and out.get("errorKind") == "validation"


def bless(solver: str, dry_run: bool = False) -> Tuple[List[Tuple[str, List[Dict[str, Any]]]], List[str]]:
    """Re-bless every case of ``solver``; return (per-case drift vs previous expectation, log lines)."""
    drift: List[Tuple[str, List[Dict[str, Any]]]] = []
    log: List[str] = []
    source = golden.solver_bytes(solver)
    for case, payload in golden.CASES[solver].items():
        base = golden.load_golden(solver, case)
        previous = golden.load_expected(solver, case)
        fresh = golden.run_solver(solver, payload)
        path = golden.step_b_path(solver, case)
        if _is_validation_envelope(fresh):
            log.append(f"skip {solver}/{case}: validation envelope "
                       f"{fresh['stdout']['error']['code']} (EXPECTED_BEHAVIOUR_CHANGES)")
            continue
        if fresh["exitCode"] != base["exitCode"]:
            raise SystemExit(f"{solver}/{case}: exit code {base['exitCode']} -> {fresh['exitCode']}; "
                             f"not a value drift, refusing to bless.\n{fresh['stderr']}")
        drift.append((f"{solver}/{case}", drift_report.diff(previous["stdout"], fresh["stdout"])))
        vs_base = drift_report.diff(base["stdout"], fresh["stdout"])
        if not vs_base:
            if path.exists() and not dry_run:
                path.unlink()
                log.append(f"removed {path.name}: output equals the {golden.BASE_REVISION} golden again")
            else:
                log.append(f"keep {solver}/{case}: equals the {golden.BASE_REVISION} golden (no step_b file)")
            continue
        doc = {
            "schema": golden.STEP_B_SCHEMA,
            "label": golden.STEP_B_LABEL,
            "solver": solver,
            "case": case,
            "supersedes": f"{case}.json ({golden.BASE_REVISION})",
            "solverFile": f"python/{solver}.py",
            "solverSha256": golden.normalised_sha256(source),
            "solverSha256Normalization": "CRLF->LF (git blob form)",
            "solverSource": "worktree",
            "gitHead": golden.git_head(),
            "invocation": f"python -B {solver}.py < input (cwd python/)",
            "volatileKeysStripped": sorted(golden.VOLATILE_KEYS),
            "input": payload,
            "exitCode": fresh["exitCode"],
            "stdout": fresh["stdout"],
            "provenance": fresh["provenance"],
            "driftVsBase": vs_base,
        }
        if not dry_run:
            golden._write(path, doc)
        log.append(f"{'would write' if dry_run else 'wrote'} {solver}/{golden.STEP_B_DIR}/{case}.json "
                   f"({len(vs_base)} key(s) differ from {golden.BASE_REVISION})")
    return drift, log


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--solver", required=True, choices=sorted(golden.CASES))
    parser.add_argument("--dry-run", action="store_true", help="print the drift, write nothing")
    args = parser.parse_args(argv)
    drift, log = bless(args.solver, args.dry_run)
    for title, rows in drift:
        print(drift_report.render(title, rows))
        # Changed strings (e.g. a generated code snippet) are shown as a line diff.
        for row in rows:
            if row["kind"] == "changed" and isinstance(row["old"], str) and isinstance(row["new"], str):
                lines = difflib.unified_diff(row["old"].splitlines(), row["new"].splitlines(),
                                             f"old {row['key']}", f"new {row['key']}", n=0, lineterm="")
                print("\n".join(["```diff", *lines, "```"]))
        print()
    for line in log:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
