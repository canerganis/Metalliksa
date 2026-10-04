#!/usr/bin/env python3
"""Build-job verdict must come from Python, not a second TypeScript decision.

Fast suite (default): Phase 0–2 + lazy defaults + cache + Murakami paste.
Slow suite (--slow): UQ Monte Carlo + NIST AM-Bench (opt-in path).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOLVER = os.path.join(HERE, "lpbf_build_job_solver.py")
SLOW = "--slow" in sys.argv


def run_job(payload, *, clear_cache=False):
    body = {"enableUq": False, "includeAmbench": False, **payload}
    if clear_cache:
        from lpbf_job_cache import clear_cache as _clear

        _clear()
    # Prefer in-process for cache tests; subprocess for isolation of CLI path.
    if payload.get("_subprocess"):
        body.pop("_subprocess", None)
        proc = subprocess.run(
            [sys.executable, SOLVER],
            input=json.dumps(body),
            capture_output=True,
            text=True,
            cwd=HERE,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr or proc.stdout)
        return json.loads(proc.stdout)

    from lpbf_build_job_solver import solve_lpbf_build_job

    return solve_lpbf_build_job(body)


KINETICS_FIXTURE = os.path.join(HERE, "..", "tests", "fixtures", "build-job-kinetics-blocks.json")
# Real build_job_kinetics output for the UI render test (tests/build-job-kinetics-panel.test.tsx).
# Rates: the four demo builds' reported rates, the degenerate 1 K/s floor, and an in-map 30 C/s.
# The TTT curves, LSW profile and timing are left out (the panel does not read them).
KINETICS_FIXTURE_CASES = (
    ("ss316l_no_model", "ss316l", 1205584.0),
    ("alsi10mg_no_model", "alsi10mg", 2603566.0),
    ("in718_above_map", "in718", 877254.0),
    ("ti6al4v_above_map", "ti6al4v", 1089047.0),
    ("in718_degenerate_floor", "in718", 1.0),
    ("ti6al4v_in_map_30", "ti6al4v", 30.0),
    ("in718_in_map_30", "in718", 30.0),
)
_KINETICS_FIXTURE_DROP = ("tttIsothermalCurves", "lswPrecipitateCoarsening", "computeTimeMs")


def kinetics_fixture_blocks():
    from lpbf_build_job_solver import build_job_kinetics

    out = {}
    for name, alloy_id, rate in KINETICS_FIXTURE_CASES:
        block = build_job_kinetics(alloy_id, {"solidificationKinetics": {"coolingRate_K_s": rate}})
        out[name] = {k: v for k, v in block.items() if k not in _KINETICS_FIXTURE_DROP}
    return out


def check_kinetics_fixture():
    """The committed UI fixture must equal the current Python output (no hand-made blocks)."""
    with open(KINETICS_FIXTURE, encoding="utf-8") as fh:
        committed = json.load(fh)
    current = json.loads(json.dumps(kinetics_fixture_blocks()))
    assert committed == current, "tests/fixtures/build-job-kinetics-blocks.json is stale: rerun with --write-kinetics-fixture"


def check_build_job_kinetics(ti):
    import math

    from kinetics_ttt_cct_solver import solve_phase_transformation_kinetics
    from lpbf_build_job_solver import (
        BUILD_JOB_KINETICS_ALLOY,
        DEGENERATE_FRONT_REASON,
        build_cooling_rate_cct_row,
        build_job_kinetics,
        build_rate_martensite,
    )

    assert BUILD_JOB_KINETICS_ALLOY == {"in718": "Inconel 718", "ti6al4v": "Ti-6Al-4V"}
    kin = ti["kinetics"]
    rate = ti["thermal"]["solidificationKinetics"]["coolingRate_K_s"]
    assert kin["status"] == "available" and kin["success"] is True
    assert kin["alloy"] == "Ti-6Al-4V" and kin["alloyId"] == "ti6al4v"
    assert kin["buildCoolingRate_C_s"] == float(rate) == kin["reportedCoolingRate_K_s"]
    assert kin["inputParameters"]["selectedCoolingRate_C_s"] == float(rate)
    assert kin["coolingRateSource"] == "thermal.solidificationKinetics.coolingRate_K_s"
    # The solver output itself is unchanged; only build-job metadata keys are added.
    reference = solve_phase_transformation_kinetics(alloy_name="Ti-6Al-4V", cooling_rate_c_s=float(rate))
    added = {"status", "alloyId", "buildCoolingRate_C_s", "reportedCoolingRate_K_s", "coolingRateSource",
             "buildCoolingRateCctRow", "buildRateMartensite"}
    assert set(kin) == set(reference) | added
    for key in set(reference) - {"computeTimeMs"}:
        assert kin[key] == reference[key], key
    # This non-degenerate build rate (~1e6 K/s) is above the 0.05-2000 °C/s CCT map: no row is
    # extrapolated, and the steel-type martensite fraction / verdict are withheld with it.
    sel = kin["buildCoolingRateCctRow"]
    assert rate > 2000.0, rate
    assert sel["status"] == "unavailable" and sel["rowIndex"] is None and sel["rowCoolingRate_C_s"] is None
    assert sel["mapRange_C_s"] == [0.05, 2000.0]
    assert sel["reason"] == (f"build cooling rate {int(rate)} °C/s is above the CCT map maximum 2000 °C/s; "
                             "no row is extrapolated"), sel["reason"]
    mart = kin["buildRateMartensite"]
    assert mart["status"] == "unavailable" and mart["predictedMartensite_pct"] is None and mart["verdict"] is None
    assert mart["reason"].startswith(sel["reason"] + "; the steel-type martensite fraction and verdict")

    cct = kin["cctContinuousCoolingMap"]
    inside = build_cooling_rate_cct_row(cct, 30.0)  # log10 nearest: 25 (|0.079|) beats 50 (|0.222|)
    assert inside["status"] == "selected" and inside["rowCoolingRate_C_s"] == 25.0
    assert cct[inside["rowIndex"]]["coolingRate_C_s"] == 25.0 and inside["reason"] is None
    assert build_cooling_rate_cct_row(cct, 0.3)["rowCoolingRate_C_s"] == 0.2
    assert build_cooling_rate_cct_row(cct, 72.0)["rowCoolingRate_C_s"] == 100.0  # log scale; linear-nearest is 50
    assert build_cooling_rate_cct_row(cct, 2000.0)["rowCoolingRate_C_s"] == 2000.0
    assert build_cooling_rate_cct_row(cct, 0.05)["rowCoolingRate_C_s"] == 0.05
    # Exact log-midpoint tie: the first row in map order (the slower rate) wins.
    tie_map = [{"coolingRate_C_s": 1.0}, {"coolingRate_C_s": 100.0}]
    assert build_cooling_rate_cct_row(tie_map, 10.0)["rowCoolingRate_C_s"] == 1.0
    # The range reason states the exact comparison, never a rounded one.
    just_above = build_cooling_rate_cct_row(cct, 2000.0000001)
    assert just_above["status"] == "unavailable"
    assert just_above["reason"] == ("build cooling rate 2000.0000001 °C/s is above the CCT map maximum "
                                    "2000 °C/s; no row is extrapolated"), just_above["reason"]
    below = build_cooling_rate_cct_row(cct, 0.01)
    assert below["status"] == "unavailable" and "below the CCT map minimum 0.05 °C/s" in below["reason"]
    for bad in (None, float("nan"), float("inf"), float("-inf"), -1.0, 0.0, True, False, "30"):
        out = build_cooling_rate_cct_row(cct, bad)
        assert out["status"] == "unavailable" and out["rowIndex"] is None, (bad, out)
    for bad_map in (None, [], [None, "x", {"coolingRate_C_s": float("nan")}, {"coolingRate_C_s": True}]):
        assert build_cooling_rate_cct_row(bad_map, 30.0)["status"] == "unavailable", bad_map
    assert build_cooling_rate_cct_row([None, {"coolingRate_C_s": 25.0}], 25.0)["rowIndex"] == 1

    # No finite cooling rate: unavailable, never the former 1e5 K/s default.
    for thermal in ({}, {"solidificationKinetics": {}},
                    {"solidificationKinetics": {"coolingRate_K_s": float("nan")}},
                    {"solidificationKinetics": {"coolingRate_K_s": float("inf")}},
                    {"solidificationKinetics": {"coolingRate_K_s": True}},
                    {"solidificationKinetics": {"coolingRate_K_s": "1e5"}}):
        missing = build_job_kinetics("in718", thermal)
        assert missing["status"] == "unavailable" and missing["calphadVsKineticsGap"] is None
        assert missing["reason"] == "the build thermal result reports no finite cooling rate", missing
        assert missing["buildCoolingRate_C_s"] is None and missing["reportedCoolingRate_K_s"] is None
    # At or below the 1 K/s floor of a degenerate solidification front (solidification_front.py):
    # not a build rate, whatever produced it.
    for floor_rate in (1.0, 1, 0.5, 0.0, -3.0):
        floor = build_job_kinetics("ti6al4v", {"solidificationKinetics": {"coolingRate_K_s": floor_rate}})
        assert floor["status"] == "unavailable" and floor["reason"] == DEGENERATE_FRONT_REASON, floor
        assert floor["buildCoolingRate_C_s"] is None and floor["reportedCoolingRate_K_s"] == float(floor_rate)
        assert floor["cctContinuousCoolingMap"] is None and floor["buildRateMartensite"] is None
    assert build_job_kinetics("ti6al4v", {"solidificationKinetics": {"coolingRate_K_s": 1.0000001}})["status"] == "available"

    # In-map rate (synthetic; real builds report ~1e5-1e6 K/s): IN718 row selected, but its registry
    # Ms is a non-physical placeholder, so no martensite fraction or verdict.
    good = build_job_kinetics("in718", {"solidificationKinetics": {"coolingRate_K_s": 30.0}})
    assert good["alloy"] == "Inconel 718" and good["buildCoolingRateCctRow"]["rowCoolingRate_C_s"] == 25.0
    assert math.isclose(good["calphadVsKineticsGap"]["kineticRealityAtSelectedCooling"]["coolingRate_C_s"], 30.0)
    assert good["buildRateMartensite"]["status"] == "unavailable"
    assert "non-physical placeholder" in good["buildRateMartensite"]["reason"]
    assert good["buildRateMartensite"]["predictedMartensite_pct"] is None
    # Ti-6Al-4V Ms is not flagged: with a selected row the fraction and verdict are reported.
    ti_in = build_job_kinetics("ti6al4v", {"solidificationKinetics": {"coolingRate_K_s": 30.0}})
    m = ti_in["buildRateMartensite"]
    reality = ti_in["calphadVsKineticsGap"]["kineticRealityAtSelectedCooling"]
    assert m["status"] == "available" and m["reason"] is None
    assert m["predictedMartensite_pct"] == reality["predictedMartensite_pct"] and m["verdict"] == reality["verdict"]
    nonfinite_gap = {"kineticRealityAtSelectedCooling": {"predictedMartensite_pct": None, "verdict": "x"}}
    assert build_rate_martensite("ti6al4v", "Ti-6Al-4V", nonfinite_gap, {"status": "selected"})["status"] == "unavailable"

    # Real degenerate-front build (B1 regression): IN718 150 W / 1500 mm/s reports the 1 K/s floor.
    fast = run_job({"alloyId": "in718", "laserPower_W": 150, "scanSpeed_mm_s": 1500, "beamDiameter_um": 80,
                    "layerThickness_um": 30, "hatchSpacing_um": 100, "bypassCache": True})
    assert fast["thermal"]["solidificationKinetics"]["coolingRate_K_s"] == 1.0
    assert fast["kinetics"]["status"] == "unavailable" and fast["kinetics"]["reason"] == DEGENERATE_FRONT_REASON
    assert fast["kinetics"]["buildCoolingRateCctRow"] is None
    # A non-degenerate IN718 build stays available with the rate out of the map range.
    slow = run_job({"alloyId": "in718", "laserPower_W": 220, "scanSpeed_mm_s": 900, "beamDiameter_um": 80,
                    "layerThickness_um": 30, "hatchSpacing_um": 100, "bypassCache": True})
    assert slow["thermal"]["solidificationKinetics"]["coolingRate_K_s"] > 2000.0
    assert slow["kinetics"]["status"] == "available"
    assert slow["kinetics"]["buildCoolingRateCctRow"]["status"] == "unavailable"
    assert "non-physical placeholder" in slow["kinetics"]["buildRateMartensite"]["reason"]

    for alloy_id, name, power, speed in (("ss316l", "316L Stainless Steel", 200, 800),
                                         ("alsi10mg", "AlSi10Mg", 330, 1100)):
        job = run_job({"alloyId": alloy_id, "laserPower_W": power, "scanSpeed_mm_s": speed,
                       "beamDiameter_um": 80, "layerThickness_um": 30, "hatchSpacing_um": 100,
                       "bypassCache": True})
        assert job["success"]
        k = job["kinetics"]
        reported = float(job["thermal"]["solidificationKinetics"]["coolingRate_K_s"])
        assert k == {
            "success": False,
            "status": "unavailable",
            "reason": f"no kinetics model for {name}",
            "alloyId": alloy_id,
            "alloy": None,
            "buildCoolingRate_C_s": None if reported <= 1.0 else reported,
            "reportedCoolingRate_K_s": reported,
            "coolingRateSource": "thermal.solidificationKinetics.coolingRate_K_s",
            "cctContinuousCoolingMap": None,
            "calphadVsKineticsGap": None,
            "buildCoolingRateCctRow": None,
            "buildRateMartensite": None,
        }, k
        assert "AISI 4140" not in json.dumps(k) and "7075" not in json.dumps(k)


def check_build_job_microstructure(job):
    """Build-job microstructure is a projection of thermal.solidificationKinetics (no second G/R)."""
    micro = job["microstructure"]
    kin = job["thermal"]["solidificationKinetics"]
    assert micro["status"] == "available"
    assert micro["source"] == "thermal.solidificationKinetics"
    assert micro["G_K_m"] == kin["thermalGradient_G_K_m"]
    assert micro["R_m_s"] == kin["solidificationRate_R_m_s"]
    assert micro["coolingRate_K_s"] == kin["coolingRate_K_s"]
    assert micro["PDAS_um"] == kin["primaryDendriteArmSpacing_PDAS_um"]
    assert micro["SDAS_um"] == kin["secondaryDendriteArmSpacing_SDAS_um"]
    assert micro["morphology"] == kin["microstructureMorphology"]
    assert micro["modelId"] == kin["modelId"]
    assert micro["gradientSource"] == kin["gradientSource"]
    assert micro["usedFieldMap"] == kin["usedFieldMap"]
    assert micro["g_over_r_ratio"] == kin["g_over_r_ratio"]
    assert micro["doi"] == kin["doi"]
    assert micro["disclaimer"].startswith(kin["disclaimer"])
    assert "no second estimate" in micro["disclaimer"]
    # The removed Rosenthal default-constant block (G floor 1e4 K/m) must not reappear.
    assert micro["G_K_m"] > 1.0e5, micro["G_K_m"]

    from lpbf_solidification_microstructure import project_build_job_microstructure

    for bad in ({}, {"solidificationKinetics": None}, {"solidificationKinetics": {}},
                {"solidificationKinetics": {**kin, "thermalGradient_G_K_m": float("nan")}},
                {"solidificationKinetics": {**kin, "solidificationRate_R_m_s": None}}):
        unavailable = project_build_job_microstructure(bad)
        assert unavailable["status"] == "unavailable"
        assert unavailable["reason"] == "thermal.solidificationKinetics missing or non-finite"
        for key in ("G_K_m", "R_m_s", "coolingRate_K_s", "PDAS_um", "SDAS_um", "morphology"):
            assert unavailable[key] is None, key


def main():
    from lpbf_job_cache import clear_cache
    from murakami_fatigue_screening import parse_defect_sqrt_areas_text

    clear_cache()

    # Paste parser
    assert parse_defect_sqrt_areas_text("40, 55; 62\n48 70") == [40.0, 55.0, 62.0, 48.0, 70.0]
    assert parse_defect_sqrt_areas_text("") == []

    ti = run_job(
        {
            "alloyId": "ti6al4v",
            "laserPower_W": 200,
            "scanSpeed_mm_s": 900,
            "beamDiameter_um": 80,
            "preheatTemp_C": 150,
            "layerThickness_um": 30,
            "hatchSpacing_um": 100,
            "preset": "nozzle",
            "processSeed": 42,
            "scanStrategy": "stripe",
            "stripeWidth_mm": 5,
            "scanRotation_deg": 67,
            "hatchDwell_ms": 0,
            "bypassCache": True,
        }
    )
    assert ti["success"]
    assert ti["engine"] == "lpbf_build_job"
    assert ti["modelId"] == "rosenthal-screening-v1"
    from lpbf_job_cache import BUILD_JOB_SOLVER_REVISION
    assert ti["solverRevision"] == BUILD_JOB_SOLVER_REVISION
    assert ti["processSeed"] == 42
    assert ti["scanStrategy"]["id"] == "stripe"
    assert ti["uq"] is None  # lazy default
    assert ti["ambench"] is None  # lazy default
    assert ti["cache"]["hit"] is False
    assert any("Hash cache" in a for a in ti["assumptions"])
    assert any("skips UQ" in a or "Default job skips" in a for a in ti["assumptions"])
    assert ti["murakami"]["status"] == "data_not_supplied"
    assert "pasteHint" in ti["murakami"]
    assert len(ti["assumptions"]) >= 6
    assert any("Goldak" in a for a in ti["assumptions"])
    assert any("King" in a for a in ti["assumptions"])
    assert any("Tang" in a for a in ti["assumptions"])
    assert any("10.1115/1.4031649" in a for a in ti["assumptions"])
    assert "verdict" in ti["verdict"]
    assert ti["verdict"]["verdict"] in ("printable", "risky", "do-not-print")
    assert ti["thermal"]["meltPoolGeometry"]["width_um"] > 0
    assert ti["materialPropertySchemaVersion"] == 1
    assert ti["materialPropertyRevision"] == ti["buildJobIdentity"]["materialPropertyRevision"]
    assert len(ti["materialPropertySha256"]) == 64
    assert ti["materialPropertySnapshot"]["alloyId"] == "ti6al4v"
    from lpbf_build_job_material_snapshot import build_build_job_identity

    assert ti["buildJobIdentity"] == {
        "schemaVersion": 1,
        "alloyId": "ti6al4v",
        "modelId": ti["modelId"],
        "solverRevision": ti["solverRevision"],
        "materialPropertySchemaVersion": ti["materialPropertySchemaVersion"],
        "materialPropertyRevision": "build-job-effective-properties-v1",
        "materialPropertySha256": ti["materialPropertySha256"],
        "sha256": build_build_job_identity(
            "Ti-6Al-4V", ti["modelId"], ti["solverRevision"],
            ti["materialPropertySha256"], ti["materialPropertySchemaVersion"],
        )["sha256"],
    }
    assert len(ti["buildJobIdentity"]["sha256"]) == 64
    assert "gates" in ti["verdict"] and len(ti["verdict"]["gates"]) >= 7

    # Kinetics: only the alloy's own kinetics model, never a substituted alloy (formerly every
    # alloy other than IN718/Ti-6Al-4V silently got AISI 4140 kinetics).
    check_build_job_kinetics(ti)
    check_kinetics_fixture()

    # Same-alloy aliases are accepted but normalized before solver invocation.
    from unittest.mock import patch
    import lpbf_build_job_solver as build_job_solver

    received_materials = {}
    calculate_thermal = build_job_solver.calculate_meltpool_physics
    solve_material_slicer = build_job_solver.solve_slicer

    def capture_thermal_name(name, *args, **kwargs):
        received_materials["thermal"] = name
        return calculate_thermal(name, *args, **kwargs)

    def capture_slicer_name(payload):
        received_materials["slicer"] = payload["material"]
        return solve_material_slicer(payload)

    with patch.object(build_job_solver, "calculate_meltpool_physics", capture_thermal_name), patch.object(
        build_job_solver, "solve_slicer", capture_slicer_name
    ):
        aliased_ti = run_job(
            {
                "alloyId": "ti-6al-4v",
                "thermalMaterial": "Ti-6Al-4V ELI",
                "slicerMaterial": "Ti-6Al-4V",
                "laserPower_W": 200,
                "scanSpeed_mm_s": 900,
                "beamDiameter_um": 80,
                "preheatTemp_C": 150,
                "layerThickness_um": 30,
                "hatchSpacing_um": 100,
                "bypassCache": True,
            }
        )
    assert aliased_ti["success"]
    assert received_materials == {"thermal": "Ti-6Al-4V", "slicer": "Ti-6Al-4V ELI"}
    assert aliased_ti["materialPropertySha256"] == ti["materialPropertySha256"]
    assert aliased_ti["buildJobIdentity"] == ti["buildJobIdentity"]

    # Hash cache hit on identical request
    clear_cache()
    a = run_job(
        {
            "alloyId": "in718",
            "laserPower_W": 285,
            "scanSpeed_mm_s": 960,
            "beamDiameter_um": 80,
            "layerThickness_um": 40,
            "hatchSpacing_um": 110,
        }
    )
    b = run_job(
        {
            "alloyId": "in718",
            "laserPower_W": 285,
            "scanSpeed_mm_s": 960,
            "beamDiameter_um": 80,
            "layerThickness_um": 40,
            "hatchSpacing_um": 110,
        }
    )
    assert a["cache"]["hit"] is False
    assert b["cache"]["hit"] is True
    assert b["verdict"]["verdict"] == a["verdict"]["verdict"]
    assert b["cache"]["stats"]["hits"] >= 1
    assert b["materialPropertySha256"] == a["materialPropertySha256"]
    check_build_job_microstructure(a)

    # The effective thermal input is frozen once per request and changes cache identity.
    from four_alloy_materials import _THERMAL

    old_conductivity = _THERMAL["in718"]["thermal_conductivity_W_mK"]
    try:
        _THERMAL["in718"]["thermal_conductivity_W_mK"] = old_conductivity + 1.0
        changed = run_job({"alloyId": "in718", "laserPower_W": 285,
                           "scanSpeed_mm_s": 960, "beamDiameter_um": 80,
                           "layerThickness_um": 40, "hatchSpacing_um": 110})
        assert changed["cache"]["hit"] is False
        assert changed["materialPropertySha256"] != a["materialPropertySha256"]
        assert changed["buildJobIdentity"]["sha256"] != a["buildJobIdentity"]["sha256"]
        assert changed["materialPropertySnapshot"]["thermal"]["thermal_conductivity_W_mK"] == old_conductivity + 1.0
        assert changed["thermal"]["processParameters"]["effectiveConductivity_W_mK"] != a["thermal"]["processParameters"]["effectiveConductivity_W_mK"]
    finally:
        _THERMAL["in718"]["thermal_conductivity_W_mK"] = old_conductivity

    # Source-only fields are part of the shared authority revision even when the
    # build-job effective-property projection does not consume them.
    old_surface_tension = _THERMAL["in718"]["surface_tension_N_m"]
    try:
        _THERMAL["in718"]["surface_tension_N_m"] = old_surface_tension + 0.01
        source_changed = run_job({"alloyId": "in718", "laserPower_W": 285,
                                  "scanSpeed_mm_s": 960, "beamDiameter_um": 80,
                                  "layerThickness_um": 40, "hatchSpacing_um": 110})
        assert source_changed["cache"]["hit"] is False
        assert source_changed["materialPropertySha256"] == a["materialPropertySha256"]
        assert source_changed["materialAuthorityRevisionSha256"] != a["materialAuthorityRevisionSha256"]
    finally:
        _THERMAL["in718"]["surface_tension_N_m"] = old_surface_tension

    # A legacy or corrupted hit cannot bypass the current snapshot contract.
    with patch.object(build_job_solver, "cache_get", return_value={
        "success": True, "alloyId": "in718", "computeTimeMs": 1,
    }):
        stale = run_job({"alloyId": "in718", "laserPower_W": 285,
                         "scanSpeed_mm_s": 960, "beamDiameter_um": 80,
                         "layerThickness_um": 40, "hatchSpacing_um": 110})
    assert stale["cache"]["hit"] is False
    assert stale["materialPropertySha256"] == a["materialPropertySha256"]

    with patch.object(build_job_solver, "cache_get", return_value={
        **a, "solverRevision": "older-build-job-implementation",
    }):
        revision_stale = run_job({"alloyId": "in718", "laserPower_W": 285,
                                  "scanSpeed_mm_s": 960, "beamDiameter_um": 80,
                                  "layerThickness_um": 40, "hatchSpacing_um": 110})
    assert revision_stale["cache"]["hit"] is False
    assert revision_stale["solverRevision"] == BUILD_JOB_SOLVER_REVISION

    import lpbf_job_cache
    from lpbf_job_cache import build_cache_key, mesh_fingerprint

    mesh_a = [[[-1, 0, 0], [1, 0, 0], [0, 1, 1]]] * 9
    mesh_b = [list(tri) for tri in mesh_a]
    mesh_b[1] = [[-1, 0, 0], [1, 0, 0], [0, 2, 1]]
    assert mesh_fingerprint(mesh_a) != mesh_fingerprint(mesh_b)
    assert build_cache_key({"customTriangles": mesh_a}) != build_cache_key({"customTriangles": mesh_b})
    assert build_cache_key({"recoatTimePerLayer_s": 9.0}) != build_cache_key({"recoatTimePerLayer_s": 12.0})
    revision_key = build_cache_key({"solverRevision": "untrusted-client-value"})
    assert revision_key == build_cache_key({})
    with patch.object(lpbf_job_cache, "BUILD_JOB_SOLVER_REVISION", "next-implementation"):
        assert build_cache_key({}) != revision_key

    base_identity = a["buildJobIdentity"]
    identity_inputs = (
        base_identity["alloyId"], base_identity["modelId"], base_identity["solverRevision"],
        base_identity["materialPropertySha256"], base_identity["materialPropertySchemaVersion"],
    )
    model_identity = build_build_job_identity(
        identity_inputs[0], "next-model", *identity_inputs[2:]
    )
    solver_identity = build_build_job_identity(
        identity_inputs[0], identity_inputs[1], "next-solver", *identity_inputs[3:]
    )
    snapshot_schema_identity = build_build_job_identity(
        *identity_inputs[:4], identity_inputs[4] + 1
    )
    snapshot_revision_identity = build_build_job_identity(
        *identity_inputs[:4], identity_inputs[4], "build-job-effective-properties-v2"
    )
    assert model_identity["materialPropertySha256"] == base_identity["materialPropertySha256"]
    assert solver_identity["materialPropertySha256"] == base_identity["materialPropertySha256"]
    assert len({
        base_identity["sha256"], model_identity["sha256"], solver_identity["sha256"],
        snapshot_schema_identity["sha256"], snapshot_revision_identity["sha256"],
    }) == 5
    keyed = {"buildJobIdentity": base_identity}
    base_identity_key = build_cache_key(keyed)
    for variant in (model_identity, solver_identity, snapshot_schema_identity, snapshot_revision_identity):
        assert build_cache_key({"buildJobIdentity": variant}) != base_identity_key

    # UQ must carry the whole frozen base, even when a sample changes only one
    # property and the live registry changes after the base solve.
    observed_uq_properties = {}

    def inspect_uq_thermal(*, thermal_runner, n_samples, **_kwargs):
        original_cp = _THERMAL["in718"]["specific_heat_J_kgK"]
        try:
            _THERMAL["in718"]["specific_heat_J_kgK"] = original_cp + 100.0

            def capture_uq_thermal(_name, *args, **kwargs):
                observed_uq_properties.update(kwargs["prop_overrides"])
                return a["thermal"]

            with patch.object(build_job_solver, "calculate_meltpool_physics", capture_uq_thermal):
                thermal_runner(285.0, 80.0, {"_uq_k_scale": 1.1})
        finally:
            _THERMAL["in718"]["specific_heat_J_kgK"] = original_cp
        return {
            "P_printable": 0.5, "normalizedEnthalpy": {},
            "dominantUncertainty": "k", "nSamples": n_samples,
            "bands": {"power_rel": 0.03, "absorptivity_rel": 0.15},
            "defectSamples": [],
        }

    with patch.object(build_job_solver, "run_screening_uq", side_effect=inspect_uq_thermal):
        uq_snapshot = run_job({"alloyId": "in718", "enableUq": True, "uqSamples": 8,
                               "bypassCache": True})
    assert uq_snapshot["success"] is True
    assert observed_uq_properties["specific_heat_J_kgK"] == a["materialPropertySnapshot"]["thermal"]["specific_heat_J_kgK"]
    assert observed_uq_properties["thermal_conductivity_W_mK"] == 1.1 * a["materialPropertySnapshot"]["thermal"]["thermal_conductivity_W_mK"]
    assert set(a["materialPropertySnapshot"]["thermal"]).issubset(observed_uq_properties)

    # AM-Bench uses an independent IN625 comparison snapshot, frozen across
    # all cases, and only its own digest changes when those props change.
    from nist_ambench_2018_02 import IN625_VALIDATION_PROPS, run_ambench_validation
    from lpbf_build_job_material_snapshot import build_ambench_material_property_snapshot

    comparison_snapshot, comparison_sha = build_ambench_material_property_snapshot(IN625_VALIDATION_PROPS)
    comparison_calls = []

    def capture_comparison(_power, _speed, _beam, props):
        comparison_calls.append(props)
        return {"meltPoolGeometry": {"length_um": 659.0, "width_um": 171.0, "depth_um": 151.0}}

    run_ambench_validation(capture_comparison, material_props=comparison_snapshot["thermal"])
    assert len(comparison_calls) == 3
    assert all(props == comparison_snapshot["thermal"] for props in comparison_calls)

    def stub_ambench(_thermal_runner, material_props=None):
        assert material_props["base"] == "Ni"
        return {"source": {"doi": "10.1007/s40192-020-00169-1"}, "cases": []}

    comparison_input = {"alloyId": "Ti-6Al-4V", "includeAmbench": True}
    clear_cache()
    with patch.object(build_job_solver, "run_ambench_validation", side_effect=stub_ambench):
        compared = run_job(comparison_input)
        compared_alias = run_job({**comparison_input, "alloyId": "ti6al4v"})
        original_k = IN625_VALIDATION_PROPS["thermal_conductivity_W_mK"]
        try:
            IN625_VALIDATION_PROPS["thermal_conductivity_W_mK"] = original_k + 1.0
            compared_changed = run_job(comparison_input)
        finally:
            IN625_VALIDATION_PROPS["thermal_conductivity_W_mK"] = original_k
    assert compared["cache"]["hit"] is False and compared_alias["cache"]["hit"] is True
    assert compared["amBenchMaterialPropertySha256"] == comparison_sha
    assert compared_alias["amBenchMaterialPropertySha256"] == comparison_sha
    assert compared["amBenchMaterialPropertySnapshot"] == comparison_snapshot
    assert compared_changed["cache"]["hit"] is False
    assert compared_changed["materialPropertySha256"] == compared["materialPropertySha256"]
    assert compared_changed["amBenchMaterialPropertySha256"] != comparison_sha

    # Murakami paste path + alloy HV default
    mur = run_job(
        {
            "alloyId": "in718",
            "laserPower_W": 285,
            "scanSpeed_mm_s": 960,
            "beamDiameter_um": 80,
            "layerThickness_um": 40,
            "hatchSpacing_um": 110,
            "defectSqrtAreasPaste": "40, 55, 62, 48, 70",
            "bypassCache": True,
        }
    )
    assert mur["murakami"]["status"] == "screening_estimate"
    assert mur["murakami"]["hardnessSource"] == "alloy_default"
    assert mur["murakami"]["hardness_HV"] == 380.0
    assert mur["murakami"]["fatigueLimit_internal_MPa"] > 0

    # R = v·cosθ
    flat = run_job(
        {
            "alloyId": "ti6al4v",
            "laserPower_W": 200,
            "scanSpeed_mm_s": 900,
            "beamDiameter_um": 80,
            "preheatTemp_C": 150,
            "layerThickness_um": 30,
            "hatchSpacing_um": 100,
            "inclineAngle_deg": 0,
            "bypassCache": True,
        }
    )
    inclined = run_job(
        {
            "alloyId": "ti6al4v",
            "laserPower_W": 200,
            "scanSpeed_mm_s": 900,
            "beamDiameter_um": 80,
            "preheatTemp_C": 150,
            "layerThickness_um": 30,
            "hatchSpacing_um": 100,
            "inclineAngle_deg": 60,
            "bypassCache": True,
        }
    )
    r0 = flat["thermal"]["solidificationKinetics"]["solidificationRate_R_m_s"]
    r60 = inclined["thermal"]["solidificationKinetics"]["solidificationRate_R_m_s"]
    assert r60 < r0 * 0.6, (r0, r60)

    bloated = [[[0, 0, 0], [1, 0, 0], [0, 1, 0]]] * 15000
    capped = run_job(
        {
            "alloyId": "in718",
            "laserPower_W": 285,
            "scanSpeed_mm_s": 960,
            "beamDiameter_um": 80,
            "layerThickness_um": 40,
            "hatchSpacing_um": 110,
            "customTriangles": bloated,
            "triangleCountNative": 15000,
            "maxTriangles": 12000,
            "preset": "custom",
            "bypassCache": True,
        }
    )
    assert capped["success"]
    assert capped["slicer"]["meshMetrics"]["triangleCount"] <= 12000

    lof = run_job(
        {
            "alloyId": "in718",
            "laserPower_W": 90,
            "scanSpeed_mm_s": 1400,
            "beamDiameter_um": 80,
            "preheatTemp_C": 80,
            "layerThickness_um": 40,
            "hatchSpacing_um": 110,
            "preset": "nozzle",
            "bypassCache": True,
        }
    )
    assert lof["verdict"]["verdict"] in ("risky", "do-not-print"), lof["verdict"]
    assert lof["verdict"]["suggestedPatch"] is not None

    kh = run_job(
        {
            "alloyId": "ti6al4v",
            "laserPower_W": 400,
            "scanSpeed_mm_s": 400,
            "beamDiameter_um": 80,
            "preheatTemp_C": 80,
            "layerThickness_um": 30,
            "hatchSpacing_um": 100,
            "preset": "nozzle",
            "bypassCache": True,
        }
    )
    assert kh["verdict"]["dominantGate"] == "keyhole", kh["verdict"]

    ds = run_job(
        {
            "alloyId": "ti6al4v",
            "laserPower_W": 200,
            "scanSpeed_mm_s": 900,
            "beamDiameter_um": 80,
            "preheatTemp_C": 150,
            "layerThickness_um": 30,
            "hatchSpacing_um": 100,
            "downskinOverhang_deg": 60,
            "bypassCache": True,
        }
    )
    assert ds["verdict"]["dominantGate"] == "downskin" or any(
        g["id"] == "downskin" and g["status"] == "fail" for g in ds["verdict"]["gates"]
    ), ds["verdict"]

    unsupported = run_job({"alloyId": "Inconel 625", "bypassCache": True})
    assert unsupported["success"] is False
    assert "Unsupported LPBF alloy identity" in unsupported["error"]
    assert "No surrogate alloy" in unsupported["error"]

    thermal_mismatch = run_job(
        {"alloyId": "ss316l", "thermalMaterial": "Inconel 718", "bypassCache": True}
    )
    assert thermal_mismatch["success"] is False
    assert "thermalMaterial" in thermal_mismatch["error"]
    slicer_mismatch = run_job(
        {"alloyId": "ss316l", "slicerMaterial": "CoCrMo", "bypassCache": True}
    )
    assert slicer_mismatch["success"] is False
    assert "slicerMaterial" in slicer_mismatch["error"]

    # A stale successful cache entry must not bypass material identity checks.
    with patch.object(
        build_job_solver,
        "cache_get",
        return_value={"success": True, "alloyId": "ss316l", "computeTimeMs": 1},
    ) as mocked_cache_get:
        cached_mismatch = build_job_solver.solve_lpbf_build_job(
            {"alloyId": "ss316l", "thermalMaterial": "Inconel 718"}
        )
    assert cached_mismatch["success"] is False
    assert "thermalMaterial" in cached_mismatch["error"]
    mocked_cache_get.assert_not_called()

    # Equivalent alloy/material aliases should resolve to one cache identity.
    cache_keys = []
    from lpbf_build_job_material_snapshot import build_material_property_snapshot
    aliased_snapshot, aliased_sha = build_material_property_snapshot(
        "ti6al4v", "Ti-6Al-4V", "Ti-6Al-4V ELI"
    )

    def return_seeded_cache_entry(key):
        cache_keys.append(key)
        return {
            "success": True, "alloyId": "ti6al4v", "computeTimeMs": 1,
            "materialPropertySha256": aliased_sha,
            "materialPropertySnapshot": aliased_snapshot,
        }

    with patch.object(build_job_solver, "cache_get", side_effect=return_seeded_cache_entry):
        alias_cache_a = build_job_solver.solve_lpbf_build_job(
            {
                "alloyId": "ti6al4v",
                "thermalMaterial": "Ti-6Al-4V ELI",
                "slicerMaterial": "Ti-6Al-4V",
            }
        )
        alias_cache_b = build_job_solver.solve_lpbf_build_job(
            {
                "alloyId": "Ti-6Al-4V",
                "thermalMaterial": "Ti-6Al-4V",
                "slicerMaterial": "Ti-6Al-4V ELI",
            }
        )
    assert alias_cache_a["success"] and alias_cache_b["success"]
    assert len(cache_keys) == 2 and cache_keys[0] == cache_keys[1]

    omitted_alloy = run_job({"bypassCache": True})
    assert omitted_alloy["success"] is True
    assert omitted_alloy["alloyId"] == "in718"

    if not SLOW:
        print("PASS: solve_lpbf_build_job Phase 5 fast (cache, lazy UQ/NIST, Murakami paste)")
        print("HINT: re-run with --slow for UQ + NIST AM-Bench coverage")
        return 0

    # --- SLOW: UQ + NIST ---
    uq = run_job(
        {
            "alloyId": "ti6al4v",
            "laserPower_W": 200,
            "scanSpeed_mm_s": 900,
            "beamDiameter_um": 80,
            "preheatTemp_C": 150,
            "layerThickness_um": 30,
            "hatchSpacing_um": 100,
            "processSeed": 42,
            "enableUq": True,
            "uqSamples": 24,
            "includeAmbench": True,
            "bypassCache": True,
        }
    )
    assert uq["uq"] is not None
    assert uq["uq"]["enabled"] is True
    assert uq["uq"]["nSamples"] == 24
    assert 0.0 <= uq["uq"]["P_printable"] <= 1.0
    assert "absorptivity" in uq["uq"]["sobolProxy"]
    assert uq["uq"].get("sensitivityMethod") == "spearman-proxy"
    assert uq["ambench"] is not None
    assert uq["ambench"]["source"]["doi"] == "10.1007/s40192-020-00169-1"
    assert len(uq["ambench"]["cases"]) == 3
    assert uq["ambench"]["cases"][0]["nist"]["length_um"] == 659.0
    assert uq["qualification"]["status"] == "not_executed"

    uq2 = run_job(
        {
            "alloyId": "ti6al4v",
            "laserPower_W": 200,
            "scanSpeed_mm_s": 900,
            "beamDiameter_um": 80,
            "preheatTemp_C": 150,
            "layerThickness_um": 30,
            "hatchSpacing_um": 100,
            "processSeed": 42,
            "enableUq": True,
            "uqSamples": 24,
            "includeAmbench": False,
            "bypassCache": True,
        }
    )
    assert uq2["uq"]["P_printable"] == uq["uq"]["P_printable"]

    print("PASS: solve_lpbf_build_job Phase 5 slow (UQ Spearman-proxy + NIST AMB2018-02)")
    return 0


if __name__ == "__main__":
    if "--write-kinetics-fixture" in sys.argv:
        with open(KINETICS_FIXTURE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(kinetics_fixture_blocks(), fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        sys.exit(0)
    sys.exit(main())
