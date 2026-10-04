#!/usr/bin/env python3
"""Goldak+Fabbro vs measured literature tracks (PROOF 022/023). Not Build Job."""
import sys

from lpbf_thermal_solver import calculate_meltpool_physics
from meltpool_literature_catalog import (
    GAPS,
    TRACKS,
    measured_coverage,
    score_track,
    validate_measured_candidate,
)


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


LAYER = {"Inconel 718": (40, 110), "316L Stainless Steel": (50, 100)}


def goldak_score(t):
    t_um, h_um = LAYER[t["material"]]
    r = calculate_meltpool_physics(
        t["material"], t["laserPower_W"], t["scanSpeed_mm_s"], t["beamDiameter_um"],
        t["preheatTemp_C"], t_um, h_um, heat_source="goldak",
    )
    assert_true(r["modelId"] == "goldak-half-space-v3", "heat source")
    s = score_track(r["meltPoolGeometry"]["width_um"], r["meltPoolGeometry"]["depth_um"], t)
    s["pred_W"] = r["meltPoolGeometry"]["width_um"]
    s["pred_D"] = r["meltPoolGeometry"]["depth_um"]
    s["extentStatus"] = r["meltPoolGeometry"]["extentStatus"]
    if s["extentStatus"] != "computed":
        # A heuristic substitute width is not a computed prediction: it cannot pass a benchmark.
        s["pass"] = False
    return s


def main():
    nist = [t for t in TRACKS if t["id"].startswith("nist-amb2022-03")]
    guo = [t for t in TRACKS if t["id"].startswith("guo-316l")]
    assert_true(len(nist) == 7, "Lane Table 4 has 7 cases")
    assert_true(len(guo) == 4, "Guo Table 3 four experimental W/D rows")
    assert_true(all(t["kind"] == "measured" and t["doi"] for t in TRACKS), "DOI measured only")
    cov = measured_coverage()
    assert_true(cov["AlSi10Mg"] == "no_measured_track", "AlSi10Mg honest gap")
    assert_true(cov["Ti-6Al-4V"] == "no_measured_track", "Ti64 no invented micrograph")
    assert_true(any(g["material"] == "AlSi10Mg" for g in GAPS), "AlSi10Mg gap recorded")

    ok, _ = validate_measured_candidate(nist[0])
    assert_true(ok, "Lane row is a valid measured candidate")
    bad, why = validate_measured_candidate(
        {"kind": "measured", "id": "solver-echo-jsonl", "doi": "10.0/x",
         "laserPower_W": 1, "scanSpeed_mm_s": 1, "beamDiameter_um": 1,
         "preheatTemp_C": 1, "width_um": 1, "depth_um": 1}
    )
    assert_true(not bad and "solver-echo" in why, why)

    nist_pass = 0
    for t in nist:
        s = goldak_score(t)
        assert_true(s["pass"], f"{t['id']} W/D out of ×0.5–2 band {s}")
        nist_pass += 1

    d49 = calculate_meltpool_physics("Inconel 718", 285, 960, 49, 23.5, 40, 110, heat_source="goldak")
    d82 = calculate_meltpool_physics("Inconel 718", 285, 960, 82, 23.5, 40, 110, heat_source="goldak")
    assert_true(
        d49["meltPoolGeometry"]["depth_um"] > d82["meltPoolGeometry"]["depth_um"],
        "smaller D4σ must be deeper (Lane 1.1 vs 1.2)",
    )

    guo_scores = {t["id"]: goldak_score(t) for t in guo}
    for gid in ("guo-316l-n04", "guo-316l-n05", "guo-316l-n06"):
        assert_true(guo_scores[gid]["pass"], f"{gid} {guo_scores[gid]}")

    n01 = guo_scores["guo-316l-n01"]
    # Guo N01 (260 W, 0.52 m/s) is a keyhole track (measured D 180 µm). The conduction
    # Goldak field plus Fabbro depth does NOT reach it: this is a REPORTED FAILURE of the
    # screening model, kept explicit on purpose (RULES: report the failing benchmark, never
    # widen the band). The half-space kernel moved N04 and N06 into the band; N01 stays out.
    assert_true(n01["widthInBand"], f"Guo N01 width unexpectedly outside the band {n01}")
    assert_true(not n01["depthInBand"] and not n01["pass"],
                f"Guo N01 depth unexpectedly inside the band; update this reported failure: {n01}")
    print(
        "REPORTED FAILURE: Guo N01 keyhole depth outside the ×0.5–2 screening band "
        f"(pred {n01['pred_D']} µm vs 180 µm, MAPE {n01['depth_mape_pct']}%) — conduction screening, not fitted"
    )

    ros = calculate_meltpool_physics("Inconel 718", 285, 960, 80, 80, 40, 110)
    assert_true(ros["modelId"] == "rosenthal-screening-v1", "Build Job heat source unchanged")
    print(f"PASS: literature catalog Goldak+Fabbro ({nist_pass} NIST + Guo N04/N05/N06; N01 depth is a reported failure)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
