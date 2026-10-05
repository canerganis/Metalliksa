import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Layers,
  Cpu,
  Flame,
  Activity,
  Zap,
  TrendingUp,
  Sliders,
  Sparkles,
  Info,
  CheckCircle2,
  AlertTriangle,
  Compass,
  ArrowRight,
  Maximize2,
  Minimize2,
  RefreshCw,
  Box,
  Play,
  Download,
  FileCode,
  SlidersHorizontal,
  Target,
  Gauge,
  Crosshair,
  Wand2,
  Clock,
  Split,
  FileSpreadsheet,
  Check,
  Atom,
  ShieldCheck,
  ShieldAlert,
  BarChart3,
  Scale,
  Copy
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  Cell,
  ReferenceLine,
  AreaChart,
  Area
} from "recharts";
import {
  pythonComputationService,
  PythonICMEMultiScaleResult
} from "../services/pythonComputationService";
import { formatOptionalValue } from "../utils/icmeDisplay";

interface BenchmarkPreset {
  id: string;
  name: string;
  base: "Ni" | "Fe" | "Ti" | "Al";
  coolingRate: number;
  agingTemp: number;
  agingTime: number;
  composition: { [key: string]: number };
  component: string;
  description: string;
}

const ICME_PRESETS: BenchmarkPreset[] = [
  {
    id: "inconel718",
    name: "Inconel 718 (Aero LPBF + Aged)",
    base: "Ni",
    coolingRate: 150000,
    agingTemp: 720,
    agingTime: 8,
    composition: { Cr: 19.0, Fe: 18.0, Nb: 5.1, Mo: 3.0, Ti: 0.9, Al: 0.5, C: 0.05, Si: 0.2, Mn: 0.2 },
    component: "turbine_blade_root",
    description: "High-temperature aerospace superalloy with gamma prime/double-prime precipitation and fine LPBF cell structure."
  },
  {
    id: "ti64",
    name: "Ti-6Al-4V Grade 5 (Aero AM)",
    base: "Ti",
    coolingRate: 250000,
    agingTemp: 550,
    agingTime: 4,
    composition: { Al: 6.0, V: 4.0, Fe: 0.25, C: 0.05, Si: 0.05 },
    component: "lpbf_bracket",
    description: "Workhorse titanium aerospace alloy, basketweave alpha-prime martensite and fine grain boundary strength."
  },
  {
    id: "aisi4340",
    name: "AISI 4340 Ultra-High Strength Steel",
    base: "Fe",
    coolingRate: 250,
    agingTemp: 480,
    agingTime: 2,
    composition: { C: 0.40, Cr: 0.80, Ni: 1.80, Mo: 0.25, Mn: 0.70, Si: 0.25 },
    component: "pressure_bulkhead",
    description: "Deep-hardening structural steel with high fracture toughness and carbon solid solution strengthening."
  },
  {
    id: "alsi10mg",
    name: "AlSi10Mg Additive Alloy",
    base: "Al",
    coolingRate: 600000,
    agingTemp: 160,
    agingTime: 6,
    composition: { Si: 10.0, Mg: 0.45, Fe: 0.15, Ti: 0.05, Mn: 0.05 },
    component: "lpbf_bracket",
    description: "Lightweight eutectic silicon alloy strengthened by cellular Si network and Mg2Si precipitation."
  }
];

export function ICMEMultiScalePipelineStudio() {
  const [selectedPresetId, setSelectedPresetId] = useState<string>("inconel718");
  const [baseMetal, setBaseMetal] = useState<"Ni" | "Fe" | "Ti" | "Al">("Ni");
  const [alloyName, setAlloyName] = useState<string>("Inconel 718");
  const [coolingRateLog, setCoolingRateLog] = useState<number>(5.17); // 1.5e5 K/s
  const [agingTemp, setAgingTemp] = useState<number>(720);
  const [agingTime, setAgingTime] = useState<number>(8);
  const [componentType, setComponentType] = useState<string>("turbine_blade_root");
  const [comp, setComp] = useState<{ [key: string]: number }>({
    Cr: 19.0, Fe: 18.0, Nb: 5.1, Mo: 3.0, Ti: 0.9, Al: 0.5, C: 0.05, Si: 0.2, Mn: 0.2
  });

  const [activeScaleTab, setActiveScaleTab] = useState<"all" | "scale0" | "scale1" | "scale2" | "scale3" | "scale4" | "cae">("all");
  const [copiedCard, setCopiedCard] = useState<string | null>(null);

  // Result state
  const [pipelineResult, setPipelineResult] = useState<PythonICMEMultiScaleResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Calculate actual cooling rate
  const coolingRate = useMemo(() => Math.pow(10, coolingRateLog), [coolingRateLog]);

  // Balance Base Metal
  const baseMetalBalance = useMemo(() => {
    let sumOthers = 0;
    Object.keys(comp).forEach((k) => {
      sumOthers += comp[k] || 0;
    });
    return Math.max(0, parseFloat((100 - sumOthers).toFixed(1)));
  }, [comp]);

  // Load Preset
  const handleSelectPreset = (presetId: string) => {
    const p = ICME_PRESETS.find(item => item.id === presetId);
    if (!p) return;
    setSelectedPresetId(presetId);
    setAlloyName(p.name);
    setBaseMetal(p.base);
    setCoolingRateLog(parseFloat(Math.log10(p.coolingRate).toFixed(2)));
    setAgingTemp(p.agingTemp);
    setAgingTime(p.agingTime);
    setComponentType(p.component);
    setComp({ ...p.composition });
  };

  // Run Python Pipeline Calculation
  const runPipelineComputation = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await pythonComputationService.calculateICMEMultiScalePipeline({
        alloyName,
        baseMetal,
        crystalSystem: baseMetal === "Ni" || baseMetal === "Al" ? "FCC" : baseMetal === "Fe" ? "BCC" : "HCP",
        composition_wt: comp,
        coolingRate_C_s: coolingRate,
        agingTemp_C: agingTemp,
        agingTime_h: agingTime,
        componentType
      });
      setPipelineResult(res);
    } catch (err: any) {
      console.error("ICME pipeline execution failed:", err);
      setErrorMsg(err.message || "Failed to execute ICME multi-scale Python solver.");
    } finally {
      setIsLoading(false);
    }
  }, [alloyName, baseMetal, comp, coolingRate, agingTemp, agingTime, componentType]);

  // Auto trigger on initial load or parameter changes (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      runPipelineComputation();
    }, 300);
    return () => clearTimeout(timer);
  }, [runPipelineComputation]);

  const handleCopyCard = (format: "abaqus" | "lsDyna" | "ansys", text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCard(format);
    setTimeout(() => setCopiedCard(null), 2500);
  };

  // Prepare Strengthening Breakdown Chart Data
  const strengtheningData = useMemo(() => {
    if (!pipelineResult) return [];
    const sc = pipelineResult.scale3_continuumPlasticity.strengtheningContributions_MPa;
    return [
      { name: "Lattice Friction (σ₀)", value: sc.sigma_0_LatticeFriction, fill: "#38bdf8", desc: "Tabulated-constant Peierls-Nabarro" },
      { name: "Solid Solution (Δσ_ss)", value: sc.deltaSigma_SS_SolidSolution, fill: "#818cf8", desc: "Solute coefficients (k·√wt%)" },
      { name: "Grain Boundary (Δσ_hp)", value: sc.deltaSigma_HP_GrainBoundary, fill: "#34d399", desc: "Hall-Petch Grain Size" },
      { name: "Dislocations (Δσ_ρ)", value: sc.deltaSigma_Disloc_Forest, fill: "#fbbf24", desc: "Taylor Forest Strain" },
      { name: "Precipitation (Δσ_ppt)", value: sc.deltaSigma_Precip_OrowanCutting, fill: "#f87171", desc: "LSW Orowan Looping" }
    ];
  }, [pipelineResult]);

  return (
    <div className="space-y-6">
      {/* HEADER: Digital Thread banner */}
      <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-900 via-[#0b1329] to-slate-900 border border-sky-500/30 shadow-xl relative overflow-hidden">
        <div className="absolute -right-16 -top-16 w-64 h-64 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30 flex items-center gap-1.5">
                <Atom className="w-3.5 h-3.5 text-sky-400" />
                ICME illustrative estimate (10⁻¹⁰ m → 10⁻¹ m)
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Illustrative · closed-form
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-bold text-slate-100 tracking-tight flex items-center gap-2">
              Yield Strength Breakdown (Illustrative)
            </h1>
            <p className="text-xs md:text-sm text-slate-400 max-w-3xl">
              Closed-form chain on tabulated constants (no DFT, CALPHAD or FEA is run): <span className="text-sky-300 font-medium">Elastic constants table (Cᵢⱼ)</span> → <span className="text-indigo-300 font-medium">Solute strengthening table</span> → <span className="text-emerald-300 font-medium">LSW/Orowan Microstructure</span> → <span className="text-amber-300 font-medium">Schematic σ-ε Curve</span> → <span className="text-rose-300 font-medium">Yield-only Component Check</span>.
            </p>
            <p role="note" className="text-[11px] text-amber-300/90 max-w-3xl">
              <span className="font-semibold">Model status: {pipelineResult?.modelStatus ?? "illustrative"}.</span>{" "}
              {pipelineResult?.modelStatusNote ?? "Illustrative closed-form estimate on tabulated constants; not calibrated or validated. Ultimate tensile strength and fracture toughness are unavailable."}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={runPipelineComputation}
              disabled={isLoading}
              className="px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold text-xs transition flex items-center gap-2 shadow-lg shadow-sky-500/20 disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
              {isLoading ? "Solving..." : "Re-Calculate Pipeline"}
            </button>
          </div>
        </div>

        {/* 5-SCALE THREAD VISUALIZER */}
        <div className="mt-5 pt-4 border-t border-slate-800 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 font-mono text-xs">
          <div
            onClick={() => setActiveScaleTab("scale0")}
            className={`p-2.5 rounded-xl border transition cursor-pointer ${
              activeScaleTab === "scale0"
                ? "bg-sky-950/60 border-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.3)]"
                : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
            }`}
          >
            <div className="flex items-center justify-between text-[10px] text-sky-400 mb-0.5">
              <span>SCALE 0 (10⁻¹⁰ m)</span>
              <Atom className="w-3 h-3" />
            </div>
            <div className="font-bold text-slate-200">Elastic Constants</div>
            <div className="text-[10px] text-slate-400 mt-0.5">Cᵢⱼ, G, B, τ_PN, Taylor M</div>
          </div>

          <div
            onClick={() => setActiveScaleTab("scale1")}
            className={`p-2.5 rounded-xl border transition cursor-pointer ${
              activeScaleTab === "scale1"
                ? "bg-indigo-950/60 border-indigo-400 shadow-[0_0_12px_rgba(129,140,248,0.3)]"
                : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
            }`}
          >
            <div className="flex items-center justify-between text-[10px] text-indigo-400 mb-0.5">
              <span>SCALE 1 (10⁻⁸ m)</span>
              <Layers className="w-3 h-3" />
            </div>
            <div className="font-bold text-slate-200">Solute Strengthening</div>
            <div className="text-[10px] text-slate-400 mt-0.5">Size/Modulus Misfit, Δσ_ss</div>
          </div>

          <div
            onClick={() => setActiveScaleTab("scale2")}
            className={`p-2.5 rounded-xl border transition cursor-pointer ${
              activeScaleTab === "scale2"
                ? "bg-emerald-950/60 border-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.3)]"
                : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
            }`}
          >
            <div className="flex items-center justify-between text-[10px] text-emerald-400 mb-0.5">
              <span>SCALE 2 (10⁻⁶ m)</span>
              <Flame className="w-3 h-3" />
            </div>
            <div className="font-bold text-slate-200">Microstructure</div>
            <div className="text-[10px] text-slate-400 mt-0.5">SDAS, Hall-Petch, LSW, Orowan</div>
          </div>

          <div
            onClick={() => setActiveScaleTab("scale3")}
            className={`p-2.5 rounded-xl border transition cursor-pointer ${
              activeScaleTab === "scale3"
                ? "bg-amber-950/60 border-amber-400 shadow-[0_0_12px_rgba(251,191,36,0.3)]"
                : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
            }`}
          >
            <div className="flex items-center justify-between text-[10px] text-amber-400 mb-0.5">
              <span>SCALE 3 (10⁻³ m)</span>
              <Activity className="w-3 h-3" />
            </div>
            <div className="font-bold text-slate-200">Tensile Constitutive</div>
            <div className="text-[10px] text-slate-400 mt-0.5">σ-ε, Rp0.2, J-C (UTS, K₁c unavailable)</div>
          </div>

          <div
            onClick={() => setActiveScaleTab("scale4")}
            className={`p-2.5 rounded-xl border transition cursor-pointer ${
              activeScaleTab === "scale4"
                ? "bg-rose-950/60 border-rose-400 shadow-[0_0_12px_rgba(248,113,113,0.3)]"
                : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
            }`}
          >
            <div className="flex items-center justify-between text-[10px] text-rose-400 mb-0.5">
              <span>SCALE 4 (10⁻¹ m)</span>
              <Target className="w-3 h-3" />
            </div>
            <div className="font-bold text-slate-200">Macro Yield Check</div>
            <div className="text-[10px] text-slate-400 mt-0.5">Component Load, CAE (flaw a_c unavailable)</div>
          </div>
        </div>
      </div>

      {/* BENCHMARK ALLOY PRESET SELECTOR */}
      <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-amber-400" />
            Standard Benchmark Preset:
          </span>
          <div className="flex flex-wrap items-center gap-1.5">
            {ICME_PRESETS.map((p) => (
              <button
                key={p.id}
                onClick={() => handleSelectPreset(p.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition cursor-pointer ${
                  selectedPresetId === p.id
                    ? "bg-sky-500 text-slate-950 font-bold shadow-md shadow-sky-500/20"
                    : "bg-slate-800/80 text-slate-300 hover:bg-slate-700 border border-slate-700/60"
                }`}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>

        {pipelineResult && (
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            Solver latency: <span className="text-emerald-300 font-bold">{pipelineResult.computeTimeMs} ms</span>
          </div>
        )}
      </div>

      {/* INPUT PARAMETER CONTROLS */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Composition & Base Metal */}
        <div className="lg:col-span-5 p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-sky-400" />
              Alloy Composition (wt%)
            </h2>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-sky-950/60 text-sky-300 border border-sky-800/60">
              Base: {baseMetal} ({baseMetalBalance} wt%)
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] text-slate-400 font-medium">Base Metal</label>
              <select aria-label="Base Metal"
                value={baseMetal}
                onChange={(e) => setBaseMetal(e.target.value as any)}
                className="w-full mt-1 bg-slate-800 border border-slate-700 text-slate-200 rounded-xl px-3 py-1.5 text-xs focus:ring-2 focus:ring-sky-500"
              >
                <option value="Ni">Nickel (Ni-base Superalloys)</option>
                <option value="Fe">Iron (Fe-base Steels)</option>
                <option value="Ti">Titanium (Ti-6Al-4V)</option>
                <option value="Al">Aluminum (Al-Si-Mg)</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] text-slate-400 font-medium">Target Component</label>
              <select aria-label="Target Component"
                value={componentType}
                onChange={(e) => setComponentType(e.target.value)}
                className="w-full mt-1 bg-slate-800 border border-slate-700 text-slate-200 rounded-xl px-3 py-1.5 text-xs focus:ring-2 focus:ring-sky-500"
              >
                <option value="turbine_blade_root">Turbine Blade Fir-Tree Root</option>
                <option value="pressure_bulkhead">Cryo Pressure Bulkhead</option>
                <option value="lpbf_bracket">Generative LPBF Rocket Bracket</option>
              </select>
            </div>
          </div>

          {/* Elemental wt% Sliders */}
          <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
            {Object.keys(comp).map((el) => (
              <div key={el} className="space-y-1">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-300 font-semibold">{el}</span>
                  <span className="text-sky-300">{comp[el].toFixed(2)} wt%</span>
                </div>
                <input aria-label={`${el} content (wt%)`}
                  type="range"
                  min="0"
                  max={el === "Ni" || el === "Fe" || el === "Cr" ? "30" : "15"}
                  step="0.05"
                  value={comp[el]}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    setComp(prev => ({ ...prev, [el]: val }));
                  }}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-400"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Thermal & Process Conditions */}
        <div className="lg:col-span-7 p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <Flame className="w-4 h-4 text-amber-400" />
              Solidification & Heat Treatment Kinetics
            </h2>
            <span className="text-xs font-mono text-amber-300 bg-amber-950/60 px-2 py-0.5 rounded border border-amber-800/60">
              dT/dt = {coolingRate.toLocaleString(undefined, { maximumFractionDigits: 0 })} K/s
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Cooling Rate Slider */}
            <div className="space-y-2 p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60">
              <div className="flex justify-between text-xs">
                <span className="text-slate-300 font-medium">Solidification Cooling Rate</span>
                <span className="font-mono text-sky-400">10^{coolingRateLog.toFixed(2)} K/s</span>
              </div>
              <input aria-label="Solidification Cooling Rate (log10 K/s)" aria-valuetext={`10^${coolingRateLog.toFixed(2)} K/s`}
                type="range"
                min="0.5"
                max="6.0"
                step="0.05"
                value={coolingRateLog}
                onChange={(e) => setCoolingRateLog(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400"
              />
              <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                <span>1 K/s (Sand Cast)</span>
                <span>10³ K/s (Die)</span>
                <span>10⁶ K/s (LPBF AM)</span>
              </div>
            </div>

            {/* Aging Heat Treatment */}
            <div className="space-y-2 p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60">
              <div className="flex justify-between text-xs">
                <span className="text-slate-300 font-medium">LSW Aging Temp & Time</span>
                <span className="font-mono text-amber-400">{agingTemp} °C / {agingTime} h</span>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-1">
                <div>
                  <label className="text-[10px] text-slate-400">Aging Temp (°C)</label>
                  <input aria-label="Aging Temp (°C)"
                    type="number"
                    value={agingTemp}
                    onChange={(e) => setAgingTemp(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400">Aging Time (hours)</label>
                  <input aria-label="Aging Time (hours)"
                    type="number"
                    value={agingTime}
                    onChange={(e) => setAgingTime(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 font-mono"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Quick Summary Badges */}
          {pipelineResult && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-center font-mono">
              <div className="p-2.5 rounded-xl bg-slate-800/70 border border-slate-700/60">
                <div className="text-[10px] text-slate-400">Yield Strength (Rp0.2)</div>
                <div className="text-base font-bold text-sky-400">{pipelineResult.scale3_continuumPlasticity.mechanicalProperties.yieldStrength_Rp02_MPa} MPa</div>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-800/70 border border-slate-700/60">
                <div className="text-[10px] text-slate-400">Tensile UTS</div>
                <div className="text-base font-bold text-indigo-400" title={pipelineResult.scale3_continuumPlasticity.mechanicalProperties.ultimateTensileStrength_UTS_status}>{formatOptionalValue(pipelineResult.scale3_continuumPlasticity.mechanicalProperties.ultimateTensileStrength_UTS_MPa, "MPa")}</div>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-800/70 border border-slate-700/60">
                <div className="text-[10px] text-slate-400">Elongation (A%)</div>
                <div className="text-base font-bold text-emerald-400">{pipelineResult.scale3_continuumPlasticity.mechanicalProperties.totalElongationPct}%</div>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-800/70 border border-slate-700/60">
                <div className="text-[10px] text-slate-400">Fracture K₁c</div>
                <div className="text-base font-bold text-rose-400" title={pipelineResult.scale3_continuumPlasticity.mechanicalProperties.fractureToughness_K1c_status}>{formatOptionalValue(pipelineResult.scale3_continuumPlasticity.mechanicalProperties.fractureToughness_K1c_MPa_sqrt_m, "MPa√m")}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* MULTI-SCALE DETAIL TABS */}
      <div className="flex items-center gap-1.5 border-b border-slate-800 pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveScaleTab("all")}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 ${
            activeScaleTab === "all"
              ? "bg-slate-200 text-slate-900"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
          }`}
        >
          <Layers className="w-3.5 h-3.5" /> Full Pipeline View
        </button>
        <button
          onClick={() => setActiveScaleTab("scale0")}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 ${
            activeScaleTab === "scale0"
              ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
          }`}
        >
          <Atom className="w-3.5 h-3.5" /> Scale 0: Elastic Constants
        </button>
        <button
          onClick={() => setActiveScaleTab("scale1")}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 ${
            activeScaleTab === "scale1"
              ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
          }`}
        >
          <Sliders className="w-3.5 h-3.5" /> Scale 1: Solute Misfit
        </button>
        <button
          onClick={() => setActiveScaleTab("scale2")}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 ${
            activeScaleTab === "scale2"
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
          }`}
        >
          <Flame className="w-3.5 h-3.5" /> Scale 2: Kinetics & Orowan
        </button>
        <button
          onClick={() => setActiveScaleTab("scale3")}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 ${
            activeScaleTab === "scale3"
              ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
          }`}
        >
          <Activity className="w-3.5 h-3.5" /> Scale 3: Tensile σ-ε
        </button>
        <button
          onClick={() => setActiveScaleTab("scale4")}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 ${
            activeScaleTab === "scale4"
              ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
          }`}
        >
          <Target className="w-3.5 h-3.5" /> Scale 4: Yield Check
        </button>
        <button
          onClick={() => setActiveScaleTab("cae")}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 ${
            activeScaleTab === "cae"
              ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
          }`}
        >
          <FileCode className="w-3.5 h-3.5" /> CAE Material Cards
        </button>
      </div>

      {/* TAB CONTENT AREAS */}
      {pipelineResult && (
        <div className="space-y-6">
          {/* STRENGTHENING WATERFALL & TENSILE CURVE (Always prominent) */}
          {(activeScaleTab === "all" || activeScaleTab === "scale3") && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Strengthening Contributions Bar */}
              <div className="lg:col-span-5 p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-sky-400" />
                    Physics Strengthening Superposition (MPa)
                  </h3>
                  <span className="text-xs font-mono text-slate-400">Power Law q=1.4</span>
                </div>

                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={strengtheningData} layout="vertical" margin={{ left: 10, right: 30, top: 10, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis type="number" stroke="#64748b" tick={{ fontSize: 10 }} />
                      <YAxis dataKey="name" type="category" stroke="#cbd5e1" tick={{ fontSize: 10 }} width={130} />
                      <Tooltip
                        contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "12px" }}
                        formatter={(val: number) => [`${val} MPa`, "Contribution"]}
                      />
                      <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                        {strengtheningData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60 font-mono text-xs space-y-1">
                  <div className="flex justify-between text-slate-300">
                    <span>Yield Equation:</span>
                    <span className="text-sky-300">σ_y = σ₀ + Δσ_ss + Δσ_hp + (Δσ_ρ^1.4 + Δσ_ppt^1.4)^(1/1.4)</span>
                  </div>
                  <div className="flex justify-between text-slate-400 text-[11px]">
                    <span>Total Calculated Rp0.2:</span>
                    <span className="text-emerald-400 font-bold">{pipelineResult.scale3_continuumPlasticity.mechanicalProperties.yieldStrength_Rp02_MPa} MPa</span>
                  </div>
                </div>
              </div>

              {/* Stress-Strain Constitutive Tensile Curve */}
              <div className="lg:col-span-7 p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    Constitutive Stress-Strain Curve (σ - ε)
                  </h3>
                  <div className="flex items-center gap-3 text-xs font-mono">
                    <span className="flex items-center gap-1 text-sky-400">
                      <span className="w-2 h-2 rounded-full bg-sky-400"></span> Eng. Stress
                    </span>
                    <span className="flex items-center gap-1 text-emerald-400">
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span> True Stress
                    </span>
                  </div>
                </div>

                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={pipelineResult.scale3_continuumPlasticity.stressStrainCurve} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis
                        dataKey="engineeringStrainPct"
                        stroke="#64748b"
                        tick={{ fontSize: 10 }}
                        unit="%"
                        label={{ value: "Engineering Strain (%)", position: "insideBottom", offset: -5, fill: "#64748b", fontSize: 10 }}
                      />
                      <YAxis
                        stroke="#64748b"
                        tick={{ fontSize: 10 }}
                        unit=" MPa"
                        label={{ value: "Stress (MPa)", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 10 }}
                      />
                      <Tooltip
                        contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "12px", fontSize: "11px" }}
                        formatter={(val: number, name: string) => [`${val} MPa`, name === "engineeringStressMPa" ? "Eng Stress" : "True Stress"]}
                        labelFormatter={(lbl) => `Strain: ${lbl}%`}
                      />
                      <ReferenceLine y={pipelineResult.scale3_continuumPlasticity.mechanicalProperties.yieldStrength_Rp02_MPa} stroke="#38bdf8" strokeDasharray="3 3" label={{ value: "Rp0.2", fill: "#38bdf8", fontSize: 10 }} />
                      {pipelineResult.scale3_continuumPlasticity.mechanicalProperties.ultimateTensileStrength_UTS_MPa != null && (
                        <ReferenceLine y={pipelineResult.scale3_continuumPlasticity.mechanicalProperties.ultimateTensileStrength_UTS_MPa} stroke="#f87171" strokeDasharray="3 3" label={{ value: "UTS", fill: "#f87171", fontSize: 10 }} />
                      )}
                      <Line type="monotone" dataKey="engineeringStressMPa" stroke="#38bdf8" strokeWidth={2.5} dot={false} name="engineeringStressMPa" />
                      <Line type="monotone" dataKey="trueStressMPa" stroke="#34d399" strokeWidth={1.5} dot={false} strokeDasharray="4 4" name="trueStressMPa" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                  <div className="p-2 rounded-xl bg-slate-800/40 border border-slate-700/50">
                    <span className="text-slate-400 block text-[10px]">Hardening exponent n (placeholder):</span>
                    <span className="text-amber-300 font-bold">{pipelineResult.scale3_continuumPlasticity.mechanicalProperties.hollomon_n}</span>
                  </div>
                  <div className="p-2 rounded-xl bg-slate-800/40 border border-slate-700/50">
                    <span className="text-slate-400 block text-[10px]">Strength Coeff (K):</span>
                    <span className="text-indigo-300 font-bold">{pipelineResult.scale3_continuumPlasticity.mechanicalProperties.hollomon_K_MPa} MPa</span>
                  </div>
                  <div className="p-2 rounded-xl bg-slate-800/40 border border-slate-700/50">
                    <span className="text-slate-400 block text-[10px]">Uniform Strain (ε_u):</span>
                    <span className="text-emerald-300 font-bold">{pipelineResult.scale3_continuumPlasticity.mechanicalProperties.uniformElongationPct}%</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SCALE 0: DFT ATOMISTIC DETAILS */}
          {(activeScaleTab === "all" || activeScaleTab === "scale0") && (
            <div className="p-5 rounded-2xl bg-slate-900/90 border border-sky-500/30 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-sky-300 flex items-center gap-2">
                  <Atom className="w-4 h-4 text-sky-400" />
                  Scale 0 (10⁻¹⁰ m): Tabulated Elastic Stiffness & Peierls-Nabarro Estimate
                </h3>
                <span className="text-xs font-mono text-slate-400">Tabulated constants (no DFT run)</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Elastic Tensor Matrix */}
                <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Cubic/Hex Elastic Stiffness Cᵢⱼ (GPa)</div>
                  <div className="grid grid-cols-3 gap-2 font-mono text-xs text-center">
                    <div className="p-2 rounded bg-slate-900 border border-slate-700">
                      <div className="text-[10px] text-slate-400">C11</div>
                      <div className="text-sky-300 font-bold">{pipelineResult.scale0_dftAtomistic.elasticTensor_Cij_GPa.C11}</div>
                    </div>
                    <div className="p-2 rounded bg-slate-900 border border-slate-700">
                      <div className="text-[10px] text-slate-400">C12</div>
                      <div className="text-sky-300 font-bold">{pipelineResult.scale0_dftAtomistic.elasticTensor_Cij_GPa.C12}</div>
                    </div>
                    <div className="p-2 rounded bg-slate-900 border border-slate-700">
                      <div className="text-[10px] text-slate-400">C44</div>
                      <div className="text-sky-300 font-bold">{pipelineResult.scale0_dftAtomistic.elasticTensor_Cij_GPa.C44}</div>
                    </div>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Cauchy Pressure (C12 - C44): <strong className="text-slate-200">{pipelineResult.scale0_dftAtomistic.homogenizedModuli.cauchyPressure_GPa} GPa</strong>
                  </div>
                </div>

                {/* VRH Homogenized Moduli */}
                <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Voigt-Reuss-Hill Homogenization</div>
                  <div className="space-y-1 text-xs font-mono">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Young's Modulus (E):</span>
                      <span className="text-slate-200 font-bold">{pipelineResult.scale0_dftAtomistic.homogenizedModuli.youngsModulus_E_GPa} GPa</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Shear Modulus (G):</span>
                      <span className="text-slate-200 font-bold">{pipelineResult.scale0_dftAtomistic.homogenizedModuli.shearModulus_G_GPa} GPa</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Bulk Modulus (B):</span>
                      <span className="text-slate-200 font-bold">{pipelineResult.scale0_dftAtomistic.homogenizedModuli.bulkModulus_B_GPa} GPa</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Poisson's Ratio (ν):</span>
                      <span className="text-slate-200 font-bold">{pipelineResult.scale0_dftAtomistic.homogenizedModuli.poissonsRatio}</span>
                    </div>
                  </div>
                </div>

                {/* Pugh Ductility & Peierls-Nabarro */}
                <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Peierls-Nabarro Dislocation Friction</div>
                  <div className="space-y-1 text-xs font-mono">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Burgers Vector (b):</span>
                      <span className="text-slate-200">{pipelineResult.scale0_dftAtomistic.burgersVector_b_nm} nm</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Slip Plane Spacing (d):</span>
                      <span className="text-slate-200">{pipelineResult.scale0_dftAtomistic.slipPlane_dhkl_nm} nm</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Taylor Orientation Factor (M):</span>
                      <span className="text-slate-200">{pipelineResult.scale0_dftAtomistic.peierlsNabarroLatticeFriction.taylorFactor_M}</span>
                    </div>
                    <div className="flex justify-between text-sky-400 font-bold pt-1 border-t border-slate-700">
                      <span>Lattice Friction (σ₀):</span>
                      <span>{pipelineResult.scale0_dftAtomistic.peierlsNabarroLatticeFriction.sigma_0_friction_stress_MPa} MPa</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SCALE 1 & SCALE 2: SOLUTE MISFIT & MICROSTRUCTURE */}
          {(activeScaleTab === "all" || activeScaleTab === "scale1" || activeScaleTab === "scale2") && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Scale 1: Solute Misfit Breakdown */}
              <div className="p-5 rounded-2xl bg-slate-900/90 border border-indigo-500/30 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-indigo-300 flex items-center gap-2">
                    <Layers className="w-4 h-4 text-indigo-400" />
                    Scale 1 (10⁻⁸ m): Solute Size & Modulus Misfit (Labusch)
                  </h3>
                  <span className="text-xs font-mono text-indigo-400 font-bold">
                    Total Δσ_ss: {pipelineResult.scale1_calphadSoluteMisfit.totalSolidSolutionStrengthening_MPa} MPa
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs font-mono text-left">
                    <thead className="text-[10px] text-slate-400 uppercase bg-slate-800/60 border-b border-slate-700">
                      <tr>
                        <th className="py-2 px-3">Solute</th>
                        <th className="py-2 px-3">wt%</th>
                        <th className="py-2 px-3">at%</th>
                        <th className="py-2 px-3">Size Misfit (δ_a)</th>
                        <th className="py-2 px-3">Modulus Misfit (η_G)</th>
                        <th className="py-2 px-3 text-right">Strengthening (MPa)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {Object.keys(pipelineResult.scale1_calphadSoluteMisfit.soluteBreakdown).map((el) => {
                        const sb = pipelineResult.scale1_calphadSoluteMisfit.soluteBreakdown[el];
                        return (
                          <tr key={el} className="hover:bg-slate-800/40">
                            <td className="py-2 px-3 font-bold text-slate-200">{el}</td>
                            <td className="py-2 px-3 text-slate-300">{sb.wt_pct ?? "-"}%</td>
                            <td className="py-2 px-3 text-slate-400">{sb.at_frac}%</td>
                            <td className="py-2 px-3 text-sky-400">{sb.sizeMisfit}</td>
                            <td className="py-2 px-3 text-indigo-400">{sb.modulusMisfit}</td>
                            <td className="py-2 px-3 text-right font-bold text-emerald-400">+{sb.strengthContribution_MPa}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Scale 2: Microstructure, Grain Size & LSW Orowan */}
              <div className="p-5 rounded-2xl bg-slate-900/90 border border-emerald-500/30 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-emerald-300 flex items-center gap-2">
                    <Flame className="w-4 h-4 text-emerald-400" />
                    Scale 2 (10⁻⁶ m): Microstructure & LSW Precipitate Looping
                  </h3>
                  <span className="text-xs font-mono text-emerald-400">Kinetics & Dislocation Obstacles</span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60">
                    <span className="text-slate-400 block text-[10px]">SDAS / Grain Size:</span>
                    <span className="text-slate-200 font-bold">{pipelineResult.scale2_microstructureKinetics.grainSize_d_um} µm</span>
                    <div className="text-[11px] text-emerald-400 mt-1">
                      Hall-Petch: +{pipelineResult.scale2_microstructureKinetics.hallPetchStrengthening_MPa} MPa
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60">
                    <span className="text-slate-400 block text-[10px]">Dislocation Density (ρ):</span>
                    <span className="text-slate-200 font-bold">{pipelineResult.scale2_microstructureKinetics.dislocationDensity_rho_m2} m⁻²</span>
                    <div className="text-[11px] text-amber-400 mt-1">
                      Taylor Forest: +{pipelineResult.scale2_microstructureKinetics.taylorDislocationStrengthening_MPa} MPa
                    </div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2 text-xs font-mono">
                  <div className="flex items-center justify-between text-slate-300">
                    <span className="font-semibold">Precipitate Kinetics (LSW):</span>
                    <span className="text-sky-300">Radius r̄ = {pipelineResult.scale2_microstructureKinetics.precipitationKinetics.meanPrecipitateRadius_nm} nm</span>
                  </div>
                  <div className="text-slate-400 text-[11px]">
                    Interparticle Spacing (λ): <strong className="text-slate-200">{pipelineResult.scale2_microstructureKinetics.precipitationKinetics.interparticleSpacing_nm} nm</strong> | Volume Fraction: <strong className="text-slate-200">{pipelineResult.scale2_microstructureKinetics.precipitationKinetics.volumeFractionPct}%</strong>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-emerald-500/30 text-[11px] flex items-center justify-between">
                    <span className="text-slate-300">Active Mechanism:</span>
                    <span className="text-emerald-400 font-bold">{pipelineResult.scale2_microstructureKinetics.precipitationKinetics.activeMechanism}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SCALE 4: MACRO STRUCTURAL FEA & LEFM DAMAGE TOLERANCE */}
          {(activeScaleTab === "all" || activeScaleTab === "scale4") && (
            <div className="p-5 rounded-2xl bg-slate-900/90 border border-rose-500/30 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-rose-300 flex items-center gap-2">
                  <Target className="w-4 h-4 text-rose-400" />
                  Scale 4 (10⁻¹ m): Macro Yield Check (no FEA); Flaw Tolerance Unavailable
                </h3>
                <span className="text-xs font-mono text-slate-400">Yield-only check, no creep / fracture check</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Component Load Rating</div>
                  <div className="space-y-1 text-xs font-mono">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Target Part:</span>
                      <span className="text-slate-200 font-bold">{pipelineResult.scale4_macroComponentFEA.componentName}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Applied Service Stress:</span>
                      <span className="text-amber-400 font-bold">{pipelineResult.scale4_macroComponentFEA.appliedStress_MPa} MPa</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Required Safety Factor:</span>
                      <span className="text-slate-300">{pipelineResult.scale4_macroComponentFEA.requiredSafetyFactor}</span>
                    </div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Actual Structural Safety Factor</div>
                  <div className="flex items-baseline gap-2 font-mono">
                    <span className="text-2xl font-bold text-emerald-400">{pipelineResult.scale4_macroComponentFEA.actualSafetyFactor}x</span>
                    <span className="text-xs text-slate-400">against Rp0.2</span>
                  </div>
                  <div
                    className={`p-2 rounded border text-[11px] font-semibold flex items-center gap-1.5 ${
                      pipelineResult.scale4_macroComponentFEA.structuralVerdict.startsWith("WARNING")
                        ? "bg-amber-950/40 border-amber-500/30 text-amber-300"
                        : "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
                    }`}
                    title={pipelineResult.scale4_macroComponentFEA.structuralVerdictBasis}
                  >
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    {pipelineResult.scale4_macroComponentFEA.structuralVerdict}
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                  <div className="text-xs font-semibold text-slate-300">LEFM Flaw Inspection Tolerance</div>
                  <div className="space-y-1 text-xs font-mono">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Critical Flaw Size (a_c):</span>
                      <span className="text-sky-300 font-bold" title={pipelineResult.scale4_macroComponentFEA.lefmDamageTolerance.status}>{formatOptionalValue(pipelineResult.scale4_macroComponentFEA.lefmDamageTolerance.criticalFlawSize_ac_mm, "mm")}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Plastic Zone Radius (r_p):</span>
                      <span className="text-slate-200" title={pipelineResult.scale4_macroComponentFEA.lefmDamageTolerance.status}>{formatOptionalValue(pipelineResult.scale4_macroComponentFEA.lefmDamageTolerance.plasticZoneRadius_rp_mm, "mm")}</span>
                    </div>
                    <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-700">
                      NDI: {pipelineResult.scale4_macroComponentFEA.lefmDamageTolerance.inspectionNDICapability}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* CAE MATERIAL CARD EXPORTER */}
          {(activeScaleTab === "all" || activeScaleTab === "cae") && (
            <div className="p-5 rounded-2xl bg-slate-900/90 border border-purple-500/30 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-purple-300 flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-purple-400" />
                  Illustrative CAE Material Cards (Abaqus, ANSYS, LS-DYNA; uncalibrated)
                </h3>
                <span className="text-xs font-mono text-slate-400">Uncalibrated deck export, not for design use</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Abaqus */}
                <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2 flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-200">Abaqus Standard / Explicit</span>
                    <button
                      onClick={() => handleCopyCard("abaqus", pipelineResult.caeExportCards.abaqus)}
                      className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-[11px] text-slate-200 flex items-center gap-1 cursor-pointer"
                    >
                      {copiedCard === "abaqus" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      {copiedCard === "abaqus" ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <pre className="p-2.5 rounded-lg bg-slate-950 font-mono text-[10px] text-sky-300 overflow-x-auto max-h-48">
                    {pipelineResult.caeExportCards.abaqus}
                  </pre>
                </div>

                {/* LS-DYNA */}
                <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2 flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-200">LS-DYNA (*MAT_024)</span>
                    <button
                      onClick={() => handleCopyCard("lsDyna", pipelineResult.caeExportCards.lsDyna)}
                      className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-[11px] text-slate-200 flex items-center gap-1 cursor-pointer"
                    >
                      {copiedCard === "lsDyna" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      {copiedCard === "lsDyna" ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <pre className="p-2.5 rounded-lg bg-slate-950 font-mono text-[10px] text-amber-300 overflow-x-auto max-h-48">
                    {pipelineResult.caeExportCards.lsDyna}
                  </pre>
                </div>

                {/* ANSYS */}
                <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2 flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-200">ANSYS Workbench APDL</span>
                    <button
                      onClick={() => handleCopyCard("ansys", pipelineResult.caeExportCards.ansys)}
                      className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-[11px] text-slate-200 flex items-center gap-1 cursor-pointer"
                    >
                      {copiedCard === "ansys" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      {copiedCard === "ansys" ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <pre className="p-2.5 rounded-lg bg-slate-950 font-mono text-[10px] text-emerald-300 overflow-x-auto max-h-48">
                    {pipelineResult.caeExportCards.ansys}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
