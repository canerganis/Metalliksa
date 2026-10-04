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
STUDIO_FIXTURE = HERE.parent / "tests" / "fixtures" / "kinetics-studio-results.json"
# Studio defaults (src/components/PhaseKineticsTTTCCTStudio.tsx ALLOY_OPTIONS): alloy -> (austenitising C, aging C),
# 10 C/s, grain 25 um, aging 8 h. The last two reproduce the former 720 C aging default (LSW above the solvus).
STUDIO_CASES = {
    "aisi4140": ("AISI 4140", 860.0, 720.0), "aisi4340": ("AISI 4340", 845.0, 650.0),
    "aisid2": ("AISI D2", 1020.0, 720.0), "in718": ("Inconel 718", 980.0, 720.0),
    "ti6al4v": ("Ti-6Al-4V", 1050.0, 720.0), "al7075": ("Al 7075", 475.0, 120.0),
    "aisi4340_aging720": ("AISI 4340", 845.0, 720.0), "al7075_aging720": ("Al 7075", 475.0, 720.0),
}


def studio_fixture_results():
    """Real solver output for the Studio render test (tests/phase-kinetics-studio.test.tsx), without timing."""
    out = {}
    for key, (name, aust, aging_c) in STUDIO_CASES.items():
        res = kin.solve_phase_transformation_kinetics(name, 10.0, 25.0, aust, 8.0, aging_c)
        res.pop("computeTimeMs")
        out[key] = res
    return json.loads(json.dumps(out))
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
        # Al 7075 is aged at 120 C (its 720 C default is above the solvus: unavailable, see LswAboveSolvusTest).
        for name, q, aging_c in (("AISI 4140", 240.0, 720.0), ("Inconel 718", 285.0, 720.0), ("Al 7075", 130.0, 120.0)):
            res = solve(name, aging_c=aging_c)
            self.assertEqual(res["alloyMetadata"]["Q_diff_kJ_mol"], q)
            for row in res["lswPrecipitateCoarsening"]:
                expected = lsw_si_oracle_nm(q, aging_c, row["agingTime_h"])
                self.assertAlmostEqual(row["meanRadius_nm"], expected, delta=0.0051,
                                       msg=f"{name} {row['agingTime_h']} h")
                self.assertEqual(row["status"], "generic-constants-illustrative")

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
                crit = res["criticalTransformationTemperatures"]
                self.assertIsNone(crit["CriticalCoolingRate_CCR_C_s"])
                # the steel-template registry echoes are withdrawn in both blocks (fx-kinetics review S3/S4)
                self.assertIsNone(crit["Ae1_C"])
                self.assertEqual(crit["Ae1_C_status"], "unavailable-kinetics-model-steel-only")
                self.assertIsNone(res["alloyMetadata"]["Ae1_C"])
                self.assertIsNone(res["alloyMetadata"]["critical_cooling_rate_C_s"])
                self.assertEqual(crit["CriticalCoolingRate_CCR_status"], "unavailable-kinetics-model-steel-only")
                # the model note does not repeat the reason (the UI prints both)
                self.assertFalse(res["kineticsModel"]["note"].startswith(STEEL_ONLY))
                self.assertFalse(res["tttIncubationFloor"]["note"].startswith(STEEL_ONLY))

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
                self.assertEqual(row["transformedStart_status"], "unavailable-ttt-incubation-law-no-ae3-asymptote")
                self.assertEqual(row["unavailableReason"], "incubation law has no Ae3 asymptote; start not computed")

    def test_no_steel_row_reports_a_diffusional_start(self):
        # fx-kinetics review S1: with no Ae3 asymptote the Scheil start is the first step below Ae3 - 5 K, whatever
        # the time step, so NO steel row reports one (the former 760 C "Pearlite" at 2000 C/s, AISI 4140, aust 800 C,
        # 100 um grain, while the same row's lookup says 98 % martensite, is gone).
        checked = 0
        for name in STEELS:
            for aust_offset in (-60.0, 0.0, 100.0):
                for grain in (5.0, 25.0, 100.0):
                    res = solve(name, grain=grain, aust=DEFAULT_AUST[name] + aust_offset)
                    for row in res["cctContinuousCoolingMap"]:
                        checked += 1
                        self.assertNotIn(row["primaryMicrostructure"], ("Pearlite", "Bainite", "Ferrite"),
                                         (name, aust_offset, grain, row["coolingRate_C_s"]))
                        self.assertIn(row["transformedStart_status"],
                                      ("unavailable-ttt-incubation-law-no-ae3-asymptote",
                                       "athermal-martensite-no-diffusional-start-above-ms"))
        self.assertEqual(checked, 3 * 3 * 3 * 10)
        row = next(r for r in solve("AISI 4140", aust=800.0, grain=100.0)["cctContinuousCoolingMap"]
                   if r["coolingRate_C_s"] == 2000.0)
        self.assertIsNone(row["transformedStartTemp_C"])
        self.assertIsNone(row["primaryMicrostructure"])
        self.assertEqual(row["phaseFractions"]["Martensite_pct"], 98.0)  # the lookup, unchanged

    def test_athermal_row_when_no_diffusional_start_exists_above_ms(self):
        # Austenitised just above Ms (340 C vs Ms 330 C): the law finds no start before Ms: the Ms row stays.
        res = solve("AISI 4140", aust=340.0)
        for row in res["cctContinuousCoolingMap"]:
            if row["transformedStart_status"] == "athermal-martensite-no-diffusional-start-above-ms":
                self.assertEqual((row["transformedStartTemp_C"], row["primaryMicrostructure"]), (330.0, "Martensite (Athermal)"))
                self.assertIsInstance(row["transformedStartTime_s"], float)
                self.assertIsNone(row["unavailableReason"])
                break
        else:
            self.fail("no athermal row for AISI 4140 austenitised at 340 C")

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


class LswAboveSolvusTest(unittest.TestCase):
    """fx-kinetics review S2: no precipitate population at or above the registry Ae3 (steels: Ae1)."""

    LIMIT = {"AISI 4140": 725.0, "AISI 4340": 710.0, "AISI D2": 800.0,  # Ae1 of the steels
             "Inconel 718": 1020.0, "Ti-6Al-4V": 995.0, "Al 7075": 480.0}  # Ae3 of the non-steels

    def test_al7075_studio_default_720_c_is_unavailable(self):
        res = solve("Al 7075")  # 720 C, above its 480 C solvus (and above its liquidus)
        for row in res["lswPrecipitateCoarsening"]:
            self.assertEqual((row["meanRadius_nm"], row["precipitationHardening_MPa"], row["strengtheningMechanism"]),
                             (None, None, None))
            self.assertEqual(row["status"], "unavailable-aging-temperature-at-or-above-solvus")
        block = res["kineticsModel"]["lswPrecipitateCoarsening"]
        self.assertEqual(block["status"], "unavailable-aging-temperature-at-or-above-solvus")
        self.assertIn("720 C is at or above the registry Ae3 (solvus/transus) of 480 C", block["reason"])
        self.assertNotIn("1884", json.dumps(res))  # the old 1.88 um "Orowan" value

    def test_boundary_is_at_or_above_the_registry_temperature(self):
        for name, limit in self.LIMIT.items():
            below = solve(name, aging_c=limit - 0.1)["lswPrecipitateCoarsening"]
            at = solve(name, aging_c=limit)["lswPrecipitateCoarsening"]
            self.assertTrue(all(r["meanRadius_nm"] is not None for r in below), name)
            self.assertTrue(all(r["meanRadius_nm"] is None for r in at), name)

    def test_steels_use_ae1_and_non_steels_only_ae3(self):
        # 4340 (Ae1 710 C) is at the old 720 C default: unavailable; Ti-6Al-4V 720 C is above the Ae1 of its
        # registry row (700 C, a steel concept that is withheld) but below its 995 C transus: available.
        self.assertIsNone(solve("AISI 4340")["lswPrecipitateCoarsening"][0]["meanRadius_nm"])
        self.assertIn("Ae1", solve("AISI 4340")["kineticsModel"]["lswPrecipitateCoarsening"]["reason"])
        self.assertIsNotNone(solve("Ti-6Al-4V")["lswPrecipitateCoarsening"][0]["meanRadius_nm"])
        self.assertIsNotNone(solve("AISI 4140", aging_c=600.0)["lswPrecipitateCoarsening"][0]["meanRadius_nm"])

    def test_available_block_has_no_reason(self):
        block = solve("AISI 4140", aging_c=600.0)["kineticsModel"]["lswPrecipitateCoarsening"]
        self.assertEqual((block["status"], block["reason"]), ("generic-constants-illustrative", None))
        self.assertIn("one molar volume", block["note"])


class SteelTextTest(unittest.TestCase):
    def test_d2_names_carbides_not_cementite(self):
        d2 = solve("AISI D2")["calphadVsKineticsGap"]["equilibriumPrediction"]
        self.assertEqual(d2["stablePhasesAtRT"], "Ferrite + alloy carbides (M7C3 / M23C6)")
        self.assertNotIn("Cementite", d2["stablePhasesAtRT"])
        for name in ("AISI 4140", "AISI 4340"):
            self.assertIn("Cementite", solve(name)["calphadVsKineticsGap"]["equilibriumPrediction"]["stablePhasesAtRT"])


class StudioFixtureTest(unittest.TestCase):
    def test_committed_fixture_is_the_current_solver_output(self):
        committed = json.loads(STUDIO_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(committed, studio_fixture_results(),
                         "tests/fixtures/kinetics-studio-results.json is stale: python -B test_kinetics_fx.py --write-studio-fixture")


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
    if "--write-studio-fixture" in sys.argv:
        STUDIO_FIXTURE.write_text(json.dumps(studio_fixture_results(), indent=1, ensure_ascii=False) + "\n",
                                  encoding="utf-8", newline="\n")
    else:
        unittest.main()
