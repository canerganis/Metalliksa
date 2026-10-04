"""evaporationModel=True is an honest boiling cap: labelled, diagnosed, never an evaporation model.

Fast reference-transient runs on the parity SMALL grid (seconds each)."""
import contextlib
import io
import unittest

from lpbf_simulation import run

SMALL = dict(mode="standard", backend="reference", power_W=80, mesh_um=40, trackLength_um=200,
             cooling_s=.0001, dwell_s=0)


def _run(raw):
    with contextlib.redirect_stdout(io.StringIO()):
        return run(dict(raw))


class BoilingCapHonesty(unittest.TestCase):
    def test_capped_run_is_labelled_and_diagnosed(self):
        result = _run({**SMALL, "evaporationModel": True})
        self.assertIn("boiling-capped", result["label"])
        self.assertIn("not an evaporation model", result["label"])
        self.assertTrue(any(a.startswith("evaporationModel=true:") and "no mass or energy leaves the domain" in a
                            for a in result["assumptions"]), result["assumptions"][:3])
        cap = result["boilingCap"]
        self.assertEqual(cap["modelId"], "boiling-cap-v1")
        self.assertTrue(cap["active"])
        self.assertFalse(cap["energyLeavesDomain"])
        self.assertGreater(cap["cappedSteps"], 0)
        self.assertGreater(cap["maxExcessEnthalpy_J_kg"], 0.0)
        self.assertTrue(0.0 < cap["maxVaporFractionProxy"] <= 1.0)
        self.assertEqual(cap["latentHeatVap_J_kg"], 6400000.0)  # IN718 authority value
        # Honesty line untouched: nothing resolved, still unvalidated.
        self.assertIsNone(result["unresolvedPhysics"]["evaporationLoss"])
        self.assertEqual(result["validationStatus"], "unvalidated")
        self.assertFalse(result["productionReady"])
        self.assertLessEqual(result["energyBalance"]["relativeError"], 0.01)

    def test_latent_heat_of_vaporization_comes_from_the_authority_per_alloy(self):
        ti = _run({**SMALL, "material": "Ti-6Al-4V", "evaporationModel": True})
        ss = _run({**SMALL, "material": "316L Stainless Steel", "evaporationModel": True})
        self.assertEqual(ti["boilingCap"]["latentHeatVap_J_kg"], 8900000.0)
        self.assertEqual(ss["boilingCap"]["latentHeatVap_J_kg"], 6250000.0)

    def test_unsourced_material_cannot_use_the_cap(self):
        from lpbf_material_registry import material
        supplied = {k: v for k, v in material("Inconel 718").items()
                    if k in ("source", "solidus_K", "liquidus_K", "boiling_K", "latentHeat_J_kg", "absorptivity",
                             "emissivity", "dGamma_dT", "table")}
        supplied["source"] = "test: user-supplied table without a latent heat of vaporization"
        with self.assertRaisesRegex(ValueError, "sourced latent heat of vaporization"):
            _run({**SMALL, "evaporationModel": True, "properties": supplied})

    def test_flag_false_result_is_unchanged_in_shape(self):
        result = _run({**SMALL, "power_W": 40})
        self.assertEqual(result["label"], "Unvalidated transient thermal")
        self.assertNotIn("boilingCap", result)
        self.assertEqual(result["assumptions"][1],
                         "No resolved momentum, Marangoni flow, evaporation, recoil, VOF, keyhole or pores.")


if __name__ == "__main__":
    unittest.main()
