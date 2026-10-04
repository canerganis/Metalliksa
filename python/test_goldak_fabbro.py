#!/usr/bin/env python3
"""Goldak field + Fabbro keyhole + recoil/Marangoni kıvam (PROOF 019/020).

The Goldak melt-pool *width* depends on which absorptivity path
lpbf_thermal_solver.calculate_meltpool_physics takes:

- GPU path: powder_bed_raytracer (NVIDIA warp, device "cuda:0") ray-traces the
  powder bed and returns an effective conduction absorptivity (0.581 for the
  NIST case below on an RTX 4060, warp 1.17.0), giving width 102.2 um with the
  goldak-total-power-v2 kernel (Q = P/2); the v3 half-space kernel has not been run on a GPU host.
- CPU fallback: when that import/launch fails the solver prints
  "Warning: GPU Powder Bed Ray Tracing failed, using flat plate absorptivity."
  and uses the material's flat-plate absorptivity (IN718 IR: 0.38), giving
  width 117.4 um (v2 kernel: 81.7 um). This is the path on the CPU lock (Docker verify stage,
  GitHub `python` job) and on any host without warp + CUDA.

The NIST width band check is skipped ONLY when the ray tracer cannot run on
this host: `import warp` fails or warp reports no CUDA device. Where warp and a
CUDA device are present, the ray-tracing path must be taken: if the solver falls
back to the flat plate (any ray-tracer exception), the test FAILS.
METALLIKSA_REQUIRE_GPU_RAYTRACE=1 turns the skip into a failure (for a GPU host
that must check the width). Under GitHub Actions a skipped width check also
prints a `::warning::` annotation. The fallback behaviour is pinned separately
and is NOT claimed to match NIST.
For this NIST case the Fabbro keyhole depth (and the Goldak+Fabbro depth) is the
same on both paths (123.9 um), so the depth checks always run.
"""
import contextlib
import io
import math
import os
import sys
import unittest
from unittest import mock

from fabbro_keyhole import fabbro_keyhole_depth_m
from goldak_solver import GoldakField, seed_goldak_axes
from lpbf_thermal_solver import THERMOPHYSICAL_DB, calculate_meltpool_physics

# NIST AMB2022-03 IN718: 285 W, 960 mm/s, 67 µm, T0=23.5 °C, W=136.3 µm, D=139.7 µm.
NIST_WIDTH_UM = 136.3
NIST_DEPTH_UM = 139.7
NIST_CASE = ("Inconel 718", 285, 960, 67, 23.5, 40, 110)
FALLBACK_WARNING = "GPU Powder Bed Ray Tracing failed, using flat plate absorptivity"
GPU_SKIP_REASON = "requires GPU warp ray tracing; CPU fallback uses the flat-plate absorptivity"


def _goldak_nist(force_flat_plate=False):
    """Run the NIST Goldak case; return (result, captured stdout)."""
    out = io.StringIO()
    with contextlib.ExitStack() as stack:
        if force_flat_plate:
            # A None entry makes `from powder_bed_raytracer import ...` raise
            # ImportError, i.e. exactly the solver's own fallback branch.
            stack.enter_context(mock.patch.dict(sys.modules, {"powder_bed_raytracer": None}))
        stack.enter_context(contextlib.redirect_stdout(out))
        gk = calculate_meltpool_physics(*NIST_CASE, heat_source="goldak")
    return gk, out.getvalue()


def _gpu_raytrace_unavailable_reason():
    """None when warp imports and reports a CUDA device; otherwise why the ray tracer cannot run here."""
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):  # warp prints an init banner
            import warp as wp
            wp.init()
            count = wp.get_cuda_device_count() if wp.is_cuda_available() else 0
    except Exception as exc:  # ImportError, or a warp/CUDA initialisation failure
        return f"warp is not usable ({type(exc).__name__}: {exc})"
    if count < 1:
        return "warp reports no CUDA device"
    return None


def _flat_plate_absorptivity():
    return float(THERMOPHYSICAL_DB["Inconel 718"]["absorptivity_IR"])


def _used_flat_plate(gk, stdout):
    return (
        FALLBACK_WARNING in stdout
        or abs(gk["processParameters"]["conductionAbsorptivity"] - round(_flat_plate_absorptivity(), 3)) < 1e-9
    )


class FabbroKeyholeTests(unittest.TestCase):
    def test_nist_depth_in_band(self):
        # Fabbro A is Fresnel (0.38), not stacked multi-reflection eta_eff.
        nist = fabbro_keyhole_depth_m(285.0, 0.960, 67e-6, 11.4, 11.4 / (8190.0 * 435.0), 2850.0, 23.5, 0.38, 35.0)
        D_um = nist["depth_m"] * 1e6
        self.assertTrue(0.70 * NIST_DEPTH_UM <= D_um <= 1.40 * NIST_DEPTH_UM, f"Fabbro NIST depth {D_um:.1f} vs {NIST_DEPTH_UM}")

    def test_smaller_spot_is_deeper(self):
        tight = fabbro_keyhole_depth_m(285.0, 0.960, 49e-6, 11.4, 11.4 / (8190.0 * 435.0), 2850.0, 23.5, 0.38, 40.0)
        wide = fabbro_keyhole_depth_m(285.0, 0.960, 82e-6, 11.4, 11.4 / (8190.0 * 435.0), 2850.0, 23.5, 0.38, 28.0)
        self.assertGreater(tight["depth_m"], wide["depth_m"], "smaller spot deeper Fabbro keyhole")

    def test_no_cavity_below_king_transition(self):
        cold = fabbro_keyhole_depth_m(80.0, 1.6, 100e-6, 11.4, 3.2e-6, 2850.0, 80.0, 0.38, 8.0)
        self.assertEqual(cold["depth_m"], 0.0, "no Fabbro cavity below King transition")


class GoldakFieldTests(unittest.TestCase):
    def test_peak_finite_and_wake_not_colder(self):
        axes = seed_goldak_axes(40e-6)
        field = GoldakField(23.5, 108.3, 8190.0, 435.0, 11.4 / (8190.0 * 435.0), **{
            "af_m": axes["af_m"], "ar_m": axes["ar_m"], "b_m": axes["b_m"], "c_m": axes["c_m"],
        }).bind_speed(0.960)
        T0 = field.temperature_C(0.0, 0.0, 0.0)
        self.assertTrue(math.isfinite(T0) and T0 > 23.5, f"Goldak peak finite {T0}")
        T_b = field.temperature_C(-80e-6, 0.0, 0.0)
        T_f = field.temperature_C(80e-6, 0.0, 0.0)
        self.assertGreaterEqual(T_b, T_f * 0.85, f"Goldak wake not colder than front {T_b} vs {T_f}")


class GoldakMeltPoolPathIndependentTests(unittest.TestCase):
    """Checks that hold on both the GPU ray-tracing path and the CPU fallback."""

    def test_nist_case_models_depth_recoil_marangoni(self):
        gk, _ = _goldak_nist()
        self.assertEqual(gk["modelId"], "goldak-half-space-v3", "goldak model id")
        self.assertEqual(gk["keyholeModel"]["modelId"], "fabbro-keyhole-v1", "fabbro on goldak path")
        self.assertLess(abs(gk["keyholeModel"]["absorptivity"] - 0.38), 0.02, "Fabbro A is Fresnel, not eta_eff")
        D = gk["meltPoolGeometry"]["depth_um"]
        # For this NIST case: the same value (123.9 um) with and without the ray tracer.
        self.assertTrue(0.70 * NIST_DEPTH_UM <= D <= 1.40 * NIST_DEPTH_UM, f"Goldak+Fabbro NIST depth {D}")
        recoil = gk["hydrodynamicsAndRecoil"]["knudsenRecoilPressure_kPa"]
        self.assertTrue(20.0 <= recoil <= 120.0, f"Knight recoil at Tv {recoil}")
        self.assertLessEqual(gk["hydrodynamicsAndRecoil"]["surfaceTemperature_C"], 2850.0 + 1.0, "surface T capped")
        self.assertEqual(gk["marangoniModel"]["modelId"], "marangoni-heiple-v1", "marangoni model")
        self.assertEqual(gk["marangoniModel"]["flowDirection"], "outward", "low-S outward")

    def test_rosenthal_build_job_default_unchanged(self):
        ros = calculate_meltpool_physics("Inconel 718", 285, 960, 80, 80, 40, 110)
        self.assertEqual(ros["modelId"], "rosenthal-screening-v1", "Build Job default unchanged")
        self.assertEqual(ros["keyholeModel"]["modelId"], "king-increment", "Rosenthal keeps King increment")


class GoldakNistWidthGpuRayTracingTests(unittest.TestCase):
    def test_nist_width_in_band_with_ray_tracing(self):
        unavailable = _gpu_raytrace_unavailable_reason()
        if unavailable is not None:
            reason = (
                f"{GPU_SKIP_REASON}: {unavailable} (flat-plate width 117.4 um vs NIST {NIST_WIDTH_UM} um; "
                "see GoldakCpuFallbackTests)"
            )
            if os.environ.get("METALLIKSA_REQUIRE_GPU_RAYTRACE") == "1":
                self.fail(f"METALLIKSA_REQUIRE_GPU_RAYTRACE=1 but {reason}")
            if os.environ.get("GITHUB_ACTIONS") == "true":
                print(f"::warning title=Goldak NIST width check skipped::{reason}", flush=True)
            print(f"SKIP test_nist_width_in_band_with_ray_tracing: {reason}", file=sys.stderr)
            self.skipTest(reason)
        gk, stdout = _goldak_nist()
        W = gk["meltPoolGeometry"]["width_um"]
        # warp and a CUDA device are present, so a flat-plate result means the ray tracer raised.
        self.assertFalse(_used_flat_plate(gk, stdout),
                         f"GPU ray tracing is available but the solver fell back to the flat plate: {stdout.strip()}")
        self.assertTrue(0.70 * NIST_WIDTH_UM <= W <= 1.40 * NIST_WIDTH_UM, f"Goldak NIST width {W}")


class GoldakCpuFallbackTests(unittest.TestCase):
    """Pins the documented flat-plate fallback (forced, so it runs on every host).

    With the goldak-half-space-v3 kernel the fallback width (117.4 um) is 0.86x the NIST value
    (136.3 um) and inside the 0.70-1.40 band (the retired v2 kernel gave 81.7 um, ratio 0.60,
    outside the band). This test pins the CPU-fallback value only and does NOT claim a NIST
    match: the GPU ray-traced path (102.2 um with v2) has not been re-run with v3. It also pins
    that the fallback says so.
    """

    def test_fallback_is_labelled_and_pinned(self):
        gk, stdout = _goldak_nist(force_flat_plate=True)
        self.assertIn(FALLBACK_WARNING, stdout, "fallback must print its warning")
        flat = _flat_plate_absorptivity()
        self.assertAlmostEqual(flat, 0.38, places=9, msg="IN718 IR flat-plate absorptivity")
        pp = gk["processParameters"]
        self.assertAlmostEqual(pp["conductionAbsorptivity"], round(flat, 3), places=9,
                               msg="fallback conduction absorptivity is the flat-plate value")
        self.assertAlmostEqual(pp["fabbroAbsorptivity"], round(flat, 3), places=9)
        W = gk["meltPoolGeometry"]["width_um"]
        self.assertAlmostEqual(W, 117.4, delta=0.5, msg=f"flat-plate fallback width {W}")
        self.assertAlmostEqual(gk["meltPoolGeometry"]["depth_um"], 123.9, delta=0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
