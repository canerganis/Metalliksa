"""Accepted-endpoint maximum on uniform Cartesian cells; no subcell inference."""
import math
from pathlib import Path
import numpy as np

PEAK_EXTRACTION = "accepted-step-molten-volume-v1"
RECTANGULAR_CORRIDOR_SECTION_OPERATOR = "bare-plate-corridor-accepted-peak-x-linear-section-v1"
RECTANGULAR_CORRIDOR_SECTION_DISTANCES_MM = (4.9, 6.0)


def midtrack_bare_plate_section(axis, z, ever_molten, dx, axis_y=None):
    """Cell-supported W/D at the plane nearest a +X track's midpoint.

    NIST AMB2022-03 optical W is the widest cross-section extent, and D is the
    deepest extent below the original bare-plate surface. Ever-liquidus cells
    are a thermal proxy for the etched boundary, not an experimental contour.
    """
    axis, z, ever_molten = np.asarray(axis), np.asarray(z), np.asarray(ever_molten)
    axis_y = axis if axis_y is None else np.asarray(axis_y)
    if (axis.ndim != 1 or axis_y.ndim != 1 or z.ndim != 1
            or ever_molten.shape != (len(axis), len(axis_y), len(z))
            or not np.isfinite(axis).all() or not np.isfinite(axis_y).all()
            or not np.isfinite(z).all() or not np.isfinite(dx) or dx <= 0):
        raise ValueError("Invalid bare-plate midpoint section grid")
    plane = int(np.argmin(np.abs(axis)))
    if abs(axis[plane]) > dx/2 + 1e-12:
        raise ValueError("Track midpoint not represented by a mesh plane")
    iy, iz = np.where(ever_molten[plane] & (z[None, :] < 0))
    result = dict(status="no-melt" if not len(iy) else "thermal-proxy",
                  operator="midtrack-ever-liquidus-cell-section-v1",
                  location="nearest cell-center plane to +X track midpoint",
                  planeOffset_um=float(axis[plane]*1e6), mesh_um=float(dx*1e6),
                  midpointResolvedWithinQuarterCell=bool(abs(axis[plane]) <= dx/4),
                  sampleCells=int(len(iy)), surface_m=0.,
                  width_um=0., depth_um=0.,
                  evidenceScope="Numerical thermal proxy; no etched-boundary or experimental validation")
    if len(iy):
        result["width_um"] = float((axis_y[iy].max()-axis_y[iy].min()+dx)*1e6)
        result["depth_um"] = float(max(0., -z[iz].min()+dx/2)*1e6)
    return result


def interpolated_midtrack_bare_plate_section(axis, z, maximum_temperature, dx, liquidus_K,
                                             plane_offset_m):
    """Linear cell-center liquidus contour of the accepted-step temperature maximum.

    This is a numerical thermal proxy. It uses only crossings between measured
    neighboring cell centers; it never extends a contour beyond the grid or
    infers a temperature at the physical top surface.
    """
    axis = np.asarray(axis, dtype=float)
    z = np.asarray(z, dtype=float)
    temperature = np.asarray(maximum_temperature, dtype=float)
    if (axis.ndim != 1 or z.ndim != 1 or temperature.shape != (len(axis), len(z))
            or len(axis) < 2 or len(z) < 2 or not np.isfinite(axis).all()
            or not np.isfinite(z).all() or not np.isfinite(temperature).all()
            or not np.isfinite(dx) or dx <= 0 or not np.isfinite(liquidus_K)
            or not np.isfinite(plane_offset_m) or abs(plane_offset_m) > dx/2 + 1e-12
            or not np.allclose(np.diff(axis), dx, rtol=1e-8, atol=1e-12)
            or not np.allclose(np.diff(z), dx, rtol=1e-8, atol=1e-12)):
        raise ValueError("Invalid interpolated bare-plate midpoint section grid")
    plate = z < 0
    if not plate.any():
        raise ValueError("Bare-plate section has no substrate cells")
    temperature = temperature[:, plate]
    z = z[plate]
    molten = temperature >= liquidus_K
    count = int(np.count_nonzero(molten))
    result = dict(status="no-melt" if not count else "inconclusive",
                  operator="midtrack-accepted-max-liquidus-linear-contour-v1",
                  location="nearest cell-center plane to +X track midpoint",
                  temporalAggregation="maximum temperature at each cell center over accepted steps",
                  contour="linear liquidus crossings between neighboring cell centers",
                  surfaceTreatment="No temperature extrapolation to the original surface",
                  planeOffset_um=float(plane_offset_m*1e6), mesh_um=float(dx*1e6),
                  midpointResolvedWithinQuarterCell=bool(abs(plane_offset_m) <= dx/4),
                  sampleCells=count,
                  width_um=None, depth_um=None,
                  evidenceScope="Numerical thermal proxy; no etched-boundary or experimental validation")
    if not count:
        return result
    if molten[0].any() or molten[-1].any() or molten[:, 0].any():
        result["reason"] = "Liquidus contour reaches a lateral or bottom domain boundary"
        return result

    def crossings(values, positions):
        high = values >= liquidus_K
        edge = high[:-1] != high[1:]
        fractions = (liquidus_K-values[:-1][edge]) / (values[1:][edge]-values[:-1][edge])
        return positions[:-1][edge] + fractions * (positions[1:][edge]-positions[:-1][edge])

    y_crossings = [crossings(temperature[:, iz], axis) for iz in range(len(z))]
    y_crossings += [axis[iy:iy+1].repeat(len(crossings(temperature[iy], z)))
                    for iy in range(len(axis))]
    z_crossings = [crossings(temperature[iy], z) for iy in range(len(axis))]
    z_crossings += [z[iz:iz+1].repeat(len(crossings(temperature[:, iz], axis)))
                    for iz in range(len(z))]
    ys = np.concatenate(y_crossings)
    zs = np.concatenate(z_crossings)
    if len(ys) < 2 or len(zs) < 2:
        result["reason"] = "Liquidus contour is not resolved between cell centers"
        return result
    width_um = float(np.ptp(ys)*1e6)
    depth_um = float(max(0., -np.min(zs))*1e6)
    if width_um <= 0 or depth_um <= 0:
        result["reason"] = "Liquidus contour has no positive resolved width or depth"
        return result
    result.update(status="thermal-proxy", width_um=width_um, depth_um=depth_um)
    return result


def rectangular_corridor_section_samples(axis_x, scan_start_x_m, track_length_m):
    """Resolve fixed section coordinates to exact or bracketed X cell centers."""
    axis_x = np.asarray(axis_x, dtype=float)
    if (axis_x.ndim != 1 or len(axis_x) < 2 or not np.isfinite(axis_x).all()
            or not np.isfinite(scan_start_x_m) or not np.isfinite(track_length_m)
            or track_length_m <= 0 or not np.all(np.diff(axis_x) > 0)):
        raise ValueError("Invalid rectangular-corridor scan axis or scan extent")
    dx_values = np.diff(axis_x)
    if not np.allclose(dx_values, dx_values[0], rtol=1e-8, atol=1e-12):
        raise ValueError("Rectangular-corridor section X axis must be uniform")
    dx = float(dx_values[0])
    samples = []
    for distance_mm in RECTANGULAR_CORRIDOR_SECTION_DISTANCES_MM:
        distance_m = distance_mm*1e-3
        x_position = float(scan_start_x_m+distance_m)
        sample = dict(recordId=f"single-line-x-{str(distance_mm).replace('.', 'p')}mm",
                      status="unsupported", operator=RECTANGULAR_CORRIDOR_SECTION_OPERATOR,
                      scanLineScope="one simulated +X track; not experimental repeats",
                      distanceFromScanStart_mm=distance_mm, xCoordinate_m=x_position,
                      scanStartX_m=float(scan_start_x_m), interpolationOperator=None,
                      sourcePlaneIndices=[], sourcePlaneX_m=[], interpolationFraction=None,
                      width_um=None, depth_um=None)
        if distance_m > track_length_m+1e-12:
            sample["reason"] = "Requested section lies beyond the simulated scan length"
            samples.append(sample)
            continue
        if x_position < axis_x[0]-1e-12 or x_position > axis_x[-1]+1e-12:
            sample["reason"] = "Requested section lies outside the represented cell-center X domain"
            samples.append(sample)
            continue
        right = int(np.searchsorted(axis_x, x_position, side="left"))
        tol = max(1e-12, dx*1e-9)
        if right < len(axis_x) and abs(axis_x[right]-x_position) <= tol:
            indices, fraction = [right], 0.
            operator = "exact-cell-center"
        elif right > 0 and right < len(axis_x):
            left = right-1
            fraction = float((x_position-axis_x[left])/(axis_x[right]-axis_x[left]))
            indices = [left, right]
            operator = "linear-interpolation-between-accepted-peak-temperature-planes-v1"
        else:
            sample["reason"] = "Requested section cannot be interpolated without X-domain extrapolation"
            samples.append(sample)
            continue
        sample.update(status="pending", interpolationOperator=operator,
                      sourcePlaneIndices=indices,
                      sourcePlaneX_m=[float(axis_x[index]) for index in indices],
                      interpolationFraction=fraction)
        samples.append(sample)
    return samples


def rectangular_corridor_section_observations(axis_y, z, peak_temperature_planes,
                                               samples, dx, liquidus_K):
    """Return separate thermal-proxy observations using the X-plane peak fields.

    For off-grid X locations, cell-center peak-temperature fields are blended
    after temporal maxima have been accumulated independently on each plane.
    """
    axis_y, z = np.asarray(axis_y, dtype=float), np.asarray(z, dtype=float)
    observations = []
    for request in samples:
        observation = dict(request)
        if request["status"] != "pending":
            observations.append(observation)
            continue
        indices = request["sourcePlaneIndices"]
        if any(index not in peak_temperature_planes for index in indices):
            observation.update(status="unsupported",
                               reason="Accepted-step peak field missing for an X interpolation plane")
            observations.append(observation)
            continue
        fields = [np.asarray(peak_temperature_planes[index], dtype=float) for index in indices]
        if any(field.shape != (len(axis_y), len(z)) or not np.isfinite(field).all() for field in fields):
            observation.update(status="unsupported", reason="Invalid accepted-step section peak-temperature field")
            observations.append(observation)
            continue
        if len(fields) == 1:
            section_field = fields[0]
        else:
            fraction = request["interpolationFraction"]
            section_field = (1-fraction)*fields[0]+fraction*fields[1]
        contour = interpolated_midtrack_bare_plate_section(
            axis_y, z, section_field, dx, liquidus_K, 0.)
        observation.update(status=contour["status"],
                           location=f"section {request['distanceFromScanStart_mm']:.1f} mm from +X scan start",
                           temporalAggregation="accepted-step maximum per source X plane, then spatially interpolated",
                           interpolationOperator=request["interpolationOperator"],
                           contourOperator="linear-liquidus-crossings-between-cell-centers-v1",
                           sourcePlaneX_um=[x*1e6 for x in request["sourcePlaneX_m"]],
                           width_um=contour["width_um"], depth_um=contour["depth_um"],
                           sampleCells=contour["sampleCells"],
                           evidenceScope="Numerical thermal proxy; no etched-boundary or experimental validation; one simulated line only")
        if contour.get("reason"):
            observation["reason"] = contour["reason"]
        observations.append(observation)
    return observations


def write_rectangular_corridor_section_field_artifact(
        output_path, axis_x_m, axis_y_m, z_m, samples, peak_temperature_planes,
        mesh_m, liquidus_K, accepted_step_count):
    """Persist the source peak planes bound to the two corridor section summaries.

    The artifact contains only source X planes referenced by the 4.9 mm and
    6.0 mm thermal-proxy observations. It preserves the source-plane indices
    and interpolation operation so the section coordinate can be audited or
    reconstructed without treating the summary geometry as an observation.
    """
    def invalid(message):
        raise ValueError(f"Invalid rectangular-corridor section field artifact: {message}")

    def finite_scalar(value):
        return (not isinstance(value, (bool, np.bool_))
                and isinstance(value, (int, float, np.integer, np.floating))
                and math.isfinite(float(value)))

    if (type(accepted_step_count) is not int or accepted_step_count <= 0):
        invalid("accepted step count must be a positive integer")
    if not finite_scalar(mesh_m) or float(mesh_m) <= 0:
        invalid("mesh must be positive and finite")
    if not finite_scalar(liquidus_K) or float(liquidus_K) <= 0:
        invalid("liquidus must be positive and finite")
    try:
        axis_x = np.asarray(axis_x_m, dtype=np.float64)
        axis_y = np.asarray(axis_y_m, dtype=np.float64)
        z = np.asarray(z_m, dtype=np.float64)
    except (TypeError, ValueError, OverflowError):
        invalid("coordinate axes must be numeric vectors")
    mesh = float(mesh_m)
    for name, axis in (("X", axis_x), ("Y", axis_y), ("Z", z)):
        if (axis.ndim != 1 or len(axis) < 2 or not np.isfinite(axis).all()
                or not np.all(np.diff(axis) > 0)
                or not np.allclose(np.diff(axis), mesh, rtol=1e-8, atol=1e-12)):
            invalid(f"{name} axis must be finite, increasing, and uniform at the declared mesh")
    if not isinstance(samples, (list, tuple)) or len(samples) != 2:
        invalid("exactly two section summaries are required")
    if not isinstance(peak_temperature_planes, dict):
        invalid("source peak planes must be a mapping")

    expected = {
        "single-line-x-4p9mm": 4.9,
        "single-line-x-6p0mm": 6.0,
    }
    normalized = []
    seen = set()
    scan_start_x_m = None
    plane_union = set()
    for row in samples:
        if not isinstance(row, dict):
            invalid("section summaries must be mappings")
        record_id = row.get("recordId")
        if record_id not in expected or record_id in seen:
            invalid("section summaries must uniquely identify the 4.9 mm and 6.0 mm locations")
        seen.add(record_id)
        distance = expected[record_id]
        if (row.get("status") != "thermal-proxy"
                or row.get("distanceFromScanStart_mm") != distance
                or row.get("operator") != RECTANGULAR_CORRIDOR_SECTION_OPERATOR
                or row.get("scanLineScope") != "one simulated +X track; not experimental repeats"
                or row.get("temporalAggregation") != "accepted-step maximum per source X plane, then spatially interpolated"
                or row.get("contourOperator") != "linear-liquidus-crossings-between-cell-centers-v1"
                or row.get("evidenceScope") != "Numerical thermal proxy; no etched-boundary or experimental validation; one simulated line only"):
            invalid("section summary is unsupported or has an unexpected observation contract")
        if (not isinstance(row.get("sampleCells"), int)
                or isinstance(row.get("sampleCells"), bool) or row["sampleCells"] <= 0
                or any(not finite_scalar(row.get(key)) or float(row[key]) <= 0
                       for key in ("width_um", "depth_um"))):
            invalid("section summary must have positive finite geometry and sampled cells")
        start_x = row.get("scanStartX_m")
        section_x = row.get("xCoordinate_m")
        if not finite_scalar(start_x) or not finite_scalar(section_x):
            invalid("section scan start and X coordinate must be finite")
        if scan_start_x_m is None:
            scan_start_x_m = float(start_x)
        elif not math.isclose(float(start_x), scan_start_x_m, rel_tol=0., abs_tol=1e-12):
            invalid("section summaries disagree on scan start")
        if not math.isclose(float(section_x), scan_start_x_m+distance*1e-3,
                            rel_tol=0., abs_tol=1e-12):
            invalid("section coordinate is detached from scan start and distance")

        indices = row.get("sourcePlaneIndices")
        positions = row.get("sourcePlaneX_m")
        fraction = row.get("interpolationFraction")
        interpolation = row.get("interpolationOperator")
        if (not isinstance(indices, (list, tuple)) or not isinstance(positions, (list, tuple))
                or len(indices) not in (1, 2) or len(positions) != len(indices)
                or any(type(index) is not int or not 0 <= index < len(axis_x) for index in indices)
                or any(not finite_scalar(position) for position in positions)
                or any(not math.isclose(float(axis_x[index]), float(position),
                                        rel_tol=0., abs_tol=1e-12)
                       for index, position in zip(indices, positions))):
            invalid("source-plane indices or positions are invalid")
        if not finite_scalar(fraction) or not 0. <= float(fraction) <= 1.:
            invalid("interpolation fraction must be finite and within [0, 1]")
        if interpolation == "exact-cell-center":
            if (len(indices) != 1 or float(fraction) != 0.
                    or not math.isclose(float(positions[0]), float(section_x),
                                        rel_tol=0., abs_tol=1e-12)):
                invalid("exact-cell-center provenance is inconsistent")
        elif interpolation == "linear-interpolation-between-accepted-peak-temperature-planes-v1":
            if (len(indices) != 2 or indices[1] != indices[0]+1
                    or not 0. < float(fraction) < 1.
                    or not axis_x[indices[0]] < float(section_x) < axis_x[indices[1]]):
                invalid("linear interpolation provenance is inconsistent")
            derived_fraction = ((float(section_x)-float(axis_x[indices[0]]))
                                / (float(axis_x[indices[1]])-float(axis_x[indices[0]])) )
            if not math.isclose(float(fraction), derived_fraction, rel_tol=1e-9, abs_tol=1e-12):
                invalid("interpolation fraction is detached from source-plane positions")
        else:
            invalid("unsupported interpolation operator")
        if any(index not in peak_temperature_planes for index in indices):
            invalid("a referenced source peak-temperature plane is missing")
        normalized.append((distance, float(section_x), list(indices), float(fraction),
                           interpolation, record_id))
        plane_union.update(indices)
    if seen != set(expected):
        invalid("one of the required section summaries is missing")
    normalized.sort(key=lambda row: row[0])

    plane_indices = sorted(plane_union)
    planes = []
    for index in plane_indices:
        try:
            field = np.asarray(peak_temperature_planes[index], dtype=np.float64)
        except (TypeError, ValueError, OverflowError):
            invalid("a source peak-temperature plane is not a numeric array")
        if field.shape != (len(axis_y), len(z)) or not np.isfinite(field).all():
            invalid("source peak-temperature planes must match the Y/Z grid and be finite")
        planes.append(field)

    padded_indices = np.full((2, 2), -1, dtype=np.int64)
    for row_index, (_, _, indices, _, _, _) in enumerate(normalized):
        padded_indices[row_index, :len(indices)] = indices
    arrays = {
        "schema_version": np.asarray(1, dtype=np.int64),
        "scan_start_x_m": np.asarray(scan_start_x_m, dtype=np.float64),
        "section_x_m": np.asarray([row[1] for row in normalized], dtype=np.float64),
        "section_distance_mm": np.asarray([row[0] for row in normalized], dtype=np.float64),
        "temperature_planes_K": np.stack(planes).astype(np.float64, copy=False),
        "plane_indices": np.asarray(plane_indices, dtype=np.int64),
        "plane_x_m": np.asarray([axis_x[index] for index in plane_indices], dtype=np.float64),
        "axis_y_m": axis_y,
        "z_m": z,
        "mesh_m": np.asarray(mesh, dtype=np.float64),
        "liquidus_K": np.asarray(float(liquidus_K), dtype=np.float64),
        "accepted_step_count": np.asarray(accepted_step_count, dtype=np.int64),
        "section_source_plane_indices": padded_indices,
        "section_interpolation_fraction": np.asarray([row[3] for row in normalized], dtype=np.float64),
        "section_interpolation_operator": np.asarray([row[4] for row in normalized], dtype=np.str_),
        "section_record_id": np.asarray([row[5] for row in normalized], dtype=np.str_),
    }
    if any(np.asarray(value).dtype.hasobject for value in arrays.values()):
        invalid("artifact arrays must not require pickle")
    try:
        path = Path(output_path)
        if not path.parent.is_dir():
            invalid("output directory does not exist")
        created = False
        try:
            with path.open("xb") as stream:
                created = True
                np.savez_compressed(stream, **arrays)
        except FileExistsError:
            invalid("output path already exists")
        except Exception:
            if created:
                path.unlink(missing_ok=True)
            raise
    except (TypeError, OSError) as exc:
        raise ValueError("Invalid rectangular-corridor section field artifact output path") from exc


def fixed_event_liquidus_cross_section(coordinates, temperature_K, x_position_m, dx_m,
                                      liquidus_K, substrate_interface_z_m=0.0):
    """Reconstruct a transverse liquidus section of one supplied event field.

    Ordered uniform Cartesian cell centers are interpolated to the physical X
    plane. Width uses all resolved Y/Z edge crossings; depth is measured below
    the original substrate interface. No temporal maximum, time verification,
    surface extrapolation, or equivalence to an etched section is implied.
    """
    result = dict(status="inconclusive", operator="fixed-event-x-linear-liquidus-section-v1",
                  temporalSelection="single accepted event supplied by caller; time alignment not verified here",
                  contour="linear liquidus crossings between neighboring Y/Z cell centers",
                  surfaceTreatment="no-extrapolation", topBoundaryMolten=False,
                  depthReference="original substrate interface",
                  experimentalValidation=False,
                  evidenceScope="Numerical thermal proxy; no etched-boundary or experimental equivalence",
                  width_um=None, depth_um=None)
    try:
        xyz = np.asarray(coordinates, dtype=float)
        temperature = np.asarray(temperature_K, dtype=float)
        x_position, dx, liquidus, interface = map(float, (
            x_position_m, dx_m, liquidus_K, substrate_interface_z_m))
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "Invalid numeric section inputs"
        return result
    if (xyz.ndim != 2 or xyz.shape[1] != 3 or temperature.shape != (len(xyz),)
            or not len(xyz) or not np.isfinite(xyz).all()
            or not np.isfinite(temperature).all() or np.any(temperature <= 0)
            or not all(math.isfinite(v) for v in (x_position, dx, liquidus, interface))
            or dx <= 0 or liquidus <= 0):
        result["reason"] = "Invalid finite Cartesian field or physical section inputs"
        return result
    axes = [np.unique(xyz[:, dimension]) for dimension in range(3)]
    shape = tuple(len(axis) for axis in axes)
    if (any(n < 2 for n in shape) or math.prod(shape) != len(xyz)
            or any(not np.allclose(np.diff(axis), dx, rtol=1e-8, atol=dx*1e-8)
                   for axis in axes)):
        result["reason"] = "Section field is not a nondegenerate uniform Cartesian grid"
        return result
    grid = xyz.reshape(*shape, 3)
    for dimension, axis in enumerate(axes):
        axis_shape = [1, 1, 1]
        axis_shape[dimension] = len(axis)
        if not np.allclose(grid[..., dimension], axis.reshape(axis_shape),
                           rtol=0, atol=dx*1e-8):
            result["reason"] = "Section field is not an ordered Cartesian grid"
            return result
    axis_x, axis_y, axis_z = axes
    result.update(xPosition_m=x_position, substrateInterfaceZ_m=interface,
                  mesh_um=dx*1e6, sampledZRange_m=[float(axis_z[0]), float(axis_z[-1])])
    if x_position < axis_x[0] or x_position > axis_x[-1]:
        result["reason"] = "Physical section lies outside X cell-center support"
        return result
    upper = int(np.searchsorted(axis_x, x_position))
    if axis_x[upper] == x_position:
        lower, fraction = upper, 0.
    else:
        lower = upper - 1
        fraction = float((x_position-axis_x[lower]) / (axis_x[upper]-axis_x[lower]))
    values = temperature.reshape(shape)
    section = (1.-fraction)*values[lower] + fraction*values[upper]
    molten = section >= liquidus
    result.update(sourcePlaneIndices=[lower, upper], xInterpolationFraction=fraction,
                  sampleCells=int(np.count_nonzero(molten)),
                  topBoundaryMolten=bool(molten[:, -1].any()))
    if not result["sampleCells"]:
        result["status"] = "no-melt"
        return result
    if molten[0].any() or molten[-1].any() or molten[:, 0].any():
        result["reason"] = "Liquidus contour reaches a lateral or bottom domain boundary"
        return result
    yz = np.stack(np.meshgrid(axis_y, axis_z, indexing="ij"), axis=-1)
    points = []
    for dimension in range(2):
        lower_slice, upper_slice = [slice(None)]*2, [slice(None)]*2
        lower_slice[dimension], upper_slice[dimension] = slice(None, -1), slice(1, None)
        low, high = tuple(lower_slice), tuple(upper_slice)
        pairs = molten[low] != molten[high]
        if pairs.any():
            fractions = (liquidus-section[low][pairs]) / (section[high][pairs]-section[low][pairs])
            points.append(yz[low][pairs] + fractions[:, None]*(yz[high][pairs]-yz[low][pairs]))
    if not points:
        result["reason"] = "Liquidus contour is not resolved between cell centers"
        return result
    crossings = np.concatenate(points)
    width = float(np.ptp(crossings[:, 0]))
    if len(crossings) < 2 or width <= 0:
        result["reason"] = "Liquidus contour has no positive resolved width"
        return result
    result.update(status="thermal-proxy", width_um=width*1e6,
                  depth_um=max(0., interface-float(crossings[:, 1].min()))*1e6,
                  crossingCount=int(len(crossings)))
    return result


def interpolated_peak_melt_pool(coordinates, temperature, surface, angle, dx, liquidus_K):
    """Width/depth from linear liquidus crossings on a Cartesian peak field.

    The field is the same accepted step selected by the cell-volume peak
    tracker. Contour vertices are reconstructed only between active neighboring
    cell centers; no boundary or surface extrapolation is performed.
    """
    xyz = np.asarray(coordinates, dtype=float)
    temperature = np.asarray(temperature, dtype=float).ravel()
    result = dict(status="inconclusive", operator="peak-liquidus-cell-edge-linear-contour-v1",
                  temporalSelection=PEAK_EXTRACTION,
                  contour="linear liquidus crossings between neighboring active cell centers",
                  surfaceTreatment="No temperature extrapolation to the model surface",
                  width_um=None, depth_um=None,
                  evidenceScope="Numerical thermal proxy; no experimental validation")
    if (xyz.ndim != 2 or xyz.shape[1] != 3 or len(xyz) != len(temperature)
            or not len(xyz) or not np.isfinite(xyz).all() or not np.isfinite(temperature).all()
            or not np.isfinite(surface) or not np.isfinite(angle) or not np.isfinite(dx)
            or not np.isfinite(liquidus_K) or dx <= 0):
        raise ValueError("Invalid peak field for interpolated melt-pool contour")
    indices = np.rint((xyz - xyz.min(axis=0)) / dx).astype(int)
    shape = tuple((indices.max(axis=0) + 1).tolist())
    expected = np.arange(len(xyz))
    linear = (indices[:, 0] * shape[1] + indices[:, 1]) * shape[2] + indices[:, 2]
    if (np.prod(shape) != len(xyz) or not np.array_equal(linear, expected)
            or not np.allclose(xyz, xyz.min(axis=0) + indices*dx, rtol=0, atol=dx*1e-6)):
        result["reason"] = "Peak field is not an ordered uniform Cartesian grid"
        return result
    if any(n < 2 for n in shape):
        result["reason"] = "Peak field has fewer than two centers on an axis"
        return result
    grid = xyz.reshape(*shape, 3)
    values = temperature.reshape(shape)
    active = grid[..., 2] < surface
    molten = (values >= liquidus_K) & active
    result["sampleCells"] = int(np.count_nonzero(molten))
    if not result["sampleCells"]:
        result["status"] = "no-melt"
        return result
    if (molten[0].any() or molten[-1].any() or molten[:, 0].any()
            or molten[:, -1].any() or molten[:, :, 0].any()):
        result["reason"] = "Liquidus contour reaches a lateral or bottom domain boundary"
        return result
    normal = np.array([-math.sin(math.radians(angle)), math.cos(math.radians(angle)), 0.])
    width_min, width_max, deepest = math.inf, -math.inf, math.inf
    crossing_count = 0
    for dimension in range(3):
        lower = [slice(None)]*3
        upper = [slice(None)]*3
        lower[dimension] = slice(None, -1)
        upper[dimension] = slice(1, None)
        lower, upper = tuple(lower), tuple(upper)
        pairs = ((values[lower] >= liquidus_K) != (values[upper] >= liquidus_K))
        pairs &= active[lower] & active[upper]
        if not pairs.any():
            continue
        fraction = (liquidus_K-values[lower][pairs]) / (values[upper][pairs]-values[lower][pairs])
        point = grid[lower][pairs] + fraction[:, None]*(grid[upper][pairs]-grid[lower][pairs])
        widths = point @ normal
        width_min = min(width_min, float(widths.min()))
        width_max = max(width_max, float(widths.max()))
        deepest = min(deepest, float(point[:, 2].min()))
        crossing_count += len(point)
    result["crossingCount"] = crossing_count
    if crossing_count < 2 or width_max <= width_min or deepest >= surface:
        result["reason"] = "Liquidus contour is not resolved between cell centers"
        return result
    result.update(status="thermal-proxy", width_um=(width_max-width_min)*1e6,
                  depth_um=(surface-deepest)*1e6)
    return result


class PeakMeltTracker:
    def __init__(self, coordinates, dx, material, track_tied_contours=False,
                 capture_tied_fields=False):
        self.xyz = np.asarray(coordinates)
        self.dx, self.m = dx, material
        self.track_tied_contours = bool(track_tied_contours)
        self.capture_tied_fields = bool(capture_tied_fields)
        if self.capture_tied_fields and not self.track_tied_contours:
            raise ValueError("Capturing tied peak fields requires contour tracking")
        self._tied_contours = []
        self._tied_fields = []
        self.count = self.sampled_count = 0
        self.state = None
        self.equal_maximum_count = 0
        self.first_equal_maximum_time = self.last_equal_maximum_time = None

    def observe(self, temperature, surface, angle, time, step, sampled=False):
        temperature = np.asarray(temperature).ravel()
        active = self.xyz[:, 2] < surface
        count = int(np.count_nonzero((temperature >= self.m['liquidus_K']) & active))
        if sampled:
            self.sampled_count = max(self.sampled_count, count)
        if count > self.count:
            self.count = count
            self.state = (temperature.copy(), active, surface, angle, float(time), int(step))
            self.equal_maximum_count = 1
            self.first_equal_maximum_time = self.last_equal_maximum_time = float(time)
            if self.track_tied_contours:
                self._tied_contours = []
                self._tied_fields = []
                self._record_tied_contour(temperature, surface, angle, time, step)
        elif count > 0 and count == self.count:
            self.equal_maximum_count += 1
            self.last_equal_maximum_time = float(time)
            if self.track_tied_contours:
                self._record_tied_contour(temperature, surface, angle, time, step)

    def _record_tied_contour(self, temperature, surface, angle, time, step):
        contour = interpolated_peak_melt_pool(
            self.xyz, temperature, surface, angle, self.dx, self.m['liquidus_K'])
        self._tied_contours.append(dict(
            time_s=float(time), step=int(step), status=contour.get("status"),
            width_um=contour.get("width_um"), depth_um=contour.get("depth_um")))
        if self.capture_tied_fields:
            self._tied_fields.append((temperature.copy(), float(surface), float(angle),
                                      float(time), int(step)))

    def finish(self, artifact_dir, observed_steps):
        metrics = dict(length_um=0., width_um=0., depth_um=0., volume_um3=0., crossSectionArea_um2=0.)
        time = step = None
        path = Path(artifact_dir)/'peak-field.npz' if artifact_dir else None
        if self.state is not None:
            temperature, active, surface, angle, time, step = self.state
            interpolated = interpolated_peak_melt_pool(
                self.xyz, temperature, surface, angle, self.dx, self.m['liquidus_K'])
            melt = (temperature >= self.m['liquidus_K']) & active
            x, y, z = self.xyz[melt].T
            c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            extent = self.dx*(abs(c)+abs(s))
            # Generated Cartesian x planes can differ by roundoff in OpenFOAM.
            planes = np.rint((x-self.xyz[:, 0].min())/self.dx).astype(int)
            metrics.update(length_um=float(np.ptp(x*c+y*s)+extent)*1e6,
                           width_um=float(np.ptp(-x*s+y*c)+extent)*1e6,
                           depth_um=max(0., surface-float(z.min())+self.dx/2)*1e6,
                           volume_um3=self.count*self.dx**3*1e18,
                           crossSectionArea_um2=float(np.bincount(planes).max())*self.dx**2*1e12)
            if path:
                np.savez_compressed(path, coordinates_m=self.xyz, T_K=temperature,
                                    active=active, liquid_fraction=np.clip((temperature-self.m['solidus_K'])/
                                    (self.m['liquidus_K']-self.m['solidus_K']), 0, 1)*active,
                                    surface_m=surface, scanAngle_deg=angle, time_s=time, step=step,
                                    liquidus_K=self.m['liquidus_K'], mesh_m=self.dx)
        elif path:
            path.unlink(missing_ok=True)
        if self.state is None:
            interpolated = dict(status="no-melt", operator="peak-liquidus-cell-edge-linear-contour-v1",
                                temporalSelection=PEAK_EXTRACTION, width_um=None, depth_um=None,
                                evidenceScope="Numerical thermal proxy; no experimental validation")
        diagnostics = dict(meltPoolExtraction=PEAK_EXTRACTION, peakMeltTime_s=time,
                           peakMeltStep=step, meltPoolObservedSteps=int(observed_steps),
                           peakMeltCellCount=self.count,
                           equalMaximumEndpointCount=self.equal_maximum_count,
                           firstEqualMaximumTime_s=self.first_equal_maximum_time,
                           lastEqualMaximumTime_s=self.last_equal_maximum_time,
                           sampledPeakMeltVolume_um3=self.sampled_count*self.dx**3*1e18,
                           peakMeltSamplingLossFraction=(self.count-self.sampled_count)/self.count if self.count else 0.,
                           interpolatedPeakMeltPool=interpolated)
        if self.track_tied_contours:
            valid = [row for row in self._tied_contours
                     if row["status"] == "thermal-proxy"
                     and all(isinstance(row[key], (int, float)) and math.isfinite(row[key])
                             for key in ("width_um", "depth_um"))]
            summary = dict(operator="peak-liquidus-cell-edge-linear-contour-v1",
                           endpointCount=self.equal_maximum_count,
                           observedContourCount=len(self._tied_contours),
                           validContourCount=len(valid),
                           invalidContourCount=len(self._tied_contours)-len(valid),
                           first=copy_contour_endpoint(self._tied_contours[0]) if self._tied_contours else None,
                           last=copy_contour_endpoint(self._tied_contours[-1]) if self._tied_contours else None)
            for key in ("width_um", "depth_um"):
                values = [float(row[key]) for row in valid]
                summary[key] = (dict(min=min(values), median=float(np.median(values)), max=max(values))
                                if values else None)
            if self.capture_tied_fields and artifact_dir and self._tied_fields:
                tied_path = Path(artifact_dir)/"peak-tied-maximum-fields.npz"
                np.savez_compressed(
                    tied_path, T_K=np.stack([row[0] for row in self._tied_fields]),
                    surface_m=np.asarray([row[1] for row in self._tied_fields]),
                    scanAngle_deg=np.asarray([row[2] for row in self._tied_fields]),
                    time_s=np.asarray([row[3] for row in self._tied_fields]),
                    step=np.asarray([row[4] for row in self._tied_fields], dtype=np.int64),
                    liquidus_K=self.m["liquidus_K"], mesh_m=self.dx)
                summary["capturedFieldsArtifact"] = tied_path.name
            diagnostics["tiedPeakContourSpread"] = summary
        return metrics, diagnostics


def copy_contour_endpoint(row):
    return {key: row[key] for key in ("time_s", "step", "status", "width_um", "depth_um")}
