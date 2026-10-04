"""RPC "solidification-microstructure": screening-field path (no CFD) from lpbf_thermal_solver.

The Microstructure Lab sends materialName + process inputs; Python resolves the alloy and returns the
projection of thermal.solidificationKinetics. Unusable inputs give status "unavailable" (no defaults, no
surrogate alloy). The legacy cfdResult path is kept only when a cfdResult is supplied.
"""
import math
import unittest

import lpbf_worker_rpc
from lpbf_solidification_microstructure import SCREENING_FIELD_SCOPE
from lpbf_thermal_solver import calculate_meltpool_physics

FALLBACK_REASON = (
    "thermal.solidificationKinetics used the tail-length heuristic (G = ΔT/x_rear, R = v·cosθ), "
    "not the liquidus field map; treat G/R/PDAS/SDAS as screening only"
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
        out = rpc({**IN718_285, "speed_mm_s": 0})
        self.assertEqual(out["status"], "unavailable")
        self.assertIn("scan_speed_mm_s", out["reason"])

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
