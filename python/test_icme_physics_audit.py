"""Physics-audit regressions for python/icme_multiscale_pipeline_solver.py (EUQ-9, EUQ-10).

EUQ-10: the weak pair-coupling cutting stress (Brown & Ham 1971, in Ardell, Metall. Trans. A 16 (1985) 2131)
    delta_tau = (gamma/2b) * [ sqrt(8*gamma*f*r / (pi*T)) - f ],  T = G*b^2/2
was coded without the '- f' term: the default IN718 run gave 222.7 MPa instead of 64.1 MPa.
EUQ-9: the Abaqus card wrote *DENSITY in kg/m^3 (8190) next to E in MPa; with mm-N-s-tonne-MPa the
density is 8.19e-9 tonne/mm^3 (Abaqus has no built-in units).
The oracle below recomputes the formula from the inputs the solver prints (G, b, M, r, f), not from its code.
"""

import math
import unittest

import icme_multiscale_pipeline_solver as icme

GAMMA_APB = 0.175  # J/m^2, the model's antiphase-boundary energy


def _run(payload=None):
    return icme.solve_multiscale_pipeline(dict(payload or {}))


def _brown_ham_MPa(out, with_minus_f=True):
    s0 = out["scale0_dftAtomistic"]
    kin = out["scale2_microstructureKinetics"]["precipitationKinetics"]
    G = s0["homogenizedModuli"]["shearModulus_G_GPa"] * 1e9
    b = s0["burgersVector_b_nm"] * 1e-9
    M = s0["peierlsNabarroLatticeFriction"]["taylorFactor_M"]
    r = kin["meanPrecipitateRadius_nm"] * 1e-9
    f = kin["volumeFractionPct"] / 100.0
    T = 0.5 * G * b * b
    root = math.sqrt(8.0 * GAMMA_APB * f * r / (math.pi * T))
    bracket = max(0.0, root - f) if with_minus_f else root
    return M * GAMMA_APB / (2.0 * b) * bracket / 1e6


class BrownHamCuttingTest(unittest.TestCase):
    def test_default_in718_cutting_term_has_the_minus_f(self):
        out = _run()
        kin = out["scale2_microstructureKinetics"]["precipitationKinetics"]
        self.assertAlmostEqual(_brown_ham_MPa(out, with_minus_f=False), 222.7, delta=1.0)  # the old value
        # Printed G, b, r are rounded, so the oracle carries ~0.5 % of rounding.
        self.assertAlmostEqual(kin["shearingStrength_MPa"], _brown_ham_MPa(out), delta=0.01 * kin["shearingStrength_MPa"])
        self.assertAlmostEqual(kin["shearingStrength_MPa"], 64.1, delta=0.2)
        self.assertEqual(kin["activeMechanism"], "Dislocation Particle Shearing (Brown-Ham weak pair-coupling cutting)")
        self.assertEqual(kin["effectivePrecipitationStrengthening_MPa"], kin["shearingStrength_MPa"])

    def test_other_bases_follow_the_same_formula(self):
        for payload in ({"baseMetal": "Fe", "composition_wt": {"C": 0.4, "Cr": 1.0}},
                        {"baseMetal": "Ti", "composition_wt": {"Al": 6.0, "V": 4.0}},
                        {"baseMetal": "Al", "composition_wt": {"Mg": 2.5, "Zn": 5.6}},
                        {"agingTime_h": 2000.0, "agingTemp_C": 900.0}):
            with self.subTest(payload=payload):
                out = _run(payload)
                kin = out["scale2_microstructureKinetics"]["precipitationKinetics"]
                expected = min(850.0, _brown_ham_MPa(out))
                self.assertAlmostEqual(kin["shearingStrength_MPa"], expected, delta=0.01 * max(1.0, expected) + 0.1)

    def test_nonpositive_weak_coupling_bracket_is_not_reported_as_cutting(self):
        # EUQ-10 review: r = 1.5 nm, f = 0.35 gives sqrt(8*gamma*f*r/(pi*T)) < f. The old code floored the
        # bracket to 0 and reported "Brown-Ham weak pair-coupling cutting" with 0.0 MPa and no note.
        out = _run({"composition_wt": {"Ni": 80, "Al": 5, "Ti": 5}, "agingTemp_C": 600, "agingTime_h": 0.1})
        kin = out["scale2_microstructureKinetics"]["precipitationKinetics"]
        self.assertEqual(kin["meanPrecipitateRadius_nm"], 1.5)
        self.assertEqual(kin["volumeFractionPct"], 35.0)
        self.assertEqual(_brown_ham_MPa(out), 0.0)  # bracket <= 0
        self.assertIsNone(kin["shearingStrength_MPa"])
        self.assertTrue(kin["cuttingContributionStatus"].startswith("unavailable_weak_coupling_not_applicable"))
        self.assertNotIn("Shearing", kin["activeMechanism"])
        self.assertTrue(kin["activeMechanism"].startswith("Not estimated"))
        self.assertEqual(kin["effectivePrecipitationStrengthening_MPa"], 0.0)

    def test_positive_bracket_has_no_cutting_status(self):
        kin = _run()["scale2_microstructureKinetics"]["precipitationKinetics"]
        self.assertIsNone(kin["cuttingContributionStatus"])

    def test_comment_no_longer_claims_pi_g_b2(self):
        with open(icme.__file__, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("(pi * G * b^2)", src)


class AbaqusUnitsTest(unittest.TestCase):
    def test_density_is_tonne_per_mm3_with_mpa(self):
        card = _run()["caeExportCards"]["abaqus"].splitlines()
        self.assertIn("** Units: mm, N, s, tonne, MPa (density in tonne/mm^3)", card)
        density = float(card[card.index("*DENSITY") + 1])
        self.assertNotEqual(density, 8190.0)  # the old kg/m^3 value
        self.assertAlmostEqual(density / 8.19e-9, 1.0, places=6)
        e_mpa = float(card[card.index("*ELASTIC, TYPE=ISOTROPIC") + 1].split(",")[0])
        self.assertGreater(e_mpa, 1e5)  # MPa, consistent with tonne/mm^3
        # ANSYS (t/mm^3) and the Abaqus card now agree on the density.
        ansys = _run()["caeExportCards"]["ansys"]
        self.assertIn("MPDATA,DENS,1,,8.1900e-09", ansys)


if __name__ == "__main__":
    unittest.main()
