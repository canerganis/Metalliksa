"""Allowlist ceilings may not grow silently (Phase 7 slice 1, review fix 2).

1. Every *.ceiling.json in the repo is pinned here. The original entries (as committed at
   ORIGINAL_COMMIT) are embedded below in ORIGINAL_ENTRIES, so the check does not depend on
   that commit staying reachable (squash/rebase merges, shallow clones); the current entries
   must be a subset of the original entries plus the explicit DELIBERATE_DELTA below.
   Descriptions may change; entries may not grow beyond original + delta. When the history
   is available, the embedded lists are cross-checked against the pinned blob sha256.
2. scripts/check_ceiling_review.py (run in CI) requires a 'Ceiling-Review: <reason>' trailer
   on the LAST commit that touches a ceiling existing at the merge base, and on the last
   commit touching each guard file (this test, the script, .github/workflows/ci.yml). It is
   tested here against a throw-away git repository.

Run from the python directory:  python -B -m unittest test_allowlist_ceilings
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_ceiling_review as review  # noqa: E402

ORIGINAL_COMMIT = "0171487a942678878518b8de3848f4aa1a1c758d"
# sha256 of the blob at ORIGINAL_COMMIT (git show <commit>:<path>); used only to cross-check
# ORIGINAL_ENTRIES when that commit is reachable.
PINNED = {
    "src/components/UNREACHABLE_BASELINE.ceiling.json": "b4d213c128b78084c729a4de1fd7b43ffae85641a29975166e0ed5e68f64537d",
    "src/components/SHARED.ceiling.json": "27b04f564c6f45689387f21e3562a4e9e166ab469a450a07e758c8ca555c1ae9",
    "routes/AUTHORITY_ALLOWLIST.ceiling.json": "b7bd114df5ba6f886a6b0474cf6e61e91c9d5b68b49ca8184edd853924209407",
    "python/module_warm_parity.ceiling.json": "9bb6d8f9d96dcd1fbecb7f0c18e5a607ef1a9a00ba83f338c058e580d14f172a",
}
# Entry lists of each PINNED ceiling at ORIGINAL_COMMIT (generated from the blobs above). These
# are the growth cap: edit only together with DELIBERATE_DELTA review, never to admit growth.
ORIGINAL_ENTRIES = {
    "src/components/UNREACHABLE_BASELINE.ceiling.json": {
        "paths": [
            "src/components/3d-distortion-lab/EmbeddedPythonLPBFSimulator.tsx",
            "src/components/3d-distortion-lab/LPBFGroundTruthDataLab.tsx",
            "src/components/3d-distortion-lab/MarangoniPoreInstabilityLab.tsx",
            "src/components/3d-distortion-lab/index.ts",
            "src/components/AdvancedBatteryPhysicsStudio.tsx",
            "src/components/BatteryEISDegradationStudio.tsx",
            "src/components/CNLSFittingStudio.tsx",
            "src/components/CircuitLibraryModal.tsx",
            "src/components/EISLabDataUploader.tsx",
            "src/components/EISUploadInsightsStudio.tsx",
            "src/components/EquivalentCircuitBuilder.tsx",
            "src/components/GrainEvolutionD3Chart.tsx",
            "src/components/LpbfBuildJobRail.tsx",
            "src/components/MonteCarloUncertaintyCard.tsx",
            "src/components/PhysicalValidationStudio.tsx",
            "src/components/PlotlyEISViewer.tsx",
            "src/components/PresetCircuitLibraryPanel.tsx",
            "src/components/PythonBatteryCorrosionUploadStudio.tsx",
            "src/components/SavitzkyGolayFilterControls.tsx",
            "src/components/StochasticUQMMPDSStudio.tsx",
            "src/components/SyntheticNoiseStressStudio.tsx",
            "src/components/TransportKineticsLab.tsx",
            "src/components/WebGLEBSDMapCanvas.tsx",
        ],
    },
    "src/components/SHARED.ceiling.json": {
        "paths": [
            "src/components/Field.tsx",
        ],
    },
    "routes/AUTHORITY_ALLOWLIST.ceiling.json": {
        "unbound": [
            "DELETE /api/python/battery-corrosion-upload/:id?",
            "GET /api/calphad/databases",
            "GET /api/lpbf/runs/:runId",
            "GET /api/lpbf/runs/bundles/:bundleId/download",
            "GET /api/lpbf/runs/bundles/restores/:restoreId/runs",
            "GET /api/lpbf/runs/bundles/restores/:restoreId/runs/:runId",
            "GET /api/lpbf/runs/proxy-campaigns",
            "GET /api/lpbf/sources/:datasetId",
            "GET /api/lpbf/sources/:datasetId/revisions",
            "GET /api/lpbf/sources/:datasetId/revisions/:revision",
            "GET /api/orchestrator/approved-sources",
            "GET /api/python/battery-corrosion-upload/recent",
            "GET /api/python/ipc-status",
            "GET /api/python/status",
            "GET /api/research/registry/history",
            "GET /api/research/registry/revisions/:revision",
            "POST /api/calphad/minimize",
            "POST /api/lpbf/runs/:runId/nist-comparison",
            "POST /api/lpbf/runs/bundles/:bundleId/restore",
            "POST /api/lpbf/runs/bundles/:bundleId/verify",
            "POST /api/lpbf/runs/bundles/export",
            "POST /api/lpbf/runs/bundles/import",
            "POST /api/lpbf/runs/bundles/imports/:bundleId/restore",
            "POST /api/lpbf/runs/bundles/restores/:restoreId/runs/:runId/nist-comparison",
            "POST /api/lpbf/runs/import",
            "POST /api/lpbf/runs/preview",
            "POST /api/lpbf/runs/proxy-campaigns",
            "POST /api/lpbf/runs/proxy-campaigns/preview",
            "POST /api/lpbf/sources/:datasetId/import",
            "POST /api/lpbf/sources/:datasetId/preview",
            "POST /api/lpbf/sources/:datasetId/verify",
            "POST /api/metallurgy/analyze-sem",
            "POST /api/metallurgy/detect-sem-legend",
            "POST /api/metallurgy/qualify-aerospace",
            "POST /api/orchestrator/collect-source",
            "POST /api/python/battery-corrosion-exec-script",
            "POST /api/python/battery-corrosion-upload",
            "POST /api/python/bisquert-tlm-identify",
            "POST /api/python/cnls-autofit",
            "POST /api/python/cnls-fit",
            "POST /api/python/cnls-synthetic-noise",
            "POST /api/python/inverse-alloy-optimize",
            "POST /api/python/ipc-warmup",
            "POST /api/python/lpbf-bayesian-optimization",
            "POST /api/python/lpbf-experimental-validation",
            "POST /api/python/lpbf-support-optimization",
            "POST /api/python/lpbf-thermal",
            "POST /api/python/lpbf-transient-enthalpy-fdm",
            "POST /api/python/marangoni-pore-instability",
            "POST /api/python/part-scale-inherent-strain",
            "POST /api/python/xrd-deconvolve",
        ],
        "cannedBaseline": [
            "GET /api/materials-project/search",
            "GET /api/orchestrator/approved-sources",
            "POST /api/metallurgy/analyze-sem",
            "POST /api/metallurgy/detect-sem-legend",
            "POST /api/metallurgy/qualify-aerospace",
        ],
    },
    "python/module_warm_parity.ceiling.json": {
        "names": [
            "cnls_fitting_solver",
            "engine_dispatcher",
            "inverse_alloy_optimizer",
            "lpbf_build_job_solver",
            "marangoni_pore_instability_solver",
            "part_scale_inherent_strain_solver",
            "xrd_peak_deconvolution",
        ],
    },
}
# Ceilings added after ORIGINAL_COMMIT are frozen by the sha256 of their current content
# (CRLF normalised to LF): any change, including growth, needs an edit here.
PINNED_CONTENT = {
    # Fix round 2 (review item 5): orphans under src/features|utils|services|hooks. Shrunk in the
    # p7 re-audit fix round (8 deleted-file slots removed).
    "src/UNREACHABLE_SUPPORT_BASELINE.ceiling.json": "ba1abc5ad86313779507ba04250389c22040d249c2dd845db2cc611af0b8ac32",
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
# Count-valued ceiling keys ({entry: max}) may only shrink below these reviewed caps; a key or
# entry not listed here is growth. p7 re-audit fix round: site count per USE mount path.
COUNT_CAPS = {
    "routes/AUTHORITY_ALLOWLIST.ceiling.json": {
        "unclassifiedSites": {
            "USE /api/lpbf": 1,
            "USE /api/lpbf/runs": 2,
            "USE /api/lpbf/sources": 2,
            "USE /api/research/registry": 1,
        },
    },
}
# Exact entries of every ceiling at its last reviewed change (descriptions excluded). A ceiling
# may not differ from its snapshot: a shrink updates the snapshot in the same reviewed commit, so
# the freed slots can never be refilled later without editing this protected file again.
CEILING_SNAPSHOT = {
    "python/module_warm_parity.ceiling.json": {
        "names": [
            "cnls_fitting_solver",
            "engine_dispatcher",
            "inverse_alloy_optimizer",
            "lpbf_build_job_solver",
            "marangoni_pore_instability_solver",
            "part_scale_inherent_strain_solver",
            "xrd_peak_deconvolution",
        ],
    },
    "routes/AUTHORITY_ALLOWLIST.ceiling.json": {
        "unbound": [
            "ALL /api/*",
            "GET /api/calphad/databases",
            "GET /api/health",
            "GET /api/lpbf/runs/:runId",
            "GET /api/lpbf/runs/bundles/:bundleId/download",
            "GET /api/lpbf/runs/bundles/restores/:restoreId/runs",
            "GET /api/lpbf/runs/bundles/restores/:restoreId/runs/:runId",
            "GET /api/lpbf/runs/proxy-campaigns",
            "GET /api/lpbf/sources/:datasetId",
            "GET /api/lpbf/sources/:datasetId/revisions",
            "GET /api/lpbf/sources/:datasetId/revisions/:revision",
            "GET /api/materials-project/search",
            "GET /api/orchestrator/approved-sources",
            "GET /api/python/ipc-status",
            "GET /api/python/status",
            "GET /api/research/registry/history",
            "GET /api/research/registry/revisions/:revision",
            "GET /api/runtime-config",
            "POST /api/calphad/minimize",
            "POST /api/lpbf/runs/:runId/nist-comparison",
            "POST /api/lpbf/runs/bundles/:bundleId/restore",
            "POST /api/lpbf/runs/bundles/:bundleId/verify",
            "POST /api/lpbf/runs/bundles/export",
            "POST /api/lpbf/runs/bundles/import",
            "POST /api/lpbf/runs/bundles/imports/:bundleId/restore",
            "POST /api/lpbf/runs/bundles/restores/:restoreId/runs/:runId/nist-comparison",
            "POST /api/lpbf/runs/import",
            "POST /api/lpbf/runs/preview",
            "POST /api/lpbf/runs/proxy-campaigns",
            "POST /api/lpbf/runs/proxy-campaigns/preview",
            "POST /api/lpbf/sources/:datasetId/import",
            "POST /api/lpbf/sources/:datasetId/preview",
            "POST /api/lpbf/sources/:datasetId/verify",
            "POST /api/metallurgy/analyze-sem",
            "POST /api/metallurgy/detect-sem-legend",
            "POST /api/metallurgy/qualify-aerospace",
            "POST /api/orchestrator/collect-source",
            "POST /api/python/bisquert-tlm-identify",
            "POST /api/python/inverse-alloy-optimize",
            "POST /api/python/ipc-warmup",
            "POST /api/python/lpbf-bayesian-optimization",
            "POST /api/python/lpbf-experimental-validation",
            "POST /api/python/lpbf-support-optimization",
            "POST /api/python/lpbf-thermal",
            "POST /api/python/lpbf-transient-enthalpy-fdm",
            "POST /api/python/marangoni-pore-instability",
            "POST /api/python/part-scale-inherent-strain",
            "POST /api/python/xrd-deconvolve",
        ],
        "unclassified": [
            "USE /api/lpbf",
            "USE /api/lpbf/runs",
            "USE /api/lpbf/sources",
            "USE /api/research/registry",
        ],
        "unclassifiedSites": {
            "USE /api/lpbf": 1,
            "USE /api/lpbf/runs": 2,
            "USE /api/lpbf/sources": 2,
            "USE /api/research/registry": 1,
        },
        "cannedBaseline": [
            "GET /api/health",
            "GET /api/materials-project/search",
            "GET /api/orchestrator/approved-sources",
            "POST /api/metallurgy/analyze-sem",
            "POST /api/metallurgy/detect-sem-legend",
            "POST /api/metallurgy/qualify-aerospace",
        ],
    },
    "src/UNREACHABLE_SUPPORT_BASELINE.ceiling.json": {
        "paths": [
            "src/hooks/useVisibleAbortSignal.ts",
            "src/utils/ebsdParser.ts",
            "src/utils/savitzkyGolay.ts",
            "src/utils/seededRandom.ts",
            "src/utils/xrdParser.ts",
            "src/utils/xrdProfileFitting.ts",
        ],
    },
    "src/components/SHARED.ceiling.json": {
        "paths": [
            "src/components/Field.tsx",
        ],
    },
    "src/components/UNREACHABLE_BASELINE.ceiling.json": {
        "paths": [],
    },
}
# Entries that were removed for cause and must never return to any ceiling or live allowlist:
# the deleted battery-corrosion upload / user-script execution and CNLS routes.
FORBIDDEN_ENTRIES = {
    "POST /api/python/battery-corrosion-exec-script",
    "POST /api/python/battery-corrosion-upload",
    "GET /api/python/battery-corrosion-upload/recent",
    "DELETE /api/python/battery-corrosion-upload/:id?",
    "POST /api/python/cnls-fit",
    "POST /api/python/cnls-autofit",
    "POST /api/python/cnls-synthetic-noise",
}
# Live list behind each ceiling: (live file, how to read its entries). A ceiling entry must be in
# the live list or name a file that still exists; anything else is a stale slot to remove.
LIVE_LISTS = {
    "src/components/UNREACHABLE_BASELINE.ceiling.json": "src/components/UNREACHABLE_BASELINE.json",
    "src/components/SHARED.ceiling.json": "src/components/SHARED.json",
    "src/UNREACHABLE_SUPPORT_BASELINE.ceiling.json": "src/UNREACHABLE_SUPPORT_BASELINE.json",
    "routes/AUTHORITY_ALLOWLIST.ceiling.json": "routes/AUTHORITY_ALLOWLIST.json",
    "python/module_warm_parity.ceiling.json": "python/test_module_warm_parity.py",
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


def count_growth(path: str, data: dict) -> list:
    """Count-map entries of a ceiling beyond COUNT_CAPS (new keys, new entries, larger counts)."""
    problems = []
    caps = COUNT_CAPS.get(path, {})
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        if key not in caps:
            problems.append(f"new count key {key!r}")
            continue
        for entry, count in sorted(value.items()):
            limit = caps[key].get(entry)
            if limit is None or not isinstance(count, int) or isinstance(count, bool) or count < 0 or count > limit:
                problems.append(f"{key}: {entry} = {count!r} (cap {limit})")
    return problems


def snapshot_of(data: dict) -> dict:
    """Entries of a parsed ceiling as compared with CEILING_SNAPSHOT (lists sorted, no description)."""
    return {key: sorted(value) if isinstance(value, list) else dict(value)
            for key, value in data.items() if isinstance(value, (list, dict))}


def live_entries(ceiling_path: str) -> set:
    """Entries of the live list a ceiling caps (site suffixes of USE keys stripped)."""
    live_path = LIVE_LISTS[ceiling_path]
    if live_path.endswith(".py"):
        sys.path.insert(0, str(REPO_ROOT / "python"))
        import test_module_warm_parity as warm
        return set(warm.WARM_WITHOUT_REGISTRY_OPERATION)
    data = json.loads((REPO_ROOT / live_path).read_text(encoding="utf-8"))
    if "files" in data:
        return {entry["path"] for entry in data["files"]}
    return {re.sub(r" \([^()]+#\d+\)$", "", key) for section in ("unbound", "cannedBaseline", "unclassified") for key in data[section]}


def stale_slots(ceiling_path: str, data: dict, live: set) -> list:
    """Ceiling entries neither in the live list nor naming an existing file (repo path or python module)."""
    stale = []
    for key, values in data.items():
        entries = values if isinstance(values, list) else list(values) if isinstance(values, dict) else []
        for entry in entries:
            on_disk = (REPO_ROOT / entry).is_file() or (REPO_ROOT / "python" / f"{entry}.py").is_file()
            if entry not in live and not on_disk:
                stale.append(f"{key}: {entry}")
    return stale


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
        self.assertEqual(ceiling_files(), sorted({**PINNED, **PINNED_CONTENT}), "a new *.ceiling.json must be pinned here")

    def test_later_ceilings_are_frozen_by_content(self):
        for path, digest in PINNED_CONTENT.items():
            with self.subTest(path=path):
                content = (REPO_ROOT / path).read_bytes().replace(b"\r\n", b"\n")
                self.assertEqual(hashlib.sha256(content).hexdigest(), digest, f"{path} changed: review it and update the pin")

    def test_ceilings_never_grow_beyond_original_plus_reviewed_delta(self):
        self.assertEqual(sorted(ORIGINAL_ENTRIES), sorted(PINNED))
        for path in PINNED:
            with self.subTest(path=path):
                original = {key: set(values) for key, values in ORIGINAL_ENTRIES[path].items()}
                current = entry_sets((REPO_ROOT / path).read_text(encoding="utf-8"))
                self.assertEqual(growth(original, current, DELIBERATE_DELTA.get(path, {})), [])

    def test_embedded_originals_match_the_pinned_blobs_when_history_is_available(self):
        for path, digest in PINNED.items():
            with self.subTest(path=path):
                blob = _git_show(ORIGINAL_COMMIT, path)
                if blob is None:
                    self.skipTest(f"{ORIGINAL_COMMIT[:12]} unreachable; ORIGINAL_ENTRIES stands alone")
                self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, "pinned original content changed")
                embedded = {key: set(values) for key, values in ORIGINAL_ENTRIES[path].items()}
                self.assertEqual(entry_sets(blob.decode("utf-8")), embedded)

    def test_growth_check_does_not_need_git_history(self):
        with unittest.mock.patch(__name__ + "._git_show", side_effect=AssertionError("git history read")):
            self.test_ceilings_never_grow_beyond_original_plus_reviewed_delta()

    def test_growth_check_rejects_an_entry_beyond_the_embedded_original(self):
        path = "routes/AUTHORITY_ALLOWLIST.ceiling.json"
        original = {key: set(values) for key, values in ORIGINAL_ENTRIES[path].items()}
        current = entry_sets((REPO_ROOT / path).read_text(encoding="utf-8"))
        current["unbound"] = current["unbound"] | {"POST /api/sneaked-in"}
        self.assertEqual(growth(original, current, DELIBERATE_DELTA[path]), ["unbound: POST /api/sneaked-in"])

    def test_every_ceiling_equals_its_reviewed_snapshot(self):
        self.assertEqual(sorted(CEILING_SNAPSHOT), ceiling_files())
        for path in ceiling_files():
            with self.subTest(path=path):
                data = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
                self.assertEqual(snapshot_of(data), CEILING_SNAPSHOT[path],
                                 "a ceiling changed: shrink it and its snapshot together in one reviewed commit")

    def test_snapshot_never_exceeds_original_plus_delta(self):
        for path in PINNED:
            with self.subTest(path=path):
                original = {key: set(values) for key, values in ORIGINAL_ENTRIES[path].items()}
                snapshot = {key: set(values) for key, values in CEILING_SNAPSHOT[path].items() if isinstance(values, list)}
                self.assertEqual(growth(original, snapshot, DELIBERATE_DELTA.get(path, {})), [])

    def test_shrunk_entries_cannot_regrow_even_if_the_original_allowed_them(self):
        path = "src/components/UNREACHABLE_BASELINE.ceiling.json"
        data = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
        regrown = dict(data, paths=data["paths"] + ["src/components/CNLSFittingStudio.tsx"])
        original = {key: set(values) for key, values in ORIGINAL_ENTRIES[path].items()}
        self.assertEqual(growth(original, entry_sets(json.dumps(regrown)), {}), [], "the original alone would allow it")
        self.assertNotEqual(snapshot_of(regrown), CEILING_SNAPSHOT[path], "the snapshot does not")

    def test_forbidden_entries_never_return(self):
        for path in ceiling_files():
            with self.subTest(path=path):
                data = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
                values = {entry for value in data.values() if isinstance(value, (list, dict)) for entry in value}
                self.assertEqual(values & FORBIDDEN_ENTRIES, set())
                self.assertEqual({entry for value in CEILING_SNAPSHOT[path].values() for entry in value} & FORBIDDEN_ENTRIES, set())
        allowlist = json.loads((REPO_ROOT / "routes" / "AUTHORITY_ALLOWLIST.json").read_text(encoding="utf-8"))
        live = {key for section in allowlist.values() if isinstance(section, dict) for key in section}
        self.assertEqual(live & FORBIDDEN_ENTRIES, set())

    def test_every_ceiling_entry_is_live_or_exists_on_disk(self):
        self.assertEqual(sorted(LIVE_LISTS), ceiling_files())
        for path in ceiling_files():
            with self.subTest(path=path):
                data = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
                self.assertEqual(stale_slots(path, data, live_entries(path)), [], "remove stale ceiling slots (reviewed shrink)")

    def test_stale_slot_logic(self):
        live = {"src/a.ts"}
        data = {"paths": ["src/a.ts", "src/deleted-file.ts", "python/test_allowlist_ceilings.py"], "names": ["module_registry", "gone_module"]}
        self.assertEqual(stale_slots("x", data, live), ["paths: src/deleted-file.ts", "names: gone_module"])

    def test_count_ceilings_never_grow(self):
        for path in ceiling_files():
            with self.subTest(path=path):
                data = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
                self.assertEqual(count_growth(path, data), [])

    def test_count_growth_logic(self):
        path = "routes/AUTHORITY_ALLOWLIST.ceiling.json"
        self.assertEqual(count_growth(path, {"unclassifiedSites": {"USE /api/lpbf": 1}}), [])
        self.assertEqual(count_growth(path, {"unclassifiedSites": {"USE /api/lpbf": 2}}), ["unclassifiedSites: USE /api/lpbf = 2 (cap 1)"])
        self.assertEqual(count_growth(path, {"unclassifiedSites": {"USE /api/new": 1}}), ["unclassifiedSites: USE /api/new = 1 (cap None)"])
        self.assertEqual(count_growth(path, {"other": {"x": 1}}), ["new count key 'other'"])
        self.assertEqual(count_growth("python/module_warm_parity.ceiling.json", {"names": ["a"]}), [])

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


class GuardWiringTests(unittest.TestCase):
    def test_ci_runs_the_base_revision_copy_of_the_checker(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn('git show "$BASE:scripts/check_ceiling_review.py" | python - "$BASE"', workflow)
        self.assertNotIn("run: python scripts/check_ceiling_review.py", workflow)

    def test_codeowners_lists_every_guard_and_ceiling(self):
        owners = {line.split()[0] for line in (REPO_ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.startswith("#")}
        missing = [path for path in (*review.PROTECTED_PATHS, *review.PROTECTED_PREFIXES)
                   if f"/{path}" not in owners]
        self.assertEqual(missing, [])
        self.assertIn("*.ceiling.json", owners)


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
        self._commit("x.ceiling.json", '{"paths": ["a", "b"]}\n', "grow it\n\nCeiling-Review: maintainer approved entry b today")
        self.assertEqual(review.unreviewed_ceiling_changes(self.base, cwd=self.repo), [])

    def test_nested_and_new_ceilings(self):
        self._commit("deep/dir/y.ceiling.json", '{"paths": []}\n', "new ceiling")  # new: pinned by the test above
        self.assertEqual(review.unreviewed_ceiling_changes(self.base, cwd=self.repo), [])
        middle = self._rev()
        self._commit("deep/dir/y.ceiling.json", '{"paths": ["z"]}\n', "grow nested")
        self.assertEqual(len(review.unreviewed_ceiling_changes(middle, cwd=self.repo)), 1)

    def test_only_the_last_commit_touching_a_ceiling_counts(self):
        self._commit("x.ceiling.json", '{"paths": ["a", "b"]}\n', "grow it\n\nCeiling-Review: maintainer approved entry b today")
        self._commit("x.ceiling.json", '{"paths": ["a", "b", "c"]}\n', "sneak c in afterwards")
        problems = review.unreviewed_ceiling_changes(self.base, cwd=self.repo)
        self.assertEqual(len(problems), 1)
        self.assertIn("x.ceiling.json", problems[0])
        # A reviewed last commit covers an earlier unreviewed one (the reviewer sees the result).
        self._commit("x.ceiling.json", '{"paths": ["a", "b"]}\n', "drop c\n\nCeiling-Review: reviewed the final list again")
        self.assertEqual(review.unreviewed_ceiling_changes(self.base, cwd=self.repo), [])

    def test_unrelated_later_commits_do_not_matter(self):
        self._commit("x.ceiling.json", '{"paths": ["a", "b"]}\n', "grow it\n\nCeiling-Review: maintainer approved entry b today")
        self._commit("other.txt", "x\n", "unrelated, no trailer")
        self.assertEqual(review.unreviewed_ceiling_changes(self.base, cwd=self.repo), [])

    def test_guard_files_are_protected_like_ceilings(self):
        self.assertEqual(set(review.PROTECTED_PATHS), {
            "scripts/check_ceiling_review.py", "python/test_allowlist_ceilings.py", ".github/workflows/ci.yml",
            ".github/CODEOWNERS", "tests/support/ceiling.ts", "tests/support/routeScan.ts", "tests/support/importGraph.ts",
            "tests/route-authority.test.ts", "tests/component-reachability.test.ts",
            "python/lpbf_implementation_fingerprint.expected",
            "python/test_lpbf_implementation_fingerprint_pin.py", "python/lpbf_fingerprint_pin.py",
            "python/test_lpbf_implementation_fingerprint.py", "python/test_phase6a_leaf_modules.py",
            "python/tools/lpbf_parity_check.py"})
        self.assertEqual(set(review.PROTECTED_PREFIXES), {"python/golden/lpbf_parity/"})
        for prefix in review.PROTECTED_PREFIXES:
            self.assertTrue((REPO_ROOT / prefix).is_dir(), f"protected prefix {prefix} does not exist")
        for guard in review.PROTECTED_PATHS:
            self.assertTrue((REPO_ROOT / guard).is_file(), f"protected path {guard} does not exist")
        for guard in review.PROTECTED_PATHS:
            with self.subTest(guard=guard):
                start = self._rev()
                self._commit(guard, f"weakened {guard}\n", "weaken the guard")
                problems = review.unreviewed_ceiling_changes(start, cwd=self.repo)
                self.assertEqual(len(problems), 1)
                self.assertIn(guard, problems[0])
                self._commit(guard, f"reviewed {guard}\n", "edit the guard\n\nCeiling-Review: maintainer approved this guard edit")
                self.assertEqual(review.unreviewed_ceiling_changes(start, cwd=self.repo), [])
                self._commit(guard, f"weakened again {guard}\n", "weaken it after review")
                self.assertEqual(len(review.unreviewed_ceiling_changes(start, cwd=self.repo)), 1)

    def test_protected_prefix_reviews_added_changed_and_removed_files(self):
        golden = f"{review.PROTECTED_PREFIXES[0]}g99_example.json"
        start = self._rev()
        self._commit(golden, "{}\n", "add a golden without review")  # new below the prefix
        problems = review.unreviewed_ceiling_changes(start, cwd=self.repo)
        self.assertEqual(len(problems), 1)
        self.assertIn(golden, problems[0])
        self._commit(golden, "{}\n\n", "re-record\n\nCeiling-Review: deliberate parity golden re-record")
        self.assertEqual(review.unreviewed_ceiling_changes(start, cwd=self.repo), [])
        middle = self._rev()
        subprocess.run(["git", "rm", "-q", golden], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "drop a golden"], cwd=self.repo, check=True, capture_output=True)
        problems = review.unreviewed_ceiling_changes(middle, cwd=self.repo)
        self.assertEqual(len(problems), 1)
        self.assertIn(golden, problems[0])
        self.assertFalse(review.is_protected("python/golden/other/x.json"))
        self.assertFalse(review.is_protected("python/golden/lpbf_parity"))

    def test_merge_taking_the_reviewed_branch_version_is_not_the_last_change(self):
        def run(*args):
            return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout.strip()
        main = run("branch", "--show-current")
        run("checkout", "-q", "-b", "feature")
        self._commit("x.ceiling.json", '{"paths": []}\n', "shrink\n\nCeiling-Review: shrink only, nothing added")
        run("checkout", "-q", main)
        self._commit("other.txt", "x\n", "main moves on")
        run("merge", "-q", "--no-ff", "-m", "merge: feature", "feature")
        self.assertEqual(review.unreviewed_ceiling_changes(self.base, cwd=self.repo), [])

    def test_ci_form_runs_the_base_copy_from_stdin(self):
        # CI: git show "$BASE:scripts/check_ceiling_review.py" | python - "$BASE"
        script = (REPO_ROOT / "scripts" / "check_ceiling_review.py").read_text(encoding="utf-8")
        self._commit("x.ceiling.json", '{"paths": ["a", "b"]}\n', "grow it")
        run = subprocess.run([sys.executable, "-", self.base], input=script, cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("x.ceiling.json", run.stderr)
        self._commit("x.ceiling.json", '{"paths": ["a"]}\n', "shrink\n\nCeiling-Review: maintainer approved the final list")
        run = subprocess.run([sys.executable, "-", self.base], input=script, cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_trailer_parser(self):
        self.assertTrue(review.has_review_trailer("subject\n\nCeiling-Review: shrink only, nothing added"))
        self.assertTrue(review.has_review_trailer("subject\n\nbody\n\nCeiling-Review: four words of reason\nCo-Authored-By: X <x@example.invalid>"))
        self.assertFalse(review.has_review_trailer("subject mentions Ceiling-Review: inline"))
        self.assertFalse(review.has_review_trailer("subject\n\nCeiling-Review:   "))
        # Too short, punctuation only, or outside the trailer block (git interpret-trailers --parse).
        self.assertFalse(review.has_review_trailer("subject\n\nCeiling-Review: reason"))
        self.assertFalse(review.has_review_trailer("subject\n\nCeiling-Review: . . . ."))
        self.assertFalse(review.has_review_trailer("subject\n\nCeiling-Review: approved by maintainer today\n\nA later paragraph that is not a trailer block."))

    def test_short_reason_fails(self):
        self._commit("x.ceiling.json", '{"paths": ["a", "b"]}\n', "grow it\n\nCeiling-Review: ok")
        self.assertEqual(len(review.unreviewed_ceiling_changes(self.base, cwd=self.repo)), 1)

    def test_renamed_ceiling_is_reviewed_under_its_old_path(self):
        subprocess.run(["git", "mv", "x.ceiling.json", "renamed.ceiling.json"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "rename the ceiling"], cwd=self.repo, check=True, capture_output=True)
        problems = review.unreviewed_ceiling_changes(self.base, cwd=self.repo)
        self.assertEqual(len(problems), 1)
        self.assertIn("x.ceiling.json", problems[0])
        # A renamed guard file is caught the same way.
        start = self._rev()
        guard = review.PROTECTED_PATHS[0]
        self._commit(guard, "guard\n", "add guard\n\nCeiling-Review: maintainer approved this guard file")
        middle = self._rev()
        Path(self.repo, "moved").mkdir()
        subprocess.run(["git", "mv", guard, "moved/guard.py"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "move the guard away"], cwd=self.repo, check=True, capture_output=True)
        self.assertEqual(len(review.unreviewed_ceiling_changes(middle, cwd=self.repo)), 1)
        self.assertNotEqual(start, middle)


if __name__ == "__main__":
    unittest.main()
