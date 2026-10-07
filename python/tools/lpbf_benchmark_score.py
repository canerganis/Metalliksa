#!/usr/bin/env python3
"""Score submissions against the open LPBF screening benchmark and build the leaderboard record.

SCREENING BENCHMARK, NOT VALIDATION. See ``python/lpbf_benchmark.py`` and ``docs/LPBF_BENCHMARK.md``. No network.

Usage (from the repo root; PYTHONDONTWRITEBYTECODE=1):
    python -B python/tools/lpbf_benchmark_score.py score --submission my.csv --meta my.json --table-cache .runtime/cache/lpbf_benchmark_default_table.json
        validates the submission and writes data/benchmark/leaderboard/submissions/<slug>.score.json
    python -B python/tools/lpbf_benchmark_score.py builtin --table-cache .runtime/cache/lpbf_benchmark_default_table.json --date 2026-10-07
        scores the 3 frozen kernels at default absorptivity (no calibrated rung: none is enabled) and writes
        docs/LPBF_LEADERBOARD_<date>.json aggregating them with the local submissions
    python -B python/tools/lpbf_benchmark_score.py builtin --check [--table-cache ...]
        re-derives the newest committed record and fails on drift (with a table, the built-in entries are recomputed)
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import List, Optional

PYTHON_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PYTHON_DIR.parent
sys.path.insert(0, str(PYTHON_DIR))

import lpbf_benchmark as bm  # noqa: E402


DEFAULT_CACHE_REL = ".runtime/cache/lpbf_benchmark_default_table.json"


def _fingerprint() -> str:
    from lpbf_simulation import implementation_fingerprint
    return implementation_fingerprint()


def _table(loaded, fp: str, cache_arg: Optional[str], jobs: int):
    cache = Path(cache_arg).resolve() if cache_arg else None
    return bm.load_default_table(loaded, fp, cache, jobs)


def cmd_score(a: argparse.Namespace) -> int:
    root = Path(a.repo_root).resolve()
    fp = _fingerprint()
    loaded = bm.load_truth()
    meta = json.loads(Path(a.meta).read_text(encoding="utf-8"))
    csv_bytes = Path(a.submission).read_bytes()
    try:
        bm.verify_manifest(root, loaded)
        table = _table(loaded, fp, a.table_cache, a.jobs)
        slug, doc = bm.score_submission(root, csv_bytes, meta, table, fp, loaded)
    except bm.BenchmarkError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    out = bm.bench_dir(root) / bm.SUBMISSIONS_DIR / f"{slug}.score.json"
    bm.write_text(out, bm.dumps(json.loads(bm.canonical_json(bm.st.round_sig(doc, 6)))))
    unresolved = sum(c.get("unresolved", 0) for c in doc["entry"]["cells"] if c["status"] == "scored")
    print(f"wrote {out} ({doc['entry']['provenance']['rowsSubmitted']} rows submitted; unresolved cells-rows: {unresolved})",
          file=sys.stderr)
    return 0


def cmd_builtin(a: argparse.Namespace) -> int:
    root = Path(a.repo_root).resolve()
    fp = _fingerprint()
    loaded = bm.load_truth()
    try:
        if a.check:
            cache = a.table_cache or str(root / DEFAULT_CACHE_REL)
            table = _table(loaded, fp, cache, a.jobs) if Path(cache).is_file() else None
            print("check mode:", "built-in entries recomputed from " + Path(cache).name if table is not None
                  else "no kernel table found, built-in numbers NOT recomputed (record structure, shas and submissions only)",
                  file=sys.stderr)
            problems = bm.check_leaderboard(root, loaded, fp, table)
            for p in problems:
                print("DRIFT:", p, file=sys.stderr)
            print("check", "FAILED" if problems else "PASSED", file=sys.stderr)
            return 1 if problems else 0
        table = _table(loaded, fp, a.table_cache, a.jobs)
        date = a.date or datetime.date.today().isoformat()
        doc = bm.build_leaderboard(root, loaded, table, fp, date)
    except bm.BenchmarkError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    path = bm.write_leaderboard(root, doc)
    print(f"wrote {path} ({len(doc['entries'])} entries; calibrated rung: {doc['calibratedRung']['enabledCells']} enabled cells)",
          file=sys.stderr)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("score", cmd_score), ("builtin", cmd_builtin)):
        p = sub.add_parser(name)
        p.add_argument("--table-cache", default=None, help="kernel table cache (the scorecard's, or a default-only one)")
        p.add_argument("--jobs", type=int, default=6)
        p.add_argument("--repo-root", default=str(REPO_ROOT))
        p.set_defaults(fn=fn)
        if name == "score":
            p.add_argument("--submission", required=True, help="CSV: row_id,width_um,depth_um[,width_lo90,width_hi90,depth_lo90,depth_hi90]")
            p.add_argument("--meta", required=True, help="JSON: name, version, author, description, url, trainedOnSources")
        else:
            p.add_argument("--date", default=None)
            p.add_argument("--check", action="store_true", help="re-derive the newest committed record; fail on drift")
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
