"""Lossless final-state evidence; byte integrity does not establish model parity.

Enthalpy is volumetric excess relative to each state's initial temperature,
in J/m^3. It is neither absolute specific enthalpy nor an experimental field.
"""

import hashlib
import math
from pathlib import Path
import re

import numpy as np


MAX_CELLS = 100_000
MAX_STEPS = 250_000
MAX_TOTAL_BYTES = 50 * 1024 * 1024
KIND = "lpbf-final-field-parity-evidence"
ENTHALPY_REFERENCE = "volumetric-excess-relative-to-initial-temperature"
UNITS = {
    "coordinates_m": "m",
    "temperature_K": "K",
    "enthalpy_J_m3": "J/m^3",
    "density_kg_m3": "kg/m^3",
    "accepted_dt_s": "s",
}
SCALARS = ("time_s", "initial_temperature_K", "cell_volume_m3")


def _positive(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(f"{name} must be a finite positive number")
    if (isinstance(value, (int, np.integer)) and abs(int(value)) > 2 ** 53
            or isinstance(value, np.floating) and value.dtype.itemsize > 8):
        raise ValueError(f"{name} is outside the supported exact float64 range")
    try:
        value = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite positive number") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return value


def _exact_keys(value, keys, name):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"Invalid {name} fields")


def _count(value, maximum, name):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"Invalid {name} count")
    return value


def _shape(quantity, cells, steps):
    return [cells, 3] if quantity == "coordinates_m" else [steps if quantity == "accepted_dt_s" else cells]


def _relative_path(backend, quantity):
    return f"gpu-pilot/{backend}-{quantity}.f64le.bin"


def _state_arrays(state):
    _exact_keys(state, (*UNITS, *SCALARS), "pilot state")
    sources = {}
    for quantity in UNITS:
        if not isinstance(state[quantity], np.ndarray):
            raise ValueError(f"{quantity} source must be a NumPy ndarray")
        try:
            # The writer accepts ndarray fields only. Coercing a mixed Python
            # sequence here can round an integer before the range check sees it.
            source = np.asarray(state[quantity])
            if source.dtype.kind not in "iuf":
                raise ValueError("Only real numeric arrays are supported")
            sources[quantity] = source
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"Invalid {quantity} array") from error
    coordinates, timesteps = sources["coordinates_m"], sources["accepted_dt_s"]
    if coordinates.ndim != 2 or coordinates.shape[1] != 3 or timesteps.ndim != 1:
        raise ValueError("Coordinates require (cells, 3); accepted timesteps require (steps,)")
    cells = _count(coordinates.shape[0], MAX_CELLS, "cell")
    steps = _count(timesteps.size, MAX_STEPS, "step")
    # Inspect every shape before allocating any float64/C-order conversion.
    for quantity, array in sources.items():
        if list(array.shape) != _shape(quantity, cells, steps):
            raise ValueError(f"Invalid shape for {quantity}")
    for quantity, array in sources.items():
        # Float16/32/64 conversion is lossless. Conservatively restrict integer
        # inputs to the consecutive exact-integer range, and reject extended
        # floats rather than silently rounding the original evidence.
        if ((array.dtype.kind in "iu" and (int(array.min()) < -(2 ** 53) or int(array.max()) > 2 ** 53))
                or (array.dtype.kind == "f" and array.dtype.itemsize > 8)):
            raise ValueError(f"{quantity} source is outside the supported exact float64 range")
        if not np.isfinite(array).all():
            raise ValueError(f"Nonfinite {quantity}")
        if quantity in ("temperature_K", "density_kg_m3", "accepted_dt_s") and np.any(array <= 0):
            raise ValueError(f"{quantity} must be strictly positive")
    scalars = {key: _positive(state[key], key) for key in SCALARS}
    arrays = {quantity: np.ascontiguousarray(source, dtype="<f8") for quantity, source in sources.items()}
    # Replay the solver's sequential float64 clock before checking its bounded
    # final snap. fsum (or Python's compensated sum) removes accumulated
    # roundoff and can incorrectly reject a faithfully recorded long sequence.
    # Preserve dt bytes; never rescale accepted steps to match the endpoint.
    realized_time = 0.
    for dt in arrays["accepted_dt_s"]:
        next_time = realized_time + float(dt)
        if realized_time >= scalars["time_s"] or next_time <= realized_time:
            raise ValueError("Accepted timestep does not advance the clock before final time")
        realized_time = next_time
    roundoff = min(1e-14, 2 * math.ulp(scalars["time_s"]) * steps)
    if not math.isfinite(realized_time) or abs(realized_time - scalars["time_s"]) > roundoff:
        raise ValueError("Accepted timestep sum does not match final time within endpoint roundoff")
    return {**arrays, **scalars}, cells, steps


def _descriptor_refs(descriptor):
    _exact_keys(descriptor, ("schemaVersion", "kind", "encoding", "order", "enthalpyReference", "states"), "pilot descriptor")
    if (type(descriptor["schemaVersion"]) is not int or descriptor["schemaVersion"] != 1
            or descriptor["kind"] != KIND or descriptor["encoding"] != "float64-le"
            or descriptor["order"] != "C" or descriptor["enthalpyReference"] != ENTHALPY_REFERENCE):
        raise ValueError("Unsupported pilot evidence contract")
    _exact_keys(descriptor["states"], ("cpu", "gpu"), "pilot backends")
    refs = []
    total = 0
    for backend in ("cpu", "gpu"):
        state = descriptor["states"][backend]
        _exact_keys(state, ("cells", "steps", *SCALARS, "fields"), "pilot state descriptor")
        cells = _count(state["cells"], MAX_CELLS, "cell")
        steps = _count(state["steps"], MAX_STEPS, "step")
        for name in SCALARS:
            _positive(state[name], name)
        _exact_keys(state["fields"], UNITS, "pilot array descriptors")
        for quantity, units in UNITS.items():
            ref = state["fields"][quantity]
            _exact_keys(ref, ("path", "shape", "units", "size_bytes", "sha256"), "pilot artifact")
            shape = _shape(quantity, cells, steps)
            if (not isinstance(ref["shape"], list) or any(type(n) is not int for n in ref["shape"])
                    or ref["shape"] != shape or ref["units"] != units
                    or ref["path"] != _relative_path(backend, quantity)
                    or type(ref["size_bytes"]) is not int or ref["size_bytes"] != 8 * math.prod(shape)
                    or not isinstance(ref["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", ref["sha256"])):
                raise ValueError("Invalid pilot artifact identity, shape, units or size")
            total += ref["size_bytes"]
            refs.append({key: ref[key] for key in ("path", "size_bytes", "sha256")})
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Pilot evidence exceeds run byte budget")
    return refs


def pilot_artifact_refs(descriptor):
    """Validate metadata and return the exact ten ordinary artifact references."""
    return _descriptor_refs(descriptor)


def _directory(folder, *, create=False):
    root = Path(folder).absolute()
    # Inspect ancestors before resolving: resolving both paths first hides a
    # linked ancestor shared by the run root and its artifact subdirectory.
    current = Path(root.anchor)
    for part in root.parts[1:]:
        current /= part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)() or not current.is_dir():
            raise ValueError("Pilot evidence root ancestors must be ordinary directories without links")
    child = root / "gpu-pilot"
    if child.is_symlink() or getattr(child, "is_junction", lambda: False)():
        raise ValueError("Pilot evidence directory must not be a link")
    if create:
        child.mkdir(exist_ok=True)
    if not child.is_dir() or child.resolve().parent != root.resolve():
        raise ValueError("Pilot evidence directory must remain inside the run root")
    return root


def write_pilot_artifacts(folder, cpu, gpu):
    """Write two final states from NumPy arrays; different step counts remain valid evidence.

    Existing files are never overwritten. Both states are checked before any
    output is written. This writer does not assert CPU/GPU agreement.
    """
    descriptor = {"schemaVersion": 1, "kind": KIND, "encoding": "float64-le", "order": "C",
                  "enthalpyReference": ENTHALPY_REFERENCE, "states": {}}
    content = {}
    for backend, state in (("cpu", cpu), ("gpu", gpu)):
        arrays, cells, steps = _state_arrays(state)
        entry = {"cells": cells, "steps": steps, **{key: arrays[key] for key in SCALARS}, "fields": {}}
        for quantity, units in UNITS.items():
            data = arrays[quantity].tobytes(order="C")
            path = _relative_path(backend, quantity)
            entry["fields"][quantity] = {"path": path, "shape": _shape(quantity, cells, steps),
                "units": units, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            content[path] = data
        descriptor["states"][backend] = entry
    _descriptor_refs(descriptor)
    root = _directory(folder, create=True)
    for path in content:
        if (root / path).exists() or (root / path).is_symlink():
            raise ValueError("Pilot evidence output already exists")
    for path, data in content.items():
        with (root / path).open("xb") as output:
            output.write(data)
    return descriptor


def read_pilot_artifacts(folder, descriptor):
    """Verify bytes, metadata and physical units/shape invariants; return states."""
    _descriptor_refs(descriptor)
    root = _directory(folder)
    states = {}
    for backend in ("cpu", "gpu"):
        metadata = descriptor["states"][backend]
        state = {key: metadata[key] for key in SCALARS}
        for quantity, ref in metadata["fields"].items():
            path = root / ref["path"]
            if path.is_symlink() or not path.is_file() or path.stat().st_size != ref["size_bytes"]:
                raise ValueError("Pilot artifact missing, linked or size mismatch")
            with path.open("rb") as stream:
                data = stream.read(ref["size_bytes"] + 1)
            if len(data) != ref["size_bytes"] or hashlib.sha256(data).hexdigest() != ref["sha256"]:
                raise ValueError("Pilot artifact byte integrity failed")
            state[quantity] = np.frombuffer(data, dtype="<f8").reshape(ref["shape"]).copy()
        states[backend], _, _ = _state_arrays(state)
    return states
