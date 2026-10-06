"""Oracles for cnls_fitting_solver input validation, the Wo/Ws convention and the
Hsu-Mansfeld / Hirschorn duplicate.

The Wo/Ws reference formulas are those of impedance.py (ECSHackWeek/impedance.py,
impedance/models/circuits/elements.py): Wo = Z0 / (sqrt(j w tau) * tanh(sqrt(j w tau)))
(open terminus, coth form) and Ws = Z0 * tanh(sqrt(j w tau)) / sqrt(j w tau) (short
terminus). Synthetic numerical checks only, not experimental validation.
"""
import json
import math
import os
import subprocess
import sys
import unittest

import numpy as np

import cnls_fitting_solver as solver
import input_validation

HERE = os.path.dirname(os.path.abspath(__file__))
FREQS = np.logspace(-3, 5, 41)
OMEGA = 2.0 * np.pi * FREQS


def impedance_py_wo(z0, tau, omega):
    root = np.sqrt(1j * omega * tau)
    return z0 / (root * np.tanh(root))


def impedance_py_ws(z0, tau, omega):
    root = np.sqrt(1j * omega * tau)
    return z0 * np.tanh(root) / root


class WarburgConventionTests(unittest.TestCase):
    def test_wo_is_the_open_coth_element_and_ws_the_short_tanh_element(self):
        for z0, tau in ((100.0, 0.5), (7.5, 12.0), (3000.0, 1e-3)):
            with self.subTest(z0=z0, tau=tau):
                params = {"r": z0, "tau": tau}
                for name in ("Wo", "OpenWarburg"):
                    np.testing.assert_allclose(solver.evaluate_element_impedance(name, params, OMEGA),
                                               impedance_py_wo(z0, tau, OMEGA), rtol=1e-9, atol=1e-12)
                for name in ("Ws", "ShortWarburg"):
                    np.testing.assert_allclose(solver.evaluate_element_impedance(name, params, OMEGA),
                                               impedance_py_ws(z0, tau, OMEGA), rtol=1e-9, atol=1e-12)

    def test_scalar_and_array_paths_agree(self):
        for name, reference in (("Wo", impedance_py_wo), ("Ws", impedance_py_ws)):
            for w in (2.0 * math.pi * 1e-3, 2.0 * math.pi * 3.0, 2.0 * math.pi * 1e4):
                got = solver.evaluate_element_impedance(name, {"r": 100.0, "tau": 0.5}, w)
                self.assertAlmostEqual(abs(got - reference(100.0, 0.5, w)), 0.0, delta=1e-9 * abs(got))

    def test_physical_limits(self):
        z0, tau = 100.0, 0.5
        low = np.array([2.0 * math.pi * 1e-6])
        wo = solver.evaluate_element_impedance("Wo", {"r": z0, "tau": tau}, low)[0]
        ws = solver.evaluate_element_impedance("Ws", {"r": z0, "tau": tau}, low)[0]
        # short (transmissive) terminus: finite DC resistance Z0; open (blocking): Z0/3 - j Z0/(w tau)
        self.assertAlmostEqual(ws.real, z0, delta=1e-3)
        self.assertAlmostEqual(ws.imag, 0.0, delta=1e-3)
        self.assertAlmostEqual(wo.real, z0 / 3.0, delta=1e-2)
        self.assertAlmostEqual(wo.imag / (-z0 / (low[0] * tau)), 1.0, delta=1e-6)
        # high frequency: both approach the semi-infinite Warburg Z0 / sqrt(j w tau)
        high = np.array([2.0 * math.pi * 1e5])
        semi = z0 / np.sqrt(1j * high * tau)
        for name in ("Wo", "Ws"):
            got = solver.evaluate_element_impedance(name, {"r": z0, "tau": tau}, high)
            np.testing.assert_allclose(got, semi, rtol=1e-9)

    def test_alias_groups_follow_the_boundary_type(self):
        params = {"r": 55.0, "tau": 2.0}
        wo = impedance_py_wo(55.0, 2.0, OMEGA)
        ws = impedance_py_ws(55.0, 2.0, OMEGA)
        # reflective = blocking = open terminus (coth, impedance.py Wo)
        np.testing.assert_allclose(solver.evaluate_element_impedance("ReflectiveWarburg", params, OMEGA), wo, rtol=1e-9)
        # finite-length / transmissive = short terminus (tanh, impedance.py Ws: "short (finite-length)")
        for name in ("FiniteWarburg", "NernstDiffusion"):
            np.testing.assert_allclose(solver.evaluate_element_impedance(name, params, OMEGA), ws, rtol=1e-9)
        self.assertGreater(np.max(np.abs(wo - ws)), 1.0)

    def test_extract_puts_each_alias_in_the_table_of_the_element_it_evaluates_as(self):
        def params_of(el_type):
            topology = {"branches": [{"connection": "series", "elements": [
                {"id": "w", "name": "W1", "type": el_type, "value": 80.0, "exponent": 1.2}]}]}
            return solver.extract_topology_parameters(topology)

        # same parameter table within a boundary group; evaluating the custom topology agrees
        for el_type in ("OpenWarburg", "ReflectiveWarburg"):
            self.assertEqual(params_of(el_type), params_of("Wo"))
        for el_type in ("ShortWarburg", "FiniteWarburg", "NernstDiffusion"):
            self.assertEqual(params_of(el_type), params_of("Ws"))
        self.assertEqual(params_of("BisquertTrans"), params_of("TLM_short"))
        self.assertEqual(params_of("BisquertOpen"), params_of("TLM_open"))
        self.assertEqual(len(params_of("BisquertTrans")), 4)  # Rion, Rct, Qd, alpha: a real table, not nothing

    def test_bisquert_trans_evaluates_as_tlm_short(self):
        params = {"value": 40.0, "rct": 150.0, "qd": 2e-4, "exponent": 0.9}
        np.testing.assert_array_equal(solver.evaluate_element_impedance("BisquertTrans", params, OMEGA),
                                      solver.evaluate_element_impedance("TLM_short", params, OMEGA))

    def test_reflective_presets_keep_their_coth_physics(self):
        params = {"Rs": 5.0, "Rct": 50.0, "Qdl": 2e-5, "ndl": 0.9, "Rd": 80.0, "tau_d": 1.2}
        z_f = 50.0 + impedance_py_wo(80.0, 1.2, OMEGA)
        z_cpe = 1.0 / (2e-5 * OMEGA ** 0.9 * np.exp(1j * 0.9 * np.pi / 2.0))
        expected = 5.0 + z_f * z_cpe / (z_f + z_cpe)
        # ws_reflective is the legacy id of the same open/reflective circuit (not the tanh Ws element)
        for topology_id in ("finite_reflective_warburg", "intercalation_warburg", "wo_reflective", "ws_reflective"):
            with self.subTest(topology=topology_id):
                np.testing.assert_allclose(solver.evaluate_circuit_impedance(topology_id, params, OMEGA),
                                           expected, rtol=1e-9)
        z_tanh = 50.0 + impedance_py_ws(80.0, 1.2, OMEGA)
        wrong = 5.0 + z_tanh * z_cpe / (z_tanh + z_cpe)
        self.assertGreater(np.max(np.abs(wrong - expected)), 1.0)


class UnknownElementTests(unittest.TestCase):
    def assert_validation(self, call, code, field):
        with self.assertRaises(input_validation.ValidationError) as ctx:
            call()
        self.assertEqual((ctx.exception.code, ctx.exception.field), (code, field))
        return ctx.exception

    def test_unknown_element_type_is_refused_not_one_ohm(self):
        for omega in (OMEGA, 2.0 * math.pi * 10.0):
            err = self.assert_validation(lambda: solver.evaluate_element_impedance("Zzz", {"value": 5.0}, omega),
                                         input_validation.UNKNOWN_ELEMENT, "elementType")
            self.assertEqual(err.detail["elementType"], "'Zzz'")

    def test_every_supported_element_type_evaluates_to_finite_values(self):
        for name in solver.ELEMENT_TYPES:
            with self.subTest(element=name):
                z = solver.evaluate_element_impedance(name, {"value": 10.0, "exponent": 0.8}, OMEGA)
                self.assertTrue(np.all(np.isfinite(z)))

    def test_custom_topology_with_unknown_element_is_refused(self):
        series = {"branches": [{"connection": "series", "elements": [
            {"id": "a", "name": "A", "type": "R", "value": 10.0}, {"id": "b", "name": "B", "type": "Bogus", "value": 3.0}]}]}
        parallel = {"branches": [{"connection": "parallel", "elements": [
            {"id": "c", "name": "C", "type": "C", "value": 1e-6}, {"id": "b", "name": "B", "type": "Bogus", "value": 3.0}]}]}
        for topology in (series, parallel):
            self.assert_validation(lambda: solver.evaluate_circuit_impedance(topology, {}, OMEGA),
                                   input_validation.UNKNOWN_ELEMENT, "elementType")
            self.assert_validation(lambda: solver.extract_topology_parameters(topology),
                                   input_validation.UNKNOWN_ELEMENT, "elementType")

    def test_run_cnls_fit_refuses_unknown_element(self):
        topology = {"branches": [{"connection": "series", "elements": [
            {"id": "b", "name": "B", "type": "Bogus", "value": 3.0}]}]}
        params = [dict(paramName="B", elementId="b", field="value", value=3.0, min=1e-3, max=1e3,
                       isFixed=False, paramType="Resistor", unit="Ohm")]
        points = [dict(frequency=10.0 ** (i / 4), zReal=3.0, minusZImag=0.0) for i in range(12)]
        self.assert_validation(lambda: solver.run_cnls_fit(topology, points, params),
                               input_validation.UNKNOWN_ELEMENT, "elementType")


class UnknownTopologyTests(unittest.TestCase):
    def refused(self, topology):
        with self.assertRaises(input_validation.ValidationError) as ctx:
            solver.evaluate_circuit_impedance(topology, {"Rs": 10.0, "Rct": 100.0}, OMEGA)
        self.assertEqual((ctx.exception.code, ctx.exception.field), (input_validation.OUT_OF_RANGE, "topology"))
        return ctx.exception

    def test_unknown_preset_is_refused_not_a_resistor(self):
        err = self.refused("no_such_circuit")
        self.assertIn("'no_such_circuit'", err.detail["topology"])
        self.refused({"id": "no_such_circuit"})

    def test_missing_id_and_empty_branches_are_refused(self):
        self.refused({})
        self.refused({"branches": []})
        self.refused(None)
        with self.assertRaises(input_validation.ValidationError):
            solver.evaluate_custom_topology_impedance([], {}, OMEGA)

    def test_extract_refuses_unknown_and_unparameterised_presets(self):
        for topology in ("no_such_circuit", {}, {"id": "no_such_circuit"}):
            with self.assertRaises(input_validation.ValidationError):
                solver.extract_topology_parameters(topology)
        # a known preset with no default parameter table is refused too, not given Rs/Rct
        with self.assertRaises(input_validation.ValidationError):
            solver.extract_topology_parameters("gerischer")

    def test_preset_aliases_get_the_parameter_table_of_the_circuit_they_evaluate_as(self):
        pairs = (("rs_rcpe", "randles_cpe"), ("cpe_randles", "randles_cpe"),
                 ("coated_metal", "two_time_constants"), ("oxide_coating", "two_time_constants"),
                 ("tlm", "bisquert_open"), ("tlm_open", "bisquert_open"), ("porous_electrode", "bisquert_open"),
                 ("transmission_line", "bisquert_open"), ("warburg", "randles_warburg"), ("rc_parallel", "standard_randles"))
        for alias, base in pairs:
            with self.subTest(alias=alias):
                table = solver.extract_topology_parameters(alias)
                self.assertEqual(table, solver.extract_topology_parameters(base))
                self.assertGreaterEqual(len(table), 3)  # a real table, not the old two-resistor fallback
                values = {row["paramName"]: row["value"] for row in table}
                np.testing.assert_allclose(solver.evaluate_circuit_impedance(alias, values, OMEGA),
                                           solver.evaluate_circuit_impedance(base, values, OMEGA), rtol=1e-12)

    def test_every_preset_id_evaluates_finite_and_scalar_matches_array(self):
        for topology_id in solver.PRESET_TOPOLOGY_IDS:
            with self.subTest(topology=topology_id):
                z = solver.evaluate_circuit_impedance(topology_id, {}, OMEGA)
                self.assertTrue(np.all(np.isfinite(z)))
                scalar = solver.evaluate_circuit_impedance(topology_id, {}, float(OMEGA[7]))
                self.assertAlmostEqual(abs(scalar - z[7]), 0.0, delta=1e-9 * abs(scalar))

    def test_main_returns_the_validation_envelope_with_exit_code_2(self):
        payload = {"action": "simulate", "topology": "no_such_circuit", "parameters": []}
        run = subprocess.run([sys.executable, "-B", os.path.join(HERE, "cnls_fitting_solver.py")],
                             input=json.dumps(payload), capture_output=True, text=True, cwd=HERE)
        self.assertEqual(run.returncode, 2, run.stderr)
        body = json.loads(run.stdout)
        self.assertEqual(body["errorKind"], "validation")
        self.assertEqual((body["error"]["code"], body["error"]["field"]), ("OUT_OF_RANGE", "topology"))
        self.assertFalse(body["success"])


class CpeCapacitanceTests(unittest.TestCase):
    TOPOLOGY = {"branches": [
        {"connection": "series", "elements": [{"id": "rs", "name": "Rs", "type": "R", "value": 15.0}]},
        {"connection": "parallel", "elements": [
            {"id": "r1", "name": "R1", "type": "R", "value": 600.0},
            {"id": "q1", "name": "Q1", "type": "CPE", "value": 5e-6, "exponent": 0.8}]}]}

    def results(self):
        return solver.calculate_cpe_effective_capacitances([], self.TOPOLOGY)

    def test_hirschorn_duplicate_is_gone_and_hsu_mansfeld_is_the_peak_frequency_value(self):
        rows = self.results()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertNotIn("cHirschorn_F", row)
        self.assertNotIn("cHirschorn_uF", row)
        q, n, r = 5e-6, 0.8, 600.0
        # independent value: C = Q * w_max^(n-1) at the -Z'' maximum of R || CPE, with
        # w_max = (R Q)^(-1/n) found numerically on a fine grid
        omega = np.logspace(-2, 6, 400001)
        z_cpe = 1.0 / (q * omega ** n * np.exp(1j * n * np.pi / 2.0))
        z = r * z_cpe / (r + z_cpe)
        w_peak = omega[np.argmax(-z.imag)]
        self.assertAlmostEqual(w_peak * (r * q) ** (1.0 / n), 1.0, delta=1e-3)
        self.assertAlmostEqual(row["cHsuMansfeld_F"] / (q * w_peak ** (n - 1.0)), 1.0, delta=2e-3)
        # Brug is a different formula (Rs in parallel with R)
        self.assertNotAlmostEqual(row["cBrug_F"] / row["cHsuMansfeld_F"], 1.0, places=3)

    def test_the_cpe_calculator_engine_names_no_hirschorn_model(self):
        with open(os.path.join(HERE, "cnls_fitting_solver.py"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("Brug-Hirschorn", source)
        self.assertNotIn("c_hirschorn", source)


def de_levie_open(r_ion, r_ct, q_d, alpha, omega):
    """Bisquert / de Levie transmission line with a blocking end: Z = sqrt(R_ion zeta) coth(sqrt(R_ion / zeta)),
    zeta = (1/R_ct + Q (j w)^alpha)^-1 (independent oracle)."""
    zeta = 1.0 / (1.0 / r_ct + q_d * (1j * omega) ** alpha)
    return np.sqrt(r_ion * zeta) / np.tanh(np.sqrt(r_ion / zeta))


def series(*elements):
    return {"connection": "series", "elements": list(elements)}


def parallel(*elements):
    return {"connection": "parallel", "elements": list(elements)}


class CustomElementSecondaryParameterTests(unittest.TestCase):
    """EUQ-1: Rct/Qd (TLM) and alpha/beta (Cole-Cole / HN) of a custom element reach the impedance."""

    def tlm(self, rct, kind="TLM_open"):
        return {"branches": [series({"id": "T", "name": "T", "type": kind, "value": 50.0, "exponent": 0.9,
                                     "secondaryValue": rct})]}

    def test_tlm_rct_changes_the_impedance(self):
        w = 2.0 * math.pi * 0.01
        z200 = solver.evaluate_topology_impedance(self.tlm(200.0), w)
        z5000 = solver.evaluate_topology_impedance(self.tlm(5000.0), w)
        # before: both were 216.343-0.328j (the evaluator default Rct = 200 was always used)
        self.assertAlmostEqual(abs(z200 - (216.3429 - 0.32764j)), 0.0, delta=1e-3)
        self.assertAlmostEqual(abs(z5000 - (4976.2589 - 201.6480j)), 0.0, delta=1e-3)
        self.assertAlmostEqual(abs(z5000 / de_levie_open(50.0, 5000.0, 1e-4, 0.9, w) - 1.0), 0.0, delta=1e-12)

    def test_fitted_rct_and_qd_keys_are_read_and_have_sensitivity(self):
        topology = self.tlm(200.0)
        z = solver.evaluate_circuit_impedance(topology, {"T_value": 50.0, "T_exponent": 0.9, "T_rct": 800.0,
                                                         "T_qd": 3e-5}, OMEGA)
        np.testing.assert_allclose(z, de_levie_open(50.0, 800.0, 3e-5, 0.9, OMEGA), rtol=1e-10)
        names = {p["field"] for p in solver.extract_topology_parameters(topology)}
        self.assertTrue({"value", "rct", "qd", "exponent"} <= names)

    def test_tlm_rct_is_recovered_by_a_fit(self):
        topology = {"branches": [series({"id": "rs", "name": "Rs", "type": "R", "value": 2.0},
                                        {"id": "T", "name": "T", "type": "TLM_open", "value": 65.0,
                                         "exponent": 0.9, "secondaryValue": 400.0})]}
        omega = 2.0 * np.pi * np.logspace(5, -2, 57)
        z = 2.0 + de_levie_open(65.0, 250.0, 1.5e-4, 0.9, omega)
        points = [{"frequency": float(w / (2 * np.pi)), "zReal": float(v.real), "minusZImag": float(-v.imag)}
                  for w, v in zip(omega, z)]
        params = solver.extract_topology_parameters(topology)
        report = solver.run_cnls_fit(topology, points, params, "modulus", 200)
        fitted = {p["field"]: p["fittedValue"] for p in report["parameters"] if p["elementId"] == "T"}
        self.assertAlmostEqual(fitted["rct"] / 250.0, 1.0, delta=1e-6)  # was stuck at its 400 initial value
        self.assertAlmostEqual(fitted["qd"] / 1.5e-4, 1.0, delta=1e-6)

    def test_havriliak_negami_alpha_and_beta_are_used_and_exposed(self):
        el = {"id": "h", "name": "H", "type": "HN", "value": 1000.0, "exponent": 1e-4}
        topology = {"branches": [series(el)]}
        z = solver.evaluate_circuit_impedance(topology, {"h_value": 1000.0, "h_exponent": 1e-4, "h_alpha": 0.6,
                                                         "h_beta": 0.4}, OMEGA)
        np.testing.assert_allclose(z, 1000.0 / (1.0 + (1j * OMEGA * 1e-4) ** 0.6) ** 0.4, rtol=1e-10)
        fields = [p["field"] for p in solver.extract_topology_parameters(topology)]
        self.assertEqual(fields, ["value", "exponent", "alpha", "beta"])


class ParallelBranchAdmittanceTests(unittest.TestCase):
    """EUQ-7: a parallel branch is an admittance sum whatever its element types."""

    def test_two_resistors_and_a_capacitor_are_all_in_parallel(self):
        topology = {"branches": [parallel({"id": "a", "name": "R1", "type": "R", "value": 100.0},
                                          {"id": "b", "name": "R2", "type": "R", "value": 100.0},
                                          {"id": "c", "name": "C1", "type": "C", "value": 1e-6})]}
        z = solver.evaluate_topology_impedance(topology, 1e-6)
        self.assertAlmostEqual(z.real, 50.0, places=6)  # was 200 Ohm: (R1 + R2) || C
        np.testing.assert_allclose(solver.evaluate_topology_impedance(topology, OMEGA),
                                   1.0 / (2.0 / 100.0 + 1j * OMEGA * 1e-6), rtol=1e-10)

    def test_randles_with_warburg_is_a_series_sub_branch(self):
        rct, sigma, cdl, rs = 120.0, 30.0, 2e-5, 8.0
        topology = {"branches": [
            series({"id": "rs", "name": "Rs", "type": "R", "value": rs}),
            parallel({"id": "cdl", "name": "Cdl", "type": "C", "value": cdl},
                     series({"id": "rct", "name": "Rct", "type": "R", "value": rct},
                            {"id": "w", "name": "W", "type": "W", "value": sigma}))]}
        z_w = solver.evaluate_element_impedance("W", {"value": sigma}, OMEGA)
        expected = rs + 1.0 / (1j * OMEGA * cdl + 1.0 / (rct + z_w))
        np.testing.assert_allclose(solver.evaluate_topology_impedance(topology, OMEGA), expected, rtol=1e-10)
        ids = [p["elementId"] for p in solver.extract_topology_parameters(topology)]
        self.assertEqual(ids, ["rs", "cdl", "rct", "w"])


class TlmShortSmallArgumentTests(unittest.TestCase):
    """EUQ-8: tanh(g) ~ g, so sqrt(R_ion zeta) tanh(sqrt(R_ion / zeta)) -> R_ion, not zeta."""

    def test_limit_is_r_ion_on_both_sides_of_the_threshold(self):
        for rct in (1e9, 1e11, 1e13):  # 1e11 and 1e13 take the |gamma| < 1e-8 branch
            with self.subTest(rct=rct):
                params = {"rion": 1e-6, "rct": rct, "qd": 1e-15, "exponent": 0.9}
                z = solver.evaluate_element_impedance("TLM_short", params, 1e-6)
                z_arr = solver.evaluate_element_impedance("TLM_short", params, np.array([1e-6, 1e-3]))
                self.assertAlmostEqual(abs(z - 1e-6), 0.0, delta=1e-12)  # was ~rct (1e11, 1e13 Ohm)
                np.testing.assert_allclose(z_arr.real, 1e-6, rtol=1e-6)


class CpeCapacitanceFittedResistanceTests(unittest.TestCase):
    """EUQ-2: Brug / Hsu-Mansfeld use the FITTED Rs and Rct (Brug et al. 1984; Hsu & Mansfeld 2001)."""

    RS, RCT, Q, N = 20.0, 5000.0, 2e-5, 0.85
    FREQS = np.logspace(5, -2, 50)

    def brug(self):
        return self.Q ** (1 / self.N) * (self.RS * self.RCT / (self.RS + self.RCT)) ** ((1 - self.N) / self.N)

    def hsu_mansfeld(self):
        return self.Q ** (1 / self.N) * self.RCT ** ((1 - self.N) / self.N)

    def points(self, topology, values):
        z = solver.evaluate_circuit_impedance(topology, values, 2 * np.pi * self.FREQS)
        return [{"frequency": float(f), "zReal": float(v.real), "minusZImag": float(-v.imag)}
                for f, v in zip(self.FREQS, z)]

    def assert_row(self, row, area=None):
        self.assertAlmostEqual(row["cBrug_F"] / self.brug(), 1.0, delta=1e-7)  # was 2.958 uF (-41 %)
        self.assertAlmostEqual(row["cHsuMansfeld_F"] / self.hsu_mansfeld(), 1.0, delta=1e-7)  # was 6.679 uF (-50 %)
        self.assertEqual((row["associatedRs"], row["associatedRct"]), (self.RS, self.RCT))  # were 1 and 100
        self.assertAlmostEqual(row["tauEffectiveMs"], self.RCT * self.brug() * 1e3, delta=2e-3)
        if area is None:
            self.assertIsNone(row["cEffectiveArea_uFcm2"])
            self.assertIsNone(row["physicsNote"])
            self.assertIn("cEffectiveArea", row["unavailable"])
        else:
            self.assertEqual(row["cEffectiveArea_uFcm2"], round(self.brug() * 1e6 / area, 3))
            self.assertTrue(row["physicsNote"].startswith("Ideal double-layer"))

    def test_custom_topology_uses_fitted_resistances(self):
        topology = {"branches": [
            series({"id": "r1", "name": "Rs", "type": "R", "value": 1.0}),
            parallel({"id": "r2", "name": "Rct", "type": "R", "value": 100.0},
                     {"id": "q1", "name": "Q1", "type": "CPE", "value": 1e-5, "exponent": 0.8})]}
        truth = {"r1_value": self.RS, "r2_value": self.RCT, "q1_value": self.Q, "q1_exponent": self.N}
        report = solver.run_cnls_fit(topology, self.points(topology, truth),
                                     solver.extract_topology_parameters(topology), "modulus", 200)
        self.assertTrue(report["converged"])
        rows = report["physicalValidation"]["cpeCapacitances"]
        self.assertEqual(len(rows), 1)
        self.assert_row(rows[0])

    def test_preset_topology_reports_capacitances_with_the_area(self):
        values = {"Rs": self.RS, "Rct": self.RCT, "Qdl": self.Q, "ndl": self.N}
        report = solver.run_cnls_fit("randles_cpe", self.points("randles_cpe", values),
                                     solver.extract_topology_parameters("randles_cpe"), "modulus", 200,
                                     electrode_area_cm2=1.0)
        rows = report["physicalValidation"]["cpeCapacitances"]  # was [] for every preset
        self.assertEqual(len(rows), 1)
        self.assert_row(rows[0], area=1.0)

    def test_blocking_cpe_has_no_hsu_mansfeld_value(self):
        topology = {"branches": [series({"id": "rs", "name": "Rs", "type": "R", "value": self.RS}),
                                 parallel({"id": "q", "name": "Q", "type": "CPE", "value": self.Q,
                                           "exponent": self.N})]}
        row = solver.calculate_cpe_effective_capacitances([], topology, 2.0)[0]
        self.assertAlmostEqual(row["cBrug_F"] / (self.Q ** (1 / self.N) * self.RS ** ((1 - self.N) / self.N)), 1.0,
                               delta=1e-12)
        self.assertIsNone(row["cHsuMansfeld_F"])
        self.assertIsNone(row["associatedRct"])  # was an invented 100 Ohm
        self.assertIn("cHsuMansfeld", row["unavailable"])

    def test_invalid_area_is_refused(self):
        for area in (0.0, -1.0, float("nan"), True):
            with self.subTest(area=area), self.assertRaises(ValueError):
                solver.calculate_cpe_effective_capacitances([], CpeCapacitanceTests.TOPOLOGY, area)


if __name__ == "__main__":
    unittest.main()
