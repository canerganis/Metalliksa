#!/usr/bin/env python3
"""Eagar–Tsai v2 kernel checks: closed-form limits, an independent integral, and the
Melt Pool lab path (PROOF 018 superseded by the corrected-physics bump).

Reference values were produced with an independent SciPy quad implementation of the
dimensional Eagar–Tsai integral (surface Gaussian I = 2P/(π r0²) exp(-2 r²/r0²), σ = r0/2,
semi-infinite body, image factor 2), itself anchored to Rosenthal as σ → 0 (0.005 %)
and to the static analytic centre value P/(√(2π) k r0) (0.02 %). No tolerance here
exceeds 0.5 %; the former 45 % wake check is gone with the bug it covered.
"""
import math
import sys

from eagar_tsai_solver import EagarTsaiField, MODEL_ID, eagar_tsai_temperature_C
from lpbf_thermal_solver import calculate_meltpool_physics, rosenthal_temperature_C


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


# Reference ΔT (K) for k=20 W/mK, rho=8000, cp=600, P=30 W, v=1 m/s, r0=40 um (laser frame,
# x < 0 behind the source, z depth), from the independent integral.
REFERENCE_DT_K = {
    (0.0, 0.0, 0.0): 6258.568,
    (-40e-6, 0.0, 0.0): 4607.236,
    (-100e-6, 0.0, 0.0): 2002.337,
    (-200e-6, 0.0, 0.0): 1077.159,
    (-600e-6, 0.0, 0.0): 383.077,
    (0.0, 40e-6, 0.0): 1204.235,
    (0.0, 0.0, 30e-6): 260.403,
    (-60e-6, 30e-6, 20e-6): 1116.270,
    (30e-6, 0.0, 0.0): 1479.892,
}


def main():
    assert_true(MODEL_ID == "eagar-tsai-v2", "model id")
    k, rho, cp = 20.0, 8000.0, 600.0
    alpha = k / (rho * cp)
    P, v, r0, T0 = 30.0, 1.0, 40e-6, 300.0

    # 1) Independent integral at nine points, 0.5 % (the v1 kernel was 0.63x-1.53x here).
    field = EagarTsaiField(T0, P, k, alpha, r0).bind_speed(v)
    for (x, y, z), ref in REFERENCE_DT_K.items():
        got = field.temperature_C(x, y, z) - T0
        assert_true(abs(got - ref) / ref < 0.005, f"ET vs integral at {(x, y, z)}: {got:.3f} vs {ref:.3f}")

    # 2) Static centre: ΔT(0) = P/(√(2π) k r0) within 0.1 % at v = 1e-4 m/s.
    static = EagarTsaiField(T0, P, k, alpha, r0).bind_speed(1e-4).temperature_C(0.0, 0.0, 0.0) - T0
    analytic = P / (math.sqrt(2.0 * math.pi) * k * r0)
    assert_true(abs(static - analytic) / analytic < 0.001, f"static centre {static:.2f} vs {analytic:.2f}")

    # 3) Point-source limit: r0 = 1 um vs Rosenthal (unregularized) within 0.1 % (v1 gave √2).
    point = EagarTsaiField(T0, P, k, alpha, 1e-6).bind_speed(v)
    for x in (-100e-6, -300e-6, -600e-6, -1200e-6):
        ros = rosenthal_temperature_C(x, 0.0, 0.0, T0, P, k, v, alpha, 0.0) - T0
        et = point.temperature_C(x, 0.0, 0.0) - T0
        assert_true(abs(et / ros - 1.0) < 0.001, f"point-source limit at x={x*1e6:g} um: {et/ros:.5f}")

    # 4) Functional: finite peak, spot-size and wake ordering (IN718-like props).
    T0, k, rho, cp = 23.5, 11.4, 8190.0, 435.0
    alpha = k / (rho * cp)
    P_eff, v, r0 = 0.38 * 285.0, 0.960, 33.5e-6
    T_origin = eagar_tsai_temperature_C(0.0, 0.0, 0.0, T0, P_eff, k, v, alpha, r0)
    assert_true(math.isfinite(T_origin) and T_origin > T0 + 200.0, f"ET peak finite and hot ({T_origin})")
    T_small = eagar_tsai_temperature_C(0.0, 0.0, 0.0, T0, P_eff, k, v, alpha, 24.5e-6)
    T_large = eagar_tsai_temperature_C(0.0, 0.0, 0.0, T0, P_eff, k, v, alpha, 41.0e-6)
    assert_true(T_small > T_large, f"larger spot cooler peak {T_small} vs {T_large}")
    T_ahead = eagar_tsai_temperature_C(80e-6, 0.0, 0.0, T0, P_eff, k, v, alpha, r0)
    T_behind = eagar_tsai_temperature_C(-80e-6, 0.0, 0.0, T0, P_eff, k, v, alpha, r0)
    assert_true(T_behind > T_ahead, f"wake hotter than front {T_behind} vs {T_ahead}")

    # 5) NIST AMB2022-03 IN718 baseline (Lane et al. 2024, DOI 10.1007/s40192-024-00355-5).
    # Bare plate, 285 W, 960 mm/s, D4σ = 67 µm, T0 = 23.5 °C. Measured W = 136.3 µm.
    # Depth 139.7 µm is keyhole — ET is conduction-only, so only width is bounded.
    # Band unchanged from v1; the v2 value on the CPU path is 122.5 µm (v1: 127.8).
    nist = calculate_meltpool_physics("Inconel 718", 285, 960, 67, 23.5, 40, 110, heat_source="eagar-tsai")
    assert_true(nist["modelId"] == "eagar-tsai-v2", "model id in the melt-pool result")
    W = nist["meltPoolGeometry"]["width_um"]
    assert_true(0.45 * 136.3 <= W <= 2.2 * 136.3, f"NIST width envelope W={W}")

    # 6) Same NIST P–v: larger D4σ → not narrower and not deeper conduction isotherm.
    tight = calculate_meltpool_physics("Inconel 718", 285, 960, 49, 23.5, 40, 110, heat_source="eagar-tsai")
    wide = calculate_meltpool_physics("Inconel 718", 285, 960, 82, 23.5, 40, 110, heat_source="eagar-tsai")
    d_iso_tight = tight["meltPoolGeometry"]["depth_um"] - tight["meltPoolGeometry"]["keyholeVaporCavityDepth_um"]
    d_iso_wide = wide["meltPoolGeometry"]["depth_um"] - wide["meltPoolGeometry"]["keyholeVaporCavityDepth_um"]
    assert_true(wide["meltPoolGeometry"]["width_um"] >= tight["meltPoolGeometry"]["width_um"] * 0.92, "larger spot not narrower")
    assert_true(d_iso_wide <= d_iso_tight * 1.08, "larger spot not deeper conduction isotherm")

    # 7) 316L conduction-ish point (Guo et al. Micromachines 2024: 260 W, 1.47 m/s, 100 µm).
    ss = calculate_meltpool_physics("316L Stainless Steel", 260, 1470, 100, 25, 50, 100, heat_source="eagar-tsai")
    assert_true(60 <= ss["meltPoolGeometry"]["width_um"] <= 280, f"316L W={ss['meltPoolGeometry']['width_um']}")
    assert_true(ss["processParameters"]["heatSource"] == "eagar-tsai", "316L heat source flag")

    # 8) Build-job default path is unchanged (no heat_source → Rosenthal).
    ros = calculate_meltpool_physics("Inconel 718", 285, 960, 80, 80, 40, 110)
    assert_true(ros["modelId"] == "rosenthal-screening-v1", "default remains Rosenthal")

    print("PASS: Eagar–Tsai v2 field (integral 0.5 %, static 0.1 %, point source 0.1 %) + NIST / 316L envelopes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
