import json
import re
import unittest
from pathlib import Path

import module_registry as mr
from module_contract import ContractError, ModuleContract
from module_contracts_database import DATABASE_OPERATIONS, HEATMAP_OPERATIONS, build_database_contract

REPO_ROOT = Path(__file__).resolve().parents[1]


def read_product_source(relative_path):
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class DatabaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = json.loads(Path(__file__).with_name("module_registry_seed.json").read_text(encoding="utf-8"))
        cls.seed = next(row for row in rows if row["id"] == "database")

    def test_builder_preserves_seed_identity_and_sets_evidence_ceiling(self):
        contract = build_database_contract(self.seed)

        self.assertIsInstance(contract, ModuleContract)
        self.assertEqual(
            (contract.id, contract.workspace, contract.label, contract.description, contract.next, contract.maturity),
            ("database", "materials", "Materials Database",
             "Handbook values and reviewed research references; source applicability requires review.",
             "alloy-builder", "Research"),
        )
        self.assertEqual(contract.seed_derived, ("label", "description", "next", "maturity"))
        self.assertEqual((contract.view.component, contract.view.export),
                         ("src/components/MaterialsDatabaseView.tsx", "MaterialsDatabaseView"))
        self.assertEqual(contract.evidence.ceiling, "screening-only")
        self.assertEqual(contract.evidence.emits, ())
        self.assertEqual(contract.tests.oracle.status, "pending")
        self.assertEqual(contract.lifecycle.background_work, "none")
        self.assertEqual(contract.lifecycle.resources, ())

    def test_local_view_interactions_are_separate_and_not_routes(self):
        operations = {operation.id: operation for operation in DATABASE_OPERATIONS}
        self.assertEqual(
            tuple(operations),
            ("search-catalog", "filter-by-category", "filter-by-min-yield-strength",
             "filter-by-min-modulus", "filter-by-max-density", "reset-property-range-filters",
             "toggle-property-filter-panel", "switch-view-mode", "sort-catalog", "select-material-record",
             "toggle-comparison-record", "open-comparison-drawer", "close-comparison-drawer",
             "copy-selected-record", "export-catalog-json", "open-transfer-picker", "dispatch-material-to-module"),
        )
        self.assertTrue(all(op.route is None and op.method is None for op in operations.values()))
        self.assertTrue(all(op.authority.kind == "browser-local" and op.authority.timeout_ms is None
                            for op in operations.values()))
        self.assertTrue(all(op.output.status_key is None for op in operations.values()))
        self.assertEqual(operations["select-material-record"].undeclared_input, ("material",))
        self.assertEqual(operations["sort-catalog"].output.fields, ("sortedMaterials",))
        self.assertEqual(operations["toggle-comparison-record"].output.fields, ("compareList",))
        self.assertEqual(operations["toggle-property-filter-panel"].output.fields, ("showFilters",))
        self.assertEqual(operations["open-comparison-drawer"].output.fields, ("isCompareOpen",))
        self.assertEqual(operations["close-comparison-drawer"].output.fields, ("isCompareOpen",))
        self.assertEqual(operations["copy-selected-record"].output.fields,
                         ("clipboardWriteAttempt", "optimisticCopyFeedback"))
        self.assertEqual(operations["export-catalog-json"].output.fields, ("fullCatalogJsonDownload",))
        self.assertEqual(operations["dispatch-material-to-module"].input[0].enum,
                         ("alloy-builder", "icme-motor", "3d-distortion-lab", "phase-diagram"))

    def test_filters_use_real_controls_without_claiming_hard_material_bounds(self):
        operations = {operation.id: operation for operation in DATABASE_OPERATIONS}
        category = operations["filter-by-category"]
        fields = {field.key: field for field in category.input}

        self.assertEqual(fields["selectedCategory"].enum, (
            "All", "Carbon Steel", "Alloy Steel", "Tool Steel", "Stainless Steel", "Aluminum Alloy",
            "Copper Alloy", "Titanium Alloy", "Nickel Superalloy", "Magnesium Alloy",
            "Refractory & Specialty", "Ceramic & Carbide",
        ))
        self.assertEqual(operations["search-catalog"].undeclared_input, ("searchQuery",))
        self.assertEqual(fields["selectedCategory"].value_problem("Nickel Superalloy"), None)
        self.assertIsNotNone(fields["selectedCategory"].value_problem("Invented category"))
        self.assertEqual(category.input_problems({"selectedCategory": "All"}), [])
        search = operations["search-catalog"]
        self.assertEqual(search.input_problems({"searchQuery": "718"}), [])
        self.assertTrue(any("composition" in problem for problem in search.input_problems(
            {"searchQuery": "718", "composition": {"Ni": 100}}
        )))
        for operation_id, key, default, step in (
            ("filter-by-min-yield-strength", "minYield", 0, 50),
            ("filter-by-min-modulus", "minModulus", 40, 10),
            ("filter-by-max-density", "maxDensity", 17.0, 0.2),
        ):
            field = operations[operation_id].input[0]
            self.assertEqual(field.key, key)
            self.assertEqual((field.default, field.step), (default, step))
            self.assertIsNone(field.min)
            self.assertIsNone(field.max)

    def test_sort_keys_and_target_options_match_visible_controls(self):
        operations = {operation.id: operation for operation in DATABASE_OPERATIONS}
        sort_fields = {field.key: field for field in operations["sort-catalog"].input}
        self.assertEqual(sort_fields["sortBy"].enum,
                         ("yield", "tensile", "specific_strength", "modulus", "density", "name"))
        self.assertEqual(sort_fields["sortOrder"].enum, ("desc", "asc"))
        self.assertEqual(sort_fields["sortBy"].value_problem("specific_strength"), None)
        self.assertIsNotNone(sort_fields["sortBy"].value_problem("hardness"))
        self.assertEqual({field.key: field.enum for field in operations["switch-view-mode"].input}["activeTab"],
                         ("split", "heatmap", "catalog"))
        self.assertIsNotNone(operations["dispatch-material-to-module"].input[0].value_problem("database"))

    def test_density_filter_drawers_copy_and_export_match_current_component_source(self):
        source = read_product_source("src/components/MaterialsDatabaseView.tsx")
        self.assertRegex(
            source,
            re.compile(
                r'<input aria-label="Maximum Density \(ρ\) \(g/cm³\)"\s+type="range"\s+'
                r'min="1\.5"\s+max="17\.0"\s+step="0\.2"\s+value=\{maxDensity\}\s+'
                r'onChange=\{\(e\) => setMaxDensity\(Number\(e\.target\.value\)\)\}',
                re.S,
            ),
        )
        self.assertIn("onClick={() => setShowFilters(!showFilters)}", source)
        self.assertIn("{showFilters && (", source)
        self.assertIn("onClick={() => setIsCompareOpen(true)}", source)
        self.assertIn("{isCompareOpen && (", source)
        self.assertIn("onClose={() => setIsCompareOpen(false)}", source)

        copy_handler = source.split("const handleCopySpec = () => {", 1)[1].split(
            "const handleExportAllJSON = () => {", 1
        )[0]
        self.assertRegex(copy_handler, r"navigator\.clipboard\.writeText\(jsonStr\);\s*setCopied\(true\);")
        self.assertNotIn("await navigator.clipboard.writeText", copy_handler)
        self.assertNotIn(".catch(", copy_handler)
        export_handler = source.split("const handleExportAllJSON = () => {", 1)[1].split("\n  };", 1)[0]
        self.assertIn("JSON.stringify(MATERIALS_DATABASE, null, 2)", export_handler)
        self.assertNotIn("filteredMaterials", export_handler)
        self.assertIn("URL.revokeObjectURL(url)", export_handler)

    def test_provenance_limits_and_derived_transfer_are_explicit(self):
        contract = build_database_contract(self.seed)
        notes = " ".join(contract.legacy_notes)
        self.assertIn("no per-property source citation", notes)
        self.assertIn("range-midpoint", notes)
        self.assertIn("source property values/confidence are not promoted", notes)
        self.assertIn("rather than inventing a record-ID endpoint or object schema", notes)
        self.assertIn("350 ms", notes)
        self.assertIn("2000 ms", notes)
        self.assertIn("not a database measurement", notes)
        self.assertIn("not provider/server execution", notes)
        self.assertIn("indexes 0 and 5", notes)
        self.assertIn("attempted copy, not confirmed clipboard success", notes)
        self.assertIn("full MATERIALS_DATABASE array, independent of active filters", notes)
        self.assertIn("maxYield, maxModulus, and minDensity remain at their initialized values", notes)
        self.assertIn("Slider limits and steps are control settings", notes)
        self.assertIn("local showFilters toggle", notes)
        self.assertIn("No fetch, worker, solver", notes)
        self.assertIn("physical validation", contract.evidence.note)

    def test_heatmap_child_controls_plot_selection_and_mode_specific_tooltips_are_inventory_items(self):
        operations = {operation.id: operation for operation in HEATMAP_OPERATIONS}
        self.assertEqual(tuple(operations), (
            "render-heatmap",
            "set-heatmap-mode", "set-heatmap-property", "set-heatmap-element",
            "sort-heatmap-alloys", "set-heatmap-palette", "select-heatmap-element-from-axis",
            "select-heatmap-property-from-axis", "select-composition-cell", "select-binned-bucket",
            "select-scatter-point", "inspect-composition-cell", "inspect-binned-cell",
            "clear-heatmap-tooltip",
            "export-heatmap-svg",
        ))
        self.assertEqual(operations["set-heatmap-mode"].input[0].enum,
                         ("alloy-elements", "element-property-binned"))
        self.assertEqual(operations["set-heatmap-property"].input[0].enum, (
            "yieldStrength", "tensileStrength", "youngsModulus", "density", "specificStrength",
            "elongation", "thermalConductivity",
        ))
        self.assertEqual(operations["set-heatmap-element"].input[0].enum,
                         ("C", "Cr", "Ni", "Mo", "Ti", "Al", "Cu", "V", "Mn", "Si", "Mg", "W",
                          "Co", "Nb", "Zr", "Fe"))
        self.assertEqual(operations["sort-heatmap-alloys"].input[0].enum,
                         ("property", "element", "category", "name"))
        self.assertEqual(operations["set-heatmap-palette"].input[0].enum,
                         ("viridis", "plasma", "turbo", "emerald", "amber-flame"))
        self.assertEqual(operations["select-composition-cell"].undeclared_input, ("mat", "elem"))
        self.assertEqual(operations["render-heatmap"].undeclared_input, ("materials", "selectedMaterial"))
        self.assertEqual(operations["select-binned-bucket"].undeclared_input, ("b",))
        self.assertEqual(operations["select-heatmap-property-from-axis"].undeclared_input, ("prop",))
        self.assertEqual(operations["select-scatter-point"].undeclared_input, ("mat",))
        self.assertEqual(operations["inspect-composition-cell"].undeclared_input, ("mat", "elem", "wt"))
        self.assertEqual(operations["inspect-composition-cell"].output.fields,
                         ("hoveredCell", "xLabel", "yLabel", "value", "unit", "material", "extraInfo",
                          "xPos", "yPos"))
        self.assertEqual(operations["inspect-binned-cell"].undeclared_input, ("b",))
        self.assertEqual(operations["export-heatmap-svg"].output.fields,
                         ("source", "blob", "url", "download"))
        self.assertTrue(all(operation.route is None and operation.method is None
                            and operation.output.status_key is None for operation in operations.values()))

        source = read_product_source("src/components/MaterialsPropertyHeatmapD3.tsx")
        for exact_control in (
            '"alloy-elements" | "element-property-binned";',
            '"yieldStrength", label: "Yield Strength (σy)", unit: "MPa"',
            '"specificStrength", label: "Specific Strength (σy/ρ)", unit: "kN·m/kg"',
            '"thermalConductivity", label: "Thermal Conductivity", unit: "W/(m·K)"',
            '"C", "Cr", "Ni", "Mo", "Ti", "Al", "Cu", "V", "Mn", "Si", "Mg", "W", "Co", "Nb", "Zr", "Fe"',
            'onChange={(e) => setSelectedPropertyKey(e.target.value)}',
            'onChange={(e) => setSelectedElement(e.target.value)}',
            'onChange={(e) => setColorPalette(e.target.value as ColorPaletteKey)}',
            '.on("click", () => onSelectMaterial(mat))',
            'a.download = `Materials_Heatmap_${heatmapMode}_${selectedPropertyKey}.svg`',
        ):
            with self.subTest(source_fragment=exact_control):
                self.assertIn(exact_control, source)

    def test_heatmap_lifecycle_matches_observer_and_render_effect_cleanup(self):
        contract = build_database_contract(self.seed)
        notes = " ".join(contract.legacy_notes)
        self.assertIn("ResizeObserver", notes)
        self.assertIn("disconnects", notes)
        self.assertIn("D3-render effect has no cleanup function", notes)
        self.assertIn('activeTab is "split" or "heatmap"', notes)
        self.assertIn("catalog mode unmounts it", notes)
        self.assertIn("If displayedMaterials becomes empty", notes)
        self.assertIn("categories, activeCategory, and onSelectCategory are passed but unused", notes)
        self.assertIn("neither has a current UI setter", notes)
        self.assertIn("materials: MaterialSpec[]", notes)
        self.assertIn("optional onSelectCategory(string)", notes)
        self.assertEqual(contract.lifecycle.background_work, "none")
        self.assertEqual(contract.lifecycle.resources, ())
        source = read_product_source("src/components/MaterialsPropertyHeatmapD3.tsx")
        resize_effect = source.split("// ResizeObserver for fluid responsive D3 rendering", 1)[1].split(
            "// Main D3 Rendering Engine", 1
        )[0]
        render_effect = source.split("// Main D3 Rendering Engine", 1)[1].split("const handleExportSVG", 1)[0]
        self.assertIn("return () => observer.disconnect()", resize_effect)
        self.assertIn("if (!svgRef.current || displayedMaterials.length === 0) return", render_effect)
        self.assertNotIn("return () =>", render_effect)
        parent = read_product_source("src/components/MaterialsDatabaseView.tsx")
        self.assertIn('(activeTab === "split" || activeTab === "heatmap")', parent)

    def test_contract_source_references_resolve_and_use_generated_docs_placeholder(self):
        contract = build_database_contract(self.seed)
        generated = frozenset({mr.module_doc_path("database")})
        self.assertEqual(contract.tests.docs, "docs/modules/database.md")
        self.assertEqual(mr.contract_ref_problems(contract, root=REPO_ROOT, generated=generated), [])
        self.assertIn("src/components/MaterialsPropertyHeatmapD3.tsx::MaterialsPropertyHeatmapD3",
                      contract.source_refs)
        self.assertIn("src/utils/materialDataPipeline.ts:666-715#createPipelinePayloadFromMaterialSpec",
                      contract.source_refs)

    def test_invalid_seed_identity_is_rejected(self):
        with self.assertRaises(ContractError):
            build_database_contract({**self.seed, "id": "Materials Database"})


if __name__ == "__main__":
    unittest.main()
