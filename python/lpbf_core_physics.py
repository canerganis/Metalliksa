import math
from functools import lru_cache
import numpy as np
from lpbf_material_registry import property_at as _registry_property_at
from lpbf_material_registry import enthalpy_table as _registry_enthalpy_table

SOURCE_INTEGRATION = "cell-integrated-gaussian-adaptive-gl-v2"
GAUSS_NODES = (.5-.5/math.sqrt(3), .5+.5/math.sqrt(3))
SOURCE_QUADRATURE_MAX_ORDER = 256
SOURCE_QUADRATURE_RELATIVE_TOLERANCE = 1e-8


@lru_cache(maxsize=32)
def source_gauss_rule(order):
    """Immutable Gauss-Legendre nodes and unit-sum weights on [0, 1]."""
    if order == 2:
        return GAUSS_NODES, (.5, .5)
    nodes, weights = np.polynomial.legendre.leggauss(order)
    return tuple((nodes+1)*.5), tuple(weights*.5)


def source_time_quadrature(segment, dt, radius):
    """Select temporal order from the laser's XY travel in beam radii.

    Long intervals require an additional N-versus-2N field convergence check.
    The finite ceiling rejects unresolved intervals rather than lowering order.
    """
    duration = segment["end_s"]-segment["start_s"]
    if not all(math.isfinite(v) and v > 0 for v in (dt, duration, radius)):
        raise ValueError("Source duration, interval and radius must be positive and finite")
    travel = np.linalg.norm(np.asarray(segment["end"], dtype=float)[:2]
                            - np.asarray(segment["start"], dtype=float)[:2])*dt/duration
    ratio = float(travel/radius)
    if not math.isfinite(ratio):
        raise ValueError("Source scan displacement must be finite")
    for bound, order in ((.1, 2), (.5, 4), (1., 6), (2., 8), (4., 20)):
        if ratio <= bound:
            return order, False
    order = max(20, 4*math.ceil(3*ratio/4))
    if 2*order > SOURCE_QUADRATURE_MAX_ORDER:
        raise ValueError("Moving source quadrature exceeds maximum order; shorten the source interval")
    return order, True


def _evaluate(function, values):
    values = np.asarray(values)
    return np.fromiter((function(float(x)) for x in values.flat), dtype=float, count=values.size).reshape(values.shape)


def gaussian_interval(lower, upper, center, radius):
    """Integral of the normalized exp(-2*(x-center)^2/radius^2) density."""
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError("Gaussian radius must be positive and finite")
    a = math.sqrt(2)*(np.asarray(lower)-center)/radius
    b = math.sqrt(2)*(np.asarray(upper)-center)/radius
    # erfc preserves small tail masses that subtraction of two rounded ones loses.
    value = np.where(a >= 0, .5*(_evaluate(math.erfc, a)-_evaluate(math.erfc, b)),
                     np.where(b <= 0, .5*(_evaluate(math.erfc, -b)-_evaluate(math.erfc, -a)), .5*(_evaluate(math.erf, b)-_evaluate(math.erf, a))))
    return np.where(b > a, np.maximum(value, 0.), 0.)


def cell_weights(axis, z, dx, position, surface, radius, penetration, axis_y=None):
    """Unnormalized probability mass; z is clipped, mass cells are not cut cells."""
    axis_y = axis if axis_y is None else np.asarray(axis_y)
    gx = gaussian_interval(axis-dx/2, axis+dx/2, position[0], radius)
    gy = gaussian_interval(axis_y-dx/2, axis_y+dx/2, position[1], radius)
    gz = gaussian_interval(z-dx/2, np.minimum(z+dx/2, surface), surface, penetration)
    gz = np.where(z < surface, gz, 0.)
    return gx[:, None, None]*gy[None, :, None]*gz[None, None, :]


def _oblique_cell_weights(axis, z, axis_y, dx, position, surface, radius, penetration,
                          incidence_angle_deg, incidence_azimuth_deg):
    """Approximate oblique Gaussian cell masses with tensor Gauss-Legendre quadrature."""
    theta = math.radians(incidence_angle_deg)
    azimuth = math.radians(incidence_azimuth_deg)
    cos_theta = math.cos(theta)
    sin_azimuth, cos_azimuth = math.sin(azimuth), math.cos(azimuth)
    radius_parallel = radius/cos_theta
    effective_penetration = penetration*cos_theta
    density_scale = (math.sqrt(2/math.pi)/radius_parallel
                     * math.sqrt(2/math.pi)/radius
                     * math.sqrt(2/math.pi)/effective_penetration)
    # Five points accurately resolve the projected Gaussian for the supported mesh sizes.
    nodes, quadrature_weights = np.polynomial.legendre.leggauss(5)
    x_samples = axis[:, None] + nodes[None, :]*(dx/2)
    y_samples = axis_y[:, None] + nodes[None, :]*(dx/2)
    result = np.zeros((len(axis), len(axis_y), len(z)))
    for k, z_center in enumerate(z):
        lower = z_center-dx/2
        upper = min(z_center+dx/2, surface)
        if z_center >= surface or upper <= lower:
            continue
        z_samples = (lower+upper)/2 + nodes*(upper-lower)/2
        # Integrate the normal-profile density and moving lateral footprint together.
        for z_node, wz in zip(z_samples, quadrature_weights):
            depth = surface-z_node
            center_x = position[0] + depth*math.tan(theta)*cos_azimuth
            center_y = position[1] + depth*math.tan(theta)*sin_azimuth
            for ix, x_node in enumerate(nodes):
                x = x_samples[:, ix, None]
                for iy, y_node in enumerate(nodes):
                    y = y_samples[None, :, iy]
                    along = (x-center_x)*cos_azimuth + (y-center_y)*sin_azimuth
                    across = -(x-center_x)*sin_azimuth + (y-center_y)*cos_azimuth
                    density = density_scale*np.exp(-2*((along/radius_parallel)**2+(across/radius)**2
                                                        +(depth/effective_penetration)**2))
                    result[:, :, k] += (wz*quadrature_weights[ix]*quadrature_weights[iy]
                                         * density*((upper-lower)/2)*(dx/2)**2)
    return result


def integrated_source(axis, z, dx, segment, time, dt, surface, radius, penetration, power, axis_y=None,
                      incidence_angle_deg=0.0, incidence_azimuth_deg=0.0):
    """Time-averaged volumetric power [W/m³] and minimum captured half-space mass."""
    axis_y = axis if axis_y is None else np.asarray(axis_y)
    source = np.zeros((len(axis), len(axis_y), len(z)))
    if (isinstance(incidence_angle_deg, (bool, np.bool_))
            or not isinstance(incidence_angle_deg, (int, float, np.number))
            or not math.isfinite(float(incidence_angle_deg))
            or not 0 <= float(incidence_angle_deg) < 90):
        raise ValueError("Incidence angle must be finite and in [0, 90) degrees")
    if (isinstance(incidence_azimuth_deg, (bool, np.bool_))
            or not isinstance(incidence_azimuth_deg, (int, float, np.number))
            or not math.isfinite(float(incidence_azimuth_deg))
            or not 0 <= float(incidence_azimuth_deg) < 360):
        raise ValueError("Incidence azimuth must be finite and in [0, 360) degrees")
    incidence_angle_deg = float(incidence_angle_deg)
    incidence_azimuth_deg = float(incidence_azimuth_deg)
    if segment is None:
        return source, 1.
    if dt <= 0 or time < segment["start_s"]-1e-13 or time+dt > segment["end_s"]+1e-13:
        raise ValueError("Source interval must remain inside one laser-on segment")
    start, stop = np.asarray(segment["start"]), np.asarray(segment["end"])
    order, refine = source_time_quadrature(segment, dt, radius)
    minimum_capture = 1.
    previous = None
    while True:
        source.fill(0.)
        nodes, temporal_weights = source_gauss_rule(order)
        for node, temporal_weight in zip(nodes, temporal_weights):
            fraction = np.clip((time+node*dt-segment["start_s"])/(segment["end_s"]-segment["start_s"]), 0., 1.)
            position = start+fraction*(stop-start)
            if incidence_angle_deg == 0:
                weights = cell_weights(axis, z, dx, position, surface, radius, penetration, axis_y)
            else:
                weights = _oblique_cell_weights(axis, z, axis_y, dx, position, surface, radius,
                                                 penetration, incidence_angle_deg, incidence_azimuth_deg)
            total = float(weights.sum())
            if not math.isfinite(total) or total <= 0:
                raise ValueError("Gaussian source is outside the represented active domain")
            minimum_capture = min(minimum_capture, 2*total)
            source += weights*(temporal_weight*power/(total*dx**3))
        if not refine:
            return source, minimum_capture
        if previous is not None:
            difference = np.linalg.norm(source-previous)
            scale = np.linalg.norm(source)
            if difference <= SOURCE_QUADRATURE_RELATIVE_TOLERANCE*scale:
                return source, minimum_capture
        if 2*order > SOURCE_QUADRATURE_MAX_ORDER:
            raise ValueError("Moving source quadrature did not converge; shorten the source interval")
        previous = source.copy()
        order *= 2

def calculate_mesh_domain(p):
    """Calculates the 3D computational domain size and discretization (SI units)."""
    radius = p["beamDiameter_um"] * 0.5e-6
    dx_requested = p["mesh_um"] * 1e-6
    span = p["trackLength_um"] * 1e-6 + (p["tracks"] - 1) * p["hatch_um"] * 1e-6 + 6 * radius
    layer_conforming = p.get("powderGridPolicy") == "layer-conforming"
    rectangular_corridor = (p.get("surfaceMode", "powder-layer") == "bare-plate"
                            and p.get("barePlateGeometry", "square") == "rectangular-corridor")
    if rectangular_corridor:
        # One +X track: preserve the full scan history in a centered frame.
        # The default retains twelve beam radii total; explicit widths support
        # bounded transverse-width sensitivity without changing the square path.
        span_y = (p.get("corridorWidth_um") or 12 * radius * 1e6) * 1e-6
        nx = int(math.ceil(span / dx_requested))
        dx = span / nx
        ny = int(math.ceil(span_y / dx))
        if ny % 2 == 0:
            ny += 1  # keep y=0 on a cell center for the centered single-track source
        nxy = nx  # compatibility alias for the legacy square-domain field
    elif layer_conforming:
        # Preserve whole-cell material semantics by placing z=0 and every
        # equal-thickness powder-layer surface on a cell face. Pad X/Y by less
        # than one cell when necessary so the grid remains cubic and centered.
        layer_m = p["layer_um"] * 1e-6
        layer_cells = max(1, int(math.ceil(layer_m / dx_requested - 1e-12)))
        dx = layer_m / layer_cells
        nxy_ratio = span / dx
        nxy_nearest = round(nxy_ratio)
        nxy = (int(nxy_nearest) if math.isclose(nxy_ratio, nxy_nearest, rel_tol=1e-12, abs_tol=1e-12)
               else int(math.ceil(nxy_ratio)))
        span = nxy * dx
        nx = ny = nxy
        span_y = span
    else:
        nxy = int(math.ceil(span / dx_requested))
        dx = span / nxy
        nx = ny = nxy
        span_y = span
    substrate_depth = math.ceil(max(300e-6, 4 * radius) / dx) * dx
    height = 0. if p.get("surfaceMode", "powder-layer") == "bare-plate" else p["layers"] * p["layer_um"] * 1e-6
    nz_ratio = (substrate_depth + height) / dx
    nz = int(round(nz_ratio)) if layer_conforming else int(math.ceil(nz_ratio))
    
    return {
        "radius": radius,
        "span": span,
        "span_x": span,
        "span_y": span_y,
        "effective_span_y": ny * dx,
        "nx": nx,
        "ny": ny,
        "nxy": nxy,
        "nz": nz,
        "dx": dx,
        "substrate_depth": substrate_depth
    }


def thermal_si_inputs(p, material):
    """Resolve shared reference/OpenFOAM thermal inputs to SI units."""
    return {
        "preheat_K": p["preheat_C"] + 273.15,
        "layer_m": p["layer_um"] * 1e-6,
        "speed_m_s": p["speed_mm_s"] * 1e-3,
        "absorbed_power_W": p["power_W"] * material["absorptivity"],
    }


def property_at(material, temperature, column):
    """Shared LPBF material-property interpolation boundary (temperature in K)."""
    return _registry_property_at(material, temperature, column)


def enthalpy_table(material):
    """Shared LPBF enthalpy boundary; preserves the versioned registry law."""
    return _registry_enthalpy_table(material)


def scan_segments(p):
    length, speed = p["trackLength_um"]*1e-6, p["speed_mm_s"]*1e-3
    time = 0.
    segments = []
    for layer in range(int(p["layers"])):
        theta = math.radians(p["scanAngle_deg"]+layer*p["layerRotation_deg"])
        u, v = np.array([math.cos(theta), math.sin(theta)]), np.array([-math.sin(theta), math.cos(theta)])
        tracks = int(p["tracks"])
        groups = []
        if p["strategy"] == "island":
            across = max(1, int(p["islandSize_um"]/p["hatch_um"]))
            columns = math.ceil(p["trackLength_um"]/p["islandSize_um"])
            for row_start in range(0,tracks,across):
                order = range(columns) if (row_start//across)%2 == 0 else reversed(range(columns))
                for col in order:
                    a = -length/2+col*length/columns
                    b = a+length/columns
                    groups.extend((track,a,b,(-1 if (track-row_start)%2 else 1),f"{row_start//across}:{col}")
                                  for track in range(row_start,min(tracks,row_start+across)))
        else:
            stripe_tracks = max(1,int(p["stripeWidth_um"]/p["hatch_um"]))
            for track in range(tracks):
                parity = track%stripe_tracks if p["strategy"] == "stripe" else track
                direction = -1 if p["strategy"] != "unidirectional" and parity%2 else 1
                groups.append((track,-length/2,length/2,direction,None))
        for track,a,b,direction,island in groups:
            offset = (track-(tracks-1)/2)*p["hatch_um"]*1e-6*v
            start,end = offset+(a if direction>0 else b)*u,offset+(b if direction>0 else a)*u
            duration = (b-a)/speed
            segments.append(dict(start_s=time,end_s=time+duration,start=start.tolist(),end=end.tolist(),
                                 layer=layer,track=track,island=island))
            time += duration+p["dwell_s"]
    return segments, time+p["cooling_s"]


def evaluate_material_properties(m, T):
    """
    Evaluates temperature-dependent material properties at temperature T (K).
    Returns density, thermal conductivity, specific heat, and dynamic viscosity.
    """
    rho = float(property_at(m, T, 1))
    k = float(property_at(m, T, 2))
    cp = float(property_at(m, T, 3))
    mu = float(property_at(m, T, 4))
    return rho, k, cp, mu
