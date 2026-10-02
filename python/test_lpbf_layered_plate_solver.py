import hashlib
import json
import unittest

from lpbf_simulation import DEFAULTS, run, transient, validate


LAYERED = dict(
    mode="standard", backend="reference", surfaceMode="bare-plate",
    barePlateGeometry="square", study="none", layers=1, tracks=1,
    scanAngle_deg=0, mesh_um=20, beamDiameter_um=20, trackLength_um=100,
    power_W=50, speed_mm_s=10000, maxDt_s=1e-5, sourcePenetration_um=20,
    thermalModelId="layered-plate-enthalpy-v1", plateThickness_um=20,
    supportThickness_um=20, contactResistance_m2K_W=1e-4,
    supportBottomBoundary="adiabatic", incidenceAngle_deg=10,
    incidenceAzimuth_deg=0,
    beamProfileModelId="assumed-oblique-gaussian-normal-plane-v1",
)


class LayeredPlateSolverTests(unittest.TestCase):
    def test_legacy_defaults_and_settings_hash_are_unchanged(self):
        settings, _ = validate({})
        self.assertEqual({key: settings[key] for key in DEFAULTS}, DEFAULTS)
        self.assertFalse((set(LAYERED) - set(DEFAULTS)) & set(settings))
        digest = hashlib.sha256(json.dumps(settings, sort_keys=True, allow_nan=False).encode()).hexdigest()
        # Frozen against the default payload before CPU progress instrumentation.
        self.assertEqual(digest, "6118a1df4bb616c72b5fafee828ebad3f80d96cc78f11ae80695682a74af19f9")

    def test_layered_inputs_are_explicit_and_strict(self):
        with self.assertRaisesRegex(ValueError, "all explicit"):
            validate({"thermalModelId": "layered-plate-enthalpy-v1"})
        for key, value in (("contactResistance_m2K_W", True),
                           ("incidenceAngle_deg", float("nan")),
                           ("plateThickness_um", 0),
                           ("beamProfileModelId", "measured")):
            raw = {**LAYERED, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(raw)
        with self.assertRaisesRegex(ValueError, "requires Inconel 718"):
            validate({**LAYERED, "material": "Ti-6Al-4V"})
        resolved, material = validate(LAYERED)
        self.assertEqual(resolved["thermalModelId"], "layered-plate-enthalpy-v1")
        self.assertEqual(material["materialId"], "in718")

    def test_one_cell_each_layer_transfers_heat_and_closes_both_boundaries(self):
        for boundary in ("adiabatic", "isothermal-at-preheat"):
            with self.subTest(boundary=boundary):
                settings, material = validate({**LAYERED, "supportBottomBoundary": boundary})
                result = (run({**LAYERED, "supportBottomBoundary": boundary})
                          if boundary == "adiabatic" else transient(settings, material))
                self.assertEqual(result["discretization"]["plateCells"], 1)
                self.assertEqual(result["discretization"]["supportCells"], 1)
                self.assertAlmostEqual(result["discretization"]["effectivePlateThickness_um"], 20)
                self.assertGreater(result["supportDiagnostics"]["maximumTemperature_K"], 353.15)
                self.assertTrue(result["supportDiagnostics"]["supportCellsExcludedFromMeltGeometry"])
                self.assertLess(result["energyBalance"]["relativeError"], 1e-12)
                self.assertEqual(result["supportMaterial"]["materialId"], "ss304")
                self.assertIn("not AMB2022-03 measured", result["layeredSensitivity"]["evidenceNote"])
                if boundary == "adiabatic":
                    self.assertEqual(result["solver"]["id"], "layered-enthalpy-fv-1")
                    self.assertEqual(result["coreContract"]["modelId"], "layered-plate-enthalpy-v1")


if __name__ == "__main__":
    unittest.main()
