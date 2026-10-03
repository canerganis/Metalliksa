import React, { useState, useRef, useMemo } from "react";
import { useEscapeToClose } from "./AccessibleModal";
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Zap,
  Layers,
  RefreshCw,
  Download,
  Sliders,
  Sparkles,
  Thermometer,
  Battery,
  ShieldAlert,
  ShieldCheck,
  Eye,
  Trash2,
  ExternalLink,
  Code2,
  Cpu,
  FileCode,
  X,
  Clipboard,
  Activity,
} from "lucide-react";
import { ExperimentalEISDataset, RawEISPoint } from "../types/eisData";
import { parseEISFile, EXPERIMENTAL_BENCHMARKS, exportDatasetToCSV } from "../utils/eisFileParser";

export interface EISLabDataUploaderProps {
  domain: "battery" | "corrosion";
  uploadedDataset: ExperimentalEISDataset | null;
  onDatasetLoaded: (dataset: ExperimentalEISDataset) => void;
  onClearDataset: () => void;
  onSendToCNLS?: (dataset: ExperimentalEISDataset) => void;
  onSendToEISInsights?: (dataset: ExperimentalEISDataset) => void;
  onNavigateToPythonUpload?: () => void;
  displayMode?: "overlay" | "lab-only" | "model-only";
  onDisplayModeChange?: (mode: "overlay" | "lab-only" | "model-only") => void;
  plotType?: "nyquist" | "bode";
  onPlotTypeChange?: (plot: "nyquist" | "bode") => void;
  isCompact?: boolean;
}

export function EISLabDataUploader({
  domain,
  uploadedDataset,
  onDatasetLoaded,
  onClearDataset,
  onSendToCNLS,
  onSendToEISInsights,
  onNavigateToPythonUpload,
  displayMode = "overlay",
  onDisplayModeChange,
  plotType = "nyquist",
  onPlotTypeChange,
  isCompact = false,
}: EISLabDataUploaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [isPasteOpen, setIsPasteOpen] = useState<boolean>(false);
  useEscapeToClose(isPasteOpen, () => setIsPasteOpen(false));
  const [pastedText, setPastedText] = useState<string>("");
  const [pastedName, setPastedName] = useState<string>(`${domain}_lab_eis.csv`);
  const [parseError, setParseError] = useState<string | null>(null);

  // Relevant benchmarks for the current domain
  const domainBenchmarks = useMemo(() => {
    if (domain === "battery") {
      return EXPERIMENTAL_BENCHMARKS.filter(
        (b) => b.id.includes("nmc") || b.id.includes("pemfc") || b.id.includes("battery")
      );
    } else {
      return EXPERIMENTAL_BENCHMARKS.filter(
        (b) => b.id.includes("coating") || b.id.includes("pitting") || b.id.includes("anodized") || b.id.includes("corrosion")
      );
    }
  }, [domain]);

  // Handle file drop / select
  const handleProcessFile = (file: File) => {
    setParseError(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string;
        if (!text || text.trim().length === 0) {
          throw new Error("File appears to be empty.");
        }
        const parsed = parseEISFile(text, file.name);
        if (!parsed.points || parsed.points.length < 3) {
          throw new Error("Could not extract at least 3 valid EIS frequency points (f, Z_real, -Z_imag). Check file format.");
        }
        onDatasetLoaded(parsed);
      } catch (err: any) {
        console.error("EIS parsing error:", err);
        setParseError(err.message || "Failed to parse experimental EIS file.");
      }
    };
    reader.onerror = () => setParseError("Failed to read file.");
    reader.readAsText(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleProcessFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleProcessFile(e.target.files[0]);
    }
    // reset input so same file can be re-selected if edited
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Handle pasted text
  const handleApplyPaste = () => {
    setParseError(null);
    try {
      if (!pastedText.trim()) {
        throw new Error("Pasted text is empty.");
      }
      const parsed = parseEISFile(pastedText, pastedName || "clipboard_eis.csv");
      if (!parsed.points || parsed.points.length < 3) {
        throw new Error("Could not extract valid EIS points. Please paste columns with Frequency, Z_real, and Z_imag.");
      }
      onDatasetLoaded(parsed);
      setIsPasteOpen(false);
      setPastedText("");
    } catch (err: any) {
      setParseError(err.message || "Failed to parse pasted data.");
    }
  };

  // Quick automated feature extraction from uploaded points
  const extractedMetrics = useMemo(() => {
    if (!uploadedDataset || uploadedDataset.points.length < 3) return null;
    const pts = uploadedDataset.points;

    // High-frequency intercept R0 / Rs (smallest Z' at high f)
    const sortedByFreq = [...pts].sort((a, b) => b.frequency - a.frequency);
    const highFreqPt = sortedByFreq[0];
    const r0 = highFreqPt.zReal;

    // Maximum -Z'' apex point
    let maxMinusZImag = -Infinity;
    let apexPt: RawEISPoint = pts[0];
    for (const p of pts) {
      if (p.minusZImag > maxMinusZImag) {
        maxMinusZImag = p.minusZImag;
        apexPt = p;
      }
    }

    // Low-frequency intercept
    const lowFreqPt = sortedByFreq[sortedByFreq.length - 1];
    const rTotal = lowFreqPt.zReal;
    const deltaR = Math.max(0.001, rTotal - r0);

    // Effective relaxation time & capacitance: tau = 1 / omega_apex
    const omegaApex = 2 * Math.PI * apexPt.frequency;
    const cEff_uF = omegaApex > 0 && deltaR > 0 ? (1 / (omegaApex * deltaR)) * 1e6 : 0;

    // Freq range
    const fMax = sortedByFreq[0].frequency;
    const fMin = sortedByFreq[sortedByFreq.length - 1].frequency;

    // Domain specific
    let corrosionRpore = deltaR;
    let corrosionWaterUptakePct = 0;
    if (domain === "corrosion") {
      // Brasher-Kingsbury estimation if high capacitance
      const cCoating_nF = (cEff_uF * 1e3);
      if (cCoating_nF > 0.5) {
        corrosionWaterUptakePct = Math.min(15, Math.max(0.2, (Math.log10(cCoating_nF / 0.35) / Math.log10(80)) * 100));
      }
    }

    return {
      r0,
      rTotal,
      deltaR,
      apexFreq: apexPt.frequency,
      maxMinusZImag,
      cEff_uF,
      fMin,
      fMax,
      pointsCount: pts.length,
      corrosionRpore,
      corrosionWaterUptakePct,
    };
  }, [uploadedDataset, domain]);

  return (
    <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-4 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#162032] pb-3">
        <div className="flex items-center gap-2">
          <div
            className={`w-8 h-8 rounded-xl flex items-center justify-center border ${
              domain === "battery"
                ? "bg-sky-500/10 border-sky-500/30 text-sky-400"
                : "bg-amber-500/10 border-amber-500/30 text-amber-400"
            }`}
          >
            {domain === "battery" ? <Battery className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
          </div>
          <div>
            <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-1.5">
              <span>{domain === "battery" ? "Battery Lab EIS Ingestion" : "Corrosion / Coating Lab EIS Ingestion"}</span>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#162032] text-slate-300 font-normal">
                BioLogic / Gamry / CSV / JSON
              </span>
            </h4>
            <p className="text-[10px] text-slate-400 font-mono">
              Upload real experimental potentiostat data to compare against model predictions
            </p>
          </div>
        </div>

        {/* Display Controls & View Modes */}
        <div className="flex items-center gap-2 flex-wrap">
          {onPlotTypeChange && (
            <div className="flex bg-[#050810] p-0.5 rounded-lg border border-[#162032] text-[10px] font-mono">
              <button
                type="button"
                onClick={() => onPlotTypeChange("nyquist")}
                className={`px-2 py-1 rounded transition-all ${
                  plotType === "nyquist" ? "bg-sky-500/20 text-sky-300 font-bold border border-sky-500/40" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Nyquist (-Z'' vs Z')
              </button>
              <button
                type="button"
                onClick={() => onPlotTypeChange("bode")}
                className={`px-2 py-1 rounded transition-all ${
                  plotType === "bode" ? "bg-sky-500/20 text-sky-300 font-bold border border-sky-500/40" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Bode (|Z| &amp; θ)
              </button>
            </div>
          )}

          {onDisplayModeChange && (
            <div className="flex bg-[#050810] p-0.5 rounded-lg border border-[#162032] text-[10px] font-mono">
              <button
                type="button"
                onClick={() => onDisplayModeChange("overlay")}
                className={`px-2 py-1 rounded transition-all ${
                  displayMode === "overlay" ? "bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/40" : "text-slate-400 hover:text-slate-200"
                }`}
                title="Overlay Model Curve and Lab Data Points"
              >
                Overlay
              </button>
              <button
                type="button"
                onClick={() => onDisplayModeChange("lab-only")}
                className={`px-2 py-1 rounded transition-all ${
                  displayMode === "lab-only" ? "bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40" : "text-slate-400 hover:text-slate-200"
                }`}
                title="Show Lab Data Only"
              >
                Lab Data
              </button>
              <button
                type="button"
                onClick={() => onDisplayModeChange("model-only")}
                className={`px-2 py-1 rounded transition-all ${
                  displayMode === "model-only" ? "bg-purple-500/20 text-purple-300 font-bold border border-purple-500/40" : "text-slate-400 hover:text-slate-200"
                }`}
                title="Show Simulated Model Only"
              >
                Model
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Upload Zone & Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
        {/* Dropzone / Upload button */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          className={`md:col-span-7 border-2 border-dashed rounded-xl p-3 flex flex-col items-center justify-center text-center transition-all cursor-pointer ${
            isDragOver
              ? "border-sky-400 bg-sky-500/10"
              : uploadedDataset
              ? "border-emerald-500/40 bg-emerald-950/10 hover:border-emerald-400"
              : "border-[#1e2d46] bg-[#050810] hover:border-sky-500/50"
          }`}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".mpt,.dta,.cor,.csv,.txt,.json,.ism"
            onChange={handleFileChange}
            className="hidden"
          />
          <div className="flex items-center gap-2 text-xs font-mono font-semibold text-slate-200">
            <Upload className={`w-4 h-4 ${uploadedDataset ? "text-emerald-400" : "text-sky-400"}`} />
            <span>{uploadedDataset ? "Replace Lab Dataset" : "Drag & Drop or Browse Lab EIS File"}</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono mt-0.5">
            Accepts BioLogic EC-Lab (.mpt), Gamry (.dta), Metrohm Autolab, CSV, or JSON
          </span>
        </div>

        {/* Secondary options: Paste & Benchmark */}
        <div className="md:col-span-5 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsPasteOpen(true)}
              className="flex-1 px-2.5 py-2 rounded-xl bg-[#050810] border border-[#1e2d46] hover:border-sky-500/50 text-slate-300 font-mono text-[11px] flex items-center justify-center gap-1.5 transition-all"
            >
              <Clipboard className="w-3.5 h-3.5 text-sky-400" />
              <span>Paste Columns</span>
            </button>

            {onNavigateToPythonUpload && (
              <button
                type="button"
                onClick={onNavigateToPythonUpload}
                className="px-2.5 py-2 rounded-xl bg-[#050810] border border-[#1e2d46] hover:border-emerald-500/50 text-slate-300 font-mono text-[11px] flex items-center justify-center gap-1.5 transition-all"
                title="Open Python 3.10 Ingestion Studio"
              >
                <FileCode className="w-3.5 h-3.5 text-emerald-400" />
                <span>Python</span>
              </button>
            )}
          </div>

          {/* Preset Benchmark Picker */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
              <span>Or pick a synthetic training example (not a measurement):</span>
            </div>
            <select
              value={uploadedDataset?.id || ""}
              onChange={(e) => {
                const target = domainBenchmarks.find((b) => b.id === e.target.value);
                if (target) onDatasetLoaded(target);
              }}
              className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-[11px] text-slate-200 font-mono focus:outline-none focus:border-sky-400"
            >
              <option value="" disabled>
                -- Select {domain === "battery" ? "Battery" : "Corrosion"} Training Example --
              </option>
              {domainBenchmarks.map((bm) => (
                <option key={bm.id} value={bm.id}>
                  [SYNTHETIC TRAINING] {bm.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Parse Error Notification */}
      {parseError && (
        <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{parseError}</span>
          </div>
          <button type="button" onClick={() => setParseError(null)} className="text-slate-400 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Active Uploaded Dataset Card & Extracted Parameters */}
      {uploadedDataset && extractedMetrics && (
        <div className="bg-[#050810] rounded-xl border border-emerald-500/30 p-3 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#162032] pb-2">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <div>
                <span className="text-xs font-bold text-white font-mono block">
                  {uploadedDataset.name}
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  {uploadedDataset.source.toUpperCase()} • {extractedMetrics.pointsCount} frequency points (
                  {extractedMetrics.fMin < 1 ? extractedMetrics.fMin.toFixed(3) : extractedMetrics.fMin.toFixed(1)} Hz to{" "}
                  {extractedMetrics.fMax >= 1000 ? `${(extractedMetrics.fMax / 1000).toFixed(1)} kHz` : `${extractedMetrics.fMax} Hz`})
                </span>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {onSendToCNLS && (
                <button
                  type="button"
                  onClick={() => onSendToCNLS(uploadedDataset)}
                  className="px-2.5 py-1 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 border border-sky-500/30 text-sky-300 font-mono text-[10px] flex items-center gap-1 transition-all"
                  title="Fit ECM in Complex Non-Linear Least Squares Studio"
                >
                  <Cpu className="w-3 h-3 text-sky-400" />
                  <span>Fit in CNLS</span>
                </button>
              )}

              {onSendToEISInsights && (
                <button
                  type="button"
                  onClick={() => onSendToEISInsights(uploadedDataset)}
                  className="px-2.5 py-1 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-300 font-mono text-[10px] flex items-center gap-1 transition-all"
                  title="Open in EIS Deep Insights (DRT, Kramers-Kronig, Bode)"
                >
                  <Sparkles className="w-3 h-3 text-purple-400" />
                  <span>Insights</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => {
                  const csv = exportDatasetToCSV(uploadedDataset);
                  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${uploadedDataset.name}_processed.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="px-2 py-1 rounded-lg bg-[#090e18] border border-[#1e2d46] hover:border-slate-400 text-slate-300 font-mono text-[10px] flex items-center gap-1"
                title="Download CSV"
              >
                <Download className="w-3 h-3" />
                <span>CSV</span>
              </button>

              <button
                type="button"
                onClick={onClearDataset}
                className="p-1 rounded-lg bg-[#090e18] border border-[#1e2d46] hover:border-rose-500/50 text-slate-400 hover:text-rose-400 transition-all"
                title="Clear Lab Data"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Quick Extracted Parameters Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
            <div className="p-2 rounded-lg bg-[#090e18] border border-[#162032]">
              <span className="text-slate-500 block text-[9px] uppercase tracking-wider">
                {domain === "battery" ? "Bulk Ohmic R_0:" : "Solution Resistance R_s:"}
              </span>
              <span className="text-sky-300 font-bold">{extractedMetrics.r0.toFixed(3)} Ω</span>
            </div>

            <div className="p-2 rounded-lg bg-[#090e18] border border-[#162032]">
              <span className="text-slate-500 block text-[9px] uppercase tracking-wider">
                {domain === "battery" ? "Polarization Arc ΔR (SEI+ct):" : "Pore / Polariz. R_p:"}
              </span>
              <span className="text-emerald-300 font-bold">
                {extractedMetrics.deltaR >= 1000
                  ? `${(extractedMetrics.deltaR / 1000).toFixed(2)} kΩ`
                  : `${extractedMetrics.deltaR.toFixed(3)} Ω`}
              </span>
            </div>

            <div className="p-2 rounded-lg bg-[#090e18] border border-[#162032]">
              <span className="text-slate-500 block text-[9px] uppercase tracking-wider">Apex Relaxation Freq:</span>
              <span className="text-amber-300 font-bold">
                {extractedMetrics.apexFreq >= 1000
                  ? `${(extractedMetrics.apexFreq / 1000).toFixed(2)} kHz`
                  : `${extractedMetrics.apexFreq.toFixed(2)} Hz`}
              </span>
            </div>

            <div className="p-2 rounded-lg bg-[#090e18] border border-[#162032]">
              <span className="text-slate-500 block text-[9px] uppercase tracking-wider">
                {domain === "battery" ? "Double Layer C_eff:" : "Coating Water Uptake:"}
              </span>
              <span className="text-purple-300 font-bold">
                {domain === "battery"
                  ? `${extractedMetrics.cEff_uF.toFixed(1)} µF`
                  : `${extractedMetrics.corrosionWaterUptakePct.toFixed(1)} % vol`}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Paste Modal */}
      {isPasteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div role="dialog" aria-modal="true" aria-label="Paste impedance data" className="bg-[#090e18] border border-[#1e2d46] rounded-2xl p-5 max-w-lg w-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#162032] pb-3">
              <div className="flex items-center gap-2">
                <Clipboard className="w-4 h-4 text-sky-400" />
                <h3 className="text-sm font-bold text-white font-mono uppercase">
                  Paste Lab EIS Tabular Data
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsPasteOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 font-mono text-xs">
              <label className="text-slate-300 font-semibold block">Dataset Name:</label>
              <input
                type="text"
                value={pastedName}
                onChange={(e) => setPastedName(e.target.value)}
                className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-400"
              />
            </div>

            <div className="space-y-2 font-mono text-xs">
              <label className="text-slate-300 font-semibold block">
                Raw Columns (Tab, Comma, or Space Delimited):
              </label>
              <span className="text-[10px] text-slate-500 block">
                Format: Frequency &nbsp; Z_Real &nbsp; -Z_Imag (or Z_Imag)
              </span>
              <textarea
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
                placeholder={`100000\t0.085\t0.012\n50000\t0.092\t0.035\n10000\t0.115\t0.090\n1000\t0.180\t0.220\n100\t0.310\t0.280\n10\t0.460\t0.240\n1.0\t0.540\t0.310\n0.1\t0.690\t0.450`}
                rows={8}
                className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-sky-400 font-mono"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#162032]">
              <button
                type="button"
                onClick={() => setIsPasteOpen(false)}
                className="px-3 py-1.5 rounded-xl bg-[#050810] border border-[#1e2d46] text-slate-400 hover:text-white text-xs font-mono"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApplyPaste}
                className="px-4 py-1.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs font-mono flex items-center gap-1.5"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Parse &amp; Ingest</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
