#!/usr/bin/env python3
"""Literature W/D (order-of-magnitude) or King class checks for the four locked alloys."""
import sys

from four_alloy_materials import (
    FOUR_ALLOY_IDS,
    LITERATURE_MELT_POOL_CASES,
    THERMAL_NAME,
    four_alloy_thermophysical_db,
    regime_family,
    resolve_alloy_id,
    thermal_props,
)
from lpbf_thermal_solver import THERMOPHYSICAL_DB, calculate_meltpool_physics


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    for aid in FOUR_ALLOY_IDS:
        name = THERMAL_NAME[aid]
        assert_true(resolve_alloy_id(name) == aid, f"resolve {name}")
        assert_true(thermal_props(name) is THERMOPHYSICAL_DB[name] or thermal_props(name) == THERMOPHYSICAL_DB[name], f"shared thermal {name}")
        assert_true(name in four_alloy_thermophysical_db(), f"db has {name}")

    # Ti-6Al-4V ELI must not fall back to IN718.
    assert_true(resolve_alloy_id("Ti-6Al-4V ELI") == "ti6al4v", "ELI alias")
    eli = calculate_meltpool_physics("Ti-6Al-4V ELI", 200, 900, 80, 150, 30, 100)
    ti = calculate_meltpool_physics("Ti-6Al-4V", 200, 900, 80, 150, 30, 100)
    assert_true(abs(eli["meltPoolGeometry"]["width_um"] - ti["meltPoolGeometry"]["width_um"]) < 0.2, "ELI same W as Ti64")

    for case in LITERATURE_MELT_POOL_CASES:
        name = THERMAL_NAME[case["alloy_id"]]
        result = calculate_meltpool_physics(
            name,
            case["laserPower_W"],
            case["scanSpeed_mm_s"],
            case["beamDiameter_um"],
            case["preheatTemp_C"],
            case["layerThickness_um"],
            case["hatchSpacing_um"],
        )
        pred_fam = regime_family(result["meltPoolGeometry"]["regime"])
        if case["publishedRegime"] is not None:
            assert_true(
                pred_fam == case["publishedRegime"],
                f"{case['id']} class {pred_fam} vs {case['publishedRegime']}",
            )
        if case["check"] == "wd":
            # Only a cited measurement may serve as a W/D anchor (MD-3).
            assert_true(case["widthDepthBasis"] == "published-measurement", f"{case['id']} wd basis")
            W = result["meltPoolGeometry"]["width_um"]
            D = result["meltPoolGeometry"]["depth_um"]
            pub_w = case["publishedWidth_um"]
            pub_d = case["publishedDepth_um"]
            # Screening Rosenthal, not Eagar–Tsai: factor-of-two envelope vs published W/D.
            assert_true(0.5 * pub_w <= W <= 2.0 * pub_w, f"{case['id']} W={W} vs {pub_w}")
            assert_true(0.4 * pub_d <= D <= 2.5 * pub_d, f"{case['id']} D={D} vs {pub_d}")

    print("PASS: four-alloy shared materials + literature W/D or class")
    return 0


if __name__ == "__main__":
    sys.exit(main())
