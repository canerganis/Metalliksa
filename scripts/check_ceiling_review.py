"""Fail when an existing allowlist ceiling (*.ceiling.json) changes without review.

Every *.ceiling.json that already exists at the merge base and differs at HEAD must be
touched by at least one commit in merge-base..HEAD whose message carries the trailer
``Ceiling-Review: <reason>``. Ceilings that are new in the range are governed by
python/test_allowlist_ceilings.py (pinned original content plus an explicit delta).

Usage (CI, full history):  python scripts/check_ceiling_review.py <base-sha> [head]
A missing/all-zero base (first push of a branch) falls back to HEAD^.
"""
from __future__ import annotations

import subprocess
import sys
from typing import List, Optional

TRAILER = "Ceiling-Review:"


def _git(args: List[str], cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def _exists(rev: str, path: str, cwd: Optional[str]) -> bool:
    return _git(["cat-file", "-e", f"{rev}:{path}"], cwd, check=False).returncode == 0


def has_review_trailer(message: str) -> bool:
    for line in message.splitlines():
        if line.startswith(TRAILER) and line[len(TRAILER):].strip():
            return True
    return False


def unreviewed_ceiling_changes(base: str, head: str = "HEAD", cwd: Optional[str] = None) -> List[str]:
    merge_base = _git(["merge-base", base, head], cwd).stdout.strip()
    changed = [p for p in _git(["diff", "--name-only", merge_base, head, "--", "*.ceiling.json"], cwd).stdout.splitlines() if p]
    problems = []
    for path in changed:
        if not _exists(merge_base, path, cwd):
            continue  # New ceiling: pinned by python/test_allowlist_ceilings.py.
        log = _git(["log", "--format=%B%x00", f"{merge_base}..{head}", "--", path], cwd).stdout
        if not any(has_review_trailer(message) for message in log.split("\x00")):
            problems.append(f"{path}: changed since {merge_base[:12]} without a '{TRAILER} <reason>' commit trailer")
    return problems


def main(argv: List[str]) -> int:
    base = argv[0] if argv and argv[0].strip("0") else "HEAD^"
    head = argv[1] if len(argv) > 1 else "HEAD"
    problems = unreviewed_ceiling_changes(base, head)
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"ceiling review: {len(problems)} unreviewed change(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
