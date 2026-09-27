"""Conservative transient enthalpy finite-volume reference solver, SI internally.

Fixed material domain: no momentum, free surface, evaporation or shrinkage.
The boiling boundary is a validity STOP, never a clipped temperature result.
"""
import copy
import hashlib
import json
import math
import datetime
from pathlib import Path
import numpy as np
from lpbf_material_registry import material
from lpbf_core_physics import property_at, enthalpy_table
from lpbf_core_physics import calculate_mesh_domain, scan_segments, thermal_si_inputs, SOURCE_INTEGRATION
from lpbf_core_contract import build_core_contract
from lpbf_verification import compare, convergence
from lpbf_heat_source import (MINIMUM_SOURCE_CAPTURE_FRACTION, require_source_capture,
                              source_limited_step, conduction_diagonal)
from lpbf_layered_conduction import conduction_heat_rate
from lpbf_ss304_support_material import (ss304_support_thermal_fields,
                                          ss304_support_thermal_snapshot,
                                          REFERENCE_TEMPERATURE_K,
                                          MAXIMUM_TEMPERATURE_K)
from lpbf_defect_diagnostics import defect_diagnostics
from lpbf_peak import (PeakMeltTracker, midtrack_bare_plate_section,
                       interpolated_midtrack_bare_plate_section,
                       rectangular_corridor_section_samples,
                       rectangular_corridor_section_observations)
from lpbf_overlap import FieldOverlapTracker, OVERLAP_MODEL_ID
from lpbf_evidence import finite_tree, measurement_evidence, resource_estimate, thermal_audits, enforce_thermal_balances, write_artifacts, FieldRecorder

VERSION = "enthalpy-fv-6"
IMPLEMENTATION_FINGERPRINT_SCHEMA = "lpbf-thermal-implementation-manifest-v2"
# Reviewed production closure for the shared thermal path and supported CPU,
# OpenFOAM, CUDA, and Warp implementations. Keep orchestration, tests, scratch
# scripts, and unrelated physics modules out of this numerical implementation ID.
IMPLEMENTATION_SOURCE_FILES = (
    "four_alloy_materials.py",
    "eagar_tsai_solver.py",
    "fabbro_keyhole.py",
    "goldak_solver.py",
    "in625_gpu_thermal_material.py",
    "in625_thermal_material.py",
    "lpbf_core_contract.py",
    "lpbf_core_physics.py",
    "lpbf_cfd.py",
    "lpbf_defect_diagnostics.py",
    "lpbf_evidence.py",
    "lpbf_gpu_thermal.py",
    "lpbf_gpu_thermal_warp.py",
    "lpbf_heat_source.py",
    "lpbf_layered_conduction.py",
    "lpbf_material_registry.py",
    "marangoni_screening.py",
    "lpbf_openfoam.py",
    "lpbf_overlap.py",
    "lpbf_peak.py",
    "powder_packer.py",
    "powder_bed_raytracer.py",
    "lpbf_simulation.py",
    "lpbf_ss304_support_material.py",
    "lpbf_thermal_solver.py",
    "lpbf_transient_3d_gpu.py",
    "lpbf_verification.py",
    "solidification_front.py",
    "warp_thermal_solver.py",
    "openfoam/Make/files",
    "openfoam/Make/options",
    "openfoam/metalliksaThermal.C",
)
DEFAULTS = dict(mode="screening", material="Inconel 718", power_W=200., speed_mm_s=800.,
                beamDiameter_um=80., preheat_C=80., layer_um=40., hatch_um=100.,
                mesh_um=20., maxDt_s=1e-6, trackLength_um=600., tracks=1, layers=1,
                dwell_s=0.0002, cooling_s=0.0005, scanAngle_deg=0., layerRotation_deg=67.,
                strategy="meander", stripeWidth_um=500., islandSize_um=200., packingFraction=0.55, powderConductivityRatio=0.12,
                convection_W_m2K=20., timeout_s=300., study="none", backend="auto",
                surfaceMode="powder-layer", sourcePenetration_um=None,
                barePlateGeometry="square")
BOUNDS = dict(power_W=(10, 1500), speed_mm_s=(10, 10000), beamDiameter_um=(20, 500),
              preheat_C=(0, 1200), layer_um=(10, 150), hatch_um=(10, 1000), mesh_um=(5, 80),
              maxDt_s=(1e-9, 1e-4), trackLength_um=(100, 10000), tracks=(1, 8), layers=(1, 5),
              dwell_s=(0, .1), cooling_s=(0, .1), scanAngle_deg=(-360, 360),
              layerRotation_deg=(-360, 360), packingFraction=(.2, 1),
              stripeWidth_um=(20,3000), islandSize_um=(50,3000),
              powderConductivityRatio=(.01, 1), convection_W_m2K=(0, 1000), timeout_s=(10, 3600))


def summarize_accepted_timesteps(accepted_dt_s, requested_max_dt_s, source_limited_steps, source_retries):
    """Summarize realized positive steps without changing the solver schedule.

    ``eulerFirstOrderWeightedDt_s`` is the diagnostic scale sum(dt**2)/T for
    first-order local-error accumulation. It is descriptive, not an automatic
    convergence pass criterion; the step distribution must also be reviewed.
    """
    if (isinstance(requested_max_dt_s, bool) or not isinstance(requested_max_dt_s, (int, float))
            or not math.isfinite(requested_max_dt_s) or requested_max_dt_s <= 0
            or type(source_limited_steps) is not int or source_limited_steps < 0
            or type(source_retries) is not int or source_retries < source_limited_steps):
        raise ValueError("Invalid accepted-timestep summary inputs")
    dt = np.asarray(accepted_dt_s, dtype=np.float64)
    if (dt.ndim != 1 or dt.size == 0 or not np.isfinite(dt).all()
            or np.any(dt <= 0) or source_limited_steps > dt.size):
        raise ValueError("Accepted timesteps must be a nonempty finite positive sequence")
    total = float(np.sum(dt, dtype=np.float64))
    squared_total = float(np.dot(dt, dt))
    if not math.isfinite(total) or not math.isfinite(squared_total) or total <= 0:
        raise ValueError("Accepted timestep totals must be finite and positive")
    cap_tolerance = max(float(requested_max_dt_s) * 1e-12, 1e-30)
    at_requested_cap = np.abs(dt - float(requested_max_dt_s)) <= cap_tolerance
    return {
        "methodId": "accepted-timestep-distribution-v1",
        "count": int(dt.size),
        "total_s": total,
        "sumSquared_s2": squared_total,
        "mean_s": total / int(dt.size),
        "minimum_s": float(np.min(dt)),
        "p50_s": float(np.quantile(dt, .50)),
        "p90_s": float(np.quantile(dt, .90)),
        "p99_s": float(np.quantile(dt, .99)),
        "maximum_s": float(np.max(dt)),
        "eulerFirstOrderWeightedDt_s": squared_total / total,
        "requestedMaxDt_s": float(requested_max_dt_s),
        "requestedMaxDtHitFraction": float(np.count_nonzero(at_requested_cap) / dt.size),
        "sourceLimitedStepCount": source_limited_steps,
        "sourceTimestepRetries": source_retries,
    }


def validate(raw):
    layered_fields = {"thermalModelId", "plateThickness_um", "supportThickness_um",
                      "contactResistance_m2K_W", "supportBottomBoundary",
                      "incidenceAngle_deg", "incidenceAzimuth_deg", "beamProfileModelId",
                      "sourcePenetration_um"}
    if not isinstance(raw, dict) or set(raw)-set(DEFAULTS)-{"properties", "measurements", "absorptivity", "emissivity", "corridorWidth_um", "powderGridPolicy"}-layered_fields:
        raise ValueError("Unknown simulation input fields")
    finite_tree(raw)
    p = {**DEFAULTS, **raw}
    layered = "thermalModelId" in raw
    if layered:
        required_layered = layered_fields
        if ((set(raw) & layered_fields) != required_layered
                or raw.get("thermalModelId") != "layered-plate-enthalpy-v1"):
            raise ValueError("Layered-plate model requires all explicit versioned sensitivity inputs")
        if (p["mode"] != "standard" or p["backend"] != "reference"
                or p["surfaceMode"] != "bare-plate" or p["barePlateGeometry"] != "square"
                or p["study"] != "none" or p["layers"] != 1 or p["tracks"] != 1
                or p["scanAngle_deg"] != 0 or p.get("measurements")):
            raise ValueError("Layered-plate sensitivity requires standard/reference bare-plate single +X track without measurements or study")
        numeric_layered = ("plateThickness_um", "supportThickness_um",
                           "contactResistance_m2K_W", "incidenceAngle_deg", "incidenceAzimuth_deg")
        limits = {"plateThickness_um": (5., 10000.), "supportThickness_um": (5., 10000.),
                  "contactResistance_m2K_W": (0., 1.), "incidenceAngle_deg": (0., 90.),
                  "incidenceAzimuth_deg": (0., 360.)}
        for key in numeric_layered:
            value = raw[key]
            lo, hi = limits[key]
            upper_ok = value < hi if key in ("incidenceAngle_deg", "incidenceAzimuth_deg") else value <= hi
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not lo <= value or not upper_ok):
                raise ValueError(f"{key} must be finite in [{lo}, {hi}]")
        if raw["beamProfileModelId"] != "assumed-oblique-gaussian-normal-plane-v1":
            raise ValueError("Unsupported layered-plate beam profile model")
        if raw["supportBottomBoundary"] not in ("adiabatic", "isothermal-at-preheat"):
            raise ValueError("Unknown support bottom boundary")
    if p["backend"] not in ("auto", "reference", "openfoam-thermal"):
        raise ValueError("Unknown thermal backend")
    for k, (lo, hi) in BOUNDS.items():
        if isinstance(p[k], bool) or not isinstance(p[k], (int, float)) or not math.isfinite(p[k]) or not lo <= p[k] <= hi:
            raise ValueError(f"{k} must be finite in [{lo}, {hi}]")
        if k in ("tracks", "layers") and int(p[k]) != p[k]:
            raise ValueError(f"{k} must be integer")
    if p["trackLength_um"] > 3000 and not (
            p["surfaceMode"] == "bare-plate" and p["barePlateGeometry"] == "rectangular-corridor"):
        raise ValueError("trackLength_um above 3000 is supported only by the opt-in bare-plate rectangular-corridor geometry")
    if p["mode"] not in ("screening", "standard", "high-fidelity", "calibration") or p["strategy"] not in ("meander", "unidirectional", "stripe", "island") or p["study"] not in ("none", "mesh", "timestep"):
        raise ValueError("Unknown mode, strategy or study")
    if p["surfaceMode"] not in ("powder-layer", "bare-plate"):
        raise ValueError("Unknown LPBF surface mode")
    if p["barePlateGeometry"] not in ("square", "rectangular-corridor"):
        raise ValueError("barePlateGeometry must be 'square' or 'rectangular-corridor'")
    if "powderGridPolicy" in raw:
        if raw["powderGridPolicy"] != "layer-conforming":
            raise ValueError("powderGridPolicy must be 'layer-conforming'")
        if (p["surfaceMode"] != "powder-layer" or p["mode"] != "standard"
                or p["backend"] not in ("reference", "openfoam-thermal")):
            raise ValueError("layer-conforming powder grid requires standard reference or OpenFOAM powder-layer mode")
    elif (p["surfaceMode"] == "powder-layer" and p["mode"] == "standard"
          and p["backend"] in ("reference", "openfoam-thermal")):
        # Standard powder transients align every powder-layer top surface with
        # a cell face on both supported thermal backends. Legacy archived
        # results retain their original settings and model identity.
        p["powderGridPolicy"] = "layer-conforming"
    if p["barePlateGeometry"] == "rectangular-corridor" and p["surfaceMode"] != "bare-plate":
        raise ValueError("rectangular-corridor geometry is only supported for bare-plate mode")
    if "corridorWidth_um" in raw and p["barePlateGeometry"] != "rectangular-corridor":
        raise ValueError("corridorWidth_um is only supported for rectangular-corridor geometry")
    if p["barePlateGeometry"] == "rectangular-corridor":
        width = p.get("corridorWidth_um")
        if width is None:
            # Preserve the historical fixed-frame width: twelve beam radii total.
            width = 6 * p["beamDiameter_um"]
        if (isinstance(width, bool) or not isinstance(width, (int, float))
                or not math.isfinite(width) or width <= 0):
            raise ValueError("corridorWidth_um must be a positive finite number")
        p["corridorWidth_um"] = float(width)
    if p["surfaceMode"] == "bare-plate":
        penetration = p["sourcePenetration_um"]
        if (p["mode"] != "standard" or p["backend"] != "reference" or p["layers"] != 1
                or p["tracks"] != 1 or p["scanAngle_deg"] != 0 or p.get("measurements")):
            raise ValueError("Bare-plate pilot requires standard/reference single +X track and no measurements")
        if type(penetration) not in (int, float) or not math.isfinite(penetration) or not 5 <= penetration <= 150:
            raise ValueError("Bare-plate sourcePenetration_um must be finite in [5, 150]")
    elif p["sourcePenetration_um"] is not None:
        raise ValueError("sourcePenetration_um is only supported for bare-plate mode")
    m = material(p["material"], p.get("properties"))
    if layered and m.get("materialId") != "in718":
        raise ValueError("Layered-plate sensitivity currently requires Inconel 718")
    if p["preheat_C"]+273.15 >= m["solidus_K"]:
        raise ValueError("Baseplate preheat must be below solidus")
    if "absorptivity" in p:
        a = p["absorptivity"]
        if isinstance(a, bool) or not isinstance(a, (int, float)) or not math.isfinite(a) or not 0 < a <= 1:
            raise ValueError("absorptivity must be in (0,1]")
        m["absorptivity"] = a
    if "emissivity" in p:
        e = p["emissivity"]
        if type(e) not in (int, float) or not math.isfinite(e) or not 0 <= e <= 1:
            raise ValueError("emissivity must be in [0,1]")
        m["emissivity"] = e
    p["absorptivity"], p["emissivity"] = m["absorptivity"], m["emissivity"]
    measurement_evidence(p.get("measurements", []), p)
    if p["mode"] == "calibration" and not p.get("measurements"):
        raise ValueError("Calibration requires measured dimensions and source")
    return p, m


def fingerprint(p, m):
    # Cache identity includes the implementation and effective inputs.
    root = Path(__file__).parent
    h = hashlib.sha256()
    for f in sorted(root.glob("*.py")):
        h.update(f.name.encode()); h.update(f.read_bytes())
    for f in sorted((root/"openfoam").glob("*.C")):
        h.update(f.name.encode()); h.update(f.read_bytes())
    for f in sorted((root/"openfoam/Make").glob("*")):
        if f.is_file(): h.update(f.name.encode()); h.update(f.read_bytes())
    h.update(json.dumps([VERSION, p, m], sort_keys=True, allow_nan=False).encode())
    return h.hexdigest()


def implementation_fingerprint():
    """Hash reviewed thermal implementation sources, independent of run inputs."""
    return _fingerprint_implementation_sources(Path(__file__).parent,
                                               IMPLEMENTATION_SOURCE_FILES, VERSION)


def _fingerprint_implementation_sources(root, source_files, version):
    """Hash a deterministic, fail-closed relative source manifest."""
    paths = tuple(source_files)
    if len(paths) != len(set(paths)):
        raise ValueError("Implementation source manifest contains duplicate paths")
    root = Path(root).resolve()
    entries = []
    for relative in paths:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Implementation source path must stay within its root: {relative}")
        source = (root / path).resolve()
        if root not in source.parents or not source.is_file():
            raise FileNotFoundError(f"Implementation source is missing from manifest: {relative}")
        entries.append((path.as_posix(), source.read_bytes()))
    return _fingerprint_manifest_entries(entries, version)


def _fingerprint_manifest_entries(entries, version):
    h = hashlib.sha256()
    h.update((IMPLEMENTATION_FINGERPRINT_SCHEMA + "\0" + str(version) + "\0").encode())
    for relative, content in sorted(entries):
        name = relative.encode("utf-8")
        h.update(len(name).to_bytes(4, "big")); h.update(name)
        h.update(len(content).to_bytes(8, "big")); h.update(content)
    return h.hexdigest()


def screening(p, m):
    from goldak_solver import GoldakField, seed_goldak_axes
    t0 = p["preheat_C"]
    rho, k, cp = [float(property_at(m, t0+273.15, i)) for i in (1, 2, 3)]
    alpha = k/(rho*cp)
    power, speed = p["power_W"]*m["absorptivity"], p["speed_mm_s"]*1e-3
    goldak = GoldakField(t0, power, rho, cp, alpha, **seed_goldak_axes(p["beamDiameter_um"]*.5e-6)).bind_speed(speed)
    def rosenthal(x, y, z):
        r = np.maximum(np.sqrt(x*x+y*y+z*z), 1e-12)
        return t0+power/(2*math.pi*k*r)*np.exp(-speed*(x+r)/(2*alpha))
    out = {}
    # Fixed analytical scan grid, independent of the transient mesh.
    ax = np.linspace(-.003, .0005, 301)
    transverse = np.linspace(0, .001, 121)
    x, y = np.meshgrid(ax, transverse, indexing="ij")
    for model, field in (("rosenthal", rosenthal), ("goldak", goldak.temperature_C)):
        top = field(x, y, 0) >= m["liquidus_K"]-273.15
        cross = field(x, 0, y) >= m["liquidus_K"]-273.15
        ix, iy = np.where(top)
        iz = np.where(cross)[1]
        out[model] = dict(width_um=float(2*transverse[iy].max()*1e6) if len(iy) else 0.,
                          depth_um=float(transverse[iz].max()*1e6) if len(iz) else 0.,
                          length_um=float(np.ptp(ax[ix])*1e6) if len(ix) else 0.,
                          gridResolution_um=[float(np.diff(ax)[0]*1e6), float(np.diff(transverse)[0]*1e6)],
                          truncated=bool(top[0].any() or top[-1].any() or top[:, -1].any() or cross[:, -1].any()),
                          assumptions="Constant preheat properties; conduction only; discrete liquidus extent; no keyhole correction.")
    return out


def conduction_rate(T, k, active, dx):
    """Conservative harmonic internal-face conduction, W/m^3, insulated exterior."""
    rate = np.zeros_like(T)
    for axis_id in range(3):
        left,right = [slice(None)]*3,[slice(None)]*3
        left[axis_id],right[axis_id] = slice(None,-1),slice(1,None)
        a,b = tuple(left),tuple(right)
        face_k = 2*k[a]*k[b]/(k[a]+k[b])
        flux = face_k*(T[b]-T[a])/dx**2*(active[a]&active[b])
        rate[a] += flux; rate[b] -= flux
    return rate


def _conduction_rate_and_diagonal(T, k, active, dx):
    """Return conductive rate [W/m^3] and row-sum diagonal [W/m^3/K].

    The transient reference path needs both quantities for every accepted
    timestep. Compute each harmonic face conductance once and reuse it for the
    conservative flux and explicit-stability bound.
    """
    rate = np.zeros_like(T)
    diagonal = np.zeros_like(k)
    for axis_id in range(3):
        left, right = [slice(None)] * 3, [slice(None)] * 3
        left[axis_id], right[axis_id] = slice(None, -1), slice(1, None)
        a, b = tuple(left), tuple(right)
        face_k = 2 * k[a] * k[b] / (k[a] + k[b])
        face_mask = active[a] & active[b]
        flux = face_k * (T[b] - T[a]) / dx**2 * face_mask
        face_diagonal = face_k / dx**2 * face_mask
        rate[a] += flux
        rate[b] -= flux
        diagonal[a] += face_diagonal
        diagonal[b] += face_diagonal
    return rate, diagonal


def active_gradient_components(T, active, dx):
    """Average active face differences; one-sided at deposition boundaries.

    Inactive future powder is not a temperature boundary condition. Including
    its preheat temperature would contaminate the extracted G and R.
    """
    components = []
    for axis in range(3):
        left, right = [slice(None)]*3, [slice(None)]*3
        left[axis], right[axis] = slice(None, -1), slice(1, None)
        a, b = tuple(left), tuple(right)
        valid = active[a] & active[b]
        difference = (T[b]-T[a])/dx*valid
        gradient, count = np.zeros_like(T), np.zeros_like(T)
        gradient[a] += difference; gradient[b] += difference
        count[a] += valid; count[b] += valid
        components.append(gradient/np.maximum(count, 1))
    return np.stack(components)


def active_gradient(T, active, dx):
    return np.linalg.norm(active_gradient_components(T, active, dx), axis=0)


def liquidus_crossing_sums(old, new, active, dx, dt, liquidus):
    """Equal event sums of G [K/m], R [m/s], cooling [K/s], and count.

    Reconstruct gradient vectors at each cell's cooling liquidus crossing,
    not at the end of the step. Thermal evolution remains first-order.
    """
    crossing = active & (old >= liquidus) & (new < liquidus)
    if not crossing.any():
        return None
    drop = old[crossing]-new[crossing]
    theta = (old[crossing]-liquidus)/drop
    before = active_gradient_components(old, active, dx)[:, crossing]
    after = active_gradient_components(new, active, dx)[:, crossing]
    grad = np.linalg.norm(before+(after-before)*theta, axis=0)
    cooling = drop/dt
    good = grad > 1e-6
    if not good.any():
        return None
    return [float(grad[good].sum()), float((cooling[good]/grad[good]).sum()),
            float(cooling[good].sum()), int(good.sum())]


def transient(p, m, report=lambda *args: None, artifact_dir=None):
    segments, end = scan_segments(p)
    thermal_inputs = thermal_si_inputs(p, m)
    layer_m = thermal_inputs["layer_m"]
    speed_m_s = thermal_inputs["speed_m_s"]
    absorbed_power_W = thermal_inputs["absorbed_power_W"]
    dx_requested = p["mesh_um"]*1e-6
    layered = p.get("thermalModelId") == "layered-plate-enthalpy-v1"
    domain = calculate_mesh_domain(p)
    if layered:
        plate_cells = max(1, int(math.ceil(p["plateThickness_um"]*1e-6/domain["dx"]-1e-12)))
        support_cells = max(1, int(math.ceil(p["supportThickness_um"]*1e-6/domain["dx"]-1e-12)))
        domain["plate_cells"], domain["support_cells"] = plate_cells, support_cells
        domain["plate_depth"] = plate_cells*domain["dx"]
        domain["support_depth"] = support_cells*domain["dx"]
        domain["substrate_depth"] = domain["plate_depth"]+domain["support_depth"]
        domain["nz"] = plate_cells+support_cells
    radius, span, nx, ny, nz, dx, substrate = (domain[k] for k in ("radius", "span", "nx", "ny", "nz", "dx", "substrate_depth"))
    cell_count = nx*ny*nz
    if cell_count > 600000:
        geometry = "rectangular corridor" if p["barePlateGeometry"] == "rectangular-corridor" else "square"
        raise ValueError(f"{geometry.capitalize()} mesh requires {cell_count:,} cells, above the 600000-cell reference solver limit; reduce the scan length or use a coarser mesh")
    axis = (np.arange(nx)+.5)*dx-span/2
    axis_y = (np.arange(ny)+.5)*dx-ny*dx/2
    z = (np.arange(nz)+.5)*dx-substrate
    bare = p["surfaceMode"] == "bare-plate"
    if not bare:
        layer_counts = [int(np.sum(z < layer*layer_m)) for layer in range(int(p["layers"])+1)]
        if any(b <= a for a,b in zip(layer_counts,layer_counts[1:])):
            raise ValueError("Mesh cannot resolve each powder layer; reduce mesh spacing below layer thickness")
    x, y, zz = np.meshgrid(axis, axis_y, z, indexing="ij")
    t0 = thermal_inputs["preheat_K"]
    T = np.full(x.shape, t0)
    tt, hh = enthalpy_table(m)
    h0 = np.interp(t0, tt, hh)
    # Fixed reference mass: avoids nonconservative rho(T)*h update on an immobile grid.
    rho = float(property_at(m, t0, 1))*np.where(zz > 0, p["packingFraction"], 1.)
    support_cells = domain.get("support_cells", 0)
    support_mask = np.broadcast_to((np.arange(nz) < support_cells)[None, None, :], T.shape) if layered else None
    in718_mask = ~support_mask if layered else None
    if layered:
        rho = np.where(support_mask, 7920.0, rho)
        _, ss_cp_table, _, ss_h_table = ss304_support_thermal_fields(
            np.linspace(REFERENCE_TEMPERATURE_K, MAXIMUM_TEMPERATURE_K, 4097))
        ss_t_table = np.linspace(REFERENCE_TEMPERATURE_K, MAXIMUM_TEMPERATURE_K, 4097)
        h0_ss = float(np.interp(t0, ss_t_table, ss_h_table))
        h0_field = np.where(support_mask, h0_ss, h0)
    else:
        h0_field = h0
    H = np.zeros_like(T)
    ever = np.zeros_like(T, dtype=bool)
    midpoint_plane = int(np.argmin(np.abs(axis))) if bare else None
    midpoint_temperature_max = np.full((ny, nz), t0) if bare else None
    rectangular_corridor = bare and p["barePlateGeometry"] == "rectangular-corridor"
    corridor_section_samples = (rectangular_corridor_section_samples(
        axis, segments[0]["start"][0], p["trackLength_um"]*1e-6)
        if rectangular_corridor else None)
    corridor_peak_planes = ({index: np.full((ny, nz), t0) for index in sorted({
        plane for sample in corridor_section_samples if sample["status"] == "pending"
        for plane in sample["sourcePlaneIndices"]})} if rectangular_corridor else None)
    remelt = np.zeros_like(ever)
    previous_melt = np.zeros_like(ever)
    energy_in = energy_out = 0.
    history, fronts = [], []
    peak_tracker = PeakMeltTracker(np.column_stack([x.ravel(), y.ravel(), zz.ravel()]), dx, m)
    overlap_tracker = None if bare else FieldOverlapTracker(np.column_stack([x.ravel(), y.ravel(), zz.ravel()]), dx, m, p)
    peak = t0
    time, step, next_sample = 0., 0, 0.
    recorder = FieldRecorder(artifact_dir, np.column_stack([x.ravel(), y.ravel(), zz.ravel()]), dx, m, p)
    min_dt = p["maxDt_s"]
    max_dt = max_increment = surface_offset = 0.
    minimum_capture, source_retries = 1., 0
    source_limited_steps = 0
    accepted_dt_s = []
    cp_floor = min(row[3] for row in m["table"])
    if layered:
        cp_floor = min(cp_floor, float(np.min(ss_cp_table)))
        interface_z = np.zeros((nz-1, ny, nx), dtype=bool)
        interface_z[support_cells-1, :, :] = True
        support_snapshot = ss304_support_thermal_snapshot()
    while time < end:
        seg = next((s for s in segments if s["start_s"] <= time+1e-14 and time < s["end_s"]-1e-14), None)
        active_layer = max([s["layer"] for s in segments if s["start_s"] <= time+1e-14] or [0])
        surface = 0. if bare else (active_layer+1)*layer_m
        active = zz < surface
        top_index = int(np.flatnonzero(z < surface)[-1])
        k = property_at(m, T, 2)*np.where((zz > 0)&~ever, p["powderConductivityRatio"], 1.)
        cp = property_at(m, T, 3)
        if layered:
            ss_rho, ss_cp, ss_k, _ = ss304_support_thermal_fields(T[support_mask])
            k[support_mask] = ss_k
            cp[support_mask] = ss_cp
        dt = min(p["maxDt_s"], .12*dx*dx/float(np.max(k/(rho*cp))), radius/(4*speed_m_s), end-time)
        # End exactly on scan/deposition events: never smear laser-on into a dwell.
        events = [s[v]-time for s in segments for v in ("start_s", "end_s") if s[v] > time+1e-14]
        if events:
            dt = min(dt, min(events))
        if layered:
            face_power = conduction_heat_rate(T.transpose(2, 1, 0), k.transpose(2, 1, 0), dx,
                contact_resistance_m2K_W=p["contactResistance_m2K_W"],
                interface_z=interface_z, active_cells=active.transpose(2, 1, 0))
            rate = face_power.transpose(2, 1, 0)/dx**3
            diagonal = conduction_diagonal(k, active, dx)
        else:
            rate, diagonal = _conduction_rate_and_diagonal(T, k, active, dx)
        # Explicit support-base boundary; legacy v1 retains its fixed-temperature base.
        bottom = np.zeros((nx, ny))
        isothermal_bottom = (not layered or p["supportBottomBoundary"] == "isothermal-at-preheat")
        if isothermal_bottom:
            bottom = 2*k[:, :, 0]*(T[:, :, 0]-t0)/dx**2
            rate[:, :, 0] -= bottom
        surface_loss = (p["convection_W_m2K"]*(T[:, :, top_index]-t0)
                        +m["emissivity"]*5.670374419e-8*(T[:, :, top_index]**4-t0**4))/dx
        rate[:, :, top_index] -= surface_loss
        # A local row-sum bound includes heterogeneous faces and boundary cooling.
        # The table minimum cp is a lower bound on enthalpy capacity across a step.
        if isothermal_bottom:
            diagonal[:, :, 0] += 2*k[:, :, 0]/dx**2
        top_temperature = T[:, :, top_index]
        diagonal[:, :, top_index] += (p["convection_W_m2K"]+m["emissivity"]*5.670374419e-8
            *(top_temperature+t0)*(top_temperature**2+t0**2))/dx
        dt = min(dt, float(np.min(.9*rho*cp_floor/np.maximum(diagonal, 1e-30))))
        dt, source, rate, capture, retries = source_limited_step(
            axis, z, dx, seg, time, dt, surface, radius,
            p["sourcePenetration_um"]*1e-6 if bare else layer_m,
            absorbed_power_W, rate, rho*cp, axis_y=axis_y,
            incidence_angle_deg=p.get("incidenceAngle_deg", 0.),
            incidence_azimuth_deg=p.get("incidenceAzimuth_deg", 0.))
        accepted_dt_s.append(dt)
        source_limited_steps += int(retries > 0)
        require_source_capture(capture, MINIMUM_SOURCE_CAPTURE_FRACTION)
        min_dt = min(min_dt, dt)
        max_dt = max(max_dt, dt)
        max_increment = max(max_increment, float(np.max(dt*np.abs(rate)/(rho*cp))))
        minimum_capture = min(minimum_capture, capture)
        source_retries += retries
        surface_offset = max(surface_offset, abs(z[top_index]+dx/2-surface)*1e6)
        old = T.copy()
        H += dt*rate
        h = H/rho+h0_field
        if layered:
            if (not np.isfinite(h).all() or float(h[~support_mask].min()) < hh[0]-1e-8
                    or float(h[~support_mask].max()) >= np.interp(m["boiling_K"], tt, hh)
                    or float(h[support_mask].min()) < ss_h_table[0]-1e-8
                    or float(h[support_mask].max()) > ss_h_table[-1]):
                raise ValueError("Thermal model validity exceeded (IN718 boiling or SS304 fit range)")
            T[~support_mask] = np.interp(h[~support_mask], hh, tt)
            T[support_mask] = np.interp(h[support_mask], ss_h_table, ss_t_table)
        else:
            if not np.isfinite(h).all() or float(h.min()) < hh[0]-1e-8 or float(h.max()) >= np.interp(m["boiling_K"], tt, hh):
                raise ValueError("Thermal model validity exceeded (boiling or nonphysical enthalpy); evaporation/free-surface CFD required")
            T = np.interp(h, hh, tt)
        time += dt
        end_roundoff = min(1e-14, 2*math.ulp(end)*(step+1))
        if end-time <= end_roundoff:
            time = end
        step += 1
        energy_in += float(source.sum())*dx**3*dt
        energy_out += (float(bottom.sum())+float(surface_loss.sum()))*dx**3*dt
        melt = (T >= m["liquidus_K"])&active
        if layered:
            melt &= in718_mask
        remelt |= melt&ever&~previous_melt
        ever |= melt
        if bare:
            np.maximum(midpoint_temperature_max, T[midpoint_plane], out=midpoint_temperature_max)
            if rectangular_corridor:
                for plane, maximum in corridor_peak_planes.items():
                    np.maximum(maximum, T[plane], out=maximum)
        front = liquidus_crossing_sums(old, T, active, dx, dt, m["liquidus_K"])
        if front is not None:
            fronts.append(front)
        previous_melt = melt
        peak = max(peak, float(T.max()))
        sampled = time >= next_sample or time >= end
        peak_tracker.observe(T, surface, p["scanAngle_deg"]+active_layer*p["layerRotation_deg"],
                             time, step, sampled=sampled)
        active_track = seg["track"] if seg is not None else (
            max([s["track"] for s in segments if s["layer"] == active_layer and s["end_s"] <= time + 1e-14] or [0])
        )
        if overlap_tracker is not None:
            overlap_tracker.observe(T, surface, active_layer, active_track)
        if sampled:
            recorder.record(time, T, surface)
            history.append(dict(time_s=time, peak_K=float(T.max()), center_K=float(T[nx//2, ny//2, top_index]),
                                storedEnergy_J=float(H.sum())*dx**3, inputEnergy_J=energy_in, lossEnergy_J=energy_out))
            report(time/end, f"step={step} t={time:.7g}s peak={T.max():.1f}K cells={T.size}")
            next_sample = time+end/60
        if step > 250000:
            raise ValueError("Reference solver step budget exceeded")
    stored = float(H.sum())*dx**3
    balance = abs(energy_in-energy_out-stored)/max(energy_in, 1e-12)
    if balance > .01:
        raise ValueError(f"Energy balance failed: {balance:.3%}")
    discretization = dict(cells=int(T.size), mesh_m=dx, minimumDt_s=min_dt, meanDt_s=end/step, steps=step)
    timestep_diagnostics = summarize_accepted_timesteps(
        accepted_dt_s, p["maxDt_s"], source_limited_steps, source_retries)
    if layered:
        discretization.update(requestedPlateThickness_um=p["plateThickness_um"],
            effectivePlateThickness_um=domain["plate_depth"]*1e6,
            requestedSupportThickness_um=p["supportThickness_um"],
            effectiveSupportThickness_um=domain["support_depth"]*1e6,
            plateCells=int(domain["plate_cells"]), supportCells=int(domain["support_cells"]))
    if rectangular_corridor:
        discretization.update(requestedCorridorWidth_um=p["corridorWidth_um"],
                              effectiveCorridorWidth_um=domain["effective_span_y"]*1e6)
    G, R, cooling = (np.sum(fronts, axis=0)[:3]/np.sum(fronts, axis=0)[3]).tolist() if fronts else (None, None, None)
    best, peak_diagnostics = peak_tracker.finish(artifact_dir, step)
    interpolated_peak = peak_diagnostics.pop("interpolatedPeakMeltPool")
    overlap_metrics = overlap_tracker.finish(artifact_dir) if overlap_tracker is not None else None
    width = best["width_um"]*1e-6
    alpha = float(property_at(m, m["liquidus_K"], 2)/(property_at(m, m["liquidus_K"], 1)*property_at(m, m["liquidus_K"], 3)))
    best.update(peakTemperature_K=peak, thermalGradient_K_m=G, solidificationRate_m_s=R,
                coolingRate_K_s=cooling, keyholeDepth_um=None, recoilPressure_Pa=None,
                marangoniNumber=abs(m["dGamma_dT"])*max(0, peak-m["liquidus_K"])*width/(float(property_at(m, peak, 4))*alpha),
                pecletNumber=p["speed_mm_s"]*1e-3*width/alpha,
                aspectRatio=best["depth_um"]/best["width_um"] if width else None,
                trackOverlapRatio=overlap_metrics["trackOverlapRatio"] if overlap_metrics else None,
                remeltingRatio=overlap_metrics["globalRemeltRatio"] if overlap_metrics else None)
    return dict(metrics=best, thermalHistory=history, fieldSeries=recorder.finish(),
                peakInterpolatedMeltPool=interpolated_peak,
                fieldOverlapDiagnostics=overlap_metrics,
                midTrackCrossSection=midtrack_bare_plate_section(axis, z, ever, dx, axis_y=axis_y) if bare else None,
                midTrackInterpolatedCrossSection=interpolated_midtrack_bare_plate_section(
                    axis_y, z, midpoint_temperature_max, dx, m["liquidus_K"], axis[midpoint_plane]
                ) if bare else None,
                **({"barePlateSectionObservations": rectangular_corridor_section_observations(
                    axis_y, z, corridor_peak_planes, corridor_section_samples, dx, m["liquidus_K"])}
                    if rectangular_corridor else {}),
                numericalDiagnostics=dict(**peak_diagnostics, overlapExtraction=OVERLAP_MODEL_ID if overlap_metrics else None, sourceIntegration=SOURCE_INTEGRATION, solidificationExtraction="linear-liquidus-crossing-v1",
                    stabilityLimit="local-conductance-row-sum", minimumCapturedSourceFraction=minimum_capture,
                    maximumSourceRenormalization=1/minimum_capture, maximumSurfaceOffset_um=surface_offset,
                    maximumTimestep_s=max_dt, maximumEnthalpyIncrement_K=max_increment,
                    sourceTimestepRetries=source_retries,
                    acceptedTimestepDistribution=timestep_diagnostics),
                energyBalance=dict(input_J=energy_in, losses_J=energy_out, stored_J=stored, relativeError=balance),
                discretization=discretization,
                scanPath=segments,
                **({"supportMaterial": support_snapshot,
                    "supportDiagnostics": dict(maximumTemperature_K=float(np.max(T[support_mask])),
                        storedThermalEnergy_J=float(H[support_mask].sum())*dx**3,
                        supportCellsExcludedFromMeltGeometry=True),
                    "layeredSensitivity": dict(interfaceModelId="planar-series-resistance-v1",
                        contactResistance_m2K_W=p["contactResistance_m2K_W"],
                        supportBottomBoundary=p["supportBottomBoundary"],
                        beamProfileModelId=p["beamProfileModelId"],
                        evidenceNote="Explicit sensitivity assumptions; not AMB2022-03 measured contact, support boundary, or irradiance-map evidence.")}
                   if layered else {}),
                **thermal_audits(np.column_stack([x.ravel(),y.ravel(),zz.ravel()]), np.full(T.size,dx**3), p,m,
                    (np.clip((T-m["solidus_K"])/(m["liquidus_K"]-m["solidus_K"]),0,1)*active).ravel()))


def _layer_aligned_mesh_levels(p):
    """Return three distinct cells-per-layer levels bracketing the request."""
    layer_um = p["layer_um"]
    base_cells = max(1, int(math.ceil(layer_um / p["mesh_um"] - 1e-12)))
    max_cells = int(math.floor(layer_um / BOUNDS["mesh_um"][0] + 1e-12))
    if max_cells < 3:
        return None
    if base_cells <= 1:
        cells = (1, 2, 3)
    elif base_cells >= max_cells:
        cells = (max_cells - 2, max_cells - 1, max_cells)
    else:
        cells = (base_cells - 1, base_cells, base_cells + 1)
    return tuple((n, layer_um / n) for n in cells)


def run(raw, report=lambda *args: None, artifact_dir=None, capabilities=None):
    requested_p, requested_m = validate(raw)
    requested_backend = requested_p["backend"]
    p, m = requested_p, requested_m
    # Standard powder-layer reference execution uses the layer-conforming grid.
    # Mesh studies and auto-dispatched standard powder runs use the NumPy
    # reference even when another backend could be selected automatically.
    layer_mesh_study = (p["study"] == "mesh" and p["mode"] == "standard"
                        and p["surfaceMode"] == "powder-layer"
                        and requested_backend in ("auto", "reference"))
    automatic_reference_powder = (p["mode"] == "standard" and p["surfaceMode"] == "powder-layer"
                                  and p["backend"] == "auto")
    if ((layer_mesh_study or automatic_reference_powder)
            and p.get("powderGridPolicy") != "layer-conforming"):
        execution_input = dict(raw)
        execution_input.update(backend="reference", powderGridPolicy="layer-conforming")
        p, m = validate(execution_input)
    bare = p["surfaceMode"] == "bare-plate"
    analytical = None if bare else screening(p, m)
    fallback = p["mode"] == "high-fidelity"
    use_foam = p["backend"] == "openfoam-thermal" or (p["backend"] == "auto" and (capabilities or {}).get("openfoamThermal"))
    use_cfd = p["backend"] == "openfoam-cfd"
    if use_cfd:
        fallback = False
        p["mode"] = "high-fidelity"
    thermal_solver = transient
    if use_foam:
        from lpbf_openfoam import thermal
        thermal_solver = thermal
    elif use_cfd:
        from lpbf_cfd import cfd_multiphysics
        thermal_solver = cfd_multiphysics
    result = dict(schemaVersion=1, requestedMode=p["mode"], effectiveMode="screening" if fallback else p["mode"],
                  solver=dict(id=("layered-enthalpy-fv-1" if p.get("thermalModelId") == "layered-plate-enthalpy-v1"
                                  else "rosenthal+goldak" if p["mode"] == "screening" or fallback else VERSION),
                              version=VERSION, openfoam=(capabilities or {}).get("openfoamVersion")),
                  settings=p, material=m, requestedBackend=requested_backend,
                  confidence="low", validationStatus="unvalidated", productionReady=False,
                  label="Screening only" if p["mode"] == "screening" or fallback else "Unvalidated transient thermal",
                  provenance=dict(inputHash=hashlib.sha256(json.dumps(requested_p, sort_keys=True, allow_nan=False).encode()).hexdigest(),
                                  executionInputHash=hashlib.sha256(json.dumps(p, sort_keys=True, allow_nan=False).encode()).hexdigest(),
                                  implementationHash=implementation_fingerprint(), materialVersion=m["version"],
                                  solverBinaryHash=(capabilities or {}).get("binaryHash"),
                                  createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat()),
                  analyticalComparison=analytical,
                  assumptions=["SI internal units; beam diameter is 1/e^2 intensity diameter.",
                               "No resolved momentum, Marangoni flow, evaporation, recoil, VOF, keyhole or pores.",
                               "Estimated material laws; fixed reference density conserves mass on a stationary grid.",
                               ("Homogeneous solid bare plate; no powder or deposited layer."
                                if bare else "Uniform effective powder, irreversible conductivity densification; no resolved powder particles."),
                               ("Gaussian penetration is an explicit model input, independent of mesh; cell-integrated source uses two time quadrature nodes and first-order Euler. Absorbed power is normalized over the represented domain."
                                if bare else "Gaussian penetration equals layer thickness, independent of mesh. Cell-integrated source uses two time quadrature nodes; thermal evolution remains first-order Euler. Absorbed power normalized over represented domain."
                                if p["mode"] in ("standard", "calibration") else "Analytical screening has no resolved transient heat source or time integration."),
                               ("Bare surface is fixed at z=0 with whole cells below it; no cut-cell interface."
                                if bare else "Transient layer activation uses whole cells selected by their centers; source surface clipping does not implement cut-cell mass or conduction. Inspect numerical resolution diagnostics when available."),
                               "Geometry is the molten-domain extent at the earliest maximum volume over accepted timesteps; playback is sparse and multi-track pools may be disconnected. Sampling loss does not bound timestep or mesh error.",
                               ("Bare-plate W/D is the ever-liquidus cell extent on the YZ plane nearest the +X track midpoint; it is a thermal proxy for the optical cross section."
                                if bare else "Cross section is the maximum YZ grid section; it is not scan-normal for rotated scans."),
                               "R = -dT/dt / |grad T| at linearly reconstructed cooling liquidus crossings; gradient vectors are interpolated in time. G, R, G×R are separately event-averaged; G <= 1e-6 K/m is excluded.",
                               "Ma and laser-travel Pe are screening numbers, not resolved velocities.",
                               "Thermal history is input for subsequent mechanics; no residual stress, distortion or cracking prediction."],
                  fallbackReason=("OpenFOAM is installed but a qualified free-surface LPBF solver is not registered."
                                  if (capabilities or {}).get("openfoamVersion") else "OpenFOAM / a qualified free-surface LPBF solver is unavailable in this worker.") if fallback else None)
    if p["mode"] in ("standard", "calibration"):
        n_runs = 1 if p["study"] == "none" else 3
        result.update(thermal_solver(p, m, lambda f, msg: report(f/n_runs, msg), artifact_dir))
        if use_foam:
            result["solver"]["id"] = "metalliksaThermal-OpenFOAM14-6"
        if p["study"] != "none":
            trials = []
            level_errors = []
            key = "mesh_um" if p["study"] == "mesh" else "maxDt_s"
            if layer_mesh_study:
                plan = _layer_aligned_mesh_levels(p)
                level_specs = ([dict(level=name, requested=spacing, cellsPerLayer=count)
                                for name, (count, spacing) in zip(("coarse", "medium", "fine"), plan)]
                               if plan else [])
                requested_spacing = p["mesh_um"]
                if not plan:
                    level_errors.append(dict(level="mesh-plan", requested=requested_spacing,
                        reason="Three distinct layer-aligned meshes require at least three cells per layer at the 5 um minimum spacing."))
                # The requested solve is one member of the sorted three-grid
                # sequence; run the other two with identical model/material.
                ordered_results = [None, None, None]
                if plan:
                    base_cells = max(1, int(math.ceil(p["layer_um"] / requested_spacing - 1e-12)))
                    base_index = next((i for i, (count, _) in enumerate(plan) if count == base_cells), None)
                    if base_index is None:
                        level_errors.append(dict(level="mesh-plan", requested=requested_spacing,
                            reason="The requested mesh is outside the selected three-level layer-aligned window."))
                    else:
                        ordered_results[base_index] = result
                        completed_solves = 1
                        for index, spec in enumerate(level_specs):
                            if index == base_index:
                                continue
                            q = copy.deepcopy(p)
                            q[key] = spec["requested"]
                            progress_slot = completed_solves
                            try:
                                ordered_results[index] = thermal_solver(
                                    q, m, lambda f, msg, i=progress_slot: report((i+f)/3, msg))
                            except Exception as exc:
                                level_errors.append(dict(level=spec["level"], requested=spec["requested"],
                                    reason=str(exc)[:500] or type(exc).__name__))
                            completed_solves += 1
                trials = ordered_results
            else:
                # Retain the legacy timestep and explicitly selected non-reference protocols.
                for index, scale in enumerate((2., math.sqrt(2.))):
                    q = copy.deepcopy(p); q[key] *= scale
                    try:
                        trial = thermal_solver(q, m, lambda f, msg: report((index+1+f)/3, msg))
                    except Exception as exc:
                        trials.append(None)
                        level_errors.append(dict(level=("coarse", "medium")[index],
                                                 requested=q[key], reason=str(exc)[:500] or type(exc).__name__))
                        continue
                    trials.append(trial)
                trials.append(result)
            resolution_key = "mesh_m" if key == "mesh_um" else "meanDt_s"
            actual = [v["discretization"][resolution_key] if v is not None else None for v in trials]
            metric_key = "midTrackCrossSection" if bare else "metrics"
            metric_names = ("width_um", "depth_um") if bare else ("width_um", "depth_um", "volume_um3")
            checks = ({k: dict(status="failed", reason="Invalid study levels: " + "; ".join(
                            f"{v['level']}: {v['reason']}" for v in level_errors)) for k in metric_names}
                      if level_errors else
                      {k: convergence([v[metric_key][k] for v in trials], actual) for k in metric_names})
            result["convergenceStudy"] = dict(kind=p["study"], spacings=actual,
                metricSource=metric_key,
                results=[v[metric_key] if v is not None else None for v in trials], checks=checks,
                status="failed" if level_errors else "complete",
                failedLevels=level_errors)
            if layer_mesh_study:
                result["convergenceStudy"].update(
                    protocol="layer-aligned-three-grid-cpu-reference-v1",
                    gridPolicy="layer-conforming",
                    requestedBackend=requested_backend,
                    executionBackend="reference",
                    cellsPerLayer=[spec["cellsPerLayer"] for spec in level_specs],
                    requestedMesh_um=requested_p["mesh_um"])
            if bare:
                targets = dict(energyRelativeErrorMax=.01, finestPairWidthDepthRelativeChangeMax=.05,
                               minimumLevels=3, source="docs/DIGITAL_TWIN_MASTER_PLAN_2026-09-21.md#11")
                if level_errors:
                    reason = "Invalid study levels: " + "; ".join(
                        f"{v['level']}: {v['reason']}" for v in level_errors)
                    verdicts = {name: dict(status="failed", reason=reason) for name in metric_names}
                else:
                    verdicts = {}
                    for name in metric_names:
                        values = [v[metric_key][name] for v in trials]
                        change = abs(values[-1]-values[-2])/values[-1] if all(x > 0 for x in values) else None
                        location_resolved = all(v[metric_key]["midpointResolvedWithinQuarterCell"] for v in trials)
                        status = ("inconclusive" if change is None else "failed" if change > .05 else
                                  "inconclusive" if not location_resolved else
                                  "pass" if checks[name]["status"] == "numerically-converging" else "inconclusive")
                        verdicts[name] = dict(status=status, finestPairRelativeChange=change,
                                             midpointLocationResolved=location_resolved)
                energies = [v["energyBalance"]["relativeError"] for v in trials if v is not None]
                energy_status = "pass" if all(e <= .01 for e in energies) else "failed"
                states = [energy_status, *(v["status"] for v in verdicts.values())]
                result["convergenceStudy"]["acceptance"] = dict(targets=targets, metrics=verdicts,
                    energyStatus=energy_status, maximumEnergyRelativeError=max(energies) if energies else None,
                    status="failed" if "failed" in states else "inconclusive" if "inconclusive" in states else "pass")
    else:
        result["metrics"] = analytical["goldak"]
    g = result["metrics"]
    w, d, length = g["width_um"], g["depth_um"], g["length_um"]
    result["geometricDefectScreen"] = None if bare else defect_diagnostics(w, d, length, p["hatch_um"], p["layer_um"],
        aggregate=p["tracks"] > 1 and p["mode"] in ("standard", "calibration"))
    lof = w <= p["hatch_um"] or d <= p["layer_um"]
    kh = d/max(w, 1e-12) > .5
    result["regime"] = "keyhole-risk (screening)" if kh else "conduction assumption"
    result["mainRisk"] = "lack-of-fusion" if lof else "keyhole (screening)" if kh else "balling (screening)" if length > math.pi*w else "not established"
    result["recommendation"] = "Reduce hatch/layer spacing; verify penetration experimentally." if lof else "Reduce power or increase speed; verify with free-surface CFD." if kh else "Compare with measured tracks before changing process parameters."
    result["riskScope"] = "Geometric screening only; no probability, density qualification or solidification cracking assessment."
    if bare:
        result.update(regime="bare-plate conduction assumption", mainRisk="not assessed",
                      recommendation="Use the midpoint section only after beam and material conditions are resolved.",
                      riskScope="Bare-plate thermal proxy; no powder defect, flow, porosity, or experimental qualification.",
                      beamConvention=dict(input="1/e2 intensity diameter", nistReported="D4sigma second-moment diameter",
                          idealGaussianRelation="For I(r)=I0 exp(-2r^2/w^2), sigma_x=w/2; D4sigma=4sigma_x=2w=1/e2 diameter.",
                          mappingStatus="conditional ideal-Gaussian identity; actual measured profile not established",
                          nistSource="https://www.nist.gov/document/amb2022-03-measurement-and-challenge-descriptions-version-101"),
                      experimentalComparison=dict(status="unavailable", reason=(
                          "NIST AMB2022-03 uses a 10 mm bare track and reports D4sigma. "
                          "The ideal-Gaussian diameter identity does not establish the actual beam profile; "
                          "the bounded reference mesh also cannot solve the full-length midpoint. "
                          "The thermal section is not the mean of six etched optical sections from three tracks at 4.9 and 6.0 mm.")))
    if p["tracks"] > 1 and p["mode"] in ("standard", "calibration"):
        field_overlap = result.get("fieldOverlapDiagnostics")
        if field_overlap and field_overlap.get("hasInterTrackGap"):
            result["mainRisk"] = "lack-of-fusion (field-resolved inter-track gap)"
            result["regime"] = "conduction assumption; field-resolved inter-track lack-of-fusion"
            result["recommendation"] = "Reduce hatch spacing; simulated melt pools leave unmelted powder gap between adjacent tracks."
        elif field_overlap and field_overlap.get("interTrackLackOfFusion"):
            result["mainRisk"] = "lack-of-fusion (insufficient inter-track penetration)"
            result["regime"] = "conduction assumption; marginal inter-track penetration"
            result["recommendation"] = "Increase power or decrease speed; inter-track penetration does not reach layer thickness."
        elif field_overlap:
            result["mainRisk"] = "keyhole (screening)" if kh else "balling (screening)" if length > math.pi*w else "continuous inter-track fusion"
            result["regime"] = "conduction assumption; continuous inter-track fusion"
            result["recommendation"] = "Field-resolved inter-track fusion verified; verify penetration and porosity with free-surface CFD or experiment."
        else:
            result["mainRisk"] = "not assessed from aggregate multi-track extents"
            result["regime"] = "conduction assumption; local flow regime unresolved"
            result["recommendation"] = "Inspect saved temperature fields and remelting history; aggregate width cannot establish inter-track fusion."
            g["trackOverlapRatio"] = None
    if p.get("measurements"):
        result["measurementComparison"] = {key: compare([g[key]]*len(p["measurements"]), [row[key] for row in p["measurements"]]) for key in ("width_um", "depth_um")}
    result["resourceEstimate"] = resource_estimate(p,m)
    result["unresolvedPhysics"] = dict(freeSurface=None, velocity=None, evaporationMassFlux=None,
        evaporationLoss=None, recoilPressure=None, keyholeDepth=None, porosityProbability=None, residualStress=None)
    if p.get("measurements"):
        result["measurementEvidence"] = measurement_evidence(p["measurements"],p)
        result["experimentalValidation"] = "Experimental validation pending"
        if any(v["sameProcessVector"] != "matched" for v in result["measurementEvidence"]):
            for value in result["measurementComparison"].values():
                value["calibrationFactor"] = None
                value["note"] += " Process vector unverified; calibration factor withheld."
    result["confidenceReason"] = f"{m['quality']} material data and unresolved flow; no independent experimental validation."
    if any(isinstance(v,(int,float)) and (not math.isfinite(v) or v < 0) for v in g.values()):
        raise ValueError("Nonfinite or negative physical result")
    result["coreContract"] = build_core_contract(p, m, result["solver"]["id"], result["effectiveMode"])
    enforce_thermal_balances(result)
    write_artifacts(result, artifact_dir)
    json.dumps(result, allow_nan=False)
    return result


if __name__ == "__main__":
    import sys
    print(json.dumps(run(json.load(sys.stdin)), allow_nan=False))
