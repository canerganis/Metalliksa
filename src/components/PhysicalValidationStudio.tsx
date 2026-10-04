import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useMemo } from "react";
import {
  ShieldCheck,
  Activity,
  Sliders,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  RefreshCw,
  Zap,
  TrendingDown,
  Layers,
  Sparkles,
  Info,
  Download,
  ArrowRight,
  ChevronRight,
  FileText,
  Copy,
  Check,
  RotateCcw,
} from "lucide-react";
import {
  ComposedChart,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  Scatter,
  AreaChart,
  Area,
} from "recharts";
import {
  ExperimentalEISDataset,
  PhysicalValidationSuite,
} from "../types/eisData";
import { usePythonAnalysis } from "../hooks/usePythonAnalysis";
import { EXPERIMENTAL_BENCHMARKS } from "../utils/eisFileParser";

interface PhysicalValidationStudioProps {
  initialDataset?: ExperimentalEISDataset | null;
  onApplyDeembeddedDataset?: (correctedDataset: ExperimentalEISDataset) => void;
  className?: string;
}

function decodeValidation(data: Record<string, unknown>): Partial<PhysicalValidationSuite> {
  if (!data.linKK && !data.inductance && !Array.isArray(data.cpeCapacitances)) {
    throw new Error("Python validation returned no usable reports.");
  }
  const report = data as Partial<PhysicalValidationSuite>;
  if (report.linKK && (!Array.isArray(report.linKK.residuals) || !report.linKK.residuals.length)) {
    throw new Error("Lin-KK screening unavailable: at least five valid impedance points are required.");
  }
  if (report.inductance && !Array.isArray(report.inductance.correctedPoints)) {
    throw new Error("Python validation returned an invalid de-embedding report.");
  }
  if (report.cpeCapacitances && !Array.isArray(report.cpeCapacitances)) {
    throw new Error("Python validation returned an invalid capacitance report.");
  }
  return report;
}

export const PhysicalValidationStudio: React.FC<PhysicalValidationStudioProps> = ({
  initialDataset,
  onApplyDeembeddedDataset,
  className = "",
}) => {
  // 1. Dataset selection
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>(
    initialDataset?.id || EXPERIMENTAL_BENCHMARKS[0].id
  );
  const [customDataset, setCustomDataset] = useState<ExperimentalEISDataset | null>(
    initialDataset || null
  );

  const activeDataset: ExperimentalEISDataset = useMemo(() => {
    if (customDataset && customDataset.id === selectedDatasetId) {
      return customDataset;
    }
    const found = EXPERIMENTAL_BENCHMARKS.find((b) => b.id === selectedDatasetId);
    return found || EXPERIMENTAL_BENCHMARKS[0];
  }, [selectedDatasetId, customDataset]);

  const [previousInitialDataset, setPreviousInitialDataset] = useState(initialDataset);
  if (previousInitialDataset !== initialDataset) {
    setPreviousInitialDataset(initialDataset);
    setCustomDataset(initialDataset ?? null);
    setSelectedDatasetId(initialDataset?.id ?? EXPERIMENTAL_BENCHMARKS[0].id);
  }

  // Active validation sub-tab
  const [activeTab, setActiveTab] = useState<"cpe-converter" | "lin-kk" | "inductance-deembed" | "astm-report">(
    "cpe-converter"
  );

  // Electrode parameters
  const [electrodeAreaCm2, setElectrodeAreaCm2] = useState<number>(1.0);

  // Interactive CPE Sandbox Parameters
  const [cpeQ, setCpeQ] = useState<number>(2.5e-5); // S*s^n
  const [cpeN, setCpeN] = useState<number>(0.88);
  const [resRs, setResRs] = useState<number>(12.5); // Ohm
  const [resRct, setResRct] = useState<number>(340.0); // Ohm
  const [cpeModelType, setCpeModelType] = useState<"brug" | "hirschorn" | "hsu">("brug");

  const payload = {
        action: "validate_dataset",
        points: activeDataset.points.map((p) => ({
          frequency: p.frequency,
          zReal: p.zReal,
          minusZImag: p.minusZImag,
          zImag: p.zImag,
          zMag: p.zMag,
        })),
        electrodeAreaCm2: electrodeAreaCm2,
        parameters: [
          { paramName: "Rs", elementId: "R1", paramType: "R", field: "value", value: resRs },
          { paramName: "Rct", elementId: "R2", paramType: "R", field: "value", value: resRct },
          { paramName: "Q_dl", elementId: "CPE1", paramType: "CPE", field: "value", value: cpeQ },
          { paramName: "n_dl", elementId: "CPE1", paramType: "CPE", field: "exponent", value: cpeN },
        ],
        topology: {
          branches: [
            { connection: "series", elements: [{ id: "R1", name: "Rs", type: "R", value: resRs }] },
            {
              connection: "parallel",
              elements: [
                { id: "CPE1", name: "Q_dl", type: "CPE", value: cpeQ, exponent: cpeN },
                { id: "R2", name: "Rct", type: "R", value: resRct },
              ],
            },
          ],
        },
      };
  const validation = usePythonAnalysis("/api/python/cnls-fit", payload, decodeValidation, { debounceMs: 250 });
  const isComputing = validation.pending;
  const pythonLatencyMs = validation.elapsedMs;
  const linKKReport = validation.result?.linKK ?? null;
  const inductanceReport = validation.result?.inductance ?? null;
  const cpeList = validation.result?.cpeCapacitances ?? [];
  const executePythonValidation = validation.retry;
  const [copiedNotification, setCopiedNotification] = useState(false);

  // Dynamic calculated sandbox values
  const currentCpe = useMemo(() => {
    if (cpeList.length > 0) return cpeList[0];
    return null;
  }, [cpeList]);

  // Handle applying de-embedded points
  const handleApplyDeembedding = () => {
    if (!inductanceReport || !inductanceReport.correctedPoints) return;
    const correctedDs: ExperimentalEISDataset = {
      ...activeDataset,
      id: `${activeDataset.id}-deembedded`,
      name: `${activeDataset.name} (De-embedded L_cable = ${inductanceReport.detectedInductance_uH} µH)`,
      points: inductanceReport.correctedPoints,
    };
    if (onApplyDeembeddedDataset) {
      onApplyDeembeddedDataset(correctedDs);
    }
  };

  // Copy ASTM report to clipboard
  const handleCopyReport = () => {
    if (!validation.result) return;
    const text = `METALLIX ADVANCED EIS PHYSICAL VALIDATION & QUALITY REPORT
SCREENING ONLY — standards compliance not evaluated
Dataset: ${activeDataset.name}
Data origin: ${activeDataset.source === "benchmark" ? "Synthetic circuit example, not an experiment" : "User upload; provenance unverified"}
Electrode Geometric Area: ${electrodeAreaCm2} cm²
Python Engine: CPython 3.10+ (Lin-KK Generalized Voigt Model)

1. CONSTANT PHASE ELEMENT (CPE) TO EFFECTIVE CAPACITANCE CONVERSION
- Parameter Q: ${cpeQ.toExponential(3)} S·s^n
- Exponent n: ${cpeN}
- Brug Effective Capacitance C_eff (2D Surface Roughness): ${currentCpe?.cBrug_uF ?? "Unavailable"} µF
- Specific Double-Layer Capacitance: ${currentCpe?.cEffectiveArea_uFcm2 ?? "Unavailable"} µF/cm²
- Hirschorn Effective Capacitance (3D Porous/Film): ${currentCpe?.cHirschorn_uF ?? "Unavailable"} µF
- Hsu-Mansfeld Effective Capacitance (Apex f0): ${currentCpe?.cHsuMansfeld_uF ?? "Unavailable"} µF
- Effective Time Constant (tau = Rct * C_eff): ${currentCpe?.tauEffectiveMs ?? "Unavailable"} ms

2. LINEAR KRAMERS-KRONIG (LIN-KK) STATIONARITY & DRIFT TEST
- Stationarity Status: ${linKKReport?.stationarityStatus ?? "Unavailable"}
- Drift Score: ${linKKReport?.driftScore ?? "Unavailable"} / 100
- Mean Lin-KK Residual: ${linKKReport?.meanResidualPct ?? "Unavailable"}%
- Pseudo-Chi-Square (χ²_KK): ${linKKReport?.pseudoChiSquare ?? "Unavailable"}
- Low-Frequency Drift Metric (mu_drift): ${linKKReport?.muDriftMetric ?? "Unavailable"}
- Diagnosis: ${linKKReport?.recommendation ?? "Unavailable"}

3. HIGH-FREQUENCY LEAD INDUCTANCE DE-EMBEDDING
- Parasitic Inductance Detected: ${!inductanceReport ? "Unavailable" : inductanceReport.hasHighFreqInduction ? "YES" : "NO"}
- Extracted L_cable: ${inductanceReport?.detectedInductance_uH ?? "Unavailable"} µH
- Zero-Crossing Frequency: ${inductanceReport?.zeroCrossingFreq_Hz ?? "Unavailable"} Hz
- Cable Artifact at 100 kHz: ${inductanceReport?.cableArtifactMagnitude_Ohm ?? "Unavailable"} Ω
`;
    navigator.clipboard.writeText(text);
    setCopiedNotification(true);
    setTimeout(() => setCopiedNotification(false), 2500);
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* 1. Header Banner & Engine Ribbon */}
      <div className="bg-gradient-to-br from-[#0c1424] via-[#09101c] to-[#060b13] border border-sky-500/20 rounded-2xl p-5 lg:p-6 shadow-2xl">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-500/20 to-emerald-500/20 border border-sky-400/40 flex items-center justify-center text-sky-300 shadow-[0_0_12px_rgba(56,189,248,0.25)]">
              <ShieldCheck className="w-5 h-5 text-sky-400" />
            </div>
            <div>
              <h2 className="text-base lg:text-lg font-bold text-white font-mono flex items-center gap-2">
                EIS Physical Validation &amp; Lin-KK Studio
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-400/30">
                  CPython 3.10+ High-Performance Solver
                </span>
              </h2>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Brug/Hirschorn C_eff Conversions • Lin-KK Stationarity &amp; Drift Testing • Cable Inductance De-embedding
              </p>
            </div>
          </div>

          {/* Engine Status & Latency */}
          <div className="flex items-center gap-2 self-stretch sm:self-auto bg-[#050810] border border-[#1e2d46] rounded-xl px-3 py-1.5">
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-[11px] font-bold text-slate-300 font-mono">{isComputing ? "Python analysis pending" : validation.result ? "Python analysis received" : "Python analysis unavailable"}</span>
            </div>
            {pythonLatencyMs !== null && (
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                {pythonLatencyMs} ms
              </span>
            )}
            <button
              type="button"
              onClick={executePythonValidation}
              disabled={isComputing}
              className="p-1 text-slate-400 hover:text-sky-300 transition-colors"
              title="Re-run Python validation"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isComputing ? "animate-spin text-sky-400" : ""}`} />
            </button>
          </div>
        </div>

        {/* Dataset & Area Selector Ribbon */}
        <div className="mt-4 pt-4 border-t border-[#162032] flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-mono">Example / Uploaded Dataset:</span>
              <select
                aria-label="Validation dataset"
                value={selectedDatasetId}
                onChange={(e) => setSelectedDatasetId(e.target.value)}
                className="bg-[#050810] border border-[#1e2d46] text-white text-xs font-mono rounded-lg px-2.5 py-1.5 focus:border-sky-400 focus:outline-none"
              >
                {EXPERIMENTAL_BENCHMARKS.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} ({b.points.length} pts)
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-mono">Electrode Area (A):</span>
              <div className="flex items-center gap-1 bg-[#050810] border border-[#1e2d46] rounded-lg px-2 py-1">
                <input
                  type="number"
                  min="0.01"
                  max="100"
                  step="0.1"
                  aria-label="Electrode area" value={electrodeAreaCm2}
                  onChange={(e) => setElectrodeAreaCm2(parseFloat(e.target.value) || 1.0)}
                  className="w-14 bg-transparent text-white text-xs font-mono text-center focus:outline-none"
                />
                <span className="text-[10px] text-slate-500 font-mono">cm²</span>
              </div>
            </div>
          </div>

          {/* Quick Metrics Badges */}
          <div className="flex items-center gap-2">
            <div className="px-2.5 py-1 rounded-lg bg-[#050810] border border-[#1e2d46] text-[11px] font-mono flex items-center gap-1.5">
              <span className="text-slate-400">Lin-KK Score:</span>
              <span className="font-bold text-emerald-400">
                {linKKReport?.driftScore ?? "Unavailable"}%
              </span>
            </div>
            <div className="px-2.5 py-1 rounded-lg bg-[#050810] border border-[#1e2d46] text-[11px] font-mono flex items-center gap-1.5">
              <span className="text-slate-400">Lead Inductance $L_0$:</span>
              <span className="font-bold text-sky-400">
                {inductanceReport?.detectedInductance_uH ?? "Unavailable"} µH
              </span>
            </div>
          </div>
        </div>
      </div>

      <p role="status" className="text-xs text-slate-400 font-mono">
        {isComputing ? "Calculating current inputs…" : validation.result ? "Screening only; numerical residuals do not establish stationarity, causality or ASTM/ISO compliance." : "Unavailable: no validation report for the current inputs."}
      </p>
      {validation.error && <div role="alert" className="p-4 border border-rose-500 text-rose-300 rounded-xl">{validation.error}</div>}
      <p className="text-xs text-amber-300">{activeDataset.source === "benchmark" ? "Synthetic circuit example — not measured laboratory data." : "User upload — measurement provenance has not been verified."}</p>
      {/* 2. Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-[#162032] pb-2 overflow-x-auto">
        {[
          {
            id: "cpe-converter",
            label: "1. CPE → C_eff Converter (Brug / Hirschorn / Hsu)",
            icon: Cpu,
            badge: "2D / 3D Roughness",
          },
          {
            id: "lin-kk",
            label: "2. Lin-KK Stationarity & Drift Test",
            icon: Activity,
            badge: "ASTM G106",
          },
          {
            id: "inductance-deembed",
            label: "3. Cable Inductance De-embedding",
            icon: Zap,
            badge: "High-f Correction",
          },
          {
            id: "astm-report",
            label: "4. Physical Screening Report",
            icon: FileText,
            badge: "Audit Export",
          },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-mono font-bold transition-all whitespace-nowrap ${
                isActive
                  ? "bg-sky-500/20 text-sky-300 border border-sky-400/50 shadow-[0_0_12px_rgba(56,189,248,0.25)]"
                  : "bg-[#090e18] border border-[#162032] text-slate-400 hover:text-slate-200"
              }`}
            >
              <Icon className="w-3.5 h-3.5 text-sky-400" />
              <span>{tab.label}</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-[#050810] text-slate-400 border border-[#1e2d46]">
                {tab.badge}
              </span>
            </button>
          );
        })}
      </div>

      {/* =========================================================================
          TAB 1: CPE TO EFFECTIVE CAPACITANCE CONVERTER (BRUG / HIRSCHORN / HSU)
         ========================================================================= */}
      {activeTab === "cpe-converter" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Interactive Controls & Physics Parameter Inputs */}
          <div className="lg:col-span-5 space-y-4">
            <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                <div className="flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-sky-400" />
                  <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                    CPE &amp; Cell Parameter Tuner
                  </span>
                </div>
                <span className="text-[10px] font-mono text-slate-400">Live Physics Sandbox</span>
              </div>

              {/* Parameter 1: CPE Q */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300">CPE Constant (Q / Y₀):</span>
                  <span className="text-sky-400 font-bold">{cpeQ.toExponential(3)} S·sⁿ</span>
                </div>
                <input
                  type="range"
                  min="1e-7"
                  max="1e-3"
                  step="1e-7"
                  aria-label="CPE constant Q" value={cpeQ}
                  onChange={(e) => setCpeQ(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-[#050810] rounded-lg appearance-none cursor-pointer accent-sky-400"
                />
                <div className="flex justify-between text-[9px] font-mono text-slate-500">
                  <span>10⁻⁷ S·sⁿ</span>
                  <span>10⁻⁵</span>
                  <span>10⁻³ S·sⁿ</span>
                </div>
              </div>

              {/* Parameter 2: CPE Exponent n */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300">CPE Exponent (n):</span>
                  <span className="text-purple-400 font-bold">{cpeN.toFixed(3)}</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.005"
                  aria-label="CPE exponent n" value={cpeN}
                  onChange={(e) => setCpeN(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-[#050810] rounded-lg appearance-none cursor-pointer accent-purple-400"
                />
                <div className="flex justify-between text-[9px] font-mono text-slate-500">
                  <span>n=0.5 (Warburg Diffusion)</span>
                  <span>n=0.85 (Rough DL)</span>
                  <span>n=1.0 (Ideal Cap)</span>
                </div>
              </div>

              {/* Parameter 3: Solution Resistance Rs */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300">Ohmic Solution Resistance (Rs):</span>
                  <span className="text-emerald-400 font-bold">{resRs.toFixed(2)} Ω</span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="200"
                  step="0.5"
                  aria-label="Solution resistance Rs" value={resRs}
                  onChange={(e) => setResRs(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-[#050810] rounded-lg appearance-none cursor-pointer accent-emerald-400"
                />
              </div>

              {/* Parameter 4: Polarization / Charge Transfer Rct */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300">Charge Transfer / Film (Rct):</span>
                  <span className="text-amber-400 font-bold">{resRct.toFixed(1)} Ω</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="5000"
                  step="5"
                  aria-label="Charge transfer resistance Rct" value={resRct}
                  onChange={(e) => setResRct(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-[#050810] rounded-lg appearance-none cursor-pointer accent-amber-400"
                />
              </div>

              {/* Formula Selection Tabs */}
              <div className="pt-2 border-t border-[#162032] space-y-2">
                <span className="text-[11px] font-bold text-slate-400 font-mono">Active Conversion Formula:</span>
                <div className="grid grid-cols-3 gap-1.5 bg-[#050810] p-1 rounded-xl border border-[#1e2d46]">
                  {[
                    { id: "brug", label: "Brug (2D)", desc: "2D Surface Roughness" },
                    { id: "hirschorn", label: "Hirschorn (3D)", desc: "3D Porous / Coating" },
                    { id: "hsu", label: "Hsu-Mansfeld", desc: "Apex Peak Frequency" },
                  ].map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => setCpeModelType(f.id as any)}
                      className={`p-1.5 rounded-lg text-center transition-all ${
                        cpeModelType === f.id
                          ? "bg-sky-500/20 text-sky-300 font-bold border border-sky-400/40"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <div className="text-xs font-mono">{f.label}</div>
                      <div className="text-[9px] text-slate-500">{f.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Educational Info Card */}
            <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-4 text-xs font-mono text-slate-300 space-y-2">
              <div className="flex items-center gap-2 text-sky-400 font-bold">
                <Info className="w-4 h-4" />
                <span>Why is Q not equal to Capacitance?</span>
              </div>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                A Constant Phase Element has units of S·sⁿ (or Ω⁻¹·sⁿ). When n &lt; 1.0, it is physically meaningless to treat Q directly as Farads. The Brug and Hirschorn formulas decouple 2D geometric roughness and 3D normal resistivity distributions to recover true Farads.
              </p>
            </div>
          </div>

          {/* Right Column: True Calculated Effective Capacitances & Physical Interpretation */}
          <div className="lg:col-span-7 space-y-4">
            {/* 1. Main Capacitance Outcome Card */}
            <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-5">
              <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                    Calculated Physical Quantities
                  </span>
                </div>
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  Area Normalized: {electrodeAreaCm2} cm²
                </span>
              </div>

              {/* 3 Formula Comparison Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* Brug */}
                <div
                  className={`p-3.5 rounded-xl border transition-all ${
                    cpeModelType === "brug"
                      ? "bg-sky-500/10 border-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.2)]"
                      : "bg-[#050810] border-[#162032]"
                  }`}
                >
                  <div className="text-[10px] text-slate-400 font-mono uppercase tracking-wider">Brug Model (2D)</div>
                  <div className="text-lg font-bold text-sky-300 font-mono mt-1">
                    {currentCpe?.cBrug_uF ?? "Unavailable"} <span className="text-xs">µF</span>
                  </div>
                  <div className="text-xs text-sky-400 font-mono mt-0.5">
                    {currentCpe?.cEffectiveArea_uFcm2 ?? "Unavailable"} µF/cm²
                  </div>
                  <div className="text-[9px] text-slate-500 font-mono mt-2 pt-2 border-t border-[#162032]">
                    C_eff = Q^(1/n) · [Rs·Rct / (Rs + Rct)]^((1-n)/n)
                  </div>
                </div>

                {/* Hirschorn */}
                <div
                  className={`p-3.5 rounded-xl border transition-all ${
                    cpeModelType === "hirschorn"
                      ? "bg-purple-500/10 border-purple-400 shadow-[0_0_12px_rgba(168,85,247,0.2)]"
                      : "bg-[#050810] border-[#162032]"
                  }`}
                >
                  <div className="text-[10px] text-slate-400 font-mono uppercase tracking-wider">Hirschorn (3D)</div>
                  <div className="text-lg font-bold text-purple-300 font-mono mt-1">
                    {currentCpe?.cHirschorn_uF ?? "Unavailable"} <span className="text-xs">µF</span>
                  </div>
                  <div className="text-xs text-purple-400 font-mono mt-0.5">
                    {currentCpe?.cHirschorn_uF != null ? (currentCpe.cHirschorn_uF / electrodeAreaCm2).toFixed(3) : "Unavailable"} µF/cm²
                  </div>
                  <div className="text-[9px] text-slate-500 font-mono mt-2 pt-2 border-t border-[#162032]">
                    C_eff = Q^(1/n) · Rf^((1-n)/n)
                  </div>
                </div>

                {/* Hsu-Mansfeld */}
                <div
                  className={`p-3.5 rounded-xl border transition-all ${
                    cpeModelType === "hsu"
                      ? "bg-amber-500/10 border-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.2)]"
                      : "bg-[#050810] border-[#162032]"
                  }`}
                >
                  <div className="text-[10px] text-slate-400 font-mono uppercase tracking-wider">Hsu-Mansfeld (Apex)</div>
                  <div className="text-lg font-bold text-amber-300 font-mono mt-1">
                    {currentCpe?.cHsuMansfeld_uF ?? "Unavailable"} <span className="text-xs">µF</span>
                  </div>
                  <div className="text-xs text-amber-400 font-mono mt-0.5">
                    {currentCpe?.cHsuMansfeld_uF != null ? (currentCpe.cHsuMansfeld_uF / electrodeAreaCm2).toFixed(3) : "Unavailable"} µF/cm²
                  </div>
                  <div className="text-[9px] text-slate-500 font-mono mt-2 pt-2 border-t border-[#162032]">
                    C_eff = Q · (ω_max)^(n-1)
                  </div>
                </div>
              </div>

              {/* Physical Interpretation Box */}
              <div className="p-4 rounded-xl bg-[#050810] border border-[#162032] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-300 font-mono">Physical Material Classification:</span>
                  <span className="text-xs font-bold text-sky-400 font-mono">
                    τ_eff = {currentCpe?.tauEffectiveMs ?? "Unavailable"} ms
                  </span>
                </div>
                <p className="text-xs text-slate-400 font-mono leading-relaxed">
                  {currentCpe?.physicsNote ?? "Unavailable"}
                </p>
              </div>

              {/* Reference Benchmarks for Electrochemistry Engineers */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-300 font-mono">Standard Specific Capacitance Ranges:</span>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] font-mono">
                  <div className="p-2 rounded bg-[#050810] border border-[#162032]">
                    <div className="text-sky-400 font-bold">Passive Barrier Film</div>
                    <div className="text-slate-400">1 - 5 µF/cm²</div>
                    <div className="text-[10px] text-slate-500">TiO₂, Al₂O₃, Paints</div>
                  </div>
                  <div className="p-2 rounded bg-[#050810] border border-[#162032]">
                    <div className="text-emerald-400 font-bold">Ideal Double Layer</div>
                    <div className="text-slate-400">10 - 40 µF/cm²</div>
                    <div className="text-[10px] text-slate-500">Smooth metal / Hg pool</div>
                  </div>
                  <div className="p-2 rounded bg-[#050810] border border-[#162032]">
                    <div className="text-purple-400 font-bold">Porous Supercapacitor</div>
                    <div className="text-slate-400">&gt; 100 µF/cm²</div>
                    <div className="text-[10px] text-slate-500">Activated carbon / 3D foam</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 2: LIN-KK STATIONARITY & DRIFT TEST
         ========================================================================= */}
      {activeTab === "lin-kk" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Metrics Column */}
            <div className="lg:col-span-4 space-y-4">
              <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-sky-400" />
                    <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                      Lin-KK Test Assessment
                    </span>
                  </div>
                </div>

                {/* Score Gauge */}
                <div className="text-center p-4 rounded-xl bg-[#050810] border border-[#162032]">
                  <div className="text-[11px] text-slate-400 font-mono">Lin-KK Screening Score</div>
                  <div
                    className={`text-3xl font-bold font-mono mt-1 ${
                      (linKKReport?.driftScore ?? -1) >= 85
                        ? "text-emerald-400"
                        : (linKKReport?.driftScore ?? -1) >= 70
                        ? "text-amber-400"
                        : "text-rose-400"
                    }`}
                  >
                    {linKKReport?.driftScore ?? "Unavailable"}%
                  </div>
                  <div className="text-xs text-slate-300 font-mono mt-1 font-semibold">
                    {linKKReport?.stationarityStatus ?? "Unavailable"}
                  </div>
                </div>

                {/* Statistics Grid */}
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="p-2.5 rounded-lg bg-[#050810] border border-[#162032]">
                    <div className="text-[10px] text-slate-500">Pseudo-χ² (Lin-KK)</div>
                    <div className="text-sky-400 font-bold">{linKKReport?.pseudoChiSquare ?? "Unavailable"}</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#050810] border border-[#162032]">
                    <div className="text-[10px] text-slate-500">Mean Residual</div>
                    <div className="text-emerald-400 font-bold">{linKKReport?.meanResidualPct ?? "Unavailable"}%</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#050810] border border-[#162032]">
                    <div className="text-[10px] text-slate-500">Low-f Drift (μ_drift)</div>
                    <div className="text-purple-400 font-bold">{linKKReport?.muDriftMetric ?? "Unavailable"}</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#050810] border border-[#162032]">
                    <div className="text-[10px] text-slate-500">Voigt Elements M</div>
                    <div className="text-amber-400 font-bold">Unavailable (not reported)</div>
                  </div>
                </div>

                {/* Recommendation Box */}
                <div className="p-3.5 rounded-xl bg-[#050810] border border-[#162032] space-y-1 text-xs font-mono">
                  <div className="flex items-center gap-1.5 text-sky-400 font-bold">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Solver Screening Assessment:</span>
                  </div>
                  <p className="text-slate-400 text-[11px] leading-relaxed">
                    {linKKReport?.recommendation ?? "Unavailable: no current screening result."}
                  </p>
                </div>
              </div>
            </div>

            {/* Right Chart Column: Lin-KK Relative Residuals */}
            <div className="lg:col-span-8 space-y-4">
              <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                      Lin-KK Generalized Voigt Residuals vs. Frequency
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono">
                    Tolerance Envelope: $\pm 2\%$
                  </div>
                </div>

                {/* Residual Chart */}
                <div className="h-80 w-full bg-[#050810] rounded-xl border border-[#162032] p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={linKKReport?.residuals || []}
                      margin={{ top: 10, right: 20, left: 10, bottom: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#162032" />
                      <XAxis
                        dataKey="logFreq"
                        name="log10(f)"
                        stroke="#64748b"
                        tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                        label={{
                          value: "log₁₀(Frequency / Hz)",
                          position: "insideBottom",
                          offset: -5,
                          fill: "#94a3b8",
                          fontSize: 10,
                        }}
                      />
                      <YAxis
                        stroke="#64748b"
                        domain={[-5, 5]}
                        tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                        label={{
                          value: "Relative Lin-KK Residual (%)",
                          angle: -90,
                          position: "insideLeft",
                          fill: "#94a3b8",
                          fontSize: 10,
                        }}
                      />
                      <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />
                      <ReferenceLine y={2} stroke="#f59e0b" strokeDasharray="3 3" />
                      <ReferenceLine y={-2} stroke="#f59e0b" strokeDasharray="3 3" />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#090e18",
                          borderColor: "#1e2d46",
                          fontSize: 11,
                          fontFamily: "monospace",
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11, fontFamily: "monospace", paddingTop: 8 }} />
                      <Line
                        type="monotone"
                        dataKey="zRealResPct"
                        name="Real Residual ΔZ'/|Z| %"
                        stroke="#38bdf8"
                        strokeWidth={1.8}
                        dot={{ r: 2 }}
                      />
                      <Line
                        type="monotone"
                        dataKey="zImagResPct"
                        name="Imag Residual ΔZ''/|Z| %"
                        stroke="#f43f5e"
                        strokeWidth={1.8}
                        dot={{ r: 2 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Explanation of Drift */}
                <div className="p-3 rounded-xl bg-[#050810] border border-[#162032] flex items-start gap-2 text-xs font-mono text-slate-400">
                  <Info className="w-4 h-4 text-sky-400 flex-shrink-0 mt-0.5" />
                  <span>
                    <strong>Stationarity Test Interpretation:</strong> A random scatter of points around 0% confirms time-invariance. If low-frequency points (f &lt; 0.1 Hz) bend systematically away from 0%, the sample experienced active OCP drift or corrosion dissolution during the measurement.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 3: HIGH-FREQUENCY CABLE INDUCTANCE DE-EMBEDDING
         ========================================================================= */}
      {activeTab === "inductance-deembed" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Inductance Extraction Readout */}
            <div className="lg:col-span-5 space-y-4">
              <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-amber-400" />
                    <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                      High-Frequency Cable Inductance (L₀)
                    </span>
                  </div>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                      inductanceReport?.hasHighFreqInduction
                        ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                        : "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                    }`}
                  >
                    {!inductanceReport ? "Unavailable" : inductanceReport.hasHighFreqInduction ? "Inductive Loop Present" : "No inductive loop detected"}
                  </span>
                </div>

                {/* Inductance Stat Cards */}
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="p-3 rounded-xl bg-[#050810] border border-[#1e2d46]">
                    <div className="text-[10px] text-slate-500">Extracted L_cable</div>
                    <div className="text-xl font-bold text-sky-400 mt-0.5">
                      {inductanceReport?.detectedInductance_uH ?? "Unavailable"} µH
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-[#050810] border border-[#1e2d46]">
                    <div className="text-[10px] text-slate-500">Zero-Crossing f₀</div>
                    <div className="text-xl font-bold text-amber-400 mt-0.5">
                      {inductanceReport?.zeroCrossingFreq_Hz
                        ? `${inductanceReport.zeroCrossingFreq_Hz} Hz`
                        : "Not reported"}
                    </div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-[#050810] border border-[#162032] space-y-2 text-xs font-mono">
                  <div className="text-slate-300 font-bold">Cable Artifact Impact:</div>
                  <p className="text-slate-400 text-[11px] leading-relaxed">
                    At 100 kHz, lead inductance creates an imaginary impedance distortion of{" "}
                    <strong className="text-sky-300">{inductanceReport?.cableArtifactMagnitude_Ohm ?? "Unavailable"} Ω</strong>.
                    De-embedding subtracts +jωL₀ to prevent artificial electrolyte resistance (Rs) overestimation in CNLS fits.
                  </p>
                </div>

                {/* 1-Click Action to Apply De-embedded Spectrum */}
                <button
                  type="button"
                  onClick={handleApplyDeembedding}
                  disabled={!inductanceReport?.correctedPoints?.length}
                  className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-sky-500/20 to-blue-600/20 hover:from-sky-500/30 hover:to-blue-600/30 border border-sky-400/50 text-sky-200 text-xs font-mono font-bold flex items-center justify-center gap-2 shadow-[0_0_12px_rgba(56,189,248,0.2)] transition-all"
                >
                  <Sparkles className="w-4 h-4 text-sky-400" />
                  <span>Apply De-embedded Spectrum to Dataset</span>
                </button>
              </div>
            </div>

            {/* Right Column: Nyquist Raw vs De-embedded Overlay */}
            <div className="lg:col-span-7 space-y-4">
              <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-sky-400" />
                    <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                      Nyquist Spectrum: Raw vs. De-embedded Overlay
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-400">-Z'' vs Z'</span>
                </div>

                {/* Overlay Chart */}
                <div className="h-80 w-full bg-[#050810] rounded-xl border border-[#162032] p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={activeDataset.points.map((p, idx) => ({
                        rawZReal: p.zReal,
                        rawMinusZImag: p.minusZImag,
                        corrMinusZImag: inductanceReport?.correctedPoints?.[idx]?.minusZImag ?? null,
                        freq: p.frequency,
                      }))}
                      margin={{ top: 10, right: 20, left: 10, bottom: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#162032" />
                      <XAxis
                        dataKey="rawZReal"
                        name="Z' (Ω)"
                        stroke="#64748b"
                        tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                        label={{
                          value: "Z' / Real Impedance (Ω)",
                          position: "insideBottom",
                          offset: -5,
                          fill: "#94a3b8",
                          fontSize: 10,
                        }}
                      />
                      <YAxis
                        dataKey="rawMinusZImag"
                        name="-Z'' (Ω)"
                        stroke="#64748b"
                        tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                        label={{
                          value: "-Z'' / Imaginary (Ω)",
                          angle: -90,
                          position: "insideLeft",
                          fill: "#94a3b8",
                          fontSize: 10,
                        }}
                      />
                      <ReferenceLine y={0} stroke="#475569" />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#090e18",
                          borderColor: "#1e2d46",
                          fontSize: 11,
                          fontFamily: "monospace",
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11, fontFamily: "monospace", paddingTop: 8 }} />
                      <Scatter
                        dataKey="rawMinusZImag"
                        name="Input Spectrum (with Cable L0)"
                        fill="#f43f5e"
                        shape="circle"
                      />
                      <Line
                        type="monotone"
                        dataKey="corrMinusZImag"
                        name="De-embedded Spectrum (Corrected)"
                        stroke="#10b981"
                        strokeWidth={2.5}
                        dot={false}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 4: SCREENING ONLY — standards compliance not evaluated REPORT GENERATOR
         ========================================================================= */}
      {activeTab === "astm-report" && (
        <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#162032] pb-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center text-emerald-300">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white font-mono">
                  EIS Physical Screening Report
                </h3>
                <p className="text-xs text-slate-400 font-mono">
                  Computed metrics and de-embedding summary; no certification claim
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={handleCopyReport}
              disabled={!validation.result}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#050810] border border-[#1e2d46] text-xs font-mono font-bold text-sky-300 hover:border-sky-400 transition-all"
            >
              {copiedNotification ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              <span>{copiedNotification ? "Copied to Clipboard!" : "Copy Report"}</span>
            </button>
          </div>

          {/* Formatted Text Box */}
          <div className="p-4 bg-[#050810] border border-[#162032] rounded-xl font-mono text-xs text-slate-300 space-y-4 overflow-x-auto leading-relaxed">
            <div>
              <div className="text-sky-400 font-bold border-b border-[#162032] pb-1">
                EIS PHYSICAL SCREENING REPORT
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Generated: {new Date().toISOString()} | Target Dataset: {activeDataset.name}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div className="space-y-1">
                <div className="text-slate-200 font-bold">1. CPE Effective Capacitance (C_eff)</div>
                <div>• Brug 2D Surface Model: <span className="text-sky-300">{currentCpe?.cBrug_uF ?? "Unavailable"} µF</span></div>
                <div>• Specific Double-Layer Capacitance: <span className="text-emerald-300">{currentCpe?.cEffectiveArea_uFcm2 ?? "Unavailable"} µF/cm²</span></div>
                <div>• Hirschorn 3D Porous/Film Model: <span className="text-purple-300">{currentCpe?.cHirschorn_uF ?? "Unavailable"} µF</span></div>
                <div>• Characteristic Time Constant (τ): <span className="text-amber-300">{currentCpe?.tauEffectiveMs ?? "Unavailable"} ms</span></div>
              </div>

              <div className="space-y-1">
                <div className="text-slate-200 font-bold">2. Kramers-Kronig (Lin-KK) Stationarity</div>
                <div>• Overall Score: <span className="text-emerald-300 font-bold">{linKKReport?.driftScore ?? "Unavailable"} / 100</span></div>
                <div>• Status: <span className="text-sky-300">{linKKReport?.stationarityStatus ?? "Unavailable"}</span></div>
                <div>• Mean Residual: <span className="text-slate-300">{linKKReport?.meanResidualPct ?? "Unavailable"}%</span></div>
                <div>• Low-Frequency Drift Metric (μ_drift): <span className="text-slate-300">{linKKReport?.muDriftMetric ?? "Unavailable"}</span></div>
              </div>
            </div>

            <div className="pt-2 border-t border-[#162032] space-y-1">
              <div className="text-slate-200 font-bold">3. Parasitic Lead Inductance &amp; High-Frequency Phase Shift</div>
              <div>• Extracted Cell/Lead Inductance (L₀): <span className="text-sky-300">{inductanceReport?.detectedInductance_uH ?? "Unavailable"} µH</span></div>
              <div>• Zero-Crossing Frequency (f₀): <span className="text-amber-300">{inductanceReport?.zeroCrossingFreq_Hz ?? "Unavailable"} Hz</span></div>
              <div>• Compliance Status: <span className="text-emerald-400 font-bold">NOT EVALUATED — screening only</span></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
