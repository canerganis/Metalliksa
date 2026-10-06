"""Bounded field encoding for the fixed scan-end numerical diagnostic."""

import hashlib
import math
from pathlib import Path

import numpy as np


OBSERVATION_OPERATOR = "fixed-scan-end-liquidus-cell-edge-contour-v1"
TEMPORAL_SELECTION = "first-scan-end-accepted-state-v1"
ARTIFACT_SCOPE = "CPU numerical diagnostic fields only; not a run archive or experimental evidence"
MAX_UNCOMPRESSED_FIELD_BYTES = 40_000_000
FIELD_NAMES = ("coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3", "accepted_dt_s")


def _canonical_array(value, name):
    source = np.asarray(value)
    if source.dtype.kind not in "iuf" or source.dtype.kind == "f" and source.dtype.itemsize > 8:
        raise ValueError(f"{name} must be a supported real numeric array")
    if source.dtype.kind in "iu" and source.size and (
            int(source.min()) < -(2 ** 53) or int(source.max()) > 2 ** 53):
        raise ValueError(f"{name} is outside the exact float64 range")
    array = np.ascontiguousarray(source, dtype="<f8")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains nonfinite values")
    return array


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_selected_state_artifact(snapshot, path, max_uncompressed_bytes=MAX_UNCOMPRESSED_FIELD_BYTES):
    """Write one copied accepted state and return exact array and file hashes."""
    if not isinstance(snapshot, dict) or set(snapshot) != {
            *FIELD_NAMES, "target_time_s", "time_s", "scheduler_time_s", "time_difference_s",
            "roundoff_tolerance_s", "step", "initial_temperature_K", "cell_volume_m3"}:
        raise ValueError("Selected-time snapshot has an unexpected field set")
    arrays = {name: _canonical_array(snapshot[name], name) for name in FIELD_NAMES}
    coordinates = arrays["coordinates_m"]
    cells = coordinates.shape[0] if coordinates.ndim == 2 else 0
    if cells <= 0 or coordinates.shape != (cells, 3):
        raise ValueError("Coordinates must have shape (cells, 3)")
    for name in ("temperature_K", "enthalpy_J_m3", "density_kg_m3"):
        if arrays[name].shape != (cells,):
            raise ValueError(f"{name} must contain one value per cell")
    accepted_dt = arrays["accepted_dt_s"]
    if (accepted_dt.ndim != 1 or accepted_dt.size <= 0 or not np.isfinite(accepted_dt).all()
            or np.any(accepted_dt <= 0) or np.any(arrays["temperature_K"] <= 0)
            or np.any(arrays["density_kg_m3"] <= 0)):
        raise ValueError("Selected-time field arrays or accepted steps are invalid")
    step = snapshot["step"]
    if type(step) is not int or step != accepted_dt.size:
        raise ValueError("Selected-time step count does not match accepted timesteps")
    for name in ("target_time_s", "time_s", "scheduler_time_s", "time_difference_s",
                 "roundoff_tolerance_s", "initial_temperature_K", "cell_volume_m3"):
        value = snapshot[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if (snapshot["target_time_s"] <= 0 or snapshot["time_s"] <= 0
            or snapshot["initial_temperature_K"] <= 0 or snapshot["cell_volume_m3"] <= 0
            or snapshot["roundoff_tolerance_s"] <= 0
            or not math.isclose(snapshot["target_time_s"] - snapshot["time_s"],
                                snapshot["time_difference_s"], rel_tol=0., abs_tol=0.)):
        raise ValueError("Selected-time snapshot metadata is inconsistent")
    if abs(snapshot["time_difference_s"]) > snapshot["roundoff_tolerance_s"]:
        raise ValueError("Selected-time snapshot exceeds its roundoff bound")
    replay_time = 0.
    for dt in accepted_dt:
        next_time = replay_time + float(dt)
        if not math.isfinite(next_time) or next_time <= replay_time:
            raise ValueError("Accepted timesteps do not advance the state clock")
        replay_time = next_time
    if replay_time != snapshot["time_s"]:
        raise ValueError("Accepted timestep replay differs from the recorded state time")
    uncompressed_bytes = sum(array.nbytes for array in arrays.values())
    if (type(max_uncompressed_bytes) is not int or max_uncompressed_bytes <= 0
            or uncompressed_bytes > max_uncompressed_bytes):
        raise ValueError("Selected-time field artifact exceeds its byte bound")

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    size_bytes = destination.stat().st_size
    if size_bytes > max_uncompressed_bytes:
        destination.unlink(missing_ok=True)
        raise ValueError("Compressed field artifact exceeds its byte bound")
    return {
        "path": destination.name,
        "scope": ARTIFACT_SCOPE,
        "format": "numpy-npz-compressed-little-endian-float64-v1",
        "cells": int(cells),
        "steps": int(step),
        "targetTime_s": float(snapshot["target_time_s"]),
        "actualTime_s": float(snapshot["time_s"]),
        "schedulerTime_s": float(snapshot["scheduler_time_s"]),
        "targetMinusActualTime_s": float(snapshot["time_difference_s"]),
        "roundoffTolerance_s": float(snapshot["roundoff_tolerance_s"]),
        "uncompressedBytes": int(uncompressed_bytes),
        "byteSize": int(size_bytes),
        "sha256": _sha256_file(destination),
        "fieldSha256": {
            name: hashlib.sha256(memoryview(array).cast("B")).hexdigest()
            for name, array in arrays.items()
        },
    }
