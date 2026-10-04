import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useEffect, useRef, useMemo } from "react";
import { AccessibleModal } from "./AccessibleModal";
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Activity,
  Zap,
  Layers,
  RefreshCw,
  Download,
  Sliders,
  ShieldCheck,
  ShieldAlert,
  HelpCircle,
  Info,
  Sparkles,
  TrendingDown,
  Thermometer,
  Battery,
  Flame,
  Copy,
  Check,
  BarChart2,
  Radio,
  Eye,
  Trash2,
  Plus,
  ExternalLink,
  ChevronRight,
  Clock,
  Cpu,
  FileCode,
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
  AreaChart,
  Area,
} from "recharts";
import {
  ExperimentalEISDataset,
  RawEISPoint,
} from "../types/eisData";
import {
  parseEISFile,
  EXPERIMENTAL_BENCHMARKS,
  exportDatasetToCSV,
} from "../utils/eisFileParser";
import type { CircuitTopology } from "./EquivalentCircuitBuilder";
import { usePythonAnalysis } from "../hooks/usePythonAnalysis";


interface EISUploadInsightsStudioProps {
  onNavigateToCNLS?: (dataset: ExperimentalEISDataset, suggestedTopology?: CircuitTopology) => void;
  onNavigateToBatteryLab?: (dataset?: ExperimentalEISDataset) => void;
  onNavigateToCorrosionLab?: (dataset?: ExperimentalEISDataset) => void;
  onNavigateToPythonUpload?: () => void;
  onNavigateToBatchTracker?: () => void;
}

interface UploadedFileRecord {
  id: string;
  name: string;
  dataset: ExperimentalEISDataset;
  timestamp: string;
}

function decodeUploadedAnalysis(data: Record<string, unknown>): Record<string, any> {
  if (!data.datasetSummary || !data.extractedParameters || !data.kramersKronigValidation) {
    throw new Error("Python EIS analysis returned an incomplete report.");
  }
  return data;
}

export function EISUploadInsightsStudio({
  onNavigateToCNLS,
  onNavigateToBatteryLab,
  onNavigateToCorrosionLab,
  onNavigateToPythonUpload,
  onNavigateToBatchTracker,
}: EISUploadInsightsStudioProps) {
  // Domain selection: Battery vs Corrosion/Coating
  const [domain, setDomain] = useState<"battery" | "corrosion">("battery");
  const [cellTempC, setCellTempC] = useState<number>(25);
  const [cellCapacityAh, setCellCapacityAh] = useState<number>(5.0);

  // File records deck (supports multiple datasets for comparison)
  const [datasets, setDatasets] = useState<UploadedFileRecord[]>([
    {
      id: EXPERIMENTAL_BENCHMARKS[0].id,
      name: EXPERIMENTAL_BENCHMARKS[0].name,
      dataset: EXPERIMENTAL_BENCHMARKS[0],
      timestamp: "Synthetic example",
    },
  ]);
  const [activeDatasetId, setActiveDatasetId] = useState<string>(EXPERIMENTAL_BENCHMARKS[0].id);

  // Active dataset
  const activeRecord = useMemo(
    () => datasets.find((d) => d.id === activeDatasetId) || datasets[0],
    [datasets, activeDatasetId]
  );
  const activeDataset = activeRecord.dataset;

  // Analysis State
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const analysis = usePythonAnalysis("/api/python/battery-corrosion-eis", {
    action: "analyze_uploaded_eis",
    frequencies: activeDataset.points.map(p => p.frequency),
    zReal: activeDataset.points.map(p => p.zReal),
    zImag: activeDataset.points.map(p => p.zImag),
    applicationDomain: domain, cellTemperatureC: cellTempC, nominalCapacityAh: cellCapacityAh,
  }, decodeUploadedAnalysis);
  const analysisResult = analysis.result;
  const isAnalyzing = analysis.pending;

  // Active View Tab
  const [activeTab, setActiveTab] = useState<
    "nyquist" | "bode" | "drt" | "kramers_kronig" | "circuit_match" | "executive_dossier" | "deck_overlay" | "batch_degradation"
  >("nyquist");

  // File Upload states
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [isPasteModalOpen, setIsPasteModalOpen] = useState<boolean>(false);
  const [pastedText, setPastedText] = useState<string>("");
  const [pastedFilename, setPastedFilename] = useState<string>("clipboard_eis.csv");
  const [copiedNotification, setCopiedNotification] = useState<boolean>(false);

  // Handle File Upload from Input or Drop (Single or Batch)
  const handleProcessRawFiles = async (files: FileList | File[]) => {
    const fileList = Array.from(files);
    if (fileList.length === 0) return;

    const newRecords: UploadedFileRecord[] = [];
    for (const file of fileList) {
      try {
        const text = await file.text();
        const parsedDataset = parseEISFile(text, file.name);

        newRecords.push({
          id: `upload-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
          name: file.name,
          dataset: parsedDataset,
          timestamp: new Date().toLocaleTimeString(),
        });
      } catch (err: any) {
        setAnalysisError(`Failed to parse file "${file.name}": ${err.message}`);
      }
    }

    if (newRecords.length > 0) {
      setDatasets((prev) => [...newRecords, ...prev]);
      setActiveDatasetId(newRecords[0].id);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleProcessRawFiles(e.dataTransfer.files);
    }
  };

  const handlePasteSubmit = () => {
    if (!pastedText.trim()) return;
    try {
      const parsed = parseEISFile(pastedText, pastedFilename || "clipboard.csv");
      const newRecord: UploadedFileRecord = {
        id: `paste-${Date.now()}`,
        name: pastedFilename || "Pasted Spectrum",
        dataset: parsed,
        timestamp: new Date().toLocaleTimeString(),
      };
      setDatasets((prev) => [newRecord, ...prev]);
      setActiveDatasetId(newRecord.id);
      setIsPasteModalOpen(false);
      setPastedText("");
    } catch (err: any) {
      setAnalysisError(`Failed to parse pasted text: ${err.message}`);
    }
  };

  const handleSelectBenchmark = (bench: ExperimentalEISDataset) => {
    const existing = datasets.find((d) => d.id === bench.id);
    if (existing) {
      setActiveDatasetId(existing.id);
    } else {
      const newRecord: UploadedFileRecord = {
        id: bench.id,
        name: bench.name,
        dataset: bench,
        timestamp: "Synthetic example",
      };
      setDatasets((prev) => [newRecord, ...prev]);
      setActiveDatasetId(bench.id);
    }
  };

  const handleDeleteRecord = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (datasets.length <= 1) return;
    setDatasets((prev) => prev.filter((d) => d.id !== id));
    if (activeDatasetId === id) {
      const remaining = datasets.filter((d) => d.id !== id);
      setActiveDatasetId(remaining[0].id);
    }
  };

  const handleExportCSV = () => {
    if (!activeDataset) return;
    const csvContent = exportDatasetToCSV(activeDataset);
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${activeDataset.name || "eis_dataset"}_cleaned.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportJSONReport = () => {
    if (!analysisResult) return;
    const payload = {
      dataset: activeDataset.name,
      dataOrigin: activeDataset.source === "benchmark" ? "synthetic circuit example" : "user upload; provenance unverified",
      domain,
      cellTempC,
      cellCapacityAh,
      timestamp: new Date().toISOString(),
      analysis: analysisResult,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${activeDataset.name || "eis"}_deep_insights.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopyMarkdownSummary = () => {
    if (!analysisResult) return;
    const params = analysisResult.extractedParameters || {};
    const kk = analysisResult.kramersKronigValidation || {};
    const eec = analysisResult.recommendedCircuit || {};

    const md = `### Electrochemical Impedance Spectroscopy (EIS) Automated Insight Dossier
**Sample:** ${activeDataset.name}
**Data origin:** ${activeDataset.source === "benchmark" ? "Synthetic circuit example, not an experiment" : "User upload; provenance unverified"}
**Application Domain:** ${domain.toUpperCase()} | **Cell Temperature:** ${cellTempC}°C
**Date Analyzed:** ${new Date().toLocaleString()}

#### 1. Extracted Physical Parameters
- **Ohmic Resistance (R₀ / R_s):** ${params.r0_ohm} Ω
- **Inductance (L_s):** ${params.inductance_nH} nH
- **SEI / Surface Film Resistance (R_sei):** ${params.rSei_ohm} Ω (Apex: ${params.fApexSei_Hz} Hz, C_sei: ${params.cSei_uF} μF)
- **Charge Transfer Resistance (R_ct):** ${params.rCt_ohm} Ω (Apex: ${params.fApexCt_Hz} Hz, C_dl: ${params.cDl_uF} μF)
- **Exchange Current (I₀):** ${params.exchangeCurrent_mA} mA
- **Warburg Coefficient (σ):** ${params.warburgSigma} Ω·s^-0.5 (Linearity R²: ${params.warburgR2})

#### 2. Kramers-Kronig Validation
- **Status:** ${kk.status} (${kk.grade})
- **Pseudo-χ²:** ${kk.pseudoChiSq}

#### 3. Recommended Equivalent Electric Circuit (EEC)
- **Model:** ${eec.name}
- **Topology:** \`${eec.topologyCode}\`

#### 4. Actionable Health Insights
${(analysisResult.engineeringInsights || [])
  .map((ins: any) => `- **${ins.title}:** ${ins.value} - ${ins.description}`)
  .join("\n")}
`;

    navigator.clipboard.writeText(md);
    setCopiedNotification(true);
    setTimeout(() => setCopiedNotification(false), 2500);
  };

  const handleSendToCNLSStudio = async () => {
    if (!onNavigateToCNLS || !analysisResult) return;
    const { STANDARD_CIRCUIT_PRESETS } = await import("./EquivalentCircuitBuilder");
    // Map recommended circuit to standard preset
    const preset =
      STANDARD_CIRCUIT_PRESETS.find((p) => p.name.includes("Warburg")) || STANDARD_CIRCUIT_PRESETS[0];
    onNavigateToCNLS(activeDataset, preset);
  };

  // Prepare chart series
  const nyquistData = useMemo(() => {
    return activeDataset.points.map((p) => ({
      frequency: p.frequency,
      zReal: p.zReal,
      minusZImag: p.minusZImag,
      zMag: p.zMag,
      phaseDeg: p.phaseDeg,
    }));
  }, [activeDataset]);

  const bodeData = useMemo(() => {
    return activeDataset.points.map((p) => ({
      frequency: p.frequency,
      logFreq: Math.log10(p.frequency),
      zMag: p.zMag,
      logZMag: Math.log10(Math.max(1e-6, p.zMag)),
      phaseDeg: Math.abs(p.phaseDeg),
    }));
  }, [activeDataset]);

  const drtCurveData = useMemo(() => {
    if (!analysisResult?.drtAnalysis?.drtCurve) return [];
    return analysisResult.drtAnalysis.drtCurve;
  }, [analysisResult]);

  const kkResidualData = useMemo(() => {
    if (!analysisResult?.kramersKronigValidation?.residuals) return [];
    return analysisResult.kramersKronigValidation.residuals.map((r: any) => ({
      frequency: r.f,
      logFreq: Math.log10(r.f),
      deltaRealPct: r.delta_real_pct,
      deltaImagPct: r.delta_imag_pct,
    }));
  }, [analysisResult]);

  return (
    <div className="space-y-6">
      {/* 1. Header Banner & High-Level Domain Controls */}
      <div className="bg-gradient-to-r from-[#0a1220] via-[#0f1b2d] to-[#0a1220] border border-sky-900/40 rounded-2xl p-6 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-sky-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-500/20 to-teal-500/20 border border-sky-400/40 flex items-center justify-center text-sky-400 shadow-[0_0_15px_rgba(56,189,248,0.25)]">
                <Upload className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-bold font-mono tracking-tight text-white">
                    EIS Data Ingestion &amp; Deep Analytics Studio
                  </h1>
                  <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-400/40 rounded-full flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-sky-300" />
                    AI Deconvolution &amp; DRT
                  </span>
                </div>
                <p className="text-xs text-slate-400 font-mono">
                  Ingest BioLogic (.mpt), Gamry (.dta), Metrohm Autolab, Solartron, or CSV impedance spectra. Instant automated Kramers-Kronig, DRT, and EEC diagnosis.
                </p>
              </div>
            </div>
          </div>

          {/* Quick Domain & Operational Temperature Selector */}
          <div className="flex flex-wrap items-center gap-3 bg-[#060b14]/80 p-2 rounded-xl border border-slate-800">
            <div className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-lg border border-slate-800">
              <button
                type="button"
                onClick={() => setDomain("battery")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-mono font-bold transition-all ${
                  domain === "battery"
                    ? "bg-sky-500/20 text-sky-300 border border-sky-400/40 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Battery className="w-3.5 h-3.5 text-sky-400" />
                <span>Battery (Li/Na-ion)</span>
              </button>
              <button
                type="button"
                onClick={() => setDomain("corrosion")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-mono font-bold transition-all ${
                  domain === "corrosion"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-400/40 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <ShieldAlert className="w-3.5 h-3.5 text-emerald-400" />
                <span>Corrosion / Coatings</span>
              </button>
            </div>

            <div className="flex items-center gap-2 px-2 py-1 bg-slate-900/60 rounded-lg border border-slate-800 text-xs font-mono">
              <Thermometer className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-slate-400">Temp:</span>
              <input
                type="number"
                aria-label="Cell temperature" value={cellTempC}
                onChange={(e) => setCellTempC(parseFloat(e.target.value) || 25)}
                className="w-12 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-right text-white font-mono"
              />
              <span className="text-slate-400">°C</span>
            </div>

            {domain === "battery" && (
              <div className="flex items-center gap-2 px-2 py-1 bg-slate-900/60 rounded-lg border border-slate-800 text-xs font-mono">
                <Zap className="w-3.5 h-3.5 text-yellow-400" />
                <span className="text-slate-400">Cap:</span>
                <input
                  type="number"
                  step="0.5"
                  aria-label="Nominal capacity" value={cellCapacityAh}
                  onChange={(e) => setCellCapacityAh(parseFloat(e.target.value) || 5.0)}
                  className="w-12 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-right text-white font-mono"
                />
                <span className="text-slate-400">Ah</span>
              </div>
            )}

            {onNavigateToBatteryLab && activeDataset && (
              <button
                type="button"
                onClick={() => onNavigateToBatteryLab(activeDataset)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-400/30 text-xs font-mono font-bold transition-all"
                title="Send active lab dataset to Battery EIS Module"
              >
                <Battery className="w-3.5 h-3.5 text-sky-400" />
                <span>Send to Battery EIS</span>
              </button>
            )}

            {onNavigateToCorrosionLab && activeDataset && (
              <button
                type="button"
                onClick={() => onNavigateToCorrosionLab(activeDataset)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-400/30 text-xs font-mono font-bold transition-all"
                title="Send active lab dataset to Corrosion & Coating EIS Module"
              >
                <ShieldAlert className="w-3.5 h-3.5 text-emerald-400" />
                <span>Send to Corrosion EIS</span>
              </button>
            )}

            <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400 pl-2">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>{isAnalyzing ? "Python analysis pending" : analysisResult ? "Python analysis received" : "Python analysis unavailable"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Drag & Drop File Upload & Benchmark Deck */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Drag & Drop Zone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          className={`lg:col-span-2 border-2 border-dashed rounded-2xl p-6 transition-all flex flex-col items-center justify-center text-center cursor-pointer relative ${
            isDragOver
              ? "border-sky-400 bg-sky-500/10 shadow-[0_0_20px_rgba(56,189,248,0.2)]"
              : "border-slate-800 bg-[#080e18]/80 hover:border-slate-700 hover:bg-[#0a1220]"
          }`}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".csv,.txt,.mpt,.dta,.cor,.tsv,.dat"
            className="hidden"
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                handleProcessRawFiles(e.target.files);
              }
            }}
          />

          <div className="w-14 h-14 rounded-2xl bg-sky-500/10 border border-sky-400/30 flex items-center justify-center text-sky-400 mb-3 shadow-[0_0_15px_rgba(56,189,248,0.2)]">
            <Upload className="w-7 h-7" />
          </div>

          <h3 className="text-sm font-mono font-bold text-white mb-1">
            Drop Your Raw Potentiostat EIS File Here or Click to Browse
          </h3>
          <p className="text-xs text-slate-400 max-w-md mb-4 font-mono">
            Directly parses BioLogic EC-Lab (.mpt), Gamry Framework (.dta / .cor), Metrohm Autolab, Solartron, Zahner, and standard CSV/TXT column layouts.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-2">
            <span className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-300">
              BioLogic (.mpt)
            </span>
            <span className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-300">
              Gamry (.dta / .cor)
            </span>
            <span className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-300">
              Autolab / CSV
            </span>
            <span className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-300">
              Solartron (.cor)
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsPasteModalOpen(true);
              }}
              className="px-3 py-1 rounded bg-sky-500/20 hover:bg-sky-500/30 border border-sky-400/40 text-[11px] font-mono font-bold text-sky-300 flex items-center gap-1.5 transition-all"
            >
              <FileText className="w-3 h-3" />
              <span>Paste Raw Clipboard Text</span>
            </button>

            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (onNavigateToPythonUpload) {
                  onNavigateToPythonUpload();
                }
              }}
              className="px-3 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/40 text-[11px] font-mono font-bold text-amber-300 flex items-center gap-1.5 transition-all shadow-[0_0_10px_rgba(245,158,11,0.15)]"
            >
              <FileCode className="w-3 h-3 text-amber-400" />
              <span>Upload with Python (.py / API)</span>
            </button>
          </div>
        </div>

        {/* Curated Benchmark Quick Selector */}
        <div className="bg-[#080e18] border border-slate-800/80 rounded-2xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-sky-400" />
                Synthetic Example Library
              </span>
              <span className="text-[10px] font-mono text-slate-500">{EXPERIMENTAL_BENCHMARKS.length} Synthetic Spectra</span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono mb-3">
              These generated circuit examples are not measured laboratory data or independent validation evidence.
            </p>

            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {EXPERIMENTAL_BENCHMARKS.map((bench) => {
                const isSelected = activeDatasetId === bench.id;
                return (
                  <button
                    key={bench.id}
                    type="button"
                    onClick={() => handleSelectBenchmark(bench)}
                    className={`w-full text-left p-2 rounded-xl text-xs font-mono transition-all border ${
                      isSelected
                        ? "bg-sky-500/20 text-white border-sky-400/50 shadow-[0_0_10px_rgba(56,189,248,0.2)]"
                        : "bg-slate-900/60 text-slate-300 border-slate-800/60 hover:bg-slate-800/80"
                    }`}
                  >
                    <div className="font-bold truncate text-[11px]">{bench.name}</div>
                    <div className="text-[10px] text-slate-400 flex items-center gap-2 mt-0.5">
                      <span>{bench.metadata?.instrument || bench.source}</span>
                      <span>•</span>
                      <span>{bench.metadata?.temperatureC ?? 25}°C</span>
                      <span>•</span>
                      <span>{bench.points.length} pts</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>Current: <strong className="text-white">{activeDataset.points.length}</strong> points</span>
            <span className="text-sky-400 font-bold">{activeDataset.source === "benchmark" ? "SYNTHETIC EXAMPLE" : activeDataset.source.toUpperCase()}</span>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {(analysisError || analysis.error) && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3 text-xs font-mono text-red-300">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
          <div className="flex-1" role="alert">{analysisError || analysis.error}</div>
          <button
            type="button"
            onClick={() => { setAnalysisError(null); analysis.retry(); }}
            className="text-slate-400 hover:text-white"
          >
            Retry analysis
          </button>
        </div>
      )}

      <p role="status" className="text-xs text-slate-400 font-mono">
        {isAnalyzing ? "Calculating current inputs…" : analysisResult ? "Screening only; this report does not establish experimental validity or standards compliance." : "Unavailable: no computed analysis for the current inputs."}
      </p>
      {/* 3. Deep Extraction Summary KPI Cards */}
      {analysisResult && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {/* R0 Bulk Intercept */}
          <div className="bg-[#080e18] border border-slate-800/90 rounded-xl p-3.5 space-y-1">
            <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>Bulk Ohmic (R₀)</span>
              <Activity className="w-3 h-3 text-sky-400" />
            </div>
            <div className="text-lg font-mono font-bold text-white">
              {analysisResult.extractedParameters?.r0_ohm >= 1
                ? `${analysisResult.extractedParameters.r0_ohm.toFixed(2)} Ω`
                : `${(analysisResult.extractedParameters.r0_ohm * 1000).toFixed(1)} mΩ`}
            </div>
            <div className="text-[10px] font-mono text-slate-400">
              L: {analysisResult.extractedParameters?.inductance_nH?.toFixed(1) || 0} nH
            </div>
          </div>

          {/* SEI Film Resistance */}
          <div className="bg-[#080e18] border border-slate-800/90 rounded-xl p-3.5 space-y-1">
            <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>SEI Film (R_sei)</span>
              <Layers className="w-3 h-3 text-teal-400" />
            </div>
            <div className="text-lg font-mono font-bold text-teal-300">
              {analysisResult.extractedParameters?.rSei_ohm > 0
                ? analysisResult.extractedParameters.rSei_ohm >= 1
                  ? `${analysisResult.extractedParameters.rSei_ohm.toFixed(2)} Ω`
                  : `${(analysisResult.extractedParameters.rSei_ohm * 1000).toFixed(1)} mΩ`
                : "Merged / Clean"}
            </div>
            <div className="text-[10px] font-mono text-slate-400">
              Apex: {analysisResult.extractedParameters?.fApexSei_Hz?.toFixed(0) || 0} Hz
            </div>
          </div>

          {/* Charge Transfer R_ct */}
          <div className="bg-[#080e18] border border-slate-800/90 rounded-xl p-3.5 space-y-1">
            <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>Charge Transfer (R_ct)</span>
              <Zap className="w-3 h-3 text-amber-400" />
            </div>
            <div className="text-lg font-mono font-bold text-amber-300">
              {analysisResult.extractedParameters?.rCt_ohm >= 1
                ? `${analysisResult.extractedParameters.rCt_ohm.toFixed(2)} Ω`
                : `${(analysisResult.extractedParameters.rCt_ohm * 1000).toFixed(1)} mΩ`}
            </div>
            <div className="text-[10px] font-mono text-slate-400">
              C_dl: {analysisResult.extractedParameters?.cDl_uF?.toFixed(1) || 0} μF
            </div>
          </div>

          {/* Exchange Current I0 */}
          <div className="bg-[#080e18] border border-slate-800/90 rounded-xl p-3.5 space-y-1">
            <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>Exchange Current (I₀)</span>
              <Flame className="w-3 h-3 text-rose-400" />
            </div>
            <div className="text-lg font-mono font-bold text-rose-300">
              {analysisResult.extractedParameters?.exchangeCurrent_mA?.toFixed(1)} mA
            </div>
            <div className="text-[10px] font-mono text-slate-400">
              Kinetics Rate Factor
            </div>
          </div>

          {/* Warburg Diffusion */}
          <div className="bg-[#080e18] border border-slate-800/90 rounded-xl p-3.5 space-y-1">
            <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>Warburg (σ)</span>
              <TrendingDown className="w-3 h-3 text-indigo-400" />
            </div>
            <div className="text-lg font-mono font-bold text-indigo-300">
              {analysisResult.extractedParameters?.hasWarburg
                ? `${analysisResult.extractedParameters.warburgSigma.toFixed(3)}`
                : "Capacitive"}
            </div>
            <div className="text-[10px] font-mono text-slate-400">
              R²: {analysisResult.extractedParameters?.warburgR2 || "N/A"}
            </div>
          </div>

          {/* Kramers-Kronig Status */}
          <div className="bg-[#080e18] border border-slate-800/90 rounded-xl p-3.5 space-y-1">
            <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>Lin-KK Linearity</span>
              <ShieldCheck className="w-3 h-3 text-emerald-400" />
            </div>
            <div
              className={`text-sm font-mono font-bold truncate ${
                analysisResult.kramersKronigValidation?.grade === "PASSED" ? "text-emerald-300" : "text-amber-300"
              }`}
            >
              {analysisResult.kramersKronigValidation?.grade ?? "NOT_EVALUATED"}
            </div>
            <div className="text-[10px] font-mono text-slate-400 truncate">
              χ²: {analysisResult.kramersKronigValidation?.pseudoChiSq?.toExponential(2)}
            </div>
          </div>
        </div>
      )}

      {/* 4. Main Multi-Tab Interactive Diagnostic Lab */}
      <div className="bg-[#080e18] border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        {/* Navigation Tabs Bar */}
        <div className="flex flex-wrap items-center justify-between p-3 border-b border-slate-800 bg-slate-900/60 gap-3">
          <div className="flex items-center gap-1.5 overflow-x-auto">
            <button
              type="button"
              onClick={() => setActiveTab("nyquist")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold transition-all whitespace-nowrap flex items-center gap-2 ${
                activeTab === "nyquist"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-400/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>1. Nyquist &amp; Apex Map</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("bode")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold transition-all whitespace-nowrap flex items-center gap-2 ${
                activeTab === "bode"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-400/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <BarChart2 className="w-3.5 h-3.5" />
              <span>2. Dual Bode &amp; Phase</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("drt")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold transition-all whitespace-nowrap flex items-center gap-2 ${
                activeTab === "drt"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-400/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-sky-300" />
              <span>3. Continuous DRT Spectrum</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("kramers_kronig")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold transition-all whitespace-nowrap flex items-center gap-2 ${
                activeTab === "kramers_kronig"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-400/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>4. Kramers-Kronig Residuals</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("circuit_match")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold transition-all whitespace-nowrap flex items-center gap-2 ${
                activeTab === "circuit_match"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-400/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              <span>5. Recommended EEC Model</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("executive_dossier")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold transition-all whitespace-nowrap flex items-center gap-2 ${
                activeTab === "executive_dossier"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-400/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <FileText className="w-3.5 h-3.5 text-amber-400" />
              <span>6. Executive Health Dossier</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("batch_degradation")}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold transition-all whitespace-nowrap flex items-center gap-2 ${
                activeTab === "batch_degradation" || activeTab === "deck_overlay"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-400/40 shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              <span>7. Batch EIS &amp; 3D Degradation Tracker</span>
              <span className="px-1.5 py-0.5 rounded text-[9px] bg-purple-500/30 text-purple-200 border border-purple-400/40 font-bold">
                PRO
              </span>
            </button>
          </div>

          {/* Export Action Tools */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleExportCSV}
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] font-mono text-slate-300 flex items-center gap-1.5 transition-all"
              title="Download Cleaned CSV"
            >
              <Download className="w-3 h-3 text-slate-400" />
              <span>CSV</span>
            </button>

            <button
              type="button"
              onClick={handleExportJSONReport}
              disabled={!analysisResult}
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] font-mono text-slate-300 flex items-center gap-1.5 transition-all"
              title="Download JSON Report"
            >
              <Download className="w-3 h-3 text-slate-400" />
              <span>JSON</span>
            </button>

            <button
              type="button"
              onClick={handleCopyMarkdownSummary}
              disabled={!analysisResult}
              className="px-2.5 py-1 rounded bg-sky-500/20 hover:bg-sky-500/30 border border-sky-400/40 text-[11px] font-mono text-sky-300 flex items-center gap-1.5 transition-all"
            >
              {copiedNotification ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              <span>{copiedNotification ? "Copied!" : "Copy Report"}</span>
            </button>
          </div>
        </div>

        {/* View Tab Body */}
        <div className="p-6">
          {/* TAB 1: NYQUIST PLOT & APEX IDENTIFICATION */}
          {activeTab === "nyquist" && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-mono font-bold text-white flex items-center gap-2">
                    <Activity className="w-4 h-4 text-sky-400" />
                    Complex Plane Nyquist Diagram (-Z&apos;&apos; vs Z&apos;)
                  </h3>
                  <p className="text-xs text-slate-400 font-mono">
                    High-frequency intercept denotes bulk solution resistance R₀; local semicircle apexes signify individual interphase and charge-transfer relaxation loops.
                  </p>
                </div>

                <div className="flex items-center gap-3 text-xs font-mono text-slate-400 bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-800">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-sky-400 inline-block" />
                    <span>{activeDataset.source === "benchmark" ? "Synthetic circuit data" : "Uploaded observations"}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-400 inline-block" />
                    <span>Apex Frequencies</span>
                  </span>
                </div>
              </div>

              <div className="h-96 w-full bg-[#050912] rounded-xl border border-slate-800/80 p-4">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={nyquistData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                      dataKey="zReal"
                      type="number"
                      domain={["auto", "auto"]}
                      stroke="#64748b"
                      fontSize={11}
                      tickFormatter={(v) => v.toFixed(3)}
                      label={{ value: "Real Impedance Z' (Ω)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                    />
                    <YAxis
                      dataKey="minusZImag"
                      type="number"
                      domain={["auto", "auto"]}
                      stroke="#64748b"
                      fontSize={11}
                      tickFormatter={(v) => v.toFixed(3)}
                      label={{ value: "-Im(Z) -Z'' (Ω)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const pt = payload[0].payload;
                          return (
                            <div className="bg-slate-900/95 border border-sky-500/40 rounded-xl p-3 shadow-xl font-mono text-xs space-y-1">
                              <div className="text-sky-300 font-bold">
                                f = {pt.frequency >= 1000 ? `${(pt.frequency / 1000).toFixed(2)} kHz` : `${pt.frequency.toFixed(2)} Hz`}
                              </div>
                              <div className="text-white">Z&apos; = {pt.zReal.toFixed(4)} Ω</div>
                              <div className="text-white">-Z&apos;&apos; = {pt.minusZImag.toFixed(4)} Ω</div>
                              <div className="text-slate-400">|Z| = {pt.zMag.toFixed(4)} Ω</div>
                              <div className="text-slate-400">Phase = {pt.phaseDeg.toFixed(1)}°</div>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="minusZImag"
                      stroke="#38bdf8"
                      strokeWidth={2}
                      dot={{ r: 3, fill: "#0284c7" }}
                      activeDot={{ r: 6, fill: "#38bdf8" }}
                      name="Experimental Z(ω)"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* Resolved Apexes Table */}
              {analysisResult?.apexPeaks && analysisResult.apexPeaks.length > 0 && (
                <div className="bg-slate-900/40 rounded-xl border border-slate-800 p-4 space-y-2">
                  <div className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                    Identified Semicircle Relaxation Apexes
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
                    {analysisResult.apexPeaks.map((peak: any, idx: number) => (
                      <div key={idx} className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 font-mono text-xs space-y-1">
                        <div className="flex items-center justify-between text-sky-400 font-bold">
                          <span>Apex Loop #{idx + 1}</span>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/10 text-sky-300">
                            {peak.frequency_Hz >= 1000 ? `${(peak.frequency_Hz / 1000).toFixed(1)} kHz` : `${peak.frequency_Hz} Hz`}
                          </span>
                        </div>
                        <div className="text-white text-[11px] font-semibold">{peak.process}</div>
                        <div className="text-slate-400 text-[10px]">
                          τ: {peak.tau_seconds} s • Est. R: {peak.estimated_r_Ohm} Ω • Est. C: {peak.estimated_c_uF} μF
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: DUAL BODE & PHASE ANGLE */}
          {activeTab === "bode" && (
            <div className="space-y-6">
              <div>
                <h3 className="text-sm font-mono font-bold text-white flex items-center gap-2">
                  <BarChart2 className="w-4 h-4 text-sky-400" />
                  Bode Representation: Impedance Modulus |Z| and Phase Angle θ vs Frequency
                </h3>
                <p className="text-xs text-slate-400 font-mono">
                  Magnitude plateau at high frequency confirms electrolyte bulk resistance; mid-frequency phase peaks correspond to interphase dielectric transitions.
                </p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Bode Modulus */}
                <div className="bg-[#050912] rounded-xl border border-slate-800/80 p-4 space-y-2">
                  <div className="text-xs font-mono font-bold text-slate-300 flex items-center justify-between">
                    <span>Impedance Modulus |Z| vs log₁₀(f)</span>
                    <span className="text-sky-400 text-[10px]">Log scale (Ω)</span>
                  </div>
                  <div className="h-80 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={bodeData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis
                          dataKey="logFreq"
                          type="number"
                          stroke="#64748b"
                          fontSize={11}
                          domain={["auto", "auto"]}
                          label={{ value: "log₁₀(Frequency / Hz)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                        />
                        <YAxis
                          dataKey="zMag"
                          type="number"
                          stroke="#64748b"
                          fontSize={11}
                          domain={["auto", "auto"]}
                          label={{ value: "|Z| (Ω)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }}
                        />
                        <Tooltip
                          content={({ active, payload }) => {
                            if (active && payload && payload.length) {
                              const pt = payload[0].payload;
                              return (
                                <div className="bg-slate-900 border border-sky-500/40 rounded-xl p-2.5 font-mono text-xs text-white">
                                  <div>Freq: {pt.frequency.toFixed(2)} Hz</div>
                                  <div>|Z|: {pt.zMag.toFixed(4)} Ω</div>
                                </div>
                              );
                            }
                            return null;
                          }}
                        />
                        <Line type="monotone" dataKey="zMag" stroke="#38bdf8" strokeWidth={2} dot={{ r: 2 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Bode Phase Angle */}
                <div className="bg-[#050912] rounded-xl border border-slate-800/80 p-4 space-y-2">
                  <div className="text-xs font-mono font-bold text-slate-300 flex items-center justify-between">
                    <span>Phase Angle |θ| vs log₁₀(f)</span>
                    <span className="text-amber-400 text-[10px]">Degrees (°)</span>
                  </div>
                  <div className="h-80 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={bodeData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis
                          dataKey="logFreq"
                          type="number"
                          stroke="#64748b"
                          fontSize={11}
                          domain={["auto", "auto"]}
                          label={{ value: "log₁₀(Frequency / Hz)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                        />
                        <YAxis
                          dataKey="phaseDeg"
                          type="number"
                          stroke="#64748b"
                          fontSize={11}
                          domain={[0, 90]}
                          label={{ value: "Phase Angle (deg)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }}
                        />
                        <Tooltip
                          content={({ active, payload }) => {
                            if (active && payload && payload.length) {
                              const pt = payload[0].payload;
                              return (
                                <div className="bg-slate-900 border border-amber-500/40 rounded-xl p-2.5 font-mono text-xs text-white">
                                  <div>Freq: {pt.frequency.toFixed(2)} Hz</div>
                                  <div>Phase: {pt.phaseDeg.toFixed(2)}°</div>
                                </div>
                              );
                            }
                            return null;
                          }}
                        />
                        <Line type="monotone" dataKey="phaseDeg" stroke="#f59e0b" strokeWidth={2} dot={{ r: 2 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: CONTINUOUS DRT SPECTRUM */}
          {activeTab === "drt" && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-mono font-bold text-white flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-sky-400" />
                    Distribution of Relaxation Times (DRT) Continuous Deconvolution
                  </h3>
                  <p className="text-xs text-slate-400 font-mono">
                    Regularized inversion of Z(ω) resolves overlapping RC semi-circles without requiring an arbitrary equivalent circuit assumption.
                  </p>
                </div>
              </div>

              <div className="h-96 w-full bg-[#050912] rounded-xl border border-slate-800/80 p-4">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={drtCurveData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                    <defs>
                      <linearGradient id="drtGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                      dataKey="logTau"
                      type="number"
                      stroke="#64748b"
                      fontSize={11}
                      domain={["auto", "auto"]}
                      label={{ value: "log₁₀(Relaxation Time τ / s)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                    />
                    <YAxis
                      dataKey="gamma_Ohm"
                      stroke="#64748b"
                      fontSize={11}
                      label={{ value: "DRT Amplitude γ(ln τ) (Ω)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const pt = payload[0].payload;
                          return (
                            <div className="bg-slate-900 border border-sky-500/40 rounded-xl p-3 font-mono text-xs space-y-1">
                              <div className="text-sky-300 font-bold">log₁₀(τ) = {pt.logTau.toFixed(3)}</div>
                              <div className="text-white">τ = {pt.tau_s?.toExponential(3)} s</div>
                              <div className="text-white">f_equiv = {pt.charFreq_Hz >= 1000 ? `${(pt.charFreq_Hz / 1000).toFixed(1)} kHz` : `${pt.charFreq_Hz?.toFixed(1)} Hz`}</div>
                              <div className="text-emerald-400 font-bold">γ = {pt.gamma_Ohm?.toFixed(4)} Ω</div>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Area type="monotone" dataKey="gamma_Ohm" stroke="#38bdf8" strokeWidth={2.5} fillOpacity={1} fill="url(#drtGradient)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* DRT Peaks attribution */}
              {analysisResult?.drtAnalysis?.identifiedPeaks && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {analysisResult.drtAnalysis.identifiedPeaks.map((peak: any, idx: number) => (
                    <div key={idx} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 font-mono text-xs space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sky-400 font-bold text-xs">Peak #{idx + 1}</span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-400/30">
                          {peak.domain}
                        </span>
                      </div>
                      <div className="text-sm font-bold text-white">{peak.process}</div>
                      <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400 pt-1 border-t border-slate-800">
                        <div>τ: <span className="text-white font-bold">{peak.tau_s?.toExponential(2)} s</span></div>
                        <div>f: <span className="text-white font-bold">{peak.charFreq_Hz?.toFixed(1)} Hz</span></div>
                        <div>Amplitude: <span className="text-emerald-400 font-bold">{peak.gammaHeight_Ohm} Ω</span></div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: KRAMERS-KRONIG RESIDUALS */}
          {activeTab === "kramers_kronig" && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-mono font-bold text-white flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    Kramers-Kronig (Lin-KK) Linearity, Causality &amp; Stationarity Test
                  </h3>
                  <p className="text-xs text-slate-400 font-mono">
                    Verifies whether the physical measurement satisfies the four core Kramers-Kronig conditions: Linearity, Causality, Stability, and Time-Invariance.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <span className="px-3 py-1 rounded-lg text-xs font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-400/40">
                    {analysisResult?.kramersKronigValidation?.status}
                  </span>
                </div>
              </div>

              <div className="h-80 w-full bg-[#050912] rounded-xl border border-slate-800/80 p-4">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={kkResidualData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                      dataKey="logFreq"
                      type="number"
                      stroke="#64748b"
                      fontSize={11}
                      domain={["auto", "auto"]}
                      label={{ value: "log₁₀(Frequency / Hz)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                    />
                    <YAxis
                      stroke="#64748b"
                      fontSize={11}
                      domain={[-3, 3]}
                      label={{ value: "Residual Δ / |Z| (%)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const pt = payload[0].payload;
                          return (
                            <div className="bg-slate-900 border border-emerald-500/40 rounded-xl p-3 font-mono text-xs text-white">
                              <div>Freq: {pt.frequency?.toFixed(2)} Hz</div>
                              <div className="text-sky-300">Δ Real: {pt.deltaRealPct?.toFixed(2)}%</div>
                              <div className="text-emerald-300">Δ Imag: {pt.deltaImagPct?.toFixed(2)}%</div>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />
                    <ReferenceLine y={1} stroke="#eab308" strokeDasharray="3 3" />
                    <ReferenceLine y={-1} stroke="#eab308" strokeDasharray="3 3" />
                    <Line type="monotone" dataKey="deltaRealPct" stroke="#38bdf8" dot={{ r: 2 }} name="Real Residual %" />
                    <Line type="monotone" dataKey="deltaImagPct" stroke="#34d399" dot={{ r: 2 }} name="Imag Residual %" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              <div className="bg-slate-900/40 rounded-xl border border-slate-800 p-4 font-mono text-xs space-y-2">
                <div className="text-slate-300 font-bold flex items-center gap-2">
                  <Info className="w-4 h-4 text-sky-400" />
                  How to Interpret Kramers-Kronig Residuals:
                </div>
                <p className="text-slate-400">
                  • Residuals within ±1% across all decades indicate a fully linear, stable measurement suitable for rigorous equivalent circuit fitting.
                  <br />
                  • Residual systematic drift (e.g. rising residuals at low frequency &lt; 0.1 Hz) typically indicates cell temperature fluctuation or open-circuit voltage relaxation during the measurement.
                </p>
              </div>
            </div>
          )}

          {/* TAB 5: RECOMMENDED EQUIVALENT ELECTRIC CIRCUIT (EEC) */}
          {activeTab === "circuit_match" && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-mono font-bold text-white flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-cyan-400" />
                    Automated Equivalent Electric Circuit (EEC) Recommendation
                  </h3>
                  <p className="text-xs text-slate-400 font-mono">
                    Topology automatically matched to the number of resolved relaxation peaks, low-frequency phase slope, and physical cell boundaries.
                  </p>
                </div>

                {onNavigateToCNLS && (
                  <button
                    type="button"
                    onClick={handleSendToCNLSStudio}
                    className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-mono font-bold text-xs flex items-center gap-2 shadow-lg transition-all"
                  >
                    <span>Open in CNLS Fitting Studio</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="bg-[#050912] border border-cyan-900/40 rounded-xl p-5 space-y-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
                  <div>
                    <div className="text-xs font-mono text-cyan-400 uppercase tracking-wider">Recommended Model</div>
                    <div className="text-base font-mono font-bold text-white">
                      {analysisResult?.recommendedCircuit?.name || "Standard Randles Cell"}
                    </div>
                  </div>
                  <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 font-mono text-xs text-slate-300">
                    Topology: <code className="text-cyan-300 font-bold">{analysisResult?.recommendedCircuit?.topologyCode}</code>
                  </div>
                </div>

                {/* Elements Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left font-mono text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 text-[11px]">
                        <th className="pb-2">Element</th>
                        <th className="pb-2">Estimated Seed Value</th>
                        <th className="pb-2">Unit</th>
                        <th className="pb-2">Physical Electrochemical Mechanism</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {(analysisResult?.recommendedCircuit?.elements || []).map((el: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-900/40">
                          <td className="py-2.5 font-bold text-cyan-300">{el.element}</td>
                          <td className="py-2.5 text-white font-bold">{el.value}</td>
                          <td className="py-2.5 text-slate-400">{el.unit}</td>
                          <td className="py-2.5 text-slate-300 text-[11px]">{el.meaning}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

                {/* BISQUERT TRANSMISSION LINE MODEL (TLM) DECONVOLUTION SECTION */}
                {analysisResult?.bisquertTLM && (
                  <div className="bg-[#030712] border border-amber-500/40 rounded-xl p-5 space-y-4 mt-6">
                    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 border-b border-amber-500/20 pb-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-amber-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                            Bisquert Transmission Line Model (TLM) Deconvolution
                          </span>
                          <span className={`text-[10px] px-2 py-0.5 rounded font-bold font-mono border ${
                            analysisResult.bisquertTLM.isPorousTransmissionLine
                              ? "bg-emerald-500/20 text-emerald-300 border-emerald-400/40"
                              : "bg-slate-800 text-slate-300 border-slate-700"
                          }`}>
                            {analysisResult.bisquertTLM.isPorousTransmissionLine ? "Porous TLM Detected" : "Standard Interfacial Mode"}
                          </span>
                        </div>
                        <div className="text-sm font-mono font-bold text-white mt-1">
                          {analysisResult.bisquertTLM.circuitModel}
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
                        <div className="px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
                          Boundary: <span className="text-amber-300 font-bold uppercase">{analysisResult.bisquertTLM.boundaryCondition}</span>
                        </div>
                        <div className="px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
                          Confidence: <span className="text-emerald-400 font-bold">{Math.round((analysisResult.bisquertTLM.confidence || 0.9) * 100)}%</span>
                        </div>
                        <div className="px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
                          45° Slope: <span className="text-sky-300 font-bold">{analysisResult.bisquertTLM.diagnostics?.highFrequencySlope45Deg?.toFixed(2) || "1.00"}</span>
                        </div>
                      </div>
                    </div>

                    {/* Physical Interpretation Statement */}
                    {analysisResult.bisquertTLM.physicalInterpretation && (
                      <p className="text-xs text-amber-200/90 font-mono bg-amber-950/20 border border-amber-800/30 rounded-lg p-3">
                        {analysisResult.bisquertTLM.physicalInterpretation}
                      </p>
                    )}

                    {/* Bisquert TLM Identified Components Table */}
                    <div className="space-y-2">
                      <div className="text-xs font-mono font-bold text-slate-200 flex items-center justify-between">
                        <span>Identified TLM Circuit Elements</span>
                        <code className="text-[11px] text-amber-300/80">{analysisResult.bisquertTLM.circuitCode}</code>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left font-mono text-xs">
                          <thead>
                            <tr className="border-b border-slate-800 text-slate-400 text-[11px]">
                              <th className="pb-2">Element</th>
                              <th className="pb-2">Component Name</th>
                              <th className="pb-2">Fitted Value</th>
                              <th className="pb-2">Unit</th>
                              <th className="pb-2">Conf.</th>
                              <th className="pb-2">Electrochemical Role</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60">
                            {(analysisResult.bisquertTLM.components || []).map((comp: any, idx: number) => (
                              <tr key={idx} className="hover:bg-slate-900/40">
                                <td className="py-2 font-bold text-amber-400">{comp.element}</td>
                                <td className="py-2 text-slate-200 font-semibold">{comp.name}</td>
                                <td className="py-2 text-white font-bold">{comp.value}</td>
                                <td className="py-2 text-slate-400">{comp.unit}</td>
                                <td className="py-2 text-emerald-400 font-bold">
                                  {Math.round((comp.confidence || 0.95) * 100)}%
                                </td>
                                <td className="py-2 text-slate-300 text-[11px]">{comp.physicalMeaning}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Porous Diagnostics KPI Cards */}
                    {analysisResult.bisquertTLM.diagnostics && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-1">
                          <div className="text-[10px] text-slate-400 font-mono">Accessibility</div>
                          <div className="text-base font-mono font-bold text-emerald-400">
                            {analysisResult.bisquertTLM.diagnostics.effectivePorosityAccessibilityPct?.toFixed(1)}%
                          </div>
                          <div className="text-[10px] text-slate-500 font-mono">Active surface reached</div>
                        </div>

                        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-1">
                          <div className="text-[10px] text-slate-400 font-mono">Pore Tortuosity (R_ion/R_s)</div>
                          <div className="text-base font-mono font-bold text-sky-400">
                            {analysisResult.bisquertTLM.diagnostics.porosityTortuosityMetric?.toFixed(2)}
                          </div>
                          <div className="text-[10px] text-slate-500 font-mono">Channel transport ratio</div>
                        </div>

                        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-1">
                          <div className="text-[10px] text-slate-400 font-mono">Transition Knee Freq</div>
                          <div className="text-base font-mono font-bold text-amber-400">
                            {analysisResult.bisquertTLM.diagnostics.transitionFrequency_Hz >= 1000
                              ? `${(analysisResult.bisquertTLM.diagnostics.transitionFrequency_Hz / 1000).toFixed(1)} kHz`
                              : `${analysisResult.bisquertTLM.diagnostics.transitionFrequency_Hz?.toFixed(1)} Hz`}
                          </div>
                          <div className="text-[10px] text-slate-500 font-mono">TLM 45° to loop turnover</div>
                        </div>

                        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-1">
                          <div className="text-[10px] text-slate-400 font-mono">Penetration Ratio (λ/L)</div>
                          <div className="text-base font-mono font-bold text-purple-400">
                            {analysisResult.bisquertTLM.diagnostics.penetrationDepthRatio?.toFixed(3)}
                          </div>
                          <div className="text-[10px] text-slate-500 font-mono">AC skin-depth / thickness</div>
                        </div>
                      </div>
                    )}

                    {/* Model Comparison Matrix (AIC / BIC) */}
                    {analysisResult.bisquertTLM.modelComparison && (
                      <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 text-xs font-mono space-y-2">
                        <div className="flex items-center justify-between text-slate-300 font-bold">
                          <span>Akaike / Bayesian Information Criterion (Model Discrimination)</span>
                          <span className="text-emerald-400 text-[11px]">
                            Preferred: {analysisResult.bisquertTLM.modelComparison.preferredModel}
                          </span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] pt-1">
                          <div className="p-2 rounded bg-slate-900 border border-slate-800">
                            <div className="text-amber-400 font-semibold">Bisquert Open (Blocking)</div>
                            <div className="text-slate-400">AIC: <span className="text-white">{analysisResult.bisquertTLM.modelComparison.aicBisquertOpen?.toFixed(1)}</span></div>
                            <div className="text-slate-400">BIC: <span className="text-white">{analysisResult.bisquertTLM.modelComparison.bicBisquertOpen?.toFixed(1)}</span></div>
                          </div>
                          <div className="p-2 rounded bg-slate-900 border border-slate-800">
                            <div className="text-cyan-400 font-semibold">Bisquert Short (Transmissive)</div>
                            <div className="text-slate-400">AIC: <span className="text-white">{analysisResult.bisquertTLM.modelComparison.aicBisquertShort?.toFixed(1)}</span></div>
                            <div className="text-slate-400">BIC: <span className="text-white">{analysisResult.bisquertTLM.modelComparison.bicBisquertShort?.toFixed(1)}</span></div>
                          </div>
                          <div className="p-2 rounded bg-slate-900 border border-slate-800">
                            <div className="text-slate-400 font-semibold">Classical Randles Cell</div>
                            <div className="text-slate-400">AIC: <span className="text-white">{analysisResult.bisquertTLM.modelComparison.aicClassicalRandles?.toFixed(1)}</span></div>
                            <div className="text-slate-400">BIC: <span className="text-white">{analysisResult.bisquertTLM.modelComparison.bicClassicalRandles?.toFixed(1)}</span></div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
            </div>
          )}

          {/* TAB 6: EXECUTIVE ENGINEERING DOSSIER */}
          {activeTab === "executive_dossier" && (
            <div className="space-y-6 font-mono">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <FileText className="w-5 h-5 text-amber-400" />
                    Executive Electrochemical Health &amp; Degradation Dossier
                  </h3>
                  <p className="text-xs text-slate-400">
                    Comprehensive diagnosis derived from multi-harmonic impedance spectroscopy, Kramers-Kronig, and DRT relaxation distribution.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleCopyMarkdownSummary}
              disabled={!analysisResult}
                  className="px-3.5 py-1.5 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 border border-sky-400/40 text-xs font-bold flex items-center gap-2 transition-all"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>{copiedNotification ? "Copied to Clipboard!" : "Copy Full Report"}</span>
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {(analysisResult?.engineeringInsights || []).map((ins: any, idx: number) => (
                  <div key={idx} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white">{ins.title}</span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                          ins.status?.includes("OPTIMAL") || ins.status?.includes("Healthy") || ins.status === "LOW"
                            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                            : "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                        }`}
                      >
                        {ins.status}
                      </span>
                    </div>
                    <div className="text-lg font-bold text-sky-300">{ins.value}</div>
                    <p className="text-xs text-slate-400 leading-relaxed">{ins.description}</p>
                  </div>
                ))}
              </div>

              <p className="text-xs text-slate-400">
                Charging limits, corrosion rates and coating lifetime are unavailable from this screening alone.
                They require independently sourced chemistry, geometry, acquisition conditions and a validated model.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 5. Paste Raw Data Modal */}
      {isPasteModalOpen && (
        <AccessibleModal
          open
          onClose={() => setIsPasteModalOpen(false)}
          label="Paste impedance data"
          overlayClassName="bg-black/80 backdrop-blur-sm p-4"
          panelClassName="bg-[#0b1320] border border-slate-700 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl"
        >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-mono font-bold text-white flex items-center gap-2">
                <FileText className="w-4 h-4 text-sky-400" />
                Paste Raw EIS Tabular / CSV Data
              </h3>
              <button
                type="button"
                onClick={() => setIsPasteModalOpen(false)}
                className="text-slate-400 hover:text-white font-mono text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-400 font-mono">
              Paste columns from Excel, Origin, or text files (e.g. Frequency, Z_Real, -Z_Imag or Im(Z)). Tab, comma, or whitespace delimited.
            </p>

            <div className="space-y-2 font-mono">
              <label className="text-xs text-slate-300">Dataset Label / Name:</label>
              <input
                type="text"
                value={pastedFilename}
                onChange={(e) => setPastedFilename(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white font-mono"
                placeholder="my_cell_eis.csv"
              />
            </div>

            <div className="space-y-2 font-mono">
              <label className="text-xs text-slate-300">Paste Data Rows:</label>
              <textarea
                rows={10}
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-sky-300 font-mono focus:outline-none focus:border-sky-500"
                placeholder={`Freq(Hz)\tZ'(Ohm)\t-Z''(Ohm)\n100000\t0.025\t-0.002\n10000\t0.038\t0.012\n1000\t0.055\t0.024\n100\t0.078\t0.035\n10\t0.110\t0.022\n1\t0.150\t0.045\n0.1\t0.220\t0.090`}
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsPasteModalOpen(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-300"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handlePasteSubmit}
                className="px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white font-mono text-xs font-bold shadow-lg"
              >
                Parse &amp; Analyze Dataset
              </button>
            </div>
        </AccessibleModal>
      )}
    </div>
  );
}


