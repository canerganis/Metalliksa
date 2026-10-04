"""Tests for alloy_data_calphad_battery_icme (Phase 6a tranche 2a domain-data leaf)."""

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

import alloy_data_calphad_battery_icme as data
import alloy_registry as reg
import physical_constants as pc
from lpbf_simulation import IMPLEMENTATION_SOURCE_FILES

HERE = Path(__file__).parent
MODULE = "alloy_data_calphad_battery_icme"
SNAPSHOT_DIR = HERE / "golden" / "phase6a"


def _snapshot(solver):
    return json.loads((SNAPSHOT_DIR / solver / "_source_tables.json").read_text(encoding="utf-8"))["values"]


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


class LeafGuardTest(unittest.TestCase):
    def test_not_in_manifest_and_not_imported_by_manifest_files(self):
        self.assertNotIn(MODULE, {Path(p).stem for p in IMPLEMENTATION_SOURCE_FILES})
        for relative in IMPLEMENTATION_SOURCE_FILES:
            if not relative.endswith(".py"):
                continue
            path = HERE / relative
            self.assertNotIn(MODULE, set(_imports(path)), relative)
            self.assertNotIn(MODULE, path.read_text(encoding="utf-8"), relative)

    def test_only_local_import_is_physical_constants(self):
        local = {m for m in _imports(HERE / f"{MODULE}.py") if (HERE / f"{m}.py").is_file()}
        self.assertEqual(local, {"physical_constants"})

    def test_imports_without_numpy_or_scipy(self):
        code = (f"import sys, {MODULE}, alloy_registry; "
                "print(sorted(m for m in ('numpy', 'scipy', 'pycalphad') if m in sys.modules))")
        out = subprocess.run([sys.executable, "-B", "-c", code], cwd=str(HERE),
                             capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "[]")


class LegacyConstantTest(unittest.TestCase):
    def test_values_are_the_solver_literals_and_not_exact(self):
        expected = {
            data.LEGACY_R_8_314: (8.314, "J/(mol*K)"),
            data.LEGACY_R_8_31446: (8.31446, "J/(mol*K)"),
            data.LEGACY_F_96485_332: (96485.332, "C/mol"),
            data.LEGACY_F_96485_33: (96485.33, "C/mol"),
        }
        for const, (value, unit) in expected.items():
            self.assertEqual(const.value, value)
            self.assertEqual(const.unit, unit)
            self.assertFalse(const.exact)
            self.assertIn("not exact", const.note)

    def test_relative_deltas_to_the_exact_values(self):
        r, f = pc.GAS_CONSTANT_R.value, pc.FARADAY.value
        self.assertAlmostEqual((data.LEGACY_R_8_314.value - r) / r, -5.565e-5, delta=1e-8)
        self.assertAlmostEqual((data.LEGACY_R_8_31446.value - r) / r, -3.15e-7, delta=1e-9)
        self.assertLess(abs((data.LEGACY_F_96485_332.value - f) / f), 1.3e-9)
        self.assertLess(abs((data.LEGACY_F_96485_33.value - f) / f), 2.3e-8)

    def test_every_site_names_a_known_constant(self):
        for site, names in data.LEGACY_CONSTANT_SITES.items():
            for name in names:
                if name is None:
                    continue
                self.assertTrue(hasattr(data, name) or hasattr(pc, name), (site, name))


class CalphadElementsTest(unittest.TestCase):
    def test_element_set_and_values_equal_the_pre_migration_table(self):
        old = _snapshot("calphad_solver")["ATOMIC_WEIGHTS"]
        self.assertEqual(sorted(data.CALPHAD_ELEMENTS), sorted(old))
        self.assertEqual(len(set(data.CALPHAD_ELEMENTS)), len(data.CALPHAD_ELEMENTS))
        for el, value in old.items():
            self.assertEqual(pc.atomic_weight(el), value, el)

    def test_registry_knows_elements_the_solver_never_had(self):
        # P, S and Sn are in physical_constants but were 50.0-fallback elements in
        # calphad; the structural step refuses them instead of changing their value.
        for el in ("P", "S", "Sn"):
            self.assertTrue(pc.is_known_element(el))
            self.assertNotIn(el, data.CALPHAD_ELEMENTS)


class IcmeDataTest(unittest.TestCase):
    def test_atomic_weights_equal_the_pre_migration_table(self):
        old = _snapshot("icme_multiscale_pipeline_solver")["atomic_weights"]
        self.assertEqual(json.dumps(dict(data.ICME_ATOMIC_WEIGHTS), sort_keys=True), json.dumps(old, sort_keys=True))

    def test_legacy_weights_are_within_0_005_of_ciaaw(self):
        for el, value in data.ICME_ATOMIC_WEIGHTS.items():
            self.assertLessEqual(abs(value - pc.atomic_weight(el)), 0.0051, el)

    def test_lookups_raise_instead_of_falling_back(self):
        self.assertEqual(data.icme_atomic_weight("Ni"), 58.69)
        for bad in ("Zr", "Xx", "cr", "", None):
            with self.assertRaises(data.UnsupportedElementError):
                data.icme_atomic_weight(bad)
        for base in data.ICME_BASE_METALS:
            self.assertEqual(data.icme_base_metal(base), base)
        for bad in ("Co", "Cu", "ni", "Xx", None):
            with self.assertRaises(data.UnsupportedElementError) as ctx:
                data.icme_base_metal(bad)
            self.assertEqual(ctx.exception.supported, ("Ni", "Fe", "Ti", "Al"))

    def test_t_melt_per_base(self):
        self.assertEqual(dict(data.ICME_JOHNSON_COOK_T_MELT_C),
                         {"Ni": 1350.0, "Fe": 1450.0, "Ti": 1650.0, "Al": 660.0})
        self.assertEqual(set(data.ICME_JOHNSON_COOK_T_MELT_C), set(data.ICME_BASE_METALS))


class RegistryWiringTest(unittest.TestCase):
    def test_in718_carries_the_icme_domain(self):
        rec = reg.resolve_alloy("IN718", reg.DOMAIN_ICME)
        self.assertEqual(rec.id, data.ICME_DEFAULT_ALLOY_ID)
        vr = rec.get("default_solute_composition_wt", reg.DOMAIN_ICME)
        self.assertEqual(dict(vr.value), {"Cr": 19.0, "Fe": 18.0, "Nb": 5.1, "Mo": 3.0, "Ti": 0.9,
                                          "Al": 0.5, "C": 0.05, "Si": 0.2, "Mn": 0.2})
        self.assertEqual(vr.unit, "wt%")
        self.assertEqual(vr.source_type, "estimated")
        self.assertIn("icme_multiscale_pipeline_solver.py", vr.source_ref)
        self.assertEqual(vr.model_version, f"{reg.REGISTRY_VERSION}:icme")

    def test_only_in718_has_icme_data(self):
        self.assertEqual(reg.alloys_with_domain(reg.DOMAIN_ICME), ("in718",))
        with self.assertRaises(reg.UnknownAlloyError) as ctx:
            reg.resolve_alloy("ss316l", reg.DOMAIN_ICME)
        self.assertEqual(ctx.exception.reason, "no-domain-data")

    def test_existing_domains_unchanged(self):
        self.assertIn(reg.DOMAIN_KINETICS, reg.REGISTRY["in718"].domains)
        self.assertIn(reg.DOMAIN_LPBF_THERMAL, reg.REGISTRY["in718"].domains)


if __name__ == "__main__":
    unittest.main()
