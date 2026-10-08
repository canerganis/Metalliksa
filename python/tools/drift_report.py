#!/usr/bin/env python3
"""
Phase 6a drift report: per-key old / new / absolute delta / relative delta.

Compares the current golden expectation (python/golden/phase6a/<solver>/step_b/<case>.json
when a design-step-(b) re-bless exists, else <solver>/<case>.json) with a fresh run of
the current solver, or two arbitrary JSON documents. Numeric leaves
are reported with abs = new - old and rel = (new - old) / |old| (None when old is
0); non-numeric differences, missing and added keys are reported as such.

Usage (from python/):
    python -B tools/drift_report.py                       # every golden case vs current code
    python -B tools/drift_report.py --solver kinetics_ttt_cct_solver
    python -B tools/drift_report.py --old a.json --new b.json
Exit code 0 when nothing drifted, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_phase6a_golden as golden  # noqa: E402

_MISSING = object()


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def flatten(value: Any, prefix: str = "") -> Iterator[Tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            # Keep empty dicts as leaves so {} -> missing (or missing -> {}) is reported.
            yield prefix, value
        for k in sorted(value):
            yield from flatten(value[k], f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(value, list):
        if not value:
            yield prefix, value
        for i, v in enumerate(value):
            yield from flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix, value


def diff(old: Any, new: Any) -> List[Dict[str, Any]]:
    """Return one row per differing leaf (bit-exact comparison; 1 and 1.0 differ)."""
    a = dict(flatten(old))
    b = dict(flatten(new))
    rows: List[Dict[str, Any]] = []
    for key in sorted(set(a) | set(b)):
        va = a.get(key, _MISSING)
        vb = b.get(key, _MISSING)
        if va is not _MISSING and vb is not _MISSING and type(va) is type(vb) and (
                va == vb or (isinstance(va, float) and math.isnan(va) and math.isnan(vb))):
            continue
        row: Dict[str, Any] = {"key": key,
                               "old": None if va is _MISSING else va,
                               "new": None if vb is _MISSING else vb}
        if va is _MISSING:
            row["kind"] = "added"
        elif vb is _MISSING:
            row["kind"] = "removed"
        elif _is_number(va) and _is_number(vb):
            row["kind"] = "numeric"
            row["abs"] = vb - va
            row["rel"] = (vb - va) / abs(va) if va != 0 else None
        else:
            row["kind"] = "changed"
        rows.append(row)
    return rows


def _fmt(x: Any, exact: bool = False) -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        # old/new values are printed exactly (repr round-trips); deltas to 3 figures.
        return repr(x) if exact else f"{x:.3g}"
    text = json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x
    return text if len(text) <= 48 else text[:45] + "..."


def render(title: str, rows: List[Dict[str, Any]], limit: Optional[int] = None) -> str:
    lines = [f"### {title}: {len(rows)} differing key(s)"]
    if not rows:
        return lines[0]
    numeric = [r for r in rows if r["kind"] == "numeric"]
    if numeric:
        rels = [abs(r["rel"]) for r in numeric if r["rel"] is not None]
        lines.append(f"numeric: {len(numeric)}, max |rel| = {max(rels):.3g}" if rels
                     else f"numeric: {len(numeric)}")
    lines.append("| key | old | new | abs | rel | kind |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows[:limit] if limit else rows:
        lines.append(f"| {r['key']} | {_fmt(r['old'], True)} | {_fmt(r['new'], True)} | "
                     f"{_fmt(r.get('abs'))} | {_fmt(r.get('rel'))} | {r['kind']} |")
    if limit and len(rows) > limit:
        lines.append(f"| ... {len(rows) - limit} more | | | | | |")
    return "\n".join(lines)


def golden_vs_current(solver_filter: Optional[str] = None,
                      python: str = sys.executable) -> List[Tuple[str, List[Dict[str, Any]]]]:
    out = []
    for solver, case in golden.iter_golden_cases():
        if solver_filter and solver != solver_filter:
            continue
        # The current expectation (step_b re-bless if any, else the d33b6f5 golden), run
        # with the CASES payload: the stored input has sorted keys, and key order matters
        # for some solvers (see test_phase6a_golden.GoldenRegressionTest._check).
        doc = golden.load_expected(solver, case)
        fresh = golden.run_solver(solver, golden.CASES[solver][case], python=python)
        old = {"exitCode": doc["exitCode"], "stdout": doc["stdout"]}
        new = {"exitCode": fresh["exitCode"], "stdout": fresh["stdout"]}
        out.append((f"{solver}/{case}", diff(old, new)))
    return out


def main(argv=None) -> int:
    # Solver strings contain non-ASCII (e.g. reaction arrows); a redirected Windows
    # console would otherwise use a legacy code page and fail to encode them.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--solver", choices=sorted(golden.CASES))
    parser.add_argument("--old", type=Path)
    parser.add_argument("--new", type=Path)
    parser.add_argument("--limit", type=int, default=40, help="rows per table (0 = all)")
    args = parser.parse_args(argv)
    if args.old or args.new:
        if not (args.old and args.new):
            parser.error("--old and --new go together")
        old = json.loads(args.old.read_text(encoding="utf-8"))
        new = json.loads(args.new.read_text(encoding="utf-8"))
        results = [(f"{args.old.name} -> {args.new.name}", diff(old, new))]
    else:
        results = golden_vs_current(args.solver)
    drifted = False
    for title, rows in results:
        drifted = drifted or bool(rows)
        print(render(title, rows, args.limit or None))
        print()
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
