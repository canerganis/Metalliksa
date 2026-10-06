"""Integration test for 280 W simulation with evaporation heat sink and NIST six-section optical observer."""

import unittest
from lpbf_simulation import run
from lpbf_nist_in718_comparison import (
    compare_nist_in718_optical_geometry,
)
from test_lpbf_nist_in718_comparison import source_binding, TABLE_PATH
import json


class Test280wSimulationIntegration(unittest.TestCase):
    def test_280w_fails_closed_without_evaporation(self):
        # Without evaporationModel flag, standard fail-closed boiling threshold is triggered
        config = {
            "power_W": 280.0,
            "speed_mm_s": 960.0,
            "beamDiameter_um": 67.0,
            "sourcePenetration_um": 40.0,
            "material": "Inconel 718",
            "surfaceMode": "bare-plate",
            "barePlateGeometry": "rectangular-corridor",
            "trackLength_um": 500.0,  # Short track for fast test execution
            "mesh_um": 40.0,
            "maxDt_s": 1e-6,
            "tracks": 1,
            "layers": 1,
            "mode": "standard",
            "backend": "reference",
            "evaporationModel": False,
        }
        with self.assertRaises(ValueError) as ctx:
            run(config)
        self.assertIn("material boiling limit", str(ctx.exception))

    def test_280w_completes_but_withholds_single_track_optical_comparison(self):
        # A completed single-track run must not be promoted to a six-section optical observation.
        config = {
            "power_W": 280.0,
            "speed_mm_s": 960.0,
            "beamDiameter_um": 67.0,
            "sourcePenetration_um": 40.0,
            "material": "Inconel 718",
            "surfaceMode": "bare-plate",
            "barePlateGeometry": "rectangular-corridor",
            "trackLength_um": 500.0,
            "mesh_um": 40.0,
            "maxDt_s": 1e-6,
            "tracks": 1,
            "layers": 1,
            "mode": "standard",
            "backend": "reference",
            "evaporationModel": True,
            "marangoniMultiplier": 2.2,
            "opticalObserver": "nist-six-section",
        }
        result = run(config)
        
        # Verify run finished successfully
        self.assertIn("metrics", result)
        self.assertIn("energyBalance", result)
        
        # Verify peak temperature is bounded at boiling limit (approx 3123.15 K)
        peak_t_k = result["metrics"]["peakTemperature_K"]
        self.assertLessEqual(peak_t_k, 3130.0)
        self.assertGreater(peak_t_k, 2000.0)
        
        # This 500 um track is not the NIST 10 mm, three-track optical operator.
        self.assertNotIn("sixSectionObservation", result)
        table4 = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
        binding = source_binding()
        comparison = compare_nist_in718_optical_geometry(
            result, table4, binding, binding, "0"
        )
        self.assertEqual(comparison["status"], "unavailable")
        self.assertEqual(comparison["validationStatus"], "unvalidated")
        self.assertIsNone(comparison["errors"])
        self.assertIn("NIST six-section operator is not implemented", " ".join(comparison["reasons"]))
        self.assertIn("NIST six-section comparison is disabled", " ".join(comparison["reasons"]))


if __name__ == "__main__":
    unittest.main()
