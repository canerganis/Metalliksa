"""Fail when an allowlist ceiling (*.ceiling.json) or its guard changes without review.

Reviewed paths: every *.ceiling.json that already exists at the merge base and differs at
HEAD, plus the guard files in PROTECTED_PATHS (this script, the pinned-ceiling test and the
CI workflow that runs both) whenever they differ. For each such path the LAST commit in
merge-base..HEAD that touches it must carry the trailer ``Ceiling-Review: <reason>`` in its
trailer block (parsed by ``git interpret-trailers``; the reason needs at least four words); an
earlier reviewed commit does not cover a later unreviewed edit. Ceilings that are new in the
range are governed by python/test_allowlist_ceilings.py (pinned content plus an explicit delta).

Usage (CI, full history):  python scripts/check_ceiling_review.py <base-sha> [head]
A missing/all-zero base (first push of a branch) falls back to HEAD^.
"""
from __future__ import annotations

import subprocess
import sys
from typing import List, Optional

TRAILER = "Ceiling-Review:"
MIN_REASON_WORDS = 4
# Guard files reviewed like a ceiling: weakening any of them would silently disable the ratchet.
PROTECTED_PATHS = (
    "scripts/check_ceiling_review.py",
    "python/test_allowlist_ceilings.py",
    ".github/workflows/ci.yml",
)


def _git(args: List[str], cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def _exists(rev: str, path: str, cwd: Optional[str]) -> bool:
    return _git(["cat-file", "-e", f"{rev}:{path}"], cwd, check=False).returncode == 0


def review_reasons(message: str) -> List[str]:
    """Values of 'Ceiling-Review' trailers, as git itself parses the trailer block."""
    parsed = subprocess.run(["git", "interpret-trailers", "--parse"], input=message, capture_output=True,
                            text=True, check=True).stdout
    reasons = []
    for line in parsed.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip().lower() == TRAILER[:-1].lower():
            reasons.append(value.strip())
    return reasons


def is_reason(text: str) -> bool:
    """A reason is at least MIN_REASON_WORDS words that contain a letter or digit ('.' is not one)."""
    return len([word for word in text.split() if any(char.isalnum() for char in word)]) >= MIN_REASON_WORDS


def has_review_trailer(message: str) -> bool:
    return any(is_reason(reason) for reason in review_reasons(message))


def reviewed_paths(merge_base: str, head: str, cwd: Optional[str] = None) -> List[str]:
    """Changed paths that need review: pre-existing ceilings and the protected guard files.

    --no-renames: a renamed ceiling shows as a deletion of the old path (which exists at the
    merge base, so it is reviewed) plus an addition, not as a new file that escapes review.
    """
    changed = [p for p in _git(["diff", "--no-renames", "--name-only", merge_base, head], cwd).stdout.splitlines() if p]
    return [p for p in changed
            if p in PROTECTED_PATHS or (p.endswith(".ceiling.json") and _exists(merge_base, p, cwd))]


def last_touching_commit(merge_base: str, head: str, path: str, cwd: Optional[str] = None) -> Optional[str]:
    """Newest commit in merge_base..head that changes ``path``, or None.

    Default history simplification: a merge that takes the file unchanged from one parent is
    skipped (the reviewed branch commit stays the last one); a merge whose result differs from
    every parent (conflict resolution or an evil merge) is itself the last change and needs
    the trailer.
    """
    out = _git(["log", "-1", "--format=%H", f"{merge_base}..{head}", "--", path], cwd).stdout.strip()
    return out or None


def unreviewed_ceiling_changes(base: str, head: str = "HEAD", cwd: Optional[str] = None) -> List[str]:
    merge_base = _git(["merge-base", base, head], cwd).stdout.strip()
    problems = []
    for path in reviewed_paths(merge_base, head, cwd):
        commit = last_touching_commit(merge_base, head, path, cwd)
        message = _git(["log", "-1", "--format=%B", commit], cwd).stdout if commit else ""
        if not has_review_trailer(message):
            where = f"last changed in {commit[:12]}" if commit else "changed"
            problems.append(f"{path}: {where} since {merge_base[:12]} without a '{TRAILER} <reason of"
                            f" {MIN_REASON_WORDS}+ words>' commit trailer")
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
