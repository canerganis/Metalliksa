"""Re-derive thermal-proxy section summaries from archived accepted-step planes."""
from io import BytesIO
import math
import zipfile
import zlib

import numpy as np

from lpbf_peak import (rectangular_corridor_section_observations,
                       rectangular_corridor_section_samples)


_MEMBERS = {
    "schema_version.npy", "scan_start_x_m.npy", "section_x_m.npy",
    "section_distance_mm.npy", "temperature_planes_K.npy", "plane_indices.npy",
    "plane_x_m.npy", "axis_y_m.npy", "z_m.npy", "mesh_m.npy",
    "liquidus_K.npy", "accepted_step_count.npy",
    "section_source_plane_indices.npy", "section_interpolation_fraction.npy",
    "section_interpolation_operator.npy", "section_record_id.npy",
}
_MAX_COMPRESSED_BYTES = 32 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
_MAX_MEMBER_BYTES = 64 * 1024 * 1024
_MAX_CELLS = 4_000_000
_FLOAT_ATOL = 1e-9
_FLOAT_RTOL = 1e-12


class SectionArtifactError(ValueError):
    """An archived section field cannot substantiate its result summaries."""


def _fail(message):
    raise SectionArtifactError(message)


def _scalar(data, name, dtype):
    value = data[name[:-4]]
    if value.shape != () or value.dtype != np.dtype(dtype):
        _fail(f"{name[:-4]} must be a scalar {np.dtype(dtype)}")
    return value.item()


def _number(value, name, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (positive and value <= 0)):
        _fail(f"{name} is missing or invalid")
    return float(value)


def _preflight_zip(payload):
    if not isinstance(payload, bytes) or not payload or len(payload) > _MAX_COMPRESSED_BYTES:
        _fail("compressed NPZ byte budget or payload type is invalid")
    try:
        with zipfile.ZipFile(BytesIO(payload), "r") as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(names) != len(_MEMBERS) or set(names) != _MEMBERS:
                _fail("NPZ member set is missing, duplicated, or unexpected")
            total = 0
            for member in members:
                if (member.is_dir() or member.file_size < 0 or member.compress_size < 0
                        or member.file_size > _MAX_MEMBER_BYTES):
                    _fail("NPZ member exceeds its decompressed byte budget")
                total += member.file_size
                if total > _MAX_UNCOMPRESSED_BYTES:
                    _fail("NPZ exceeds the decompressed byte budget")
            # Verify actual decompressed byte counts under the same limits before NumPy sees the ZIP.
            actual_total = 0
            for member in members:
                actual = 0
                with archive.open(member, "r") as stream:
                    while True:
                        chunk = stream.read(64 * 1024)
                        if not chunk:
                            break
                        actual += len(chunk)
                        actual_total += len(chunk)
                        if actual > _MAX_MEMBER_BYTES or actual_total > _MAX_UNCOMPRESSED_BYTES:
                            _fail("NPZ exceeds the decompressed byte budget")
                if actual != member.file_size:
                    _fail("NPZ member size does not match its directory record")
    except SectionArtifactError:
        raise
    except (OSError, EOFError, RuntimeError, ValueError, zlib.error,
            zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise SectionArtifactError("NPZ ZIP structure or compressed data is corrupt") from exc


def rederive_rectangular_corridor_sections(payload, result):
    """Validate the producer NPZ and rederive both sections from its source planes."""
    _preflight_zip(payload)
    try:
        with np.load(BytesIO(payload), allow_pickle=False) as archive:
            data = {name: archive[name] for name in archive.files}
    except Exception as exc:
        raise SectionArtifactError("NPZ arrays cannot be loaded without pickle") from exc

    expected_arrays = {name[:-4] for name in _MEMBERS}
    if set(data) != expected_arrays:
        _fail("NPZ array names do not match version 1")
    version = _scalar(data, "schema_version.npy", np.int64)
    if version != 1:
        _fail("NPZ schema version is unsupported")
    scan_start = _scalar(data, "scan_start_x_m.npy", np.float64)
    mesh = _scalar(data, "mesh_m.npy", np.float64)
    liquidus = _scalar(data, "liquidus_K.npy", np.float64)
    steps = _scalar(data, "accepted_step_count.npy", np.int64)
    if not math.isfinite(scan_start) or not math.isfinite(mesh) or mesh <= 0:
        _fail("NPZ scan start or mesh is invalid")
    if not math.isfinite(liquidus) or liquidus <= 0 or type(steps) is not int or steps <= 0:
        _fail("NPZ liquidus or accepted-step count is invalid")

    def array(name, dtype, ndim, shape=None):
        value = data[name]
        if value.dtype != np.dtype(dtype) or value.ndim != ndim or (shape is not None and value.shape != shape):
            _fail(f"{name} has an invalid shape or dtype")
        if value.dtype.kind in "f" and not np.isfinite(value).all():
            _fail(f"{name} contains non-finite values")
        return value

    section_x = array("section_x_m", np.float64, 1, (2,))
    distances = array("section_distance_mm", np.float64, 1, (2,))
    plane_indices = array("plane_indices", np.int64, 1)
    plane_x = array("plane_x_m", np.float64, 1)
    axis_y = array("axis_y_m", np.float64, 1)
    z = array("z_m", np.float64, 1)
    fractions = array("section_interpolation_fraction", np.float64, 1, (2,))
    section_indices = array("section_source_plane_indices", np.int64, 2, (2, 2))
    temperatures = array("temperature_planes_K", np.float64, 3)
    operators = data["section_interpolation_operator"]
    record_ids = data["section_record_id"]
    if operators.dtype.kind != "U" or operators.shape != (2,) or record_ids.dtype.kind != "U" or record_ids.shape != (2,):
        _fail("NPZ section identifiers or interpolation operators have an invalid dtype or shape")
    if (len(plane_indices) < 1 or len(plane_indices) > 4 or len(plane_x) != len(plane_indices)
            or temperatures.shape[0] != len(plane_indices) or np.any(plane_indices < 0)
            or not np.all(np.diff(plane_indices) > 0)):
        _fail("NPZ source-plane indices must be sorted and unique")
    if (axis_y.size < 2 or z.size < 2 or axis_y.size * z.size > _MAX_CELLS
            or temperatures.shape[1:] != (len(axis_y), len(z))):
        _fail("NPZ temperature planes do not fit the bounded Y/Z grid")
    # result.json records executed mesh and steps but carries no executed domain origin/extent.
    # Keep the Y/Z coordinate axes internally uniform; do not invent a domain binding here.
    for name, axis in (("Y", axis_y), ("Z", z)):
        if (not np.all(np.diff(axis) > 0)
                or not np.allclose(np.diff(axis), mesh, rtol=1e-8, atol=1e-12)):
            _fail(f"NPZ {name} axis is not increasing at the declared mesh")

    # The producer's source X axis is uniform, indexed from zero, and has this mesh.
    inferred_origins = plane_x - plane_indices.astype(np.float64) * mesh
    if not np.allclose(inferred_origins, inferred_origins[0], rtol=0., atol=1e-12):
        _fail("NPZ source-plane coordinates do not match their mesh indices")
    if np.any(np.abs(plane_x - (inferred_origins[0] + plane_indices * mesh)) > 1e-12):
        _fail("NPZ source-plane coordinates are inconsistent")

    settings = result.get("settings") if isinstance(result, dict) else None
    material = result.get("material") if isinstance(result, dict) else None
    discretization = result.get("discretization") if isinstance(result, dict) else None
    scan_path = result.get("scanPath") if isinstance(result, dict) else None
    observations = result.get("barePlateSectionObservations") if isinstance(result, dict) else None
    if (not isinstance(settings, dict) or not isinstance(material, dict)
            or not isinstance(discretization, dict) or not isinstance(scan_path, list)
            or len(scan_path) != 1 or not isinstance(observations, list) or len(observations) != 2):
        _fail("result.json lacks executed material, discretization, scan, or section records")
    result_mesh = _number(discretization.get("mesh_m"), "executed mesh", positive=True)
    result_steps = discretization.get("steps")
    result_liquidus = _number(material.get("liquidus_K"), "executed liquidus", positive=True)
    track_length = _number(settings.get("trackLength_um"), "executed track length", positive=True) * 1e-6
    scan_start_result = _number(scan_path[0].get("start", [None])[0], "executed scan start")
    if (type(result_steps) is not int or result_steps <= 0 or result_steps != steps
            or not math.isclose(result_mesh, mesh, rel_tol=0., abs_tol=1e-15)
            or not math.isclose(result_liquidus, liquidus, rel_tol=0., abs_tol=1e-9)
            or not math.isclose(scan_start_result, scan_start, rel_tol=0., abs_tol=1e-12)):
        _fail("NPZ mesh, liquidus, accepted steps, or scan start differs from execution records")

    max_index = int(plane_indices[-1])
    if max_index > 100_000:
        _fail("NPZ source-plane index exceeds the bounded scan grid")
    axis_x = inferred_origins[0] + np.arange(max_index + 1, dtype=np.float64) * mesh
    samples = rectangular_corridor_section_samples(axis_x, scan_start, track_length)
    expected_ids = ["single-line-x-4p9mm", "single-line-x-6p0mm"]
    expected_union = set()
    fields = {}
    for index, request in enumerate(samples):
        row_id = expected_ids[index]
        row_indices = request["sourcePlaneIndices"]
        if request["status"] != "pending" or request["recordId"] != row_id:
            _fail("Executed scan cannot resolve both required section positions")
        padded = row_indices + [-1] * (2 - len(row_indices))
        if (record_ids[index] != row_id or distances[index] != request["distanceFromScanStart_mm"]
                or not math.isclose(section_x[index], request["xCoordinate_m"], rel_tol=0., abs_tol=1e-12)
                or not np.array_equal(section_indices[index], np.asarray(padded, dtype=np.int64))
                or operators[index] != request["interpolationOperator"]
                or not math.isclose(fractions[index], request["interpolationFraction"], rel_tol=0., abs_tol=1e-12)):
            _fail("NPZ section IDs, distances, X coordinates, indices, or interpolation differs from execution")
        expected_union.update(row_indices)
    if list(plane_indices) != sorted(expected_union) or not np.allclose(plane_x, axis_x[plane_indices], rtol=0., atol=1e-12):
        _fail("NPZ source-plane list is not the exact section-plane union")
    for index, plane_index in enumerate(plane_indices):
        fields[int(plane_index)] = temperatures[index]

    # The shared observation routine blends archived peak planes and calls the
    # existing interpolated_midtrack_bare_plate_section contour operator.
    computed = rectangular_corridor_section_observations(axis_y, z, fields, samples, mesh, liquidus)
    by_id = {row.get("recordId"): row for row in observations if isinstance(row, dict)}
    if len(by_id) != 2 or set(by_id) != set(expected_ids):
        _fail("result.json does not contain exactly the two required section records")
    for actual in computed:
        expected = by_id[actual["recordId"]]
        for key in ("status", "recordId", "operator", "interpolationOperator",
                    "sourcePlaneIndices", "contourOperator", "temporalAggregation"):
            if actual.get(key) != expected.get(key):
                _fail(f"result.json section {actual['recordId']} has inconsistent {key}")
        for key, tolerance in (("distanceFromScanStart_mm", 1e-12), ("scanStartX_m", 1e-12),
                               ("xCoordinate_m", 1e-12), ("interpolationFraction", 1e-12)):
            try:
                agrees = math.isclose(float(actual[key]), float(expected[key]), rel_tol=0., abs_tol=tolerance)
            except (KeyError, TypeError, ValueError, OverflowError):
                agrees = False
            if not agrees:
                _fail(f"result.json section {actual['recordId']} has inconsistent {key}")
        for key, tolerance in (("sourcePlaneX_m", 1e-12), ("sourcePlaneX_um", 1e-6)):
            try:
                agrees = len(actual[key]) == len(expected[key]) and all(
                    math.isclose(float(left), float(right), rel_tol=0., abs_tol=tolerance)
                    for left, right in zip(actual[key], expected[key]))
            except (KeyError, TypeError, ValueError, OverflowError):
                agrees = False
            if not agrees:
                _fail(f"result.json section {actual['recordId']} has inconsistent {key}")
        if actual.get("status") != "thermal-proxy" or actual.get("sampleCells") != expected.get("sampleCells"):
            _fail(f"result.json section {actual['recordId']} status or sampleCells is not reproducible")
        for key in ("width_um", "depth_um"):
            try:
                agrees = math.isclose(float(actual[key]), float(expected[key]), rel_tol=_FLOAT_RTOL, abs_tol=_FLOAT_ATOL)
            except (KeyError, TypeError, ValueError, OverflowError):
                agrees = False
            if not agrees:
                _fail(f"result.json section {actual['recordId']} {key} is not reproducible")
    return {"status": "validated", "sections": computed}
