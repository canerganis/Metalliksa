"""Engine-fix lane fx-kinetics: kinetics_ttt_cct_solver honesty fixes (audit D4).

1. The TTT/CCT/phase-fraction/hardness model is a steel template: for non-steel alloys (Inconel 718,
   Ti-6Al-4V, Al 7075) those outputs are None with an explicit status and the reason
   "kinetics model is steel-only". Registry placeholders (alloy_registry.KINETICS_PLACEHOLDERS) are
   never reported.
2. LSW coarsening: K_LSW = 8 gamma D C_e Vm^2 / (9 R T) needs C_e in mol/m^3; the solver used the
   mole fraction (K too small by 1/Vm = 9.1e4). Oracle: an independent SI calculation and the
   audit's own number r(8 h) = 9.6 nm for AISI 4140 at 720 C (old code: 1.5 nm).
3. TTT incubation floor: 32 of 40 TTT points of AISI 4140 are the 1 ms floor; they are flagged
   (floorHit, tttIncubationFloor) and a CCT start the floor or a single integration step drives is
   unavailable instead of "Pearlite starts at ~770 C at every cooling rate".

Run from python/: python -B -m unittest test_kinetics_fx
"""

import json
import math
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import alloy_registry
import kinetics_ttt_cct_solver as kin

HERE = Path(__file__).parent
STEELS = ("AISI 4140", "AISI 4340", "AISI D2")
NON_STEELS = ("Inconel 718", "Ti-6Al-4V", "Al 7075")
DEFAULT_AUST = {"AISI 4140": 860.0, "AISI 4340": 845.0, "AISI D2": 1020.0,
                "Inconel 718": 980.0, "Ti-6Al-4V": 1050.0, "Al 7075": 475.0}
STEEL_ONLY = "kinetics model is steel-only"
R = 8.31446261815324  # J/(mol K), exact SI 2019 N_A * k


def solve(name, cooling=10.0, grain=25.0, aust=None, aging_h=8.0, aging_c=720.0):
    return kin.solve_phase_transformation_kinetics(
        name, cooling, grain, DEFAULT_AUST[name] if aust is None else aust, aging_h, aging_c)


def lsw_si_oracle_nm(q_kj_mol, temp_c, time_h):
    """Independent SI calculation: C_e in mol/m^3 (= x_e / Vm), K in m^3/s, radius in nm."""
    t_k = temp_c + 273.15
    gamma, x_e, v_m, d0, r0 = 0.045, 0.02, 1.1e-5, 1.2e-4, 1.5e-9
    d = d0 * math.exp(-q_kj_mol * 1e3 / (R * t_k))   # m^2/s
    c_e = x_e / v_m                                   # mol/m^3
    k = 8.0 * gamma * d * c_e * v_m ** 2 / (9.0 * R * t_k)  # m^3/s
    return (r0 ** 3 + k * time_h * 3600.0) ** (1.0 / 3.0) * 1e9


def string_values(doc):
    if isinstance(doc, dict):
        for v in doc.values():
            yield from string_values(v)
    elif isinstance(doc, list):
        for v in doc:
            yield from string_values(v)
    elif isinstance(doc, str):
        yield doc


class LswUnitTest(unittest.TestCase):
    def test_audit_oracle_aisi4140_8h(self):
        # audit D4: "r(8 h) 1.50 vs 9.6 nm" (old 1.5 nm because K was 9.1e4 too small)
        res = solve("AISI 4140")
        row = next(r for r in res["lswPrecipitateCoarsening"] if r["agingTime_h"] == 8.0)
        self.assertEqual(row["meanRadius_nm"], 9.59)
        self.assertGreater(row["meanRadius_nm"], 9.5)

    def test_matches_independent_si_oracle_for_every_alloy_and_time(self):
        for name, q in (("AISI 4140", 240.0), ("Inconel 718", 285.0), ("Al 7075", 130.0)):
            res = solve(name)
            self.assertEqual(res["alloyMetadata"]["Q_diff_kJ_mol"], q)
            for row in res["lswPrecipitateCoarsening"]:
                expected = lsw_si_oracle_nm(q, 720.0, row["agingTime_h"])
                self.assertAlmostEqual(row["meanRadius_nm"], expected, delta=0.0051,
                                       msg=f"{name} {row['agingTime_h']} h")

    def test_hand_calculated_values(self):
        # K(AISI 4140, 720 C) = 3.05e-29 m^3/s -> r(100 h) = 22.2 nm; IN718 K = 1.31e-31 m^3/s -> 3.70 nm
        self.assertAlmostEqual(lsw_si_oracle_nm(240.0, 720.0, 100.0), 22.228, places=2)
        self.assertAlmostEqual(lsw_si_oracle_nm(285.0, 720.0, 100.0), 3.698, places=2)
        self.assertEqual(solve("AISI 4140")["lswPrecipitateCoarsening"][-1]["meanRadius_nm"], 22.23)
        self.assertEqual(solve("Inconel 718")["lswPrecipitateCoarsening"][-1]["meanRadius_nm"], 3.7)

    def test_cube_law_is_linear_in_time(self):
        res = solve("AISI 4140")["lswPrecipitateCoarsening"]
        cubes = [(r["agingTime_h"], r["meanRadius_nm"] ** 3 - 1.5 ** 3) for r in res]
        k_t = [c / t for t, c in cubes if t >= 4.0]
        self.assertAlmostEqual(max(k_t) / min(k_t), 1.0, delta=0.01)

    def test_no_silent_k_floor(self):
        # At 300 C the diffusion is negligible: the radius stays r0 (the old 1e-3 nm^3/h floor added growth).
        res = solve("AISI 4140", aging_c=300.0)["lswPrecipitateCoarsening"]
        self.assertTrue(all(r["meanRadius_nm"] == 1.5 for r in res))


class SteelOnlyTest(unittest.TestCase):
    def test_non_steel_outputs_are_unavailable_with_the_reason(self):
        for name in NON_STEELS:
            with self.subTest(alloy=name):
                res = solve(name, cooling=100.0)
                self.assertEqual(res["kineticsModel"]["status"], "unavailable")
                self.assertEqual(res["kineticsModel"]["reason"], STEEL_ONLY)
                self.assertIsNone(res["tttIsothermalCurves"])
                self.assertEqual(res["tttIncubationFloor"]["status"], "unavailable-kinetics-model-steel-only")
                self.assertEqual(len(res["cctContinuousCoolingMap"]), 10)
                for row in res["cctContinuousCoolingMap"]:
                    self.assertEqual(set(row["phaseFractions"]),
                                     {"Martensite_pct", "Bainite_pct", "Pearlite_Ferrite_pct", "RetainedAustenite_pct"})
                    self.assertTrue(all(v is None for v in row["phaseFractions"].values()))
                    for key in ("transformedStartTemp_C", "transformedStartTime_s", "primaryMicrostructure",
                                "predictedHardness_HRC", "predictedHardness_HV"):
                        self.assertIsNone(row[key], key)
                    for key in ("transformedStart_status", "phaseFractions_status", "predictedHardness_HRC_status"):
                        self.assertEqual(row[key], "unavailable-kinetics-model-steel-only")
                    self.assertEqual(row["unavailableReason"], STEEL_ONLY)
                    self.assertEqual(row["predictedHardness_HV_status"], "unavailable-no-verified-table-for-alloy-class")
                gap = res["calphadVsKineticsGap"]
                for block in gap.values():
                    self.assertEqual(block["status"], "unavailable-kinetics-model-steel-only")
                    self.assertEqual(block["reason"], STEEL_ONLY)
                self.assertTrue(all(gap["equilibriumPrediction"][k] is None for k in
                                    ("stablePhasesAtRT", "martensiteFraction", "soluteSupersaturation")))
                reality = gap["kineticRealityAtSelectedCooling"]
                self.assertEqual(reality["coolingRate_C_s"], 100.0)  # the user's own input
                for key in ("criticalCoolingRate_C_s", "isSuppressedEquilibrium", "predictedMartensite_pct",
                            "diffusionSuppressionIndex", "verdict"):
                    self.assertIsNone(reality[key], key)
                self.assertIsNone(res["criticalTransformationTemperatures"]["CriticalCoolingRate_CCR_C_s"])

    def test_old_audit_claims_are_gone(self):
        # audit: IN718 at 100 C/s gave 63 % "martensite"; "Ferrite + Cementite" for every alloy.
        res = solve("Inconel 718", cooling=100.0)
        self.assertIsNone(res["calphadVsKineticsGap"]["kineticRealityAtSelectedCooling"]["predictedMartensite_pct"])
        for name in NON_STEELS:
            res = solve(name)
            res.pop("alloyMetadata")  # registry labels (real IN718 phases such as Gamma Prime) are not model output
            text = " ".join(string_values(res))
            for word in ("Ferrite", "Cementite", "Pearlite", "Bainite", "Martensite", "Equiaxed Alpha", "Gamma Prime"):
                self.assertNotIn(word, text, f"{name}: steel-template word {word!r} in a value")

    def test_steel_class_is_the_registry_descriptor_type(self):
        for name in STEELS + NON_STEELS:
            rid, _legacy, meta = kin.resolve_kinetics_alloy(name)
            self.assertEqual(kin.is_steel_alloy(meta), rid in kin.E140_NON_AUSTENITIC_STEEL_IDS, name)
            self.assertEqual(kin.is_steel_alloy(meta), name in STEELS)

    def test_steel_values_keep_the_model_numbers_and_get_statuses(self):
        res = solve("AISI 4140", cooling=100.0)
        self.assertEqual(res["kineticsModel"]["status"], "available")
        self.assertIsNone(res["kineticsModel"]["reason"])
        self.assertIs(res["kineticsModel"]["illustrativeOnly"], True)
        row = next(r for r in res["cctContinuousCoolingMap"] if r["coolingRate_C_s"] == 100.0)
        self.assertEqual(row["phaseFractions"]["Martensite_pct"], 98.0)
        self.assertEqual(row["predictedHardness_HRC"], 58.0)
        self.assertEqual(row["phaseFractions_status"], "steel-lookup-by-ccr-band-not-computed")
        self.assertEqual(row["predictedHardness_HRC_status"], "steel-lookup-by-ccr-band-not-computed")
        self.assertEqual(res["calphadVsKineticsGap"]["equilibriumPrediction"]["status"],
                         "static-text-not-a-calphad-calculation")
        self.assertEqual(res["calphadVsKineticsGap"]["kineticRealityAtSelectedCooling"]["predictedMartensite_pct"], 96.5)

    def test_registry_placeholders_are_never_reported(self):
        self.assertEqual(alloy_registry.KINETICS_PLACEHOLDERS,
                         {("in718", "Ms_C"), ("in718", "Mf_C"), ("al7075", "Ms_C"), ("al7075", "Mf_C")})
        for name in ("Inconel 718", "Al 7075"):
            res = solve(name)
            crit = res["criticalTransformationTemperatures"]
            self.assertIsNone(crit["Ms_C"])
            self.assertIsNone(crit["Mf_C"])
            self.assertEqual(crit["Ms_C_status"], "unavailable-registry-placeholder")
            self.assertEqual(crit["Mf_C_status"], "unavailable-registry-placeholder")
            self.assertIsNone(res["alloyMetadata"]["Ms_C"])
            self.assertIsNone(res["alloyMetadata"]["Mf_C"])
            self.assertEqual(sorted(res["kineticsModel"]["placeholderParameters"]), ["Mf_C", "Ms_C"])
            self.assertNotIn(-50.0, [res["alloyMetadata"].get("Ms_C"), crit["Ms_C"]])
        # the Ti-6Al-4V Ms/Mf are not flagged: reported as the registry screening value
        ti = solve("Ti-6Al-4V")["criticalTransformationTemperatures"]
        self.assertEqual((ti["Ms_C"], ti["Mf_C"]), (800.0, 650.0))
        self.assertEqual(ti["Ms_C_status"], "registry-screening-value")

    def test_the_flags_drive_the_output(self):
        flags = frozenset(alloy_registry.KINETICS_PLACEHOLDERS | {("aisi4140", "Ms_C")})
        with mock.patch.object(alloy_registry, "KINETICS_PLACEHOLDERS", flags):
            res = solve("AISI 4140")
        self.assertIsNone(res["criticalTransformationTemperatures"]["Ms_C"])
        self.assertIsNone(res["alloyMetadata"]["Ms_C"])
        self.assertEqual(res["criticalTransformationTemperatures"]["Mf_C"], 180.0)

    def test_every_alloy_serialises_without_nan_or_inf(self):
        for name in STEELS + NON_STEELS:
            for cooling in (0.05, 10.0, 2000.0):
                text = json.dumps(solve(name, cooling=cooling), allow_nan=False)
                self.assertNotIn("NaN", text)


class TttFloorTest(unittest.TestCase):
    def test_audit_4140_32_of_40_points_are_the_floor(self):
        res = solve("AISI 4140")
        curves = res["tttIsothermalCurves"]
        self.assertEqual(len(curves), 40)
        flagged = [p for p in curves if p["floorHit"]]
        self.assertEqual(len(flagged), 32)
        self.assertTrue(all(p["tStart_s"] == 0.001 for p in flagged))
        self.assertTrue(all(p["tStart_s"] > 0.001 for p in curves if not p["floorHit"]))
        block = res["tttIncubationFloor"]
        self.assertEqual((block["status"], block["pointCount"], block["floorHitCount"], block["floorValue_s"]),
                         ("floor-hit-points-flagged", 40, 32, 0.001))
        self.assertIn("floor", block["note"])

    def test_point_key_set_is_the_old_one_plus_the_flag(self):
        # No model rework (audit): the TTT numbers equal the base blob's (test_phase6a_t2b_migration);
        # only floorHit is new.
        res = solve("AISI 4140")
        self.assertEqual(list(res["tttIsothermalCurves"][0]),
                         ["temperature_C", "phase", "tStart_s", "t50_s", "tFinish_s", "avramiExponent_n",
                          "drivingForce_DeltaT_C", "floorHit"])

    def test_cct_pearlite_at_770_at_every_rate_is_unavailable(self):
        # audit: "Pearlite starts at ~770 C" at every cooling rate for AISI 4140 up to 500 C/s.
        res = solve("AISI 4140")
        for row in res["cctContinuousCoolingMap"]:
            with self.subTest(rate=row["coolingRate_C_s"]):
                self.assertIsNone(row["transformedStartTemp_C"])
                self.assertIsNone(row["transformedStartTime_s"])
                self.assertIsNone(row["primaryMicrostructure"])
                self.assertEqual(row["transformedStart_status"], "unavailable-ttt-incubation-floor-or-step-limited")
                self.assertIn("1 ms floor", row["unavailableReason"])

    def test_an_accumulated_start_is_still_reported(self):
        # Not everything is blanked: AISI 4140 from 800 C with a 100 um grain at 2000 C/s accumulates its
        # incubation over several steps (no floor point, no single-step crossing).
        res = solve("AISI 4140", aust=800.0, grain=100.0)
        row = next(r for r in res["cctContinuousCoolingMap"] if r["coolingRate_C_s"] == 2000.0)
        self.assertEqual(row["transformedStart_status"], "diffusional-start-scheil-additivity")
        self.assertEqual((row["transformedStartTemp_C"], row["primaryMicrostructure"]), (760.0, "Pearlite"))
        self.assertIsNone(row["unavailableReason"])

    def test_floor_check_uses_the_unrounded_law_value(self):
        steel = kin.resolve_kinetics_alloy("AISI 4140")[2]
        point = kin.calculate_jmak_isothermal_kinetics(700.0, steel, 25.0, "Pearlite")
        self.assertTrue(point["floorHit"] and point["tStart_s"] == 0.001)
        near_ae3 = kin.calculate_jmak_isothermal_kinetics(770.0, steel, 25.0, "Pearlite")
        self.assertFalse(near_ae3["floorHit"])
        self.assertGreater(near_ae3["tStart_s"], 0.001)

    def test_steel_floor_summary_for_all_steels(self):
        for name in STEELS:
            res = solve(name)
            block = res["tttIncubationFloor"]
            self.assertEqual(block["pointCount"], len(res["tttIsothermalCurves"]))
            self.assertEqual(block["floorHitCount"], sum(p["floorHit"] for p in res["tttIsothermalCurves"]))
            self.assertGreater(block["floorHitCount"], 0)


class MainEnvelopeTest(unittest.TestCase):
    def test_stdout_json_has_the_new_keys(self):
        proc = subprocess.run([sys.executable, "-B", "kinetics_ttt_cct_solver.py"], capture_output=True, cwd=str(HERE),
                              input=json.dumps({"alloy": "Inconel 718", "coolingRate_C_s": 100.0}).encode())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(out["kineticsModel"]["reason"], STEEL_ONLY)
        self.assertIsNone(out["tttIsothermalCurves"])
        self.assertIn("provenance", out)


if __name__ == "__main__":
    unittest.main()
