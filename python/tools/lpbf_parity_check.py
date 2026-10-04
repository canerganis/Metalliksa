#!/usr/bin/env python3
"""LPBF 5c parity harness: bit-equality goldens for the planned fingerprint bump.

Design: docs/LPBF_5C_FINGERPRINT_BUMP_DESIGN_2026-10-04.md, section 2 and stage P
(P2 parity harness, P3 material and case-generation goldens). The goldens are
recorded ONCE at the pre-bump implementation (fingerprint 7482697c...). After
every bump commit, ``--check`` must stay green: the cleanup is accepted only if
every observation below is bit-equal.

What "bit-equal" means (design 2.1):
- A run() result is compared after removing provenance.createdAt, runtime_s
  (top level or provenance), the worker-only fields provenance.executionRuntime,
  runKind and the input.json / capabilities.json artifact entries. Everything
  else is hashed as canonical JSON (sort_keys=True, allow_nan=False) AND as an
  insertion-ordered, type-tagged tree (int vs float, tuple vs list, exact float
  bits), so key order and Python types are pinned as well.
- provenance.implementationHash is compared separately: it must equal the pinned
  python/lpbf_implementation_fingerprint.expected value. It is the only value
  that may differ from the golden, and only at the bump.
- Every artifact file written by run() is compared by SHA-256; every NPZ is also
  compared array by array (dtype, shape, bytes).

Cases (design 2.3 matrix): G1..G12 plus an NPZ determinism check. G2 (the in-repo
real bare-plate 100 W fixture) takes about 106 s on the reference machine and is
opt-in (--slow or --case). Everything else runs in about one minute.

Usage (from python/, locked interpreter, PYTHONDONTWRITEBYTECODE=1):
    python -B tools/lpbf_parity_check.py --list
    python -B tools/lpbf_parity_check.py --check [--slow] [--case ID ...]
    python -B tools/lpbf_parity_check.py --record --force [--twice] [--slow] [--case ID ...]

--record refuses to overwrite an existing golden without --force, and refuses to
record at all unless implementation_fingerprint() equals the pinned .expected
value (so goldens are never captured from an unpinned implementation). --twice
runs every case twice in different work directories and refuses to write unless
both runs are identical (determinism and work-directory independence).

Platform note: goldens are recorded on Windows with the locked py312 runtime
(numpy 2.2.6). G10 file trees are written with Path.write_text and therefore
carry platform newlines; a check on another platform reports that explicitly.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

PYTHON_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PYTHON_DIR.parent
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import numpy as np  # noqa: E402

GOLDEN_DIR = PYTHON_DIR / "golden" / "lpbf_parity"
EXPECTED_FINGERPRINT_FILE = PYTHON_DIR / "lpbf_implementation_fingerprint.expected"
DEFAULT_WORK_ROOT = PYTHON_DIR / ".tmp-lpbf-parity"  # ignored by /python/.tmp-*/
GOLDEN_SCHEMA = "lpbf-parity-golden-1"
FIXTURE_CAPTURE = REPO_ROOT / "tests" / "fixtures" / "lpbf-real-bare-plate-100W-capture.json"
FIXTURE_NPZ = REPO_ROOT / "tests" / "fixtures" / "lpbf-real-bare-plate-100W-section-fields.npz"
CORRIDOR_NPZ = "rectangular-corridor-section-fields.npz"
# Artifact entries added by the worker (lpbf_worker.py), never by run() itself.
WORKER_ONLY_ARTIFACTS = ("capabilities.json", "input.json")

# V1 acceptance case, byte-exact inputJson of archived run 318937f610074c1b8d43ea93273b87eb
# (066b6b9 PHASE2 bundle; replayed for V1 as job 50a98fa4...). sha256 = fc8325d9...
V1_INPUT_JSON = (
    '{"absorptivity":0.38,"backend":"reference","barePlateGeometry":"square","beamDiameter_um":80,'
    '"convection_W_m2K":20,"cooling_s":0.0005,"dwell_s":0.0002,"emissivity":0.35,'
    '"evaporationModel":false,"hatch_um":80,"islandSize_um":200,"layerRotation_deg":67,'
    '"layer_um":20,"layers":1,"marangoniMultiplier":2.2,"material":"Inconel 718","maxDt_s":1e-06,'
    '"mesh_um":20,"mode":"standard","opticalObserver":null,"packingFraction":0.55,'
    '"powderConductivityRatio":0.12,"powderGridPolicy":"layer-conforming","power_W":60,'
    '"preheat_C":200,"scanAngle_deg":0,"sourcePenetration_um":null,"speed_mm_s":1200,'
    '"strategy":"stripe","stripeWidth_um":500,"study":"none","surfaceMode":"powder-layer",'
    '"timeout_s":300,"trackLength_um":600,"tracks":1}'
)
V1_INPUT_SHA256 = "fc8325d91b01ca02043cf0fa963396a58f6a4dab428559b63f732f46538db6da"
# strip_result() canonical digest of that archived run's resultJson (resultJson bytes sha256
# a9761a1a4464714ef2fbd4da1ceb54265d96e8f06ae511f14e55b2d0b7270ab9, worker run at 066b6b9,
# implementationHash 7482697c...). A direct run() at the pre-bump HEAD reproduces it exactly.
V1_ARCHIVED_RESULT_STRIPPED_SHA256 = "3eed50effcb82e8cffce55f2a24816cee37e634bb92aa4127be46f1c23a88f83"

# Small powder case shared with test_lpbf_engineering.CASE.
SMALL = dict(mode="standard", backend="reference", power_W=40, mesh_um=40, trackLength_um=200,
             cooling_s=.0001, dwell_s=0)
# Observer case shared with test_lpbf_fixed_event_time_history_observer.SMALL_CASE.
OBSERVER_CASE = {"mode": "standard", "backend": "reference", "material": "Inconel 718",
                 "power_W": 60, "speed_mm_s": 1200, "mesh_um": 40, "maxDt_s": 2e-7,
                 "layer_um": 80, "trackLength_um": 100, "cooling_s": 0, "dwell_s": 0}
# Layered-plate case shared with test_lpbf_layered_plate_solver.LAYERED.
LAYERED = dict(
    mode="standard", backend="reference", surfaceMode="bare-plate",
    barePlateGeometry="square", study="none", layers=1, tracks=1,
    scanAngle_deg=0, mesh_um=20, beamDiameter_um=20, trackLength_um=100,
    power_W=50, speed_mm_s=10000, maxDt_s=1e-5, sourcePenetration_um=20,
    thermalModelId="layered-plate-enthalpy-v1", plateThickness_um=20,
    supportThickness_um=20, contactResistance_m2K_W=1e-4,
    supportBottomBoundary="adiabatic", incidenceAngle_deg=10,
    incidenceAzimuth_deg=0,
    beamProfileModelId="assumed-oblique-gaussian-normal-plane-v1",
)


# --------------------------------------------------------------------------- digests

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    """Design 2.1 comparison form: canonical JSON, sort_keys=True, allow_nan=False."""
    return sha256_bytes(json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8"))


def typed_tree(value: Any) -> Any:
    """Insertion-ordered, type-tagged tree: pins key order, int/float, tuple/list, float bits."""
    kind = type(value)
    if value is None:
        return None
    if kind is bool:
        return {"bool": value}
    if kind is int:
        return {"int": str(value)}
    if kind is float:
        return {"float": value.hex()}
    if kind is str:
        return {"str": value}
    if kind is dict:
        return {"dict": [[typed_tree(k), typed_tree(v)] for k, v in value.items()]}
    if kind is list:
        return {"list": [typed_tree(v) for v in value]}
    if kind is tuple:
        return {"tuple": [typed_tree(v) for v in value]}
    if isinstance(value, types.MappingProxyType):
        return {"mappingproxy": [[typed_tree(k), typed_tree(v)] for k, v in value.items()]}
    if isinstance(value, np.ndarray):
        array = np.ascontiguousarray(value)
        return {"ndarray": [array.dtype.str, list(array.shape), sha256_bytes(array.tobytes())]}
    if isinstance(value, np.generic):
        return {"numpy-scalar": [value.dtype.str, value.tobytes().hex()]}
    if isinstance(value, (set, frozenset)):
        items = sorted((typed_tree(v) for v in value), key=lambda item: json.dumps(item, sort_keys=True))
        return {kind.__name__: items}
    tag = f"{kind.__module__}.{kind.__qualname__}"
    if isinstance(value, dict):
        return {tag: [[typed_tree(k), typed_tree(v)] for k, v in value.items()]}
    if isinstance(value, (list, tuple)):
        return {tag: [typed_tree(v) for v in value]}
    if isinstance(value, (int, float, str)):
        return {tag: repr(value)}
    raise TypeError(f"No typed parity encoding for {tag}")


def typed_sha256(value: Any) -> str:
    return sha256_bytes(json.dumps(typed_tree(value), separators=(",", ":"),
                                   ensure_ascii=True, allow_nan=False).encode("ascii"))


def error_text(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def capture_call(function: Callable[[], Any]) -> Tuple[str, Any]:
    """Return ("ok", value) or ("error", "Type: message"); errors are observations too."""
    try:
        return "ok", function()
    except Exception as exc:  # noqa: BLE001 - the error text itself is pinned
        return "error", error_text(exc)


def observe_value(observations: Dict[str, Any], key: str, function: Callable[[], Any]) -> None:
    status, value = capture_call(function)
    observations[key] = typed_sha256(value) if status == "ok" else {"error": value}


def each(function: Callable[[Any], Any], items) -> List[Any]:
    """Per-item [status, value]: one out-of-range point must not hide the others."""
    return [list(capture_call(lambda item=item: function(item))) for item in items]


# --------------------------------------------------------------------------- result handling

def strip_result(result: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """Remove the design-2.1 volatile and worker-only fields; return (stripped, implementationHash)."""
    stripped = copy.deepcopy(result)
    implementation = None
    provenance = stripped.get("provenance")
    if isinstance(provenance, dict):
        implementation = provenance.pop("implementationHash", None)
        for key in ("createdAt", "runtime_s", "executionRuntime"):
            provenance.pop(key, None)
    stripped.pop("runtime_s", None)
    stripped.pop("runKind", None)
    if isinstance(stripped.get("artifacts"), list):
        stripped["artifacts"] = [item for item in stripped["artifacts"]
                                 if not (isinstance(item, dict) and item.get("path") in WORKER_ONLY_ARTIFACTS)]
    return stripped, implementation


def npz_observations(path: Path, prefix: str) -> Dict[str, Any]:
    observations: Dict[str, Any] = {}
    with np.load(path, allow_pickle=False) as archive:
        observations[f"{prefix}.arrayNames"] = list(archive.files)
        for name in archive.files:
            array = np.ascontiguousarray(archive[name])
            observations[f"{prefix}.array.{name}"] = [array.dtype.str, list(array.shape),
                                                      sha256_bytes(array.tobytes())]
    return observations


def artifact_observations(artifact_dir: Path) -> Dict[str, Any]:
    observations: Dict[str, Any] = {}
    files = sorted(p for p in artifact_dir.rglob("*") if p.is_file())
    names = [p.relative_to(artifact_dir).as_posix() for p in files]
    observations["artifacts.files"] = [n for n in names if n not in WORKER_ONLY_ARTIFACTS]
    for path, name in zip(files, names):
        if name in WORKER_ONLY_ARTIFACTS:
            continue
        data = path.read_bytes()
        observations[f"artifact.{name}"] = [len(data), sha256_bytes(data)]
        if name.endswith(".npz"):
            observations.update(npz_observations(path, f"npz.{name}"))
    return observations


def result_observations(result: Dict[str, Any], artifact_dir: Optional[Path],
                        prefix: str = "result") -> Tuple[Dict[str, Any], Optional[str]]:
    stripped, implementation = strip_result(result)
    observations: Dict[str, Any] = {
        f"{prefix}.canonicalSha256": canonical_json_sha256(stripped),
        f"{prefix}.orderedTypedSha256": typed_sha256(stripped),
        f"{prefix}.topLevelKeys": list(stripped),
    }
    for key, value in stripped.items():
        observations[f"{prefix}.key.{key}"] = canonical_json_sha256(value)
    contract = stripped.get("coreContract")
    if isinstance(contract, dict):
        for key in ("inputSha256", "materialSha256", "solverId", "modelId"):
            if key in contract:
                observations[f"{prefix}.coreContract.{key}"] = contract[key]
    material = stripped.get("material")
    if isinstance(material, dict) and "materialRevisionSha256" in material:
        observations[f"{prefix}.material.materialRevisionSha256"] = material["materialRevisionSha256"]
    for key in ("validationStatus", "productionReady", "effectiveMode", "label", "confidence"):
        if key in stripped:
            observations[f"{prefix}.{key}"] = stripped[key]
    # The fingerprint must live only in provenance.implementationHash; if it were embedded
    # anywhere else the stripped digests would move at the bump for a non-numerical reason.
    if implementation:
        observations[f"{prefix}.implementationHashOccurrencesAfterStrip"] = json.dumps(
            stripped, allow_nan=False).count(implementation)
    if artifact_dir is not None:
        artifacts = artifact_observations(artifact_dir)
        observations.update({f"{prefix}.{k}" if prefix != "result" else k: v for k, v in artifacts.items()})
        listed = {item["path"]: item.get("sha256") for item in stripped.get("artifacts", [])
                  if isinstance(item, dict) and "path" in item}
        on_disk = {name: hashlib.sha256((artifact_dir / name).read_bytes()).hexdigest()
                   for name in listed if (artifact_dir / name).is_file()}
        observations[f"{prefix}.artifactsListedMatchDisk"] = (on_disk == listed)
        if implementation:
            needle = implementation.encode("ascii")
            observations[f"{prefix}.artifactsImplementationHashOccurrences"] = sum(
                path.read_bytes().count(needle) for path in artifact_dir.rglob("*") if path.is_file())
    return observations, implementation


# --------------------------------------------------------------------------- case context

class CaseContext:
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.implementation_hashes: List[str] = []
        self.notes: List[str] = []

    def new_dir(self, name: str) -> Path:
        path = self.work_dir / name
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
        return path

    def run_case(self, raw: Dict[str, Any], *, artifacts: bool = False, prefix: str = "result",
                 **kwargs) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        from lpbf_simulation import run
        artifact_dir = self.new_dir(prefix.replace(".", "-")) if artifacts else None
        result = run(copy.deepcopy(raw), artifact_dir=artifact_dir, **kwargs)
        observations, implementation = result_observations(result, artifact_dir, prefix)
        if implementation is not None:
            self.implementation_hashes.append(implementation)
        return result, observations


# --------------------------------------------------------------------------- cases

def case_g1_v1_60w(ctx: CaseContext) -> Dict[str, Any]:
    if sha256_bytes(V1_INPUT_JSON.encode("utf-8")) != V1_INPUT_SHA256:
        raise AssertionError("embedded V1 inputJson no longer matches its archived sha256")
    _, observations = ctx.run_case(json.loads(V1_INPUT_JSON), artifacts=True)
    observations["v1Archive.strippedResultEqual"] = (
        observations["result.canonicalSha256"] == V1_ARCHIVED_RESULT_STRIPPED_SHA256)
    return observations


def _fixture() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    capture = json.loads(FIXTURE_CAPTURE.read_text(encoding="utf-8"))
    return capture, json.loads(capture["resultJson"])


def case_g2_bare_plate_fixture(ctx: CaseContext) -> Dict[str, Any]:
    """Real bare-plate 100 W corridor job 7ec9dc57...: rerun and compare with the in-repo fixture."""
    capture, reference = _fixture()
    result, observations = ctx.run_case(json.loads(capture["inputJson"]), artifacts=True)
    artifact_dir = ctx.work_dir / "result"
    run_stripped, _ = strip_result(result)
    reference_stripped, reference_hash = strip_result(reference)
    observations["fixture.strippedResultEqual"] = (
        canonical_json_sha256(run_stripped) == canonical_json_sha256(reference_stripped))
    # No ordered/typed comparison with the fixture: the worker passed the original request
    # dict, whose key order (not the implementation) sets the order of extra settings keys,
    # and the fixture went through JSON (tuples become lists). Canonical equality is the
    # design-2.1 criterion; the ordered/typed digest of this direct run is pinned above.
    observations["fixture.recordedImplementationHash"] = reference_hash
    compared, mismatched = 0, []
    for item in reference.get("artifacts", []):
        name = item["path"]
        if name in WORKER_ONLY_ARTIFACTS:
            continue
        compared += 1
        path = artifact_dir / name
        if not path.is_file() or sha256_bytes(path.read_bytes()) != item["sha256"]:
            mismatched.append(name)
    observations["fixture.artifactsCompared"] = compared
    observations["fixture.artifactsMismatched"] = mismatched
    observations["fixture.fieldArtifactsCompared"] = sum(
        1 for item in reference.get("artifacts", [])
        if item["path"] not in WORKER_ONLY_ARTIFACTS and item["path"] != CORRIDOR_NPZ)
    observations["fixture.npzBytesEqual"] = (
        (artifact_dir / CORRIDOR_NPZ).read_bytes() == FIXTURE_NPZ.read_bytes())
    observations["fixture.inputSha256Equal"] = (
        result["coreContract"]["inputSha256"] == reference["coreContract"]["inputSha256"])
    observations["fixture.materialSha256Equal"] = (
        result["coreContract"]["materialSha256"] == reference["coreContract"]["materialSha256"])
    return observations


def case_g3_powder_stripe_multilayer(ctx: CaseContext) -> Dict[str, Any]:
    raw = {**SMALL, "strategy": "stripe", "tracks": 2, "layers": 2, "stripeWidth_um": 100,
           "dwell_s": 2e-5, "scanAngle_deg": 35, "layerRotation_deg": 67}
    _, observations = ctx.run_case(raw, artifacts=True)
    return observations


def case_g3_powder_island(ctx: CaseContext) -> Dict[str, Any]:
    raw = {**SMALL, "strategy": "island", "islandSize_um": 100, "tracks": 2, "layers": 1,
           "dwell_s": 1e-5}
    _, observations = ctx.run_case(raw)
    return observations


def case_g4_layered_plate(ctx: CaseContext) -> Dict[str, Any]:
    _, observations = ctx.run_case(LAYERED)
    return observations


def case_g5_evaporation(ctx: CaseContext) -> Dict[str, Any]:
    _, observations = ctx.run_case({**SMALL, "power_W": 80, "evaporationModel": True})
    # Proof that the opt-in path is exercised: the same case without it must differ.
    # At 80 W the baseline stops at the boiling validity limit (fail closed); that error text
    # is pinned too, so this case also covers the boiling STOP message.
    status, baseline = capture_call(lambda: ctx.run_case(
        {**SMALL, "power_W": 80, "evaporationModel": False}, prefix="baseline")[1])
    observations["baseline"] = (baseline["baseline.canonicalSha256"] if status == "ok"
                                else {"error": baseline})
    observations["evaporation.differsFromBaseline"] = (
        status != "ok" or observations["result.canonicalSha256"] != baseline["baseline.canonicalSha256"])
    return observations


def case_g6_screening_and_fallback(ctx: CaseContext) -> Dict[str, Any]:
    observations: Dict[str, Any] = {}
    for prefix, raw in (("screening", {"mode": "screening"}),
                        ("highFidelityFallback", {"mode": "high-fidelity"}),
                        ("screeningTi64", {"mode": "screening", "material": "Ti-6Al-4V",
                                           "power_W": 180, "speed_mm_s": 900})):
        _, part = ctx.run_case(raw, prefix=prefix)
        observations.update(part)
    return observations


def case_g7_mesh_study(ctx: CaseContext) -> Dict[str, Any]:
    _, observations = ctx.run_case({**SMALL, "power_W": 10, "study": "mesh"})
    return observations


def _observer_rejections() -> Dict[str, Any]:
    from lpbf_simulation import run, validate, scan_segments
    from lpbf_run_progress import CpuRunProgress

    def sink(_payload):
        return None

    p, _ = validate(OBSERVER_CASE)
    event = scan_segments(p)[0][0]["end_s"]
    bare = {"mode": "standard", "backend": "reference", "surfaceMode": "bare-plate",
            "sourcePenetration_um": 40, "mesh_um": 40, "trackLength_um": 100}
    attempts = {
        "finalState.screening": lambda: run({"mode": "screening"}, final_state_observer=sink),
        "finalState.meshStudy": lambda: run({**OBSERVER_CASE, "study": "mesh"}, final_state_observer=sink),
        "finalState.barePlate": lambda: run(bare, final_state_observer=sink),
        "finalState.layered": lambda: run(LAYERED, final_state_observer=sink),
        "finalState.notCallable": lambda: run(OBSERVER_CASE, final_state_observer=123),
        "finalStateBeforeSelectedTime.screening": lambda: run(
            {"mode": "screening"}, final_state_observer=sink, selected_time_observer=sink,
            selected_time_s=event),
        "selectedTime.barePlate": lambda: run(bare, selected_time_observer=sink, selected_time_s=event),
        "selectedTime.notEvent": lambda: run(OBSERVER_CASE, selected_time_observer=sink,
                                             selected_time_s=event * 0.5),
        "selectedTime.withoutObserver": lambda: run(OBSERVER_CASE, selected_time_s=event),
        "selectedTime.notCallable": lambda: run(OBSERVER_CASE, selected_time_observer="x",
                                                selected_time_s=event),
        "localHistory.screening": lambda: run({"mode": "screening"}, local_history_observer=sink,
                                              local_history_indices_ijk=[(0, 0, 0)]),
        "localHistory.indicesWithoutObserver": lambda: run(OBSERVER_CASE,
                                                           local_history_indices_ijk=[(0, 0, 0)]),
        "localHistory.missingIndices": lambda: run(OBSERVER_CASE, local_history_observer=sink),
        "localHistory.duplicateIndices": lambda: run(OBSERVER_CASE, local_history_observer=sink,
                                                     local_history_indices_ijk=[(0, 0, 0), (0, 0, 0)]),
        "localHistory.badTriple": lambda: run(OBSERVER_CASE, local_history_observer=sink,
                                              local_history_indices_ijk=[(0, 0)]),
        "runProgress.screening": lambda: run({"mode": "screening"}, run_progress=CpuRunProgress()),
        "runProgress.openfoam": lambda: run({**OBSERVER_CASE, "backend": "openfoam-thermal"},
                                            run_progress=CpuRunProgress()),
        "runProgress.meshStudy": lambda: run({**OBSERVER_CASE, "study": "mesh"},
                                             run_progress=CpuRunProgress()),
        "validate.cfdBackend": lambda: run({"backend": "openfoam-cfd"}),
        "validate.unknownField": lambda: run({"notAField": 1}),
    }
    observations: Dict[str, Any] = {}
    for label, attempt in attempts.items():
        status, value = capture_call(attempt)
        observations[f"reject.{label}"] = value if status == "error" else "NO-ERROR"
    return observations


def case_g8_observers(ctx: CaseContext) -> Dict[str, Any]:
    from lpbf_simulation import validate, scan_segments
    from lpbf_run_progress import CpuRunProgress

    p, _ = validate(OBSERVER_CASE)
    event = scan_segments(p)[0][0]["end_s"]
    final_states: List[Any] = []
    selected: List[Any] = []
    history_digest = hashlib.sha256()
    history_count = [0]
    progress_digest = hashlib.sha256()
    progress_count = [0]

    def history(record):
        history_count[0] += 1
        history_digest.update(typed_sha256(record).encode("ascii"))

    def progress(snapshot):
        progress_count[0] += 1
        progress_digest.update(typed_sha256(snapshot).encode("ascii"))

    tracker = CpuRunProgress(observer=progress)
    _, observations = ctx.run_case(
        OBSERVER_CASE, final_state_observer=final_states.append,
        selected_time_observer=selected.append, selected_time_s=event,
        local_history_observer=history, local_history_indices_ijk=[(0, 0, 0), (1, 0, 1)],
        run_progress=tracker)
    observations["observer.finalState.count"] = len(final_states)
    observations["observer.finalState.typedSha256"] = [typed_sha256(item) for item in final_states]
    observations["observer.selectedTime.count"] = len(selected)
    observations["observer.selectedTime.typedSha256"] = [typed_sha256(item) for item in selected]
    observations["observer.localHistory.count"] = history_count[0]
    observations["observer.localHistory.chainSha256"] = history_digest.hexdigest()
    observations["observer.runProgress.count"] = progress_count[0]
    observations["observer.runProgress.chainSha256"] = progress_digest.hexdigest()
    observations["observer.runProgress.finalSnapshot"] = typed_sha256(tracker.snapshot())
    # Plain run of the same case: observers must not change the result.
    _, plain = ctx.run_case(OBSERVER_CASE, prefix="plain")
    observations["plain.canonicalSha256"] = plain["plain.canonicalSha256"]
    observations.update(_observer_rejections())
    return observations


def case_g9_material_snapshots(ctx: CaseContext) -> Dict[str, Any]:
    import four_alloy_materials as fam
    import lpbf_material_registry as registry
    import in625_thermal_material as in625
    import in625_gpu_thermal_material as in625_gpu
    import lpbf_ss304_support_material as ss304
    from lpbf_core_physics import enthalpy_table, property_at

    observations: Dict[str, Any] = {}
    names = [item["name"] for item in registry.catalog()]
    observe_value(observations, "registry.catalog", registry.catalog)
    observations["registry.VERSION"] = registry.VERSION
    for name in names + ["IN625", "inconel 718", "ti64", "Unobtainium"]:
        observe_value(observations, f"registry.material.{name}", lambda name=name: registry.material(name))
        status, value = capture_call(lambda name=name: registry.material(name))
        if status == "ok":
            observations[f"registry.material.{name}.json"] = sha256_bytes(
                json.dumps(value, allow_nan=False).encode("utf-8"))
            if "materialRevisionSha256" in value:
                observations[f"registry.material.{name}.materialRevisionSha256"] = value["materialRevisionSha256"]
            observe_value(observations, f"core.enthalpyTable.{name}", lambda value=value: enthalpy_table(value))
            grid = np.linspace(250.0, 3600.0, 61)
            for column in (1, 2, 3, 4):
                observe_value(observations, f"core.propertyAt.{name}.{column}",
                              lambda value=value, column=column: property_at(value, grid, column))
    for name in ("Inconel 625", "IN625"):
        observe_value(observations, f"registry.thermalScreeningMaterial.{name}",
                      lambda name=name: registry.thermal_screening_material(name))
        observe_value(observations, f"registry.thermalScreeningAt.{name}",
                      lambda name=name: [registry.thermal_screening_at(name, t) for t in (300.0, 1000.0, 1600.0)])
    for constant in ("FOUR_ALLOY_IDS", "MATERIAL_AUTHORITY", "MATERIAL_AUTHORITY_SCHEMA_VERSION",
                     "THERMAL_NAME", "SLICER_NAME", "ALLOY_MATERIALS", "LITERATURE_PV_WINDOWS",
                     "LITERATURE_MELT_POOL_CASES", "FOUR_ALLOY_U95_BUDGET"):
        observe_value(observations, f"fam.{constant}", lambda constant=constant: getattr(fam, constant))
    observe_value(observations, "fam.four_alloy_thermophysical_db", fam.four_alloy_thermophysical_db)
    observations["fam.four_alloy_thermophysical_db.json"] = sha256_bytes(
        json.dumps(fam.four_alloy_thermophysical_db(), allow_nan=False).encode("utf-8"))
    probe_names = sorted({*fam.FOUR_ALLOY_IDS, *fam.THERMAL_NAME.values(), *fam.SLICER_NAME.values(),
                          "Ti64", "316L", "Inconel 625", "unknown-alloy"})
    for name in probe_names:
        observe_value(observations, f"fam.resolve_alloy_id.{name}", lambda name=name: fam.resolve_alloy_id(name))
        for function in ("thermal_props", "slicer_props", "marangoni_props", "inherent_strain_props"):
            observe_value(observations, f"fam.{function}.{name}",
                          lambda name=name, function=function: getattr(fam, function)(name))
        observe_value(observations, f"fam.canonical_material_source.{name}",
                      lambda name=name: fam.canonical_material_source(name))
    for alloy in fam.FOUR_ALLOY_IDS:
        observations[f"fam.canonical_material_source.{alloy}.sha256"] = fam.canonical_material_source(alloy)[1]
        for prop in ("rho", "cp", "k", "latent", "viscosity", "unknown"):
            observe_value(observations, f"fam.u95.{alloy}.{prop}",
                          lambda alloy=alloy, prop=prop: each(
                              lambda t: fam.four_alloy_u95_at_temperature(alloy, prop, t),
                              (300.0, 900.0, 1500.0, 1600.0, 1700.0, 1950.0, 2500.0)))
        observe_value(observations, f"fam.evaluate_literature_pv.{alloy}",
                      lambda alloy=alloy: [fam.evaluate_literature_pv(alloy, power, speed)
                                           for power in (100.0, 150, 200.0, 300, 400.0)
                                           for speed in (500, 800.0, 1000, 1500.0)])
    observe_value(observations, "fam.evaluate_literature_pv.unknownDefaultsToIn718",
                  lambda: fam.evaluate_literature_pv("unknown", 200, 800))
    observe_value(observations, "fam.regime_family",
                  lambda: [fam.regime_family(r) for r in ("Keyhole", "transition", "conduction", None, 3)])
    observe_value(observations, "in625.snapshot", in625.in625_lpbf_thermal_snapshot)
    observations["in625.snapshot.materialRevisionSha256"] = in625.in625_lpbf_thermal_snapshot().get(
        "materialRevisionSha256")
    observe_value(observations, "in625.transientSpecification", in625.in625_transient_material_specification)
    observe_value(observations, "in625.validateScreeningAdmission", in625.validate_in625_screening_admission)
    observe_value(observations, "in625.solidAtCelsius",
                  lambda: [in625.in625_solid_thermal_at_celsius(t) for t in (-18.0, 20.0, 500.0, 982.0)])
    for function in ("in625_lpbf_thermal_at_kelvin", "in625_extended_thermal_at_kelvin"):
        observe_value(observations, f"in625.{function}",
                      lambda function=function: each(getattr(in625, function),
                                                     (300.0, 900.0, 1563.15, 1590.0, 1623.15, 2500.0)))
    observe_value(observations, "in625.U95_BUDGET", lambda: in625.IN625_U95_BUDGET)
    for prop in ("density", "conductivity", "viscosity", "cp"):
        observe_value(observations, f"in625.u95.{prop}",
                      lambda prop=prop: each(lambda t: in625.in625_u95_uncertainty_at_kelvin(t, prop),
                                             (300.0, 1590.0, 2000.0, 3500.0)))
    observe_value(observations, "in625gpu.cpuThermal",
                  lambda: in625_gpu.in625_cpu_thermal_at_kelvin(np.linspace(300.0, 2500.0, 23)))
    observe_value(observations, "ss304.snapshot", ss304.ss304_support_thermal_snapshot)
    observe_value(observations, "ss304.atKelvin",
                  lambda: [ss304.ss304_support_thermal_at_kelvin(t) for t in (273.15, 600.0, 1473.15)])
    observe_value(observations, "ss304.fields",
                  lambda: ss304.ss304_support_thermal_fields(np.linspace(273.15, 1473.15, 13)))
    return observations


def _cfd_case_module():
    """B1 moves the test-only setup functions to lpbf_cfd_cases; resolve by name either way."""
    try:
        import lpbf_cfd_cases as module  # type: ignore[import-not-found]
        return module
    except ImportError:
        import lpbf_cfd as module
        return module


def _tree_observations(root: Path, prefix: str) -> Dict[str, Any]:
    observations: Dict[str, Any] = {}
    files = sorted(p for p in root.rglob("*") if p.is_file())
    observations[f"{prefix}.files"] = [p.relative_to(root).as_posix() for p in files]
    for path in files:
        data = path.read_bytes()
        observations[f"{prefix}.file.{path.relative_to(root).as_posix()}"] = [len(data), sha256_bytes(data)]
    return observations


def case_g10_openfoam_case_generation(ctx: CaseContext) -> Dict[str, Any]:
    import lpbf_cfd
    import lpbf_openfoam
    from lpbf_simulation import validate

    cases_module = _cfd_case_module()
    observations: Dict[str, Any] = {"platform.newline": repr(os.linesep)}
    for name in ("setup_droplet_case", "setup_stefan_case", "setup_darcy_damping_case",
                 "setup_thermal_parity_case", "setup_marangoni_case", "setup_recoil_case",
                 "setup_laser_case"):
        folder = ctx.new_dir(f"cfd-{name}")
        status, value = capture_call(lambda name=name, folder=folder: getattr(cases_module, name)(folder))
        observations[f"cfd.{name}.return"] = typed_sha256(_relative(value, folder)) if status == "ok" else {"error": value}
        observations.update(_tree_observations(folder, f"cfd.{name}"))
    observe_value(observations, "cfd.stefan_analytical_solution",
                  lambda: [cases_module.stefan_analytical_solution(t) for t in (1e-7, 1e-6, 5e-6, 1e-5)])
    observe_value(observations, "cfd.knight_analytical_recoil_pressure",
                  lambda: [cases_module.knight_analytical_recoil_pressure(t) for t in (2500.0, 3000.0, 3560.0, 4000.0)])
    p, m = validate({**SMALL, "tracks": 2, "layers": 1})
    folder = ctx.new_dir("cfd-multiphysics")
    status, value = capture_call(lambda: lpbf_cfd.setup_cfd_multiphysics_case(p, m, folder))
    observations["cfd.setup_cfd_multiphysics_case.return"] = (
        typed_sha256(_relative(value, folder)) if status == "ok" else {"error": value})
    observations.update(_tree_observations(folder, "cfd.setup_cfd_multiphysics_case"))
    for label, raw in (("powder", {**SMALL, "backend": "openfoam-thermal"}),
                       ("powderMultilayer", {**SMALL, "backend": "openfoam-thermal", "tracks": 2,
                                             "layers": 2, "dwell_s": 2e-5})):
        p, m = validate(raw)
        folder = ctx.new_dir(f"openfoam-{label}")
        status, value = capture_call(lambda p=p, m=m, folder=folder: lpbf_openfoam.generate_case(p, m, folder))
        observations[f"openfoam.generate_case.{label}.return"] = (
            typed_sha256(value) if status == "ok" else {"error": value})
        observations.update(_tree_observations(folder, f"openfoam.generate_case.{label}"))
    return observations


def _relative(value: Any, folder: Path) -> Any:
    """Replace the absolute work folder in returned values so goldens are location-independent."""
    text = str(folder)
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        return value.replace(text, "<CASE>").replace(folder.as_posix(), "<CASE>")
    if isinstance(value, dict):
        return {k: _relative(v, folder) for k, v in value.items()}
    if isinstance(value, list):
        return [_relative(v, folder) for v in value]
    if isinstance(value, tuple):
        return tuple(_relative(v, folder) for v in value)
    return value


G11_PAYLOADS = (
    dict(material_name="Inconel 718", laser_power_W=200.0, scan_speed_mm_s=800.0, beam_diameter_um=80.0,
         preheat_temp_C=80.0, layer_thickness_um=40.0, hatch_spacing_um=100.0, heat_source="rosenthal"),
    dict(material_name="Ti-6Al-4V", laser_power_W=280.0, scan_speed_mm_s=1200.0, beam_diameter_um=70.0,
         preheat_temp_C=200.0, layer_thickness_um=30.0, hatch_spacing_um=120.0, heat_source="eagar-tsai",
         sulfur_ppm=40.0),
    dict(material_name="316L Stainless Steel", laser_power_W=370.0, scan_speed_mm_s=600.0,
         beam_diameter_um=60.0, preheat_temp_C=25.0, layer_thickness_um=50.0, hatch_spacing_um=90.0,
         heat_source="goldak", incline_angle_deg=15.0),
)


def case_g11_build_job_meltpool(ctx: CaseContext) -> Dict[str, Any]:
    from lpbf_thermal_solver import calculate_meltpool_physics, classify_enthalpy_regime, THERMOPHYSICAL_DB

    observations: Dict[str, Any] = {}
    for index, payload in enumerate(G11_PAYLOADS):
        status, value = capture_call(lambda payload=payload: calculate_meltpool_physics(**payload))
        if status == "ok":
            observations[f"meltpool.{index}.typedSha256"] = typed_sha256(value)
            observations[f"meltpool.{index}.canonicalSha256"] = canonical_json_sha256(value)
        else:
            observations[f"meltpool.{index}"] = {"error": value}
    observe_value(observations, "thermalSolver.THERMOPHYSICAL_DB", lambda: THERMOPHYSICAL_DB)
    observe_value(observations, "thermalSolver.classify_enthalpy_regime",
                  lambda: [classify_enthalpy_regime(x) for x in (0.0, 14.99, 15.0, 29.99, 30.0, 80.0)])
    return observations


def case_g12_analytical_modules(ctx: CaseContext) -> Dict[str, Any]:
    import eagar_tsai_solver
    import fabbro_keyhole
    import goldak_solver
    import marangoni_screening
    import solidification_front
    import powder_packer
    from lpbf_thermal_solver import rosenthal_temperature_C

    observations: Dict[str, Any] = {}
    xs = np.linspace(-200e-6, 100e-6, 7)
    ys = np.linspace(0.0, 80e-6, 3)
    zs = np.linspace(-60e-6, 0.0, 3)
    grid = [(float(x), float(y), float(z)) for x in xs for y in ys for z in zs]
    observe_value(observations, "eagarTsai.temperature",
                  lambda: [eagar_tsai_solver.eagar_tsai_temperature_C(x, y, z, 80.0, 76.0, 25.0, 0.8,
                                                                       5.5e-6, 40e-6) for x, y, z in grid])
    observe_value(observations, "rosenthal.temperature",
                  lambda: [rosenthal_temperature_C(x, y, z, 80.0, 76.0, 25.0, 0.8, 5.5e-6, 5e-6)
                           for x, y, z in grid])

    def goldak():
        axes = goldak_solver.seed_goldak_axes(40e-6)
        field = goldak_solver.GoldakField(80.0, 76.0, 8190.0, 435.0, 5.5e-6, **axes).bind_speed(0.8)
        return {"axes": axes, "fractions": goldak_solver.goldak_fractions(40e-6, 80e-6),
                "q": goldak_solver.goldak_q_parameter_W(76.0),
                "temperature": [field.temperature_C(x, y, z) for x, y, z in grid]}
    observe_value(observations, "goldak.field", goldak)
    observe_value(observations, "fabbro.depth",
                  lambda: [fabbro_keyhole.fabbro_keyhole_depth_m(p, v, 80e-6, 25.0, 5.5e-6, 2900.0, 80.0, 0.4, h)
                           for p, v, h in ((100.0, 1.0, 10.0), (200.0, 0.8, 20.0), (370.0, 0.5, 45.0))])
    observe_value(observations, "marangoni.heipleRoper",
                  lambda: [marangoni_screening.heiple_roper_d_gamma_dT(-3.7e-4, s) for s in (0.0, 15.0, 30.0, 45.0, 60.0, 90.0)])
    observe_value(observations, "marangoni.screening",
                  lambda: [marangoni_screening.marangoni_screening(-3.7e-4, 5e-3, 5.5e-6, 7400.0, 50e-6, t, 1336.0, s)
                           for t in (1500.0, 2500.0) for s in (5.0, 45.0, 80.0)])
    observe_value(observations, "solidification.hunt",
                  lambda: [solidification_front.hunt_morphology(x) for x in (1e11, 1e9, 1e8, 1e6, 1e3)])
    observe_value(observations, "solidification.pdas",
                  lambda: [solidification_front.hunt_lu_pdas_um(g, r) for g, r in ((1e6, 0.1), (5e7, 0.5), (1e7, 1.0))])
    observe_value(observations, "solidification.sdas",
                  lambda: [solidification_front.kirkwood_sdas_um(c, 50.0) for c in (1e3, 1e5, 1e7)])
    observe_value(observations, "solidification.phaseNote",
                  lambda: [solidification_front.phase_transformation_note(n, c)
                           for n in ("Ti-6Al-4V", "Inconel 718", "316L Stainless Steel", "AlSi10Mg")
                           for c in (1e2, 1e5, 1e7)])
    field = eagar_tsai_solver.EagarTsaiField(80.0, 76.0, 25.0, 5.5e-6, 40e-6).bind_speed(0.8)

    def evaluate():
        return solidification_front.evaluate_solidification(
            field.temperature_C, T_liq=1336.0, T_sol=1260.0, t_surface=2400.0, v_scan=0.8,
            x_rear=-150e-6, x_front=50e-6, search_depth=80e-6, r_beam=40e-6, cos_theta=1.0,
            pdas_A1=1.0, sdas_B1=50.0, material_name="Inconel 718")
    observe_value(observations, "solidification.evaluate", evaluate)
    # powder_bed_raytracer and warp_thermal_solver import warp at module import; they are
    # GPU-only (design 2.3: GPU numerics are not verifiable here) and are not covered.

    def packing():
        spheres = powder_packer.generate_powder_bed(300e-6, 200e-6, 40e-6, target_packing=0.5, seed=7)
        return {"spheres": spheres,
                "statistics": powder_packer.compute_powder_bed_statistics(spheres, 300e-6, 200e-6, 40e-6),
                "validation": powder_packer.validate_powder_bed(spheres, 300e-6, 200e-6, 40e-6)}
    observe_value(observations, "powderPacker.seeded", packing)
    return observations


def case_npz_determinism(ctx: CaseContext) -> Dict[str, Any]:
    """np.savez_compressed writes the 1980 zip timestamp: identical bytes across time."""
    with np.load(FIXTURE_NPZ, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    first = io.BytesIO()
    np.savez_compressed(first, **arrays)
    time.sleep(2.1)  # zip timestamps have a 2 s resolution
    second = io.BytesIO()
    np.savez_compressed(second, **arrays)
    observations: Dict[str, Any] = {
        "npz.resaveTwiceEqual": first.getvalue() == second.getvalue(),
        "npz.resaveEqualsFixtureBytes": first.getvalue() == FIXTURE_NPZ.read_bytes(),
        "npz.resaveSha256": sha256_bytes(first.getvalue()),
        "npz.fixtureSha256": sha256_bytes(FIXTURE_NPZ.read_bytes()),
    }
    observations.update(npz_observations(FIXTURE_NPZ, "npz.fixture"))
    return observations


class Case:
    def __init__(self, case_id: str, group: str, function: Callable[[CaseContext], Dict[str, Any]],
                 description: str, *, slow: bool = False, runs_solver: bool = True):
        self.id, self.group, self.function, self.description = case_id, group, function, description
        self.slow, self.runs_solver = slow, runs_solver


CASES: Tuple[Case, ...] = (
    Case("g1_v1_60w_in718", "G1", case_g1_v1_60w,
         "V1 acceptance case from the archived inputJson (fc8325d9...), with all artifacts"),
    Case("g2_bare_plate_100w_corridor", "G2", case_g2_bare_plate_fixture,
         "Real bare-plate 100 W corridor job 7ec9dc57...; compared with the in-repo fixture (~106 s)",
         slow=True),
    Case("g3_powder_stripe_multilayer", "G3", case_g3_powder_stripe_multilayer,
         "Two-track two-layer stripe powder run with dwell, scan angle and layer rotation"),
    Case("g3_powder_island", "G3", case_g3_powder_island, "Two-track island powder run with dwell"),
    Case("g4_layered_plate", "G4", case_g4_layered_plate, "layered-plate-enthalpy-v1 with SS304 support"),
    Case("g5_evaporation", "G5", case_g5_evaporation, "evaporationModel=True short powder track"),
    Case("g6_screening_and_fallback", "G6", case_g6_screening_and_fallback,
         "Screening (Goldak/Rosenthal) and the honest high-fidelity fallback"),
    Case("g7_mesh_study", "G7", case_g7_mesh_study, "Smallest layer-aligned three-grid mesh study"),
    Case("g8_observers", "G8", case_g8_observers,
         "final-state, selected-time, local-history observers and CpuRunProgress; rejection messages"),
    Case("g9_material_snapshots", "G9", case_g9_material_snapshots,
         "Material snapshots, four-alloy tables, IN625 and SS304, typed and key-ordered", runs_solver=False),
    Case("g10_openfoam_case_generation", "G10", case_g10_openfoam_case_generation,
         "OpenFOAM case writers (CFD setup_*_case, multiphysics, thermal) file-tree SHA-256", runs_solver=False),
    Case("g11_build_job_meltpool", "G11", case_g11_build_job_meltpool,
         "lpbf_thermal_solver.calculate_meltpool_physics for three fixed payloads", runs_solver=False),
    Case("g12_analytical_modules", "G12", case_g12_analytical_modules,
         "Eagar-Tsai, Rosenthal, Goldak, Fabbro, Marangoni, solidification front", runs_solver=False),
    Case("npz_determinism", "NPZ", case_npz_determinism,
         "np.savez_compressed bytes are time-independent (fixture arrays, 2.1 s apart)", runs_solver=False),
)
CASE_BY_ID = {case.id: case for case in CASES}


# --------------------------------------------------------------------------- record / check

def pinned_fingerprint() -> str:
    text = EXPECTED_FINGERPRINT_FILE.read_text(encoding="ascii").strip()
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise ValueError(f"{EXPECTED_FINGERPRINT_FILE.name} must hold one lowercase sha256 hex line")
    return text


def _git_head() -> Optional[str]:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment() -> Dict[str, Any]:
    return {"python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.system(), "executable": Path(sys.executable).name}


def execute(case: Case, work_root: Path) -> Tuple[Dict[str, Any], List[str], float]:
    work_root.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix=f"{case.id}-", dir=str(work_root)))
    ctx = CaseContext(work_dir)
    started = time.perf_counter()
    try:
        observations = case.function(ctx)
    finally:
        elapsed = time.perf_counter() - started
        shutil.rmtree(work_dir, ignore_errors=True)
    # Round-trip through JSON so record and check compare the same value domain.
    observations = json.loads(json.dumps(observations, allow_nan=False))
    return observations, ctx.implementation_hashes, elapsed


def golden_path(case: Case) -> Path:
    return GOLDEN_DIR / f"{case.id}.json"


def diff_observations(expected: Dict[str, Any], actual: Dict[str, Any]) -> List[str]:
    problems = []
    for key in sorted(set(expected) | set(actual)):
        if key not in actual:
            problems.append(f"missing observation {key}")
        elif key not in expected:
            problems.append(f"unexpected new observation {key}")
        elif expected[key] != actual[key]:
            problems.append(f"changed {key}: expected {json.dumps(expected[key])[:160]} "
                            f"got {json.dumps(actual[key])[:160]}")
    return problems


def check_implementation(case: Case, hashes: List[str], pinned: str, current: str) -> List[str]:
    problems = []
    if current != pinned:
        problems.append(f"implementation_fingerprint() {current} != pinned {pinned}")
    for value in hashes:
        if value != current:
            problems.append(f"result provenance.implementationHash {value} != implementation_fingerprint() {current}")
    if case.runs_solver and not hashes:
        problems.append("solver case produced no provenance.implementationHash")
    return problems


def selected_cases(args) -> List[Case]:
    if args.case:
        unknown = [c for c in args.case if c not in CASE_BY_ID]
        if unknown:
            raise SystemExit(f"unknown case(s): {', '.join(unknown)}")
        return [CASE_BY_ID[c] for c in args.case]
    return [case for case in CASES if args.slow or not case.slow]


def command_record(args) -> int:
    from lpbf_simulation import implementation_fingerprint, VERSION
    current, pinned = implementation_fingerprint(), pinned_fingerprint()
    if current != pinned:
        print(f"REFUSED: implementation_fingerprint() {current} != pinned {pinned}")
        return 2
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for case in selected_cases(args):
        path = golden_path(case)
        if path.exists() and not args.force:
            print(f"{case.id}: golden exists; use --force to overwrite")
            failures += 1
            continue
        observations, hashes, elapsed = execute(case, Path(args.work_root))
        problems = check_implementation(case, hashes, pinned, current)
        runs = [round(elapsed, 1)]
        if args.twice:
            again, hashes_again, elapsed_again = execute(case, Path(args.work_root))
            runs.append(round(elapsed_again, 1))
            problems += check_implementation(case, hashes_again, pinned, current)
            problems += [f"run 2 differs: {p}" for p in diff_observations(observations, again)]
        if problems:
            failures += 1
            print(f"{case.id}: NOT RECORDED")
            for problem in problems:
                print(f"    {problem}")
            continue
        golden = {
            "schema": GOLDEN_SCHEMA, "case": case.id, "group": case.group,
            "description": case.description, "slow": case.slow,
            "recordedImplementationHash": current, "recordedVersion": VERSION,
            "recordedGitHead": _git_head(), "recordedEnvironment": environment(),
            "recordedRuns_s": runs, "recordedTwice": bool(args.twice),
            "observations": observations,
        }
        path.write_text(json.dumps(golden, indent=1, sort_keys=False, allow_nan=False) + "\n",
                        encoding="utf-8", newline="\n")
        print(f"{case.id}: recorded {len(observations)} observations in {'/'.join(map(str, runs))} s")
    return 1 if failures else 0


def check_case(case: Case, work_root: Path) -> Dict[str, Any]:
    """Run one case against its golden; returns problems, observations and timing."""
    from lpbf_simulation import implementation_fingerprint
    path = golden_path(case)
    outcome: Dict[str, Any] = {"case": case.id, "problems": [], "elapsed_s": 0.0,
                               "observations": {}, "golden": None}
    if not path.is_file():
        outcome["problems"] = [f"golden missing: {path}"]
        return outcome
    golden = json.loads(path.read_text(encoding="utf-8"))
    outcome["golden"] = golden
    if golden.get("schema") != GOLDEN_SCHEMA or golden.get("case") != case.id:
        outcome["problems"] = [f"golden {path.name} has the wrong schema or case id"]
        return outcome
    current, pinned = implementation_fingerprint(), pinned_fingerprint()
    observations, hashes, elapsed = execute(case, work_root)
    problems = check_implementation(case, hashes, pinned, current)
    problems += diff_observations(golden["observations"], observations)
    recorded_env = golden.get("recordedEnvironment", {})
    if problems and recorded_env != environment():
        problems.append(f"note: environment differs from the recording {recorded_env} -> {environment()}")
    outcome.update(problems=problems, elapsed_s=elapsed, observations=observations,
                   implementationHashes=sorted(set(hashes)))
    return outcome


def command_check(args) -> int:
    from lpbf_simulation import implementation_fingerprint
    current, pinned = implementation_fingerprint(), pinned_fingerprint()
    print(f"implementation_fingerprint() = {current}  pinned = {pinned}")
    failures = 0
    for case in selected_cases(args):
        outcome = check_case(case, Path(args.work_root))
        problems, golden = outcome["problems"], outcome["golden"] or {}
        recorded = golden.get("recordedImplementationHash")
        status = "PASS" if not problems else "FAIL"
        suffix = (f" (implementationHash differs from the recording {str(recorded)[:12]}: bump)"
                  if recorded not in (None, current) and not problems else "")
        print(f"{status} {case.id} [{case.group}] {len(outcome['observations'])} observations, "
              f"{outcome['elapsed_s']:.1f} s{suffix}")
        for problem in problems[:40]:
            print(f"    {problem}")
        if len(problems) > 40:
            print(f"    ... {len(problems) - 40} more")
        failures += bool(problems)
    print("RESULT:", "PASS" if not failures else f"FAIL ({failures} case(s))")
    return 1 if failures else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true", help="write goldens at the pinned implementation")
    mode.add_argument("--check", action="store_true", help="compare the current implementation with the goldens")
    mode.add_argument("--list", action="store_true", help="list cases")
    parser.add_argument("--case", action="append", help="case id (repeatable); default: all non-slow cases")
    parser.add_argument("--slow", action="store_true", help="include slow cases (G2 bare plate, ~106 s)")
    parser.add_argument("--force", action="store_true", help="overwrite existing goldens when recording")
    parser.add_argument("--twice", action="store_true", help="record: run twice and require identical observations")
    parser.add_argument("--work-root", default=str(DEFAULT_WORK_ROOT), help="scratch root for artifacts")
    args = parser.parse_args(argv)
    if args.list:
        for case in CASES:
            print(f"{case.id:32s} {case.group:4s} {'slow' if case.slow else 'fast'}  {case.description}")
        return 0
    if args.record:
        return command_record(args)
    return command_check(args)


if __name__ == "__main__":
    sys.exit(main())
