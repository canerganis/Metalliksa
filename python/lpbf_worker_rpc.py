"""RPC dispatch table for the LPBF worker (method name -> handler)."""
import base64

from four_alloy_materials import resolve_alloy_id, thermal_props, THERMAL_NAME
from lpbf_evidence import resource_estimate
from lpbf_simulation import validate
from lpbf_adaptive_feedforward import AdaptiveFeedforwardMitigator
from lpbf_fatigue_fracture import MurakamiFatigueEngine
from lpbf_multilaser_plume import ShieldGasFlow, PlumeParameters, MultiLaserPlumeEngine
from lpbf_optical_tomography import OpticalTomographySimulator
from lpbf_solidification_microstructure import (
    compute_screening_field_microstructure,
    compute_solidification_microstructure,
)
from lpbf_thermal_accumulation import AlloyThermalProperties, HatchProcessConfig, MultiTrackThermalEngine
from lpbf_toolpath_kinematics import LPBFToolpathParser, GalvanometerKinematicsEngine, ScannerProfile
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
    "toolpath-kinematics": _rpc_toolpath_kinematics,
    "fatigue-fracture": _rpc_fatigue_fracture,
    "toolpath-thermal-map": _rpc_toolpath_thermal_map,
    "stl-voxelize": _rpc_stl_voxelize,
    "adaptive-feedforward": _rpc_adaptive_feedforward,
    "multilaser-plume": _rpc_multilaser_plume,
    "thermal-accumulation": _rpc_thermal_accumulation,
    "optical-tomography": _rpc_optical_tomography,
    "keyhole-raytracing": _rpc_keyhole_raytracing,
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
