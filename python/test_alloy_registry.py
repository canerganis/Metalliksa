import unittest
from types import MappingProxyType
from unittest import mock

import alloy_registry as reg
import four_alloy_materials as fam

# Strings the UI sends today (src/ at 01eb3f0), mapped to the expected registry id.
UI_ALIASES = {
    # PhaseKineticsTTTCCTStudio.tsx:63-68 option ids -> kinetics `alloy`
    "AISI 4140": "aisi4140", "AISI 4340": "aisi4340", "AISI D2": "aisid2",
    "Inconel 718": "in718", "Ti-6Al-4V": "ti6al4v", "Al 7075": "al7075",
    # MurakamiFatigueLab.tsx:7 AVAILABLE_ALLOYS -> `alloyName`
    "316L SS": "ss316l", "AlSi10Mg": "alsi10mg",
    # PythonAnnualCorrosionRateModule.tsx:39-47 preset ids -> tafel `alloyId`
    "steel-316l": "ss316l", "steel-304": "ss304", "steel-1018": "steel1018",
    "ti-6al-4v": "ti6al4v", "al-7075": "al7075", "al-6061": "al6061", "cu-c110": "cu_c110",
    "inconel-718": "in718", "az31b": "az31b",
    # ... and their `alloyName` display strings
    "AISI 316L Stainless Steel": "ss316l", "AISI 304 Stainless Steel": "ss304",
    "Carbon Steel (AISI 1018)": "steel1018", "Titanium Ti-6Al-4V (Grade 5)": "ti6al4v",
    "Aerospace Al 7075-T6": "al7075", "Structural Al 6061-T6": "al6061",
    "Pure Copper (ETP C11000)": "cu_c110", "Inconel 718 Superalloy": "in718",
    "Magnesium Alloy AZ31B": "az31b",
    # src/utils/tafelParser.ts:21-29 COMMON_ALLOYS ids and names
    "ss316l": "ss316l", "ss304": "ss304", "steel1018": "steel1018", "ti64": "ti6al4v",
    "al7075": "al7075", "al6061": "al6061", "cu_c110": "cu_c110", "inconel718": "in718",
    "Ti-6Al-4V Grade 5 Titanium": "ti6al4v", "Al 7075-T6 Aerospace Aluminum": "al7075",
    "Al 6061-T6 Structural Aluminum": "al6061", "C11000 Electrolytic Tough Pitch Copper": "cu_c110",
    "AZ31B Magnesium Alloy": "az31b", "AISI 1018 Carbon Steel": "steel1018",
    # StochasticUQMMPDSStudio.tsx:79-134 preset ids and names (`alloyName`)
    "inconel718_ams5664": "in718", "Inconel 718 (AMS 5664 / AMS 5662)": "in718",
    "ti64_ams4928": "ti6al4v", "Ti-6Al-4V Grade 5 (AMS 4928)": "ti6al4v",
    "steel4340_ams6414": "aisi4340", "AISI 4340 Ultra-High Strength (AMS 6414)": "aisi4340",
    "alsi10mg_ams4215": "alsi10mg", "AlSi10Mg Additive (AMS 4215)": "alsi10mg",
    # ICMEMultiScalePipelineStudio.tsx:74-108 preset names (`alloyName`)
    "Inconel 718 (Aero LPBF + Aged)": "in718", "Ti-6Al-4V Grade 5 (Aero AM)": "ti6al4v",
    "AISI 4340 Ultra-High Strength Steel": "aisi4340", "AlSi10Mg Additive Alloy": "alsi10mg",
    # LPBF specimen ids (LpbfBayesianOptimizerLab `alloyId: specimen.id`) and locked names
    "in718": "in718", "ti6al4v": "ti6al4v", "alsi10mg": "alsi10mg",
    "316L Stainless Steel": "ss316l", "SS 316L": "ss316l", "Ti-6Al-4V ELI": "ti6al4v",
    "Inconel 718 (AMS 5662)": "in718", "IN718": "in718",
}

# Names that the golden baselines (.orchestra/golden/*/MANIFEST.md) show being silently
# mapped to another alloy today. The registry must refuse every one of them.
GOLDEN_SILENT_DEFAULT_NAMES = (
    "Unobtainium XYZ",   # kinetics -> AISI 4140
    "Unobtanium-X",      # lpbf_fatigue_fracture -> Ti-6Al-4V
    "unobtainium-x",     # tafel -> steel-316l
    "unknown-alloy",     # battery corrosion_kinetics: substring "al" -> aluminium
    "Unobtainium-X",     # dft: substring "ni" -> Ni benchmark
    "UnobtainiumXYZ",    # inherent strain -> Inconel 718
    "UnobtaniumX",       # icme
    "Zz",                # uq baseMetal -> Al branch
    "duplex2205",        # tafelParser.ts:30 option with no python data anywhere
    "Inconel",           # partial / substring names never resolve
    "steel",
    "316",
    "",
    "   ",
)


class ProjectionTest(unittest.TestCase):
    def test_four_alloy_thermal_projection_matches_frozen_source(self):
        for aid in fam.FOUR_ALLOY_IDS:
            rec = reg.REGISTRY[aid]
            table = rec.domains[reg.DOMAIN_LPBF_THERMAL]
            source = fam._THERMAL[aid]
            self.assertEqual(rec.base_element, source["base"])
            self.assertEqual(set(table), set(source) - {"base"})
            for key, value in source.items():
                if key == "base":
                    continue
                self.assertEqual(table[key].value, value, f"{aid}.{key}")

    def test_other_four_alloy_tables_match_frozen_source(self):
        pairs = ((reg.DOMAIN_INHERENT_STRAIN, fam._ISM), (reg.DOMAIN_MARANGONI, fam._MARANGONI),
                 (reg.DOMAIN_PV_WINDOW, fam.LITERATURE_PV_WINDOWS))
        for aid in fam.FOUR_ALLOY_IDS:
            for domain, source in pairs:
                table = reg.REGISTRY[aid].domains[domain]
                self.assertEqual({k: v.value for k, v in table.items()}, source[aid], f"{aid}/{domain}")

    def test_digest_matches_canonical_material_source(self):
        for aid in fam.FOUR_ALLOY_IDS:
            self.assertEqual(reg.REGISTRY[aid].material_source_sha256,
                             fam.canonical_material_source(aid)[1])
            self.assertEqual(reg.provenance(aid)["materialSourceSha256"],
                             fam.canonical_material_source(aid)[1])

    def test_projection_does_not_alias_frozen_dicts(self):
        table = reg.REGISTRY["in718"].domains[reg.DOMAIN_LPBF_THERMAL]
        with self.assertRaises(TypeError):
            table["density_kg_m3"] = 1.0  # type: ignore[index]
        self.assertEqual(fam._THERMAL["in718"]["density_kg_m3"], 8190.0)


class CopiedTableDriftTest(unittest.TestCase):
    """Registry copies must equal the live solver tables until each solver migrates."""

    def test_kinetics_table(self):
        import kinetics_ttt_cct_solver as kin
        self.assertEqual(set(reg._KINETICS_SOURCE_NAME.values()), set(kin.ALLOY_KINETICS_DB))
        for aid, src_name in reg._KINETICS_SOURCE_NAME.items():
            src = kin.ALLOY_KINETICS_DB[src_name]
            table = reg.REGISTRY[aid].domains[reg.DOMAIN_KINETICS]
            for key, rec in table.items():
                self.assertEqual(dict(rec.value) if key == "composition_wt" else rec.value,
                                 src[key], f"{aid}.{key}")
            numeric = {k for k, v in src.items() if isinstance(v, (int, float)) or k == "composition_wt"}
            self.assertEqual(set(table), numeric, aid)

    def test_fatigue_fracture_table(self):
        import lpbf_fatigue_fracture as ff
        self.assertEqual(set(reg._FATIGUE_FRACTURE_SOURCE_NAME.values()), set(ff.ALLOY_FATIGUE_DATABASE))
        for aid, src_name in reg._FATIGUE_FRACTURE_SOURCE_NAME.items():
            src = ff.ALLOY_FATIGUE_DATABASE[src_name]
            table = reg.REGISTRY[aid].domains[reg.DOMAIN_FATIGUE_FRACTURE]
            for key, rec in table.items():
                self.assertEqual(rec.value, getattr(src, key), f"{aid}.{key}")

    def test_fatigue_screening_table(self):
        import murakami_fatigue_screening as ms
        self.assertEqual(set(ms.ALLOY_HV_DEFAULTS), set(reg._FATIGUE_SCREENING))
        for aid, hv in ms.ALLOY_HV_DEFAULTS.items():
            self.assertEqual(reg.REGISTRY[aid].value("hardness_HV", reg.DOMAIN_FATIGUE_SCREENING), hv)

    def test_corrosion_table(self):
        import tafel_corrosion_rate_solver as tafel
        self.assertEqual(set(reg._CORROSION_SOURCE_NAME.values()), set(tafel.ALLOY_LIBRARY))
        for aid, src_name in reg._CORROSION_SOURCE_NAME.items():
            src = tafel.ALLOY_LIBRARY[src_name]
            table = reg.REGISTRY[aid].domains[reg.DOMAIN_CORROSION]
            for key, rec in table.items():
                value = dict(rec.value) if key in ("composition", "valencies") else rec.value
                self.assertEqual(value, src[key], f"{aid}.{key}")


class MetadataTest(unittest.TestCase):
    def test_every_value_carries_full_metadata(self):
        count = 0
        for aid, rec in reg.REGISTRY.items():
            self.assertTrue(rec.domains, aid)
            for domain, table in rec.domains.items():
                for key, vr in table.items():
                    count += 1
                    where = f"{aid}/{domain}/{key}"
                    self.assertIsInstance(vr, reg.ValueRecord, where)
                    self.assertTrue(vr.unit, where)
                    self.assertIn(vr.source_type, reg.SOURCE_TYPES, where)
                    self.assertTrue(vr.source_ref, where)
                    self.assertTrue(vr.model_version, where)
                    self.assertTrue(vr.validity is None or isinstance(vr.validity, reg.Validity), where)
                    self.assertIn("sourceType", vr.to_json())
        self.assertGreater(count, 200)

    def test_literature_or_measured_requires_citation(self):
        for aid, rec in reg.REGISTRY.items():
            for domain, table in rec.domains.items():
                for key, vr in table.items():
                    if vr.source_type in ("literature", "measured"):
                        self.assertRegex(vr.source_ref, r"doi|10\.\d{4}|ISBN|ASTM|ISO|AMS",
                                         f"{aid}/{domain}/{key}")

    def test_value_record_rejects_bad_metadata(self):
        with self.assertRaises(reg.RegistryIntegrityError):
            reg.ValueRecord(1.0, "K", "guessed", "x", None, "v1")
        with self.assertRaises(reg.RegistryIntegrityError):
            reg.ValueRecord(1.0, "", "estimated", "x", None, "v1")
        with self.assertRaises(reg.RegistryIntegrityError):
            reg.ValueRecord(1.0, "K", "estimated", "", None, "v1")

    def test_unit_table_missing_key_fails_build(self):
        with self.assertRaises(reg.RegistryIntegrityError):
            reg._domain_table({"new_key": 1.0}, {}, "ref", "v1", "")

    def test_phase_temperature_ordering(self):
        for aid in fam.FOUR_ALLOY_IDS:
            t = reg.REGISTRY[aid].domains[reg.DOMAIN_LPBF_THERMAL]
            self.assertGreater(t["liquidus_C"].value, t["solidus_C"].value, aid)
            self.assertGreater(t["boiling_C"].value, t["liquidus_C"].value, aid)
        for aid in reg.alloys_with_domain(reg.DOMAIN_KINETICS):
            k = reg.REGISTRY[aid].domains[reg.DOMAIN_KINETICS]
            self.assertGreater(k["Ae3_C"].value, k["Ae1_C"].value, aid)
            self.assertGreater(k["Ms_C"].value, k["Mf_C"].value, aid)


class AliasTest(unittest.TestCase):
    def test_aliases_are_unique_across_records(self):
        exact, compact = reg.build_alias_index(reg.REGISTRY)
        self.assertTrue(exact)
        ambiguous = {k: v for k, v in compact.items() if len(v) > 1}
        self.assertEqual(ambiguous, {})

    def test_duplicate_alias_across_records_fails_build(self):
        a = reg.REGISTRY["aisi4140"]
        b = reg.REGISTRY["aisi4340"]
        clash = {"aisi4140": a,
                 "aisi4340": reg.AlloyRecord(b.id, b.display_names, b.base_element,
                                             b.aliases + ("4140",), b.domains)}
        with self.assertRaises(reg.RegistryIntegrityError):
            reg.build_alias_index(clash)

    def test_every_alias_resolves_to_its_record(self):
        for aid, rec in reg.REGISTRY.items():
            for alias in rec.aliases:
                self.assertEqual(reg.resolve_alloy_id(alias), aid, alias)

    def test_registry_is_superset_of_frozen_alias_table(self):
        for alias, aid in fam._ALIAS.items():
            self.assertEqual(reg.resolve_alloy_id(alias), fam.resolve_alloy_id(alias))
            self.assertEqual(reg.resolve_alloy_id(alias), aid)

    def test_ui_strings_resolve(self):
        for name, aid in UI_ALIASES.items():
            with self.subTest(name=name):
                self.assertEqual(reg.resolve_alloy(name).id, aid)

    def test_ui_strings_resolve_in_their_domain(self):
        cases = (
            (("AISI 4140", "AISI 4340", "AISI D2", "Inconel 718", "Ti-6Al-4V", "Al 7075"),
             reg.DOMAIN_KINETICS),
            (("Ti-6Al-4V", "316L SS", "Inconel 718", "AlSi10Mg"), reg.DOMAIN_FATIGUE_FRACTURE),
            (("steel-316l", "steel-304", "steel-1018", "ti-6al-4v", "al-7075", "al-6061",
              "cu-c110", "inconel-718", "az31b"), reg.DOMAIN_CORROSION),
        )
        for names, domain in cases:
            for name in names:
                with self.subTest(name=name, domain=domain):
                    self.assertTrue(reg.resolve_alloy(name, domain).has_domain(domain))

    def test_case_and_separator_insensitive(self):
        self.assertEqual(reg.resolve_alloy_id("  aisi   4140 "), "aisi4140")
        self.assertEqual(reg.resolve_alloy_id("TI_6AL_4V"), "ti6al4v")
        self.assertEqual(reg.resolve_alloy_id("Ti 6Al 4V"), "ti6al4v")


class NoSilentDefaultTest(unittest.TestCase):
    def test_golden_silent_default_names_raise(self):
        for name in GOLDEN_SILENT_DEFAULT_NAMES:
            with self.subTest(name=name):
                with self.assertRaises(reg.UnknownAlloyError):
                    reg.resolve_alloy(name)

    def test_non_string_names_raise(self):
        for name in (None, 4140, 3.5, ["in718"], {"id": "in718"}):
            with self.subTest(name=name):
                with self.assertRaises(reg.UnknownAlloyError):
                    reg.resolve_alloy(name)

    def test_kinetics_unknown_alloy_does_not_become_4140(self):
        with self.assertRaises(reg.UnknownAlloyError) as ctx:
            reg.resolve_alloy("Unobtainium XYZ", reg.DOMAIN_KINETICS)
        self.assertEqual(ctx.exception.domain, reg.DOMAIN_KINETICS)
        self.assertEqual(ctx.exception.code, "UNKNOWN_ALLOY")

    def test_registered_alloy_without_domain_data_raises(self):
        # Kinetics has no AlSi10Mg data; today the solver would silently use AISI 4140.
        with self.assertRaises(reg.UnknownAlloyError) as ctx:
            reg.resolve_alloy("AlSi10Mg", reg.DOMAIN_KINETICS)
        self.assertEqual(ctx.exception.reason, "no-domain-data")
        self.assertIn("aisi4140", ctx.exception.suggestions)
        # Tafel has no AlSi10Mg or duplex 2205 entry; today it silently uses steel-316l.
        with self.assertRaises(reg.UnknownAlloyError):
            reg.resolve_alloy("alsi10mg", reg.DOMAIN_CORROSION)

    def test_fatigue_display_and_lowercase_names_resolve_to_the_right_alloy(self):
        # murakami: "Ti-6Al-4V" fell to the generic 350 HV; fatigue_fracture: lowercase fell to Ti64.
        self.assertEqual(reg.get_value("Ti-6Al-4V", "hardness_HV", reg.DOMAIN_FATIGUE_SCREENING).value, 340.0)
        self.assertEqual(reg.get_value("inconel 718", "hardness_HV", reg.DOMAIN_FATIGUE_FRACTURE).value, 440.0)

    def test_missing_property_raises(self):
        rec = reg.resolve_alloy("in718", reg.DOMAIN_LPBF_THERMAL)
        with self.assertRaises(reg.MissingPropertyError) as ctx:
            rec.get("melting_point_K", reg.DOMAIN_LPBF_THERMAL)
        self.assertEqual(ctx.exception.code, "MISSING_PROPERTY")
        with self.assertRaises(reg.MissingPropertyError):
            rec.get("density_kg_m3", "no_such_domain")

    def test_unknown_name_offers_suggestions(self):
        with self.assertRaises(reg.UnknownAlloyError) as ctx:
            reg.resolve_alloy("inconel 71")
        self.assertTrue(ctx.exception.suggestions)

    def test_compact_collision_raises_ambiguous(self):
        exact = dict(reg._EXACT_INDEX)
        compact = dict(reg._COMPACT_INDEX)
        compact["fooalloy"] = frozenset({"aisi4140", "aisi4340"})
        with mock.patch.object(reg, "_EXACT_INDEX", exact), \
                mock.patch.object(reg, "_COMPACT_INDEX", compact):
            with self.assertRaises(reg.AmbiguousAlloyError) as ctx:
                reg.resolve_alloy("foo-alloy")
        self.assertEqual(ctx.exception.candidates, ("aisi4140", "aisi4340"))

    def test_registry_is_read_only(self):
        self.assertIsInstance(reg.REGISTRY, MappingProxyType)
        with self.assertRaises(TypeError):
            reg.REGISTRY["x"] = None  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
