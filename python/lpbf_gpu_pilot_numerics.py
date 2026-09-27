"""Recompute archived GPU-pilot numerical consistency from decoded fields.

This is a bounded integrity check, not a solver, parity-target source, or
scientific validation. Final fields cannot recover peak/history geometry,
input/loss integrals, or independently establish the constitutive H-T law.
"""

import math

import numpy as np


_BACKENDS = ("cpu", "gpu")
_COMPARISON_KEYS = (
    "finalSampling", "finalTemperatureField", "peakTemperature_K", "input_J",
    "losses_J", "stored_J", "width_um", "depth_um", "length_um", "volume_um3",
)
_INTEGRAL_KEYS = ("peakTemperature_K", "input_J", "losses_J", "stored_J")
_GEOMETRY_KEYS = ("width_um", "depth_um", "length_um")
_ARRAY_KEYS = (
    "coordinates_m", "temperature_K", "enthalpy_J_m3", "density_kg_m3",
    "accepted_dt_s",
)
_MAX_CELLS = 100_000
_MAX_STEPS = 250_000


def _mapping(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"Invalid GPU pilot {name}")
    return value


def _number(value, name, *, nonnegative=False, positive=False):
    if type(value) not in (int, float):
        raise ValueError(f"Invalid GPU pilot {name}")
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0) or (nonnegative and number < 0):
        raise ValueError(f"Invalid GPU pilot {name}")
    return number


def _count(value, maximum, name):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"Invalid GPU pilot {name} count")
    return value


def _gamma(k):
    unit = 2.0 ** -53
    product = k * unit
    if product >= 1.0:
        raise ValueError("GPU pilot roundoff bound exceeds float64 support")
    return product / (1.0 - product)


def _finite_array(state, key, shape, *, positive=False):
    value = state.get(key)
    if not isinstance(value, np.ndarray) or value.dtype.kind not in "fiu" or value.dtype.itemsize > 8:
        raise ValueError(f"Invalid GPU pilot decoded {key}")
    if value.shape != shape or not np.isfinite(value).all():
        raise ValueError(f"Invalid GPU pilot decoded {key}")
    if value.dtype.kind in "iu" and value.size:
        if int(value.min()) < -(2 ** 53) or int(value.max()) > 2 ** 53:
            raise ValueError(f"GPU pilot decoded {key} exceeds exact float64 integer range")
    array = np.asarray(value, dtype=np.float64)
    if positive and np.any(array <= 0):
        raise ValueError(f"GPU pilot decoded {key} must be positive")
    return array


def _close(actual, expected, *, rel=1e-12, abs_=0.0):
    return math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_)


def _strict_json_equal(left, right):
    """Mirror JSON structural equality while keeping booleans distinct from numbers."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (left.keys() == right.keys()
                and all(_strict_json_equal(left[key], right[key]) for key in left))
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _strict_json_equal(a, b) for a, b in zip(left, right))
    return left == right


def _roundoff_equal(stored, computed, cells):
    if stored == computed == 0.0:
        return True
    scale = max(abs(stored), abs(computed))
    factor = 2.0 * _gamma(4 * cells + 32) / (1.0 - _gamma(4 * cells + 32))
    bound = factor * scale
    if scale > 0.0 and (bound == 0.0 or not math.isfinite(bound)):
        raise ValueError("Unsupported underflow or overflow in GPU pilot norm bound")
    return abs(stored - computed) <= bound


def _stable_norm(values):
    """Compute an L2 norm without squaring unscaled large/small values."""
    if values.size == 0:
        return 0.0
    scale = float(np.max(np.abs(values)))
    if scale == 0.0:
        return 0.0
    try:
        squares = math.fsum((float(value) / scale) ** 2 for value in values)
        norm = scale * math.sqrt(squares)
    except (OverflowError, ValueError) as error:
        raise ValueError("Unsupported overflow in GPU pilot field norm") from error
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError("Unsupported overflow or underflow in GPU pilot field norm")
    return norm


def _state(result, descriptor, states, backend):
    state = _mapping(states.get(backend), f"{backend} decoded state")
    metadata = _mapping(descriptor["states"].get(backend), f"{backend} field metadata")
    coordinates = state.get("coordinates_m")
    if (not isinstance(coordinates, np.ndarray) or coordinates.dtype.kind not in "fiu"
            or coordinates.dtype.itemsize > 8 or coordinates.ndim != 2
            or coordinates.shape[1] != 3):
        raise ValueError(f"Invalid GPU pilot decoded {backend} coordinates")
    cells = _count(coordinates.shape[0], _MAX_CELLS, f"{backend} cell")
    descriptor_cells = _count(metadata.get("cells"), _MAX_CELLS, f"{backend} field cell")
    if descriptor_cells != cells:
        raise ValueError(f"GPU pilot {backend} field cell count changed")
    steps = _count(state.get("accepted_dt_s").size if isinstance(state.get("accepted_dt_s"), np.ndarray)
                   and state["accepted_dt_s"].ndim == 1 else 0, _MAX_STEPS, f"{backend} step")
    descriptor_steps = _count(metadata.get("steps"), _MAX_STEPS, f"{backend} field step")
    if descriptor_steps != steps:
        raise ValueError(f"GPU pilot {backend} field step count changed")

    arrays = {
        "coordinates_m": _finite_array(state, "coordinates_m", (cells, 3)),
        "temperature_K": _finite_array(state, "temperature_K", (cells,), positive=True),
        "enthalpy_J_m3": _finite_array(state, "enthalpy_J_m3", (cells,)),
        "density_kg_m3": _finite_array(state, "density_kg_m3", (cells,), positive=True),
        "accepted_dt_s": _finite_array(state, "accepted_dt_s", (steps,), positive=True),
    }
    scalars = {}
    for key in ("time_s", "initial_temperature_K", "cell_volume_m3"):
        value = _number(state.get(key), f"{backend} {key}", positive=True)
        descriptor_value = _number(metadata.get(key), f"{backend} metadata {key}", positive=True)
        if value != descriptor_value:
            raise ValueError(f"GPU pilot {backend} field scalar metadata changed")
        scalars[key] = value
    return {**arrays, **scalars, "cells": cells, "steps": steps}


def _energy_integral(state):
    enthalpy = state["enthalpy_J_m3"]
    try:
        total = math.fsum(float(value) for value in enthalpy)
        absolute_total = math.fsum(abs(float(value)) for value in enthalpy)
        volume = state["cell_volume_m3"]
        integral = total * volume
        absolute_integral = absolute_total * volume
    except (OverflowError, ValueError) as error:
        raise ValueError("Unsupported overflow in GPU pilot enthalpy integral") from error
    if (not math.isfinite(integral) or not math.isfinite(absolute_integral)
            or (total != 0.0 and integral == 0.0)
            or (absolute_total != 0.0 and absolute_integral == 0.0)):
        raise ValueError("Unsupported overflow or underflow in GPU pilot enthalpy integral")
    cells = state["cells"]
    left = 2.0 * _gamma(cells + 2)
    right = 1.0 - _gamma(cells - 1)
    tolerance = left * absolute_integral / right
    if absolute_integral > 0.0 and (tolerance == 0.0 or not math.isfinite(tolerance)):
        raise ValueError("Unsupported overflow or underflow in GPU pilot enthalpy bound")
    return integral, tolerance


def _validate_state_metadata(result, state, backend):
    if backend == "gpu":
        discretization = _mapping(result.get("discretization"), "GPU discretization")
    else:
        cpu = _mapping(result.get("gpuPilot", {}).get("cpu"), "CPU summary")
        discretization = _mapping(cpu.get("discretization"), "CPU discretization")
    cells = _count(discretization.get("cells"), _MAX_CELLS, f"{backend} summary cell")
    steps = _count(discretization.get("steps"), _MAX_STEPS, f"{backend} summary step")
    mesh = _number(discretization.get("mesh_m"), f"{backend} mesh", positive=True)
    if cells != state["cells"] or steps != state["steps"]:
        raise ValueError(f"GPU pilot {backend} field counts conflict with summary")
    try:
        expected_volume = mesh * mesh * mesh
    except OverflowError as error:
        raise ValueError(f"Invalid GPU pilot {backend} cell volume") from error
    if not math.isfinite(expected_volume) or expected_volume == 0.0:
        raise ValueError(f"Unsupported overflow or underflow in GPU pilot {backend} mesh volume")
    if not _close(state["cell_volume_m3"], expected_volume, abs_=1e-30):
        raise ValueError(f"GPU pilot {backend} field cell volume conflicts with mesh")

    settings = _mapping(result.get("settings"), "resolved settings")
    preheat = _number(settings.get("preheat_C"), "preheat_C") + 273.15
    if not math.isfinite(preheat) or preheat <= 0.0 or not _close(
            state["initial_temperature_K"], preheat, rel=1e-12, abs_=1e-12):
        raise ValueError(f"GPU pilot {backend} field preheat conflicts with settings")
    if not _close(state["time_s"], _number(discretization.get("meanDt_s"),
                                           f"{backend} mean timestep", positive=True) * steps,
                  rel=1e-12, abs_=1e-14):
        raise ValueError(f"GPU pilot {backend} field final time conflicts with mean timestep")
    accepted_dt = state["accepted_dt_s"]
    minimum, maximum = float(np.min(accepted_dt)), float(np.max(accepted_dt))
    mean = state["time_s"] / steps
    for key, actual in (("minimumDt_s", minimum), ("maximumDt_s", maximum)):
        if key in discretization:
            stored = _number(discretization[key], f"{backend} {key}", positive=True)
            if not _close(stored, actual):
                raise ValueError(f"GPU pilot {backend} accepted timestep {key} changed")
    if not _close(_number(discretization.get("meanDt_s"), f"{backend} mean timestep", positive=True), mean,
                  rel=1e-12, abs_=1e-14):
        raise ValueError(f"GPU pilot {backend} accepted timestep mean changed")
    return {"cells": cells, "steps": steps, "mesh_m": mesh,
            "minimumDt_s": minimum, "maximumDt_s": maximum, "meanDt_s": mean,
            "time_s": state["time_s"], "cell_volume_m3": expected_volume}


def _expected_end(settings):
    try:
        from lpbf_core_physics import scan_segments

        _, end = scan_segments(settings)
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError("Invalid bound GPU pilot settings for sampling check") from error
    if not math.isfinite(end) or end <= 0.0:
        raise ValueError("Invalid bound GPU pilot expected end time")
    return float(end)


def _reported_number(item, key):
    return _number(item.get(key), f"comparison {key}", nonnegative=True)


def _validate_scalar_comparisons(result, comparisons, targets, gpu_mesh):
    metrics = _mapping(result.get("metrics"), "metrics")
    energy = _mapping(result.get("energyBalance"), "energy balance")
    statuses = []
    diagnostics = {}
    for key in _INTEGRAL_KEYS:
        item = _mapping(comparisons.get(key), f"{key} comparison")
        cpu = _reported_number(item, "cpu")
        gpu = _reported_number(item, "gpu")
        displayed = energy.get(key) if key.endswith("_J") else metrics.get(key)
        displayed = _number(displayed, f"displayed {key}", nonnegative=True)
        if gpu != displayed:
            raise ValueError("GPU pilot GPU comparison value is not bound to displayed result")
        difference = abs(cpu - gpu) / max(abs(cpu), 1e-30)
        reported = _number(item.get("relativeDifference"),
                           f"{key} relative difference", nonnegative=True)
        if not math.isfinite(difference) or reported != difference:
            raise ValueError(f"GPU pilot {key} relative difference changed")
        status = "pass" if difference <= targets["integralRelativeMax"] else "failed"
        if item.get("status") != status:
            raise ValueError(f"GPU pilot {key} status conflicts with scalar difference")
        statuses.append(status)
        diagnostics[key] = {"cpu": cpu, "gpu": gpu, "relativeDifference": difference,
                            "status": status}

    gpu_mesh_um = gpu_mesh * 1e6
    if not math.isfinite(gpu_mesh_um) or gpu_mesh_um <= 0.0:
        raise ValueError("Unsupported overflow or underflow in GPU pilot mesh tolerance")
    for key in _GEOMETRY_KEYS:
        item = _mapping(comparisons.get(key), f"{key} comparison")
        cpu, gpu = _reported_number(item, "cpu"), _reported_number(item, "gpu")
        displayed = _number(metrics.get(key), f"displayed {key}", nonnegative=True)
        if gpu != displayed:
            raise ValueError("GPU pilot GPU comparison value is not bound to displayed result")
        difference = abs(cpu - gpu)
        reported = _number(item.get("absoluteDifference_um"),
                           f"{key} absolute difference", nonnegative=True)
        if reported != difference:
            raise ValueError(f"GPU pilot {key} absolute difference changed")
        status = ("inconclusive" if cpu == gpu == 0.0 else
                  "pass" if difference <= targets["widthDepthAbsoluteCellsMax"] * gpu_mesh_um else "failed")
        if item.get("status") != status:
            raise ValueError(f"GPU pilot {key} status conflicts with scalar difference")
        statuses.append(status)
        diagnostics[key] = {"cpu": cpu, "gpu": gpu,
                            "absoluteDifference_um": difference, "status": status}

    item = _mapping(comparisons.get("volume_um3"), "volume comparison")
    cpu, gpu = _reported_number(item, "cpu"), _reported_number(item, "gpu")
    displayed = _number(metrics.get("volume_um3"), "displayed volume_um3", nonnegative=True)
    if gpu != displayed:
        raise ValueError("GPU pilot GPU comparison value is not bound to displayed result")
    difference = abs(cpu - gpu) / max(abs(cpu), 1e-30)
    reported = _number(item.get("relativeDifference"), "volume relative difference", nonnegative=True)
    if not math.isfinite(difference) or reported != difference:
        raise ValueError("GPU pilot volume relative difference changed")
    status = ("inconclusive" if cpu == gpu == 0.0 else
              "pass" if difference <= targets["peakMeltVolumeRelativeMax"] else "failed")
    if item.get("status") != status:
        raise ValueError("GPU pilot volume status conflicts with scalar difference")
    statuses.append(status)
    diagnostics["volume_um3"] = {"cpu": cpu, "gpu": gpu,
                                 "relativeDifference": difference, "status": status}
    return statuses, diagnostics


def validate_pilot_numerics(result, decoded_states, targets):
    """Validate captured CPU/GPU fields against the archived parity summary.

    ``decoded_states`` is the result of ``read_pilot_artifacts``. This function
    performs no solver, CUDA, material-registry, capability, or hash operations.
    It raises ``ValueError`` for malformed/internally inconsistent evidence and
    returns a fresh diagnostic proof for sound evidence, including failed or
    inconclusive parity.
    """
    try:
        result = _mapping(result, "result")
        states = _mapping(decoded_states, "decoded states")
        if set(states) != set(_BACKENDS):
            raise ValueError("GPU pilot decoded states must contain CPU and GPU")
        target_map = _mapping(targets, "frozen targets")
        required_targets = (
            "integralRelativeMax", "widthDepthAbsoluteCellsMax",
            "fieldRiseL2RelativeMax", "fieldRiseMaxRelativeMax",
            "peakMeltVolumeRelativeMax",
        )
        frozen = {key: _number(target_map.get(key), f"target {key}", nonnegative=True)
                  for key in required_targets}
        if not isinstance(target_map.get("source"), str) or not target_map["source"]:
            raise ValueError("GPU pilot frozen target source is missing")

        pilot = _mapping(result.get("gpuPilot"), "parity report")
        if not _strict_json_equal(pilot.get("targets"), target_map):
            raise ValueError("GPU pilot stored targets differ from supplied frozen targets")
        descriptor = _mapping(result.get("gpuFieldArtifacts"), "field artifacts")
        descriptor_states = _mapping(descriptor.get("states"), "field artifact states")
        if set(descriptor_states) != set(_BACKENDS):
            raise ValueError("GPU pilot field descriptor must contain CPU and GPU")

        normalized = {backend: _state(result, descriptor, states, backend) for backend in _BACKENDS}
        metadata = {backend: _validate_state_metadata(result, normalized[backend], backend)
                    for backend in _BACKENDS}
        comparisons = _mapping(pilot.get("comparisons"), "comparisons")
        if set(comparisons) != set(_COMPARISON_KEYS):
            raise ValueError("GPU pilot comparisons are incomplete or unexpected")

        energies = {}
        for backend in _BACKENDS:
            computed, tolerance = _energy_integral(normalized[backend])
            item = _mapping(comparisons.get("stored_J"), "stored_J comparison")
            stored = _reported_number(item, backend)
            if abs(computed - stored) > tolerance:
                raise ValueError(f"GPU pilot {backend} enthalpy integral conflicts with stored energy")
            energies[backend] = {"integral_J": computed, "stored_J": stored,
                                 "roundoffTolerance_J": tolerance}

        sampling = _mapping(comparisons.get("finalSampling"), "final sampling")
        cpu_disc, gpu_disc = metadata["cpu"], metadata["gpu"]
        cpu_time = _number(sampling.get("cpuFinalTime_s"), "CPU final time", positive=True)
        cpu_frame_time = _number(sampling.get("cpuFrameTime_s"), "CPU frame time", positive=True)
        gpu_time = _number(sampling.get("gpuFinalTime_s"), "GPU final time", positive=True)
        expected_end = _expected_end(_mapping(result.get("settings"), "resolved settings"))
        stored_end = _number(sampling.get("expectedEnd_s"), "expected end time", positive=True)
        cpu_steps = _count(sampling.get("cpuSteps"), _MAX_STEPS, "reported CPU step")
        gpu_steps = _count(sampling.get("gpuSteps"), _MAX_STEPS, "reported GPU step")
        cell_count = _count(sampling.get("cellCount"), _MAX_CELLS, "reported cell")
        if (not _close(stored_end, expected_end, rel=1e-12, abs_=1e-14)
                or cpu_time != cpu_disc["time_s"] or gpu_time != gpu_disc["time_s"]
                or cpu_steps != cpu_disc["steps"] or gpu_steps != gpu_disc["steps"]
                or cell_count != cpu_disc["cells"]):
            raise ValueError("GPU pilot final sampling report conflicts with archived fields")
        aligned = (
            cpu_disc["cells"] == gpu_disc["cells"] == normalized["cpu"]["cells"]
            == normalized["gpu"]["cells"]
            and cpu_disc["steps"] == gpu_disc["steps"]
            and _close(cpu_disc["mesh_m"], gpu_disc["mesh_m"])
            and _close(cpu_time, cpu_frame_time, rel=1e-12, abs_=1e-14)
            and _close(cpu_time, expected_end, rel=1e-12, abs_=1e-14)
            and _close(gpu_time, cpu_time, rel=1e-12, abs_=1e-14)
            and normalized["cpu"]["coordinates_m"].shape == normalized["gpu"]["coordinates_m"].shape
            and np.array_equal(normalized["cpu"]["coordinates_m"], normalized["gpu"]["coordinates_m"])
        )
        expected_sampling_status = "pass" if aligned else "failed"
        if sampling.get("status") != expected_sampling_status:
            raise ValueError("GPU pilot final sampling status conflicts with archived fields")

        field = _mapping(comparisons.get("finalTemperatureField"), "temperature-field comparison")
        field_status = field.get("status")
        if not aligned:
            reason = field.get("reason")
            if (field_status != "failed" or not isinstance(reason, str) or not reason.strip()
                    or "relativeRiseL2" in field or "relativeRiseMax" in field):
                raise ValueError("GPU pilot misaligned fields must be failed without fabricated norms")
            field_diagnostic = {"status": "failed", "normsRecomputed": False}
        else:
            t0 = normalized["cpu"]["initial_temperature_K"]
            difference = normalized["gpu"]["temperature_K"] - normalized["cpu"]["temperature_K"]
            rise = normalized["cpu"]["temperature_K"] - t0
            try:
                l2 = _stable_norm(difference) / max(_stable_norm(rise), 1.0)
                max_difference = float(np.max(np.abs(difference)))
                max_rise = float(np.max(np.abs(rise)))
                maximum = max_difference / max(max_rise, 1.0)
            except (OverflowError, FloatingPointError) as error:
                raise ValueError("Unsupported overflow in GPU pilot temperature parity") from error
            if not math.isfinite(l2) or not math.isfinite(maximum):
                raise ValueError("Unsupported overflow in GPU pilot temperature parity")
            stored_l2 = _reported_number(field, "relativeRiseL2")
            stored_max = _reported_number(field, "relativeRiseMax")
            if (not _roundoff_equal(stored_l2, l2, cpu_disc["cells"])
                    or not _roundoff_equal(stored_max, maximum, cpu_disc["cells"])):
                raise ValueError("GPU pilot stored temperature norms conflict with decoded fields")
            # Integrity is checked against recomputed norms above, while the
            # frozen parity decision remains exactly on the stored report.
            # This avoids reclassifying an archived threshold-edge result due
            # only to a different but roundoff-consistent reduction order.
            expected_field_status = ("pass" if stored_l2 <= frozen["fieldRiseL2RelativeMax"]
                                     and stored_max <= frozen["fieldRiseMaxRelativeMax"] else "failed")
            if field_status != expected_field_status:
                raise ValueError("GPU pilot temperature-field status conflicts with recomputed norms")
            field_diagnostic = {"status": expected_field_status, "normsRecomputed": True,
                                "relativeRiseL2": l2, "relativeRiseMax": maximum}

        scalar_statuses, scalar_diagnostics = _validate_scalar_comparisons(
            result, comparisons, frozen, gpu_disc["mesh_m"])
        statuses = [expected_sampling_status, field_status, *scalar_statuses]
        overall = ("failed" if "failed" in statuses else
                   "inconclusive" if "inconclusive" in statuses else "pass")
        if pilot.get("status") != overall:
            raise ValueError("GPU pilot overall status conflicts with recomputed comparisons")
        return {
            "status": overall,
            "samplingAligned": aligned,
            "states": {backend: metadata[backend] | energies[backend] for backend in _BACKENDS},
            "temperatureField": field_diagnostic,
            "scalarComparisons": scalar_diagnostics,
        }
    except ValueError:
        raise
    except (ArithmeticError, IndexError, KeyError, TypeError) as error:
        raise ValueError("Invalid GPU pilot numerical evidence") from error
