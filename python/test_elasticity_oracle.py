"""Oracle tests of the continuum-elasticity module (python/dft_property_calculator.py, v4.1).

Run from python/: ``python -B -m unittest test_elasticity_oracle``.

Nothing here is a DFT check: the module homogenises supplied single-crystal elastic constants. The
oracles are independent of the module:

* published cubic constants (J. Appl. Phys. 119, 244304 (2016), arXiv:1605.09237, Tables 1-3, the
  experimental column: Cu 168.4/121.4/75.4, Al 107.3/60.08/28.3, Ni 253/152/124 GPa for C11/C12/C44), with
  the textbook closed forms for K, G_V, G_R, E, nu and the Anderson (1963) Debye temperature computed here
  in plain Python from CODATA constants and hard-coded standard atomic weights;
* a trigonal oracle with no table in it: a cubic crystal viewed with [111] along z and [-110] along x IS a
  -3m crystal with C14 != 0, so (a) its rotated tensor (numpy tensor rotation) must equal the module's
  trigonal tensor built from the closed-form constants, and (b) every rotation invariant (K_V, K_R, G_V,
  G_R) and the Young's modulus along the rotated axes must equal the cubic values. A hexagonal treatment
  that drops C14 (the pre-v4.1 behaviour) fails all of these.
"""

import math
import unittest
from unittest.mock import patch

import numpy as np

import dft_property_calculator as dft

H = 6.62607015e-34
KB = 1.380649e-23
NA = 6.02214076e23

# C11, C12, C44 (GPa), density (g/cm^3), standard atomic weight (g/mol), tabulated experimental Debye
# temperature (K; textbook value, used only as a +-8 % sanity band, not as the oracle)
REFERENCE = {
    "Al": ((107.3, 60.08, 28.3), 2.70, 26.982, 428.0),
    "Cu": ((168.4, 121.4, 75.4), 8.96, 63.546, 343.0),
    "Ni": ((253.0, 152.0, 124.0), 8.90, 58.693, 450.0),
}


def cubic_oracle(c11, c12, c44):
    k = (c11 + 2 * c12) / 3
    g_v = (c11 - c12 + 3 * c44) / 5
    g_r = 5 * (c11 - c12) * c44 / (4 * c44 + 3 * (c11 - c12))
    g = (g_v + g_r) / 2
    e = 9 * k * g / (3 * k + g)
    nu = (3 * k - 2 * g) / (2 * (3 * k + g))
    s11 = (c11 + c12) / ((c11 - c12) * (c11 + 2 * c12))
    s12 = -c12 / ((c11 - c12) * (c11 + 2 * c12))
    s44 = 1.0 / c44
    return {"K": k, "G_V": g_v, "G_R": g_r, "G": g, "E": e, "nu": nu, "S11": s11, "S12": s12, "S44": s44}


def debye_oracle(k, g, rho_g_cm3, atomic_mass_g_mol, atoms_per_formula=1.0):
    """Anderson (1963) per-atom Debye temperature, plain arithmetic."""
    rho = rho_g_cm3 * 1000.0
    vl = math.sqrt((k + 4.0 * g / 3.0) * 1e9 / rho)
    vt = math.sqrt(g * 1e9 / rho)
    vm = (((1.0 / vl ** 3) + 2.0 / vt ** 3) / 3.0) ** (-1.0 / 3.0)
    n_density = atoms_per_formula * rho * NA / (atomic_mass_g_mol * 1e-3)
    return (H / KB) * (3.0 * n_density / (4.0 * math.pi)) ** (1.0 / 3.0) * vm


def run(payload):
    return dft.calculate_dft_properties(payload)


def cubic_payload(element, **extra):
    (c11, c12, c44), rho, _, _ = REFERENCE[element]
    payload = {"formula": element, "crystal_system": "Cubic", "density": rho,
               "custom_c_ij": {"c11": c11, "c12": c12, "c44": c44}}
    payload.update(extra)
    return payload


class CubicPublishedConstantsTest(unittest.TestCase):
    def test_moduli_and_debye_match_the_independent_oracle(self):
        for element, ((c11, c12, c44), rho, mass, _) in REFERENCE.items():
            with self.subTest(element=element):
                out = run(cubic_payload(element))
                o = cubic_oracle(c11, c12, c44)
                vrh = out["voigtReussHillModuli"]
                # outputs are rounded to 0.01 GPa (0.001 for nu); allow one display unit
                self.assertAlmostEqual(vrh["bulkModulus_K_VRH_GPa"], o["K"], delta=0.006)
                self.assertAlmostEqual(vrh["bulkModulus_K_Voigt_GPa"], o["K"], delta=0.006)
                self.assertAlmostEqual(vrh["bulkModulus_K_Reuss_GPa"], o["K"], delta=0.006)
                self.assertAlmostEqual(vrh["shearModulus_G_Voigt_GPa"], o["G_V"], delta=0.006)
                self.assertAlmostEqual(vrh["shearModulus_G_Reuss_GPa"], o["G_R"], delta=0.006)
                self.assertAlmostEqual(vrh["shearModulus_G_VRH_GPa"], o["G"], delta=0.006)
                self.assertAlmostEqual(vrh["youngsModulus_E_VRH_GPa"], o["E"], delta=0.02)
                self.assertAlmostEqual(vrh["poissonsRatio_nu"], o["nu"], delta=0.001)
                theta = debye_oracle(o["K"], o["G"], rho, mass)
                self.assertAlmostEqual(out["acousticAndThermalProperties"]["debyeTemperature_K"], theta, delta=0.06)
                # directional E: cubic closed forms, E[100] = 1/S11 and E[111] = 1/(S11 - 2/3 (S11 - S12 - S44/2))
                e_dir = {d["direction"]: d["youngsModulusGPa"] for d in out["directionalYoungsModuli"]}
                self.assertAlmostEqual(e_dir["[100]"], 1.0 / o["S11"], delta=0.006)
                inv_111 = o["S11"] - (2.0 / 3.0) * (o["S11"] - o["S12"] - o["S44"] / 2.0)
                self.assertAlmostEqual(e_dir["[111]"], 1.0 / inv_111, delta=0.006)

    def test_debye_temperature_is_near_the_tabulated_experiment(self):
        # Sanity band only (+-8 %): elastic-constant Debye temperatures differ from the calorimetric ones.
        for element, (_, _, _, experiment) in REFERENCE.items():
            with self.subTest(element=element):
                theta = run(cubic_payload(element))["acousticAndThermalProperties"]["debyeTemperature_K"]
                self.assertLess(abs(theta - experiment) / experiment, 0.08, (element, theta, experiment))

    def test_ni_per_atom_basis_regression(self):
        # Audit D7: with nsites = 4 (the FCC cell) and an atomic molar mass the old code counted 4 atoms per
        # 58.69 g/mol and gave 753 K; per atom the same crystal is 467 K (experiment ~450 K).
        legacy = cubic_payload("Ni", nsites=4, molar_mass=58.69)
        theta = run(legacy)["acousticAndThermalProperties"]["debyeTemperature_K"]
        o = cubic_oracle(*REFERENCE["Ni"][0])
        self.assertAlmostEqual(theta, debye_oracle(o["K"], o["G"], 8.90, 58.693), delta=0.06)
        self.assertLess(abs(theta - 467.0), 1.0)
        self.assertGreater(abs(753.0 - theta), 250.0)
        # the old basis (n = nsites = 4) is exactly what the oracle comparison must reject
        wrong = debye_oracle(o["K"], o["G"], 8.90, 58.69, atoms_per_formula=4.0)
        self.assertGreater(abs(wrong - theta), 250.0)

    def test_mutation_cell_count_basis_is_detected(self):
        o = cubic_oracle(*REFERENCE["Ni"][0])
        expected = debye_oracle(o["K"], o["G"], 8.90, 58.693)
        with patch.object(dft, "composition_basis", lambda formula: (4.0, 58.693)):  # nsites-style count
            mutated = run(cubic_payload("Ni"))["acousticAndThermalProperties"]["debyeTemperature_K"]
        self.assertGreater(abs(mutated - expected), 100.0)

    def test_compound_uses_atoms_per_formula_unit_not_cell_sites(self):
        # Fe3C: 4 atoms per formula unit, 179.55 g/mol per formula unit (the library cell has 16 sites)
        out = run({"formula": "Fe3C (Cementite)"})
        basis = out["acousticAndThermalProperties"]["debyeBasis"]
        self.assertEqual(basis["atomsPerFormulaUnit"], 4.0)
        self.assertAlmostEqual(basis["formulaUnitMolarMass_g_mol"], 3 * 55.845 + 12.011, delta=0.05)
        vrh = out["voigtReussHillModuli"]
        theta = debye_oracle(vrh["bulkModulus_K_VRH_GPa"], vrh["shearModulus_G_VRH_GPa"], 7.68,
                             3 * 55.845 + 12.011, atoms_per_formula=4.0)
        self.assertAlmostEqual(out["acousticAndThermalProperties"]["debyeTemperature_K"], theta, delta=0.5)


class LibraryLookupTest(unittest.TestCase):
    def test_non_exact_formulas_get_no_benchmark(self):
        # Audit D7: 'Al2O3' used to receive aluminium constants and 'TiC' alpha-titanium, 'Fe2O3' alpha-iron.
        for formula in ("Al2O3", "TiC", "Fe2O3", "Ni3Al2", "NiTiCu", "CuZn", "Fe3Cx", "WCo", "ZnO2", "Ti3Al", "Co"):
            with self.subTest(formula=formula):
                out = run({"formula": formula})
                self.assertEqual((out["success"], out["status"]), (False, "unavailable"))
                self.assertEqual(out["unavailableCode"], "NO_ELASTIC_CONSTANTS")
                self.assertNotIn("elasticStiffnessMatrix_Cij_GPa", out)
                self.assertFalse(out["isDft"])
                self.assertIsNone(dft.lookup_library_entry(formula))

    def test_exact_formulas_and_descriptive_suffix_match(self):
        for formula, entry in (("Al", "al"), ("Ni3Al", "ni3al"), ("Ni3Al (gamma prime)", "ni3al"),
                               ("Fe3C (Cementite)", "fe3c"), ("Cu", "cu"), ("ZnO", "zno")):
            with self.subTest(formula=formula):
                self.assertIs(dft.lookup_library_entry(formula), dft.ELASTIC_CONSTANTS_LIBRARY[entry])
        self.assertIsNone(dft.lookup_library_entry("al"))  # case-sensitive: not a different formula
        # LiFePO4 has no sourced constants and is not in the library (no unverified values are offered)
        self.assertIsNone(dft.lookup_library_entry("LiFePO4"))
        self.assertEqual(run({"formula": "LiFePO4"})["unavailableCode"], "NO_ELASTIC_CONSTANTS")
        iso = run({"formula": "LiFePO4", "k_vrh": 96.5, "g_vrh": 52.8, "density": 3.59})
        self.assertEqual(iso["constantsOrigin"], "isotropic-from-supplied-K-G")
        out = run({"formula": "Al"})
        self.assertEqual(out["status"], "available")
        self.assertEqual(out["constantsOrigin"], "builtin-library-exact-match")
        self.assertEqual(out["materialInfo"]["crystal_system"], "Cubic")

    def test_library_phase_must_match(self):
        for payload, code in (({"formula": "Ni3Al", "crystal_system": "Hexagonal"}, "PHASE_MISMATCH"),
                              ({"formula": "Fe", "space_group": "Fm-3m"}, "PHASE_MISMATCH")):
            with self.subTest(payload=payload):
                out = run(payload)
                self.assertEqual((out["status"], out["unavailableCode"]), ("unavailable", code))
        self.assertEqual(run({"formula": "Fe", "space_group": "Im-3m"})["status"], "available")

    def test_labels_never_claim_dft(self):
        out = run({"formula": "Ni3Al"})
        self.assertFalse(out["isDft"])
        self.assertNotIn("DFT", out["sourceNotes"].replace("not a DFT calculation", ""))
        self.assertNotIn("Authentic", out["sourceNotes"])
        self.assertIn("not a DFT calculation", out["label"])
        self.assertEqual(out["referenceStatus"], "experimental-single-crystal")
        self.assertIn("Kayser & Stassis", out["sourceNotes"])
        self.assertEqual(run({"formula": "Fe3C"})["referenceStatus"], "dft-calculation")
        self.assertIn("Jiang", run({"formula": "Fe3C"})["sourceNotes"])
        self.assertIn("Overton & Gaffney", dft.ELASTIC_CONSTANTS_LIBRARY["cu"]["reference"])
        self.assertIn("caveat: secondary-source conflict on C13", run({"formula": "WC"})["sourceNotes"])


# Sourced library constants, restated independently of the module (GPa). Every value was read in the cited
# table: Rayne & Chandrasekhar 1961 / Alers, Neighbours & Sato 1960 via Ledbetter & Reed, JPCRD 2, 531 (1973),
# Tables 5 and 6; Vallin et al. 1964 via arXiv:1605.09237; Featherston & Neighbours 1963 via OSTI 1529600;
# Kayser & Stassis 1981 via Luan et al. 2018; Mercier et al. 1980 via Ren & Sehitoglu 2016; Bateman 1962 via
# Morkoc & Ozgur 2009; Lee & Gilmore 1982 via Kim, Massa & Rohrer 2006; Fisher & Renken 1964 via arXiv:2008.00165;
# Jiang et al. 2008 Table III (energy-strain DFT); Overton & Gaffney 1955 via Ledbetter & Naimon 1974.
SOURCED = {
    "Cu": {"c11": 168.4, "c12": 121.4, "c44": 75.4},
    "Fe": {"c11": 233.1, "c12": 135.4, "c44": 117.8},
    "Ni": {"c11": 250.8, "c12": 150.0, "c44": 123.5},
    "Al": {"c11": 107.3, "c12": 60.08, "c44": 28.3},
    "W": {"c11": 523.27, "c12": 204.53, "c44": 160.72},
    "Ni3Al": {"c11": 224.3, "c12": 148.6, "c44": 125.8},
    "NiTi": {"c11": 162.0, "c12": 129.0, "c44": 35.0},
    "Ti": {"c11": 162.4, "c12": 92.0, "c13": 69.0, "c33": 180.7, "c44": 46.7},
    "ZnO": {"c11": 209.7, "c12": 121.1, "c13": 105.1, "c33": 210.9, "c44": 42.47},
    "WC": {"c11": 720.0, "c12": 254.0, "c13": 267.0, "c33": 972.0, "c44": 328.0},
    "Ti3AlC2": {"c11": 361.0, "c12": 75.0, "c13": 70.0, "c33": 299.0, "c44": 124.0},
    "Fe3C": {"c11": 388.0, "c22": 345.0, "c33": 322.0, "c12": 156.0, "c13": 164.0, "c23": 162.0,
             "c44": 15.0, "c55": 134.0, "c66": 134.0},
}
# Zener ratios 2 C44 / (C11 - C12) of the cubic entries as stated by the reviewer (rounded)
ZENER_REVIEW = {"Fe": 2.41, "Ni": 2.45, "Cu": 3.22, "Al": 1.20, "W": 1.008, "Ni3Al": 3.32, "NiTi": 2.12}
ENTRY_MASS = {"Cu": 63.546, "Fe": 55.845, "Ni": 58.693, "Al": 26.982, "W": 183.84, "Ti": 47.867}


class SourcedLibraryTest(unittest.TestCase):
    def test_every_entry_holds_the_sourced_constants_and_a_citation(self):
        self.assertEqual({e["match"] for e in dft.ELASTIC_CONSTANTS_LIBRARY.values()}, set(SOURCED))
        statuses = {"experimental-single-crystal", "experimental-polycrystal-neutron-diffraction", "dft-calculation"}
        for entry in dft.ELASTIC_CONSTANTS_LIBRARY.values():
            with self.subTest(entry=entry["match"]):
                self.assertEqual(entry["c_ij"], SOURCED[entry["match"]])
                self.assertIn(entry["reference_status"], statuses)
                self.assertGreater(len(entry["reference"]), 30)
                self.assertTrue(entry["density_basis"])
        self.assertEqual(dft.ELASTIC_CONSTANTS_LIBRARY["fe3c"]["reference_status"], "dft-calculation")
        self.assertEqual(dft.ELASTIC_CONSTANTS_LIBRARY["ti3alc2"]["reference_status"],
                         "experimental-polycrystal-neutron-diffraction")
        self.assertIn("C13", dft.ELASTIC_CONSTANTS_LIBRARY["wc"]["reference_note"])
        self.assertIn("saturating", dft.ELASTIC_CONSTANTS_LIBRARY["ni"]["reference_note"])

    def test_mutated_library_value_is_detected(self):
        with patch.dict(dft.ELASTIC_CONSTANTS_LIBRARY["fe3c"]["c_ij"], {"c44": 63.0}):  # the old, unsourced shear
            self.assertNotEqual(dft.ELASTIC_CONSTANTS_LIBRARY["fe3c"]["c_ij"], SOURCED["Fe3C"])

    def test_cubic_entries_moduli_zener_and_per_atom_debye(self):
        for name, c in SOURCED.items():
            if len(c) != 3:
                continue
            with self.subTest(entry=name):
                out = run({"formula": name})
                o = cubic_oracle(c["c11"], c["c12"], c["c44"])
                vrh = out["voigtReussHillModuli"]
                self.assertAlmostEqual(vrh["bulkModulus_K_VRH_GPa"], o["K"], delta=0.006)
                self.assertAlmostEqual(vrh["shearModulus_G_VRH_GPa"], o["G"], delta=0.006)
                zener = 2.0 * c["c44"] / (c["c11"] - c["c12"])
                self.assertAlmostEqual(out["mechanicalIntegrityIndices"]["zenerAnisotropyFactor_AZ"], zener, delta=0.0006)
                self.assertAlmostEqual(zener, ZENER_REVIEW[name], delta=0.012)
                entry = dft.ELASTIC_CONSTANTS_LIBRARY[name.lower()]
                if name in ENTRY_MASS:
                    theta = debye_oracle(o["K"], o["G"], entry["density"], ENTRY_MASS[name])
                else:  # Ni3Al: 4 atoms per formula unit, 3 Ni + 1 Al
                    theta = debye_oracle(o["K"], o["G"], entry["density"], 3 * 58.693 + 26.982, atoms_per_formula=4.0) \
                        if name == "Ni3Al" else None
                if theta is not None:
                    self.assertAlmostEqual(out["acousticAndThermalProperties"]["debyeTemperature_K"], theta, delta=0.15)

    def test_noncubic_voigt_bounds_from_the_sourced_tensors(self):
        # Voigt averages in closed form from the sourced constants (hexagonal: c66 = (c11 - c12) / 2)
        for name, c in SOURCED.items():
            if len(c) != 5:
                continue
            with self.subTest(entry=name):
                c66 = (c["c11"] - c["c12"]) / 2.0
                k_v = (2.0 * c["c11"] + c["c33"] + 2.0 * (c["c12"] + 2.0 * c["c13"])) / 9.0
                g_v = (2.0 * c["c11"] + c["c33"] - (c["c12"] + 2.0 * c["c13"]) + 3.0 * (2.0 * c["c44"] + c66)) / 15.0
                vrh = run({"formula": name})["voigtReussHillModuli"]
                self.assertAlmostEqual(vrh["bulkModulus_K_Voigt_GPa"], k_v, delta=0.006)
                self.assertAlmostEqual(vrh["shearModulus_G_Voigt_GPa"], g_v, delta=0.006)

    def test_cementite_uses_jiangs_axis_order(self):
        c = SOURCED["Fe3C"]
        out = run({"formula": "Fe3C"})
        m = out["elasticStiffnessMatrix_Cij_GPa"]
        self.assertEqual([m[i][i] for i in range(6)], [388.0, 345.0, 322.0, 15.0, 134.0, 134.0])
        self.assertEqual((m[0][1], m[0][2], m[1][2]), (156.0, 164.0, 162.0))  # c12, c13, c23
        k_v = (c["c11"] + c["c22"] + c["c33"] + 2 * (c["c12"] + c["c23"] + c["c13"])) / 9.0
        self.assertAlmostEqual(out["voigtReussHillModuli"]["bulkModulus_K_Voigt_GPa"], k_v, delta=0.006)
        self.assertTrue(out["bornStability"]["isMechanicallyStable"])
        self.assertEqual(out["referenceStatus"], "dft-calculation")

    def test_zno_density_is_the_lattice_density(self):
        a, c_ax = 3.2496, 5.2042  # Angstrom (Morkoc & Ozgur 2009, Table 1.2)
        volume_cm3 = (math.sqrt(3.0) / 2.0) * a * a * c_ax * 1e-24
        rho = 2.0 * (65.38 + 15.999) / (NA * volume_cm3)
        self.assertAlmostEqual(dft.ELASTIC_CONSTANTS_LIBRARY["zno"]["density"], rho, delta=0.01)


class NoSilentDefaultsTest(unittest.TestCase):
    def test_empty_payload_is_unavailable(self):
        out = run({})
        self.assertEqual((out["status"], out["unavailableCode"]), ("unavailable", "NO_ELASTIC_CONSTANTS"))

    def test_missing_molar_basis_is_unavailable_not_iron(self):
        # a formula that is not a composition and no atoms_per_formula_unit + molar_mass: no 55.85 default
        payload = cubic_payload("Ni")
        payload["formula"] = "Custom alloy"
        out = run(payload)
        acoustic = out["acousticAndThermalProperties"]
        self.assertEqual(acoustic["status"], "available")  # velocities need no composition
        self.assertIsNone(acoustic["debyeTemperature_K"])
        self.assertIsNone(acoustic["minimumThermalConductivity_W_mK"])
        self.assertIn("no default molar mass", acoustic["reason"])
        # both supplied: the per-atom oracle
        payload.update(molar_mass=58.693, atoms_per_formula_unit=1)
        theta = run(payload)["acousticAndThermalProperties"]["debyeTemperature_K"]
        o = cubic_oracle(*REFERENCE["Ni"][0])
        self.assertAlmostEqual(theta, debye_oracle(o["K"], o["G"], 8.90, 58.693), delta=0.06)
        # molar_mass alone (ambiguous: atom or formula unit) is not enough
        alone = cubic_payload("Ni", molar_mass=58.693)
        alone["formula"] = "Custom alloy"
        self.assertIsNone(run(alone)["acousticAndThermalProperties"]["debyeTemperature_K"])

    def test_missing_density_is_unavailable(self):
        payload = cubic_payload("Ni")
        payload["formula"] = "CuZn"  # a parsable composition without a library entry: no density of its own
        del payload["density"]
        acoustic = run(payload)["acousticAndThermalProperties"]
        self.assertIsNone(acoustic["debyeTemperature_K"])
        self.assertIsNone(acoustic["longitudinalSoundVelocity_m_s"])
        self.assertIn("density", acoustic["reason"])
        # a library entry supplies its own density; a non-positive density is not clamped to 500 kg/m^3
        self.assertIsNotNone(run({"formula": "Ni"})["acousticAndThermalProperties"]["debyeTemperature_K"])
        self.assertIsNone(run(cubic_payload("Ni", density=-1.0))["acousticAndThermalProperties"]["debyeTemperature_K"])

    def test_missing_custom_constants_are_not_defaulted(self):
        for payload, missing in (({"formula": "X", "crystal_system": "Cubic", "custom_c_ij": {"c12": 100.0, "c44": 50.0}}, "c11"),
                                 ({"formula": "X", "crystal_system": "Tetragonal",
                                   "custom_c_ij": {"c11": 200.0, "c12": 100.0, "c13": 90.0, "c33": 210.0, "c44": 60.0}}, "c66"),
                                 ({"formula": "X", "crystal_system": "Trigonal",
                                   "custom_c_ij": {"c11": 200.0, "c12": 100.0, "c13": 90.0, "c33": 210.0, "c44": 60.0}}, "c14")):
            with self.subTest(missing=missing):
                out = run(payload)
                self.assertEqual((out["status"], out["unavailableCode"]), ("unavailable", "MISSING_ELASTIC_CONSTANTS"))
                self.assertIn(missing, out["reason"])
        out = run({"formula": "X", "custom_c_ij": {"c11": 200.0, "c12": 100.0, "c44": 50.0}})
        self.assertEqual(out["unavailableCode"], "MISSING_CRYSTAL_SYSTEM")

    def test_unknown_crystal_system_is_unavailable_not_isotropic(self):
        out = run({"formula": "X", "crystal_system": "Klingon", "k_vrh": 150.0, "g_vrh": 70.0})
        self.assertEqual((out["status"], out["unavailableCode"]), ("unavailable", "UNSUPPORTED_CRYSTAL_SYSTEM"))
        out = run({"formula": "X", "crystal_system": "Monoclinic", "custom_c_ij": {"c11": 200.0, "c12": 100.0, "c44": 50.0}})
        self.assertEqual(out["unavailableCode"], "UNSUPPORTED_CRYSTAL_SYSTEM")

    def test_isotropic_from_supplied_k_g_and_no_default_k_g(self):
        out = run({"formula": "Ni", "crystal_system": "Cubic", "k_vrh": 180.0, "g_vrh": 80.0, "density": 8.9,
                   "custom_c_ij": {}})
        # {} custom -> library entry (exact formula) wins over the supplied K, G
        self.assertEqual(out["constantsOrigin"], "builtin-library-exact-match")
        out = run({"formula": "Zr3Al2", "k_vrh": 100.0, "g_vrh": 40.0, "density": 5.0})
        self.assertEqual(out["constantsOrigin"], "isotropic-from-supplied-K-G")
        self.assertIn("Isotropic tensor from supplied K_VRH=100.0 GPa", out["sourceNotes"])
        vrh = out["voigtReussHillModuli"]
        self.assertAlmostEqual(vrh["bulkModulus_K_VRH_GPa"], 100.0, delta=0.006)
        self.assertAlmostEqual(vrh["shearModulus_G_VRH_GPa"], 40.0, delta=0.006)
        self.assertEqual(out["mechanicalIntegrityIndices"]["zenerAnisotropyFactor_AZ"], 1.0)
        self.assertEqual(run({"formula": "Zr3Al2", "k_vrh": 100.0})["unavailableCode"], "NO_ELASTIC_CONSTANTS")
        self.assertEqual(run({"formula": "Zr3Al2", "k_vrh": -5.0, "g_vrh": 40.0})["unavailableCode"], "NON_POSITIVE_MODULI")

    def test_material_info_echoes_only_what_was_sent(self):
        info = run({"formula": "Ni"})["materialInfo"]
        for key in ("formation_energy_per_atom", "energy_above_hull", "band_gap", "is_stable", "is_metal"):
            self.assertIsNone(info[key], key)
        info = run({"formula": "Ni", "energy_above_hull": 0.0, "band_gap": 0.0, "formation_energy_per_atom": -0.1})["materialInfo"]
        self.assertEqual((info["is_stable"], info["is_metal"], info["formation_energy_per_atom"]), (True, True, -0.1))

    def test_unstable_tensor_has_no_acoustic_numbers(self):
        out = run({"formula": "X", "crystal_system": "Cubic", "density": 7.0,
                   "custom_c_ij": {"c11": 150.0, "c12": 150.0, "c44": 60.0}})
        self.assertFalse(out["bornStability"]["isMechanicallyStable"])
        self.assertEqual(out["acousticAndThermalProperties"]["status"], "unavailable")
        self.assertIsNone(out["acousticAndThermalProperties"]["debyeTemperature_K"])
        self.assertIsNone(out["directionalYoungsModuli"])
        self.assertEqual(out["directionalYoungsModuliStatus"], "unavailable")


class FormulaParsingTest(unittest.TestCase):
    def test_composition(self):
        self.assertEqual(dft.parse_formula("Fe3C"), {"Fe": 3.0, "C": 1.0})
        self.assertEqual(dft.parse_formula("Ni3Al (gamma prime)"), {"Ni": 3.0, "Al": 1.0})
        self.assertEqual(dft.parse_formula("LiFePO4"), {"Li": 1.0, "Fe": 1.0, "P": 1.0, "O": 4.0})
        for bad in ("Custom HCP", "Zq", "Unobtainium-X", "", None, "Fe 3 C", "fe3c", "Ca(OH)2"):
            self.assertIsNone(dft.parse_formula(bad), bad)
        n, mass = dft.composition_basis("Ni3Al")
        self.assertEqual(n, 4.0)
        self.assertAlmostEqual(mass, 3 * 58.693 + 26.982, delta=0.01)


def rotated_cubic_tensor(c11, c12, c44):
    """Voigt 6x6 of a cubic crystal viewed with x = [-110]/sqrt2, z = [111]/sqrt3 (numpy tensor rotation)."""
    d = np.eye(3)
    c = np.zeros((3, 3, 3, 3))
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for l in range(3):
                    c[i, j, k, l] = (c12 * d[i, j] * d[k, l] + c44 * (d[i, k] * d[j, l] + d[i, l] * d[j, k])
                                     + (c11 - c12 - 2 * c44) * (1.0 if i == j == k == l else 0.0))
    x = np.array([-1.0, 1.0, 0.0]) / math.sqrt(2.0)
    z = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    r = np.array([x, np.cross(z, x), z])
    cr = np.einsum("ia,jb,kc,ld,abcd->ijkl", r, r, r, r, c)
    pairs = [(0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1)]
    return np.array([[cr[a[0], a[1], b[0], b[1]] for b in pairs] for a in pairs])


def trigonal_constants_of_cubic(c11, c12, c44):
    """Closed forms for a cubic crystal with [111] along z and [-110] along x (point group -3m)."""
    return {"c11": (c11 + c12 + 2 * c44) / 2, "c12": (c11 + 5 * c12 - 2 * c44) / 6,
            "c13": (c11 + 2 * c12 - 2 * c44) / 3, "c33": (c11 + 2 * c12 + 4 * c44) / 3,
            "c44": (c11 - c12 + c44) / 3, "c14": -math.sqrt(2.0) * (c11 - c12 - 2 * c44) / 6}


class TrigonalOracleTest(unittest.TestCase):
    C11, C12, C44 = REFERENCE["Ni"][0]

    def payload(self):
        return {"formula": "Ni (rotated)", "crystal_system": "Trigonal", "density": 8.90,
                "custom_c_ij": trigonal_constants_of_cubic(self.C11, self.C12, self.C44)}

    def test_closed_forms_equal_the_numpy_rotation(self):
        voigt = rotated_cubic_tensor(self.C11, self.C12, self.C44)
        c = trigonal_constants_of_cubic(self.C11, self.C12, self.C44)
        self.assertAlmostEqual(voigt[0][3], c["c14"], places=9)
        self.assertAlmostEqual(voigt[1][3], -c["c14"], places=9)
        self.assertAlmostEqual(voigt[4][5], c["c14"], places=9)
        self.assertAlmostEqual(voigt[5][5], (c["c11"] - c["c12"]) / 2, places=9)

    def test_stiffness_matrix_is_the_rotated_cubic_tensor(self):
        out = run(self.payload())
        got = np.array(out["elasticStiffnessMatrix_Cij_GPa"])
        self.assertLess(float(np.max(np.abs(got - rotated_cubic_tensor(self.C11, self.C12, self.C44)))), 0.006)
        self.assertNotEqual(got[0][3], 0.0)

    def test_rotation_invariants_equal_the_cubic_values(self):
        o = cubic_oracle(self.C11, self.C12, self.C44)
        vrh = run(self.payload())["voigtReussHillModuli"]
        self.assertAlmostEqual(vrh["bulkModulus_K_Voigt_GPa"], o["K"], delta=0.006)
        self.assertAlmostEqual(vrh["bulkModulus_K_Reuss_GPa"], o["K"], delta=0.006)
        self.assertAlmostEqual(vrh["shearModulus_G_Voigt_GPa"], o["G_V"], delta=0.006)
        self.assertAlmostEqual(vrh["shearModulus_G_Reuss_GPa"], o["G_R"], delta=0.006)
        self.assertAlmostEqual(vrh["shearModulus_G_VRH_GPa"], o["G"], delta=0.006)

    def test_directional_modulus_uses_the_full_compliance(self):
        # Cartesian z is the cubic [111]; Cartesian x is the cubic [-110] (E[110] by cubic symmetry).
        o = cubic_oracle(self.C11, self.C12, self.C44)
        e100 = 1.0 / o["S11"]
        e110 = 1.0 / (o["S11"] - 0.5 * (o["S11"] - o["S12"] - o["S44"] / 2.0))
        e111 = 1.0 / (o["S11"] - (2.0 / 3.0) * (o["S11"] - o["S12"] - o["S44"] / 2.0))
        s = np.linalg.inv(rotated_cubic_tensor(self.C11, self.C12, self.C44))
        self.assertAlmostEqual(dft.calculate_directional_youngs_modulus_general(s.tolist(), [0, 0, 1]), e111, places=6)
        self.assertAlmostEqual(dft.calculate_directional_youngs_modulus_general(s.tolist(), [1, 0, 0]), e110, places=6)
        out = run(self.payload())
        by_label = {d["direction"]: d for d in out["directionalYoungsModuli"]}
        self.assertAlmostEqual(by_label["[001]"]["youngsModulusGPa"], e111, delta=0.006)
        self.assertAlmostEqual(by_label["[100]"]["youngsModulusGPa"], e110, delta=0.006)
        self.assertGreater(abs(e100 - e110), 1.0)  # the check distinguishes the directions

    def test_hex_style_c14_less_treatment_is_detected(self):
        # Mutation: the pre-v4.1 behaviour (trigonal = hexagonal, C14 dropped) must fail the oracle.
        o = cubic_oracle(self.C11, self.C12, self.C44)
        payload = self.payload()
        payload["custom_c_ij"]["c14"] = 0.0
        dropped = run(payload)["voigtReussHillModuli"]
        self.assertGreater(abs(dropped["shearModulus_G_Reuss_GPa"] - o["G_R"]), 0.5)
        self.assertGreater(abs(dropped["shearModulus_G_VRH_GPa"] - o["G"]), 0.25)

    def test_trigonal_born_criteria_and_instability(self):
        out = run(self.payload())
        names = [c["name"] for c in out["bornStability"]["criteriaChecks"]]
        self.assertIn("Trigonal Shear Coupling C14", names)
        self.assertTrue(out["bornStability"]["isMechanicallyStable"])
        # C14 so large that C44*(C11-C12) < 2*C14^2: the C14 criterion (and the eigenvalues) reject it
        payload = self.payload()
        payload["custom_c_ij"]["c14"] = 200.0
        unstable = run(payload)["bornStability"]
        self.assertFalse(unstable["isMechanicallyStable"])
        failed = [c["name"] for c in unstable["criteriaChecks"] if not c["passed"]]
        self.assertIn("Trigonal Shear Coupling C14", failed)

    def test_c15_class_is_unsupported(self):
        payload = self.payload()
        payload["custom_c_ij"]["c15"] = 5.0
        self.assertEqual(run(payload)["unavailableCode"], "UNSUPPORTED_SYMMETRY_CLASS")


class DirectionalFrameTest(unittest.TestCase):
    def test_non_cubic_directions_are_labelled_cartesian(self):
        out = run({"formula": "Ti"})  # hexagonal library entry
        frames = {d["direction"]: (d["frame"], d["label"]) for d in out["directionalYoungsModuli"]}
        self.assertEqual(frames["[100]"], ("lattice", "[100]"))
        self.assertEqual(frames["[001]"], ("lattice", "[001]"))
        self.assertEqual(frames["[110]"], ("cartesian", "(1,1,0) Cartesian"))
        self.assertIsNone(out["mechanicalIntegrityIndices"]["zenerAnisotropyFactor_AZ"])
        cubic = run({"formula": "Ni"})
        self.assertTrue(all(d["frame"] == "lattice" for d in cubic["directionalYoungsModuli"]))
        self.assertIsNotNone(cubic["mechanicalIntegrityIndices"]["zenerAnisotropyFactor_AZ"])


if __name__ == "__main__":
    unittest.main()
