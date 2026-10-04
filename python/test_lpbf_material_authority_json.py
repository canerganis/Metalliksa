"""src/generated/lpbfMaterialAuthority.json must equal the Python material authority.

The UI holds no alloy numbers of its own: scripts/emit-lpbf-material-authority.py projects
four_alloy_materials.py (four_alloy_thermophysical_db(), LITERATURE_PV_WINDOWS,
canonical_material_source()) plus the IN625 secondary row of lpbf_thermal_solver.py into a
committed JSON file. These tests pin, from the Python side:
- the committed file is byte-identical to a fresh regeneration (and rendering is deterministic);
- every projected value equals the live authority value;
- the IN625 secondary row carries its own label and lists every other IN625 value Python holds;
- the TypeScript consumers read that JSON, hold no alloy-property literals and compute no
  normalized enthalpy (source parse, like test_hardness_conversion_e140).
  TypeScript side (label maps, payloads, ranking): tests/lpbf-material-authority.test.ts.
Non-manifest test; it only reads manifest modules.
"""
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

import four_alloy_materials as fam  # noqa: E402
import in625_thermal_material as in625  # noqa: E402
import lpbf_material_registry as registry  # noqa: E402
from lpbf_thermal_solver import SECONDARY_THERMOPHYSICAL_DB  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
GENERATOR = REPO / "scripts" / "emit-lpbf-material-authority.py"
GENERATED = REPO / "src" / "generated" / "lpbfMaterialAuthority.json"
ACCESSOR_TS = REPO / "src" / "data" / "lpbfMaterialAuthority.ts"
# file -> (allowed literal block, allowed line fragments). Same allowances as the TS test.
CONSUMERS_TS = {
    "src/types/lpbfDataFoundation.ts": (None, ()),
    "src/components/TransientEnthalpy3DGPULab.tsx": (None, ()),
    "src/components/SolidificationMicrostructureLab.tsx": (None, ("radius={[7, 7, 2, 2]}",)),
    # The labelled TS-local IN625 P-v box is the only literal block allowed.
    "src/utils/lpbfFourAlloySchema.ts": (re.compile(r"const IN625_PV_WINDOW_TS_LOCAL[\s\S]*?\n};\n"),
                                         ("([0, 45, 90] as const)",)),
}
PROPERTY_LITERAL = re.compile(
    r"\b(rho|L_f|T_solidus|T_liquidus|cp_solid|cp_liquid|k_solid|k_liquid|k_WmK|liquidus_K|absorptivity|"
    r"meltingPoint_C|density_kg_m3|specificHeat_J_kgK|thermalConductivity_W_mK|thermalDiffusivity_m2_s|"
    r"enthalpyOfMelting_hs_J_m3|defaultAbsorptivity|powerMin_W|powerMax_W|speedMin_mm_s|speedMax_mm_s|Tm|Tl|Ts)"
    r"\s*:\s*-?\d"
)
NAMED_NUMERIC_CONSTANT = re.compile(r"^\s*(export\s+)?(const|let|var)\s+\w+\s*(:[^=]+)?=\s*-?\d")
NUMERIC_TABLE = re.compile(r"\[\s*-?[\d.]+(e-?\d+)?\s*(,\s*-?[\d.]+(e-?\d+)?\s*){2,}\]")
TS_NORMALIZED_ENTHALPY = re.compile(
    r"\bcalculateNormalizedEnthalpy\s*[(<]|enthalpyOfMelting_hs|normalizedEnthalpy_dH_hs\s*:\s*[a-zA-Z0-9]")


def _load_generator():
    spec = importlib.util.spec_from_file_location("emit_lpbf_material_authority", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GeneratedFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = _load_generator()
        cls.committed_bytes = GENERATED.read_bytes()
        cls.doc = json.loads(cls.committed_bytes.decode("utf-8"))

    def test_regeneration_is_byte_identical_to_committed_file(self):
        self.assertEqual(self.gen.rendered_bytes(), self.committed_bytes,
                         "stale: run python -B scripts/emit-lpbf-material-authority.py")
        self.assertTrue(self.gen.is_current())

    def test_rendering_is_deterministic_lf_utf8(self):
        first, second = self.gen.rendered_bytes(), self.gen.rendered_bytes()
        self.assertEqual(first, second)
        self.assertNotIn(b"\r", first)
        self.assertTrue(first.endswith(b"}\n"))
        self.assertEqual(self.doc["schemaVersion"], 1)

    def test_four_alloy_values_equal_the_authority(self):
        db = fam.four_alloy_thermophysical_db()
        self.assertEqual(self.doc["authority"], "python/four_alloy_materials.py")
        self.assertEqual(self.doc["authoritySchemaVersion"], fam.MATERIAL_AUTHORITY_SCHEMA_VERSION)
        self.assertEqual(tuple(self.doc["alloyIds"]), fam.FOUR_ALLOY_IDS)
        self.assertEqual(set(self.doc["alloys"]), set(fam.FOUR_ALLOY_IDS))
        for aid in fam.FOUR_ALLOY_IDS:
            entry = self.doc["alloys"][aid]
            with self.subTest(alloy=aid):
                self.assertEqual(entry["thermal"], db[fam.THERMAL_NAME[aid]])
                self.assertEqual(entry["thermal"], db[fam.SLICER_NAME[aid]])
                self.assertEqual(entry["literaturePvWindow"], fam.LITERATURE_PV_WINDOWS[aid])
                self.assertEqual(entry["thermalName"], fam.THERMAL_NAME[aid])
                self.assertEqual(entry["slicerName"], fam.SLICER_NAME[aid])
                self.assertEqual(entry["canonicalSourceSha256"], fam.canonical_material_source(aid)[1])
                evidence = registry.material(fam.THERMAL_NAME[aid])
                self.assertEqual(entry["quality"], evidence["quality"])
                self.assertEqual(entry["quality"], "estimated")
                self.assertEqual(entry["source"], evidence["source"])
                # Exact float round trip: JSON text -> float is the same double as the authority.
                for key, value in entry["thermal"].items():
                    self.assertEqual(type(value), type(db[fam.THERMAL_NAME[aid]][key]), key)

    def test_in625_secondary_row_is_labelled_and_equal(self):
        entry = self.doc["secondary"]["in625"]
        row = SECONDARY_THERMOPHYSICAL_DB["Inconel 625"]
        self.assertEqual(entry["thermal"], row)
        self.assertEqual(entry["source"], "python/lpbf_thermal_solver.py SECONDARY_THERMOPHYSICAL_DB")
        self.assertEqual(entry["quality"], "secondary-unreconciled")
        catalog = next(c for c in registry.catalog() if c["name"] == "Inconel 625")
        self.assertEqual(entry["registryCatalogQuality"], catalog["quality"])
        self.assertEqual(entry["registryCatalogNote"], catalog["note"])
        self.assertIn("not reconciled", entry["note"])
        self.assertNotIn("in625", self.doc["alloys"])
        listed = {item["quantity"]: [v["value"] for v in item["values"]] for item in entry["unreconciledPythonValues"]}
        self.assertEqual(listed["latent heat of fusion"],
                         [row["latent_heat_fusion_J_kg"], in625.LATENT_HEAT_J_KG, in625.IN625_LATENT_HEAT_FUSION_MILLS_J_KG])
        self.assertEqual(listed["latent heat of fusion"], [290000.0, 290000.0, 227000.0])
        self.assertEqual(listed["boiling point"], [row["boiling_C"], round(in625.IN625_BOILING_K - 273.15, 2)])
        self.assertEqual(listed["boiling point"], [2880.0, 2900.0])
        self.assertEqual(listed["IR absorptivity"], [row["absorptivity_IR"], in625.IN625_ABSORPTIVITY_IR])
        self.assertIn("290000 vs 290000 vs 227000 J/kg", entry["note"])
        self.assertIn("2880 vs 2900 C", entry["note"])


class TypeScriptConsumersTest(unittest.TestCase):
    def test_accessor_reads_the_generated_json(self):
        text = ACCESSOR_TS.read_text(encoding="utf-8")
        self.assertIn('from "../generated/lpbfMaterialAuthority.json"', text)
        self.assertIn("checkedAuthorityDocument(authorityDocument)", text)

    def test_consumers_import_the_accessor(self):
        for rel in CONSUMERS_TS:
            text = (REPO / rel).read_text(encoding="utf-8")
            with self.subTest(file=rel):
                self.assertRegex(text, r"from ['\"]\.\./data/lpbfMaterialAuthority['\"]")

    def test_consumers_hold_no_alloy_property_literals(self):
        for rel, (block, fragments) in CONSUMERS_TS.items():
            text = (REPO / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
            if block is not None:
                self.assertRegex(text, block, f"{rel}: labelled TS-local block missing")
                text = block.sub("", text)
            hits = [line for line in text.split("\n")
                    if (PROPERTY_LITERAL.search(line) or NAMED_NUMERIC_CONSTANT.search(line) or NUMERIC_TABLE.search(line))
                    and not any(fragment in line for fragment in fragments)]
            with self.subTest(file=rel):
                self.assertEqual(hits, [])

    def test_no_ts_normalized_enthalpy_path(self):
        hits = [path.relative_to(REPO).as_posix() for path in sorted((REPO / "src").rglob("*"))
                if path.suffix in (".ts", ".tsx") and TS_NORMALIZED_ENTHALPY.search(path.read_text(encoding="utf-8"))]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
