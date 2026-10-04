"""Pourbaix engine v5: the Cr, Mo and Ti tables, their withheld candidate sets and the dataValidity regions.

Run from python/:  python -B -m unittest test_pourbaix_ticrmo

Every expected number below is recomputed here from the cited primary constants (NBS 1982 kJ/mol values read
from the NIST-hosted scan, NECTAR log K values, Wikipedia data-page E0 values, OBIGT cal/mol, llnl.dat log K,
NIST-JANAF kJ/mol) with this module's own constants; neither the engine nor the oracle is used to make an
expected value. Tolerances: line intercepts and E0 1 mV against the recomputation, published E0 cross-checks
10 mV (the verification level V2 criterion), vertical pH lines 0.01, published pKa 0.1.
"""

import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "tools"))

import pourbaix_golden_check as check  # noqa: E402
import pourbaix_oracle as oracle  # noqa: E402
import pourbaix_solver as solver  # noqa: E402
import pourbaix_species_25c as table  # noqa: E402

R, F, T = 8.314462618, 96485.33212, 298.15  # CODATA 2018 printed values (independent of physical_constants)
K_LOG = math.log(10) * R * T / 1000.0       # kJ/mol per log10 unit (5.7080)
K_V = K_LOG / (F / 1000.0)                  # V per pH unit (0.05916)
FK = F / 1000.0
W = -237.129                                # NBS water
INTERCEPT, PUBLISHED_E0, VERTICAL, PKA = 0.001, 0.010, 0.01, 0.1

# NBS 1982 values (kJ/mol) as read from the scan: Table 51 Cr p. 2-197, 52 Mo p. 2-201, 57 Ti p. 2-209
NBS = {"Cr2O3": -1058.1, "CrO4": -727.75, "HCrO4": -764.7, "Cr2O7": -1301.1, "MoO2": -533.01, "MoO3": -667.97,
       "MoO4": -836.3, "rutile": -889.5, "anatase": -884.5, "Ti2O3": -1434.2, "Ti3O5": -2317.4, "TiO": -495.0,
       "TiH2": -80.3}
JANAF = {"Cr2O3": -1053.066, "MoO2": -532.011, "MoO3": -668.079, "rutile": -889.406, "Ti2O3": -1433.829,
         "Ti3O5": -2317.293, "TiO": -513.278, "anatase": -883.266}


def e0(dg_reduction_kj, n):
    """E0 (V) of a reduction with standard reaction Gibbs energy dg (kJ/mol) and n electrons."""
    return -dg_reduction_kj / (n * FK)


def row(element, sid):
    return next(r for r in table.species_rows(element) if r["id"] == sid)


def withheld(element, sid):
    return next(r for r in table.withheld_rows(element) if r["id"] == sid)


class ServedRowsFromPrimaryConstantsTest(unittest.TestCase):
    def test_nbs_rows(self):
        for el, sid, key in (("Cr", "Cr2O3", "Cr2O3"), ("Cr", "CrO4^2-", "CrO4"), ("Cr", "HCrO4-", "HCrO4"),
                             ("Mo", "MoO2", "MoO2"), ("Mo", "MoO3", "MoO3"), ("Mo", "MoO4^2-", "MoO4"),
                             ("Ti", "TiO2", "rutile"), ("Ti", "Ti2O3", "Ti2O3"), ("Ti", "Ti3O5", "Ti3O5")):
            self.assertEqual(row(el, sid)["dfG_kJ_mol"], NBS[key], (el, sid))
            self.assertEqual(row(el, sid)["source"], "N")
        for el in ("Cr", "Mo", "Ti"):
            self.assertEqual(table.water_dfg_kj_mol(el), W)

    def test_mo_protonated_rows_from_crea_2017(self):
        # MoO4 2- + H+ = HMoO4- 4.47; MoO4 2- + 2H+ = H2MoO4 8.12 (NECTAR Mo table, Crea et al. 2017)
        self.assertAlmostEqual(row("Mo", "HMoO4-")["dfG_kJ_mol"], NBS["MoO4"] - 4.47 * K_LOG, delta=1e-6)
        self.assertAlmostEqual(row("Mo", "H2MoO4")["dfG_kJ_mol"], NBS["MoO4"] - 8.12 * K_LOG, delta=1e-6)

    def test_verification_claims_recomputed(self):
        # JANAF deltas quoted in the evidence: V1 rows within 0.5 kJ/mol, V2 rows through the E0 criterion
        for el, sid, key, level in (("Mo", "MoO3", "MoO3", "V1"), ("Ti", "TiO2", "rutile", "V1"),
                                    ("Ti", "Ti2O3", "Ti2O3", "V1"), ("Ti", "Ti3O5", "Ti3O5", "V1")):
            self.assertLess(abs(NBS[key] - JANAF[key]), 0.5, sid)
            self.assertEqual(row(el, sid)["verification"], level)
        # Cr2O3: E0(Cr2O3/Cr) NBS vs JANAF within 10 mV (8.7 mV), KAPL 14 mV is quoted, not used
        e_nbs, e_janaf = e0(3 * W - NBS["Cr2O3"], 6), e0(3 * W - JANAF["Cr2O3"], 6)
        self.assertAlmostEqual(e_nbs, -0.5989, delta=1e-4)
        self.assertAlmostEqual(e_nbs - e_janaf, -0.0087, delta=2e-4)
        self.assertIn("8.7 mV", row("Cr", "Cr2O3")["evidence"])
        # MoO2: E0(MoO2/Mo) -0.1522 V vs -0.15 V (Wikipedia data page)
        self.assertAlmostEqual(e0(2 * W - NBS["MoO2"], 4), -0.15, delta=PUBLISHED_E0)
        # HCrO4- pKa: NBS 6.473 vs Ball & Nordstrom 6.55, Baes & Mesmer 6.51
        pka = (NBS["CrO4"] - NBS["HCrO4"]) / K_LOG
        self.assertAlmostEqual(pka, 6.473, delta=1e-3)
        self.assertAlmostEqual(pka, 6.55, delta=PKA)
        self.assertAlmostEqual(pka, 6.51, delta=PKA)
        # LLNL (llnl.dat) CrO4 2- and Cr2O3 through Cr(s), SUPCRT water and OBIGT O2(aq)
        w_s, o2 = -56687 * 4.184e-3, 3954 * 4.184e-3
        cr3 = -98.6784 * K_LOG + 0.75 * o2 - 1.5 * w_s
        cro4 = cr3 + 2.5 * w_s + 0.75 * o2 + 8.3842 * K_LOG
        cr2o3 = 2 * cro4 - 2 * w_s - 1.5 * o2 - 9.1306 * K_LOG
        self.assertAlmostEqual(cro4, NBS["CrO4"], delta=0.05)
        self.assertAlmostEqual(cr2o3, NBS["Cr2O3"], delta=0.05)
        self.assertAlmostEqual(cro4 - 6.4944 * K_LOG, NBS["HCrO4"], delta=0.2)

    def test_mo_e0_against_the_published_couples(self):
        h2moo4 = NBS["MoO4"] - 8.12 * K_LOG
        self.assertAlmostEqual(e0(NBS["MoO2"] + 2 * W - h2moo4, 2), 0.65, delta=PUBLISHED_E0)  # H2MoO4/MoO2
        self.assertAlmostEqual(e0(4 * W - h2moo4, 6), 0.11, delta=PUBLISHED_E0)                 # H2MoO4/Mo
        self.assertAlmostEqual(e0(NBS["Ti2O3"] + W - 2 * NBS["rutile"], 2), -0.56, delta=PUBLISHED_E0)  # 2TiO2/Ti2O3

    def test_served_rows_are_verified_and_withheld_rows_are_not_served(self):
        for el in ("Cr", "Mo", "Ti"):
            served = {r["id"] for r in table.species_rows(el)}
            for r in table.species_rows(el):
                self.assertIn(r["verification"], ("V1", "V2"), (el, r["id"]))
            for r in table.withheld_rows(el):
                self.assertNotIn(r["id"], served)
                self.assertIn(r["verification"], ("V2", "V3"))
                self.assertTrue(r["evidence"].startswith(("WITHHELD", "EXCLUDED")), (el, r["id"]))
                self.assertTrue(math.isfinite(r["dfG_kJ_mol"]))
        self.assertEqual([r["role"] for r in table.species_rows("Mo")],
                         ["metal", "oxide", "oxide", "anion_high", "anion_high", "anion_high"])


class BoundaryOracleValuesTest(unittest.TestCase):
    """Lines recomputed from the primary constants, compared with the engine."""

    def _line(self, el, a, b, log_a, e0_want, slope_want):
        line = solver.boundary_line(el, a, b, log_a)
        self.assertEqual(line["type"], "sloped", (el, a, b))
        self.assertAlmostEqual(line["E_V_SHE_at_pH0"], e0_want, delta=INTERCEPT, msg=(el, a, b, log_a))
        self.assertAlmostEqual(line["slope_V_per_pH"], slope_want, delta=5e-4, msg=(el, a, b, log_a))

    def test_cr(self):
        # per Cr: CrO1.5 + 3H+ + 3e- = Cr + 1.5H2O
        self._line("Cr", "Cr", "Cr2O3", -6, e0(1.5 * W - NBS["Cr2O3"] / 2, 3), -K_V)
        for la in (-6.0, -2.0):
            # CrO1.5 + 2.5H2O = HCrO4- + 4H+ + 3e-: E = E0 - (4/3) k pH + (k/3) log a
            e_h = (NBS["HCrO4"] - NBS["Cr2O3"] / 2 - 2.5 * W) / (3 * FK) + K_V / 3 * la
            self._line("Cr", "Cr2O3", "HCrO4-", la, e_h, -4 / 3 * K_V)
            e_c = (NBS["CrO4"] - NBS["Cr2O3"] / 2 - 2.5 * W) / (3 * FK) + K_V / 3 * la
            self._line("Cr", "Cr2O3", "CrO4^2-", la, e_c, -5 / 3 * K_V)
        line = solver.boundary_line("Cr", "HCrO4-", "CrO4^2-")
        self.assertAlmostEqual(line["pH"], (NBS["CrO4"] - NBS["HCrO4"]) / K_LOG, delta=1e-6)
        self.assertAlmostEqual(line["pH"], 6.5, delta=0.05)  # Baes & Mesmer / Ball & Nordstrom: 6.51 / 6.55

    def test_mo(self):
        self._line("Mo", "Mo", "MoO2", -6, e0(2 * W - NBS["MoO2"], 4), -K_V)
        for la in (-6.0, -4.0):
            e_m = (NBS["MoO4"] - NBS["MoO2"] - 2 * W) / (2 * FK) + K_V / 2 * la
            self._line("Mo", "MoO2", "MoO4^2-", la, e_m, -2 * K_V)
        h2 = NBS["MoO4"] - 8.12 * K_LOG
        self._line("Mo", "MoO2", "H2MoO4", -6, (h2 - NBS["MoO2"] - 2 * W) / (2 * FK) - 6 * K_V / 2, -K_V)
        self.assertAlmostEqual(solver.boundary_line("Mo", "H2MoO4", "HMoO4-")["pH"], 8.12 - 4.47, delta=1e-9)
        self.assertAlmostEqual(solver.boundary_line("Mo", "HMoO4-", "MoO4^2-")["pH"], 4.47, delta=1e-9)
        # NIST46 (minteq.v4.dat) 4.24 and 4.0: the HMoO4-/MoO4 2- and H2MoO4/HMoO4- edges move by 0.23 / 0.35
        self.assertAlmostEqual(solver.boundary_line("Mo", "HMoO4-", "MoO4^2-")["pH"], 4.24, delta=0.25)

    def test_ti(self):
        self._line("Ti", "Ti", "TiO2", -6, e0(2 * W - NBS["rutile"], 4), -K_V)
        self._line("Ti", "Ti", "Ti2O3", -6, e0(3 * W - NBS["Ti2O3"], 6), -K_V)
        self._line("Ti", "Ti2O3", "TiO2", -6, e0(NBS["Ti2O3"] + W - 2 * NBS["rutile"], 2), -K_V)
        self.assertAlmostEqual(solver.boundary_line("Ti", "Ti", "TiO2")["E_V_SHE_at_pH0"], -1.076, delta=INTERCEPT)

    def test_domains_and_triple_points(self):
        doms = {el: {d["speciesId"] for d in solver.solve_pourbaix_diagram(el, 25, -6, 0, [])["domains"]}
                for el in ("Cr", "Mo", "Ti")}
        self.assertEqual(doms["Cr"], {"Cr", "Cr2O3", "HCrO4-", "CrO4^2-"})
        self.assertEqual(doms["Mo"], {"Mo", "MoO2", "H2MoO4", "HMoO4-", "MoO4^2-"})  # MoO3 below 10^-3.93 M: none
        self.assertEqual(doms["Ti"], {"Ti", "Ti2O3", "TiO2"})                       # Ti3O5 never has a domain
        # Cr2O3 / HCrO4- / CrO4 2- triple point at the pKa
        b = {x["id"]: x for x in solver.compute_boundaries("Cr", -6.0)}
        ph = (NBS["CrO4"] - NBS["HCrO4"]) / K_LOG
        e = (NBS["CrO4"] - NBS["Cr2O3"] / 2 - 2.5 * W) / (3 * FK) - 2 * K_V - 5 / 3 * K_V * ph
        end = b["Cr2O3__HCrO4-"]["points"][1]
        self.assertAlmostEqual(end["pH"], ph, delta=VERTICAL)
        self.assertAlmostEqual(end["E_V_SHE"], e, delta=0.002)
        # Mo: Mo / MoO2 / MoO4 2- meet at pH where -0.1522 - k pH = E(MoO2/MoO4)
        e_moo2 = e0(2 * W - NBS["MoO2"], 4)
        e_moo4 = (NBS["MoO4"] - NBS["MoO2"] - 2 * W) / (2 * FK) - 3 * K_V
        ph_t = (e_moo4 - e_moo2) / (2 * K_V - K_V)
        mo = {x["id"]: x for x in solver.compute_boundaries("Mo", -6.0)}
        self.assertAlmostEqual(mo["Mo__MoO2"]["points"][1]["pH"], ph_t, delta=VERTICAL)
        self.assertAlmostEqual(ph_t, 14.55, delta=0.01)

    def test_mo3_and_moo3_numbers(self):
        h2 = NBS["MoO4"] - 8.12 * K_LOG
        self.assertAlmostEqual(-(h2 - NBS["MoO3"] - W) / K_LOG, -3.93, delta=0.01)  # MoO3 + H2O = H2MoO4
        mo3 = h2 - 4 * W - 3 * FK * 0.43
        self.assertAlmostEqual(withheld("Mo", "Mo3+[CRC]")["dfG_kJ_mol"], mo3, delta=1e-6)
        self.assertAlmostEqual(mo3 / (3 * FK), -0.200, delta=0.005)  # E0(Mo3+/Mo) of the same table: -0.200 V


class WithheldCandidatesTest(unittest.TestCase):
    def test_cr3_spread_in_the_text_is_the_spread_of_the_rows(self):
        cr3 = {k: withheld("Cr", f"Cr3+[{k}]")["dfG_kJ_mol"] for k in ("CRC", "SSWS97", "LLNL", "BN98")}
        self.assertAlmostEqual(cr3["CRC"], 3 * FK * -0.74, delta=1e-6)
        self.assertAlmostEqual(cr3["SSWS97"], -49300 * 4.184e-3, delta=1e-6)
        self.assertAlmostEqual(cr3["BN98"], (-8.52 * K_LOG - 3 * W + NBS["Cr2O3"]) / 2, delta=1e-6)
        self.assertAlmostEqual(min(cr3.values()), -214.2, delta=0.05)
        self.assertAlmostEqual(max(cr3.values()), -195.1, delta=0.05)
        spread_mv = (max(cr3.values()) - min(cr3.values())) / (3 * FK) * 1000
        self.assertAlmostEqual(spread_mv, 66, delta=0.5)
        for text in (table.ELEMENT_SET["Cr"][2], withheld("Cr", "Cr3+[CRC]")["evidence"]):
            self.assertIn("-214.2", text)
            self.assertIn("-195.1", text)
            self.assertIn("66 mV", text)
        # LLNL's own Cr3+/Cr2+ couple against the measured -0.407 V
        llnl = withheld("Cr", "Cr2+[LLNL]")["dfG_kJ_mol"] - cr3["LLNL"]
        self.assertAlmostEqual(-llnl / FK, -0.504, delta=0.001)

    def test_ti_candidates(self):
        self.assertAlmostEqual(withheld("Ti", "TiO2+[CRC]")["dfG_kJ_mol"], W - 4 * FK * 0.93, delta=1e-6)
        self.assertAlmostEqual(withheld("Ti", "TiO2+[CRC]")["dfG_kJ_mol"], -596.05, delta=0.01)
        self.assertAlmostEqual(withheld("Ti", "TiO2+[CRC-b]")["dfG_kJ_mol"], 3 * FK * -1.37 + W + FK * 0.19, delta=1e-6)
        self.assertAlmostEqual(withheld("Ti", "TiO2+[CRC-b]")["dfG_kJ_mol"], -615.35, delta=0.01)
        self.assertAlmostEqual(NBS["TiO"] - JANAF["TiO"], 18.28, delta=0.01)
        self.assertAlmostEqual(withheld("Ti", "Ti4+[BE16]")["dfG_kJ_mol"], NBS["rutile"] - 2 * W + 3.56 * K_LOG,
                               delta=1e-6)
        self.assertAlmostEqual(withheld("Ti", "TiO(OH)3-[BE16]")["dfG_kJ_mol"],
                               NBS["rutile"] + 2 * W + (9.02 + 11.9) * K_LOG, delta=1e-6)

    def test_every_candidate_set_member_is_a_withheld_row(self):
        for el in ("Cr", "Mo", "Ti"):
            ids = {r["id"] for r in table.withheld_rows(el)}
            for cset in table.candidate_sets(el):
                self.assertTrue(set(cset["speciesIds"]) <= ids, cset["id"])
            self.assertEqual([c["id"] for c in table.candidate_sets(el)], list(oracle.CANDIDATES[el]))
        for el in ("Fe", "Ni", "Cu", "Zn", "Mg", "Al"):
            self.assertEqual(table.candidate_sets(el), [])

    def test_regions_equal_the_oracle_and_flags_are_brute_force(self):
        for el in ("Cr", "Mo", "Ti"):
            lo, hi = table.activity_range(el)
            for la in (lo, hi):
                got = solver.compute_withheld_regions(el, la)
                want = oracle.withheld_polygons(el, la)
                self.assertEqual([(r["candidateSet"], r["speciesId"]) for r in got], [(a, b) for a, b, _ in want])
                for r, (_, _, poly) in zip(got, want):
                    pts = [(q["pH"], q["E_V_SHE"]) for q in r["polygon"]]
                    self.assertIsNone(check._match_vertices(check._dedupe(pts), check._dedupe(poly)), r["speciesId"])
                for ph in [x * 0.37 - 2 for x in range(49)]:
                    for e in [y * 0.113 - 3 for y in range(49)]:
                        self.assertEqual([h[1] for h in solver.withheld_species_at(el, ph, e, la)],
                                         [h[1] for h in oracle.withheld_hits(el, ph, e, la)], (el, la, ph, e))

    def test_free_ph_windows_at_the_default_activity(self):
        # inside the water window, pH ranges without any withheld region (a = 1e-6)
        want = {"Cr": [[4.778, 14.405]], "Mo": [[1.991, 16.0]], "Ti": [[0.909, 14.92]]}
        for el, w in want.items():
            got = solver.free_ph_windows(solver.compute_withheld_regions(el, -6.0))
            self.assertEqual(len(got), len(w), el)
            for (a, b), (c, d) in zip(got, w):
                self.assertAlmostEqual(a, c, delta=0.001)
                self.assertAlmostEqual(b, d, delta=0.001)
            self.assertEqual(len(check._oracle_free_windows(el, -6.0)), len(w))
        # Cr acid edge: CrOH2+ (CRC set) / Cr2O3 at 1e-6: CrO1.5 + 2H+ = CrOH2+ + 0.5H2O
        cr3 = 3 * FK * -0.74
        croh = cr3 + W + 3.60 * K_LOG  # Cr3+ + H2O = CrOH2+ + H+, log K -3.60
        log_k = -(croh + 0.5 * W - NBS["Cr2O3"] / 2) / K_LOG
        self.assertAlmostEqual((log_k + 6) / 2, 4.778, delta=0.002)
        # Cr alkaline edge: Cr(OH)4- (CRC) / Cr2O3 at 1e-6: CrO1.5 + 2.5H2O = Cr(OH)4- + H+
        croh4 = cr3 + 4 * W + 27.56 * K_LOG
        log_k4 = -(croh4 - NBS["Cr2O3"] / 2 - 2.5 * W) / K_LOG
        self.assertAlmostEqual(-6 - log_k4, 14.405, delta=0.002)
        # Ti alkaline edge: TiO(OH)3- (Brown & Ekberg) / rutile: pH = log a - log K, log K = -9.02 - 11.9
        self.assertAlmostEqual(-6 + 9.02 + 11.9, 14.92, delta=1e-9)

    def test_tih2_covers_the_whole_ti_metal_domain(self):
        # Ti + 2H+ + 2e- = TiH2 lies at E = -dfG/2F - k pH = 0.416 - k pH, above every Ti/oxide line
        self.assertAlmostEqual(-NBS["TiH2"] / (2 * FK), 0.416, delta=0.001)
        out = solver.solve_pourbaix_diagram("Ti", 25, -6, 0, [])
        ti = next(d for d in out["domains"] if d["speciesId"] == "Ti")
        poly = [(q["pH"], q["E_V_SHE"]) for q in ti["polygon"]]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        for ph, e in poly + [(cx, cy)]:
            ph, e = 0.999 * ph + 0.001 * cx, 0.999 * e + 0.001 * cy  # just inside the vertex
            self.assertIn(("Ti-hydride", "TiH2"), solver.withheld_species_at("Ti", ph, e, -6.0))

    def test_point_flags_and_categories(self):
        pts = [{"id": "cr_acid", "ph": 2.0, "potential_V": 0.0}, {"id": "cr_neutral", "ph": 7.0, "potential_V": 0.2},
               {"id": "cr_trans", "ph": 7.0, "potential_V": 1.0}]
        out = solver.solve_pourbaix_diagram("Cr", 25, -6, 0, pts)
        got = {p["id"]: (p["dominantSpeciesId"], p["category"], p["insideWithheldDataRegion"])
               for p in out["experimentalOverlay"]["points"]}
        self.assertEqual(got["cr_acid"], ("Cr2O3", "Passivation (thermodynamic)", True))
        self.assertEqual(got["cr_neutral"], ("Cr2O3", "Passivation (thermodynamic)", False))
        self.assertEqual(got["cr_trans"], ("CrO4^2-", "Transpassive", False))
        self.assertEqual(out["experimentalOverlay"]["points"][0]["withheldDataSpeciesIds"],
                         ["Cr3+[CRC]", "Cr3+[SSWS97]", "Cr3+[LLNL]", "Cr3+[BN98]"])
        self.assertIn("1 point(s) lie in a withheld-data region", out["experimentalOverlay"]["overallTrajectoryDiagnosis"])
        mo = solver.solve_pourbaix_diagram("Mo", 25, -6, 0, [{"ph": 7, "potential_V": 0.2}, {"ph": 7, "potential_V": -0.4},
                                                             {"ph": 2, "potential_V": 0.6}])
        self.assertEqual([p["dominantSpeciesId"] for p in mo["experimentalOverlay"]["points"]],
                         ["MoO4^2-", "MoO2", "H2MoO4"])
        ti = solver.solve_pourbaix_diagram("Ti", 25, -6, 0, [{"ph": 7, "potential_V": 0.2}, {"ph": 7, "potential_V": -1.8}])
        p = ti["experimentalOverlay"]["points"]
        self.assertEqual((p[0]["dominantSpeciesId"], p[0]["insideWithheldDataRegion"]), ("TiO2", False))
        self.assertEqual((p[1]["dominantSpeciesId"], p[1]["insideWithheldDataRegion"]), ("Ti", True))
        self.assertIn("TiH2", p[1]["withheldDataSpeciesIds"])
        for doc in (out, mo, ti):
            self.assertIsNone(doc["parameters"]["standardE0_V"])
            self.assertEqual(check.document_problems(
                {"element": doc["element"], "parameters": doc["parameters"],
                 "experimentalOverlay": {"points": doc["experimentalOverlay"]["points"]}}, json.loads(json.dumps(doc))),
                {s: [] for s in check.SECTIONS})


class GuardRejectsWrongV5DataTest(unittest.TestCase):
    """tools/pourbaix_golden_check (used for any future re-bless) rejects forged Cr/Mo/Ti documents."""

    def _doc(self, el, la):
        pts = [{"id": "a", "name": "a", "ph": 2.0, "potential_V": 0.0}, {"id": "b", "name": "b", "ph": 7.0, "potential_V": -1.8}]
        doc = json.loads(json.dumps(solver.solve_pourbaix_diagram(el, 25.0, la, 0.0, pts)))
        old = {"element": el, "parameters": doc["parameters"],
               "experimentalOverlay": {"points": json.loads(json.dumps(doc["experimentalOverlay"]["points"]))}}
        return old, doc

    def test_mutants_are_rejected(self):
        def region_vertex(d):
            d["dataValidity"]["regions"][0]["polygon"][1]["pH"] += 2e-4

        def region_dropped(d):
            d["dataValidity"]["regions"].pop()

        def flag_flip(d):
            cell = next(c for c in d["stabilityFieldGrid"] if c["insideWithheldDataRegion"])
            cell["insideWithheldDataRegion"] = False

        def point_ids(d):
            d["experimentalOverlay"]["points"][0]["withheldDataSpeciesIds"] = []

        def set_member(d):
            d["dataValidity"]["candidateSets"][0]["speciesIds"].pop()

        def withheld_level(d):
            d["speciesTable"]["withheldSpecies"][0]["verification"] = "V2"

        def window(d):
            d["dataValidity"]["pHWindowsFreeOfRegionsInsideWater"][0][0] += 0.01

        def range_(d):
            d["dataValidity"]["activityRange_log10"][1] -= 1.0

        def served_value(d):
            d["speciesTable"]["species"][1]["dfG_kJ_mol"] += 1e-3

        for el, la in (("Cr", -6.0), ("Ti", -6.0), ("Mo", -4.0)):
            old, base = self._doc(el, la)
            self.assertEqual({k: v for k, v in check.document_problems(old, base).items() if v}, {}, el)
            for mutate in (region_vertex, region_dropped, flag_flip, point_ids, set_member, withheld_level, window,
                           range_, served_value):
                if mutate is point_ids and not base["experimentalOverlay"]["points"][0]["withheldDataSpeciesIds"]:
                    continue
                doc = json.loads(json.dumps(base))
                mutate(doc)
                problems = check.document_problems(old, doc)
                self.assertTrue(any(problems.values()), (el, mutate.__name__))


class ActivityRangeTest(unittest.TestCase):
    def _first_log_a_with_domain(self, element, extra):
        sp = dict(oracle.DATA[element]["sp"])
        sp.update(extra)
        la = -6.0
        while la <= 0.0:
            c = oracle.coeffs_of(sp, W, la)
            if any(k in extra for k in oracle._polygons_of(c)):
                return la
            la = round(la + 0.01, 2)
        return None

    def test_polynuclear_thresholds_are_above_the_limits(self):
        cr2o7_nbs = self._first_log_a_with_domain("Cr", {"Cr2O7^2-": (2, 7, 0, -2, NBS["Cr2O7"], "aq", "anion_high")})
        cr2o7_bn = self._first_log_a_with_domain(
            "Cr", {"Cr2O7^2-": (2, 7, 0, -2, 2 * NBS["CrO4"] - W - 14.7 * K_LOG, "aq", "anion_high")})
        self.assertAlmostEqual(cr2o7_nbs, -1.54, delta=0.02)
        self.assertAlmostEqual(cr2o7_bn, -1.75, delta=0.02)
        hepta = {n: (7, 24, h, z, 7 * NBS["MoO4"] - 4 * W - lk * K_LOG, "aq", "anion_high")
                 for n, h, z, lk in (("Mo7O24", 0, -6, 51.93), ("HMo7O24", 1, -5, 58.90), ("H2Mo7O24", 2, -4, 64.63),
                                     ("H3Mo7O24", 3, -3, 68.68))}
        mo7 = self._first_log_a_with_domain("Mo", hepta)
        self.assertAlmostEqual(mo7, -3.53, delta=0.02)
        self.assertEqual(table.activity_range("Cr"), (-6.0, -2.0))
        self.assertEqual(table.activity_range("Mo"), (-6.0, -4.0))
        self.assertEqual(table.activity_range("Ti"), (-6.0, 0.0))
        self.assertLess(table.activity_range("Cr")[1], cr2o7_bn)
        self.assertLess(table.activity_range("Mo")[1], mo7)

    def test_requests_outside_the_element_range_are_refused(self):
        for el, bad in (("Cr", -1.9), ("Cr", 0.0), ("Mo", -3.9), ("Mo", -3.0), ("Ti", 0.1), ("Ti", -6.1)):
            with self.assertRaises(solver.ValidationError) as ctx:
                solver.solve_pourbaix_diagram(el, 25.0, bad, 0.0, [])
            self.assertEqual((ctx.exception.code, ctx.exception.field), ("OUT_OF_RANGE", "ionActivity_log10"))
        for el, good in (("Cr", -2.0), ("Mo", -4.0), ("Ti", 0.0)):
            out = solver.solve_pourbaix_diagram(el, 25.0, good, 0.0, [])
            self.assertEqual(out["model"]["dissolvedActivityRange_log10"], list(table.activity_range(el)))
            self.assertEqual(out["dataValidity"]["activityRange_log10"], list(table.activity_range(el)))

    def test_json_carries_ranges_candidates_and_unsourced_species(self):
        doc = json.loads(table.GENERATED_JSON.read_text(encoding="utf-8"))
        for el in ("Cr", "Mo", "Ti"):
            e = doc["elements"][el]
            self.assertTrue(e["available"])
            self.assertEqual(e["activityLog10Range"], list(table.activity_range(el)))
            self.assertEqual(e["candidateSets"], table.candidate_sets(el))
            self.assertEqual([w["id"] for w in e["withheldSpecies"]], [r["id"] for r in table.withheld_rows(el)])
            self.assertIsNone(e["referenceCation"])
        self.assertEqual([u["formula"] for u in doc["elements"]["Mo"]["unsourcedSpecies"]], ["MoO₂²⁺", "Mo(V)"])


if __name__ == "__main__":
    unittest.main()
