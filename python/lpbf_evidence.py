"""Auditable metadata for the stationary thermal model; never CFD evidence."""
import csv
import hashlib
import math
from pathlib import Path
from lpbf_core_contract import enforce_core_contract

PROCESS_KEYS = ("material", "power_W", "speed_mm_s", "beamDiameter_um", "preheat_C",
                "layer_um", "hatch_um", "tracks", "layers", "trackLength_um", "strategy",
                "scanAngle_deg", "layerRotation_deg", "dwell_s", "packingFraction", "stripeWidth_um", "islandSize_um",
                "absorptivity", "emissivity", "powderConductivityRatio", "convection_W_m2K", "cooling_s")


def finite_tree(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("NaN and Infinity are not accepted anywhere in the input")
    if isinstance(value, dict):
        for item in value.values(): finite_tree(item)
    elif isinstance(value, (list, tuple)):
        for item in value: finite_tree(item)


def measurement_evidence(rows, p):
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError("measurements must be a list of at most 1000 replicates")
    checks = []
    for row in rows:
        required = {"width_um", "depth_um", "source"}
        optional = {"processVector", "uncertainty_um", "independentHoldout"}
        if not isinstance(row, dict) or not required <= row.keys() or row.keys()-required-optional:
            raise ValueError("Measurement requires width_um, depth_um, source; unknown fields rejected")
        if not isinstance(row["source"], str) or not row["source"].strip():
            raise ValueError("Measurement source / specimen ID / DOI is required")
        for key in ("width_um", "depth_um"):
            if type(row[key]) not in (int, float) or not math.isfinite(row[key]) or row[key] <= 0:
                raise ValueError("Measured dimensions must be finite and positive")
        if "independentHoldout" in row and type(row["independentHoldout"]) is not bool:
            raise ValueError("independentHoldout must be boolean")
        uncertainty = row.get("uncertainty_um")
        if uncertainty is not None and (not isinstance(uncertainty, dict) or set(uncertainty) != {"width_um", "depth_um"}
                or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in uncertainty.values())):
            raise ValueError("uncertainty_um requires nonnegative width_um and depth_um")
        vector = row.get("processVector")
        if vector is not None:
            if not isinstance(vector, dict) or set(vector) != set(PROCESS_KEYS):
                raise ValueError("Measurement processVector must contain exactly: "+", ".join(PROCESS_KEYS))
            if any(type(vector[k]) is bool or vector[k] != p[k] for k in PROCESS_KEYS):
                raise ValueError("Measurement process vector does not match this simulation")
        checks.append(dict(source=row["source"], sameProcessVector="matched" if vector is not None else "unverified",
                           uncertainty_um=uncertainty, independentHoldout=row.get("independentHoldout"),
                           status="user-supplied-unverified"))
    return checks


def resource_estimate(p, m):
    from lpbf_core_physics import calculate_mesh_domain
    domain = calculate_mesh_domain(p)
    radius, dx, nx, ny, nz = (domain[k] for k in ("radius", "dx", "nx", "ny", "nz"))
    from lpbf_simulation import scan_segments
    _, duration = scan_segments(p)
    # Conservative estimate before temperature-dependent source limiting; not a wall-time benchmark.
    alpha = max(row[2]/(row[1]*row[3]*p["packingFraction"]) for row in m["table"])
    dt = min(p["maxDt_s"], .12*dx*dx/alpha, radius/(4*p["speed_mm_s"]*.001))
    cells = nx*ny*nz
    return dict(cells=cells, spacing_m=dx, shape=[nx,ny,nz], duration_s=duration,
                minimumEstimatedSteps=math.ceil(duration/dt), workingMemoryEstimate_MB=cells*200/1e6,
                minimumRequiredSteps=math.ceil(duration/p["maxDt_s"]), stepBudget=250000,
                exceedsStepBudget=math.ceil(duration/p["maxDt_s"])>250000,
                runs=1 if p["study"] == "none" else 3, cellBudget=600000,
                exceedsCellBudget=cells > 600000, runtimeEstimate="Seconds to minutes; hardware and adaptive timestep dependent",
                note="Uniform orthogonal mesh; memory is approximate. Source limiting can increase steps. No calibrated wall-time estimate.")


def thermal_audits(coords, volumes, p, m, liquid_fraction):
    import numpy as np
    from lpbf_core_physics import property_at
    if (not np.isfinite(coords).all() or not np.isfinite(volumes).all()
            or np.any(volumes <= 0) or not np.isfinite(liquid_fraction).all()
            or np.any(liquid_fraction < 0) or np.any(liquid_fraction > 1)):
        raise ValueError("Mass/phase audit failed: invalid cells or unbounded liquid fraction")
    z = coords[:, 2]
    rho = float(property_at(m, p["preheat_C"]+273.15, 1))*np.where(z > 0, p["packingFraction"], 1.)
    initial = z < p["layer_um"]*1e-6
    active = z < p["layers"]*p["layer_um"]*1e-6
    start = float(np.sum(rho[initial]*volumes[initial]))
    added = float(np.sum(rho[active & ~initial]*volumes[active & ~initial]))
    final = float(np.sum(rho[active]*volumes[active]))
    return dict(massBalance=dict(initial_kg=start, deposited_kg=added, final_kg=final,
                relativeError=abs(final-start-added)/max(final, 1e-30),
                scope="Stationary reference mass accounting; no continuity, evaporation or shrinkage solved"),
                phaseAudit=dict(liquidVolume_m3=float(np.sum(liquid_fraction[active]*volumes[active])),
                    solidVolume_m3=float(np.sum((1-liquid_fraction[active])*volumes[active])),
                    activeVolume_m3=float(np.sum(volumes[active])), minFraction=float(liquid_fraction.min()),
                    maxFraction=float(liquid_fraction.max()), interfaceConservation=None,
                    scope="Enthalpy liquid fraction partition; not a metal/gas interface conservation test"))


def enforce_thermal_balances(result):
    """Fail closed at the result boundary, including restored/cached thermal jobs.

    Closure is recomputed from extensive quantities, never trusted from a badge.
    This verifies stationary accounting, not a gas interface or fluid continuity.
    """
    enforce_core_contract(result)
    if result.get("effectiveMode") not in ("standard", "calibration"):
        return
    for name, keys, tolerance in (
        ("energyBalance", ("input_J", "losses_J", "stored_J"), .01),
        ("massBalance", ("final_kg", "initial_kg", "deposited_kg"), 1e-10),
        ("phaseAudit", ("activeVolume_m3", "liquidVolume_m3", "solidVolume_m3"), 1e-10),
    ):
        audit = result.get(name, {})
        values = [audit.get(k) for k in keys]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError(f"{name} failed: missing/nonphysical accounting")
        total, part1, part2 = values
        error = abs(total-part1-part2)/max(total, 1e-30)
        reported = audit.get("relativeError", error)
        if type(reported) not in (int, float) or not math.isfinite(reported) or not 0 <= reported <= tolerance or error > tolerance:
            raise ValueError(f"{name} failed: closure error {error:.6g}")
    phase = result["phaseAudit"]
    lo, hi = phase.get("minFraction"), phase.get("maxFraction")
    if (type(lo) not in (int, float) or type(hi) not in (int, float)
            or not 0 <= lo <= hi <= 1):
        raise ValueError("phaseAudit failed: unbounded liquid fraction")


def write_artifacts(result, folder):
    if folder is None: return
    folder = Path(folder)
    field = folder/"peak-field.npz"
    if field.exists():
        write_field_slices(field, folder, result)
    else:
        # Reused no-melt runs must not publish previews from an older peak.
        for name in ("temperature-slice.svg", "phase-slice.svg"):
            (folder/name).unlink(missing_ok=True)
    if result.get("thermalHistory"):
        rows = result["thermalHistory"]
        with (folder/"thermal-history.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    artifacts = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name in ("result.json", "result.tmp", "progress.log"): continue
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b""): digest.update(chunk)
        artifacts.append(dict(path=path.relative_to(folder).as_posix(), size_bytes=path.stat().st_size,
                              sha256=digest.hexdigest()))
    result["artifacts"] = artifacts
    result["retentionPolicy"] = "Retained locally until explicit operator deletion; no automatic expiry. Paths relative to job directory."


def write_field_slices(field, folder, result):
    """Render actual peak-volume temperature/enthalpy fraction on the nearest y=0 plane."""
    import numpy as np
    with np.load(field, allow_pickle=False) as data:
        if "coordinates_m" in data:
            xyz = data["coordinates_m"]
        else:
            xyz = np.column_stack([a.ravel() for a in np.meshgrid(data["x_m"],data["y_m"],data["z_m"],indexing="ij")])
        plane = np.unique(xyz[:,1])[np.argmin(np.abs(np.unique(xyz[:,1])))]
        mask = np.isclose(xyz[:,1],plane,rtol=0,atol=1e-12)
        x,z = xyz[mask,0],xyz[mask,2]
        dx = result["discretization"]["mesh_m"]
        time = float(data["time_s"])
        for key,name,unit in (("T_K","temperature-slice.svg","K"),("liquid_fraction","phase-slice.svg","fraction")):
            values = data[key].ravel()[mask]
            lo,hi = (float(values.min()),float(values.max())) if key == "T_K" else (0.,1.)
            width,height = 640,280
            sx,sz = 580/(float(np.ptp(x))+dx),210/(float(np.ptp(z))+dx)
            parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><rect width="640" height="280" fill="#0f172a"/>',
                     f'<text x="20" y="20" fill="#e2e8f0" font-size="12">Resolved thermal field: {key}; y={plane*1e6:.3g} um; t={time*1e3:.4g} ms</text>']
            for xx,zz,v in zip(x,z,values):
                f = min(1.,max(0.,(v-lo)/max(hi-lo,1e-12)))
                colour = f'rgb({int(30+225*f)},{int(90+110*f)},{int(200-150*f)})'
                parts.append(f'<rect x="{30+(xx-x.min())*sx:.3f}" y="{35+(z.max()-zz)*sz:.3f}" width="{dx*sx+.1:.3f}" height="{dx*sz+.1:.3f}" fill="{colour}"/>')
            parts.append(f'<text x="20" y="270" fill="#94a3b8" font-size="11">Blue {lo:.5g} / Amber {hi:.5g} {unit}; X horizontal, Z vertical; uniform cells; no velocity or gas interface</text></svg>')
            (folder/name).write_text("".join(parts),encoding="utf-8")
    result["fieldPreviews"] = ["temperature-slice.svg","phase-slice.svg"]


class FieldRecorder:
    """Full cell samples, little-endian float32, streamed separately from result JSON.

    Visualization precision only; solver and metrics retain float64. No spatial
    interpolation, fabricated interface or inferred velocity is exported.
    """
    def __init__(self, folder, coords, spacing, material, process=None):
        import numpy as np
        self.folder = Path(folder) if folder else None
        self.coords = np.asarray(coords)
        self.frames = []
        self.process = process
        self.metadata = dict(version=1, cells=len(coords), spacing_m=spacing,
            coordinates="field-coordinates.bin", frames=self.frames,
            solidus_K=material["solidus_K"], liquidus_K=material["liquidus_K"],
            boiling_K=material["boiling_K"],
            encoding="little-endian-float32", scope="Sampled resolved cell temperatures; stationary enthalpy phase fraction; no velocity or VOF")
        if self.folder:
            self.coords.astype("<f4").tofile(self.folder/"field-coordinates.bin")

    def record(self, time, temperature, surface):
        import numpy as np
        if not self.folder: return
        values = np.asarray(temperature).ravel()
        if len(values) != len(self.coords) or not np.isfinite(values).all() or values.min() <= 0:
            raise ValueError("Invalid resolved field frame")
        if self.frames and time <= self.frames[-1]["time_s"]:
            raise ValueError("Nonmonotonic field time")
        if len(self.frames) >= 128: raise ValueError("Field frame budget exceeded")
        name = f"field-frame-{len(self.frames):03d}.bin"
        values.astype("<f4").tofile(self.folder/name)
        self.frames.append(dict(path=name, time_s=float(time), surface_m=float(surface),
            minimum_K=float(values.min()), maximum_K=float(values.max())))
        molten = (values >= self.metadata["liquidus_K"]) & (self.coords[:,2] < surface)
        if self.process and molten.any():
            layer = round(surface/(self.process["layer_um"]*1e-6))-1
            angle = math.radians(self.process["scanAngle_deg"]+layer*self.process["layerRotation_deg"])
            x,y,z = self.coords[molten].T
            along,across = x*math.cos(angle)+y*math.sin(angle), -x*math.sin(angle)+y*math.cos(angle)
            support = self.metadata["spacing_m"]*(abs(math.cos(angle))+abs(math.sin(angle)))/2
            self.frames[-1]["geometry"] = dict(angle_rad=angle,
                along_m=[float(along.min()-support),float(along.max()+support)],
                across_m=[float(across.min()-support),float(across.max()+support)],
                bottom_m=float(z.min()-self.metadata["spacing_m"]/2),
                scope="All concurrently molten cells; projected cell support; not an interpolated interface")

    def finish(self):
        import json
        if not self.folder: return None
        (self.folder/"field-series.json").write_text(json.dumps(self.metadata,allow_nan=False),encoding="utf-8")
        return "field-series.json"
