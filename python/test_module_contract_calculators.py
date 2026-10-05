import json
import re
import unittest
from pathlib import Path

from module_contract import ContractError, ModuleContract, contract_from_dict
from module_contracts_calculators import CALCULATORS_OPERATIONS, build_calculators_contract


ROOT = Path(__file__).resolve().parents[1]


class CalculatorsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = json.loads((ROOT / "python" / "module_registry_seed.json").read_text(encoding="utf-8"))
        cls.seed = next(row for row in rows if row["id"] == "calculators")
        cls.contract = build_calculators_contract(cls.seed)
        cls.operations = {operation.id: operation for operation in CALCULATORS_OPERATIONS}

    def test_seed_identity_and_full_contract_round_trip(self):
        contract = self.contract
        self.assertIsInstance(contract, ModuleContract)
        self.assertEqual((contract.id, contract.workspace, contract.maturity),
                         ("calculators", "materials", "Research"))
        self.assertEqual(contract.seed_derived, ("label", "description", "next", "maturity"))
        self.assertEqual((contract.view.component, contract.view.export),
                         ("src/components/PocketCalculators.tsx", "PocketCalculators"))
        self.assertEqual(contract.migration_state, "contracted")
        self.assertEqual(contract.evidence.ceiling, "screening-only")
        self.assertEqual(contract.evidence.emits, ())
        self.assertEqual(contract.tests.oracle.status, "pending")
        self.assertEqual(contract.lifecycle.background_work, "none")
        self.assertEqual(contract_from_dict(contract.to_dict()).to_dict(), contract.to_dict())

    def test_reachable_tabs_unit_categories_and_quick_grid_are_declared(self):
        expected = {
            "select-calculator-tab", "sync-from-active-specimen", "calculate-hardness",
            "apply-hardness-preset", "calculate-weldability", "reset-weldability-s355",
            "simulate-diffusion", "calculate-schaeffler", "apply-schaeffler-preset", "calculate-xrd",
            "apply-xrd-structure-preset", "calculate-hall-petch", "calculate-transformation",
            "filter-quick-conversions", "toggle-quick-conversions", "open-full-unit-suite", "convert-quick-stress",
            "apply-quick-stress-preset", "convert-quick-hardness", "apply-quick-hardness-preset",
            "convert-quick-temperature", "apply-quick-temperature-preset", "load-quick-active-specimen",
            "copy-quick-conversion-value", "select-unit-category", "convert-unit-suite-stress",
            "convert-unit-suite-hardness", "convert-unit-suite-temperature", "convert-fracture-toughness",
            "apply-unit-suite-hardness-preset",
            "convert-charpy-impact-energy", "convert-micro-length", "calculate-astm-e112-grain-size",
            "convert-corrosion-rate", "sync-unit-report-from-specimen", "calculate-dual-unit-report",
            "copy-formatted-report", "copy-unit-suite-conversion-value",
        }
        self.assertEqual(set(self.operations), expected)
        self.assertTrue(all(op.route is None and op.method is None for op in self.operations.values()))
        self.assertTrue(all(op.authority.kind == "browser-local" and op.authority.timeout_ms is None
                            for op in self.operations.values()))

        tabs = self.operations["select-calculator-tab"].input[0]
        self.assertEqual(tabs.enum, ("units", "hardness", "weldability", "diffusion", "schaeffler", "xrd", "hall-petch", "transformation"))
        categories = self.operations["select-unit-category"].input[0]
        self.assertEqual(categories.enum, ("stress", "hardness", "temperature", "toughness", "grain_length", "corrosion", "report_matrix"))
        self.assertIn("searchQuery", self.operations["filter-quick-conversions"].undeclared_input)
        self.assertIn("copy-quick-conversion-value", self.operations)

    def test_hardness_value_has_conditional_unit_and_real_material_class_enum(self):
        operation = self.operations["calculate-hardness"]
        fields = {field.key: field for field in operation.input}
        self.assertEqual(fields["hardnessVal"].unit, "scale-dependent (hardnessScale)")
        self.assertEqual(fields["hardnessVal"].quantity_kind, "hardness")
        self.assertIsNone(fields["hardnessVal"].min)
        self.assertIsNone(fields["hardnessVal"].max)
        self.assertEqual(fields["hardnessScale"].enum, ("HRC", "HV", "HRB", "HBW", "HBS"))
        self.assertEqual(fields["hardnessClass"].enum,
                         ("non-austenitic-steel", "austenitic-steel", "titanium-alloy", "nickel-alloy",
                          "aluminium-alloy", "hardmetal", "other"))
        self.assertEqual(operation.input_problems({"hardnessVal": 34, "hardnessScale": "HRC",
                                                   "hardnessClass": "titanium-alloy"}), [])
        self.assertTrue(any("hardnessScale" in problem for problem in
                            operation.input_problems({"hardnessVal": 34, "hardnessScale": "HVX",
                                                      "hardnessClass": "titanium-alloy"})))
        self.assertTrue(any("hardnessVal" in problem for problem in
                            operation.input_problems({"hardnessVal": None, "hardnessScale": "HRC",
                                                      "hardnessClass": "titanium-alloy"})))

    def test_composition_maps_are_explicitly_undeclared_and_slider_ranges_are_not_hard_bounds(self):
        for operation_id, key in (("calculate-weldability", "ceComp"),
                                  ("calculate-schaeffler", "schaefflerComp"),
                                  ("calculate-transformation", "ttComp")):
            operation = self.operations[operation_id]
            self.assertIn(key, operation.undeclared_input)
            self.assertNotIn(key, {field.key for field in operation.input})
        thickness = next(field for field in self.operations["calculate-weldability"].input
                         if field.key == "plateThickness")
        self.assertIsNone(thickness.min)
        self.assertIsNone(thickness.max)
        self.assertIn("slider", thickness.note)
        self.assertIn("physical validity", thickness.note)

    def test_outputs_capture_real_result_surfaces_and_sync_preserves_prior_values(self):
        expected_outputs = {
            "calculate-weldability": {"ceResult", "ceIIW", "pcm", "cen", "recommendedPreheatTemp"},
            "simulate-diffusion": {"diffusionResult", "profileData", "effectiveCaseDepth", "caseDepth", "diffusivity"},
            "calculate-xrd": {"xrdPeaks", "twoTheta", "dSpacing", "hkl", "intensityPct"},
            "calculate-hall-petch": {"hallPetchResult", "grainSizeMicrons", "yieldStrengthMpa", "strengtheningIncrement", "astmG"},
            "calculate-astm-e112-grain-size": {"astmResult", "gNumber", "meanInterceptUm", "meanInterceptMm", "grainsPerMm2", "grainsPerSqInch100x", "classification"},
            "calculate-transformation": {"ttResult", "ms", "mf", "bs", "ac1", "ac3"},
            "sync-from-active-specimen": {"ceComp", "schaefflerComp", "ttComp", "xrdStructure", "latticeA", "syncToast"},
            "calculate-dual-unit-report": {"reportCalculated", "yieldKsi", "utsKsi", "hardnessText", "cvnFtLbf", "tempF", "tempK"},
        }
        for operation_id, expected in expected_outputs.items():
            self.assertTrue(expected.issubset(set(self.operations[operation_id].output.fields)), operation_id)
        self.assertEqual(self.operations["sync-from-active-specimen"].output.status_key, None)
        self.assertEqual(self.operations["sync-from-active-specimen"].undeclared_input, ("activeMaterialSpecimen",))

    def test_contract_source_references_resolve_to_the_declared_symbols(self):
        required_symbols = (
            "handleSyncFromActiveSpecimen", "MetallurgicalQuickConversionsGrid", "setActiveTab",
            "MetallurgicalUnitConverter", "HARDNESS_MATERIAL_CLASSES", "METALLURGICAL_MELTING_PRESETS",
            "convertStress", "calculateCarbonEquivalent", "calculateXrdPeaks",
        )
        corpus = "\n".join(path.read_text(encoding="utf-8") for path in (
            ROOT / "src/components/PocketCalculators.tsx",
            ROOT / "src/components/MetallurgicalUnitConverter.tsx",
            ROOT / "src/components/MetallurgicalQuickConversionsGrid.tsx",
            ROOT / "src/utils/hardnessConversion.ts",
            ROOT / "src/utils/metallurgicalConversions.ts",
            ROOT / "src/utils/metallurgyCalculations.ts",
        ))
        for symbol in required_symbols:
            self.assertIn(symbol, corpus)

        refs = self.contract.source_refs
        self.assertGreaterEqual(len(refs), 15)
        for ref in refs:
            match = re.fullmatch(r"([^:]+):(\d+)-(\d+)#(.+)", ref)
            self.assertIsNotNone(match, ref)
            rel_path, start, end, _label = match.groups()
            source_path = ROOT / rel_path
            self.assertTrue(source_path.is_file(), rel_path)
            lines = source_path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(1 <= int(start) <= int(end) <= len(lines), ref)

        pocket = (ROOT / "src/components/PocketCalculators.tsx").read_text(encoding="utf-8")
        self.assertIn('useState<CalcTab>("units")', pocket)
        self.assertLess(pocket.index("<MetallurgicalQuickConversionsGrid"), pocket.index('{activeTab === "units"'))
        self.assertIn("C: comp.C ?? prev.C", pocket)
        self.assertIn("N: prev.N", pocket)
        self.assertIn("if (activeMaterialSpecimen.xrd)", pocket)
        self.assertIn("if (activeMaterialSpecimen.xrd.latticeA_A > 0)", pocket)
        self.assertIn('onOpenFullSuite={() => setActiveTab("units")}', pocket)
        self.assertIn("setTimeout(() => setSyncToast(null), 3000)", pocket)

        hardness_source = (ROOT / "src/utils/hardnessConversion.ts").read_text(encoding="utf-8")
        class_block = re.search(r"export const HARDNESS_MATERIAL_CLASSES[^=]*= \[(.*?)\n\];", hardness_source, re.S)
        self.assertIsNotNone(class_block)
        source_classes = tuple(re.findall(r'id: "([a-z-]+)"', class_block.group(1)))
        self.assertEqual(source_classes, self.operations["calculate-hardness"].input[2].enum)
        hardness_scale = re.search(r'export type HardnessScale = [^;]+;', hardness_source)
        self.assertIsNotNone(hardness_scale)
        all_scales = tuple(re.findall(r'"([^\"]+)"', hardness_scale.group(0)))
        full_scale_field = next(field for field in self.operations["convert-unit-suite-hardness"].input
                                if field.key == "hardnessScale")
        self.assertEqual(all_scales, full_scale_field.enum)
        self.assertEqual(all_scales, self.operations["convert-unit-suite-hardness"].input[1].enum)

        preset_source = (ROOT / "src/utils/hardnessPresets.ts").read_text(encoding="utf-8")
        preset_block = re.search(r"export const HARDNESS_PRESETS[^=]*= \[(.*?)\n\];", preset_source, re.S)
        self.assertIsNotNone(preset_block)
        preset_names = tuple(re.findall(r'name: "([^"]+)"', preset_block.group(1)))
        self.assertEqual(preset_names, self.operations["apply-hardness-preset"].input[0].enum)
        self.assertEqual(tuple(name for name in preset_names if name != "316L Annealed"),
                         self.operations["apply-quick-hardness-preset"].input[0].enum)

        conversion_source = (ROOT / "src/utils/metallurgicalConversions.ts").read_text(encoding="utf-8")
        stress_type = re.search(r'export type StressUnit = "([^"]+)"(?: \| "([^"]+)")*;', conversion_source)
        self.assertIsNotNone(stress_type)
        stress_values = tuple(re.findall(r'"([^"]+)"', stress_type.group(0)))
        self.assertEqual(stress_values, self.operations["convert-unit-suite-stress"].input[1].enum)

        for type_name, operation_id, field_key in (
            ("TempUnit", "convert-unit-suite-temperature", "tempUnit"),
            ("FractureToughnessUnit", "convert-fracture-toughness", "kicUnit"),
            ("ImpactEnergyUnit", "convert-charpy-impact-energy", "cvnUnit"),
            ("LengthUnit", "convert-micro-length", "lengthUnit"),
            ("CorrosionRateUnit", "convert-corrosion-rate", "crUnit"),
        ):
            source_enum = re.search(rf'export type {type_name} = [^;]+;', conversion_source)
            self.assertIsNotNone(source_enum, type_name)
            values = tuple(re.findall(r'"([^"]+)"', source_enum.group(0)))
            field = next(item for item in self.operations[operation_id].input if item.key == field_key)
            self.assertEqual(set(values), set(field.enum), type_name)

        report_scale = re.search(r'export type ReportHardnessScale = [^;]+;', conversion_source)
        self.assertIsNotNone(report_scale)
        report_values = tuple(re.findall(r'"([^"]+)"', report_scale.group(0)))
        report_field = next(item for item in self.operations["calculate-dual-unit-report"].input
                            if item.key == "reportHardnessScale")
        self.assertEqual(report_values, report_field.enum)

        melting_source = re.search(r"export const METALLURGICAL_MELTING_PRESETS[^=]*= \[(.*?)\n\];", conversion_source, re.S)
        self.assertIsNotNone(melting_source)
        melting_names = re.findall(r'name: "([^"]+)"', melting_source.group(1))
        self.assertEqual(len(melting_names), 9)
        melting_index = next(field for field in self.operations["convert-unit-suite-temperature"].input
                             if field.key == "selectedMeltingPresetIdx")
        self.assertEqual((melting_index.value_type, melting_index.min, melting_index.max, melting_index.default),
                         ("integer", 0, len(melting_names) - 1, 0))

        # The cited calculation spans must actually contain their named source entry points.
        for source_ref, symbol in (
            ("src/utils/metallurgyCalculations.ts:58-123#calculateCarbonEquivalent", "calculateCarbonEquivalent"),
            ("src/utils/metallurgyCalculations.ts:124-183#calculateSchaeffler", "calculateSchaeffler"),
            ("src/utils/metallurgyCalculations.ts:184-213#calculateTransformationTemps", "calculateTransformationTemps"),
            ("src/utils/metallurgyCalculations.ts:214-267#simulateCarburizingDiffusion", "simulateCarburizingDiffusion"),
            ("src/utils/metallurgyCalculations.ts:268-296#calculateHallPetch", "calculateHallPetch"),
            ("src/utils/metallurgyCalculations.ts:297-347#calculateXrdPeaks", "calculateXrdPeaks"),
        ):
            self.assertIn(source_ref, refs)
            path_and_lines, _label = source_ref.split("#")
            rel, line_range = path_and_lines.rsplit(":", 1)
            start, end = map(int, line_range.split("-"))
            snippet = "\n".join((ROOT / rel).read_text(encoding="utf-8").splitlines()[start - 1:end])
            self.assertIn(symbol, snippet, source_ref)

    def test_seed_identity_rejection_remains_active(self):
        bad_seed = {**self.seed, "id": "Calculators App"}
        with self.assertRaises(ContractError):
            build_calculators_contract(bad_seed)


if __name__ == "__main__":
    unittest.main()
