"""Tests for alloy_data_kinetics_uq_fatigue (Phase 6a tranche 2b domain data).

- values equal the pre-migration solver tables (golden _source_tables.json snapshots
  for kinetics/fatigue; an AST extraction of the base blob for the stochastic UQ
  constants, which lived inside a function body);
- metadata is present and honest (estimated, no invented validity);
- every alloy string the four target UI components send resolves, so removing the
  kinetics/fatigue silent fallbacks does not turn a UI request into a 422;
- the phase9 name mapping and the kept UQ fallbacks behave exactly as before.
"""

import ast
import json
import subprocess
import unittest
from pathlib import Path

import alloy_data_kinetics_uq_fatigue as data
import alloy_registry as reg
import input_validation as iv
import physical_constants as pc
from phase6a_test_support import require_git_revision

HERE = Path(__file__).parent
SNAPSHOTS = HERE / "golden" / "phase6a"
BASE = data.BASE_REVISION

# Strings sent by the target UI components (src/ at 7f3f803) -> expected registry id.
UI_NAMES = {
    reg.DOMAIN_KINETICS: {
        # PhaseKineticsTTTCCTStudio.tsx:62-69 alloyOptions ids (+ the default initialAlloy)
        "AISI 4140": "aisi4140", "AISI 4340": "aisi4340", "AISI D2": "aisid2",
        "Inconel 718": "in718", "Ti-6Al-4V": "ti6al4v", "Al 7075": "al7075",
        # lpbf_build_job_solver.py:641 in-process caller
    },
    reg.DOMAIN_FATIGUE_FRACTURE: {
        # MurakamiFatigueLab.tsx:7 AVAILABLE_ALLOYS (+ lpbf_worker_rpc default "Ti-6Al-4V")
        "Ti-6Al-4V": "ti6al4v", "316L SS": "ss316l", "Inconel 718": "in718", "AlSi10Mg": "alsi10mg",
    },
    # UQ sends alloyName as a label only (no lookup); these must resolve as aliases.
    None: {
        # StochasticUQMMPDSStudio.tsx:77-135 UQ_PRESETS ids and names
        "inconel718_ams5664": "in718", "Inconel 718 (AMS 5664 / AMS 5662)": "in718",
        "ti64_ams4928": "ti6al4v", "Ti-6Al-4V Grade 5 (AMS 4928)": "ti6al4v",
        "steel4340_ams6414": "aisi4340", "AISI 4340 Ultra-High Strength (AMS 6414)": "aisi4340",
        "alsi10mg_ams4215": "alsi10mg", "AlSi10Mg Additive (AMS 4215)": "alsi10mg",
        # UQLab.tsx:159 -> uqLabData.ts datasets (ids and names)
        "inconel718-ams5664": "in718", "Inconel 718 Forged Turbine Disks (AMS 5664)": "in718",
        "ti64-ams4928": "ti6al4v", "Ti-6Al-4V Grade 5 Airframe Billets (AMS 4928)": "ti6al4v",
        "al7075-t651": "al7075", "Al 7075-T651 Aerospace Plate (AMS 4045)": "al7075",
        "steel4340-ams6414": "aisi4340", "AISI 4340 Ultra-High Strength VAR (AMS 6414)": "aisi4340",
        "alsi10mg-lpbf-ams4215": "alsi10mg", "AlSi10Mg Additive LPBF As-Built & SR (AMS 4215)": "alsi10mg",
        # stochastic_uq_mmpds_solver default alloyName
        "Inconel 718 (Aero LPBF)": "in718",
    },
}


def _snapshot(solver):
    return json.loads((SNAPSHOTS / solver / "_source_tables.json").read_text(encoding="utf-8"))["values"]


def _base_blob(path):
    try:
        return subprocess.run(["git", "-C", str(HERE), "show", f"{BASE}:{path}"],
                              capture_output=True, check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        return None


class LeafModuleTest(unittest.TestCase):
    def test_imports_only_standard_library(self):
        tree = ast.parse((HERE / "alloy_data_kinetics_uq_fatigue.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertLessEqual(imported, {"__future__", "types", "typing"})

    def test_every_source_is_estimated_without_invented_validity(self):
        for name, meta in data.SOURCES.items():
            self.assertEqual(meta["sourceType"], "estimated", name)
            self.assertIn(BASE, meta["sourceRef"], name)
            self.assertIsNone(meta["validity"], name)
            self.assertIn(meta["sourceType"], reg.SOURCE_TYPES)

    def test_tables_are_read_only(self):
        with self.assertRaises(TypeError):
            data.UQ_BASE_METAL_LATTICE["Ni"]["nu"] = 0.0  # type: ignore[index]
        with self.assertRaises(TypeError):
            data.KINETICS_DESCRIPTORS["aisi4140"]["type"] = "x"  # type: ignore[index]

    def test_legacy_r_constant_is_gone(self):
        # Design step (b): kinetics and stochastic UQ use the exact R; the 8.314 record
        # (LEGACY_GAS_CONSTANT_R_4SF) was removed. Its old relative offset, for the record:
        self.assertFalse(hasattr(pc, "LEGACY_GAS_CONSTANT_R_4SF"))
        rel = (8.314 - pc.GAS_CONSTANT_R.value) / pc.GAS_CONSTANT_R.value
        self.assertAlmostEqual(rel, -5.5645e-5, delta=1e-8)


class KineticsAndFatigueValueTest(unittest.TestCase):
    def test_legacy_names_match_registry(self):
        self.assertEqual(dict(data.KINETICS_LEGACY_NAMES), reg._KINETICS_SOURCE_NAME)
        self.assertEqual(dict(data.FATIGUE_LEGACY_NAMES), reg._FATIGUE_FRACTURE_SOURCE_NAME)
        self.assertEqual(set(data.KINETICS_DESCRIPTORS), set(data.KINETICS_LEGACY_NAMES))

    def test_kinetics_registry_plus_descriptors_equal_the_pre_migration_table(self):
        snap = _snapshot("kinetics_ttt_cct_solver")
        self.assertEqual(list(snap), sorted(data.KINETICS_LEGACY_NAMES.values()))
        for aid, legacy in data.KINETICS_LEGACY_NAMES.items():
            with self.subTest(alloy=aid):
                old = snap[legacy]
                self.assertEqual(set(old), set(data.KINETICS_METADATA_KEYS))
                for key in data.KINETICS_METADATA_KEYS:
                    if key in data.KINETICS_DESCRIPTOR_KEYS:
                        new = data.KINETICS_DESCRIPTORS[aid][key]
                        new = list(new) if key == "phases" else new
                    else:
                        new = reg.REGISTRY[aid].value(key, reg.DOMAIN_KINETICS)
                        new = dict(new) if key == "composition_wt" else new
                    self.assertEqual(json.dumps(new, sort_keys=True), json.dumps(old[key], sort_keys=True), key)

    def test_fatigue_registry_equals_the_pre_migration_table(self):
        snap = _snapshot("lpbf_fatigue_fracture")
        self.assertEqual(set(snap), set(data.FATIGUE_LEGACY_NAMES.values()))
        for aid, legacy in data.FATIGUE_LEGACY_NAMES.items():
            old = snap[legacy]
            self.assertEqual(old["name"], legacy)
            for key in data.FATIGUE_KEYS:
                self.assertEqual(repr(reg.REGISTRY[aid].value(key, reg.DOMAIN_FATIGUE_FRACTURE)),
                                 repr(old[key]), f"{aid}.{key}")


class StochasticFallbackTest(unittest.TestCase):
    def test_kept_al_fallback_mirrors_the_old_equality_chain(self):
        for base in ("Ni", "Fe", "Ti", "Al"):
            self.assertIs(data.uq_lattice_constants(base), data.UQ_BASE_METAL_LATTICE[base])
        for other in ("Zz", "ni", "NI", "", None, 3, ["Ni"], {"Ni": 1}):
            self.assertIs(data.uq_lattice_constants(other), data.UQ_BASE_METAL_LATTICE["Al"], repr(other))

    def test_default_compositions_are_fresh_copies(self):
        a = data.uq_default_composition_wt()
        a["Cr"] = 0.0
        self.assertEqual(data.uq_default_composition_wt()["Cr"], 19.0)
        self.assertEqual(list(data.uq_default_composition_wt()), ["Cr", "Fe", "Nb", "Mo", "Ti", "Al", "C", "Si"])


class UiAliasTest(unittest.TestCase):
    def test_every_ui_name_resolves(self):
        for domain, names in UI_NAMES.items():
            for name, aid in names.items():
                with self.subTest(name=name, domain=domain):
                    self.assertEqual(iv.require_known_alloy(name, domain).id, aid)

    def test_extra_aliases_are_registered_once(self):
        for aid, names in data.EXTRA_ALIASES.items():
            for name in names:
                self.assertEqual(reg.resolve_alloy_id(name), aid)
                self.assertIn(name, reg.REGISTRY[aid].aliases)

    def test_unregistered_ui_dataset_is_refused(self):
        for name in ("Hastelloy X Combustor Sheet (AMS 5754)", "hastelloy-x-ams5754"):
            with self.assertRaises(reg.UnknownAlloyError):
                reg.resolve_alloy_id(name)

    def test_extra_aliases_do_not_unlock_the_tafel_grade5_preset(self):
        import tafel_corrosion_rate_solver as tafel
        with self.assertRaises(iv.ValidationError) as ctx:
            tafel.corrosion_preset("Ti-6Al-4V Grade 5 Airframe Billets (AMS 4928)")
        self.assertEqual(ctx.exception.code, iv.UNKNOWN_ALLOY)


class ProcessMapNameTest(unittest.TestCase):
    def test_same_mapping_as_the_old_expression(self):
        def old(alloy_name):
            return "Inconel 718" if alloy_name.upper() == "IN718" else alloy_name
        for name in ("IN718", "in718", "In718", "Inconel 718", "IN 718", "Ti-6Al-4V", "316L SS",
                     "AlSi10Mg", "Hastelloy X", "", "inconel718"):
            self.assertEqual(data.process_map_material_name(name), old(name), name)
        with self.assertRaises(AttributeError):
            data.process_map_material_name(None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
