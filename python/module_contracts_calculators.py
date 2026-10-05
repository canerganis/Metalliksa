"""Source-bounded Module SDK contract for the browser-local calculator suite."""

from typing import Mapping, Tuple

from module_contract import (
    FORBIDDEN_CLAIM_KEYS,
    OWNER_UNASSIGNED,
    PENDING_ORACLE_CEILING,
    Authority,
    ContractError,
    Evidence,
    InputField,
    Lifecycle,
    ModuleContract,
    Operation,
    Oracle,
    OutputSchema,
    TestRefs,
    View,
)

CONTRACT_VERSION = "0.1.0"

_BROWSER_LOCAL_REASON = (
    "Calculator formulas and state transitions run synchronously in React local state; "
    "they have no server route, Python worker, or declared execution deadline."
)
_NO_HARD_BOUND = "No code or independent source establishes a hard validity bound. UI slider extents are presentation ranges only."


def _number(key: str, label: str, unit: str, quantity: str, default: float, *, note: str = _NO_HARD_BOUND) -> InputField:
    return InputField(key=key, label=label, unit=unit, quantity_kind=quantity, min=None, max=None,
                      default=default, required=True, note=note)


def _enum(key: str, label: str, quantity: str, default: str, values: Tuple[str, ...]) -> InputField:
    return InputField(key=key, label=label, unit=None, quantity_kind=quantity, min=None, max=None,
                      default=default, value_type="enum", enum=values, required=True)


def _selected(key, label, selector, options, quantity, default, note=_NO_HARD_BOUND):
    return InputField(key=key, label=label, unit=None, unit_selector=selector,
                      unit_options=tuple(options), quantity_kind=quantity,
                      min=None, max=None, default=default, required=True, note=note)


def _browser_operation(
    operation_id: str,
    *,
    fields: Tuple[InputField, ...] = (),
    undeclared: Tuple[str, ...] = (),
    outputs: Tuple[str, ...],
) -> Operation:
    return Operation(
        id=operation_id,
        route=None,
        method=None,
        authority=Authority(kind="browser-local", timeout_ms=None, exception_reason=_BROWSER_LOCAL_REASON),
        input=fields,
        undeclared_input=undeclared,
        output=OutputSchema(fields=outputs, status_key=None),
    )


_HARDNESS_CLASSES = (
    "non-austenitic-steel", "austenitic-steel", "titanium-alloy", "nickel-alloy",
    "aluminium-alloy", "hardmetal", "other",
)
_HARDNESS_SCALES = ("HRC", "HV", "HRB", "HBW", "HBS")
_ALL_HARDNESS_SCALES = ("HRC", "HV", "HRB", "HBW", "HBS", "HK", "HLD")
_STRESS_UNITS = (("MPa", "MPa"), ("ksi", "ksi"), ("GPa", "GPa"), ("psi", "psi"),
                 ("bar", "bar"), ("kgf_mm2", "kgf/mm^2"), ("N_mm2", "N/mm^2"))
_TEMP_UNITS = (("C", "degC"), ("K", "K"), ("F", "degF"), ("R", "degR"))
_KIC_UNITS = (("MPa_m05", "MPa*sqrt(m)"), ("ksi_in05", "ksi*sqrt(in)"),
              ("N_mm15", "N/mm^(3/2)"), ("MPa_mm05", "MPa*sqrt(mm)"))
_CVN_UNITS = (("J", "J"), ("ft_lbf", "ft*lbf"), ("kgf_m", "kgf*m"), ("J_cm2", "J/cm^2"))
_LENGTH_UNITS = (("angstrom", "angstrom"), ("nm", "nm"), ("um", "µm"),
                 ("mm", "mm"), ("mil", "mil"), ("in", "in"))
_CR_UNITS = (("mpy", "mpy"), ("mm_yr", "mm/yr"), ("um_yr", "µm/yr"),
             ("nm_day", "nm/day"), ("g_m2_day", "g/(m^2*day)"))
_HARDNESS_PRESETS = (
    "316L Annealed", "Ti-6Al-4V Annealed", "Inconel 718 Aged", "4140 Q&T",
    "AerMet 100", "52100 Bearing Steel", "M2 High-Speed Tool",
)
_QUICK_HARDNESS_PRESETS = tuple(name for name in _HARDNESS_PRESETS if name != "316L Annealed")

CALCULATORS_OPERATIONS: Tuple[Operation, ...] = (
    _browser_operation("select-calculator-tab", fields=(_enum(
        "activeTab", "Selected calculator tab", "calculator-tab", "units",
        ("units", "hardness", "weldability", "diffusion", "schaeffler", "xrd", "hall-petch", "transformation"),
    ),), outputs=("activeTab",)),
    _browser_operation("sync-from-active-specimen", undeclared=("activeMaterialSpecimen",), outputs=(
        "ceComp", "schaefflerComp", "ttComp", "xrdStructure", "latticeA", "syncToast",
    )),
    _browser_operation("calculate-hardness", fields=(
        _selected("hardnessVal", "Measured hardness value", "hardnessScale",
                  tuple((scale, scale) for scale in _HARDNESS_SCALES), "hardness", 30.0,
                note="Value is interpreted in hardnessScale. Conversion table range is scale- and class-dependent; "
                     "no universal static numeric bound applies."),
        _enum("hardnessScale", "Hardness scale", "hardness-scale", "HRC", _HARDNESS_SCALES),
        _enum("hardnessClass", "Material class", "hardness-material-class", "non-austenitic-steel", _HARDNESS_CLASSES),
    ), outputs=("hardnessResult",)),
    _browser_operation("apply-hardness-preset", fields=(_enum(
        "preset", "Measured hardness example", "hardness-preset", "4140 Q&T", _HARDNESS_PRESETS,
    ),), outputs=("hardnessVal", "hardnessScale", "hardnessClass", "hardnessResult")),
    _browser_operation("calculate-weldability", fields=(
        _number("plateThickness", "Joint plate thickness", "mm", "length", 30.0,
                note="UI slider spans 5–100 mm in 5 mm steps; this is a control range, not a physical validity oracle."),
    ), undeclared=("ceComp",), outputs=("ceResult", "ceIIW", "pcm", "cen", "weldabilityLevel", "recommendedPreheatTemp", "riskNotes")),
    _browser_operation("reset-weldability-s355", outputs=("ceComp", "ceResult")),
    _browser_operation("simulate-diffusion", fields=(
        _number("carbTemp", "Carburizing temperature", "degC", "temperature", 930.0, note="UI slider spans 840–1020 degC; not an independently established model-validity domain."),
        _number("carbTime", "Soak time", "h", "time", 6.0, note="UI slider spans 1–24 h; not an independently established model-validity domain."),
        _number("carbSurfaceC", "Surface carbon potential", "mass % C", "mass-fraction-percent", 1.05, note="UI slider spans 0.70–1.30 mass %; not an independent validity oracle."),
        _number("carbCoreC", "Core carbon content", "mass % C", "mass-fraction-percent", 0.20, note="UI slider spans 0.10–0.35 mass %; not an independent validity oracle."),
    ), outputs=("diffusionResult", "profileData", "caseDepth", "effectiveCaseDepth", "diffusivity")),
    _browser_operation("calculate-schaeffler", undeclared=("schaefflerComp",), outputs=(
        "schaefflerResult", "crEq", "niEq", "primaryPhase", "ferriteNumberEstimated", "hotCrackingRisk", "martensiticHardeningRisk",
    )),
    _browser_operation("apply-schaeffler-preset", fields=(_enum(
        "preset", "Schaeffler composition preset", "composition-preset", "304L", ("304L", "316L", "2205 Duplex", "309L"),
    ),), outputs=("schaefflerComp", "schaefflerResult")),
    _browser_operation("calculate-xrd", fields=(
        _enum("xrdStructure", "Bravais lattice", "crystal-structure", "BCC", ("BCC", "FCC")),
        _number("latticeA", "Cubic lattice parameter", "angstrom", "length", 2.8665, note="UI slider spans 2.5–5.0 angstrom; display/control range only."),
        _enum("xrayTarget", "X-ray tube target", "xray-target", "Cu-Ka", ("Cu-Ka", "Mo-Ka", "Co-Ka", "Fe-Ka")),
    ), outputs=("xrdPeaks", "twoTheta", "dSpacing", "hkl", "intensityPct")),
    _browser_operation("apply-xrd-structure-preset", fields=(
        _enum("xrdStructure", "Bravais lattice preset", "crystal-structure", "BCC", ("BCC", "FCC")),
    ), outputs=("xrdStructure", "latticeA", "xrdPeaks")),
    _browser_operation("calculate-hall-petch", fields=(
        _number("grainSize", "Average planimetric grain diameter", "µm", "length", 25.0, note="UI slider spans 0.5–100 µm; display/control range only."),
        _number("sigma0", "Lattice friction stress", "MPa", "pressure", 70.0, note="UI slider spans 20–200 MPa; display/control range only."),
        _number("ky", "Hall–Petch slope", "MPa*sqrt(mm)", "stress-intensity", 18.5, note="UI slider spans 5–30; display/control range only."),
    ), outputs=("hallPetchResult", "grainSizeMicrons", "yieldStrengthMpa", "strengtheningIncrement", "astmG")),
    _browser_operation("calculate-transformation", undeclared=("ttComp",), outputs=("ttResult", "ms", "mf", "bs", "ac1", "ac3")),

    # Always-mounted MetallurgicalQuickConversionsGrid; its state is independent of the selected tab.
    _browser_operation("filter-quick-conversions", undeclared=("searchQuery",), outputs=("visibleCards",)),
    _browser_operation("toggle-quick-conversions", fields=(InputField(
        key="isCollapsed", label="Collapsed state", unit=None, quantity_kind="ui-state", min=None, max=None,
        default=False, value_type="boolean",
    ),), outputs=("isCollapsed",)),
    _browser_operation("open-full-unit-suite", outputs=("activeTab",)),
    _browser_operation("convert-quick-stress", fields=(
        _enum("stressInputMode", "Stress input mode", "stress-unit", "MPa", ("MPa", "ksi")),
        _number("stressValMpa", "Stress input in MPa", "MPa", "pressure", 850.0),
        _number("stressValKsi", "Stress input in ksi", "ksi", "pressure", 123.3),
    ), outputs=("stressConversions", "MPa", "ksi", "GPa", "psi", "bar", "kgf_mm2", "N_mm2",
                "stressInterpretation", "category", "typicalMaterials", "color", "notes")),
    _browser_operation("apply-quick-stress-preset", fields=(_enum(
        "preset", "Quick stress preset", "stress-preset", "A36 Steel Yield",
        ("A36 Steel Yield", "Al 7075-T6 Yield", "Ti-6Al-4V UTS", "4140 Q&T UTS", "Inconel 718 Aged", "AerMet 100 Ultra"),
    ),), outputs=("stressInputMode", "stressValMpa", "stressValKsi", "stressConversions")),
    _browser_operation("convert-quick-hardness", fields=(
        _enum("hardnessInputScale", "Input hardness scale", "hardness-scale", "HRC", ("HRC", "HV")),
        _number("hardnessValHrc", "Measured HRC value", "HRC", "hardness", 34.0),
        _number("hardnessValHv", "Measured Vickers value", "HV", "hardness", 336.0),
        _enum("hardnessClass", "Material class", "hardness-material-class", "non-austenitic-steel", _HARDNESS_CLASSES),
    ), outputs=("hardnessConversions", "inputScale", "inputValue", "HRC", "HV", "HRB", "HBW", "HBS", "HK", "HLD",
                "tensileRm_MPa", "tensileRm_ksi", "unavailable", "validRangeNote", "hardnessInterpretation")),
    _browser_operation("apply-quick-hardness-preset", fields=(_enum(
        "preset", "Measured HRC/HV example", "hardness-preset", "4140 Q&T", _QUICK_HARDNESS_PRESETS,
    ),), outputs=("hardnessInputScale", "hardnessValHrc", "hardnessValHv", "hardnessClass", "hardnessConversions")),
    _browser_operation("convert-quick-temperature", fields=(
        _enum("tempInputScale", "Temperature input scale", "temperature-scale", "C", ("C", "K", "R", "F")),
        _number("tempValC", "Temperature in Celsius", "degC", "temperature", 650.0),
        _number("tempValK", "Temperature in kelvin", "K", "temperature", 923.15),
        _number("tempValR", "Temperature in Rankine", "degR", "temperature", 1661.67),
        _number("tempValF", "Temperature in Fahrenheit", "degF", "temperature", 1202.0),
    ), outputs=("tempConversions", "C", "K", "R", "F")),
    _browser_operation("apply-quick-temperature-preset", fields=(_enum(
        "preset", "Quick temperature preset", "temperature-preset", "Ambient Standard Lab",
        ("Cryogenic LN2", "Ambient Standard Lab", "Stress Relief Temper", "Aging / Nitriding", "Steel Austenitizing Ac3", "Carburizing Atmosphere", "Pure Iron Liquidus"),
    ),), outputs=("tempInputScale", "tempValC", "tempValK", "tempValR", "tempValF", "tempConversions")),
    _browser_operation("load-quick-active-specimen", undeclared=("activeMaterialSpecimen",), outputs=("stressValMpa", "stressValKsi", "stressInputMode")),
    _browser_operation("copy-quick-conversion-value", fields=(
        _enum("copiedId", "Copy feedback identifier", "ui-state", "quick-mpa",
              ("quick-mpa", "quick-ksi", "quick-hrc", "quick-hv", "quick-temp-c", "quick-temp-k", "quick-temp-r")),
    ), undeclared=("value",), outputs=("clipboardWrite", "copiedId", "copyToastTimeoutMs")),

    # Full-suite unit converter: all seven selectable categories and their result surfaces.
    _browser_operation("select-unit-category", fields=(_enum(
        "propertyCategory", "Unit-converter category", "unit-category", "stress",
        ("stress", "hardness", "temperature", "toughness", "grain_length", "corrosion", "report_matrix"),
    ),), outputs=("propertyCategory",)),
    _browser_operation("convert-unit-suite-stress", fields=(
        _selected("stressInput", "Stress input", "stressUnit", _STRESS_UNITS, "pressure", 850.0),
        _enum("stressUnit", "Stress input unit", "stress-unit", "MPa", ("MPa", "ksi", "GPa", "psi", "bar", "kgf_mm2", "N_mm2")),
    ), outputs=("stressState", "MPa", "ksi", "GPa", "psi", "bar", "kgf_mm2", "N_mm2",
                "stressInterpretation", "category", "typicalMaterials", "color", "notes")),
    _browser_operation("convert-unit-suite-hardness", fields=(
        _selected("hardnessInput", "Measured hardness input", "hardnessScale",
                  tuple((scale, scale) for scale in _ALL_HARDNESS_SCALES), "hardness", 32.0),
        _enum("hardnessScale", "Hardness scale", "hardness-scale", "HRC", _ALL_HARDNESS_SCALES),
        _enum("hardnessClass", "Material class", "hardness-material-class", "non-austenitic-steel", _HARDNESS_CLASSES),
    ), outputs=("hardnessState", "inputScale", "inputValue", "HV", "HRC", "HRB", "HBW", "HBS", "HK", "HLD",
                "tensileRm_MPa", "tensileRm_ksi", "unavailable", "validRangeNote", "hardnessInterpretation")),
    _browser_operation("apply-unit-suite-hardness-preset", fields=(_enum(
        "preset", "Measured hardness example", "hardness-preset", "4140 Q&T", _HARDNESS_PRESETS,
    ),), outputs=("hardnessInput", "hardnessScale", "hardnessClass", "hardnessState")),
    _browser_operation("convert-unit-suite-temperature", fields=(
        _selected("tempInput", "Temperature input", "tempUnit", _TEMP_UNITS, "temperature", 650.0),
        _enum("tempUnit", "Temperature unit", "temperature-scale", "C", ("C", "K", "F", "R")),
        InputField(key="selectedMeltingPresetIdx", label="Melting-point preset option index", unit="1",
                   quantity_kind="ui-selection-index", min=0, max=8, step=1, default=0, required=True,
                   value_type="integer",
                   note="Index selects one of the nine source-defined METALLURGICAL_MELTING_PRESETS; index limits are UI options, not material validity bounds."),
    ), outputs=("tempState", "C", "K", "F", "R", "homologousState", "th", "regime",
                "deformationMechanism", "color", "recommendation")),
    _browser_operation("convert-fracture-toughness", fields=(
        _selected("kicInput", "Plane-strain fracture toughness", "kicUnit", _KIC_UNITS, "fracture-toughness", 55.0),
        _enum("kicUnit", "Fracture-toughness unit", "fracture-toughness-unit", "MPa_m05", ("MPa_m05", "ksi_in05", "N_mm15", "MPa_mm05")),
    ), outputs=("kicState", "MPa_m05", "ksi_in05", "N_mm15", "MPa_mm05")),
    _browser_operation("convert-charpy-impact-energy", fields=(
        _selected("cvnInput", "Charpy V-notch impact energy", "cvnUnit", _CVN_UNITS, "impact-energy-or-area-normalized-energy", 45.0),
        _enum("cvnUnit", "Impact-energy unit", "impact-energy-unit", "J", ("J", "ft_lbf", "kgf_m", "J_cm2")),
    ), outputs=("cvnState", "J", "ft_lbf", "kgf_m", "J_cm2")),
    _browser_operation("convert-micro-length", fields=(
        _selected("lengthInput", "Micro length input", "lengthUnit", _LENGTH_UNITS, "length", 25.0),
        _enum("lengthUnit", "Length unit", "length-unit", "um", ("angstrom", "nm", "um", "mm", "mil", "in")),
    ), outputs=("lengthState", "angstrom", "nm", "um", "mm", "mil", "in")),
    _browser_operation("calculate-astm-e112-grain-size", fields=(
        _enum("astmMode", "ASTM E112 input mode", "grain-size-input-mode", "g_number", ("g_number", "diameter")),
        _number("astmGInput", "ASTM grain-size number", "1", "grain-size-number", 8.0),
        _number("astmDInput", "Mean grain diameter", "µm", "length", 22.4),
    ), outputs=("astmResult", "gNumber", "meanInterceptUm", "meanInterceptMm", "grainsPerMm2",
                "grainsPerSqInch100x", "classification")),
    _browser_operation("convert-corrosion-rate", fields=(
        _selected("crInput", "Corrosion penetration or mass-loss rate", "crUnit", _CR_UNITS, "corrosion-rate", 2.5),
        _enum("crUnit", "Corrosion-rate unit", "corrosion-rate-unit", "mpy", ("mpy", "mm_yr", "um_yr", "nm_day", "g_m2_day")),
    ), outputs=("crState", "mpy", "mm_yr", "um_yr", "nm_day", "g_m2_day", "naceRating", "naceColor")),
    _browser_operation("sync-unit-report-from-specimen", undeclared=("activeMaterialSpecimen",), outputs=(
        "stressInput", "stressUnit", "reportYieldMpa", "reportUtsMpa", "reportAlloyName",
        "reportHardnessEntered", "reportHardnessSyncNote",
    )),
    _browser_operation("calculate-dual-unit-report", fields=(
        _number("reportYieldMpa", "Yield strength", "MPa", "pressure", 880.0),
        _number("reportUtsMpa", "Tensile strength", "MPa", "pressure", 950.0),
        _selected("reportHardnessValue", "Measured hardness", "reportHardnessScale",
                  tuple((scale, scale) for scale in ("HRC", "HV", "HBW", "HRB")), "hardness", 34.0),
        _enum("reportHardnessScale", "Reported hardness scale", "hardness-scale", "HRC", ("HRC", "HV", "HBW", "HRB")),
        _enum("reportHardnessClass", "Hardness material class", "hardness-material-class", "titanium-alloy", _HARDNESS_CLASSES),
        _number("reportCvnJ", "Charpy V-notch energy", "J", "energy", 42.0),
        _number("reportTestTempC", "Test temperature", "degC", "temperature", 23.0),
    ), undeclared=("reportAlloyName",), outputs=("reportCalculated", "yieldKsi", "utsKsi", "hardnessMeasured", "hardnessConverted", "hardnessText", "hrc", "hv", "hbw", "cvnFtLbf", "tempF", "tempK")),
    _browser_operation("copy-formatted-report", undeclared=("reportCalculated", "reportHardnessEntered", "reportHardnessSyncNote", "reportAlloyName"),
                       outputs=("reportText", "clipboardWrite", "copiedId", "copyToastTimeoutMs")),
    _browser_operation("copy-unit-suite-conversion-value", undeclared=("value", "copiedId"),
                       outputs=("clipboardWrite", "copiedId", "copyToastTimeoutMs")),
)


def build_calculators_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Build the calculator contract without changing registry seed identity."""
    if seed.get("id") != "calculators":
        raise ContractError("Calculator contract preserves only the calculators identity")
    return ModuleContract(
        id=seed["id"], version=CONTRACT_VERSION, owner=OWNER_UNASSIGNED,
        workspace=seed["workspace"], label=seed["label"], description=seed["description"],
        next=seed["next"], maturity=seed["scope"], navigation="listed",
        view=View(component=seed["viewComponent"], export=seed["viewExport"]),
        evidence=Evidence(
            emits=(), ceiling=PENDING_ORACLE_CEILING, forbidden_claims=FORBIDDEN_CLAIM_KEYS,
            note=("The reachable calculator surfaces implement analytical/table-based calculations and conversions. "
                  "No independent oracle is declared; numerical outputs remain screening-only and unvalidated."),
        ),
        tests=TestRefs(oracle=Oracle(status="pending"), schema="python/test_module_contract_calculators.py",
                       docs="docs/modules/calculators.md"),
        migration_state="contracted", operations=CALCULATORS_OPERATIONS,
        lifecycle=Lifecycle(background_work="none", resources=()),
        legacy_notes=(
            "The PocketCalculators tab starts at units. MetallurgicalQuickConversionsGrid is mounted independently "
            "above the tab panel, so its local state and conversions remain reachable across tab selection.",
        "MetallurgicalUnitConverter is conditionally mounted only for the units tab; leaving that tab unmounts it "
        "and returning recreates its local converter state. The quick grid remains mounted across those changes.",
            "PocketCalculators sync reads activeMaterialSpecimen from Zustand. Missing composition keys retain the "
            "previous local composition values; XRD structure/lattice fields are updated only when present and eligible.",
            "Composition objects are passed as explicit undeclared keys because the contract field schema cannot "
            "describe dynamic element-keyed maps. Their UI slider extents are not physical/model validity bounds.",
            "Hardness numbers are conditional on their selected scale. The hardness material class is the finite "
            "source enum; table availability and tabulated conversion ranges vary by scale and class.",
            "Copy and toast-feedback actions use browser clipboard and short timers (1.8–3.0 s); there is no "
            "persistent background worker or external resource lifecycle. Clipboard promises are not awaited, "
            "so feedback is optimistic, not confirmed write success; the short timers have no unmount cleanup.",
            "Selected-unit fields carry their real enum-to-unit map; the browser passes their value and selected "
            "unit directly to conversion functions. Contract declarations do not normalize values or certify conversions. "
            "Impact J/cm^2 conversion assumes a fixed 0.8 cm^2 Charpy ligament; mass-loss corrosion conversion uses "
            "the converter's default carbon-steel density 7.85 g/cm^3, not the active specimen density.",
            "The copied report calls reportHardnessLine with reportHardnessEntered and reportHardnessSyncNote. "
            "After loading a specimen without entered measured hardness, it reports not entered rather than "
            "exporting the scratchpad's illustrative numeric value as a measurement.",
        ),
        source_refs=(
            "src/components/PocketCalculators.tsx:62-75#root, tab, and hardness state",
            "src/components/PocketCalculators.tsx:78-157#calculator state and derived results",
            "src/components/PocketCalculators.tsx:159-206#handleSyncFromActiveSpecimen",
            "src/components/PocketCalculators.tsx:238-294#always-mounted quick grid and tab selection",
            "src/components/PocketCalculators.tsx:317-388#hardness scale changes and presets",
            "src/components/PocketCalculators.tsx:500-575#weldability inputs and S355 reset",
            "src/components/PocketCalculators.tsx:670-730#diffusion control ranges",
            "src/components/PocketCalculators.tsx:810-860#Schaeffler inputs and presets",
            "src/components/PocketCalculators.tsx:965-1035#XRD structure, target, and lattice controls",
            "src/components/PocketCalculators.tsx:1100-1165#Hall-Petch controls and results",
            "src/components/PocketCalculators.tsx:1200-1245#transformation composition controls",
            "src/components/MetallurgicalQuickConversionsGrid.tsx:40-219#quick conversions, presets, and specimen state",
            "src/components/MetallurgicalQuickConversionsGrid.tsx:300-370#always-mounted grid search and collapse controls",
            "src/components/MetallurgicalQuickConversionsGrid.tsx:420-930#quick conversion inputs, outputs, copy, and presets",
            "src/components/MetallurgicalUnitConverter.tsx:72-245#unit-suite state, derived results, sync, and report copy",
            "src/components/MetallurgicalUnitConverter.tsx:280-320#unit-suite category selection",
            "src/components/MetallurgicalUnitConverter.tsx:331-1535#unit-suite operation controls and rendered outputs",
            "src/utils/hardnessConversion.ts:44-50#HardnessScale enum",
            "src/utils/hardnessConversion.ts:177-192#SteelHardnessConversion result fields",
            "src/utils/hardnessConversion.ts:275-298#HardnessMaterialClass and HARDNESS_MATERIAL_CLASSES",
            "src/utils/hardnessPresets.ts:1-25#HARDNESS_PRESETS illustrative measured-input examples",
            "src/utils/metallurgicalConversions.ts:1-55#StressUnit and convertStress output units",
            "src/utils/metallurgicalConversions.ts:179-179#TempUnit",
            "src/utils/metallurgicalConversions.ts:284-284#FractureToughnessUnit",
            "src/utils/metallurgicalConversions.ts:320-320#ImpactEnergyUnit",
            "src/utils/metallurgicalConversions.ts:361-361#LengthUnit",
            "src/utils/metallurgicalConversions.ts:452-452#CorrosionRateUnit",
            "src/utils/metallurgicalConversions.ts:566-566#ReportHardnessScale",
            "src/utils/metallurgicalConversions.ts:226-246#melting-point preset enum source",
            "src/utils/metallurgyCalculations.ts:58-123#calculateCarbonEquivalent",
            "src/utils/metallurgyCalculations.ts:124-183#calculateSchaeffler",
            "src/utils/metallurgyCalculations.ts:184-213#calculateTransformationTemps",
            "src/utils/metallurgyCalculations.ts:214-267#simulateCarburizingDiffusion",
            "src/utils/metallurgyCalculations.ts:268-296#calculateHallPetch",
            "src/utils/metallurgyCalculations.ts:297-347#calculateXrdPeaks",
            "python/module_contract.py:151-233#InputField type, enum, and unit validation",
            "python/module_contract.py:279-389#OutputSchema and Operation request validation",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )
