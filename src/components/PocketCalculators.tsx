import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useMemo } from "react";
import {
  Calculator,
  Flame,
  Activity,
  Layers,
  Sparkles,
  ArrowRightLeft,
  Thermometer,
  ShieldAlert,
  Sliders,
  TrendingUp,
  Cpu,
  RefreshCw,
  Scale,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import {
  calculateCarbonEquivalent,
  calculateHallPetch,
  calculateSchaeffler,
  calculateTransformationTemps,
  calculateXrdPeaks,
  simulateCarburizingDiffusion,
} from "../utils/metallurgyCalculations";
import {
  HARDNESS_CONVERSION_DISCLAIMER,
  HARDNESS_MATERIAL_CLASSES,
  HARDNESS_VERIFIED_RANGES,
  HardnessMaterialClass,
  BRINELL_NOTE,
  TENSILE_ESTIMATE_NOTE,
  UNAVAILABLE_TEXT,
  convertHardness,
  hardnessInputForScale,
} from "../utils/hardnessConversion";
import { HARDNESS_PRESETS, HardnessPreset } from "../utils/hardnessPresets";
import { useMaterialStore } from "../store/useMaterialStore";
import { MetallurgicalUnitConverter } from "./MetallurgicalUnitConverter";
import { MetallurgicalQuickConversionsGrid } from "./MetallurgicalQuickConversionsGrid";
import { StandardInfoIcon } from "./StandardInfoIcon";

type CalcTab =
  | "units"
  | "hardness"
  | "weldability"
  | "diffusion"
  | "schaeffler"
  | "xrd"
  | "hall-petch"
  | "transformation";

export const PocketCalculators: React.FC = () => {
  const { activeMaterialSpecimen, updateComposition: updateGlobalComposition } = useMaterialStore();
  const [syncToast, setSyncToast] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<CalcTab>("units");

  // 1. Hardness State
  const [hardnessVal, setHardnessVal] = useState<number>(30);
  const [hardnessScale, setHardnessScale] = useState<"HRC" | "HV" | "HRB" | "HBW" | "HBS">("HRC");
  // Conversion tables exist only for non-austenitic steels; other classes keep the measured value only.
  const [hardnessClass, setHardnessClass] = useState<HardnessMaterialClass>("non-austenitic-steel");
  const hardnessResult = useMemo(
    () => convertHardness(hardnessVal, hardnessScale, hardnessClass),
    [hardnessVal, hardnessScale, hardnessClass]
  );

  // 2. Weldability & CE State
  const [ceComp, setCeComp] = useState({
    C: 0.22,
    Mn: 1.35,
    Si: 0.35,
    Cr: 0.25,
    Mo: 0.15,
    V: 0.05,
    Ni: 0.20,
    Cu: 0.15,
    Nb: 0.02,
    B: 0.0005,
  });
  const [plateThickness, setPlateThickness] = useState<number>(30);
  const ceResult = useMemo(
    () => calculateCarbonEquivalent(ceComp, plateThickness),
    [ceComp, plateThickness]
  );

  // 3. Diffusion & Case Depth State
  const [carbTemp, setCarbTemp] = useState<number>(930); // °C
  const [carbTime, setCarbTime] = useState<number>(6); // hours
  const [carbSurfaceC, setCarbSurfaceC] = useState<number>(1.05); // % C
  const [carbCoreC, setCarbCoreC] = useState<number>(0.20); // % C
  const diffusionResult = useMemo(
    () =>
      simulateCarburizingDiffusion(
        carbTemp,
        carbTime,
        carbSurfaceC,
        carbCoreC,
        0.40
      ),
    [carbTemp, carbTime, carbSurfaceC, carbCoreC]
  );

  // 4. Schaeffler State
  const [schaefflerComp, setSchaefflerComp] = useState({
    C: 0.05,
    Cr: 19.5,
    Ni: 9.8,
    Mo: 0.4,
    Si: 0.6,
    Mn: 1.7,
    Nb: 0.0,
    N: 0.04,
  });
  const schaefflerResult = useMemo(
    () => calculateSchaeffler(schaefflerComp),
    [schaefflerComp]
  );

  // 5. XRD State
  const [xrdStructure, setXrdStructure] = useState<"BCC" | "FCC">("BCC");
  const [latticeA, setLatticeA] = useState<number>(2.8665); // Å
  const [xrayTarget, setXrayTarget] = useState<"Cu-Ka" | "Mo-Ka" | "Co-Ka" | "Fe-Ka">("Cu-Ka");
  const xrdPeaks = useMemo(
    () => calculateXrdPeaks(xrdStructure, latticeA, xrayTarget),
    [xrdStructure, latticeA, xrayTarget]
  );

  // 6. Hall-Petch State
  const [grainSize, setGrainSize] = useState<number>(25); // µm
  const [sigma0, setSigma0] = useState<number>(70);
  const [ky, setKy] = useState<number>(18.5);
  const hallPetchResult = useMemo(
    () => calculateHallPetch(grainSize, sigma0, ky),
    [grainSize, sigma0, ky]
  );

  // 7. Transformation Temps State
  const [ttComp, setTtComp] = useState({
    C: 0.42,
    Mn: 0.85,
    Cr: 1.05,
    Mo: 0.22,
    Ni: 0.20,
    Si: 0.25,
    V: 0.02,
  });
  const ttResult = useMemo(() => calculateTransformationTemps(ttComp), [ttComp]);

  const handleSyncFromActiveSpecimen = () => {
    const comp = activeMaterialSpecimen.composition || {};
    // Populate Carbon Equivalent
    setCeComp((prev) => ({
      C: comp.C ?? prev.C,
      Mn: comp.Mn ?? prev.Mn,
      Si: comp.Si ?? prev.Si,
      Cr: comp.Cr ?? prev.Cr,
      Mo: comp.Mo ?? prev.Mo,
      V: comp.V ?? prev.V,
      Ni: comp.Ni ?? prev.Ni,
      Cu: comp.Cu ?? prev.Cu,
      Nb: comp.Nb ?? prev.Nb,
      B: comp.B ?? prev.B,
    }));
    // Populate Schaeffler
    setSchaefflerComp((prev) => ({
      C: comp.C ?? prev.C,
      Cr: comp.Cr ?? prev.Cr,
      Ni: comp.Ni ?? prev.Ni,
      Mo: comp.Mo ?? prev.Mo,
      Si: comp.Si ?? prev.Si,
      Mn: comp.Mn ?? prev.Mn,
      Nb: comp.Nb ?? prev.Nb,
      N: prev.N,
    }));
    // Populate Transformation
    setTtComp((prev) => ({
      C: comp.C ?? prev.C,
      Mn: comp.Mn ?? prev.Mn,
      Cr: comp.Cr ?? prev.Cr,
      Mo: comp.Mo ?? prev.Mo,
      Ni: comp.Ni ?? prev.Ni,
      Si: comp.Si ?? prev.Si,
      V: comp.V ?? prev.V,
    }));
    // Populate XRD
    if (activeMaterialSpecimen.xrd) {
      if (activeMaterialSpecimen.xrd.crystalSystem === "FCC" || activeMaterialSpecimen.xrd.crystalSystem === "BCC") {
        setXrdStructure(activeMaterialSpecimen.xrd.crystalSystem);
      }
      if (activeMaterialSpecimen.xrd.latticeA_A > 0) {
        setLatticeA(activeMaterialSpecimen.xrd.latticeA_A);
      }
    }
    setSyncToast(`Loaded chemistry from ${activeMaterialSpecimen.name}!`);
    setTimeout(() => setSyncToast(null), 3000);
  };

  return (
    <div id="pocket-calculators-container" className="space-y-6">
      {/* Universal Active Specimen Sync Banner */}
      <div className="p-3 bg-slate-900/90 border border-sky-500/30 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs shadow-md">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="flex items-center gap-1.5 font-bold text-sky-400">
            <Sparkles className="w-4 h-4 text-sky-400" />
            <span>Active Universal Specimen:</span>
          </span>
          <span className="px-2.5 py-0.5 rounded-full bg-sky-950/80 border border-sky-600/50 text-sky-200 font-semibold">
            {activeMaterialSpecimen.name}
          </span>
          <span className="font-mono text-slate-400 text-[11px]">
            ({activeMaterialSpecimen.chemicalFormula})
          </span>
          {syncToast && (
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[11px] font-medium">
              ✓ {syncToast}
            </span>
          )}
        </div>

        <button
          id="btn-sync-calculators-specimen"
          onClick={handleSyncFromActiveSpecimen}
          className="px-3 py-1.5 bg-sky-600/20 hover:bg-sky-600/30 text-sky-300 border border-sky-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm"
        >
          <RefreshCw className="w-3.5 h-3.5 text-sky-400" />
          <span>Sync Calculators from Active Specimen</span>
        </button>
      </div>

      {/* Dedicated Metallurgical Unit Conversions Section (MPa/ksi, RC/HV, Celsius/Kelvin/Rankine) */}
      <MetallurgicalQuickConversionsGrid
        onOpenFullSuite={() => setActiveTab("units")}
      />

      {/* Header Tabs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl bg-[#090e18] border border-[#162032] shadow-md">
        <div>
          <div className="flex items-center gap-2 text-sky-400 font-mono text-xs font-semibold uppercase tracking-widest">
            <Calculator className="w-4 h-4 text-sky-400" />
            Aerospace Metallurgy Toolbox
          </div>
          <h2 className="text-lg font-bold text-white tracking-tight mt-0.5">Analytical & Empirical Calculators</h2>
        </div>

        {/* Tab Buttons Bar */}
        <div className="flex flex-wrap gap-1 p-1 bg-[#060a12] rounded-lg border border-[#162032]">
          {[
            { id: "units", label: "Full Unit Suite (E140 / E112)", icon: Scale, stdCategory: "hardness" },
            { id: "hardness", label: "Hardness & Rm", icon: ArrowRightLeft, stdCategory: "hardness" },
            { id: "weldability", label: "CE & Weldability", icon: Flame, stdCategory: "weldability" },
            { id: "diffusion", label: "Fick's Diffusion", icon: Sliders, stdCategory: "diffusion" },
            { id: "schaeffler", label: "Schaeffler Diagram", icon: Layers, stdCategory: "schaeffler" },
            { id: "xrd", label: "XRD & Bragg", icon: Activity, stdCategory: "xrd" },
            { id: "hall-petch", label: "Hall-Petch", icon: TrendingUp, stdCategory: "hall_petch" },
            { id: "transformation", label: "Ms / Bs / Ac3", icon: Thermometer, stdCategory: "transformation" },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <div
                key={tab.id}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition ${
                  isActive
                    ? "bg-sky-500/15 border border-sky-400/50 text-sky-300 shadow-[0_0_10px_rgba(56,189,248,0.2)] font-semibold"
                    : "text-slate-400 hover:text-white hover:bg-white/5 border border-transparent"
                }`}
              >
                <button
                  type="button"
                  onClick={() => setActiveTab(tab.id as CalcTab)}
                  className="flex items-center gap-1.5 text-left"
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                </button>
                <StandardInfoIcon category={tab.stdCategory} align="center" size="sm" />
              </div>
            );
          })}
        </div>
      </div>

      {/* --- TAB 0: METALLURGICAL UNIT CONVERTER --- */}
      {activeTab === "units" && <MetallurgicalUnitConverter />}

      {/* --- TAB 1: HARDNESS & TENSILE CONVERTER --- */}
      {activeTab === "hardness" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Input Panel */}
          <div className="lg:col-span-5 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                  ASTM E140 / ISO 18265 Standard
                </span>
                <StandardInfoIcon category="hardness" align="left" />
              </div>
              <h3 className="text-sm font-bold text-white mt-0.5">Select Scale & Value</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {HARDNESS_CONVERSION_DISCLAIMER}
              </p>
            </div>

            <div className="grid grid-cols-5 gap-2">
              {(["HRC", "HV", "HRB", "HBW", "HBS"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    setHardnessScale(s);
                    setHardnessVal(hardnessInputForScale(hardnessVal, s));
                  }}
                  className={`py-1.5 text-xs font-mono font-bold rounded border transition ${
                    hardnessScale === s
                      ? "bg-sky-500/15 border-sky-400/50 text-sky-300 shadow-[0_0_8px_rgba(56,189,248,0.25)]"
                      : "bg-[#0c1322] border-[#162032] text-slate-400 hover:text-white"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            {/* Alloy class: only non-austenitic steels are converted */}
            <div className="flex justify-between items-center gap-2 text-xs text-slate-300 font-medium">
              <span>Alloy class</span>
              <select
                aria-label="Alloy class"
                value={hardnessClass}
                onChange={(e) => setHardnessClass(e.target.value as HardnessMaterialClass)}
                className="px-2 py-1 bg-[#0c1322] border border-[#1e2d46] rounded font-mono text-[11px] text-sky-300 focus:outline-none focus:border-sky-400"
              >
                {HARDNESS_MATERIAL_CLASSES.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Slider and Number Input */}
            <div className="space-y-2">
              <div className="flex justify-between items-center text-xs text-slate-300 font-medium">
                <span>Value in {hardnessScale}</span>
                <input aria-label={`Value in ${hardnessScale}`}
                  type="number"
                  inputMode="decimal"
                  value={hardnessVal}
                  onChange={(e) => setHardnessVal(parseFloat(e.target.value) || 0)}
                  className="w-24 px-2.5 py-1 bg-[#0c1322] border border-[#1e2d46] rounded text-right font-mono font-bold text-sky-400 focus:outline-none focus:border-sky-400"
                />
              </div>

              <input aria-label={`Value in ${hardnessScale} slider`}
                type="range"
                min={HARDNESS_VERIFIED_RANGES[hardnessScale]?.min}
                max={HARDNESS_VERIFIED_RANGES[hardnessScale]?.max}
                step={hardnessScale === "HRC" || hardnessScale === "HRB" ? 0.5 : 5}
                value={hardnessVal}
                onChange={(e) => setHardnessVal(parseFloat(e.target.value))}
                className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            {/* Presets */}
            <div>
              <span className="text-[10px] text-slate-400 font-mono tracking-wider block mb-2 uppercase">Aerospace & Metallurgy Presets:</span>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {HARDNESS_PRESETS.filter(
                  (p): p is HardnessPreset & { scale: "HRC" | "HV" | "HRB" | "HBW" } =>
                    p.scale === "HRC" || p.scale === "HV" || p.scale === "HRB" || p.scale === "HBW"
                ).map((p, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setHardnessScale(p.scale);
                      setHardnessVal(p.value);
                      setHardnessClass(p.cls);
                    }}
                    className="p-2 text-left bg-[#0c1322] border border-[#162032] hover:border-sky-400/40 rounded transition text-slate-300 hover:text-sky-300"
                  >
                    <div className="font-medium truncate text-xs">{p.name}</div>
                    <div className="font-mono text-[10px] text-slate-500">
                      {p.value} {p.scale}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Results Display */}
          <div className="lg:col-span-7 space-y-3">
            <div className="text-[11px] font-mono text-slate-300">
              Measured: <span className="font-bold text-white">{hardnessVal} {hardnessScale}</span>
              <span className="text-slate-500"> - other scales are table estimates (converted), not measurements.</span>
            </div>
            {hardnessClass !== "non-austenitic-steel" && (
              <div className="text-[11px] font-mono text-amber-300">{hardnessResult.validRangeNote}</div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] relative overflow-hidden">
                <span className="text-xs text-slate-400 font-mono">Vickers (HV)</span>
                <div className="text-2xl font-black font-mono text-cyan-400 mt-1">
                  {hardnessResult.HV ?? UNAVAILABLE_TEXT} <span className="text-xs font-normal text-slate-500">HV</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">Diamond 136° indenter</div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] relative overflow-hidden">
                <span className="text-xs text-slate-400 font-mono">Rockwell C (HRC)</span>
                <div className="text-2xl font-black font-mono text-sky-400 mt-1">
                  {hardnessResult.HRC ?? UNAVAILABLE_TEXT}{" "}
                  <span className="text-xs font-normal text-slate-500">HRC</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">120° Brale Diamond Cone</div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] relative overflow-hidden">
                <span className="text-xs text-slate-400 font-mono">Brinell (HBW)</span>
                <div className="text-2xl font-black font-mono text-emerald-400 mt-1">
                  {hardnessResult.HBW ?? UNAVAILABLE_TEXT} <span className="text-xs font-normal text-slate-500">HBW</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">10 mm carbide ball, 3000 kgf (E140 Table 1)</div>
                <div className="text-[10px] text-slate-400 mt-0.5 font-mono">
                  HB(S), E140 Table 2 (steel ball): {hardnessResult.HBS ?? UNAVAILABLE_TEXT}
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] relative overflow-hidden">
                <span className="text-xs text-slate-400 font-mono">Rockwell B (HRB)</span>
                <div className="text-2xl font-black font-mono text-indigo-300 mt-1">
                  {hardnessResult.HRB ?? UNAVAILABLE_TEXT}{" "}
                  <span className="text-xs font-normal text-slate-500">HRB</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">1/16" ball (100kgf)</div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] relative overflow-hidden col-span-2 sm:col-span-2">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-xs text-slate-400 font-mono">Estimated Tensile Strength (Rm)</span>
                    <div className="text-2xl font-black font-mono text-white mt-0.5">
                      {hardnessResult.tensileRm_MPa === null ? (
                        <span className="text-sm font-mono text-slate-500">{UNAVAILABLE_TEXT} ({hardnessResult.unavailable.Rm})</span>
                      ) : (
                        <>
                          ≈ {hardnessResult.tensileRm_MPa} <span className="text-xs font-normal text-slate-400">MPa</span>
                          <span className="text-sm font-mono text-slate-400 ml-2">({hardnessResult.tensileRm_ksi} ksi)</span>
                        </>
                      )}
                    </div>
                  </div>
                  <span className="px-2 py-0.5 bg-sky-500/10 text-sky-300 border border-sky-400/30 text-[11px] rounded font-mono font-semibold">
                    ISO 18265 Table A.1
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 mt-1.5">
                  {TENSILE_ESTIMATE_NOTE}
                </div>
                <div className="text-[10px] text-slate-500 mt-1">{BRINELL_NOTE}</div>
              </div>
            </div>

            {/* Hardness Scale Comparison Bar */}
            <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032] space-y-1.5">
              <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest block">
                Hardness Scale Range Indicator
              </span>
              <div className="h-2 w-full bg-[#060a12] rounded-full overflow-hidden p-0.5 relative flex border border-[#162032]">
                <div className="h-full bg-cyan-500/60 rounded-l-full" style={{ width: "25%" }}></div>
                <div className="h-full bg-sky-500/70" style={{ width: "25%" }}></div>
                <div className="h-full bg-blue-500/80 shadow-[0_0_8px_rgba(56,189,248,0.5)]" style={{ width: "25%" }}></div>
                <div className="h-full bg-indigo-500/80 rounded-r-full" style={{ width: "25%" }}></div>
              </div>
              <div className="flex justify-between text-[9px] font-mono text-slate-500">
                <span>Soft (100 HV)</span>
                <span>Structural (300 HV)</span>
                <span>Hardened (600 HV)</span>
                <span>Ultra-Hard (1200+ HV)</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 2: WELDABILITY & CARBON EQUIVALENTS --- */}
      {activeTab === "weldability" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Composition Input Sliders */}
          <div className="lg:col-span-6 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-3">
            <div className="flex justify-between items-center">
              <div>
                <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                  Chemical Composition (% wt)
                </span>
                <h3 className="text-sm font-bold text-white mt-0.5">Alloy Elements for CE Calculation</h3>
              </div>
              <button
                onClick={() =>
                  setCeComp({
                    C: 0.16,
                    Mn: 1.20,
                    Si: 0.30,
                    Cr: 0.05,
                    Mo: 0.02,
                    V: 0.01,
                    Ni: 0.05,
                    Cu: 0.02,
                    Nb: 0.02,
                    B: 0.0,
                  })
                }
                className="text-xs text-slate-400 hover:text-sky-300 flex items-center gap-1 font-mono transition"
              >
                <RefreshCw className="w-3 h-3" /> Reset S355
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
              {Object.entries(ceComp).map(([el, val]) => (
                <div key={el} className="p-2 bg-[#0c1322] rounded border border-[#162032]">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-white font-mono">{el}</span>
                    <input aria-label={`${el} content`}
                      type="number"
                      inputMode="decimal"
                      step={el === "B" ? "0.0001" : "0.01"}
                      value={val}
                      onChange={(e) =>
                        setCeComp({ ...ceComp, [el]: parseFloat(e.target.value) || 0 })
                      }
                      className="w-14 text-right font-mono font-bold text-sky-400 bg-transparent border-b border-[#1e2d46] focus:outline-none focus:border-sky-400"
                    />
                  </div>
                  <input aria-label={`${el} content slider`}
                    type="range"
                    min="0"
                    max={el === "C" ? 1.0 : el === "Mn" ? 2.5 : el === "Cr" || el === "Ni" ? 5.0 : el === "B" ? 0.005 : 1.5}
                    step={el === "B" ? 0.0001 : 0.01}
                    value={val}
                    onChange={(e) =>
                      setCeComp({ ...ceComp, [el]: parseFloat(e.target.value) })
                    }
                    className="w-full accent-sky-400 bg-[#060a12] cursor-pointer"
                  />
                </div>
              ))}
            </div>

            {/* Thickness Slider */}
            <div className="p-2.5 bg-[#0c1322] rounded border border-[#162032] space-y-1">
              <div className="flex justify-between text-xs text-slate-300 font-medium">
                <span>Joint Plate Thickness (t):</span>
                <span className="font-mono font-bold text-sky-400">{plateThickness} mm</span>
              </div>
              <input aria-label="Joint Plate Thickness (t) (mm)"
                type="range"
                min="5"
                max="100"
                step="5"
                value={plateThickness}
                onChange={(e) => setPlateThickness(parseInt(e.target.value))}
                className="w-full accent-sky-400 bg-[#060a12] cursor-pointer"
              />
            </div>
          </div>

          {/* CE & Preheat Results */}
          <div className="lg:col-span-6 space-y-3">
            <div className="grid grid-cols-3 gap-2.5">
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">CE (IIW)</span>
                <div className="text-xl font-black font-mono text-cyan-400 mt-0.5">{ceResult.ceIIW}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">C + Mn/6 + ...</div>
              </div>
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">Pcm (Ito-Bessyo)</span>
                <div className="text-xl font-black font-mono text-sky-400 mt-0.5">{ceResult.pcm}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">For low-C pipe/HSLA</div>
              </div>
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">CEN (Yurioka)</span>
                <div className="text-xl font-black font-mono text-emerald-400 mt-0.5">{ceResult.cen}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Non-linear carbon fit</div>
              </div>
            </div>

            {/* Weldability Verdict Banner */}
            <div
              className={`p-4 rounded-xl border ${
                ceResult.weldabilityLevel.includes("Excellent") || ceResult.weldabilityLevel.includes("Good")
                  ? "bg-emerald-950/20 border-emerald-500/40 text-emerald-300"
                  : ceResult.weldabilityLevel.includes("Moderate")
                  ? "bg-sky-950/25 border-sky-500/40 text-sky-300"
                  : "bg-amber-950/25 border-amber-500/40 text-amber-300"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-sky-400" />
                  <span className="font-bold text-xs uppercase tracking-wider font-mono">Weldability Assessment</span>
                </div>
                <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-black/60 border border-white/10 font-bold">
                  {ceResult.weldabilityLevel}
                </span>
              </div>

              <div className="mt-2.5 pt-2.5 border-t border-white/10 flex items-center justify-between">
                <div>
                  <div className="text-xs opacity-80">Recommended Minimum Preheat Temperature (AWS D1.1):</div>
                  <div className="text-2xl font-black font-mono mt-0.5 text-white">
                    {ceResult.recommendedPreheatTemp} °C{" "}
                    <span className="text-xs font-normal text-slate-400">
                      ({Math.round((ceResult.recommendedPreheatTemp * 9) / 5 + 32)} °F)
                    </span>
                  </div>
                </div>
                <Flame className="w-7 h-7 text-sky-400 opacity-60" />
              </div>

              <div className="mt-2.5 space-y-1 text-xs">
                {ceResult.riskNotes.map((note, idx) => (
                  <div key={idx} className="flex items-start gap-1.5">
                    <span className="text-sky-400 mt-0.5">•</span>
                    <span>{note}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Welding Metallurgy Tip */}
            <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032] text-xs text-slate-400 space-y-1">
              <span className="font-bold text-white block">Diffusible Hydrogen Control Guideline:</span>
              <p>
                Hydrogen-Induced Cold Cracking (HICC) requires (1) susceptible HAZ (CE &gt; 0.45), (2) diffusible hydrogen (&gt;5 mL / 100g), and (3) residual stresses.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 3: FICK'S DIFFUSION & CASE DEPTH --- */}
      {activeTab === "diffusion" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Sliders */}
          <div className="lg:col-span-5 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-3">
            <div>
              <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                Non-Steady State Diffusion (Fick's 2nd Law)
              </span>
              <h3 className="text-sm font-bold text-white mt-0.5">Carburizing Parameters</h3>
              <p className="text-xs text-slate-400">
                Solute Carbon diffusion in γ-Austenite matrix: D = D₀ · exp(-Q / RT).
              </p>
            </div>

            {/* Carburizing Temp */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-300 font-medium">
                <span>Furnace Temperature (T):</span>
                <span className="font-mono font-bold text-sky-400">{carbTemp} °C</span>
              </div>
              <input aria-label="Furnace Temperature (T) (°C)"
                type="range"
                min="840"
                max="1020"
                step="10"
                value={carbTemp}
                onChange={(e) => setCarbTemp(parseInt(e.target.value))}
                className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            {/* Carburizing Time */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-300 font-medium">
                <span>Soak Time at Temp (t):</span>
                <span className="font-mono font-bold text-sky-400">{carbTime} Hours</span>
              </div>
              <input aria-label="Soak Time at Temp (t) (Hours)"
                type="range"
                min="1"
                max="24"
                step="0.5"
                value={carbTime}
                onChange={(e) => setCarbTime(parseFloat(e.target.value))}
                className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            {/* Surface Carbon Potential */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-300 font-medium">
                <span>Surface Carbon Potential (Cs):</span>
                <span className="font-mono font-bold text-cyan-400">{carbSurfaceC.toFixed(2)} % C</span>
              </div>
              <input aria-label="Surface Carbon Potential (Cs) (% C)"
                type="range"
                min="0.70"
                max="1.30"
                step="0.05"
                value={carbSurfaceC}
                onChange={(e) => setCarbSurfaceC(parseFloat(e.target.value))}
                className="w-full accent-cyan-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            {/* Core Base Carbon */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-300 font-medium">
                <span>Base Alloy Core Carbon (C₀):</span>
                <span className="font-mono font-bold text-slate-300">{carbCoreC.toFixed(2)} % C</span>
              </div>
              <input aria-label="Base Alloy Core Carbon (C₀) (% C)"
                type="range"
                min="0.10"
                max="0.35"
                step="0.02"
                value={carbCoreC}
                onChange={(e) => setCarbCoreC(parseFloat(e.target.value))}
                className="w-full accent-slate-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            {/* Result KPI Badges */}
            <div className="grid grid-cols-2 gap-2.5 pt-2.5 border-t border-[#162032]">
              <div className="p-2.5 bg-[#0c1322] rounded border border-[#162032]">
                <span className="text-[10px] text-slate-400 font-mono">Effective Case Depth (0.40% C)</span>
                <div className="text-lg font-mono font-bold text-sky-400 mt-0.5">
                  {diffusionResult.effectiveCaseDepth} mm
                </div>
              </div>
              <div className="p-2.5 bg-[#0c1322] rounded border border-[#162032]">
                <span className="text-[10px] text-slate-400 font-mono">Total Case Depth</span>
                <div className="text-lg font-mono font-bold text-cyan-400 mt-0.5">
                  {diffusionResult.caseDepth} mm
                </div>
              </div>
            </div>
          </div>

          {/* Concentration vs Depth Chart */}
          <div className="lg:col-span-7 bg-[#090e18] rounded-xl border border-[#162032] p-4 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center mb-2.5">
                <h4 className="text-sm font-bold text-white">Carbon Concentration Profile: C(x, t)</h4>
                <span className="text-xs font-mono text-slate-400">
                  D = {(diffusionResult.diffusivity * 1e11).toFixed(2)} × 10⁻¹¹ m²/s
                </span>
              </div>

              {/* Chart */}
              <div className="w-full h-60">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={diffusionResult.profileData} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#162032" />
                    <XAxis
                      dataKey="depthMm"
                      stroke="#475569"
                      label={{ value: "Depth from Surface (mm)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                    />
                    <YAxis
                      stroke="#475569"
                      domain={[0, Math.max(1.4, carbSurfaceC + 0.1)]}
                      label={{ value: "Carbon Content (% wt)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#090e18", borderColor: "#162032", borderRadius: "6px", fontSize: "12px", color: "#fff" }}
                      formatter={(val: any) => [`${val}% C`, "Concentration"]}
                      labelFormatter={(label) => `Depth: ${label} mm`}
                    />
                    <ReferenceLine y={0.4} stroke="#38bdf8" strokeDasharray="4 4" label={{ value: "Effective Depth Limit (0.4% C / 50 HRC)", fill: "#38bdf8", fontSize: 10 }} />
                    <ReferenceLine x={diffusionResult.effectiveCaseDepth} stroke="#38bdf8" strokeDasharray="4 4" />
                    <Line
                      type="monotone"
                      dataKey="concentrationPct"
                      stroke="#38bdf8"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="p-2.5 bg-[#0c1322] rounded border border-[#162032] text-xs text-slate-400 mt-3 leading-relaxed">
              <span className="font-bold text-white">Harris Formula:</span> Case depth scales with square root of time (x ∝ √t). Raising temperature from 900°C to 980°C doubles diffusion velocity.
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 4: SCHAEFFLER CONSTITUTION DIAGRAM --- */}
      {activeTab === "schaeffler" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-5 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-3">
            <div>
              <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                Stainless & Dissimilar Welding Metallurgy
              </span>
              <h3 className="text-sm font-bold text-white mt-0.5">Schaeffler / DeLong Coordinates</h3>
              <p className="text-xs text-slate-400">
                Predicts weld constitution phases: Austenite (γ), Ferrite (δ), Martensite (α').
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2.5 text-xs">
              {Object.entries(schaefflerComp).map(([el, val]) => (
                <div key={el} className="p-2 bg-[#0c1322] rounded border border-[#162032]">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-white font-mono">{el}</span>
                    <input aria-label={`${el} content`}
                      type="number"
                      inputMode="decimal"
                      step={el === "C" || el === "N" ? "0.005" : "0.1"}
                      value={val}
                      onChange={(e) =>
                        setSchaefflerComp({ ...schaefflerComp, [el]: parseFloat(e.target.value) || 0 })
                      }
                      className="w-14 text-right font-mono font-bold text-sky-400 bg-transparent border-b border-[#1e2d46] focus:outline-none"
                    />
                  </div>
                  <input aria-label={`${el} content slider`}
                    type="range"
                    min="0"
                    max={el === "Cr" ? 30 : el === "Ni" ? 25 : el === "C" || el === "N" ? 0.3 : 5.0}
                    step={el === "C" || el === "N" ? 0.005 : 0.1}
                    value={val}
                    onChange={(e) =>
                      setSchaefflerComp({ ...schaefflerComp, [el]: parseFloat(e.target.value) })
                    }
                    className="w-full accent-sky-400 bg-[#060a12] cursor-pointer"
                  />
                </div>
              ))}
            </div>

            <div className="pt-2 border-t border-[#162032] flex flex-wrap gap-1.5">
              {[
                { name: "304L", comp: { C: 0.02, Cr: 18.2, Ni: 8.5, Mo: 0.2, Si: 0.5, Mn: 1.5, Nb: 0, N: 0.04 } },
                { name: "316L", comp: { C: 0.02, Cr: 17.0, Ni: 12.0, Mo: 2.2, Si: 0.5, Mn: 1.5, Nb: 0, N: 0.04 } },
                { name: "2205 Duplex", comp: { C: 0.02, Cr: 22.5, Ni: 5.5, Mo: 3.2, Si: 0.5, Mn: 1.5, Nb: 0, N: 0.18 } },
                { name: "309L", comp: { C: 0.02, Cr: 23.5, Ni: 13.0, Mo: 0.2, Si: 0.6, Mn: 1.8, Nb: 0, N: 0.05 } },
              ].map((preset, idx) => (
                <button
                  key={idx}
                  onClick={() => setSchaefflerComp(preset.comp)}
                  className="px-2 py-1 bg-[#0c1322] border border-[#162032] hover:border-sky-400/40 rounded text-xs font-mono text-slate-300 transition hover:text-sky-300"
                >
                  {preset.name}
                </button>
              ))}
            </div>
          </div>

          {/* Diagram Plot Area */}
          <div className="lg:col-span-7 bg-[#090e18] rounded-xl border border-[#162032] p-4 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center mb-2.5">
                <div>
                  <h4 className="text-sm font-bold text-white">Schaeffler Diagram Position</h4>
                  <div className="text-xs font-mono text-slate-400 mt-0.5">
                    Cr_eq = {schaefflerResult.crEq} % | Ni_eq = {schaefflerResult.niEq} %
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-400 font-mono block">Estimated Ferrite (FN)</span>
                  <span className="text-lg font-bold font-mono text-sky-400">
                    {schaefflerResult.ferriteNumberEstimated} FN
                  </span>
                </div>
              </div>

              {/* Schaeffler SVG Diagram */}
              <div className="w-full aspect-[16/10] bg-[#060a12] rounded-lg border border-[#162032] relative overflow-hidden p-2">
                <svg viewBox="0 0 400 280" className="w-full h-full">
                  {/* Grid Lines */}
                  <g stroke="#162032" strokeWidth="1">
                    {[0, 10, 20, 30, 40].map((cr) => (
                      <line key={cr} x1={cr * 9 + 30} y1="10" x2={cr * 9 + 30} y2="250" />
                    ))}
                    {[0, 10, 20, 30].map((ni) => (
                      <line key={ni} x1="30" y1={250 - ni * 7.5} x2="390" y2={250 - ni * 7.5} />
                    ))}
                  </g>

                  {/* Phase Field Regions */}
                  <polygon points="30,120 180,140 280,250 30,250" fill="rgba(16, 185, 129, 0.12)" stroke="rgba(16, 185, 129, 0.4)" strokeWidth="1.5" />
                  <text x="70" y="70" fill="#10b981" fontSize="12" fontWeight="bold" fontFamily="sans-serif">Austenite (γ)</text>

                  <polygon points="30,250 160,250 120,170 30,170" fill="rgba(239, 68, 68, 0.12)" stroke="rgba(239, 68, 68, 0.4)" strokeWidth="1.5" />
                  <text x="50" y="210" fill="#ef4444" fontSize="11" fontWeight="bold" fontFamily="sans-serif">Martensite (α')</text>

                  <polygon points="200,250 390,250 390,180 240,180" fill="rgba(56, 189, 248, 0.12)" stroke="rgba(56, 189, 248, 0.4)" strokeWidth="1.5" />
                  <text x="300" y="220" fill="#38bdf8" fontSize="11" fontWeight="bold" fontFamily="sans-serif">Ferrite (δ)</text>

                  <text x="180" y="160" fill="#38bdf8" fontSize="11" fontWeight="bold" fontFamily="sans-serif">γ + δ (3-12 FN)</text>

                  {/* Current Alloy Plotted Coordinate */}
                  {(() => {
                    const cx = Math.max(30, Math.min(390, 30 + schaefflerResult.crEq * 9));
                    const cy = Math.max(10, Math.min(250, 250 - schaefflerResult.niEq * 7.5));
                    return (
                      <g>
                        <circle cx={cx} cy={cy} r="10" fill="rgba(56, 189, 248, 0.3)" className="animate-ping" />
                        <circle cx={cx} cy={cy} r="5" fill="#38bdf8" stroke="#ffffff" strokeWidth="1.5" />
                        <text x={cx + 8} y={cy - 5} fill="#bae6fd" fontSize="10" fontWeight="bold" fontFamily="Fira Code">
                          Alloy ({schaefflerResult.primaryPhase})
                        </text>
                      </g>
                    );
                  })()}

                  {/* Axis labels */}
                  <text x="210" y="270" fill="#64748b" fontSize="10" textAnchor="middle">Cr Equivalent = %Cr + %Mo + 1.5%Si + 0.5%Nb</text>
                  <text x="12" y="130" fill="#64748b" fontSize="10" transform="rotate(-90 12 130)" textAnchor="middle">Ni Equivalent</text>
                </svg>
              </div>
            </div>

            <div className="p-2.5 bg-[#0c1322] rounded border border-[#162032] flex justify-between items-center text-xs text-slate-300 mt-2.5">
              <div>
                <span className="text-slate-400">Primary Phase: </span>
                <span className="font-bold text-sky-400 font-mono">{schaefflerResult.primaryPhase}</span>
              </div>
              <div>
                <span className="text-slate-400">Hot Cracking Risk: </span>
                <span className={`font-bold font-mono ${schaefflerResult.hotCrackingRisk === "High" ? "text-amber-400" : "text-emerald-400"}`}>
                  {schaefflerResult.hotCrackingRisk}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 5: XRD & BRAGG'S LAW --- */}
      {activeTab === "xrd" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-5 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-3">
            <div>
              <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                X-Ray Diffraction Indexer
              </span>
              <h3 className="text-sm font-bold text-white mt-0.5">Bragg's Law & Lattice Indexing</h3>
              <p className="text-xs text-slate-400">
                λ = 2d·sin(θ) with selection rules for cubic systems.
              </p>
            </div>

            {/* Target Select */}
            <div className="space-y-1">
              <label className="text-xs text-slate-400 font-medium">X-Ray Tube Target</label>
              <div className="grid grid-cols-4 gap-2">
                {(["Cu-Ka", "Mo-Ka", "Co-Ka", "Fe-Ka"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setXrayTarget(t)}
                    className={`py-1.5 text-xs font-mono font-bold rounded border transition ${
                      xrayTarget === t
                        ? "bg-sky-500/15 border-sky-400/50 text-sky-300 shadow-[0_0_8px_rgba(56,189,248,0.25)]"
                        : "bg-[#0c1322] border-[#162032] text-slate-400 hover:text-white"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Structure Select */}
            <div className="space-y-1">
              <label className="text-xs text-slate-400 font-medium">Bravais Lattice</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => {
                    setXrdStructure("BCC");
                    setLatticeA(2.8665); // α-Fe
                  }}
                  className={`py-1.5 text-xs font-mono font-bold rounded border transition ${
                    xrdStructure === "BCC"
                      ? "bg-sky-500/15 border-sky-400/50 text-sky-300 shadow-[0_0_8px_rgba(56,189,248,0.25)]"
                      : "bg-[#0c1322] border-[#162032] text-slate-400"
                  }`}
                >
                  BCC (α-Ferrite)
                </button>
                <button
                  onClick={() => {
                    setXrdStructure("FCC");
                    setLatticeA(3.590); // γ-Austenite
                  }}
                  className={`py-1.5 text-xs font-mono font-bold rounded border transition ${
                    xrdStructure === "FCC"
                      ? "bg-sky-500/15 border-sky-400/50 text-sky-300 shadow-[0_0_8px_rgba(56,189,248,0.25)]"
                      : "bg-[#0c1322] border-[#162032] text-slate-400"
                  }`}
                >
                  FCC (γ-Austenite / Al)
                </button>
              </div>
            </div>

            {/* Lattice parameter input */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-300 font-medium">
                <span>Lattice Parameter a (Å):</span>
                <input aria-label="Lattice Parameter a (Å)"
                  type="number"
                  inputMode="decimal"
                  step="0.01"
                  value={latticeA}
                  onChange={(e) => setLatticeA(parseFloat(e.target.value) || 2.86)}
                  className="w-20 px-2 py-0.5 bg-[#0c1322] border border-[#1e2d46] rounded text-right font-mono font-bold text-sky-400"
                />
              </div>
              <input aria-label="Lattice Parameter a (Å) slider"
                type="range"
                min="2.5"
                max="5.0"
                step="0.01"
                value={latticeA}
                onChange={(e) => setLatticeA(parseFloat(e.target.value))}
                className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
              />
            </div>
          </div>

          {/* Simulated XRD Diffractogram */}
          <div className="lg:col-span-7 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-3">
            <div className="flex justify-between items-center">
              <h4 className="text-sm font-bold text-white">Simulated Powder XRD Pattern</h4>
              <span className="text-xs font-mono text-slate-400">λ = {xrayTarget === "Cu-Ka" ? "1.5406" : "0.7093"} Å</span>
            </div>

            {/* Visual Peak Spectrum */}
            <div className="w-full h-44 bg-[#060a12] rounded-lg border border-[#162032] p-3 relative flex items-end">
              <div className="w-full h-full relative">
                {xrdPeaks.map((peak, idx) => {
                  const leftPct = ((peak.twoTheta - 20) / (120 - 20)) * 100;
                  const heightPct = peak.intensityPct;
                  return (
                    <div
                      key={idx}
                      className="absolute bottom-0 flex flex-col items-center group cursor-pointer"
                      style={{ left: `${leftPct}%` }}
                    >
                      <span className="text-[10px] font-mono font-bold text-sky-300 mb-1 opacity-90 group-hover:scale-110 transition">
                        {peak.hkl}
                      </span>
                      <div
                        className="w-1.5 bg-gradient-to-t from-sky-600 to-cyan-300 rounded-t shadow-lg shadow-sky-500/20"
                        style={{ height: `${heightPct * 1.2}px` }}
                      ></div>
                      <span className="text-[9px] font-mono text-slate-500 mt-1">{peak.twoTheta}°</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Peaks Data Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-[#0c1322] text-slate-400 border-b border-[#162032]">
                  <tr>
                    <th className="p-2">Miller Index (hkl)</th>
                    <th className="p-2">2θ Angle (°)</th>
                    <th className="p-2">d-Spacing (Å)</th>
                    <th className="p-2">Relative Intensity (I/I₀)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#162032]">
                  {xrdPeaks.map((p, idx) => (
                    <tr key={idx} className="hover:bg-white/[0.02]">
                      <td className="p-2 font-bold text-sky-400">{p.hkl}</td>
                      <td className="p-2 text-slate-200">{p.twoTheta}°</td>
                      <td className="p-2 text-cyan-400">{p.dSpacing} Å</td>
                      <td className="p-2 text-slate-400">{p.intensityPct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 6: HALL-PETCH GRAIN BOUNDARY STRENGTHENING --- */}
      {activeTab === "hall-petch" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-5 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-3">
            <div>
              <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                Grain Boundary Strengthening
              </span>
              <h3 className="text-sm font-bold text-white mt-0.5">Hall-Petch Equation</h3>
              <p className="text-xs text-slate-400">
                σ_y = σ₀ + k_y · d^(-1/2) relating grain diameter to yield strength.
              </p>
            </div>

            {/* Grain Size Slider */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-300 font-medium">
                <span>Average Grain Diameter (d, planimetric):</span>
                <span className="font-mono font-bold text-sky-400">{grainSize} µm</span>
              </div>
              <input aria-label="Average Grain Diameter (d, planimetric) (µm)"
                type="range"
                min="0.5"
                max="100"
                step="0.5"
                value={grainSize}
                onChange={(e) => setGrainSize(parseFloat(e.target.value))}
                className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            {/* Friction Stress Sigma0 */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-300 font-medium">
                <span>Lattice Friction Stress (σ₀):</span>
                <span className="font-mono font-bold text-slate-300">{sigma0} MPa</span>
              </div>
              <input aria-label="Lattice Friction Stress (σ₀) (MPa)"
                type="range"
                min="20"
                max="200"
                step="5"
                value={sigma0}
                onChange={(e) => setSigma0(parseInt(e.target.value))}
                className="w-full accent-slate-400 bg-[#0c1322] cursor-pointer"
              />
            </div>

            {/* Hall-Petch Slope ky */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-300 font-medium">
                <span>Hall-Petch Slope (k_y):</span>
                <span className="font-mono font-bold text-cyan-400">{ky} MPa·mm^(1/2)</span>
              </div>
              <input aria-label="Hall-Petch Slope (k_y) (MPa·mm^(1/2))"
                type="range"
                min="5"
                max="30"
                step="0.5"
                value={ky}
                onChange={(e) => setKy(parseFloat(e.target.value))}
                className="w-full accent-cyan-400 bg-[#0c1322] cursor-pointer"
              />
            </div>
          </div>

          {/* Results Display */}
          <div className="lg:col-span-7 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">Predicted Yield Strength (σ_y)</span>
                <div className="text-2xl font-black font-mono text-emerald-400 mt-1">
                  {hallPetchResult.yieldStrengthMpa} <span className="text-xs font-normal text-slate-500">MPa</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">
                  Base ({sigma0} MPa) + Boundary Increment ({hallPetchResult.strengtheningIncrement} MPa)
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">ASTM Grain Size (G)</span>
                <div className="text-2xl font-black font-mono text-sky-400 mt-1">
                  ASTM {hallPetchResult.astmG}
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">
                  Higher number = finer microstructural grain size
                </div>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] text-xs text-slate-300 leading-relaxed space-y-1">
              <span className="font-bold text-sky-400 block font-mono">Strength & Toughness Synergy:</span>
              <p>
                Grain refinement is the primary metallurgical mechanism that simultaneously raises yield strength and lowers ductile-to-brittle transition temperature (DBTT).
              </p>
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 7: TRANSFORMATION TEMPERATURES --- */}
      {activeTab === "transformation" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-5 bg-[#090e18] rounded-xl border border-[#162032] p-4 space-y-3">
            <div>
              <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                Continuous Cooling & Quench Parameters
              </span>
              <h3 className="text-sm font-bold text-white mt-0.5">Ms, Bs & Austenitizing Temps</h3>
              <p className="text-xs text-slate-400">
                Andrews & Steven-Haynes empirical thermodynamics models for steels.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2.5 text-xs">
              {Object.entries(ttComp).map(([el, val]) => (
                <div key={el} className="p-2 bg-[#0c1322] rounded border border-[#162032]">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-white font-mono">{el}</span>
                    <input aria-label={`${el} content`}
                      type="number"
                      inputMode="decimal"
                      step="0.01"
                      value={val}
                      onChange={(e) =>
                        setTtComp({ ...ttComp, [el]: parseFloat(e.target.value) || 0 })
                      }
                      className="w-14 text-right font-mono font-bold text-sky-400 bg-transparent border-b border-[#1e2d46] focus:outline-none"
                    />
                  </div>
                  <input aria-label={`${el} content slider`}
                    type="range"
                    min="0"
                    max={el === "C" ? 1.2 : el === "Cr" || el === "Ni" ? 5.0 : 2.0}
                    step="0.01"
                    value={val}
                    onChange={(e) =>
                      setTtComp({ ...ttComp, [el]: parseFloat(e.target.value) })
                    }
                    className="w-full accent-sky-400 bg-[#060a12] cursor-pointer"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-7 space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">Martensite Start (Ms)</span>
                <div className="text-xl font-black font-mono text-rose-400 mt-0.5">{ttResult.ms} °C</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Quench bath target</div>
              </div>

              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">Martensite Finish (Mf)</span>
                <div className="text-xl font-black font-mono text-indigo-300 mt-0.5">{ttResult.mf} °C</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Cryogenic threshold</div>
              </div>

              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">Bainite Start (Bs)</span>
                <div className="text-xl font-black font-mono text-sky-400 mt-0.5">{ttResult.bs} °C</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Austempering target</div>
              </div>

              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-xs text-slate-400 font-mono">Ac1 (Austenite Start)</span>
                <div className="text-xl font-black font-mono text-cyan-400 mt-0.5">{ttResult.ac1} °C</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Heating onset</div>
              </div>

              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032] col-span-2">
                <span className="text-xs text-slate-400 font-mono">Recommended Austenitizing Temp</span>
                <div className="text-xl font-black font-mono text-emerald-400 mt-0.5">
                  {ttResult.ac3 + 40} - {ttResult.ac3 + 60} °C
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">
                  (Ac3 = {ttResult.ac3} °C + 50°C superheat for homogenization)
                </div>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032] text-xs text-slate-400 space-y-1">
              <span className="font-bold text-white block">Retained Austenite Warning:</span>
              <p>
                If calculated Ms &lt; 220°C or Mf &lt; 20°C, significant retained austenite will persist after oil quenching, requiring sub-zero cryogenic stabilization treatment (-80°C or -196°C LN2).
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
