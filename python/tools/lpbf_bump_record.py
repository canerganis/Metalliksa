#!/usr/bin/env python3
"""Generate the LPBF implementation bump record (design 5c, section 2.5).

Skeleton mode (no --from-revision): the "from" side is the current working tree
(old fingerprint, VERSION, and the canonical and raw SHA-256 of every manifest
file); every value that only exists after the bump is null and listed in "todo".

Bump mode (--from-revision REV): the "from" side is rebuilt from git objects at
REV (manifest and VERSION parsed from REV's python/lpbf_simulation.py, file bytes
from `git show`), the "to" side is the current working tree, and the manifest
diff, version check and commit SHAs are filled in. With --with-parity-check the
parity harness (tools/lpbf_parity_check.py) is run and its per-case result and
after-digests are recorded next to the golden (before) digests.

Usage (from python/, locked interpreter, PYTHONDONTWRITEBYTECODE=1):
    python -B tools/lpbf_bump_record.py [--out FILE]
    python -B tools/lpbf_bump_record.py --from-revision <pre-bump sha> \
        --with-parity-check [--slow] [--expect-drift CASE[:KEY_GLOB][,...]]         --out ../docs/LPBF_IMPLEMENTATION_BUMP_<date>.json

Identity note: raw file SHA-256 depends on the checkout's line endings
(core.autocrlf); the canonical SHA-256 (CRLF -> LF for registered text sources,
exactly as lpbf_source_identity canonical-v3) is the stable per-file identity.
Git objects only provide canonical digests here.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PYTHON_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PYTHON_DIR.parent
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from lpbf_fingerprint_pin import read_pinned_fingerprint  # noqa: E402

RECORD_SCHEMA = "lpbf-implementation-bump-record-1"
GOLDEN_DIR = PYTHON_DIR / "golden" / "lpbf_parity"
DESIGN = "docs/LPBF_5C_FINGERPRINT_BUMP_DESIGN_2026-10-04.md"


def _git(*args: str, binary: bool = False):
    result = subprocess.run(["git", *args], cwd=str(REPO_ROOT), capture_output=True, check=True)
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def _literal_assignment(source: str, name: str) -> Any:
    for node in ast.parse(source).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name):
            return ast.literal_eval(node.value)
    raise ValueError(f"{name} is not a literal top-level assignment in lpbf_simulation.py")


def _side(entries: List[Tuple[str, bytes]], version: str, revision: str, *, raw: bool) -> Dict[str, Any]:
    from lpbf_source_identity import (CANONICAL_SCHEMA, RAW_SCHEMA, canonical_source_bytes,
                                      fingerprint_manifest_entries)
    files: Dict[str, Any] = {}
    for relative, content in sorted(entries):
        canonical = canonical_source_bytes(relative, content)
        files[relative] = {"canonicalSha256": hashlib.sha256(canonical).hexdigest(),
                           "canonicalBytes": len(canonical)}
        if raw:
            files[relative].update(rawSha256=hashlib.sha256(content).hexdigest(), rawBytes=len(content))
    side = {"revision": revision, "version": version, "fingerprintSchema": CANONICAL_SCHEMA,
            "implementationHash": fingerprint_manifest_entries(entries, version),
            "manifestCount": len(entries), "manifest": [relative for relative, _ in entries],
            "files": files}
    if raw:
        side["rawSchema"] = RAW_SCHEMA
        side["rawByteImplementationHash"] = fingerprint_manifest_entries(entries, version, schema=RAW_SCHEMA)
    return side


def worktree_side() -> Dict[str, Any]:
    import lpbf_simulation
    entries = [(relative, (PYTHON_DIR / relative).read_bytes())
               for relative in lpbf_simulation.IMPLEMENTATION_SOURCE_FILES]
    side = _side(entries, lpbf_simulation.VERSION, "worktree", raw=True)
    if side["implementationHash"] != lpbf_simulation.implementation_fingerprint():
        raise AssertionError("bump record framing disagrees with implementation_fingerprint()")
    side["manifest"] = list(lpbf_simulation.IMPLEMENTATION_SOURCE_FILES)
    return side


def revision_side(revision: str) -> Dict[str, Any]:
    commit = _git("rev-parse", "--verify", f"{revision}^{{commit}}")
    simulation = _git("show", f"{commit}:python/lpbf_simulation.py", binary=True).decode("utf-8")
    manifest = _literal_assignment(simulation, "IMPLEMENTATION_SOURCE_FILES")
    version = _literal_assignment(simulation, "VERSION")
    entries = [(relative, _git("show", f"{commit}:python/{relative}", binary=True)) for relative in manifest]
    side = _side(entries, version, commit, raw=False)
    side["manifest"] = list(manifest)
    return side


def golden_digests() -> Dict[str, Any]:
    digests: Dict[str, Any] = {}
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        golden = json.loads(path.read_text(encoding="utf-8"))
        observations = golden["observations"]
        digests[golden["case"]] = {
            "group": golden["group"], "slow": golden["slow"],
            "recordedImplementationHash": golden["recordedImplementationHash"],
            "recordedGitHead": golden.get("recordedGitHead"),
            "observationCount": len(observations),
            "observationsSha256": hashlib.sha256(json.dumps(
                observations, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest(),
            "resultDigests": {key: value for key, value in observations.items()
                              if key.endswith(("canonicalSha256", "orderedTypedSha256"))},
            "artifactDigests": {key: value for key, value in observations.items()
                                if key.startswith("artifact.")},
        }
    return digests


def _parity_module():
    spec = importlib.util.spec_from_file_location("lpbf_parity_check", PYTHON_DIR / "tools" / "lpbf_parity_check.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def parity_after(slow: bool, expect_drift: Optional[List[str]] = None) -> Dict[str, Any]:
    """Per-case parity result after the bump. expect_drift uses exactly the --check semantics
    (tools/lpbf_parity_check.py --expect-drift): allowed drift is status DRIFT and carries
    before -> after records (observation values, raw values and leaf-level raw changes)."""
    parity = _parity_module()
    entries = parity.parse_expect_drift(expect_drift)
    after: Dict[str, Any] = {}
    for case in parity.CASES:
        if case.slow and not slow:
            after[case.id] = {"status": "not-run (slow; pass --slow)"}
            if any(entry.case_id == case.id for entry in entries):
                after[case.id] = {"status": "FAIL", "problems": [
                    "named in --expect-drift but not run (slow; pass --slow)"]}
            continue
        outcome = parity.check_case(case, parity.DEFAULT_WORK_ROOT)
        if outcome["skipped"] is not None:
            after[case.id] = {"status": "SKIPPED", "reason": outcome["skipped"]}
            continue
        observations = outcome["observations"]
        verdict = parity.evaluate_drift(case, outcome, entries)
        after[case.id] = {
            "status": verdict["status"],
            "problems": verdict["problems"],
            "drift": verdict["drift"],
            "elapsed_s": round(outcome["elapsed_s"], 1),
            "implementationHashes": outcome.get("implementationHashes", []),
            "observationsSha256": hashlib.sha256(json.dumps(
                observations, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest(),
        }
    return after


def _require_goldens_recorded_at(from_hash: str, goldens: Dict[str, Any]) -> None:
    """Every parity golden is the pre-bump side of the proof: it must carry fromHash."""
    if not goldens:
        raise SystemExit("refused: no parity goldens found")
    wrong = {case: value["recordedImplementationHash"] for case, value in goldens.items()
             if value["recordedImplementationHash"] != from_hash}
    if wrong:
        raise SystemExit(f"refused: goldens not recorded at fromHash {from_hash}: {wrong}")


def build_record(from_revision: Optional[str], with_parity: bool, slow: bool,
                 allow_same_hash: bool = False, expect_drift: Optional[List[str]] = None) -> Dict[str, Any]:
    import numpy
    current = worktree_side()
    pinned = read_pinned_fingerprint()
    record: Dict[str, Any] = {
        "schema": RECORD_SCHEMA, "design": DESIGN,
        "environment": {"python": platform.python_version(), "numpy": numpy.__version__,
                        "platform": platform.platform()},
        "pinnedExpectedFingerprint": pinned,
        "parityGoldens": golden_digests(),
        "legacyBroadCacheNote": ("_legacy_broad_cache_fingerprint hashes every python/*.py, so any "
                                 "commit adding or editing a top-level python file already "
                                 "invalidates build-job/GPU caches; unrelated to this record."),
    }
    if from_revision is None:
        if current["implementationHash"] != pinned:
            raise SystemExit(f"skeleton refused: worktree fingerprint {current['implementationHash']} "
                             f"!= pinned {pinned}")
        _require_goldens_recorded_at(current["implementationHash"], record["parityGoldens"])
        record.update({
            "from": current, "to": None, "fromHash": current["implementationHash"], "toHash": None,
            "versionUnchanged": None, "manifestDiff": None,
            "commits": {"fromRevision": _git("rev-parse", "HEAD"), "toRevision": None},
            "parityAfter": None,
            "todo": ["to", "toHash", "versionUnchanged", "manifestDiff", "commits.toRevision",
                     "parityAfter (run with --from-revision ... --with-parity-check --slow)"],
        })
        return record
    before = revision_side(from_revision)
    _require_goldens_recorded_at(before["implementationHash"], record["parityGoldens"])
    if current["implementationHash"] == before["implementationHash"] and not allow_same_hash:
        raise SystemExit(f"refused: toHash equals fromHash {before['implementationHash']}; a bump record "
                         "needs a changed fingerprint (use --allow-same-hash only for a dry run)")
    old_files, new_files = before["files"], current["files"]
    record.update({
        "from": before, "to": current,
        "fromHash": before["implementationHash"], "toHash": current["implementationHash"],
        "dryRunSameHash": current["implementationHash"] == before["implementationHash"],
        "versionUnchanged": before["version"] == current["version"],
        "pinMatchesToHash": pinned == current["implementationHash"],
        "manifestDiff": {
            "added": sorted(set(new_files) - set(old_files)),
            "removed": sorted(set(old_files) - set(new_files)),
            "changed": sorted(name for name in set(old_files) & set(new_files)
                              if old_files[name]["canonicalSha256"] != new_files[name]["canonicalSha256"]),
            "unchanged": sorted(name for name in set(old_files) & set(new_files)
                                if old_files[name]["canonicalSha256"] == new_files[name]["canonicalSha256"]),
        },
        "commits": {"fromRevision": before["revision"], "toRevision": _git("rev-parse", "HEAD"),
                    "worktreeDirty": bool(_git("status", "--porcelain", "--", "python"))},
        "expectDrift": list(expect_drift or []),
        "parityAfter": parity_after(slow, expect_drift) if with_parity else None,
        "todo": ([] if with_parity and slow else
                 ["parityAfter.g2 (rerun with --with-parity-check --slow)"] if with_parity else
                 ["parityAfter (rerun with --with-parity-check --slow)"]),
    })
    return record


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-revision", help="pre-bump git revision (bump mode)")
    parser.add_argument("--with-parity-check", action="store_true", help="run the parity harness (bump mode)")
    parser.add_argument("--slow", action="store_true", help="include slow parity cases (G2, ~106 s)")
    parser.add_argument("--out", help="write the record here instead of stdout")
    parser.add_argument("--allow-same-hash", action="store_true",
                        help="bump mode dry run: allow toHash == fromHash (never for the real record)")
    parser.add_argument("--expect-drift", action="append", metavar="CASE[:KEY_GLOB][,...]",
                        help="planned drift, exactly as tools/lpbf_parity_check.py --check --expect-drift; "
                             "drifted cases are recorded as DRIFT with before -> after values")
    args = parser.parse_args(argv)
    if args.with_parity_check and not args.from_revision:
        parser.error("--with-parity-check needs --from-revision")
    if args.expect_drift and not args.with_parity_check:
        parser.error("--expect-drift needs --with-parity-check")
    record = build_record(args.from_revision, args.with_parity_check, args.slow, args.allow_same_hash,
                          args.expect_drift)
    text = json.dumps(record, indent=1, allow_nan=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {args.out}: fromHash {record['fromHash']} toHash {record['toHash']}")
    else:
        sys.stdout.write(text)
    statuses = [value.get("status") for value in (record.get("parityAfter") or {}).values()]
    if "FAIL" in statuses:
        return 1
    return 3 if "SKIPPED" in statuses else 0


if __name__ == "__main__":
    sys.exit(main())
