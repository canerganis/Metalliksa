#!/usr/bin/env python3
"""
Single LPBF Build Job engine: Rosenthal melt-pool screening + STL slicer + print verdict.

The industrial UI must display this verdict. TypeScript must not re-decide printability.
Melt-pool geometry for the verdict is regularized Rosenthal. Eagar–Tsai (`eagar-tsai-v1`) is opt-in on the thermal / Melt Pool 3D lab only — it does not change this verdict.
"""

import json
import sys
import time

from four_alloy_materials import (
    ALLOY_MATERIALS,
    LITERATURE_PV_WINDOWS,
    canonical_material_source,
    evaluate_literature_pv,
    resolve_alloy_id,
)
from lpbf_build_job_schema import LpbfBuildJobRequest
from lpbf_build_job_material_snapshot import (
    MATERIAL_PROPERTY_REVISION,
    build_ambench_material_property_snapshot,
    build_build_job_identity,
    build_material_property_snapshot,
)
from lpbf_job_cache import (
    BUILD_JOB_MODEL_ID,
    BUILD_JOB_SOLVER_REVISION,
    build_cache_key,
    cache_get,
    cache_put,
)
from lpbf_screening_uq import apply_uq_prop_scales, run_screening_uq
from lpbf_thermal_solver import calculate_meltpool_physics
from murakami_fatigue_screening import (
    build_qualification_block,
    evaluate_murakami_block,
    parse_defect_sqrt_areas_text,
)
from nist_ambench_2018_02 import (
    IN625_VALIDATION_PROPS,
    coverage_for_alloy,
    run_ambench_validation,
)
from stl_slicer_build_time_solver import solve_slicer
from lpbf_part_porosity_aggregator import aggregate_part_porosity
from lpbf_scanner_kinematics import calculate_scanner_kinematics
from lpbf_solidification_microstructure import compute_solidification_microstructure
from kinetics_ttt_cct_solver import solve_phase_transformation_kinetics

# Hatch/layer used with literature-box mid P–v when LoF is the dominant gate.
# Matches src/utils/lpbfDemoVectors.ts printable demos (inputs only).
_LOF_HT = {
    "ti6al4v": {"hatch_um": 100, "layer_um": 30, "beamDiameter_um": 80},
    "ss316l": {"hatch_um": 90, "layer_um": 30, "beamDiameter_um": 80},
    "alsi10mg": {"hatch_um": 110, "layer_um": 30, "beamDiameter_um": 100},
    "in718": {"hatch_um": 90, "layer_um": 30, "beamDiameter_um": 80},
}

DEFAULT_PROCESS_SEED = 42


def _gate(gid, status, measured, required, unit, note):
    return {
        "id": gid,
        "status": status,
        "measured": measured,
        "required": required,
        "unit": unit,
        "note": note,
    }


def _suggested_patch(thermal, alloy_id, dominant_gate, verdict):
    if verdict == "printable" or dominant_gate in (None, "none"):
        return None
    box = LITERATURE_PV_WINDOWS[alloy_id]
    mid_p = int(round((box["powerMin_W"] + box["powerMax_W"]) / 2.0))
    mid_v = int(round((box["speedMin_mm_s"] + box["speedMax_mm_s"]) / 2.0))
    pp = thermal["processParameters"]
    cur_h = float(pp["hatchSpacing_um"])
    cur_t = float(pp["layerThickness_um"])
    cur_d = float(pp["beamDiameter_um"])
    ht = _LOF_HT.get(alloy_id, {"hatch_um": 100, "layer_um": 30, "beamDiameter_um": cur_d})
    if dominant_gate == "keyhole":
        return {
            "laserPower_W": int(box["powerMin_W"]),
            "scanSpeed_mms": int(box["speedMax_mm_s"]),
            "hatch_um": int(round(cur_h)),
            "layer_um": int(round(cur_t)),
            "beamDiameter_um": int(round(cur_d)),
        }
    if dominant_gate in ("lof_tang", "lof_wh", "lof_dt", "downskin"):
        return {
            "laserPower_W": mid_p,
            "scanSpeed_mms": mid_v,
            "hatch_um": ht["hatch_um"],
            "layer_um": ht["layer_um"],
            "beamDiameter_um": ht["beamDiameter_um"],
        }
    return {
        "laserPower_W": mid_p,
        "scanSpeed_mms": mid_v,
        "hatch_um": int(round(cur_h)),
        "layer_um": int(round(cur_t)),
        "beamDiameter_um": int(round(cur_d)),
    }


def compose_verdict(thermal, alloy_id, extras=None):
    extras = extras or {}
    W = float(thermal["meltPoolGeometry"]["width_um"])
    D = float(thermal["meltPoolGeometry"]["depth_um"])
    h = float(thermal["processParameters"]["hatchSpacing_um"])
    t = float(thermal["processParameters"]["layerThickness_um"])
    width_over_hatch = W / max(1e-6, h)
    depth_over_layer = D / max(1e-6, t)
    tang = float(
        thermal["defectDiagnostics"].get(
            "tangIndex_hW_tD",
            thermal["defectDiagnostics"].get("lackOfFusionOverlapIndex", 0.0),
        )
    )

    def_ = thermal["defectDiagnostics"]
    lof_fail = def_["lackOfFusionStatus"] == "Fail"
    lof_warn = def_["lackOfFusionStatus"] == "Warning"
    keyhole_high = str(def_["keyholePorosityRisk"]).startswith("High")
    balling_high = str(def_["ballingInstabilityRisk"]).startswith("High")
    recoater_high = str(def_["recoaterCrashRisk"]).startswith("High")
    distortion_high = float(def_["distortionIndex"]) >= 0.65
    dh = float(thermal["processParameters"]["normalizedEnthalpy"])
    win = evaluate_literature_pv(
        alloy_id,
        float(thermal["processParameters"]["laserPower_W"]),
        float(thermal["processParameters"]["scanSpeed_mm_s"]),
    )

    downskin_angle = extras.get("downskinOverhang_deg")
    downskin_fail = False
    downskin_warn = False
    if downskin_angle is not None:
        # Overhang from vertical: >45° downskin needs support / parameter change in screening.
        if float(downskin_angle) > 55.0:
            downskin_fail = True
        elif float(downskin_angle) > 45.0:
            downskin_warn = True

    reasons = []
    if lof_fail:
        reasons.append(
            f"Lack of fusion (Tang): (h/W)²+(t/D)² = {tang:.3f} (need ≤1.0); "
            f"W/h = {width_over_hatch:.2f}, D/t = {depth_over_layer:.2f}."
        )
    elif lof_warn:
        reasons.append(
            f"Tang overlap marginal: (h/W)²+(t/D)² = {tang:.3f} (pass ≤0.80)."
        )
    if keyhole_high:
        reasons.append(f"Keyhole porosity: ΔH/hₛ = {dh} (King onset ~30).")
    if balling_high:
        reasons.append(
            f"Plateau–Rayleigh balling: L/W = {thermal['meltPoolGeometry']['aspectRatio_L_over_W']}."
        )
    if recoater_high:
        reasons.append("Recoater crash / part curl risk from residual stress.")
    if distortion_high:
        reasons.append(f"Inherent-strain distortion index {def_['distortionIndex']} (≥0.65).")
    if downskin_fail:
        reasons.append(
            f"Downskin overhang {float(downskin_angle):.1f}° from vertical exceeds 55° screening gate."
        )
    elif downskin_warn:
        reasons.append(
            f"Downskin overhang {float(downskin_angle):.1f}° is marginal (45–55°); expect support or stripe reorient."
        )
    if not win["inside"]:
        box = win["box"]
        reasons.append(
            f"P–v is outside the {alloy_id} literature box "
            f"({box['powerMin_W']}–{box['powerMax_W']} W, {box['speedMin_mm_s']}–{box['speedMax_mm_s']} mm/s)."
        )

    verdict = "printable"
    if lof_fail or balling_high or downskin_fail or (keyhole_high and dh > 35):
        verdict = "do-not-print"
    elif lof_warn or keyhole_high or recoater_high or distortion_high or downskin_warn or (not win["inside"]):
        verdict = "risky"

    if not reasons:
        reasons.append(
            "Conduction-mode melt pool with Tang hatch/layer overlap above LoF gates. "
            "VED is not used as the sole criterion."
        )

    headline = {
        "printable": "Printable — stay in the conduction window",
        "risky": "Risky — qualify with coupon builds before flight hardware",
        "do-not-print": "Do not print — change P, v, h, or t before a build",
    }[verdict]

    lw = round(width_over_hatch, 3)
    dt = round(depth_over_layer, 3)
    tang_r = round(tang, 3)
    tang_status = "fail" if lof_fail else ("warn" if lof_warn else "pass")
    kh_status = "fail" if (keyhole_high and dh > 35) else ("warn" if keyhole_high else "pass")
    ball_status = "fail" if balling_high else "pass"
    lit_status = "pass" if win["inside"] else "warn"
    rec_status = "warn" if recoater_high else "pass"
    dist_status = "warn" if distortion_high else "pass"
    ds_status = "fail" if downskin_fail else ("warn" if downskin_warn else "pass")
    aspect = float(thermal["meltPoolGeometry"]["aspectRatio_L_over_W"])

    gates = [
        _gate(
            "lof_tang",
            tang_status,
            tang_r,
            1.0,
            "1",
            "Tang LoF index (h/W)²+(t/D)² — pass ≤0.80, fail >1.0. Primary hatch/layer fusion gate.",
        ),
        _gate(
            "lof_wh",
            tang_status,
            lw,
            1.05,
            "1",
            "Diagnostic melt-pool width / hatch (W/h). Informational; Tang index is the gate.",
        ),
        _gate(
            "lof_dt",
            tang_status,
            dt,
            1.15,
            "1",
            "Diagnostic melt-pool depth / layer (D/t). Informational; Tang index is the gate.",
        ),
        _gate(
            "keyhole",
            kh_status,
            dh,
            30.0,
            "1",
            "King normalized enthalpy ΔH/hₛ — onset ~30; do-not-print when High and >35.",
        ),
        _gate(
            "balling",
            ball_status,
            aspect,
            None,
            "1",
            "Plateau–Rayleigh aspect L/W from Rosenthal length — High → fail.",
        ),
        _gate(
            "literature_pv",
            lit_status,
            1.0 if win["inside"] else 0.0,
            1.0,
            "inside",
            "Inside four-alloy published P–v box (screening envelope, not OEM machine limits).",
        ),
        _gate(
            "recoater",
            rec_status,
            float(def_["distortionIndex"]),
            None,
            "index",
            "Recoater-crash heuristic from residual-stress index — not a blade FEA.",
        ),
        _gate(
            "distortion",
            dist_status,
            float(def_["distortionIndex"]),
            0.65,
            "index",
            "Inherent-strain distortion screening (≥0.65 warn) — not Goldak FEA.",
        ),
        _gate(
            "downskin",
            ds_status,
            None if downskin_angle is None else round(float(downskin_angle), 1),
            45.0,
            "deg",
            "Overhang from vertical: >45° warn, >55° fail. Omitted angle → pass.",
        ),
    ]
    dominant = "none"
    for g in gates:
        if g["status"] == "fail":
            dominant = g["id"]
            break
    if dominant == "none":
        for g in gates:
            if g["status"] == "warn":
                dominant = g["id"]
                break

    return {
        "verdict": verdict,
        "headline": headline,
        "reasons": reasons,
        "lofGeometry": {
            "widthOverHatch": lw,
            "depthOverLayer": dt,
            "tangIndex": tang_r,
            "hOverW": round(h / max(1e-6, W), 3),
            "tOverD": round(t / max(1e-6, D), 3),
        },
        "literatureWindow": win,
        "gates": gates,
        "dominantGate": dominant,
        "suggestedPatch": _suggested_patch(thermal, alloy_id, dominant, verdict),
    }


def _scan_strategy_assumptions(scan_strategy, stripe_width_mm, rotation_deg, dwell_ms):
    strat = (scan_strategy or "stripe").strip().lower().replace("_", "-")
    return [
        (
            f"Scan strategy screening default: {strat}; stripe width {stripe_width_mm} mm; "
            f"inter-layer rotation {rotation_deg}°; hatch dwell {dwell_ms} ms."
        ),
        "Strategy DOIs: 10.1115/1.4031649 (Cheng et al. residual stress / scan strategy); "
        "10.1016/j.jmapro.2020.01.039 (stripe / hatch strategy process effects); "
        "10.1016/j.jmrt.2022.04.055 (scan strategy on microstructure / defects); "
        "10.1016/j.matdes.2018.107552 (scan strategy design of LPBF parts).",
    ]


def solve_lpbf_build_job(data):
    t0 = time.time()
    try:
        req = LpbfBuildJobRequest.model_validate(data if isinstance(data, dict) else {})
        data = req.to_solver_dict()
    except Exception as e:
        return {"success": False, "error": f"Invalid LPBF build-job payload: {e}"}

    # Normalize paste → defect list before cache key.
    if not data.get("defectSqrtAreas_um") and data.get("defectSqrtAreasPaste"):
        parsed = parse_defect_sqrt_areas_text(data.get("defectSqrtAreasPaste"))
        if parsed:
            data["defectSqrtAreas_um"] = parsed

    requested_alloy = data.get("alloyId")
    if requested_alloy is None or not str(requested_alloy).strip():
        alloy_id = "in718"
    else:
        alloy_id = resolve_alloy_id(requested_alloy)
        if alloy_id is None:
            return {
                "success": False,
                "error": (
                    f"Unsupported LPBF alloy identity: {requested_alloy!r}. "
                    "No surrogate alloy was submitted."
                ),
            }
    mats = ALLOY_MATERIALS[alloy_id]
    for field, canonical_name in (
        ("thermalMaterial", mats["thermal"]),
        ("slicerMaterial", mats["slicer"]),
    ):
        override = data.get(field)
        if override is None or not str(override).strip():
            continue
        override_alloy = resolve_alloy_id(override)
        if override_alloy != alloy_id:
            return {
                "success": False,
                "error": (
                    f"{field} {override!r} does not match requested LPBF alloy "
                    f"{alloy_id!r}; expected an alias of {canonical_name!r}."
                ),
            }

    # Aliases are accepted only as identity assertions; always pass the mapped
    # canonical name to the underlying solver so the requested alloy controls it.
    thermal_mat = mats["thermal"]
    slicer_mat = mats["slicer"]
    try:
        material_snapshot, material_property_sha256 = build_material_property_snapshot(
            alloy_id, thermal_mat, slicer_mat
        )
        material_authority_snapshot, material_authority_revision_sha256 = canonical_material_source(alloy_id)
        build_job_identity = build_build_job_identity(
            alloy_id,
            BUILD_JOB_MODEL_ID,
            BUILD_JOB_SOLVER_REVISION,
            material_property_sha256,
            material_snapshot["schemaVersion"],
        )
        ambench_snapshot, ambench_property_sha256 = (
            build_ambench_material_property_snapshot(IN625_VALIDATION_PROPS)
            if data.get("includeAmbench", False) else (None, None)
        )
    except (KeyError, TypeError, ValueError) as e:
        return {"success": False, "error": f"Invalid LPBF material properties: {e}"}

    bypass_cache = bool(data.get("bypassCache", False))
    cache_data = dict(data)
    cache_data["alloyId"] = alloy_id
    cache_data["thermalMaterial"] = thermal_mat
    cache_data["slicerMaterial"] = slicer_mat
    cache_data["materialPropertySha256"] = material_property_sha256
    cache_data["materialAuthorityRevisionSha256"] = material_authority_revision_sha256
    cache_data["buildJobIdentity"] = build_job_identity
    cache_data["amBenchMaterialPropertySha256"] = ambench_property_sha256
    try:
        cache_key = build_cache_key(cache_data)
    except (TypeError, ValueError) as e:
        return {"success": False, "error": f"Invalid LPBF build-job cache input: {e}"}
    if not bypass_cache:
        cached = cache_get(cache_key)
        if (
            cached is not None
            and cached.get("success") is True
            and cached.get("solverRevision") == BUILD_JOB_SOLVER_REVISION
            and cached.get("buildJobIdentity") == build_job_identity
            and cached.get("alloyId") == alloy_id
            and cached.get("materialPropertySha256") == material_property_sha256
            and cached.get("materialAuthorityRevisionSha256") == material_authority_revision_sha256
            and cached.get("materialPropertySnapshot") == material_snapshot
            and cached.get("amBenchMaterialPropertySha256") == ambench_property_sha256
            and cached.get("amBenchMaterialPropertySnapshot") == ambench_snapshot
        ):
            cached["computeTimeMs"] = round((time.time() - t0) * 1000.0, 1)
            if cached.get("thermal"):
                cached["thermal"]["computeTimeMs"] = cached["computeTimeMs"]
            return cached

    power = float(data.get("laserPower_W", 285.0))
    speed = float(data.get("scanSpeed_mm_s", data.get("scanSpeed_mms", 960.0)))
    beam = float(data.get("beamDiameter_um", 80.0))
    preheat = float(data.get("preheatTemp_C", 80.0))
    layer = float(data.get("layerThickness_um", 40.0))
    hatch = float(data.get("hatchSpacing_um", 110.0))
    wavelength = data.get("laserWavelength", "IR_1064nm")
    process_seed = int(data.get("processSeed", data.get("seed", DEFAULT_PROCESS_SEED)))

    incline_deg = float(data.get("inclineAngle_deg", data.get("surfaceIncline_deg", 0.0) or 0.0))
    downskin_deg = data.get("downskinOverhang_deg")
    if downskin_deg is None and incline_deg > 0:
        # Treat surface incline from horizontal as overhang from vertical when only one angle given.
        downskin_deg = max(0.0, 90.0 - incline_deg) if incline_deg <= 90 else incline_deg

    scan_strategy = data.get("scanStrategy", "stripe")
    stripe_width_mm = float(data.get("stripeWidth_mm", 5.0))
    rotation_deg = float(data.get("scanRotation_deg", 67.0))
    dwell_ms = float(data.get("hatchDwell_ms", 0.0))

    thermal = calculate_meltpool_physics(
        thermal_mat,
        power,
        speed,
        beam,
        preheat,
        layer,
        hatch,
        wavelength,
        incline_angle_deg=incline_deg,
        process_seed=process_seed,
        prop_overrides=material_snapshot["thermal"],
    )
    slicer = solve_slicer(
        {
            "preset": data.get("preset", "nozzle"),
            "material": slicer_mat,
            "_materialPropertiesSnapshot": material_snapshot["slicer"],
            "laserPower_W": power,
            "scanSpeed_mms": speed,
            "layerThickness_um": layer,
            "hatchSpacing_um": hatch,
            "recoatTimePerLayer_s": data.get("recoatTimePerLayer_s", 9.0),
            "customTriangles": data.get("customTriangles"),
            "cadAssetName": data.get("cadAssetName", ""),
            "triangleCountNative": data.get("triangleCountNative"),
            "maxTriangles": data.get("maxTriangles"),
        }
    )
    if slicer.get("error"):
        return {"success": False, "error": slicer["error"]}

    decision = compose_verdict(
        thermal,
        alloy_id,
        extras={"downskinOverhang_deg": downskin_deg},
    )

    # --- Faz 3: literature-default Monte Carlo UQ (lazy; default off) ---
    # UQ samples thermal+verdict only — slicer is NOT re-run inside MC.
    uq_block = None
    enable_uq = bool(data.get("enableUq", False))
    uq_n = int(data.get("uqSamples", 96))
    if enable_uq:
        base_props = material_snapshot["thermal"]

        def _thermal_runner(p_w, beam_um, scale_overrides):
            concrete = apply_uq_prop_scales(base_props, scale_overrides)
            return calculate_meltpool_physics(
                thermal_mat,
                p_w,
                speed,
                beam_um,
                preheat,
                layer,
                hatch,
                wavelength,
                incline_angle_deg=incline_deg,
                process_seed=process_seed,
                prop_overrides={**base_props, **concrete},
            )

        def _verdict_runner(th):
            return compose_verdict(th, alloy_id, extras={"downskinOverhang_deg": downskin_deg})

        uq_block = run_screening_uq(
            base_power_W=power,
            base_beam_um=beam,
            thermal_runner=_thermal_runner,
            verdict_fn=_verdict_runner,
            n_samples=uq_n,
            seed=process_seed,
        )
        decision["uq"] = {
            "P_printable": uq_block["P_printable"],
            "normalizedEnthalpy": uq_block["normalizedEnthalpy"],
            "dominantUncertainty": uq_block["dominantUncertainty"],
            "nSamples": uq_block["nSamples"],
        }

    # --- Faz 4a: NIST AM-Bench (lazy; default off) ---
    ambench = None
    if bool(data.get("includeAmbench", False)):

        def _amb_thermal(p_w, v_mms, beam_um, overrides):
            return calculate_meltpool_physics(
                "Inconel 718",
                p_w,
                v_mms,
                beam_um,
                25.0,
                40.0,
                100.0,
                "IR_1064nm",
                incline_angle_deg=0.0,
                process_seed=process_seed,
                prop_overrides=overrides,
            )

        ambench = run_ambench_validation(
            _amb_thermal, material_props=ambench_snapshot["thermal"]
        )
        ambench["alloyCoverage"] = coverage_for_alloy(alloy_id)

    # --- Faz 4b/c: Murakami + qualification template ---
    murakami = evaluate_murakami_block(
        data.get("defectSqrtAreas_um"),
        hardness_HV=data.get("hardness_HV"),
        ct_detection_threshold_um=data.get("ctDetectionThreshold_um"),
        alloy_id=alloy_id,
        defect_paste=data.get("defectSqrtAreasPaste"),
    )
    input_hash = cache_key[:16]
    qualification = build_qualification_block(
        alloy_id,
        input_hash=input_hash,
        git_sha=data.get("gitSha"),
    )

    elapsed = round((time.time() - t0) * 1000.0, 1)
    thermal["computeTimeMs"] = elapsed

    assumptions = [
        "Melt-pool field is regularized Rosenthal (not volumetric Goldak FEA).",
        "LoF gate is Tang (h/W)²+(t/D)² ≤ 1; VED is not the sole criterion.",
        "Keyhole uses King ΔH/hs ≈ 30.",
        "Slicer uses live customTriangles when present; otherwise a demo CAD preset.",
        "No artificial peak-T / PDAS / residual-stress display ceilings; alloy M_molar drives recoil.",
        "Marangoni characteristic length uses the same thermal melt-pool width (geometrySource=thermal).",
        f"Deterministic processSeed={process_seed} for reproducible screening extras.",
        "Request validated with Pydantic; customTriangles capped at maxTriangles (default 12000).",
        "Hash cache keys alloy+P/v/h/t/d+seed+strategy+mesh+UQ/NIST/Murakami flags.",
        "Default job skips UQ and NIST AM-Bench (opt-in via enableUq / includeAmbench).",
    ]
    assumptions.extend(
        _scan_strategy_assumptions(scan_strategy, stripe_width_mm, rotation_deg, dwell_ms)
    )
    if thermal.get("processParameters", {}).get("effectiveConductivity_W_mK") is not None:
        assumptions.append(
            "Effective k/Cp blend solid↔liquid for Rosenthal geometry; King ΔH/hs stays on solid thermophysics."
        )
    if abs(incline_deg) > 1e-6:
        assumptions.append(
            f"Solidification rate R = v·cos(θ) with surface incline θ={incline_deg:.1f}°."
        )
    if uq_block:
        assumptions.append(
            f"UQ: literature-default MC n={uq_block['nSamples']} "
            f"(P±{uq_block['bands']['power_rel']*100:.0f}%, A±{uq_block['bands']['absorptivity_rel']*100:.0f}%); "
            "Spearman sensitivity proxy; slicer not re-run in MC. Not machine-calibrated."
        )
    if ambench:
        assumptions.append(
            "NIST AMB2018-02 IN625 CBM Table 4 attached for screening MAPE "
            f"(doi:{ambench['source']['doi']}); four-alloy direct coverage is limited."
        )
    assumptions.append(
        "Murakami/qualification blocks are SCREENING ONLY; defect √area not invented when absent."
    )

    result = {
        "success": True,
        "engine": "lpbf_build_job",
        "modelId": BUILD_JOB_MODEL_ID,
        "solverRevision": BUILD_JOB_SOLVER_REVISION,
        "buildJobIdentity": build_job_identity,
        "assumptions": assumptions,
        "alloyId": alloy_id,
        "materialPropertySchemaVersion": material_snapshot["schemaVersion"],
        "materialPropertyRevision": MATERIAL_PROPERTY_REVISION,
        "materialPropertySha256": material_property_sha256,
        "materialPropertySnapshot": material_snapshot,
        "materialAuthority": material_authority_snapshot["authority"],
        "materialAuthorityRevisionSha256": material_authority_revision_sha256,
        "amBenchMaterialPropertySha256": ambench_property_sha256,
        "amBenchMaterialPropertySnapshot": ambench_snapshot,
        "processSeed": process_seed,
        "scanStrategy": {
            "id": scan_strategy,
            "stripeWidth_mm": stripe_width_mm,
            "rotation_deg": rotation_deg,
            "hatchDwell_ms": dwell_ms,
        },
        "computeTimeMs": elapsed,
        "thermal": thermal,
        "slicer": slicer,
        "kinematics": calculate_scanner_kinematics(speed, max(50.0, float(stripe_width_mm * 1000.0))),
        "microstructure": compute_solidification_microstructure(data, data.get("material", {}), None),
        "kinetics": solve_phase_transformation_kinetics(
            alloy_name={"in718": "Inconel 718", "ti6al4v": "Ti-6Al-4V"}.get(alloy_id, "AISI 4140"),
            cooling_rate_c_s=thermal.get("solidificationKinetics", {}).get("coolingRate_K_s", 1e5)
        ),
        "porosity": aggregate_part_porosity(
            uq_block.pop("defectSamples", []) if uq_block else [thermal.get("geometricDefectScreen", {})]
        ),
        "verdict": decision,
        "uq": uq_block,
        "ambench": ambench,
        "murakami": murakami,
        "qualification": qualification,
    }
    return cache_put(cache_key, result)


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "Empty payload provided to LPBF build-job solver."}))
        sys.exit(1)
    try:
        data = json.loads(raw)
    except Exception as e:
        print(json.dumps({"error": f"Invalid JSON input: {str(e)}"}))
        sys.exit(1)
    result = solve_lpbf_build_job(data)
    if not result.get("success"):
        print(json.dumps(result))
        sys.exit(1)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
