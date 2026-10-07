#!/usr/bin/env python3
"""Fixture checks for King-aligned LPBF melt-pool geometry (v5)."""
import sys
from lpbf_thermal_solver import (
    calculate_meltpool_physics,
    classify_enthalpy_regime,
    ENTHALPY_TRANSITION,
    ENTHALPY_KEYHOLE,
)


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    assert_true(classify_enthalpy_regime(10) == "Conduction Mode (Stable)", "King conduction cut")
    assert_true(classify_enthalpy_regime(19.99) == "Transition Mode", "transition cut (15 <= dH/hs < 20)")
    assert_true(classify_enthalpy_regime(20) == "Keyhole Mode (melt-pool D/W > 0.5 screening onset)", "keyhole-mode cut")
    assert_true(classify_enthalpy_regime(35).startswith("Keyhole Mode"), "keyhole mode above the cut")
    assert_true(ENTHALPY_TRANSITION == 15.0 and ENTHALPY_KEYHOLE == 20.0, "regime thresholds 15 / 20")

    in718 = calculate_meltpool_physics("Inconel 718", 285, 960, 80, 80, 40, 110)
    g = in718["meltPoolGeometry"]
    pp = in718["processParameters"]
    assert_true(g["width_um"] > 80 and g["depth_um"] > 20, "IN718 default W,D")
    assert_true(g["length_um"] > g["width_um"], "IN718 L > W")
    assert_true(pp["normalizedEnthalpy"] > 0 and pp.get("peakIntensity_MW_cm2", 0) > 0, "I0 and ΔH/hs")
    assert_true(len(in718["geometricContours"]["longitudinalXZ"]) >= 16, "longitudinal contour")
    assert_true(len(in718["geometricContours"]["transverseYZ"]) >= 8, "transverse contour")
    assert_true(len(in718["thermalSlices"]["xz"]["T_C"]) == 36 * 24, "XZ thermal slice")
    assert_true("Keyhole" in g["regime"] or "Transition" in g["regime"], "IN718 near King onset")

    low = calculate_meltpool_physics("Inconel 718", 140, 1600, 100, 80, 60, 150)
    assert_true(low["meltPoolGeometry"]["depthToWidthRatio_D_over_W"] < 0.85, "LoF case shallower D/W")
    assert_true(not low["meltPoolGeometry"]["regime"].startswith("Keyhole"), "LoF not keyhole")

    kh = calculate_meltpool_physics("Inconel 718", 480, 450, 65, 80, 40, 120)
    assert_true(kh["meltPoolGeometry"]["regime"].startswith("Keyhole"), "high P/v is keyhole")
    assert_true(kh["meltPoolGeometry"]["depth_um"] > in718["meltPoolGeometry"]["depth_um"], "keyhole deeper")

    ti = calculate_meltpool_physics("Ti-6Al-4V", 200, 900, 80, 150, 30, 100)
    assert_true(40 <= ti["meltPoolGeometry"]["width_um"] <= 280, "Ti64 W order of magnitude")
    assert_true(15 <= ti["meltPoolGeometry"]["depth_um"] <= 200, "Ti64 D order of magnitude")

    ss = calculate_meltpool_physics("316L Stainless Steel", 200, 800, 70, 80, 30, 100)
    assert_true(ss["processParameters"]["normalizedEnthalpy"] < 40.0, "316L 200W below severe keyhole")
    assert_true(ss["meltPoolGeometry"]["width_um"] > 70, "316L width")

    print("PASS: LPBF melt-pool accuracy fixture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
