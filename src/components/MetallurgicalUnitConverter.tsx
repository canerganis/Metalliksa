import React, { useState, useMemo } from "react";
import {
  ArrowLeftRight,
  Sparkles,
  Copy,
  Check,
  Zap,
  BookOpen,
  Info,
  Flame,
  ShieldCheck,
  TrendingUp,
  Activity,
  Layers,
  Thermometer,
  Compass,
  FileSpreadsheet,
} from "lucide-react";
import {
  StressUnit,
  convertStress,
  interpretStressMpa,
  interpretHardness,
  TempUnit,
  convertTemperature,
  METALLURGICAL_MELTING_PRESETS,
  calculateHomologousTemperature,
  FractureToughnessUnit,
  convertFractureToughness,
  ImpactEnergyUnit,
  convertImpactEnergy,
  LengthUnit,
  convertMicroLength,
  calculateAstmE112FromG,
  calculateAstmE112FromDiameterUm,
  CorrosionRateUnit,
  convertCorrosionRate,
  convertDensity,
  computeDualUnitReport,
} from "../utils/metallurgicalConversions";
import {
  HardnessScale,
  HARDNESS_VERIFIED_RANGES,
  TENSILE_ESTIMATE_NOTE,
  convertSteelHardness,
} from "../utils/hardnessConversion";
import { useMaterialStore } from "../store/useMaterialStore";
import { StandardInfoIcon } from "./StandardInfoIcon";

// Display text of each unit <option> below, for accessible names (state holds raw keys such as "MPa_m05").
const UNIT_DISPLAY: Record<string, string> = {
  MPa: "MPa", ksi: "ksi", GPa: "GPa", psi: "psi", bar: "bar", kgf_mm2: "kgf/mm²",
  C: "°C", K: "K", F: "°F", R: "°R",
  MPa_m05: "MPa·√m", ksi_in05: "ksi·√in", N_mm15: "N·mm⁻³/²",
  J: "J", ft_lbf: "ft·lbf", kgf_m: "kgf·m", J_cm2: "J/cm²",
  angstrom: "Å", nm: "nm", um: "µm", mm: "mm", mil: "mil", in: "in",
  mpy: "mpy", mm_yr: "mm/year", um_yr: "µm/year", g_m2_day: "g/(m²·day)",
};
const withUnit = (name: string, unit: string): string => (UNIT_DISPLAY[unit] ? `${name} (${UNIT_DISPLAY[unit]})` : name);

export const MetallurgicalUnitConverter: React.FC = () => {
  const { activeMaterialSpecimen } = useMaterialStore();

  // Active Category inside Converter
  const [propertyCategory, setPropertyCategory] = useState<
    "stress" | "hardness" | "temperature" | "toughness" | "grain_length" | "corrosion" | "report_matrix"
  >("stress");

  const [copiedId, setCopiedId] = useState<string | null>(null);
  const handleCopy = (text: string | number, id: string) => {
    navigator.clipboard.writeText(String(text));
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };
  // Converted hardness values are table estimates; null means outside the verified table range.
  const hardnessValue = (v: number | null) =>
    v === null ? <span className="text-slate-600 text-sm">Unavailable</span> : v;

  // -------------------------------------------------------------
  // 1. STRESS / STRENGTH STATE
  // -------------------------------------------------------------
  const [stressInput, setStressInput] = useState<number>(850);
  const [stressUnit, setStressUnit] = useState<StressUnit>("MPa");
  const stressState = useMemo(
    () => convertStress(stressInput, stressUnit),
    [stressInput, stressUnit]
  );
  const stressInterpretation = useMemo(
    () => interpretStressMpa(stressState.MPa),
    [stressState.MPa]
  );

  // -------------------------------------------------------------
  // 2. HARDNESS STATE
  // -------------------------------------------------------------
  const [hardnessInput, setHardnessInput] = useState<number>(32);
  const [hardnessScale, setHardnessScale] = useState<HardnessScale>("HRC");
  const hardnessState = useMemo(
    () => convertSteelHardness(hardnessInput, hardnessScale),
    [hardnessInput, hardnessScale]
  );
  const hardnessInterpretation = useMemo(
    () => (hardnessState.HV === null ? null : interpretHardness(hardnessState.HV)),
    [hardnessState.HV]
  );

  // -------------------------------------------------------------
  // 3. TEMPERATURE & HOMOLOGOUS STATE
  // -------------------------------------------------------------
  const [tempInput, setTempInput] = useState<number>(650);
  const [tempUnit, setTempUnit] = useState<TempUnit>("C");
  const [selectedMeltingPresetIdx, setSelectedMeltingPresetIdx] = useState<number>(0);
  const tempState = useMemo(
    () => convertTemperature(tempInput, tempUnit),
    [tempInput, tempUnit]
  );
  const selectedMelting = METALLURGICAL_MELTING_PRESETS[selectedMeltingPresetIdx];
  const homologousState = useMemo(
    () => calculateHomologousTemperature(tempState.C, selectedMelting.tmC),
    [tempState.C, selectedMelting.tmC]
  );

  // -------------------------------------------------------------
  // 4. FRACTURE TOUGHNESS & IMPACT STATE
  // -------------------------------------------------------------
  const [kicInput, setKicInput] = useState<number>(55);
  const [kicUnit, setKicUnit] = useState<FractureToughnessUnit>("MPa_m05");
  const kicState = useMemo(
    () => convertFractureToughness(kicInput, kicUnit),
    [kicInput, kicUnit]
  );

  const [cvnInput, setCvnInput] = useState<number>(45);
  const [cvnUnit, setCvnUnit] = useState<ImpactEnergyUnit>("J");
  const cvnState = useMemo(
    () => convertImpactEnergy(cvnInput, cvnUnit),
    [cvnInput, cvnUnit]
  );

  // -------------------------------------------------------------
  // 5. GRAIN SIZE & MICRO LENGTH
  // -------------------------------------------------------------
  const [lengthInput, setLengthInput] = useState<number>(25);
  const [lengthUnit, setLengthUnit] = useState<LengthUnit>("um");
  const lengthState = useMemo(
    () => convertMicroLength(lengthInput, lengthUnit),
    [lengthInput, lengthUnit]
  );

  const [astmMode, setAstmMode] = useState<"g_number" | "diameter">("g_number");
  const [astmGInput, setAstmGInput] = useState<number>(8);
  const [astmDInput, setAstmDInput] = useState<number>(22.4);

  const astmResult = useMemo(() => {
    if (astmMode === "g_number") {
      return calculateAstmE112FromG(astmGInput);
    } else {
      return calculateAstmE112FromDiameterUm(astmDInput);
    }
  }, [astmMode, astmGInput, astmDInput]);

  // -------------------------------------------------------------
  // 6. CORROSION PENETRATION STATE
  // -------------------------------------------------------------
  const [crInput, setCrInput] = useState<number>(2.5);
  const [crUnit, setCrUnit] = useState<CorrosionRateUnit>("mpy");
  const crState = useMemo(
    () => convertCorrosionRate(crInput, crUnit),
    [crInput, crUnit]
  );

  // -------------------------------------------------------------
  // 7. RAPID DUAL-UNIT REPORT SCRATCHPAD
  // -------------------------------------------------------------
  const [reportAlloyName, setReportAlloyName] = useState<string>("Ti-6Al-4V Grade 5 (Annealed)");
  const [reportYieldMpa, setReportYieldMpa] = useState<number>(880);
  const [reportUtsMpa, setReportUtsMpa] = useState<number>(950);
  const [reportHardnessHrc, setReportHardnessHrc] = useState<number>(34);
  const [reportCvnJ, setReportCvnJ] = useState<number>(42);
  const [reportTestTempC, setReportTestTempC] = useState<number>(23);

  const reportCalculated = useMemo(
    () =>
      computeDualUnitReport({
        yieldMpa: reportYieldMpa,
        utsMpa: reportUtsMpa,
        hardnessHrc: reportHardnessHrc,
        cvnJ: reportCvnJ,
        testTempC: reportTestTempC,
      }),
    [reportYieldMpa, reportUtsMpa, reportHardnessHrc, reportCvnJ, reportTestTempC]
  );

  const handleSyncFromActiveSpecimen = () => {
    if (activeMaterialSpecimen) {
      if (activeMaterialSpecimen.yieldStrength_25C_MPa > 0) {
        setStressInput(activeMaterialSpecimen.yieldStrength_25C_MPa);
        setStressUnit("MPa");
        setReportYieldMpa(activeMaterialSpecimen.yieldStrength_25C_MPa);
      }
      if (activeMaterialSpecimen.uts_25C_MPa > 0) {
        setReportUtsMpa(activeMaterialSpecimen.uts_25C_MPa);
      }
      if (activeMaterialSpecimen.hardness_HV > 0) {
        setHardnessInput(activeMaterialSpecimen.hardness_HV);
        setHardnessScale("HV");
        const converted = convertSteelHardness(activeMaterialSpecimen.hardness_HV, "HV");
        if (converted.HRC !== null) {
          setReportHardnessHrc(converted.HRC);
        }
      }
      if (activeMaterialSpecimen.name) {
        setReportAlloyName(activeMaterialSpecimen.name);
      }
    }
  };

  const copyReportText = () => {
    const text = `=== METALLURGICAL TEST REPORT SUMMARY (${reportAlloyName}) ===
Yield Strength (Rp0.2): ${reportYieldMpa} MPa [${reportCalculated.yieldKsi} ksi]
Tensile Strength (Rm): ${reportUtsMpa} MPa [${reportCalculated.utsKsi} ksi]
Hardness: ${reportHardnessHrc} HRC [approx. ${reportCalculated.hv ?? "n/a"} HV / ${reportCalculated.hbw ?? "n/a"} HBW, converted per ASTM E140 tables, not measured]
Charpy V-Notch Impact: ${reportCvnJ} J [${reportCalculated.cvnFtLbf} ft-lbf]
Test Condition: ${reportTestTempC} °C [${reportCalculated.tempF} °F / ${reportCalculated.tempK} K]
Standard Conformance: ASTM E8 / ASTM E18 / ASTM E23 / ASTM E140`;
    handleCopy(text, "report-full");
  };

  return (
    <div id="metallurgical-unit-converter-panel" className="space-y-5">
      {/* Top Banner with Quick Specimen Sync */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 bg-gradient-to-r from-sky-950/40 via-slate-900 to-indigo-950/40 border border-sky-500/30 rounded-xl shadow-md">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-sky-500/20 text-sky-400 border border-sky-400/40">
            <ArrowLeftRight className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white tracking-wide">
                Metallurgical Property &amp; Unit Conversion Suite
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-400/40">
                ASTM E140 / E112 / ISO
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Bidirectional conversion with microstructural regime interpretation for rapid lab &amp; design analysis.
            </p>
          </div>
        </div>

        <button
          onClick={handleSyncFromActiveSpecimen}
          className="px-3 py-1.5 bg-sky-600/20 hover:bg-sky-600/30 text-sky-300 border border-sky-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all self-start sm:self-auto shrink-0 shadow-sm"
          title="Import mechanical strength and properties from active specimen"
        >
          <Sparkles className="w-3.5 h-3.5 text-sky-400" />
          <span>Load Active Specimen ({activeMaterialSpecimen.name})</span>
        </button>
      </div>

      {/* Category Navigation Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-1.5 p-1.5 bg-[#060a12] border border-[#162032] rounded-xl">
        {[
          { id: "stress", label: "Stress & Modulus", icon: Activity, badge: "MPa ⇄ ksi" },
          { id: "hardness", label: "Hardness Scales", icon: ShieldCheck, badge: "HRC ⇄ HV" },
          { id: "temperature", label: "Temperature & TH", icon: Thermometer, badge: "°C ⇄ K ⇄ °F" },
          { id: "toughness", label: "Toughness & CVN", icon: Zap, badge: "MPa√m ⇄ J" },
          { id: "grain_length", label: "Grain Size (E112)", icon: Layers, badge: "ASTM G ⇄ µm" },
          { id: "corrosion", label: "Corrosion Rate", icon: TrendingUp, badge: "mm/yr ⇄ mpy" },
          { id: "report_matrix", label: "Report Scratchpad", icon: FileSpreadsheet, badge: "SI / US Customary" },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = propertyCategory === tab.id;
          return (
            <div
              key={tab.id}
              className={`flex flex-col items-start gap-1 p-2 rounded-lg text-left transition-all ${
                isActive
                  ? "bg-sky-500/20 border border-sky-400/60 text-white shadow-[0_0_12px_rgba(56,189,248,0.25)]"
                  : "bg-slate-900/40 hover:bg-slate-800/60 border border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <div className="flex items-center justify-between w-full gap-1">
                <button
                  type="button"
                  onClick={() => setPropertyCategory(tab.id as any)}
                  className="flex items-center gap-1.5 min-w-0 text-left flex-1"
                >
                  <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? "text-sky-300" : "text-slate-400"}`} />
                  <span className="text-xs font-bold truncate">{tab.label}</span>
                </button>
                <StandardInfoIcon category={tab.id} align="center" size="sm" />
              </div>
              <button
                type="button"
                onClick={() => setPropertyCategory(tab.id as any)}
                className="w-full text-left"
              >
                <span className={`text-[10px] font-mono ${isActive ? "text-sky-300" : "text-slate-500"}`}>
                  {tab.badge}
                </span>
              </button>
            </div>
          );
        })}
      </div>

      {/* =========================================================================
          TAB 1: STRESS, STRENGTH & ELASTIC MODULUS
         ========================================================================= */}
      {propertyCategory === "stress" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Controls & Inputs */}
          <div className="lg:col-span-5 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                  Yield, Tensile, Shear &amp; Modulus
                </span>
                <StandardInfoIcon category="stress" align="left" />
              </div>
              <h4 className="text-sm font-bold text-white mt-0.5">Stress &amp; Pressure Inputs</h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Instant cross-conversion between SI metric (MPa, GPa) and Imperial (ksi, psi, bar).
              </p>
            </div>

            {/* Input Value & Source Unit Selector */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 flex justify-between">
                <span>Magnitude</span>
                <span className="text-[10px] font-mono text-sky-400">Current Base: {stressUnit}</span>
              </label>

              <div className="flex gap-2">
                <input aria-label={withUnit("Stress Magnitude", stressUnit)}
                  type="number"
                  inputMode="decimal"
                  value={stressInput}
                  onChange={(e) => setStressInput(parseFloat(e.target.value) || 0)}
                  className="flex-1 px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-base text-sky-400 focus:outline-none focus:border-sky-400"
                />
                <select aria-label="Stress unit"
                  value={stressUnit}
                  onChange={(e) => setStressUnit(e.target.value as StressUnit)}
                  className="px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-xs text-slate-200 focus:outline-none focus:border-sky-400 cursor-pointer"
                >
                  <option value="MPa">MPa (N/mm²)</option>
                  <option value="ksi">ksi (kips/in²)</option>
                  <option value="GPa">GPa (Modulus)</option>
                  <option value="psi">psi (lbf/in²)</option>
                  <option value="bar">bar</option>
                  <option value="kgf_mm2">kgf/mm²</option>
                </select>
              </div>

              <input aria-label={withUnit("Stress Magnitude slider", stressUnit)}
                type="range"
                min={stressUnit === "GPa" ? 10 : stressUnit === "ksi" ? 5 : 50}
                max={stressUnit === "GPa" ? 450 : stressUnit === "ksi" ? 350 : 2500}
                step={stressUnit === "GPa" ? 1 : stressUnit === "ksi" ? 0.5 : 5}
                value={stressInput}
                onChange={(e) => setStressInput(parseFloat(e.target.value) || 0)}
                className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            {/* Quick Aerospace & Metallurgy Presets */}
            <div className="space-y-2 pt-2 border-t border-[#162032]">
              <span className="text-[10px] text-slate-400 font-mono uppercase tracking-wider block">
                Aerospace &amp; Structural Presets:
              </span>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  { name: "A36 Steel Yield", val: 250, unit: "MPa" as StressUnit, sub: "Structural mild steel" },
                  { name: "Al 7075-T6 Yield", val: 503, unit: "MPa" as StressUnit, sub: "Aerospace wing spar" },
                  { name: "Ti-6Al-4V Grade 5 UTS", val: 950, unit: "MPa" as StressUnit, sub: "Airframe forging" },
                  { name: "4140 Q&T UTS", val: 1050, unit: "MPa" as StressUnit, sub: "152.3 ksi shafting" },
                  { name: "Inconel 718 Aged UTS", val: 1400, unit: "MPa" as StressUnit, sub: "203.1 ksi turbine disk" },
                  { name: "Steel Young's Modulus", val: 210, unit: "GPa" as StressUnit, sub: "30.5 Msi stiffness" },
                  { name: "Al Young's Modulus", val: 69, unit: "GPa" as StressUnit, sub: "10.0 Msi stiffness" },
                  { name: "AerMet 100 Ultra-UTS", val: 1965, unit: "MPa" as StressUnit, sub: "285 ksi landing gear" },
                ].map((p, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setStressUnit(p.unit);
                      setStressInput(p.val);
                    }}
                    className="p-2 text-left bg-[#0c1322] hover:bg-slate-800/80 border border-[#162032] hover:border-sky-400/50 rounded-lg transition"
                  >
                    <div className="font-semibold text-slate-200 truncate">{p.name}</div>
                    <div className="font-mono text-[10px] text-sky-400 mt-0.5">
                      {p.val} {p.unit}
                    </div>
                    <div className="text-[9px] text-slate-500 truncate">{p.sub}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Results Grid & Interpretation Card */}
          <div className="lg:col-span-7 space-y-4">
            {/* Real-time Cross Unit Matrix */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                { label: "Megapascals (MPa)", val: stressState.MPa, unit: "MPa", sub: "= 1 N/mm²", key: "mpa" },
                { label: "Kilopounds/sq.in (ksi)", val: stressState.ksi, unit: "ksi", sub: "= 1000 psi", key: "ksi", highlight: true },
                { label: "Gigapascals (GPa)", val: stressState.GPa, unit: "GPa", sub: "Elastic modulus unit", key: "gpa" },
                { label: "Pounds/sq.in (psi)", val: stressState.psi.toLocaleString(), unit: "psi", sub: "US Customary", key: "psi" },
                { label: "Bar", val: stressState.bar, unit: "bar", sub: "Hydrostatic / Autoclave", key: "bar" },
                { label: "Kilogram-force/mm²", val: stressState.kgf_mm2, unit: "kgf/mm²", sub: "Metric legacy", key: "kgf" },
              ].map((item) => (
                <div
                  key={item.key}
                  className={`p-3 rounded-xl border transition relative group ${
                    item.highlight
                      ? "bg-sky-950/30 border-sky-500/50 shadow-[0_0_12px_rgba(56,189,248,0.15)]"
                      : "bg-[#090e18] border-[#162032]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400 font-mono">{item.label}</span>
                    <button
                      onClick={() => handleCopy(item.val, item.key)}
                      className="text-slate-500 hover:text-sky-300 transition p-1"
                      title="Copy value"
                    >
                      {copiedId === item.key ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                  <div className="text-xl font-black font-mono text-white mt-1">
                    {item.val} <span className="text-xs font-normal text-sky-400">{item.unit}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{item.sub}</div>
                </div>
              ))}
            </div>

            {/* Metallurgical Engineering Interpretation */}
            <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
              <div className="flex items-center justify-between border-b border-[#162032] pb-2">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-sky-400" />
                  <span className="text-xs font-bold text-white uppercase tracking-wider">
                    Metallurgical Strength Interpretation
                  </span>
                </div>
                <span className={`text-xs font-mono font-bold ${stressInterpretation.color}`}>
                  ● {stressInterpretation.category}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032]">
                  <span className="text-[10px] font-mono text-slate-400 uppercase block mb-1">
                    Representative Alloys in this Range:
                  </span>
                  <span className="text-slate-200 font-medium">{stressInterpretation.typicalMaterials}</span>
                </div>

                <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032]">
                  <span className="text-[10px] font-mono text-slate-400 uppercase block mb-1">
                    Engineering Design Context:
                  </span>
                  <span className="text-slate-300">{stressInterpretation.notes}</span>
                </div>
              </div>

              {/* Stress Ratio rule of thumb */}
              <div className="p-2.5 bg-slate-900/60 rounded-lg border border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
                <span>
                  <strong>Standard Conversion Factor:</strong> 1 MPa = 0.145038 ksi | 1 ksi = 6.89476 MPa
                </span>
                <span className="text-sky-400 font-mono">
                  {stressState.MPa} MPa = {stressState.ksi} ksi
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 2: HARDNESS CONVERSION & ESTIMATED TENSILE Rm
         ========================================================================= */}
      {propertyCategory === "hardness" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Controls */}
          <div className="lg:col-span-5 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                  ASTM E140 / ISO 18265 Table Interpolation
                </span>
                <StandardInfoIcon category="hardness" align="left" />
              </div>
              <h4 className="text-sm font-bold text-white mt-0.5">Select Scale &amp; Test Value</h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Approximate conversion for non-austenitic steels between Rockwell C/B, Vickers, Brinell and Knoop; not a
                substitute for direct testing. Leeb D is not converted.
              </p>
            </div>

            {/* Scale Selector */}
            <div className="grid grid-cols-3 gap-2">
              {(["HRC", "HV", "HRB", "HBW", "HK", "HLD"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    setHardnessScale(s);
                    if (s === "HRC" && (hardnessInput > 68 || hardnessInput < 20)) setHardnessInput(35);
                    if (s === "HRB" && (hardnessInput > 100 || hardnessInput < 55)) setHardnessInput(85);
                    if (s === "HV" && hardnessInput < 100) setHardnessInput(350);
                    if (s === "HBW" && (hardnessInput > 634 || hardnessInput < 226)) setHardnessInput(320);
                  }}
                  className={`py-1.5 text-xs font-mono font-bold rounded-lg border transition ${
                    hardnessScale === s
                      ? "bg-sky-500/20 border-sky-400 text-sky-300 shadow-[0_0_10px_rgba(56,189,248,0.25)]"
                      : "bg-[#0c1322] border-[#162032] text-slate-400 hover:text-white"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            {/* Magnitude Input */}
            <div className="space-y-2">
              <div className="flex justify-between items-center text-xs text-slate-300 font-medium">
                <span>Value in {hardnessScale}</span>
                <input aria-label={`Value in ${hardnessScale}`}
                  type="number"
                  inputMode="decimal"
                  value={hardnessInput}
                  onChange={(e) => setHardnessInput(parseFloat(e.target.value) || 0)}
                  className="w-24 px-2.5 py-1 bg-[#0c1322] border border-[#1e2d46] rounded-lg text-right font-mono font-bold text-sky-400 focus:outline-none focus:border-sky-400"
                />
              </div>

              <input aria-label={`Value in ${hardnessScale} slider`}
                type="range"
                min={HARDNESS_VERIFIED_RANGES[hardnessScale]?.min ?? 80}
                max={HARDNESS_VERIFIED_RANGES[hardnessScale]?.max ?? 1200}
                step={hardnessScale === "HRC" || hardnessScale === "HRB" ? 0.5 : 5}
                value={hardnessInput}
                onChange={(e) => setHardnessInput(parseFloat(e.target.value) || 0)}
                className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            {/* Presets */}
            <div className="space-y-2 pt-2 border-t border-[#162032]">
              <span className="text-[10px] text-slate-400 font-mono uppercase tracking-wider block">
                Typical Heat Treat &amp; Alloy Presets:
              </span>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  { name: "316L Annealed", val: 80, scale: "HRB" as HardnessScale, sub: "Austenitic (~150 HV)" },
                  { name: "Ti-6Al-4V Annealed", val: 34, scale: "HRC" as HardnessScale, sub: "336 HV, 138 ksi" },
                  { name: "Inconel 718 Aged", val: 44, scale: "HRC" as HardnessScale, sub: "434 HV, 203 ksi" },
                  { name: "52100 Bearing Steel", val: 60, scale: "HRC" as HardnessScale, sub: "700 HV hardened" },
                  { name: "M2 High Speed Tool", val: 64, scale: "HRC" as HardnessScale, sub: "800 HV cold die" },
                  { name: "Nitrided Case Layer", val: 950, scale: "HV" as HardnessScale, sub: "~68 HRC surface" },
                ].map((p, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setHardnessScale(p.scale);
                      setHardnessInput(p.val);
                    }}
                    className="p-2 text-left bg-[#0c1322] hover:bg-slate-800/80 border border-[#162032] hover:border-sky-400/50 rounded-lg transition"
                  >
                    <div className="font-semibold text-slate-200 truncate">{p.name}</div>
                    <div className="font-mono text-[10px] text-sky-400 mt-0.5">
                      {p.val} {p.scale}
                    </div>
                    <div className="text-[9px] text-slate-500 truncate">{p.sub}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Hardness Output Grid */}
          <div className="lg:col-span-7 space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {/* Vickers */}
              <div className="p-3 rounded-xl bg-sky-950/20 border border-sky-500/40 shadow-sm relative group">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-mono">Vickers (HV / DPH)</span>
                  <button onClick={() => handleCopy(hardnessState.HV ?? "N/A", "h-hv")} className="text-slate-500 hover:text-sky-300">
                    {copiedId === "h-hv" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
                <div className="text-2xl font-black font-mono text-sky-300 mt-1">{hardnessValue(hardnessState.HV)}</div>
                <div className="text-[10px] text-slate-500">Universal standard diamond pyramid</div>
              </div>

              {/* Rockwell C */}
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032] relative group">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-mono">Rockwell C (HRC)</span>
                  <button onClick={() => handleCopy(hardnessState.HRC ?? "N/A", "h-hrc")} className="text-slate-500 hover:text-sky-300">
                    {copiedId === "h-hrc" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
                <div className="text-2xl font-black font-mono text-emerald-400 mt-1">
                  {hardnessValue(hardnessState.HRC)}
                </div>
                <div className="text-[10px] text-slate-500">150 kgf Brale diamond cone</div>
              </div>

              {/* Rockwell B */}
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032] relative group">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-mono">Rockwell B (HRB)</span>
                  <button onClick={() => handleCopy(hardnessState.HRB ?? "N/A", "h-hrb")} className="text-slate-500 hover:text-sky-300">
                    {copiedId === "h-hrb" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
                <div className="text-2xl font-black font-mono text-amber-400 mt-1">
                  {hardnessValue(hardnessState.HRB)}
                </div>
                <div className="text-[10px] text-slate-500">100 kgf 1/16" steel ball indenter</div>
              </div>

              {/* Brinell */}
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">Brinell (HBW 10/3000)</span>
                <div className="text-xl font-black font-mono text-cyan-400 mt-1">{hardnessValue(hardnessState.HBW)}</div>
                <div className="text-[10px] text-slate-500">10mm tungsten carbide ball</div>
              </div>

              {/* Knoop */}
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">Knoop (HK)</span>
                <div className="text-xl font-black font-mono text-indigo-300 mt-1">{hardnessValue(hardnessState.HK)}</div>
                <div className="text-[10px] text-slate-500">Thin foils &amp; case depths</div>
              </div>

              {/* Leeb D */}
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">Leeb Rebound (HLD)</span>
                <div className="text-xl font-black font-mono text-violet-400 mt-1">{hardnessValue(hardnessState.HLD)}</div>
                <div className="text-[10px] text-slate-500">No verified conversion table</div>
              </div>
            </div>

            {/* Estimated Tensile Strength Rm Banner */}
            <div className="p-3.5 rounded-xl bg-gradient-to-r from-emerald-950/40 via-[#090e18] to-sky-950/40 border border-emerald-500/30 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono text-emerald-400 uppercase tracking-wider block">
                  ISO 18265 Estimated Tensile Strength (Rm)
                </span>
                <div className="flex items-baseline gap-3 mt-0.5">
                  {hardnessState.tensileRm_MPa === null ? (
                    <span className="text-sm font-mono text-slate-500">Unavailable ({hardnessState.unavailable.Rm})</span>
                  ) : (
                    <>
                      <span className="text-xl font-black font-mono text-white">≈ {hardnessState.tensileRm_MPa} MPa</span>
                      <span className="text-sm font-mono text-emerald-300">({hardnessState.tensileRm_ksi} ksi)</span>
                    </>
                  )}
                </div>
              </div>
              <div className="text-right text-[10px] text-slate-400 font-mono max-w-xs">
                {TENSILE_ESTIMATE_NOTE}
              </div>
            </div>

            {/* Microstructural Interpretation */}
            <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
              <div className="flex items-center justify-between border-b border-[#162032] pb-2">
                <span className="text-xs font-bold text-white uppercase tracking-wider">
                  Condition &amp; Machinability Assessment
                </span>
                <span className="text-xs font-mono text-sky-400 font-semibold">
                  {hardnessInterpretation?.condition ?? "Unavailable (no HV)"}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032]">
                  <span className="text-[10px] font-mono text-slate-400 uppercase block mb-1">
                    Machining Behavior:
                  </span>
                  <span className="text-slate-300">{hardnessInterpretation?.machinability ?? "-"}</span>
                </div>
                <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032]">
                  <span className="text-[10px] font-mono text-slate-400 uppercase block mb-1">
                    Wear &amp; Fatigue Life:
                  </span>
                  <span className="text-slate-300">{hardnessInterpretation?.wearResistance ?? "-"}</span>
                </div>
              </div>

              <div className="text-[10px] text-slate-500 font-mono">
                {hardnessState.validRangeNote}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 3: TEMPERATURE & HOMOLOGOUS RATIO (TH = T / Tm)
         ========================================================================= */}
      {propertyCategory === "temperature" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Temperature Inputs */}
          <div className="lg:col-span-5 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                  Thermal &amp; Arrhenius Scales
                </span>
                <StandardInfoIcon category="temperature" align="left" />
              </div>
              <h4 className="text-sm font-bold text-white mt-0.5">Temperature Inputs</h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Conversion across Celsius (°C), Kelvin (K), Fahrenheit (°F), and Rankine (°R).
              </p>
            </div>

            {/* Input & Unit */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 flex justify-between">
                <span>Value</span>
                <span className="text-[10px] font-mono text-sky-400">Unit: {tempUnit}</span>
              </label>

              <div className="flex gap-2">
                <input aria-label={withUnit("Temperature Value", tempUnit)}
                  type="number"
                  inputMode="decimal"
                  value={tempInput}
                  onChange={(e) => setTempInput(parseFloat(e.target.value) || 0)}
                  className="flex-1 px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-base text-sky-400 focus:outline-none focus:border-sky-400"
                />
                <select aria-label="Temperature unit"
                  value={tempUnit}
                  onChange={(e) => setTempUnit(e.target.value as TempUnit)}
                  className="px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-xs text-slate-200 focus:outline-none focus:border-sky-400 cursor-pointer"
                >
                  <option value="C">°C (Celsius)</option>
                  <option value="K">K (Kelvin)</option>
                  <option value="F">°F (Fahrenheit)</option>
                  <option value="R">°R (Rankine)</option>
                </select>
              </div>

              <input aria-label={withUnit("Temperature Value slider", tempUnit)}
                type="range"
                min={tempUnit === "C" ? -200 : tempUnit === "K" ? 70 : -320}
                max={tempUnit === "C" ? 1600 : tempUnit === "K" ? 1873 : 2900}
                step={5}
                value={tempInput}
                onChange={(e) => setTempInput(parseFloat(e.target.value) || 0)}
                className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            {/* Thermal Process Milestones */}
            <div className="space-y-2 pt-2 border-t border-[#162032]">
              <span className="text-[10px] text-slate-400 font-mono uppercase tracking-wider block">
                Heat Treating &amp; Processing Milestones:
              </span>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  { name: "Liquid Nitrogen (Cryo)", val: -196, unit: "C" as TempUnit, sub: "77.15 K sub-zero" },
                  { name: "Ambient Standard Lab", val: 20, unit: "C" as TempUnit, sub: "293.15 K, 68 °F" },
                  { name: "Stress Relief / Low Temper", val: 200, unit: "C" as TempUnit, sub: "392 °F tempering" },
                  { name: "Secondary Hardening", val: 550, unit: "C" as TempUnit, sub: "Nitriding & aging" },
                  { name: "Steel Austenitizing (Ac3)", val: 850, unit: "C" as TempUnit, sub: "1123 K, 1562 °F" },
                  { name: "Gas Carburizing", val: 930, unit: "C" as TempUnit, sub: "1203 K, 1706 °F" },
                  { name: "Superalloy Solutionizing", val: 1150, unit: "C" as TempUnit, sub: "1423 K, 2102 °F" },
                  { name: "Pure Iron Melting Pt", val: 1538, unit: "C" as TempUnit, sub: "1811 K solidus" },
                ].map((p, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setTempUnit(p.unit);
                      setTempInput(p.val);
                    }}
                    className="p-2 text-left bg-[#0c1322] hover:bg-slate-800/80 border border-[#162032] hover:border-sky-400/50 rounded-lg transition"
                  >
                    <div className="font-semibold text-slate-200 truncate">{p.name}</div>
                    <div className="font-mono text-[10px] text-sky-400 mt-0.5">
                      {p.val} {p.unit === "C" ? "°C" : p.unit}
                    </div>
                    <div className="text-[9px] text-slate-500 truncate">{p.sub}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Temperature Outputs & Homologous Calculator */}
          <div className="lg:col-span-7 space-y-4">
            {/* 4 Scale Display */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "Celsius (°C)", val: tempState.C, unit: "°C", key: "t-c" },
                { label: "Kelvin (K)", val: tempState.K, unit: "K", key: "t-k", highlight: true },
                { label: "Fahrenheit (°F)", val: tempState.F, unit: "°F", key: "t-f" },
                { label: "Rankine (°R)", val: tempState.R, unit: "°R", key: "t-r" },
              ].map((item) => (
                <div
                  key={item.key}
                  className={`p-3 rounded-xl border transition ${
                    item.highlight
                      ? "bg-sky-950/30 border-sky-500/50 shadow-[0_0_12px_rgba(56,189,248,0.15)]"
                      : "bg-[#090e18] border-[#162032]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400 font-mono">{item.label}</span>
                    <button onClick={() => handleCopy(item.val, item.key)} className="text-slate-500 hover:text-sky-300">
                      {copiedId === item.key ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                  <div className="text-2xl font-black font-mono text-white mt-1">
                    {item.val} <span className="text-xs font-normal text-sky-400">{item.unit}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Homologous Temperature TH Section */}
            <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#162032] pb-2">
                <div className="flex items-center gap-2">
                  <Flame className="w-4 h-4 text-amber-400" />
                  <span className="text-xs font-bold text-white uppercase tracking-wider">
                    Homologous Temperature (TH = T / Tm)
                  </span>
                </div>

                <div className="flex items-center gap-1.5 text-xs">
                  <span className="text-slate-400 font-mono">Alloy Matrix:</span>
                  <select aria-label="Alloy Matrix"
                    value={selectedMeltingPresetIdx}
                    onChange={(e) => setSelectedMeltingPresetIdx(parseInt(e.target.value))}
                    className="px-2 py-1 bg-[#0c1322] border border-[#1e2d46] rounded text-slate-200 text-xs font-semibold focus:outline-none focus:border-sky-400 cursor-pointer"
                  >
                    {METALLURGICAL_MELTING_PRESETS.map((m, idx) => (
                      <option key={idx} value={idx}>
                        {m.name} (Tm = {m.tmC} °C)
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Progress bar visualizer for TH */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-400">
                    TH = {tempState.K} K / {selectedMelting.tmK} K
                  </span>
                  <span className={`font-bold ${homologousState.color}`}>
                    TH = {homologousState.th} ({homologousState.regime})
                  </span>
                </div>

                <div className="w-full h-3 bg-[#0c1322] rounded-full overflow-hidden flex border border-[#162032]">
                  <div
                    className={`h-full transition-all duration-300 ${
                      homologousState.th < 0.3
                        ? "bg-sky-400"
                        : homologousState.th <= 0.5
                        ? "bg-amber-400"
                        : "bg-rose-500"
                    }`}
                    style={{ width: `${Math.min(100, Math.max(2, homologousState.th * 100))}%` }}
                  />
                </div>

                <div className="flex justify-between text-[10px] font-mono text-slate-500">
                  <span>0.0 (Cold)</span>
                  <span>0.3 (Recovery)</span>
                  <span>0.5 (Recrystallization / Creep)</span>
                  <span>1.0 (Melting)</span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-1">
                <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032]">
                  <span className="text-[10px] font-mono text-slate-400 uppercase block mb-1">
                    Deformation Mechanism:
                  </span>
                  <span className="text-slate-300">{homologousState.deformationMechanism}</span>
                </div>
                <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032]">
                  <span className="text-[10px] font-mono text-slate-400 uppercase block mb-1">
                    Process Guidance:
                  </span>
                  <span className="text-slate-300">{homologousState.recommendation}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 4: FRACTURE TOUGHNESS & CHARPY IMPACT
         ========================================================================= */}
      {propertyCategory === "toughness" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Fracture Toughness KIC */}
          <div className="bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-[#162032] pb-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                    ASTM E399 Linear Elastic Fracture
                  </span>
                  <StandardInfoIcon category="toughness" align="left" />
                </div>
                <h4 className="text-sm font-bold text-white mt-0.5">Plane-Strain Toughness (KIC)</h4>
              </div>
              <Compass className="w-5 h-5 text-sky-400" />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 flex justify-between">
                <span>Value</span>
                <span className="text-[10px] font-mono text-sky-400">{kicUnit}</span>
              </label>
              <div className="flex gap-2">
                <input aria-label={withUnit("Fracture toughness Value", kicUnit)}
                  type="number"
                  inputMode="decimal"
                  value={kicInput}
                  onChange={(e) => setKicInput(parseFloat(e.target.value) || 0)}
                  className="flex-1 px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-base text-sky-400 focus:outline-none"
                />
                <select aria-label="Fracture toughness unit"
                  value={kicUnit}
                  onChange={(e) => setKicUnit(e.target.value as FractureToughnessUnit)}
                  className="px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-xs text-slate-200 cursor-pointer"
                >
                  <option value="MPa_m05">MPa·√m</option>
                  <option value="ksi_in05">ksi·√in</option>
                  <option value="N_mm15">N·mm⁻³/²</option>
                </select>
              </div>
            </div>

            {/* Results */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-[#0c1322] border border-[#162032]">
                <span className="text-[11px] text-slate-400 font-mono">MPa·√m (SI Standard)</span>
                <div className="text-xl font-black font-mono text-white mt-1">{kicState.MPa_m05}</div>
              </div>
              <div className="p-3 rounded-lg bg-[#0c1322] border border-sky-500/40">
                <span className="text-[11px] text-slate-400 font-mono">ksi·√in (US Aerospace)</span>
                <div className="text-xl font-black font-mono text-sky-400 mt-1">{kicState.ksi_in05}</div>
              </div>
            </div>

            {/* Conversion footnote */}
            <div className="text-[11px] text-slate-400 p-2.5 bg-slate-900/50 rounded-lg border border-slate-800">
              <strong>Exact factor:</strong> 1 ksi·√in = 1.09884 MPa·√m | 1 MPa·√m = 0.91005 ksi·√in
            </div>
          </div>

          {/* Charpy Impact Energy */}
          <div className="bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-[#162032] pb-2">
              <div>
                <span className="text-[10px] font-mono text-emerald-400 uppercase tracking-widest font-semibold">
                  ASTM E23 / ISO 148-1 Pendulum Test
                </span>
                <h4 className="text-sm font-bold text-white mt-0.5">Charpy V-Notch (CVN) Impact</h4>
              </div>
              <Zap className="w-5 h-5 text-emerald-400" />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 flex justify-between">
                <span>Energy Input</span>
                <span className="text-[10px] font-mono text-emerald-400">{cvnUnit}</span>
              </label>
              <div className="flex gap-2">
                <input aria-label={withUnit("Energy Input", cvnUnit)}
                  type="number"
                  inputMode="decimal"
                  value={cvnInput}
                  onChange={(e) => setCvnInput(parseFloat(e.target.value) || 0)}
                  className="flex-1 px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-base text-emerald-400 focus:outline-none"
                />
                <select aria-label="Impact energy unit"
                  value={cvnUnit}
                  onChange={(e) => setCvnUnit(e.target.value as ImpactEnergyUnit)}
                  className="px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-xs text-slate-200 cursor-pointer"
                >
                  <option value="J">Joules (J)</option>
                  <option value="ft_lbf">Foot-pounds (ft·lbf)</option>
                  <option value="kgf_m">kgf·m</option>
                  <option value="J_cm2">J/cm²</option>
                </select>
              </div>
            </div>

            {/* Results */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-[#0c1322] border border-emerald-500/40">
                <span className="text-[11px] text-slate-400 font-mono">Joules (J - Metric)</span>
                <div className="text-xl font-black font-mono text-emerald-400 mt-1">{cvnState.J} J</div>
              </div>
              <div className="p-3 rounded-lg bg-[#0c1322] border border-[#162032]">
                <span className="text-[11px] text-slate-400 font-mono">ft·lbf (US Customary)</span>
                <div className="text-xl font-black font-mono text-white mt-1">{cvnState.ft_lbf} ft·lbf</div>
              </div>
            </div>

            <div className="text-[11px] text-slate-400 p-2.5 bg-slate-900/50 rounded-lg border border-slate-800">
              <strong>Exact factor:</strong> 1 ft·lbf = 1.35582 Joules | 1 Joule = 0.73756 ft·lbf
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 5: ASTM E112 GRAIN SIZE & MICRO LENGTH
         ========================================================================= */}
      {propertyCategory === "grain_length" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* ASTM E112 Calculator */}
          <div className="lg:col-span-6 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-4">
            <div className="border-b border-[#162032] pb-2">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                  ASTM E112 Standard Test Methods
                </span>
                <StandardInfoIcon category="grain_length" align="left" />
              </div>
              <h4 className="text-sm font-bold text-white mt-0.5">Grain Size Number (G) &amp; Intercept</h4>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setAstmMode("g_number")}
                className={`flex-1 py-1.5 rounded-lg text-xs font-bold border transition ${
                  astmMode === "g_number"
                    ? "bg-sky-500/20 border-sky-400 text-sky-300"
                    : "bg-[#0c1322] border-[#162032] text-slate-400"
                }`}
              >
                Specify ASTM G Number
              </button>
              <button
                onClick={() => setAstmMode("diameter")}
                className={`flex-1 py-1.5 rounded-lg text-xs font-bold border transition ${
                  astmMode === "diameter"
                    ? "bg-sky-500/20 border-sky-400 text-sky-300"
                    : "bg-[#0c1322] border-[#162032] text-slate-400"
                }`}
              >
                Specify Mean Diameter (µm)
              </button>
            </div>

            {astmMode === "g_number" ? (
              <div className="space-y-2">
                <div className="flex justify-between text-xs text-slate-300">
                  <span>ASTM Grain Size Number (G)</span>
                  <span className="font-mono font-bold text-sky-400">G = {astmGInput}</span>
                </div>
                <input aria-label="ASTM Grain Size Number (G)"
                  type="range"
                  min={1}
                  max={14}
                  step={0.5}
                  value={astmGInput}
                  onChange={(e) => setAstmGInput(parseFloat(e.target.value))}
                  className="w-full accent-sky-400"
                />
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex justify-between text-xs text-slate-300">
                  <span>Mean Intercept Diameter (µm)</span>
                  <span className="font-mono font-bold text-sky-400">{astmDInput} µm</span>
                </div>
                <input aria-label="Mean Intercept Diameter (µm)"
                  type="number"
                  inputMode="decimal"
                  value={astmDInput}
                  onChange={(e) => setAstmDInput(parseFloat(e.target.value) || 1)}
                  className="w-full px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono text-sky-400"
                />
              </div>
            )}

            {/* Results Matrix */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032]">
                <span className="text-[10px] font-mono text-slate-400 block">ASTM G Number</span>
                <span className="text-xl font-black font-mono text-sky-400">{astmResult.gNumber}</span>
              </div>
              <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032]">
                <span className="text-[10px] font-mono text-slate-400 block">Mean Intercept (d)</span>
                <span className="text-xl font-black font-mono text-emerald-400">{astmResult.meanInterceptUm} µm</span>
              </div>
              <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032]">
                <span className="text-[10px] font-mono text-slate-400 block">Grains / mm² (at 1×)</span>
                <span className="text-lg font-black font-mono text-white">{astmResult.grainsPerMm2.toLocaleString()}</span>
              </div>
              <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032]">
                <span className="text-[10px] font-mono text-slate-400 block">Grains / in² (at 100×)</span>
                <span className="text-lg font-black font-mono text-white">{astmResult.grainsPerSqInch100x}</span>
              </div>
            </div>

            <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 text-xs text-slate-300">
              <strong>Classification:</strong> {astmResult.classification}
            </div>
          </div>

          {/* Microstructural Length Scale Converter */}
          <div className="lg:col-span-6 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-4">
            <div className="border-b border-[#162032] pb-2">
              <span className="text-[10px] font-mono text-indigo-400 uppercase tracking-widest font-semibold">
                Lattice to Component Dimension
              </span>
              <h4 className="text-sm font-bold text-white mt-0.5">Micro Length Scale Converter</h4>
            </div>

            <div className="flex gap-2">
              <input aria-label={withUnit("Micro Length Scale Converter value", lengthUnit)}
                type="number"
                inputMode="decimal"
                value={lengthInput}
                onChange={(e) => setLengthInput(parseFloat(e.target.value) || 0)}
                className="flex-1 px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-base text-indigo-400 focus:outline-none"
              />
              <select aria-label="Micro Length Scale Converter unit"
                value={lengthUnit}
                onChange={(e) => setLengthUnit(e.target.value as LengthUnit)}
                className="px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-xs text-slate-200 cursor-pointer"
              >
                <option value="angstrom">Å (Angstroms)</option>
                <option value="nm">nm (Nanometers)</option>
                <option value="um">µm (Microns)</option>
                <option value="mm">mm (Millimeters)</option>
                <option value="mil">mil (Thousandths)</option>
                <option value="in">in (Inches)</option>
              </select>
            </div>

            {/* Results Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              <div className="p-2.5 bg-[#0c1322] rounded-lg border border-[#162032]">
                <span className="text-[10px] font-mono text-slate-400">Angstroms (Å)</span>
                <div className="text-sm font-bold font-mono text-white mt-0.5">{lengthState.angstrom} Å</div>
              </div>
              <div className="p-2.5 bg-[#0c1322] rounded-lg border border-[#162032]">
                <span className="text-[10px] font-mono text-slate-400">Nanometers (nm)</span>
                <div className="text-sm font-bold font-mono text-white mt-0.5">{lengthState.nm} nm</div>
              </div>
              <div className="p-2.5 bg-[#0c1322] rounded-lg border border-indigo-500/40">
                <span className="text-[10px] font-mono text-slate-400">Microns (µm)</span>
                <div className="text-sm font-bold font-mono text-indigo-300 mt-0.5">{lengthState.um} µm</div>
              </div>
              <div className="p-2.5 bg-[#0c1322] rounded-lg border border-[#162032]">
                <span className="text-[10px] font-mono text-slate-400">Millimeters (mm)</span>
                <div className="text-sm font-bold font-mono text-white mt-0.5">{lengthState.mm} mm</div>
              </div>
              <div className="p-2.5 bg-[#0c1322] rounded-lg border border-[#162032]">
                <span className="text-[10px] font-mono text-slate-400">Mils (thou)</span>
                <div className="text-sm font-bold font-mono text-white mt-0.5">{lengthState.mil} mil</div>
              </div>
              <div className="p-2.5 bg-[#0c1322] rounded-lg border border-[#162032]">
                <span className="text-[10px] font-mono text-slate-400">Inches (in)</span>
                <div className="text-sm font-bold font-mono text-white mt-0.5">{lengthState.in} in</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 6: CORROSION PENETRATION RATE
         ========================================================================= */}
      {propertyCategory === "corrosion" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-5 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-4">
            <div className="border-b border-[#162032] pb-2">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-amber-400 uppercase tracking-widest font-semibold">
                  NACE / ISO 15156 Wall Loss
                </span>
                <StandardInfoIcon category="corrosion" align="left" />
              </div>
              <h4 className="text-sm font-bold text-white mt-0.5">Corrosion Rate Penetration</h4>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 flex justify-between">
                <span>Rate Magnitude</span>
                <span className="text-[10px] font-mono text-amber-400">{crUnit}</span>
              </label>

              <div className="flex gap-2">
                <input aria-label={withUnit("Corrosion Rate Magnitude", crUnit)}
                  type="number"
                  inputMode="decimal"
                  value={crInput}
                  onChange={(e) => setCrInput(parseFloat(e.target.value) || 0)}
                  className="flex-1 px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-base text-amber-400 focus:outline-none"
                />
                <select aria-label="Corrosion rate unit"
                  value={crUnit}
                  onChange={(e) => setCrUnit(e.target.value as CorrosionRateUnit)}
                  className="px-3 py-2 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-mono font-bold text-xs text-slate-200 cursor-pointer"
                >
                  <option value="mpy">mils/yr (mpy)</option>
                  <option value="mm_yr">mm/year</option>
                  <option value="um_yr">µm/year</option>
                  <option value="g_m2_day">g/(m²·day) [MDD]</option>
                </select>
              </div>

              <input aria-label={withUnit("Corrosion Rate Magnitude slider", crUnit)}
                type="range"
                min={crUnit === "mm_yr" ? 0.01 : 0.2}
                max={crUnit === "mm_yr" ? 1.5 : 50}
                step={0.1}
                value={crInput}
                onChange={(e) => setCrInput(parseFloat(e.target.value) || 0)}
                className="w-full accent-amber-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            <div className="text-xs text-slate-400 p-3 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
              <span className="font-bold text-white block">Conversion Rule:</span>
              <p>1 mpy (0.001 in/yr) = 0.0254 mm/year = 25.4 µm/year</p>
            </div>
          </div>

          <div className="lg:col-span-7 space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="p-3 bg-[#090e18] border border-amber-500/40 rounded-xl">
                <span className="text-xs text-slate-400 font-mono">Mils Per Year (mpy)</span>
                <div className="text-2xl font-black font-mono text-amber-300 mt-1">{crState.mpy}</div>
                <div className="text-[10px] text-slate-500">US Oil &amp; Gas Standard</div>
              </div>

              <div className="p-3 bg-[#090e18] border border-[#162032] rounded-xl">
                <span className="text-xs text-slate-400 font-mono">Millimeters / Year</span>
                <div className="text-2xl font-black font-mono text-white mt-1">{crState.mm_yr}</div>
                <div className="text-[10px] text-slate-500">ISO / Euro Norms</div>
              </div>

              <div className="p-3 bg-[#090e18] border border-[#162032] rounded-xl">
                <span className="text-xs text-slate-400 font-mono">Microns / Year</span>
                <div className="text-2xl font-black font-mono text-white mt-1">{crState.um_yr}</div>
                <div className="text-[10px] text-slate-500">Precision thin film loss</div>
              </div>
            </div>

            <div className="p-4 bg-[#090e18] border border-[#162032] rounded-xl space-y-2">
              <div className="text-xs font-bold text-white uppercase tracking-wider">
                Industrial Severity &amp; NACE Rating
              </div>
              <div className={`text-sm font-semibold font-mono ${crState.naceColor}`}>
                {crState.naceRating}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 7: DUAL-UNIT RAPID SCRATCHPAD & REPORT GENERATOR
         ========================================================================= */}
      {propertyCategory === "report_matrix" && (
        <div className="bg-[#090e18] rounded-xl border border-[#162032] p-5 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#162032] pb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                  Universal Dual-Unit Report Builder
                </span>
                <StandardInfoIcon category="report_matrix" align="left" />
              </div>
              <h4 className="text-base font-bold text-white">
                Side-by-Side SI (Metric) vs. Imperial (US Customary) Matrix
              </h4>
              <p className="text-xs text-slate-400">
                Input material test data in either system; automatically format synchronized inspection certificates.
              </p>
            </div>

            <button
              onClick={copyReportText}
              className="px-3.5 py-2 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-xs font-bold flex items-center gap-2 transition shadow-sm self-start sm:self-auto"
            >
              {copiedId === "report-full" ? (
                <>
                  <Check className="w-4 h-4 text-emerald-400" />
                  <span>Copied to Clipboard!</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4 text-emerald-400" />
                  <span>Copy Formatted Certificate Summary</span>
                </>
              )}
            </button>
          </div>

          {/* Alloy Title Input */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-slate-400 whitespace-nowrap">Specimen Identifier:</span>
            <input aria-label="Specimen Identifier"
              type="text"
              value={reportAlloyName}
              onChange={(e) => setReportAlloyName(e.target.value)}
              className="flex-1 px-3 py-1.5 bg-[#0c1322] border border-[#1e2d46] rounded-lg font-bold text-xs text-white focus:outline-none focus:border-sky-400"
            />
          </div>

          {/* Side-by-Side Dual Unit Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-[#162032] text-slate-400 text-[11px] uppercase tracking-wider">
                  <th className="py-2.5 px-3">Property Name</th>
                  <th className="py-2.5 px-3 bg-sky-950/20 text-sky-300">SI Metric Value</th>
                  <th className="py-2.5 px-3 bg-indigo-950/20 text-indigo-300">Imperial / US Customary</th>
                  <th className="py-2.5 px-3">Standard Reference</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#162032]/60">
                {/* Yield Strength */}
                <tr>
                  <td className="py-3 px-3 font-sans font-semibold text-slate-200">
                    Yield Strength (0.2% Offset Rp0.2)
                  </td>
                  <td className="py-3 px-3 bg-sky-950/10">
                    <div className="flex items-center gap-1.5">
                      <input aria-label="Yield Strength (0.2% Offset Rp0.2) (MPa)"
                        type="number"
                        value={reportYieldMpa}
                        onChange={(e) => setReportYieldMpa(parseFloat(e.target.value) || 0)}
                        className="w-24 px-2 py-1 bg-[#0c1322] border border-[#1e2d46] rounded text-sky-400 font-bold text-right"
                      />
                      <span className="text-slate-400">MPa</span>
                    </div>
                  </td>
                  <td className="py-3 px-3 bg-indigo-950/10 font-bold text-indigo-300 text-sm">
                    {reportCalculated.yieldKsi} ksi
                  </td>
                  <td className="py-3 px-3 text-slate-500 text-[11px]">ASTM E8 / ISO 6892-1</td>
                </tr>

                {/* Tensile Strength */}
                <tr>
                  <td className="py-3 px-3 font-sans font-semibold text-slate-200">
                    Ultimate Tensile Strength (Rm)
                  </td>
                  <td className="py-3 px-3 bg-sky-950/10">
                    <div className="flex items-center gap-1.5">
                      <input aria-label="Ultimate Tensile Strength (Rm) (MPa)"
                        type="number"
                        value={reportUtsMpa}
                        onChange={(e) => setReportUtsMpa(parseFloat(e.target.value) || 0)}
                        className="w-24 px-2 py-1 bg-[#0c1322] border border-[#1e2d46] rounded text-sky-400 font-bold text-right"
                      />
                      <span className="text-slate-400">MPa</span>
                    </div>
                  </td>
                  <td className="py-3 px-3 bg-indigo-950/10 font-bold text-indigo-300 text-sm">
                    {reportCalculated.utsKsi} ksi
                  </td>
                  <td className="py-3 px-3 text-slate-500 text-[11px]">ASTM E8 / ISO 6892-1</td>
                </tr>

                {/* Hardness */}
                <tr>
                  <td className="py-3 px-3 font-sans font-semibold text-slate-200">
                    Indentation Hardness
                  </td>
                  <td className="py-3 px-3 bg-sky-950/10 font-bold text-sky-300">
                    ≈ {reportCalculated.hv ?? "n/a"} HV / {reportCalculated.hbw ?? "n/a"} HBW
                    <span className="block text-[10px] font-normal text-slate-500">converted (ASTM E140), not measured</span>
                  </td>
                  <td className="py-3 px-3 bg-indigo-950/10">
                    <div className="flex items-center gap-1.5">
                      <input aria-label="Indentation Hardness (HRC)"
                        type="number"
                        value={reportHardnessHrc}
                        onChange={(e) => setReportHardnessHrc(parseFloat(e.target.value) || 0)}
                        className="w-24 px-2 py-1 bg-[#0c1322] border border-[#1e2d46] rounded text-indigo-300 font-bold text-right"
                      />
                      <span className="text-slate-400">HRC</span>
                    </div>
                  </td>
                  <td className="py-3 px-3 text-slate-500 text-[11px]">ASTM E18 / ASTM E140</td>
                </tr>

                {/* Charpy V-Notch Impact */}
                <tr>
                  <td className="py-3 px-3 font-sans font-semibold text-slate-200">
                    Charpy V-Notch Impact Toughness
                  </td>
                  <td className="py-3 px-3 bg-sky-950/10">
                    <div className="flex items-center gap-1.5">
                      <input aria-label="Charpy V-Notch Impact Toughness (J)"
                        type="number"
                        value={reportCvnJ}
                        onChange={(e) => setReportCvnJ(parseFloat(e.target.value) || 0)}
                        className="w-24 px-2 py-1 bg-[#0c1322] border border-[#1e2d46] rounded text-sky-400 font-bold text-right"
                      />
                      <span className="text-slate-400">J (Joules)</span>
                    </div>
                  </td>
                  <td className="py-3 px-3 bg-indigo-950/10 font-bold text-indigo-300 text-sm">
                    {reportCalculated.cvnFtLbf} ft·lbf
                  </td>
                  <td className="py-3 px-3 text-slate-500 text-[11px]">ASTM E23 / ISO 148-1</td>
                </tr>

                {/* Test Temperature */}
                <tr>
                  <td className="py-3 px-3 font-sans font-semibold text-slate-200">
                    Test Chamber Temperature
                  </td>
                  <td className="py-3 px-3 bg-sky-950/10">
                    <div className="flex items-center gap-1.5">
                      <input aria-label="Test Chamber Temperature (°C)"
                        type="number"
                        value={reportTestTempC}
                        onChange={(e) => setReportTestTempC(parseFloat(e.target.value) || 0)}
                        className="w-24 px-2 py-1 bg-[#0c1322] border border-[#1e2d46] rounded text-sky-400 font-bold text-right"
                      />
                      <span className="text-slate-400">°C ({reportCalculated.tempK} K)</span>
                    </div>
                  </td>
                  <td className="py-3 px-3 bg-indigo-950/10 font-bold text-indigo-300 text-sm">
                    {reportCalculated.tempF} °F
                  </td>
                  <td className="py-3 px-3 text-slate-500 text-[11px]">Laboratory Standard 23±2°C</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
