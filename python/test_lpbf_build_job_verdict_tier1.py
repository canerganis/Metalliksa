"""Tier 1 build-job verdict policy (python/lpbf_build_job_solver.py compose_verdict).

- The frozen balling flag (steady-Rosenthal L/W > 3.8) makes a verdict risky, never do-not-print.
- Recoater / distortion flags are alloy/layer advisories independent of P, v and hatch: reported, never
  verdict-driving, never the dominant gate.
- The keyhole rule (High and dH > 35 -> do-not-print) is unchanged.

Thermal inputs are real calculate_meltpool_physics output (in-repo frozen solver); only the defect
flags under test are overwritten so each case isolates one gate.
"""
import copy
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lpbf_build_job_solver import ADVISORY_GATES, compose_verdict, solve_lpbf_build_job  # noqa: E402
from lpbf_thermal_solver import calculate_meltpool_physics  # noqa: E402

_BASE = None


def _base_thermal():
    """A real computed-extent IN718 thermal result inside the literature P-v box."""
    global _BASE
    if _BASE is None:
        _BASE = calculate_meltpool_physics(
            material_name="in718", laser_power_W=280.0, scan_speed_mm_s=940.0, beam_diameter_um=80.0,
            preheat_temp_C=80.0, layer_thickness_um=40.0, hatch_spacing_um=100.0,
            laser_wavelength="IR_1064nm")
    return copy.deepcopy(_BASE)


def _clean(**flags):
    """Real thermal result with every verdict-driving flag passing, then `flags` applied."""
    th = _base_thermal()
    assert th["meltPoolGeometry"]["extentStatus"] == "computed", th["meltPoolGeometry"]["extentStatus"]
    dd = th["defectDiagnostics"]
    dd.update(lackOfFusionStatus="Pass", keyholePorosityRisk="Low (Conduction Mode)",
              ballingInstabilityRisk="Stable Continuous Track (No Balling)",
              recoaterCrashRisk="Low (Safe Thermal Stress Window)", distortionIndex=0.3)
    th["processParameters"]["normalizedEnthalpy"] = 20.0
    for k, v in flags.items():
        if k == "normalizedEnthalpy":
            th["processParameters"][k] = v
        else:
            dd[k] = v
    return th


HIGH_BALLING = "High Balling Risk (Capillary Pinch-Off & Humping)"
HIGH_RECOATER = "High (Blade Collision & Part Curl Risk)"


class ComposeVerdictTier1(unittest.TestCase):
    def test_clean_case_is_printable(self):
        out = compose_verdict(_clean(), "in718")
        self.assertEqual(out["verdict"], "printable")
        self.assertEqual(out["blockingGates"], [])
        self.assertEqual(out["advisories"], [])

    def test_only_balling_high_is_risky_with_screen_reason(self):
        out = compose_verdict(_clean(ballingInstabilityRisk=HIGH_BALLING), "in718")
        self.assertEqual(out["verdict"], "risky")
        gates = {g["id"]: g["status"] for g in out["gates"]}
        self.assertEqual(gates["balling"], "warn")
        self.assertEqual(out["blockingGates"], [])
        self.assertEqual(out["riskGates"], ["balling"])
        self.assertEqual(out["dominantGate"], "balling")
        line = next(r for r in out["reasons"] if "balling" in r)
        self.assertIn("steady-Rosenthal aspect-ratio screen", line)
        self.assertIn("not a demonstrated balling prediction", line)

    def test_only_recoater_distortion_high_keeps_printable(self):
        out = compose_verdict(_clean(recoaterCrashRisk=HIGH_RECOATER, distortionIndex=7.59), "in718")
        self.assertEqual(out["verdict"], "printable")
        self.assertEqual(out["dominantGate"], "none")
        self.assertIsNone(out["suggestedPatch"])
        gates = {g["id"]: g["status"] for g in out["gates"]}
        self.assertEqual(gates["recoater"], "advisory")
        self.assertEqual(gates["distortion"], "advisory")
        self.assertEqual(out["advisoryGates"], list(ADVISORY_GATES))
        self.assertEqual(out["blockingGates"], [])
        self.assertEqual(out["riskGates"], [])
        # Advisories are visible in reasons, last, and say why they do not change the verdict.
        self.assertEqual(out["reasons"][-2:], out["advisories"])
        self.assertTrue(out["reasons"][0].startswith("Conduction-mode melt pool"))
        for a in out["advisories"]:
            self.assertTrue(a.startswith("Advisory:"), a)
            self.assertIn("not on P, v or hatch", a)
            self.assertIn("does not change the verdict", a)

    def test_advisories_do_not_change_any_verdict(self):
        cases = [
            {}, {"ballingInstabilityRisk": HIGH_BALLING}, {"lackOfFusionStatus": "Warning"},
            {"lackOfFusionStatus": "Fail"}, {"keyholePorosityRisk": "High", "normalizedEnthalpy": 32.0},
            {"keyholePorosityRisk": "High", "normalizedEnthalpy": 40.0},
        ]
        for flags in cases:
            plain = compose_verdict(_clean(**flags), "in718")
            adv = compose_verdict(_clean(recoaterCrashRisk=HIGH_RECOATER, distortionIndex=7.59, **flags), "in718")
            self.assertEqual(plain["verdict"], adv["verdict"], flags)
            self.assertEqual(plain["dominantGate"], adv["dominantGate"], flags)
            self.assertEqual(plain["suggestedPatch"], adv["suggestedPatch"], flags)

    def test_keyhole_rule_unchanged(self):
        self.assertEqual(compose_verdict(_clean(keyholePorosityRisk="High", normalizedEnthalpy=35.0), "in718")["verdict"], "risky")
        out = compose_verdict(_clean(keyholePorosityRisk="High", normalizedEnthalpy=35.01), "in718")
        self.assertEqual(out["verdict"], "do-not-print")
        self.assertEqual(out["blockingGates"], ["keyhole"])
        self.assertEqual(out["dominantGate"], "keyhole")

    def test_lof_fail_still_do_not_print(self):
        out = compose_verdict(_clean(lackOfFusionStatus="Fail"), "in718")
        self.assertEqual(out["verdict"], "do-not-print")
        self.assertIn("lof_tang", out["blockingGates"])


class In718EndToEnd(unittest.TestCase):
    PAYLOAD = {"alloyId": "in718", "laserPower_W": 280, "scanSpeed_mm_s": 940, "hatchSpacing_um": 100,
               "layerThickness_um": 40, "beamDiameter_um": 80, "preheatTemp_C": 80, "bypassCache": True,
               "enableUq": False, "includeAmbench": False}

    def setUp(self):
        # Another test in a combined run can leave a None entry for the tracer (a "module unavailable" stub);
        # these tests patch the real module, so give each one a clean import table and restore it after.
        patcher = mock.patch.dict(sys.modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        if sys.modules.get("powder_bed_raytracer", 0) is None:
            del sys.modules["powder_bed_raytracer"]

    def _check(self, res):
        self.assertTrue(res["success"], res.get("error"))
        v = res["verdict"]
        th = res["thermal"]
        dh = float(th["processParameters"]["normalizedEnthalpy"])
        self.assertEqual(th["meltPoolGeometry"]["extentStatus"], "computed")
        self.assertGreater(float(th["meltPoolGeometry"]["aspectRatio_L_over_W"]), 3.8)
        # Balling and recoater/distortion never block; keyhole is the only possible blocking gate here.
        gates = {g["id"]: g["status"] for g in v["gates"]}
        self.assertEqual(gates["balling"], "warn")
        self.assertEqual(gates["recoater"], "advisory")
        self.assertEqual(gates["distortion"], "advisory")
        self.assertTrue(set(v["blockingGates"]) <= {"keyhole"}, v["blockingGates"])
        return v, dh

    def test_in718_280_940_keyhole_is_the_only_blocking_gate(self):
        v, dh = self._check(solve_lpbf_build_job(dict(self.PAYLOAD)))
        if dh > 35:
            # Powder ray-traced absorptivity path (dH ~47.3): do-not-print from keyhole alone.
            self.assertEqual(v["verdict"], "do-not-print")
            self.assertEqual(v["blockingGates"], ["keyhole"])
            self.assertEqual(v["dominantGate"], "keyhole")
            blocking_reasons = [r for r in v["reasons"]
                                if not r.startswith("Advisory:") and "not a demonstrated balling" not in r
                                and "literature box" not in r]
            self.assertEqual(len(blocking_reasons), 1, v["reasons"])
            self.assertTrue(blocking_reasons[0].startswith("Keyhole porosity"), blocking_reasons)
        else:
            self.assertEqual(v["verdict"], "risky", (dh, v["reasons"]))
            self.assertEqual(v["blockingGates"], [])

    def test_in718_280_940_flat_absorptivity_path_is_risky(self):
        # Ray tracer unavailable -> frozen solver falls back to flat-plate absorptivity (dH ~30): risky.
        import powder_bed_raytracer as pbr
        with mock.patch.object(pbr, "calculate_powder_bed_absorptivity", side_effect=RuntimeError("no ray tracer")):
            v, dh = self._check(solve_lpbf_build_job(dict(self.PAYLOAD)))
        self.assertLessEqual(dh, 35.0)
        self.assertEqual(v["verdict"], "risky")
        self.assertEqual(v["blockingGates"], [])

    def test_in718_280_940_ray_traced_absorptivity_path_is_keyhole_do_not_print(self):
        # Runs the do-not-print branch on every machine: the frozen ray tracer is patched (not edited) to
        # return the effective absorptivity it produced for IN718 / 80 um beam (0.588, recorded in the
        # STATUS diagnosis for 280 W / 940 mm/s), so dH ~47.3 > 35 regardless of GPU availability.
        import powder_bed_raytracer as pbr
        with mock.patch.object(pbr, "calculate_powder_bed_absorptivity",
                               return_value={"effective_absorptivity": 0.588}):
            v, dh = self._check(solve_lpbf_build_job(dict(self.PAYLOAD)))
        self.assertGreater(dh, 35.0)
        self.assertEqual(v["verdict"], "do-not-print")
        self.assertEqual(v["blockingGates"], ["keyhole"])
        self.assertEqual(v["dominantGate"], "keyhole")
        gates = {g["id"]: g["status"] for g in v["gates"]}
        self.assertEqual([gid for gid, st in gates.items() if st == "fail"], ["keyhole"])


if __name__ == "__main__":
    unittest.main()
