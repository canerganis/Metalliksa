"""RPC dispatch table for the LPBF worker (method name -> handler)."""
import base64

from four_alloy_materials import resolve_alloy_id, thermal_props, THERMAL_NAME, canonical_material_source
from physical_constants import GAS_CONSTANT_R
from lpbf_evidence import resource_estimate
from lpbf_simulation import validate
from lpbf_adaptive_feedforward import AdaptiveFeedforwardMitigator
from lpbf_experimental_validation import validate_experiment
from lpbf_fatigue_fracture import MurakamiFatigueEngine
from lpbf_multilaser_plume import ShieldGasFlow, PlumeParameters, MultiLaserPlumeEngine
from lpbf_optical_tomography import OpticalTomographySimulator
from lpbf_powder_dem_compaction import PowderCompactionEngine
from lpbf_solidification_microstructure import (
    compute_screening_field_microstructure,
    compute_solidification_microstructure,
)
from lpbf_support_optimization import SupportStructureOptimizer
from lpbf_thermal_accumulation import AlloyThermalProperties, HatchProcessConfig, MultiTrackThermalEngine
from lpbf_toolpath_kinematics import LPBFToolpathParser, GalvanometerKinematicsEngine, ScannerProfile
from lpbf_transient_enthalpy_fdm import TransientEnthalpyFDMSolver
from stl_voxelizer import STLVoxelizer


def _rpc_solidification_microstructure(request):
    # Phase 8
    payload = request["payload"]
    p = payload.get("params", {})
    cfd = payload.get("cfdResult", None)
    if cfd:
        # Legacy CFD path, only when a cfdResult is supplied (no UI caller does today).
        m = payload.get("material", {})
        return compute_solidification_microstructure(p, m, cfd)
    # Screening-field path: Python (lpbf_thermal_solver) is the authority for every number;
    # material k/liquidus/absorptivity are looked up there, never taken from the payload.
    # Unusable inputs return status "unavailable" with a reason instead of raising.
    return compute_screening_field_microstructure(p)


def _rpc_thermomechanical_distortion(request):
    # Phase 9
    payload = request["payload"]
    p = payload.get("params", {})
    m = payload.get("material", {})
    from lpbf_thermomechanical import analyze_distortion
    data = analyze_distortion(p, m)
    return data


def _rpc_industrial_fatigue(request):
    # Phase 10 (New)
    payload = request["payload"]
    from phase10_industrial import run_industrial_fatigue_analysis
    alloy = payload.get("alloy", "IN718")
    power = float(payload.get("power_W", 300))
    speed = float(payload.get("speed_mms", 1000))
    layer = float(payload.get("layer_um", 30.0))
    hatch = float(payload.get("hatch_um", 100.0))
    data = run_industrial_fatigue_analysis(alloy, power, speed, layer, hatch)
    return data


def _rpc_experimental_validation(request):
    # Phase 10
    payload = request["payload"]
    p = payload.get("params", {})
    m = payload.get("material", {})
    sim = payload.get("simulationResult", {})
    exp = payload.get("experimentalData", {})
    data = validate_experiment(p, m, sim, exp)
    return data


def _rpc_modulus_fno(request):
    # Phase 11
    from lpbf_modulus_fno import predict_part_scale_thermal_history
    payload = request["payload"]
    power_W = payload.get("laserPower_W", 250.0)
    speed_mms = payload.get("scanSpeed_mms", 1000.0)
    preheat_C = payload.get("preheatTemp_C", 25.0)
    hatch_um = payload.get("hatch_um", 100.0)
    layer_um = payload.get("layer_um", 40.0)
    data = predict_part_scale_thermal_history(
        power_W=power_W, speed_mms=speed_mms, preheat_C=preheat_C, hatch_um=hatch_um, layer_um=layer_um
    )
    return data


def _rpc_toolpath_kinematics(request):
    # Phase 12
    payload = request["payload"]
    raw_text = payload.get("content", "")
    fmt = payload.get("format", "gcode").lower()
    power = payload.get("defaultPower_W", 250.0)
    speed = payload.get("defaultSpeed_mms", 1000.0)
    skywriting = payload.get("skywritingEnabled", False)

    if fmt == "cli":
        vectors = LPBFToolpathParser.parse_cli(raw_text, default_power_W=power, default_speed_mms=speed)
    else:
        vectors = LPBFToolpathParser.parse_gcode(raw_text, default_power_W=power, default_speed_mms=speed)

    prof = ScannerProfile(
        accel_max_mms2=payload.get("accelMax_mms2", 40000.0),
        jump_speed_mms=payload.get("jumpSpeed_mms", 3000.0),
        laser_on_delay_us=payload.get("laserOnDelay_us", 100.0),
        laser_off_delay_us=payload.get("laserOffDelay_us", 120.0),
        mark_delay_us=payload.get("markDelay_us", 200.0),
        jump_delay_us=payload.get("jumpDelay_us", 350.0),
        skywriting_enabled=skywriting
    )
    engine = GalvanometerKinematicsEngine(prof)
    data = engine.simulate_toolpath(vectors)
    return data


def _rpc_fatigue_fracture(request):
    # Phase 13
    payload = request["payload"]
    alloy = payload.get("alloyName", "Ti-6Al-4V")
    engine = MurakamiFatigueEngine(alloy)
    sqrt_area = float(payload.get("sqrtArea_um", 45.0))
    location = payload.get("location", "internal")
    r_ratio = float(payload.get("stressRatio_R", -1.0))
    calc_type = payload.get("type", "full")

    fatigue_res = engine.calculate_fatigue_limit(sqrt_area, location, r_ratio)
    kt_curve = engine.generate_kitagawa_takahashi_curve(location, r_ratio, n_points=30)
    paris_res = engine.simulate_paris_crack_growth(
        initial_defect_sqrt_area_um=sqrt_area,
        cyclic_stress_amplitude_MPa=float(payload.get("stressAmplitude_MPa", 220.0)),
        stress_ratio_R=r_ratio
    )
    data = {
        "fatigue_limit": fatigue_res,
        "kitagawa_takahashi_curve": kt_curve,
        "paris_crack_growth": paris_res
    }
    return data


def _rpc_toolpath_thermal_map(request):
    # Option 1 Toolpath 3D Viz
    payload = request["payload"]
    from lpbf_toolpath_thermal_api import generate_toolpath_thermal_map
    alloy = payload.get("alloy", "IN718")
    power = float(payload.get("power_W", 250))
    speed = float(payload.get("speed_mms", 1000))
    strategy = payload.get("strategy", "chessboard")
    hatch = float(payload.get("hatch_um", 100))
    angle = float(payload.get("angle_deg", 45))
    island = float(payload.get("island_size_mm", 5.0))
    data = generate_toolpath_thermal_map(alloy, power, speed, strategy, hatch, angle, island)
    return data


def _rpc_stl_voxelize(request):
    # Phase 14
    payload = request["payload"]
    stl_text = payload.get("stlContent", "")
    resolution = int(payload.get("resolution", 32))
    defects = payload.get("defects", [])

    if stl_text.strip().startswith("solid"):
        triangles = STLVoxelizer.parse_ascii_stl(stl_text)
    else:
        try:
            raw_bytes = base64.b64decode(stl_text)
            triangles = STLVoxelizer.parse_binary_stl(raw_bytes)
        except Exception:
            triangles = STLVoxelizer.parse_ascii_stl(stl_text)

    data = STLVoxelizer.voxelize(triangles, resolution=resolution, detected_defects=defects)
    return data


def _rpc_adaptive_feedforward(request):
    # Phase 15
    payload = request["payload"]
    raw_text = payload.get("content", "")
    fmt = payload.get("format", "gcode").lower()
    power = float(payload.get("defaultPower_W", 280.0))
    speed = float(payload.get("defaultSpeed_mms", 1000.0))
    apply_rot = bool(payload.get("apply67DegRotation", False))
    layer_idx = int(payload.get("layerIndex", 1))

    if fmt == "cli":
        vectors = LPBFToolpathParser.parse_cli(raw_text, default_power_W=power, default_speed_mms=speed)
    else:
        vectors = LPBFToolpathParser.parse_gcode(raw_text, default_power_W=power, default_speed_mms=speed)

    prof = ScannerProfile(
        accel_max_mms2=float(payload.get("accelMax_mms2", 40000.0)),
        jump_speed_mms=float(payload.get("jumpSpeed_mms", 3000.0))
    )
    mitigator = AdaptiveFeedforwardMitigator(prof)
    data = mitigator.process_toolpath(vectors, apply_67_deg_rotation=apply_rot, layer_index=layer_idx)
    return data


def _rpc_multilaser_plume(request):
    # Phase 16
    payload = request["payload"]
    gas_cfg = payload.get("gasFlow", {})
    flow = ShieldGasFlow(
        gas_type=gas_cfg.get("gasType", "Argon"),
        velocity_m_s=float(gas_cfg.get("velocity_m_s", 2.0)),
        angle_deg=float(gas_cfg.get("angle_deg", 0.0))
    )
    plume_cfg = payload.get("plumeParams", {})
    plume_params = PlumeParameters(
        sigma_plume_mm=float(plume_cfg.get("sigma_plume_mm", 2.5)),
        decay_length_mm=float(plume_cfg.get("decay_length_mm", 25.0)),
        base_extinction_coeff=float(plume_cfg.get("base_extinction_coeff", 0.35)),
        min_collision_dist_mm=float(plume_cfg.get("min_collision_dist_mm", 1.0)),
        attenuation_hazard_threshold=float(plume_cfg.get("attenuation_hazard_threshold", 0.10))
    )
    engine = MultiLaserPlumeEngine(flow, plume_params)
    l1_vecs = [tuple(v) for v in payload.get("laser1_vectors", [])]
    l2_vecs = [tuple(v) for v in payload.get("laser2_vectors", [])]
    if not l1_vecs:
        l1_vecs = [(0.0, 0.0, 40.0, 0.0, 300.0, 1000.0)]
    if not l2_vecs:
        l2_vecs = [(10.0, 1.0, 50.0, 1.0, 300.0, 1000.0)]

    mode = payload.get("mode", "simulate")
    if mode == "optimize":
        data = engine.optimize_deconfliction_schedule(l1_vecs, l2_vecs)
    else:
        data = engine.simulate_multitrack_scenarios(l1_vecs, l2_vecs)
    return data


def _rpc_thermal_accumulation(request):
    # Phase 17
    payload = request["payload"]
    mat_cfg = payload.get("material", {})
    alloy_name = mat_cfg.get("name")
    alloy_id = resolve_alloy_id(alloy_name)
    if alloy_id is None:
        raise ValueError("Unknown or missing alloy for thermal accumulation")
    # Shared screening constants; this model uses IR absorptivity.
    props = thermal_props(alloy_id)
    mat = AlloyThermalProperties(
        name=THERMAL_NAME[alloy_id],
        density_kg_m3=props["density_kg_m3"],
        specific_heat_J_kgK=props["specific_heat_J_kgK"],
        thermal_conductivity_W_mK=props["thermal_conductivity_W_mK"],
        absorptivity=props["absorptivity_IR"],
        melting_temp_K=props["liquidus_C"] + 273.15,
        boiling_temp_K=props["boiling_C"] + 273.15
    )
    hatch_cfg = payload.get("config", {})
    cfg = HatchProcessConfig(
        laser_power_W=float(hatch_cfg.get("laserPower_W", 280.0)),
        scan_velocity_mm_s=float(hatch_cfg.get("scanVelocity_mms", 1000.0)),
        beam_diameter_um=float(hatch_cfg.get("beamDiameter_um", 80.0)),
        hatch_spacing_um=float(hatch_cfg.get("hatchSpacing_um", 100.0)),
        track_length_mm=float(hatch_cfg.get("trackLength_mm", 10.0)),
        num_tracks=int(hatch_cfg.get("numTracks", 10)),
        bed_temperature_K=float(hatch_cfg.get("bedTemperature_K", 353.15)),
        turnaround_delay_ms=float(hatch_cfg.get("turnaroundDelay_ms", 0.5))
    )
    engine = MultiTrackThermalEngine(mat)
    mode = payload.get("mode", "simulate")
    if mode == "optimize":
        allowable_drift = float(payload.get("maxAllowableDrift_K", 120.0))
        data = engine.optimize_dwell_delays(cfg, max_allowable_drift_K=allowable_drift)
    else:
        data = engine.simulate_hatch_sequence(cfg)
    return data


def _rpc_powder_dem_compaction(request):
    # Phase 18
    payload = request["payload"]
    engine = PowderCompactionEngine(
        d10_um=float(payload.get("d10_um", 20.0)),
        d50_um=float(payload.get("d50_um", 35.0)),
        d90_um=float(payload.get("d90_um", 55.0)),
        recoater_gap_um=float(payload.get("recoater_gap_um", 60.0)),
        box_width_um=float(payload.get("box_width_um", 500.0))
    )
    data = engine.generate_psd_deterministic(int(payload.get("num_particles", 500)))
    return data


def _rpc_optical_tomography(request):
    # Phase 19
    payload = request["payload"]
    sim = OpticalTomographySimulator(
        sensor_resolution=(int(payload.get("res_x", 64)), int(payload.get("res_y", 64))),
        fov_um=float(payload.get("fov_um", 1000.0)),
        emissivity=float(payload.get("emissivity", 0.35))
    )
    data = sim.simulate_sensor_frame(
        laser_power_W=float(payload.get("laserPower_W", 280.0)),
        scan_speed_mm_s=float(payload.get("scanSpeed_mms", 1000.0)),
        material_k=float(payload.get("material_k", 15.0)),
        material_alpha=float(payload.get("material_alpha", 5e-6)),
        T0_K=float(payload.get("T0_K", 300.0))
    )
    return data


def _rpc_support_optimization(request):
    # Phase 20
    payload = request["payload"]
    opt = SupportStructureOptimizer(
        E_modulus_Pa=float(payload.get("E_modulus_Pa", 110e9)),
        cte_1_K=float(payload.get("cte_1_K", 9e-6)),
        yield_strength_Pa=float(payload.get("yield_strength_Pa", 950e6)),
        thermal_k_W_mK=float(payload.get("thermal_k_W_mK", 15.0)),
        T_melt_K=float(payload.get("T_melt_K", 1928.0)),
        T_preheat_K=float(payload.get("T_preheat_K", 353.15))
    )
    # Quick response bundling both thermal and mechanical requirements
    heat_input = float(payload.get("heat_input_W", 280.0))
    L_m = float(payload.get("support_length_m", 0.01))
    area_m2 = float(payload.get("layer_area_m2", 0.0001))
    data = {
        "thermal_area_m2": opt.calculate_thermal_requirement(heat_input, L_m),
        "mechanical_area_m2": opt.calculate_mechanical_requirement(area_m2)
    }
    return data


def _rpc_bayesian_optimizer(request):
    payload = request["payload"]
    from lpbf_bayesian_optimizer import run_bayesian_optimization
    data = run_bayesian_optimization(
        alloy_id=payload.get("alloyId", "in718"),
        param_bounds=payload.get("paramBounds"),
        n_iter=payload.get("nIterations", 20),
        n_warmup=payload.get("nWarmup", 5),
        seed=payload.get("seed", 42)
    )
    return data


def _rpc_transient_enthalpy_fdm(request):
    # Phase 21
    payload = request["payload"]
    solver = TransientEnthalpyFDMSolver(
        nx=int(payload.get("nx", 100)),
        nz=int(payload.get("nz", 50)),
        dx=float(payload.get("dx", 2e-6)),
        dz=float(payload.get("dz", 2e-6))
    )
    # Using 2D method signature
    data = solver.solve_meltpool_cross_section(
        power_W=float(payload.get("power_W", 250.0)),
        speed_m_s=float(payload.get("speed_m_s", 0.8)),
        T_preheat_K=float(payload.get("T_preheat_K", 300.0)),
        rho=float(payload.get("rho", 4420.0)),
        cp=float(payload.get("cp", 670.0)),
        k_solid=float(payload.get("k_solid", 15.0)),
        k_liquid=float(payload.get("k_liquid", 25.0)),
        latent_heat_J_kg=float(payload.get("latent_heat_J_kg", 2.9e5)),
        T_solidus=float(payload.get("T_solidus", 1878.0)),
        T_liquidus=float(payload.get("T_liquidus", 1928.0)),
        sim_time_s=float(payload.get("sim_time_s", 5e-4)),
        dt=float(payload.get("dt", 1e-6))
    )
    # Convert numpy arrays to lists for JSON serialization
    if isinstance(data, dict):
        for k, v in data.items():
            if hasattr(v, 'tolist'):
                data[k] = v.tolist()
    return data


# Alloy data the Phase 22 solver needs. They come ONLY from four_alloy_materials;
# a request that carries any of them is rejected rather than silently preferred.
_TRANSIENT_3D_GPU_MATERIAL_OVERRIDE_KEYS = (
    "rho", "L_f", "T_solidus", "T_liquidus", "Lv", "Rs", "Tv",
    "cp_solid", "cp_liquid", "k_solid", "k_liquid",
)


def _transient_3d_gpu_material_from_authority(payload):
    """Resolve payload alloy identity to (alloyId, solver material kwargs, authority digest)."""
    if not isinstance(payload, dict):
        raise ValueError("transient-3d-gpu requires a supported alloy identity; got a non-object payload")
    overrides = [key for key in _TRANSIENT_3D_GPU_MATERIAL_OVERRIDE_KEYS if key in payload]
    if overrides:
        raise ValueError(
            "material properties come from four_alloy_materials; remove "
            + ", ".join(overrides) + " from the transient-3d-gpu payload and send alloyId"
        )
    given = [payload[key] for key in ("alloyId", "materialName") if payload.get(key) is not None]
    resolved = {resolve_alloy_id(value) for value in given}
    if not given or None in resolved or len(resolved) != 1:
        raise ValueError(
            "transient-3d-gpu requires a supported alloy identity; got "
            f"alloyId={payload.get('alloyId')!r}, materialName={payload.get('materialName')!r}"
        )
    aid = resolved.pop()
    t = thermal_props(aid)
    material = {
        "rho": t["density_kg_m3"],
        "L_f": t["latent_heat_fusion_J_kg"],
        "T_solidus": t["solidus_C"] + 273.15,
        "T_liquidus": t["liquidus_C"] + 273.15,
        "Lv": t["latent_heat_vap_J_kg"],
        # Hertz-Knudsen / Clausius-Clapeyron in the kernel use the specific gas constant, J/(kg K).
        "Rs": GAS_CONSTANT_R.value / t["M_molar_kg_mol"],
        "Tv": t["boiling_C"] + 273.15,
        "cp_solid": t["specific_heat_J_kgK"],
        "cp_liquid": t["specific_heat_liquid_J_kgK"],
        "k_solid": t["thermal_conductivity_W_mK"],
        "k_liquid": t["thermal_conductivity_liquid_W_mK"],
    }
    return aid, material, canonical_material_source(aid)[1]


def _rpc_transient_3d_gpu(request):
    # Phase 22
    from lpbf_transient_3d_gpu import TransientEnthalpy3DGPU
    payload = request["payload"]
    alloy_id, material, material_sha256 = _transient_3d_gpu_material_from_authority(payload)

    # Safety clamping to prevent GPU OOM
    nx = max(8, min(256, int(payload.get("nx", 64))))
    ny = max(8, min(256, int(payload.get("ny", 64))))
    nz = max(8, min(128, int(payload.get("nz", 32))))

    solver = TransientEnthalpy3DGPU(
        nx=nx,
        ny=ny,
        nz=nz,
        dx=float(payload.get("dx", 2e-6)),
        dy=float(payload.get("dy", 2e-6)),
        dz=float(payload.get("dz", 2e-6))
    )
    toolpath = payload.get("toolpath", {
        't': [0.0, 100e-6],
        'x': [32e-6, 96e-6],
        'y': [32e-6, 32e-6],
        'p': [float(payload.get("power_W", 200.0)), float(payload.get("power_W", 200.0))]
    })
    
    # Check for empty toolpath arrays
    if not toolpath.get("t") or not toolpath.get("x") or not toolpath.get("y") or not toolpath.get("p"):
         raise ValueError("Toolpath arrays cannot be empty")

    data = solver.solve_toolpath(
        toolpath=toolpath,
        T_preheat_K=float(payload.get("T_preheat_K", 300.0)),
        **material,
    )
    if isinstance(data, dict):
        data["materialAuthority"] = {
            "alloyId": alloy_id,
            "authority": canonical_material_source(alloy_id)[0]["authority"],
            "materialSha256": material_sha256,
            "valuesUsed": dict(material),
            "units": {
                "rho": "kg/m3", "L_f": "J/kg", "T_solidus": "K", "T_liquidus": "K",
                "Lv": "J/kg", "Rs": "J/(kg K) = R/M_molar", "Tv": "K",
                "cp_solid": "J/(kg K)", "cp_liquid": "J/(kg K)",
                "k_solid": "W/(m K)", "k_liquid": "W/(m K)",
            },
        }
    return data


def _rpc_micrograph_measure(request):
    # Micrograph measurement authority (numpy/scipy only); invalid requests raise MeasureInputError.
    from micrograph_measure import measure
    return measure(request.get("payload"))


def _rpc_keyhole_raytracing(request):
    # Phase 26
    from lpbf_keyhole_raytracing import compute_keyhole_raytracing
    data = compute_keyhole_raytracing(request.get("payload", {}))
    return data


# Pure research endpoints: handler(request) -> data.
RESEARCH_HANDLERS = {
    "solidification-microstructure": _rpc_solidification_microstructure,
    "thermomechanical-distortion": _rpc_thermomechanical_distortion,
    "industrial-fatigue": _rpc_industrial_fatigue,
    "experimental-validation": _rpc_experimental_validation,
    "modulus-fno": _rpc_modulus_fno,
    "toolpath-kinematics": _rpc_toolpath_kinematics,
    "fatigue-fracture": _rpc_fatigue_fracture,
    "toolpath-thermal-map": _rpc_toolpath_thermal_map,
    "stl-voxelize": _rpc_stl_voxelize,
    "adaptive-feedforward": _rpc_adaptive_feedforward,
    "multilaser-plume": _rpc_multilaser_plume,
    "thermal-accumulation": _rpc_thermal_accumulation,
    "powder-dem-compaction": _rpc_powder_dem_compaction,
    "optical-tomography": _rpc_optical_tomography,
    "support-optimization": _rpc_support_optimization,
    "bayesian-optimizer": _rpc_bayesian_optimizer,
    "transient-enthalpy-fdm": _rpc_transient_enthalpy_fdm,
    "transient-3d-gpu": _rpc_transient_3d_gpu,
    "keyhole-raytracing": _rpc_keyhole_raytracing,
    "micrograph-measure": _rpc_micrograph_measure,
}


# Methods served by the job queue: handler(queue, request) -> data.
QUEUE_HANDLERS = {
    "submit": lambda queue, request: queue.submit(request["payload"]),
    "submit-repeat": lambda queue, request: queue.submit(request["payload"], execution_scope="repeat"),
    "artifact": lambda queue, request: queue.artifact(request["payload"]),
    "capture": lambda queue, request: queue.capture(request["payload"]),
    "archive-capture": lambda queue, request: queue.archive_capture(request["payload"]),
    "get": lambda queue, request: queue.get(request["payload"]),
    "cancel": lambda queue, request: queue.cancel(request["payload"]),
    "purge-unverified-artifacts": lambda queue, request: _purge_unverified_artifacts(queue, request),
}


def _purge_unverified_artifacts(queue, request):
    payload = request.get("payload", {})
    return queue.purge_unverified_artifacts(
        job=payload.get("job"),
        older_than_seconds=float(payload.get("olderThanSeconds", 0)),
        dry_run=bool(payload.get("dryRun", False))
    )


def _estimate(request):
    p, m = validate(request["payload"])
    return resource_estimate(p, m)


def method_names():
    """Every RPC method name the worker serves."""
    return {"capabilities", "estimate", *QUEUE_HANDLERS, *RESEARCH_HANDLERS}


def dispatch(request, queue, capabilities_handler):
    """Resolve request["method"] and return its data; unknown methods raise ValueError."""
    method = request["method"]
    if not isinstance(method, str):
        raise ValueError("Unknown method")
    if method == "capabilities":
        return capabilities_handler(queue)
    if method == "estimate":
        return _estimate(request)
    if method in QUEUE_HANDLERS:
        return QUEUE_HANDLERS[method](queue, request)
    if method in RESEARCH_HANDLERS:
        return RESEARCH_HANDLERS[method](request)
    raise ValueError("Unknown method")
