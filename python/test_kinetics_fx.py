"""Engine-fix lane fx-kinetics: kinetics_ttt_cct_solver honesty fixes (audit D4).

1. The TTT/CCT/phase-fraction/hardness model is a steel template: for non-steel alloys (Inconel 718,
   Ti-6Al-4V, Al 7075) those outputs are None with an explicit status and the reason
   "kinetics model is steel-only". Registry placeholders (alloy_registry.KINETICS_PLACEHOLDERS) are
   never reported.
2. LSW coarsening: K_LSW = 8 gamma D C_e Vm^2 / (9 R T) needs C_e in mol/m^3; the solver used the
   mole fraction (K too small by 1/Vm = 9.1e4). Oracle: an independent SI calculation and the
   audit's own number r(8 h) = 9.6 nm for AISI 4140 at 720 C (old code: 1.5 nm).
3. (superseded by lane kin-li) The steel template with its 1 ms TTT floor is replaced by the Li (1998)
   model (oracle tests: test_kinetics_li1998.py); the tests below keep the steel-only / placeholder / LSW
   behaviour and check that the floor and the cooling-rate-band lookup are gone.

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

    def test_steel_values_come_from_the_li_model_with_statuses(self):
        res = solve("AISI 4140", cooling=100.0)
        self.assertEqual(res["kineticsModel"]["status"], "available")
        self.assertIsNone(res["kineticsModel"]["reason"])
        self.assertIs(res["kineticsModel"]["illustrativeOnly"], True)
        self.assertEqual(res["kineticsModel"]["validationStatus"], "unvalidated")
        row = next(r for r in res["cctContinuousCoolingMap"] if r["coolingRate_C_s"] == 100.0)
        # the former lookup (98 % martensite, 58 HRC) is gone: fractions and hardness are not computed
        self.assertIsNone(row["phaseFractions"]["Martensite_pct"])
        self.assertIsNone(row["predictedHardness_HRC"])
        self.assertEqual(row["phaseFractions_status"], "unavailable-fractions-not-computed")
        self.assertEqual(row["predictedHardness_HRC_status"], "unavailable-fractions-not-computed")
        self.assertEqual(row["primaryMicrostructure"], "Martensite (Athermal)")
        self.assertEqual(res["calphadVsKineticsGap"]["equilibriumPrediction"]["status"],
                         "static-text-not-a-calphad-calculation")
        reality = res["calphadVsKineticsGap"]["kineticRealityAtSelectedCooling"]
        self.assertTrue(reality["isSuppressedEquilibrium"])
        self.assertEqual(reality["predictedMartensite_pct"], 96.5)  # Koistinen-Marburger at 25 C from Ms 328.5 C

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
        # the flagged registry echo is withheld; the Li model's own Ms (composition, Kung-Rayment) is not a
        # registry value and stays
        self.assertIsNone(res["alloyMetadata"]["Ms_C"])
        self.assertEqual(res["kineticsModel"]["placeholderParameters"], ["Ms_C"])
        self.assertEqual(res["criticalTransformationTemperatures"]["Ms_C"], 328.5)
        self.assertEqual(res["alloyMetadata"]["Mf_C"], 180.0)

    def test_every_alloy_serialises_without_nan_or_inf(self):
        for name in STEELS + NON_STEELS:
            for cooling in (0.05, 10.0, 2000.0):
                text = json.dumps(solve(name, cooling=cooling), allow_nan=False)
                self.assertNotIn("NaN", text)


class NoFloorTest(unittest.TestCase):
    """The audit's 1 ms incubation floor (32 of 40 AISI 4140 TTT points) is gone with the Li (1998) law."""

    def test_no_point_is_on_a_floor(self):
        for name in ("AISI 4140", "AISI 4340"):
            res = solve(name)
            curves = res["tttIsothermalCurves"]
            self.assertTrue(curves)
            self.assertTrue(all(p["floorHit"] is False for p in curves))
            self.assertEqual(res["tttIncubationFloor"], {
                "status": "no-floor-li-1998-law", "floorValue_s": None, "pointCount": len(curves),
                "floorHitCount": 0, "note": kin.TTT_NO_FLOOR_NOTE})
            self.assertEqual({p["phase"] for p in curves}, {"Ferrite", "Pearlite", "Bainite"})

    def test_point_key_set_is_kept(self):
        res = solve("AISI 4140")
        self.assertEqual(list(res["tttIsothermalCurves"][0]),
                         ["temperature_C", "phase", "tStart_s", "t50_s", "tFinish_s", "avramiExponent_n",
                          "drivingForce_DeltaT_C", "floorHit"])
        self.assertIsNone(res["tttIsothermalCurves"][0]["avramiExponent_n"])  # S(X), not an Avrami exponent

    def test_cct_pearlite_at_770_at_every_rate_is_gone(self):
        # audit: "Pearlite starts at ~770 C" at every cooling rate for AISI 4140 up to 500 C/s.
        res = solve("AISI 4140")
        rows = res["cctContinuousCoolingMap"]
        self.assertFalse(any(r["primaryMicrostructure"] == "Pearlite" and r["transformedStartTemp_C"] >= 760.0
                             for r in rows))
        self.assertEqual([r["primaryMicrostructure"] for r in rows][-3:], ["Martensite (Athermal)"] * 3)

    def test_athermal_row_above_the_critical_cooling_rate(self):
        res = solve("AISI 4140")
        crit = res["criticalTransformationTemperatures"]
        for row in res["cctContinuousCoolingMap"]:
            if row["coolingRate_C_s"] >= crit["CriticalCoolingRate_CCR_C_s"]:
                self.assertEqual((row["transformedStartTemp_C"], row["primaryMicrostructure"]),
                                 (crit["Ms_C"], "Martensite (Athermal)"))
                self.assertEqual(row["transformedStart_status"], "athermal-martensite-no-diffusional-start-above-ms")
                self.assertIsNone(row["unavailableReason"])
            else:
                self.assertEqual(row["transformedStart_status"], "li1998-additivity-first-diffusional-start")


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
    def test_d2_is_outside_the_li_range_and_unavailable(self):
        res = solve("AISI D2")
        self.assertEqual(res["kineticsModel"]["status"], "unavailable")
        self.assertTrue(res["kineticsModel"]["reason"].startswith("composition outside the Li (1998) model range"))
        eq = res["calphadVsKineticsGap"]["equilibriumPrediction"]
        self.assertIsNone(eq["stablePhasesAtRT"])
        self.assertEqual(eq["status"], "unavailable-composition-outside-li-model-range")
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
