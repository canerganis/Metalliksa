"""fx-icme (backlog lane 9): phase10_industrial must not invent a defect.

Before the fix an empty defect population got a fictitious 10 um defect "so the formula does
not blow up", which fed the Murakami limit and a '99 % survival' limit. phase9_surrogate needs
scikit-learn and a trained model; it is replaced by a stub, so the test is hermetic.
"""

import json
import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _install_stub(depth_um, std_um=2.0):
    stub = types.ModuleType("phase9_surrogate")
    stub.predict_surrogate = lambda alloy, power, speed, preheat: {
        "depth_um": depth_um, "error_budget": {"depth_std_um": std_um, "confidence_pct": 90.0}}
    sys.modules["phase9_surrogate"] = stub
    sys.modules.pop("phase10_industrial", None)
    import phase10_industrial
    return phase10_industrial


class Phase10DefectTest(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("phase9_surrogate", None)
        sys.modules.pop("phase10_industrial", None)

    def test_no_simulated_defect_is_unavailable_not_a_10_um_defect(self):
        # depth 90 um at a 30 um layer: above the lack-of-fusion line (45 um), below keyhole (120 um).
        mod = _install_stub(90.0)
        res = mod.run_industrial_fatigue_analysis("IN718", 300, 1000, 30.0, 100.0)
        sim, lim = res["Defect_Simulation"], res["Certification_Limits"]
        self.assertEqual(sim["Total_Defects_Found"], 0)
        self.assertIsNone(sim["Max_Simulated_Defect_um"])
        self.assertIsNone(sim["Gumbel_Predicted_Largest_Defect_um"])
        self.assertTrue(sim["Status"].startswith("unavailable:"))
        self.assertIsNone(lim["Expected_Fatigue_Limit_MPa"])
        self.assertIsNone(lim["Design_Limit_MPa"])
        self.assertIsNone(lim["Hardness_Used_HV"])
        self.assertTrue(lim["Status"].startswith("unavailable:"))
        self.assertEqual(res["modelStatus"], "illustrative")
        self.assertNotIn("10.0", json.dumps(res["Defect_Simulation"]))
        json.dumps(res, allow_nan=False)

    def test_sampled_defects_give_limits_with_an_honest_design_limit_label(self):
        # depth 30 um at a 30 um layer: lack of fusion (< 45 um) in about every draw.
        mod = _install_stub(30.0)
        res = mod.run_industrial_fatigue_analysis("IN718", 300, 1000, 30.0, 100.0)
        sim, lim = res["Defect_Simulation"], res["Certification_Limits"]
        self.assertGreater(sim["Total_Defects_Found"], 100)
        self.assertGreater(sim["Max_Simulated_Defect_um"], 5.0)
        self.assertGreater(lim["Expected_Fatigue_Limit_MPa"], 0.0)
        self.assertAlmostEqual(lim["Design_Limit_MPa"], round(0.85 * lim["Expected_Fatigue_Limit_MPa"], 2), places=2)
        self.assertNotIn("99_Percent_Survival_Design_Limit_MPa", lim)
        self.assertIn("not a statistical 99 % survival bound", lim["Design_Limit_Basis"])
        self.assertEqual(res["modelStatus"], "illustrative")
        self.assertIn("not measured defects", res["modelStatusNote"])


if __name__ == "__main__":
    unittest.main()
