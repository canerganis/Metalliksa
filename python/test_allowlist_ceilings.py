"""Allowlist ceilings may not grow silently (Phase 7 slice 1, review fix 2).

1. Every *.ceiling.json in the repo is pinned here. Its original content is read from git
   at the pinned commit and must hash to the pinned sha256; the current entries must be a
   subset of the original entries plus the explicit DELIBERATE_DELTA below. Descriptions
   may change; entries may not grow beyond original + delta.
2. scripts/check_ceiling_review.py (run in CI) requires a 'Ceiling-Review: <reason>' commit
   trailer for any change to a ceiling that already exists at the merge base. It is tested
   here against a throw-away git repository.

Needs git history (the CI python job checks out with fetch-depth 0). Without history the
pinned-original test skips locally and fails under CI.

Run from the python directory:  python -B -m unittest test_allowlist_ceilings
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_ceiling_review as review  # noqa: E402

ORIGINAL_COMMIT = "0171487a942678878518b8de3848f4aa1a1c758d"
# sha256 of the blob at ORIGINAL_COMMIT (git show <commit>:<path>).
PINNED = {
    "src/components/UNREACHABLE_BASELINE.ceiling.json": "b4d213c128b78084c729a4de1fd7b43ffae85641a29975166e0ed5e68f64537d",
    "src/components/SHARED.ceiling.json": "27b04f564c6f45689387f21e3562a4e9e166ab469a450a07e758c8ca555c1ae9",
    "routes/AUTHORITY_ALLOWLIST.ceiling.json": "b7bd114df5ba6f886a6b0474cf6e61e91c9d5b68b49ca8184edd853924209407",
    "python/module_warm_parity.ceiling.json": "9bb6d8f9d96dcd1fbecb7f0c18e5a607ef1a9a00ba83f338c058e580d14f172a",
}
# Reviewed growth after ORIGINAL_COMMIT (slice-1 fix rounds). Nothing else may be added.
DELIBERATE_DELTA = {
    "routes/AUTHORITY_ALLOWLIST.ceiling.json": {
        # a82a021: new 'unclassified' section (handlers the parser cannot classify). Fix round 2
        # widened discovery to .use mounts: the four guard/parser middleware mounts below.
        "unclassified": {"USE /api/lpbf", "USE /api/lpbf/sources", "USE /api/lpbf/runs", "USE /api/research/registry"},
        # b5d6ba8: the canned Materials Project search was unbound from the registry (review item 4).
        # Fix round 2 widened discovery to server.ts: its three infrastructure handlers.
        "unbound": {"GET /api/materials-project/search", "GET /api/health", "GET /api/runtime-config", "ALL /api/*"},
        # Fix round 2, stricter canned rules (ternary of literals): the server.ts liveness flag.
        "cannedBaseline": {"GET /api/health"},
    },
}
IGNORED_DIRS = {"node_modules", ".git", "dist", "graft", ".runtime"}


def entry_sets(text: str) -> dict:
    data = json.loads(text)
    return {key: set(value) for key, value in data.items() if isinstance(value, list)}


def ceiling_files() -> list:
    found = []
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        found += [Path(root, f).relative_to(REPO_ROOT).as_posix() for f in files if f.endswith(".ceiling.json")]
    return sorted(found)


def growth(original: dict, current: dict, delta: dict) -> list:
    """Entries (or keys) in ``current`` that neither ``original`` nor ``delta`` allows."""
    problems = []
    for key, values in current.items():
        allowed = original.get(key)
        if allowed is None and key not in delta:
            problems.append(f"new key {key!r}")
            continue
        extra = values - (allowed or set()) - delta.get(key, set())
        problems += [f"{key}: {value}" for value in sorted(extra)]
    return problems


def _git_show(commit: str, path: str):
    result = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=REPO_ROOT, capture_output=True)
    return result.stdout if result.returncode == 0 else None


class PinnedCeilingTests(unittest.TestCase):
    def test_every_ceiling_file_is_pinned(self):
        self.assertEqual(ceiling_files(), sorted(PINNED), "a new *.ceiling.json must be pinned here")

    def test_ceilings_never_grow_beyond_original_plus_reviewed_delta(self):
        for path, digest in PINNED.items():
            with self.subTest(path=path):
                blob = _git_show(ORIGINAL_COMMIT, path)
                if blob is None:
                    if os.environ.get("CI"):
                        self.fail(f"{ORIGINAL_COMMIT}:{path} unavailable (CI needs fetch-depth 0)")
                    self.skipTest("git history unavailable")
                self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, "pinned original content changed")
                current = entry_sets((REPO_ROOT / path).read_text(encoding="utf-8"))
                self.assertEqual(growth(entry_sets(blob.decode("utf-8")), current, DELIBERATE_DELTA.get(path, {})), [])

    def test_growth_logic_rejects_additions_and_new_keys(self):
        original = {"unbound": {"a"}, "cannedBaseline": {"c"}}
        self.assertEqual(growth(original, {"unbound": {"a"}, "cannedBaseline": set()}, {}), [])
        self.assertEqual(growth(original, {"unbound": {"a", "sneaked"}}, {}), ["unbound: sneaked"])
        self.assertEqual(growth(original, {"unbound": {"a", "ok"}}, {"unbound": {"ok"}}), [])
        self.assertEqual(growth(original, {"newKey": {"x"}}, {}), ["new key 'newKey'"])
        # The reviewed delta for the routes ceiling allows exactly one unbound entry more.
        delta = DELIBERATE_DELTA["routes/AUTHORITY_ALLOWLIST.ceiling.json"]
        self.assertEqual(growth({"unbound": set()}, {"unbound": {"GET /api/materials-project/search", "GET /api/x"}, "unclassified": {"USE /api/lpbf", "y"}}, delta),
                         ["unbound: GET /api/x", "unclassified: y"])


class CeilingReviewTrailerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"],
                     ["config", "commit.gpgsign", "false"], ["config", "core.autocrlf", "false"]):
            subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)
        self._commit("x.ceiling.json", '{"paths": ["a"]}\n', "base")
        self.base = self._rev()

    def tearDown(self):
        self.tmp.cleanup()

    def _commit(self, name: str, text: str, message: str) -> None:
        path = Path(self.repo, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", name], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=self.repo, check=True, capture_output=True)

    def _rev(self) -> str:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, check=True, capture_output=True, text=True).stdout.strip()

    def test_unreviewed_change_to_existing_ceiling_fails(self):
        self._commit("x.ceiling.json", '{"paths": ["a", "b"]}\n', "grow it")
        problems = review.unreviewed_ceiling_changes(self.base, cwd=self.repo)
        self.assertEqual(len(problems), 1)
        self.assertIn("x.ceiling.json", problems[0])

    def test_trailer_without_reason_fails(self):
        self._commit("x.ceiling.json", '{"paths": ["a", "b"]}\n', "grow it\n\nCeiling-Review:")
        self.assertEqual(len(review.unreviewed_ceiling_changes(self.base, cwd=self.repo)), 1)

    def test_reviewed_change_passes(self):
        self._commit("x.ceiling.json", '{"paths": ["a", "b"]}\n', "grow it\n\nCeiling-Review: maintainer approved b")
        self.assertEqual(review.unreviewed_ceiling_changes(self.base, cwd=self.repo), [])

    def test_nested_and_new_ceilings(self):
        self._commit("deep/dir/y.ceiling.json", '{"paths": []}\n', "new ceiling")  # new: pinned by the test above
        self.assertEqual(review.unreviewed_ceiling_changes(self.base, cwd=self.repo), [])
        middle = self._rev()
        self._commit("deep/dir/y.ceiling.json", '{"paths": ["z"]}\n', "grow nested")
        self.assertEqual(len(review.unreviewed_ceiling_changes(middle, cwd=self.repo)), 1)

    def test_trailer_parser(self):
        self.assertTrue(review.has_review_trailer("subject\n\nCeiling-Review: reason"))
        self.assertFalse(review.has_review_trailer("subject mentions Ceiling-Review: inline"))
        self.assertFalse(review.has_review_trailer("subject\n\nCeiling-Review:   "))


if __name__ == "__main__":
    unittest.main()
