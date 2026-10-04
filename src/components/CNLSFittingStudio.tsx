import { AccessibleModal } from "./AccessibleModal";
import { useInputBoundTask } from "../hooks/useInputBoundTask";
import { requestPythonAnalysis } from "../services/pythonAnalysis";
import { normalizePythonCnlsReport } from "../utils/pythonCnlsReport";
import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useMemo, useRef, useEffect } from "react";
import {
  Activity,
  Upload,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Sliders,
  Download,
  Copy,
  Check,
  Sparkles,
  Lock,
  Unlock,
  Layers,
  ArrowRight,
  ShieldCheck,
  Battery,
  Flame,
  Info,
  HelpCircle,
  BarChart2,
  ChevronRight,
  TrendingDown,
  RefreshCw,
  Zap,
  RadioTower,
  Scale,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ScatterChart,
  Scatter,
  ComposedChart,
} from "recharts";
import {
  CircuitTopology,
  CircuitElement,
  STANDARD_CIRCUIT_PRESETS,
} from "./EquivalentCircuitBuilder";
import { EXTENDED_CIRCUIT_LIBRARY } from "../data/circuitModelLibrary";
import { PlotlyEISViewer } from "./PlotlyEISViewer";
import { PhysicalValidationStudio } from "./PhysicalValidationStudio";
import { SyntheticNoiseStressStudio } from "./SyntheticNoiseStressStudio";
import {
  ExperimentalEISDataset,
  CNLSFitReport,
  WeightingMethod,
  ParameterFitResult,
} from "../types/eisData";
import {
  parseEISFile,
  EXPERIMENTAL_BENCHMARKS,
} from "../utils/eisFileParser";
import {
  extractAdjustableParameters,
  applyParametersToTopology,
} from "../utils/cnlsOptimizer";

interface CNLSFittingStudioProps {
  currentTopology: CircuitTopology;
  onApplyTopology: (topology: CircuitTopology) => void;
  onClose?: () => void;
}

export function CNLSFittingStudio(props: CNLSFittingStudioProps) {
  return <CNLSFittingSession key={JSON.stringify(props.currentTopology)} {...props} />;
}

function CNLSFittingSession({
  currentTopology,
  onApplyTopology,
  onClose,
}: CNLSFittingStudioProps) {
  // Active experimental dataset
  const [activeDataset, setActiveDataset] = useState<ExperimentalEISDataset>(
    EXPERIMENTAL_BENCHMARKS[0]
  );

  // Selected topology for fitting (defaults to active topology from builder or matching preset)
  const [selectedTopology, setSelectedTopology] = useState<CircuitTopology>(() => {
    // If current topology is custom, use it, else pick the first preset
    return currentTopology || STANDARD_CIRCUIT_PRESETS[0];
  });

  // Extract initial parameters
  const [editableParams, setEditableParams] = useState(() =>
    extractAdjustableParameters(selectedTopology)
  );

  // Optimizer Settings
  const [weighting, setWeighting] = useState<WeightingMethod>("modulus");
  const [maxIterations, setMaxIterations] = useState<number>(80);
  const [executionEngine, setExecutionEngine] = useState<"python_hpc" | "client_js">("python_hpc");
  const fitTask = useInputBoundTask<{ report: CNLSFitReport; drt: any }>(
    JSON.stringify([selectedTopology, activeDataset, editableParams, weighting, maxIterations, executionEngine]));
  const fitReport = fitTask.data?.report ?? null;
  const drtResult = fitTask.data?.drt ?? null;
  const fitError = fitTask.error;
  const isFitting = fitTask.pending === "local";
  const isAutoFitting = fitTask.pending === "global";

  // UI Tabs & Views
  const [activeChartTab, setActiveChartTab] = useState<
    "plotly" | "nyquist" | "bode" | "residuals" | "kk" | "astm_g106" | "validation" | "drt" | "python_code" | "synthetic_noise"
  >("plotly");
  const [isImportModalOpen, setIsImportModalOpen] = useState<boolean>(false);
  const [copiedNotification, setCopiedNotification] = useState<boolean>(false);
  const [appliedNotification, setAppliedNotification] = useState<boolean>(false);

  const appliedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (appliedTimer.current) clearTimeout(appliedTimer.current); }, []);

  // File upload drag & drop ref
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [manualPasteText, setManualPasteText] = useState<string>("");
  const [manualFilename, setManualFilename] = useState<string>("custom_data.csv");

  // When selectedTopology changes, re-extract editable parameters
  const handleSelectTopology = (topo: CircuitTopology) => {
    setSelectedTopology(topo);
    const newParams = extractAdjustableParameters(topo);
    setEditableParams(newParams);
  };

  // Handle parameter value change in table
  const handleParamValueChange = (index: number, val: number) => {
    setEditableParams((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], value: val };
      return updated;
    });
  };

  // Handle parameter lock toggle
  const handleParamLockToggle = (index: number) => {
    setEditableParams((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], isFixed: !updated[index].isFixed };
      return updated;
    });
  };

  // Auto-Estimate initial parameter guesses based on high-frequency and low-frequency intercepts
  const handleAutoEstimate = () => {
    if (activeDataset.points.length < 2) return;
    const sorted = [...activeDataset.points].sort((a, b) => b.frequency - a.frequency);
    const highestFreqPt = sorted[0];
    const lowestFreqPt = sorted[sorted.length - 1];

    const estimatedRs = Math.max(1e-4, highestFreqPt.zReal);
    const estimatedTotalR = Math.max(estimatedRs * 1.2, lowestFreqPt.zReal);
    const estimatedRct = Math.max(1e-4, estimatedTotalR - estimatedRs);

    setEditableParams((prev) =>
      prev.map((p) => {
        if (p.paramName.toLowerCase().includes("s") || p.paramName.toLowerCase().includes("0") || p.paramName.toLowerCase().includes("bulk")) {
          return { ...p, value: estimatedRs };
        }
        if (p.paramName.toLowerCase().includes("ct") || p.paramName.toLowerCase().includes("p") || p.paramName.toLowerCase().includes("corr")) {
          return { ...p, value: estimatedRct };
        }
        if (p.field === "exponent") {
          return { ...p, value: 0.88 };
        }
        return p;
      })
    );
  };

  // Results remain separate from editable initial guesses until explicitly applied.
  const runFit = async (global: boolean) => {
    const request = fitTask.begin(global ? "global" : "local");
    setAppliedNotification(false);
    try {
      const report = normalizePythonCnlsReport(await requestPythonAnalysis(
          global ? "/api/python/cnls-autofit" : "/api/python/cnls-fit",
          JSON.stringify({
            action: global ? "auto_fit" : "fit",
            topologyId: selectedTopology.id, topology: selectedTopology,
            points: activeDataset.points, parameters: editableParams, weighting,
            ...(global ? { maxGenerations: Math.max(60, maxIterations), populationSize: 40, polishLM: true }
              : { maxIterations }),
          }), request.signal), selectedTopology, activeDataset, weighting, editableParams);
      if (!request.isCurrent()) return;
      request.publish({ report, drt: null });
      try {
        const drt = await requestPythonAnalysis("/api/python/battery-corrosion-eis", JSON.stringify({
          action: "drt", frequencies: activeDataset.points.map(p => p.frequency),
          zReal: activeDataset.points.map(p => p.zReal), zImag: activeDataset.points.map(p => p.zImag),
          lambdaReg: 1e-3, numTau: 50,
        }), request.signal);
        if (drt.drtCurve) request.publish({ report, drt });
      } catch (error) {
        if (request.isCurrent()) console.warn("DRT unavailable:", error);
      }
    } catch (error) {
      request.fail(error);
    } finally {
      request.finish();
    }
  };
  const handleRunAutoFit = () => runFit(true);
  const handleRunFit = () => runFit(false);

  // File Upload Handler
  const handleFileUpload = (file: File) => {
    const request = fitTask.begin('upload');
    const reader = new FileReader();
    request.signal.addEventListener('abort', () => reader.abort(), { once: true });
    reader.onerror = () => request.fail(new Error('Failed to read EIS file.'));
    reader.onload = (e) => {
      if (!request.isCurrent()) return;
      try {
        const text = e.target?.result as string;
        if (!text) return;
        const parsed = parseEISFile(text, file.name);
        setActiveDataset(parsed);
        setIsImportModalOpen(false);
      } catch (err: any) {
        request.fail(new Error(`Failed to parse EIS file: ${err.message}`));
      } finally {
        request.finish();
      }
    };
    reader.readAsText(file);
  };

  // Manual Paste Handler
  const handleManualPasteSubmit = () => {
    try {
      if (!manualPasteText.trim()) return;
      const parsed = parseEISFile(manualPasteText, manualFilename);
      setActiveDataset(parsed);
      setIsImportModalOpen(false);
      setManualPasteText("");
    } catch (err: any) {
      alert(`Parse error: ${err.message}`);
    }
  };

  // Apply fitted model to workspace
  const handleApplyToWorkspace = () => {
    if (!fitReport) return;
    setAppliedNotification(true);
    if (appliedTimer.current) clearTimeout(appliedTimer.current);
    appliedTimer.current = setTimeout(() => setAppliedNotification(false), 2500);
    onApplyTopology(fitReport.topology);
  };

  // Format Scientific Notation nicely
  const formatSci = (val: number, digits = 4): string => {
    if (val === 0) return "0";
    if (Math.abs(val) >= 0.001 && Math.abs(val) < 10000) {
      return val.toFixed(digits);
    }
    return val.toExponential(digits - 1);
  };

  // Combine Experimental Points with Fitted Curve for Charts
  const chartData = useMemo(() => {
    if (!fitReport) {
      // Just experimental points
      return activeDataset.points.map((pt) => ({
        frequency: pt.frequency,
        logFreq: Math.log10(pt.frequency),
        expZReal: pt.zReal,
        expMinusZImag: pt.minusZImag,
        expZMag: pt.zMag,
        expPhaseDeg: pt.phaseDeg,
      }));
    }

    return fitReport.residuals.map((r, idx) => {
      const expPt = activeDataset.points[idx];
      const calcMag = Math.sqrt(r.calcZReal * r.calcZReal + r.calcMinusZImag * r.calcMinusZImag);
      const calcPhase = (Math.atan2(-r.calcMinusZImag, r.calcZReal) * 180) / Math.PI;

      return {
        frequency: r.frequency,
        logFreq: r.logFreq,
        // Experimental
        expZReal: r.expZReal,
        expMinusZImag: r.expMinusZImag,
        expZMag: expPt ? expPt.zMag : Math.sqrt(r.expZReal ** 2 + r.expMinusZImag ** 2),
        expPhaseDeg: expPt ? expPt.phaseDeg : (Math.atan2(-r.expMinusZImag, r.expZReal) * 180) / Math.PI,
        // Fitted Model
        calcZReal: r.calcZReal,
        calcMinusZImag: r.calcMinusZImag,
        calcZMag: calcMag,
        calcPhaseDeg: calcPhase,
        // Residuals %
        resZRealPct: r.resZRealPct,
        resZImagPct: r.resZImagPct,
        // ASTM G106 Weights
        weightReal: r.weightReal ?? 1.0,
        weightImag: r.weightImag ?? 1.0,
        logWeightReal: parseFloat(Math.log10(Math.max(1e-25, r.weightReal ?? 1.0)).toFixed(3)),
        logWeightImag: parseFloat(Math.log10(Math.max(1e-25, r.weightImag ?? 1.0)).toFixed(3)),
        weightedDiffReal: r.weightedDiffReal ?? 0,
        weightedDiffImag: r.weightedDiffImag ?? 0,
      };
    });
  }, [activeDataset, fitReport]);

  return (
    <div className="flex flex-col h-full bg-[#050810] text-slate-200 font-mono select-none">
      {/* Top Banner & Dataset Selector */}
      <div className="p-4 border-b border-[#162032] bg-[#070b14] flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-400/30 text-sky-400">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                CNLS Impedance Fitting Engine
              </h2>
              <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold">
                Levenberg-Marquardt
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30">
                Kramers-Kronig Check
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Fit experimental EIS spectra to Equivalent Circuit Models with weighted non-linear regression, parameter error bounds (&plusmn;&sigma;%), and residuals.
            </p>
          </div>
        </div>

        {/* Dataset Controls & File Importer Trigger */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setIsImportModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#0c1424] border border-[#1e2d46] hover:border-sky-400 text-xs text-sky-300 transition-all shadow-sm"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Import EIS File...</span>
          </button>

          {/* Benchmark Selector Dropdown */}
          <div className="flex items-center gap-1.5 bg-[#050810] border border-[#162032] rounded-xl px-2.5 py-1 text-xs">
            <span className="text-slate-500 text-[10px]">Benchmark:</span>
            <select
              value={activeDataset.id}
              onChange={(e) => {
                const selected = EXPERIMENTAL_BENCHMARKS.find((b) => b.id === e.target.value);
                if (selected) {
                  setActiveDataset(selected);
                }
              }}
              className="bg-transparent text-xs text-slate-200 focus:outline-none max-w-[200px] truncate"
            >
              {EXPERIMENTAL_BENCHMARKS.map((bm) => (
                <option key={bm.id} value={bm.id} className="bg-[#090e18]">
                  {bm.name}
                </option>
              ))}
            </select>
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded-xl bg-[#090e18] border border-[#162032] hover:border-slate-500 text-xs text-slate-400 hover:text-white"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Main Studio Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 flex-1 overflow-hidden min-h-0 divide-y lg:divide-y-0 lg:divide-x divide-[#162032]">
        {/* Left Column: Model Setup, Initial Parameters & Fit Actions (5 Cols) */}
        <div className="lg:col-span-5 overflow-y-auto p-4 space-y-4 bg-[#070b14]/50">
          {/* Active Dataset Summary Card */}
          <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-sky-400" />
                Active Experimental Dataset
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-400/20 font-bold uppercase">
                {activeDataset.source}
              </span>
            </div>

            <h4 className="text-xs font-bold text-white">{activeDataset.name}</h4>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              {activeDataset.description}
            </p>

            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[#162032] text-[10px]">
              <div>
                <span className="text-slate-500 block">Points</span>
                <span className="text-slate-200 font-bold">{activeDataset.points.length}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Max Freq</span>
                <span className="text-slate-200 font-bold">
                  {formatSci(Math.max(...activeDataset.points.map((p) => p.frequency)), 2)} Hz
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Min Freq</span>
                <span className="text-slate-200 font-bold">
                  {formatSci(Math.min(...activeDataset.points.map((p) => p.frequency)), 2)} Hz
                </span>
              </div>
            </div>
          </div>

          {/* Model Topology Selection */}
          <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-sky-400" />
                Equivalent Circuit Model (ECM)
              </span>
              <span className="text-[10px] font-mono text-sky-300 font-bold bg-sky-500/10 px-2 py-0.5 rounded border border-sky-400/30">
                {selectedTopology.cdcNotation}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <select
                value={selectedTopology.id}
                onChange={(e) => {
                  const found = STANDARD_CIRCUIT_PRESETS.find((p) => p.id === e.target.value);
                  if (found) handleSelectTopology(found);
                }}
                className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-3 py-2 text-xs text-sky-300 font-mono focus:outline-none focus:border-sky-400"
              >
                {STANDARD_CIRCUIT_PRESETS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.cdcNotation})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Parameter Matrix Table with Locks & Bounds */}
          <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-sky-400" />
                Initial Guess &amp; Parameter Constraints
              </span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={isAutoFitting || isFitting}
                  onClick={handleRunAutoFit}
                  className="flex items-center gap-1 text-[10px] text-amber-300 hover:text-amber-200 font-bold px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 transition-all cursor-pointer"
                  title="Run Python Differential Evolution to find global optimal initial estimates"
                >
                  <Zap className="w-3 h-3 text-amber-400 fill-amber-400" />
                  <span>⚡ Auto-Fit (Global DE)</span>
                </button>
                <button
                  type="button"
                  onClick={handleAutoEstimate}
                  className="flex items-center gap-1 text-[10px] text-sky-400 hover:text-sky-300 font-bold px-2 py-0.5 rounded bg-sky-500/10 border border-sky-500/20"
                >
                  <Sparkles className="w-3 h-3" />
                  <span>Heuristics</span>
                </button>
              </div>
            </div>

            <div className="border border-[#162032] rounded-xl overflow-hidden bg-[#050810]">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#0c1424] border-b border-[#162032] text-[10px] text-slate-400 uppercase">
                  <tr>
                    <th className="p-2 font-semibold">Param</th>
                    <th className="p-2 font-semibold">Value</th>
                    <th className="p-2 font-semibold text-center">Lock</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#162032] text-[11px]">
                  {editableParams.map((param, idx) => (
                    <tr key={idx} className="hover:bg-[#0c1424]/40">
                      <td className="p-2 font-bold text-sky-300 whitespace-nowrap">
                        <span>{param.paramName}</span>
                        <span className="text-[9px] text-slate-500 block font-normal">
                          {param.paramType} ({param.unit})
                        </span>
                      </td>

                      <td className="p-2">
                        <input
                          type="number"
                          step="any"
                          value={param.value}
                          disabled={param.isFixed}
                          onChange={(e) => handleParamValueChange(idx, parseFloat(e.target.value) || 0)}
                          className="w-28 bg-[#090e18] border border-[#1e2d46] rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-sky-400 disabled:opacity-50 disabled:bg-[#050810]"
                        />
                      </td>

                      <td className="p-2 text-center">
                        <button
                          type="button"
                          onClick={() => handleParamLockToggle(idx)}
                          className={`p-1.5 rounded-lg border transition-all ${
                            param.isFixed
                              ? "bg-amber-500/20 border-amber-500/40 text-amber-300"
                              : "bg-[#090e18] border-[#162032] text-slate-500 hover:text-slate-300"
                          }`}
                          title={param.isFixed ? "Fixed (locked during fitting)" : "Free (adjustable)"}
                        >
                          {param.isFixed ? <Lock className="w-3 h-3" /> : <Unlock className="w-3 h-3" />}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Regression Controls & Run Button */}
          <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
              CNLS Regression Settings
            </span>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Optimizer Engine</label>
                <select
                  value={executionEngine}
                  onChange={(e) => setExecutionEngine(e.target.value as any)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2 py-1.5 text-xs text-emerald-400 font-mono focus:outline-none"
                >
                  <option value="python_hpc">CPython 3.10+ (LM + DRT)</option>
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[10px] text-slate-400">Weighting Scheme</label>
                  <span
                    className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                      weighting === "modulus"
                        ? "text-emerald-400 bg-emerald-500/15"
                        : weighting === "proportional"
                        ? "text-sky-400 bg-sky-500/15"
                        : "text-rose-400 bg-rose-500/20"
                    }`}
                  >
                    {weighting === "modulus"
                      ? "ASTM G106 Standard"
                      : weighting === "proportional"
                      ? "ASTM G106 Regularized"
                      : "Non-Compliant"}
                  </span>
                </div>
                <select
                  value={weighting}
                  onChange={(e) => setWeighting(e.target.value as WeightingMethod)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
                >
                  <option value="modulus">Modulus (1/|Z|²) [ASTM G106]</option>
                  <option value="proportional">Proportional (1/Z'², 1/Z''²) [Reg.]</option>
                  <option value="unit">Unit (w = 1) [Unweighted Skew]</option>
                </select>
              </div>
            </div>

            {/* ASTM G106 Compliance Feedback Card */}
            {weighting === "unit" ? (
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-[10px] text-rose-300 space-y-1">
                <div className="flex items-center gap-1.5 font-bold text-rose-200">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                  <span>ASTM G106 Non-Compliance Warning</span>
                </div>
                <p className="leading-relaxed text-rose-300/90">
                  Unweighted least squares (w=1) causes high low-frequency impedance (10⁷ – 10⁹ Ω) to completely dominate the loss function. High-frequency semicircle (Rs ~ 10–100 Ω, C_dl) is ignored by Levenberg-Marquardt.
                </p>
                <button
                  type="button"
                  onClick={() => setWeighting("modulus")}
                  className="mt-1 inline-flex items-center gap-1 text-[10px] text-amber-300 font-bold hover:underline"
                >
                  <span>Switch to Modulus Weighting (1/|Z|²) per ASTM G106 &rarr;</span>
                </button>
              </div>
            ) : (
              <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-[10px] text-emerald-300 flex items-start gap-2">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span className="leading-relaxed">
                  {weighting === "modulus"
                    ? "ASTM G106 Modulus Weighting (1/|Z|²) normalizes fractional error squared across 6–9 decades, balancing electrolyte resistance (Rs) against polarization resistance (Rp)."
                    : "ASTM G106 Regularized Proportional Weighting with (0.01·|Z|)² floor preventing zero-crossing singularity."}
                </span>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Max Iterations</label>
                <input
                  type="number"
                  min="10"
                  max="500"
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(parseInt(e.target.value) || 80)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
                />
              </div>
              <div className="flex items-end">
                <span className="text-[10px] text-slate-500 pb-2">
                  Auto-calculates Lin-KK &amp; DRT continuous spectrum
                </span>
              </div>
            </div>

            {fitError && (
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{fitError}</span>
              </div>
            )}

            {/* Two Action Buttons: 1-Click Auto-Fit & Standard LM Run */}
            <div className="space-y-2">
              <button
                type="button"
                disabled={isAutoFitting || isFitting}
                onClick={handleRunAutoFit}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-400 via-orange-500 to-rose-500 hover:from-amber-300 hover:to-rose-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(245,158,11,0.4)] transition-all disabled:opacity-50 active:scale-[0.99] cursor-pointer"
              >
                {isAutoFitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin text-slate-950" />
                    <span>Running Global Differential Evolution (Python)...</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4 fill-slate-950" />
                    <span>⚡ One-Click Auto-Fit (Global Optimization)</span>
                  </>
                )}
              </button>

              <button
                type="button"
                disabled={isFitting || isAutoFitting}
                onClick={handleRunFit}
                className="w-full py-2.5 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-slate-700/60 text-slate-200 font-bold text-xs flex items-center justify-center gap-2 transition-all disabled:opacity-50 active:scale-[0.99] cursor-pointer"
              >
                {isFitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                    <span>Iterating Levenberg-Marquardt...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current text-sky-400" />
                    <span>Run Local Levenberg-Marquardt Polish</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Graphs (Nyquist, Bode, Residuals, K-K) & Fitted Parameter Report (7 Cols) */}
        <div className="lg:col-span-7 overflow-y-auto p-4 space-y-4 bg-[#050810]">
          {/* Fit Results Scorecard Banner */}
          {fitReport && (
            <div className="p-4 rounded-xl bg-gradient-to-br from-[#0c1424] to-[#080d18] border border-sky-400/40 shadow-lg space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <div>
                    <h3 className="text-xs font-bold text-white uppercase">
                      {fitReport.converged ? "Fit converged" : "Convergence not confirmed"} ({fitReport.iterations} iterations in {fitReport.executionTimeMs} ms)
                    </h3>
                    <span className="text-[10px] text-slate-400">
                      Reduced Chi-Square (&chi;&sup2;<sub>red</sub>):{" "}
                      <strong className="text-emerald-300 font-bold">
                        {fitReport.reducedChiSquare.toExponential(3)}
                      </strong>{" "}
                      | R² = <strong className="text-emerald-300 font-bold">{(fitReport.rSquared == null ? "Unavailable" : fitReport.rSquared.toFixed(5))}</strong>
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleApplyToWorkspace}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition-all shadow-[0_0_12px_rgba(16,185,129,0.3)]"
                  >
                    {appliedNotification ? <Check className="w-3.5 h-3.5" /> : <Zap className="w-3.5 h-3.5 fill-current" />}
                    <span>{appliedNotification ? "Applied to Workspace!" : "Apply to Circuit Workspace"}</span>
                  </button>
                </div>
              </div>

              {/* Kramers-Kronig Validation Alert */}
              <div
                className={`p-2.5 rounded-xl border text-xs flex items-center justify-between ${
                  fitReport.kramersKronig.isValid
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                    : "bg-amber-500/10 border-amber-500/30 text-amber-300"
                }`}
              >
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 shrink-0" />
                  <span>
                    <strong>K-K Consistency:</strong> {fitReport.kramersKronig.assessment} (Mean Residual: {fitReport.kramersKronig.meanResidualPct}%)
                  </span>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-black/40">
                  {fitReport.kramersKronig.score == null ? "Independent K-K unavailable" : `${fitReport.kramersKronig.score}% Score`}
                </span>
              </div>

              {/* ASTM G106 Weighting & Multi-Decade Dynamic Range Status */}
              {fitReport.astmG106 && (
                <div
                  className={`p-2.5 rounded-xl border text-xs flex items-center justify-between flex-wrap gap-2 ${
                    fitReport.astmG106.isAstmG106Compliant
                      ? "bg-indigo-500/10 border-indigo-500/30 text-indigo-300"
                      : "bg-rose-500/15 border-rose-500/40 text-rose-300"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Scale className="w-4 h-4 shrink-0" />
                    <div>
                      <span>
                        <strong>ASTM G106 Status:</strong>{" "}
                        {fitReport.astmG106.isAstmG106Compliant ? (
                          <span className="text-emerald-300 font-bold">
                            Compliant ({fitReport.astmG106.weightingScheme} weighting)
                          </span>
                        ) : (
                          <span className="text-rose-300 font-bold">
                            Non-Compliant (Unweighted Least Squares Skew)
                          </span>
                        )}
                      </span>
                      <span className="text-[10px] text-slate-400 block mt-0.5">
                        Dynamic Range: <strong>{fitReport.astmG106.dynamicRangeDecades} decades</strong> (
                        {fitReport.astmG106.minImpedanceMagnitude_Ohm} Ω → {fitReport.astmG106.maxImpedanceMagnitude_Ohm.toExponential(1)} Ω)
                        {" · "}
                        Balancing Ratio: <strong>{fitReport.astmG106.hfSensitivityBalancingFactor.toExponential(1)}×</strong>
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveChartTab("astm_g106")}
                    className="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-[#050810] border border-[#1e2d46] hover:border-indigo-400 text-indigo-300 transition-all flex items-center gap-1"
                  >
                    <span>View Weighting Audit</span>
                    <ChevronRight className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Chart Header & Navigation Tabs */}
          <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2 border-b border-[#162032] pb-2">
              <div className="flex items-center gap-1.5 flex-wrap">
                <button
                  type="button"
                  onClick={() => setActiveChartTab("plotly" as any)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    (activeChartTab as string) === "plotly"
                      ? "bg-sky-500/20 border border-sky-400 text-sky-200 shadow-[0_0_10px_rgba(56,189,248,0.3)]"
                      : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  ⚡ Plotly 3D/Interactive View
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChartTab("nyquist")}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    activeChartTab === "nyquist"
                      ? "bg-sky-500/20 border border-sky-400 text-sky-200"
                      : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Nyquist Overlay (-Z'' vs Z')
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChartTab("bode")}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    activeChartTab === "bode"
                      ? "bg-sky-500/20 border border-sky-400 text-sky-200"
                      : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Bode (Mag &amp; Phase)
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChartTab("residuals")}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    activeChartTab === "residuals"
                      ? "bg-sky-500/20 border border-sky-400 text-sky-200"
                      : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Normalized Residuals (% Error)
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChartTab("astm_g106")}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                    activeChartTab === "astm_g106"
                      ? "bg-indigo-500/25 border border-indigo-400 text-indigo-200 shadow-[0_0_12px_rgba(99,102,241,0.3)]"
                      : "bg-[#050810] border border-[#162032] text-indigo-400/90 hover:text-indigo-200"
                  }`}
                >
                  <Scale className="w-3.5 h-3.5 text-indigo-400" />
                  <span>ASTM G106 Weighting Audit</span>
                  {fitReport?.astmG106 && (
                    <span
                      className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                        fitReport.astmG106.isAstmG106Compliant
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-rose-500/30 text-rose-300 animate-pulse"
                      }`}
                    >
                      {fitReport.astmG106.isAstmG106Compliant ? "Compliant" : "Skewed"}
                    </span>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChartTab("kk")}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    activeChartTab === "kk"
                      ? "bg-sky-500/20 border border-sky-400 text-sky-200"
                      : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Kramers-Kronig Test
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChartTab("validation")}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    activeChartTab === "validation"
                      ? "bg-emerald-500/20 border border-emerald-400 text-emerald-200"
                      : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  🛡️ Physical Validation (Brug / Lin-KK)
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChartTab("drt")}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    activeChartTab === "drt"
                      ? "bg-emerald-500/20 border border-emerald-400 text-emerald-200"
                      : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  DRT Relaxation Spectrum γ(ln τ)
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChartTab("python_code")}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    activeChartTab === "python_code"
                      ? "bg-indigo-500/20 border border-indigo-400 text-indigo-200"
                      : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Python Solver Code
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChartTab("synthetic_noise" as any)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    (activeChartTab as string) === "synthetic_noise"
                      ? "bg-amber-500/20 border border-amber-400 text-amber-200 shadow-[0_0_12px_rgba(245,158,11,0.3)]"
                      : "bg-[#050810] border border-[#162032] text-amber-400/80 hover:text-amber-200"
                  }`}
                >
                  ⚡ Synthetic Noise &amp; Artifact Simulator
                </button>
              </div>

              <div className="flex items-center gap-3 text-[10px] text-slate-400">
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-sky-400 inline-block"></span>
                  <span>Experimental (Dots)</span>
                </span>
                {fitReport && (
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-0.5 bg-rose-400 inline-block"></span>
                    <span>CNLS Fit (Curve)</span>
                  </span>
                )}
              </div>
            </div>

            {/* Visual Plots */}
            <div className="min-h-[360px] w-full pt-2">
              {(activeChartTab as string) === "plotly" && (
                <PlotlyEISViewer
                  topology={fitReport?.topology ?? applyParametersToTopology(selectedTopology, editableParams)}
                  experimentalDataset={activeDataset}
                  fitReport={fitReport}
                  className="w-full"
                />
              )}

              {activeChartTab === "nyquist" && (
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" />
                    <XAxis
                      dataKey="expZReal"
                      type="number"
                      stroke="#64748b"
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      label={{ value: "Z' Real (Ω)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                    />
                    <YAxis
                      dataKey="expMinusZImag"
                      type="number"
                      stroke="#64748b"
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      label={{ value: "-Z'' Imag (Ω)", angle: -90, position: "insideLeft", offset: 10, fill: "#94a3b8", fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", borderRadius: "12px", fontSize: "11px", color: "#f8fafc" }}
                      formatter={(val: any) => [typeof val === "number" ? formatSci(val, 3) + " Ω" : val]}
                    />
                    {/* Experimental Scatter Points */}
                    <Scatter name="Experimental Data" dataKey="expMinusZImag" fill="#38bdf8" shape="circle" />
                    {/* Fitted Curve Line */}
                    {fitReport && (
                      <Line
                        type="monotone"
                        dataKey="calcMinusZImag"
                        stroke="#f43f5e"
                        strokeWidth={2.5}
                        dot={false}
                        name="CNLS Fit Model"
                      />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              )}

              {activeChartTab === "bode" && (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" />
                    <XAxis
                      dataKey="logFreq"
                      stroke="#64748b"
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      label={{ value: "log₁₀(Frequency [Hz])", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                    />
                    <YAxis
                      yAxisId="mag"
                      stroke="#38bdf8"
                      tick={{ fontSize: 10, fill: "#38bdf8" }}
                      label={{ value: "|Z| Magnitude (Ω)", angle: -90, position: "insideLeft", offset: 10, fill: "#38bdf8", fontSize: 11 }}
                    />
                    <YAxis
                      yAxisId="phase"
                      orientation="right"
                      domain={[-90, 10]}
                      stroke="#a855f7"
                      tick={{ fontSize: 10, fill: "#a855f7" }}
                      label={{ value: "Phase θ (deg)", angle: 90, position: "insideRight", offset: 10, fill: "#a855f7", fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", borderRadius: "12px", fontSize: "11px", color: "#f8fafc" }}
                    />
                    <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "5px" }} />
                    <Line yAxisId="mag" type="monotone" dataKey="expZMag" stroke="#38bdf8" strokeWidth={2} dot={{ r: 2 }} name="Exp |Z|" />
                    {fitReport && (
                      <Line yAxisId="mag" type="monotone" dataKey="calcZMag" stroke="#0ea5e9" strokeDasharray="4 4" strokeWidth={2} dot={false} name="Fit |Z|" />
                    )}
                    <Line yAxisId="phase" type="monotone" dataKey="expPhaseDeg" stroke="#a855f7" strokeWidth={2} dot={{ r: 2 }} name="Exp Phase" />
                    {fitReport && (
                      <Line yAxisId="phase" type="monotone" dataKey="calcPhaseDeg" stroke="#ec4899" strokeDasharray="4 4" strokeWidth={2} dot={false} name="Fit Phase" />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              )}

              {activeChartTab === "residuals" && (
                <div className="h-full flex flex-col">
                  {!fitReport ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs">
                      <span>Run CNLS Optimization to view normalized residuals.</span>
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" />
                        <XAxis
                          dataKey="logFreq"
                          stroke="#64748b"
                          tick={{ fontSize: 10, fill: "#94a3b8" }}
                          label={{ value: "log₁₀(Frequency [Hz])", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                        />
                        <YAxis
                          stroke="#64748b"
                          domain={[-5, 5]}
                          tick={{ fontSize: 10, fill: "#94a3b8" }}
                          label={{ value: "Residual ΔZ / |Z| (%)", angle: -90, position: "insideLeft", offset: 10, fill: "#94a3b8", fontSize: 11 }}
                        />
                        <ReferenceLine y={0} stroke="#475569" strokeDasharray="2 2" />
                        <ReferenceLine y={1} stroke="#10b981" strokeDasharray="3 3" />
                        <ReferenceLine y={-1} stroke="#10b981" strokeDasharray="3 3" />
                        <Tooltip
                          contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", borderRadius: "12px", fontSize: "11px", color: "#f8fafc" }}
                        />
                        <Legend wrapperStyle={{ fontSize: "11px" }} />
                        <Line type="monotone" dataKey="resZRealPct" stroke="#38bdf8" strokeWidth={2} dot={{ r: 2 }} name="ΔZ' Residual %" />
                        <Line type="monotone" dataKey="resZImagPct" stroke="#f43f5e" strokeWidth={2} dot={{ r: 2 }} name="ΔZ'' Residual %" />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>
              )}

              {/* ASTM G106 Weighting & Dynamic Range Audit Tab */}
              {activeChartTab === "astm_g106" && (
                <div className="h-full flex flex-col p-2 space-y-4 overflow-y-auto">
                  {/* Dynamic Range Statistics Tiles */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div className="p-3 rounded-xl bg-[#050810] border border-[#162032] space-y-1">
                      <span className="text-slate-500 text-[10px] uppercase font-bold block">Dynamic Range Span</span>
                      <span className="text-indigo-400 text-lg font-bold">
                        {fitReport?.astmG106
                          ? `${fitReport.astmG106.dynamicRangeDecades} Decades`
                          : `${(Math.log10(Math.max(...activeDataset.points.map((p) => p.zMag)) / Math.max(1e-6, Math.min(...activeDataset.points.map((p) => p.zMag))))).toFixed(1)} Decades`}
                      </span>
                      <span className="text-[10px] text-slate-500 block">Wide-band frequency sweep</span>
                    </div>

                    <div className="p-3 rounded-xl bg-[#050810] border border-[#162032] space-y-1">
                      <span className="text-slate-500 text-[10px] uppercase font-bold block">HF Regime (Rs)</span>
                      <span className="text-sky-400 text-lg font-bold">
                        {fitReport?.astmG106
                          ? `${fitReport.astmG106.minImpedanceMagnitude_Ohm.toFixed(1)} Ω`
                          : `${Math.min(...activeDataset.points.map((p) => p.zMag)).toFixed(1)} Ω`}
                      </span>
                      <span className="text-[10px] text-slate-500 block">Electrolyte ohmic resistance</span>
                    </div>

                    <div className="p-3 rounded-xl bg-[#050810] border border-[#162032] space-y-1">
                      <span className="text-slate-500 text-[10px] uppercase font-bold block">LF Regime (Rp / Rct)</span>
                      <span className="text-emerald-400 text-lg font-bold">
                        {fitReport?.astmG106
                          ? `${formatSci(fitReport.astmG106.maxImpedanceMagnitude_Ohm, 2)} Ω`
                          : `${formatSci(Math.max(...activeDataset.points.map((p) => p.zMag)), 2)} Ω`}
                      </span>
                      <span className="text-[10px] text-slate-500 block">Passivation / coating barrier</span>
                    </div>

                    <div className="p-3 rounded-xl bg-[#050810] border border-[#162032] space-y-1">
                      <span className="text-slate-500 text-[10px] uppercase font-bold block">HF Balancing Ratio</span>
                      <span className="text-amber-400 text-lg font-bold">
                        {fitReport?.astmG106
                          ? `${fitReport.astmG106.hfSensitivityBalancingFactor.toExponential(1)}×`
                          : `${(Math.pow(Math.max(...activeDataset.points.map((p) => p.zMag)) / Math.max(1e-6, Math.min(...activeDataset.points.map((p) => p.zMag))), 2)).toExponential(1)}×`}
                      </span>
                      <span className="text-[10px] text-slate-500 block">Weight scaling factor (|Z|max/|Z|min)²</span>
                    </div>
                  </div>

                  {/* ASTM Standard Recommendation Banner */}
                  <div
                    className={`p-3.5 rounded-xl border text-xs space-y-2 ${
                      (fitReport?.astmG106?.isAstmG106Compliant === true)
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-200"
                        : "bg-rose-500/15 border-rose-500/40 text-rose-200"
                    }`}
                  >
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2">
                        <Scale className="w-5 h-5 text-indigo-400 shrink-0" />
                        <div>
                          <h4 className="font-bold text-xs uppercase tracking-wide">
                            ASTM G106 compliance unavailable
                          </h4>
                          <p className="text-[11px] opacity-90 mt-0.5 leading-relaxed">
                            {"Weighting diagnostics do not establish standards compliance. Modulus weights fractional complex residuals; proportional weighting uses component magnitudes with a floor; unit weighting uses absolute residuals."}
                          </p>
                        </div>
                      </div>

                      {weighting === "unit" && (
                        <button
                          type="button"
                          onClick={() => {
                            setWeighting("modulus");
                            setTimeout(() => handleRunFit(), 50);
                          }}
                          className="px-3 py-1.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs transition-all shadow-[0_0_12px_rgba(245,158,11,0.4)] cursor-pointer shrink-0"
                        >
                          Switch to Modulus (1/|Z|²) &amp; Refit Now
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Weight Distribution vs Frequency Plot */}
                  <div className="p-3 rounded-xl bg-[#050810] border border-[#162032] space-y-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                          Statistical Weight Distribution log₁₀(w) vs log₁₀(Frequency)
                        </h4>
                        <span className="text-[10px] text-slate-400">
                          Shows how ASTM G106 modulus weighting w = 1/|Z|² scales statistical sensitivity across frequencies
                        </span>
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-bold">
                        {weighting === "modulus" ? "Modulus (1/|Z|²)" : weighting === "proportional" ? "Proportional (1/Z²)" : "Unit (w=1)"}
                      </span>
                    </div>

                    <div className="h-[200px] w-full pt-1">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" />
                          <XAxis
                            dataKey="logFreq"
                            stroke="#64748b"
                            tick={{ fontSize: 10, fill: "#94a3b8" }}
                            label={{ value: "log₁₀(Frequency [Hz])", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                          />
                          <YAxis
                            stroke="#818cf8"
                            tick={{ fontSize: 10, fill: "#818cf8" }}
                            label={{ value: "log₁₀(Weight w [Ω⁻²])", angle: -90, position: "insideLeft", offset: 10, fill: "#818cf8", fontSize: 11 }}
                          />
                          <Tooltip
                            contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", borderRadius: "12px", fontSize: "11px", color: "#f8fafc" }}
                            formatter={(value: any, name: any) => [value, name === "logWeightReal" ? "log₁₀(w_Real)" : "log₁₀(w_Imag)"]}
                          />
                          <Legend wrapperStyle={{ fontSize: "11px" }} />
                          <Line type="monotone" dataKey="logWeightReal" stroke="#818cf8" strokeWidth={2.5} dot={{ r: 2 }} name="log₁₀(w_Real)" />
                          {weighting === "proportional" && (
                            <Line type="monotone" dataKey="logWeightImag" stroke="#f43f5e" strokeWidth={2} strokeDasharray="3 3" dot={{ r: 2 }} name="log₁₀(w_Imag)" />
                          )}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* ASTM G106 Engineering Reference Table */}
                  <div className="border border-[#162032] rounded-xl overflow-hidden bg-[#050810] text-[11px]">
                    <div className="px-3 py-2 bg-[#0c1424] font-bold text-[10px] text-slate-400 uppercase tracking-wider flex items-center justify-between">
                      <span>ASTM G106-89 Impedance Weighting Methods Comparison</span>
                      <span className="text-[10px] text-slate-500 font-normal">Complex Non-Linear Least Squares (CNLS)</span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left">
                        <thead>
                          <tr className="border-b border-[#162032] text-slate-400 text-[10px] bg-[#070b14]">
                            <th className="p-2.5">Weighting Method</th>
                            <th className="p-2.5">Weight Formulation</th>
                            <th className="p-2.5">Loss Metric Minimized</th>
                            <th className="p-2.5">HF Semicircle Sensitivity</th>
                            <th className="p-2.5">Singularity Protection</th>
                            <th className="p-2.5">ASTM G106 Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#162032] text-slate-300">
                          <tr className={weighting === "modulus" ? "bg-indigo-950/20" : ""}>
                            <td className="p-2.5 font-bold text-emerald-400 flex items-center gap-1.5">
                              {weighting === "modulus" && <Check className="w-3.5 h-3.5 text-emerald-400" />}
                              <span>Modulus Weighting</span>
                            </td>
                            <td className="p-2.5 font-mono text-sky-300">w_i = 1 / |Z_i|²</td>
                            <td className="p-2.5 text-slate-300">Σ ((ΔZ' / |Z|)² + (ΔZ'' / |Z|)²)</td>
                            <td className="p-2.5 text-emerald-400 font-bold">Equal relative sensitivity across all decades</td>
                            <td className="p-2.5 text-slate-300">Intrinsic (|Z| &gt; 0 for physical cells)</td>
                            <td className="p-2.5">
                              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[9px] font-bold">
                                Primary Standard (Recommended)
                              </span>
                            </td>
                          </tr>
                          <tr className={weighting === "proportional" ? "bg-indigo-950/20" : ""}>
                            <td className="p-2.5 font-bold text-sky-400 flex items-center gap-1.5">
                              {weighting === "proportional" && <Check className="w-3.5 h-3.5 text-sky-400" />}
                              <span>Proportional Weighting</span>
                            </td>
                            <td className="p-2.5 font-mono text-sky-300">w_re = 1/Z'², w_im = 1/Z''²</td>
                            <td className="p-2.5 text-slate-300">Σ ((ΔZ'/Z')² + (ΔZ''/Z'')²)</td>
                            <td className="p-2.5 text-sky-400">High relative sensitivity per component</td>
                            <td className="p-2.5 text-amber-300">Regularized: max((0.01·|Z|)², Z''²)</td>
                            <td className="p-2.5">
                              <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30 text-[9px] font-bold">
                                Approved Variant (Macdonald)
                              </span>
                            </td>
                          </tr>
                          <tr className={weighting === "unit" ? "bg-rose-950/20" : ""}>
                            <td className="p-2.5 font-bold text-rose-400 flex items-center gap-1.5">
                              {weighting === "unit" && <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />}
                              <span>Unit Weighting (OLS)</span>
                            </td>
                            <td className="p-2.5 font-mono text-slate-400">w_i = 1.0</td>
                            <td className="p-2.5 text-slate-300">Σ ((ΔZ')² + (ΔZ'')²)</td>
                            <td className="p-2.5 text-rose-400 font-bold">
                              Suppressed by 10¹²–10¹⁶x vs low-freq Rp
                            </td>
                            <td className="p-2.5 text-slate-400">Trivial (Constant 1)</td>
                            <td className="p-2.5">
                              <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[9px] font-bold">
                                ASTM G106 Non-Compliant
                              </span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {activeChartTab === "kk" && (
                <div className="h-full flex flex-col p-2 space-y-3">
                  <div className="p-3 rounded-xl bg-[#050810] border border-[#162032] space-y-1">
                    <span className="text-slate-400 text-[10px] font-bold uppercase tracking-wider block">
                      Linear Kramers-Kronig (K-K) Transform Principle
                    </span>
                    <p className="text-slate-300 text-xs leading-relaxed">
                      K-K relations transform the real part Z&apos;(&omega;) into the imaginary part Z&apos;&apos;<sub>KK</sub>(&omega;) via Hilbert integration. Consistent data confirms that the electrochemical system is linear, causal, and stationary during the frequency sweep.
                    </p>
                  </div>

                  <div className="grid grid-cols-3 gap-3 text-xs">
                    <div className="p-3 rounded-xl bg-[#050810] border border-[#162032]">
                      <span className="text-slate-500 text-[10px] block">Mean Residual</span>
                      <span className="text-emerald-400 text-base font-bold">
                        {fitReport ? fitReport.kramersKronig.meanResidualPct : "Unavailable"}%
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-[#050810] border border-[#162032]">
                      <span className="text-slate-500 text-[10px] block">Max Residual</span>
                      <span className="text-slate-200 text-base font-bold">
                        {fitReport ? fitReport.kramersKronig.maxResidualPct : "Unavailable"}%
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-[#050810] border border-[#162032]">
                      <span className="text-slate-500 text-[10px] block">Status</span>
                      <span className="text-sky-400 text-xs font-bold block mt-1">
                        {fitReport ? fitReport.kramersKronig.assessment : "Independent K-K unavailable"}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {activeChartTab === "drt" && (
                <div className="h-full flex flex-col space-y-3">
                  {!drtResult ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs p-8 text-center space-y-2">
                      <Zap className="w-8 h-8 text-emerald-400/50 mx-auto" />
                      <span>Run CNLS Optimization to calculate DRT continuous relaxation spectrum γ(ln τ).</span>
                    </div>
                  ) : (
                    <div className="h-full flex flex-col space-y-2">
                      <div className="h-[220px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={drtResult.drtCurve} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" />
                            <XAxis
                              dataKey="logTau"
                              stroke="#64748b"
                              tick={{ fontSize: 10, fill: "#94a3b8" }}
                              label={{ value: "log₁₀(Relaxation Time τ [s])", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                            />
                            <YAxis
                              stroke="#10b981"
                              tick={{ fontSize: 10, fill: "#10b981" }}
                              label={{ value: "DRT Amplitude γ(ln τ) [Ω]", angle: -90, position: "insideLeft", offset: 10, fill: "#10b981", fontSize: 11 }}
                            />
                            <Tooltip
                              contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", borderRadius: "12px", fontSize: "11px", color: "#f8fafc" }}
                            />
                            <Line type="monotone" dataKey="gamma_Ohm" stroke="#10b981" strokeWidth={2.5} dot={false} name="DRT γ(ln τ)" />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Deconvolved Peaks Table */}
                      <div className="border border-[#162032] rounded-xl overflow-hidden bg-[#050810] text-[11px]">
                        <div className="px-3 py-1.5 bg-[#0c1424] font-bold text-[10px] text-slate-400 uppercase tracking-wider">
                          Deconvolved Time-Constants &amp; Physical Processes (Tikhonov Ridge)
                        </div>
                        <div className="max-h-[100px] overflow-y-auto divide-y divide-[#162032]">
                          {drtResult.identifiedPeaks?.map((pk: any, pkIdx: number) => (
                            <div key={pkIdx} className="px-3 py-1.5 flex items-center justify-between hover:bg-[#0c1424]/40">
                              <span className="font-bold text-emerald-300">
                                τ = {pk.tau_s < 0.001 ? (pk.tau_s * 1e6).toFixed(1) + " µs" : (pk.tau_s * 1000).toFixed(2) + " ms"} (f ≈ {pk.charFreq_Hz?.toFixed(1)} Hz)
                              </span>
                              <span className="text-slate-300 text-[10px]">{pk.process}</span>
                              <span className="text-slate-400 font-mono text-[10px]">γ = {pk.gammaHeight_Ohm} Ω</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeChartTab === "validation" && (
                <div className="w-full">
                  <PhysicalValidationStudio
                    initialDataset={activeDataset}
                    onApplyDeembeddedDataset={(correctedDs) => {
                      setActiveDataset(correctedDs);
                    }}
                  />
                </div>
              )}

              {activeChartTab === "python_code" && (
                <div className="h-full overflow-y-auto bg-[#050810] border border-[#162032] rounded-xl p-4 font-mono text-[11px] text-slate-300 leading-relaxed space-y-2">
                  <div className="text-indigo-400 font-bold"># High-Performance CPython 3.10+ CNLS &amp; DRT Engine</div>
                  <pre className="text-slate-300 whitespace-pre-wrap">
{`# Complex Non-Linear Least Squares (CNLS) Levenberg-Marquardt Optimizer
import numpy as np
import scipy.optimize as opt

# Circuit: ${selectedTopology.name}
# Frequency points: ${activeDataset.points.length} points (${activeDataset.name})

def objective_function(params, freqs, z_exp, weighting="${weighting}"):
    # Evaluates complex impedance residuals:
    # r = (Z_calc - Z_exp) * sqrt(weight)
    pass

# Run Fit with parameter bounds and Lin-KK validation
# Reduced Chi-Square: ${fitReport?.reducedChiSquare?.toExponential(3) || "Pending"}
# R-Squared: ${fitReport?.rSquared?.toFixed(5) || "Pending"}
`}
                  </pre>
                </div>
              )}

              {(activeChartTab as string) === "synthetic_noise" && (
                <div className="w-full">
                  <SyntheticNoiseStressStudio
                    initialTopology={selectedTopology}
                    onExportToCNLS={(dataset, topo) => {
                      setActiveDataset(dataset);
                      setSelectedTopology(topo);
                      setEditableParams(extractAdjustableParameters(topo));
                      setActiveChartTab("nyquist");
                    }}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Optimized Parameters & Error Table */}
          {fitReport && (
            <div className="p-3.5 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <BarChart2 className="w-3.5 h-3.5 text-sky-400" />
                  Optimized Physical Parameters &amp; Asymptotic Uncertainty (&plusmn;&sigma;)
                </span>
                <span className="text-[10px] text-slate-500">
                  Weighting: <strong className="text-sky-300 capitalize">{fitReport.weighting}</strong>
                </span>
              </div>

              <div className="border border-[#162032] rounded-xl overflow-hidden bg-[#050810]">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#0c1424] border-b border-[#162032] text-[10px] text-slate-400 uppercase">
                    <tr>
                      <th className="p-2.5 font-semibold">Parameter</th>
                      <th className="p-2.5 font-semibold">Initial</th>
                      <th className="p-2.5 font-semibold">Fitted Value</th>
                      <th className="p-2.5 font-semibold">Std Error ($\pm\sigma$)</th>
                      <th className="p-2.5 font-semibold">Error (%)</th>
                      <th className="p-2.5 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#162032] text-[11px]">
                    {fitReport.parameters.map((p, pIdx) => (
                      <tr key={pIdx} className="hover:bg-[#0c1424]/50 transition-colors">
                        <td className="p-2.5 text-sky-300 font-bold whitespace-nowrap">
                          {p.paramName}
                          <span className="text-[9px] text-slate-500 block font-normal">{p.paramType}</span>
                        </td>
                        <td className="p-2.5 text-slate-400 whitespace-nowrap">
                          {formatSci(p.initialValue, 3)} {p.unit}
                        </td>
                        <td className="p-2.5 text-emerald-300 font-bold whitespace-nowrap">
                          {formatSci(p.fittedValue, 4)} {p.unit}
                        </td>
                        <td className="p-2.5 text-slate-300 whitespace-nowrap">
                          {p.isFixed ? "—" : p.stdError == null ? "Unavailable" : `± ${formatSci(p.stdError, 3)}`}
                        </td>
                        <td className="p-2.5 whitespace-nowrap">
                          {p.isFixed ? (
                            <span className="text-slate-500 text-[10px]">Locked</span>
                          ) : (
                            <span
                              className={`font-bold ${
                                p.percentError != null && p.percentError < 5
                                  ? "text-emerald-400"
                                  : p.percentError != null && p.percentError < 15
                                  ? "text-amber-400"
                                  : "text-rose-400"
                              }`}
                            >
                              {p.percentError == null ? "Unavailable" : `±${p.percentError}%`}
                            </span>
                          )}
                        </td>
                        <td className="p-2.5 whitespace-nowrap">
                          {p.isFixed ? (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                              Fixed
                            </span>
                          ) : (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                              Optimized
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* File Import Modal */}
      {isImportModalOpen && (
        <AccessibleModal
          open
          onClose={() => setIsImportModalOpen(false)}
          label="Import impedance data"
          overlayClassName="p-4 bg-black/80 backdrop-blur-sm animate-in fade-in"
          panelClassName="bg-[#090e18] border border-[#1e2d46] rounded-2xl w-full max-w-2xl p-5 shadow-2xl space-y-4"
        >
            <div className="flex items-center justify-between border-b border-[#162032] pb-3">
              <div className="flex items-center gap-2">
                <Upload className="w-5 h-5 text-sky-400" />
                <h3 className="text-sm font-bold text-white">Import Experimental EIS Data</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsImportModalOpen(false)}
                className="text-slate-400 hover:text-white text-xs font-mono"
              >
                ✕ Close
              </button>
            </div>

            {/* Drop Zone */}
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-[#1e2d46] hover:border-sky-400 rounded-xl p-8 text-center cursor-pointer bg-[#050810] hover:bg-[#0c1424] transition-all space-y-2"
            >
              <Upload className="w-8 h-8 text-sky-400 mx-auto" />
              <h4 className="text-xs font-bold text-white">Click or Drag &amp; Drop EIS Measurement Files</h4>
              <p className="text-[11px] text-slate-400">
                Supports BioLogic (.mpt), Gamry (.dta), Zahner (.ism, .txt), Metrohm Autolab, and tabular CSV / TSV
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".mpt,.dta,.ism,.csv,.tsv,.txt,.dat"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileUpload(file);
                }}
              />
            </div>

            {/* Manual Text Paste Option */}
            <div className="space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Or Paste Tabular Text Directly (Freq, Z_real, -Z_imag)
              </span>
              <textarea
                value={manualPasteText}
                onChange={(e) => setManualPasteText(e.target.value)}
                placeholder={`Frequency\tRe(Z)\t-Im(Z)\n100000\t0.025\t0.001\n10000\t0.026\t0.003\n...`}
                rows={4}
                className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl p-3 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-400"
              />
              <div className="flex items-center justify-between">
                <input
                  type="text"
                  value={manualFilename}
                  onChange={(e) => setManualFilename(e.target.value)}
                  className="bg-[#050810] border border-[#1e2d46] rounded-lg px-2.5 py-1 text-xs text-slate-300 w-48"
                  placeholder="Dataset Name"
                />
                <button
                  type="button"
                  disabled={!manualPasteText.trim()}
                  onClick={handleManualPasteSubmit}
                  className="px-4 py-1.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs disabled:opacity-40 transition-all"
                >
                  Parse &amp; Load Text
                </button>
              </div>
            </div>
        </AccessibleModal>
      )}
    </div>
  );
}
