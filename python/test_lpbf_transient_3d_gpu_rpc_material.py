"""Phase 22 transient-3d-gpu RPC: alloy data comes only from four_alloy_materials.

Parameter plumbing only. warp/CUDA is not needed and no kernel runs: the solver
class is replaced by a recording fake injected as ``lpbf_transient_3d_gpu`` in
sys.modules, and the ``solve_toolpath`` signature is checked from source via ast.
"""
import ast
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import four_alloy_materials as fam
import lpbf_worker_rpc

MATERIAL_KEYS = (
    "rho", "L_f", "T_solidus", "T_liquidus", "Lv", "Rs", "Tv",
    "cp_solid", "cp_liquid", "k_solid", "k_liquid",
)
GAS_CONSTANT_R = 8.314462618  # J/(mol K); the RPC uses the exact physical_constants value (differs ~2e-12 relative)

# Independent literals (not read back through the code under test): Ti-6Al-4V row of _THERMAL.
TI64_EXPECTED = {
    "rho": 4430.0, "L_f": 290000.0, "T_solidus": 1604.0 + 273.15, "T_liquidus": 1660.0 + 273.15,
    "Lv": 8.9e6, "Tv": 3287.0 + 273.15, "cp_solid": 526.0, "cp_liquid": 830.0,
    "k_solid": 6.7, "k_liquid": 23.0,
}


class _RecordingSolver:
    constructed = []
    solves = []

    def __init__(self, **kwargs):
        type(self).constructed.append(kwargs)

    def solve_toolpath(self, **kwargs):
        type(self).solves.append(kwargs)
        return {"steps": 1, "device": "fake"}


def _fake_module():
    _RecordingSolver.constructed = []
    _RecordingSolver.solves = []
    module = types.ModuleType("lpbf_transient_3d_gpu")
    module.TransientEnthalpy3DGPU = _RecordingSolver
    return module


def _call(payload):
    request = {"payload": payload}
    with mock.patch.dict(sys.modules, {"lpbf_transient_3d_gpu": _fake_module()}):
        return lpbf_worker_rpc._rpc_transient_3d_gpu(request)


def _expected_from_authority(aid):
    t = fam.thermal_props(aid)
    return {
        "rho": t["density_kg_m3"],
        "L_f": t["latent_heat_fusion_J_kg"],
        "T_solidus": t["solidus_C"] + 273.15,
        "T_liquidus": t["liquidus_C"] + 273.15,
        "Lv": t["latent_heat_vap_J_kg"],
        "Tv": t["boiling_C"] + 273.15,
        "cp_solid": t["specific_heat_J_kgK"],
        "cp_liquid": t["specific_heat_liquid_J_kgK"],
        "k_solid": t["thermal_conductivity_W_mK"],
        "k_liquid": t["thermal_conductivity_liquid_W_mK"],
    }


class TransientGpuRpcMaterial(unittest.TestCase):
    def test_each_alloy_gets_exactly_the_authority_values(self):
        for aid in fam.FOUR_ALLOY_IDS:
            with self.subTest(alloy=aid):
                _call({"alloyId": aid, "power_W": 150.0, "T_preheat_K": 400.0})
                self.assertEqual(len(_RecordingSolver.solves), 1)
                kwargs = _RecordingSolver.solves[0]
                self.assertEqual(set(kwargs), {"toolpath", "T_preheat_K", *MATERIAL_KEYS})
                self.assertEqual(kwargs["T_preheat_K"], 400.0)
                expected = _expected_from_authority(aid)
                for key, value in expected.items():
                    self.assertEqual(kwargs[key], value, key)
                m_molar = fam.thermal_props(aid)["M_molar_kg_mol"]
                self.assertAlmostEqual(kwargs["Rs"] * m_molar, GAS_CONSTANT_R, delta=1e-9)
                self.assertGreater(kwargs["Rs"], 100.0)
                self.assertLess(kwargs["Rs"], 400.0)

    def test_ti6al4v_matches_independent_literals_not_the_old_defaults(self):
        _call({"alloyId": "ti6al4v"})
        kwargs = _RecordingSolver.solves[0]
        for key, value in TI64_EXPECTED.items():
            self.assertEqual(kwargs[key], value, key)
        # The retired hard-coded defaults (rho 4420, Lv 9.7e6, Tv 3533, Rs 173.93) must not leak through.
        self.assertNotEqual(kwargs["rho"], 4420.0)
        self.assertNotEqual(kwargs["Lv"], 9.7e6)
        self.assertNotEqual(kwargs["Tv"], 3533.0)
        self.assertNotEqual(kwargs["Rs"], 173.93)

    def test_material_name_alias_resolves_and_conflict_is_rejected(self):
        _call({"materialName": "Ti-6Al-4V"})
        self.assertEqual(_RecordingSolver.solves[0]["rho"], 4430.0)
        _call({"alloyId": "in718", "materialName": "Inconel 718"})
        with self.assertRaisesRegex(ValueError, "supported alloy identity"):
            _call({"alloyId": "in718", "materialName": "ss316l"})

    def test_missing_or_unknown_alloy_raises_before_any_solver_is_built(self):
        for payload in ({}, {"alloyId": None}, {"alloyId": "unobtainium"}, {"alloyId": "in625"},
                        {"materialName": ""}, {"power_W": 100.0}):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "transient-3d-gpu requires a supported alloy identity; got"):
                    _call(payload)
                self.assertEqual(_RecordingSolver.constructed, [])
                self.assertEqual(_RecordingSolver.solves, [])

    def test_explicit_material_overrides_are_rejected_by_name(self):
        for key in MATERIAL_KEYS:
            with self.subTest(key=key):
                with self.assertRaises(ValueError) as caught:
                    _call({"alloyId": "ti6al4v", key: 1.0})
                message = str(caught.exception)
                self.assertIn("material properties come from four_alloy_materials; remove", message)
                self.assertIn(key, message)
                self.assertEqual(_RecordingSolver.solves, [])
        with self.assertRaises(ValueError) as caught:
            _call({"alloyId": "in718", "rho": 4420.0, "L_f": 2.9e5})
        self.assertIn("rho, L_f", str(caught.exception))

    def test_echo_digest_equals_canonical_material_source(self):
        for aid in fam.FOUR_ALLOY_IDS:
            with self.subTest(alloy=aid):
                data = _call({"alloyId": aid})
                echo = data["materialAuthority"]
                snapshot, digest = fam.canonical_material_source(aid)
                self.assertEqual(echo["alloyId"], aid)
                self.assertEqual(echo["materialSha256"], digest)
                self.assertEqual(echo["authority"], snapshot["authority"])
                self.assertEqual(echo["valuesUsed"], {k: _RecordingSolver.solves[-1][k] for k in MATERIAL_KEYS})
                self.assertEqual(data["steps"], 1)  # solver result is preserved

    def test_solve_toolpath_material_parameters_are_keyword_only_and_required(self):
        source = Path(__file__).with_name("lpbf_transient_3d_gpu.py").read_text(encoding="utf-8")
        function = next(
            node for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.FunctionDef) and node.name == "solve_toolpath"
        )
        args = function.args
        self.assertEqual([a.arg for a in args.args], ["self", "toolpath", "T_preheat_K"])
        self.assertEqual(len(args.defaults), 1)  # T_preheat_K only
        required = {a.arg for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is None}
        self.assertEqual(required, set(MATERIAL_KEYS))
        defaulted = {a.arg for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None}
        self.assertEqual(
            defaulted,
            {"P0", "mu", "d_gamma_dT", "beta", "include_diagnostic_fields", "include_energy_ledger"},
        )


if __name__ == "__main__":
    unittest.main()
