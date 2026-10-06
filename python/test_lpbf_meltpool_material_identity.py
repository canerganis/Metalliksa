"""Direct melt-pool material identity and legacy IN625 provenance boundary."""

import unittest

from lpbf_thermal_solver import calculate_meltpool_physics


def solve(name, **kwargs):
    return calculate_meltpool_physics(name, 195.0, 800.0, 80.0,
                                      heat_source="rosenthal", **kwargs)


class MeltPoolMaterialIdentity(unittest.TestCase):
    def test_unknown_or_contradictory_identity_never_substitutes_in718(self):
        for name in ("Unobtainium", "IN625/IN718", "Inconel 719", "", None, 718):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Unsupported LPBF material identity"):
                solve(name)
        with self.assertRaisesRegex(ValueError, "Unsupported LPBF material identity"):
            solve("Unobtainium", prop_overrides={"absorptivity_IR": .4})

    def test_known_four_alloy_alias_and_secondary_keep_physics(self):
        canonical = solve("Inconel 718")
        alias = solve("IN718")
        self.assertEqual(alias["processParameters"], canonical["processParameters"])
        self.assertEqual(alias["meltPoolGeometry"], canonical["meltPoolGeometry"])
        self.assertEqual(solve("Ti64")["baseMetal"], "Ti")
        self.assertEqual(solve("CoCrMo")["baseMetal"], "Co")

    def test_secondary_in625_has_explicit_legacy_provenance(self):
        result = solve("Inconel 625")
        self.assertEqual(result["material"], "Inconel 625")
        self.assertEqual(result["processParameters"]["solidConductivity_W_mK"], 9.8)
        self.assertEqual(result["materialEvidence"]["provenanceClass"], "legacy-estimated-secondary")
        self.assertEqual(result["materialEvidence"]["validationStatus"], "unvalidated")
        self.assertIn("SECONDARY_THERMOPHYSICAL_DB", result["materialEvidence"]["propertySource"])
        self.assertFalse(result["materialEvidence"]["usesBoundedIN625Snapshot"])


if __name__ == "__main__":
    unittest.main()
