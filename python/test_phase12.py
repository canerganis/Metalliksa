import unittest
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from lpbf_toolpath_kinematics import (
    LPBFToolpathParser,
    GalvanometerKinematicsEngine,
    ScannerProfile,
    ToolpathVector
)

class TestPhase12ToolpathKinematics(unittest.TestCase):

    def setUp(self):
        self.profile = ScannerProfile(
            accel_max_mms2=50000.0,   # 50,000 mm/s^2
            jump_speed_mms=3000.0,
            laser_on_delay_us=50.0,
            laser_off_delay_us=50.0,
            mark_delay_us=100.0,
            jump_delay_us=200.0,
            skywriting_enabled=False
        )
        self.engine = GalvanometerKinematicsEngine(self.profile)

    def test_gcode_parser(self):
        gcode = """
        ; Layer 1
        G0 X0.0 Y0.0
        M3 S300
        G1 X10.0 Y0.0 F60000
        G1 X10.0 Y10.0 F60000
        M5
        G0 X0.0 Y0.0
        """
        vectors = LPBFToolpathParser.parse_gcode(gcode, default_power_W=200.0, default_speed_mms=1000.0)
        self.assertEqual(len(vectors), 3) # Jump to start, 2 mark vectors, 1 jump back
        self.assertEqual(vectors[0].vector_type, "hatch")
        self.assertEqual(vectors[0].nominal_power_W, 300.0)
        self.assertEqual(vectors[0].nominal_speed_mms, 1000.0) # 60000 mm/min = 1000 mm/s
        self.assertEqual(vectors[2].vector_type, "jump")

    def test_cli_parser(self):
        cli = """
        $$UNITS/1.0
        $$LAYER/0.04
        $$HATCHES/1, 2, 0.0, 0.0, 5.0, 0.0, 5.0, 1.0, 0.0, 1.0
        """
        vectors = LPBFToolpathParser.parse_cli(cli, default_power_W=250.0, default_speed_mms=800.0)
        self.assertEqual(len(vectors), 2)
        self.assertEqual(vectors[0].x_end, 5.0)
        self.assertEqual(vectors[1].y_end, 1.0)

    def test_trapezoidal_kinematics(self):
        # Long vector: 50 mm at 1000 mm/s, a = 50,000 mm/s^2
        # d_acc = 1000^2 / (2 * 50,000) = 10 mm
        # Total distance (50 mm) > 2 * 10 mm -> Trapezoidal
        vec = ToolpathVector(
            x_start=0.0, y_start=0.0, x_end=50.0, y_end=0.0,
            vector_type="hatch", nominal_power_W=250.0, nominal_speed_mms=1000.0
        )
        seg = self.engine.simulate_vector(vec)
        self.assertEqual(seg.v_peak_mms, 1000.0)
        self.assertAlmostEqual(seg.t_acc_s, 1000.0 / 50000.0, places=5)
        self.assertAlmostEqual(seg.t_dec_s, 1000.0 / 50000.0, places=5)
        self.assertAlmostEqual(seg.t_cruise_s, (50.0 - 20.0) / 1000.0, places=5)

    def test_triangular_kinematics_short_vector(self):
        # Short vector: 4 mm at 1000 mm/s
        # Needs 20 mm for full accel/decel -> Must be triangular
        vec = ToolpathVector(
            x_start=0.0, y_start=0.0, x_end=4.0, y_end=0.0,
            vector_type="hatch", nominal_power_W=250.0, nominal_speed_mms=1000.0
        )
        seg = self.engine.simulate_vector(vec)
        # Peak velocity = sqrt(dist * a) = sqrt(4 * 50,000) = sqrt(200,000) = 447.21 mm/s
        expected_v_peak = math.sqrt(4.0 * 50000.0)
        self.assertAlmostEqual(seg.v_peak_mms, expected_v_peak, places=2)
        self.assertEqual(seg.t_cruise_s, 0.0)

    def test_hotspot_detection_without_skywriting(self):
        # Create a series of very short vectors (simulating tight turnaround corners)
        vectors = [
            ToolpathVector(0.0, 0.0, 1.0, 0.0, "hatch", 300.0, 1200.0),
            ToolpathVector(1.0, 0.0, 1.0, 0.5, "hatch", 300.0, 1200.0),
            ToolpathVector(1.0, 0.5, 0.0, 0.5, "hatch", 300.0, 1200.0)
        ]
        res = self.engine.simulate_toolpath(vectors)
        self.assertGreater(res["hotspot_count"], 0)
        self.assertIn("hotspots", res)

    def test_skywriting_mitigates_energy_spikes(self):
        self.engine.profile.skywriting_enabled = True
        vectors = [
            ToolpathVector(0.0, 0.0, 20.0, 0.0, "hatch", 300.0, 1000.0)
        ]
        res = self.engine.simulate_toolpath(vectors)
        self.assertTrue(res["skywriting_mitigation_active"])

    def test_skywriting_without_cruise_reports_laser_never_fires(self):
        # 15 mm at 1000 mm/s, a=40000 mm/s^2: 25 mm needed to reach speed -> triangular, cruise = 0.
        self.engine.profile.skywriting_enabled = True
        vectors = [ToolpathVector(0.0, 0.0, 15.0, 0.0, "hatch", 280.0, 1000.0)]
        res = self.engine.simulate_toolpath(vectors)
        self.assertEqual(res["total_energy_input_J"], 0.0)
        self.assertEqual(res["hotspot_count"], 0)
        self.assertEqual(res["no_cruise_segment_count"], 1)
        self.assertTrue(res["laser_never_fires"])
        self.assertTrue(any("never fires" in w for w in res["warnings"]))

    def test_skywriting_with_cruise_has_no_warning(self):
        self.engine.profile.skywriting_enabled = True
        vectors = [ToolpathVector(0.0, 0.0, 40.0, 0.0, "hatch", 280.0, 1000.0)]
        res = self.engine.simulate_toolpath(vectors)
        self.assertGreater(res["total_energy_input_J"], 0.0)
        self.assertEqual(res["no_cruise_segment_count"], 0)
        self.assertFalse(res["laser_never_fires"])
        self.assertEqual(res["warnings"], [])

if __name__ == "__main__":
    unittest.main()
