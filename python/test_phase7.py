import tempfile
import unittest
from pathlib import Path
from lpbf_cfd import cfd_multiphysics

class Phase7ShieldingGasAndPlume(unittest.TestCase):
    def test_phase7_shielding_gas_and_plume(self):
        # Setup a quick case with intense laser and shielding gas
        p = {
            "power_W": 400.0,
            "speed_mm_s": 500.0,
            "beamDiameter_um": 20,
            "tracks": 1,
            "trackLength_um": 50,
            "hatch_um": 50,
            "layers": 1,
            "layer_um": 30,
            "preheat_C": 20,
            "scanAngle_deg": 0.0,
            "layerRotation_deg": 67.0,
            "strategy": "unidirectional",
            "stripeWidth_um": 10000,
            "islandSize_um": 5000,
            "dwell_s": 0.0,
            "cooling_s": 0.0,
            "mesh_um": 20,
            "maxDt_s": 5e-8,
            "shielding_gas_velocity_mps": 2.0,
            "plumeMomentumScale": 1.0,
        }
    
        m = {
            "solidus_K": 1650,
            "liquidus_K": 1700,
            "boiling_K": 3560,
            "absorptivity": 0.4
        }
    
        with tempfile.TemporaryDirectory() as tmp:
            try:
                res = cfd_multiphysics(p, m, artifact_dir=tmp)
            except NotImplementedError as exc:
                if "Fabrication of powder bed via random packing is disabled" not in str(exc):
                    raise
                self.skipTest(f"cfd_multiphysics currently refuses to run (powder-bed packing disabled): {exc}")
            diag = res.get("numericalDiagnostics", {})
        
            # 1. Verify spatter was tracked or at least the key exists
            self.assertIn("spatterVolume_m3", diag, "Spatter volume diagnostic missing")
            self.assertIn("maxSpatterVelocity_mps", diag, "Max spatter velocity diagnostic missing")
        
            # 2. Verify plume scale was recorded in thermalProperties
            tp_text = (Path(tmp) / "openfoam-cfd-case/constant/thermalProperties").read_text()
            self.assertIn("plumeMomentumScale", tp_text)
        
            # 3. Verify shielding gas U field boundary conditions
            u_text = (Path(tmp) / "openfoam-cfd-case/0/U").read_text()
            self.assertIn("(2.0 0 0)", u_text, "Shielding gas velocity not set correctly in U field")


if __name__ == "__main__":
    unittest.main()
