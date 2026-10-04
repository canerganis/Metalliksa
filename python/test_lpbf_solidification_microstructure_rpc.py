"""RPC "solidification-microstructure": screening-field path (no CFD) from lpbf_thermal_solver.

The Microstructure Lab sends materialName + process inputs; Python resolves the alloy and returns the
projection of thermal.solidificationKinetics. Unusable inputs give status "unavailable" (no defaults, no
surrogate alloy). The legacy cfdResult path is kept only when a cfdResult is supplied.
"""
import collections
import math
import unittest

import lpbf_worker_rpc
from lpbf_solidification_microstructure import SCREENING_FIELD_SCOPE
from lpbf_thermal_solver import calculate_meltpool_physics

FALLBACK_REASON = (
    "thermal.solidificationKinetics used the tail-length heuristic (G = ΔT/x_rear, R = v·cosθ), "
    "not the liquidus field map; treat G/R/PDAS/SDAS as screening only"
)

DEGENERATE_FLOOR_REASON = (
    "solidification front degenerate: floor-clamped R/cooling "
    "(R <= 1e-4 m/s or cooling <= 1 K/s), not a computed value"
)

IN718_285 = {
    "materialName": "Inconel 718",
    "power_W": 285,
    "speed_mm_s": 960,
    "beamDiameter_um": 80,
    "preheat_C": 80,
    "layerThickness_um": 40,
    "hatch_um": 110,
    "heatSource": "rosenthal",
}


def rpc(params, **extra):
    return lpbf_worker_rpc._rpc_solidification_microstructure({"payload": {"params": params, **extra}})


class SolidificationMicrostructureRpcTest(unittest.TestCase):
    def test_available_field_map_equals_thermal_kinetics(self):
        out = rpc(IN718_285)
        thermal = calculate_meltpool_physics("Inconel 718", 285, 960, 80, 80, 40, 110, heat_source="rosenthal")
        kin = thermal["solidificationKinetics"]
        self.assertEqual(out["status"], "available")
        self.assertIs(out["usedFieldMap"], True)
        self.assertEqual(out["gradientSource"], kin["gradientSource"])
        self.assertEqual(out["G_K_m"], kin["thermalGradient_G_K_m"])
        self.assertEqual(out["R_m_s"], kin["solidificationRate_R_mm_s"] / 1.0e3)
        self.assertEqual(out["coolingRate_K_s"], kin["coolingRate_K_s"])
        self.assertEqual(out["PDAS_um"], kin["primaryDendriteArmSpacing_PDAS_um"])
        self.assertEqual(out["SDAS_um"], kin["secondaryDendriteArmSpacing_SDAS_um"])
        self.assertEqual(out["morphology"], kin["microstructureMorphology"])
        self.assertEqual(out["heatSourceModel"], thermal["heatSourceModel"])
        self.assertEqual(out["regime"], thermal["meltPoolGeometry"]["regime"])
        self.assertTrue(out["regime"].startswith("Keyhole"))
        self.assertEqual(out["regimeNote"], "Keyhole Mode: outside the conduction regime of the G/R field")
        self.assertEqual(out["normalizedEnthalpy"], thermal["processParameters"]["normalizedEnthalpy"])
        self.assertEqual(out["absorptivity"]["conduction"], thermal["processParameters"]["conductionAbsorptivity"])
        self.assertEqual(out["absorptivity"]["effective"], thermal["processParameters"]["effectiveAbsorptivity"])
        self.assertEqual(out["materialName"], "Inconel 718")
        self.assertEqual(out["scope"], SCREENING_FIELD_SCOPE)
        self.assertIn("not validated", out["scope"])
        # The scope no longer claims equality with the Build Job for every heat source.
        self.assertIn("heatSource=rosenthal", out["scope"])
        self.assertIn("Goldak/Eagar-Tsai fields give different G/R", out["scope"])
        # The RPC has its own projection note, not the Build Job one.
        self.assertIn("Screening-field projection of python/lpbf_thermal_solver solidificationKinetics", out["disclaimer"])
        self.assertNotIn("Build-job microstructure is a projection", out["disclaimer"])
        self.assertEqual(out["morphologyBands_G_over_R"], {"planar": 1.0e10, "cellular": 5.0e8, "columnar": 1.0e7})
        self.assertEqual(out["inputs"]["power_W"], 285.0)
        print("  rpc available IN718 285/960:", {k: out[k] for k in ("status", "G_K_m", "R_m_s", "PDAS_um", "SDAS_um", "morphology", "heatSourceModel", "gradientSource")})

    def test_screening_fallback_is_labelled(self):
        out = rpc({**IN718_285, "power_W": 60, "speed_mm_s": 2000})
        self.assertEqual(out["status"], "screening-fallback")
        self.assertEqual(out["reason"], FALLBACK_REASON)
        self.assertIs(out["usedFieldMap"], False)
        self.assertEqual(out["gradientSource"], "tail-length-fallback")
        self.assertTrue(math.isfinite(out["G_K_m"]))

    def test_degenerate_floor_in718_285_1200(self):
        # Real output: the frozen front mapper reports usedFieldMap True but clamps R and cooling to floors.
        out = rpc({**IN718_285, "speed_mm_s": 1200})
        kin = calculate_meltpool_physics("Inconel 718", 285, 1200, 80, 80, 40, 110, heat_source="rosenthal")["solidificationKinetics"]
        self.assertIs(kin["usedFieldMap"], True)
        self.assertLessEqual(kin["solidificationRate_R_mm_s"], 0.1)
        self.assertLessEqual(kin["coolingRate_K_s"], 1.0)
        self.assertEqual(out["status"], "degenerate-floor")
        self.assertEqual(out["reason"], DEGENERATE_FLOOR_REASON)
        self.assertIs(out["usedFieldMap"], True)
        # Numbers are copied, not recomputed.
        self.assertEqual(out["coolingRate_K_s"], kin["coolingRate_K_s"])
        self.assertEqual(out["G_K_m"], kin["thermalGradient_G_K_m"])
        self.assertEqual(out["PDAS_um"], kin["primaryDendriteArmSpacing_PDAS_um"])
        self.assertLessEqual(out["R_m_s"], 1.0e-4 * (1.0 + 1.0e-9))
        self.assertIn("not a computed result", out["disclaimer"])
        print("  rpc degenerate-floor IN718 285/1200:", {k: out[k] for k in ("status", "R_m_s", "coolingRate_K_s", "PDAS_um", "SDAS_um", "morphology")})

    def test_no_available_result_sits_on_a_clamp_floor(self):
        # Sample grid (4 alloys x 5 powers x 5 speeds), calculate_meltpool_physics + projection directly.
        from lpbf_solidification_microstructure import project_build_job_microstructure

        names = ("Inconel 718", "Ti-6Al-4V", "AlSi10Mg", "316L Stainless Steel")
        counts = collections.Counter()
        for name in names:
            for power in (100, 150, 200, 285, 350):
                for speed in (300, 600, 960, 1200, 1600):
                    block = project_build_job_microstructure(
                        calculate_meltpool_physics(name, power, speed, 80, 80, 40, 110, heat_source="rosenthal"))
                    counts[block["status"]] += 1
                    if block["status"] == "available":
                        self.assertGreater(block["R_m_s"], 1.0e-4, (name, power, speed))
                        self.assertGreater(block["coolingRate_K_s"], 1.0, (name, power, speed))
                    if block["status"] == "degenerate-floor":
                        self.assertEqual(block["reason"], DEGENERATE_FLOOR_REASON)
                        self.assertTrue(block["R_m_s"] <= 1.0e-4 * (1.0 + 1.0e-9) or block["coolingRate_K_s"] <= 1.0)
        print("  grid scan status counts:", dict(counts))
        self.assertGreaterEqual(counts["degenerate-floor"], 1)
        self.assertGreaterEqual(counts["available"], 1)

    def test_heat_source_is_passed_through(self):
        out = rpc({**IN718_285, "heatSource": "goldak"})
        self.assertEqual(out["heatSourceModel"], calculate_meltpool_physics(
            "Inconel 718", 285, 960, 80, 80, 40, 110, heat_source="goldak")["heatSourceModel"])
        self.assertNotEqual(out["heatSourceModel"], rpc(IN718_285)["heatSourceModel"])

    def test_default_heat_source_is_rosenthal(self):
        params = {k: v for k, v in IN718_285.items() if k != "heatSource"}
        self.assertEqual(rpc(params)["G_K_m"], rpc(IN718_285)["G_K_m"])

    def test_unknown_material_is_unavailable_without_surrogate(self):
        out = rpc({**IN718_285, "materialName": "Unobtainium 9000"})
        self.assertEqual(out["status"], "unavailable")
        self.assertIn("Unsupported LPBF material identity", out["reason"])
        self.assertIsNone(out["G_K_m"])
        self.assertIsNone(out["PDAS_um"])
        self.assertEqual(out["source"], "none")

    def test_missing_inputs_are_unavailable_without_defaults(self):
        for key in ("materialName", "power_W", "speed_mm_s", "beamDiameter_um", "preheat_C",
                    "layerThickness_um", "hatch_um"):
            params = {k: v for k, v in IN718_285.items() if k != key}
            out = rpc(params)
            self.assertEqual(out["status"], "unavailable", key)
            self.assertIn(key, out["reason"], key)
            self.assertIsNone(out["G_K_m"], key)
        for bad in (None, "285", True, float("nan")):
            out = rpc({**IN718_285, "power_W": bad})
            self.assertEqual(out["status"], "unavailable", repr(bad))
        self.assertEqual(rpc({})["status"], "unavailable")
        self.assertEqual(lpbf_worker_rpc._rpc_solidification_microstructure({"payload": {}})["status"], "unavailable")

    def test_non_positive_input_is_unavailable(self):
        for key in ("power_W", "speed_mm_s", "beamDiameter_um", "layerThickness_um", "hatch_um"):
            for bad in (0, -1):
                out = rpc({**IN718_285, key: bad})
                self.assertEqual(out["status"], "unavailable", (key, bad))
                self.assertIn(key, out["reason"], (key, bad))
                self.assertIn("positive", out["reason"], (key, bad))
                self.assertIsNone(out["G_K_m"], (key, bad))

    def test_impossible_preheat_is_unavailable(self):
        for bad in (-300, -273.15, 2000, 1336):
            out = rpc({**IN718_285, "preheat_C": bad})
            self.assertEqual(out["status"], "unavailable", bad)
            self.assertIn("preheat_C", out["reason"], bad)
            self.assertIsNone(out["PDAS_um"], bad)
        self.assertIn("absolute zero", rpc({**IN718_285, "preheat_C": -300})["reason"])
        self.assertIn("liquidus", rpc({**IN718_285, "preheat_C": 2000})["reason"])
        # A physical preheat (including sub-zero, above absolute zero) is still accepted.
        self.assertEqual(rpc({**IN718_285, "preheat_C": 20})["status"], "available")
        self.assertIn(rpc({**IN718_285, "preheat_C": -20})["status"], ("available", "screening-fallback", "degenerate-floor"))

    def test_unsupported_heat_source_is_unavailable(self):
        out = rpc({**IN718_285, "heatSource": "gaussian-magic"})
        self.assertEqual(out["status"], "unavailable")
        self.assertIn("Unsupported LPBF heat source", out["reason"])

    def test_payload_material_numbers_are_ignored(self):
        # Python is the authority: legacy k/liquidus/absorptivity in the payload must not change anything.
        base = rpc(IN718_285)
        lied = rpc(IN718_285, material={"k_WmK": 1.0, "liquidus_K": 999.0, "absorptivity": 0.99})
        self.assertEqual(base["G_K_m"], lied["G_K_m"])
        self.assertEqual(base["absorptivity"], lied["absorptivity"])

    def test_legacy_cfd_path_only_when_cfd_result_supplied(self):
        cfd = {"solidificationMicrostructure": {"meanG_K_m": 5.0e6, "meanR_m_s": 0.05, "frontCellCount": 12}}
        out = rpc(IN718_285, cfdResult=cfd)
        self.assertEqual(out["status"], "available")
        self.assertEqual(out["source"], "openfoam-solidification-model-v1")
        self.assertEqual(out["frontCellCount"], 12)


if __name__ == "__main__":
    unittest.main()
