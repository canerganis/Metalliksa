import unittest
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from lpbf_adaptive_feedforward import (
    AdaptiveFeedforwardMitigator,
    ScannerProfile,
    ToolpathVector
)

class TestPhase15AdaptiveFeedforward(unittest.TestCase):

    def setUp(self):
        # Scanner profile with realistic acceleration limit: 40,000 mm/s^2
        self.profile = ScannerProfile(accel_max_mms2=40000.0, jump_speed_mms=3000.0)
        self.mitigator = AdaptiveFeedforwardMitigator(self.profile)

    def test_short_vector_power_compensation(self):
        # Short vector: 2 mm at 1000 mm/s (cannot reach 1000 mm/s due to 40,000 mm/s^2 accel limit)
        vec = ToolpathVector(
            x_start=0.0, y_start=0.0, x_end=2.0, y_end=0.0,
            vector_type="hatch", nominal_power_W=300.0, nominal_speed_mms=1000.0
        )
        seg = self.mitigator.compensate_vector(vec)

        # Average speed will be much lower than 1000 mm/s
        self.assertTrue(seg.is_mitigated)
        self.assertLess(seg.compensated_power_W, 300.0)
        self.assertGreater(seg.compensated_power_W, 50.0)
        self.assertIn("S", seg.gcode_command)

    def test_long_vector_preserves_nominal_power(self):
        # Long vector: 50 mm at 1000 mm/s (reaches full cruise velocity)
        vec = ToolpathVector(
            x_start=0.0, y_start=0.0, x_end=50.0, y_end=0.0,
            vector_type="hatch", nominal_power_W=300.0, nominal_speed_mms=1000.0
        )
        seg = self.mitigator.compensate_vector(vec)

        # Average speed is nearly nominal
        self.assertAlmostEqual(seg.compensated_power_W, 300.0, delta=25.0)

    def test_67_degree_interlayer_rotation(self):
        vectors = [
            ToolpathVector(0.0, 0.0, 10.0, 0.0, "hatch", 250.0, 1000.0)
        ]
        # Process layer 1 with 67 degree rotation
        res_l1 = self.mitigator.process_toolpath(vectors, apply_67_deg_rotation=True, layer_index=1)
        self.assertEqual(res_l1["rotation_angle_deg"], 67.0)

        # Process layer 2 with 67 degree rotation -> 134 deg
        res_l2 = self.mitigator.process_toolpath(vectors, apply_67_deg_rotation=True, layer_index=2)
        self.assertEqual(res_l2["rotation_angle_deg"], 134.0)

    def test_gcode_export_format(self):
        vectors = [
            ToolpathVector(0.0, 0.0, 5.0, 0.0, "hatch", 280.0, 1200.0)
        ]
        res = self.mitigator.process_toolpath(vectors)
        gcode = res["mitigated_gcode"]
        self.assertIn("M3 S0", gcode)
        self.assertIn("G1 X", gcode)
        self.assertIn("M5", gcode)

    def test_travel_moves_command_laser_off(self):
        # M3 stays on for the whole layer, so every G0 jump must carry an explicit S0.
        vectors = [
            ToolpathVector(0.0, 0.0, 5.0, 0.0, "hatch", 280.0, 1200.0),
            ToolpathVector(5.0, 0.0, 0.0, 1.0, "jump", 0.0, 3000.0),
            ToolpathVector(0.0, 1.0, 5.0, 1.0, "hatch", 280.0, 1200.0),
        ]
        gcode = self.mitigator.process_toolpath(vectors)["mitigated_gcode"]
        g0_lines = [ln for ln in gcode.splitlines() if ln.startswith("G0")]
        self.assertTrue(g0_lines)
        for ln in g0_lines:
            self.assertTrue(ln.endswith(" S0"), ln)
        self.assertIn("NOT machine-validated", gcode)
        self.assertNotIn("Closed-Loop", gcode)

if __name__ == "__main__":
    unittest.main()
