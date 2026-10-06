import { ResponsiveContainer } from './VisibleResponsiveContainer';
import { AccessibleModal } from "./AccessibleModal";
import React, { useState, useMemo, useRef, useCallback, useEffect } from "react";
import {
  Upload,
  FileText,
  Activity,
  Zap,
  Sliders,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Download,
  Copy,
  Check,
  RefreshCw,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Droplets,
  Layers,
  ShieldCheck,
  ShieldAlert,
  Flame,
  X,
  Target,
  FileSpreadsheet,
  Cpu,
  Info,
  ArrowRight,
  ExternalLink,
  Plus,
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
  ReferenceArea,
  ComposedChart,
} from "recharts";
import { TafelDataset, TafelFitResult, ReferenceElectrodeType } from "../types/tafel";
import {
  parseTafelFile,
  tryAutoFitTafel,
  TAFEL_BENCHMARK_DATASETS,
  COMMON_ALLOYS,
  REFERENCE_ELECTRODES,
  exportTafelToCSV,
  AlloyMaterialPreset,
} from "../utils/tafelParser";
import { useDigitalTwin } from "../context/DigitalTwinContext";
import { PythonAnnualCorrosionRateModule } from "./PythonAnnualCorrosionRateModule";
import { D3TafelPolarizationChart } from "./D3TafelPolarizationChart";
import { executePythonTafelFit } from "../utils/tafelPythonService";
import { isPythonValidationError } from "../utils/pythonValidationError";
import {
  digitalTwinElectrochemistry,
  fmtTafelNumber,
  fmtTafelQuantity,
  fmtTafelR2,
  tafelIntersectionAnchors,
  tafelUnavailableReason,
  UNAVAILABLE_TEXT,
} from "../utils/tafelDisplay";

interface TafelPolarizationLabProps {
  onDatasetLoaded?: (dataset: TafelDataset) => void;
  className?: string;
}

/**
 * TAFEL_BENCHMARK_DATASETS is empty (the former PRNG-fabricated curves were removed), so
 * the lab starts without data: it shows an empty state with a file input and renders the
 * full lab only once a polarization file has been parsed.
 */
export function TafelPolarizationLab(props: TafelPolarizationLabProps) {
  const [initialDataset, setInitialDataset] = useState<TafelDataset | null>(TAFEL_BENCHMARK_DATASETS[0] ?? null);
  const [loadError, setLoadError] = useState<string | null>(null);

  if (initialDataset) {
    return <TafelPolarizationLabWithData {...props} initialDataset={initialDataset} />;
  }

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = parseTafelFile(String(reader.result ?? ""), file.name, 1.0, COMMON_ALLOYS[0]);
        setLoadError(null);
        setInitialDataset(parsed);
        if (props.onDatasetLoaded) props.onDatasetLoaded(parsed);
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : String(err));
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className={`rounded-2xl border border-[#162032] bg-[#050810] p-6 text-slate-300 font-mono text-xs space-y-3 ${props.className ?? ""}`}>
      <p>No benchmark dataset available</p>
      <input
        aria-label="Load polarization data file"
        type="file"
        accept=".csv,.txt,.dta,.mpt,.tsv"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {loadError && <p role="alert" className="text-rose-400">{loadError}</p>}
    </div>
  );
}

function TafelPolarizationLabWithData({
  onDatasetLoaded,
  className = "",
  initialDataset,
}: TafelPolarizationLabProps & { initialDataset: TafelDataset }) {
  // Digital Twin Context for syncing
  const dtContext = useDigitalTwin();

  // Active dataset & fitting state
  const [dataset, setDataset] = useState<TafelDataset>(initialDataset);
  const [selectedBenchmarkId, setSelectedBenchmarkId] = useState<string>(initialDataset.id);

  // File upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [isPasteModalOpen, setIsPasteModalOpen] = useState<boolean>(false);
  const [pastedText, setPastedText] = useState<string>("");

  // Specimen & Environment Config
  const [selectedAlloyId, setSelectedAlloyId] = useState<string>("ss316l");
  const [electrodeAreaCm2, setElectrodeAreaCm2] = useState<number>(1.0);
  const [referenceElectrode, setReferenceElectrode] = useState<ReferenceElectrodeType>("SCE");
  const [customDensity, setCustomDensity] = useState<number>(COMMON_ALLOYS[0].density);
  const [customEW, setCustomEW] = useState<number>(COMMON_ALLOYS[0].equivalentWeight);
  const [electrolyteDesc, setElectrolyteDesc] = useState<string>("3.5 wt% NaCl (Simulated Marine / ASTM G5)");
  const [temperatureC, setTemperatureC] = useState<number>(25);

  // Interactive Tafel Extrapolation Controls
  const [isManualOverride, setIsManualOverride] = useState<boolean>(false);
  const [customCathodicRange, setCustomCathodicRange] = useState<[number, number] | undefined>(undefined);
  const [customAnodicRange, setCustomAnodicRange] = useState<[number, number] | undefined>(undefined);
  const [manualEcorr, setManualEcorr] = useState<number | undefined>(undefined);
  const [manualLogIcorr, setManualLogIcorr] = useState<number | undefined>(undefined);
  const [manualBetaA, setManualBetaA] = useState<number | undefined>(undefined);
  const [manualBetaC, setManualBetaC] = useState<number | undefined>(undefined);

  // Visualization options
  const [chartOrientation, setChartOrientation] = useState<"evans" | "potentiodynamic">("evans");
  const [showTangentLines, setShowTangentLines] = useState<boolean>(true);
  const [showButlerVolmer, setShowButlerVolmer] = useState<boolean>(true);
  const [showFittingWindows, setShowFittingWindows] = useState<boolean>(true);
  const [showRawPoints, setShowRawPoints] = useState<boolean>(true);
  const [showHelpGuide, setShowHelpGuide] = useState<boolean>(false);
  const [showDataTable, setShowDataTable] = useState<boolean>(false);
  const [copiedNotification, setCopiedNotification] = useState<boolean>(false);
  const [savedToDtNotification, setSavedToDtNotification] = useState<boolean>(false);

  // Python Engine Integration & D3 Visualizer State
  const [pythonFitResult, setPythonFitResult] = useState<TafelFitResult | null>(null);
  const [isPythonFitting, setIsPythonFitting] = useState<boolean>(false);
  const [pythonFitError, setPythonFitError] = useState<string | null>(null);
  const [activeChartEngine, setActiveChartEngine] = useState<"d3" | "recharts">("d3");

  // Sync alloy preset selection with inputs
  const currentAlloy = useMemo(() => {
    return COMMON_ALLOYS.find((a) => a.id === selectedAlloyId) || COMMON_ALLOYS[0];
  }, [selectedAlloyId]);

  const handleAlloyChange = (alloyId: string) => {
    setSelectedAlloyId(alloyId);
    const alloy = COMMON_ALLOYS.find((a) => a.id === alloyId);
    if (alloy) {
      setCustomDensity(alloy.density);
      setCustomEW(alloy.equivalentWeight);
      // Update dataset metadata
      setDataset((prev) => ({
        ...prev,
        metadata: {
          ...prev.metadata,
          alloyName: alloy.name,
          density_g_cm3: alloy.density,
          equivalentWeight: alloy.equivalentWeight,
        },
      }));
    }
  };

  // Compute Tafel Fit Result
  const fitResult: TafelFitResult = useMemo(() => {
    try {
      const activeDataset: TafelDataset = {
        ...dataset,
        metadata: {
          ...dataset.metadata,
          electrodeAreaCm2: Math.max(0.01, electrodeAreaCm2),
          referenceElectrode,
          refOffsetVsSHE: REFERENCE_ELECTRODES[referenceElectrode]?.offsetVsSHE || 0.241,
          alloyName: currentAlloy.name,
          density_g_cm3: customDensity,
          equivalentWeight: customEW,
          electrolyte: electrolyteDesc,
          temperatureC,
        },
      };

      const baseFit = tryAutoFitTafel(
        activeDataset,
        customCathodicRange,
        customAnodicRange,
        isManualOverride ? manualEcorr : undefined,
        isManualOverride && typeof manualLogIcorr === "number" ? Math.pow(10, manualLogIcorr) : undefined
      );

      // If user manually customized betaA or betaC
      if (isManualOverride && (manualBetaA || manualBetaC)) {
        // A slope that is neither entered nor fitted stays unavailable (no assumed value); Stern-Geary B and Rp
        // need both slopes and i_corr.
        const bAmv = manualBetaA || baseFit.betaA_mV_dec;
        const bCmv = manualBetaC || baseFit.betaC_mV_dec;
        const bA = bAmv ? bAmv / 1000 : null;
        const bC = bCmv ? bCmv / 1000 : null;
        const bStern = bA !== null && bC !== null ? (bA * bC) / (Math.LN10 * (bA + bC)) : null;
        const rp = bStern !== null && baseFit.iCorr_uA_cm2 !== null ? bStern / (baseFit.iCorr_uA_cm2 * 1e-6) : null;
        return {
          ...baseFit,
          betaA_V_dec: bA,
          betaA_mV_dec: bA === null ? null : bA * 1000,
          betaC_V_dec: bC,
          betaC_mV_dec: bC === null ? null : bC * 1000,
          sternGearyB_V: bStern === null ? null : parseFloat(bStern.toFixed(4)),
          rp_ohm_cm2: rp === null ? null : parseFloat(rp.toFixed(1)),
        };
      }

      return baseFit;
    } catch (err) {
      console.error("Tafel fit error:", err);
      // Fall back to the dataset the lab was opened with (no fabricated benchmark exists).
      return tryAutoFitTafel(initialDataset);
    }
  }, [
    dataset,
    initialDataset,
    electrodeAreaCm2,
    referenceElectrode,
    currentAlloy,
    customDensity,
    customEW,
    electrolyteDesc,
    temperatureC,
    customCathodicRange,
    customAnodicRange,
    isManualOverride,
    manualEcorr,
    manualLogIcorr,
    manualBetaA,
    manualBetaC,
  ]);

  // Automated Python Fitting Trigger for User Uploads and Datasets
  const runPythonFit = useCallback(
    async (targetDataset: TafelDataset = dataset) => {
      setIsPythonFitting(true);
      try {
        const res = await executePythonTafelFit(targetDataset, {
          customCathodicRange,
          customAnodicRange,
          manualEcorrOverride: isManualOverride ? manualEcorr : undefined,
          manualIcorrOverride:
            isManualOverride && typeof manualLogIcorr === "number"
              ? Math.pow(10, manualLogIcorr)
              : undefined,
          alloyId: selectedAlloyId,
        });
        setPythonFitResult(res);
        setPythonFitError(null);
      } catch (err) {
        if (isPythonValidationError(err)) {
          // Rejected input: drop the previous Python fit instead of showing it as current.
          setPythonFitResult(null);
          setPythonFitError(err.message);
        }
        console.error("Failed to execute Python Tafel fitting:", err);
      } finally {
        setIsPythonFitting(false);
      }
    },
    [
      dataset,
      customCathodicRange,
      customAnodicRange,
      isManualOverride,
      manualEcorr,
      manualLogIcorr,
      selectedAlloyId,
    ]
  );

  // Initial Python calculation on component mount
  useEffect(() => {
    runPythonFit(dataset);
  }, []);

  // Effective fit result prioritizing Python backend calculation
  const effectiveFitResult: TafelFitResult = useMemo(() => {
    return pythonFitResult || fitResult;
  }, [pythonFitResult, fitResult]);

  // Update manual sliders when dataset changes
  useEffect(() => {
    if (!isManualOverride) {
      setManualEcorr(effectiveFitResult.eCorr ?? undefined);
      setManualLogIcorr(effectiveFitResult.logIcorr ?? undefined);
      setManualBetaA(effectiveFitResult.betaA_mV_dec ?? undefined);
      setManualBetaC(effectiveFitResult.betaC_mV_dec ?? undefined);
      setCustomCathodicRange(effectiveFitResult.cathodicRange);
      setCustomAnodicRange(effectiveFitResult.anodicRange);
    }
  }, [dataset.id, effectiveFitResult.eCorr, effectiveFitResult.logIcorr]);

  // Anchors of the manual tuning controls and of the branch column. When the Evans intersection is unavailable they
  // fall back to the measured current valley (a measured value, labelled "Raw Valley"), never to an assumed one.
  const { eCorrRef: eCorrAnchor, logIcorrRef: logIcorrAnchor } = tafelIntersectionAnchors(fitResult);
  const effectiveUnavailableReason = tafelUnavailableReason(effectiveFitResult);

  // Handle benchmark change
  const handleSelectBenchmark = (benchId: string) => {
    setSelectedBenchmarkId(benchId);
    const bench = TAFEL_BENCHMARK_DATASETS.find((b) => b.id === benchId);
    if (bench) {
      setDataset(bench);
      setIsManualOverride(false);
      setCustomCathodicRange(undefined);
      setCustomAnodicRange(undefined);
      setParseError(null);
      if (onDatasetLoaded) onDatasetLoaded(bench);
      runPythonFit(bench);
    }
  };

  // File processing with automated Python Ecorr & Icorr calculation
  const handleProcessFile = (file: File) => {
    setParseError(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string;
        if (!text || !text.trim()) {
          throw new Error("The uploaded file is empty.");
        }
        const parsed = parseTafelFile(text, file.name, electrodeAreaCm2, currentAlloy);
        setDataset(parsed);
        setSelectedBenchmarkId("custom_upload");
        setIsManualOverride(false);
        setCustomCathodicRange(undefined);
        setCustomAnodicRange(undefined);
        if (onDatasetLoaded) onDatasetLoaded(parsed);
        // Automatically calculate Ecorr and Icorr using Python backend solver
        runPythonFit(parsed);
      } catch (err: any) {
        console.error("Tafel upload parsing error:", err);
        setParseError(err.message || "Failed to parse polarization data file.");
      }
    };
    reader.onerror = () => setParseError("Error reading file from disk.");
    reader.readAsText(file);
  };

  const handlePasteSubmit = () => {
    setParseError(null);
    try {
      if (!pastedText || !pastedText.trim()) {
        throw new Error("No text was pasted.");
      }
      const parsed = parseTafelFile(pastedText, "pasted_tafel_data.csv", electrodeAreaCm2, currentAlloy);
      setDataset(parsed);
      setSelectedBenchmarkId("custom_upload");
      setIsManualOverride(false);
      setCustomCathodicRange(undefined);
      setCustomAnodicRange(undefined);
      setIsPasteModalOpen(false);
      setPastedText("");
      if (onDatasetLoaded) onDatasetLoaded(parsed);
      // Automatically calculate Ecorr and Icorr using Python backend solver
      runPythonFit(parsed);
    } catch (err: any) {
      setParseError(err.message || "Failed to parse pasted polarization data.");
    }
  };

  // Reset to auto-fit
  const handleResetToAutoFit = () => {
    setIsManualOverride(false);
    setCustomCathodicRange(undefined);
    setCustomAnodicRange(undefined);
    const cleanFit = tryAutoFitTafel(dataset);
    setManualEcorr(cleanFit.eCorr ?? undefined);
    setManualLogIcorr(cleanFit.logIcorr ?? undefined);
    setManualBetaA(cleanFit.betaA_mV_dec ?? undefined);
    setManualBetaC(cleanFit.betaC_mV_dec ?? undefined);
    setCustomCathodicRange(cleanFit.cathodicRange);
    setCustomAnodicRange(cleanFit.anodicRange);
  };

  // Chart Data Assembly
  // Merge raw experimental points with tangent lines and Butler-Volmer model
  const chartPoints = useMemo(() => {
    const rawMap: { [key: string]: any } = {};

    dataset.points.forEach((p) => {
      const key = p.potential.toFixed(3);
      rawMap[key] = {
        potential: p.potential,
        logI_exp: p.logCurrentDensity,
        currentDensity: p.currentDensity_uA_cm2,
      };
    });

    // Merge tangents
    fitResult.tangentLines.forEach((t) => {
      const key = t.potential.toFixed(3);
      if (!rawMap[key]) {
        rawMap[key] = { potential: t.potential };
      }
      if (t.logI_anodic !== undefined) rawMap[key].tangentAnodic = t.logI_anodic;
      if (t.logI_cathodic !== undefined) rawMap[key].tangentCathodic = t.logI_cathodic;
    });

    // Merge Butler-Volmer model
    fitResult.syntheticButlerVolmer.forEach((m) => {
      const key = m.potential.toFixed(3);
      if (!rawMap[key]) {
        rawMap[key] = { potential: m.potential };
      }
      rawMap[key].butlerVolmer = m.logI_model;
    });

    return Object.values(rawMap).sort((a, b) => a.potential - b.potential);
  }, [dataset.points, fitResult]);

  // Export to CSV
  const handleDownloadCSV = () => {
    const csvContent = exportTafelToCSV(dataset, fitResult);
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `Tafel_Report_${dataset.name.replace(/\s+/g, "_")}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Copy Summary
  const handleCopySummary = () => {
    const summary = [
      `MetalliX Electrochemical Tafel Analysis (ASTM G102 / G59)`,
      `Sample / Dataset: ${dataset.name}`,
      `Substrate: ${dataset.metadata.alloyName}`,
      `Electrolyte: ${dataset.metadata.electrolyte}`,
      `----------------------------------------------------`,
      `Corrosion Potential (Ecorr): ${fmtTafelQuantity(fitResult.eCorr, "V")} vs ${dataset.metadata.referenceElectrode} (${fmtTafelQuantity(fitResult.eCorrSHE, "V")} vs SHE)`,
      `Corrosion Current Density (icorr): ${fmtTafelQuantity(fitResult.iCorr_uA_cm2, "µA/cm²")} (log10 = ${fmtTafelNumber(fitResult.logIcorr)})`,
      `Total Corrosion Current (Icorr): ${fmtTafelQuantity(fitResult.totalCurrentIcorr_uA, "µA")}`,
      `Anodic Tafel Slope (Beta_a): ${fmtTafelQuantity(fitResult.betaA_mV_dec, "mV/decade")} (${fmtTafelR2(fitResult.anodicR2)})`,
      `Cathodic Tafel Slope (Beta_c): ${fmtTafelQuantity(fitResult.betaC_mV_dec, "mV/decade")} (${fmtTafelR2(fitResult.cathodicR2)})`,
      `Stern-Geary Constant (B): ${fmtTafelQuantity(fitResult.sternGearyB_V, "V")}`,
      `Polarization Resistance (Rp): ${fmtTafelQuantity(fitResult.rp_ohm_cm2, "Ω·cm²", { grouped: true })}`,
      `Faraday Penetration Rate: ${fmtTafelQuantity(fitResult.corrosionRateMmYr, "mm/year")} (${fmtTafelQuantity(fitResult.corrosionRateMpy, "mpy")})`,
      `Daily Mass Loss: ${fmtTafelQuantity(fitResult.massLoss_g_m2_day, "g/(m²·day)")}`,
      `Classification: ${fitResult.astmClassification ?? UNAVAILABLE_TEXT}`,
      ...(tafelUnavailableReason(fitResult) ? [`Unavailable: ${tafelUnavailableReason(fitResult)}`] : []),
    ].join("\n");

    navigator.clipboard.writeText(summary);
    setCopiedNotification(true);
    setTimeout(() => setCopiedNotification(false), 2500);
  };

  // Sync with Digital Twin
  const handleSyncToDigitalTwin = () => {
    if (dtContext?.syncWithModuleData) {
      dtContext.syncWithModuleData("TafelPolarizationLab", {
        electrochemistry: digitalTwinElectrochemistry(fitResult),
      });
      setSavedToDtNotification(true);
      setTimeout(() => setSavedToDtNotification(false), 2500);
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* 1. TOP BANNER / MODULE HEADER */}
      <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-[0_0_16px_rgba(52,211,153,0.25)]">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg font-extrabold text-white font-mono tracking-wide uppercase">
                Tafel Polarization &amp; Ecorr/Icorr Solver
              </h2>
              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-mono border border-emerald-500/40 font-bold">
                ASTM G102 / ASTM G59
              </span>
              <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 text-[10px] font-mono border border-sky-500/40">
                Multi-Format Ingestion
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Upload Potentiodynamic Data, Locate Corrosion Potential (Ecorr) &amp; Current (Icorr) via Linear Tafel Extrapolation
            </p>
          </div>
        </div>

        {/* Top Quick Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setShowHelpGuide(!showHelpGuide)}
            className="px-3 py-1.5 rounded-lg text-xs font-mono transition border flex items-center gap-1.5 bg-[#050810] border-[#162032] text-slate-300 hover:text-white hover:border-slate-600"
          >
            <HelpCircle className="w-3.5 h-3.5 text-sky-400" />
            <span>{showHelpGuide ? "Hide Guide" : "How Ecorr/Icorr Works"}</span>
          </button>

          <button
            type="button"
            onClick={handleDownloadCSV}
            className="px-3 py-1.5 rounded-lg text-xs font-mono transition border flex items-center gap-1.5 bg-[#050810] border-[#162032] text-slate-300 hover:text-white hover:border-emerald-500/40"
          >
            <Download className="w-3.5 h-3.5 text-emerald-400" />
            <span>Export CSV</span>
          </button>

          <button
            type="button"
            onClick={handleCopySummary}
            className="px-3 py-1.5 rounded-lg text-xs font-mono transition border flex items-center gap-1.5 bg-[#050810] border-[#162032] text-slate-300 hover:text-white hover:border-sky-500/40"
          >
            {copiedNotification ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-sky-400" />}
            <span>{copiedNotification ? "Copied!" : "Copy Report"}</span>
          </button>

          {dtContext && (
            <button
              type="button"
              onClick={handleSyncToDigitalTwin}
              className="px-3 py-1.5 rounded-lg text-xs font-mono transition border flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20"
            >
              {savedToDtNotification ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />}
              <span>{savedToDtNotification ? "Record Saved!" : "Save to Specimen Record"}</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. COLLAPSIBLE EDUCATIONAL GUIDE */}
      {showHelpGuide && (
        <div className="bg-[#0b1322] border border-sky-500/30 rounded-2xl p-5 space-y-4 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-sky-500/20 pb-3">
            <h3 className="text-sm font-bold text-sky-300 font-mono flex items-center gap-2">
              <Info className="w-4 h-4 text-sky-400" />
              <span>Scientific Foundation: Finding Ecorr &amp; Icorr (ASTM G102 &amp; ASTM G59)</span>
            </h3>
            <button
              type="button"
              onClick={() => setShowHelpGuide(false)}
              className="text-slate-400 hover:text-white p-1"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono text-slate-300 leading-relaxed">
            <div className="p-3.5 bg-[#070c17] rounded-xl border border-[#162032] space-y-2">
              <span className="text-amber-400 font-bold block flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5" />
                1. Identifying Ecorr (Corrosion Potential)
              </span>
              <p className="text-[11px] text-slate-400">
                At open-circuit equilibrium (Ecorr), the rate of anodic metal dissolution equals the rate of cathodic reduction (ia = |ic| = icorr). The measured net current drops towards zero (|inet| → 0), creating a distinct downward V-shaped valley on the logarithmic scale.
              </p>
            </div>

            <div className="p-3.5 bg-[#070c17] rounded-xl border border-[#162032] space-y-2">
              <span className="text-sky-400 font-bold block flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5" />
                2. Tafel Slopes &amp; Extrapolation
              </span>
              <p className="text-[11px] text-slate-400">
                At overpotentials |η| = |E - Ecorr| ≥ 50 to 100 mV, the reverse reaction becomes negligible. Butler-Volmer kinetics simplify to straight lines: η_a = β_a · log(i_a / i_corr) and η_c = -β_c · log(|i_c| / i_corr). The intersection of these two linear tangents yields the exact (Ecorr, Icorr) coordinates.
              </p>
            </div>

            <div className="p-3.5 bg-[#070c17] rounded-xl border border-[#162032] space-y-2">
              <span className="text-emerald-400 font-bold block flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" />
                3. Stern-Geary &amp; Faraday Penetration
              </span>
              <p className="text-[11px] text-slate-400">
                Polarization Resistance Rp = (β_a · β_c) / [2.303 · (β_a + β_c) · i_corr] (ASTM G59). Faraday&apos;s Law calculates annual penetration: CR (mm/yr) = (0.00327 · i_corr · EW) / ρ.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3. FILE UPLOAD & BENCHMARK SELECTION SUITE */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Drag & Drop Ingestion Card */}
        <div className="lg:col-span-8 bg-[#090e18] rounded-2xl border border-[#162032] p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#162032] pb-3">
            <div className="flex items-center gap-2">
              <Upload className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                Upload Experimental Polarization Data
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#050810] border border-[#162032] text-slate-400">
                BioLogic .mpt | Gamry .DTA | Autolab | CSV / TSV
              </span>
            </div>
          </div>

          {/* Drag & Drop Zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragOver(false);
              if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleProcessFile(e.dataTransfer.files[0]);
              }
            }}
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-all cursor-pointer flex flex-col items-center justify-center gap-2.5 ${
              isDragOver
                ? "border-emerald-400 bg-emerald-500/10 scale-[1.005]"
                : "border-[#1e2d46] hover:border-emerald-500/40 bg-[#050810]/60 hover:bg-[#050810]"
            }`}
            onClick={() => fileInputRef.current?.click()}
          >
            <input aria-label="Upload polarization file"
              type="file"
              ref={fileInputRef}
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleProcessFile(e.target.files[0]);
                }
              }}
              accept=".csv,.txt,.mpt,.dta,.par,.dat,.tsv"
              className="hidden"
            />

            <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Upload className="w-5 h-5" />
            </div>

            <div className="space-y-1">
              <div className="text-sm font-bold text-white font-mono">
                Drag &amp; drop your polarization file here, or <span className="text-emerald-400 underline">browse</span>
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Accepts potentiodynamic scan files with Potential (V) and Current (A, mA, µA, or log i) columns
              </p>
            </div>

            <div className="flex items-center gap-3 pt-1 text-[11px] font-mono text-slate-500">
              <span>Automatic comma/dot decimal detection</span>
              <span>•</span>
              <span>Unit auto-scaling (A → µA)</span>
              <span>•</span>
              <span>Zero-noise filtering</span>
            </div>
          </div>

          {/* Error Message if parsing failed */}
          {parseError && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 font-mono text-xs flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{parseError}</span>
              </div>
              <button
                type="button"
                onClick={() => setParseError(null)}
                className="text-rose-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Quick Paste or Load Buttons */}
          <div className="flex items-center justify-between gap-3 pt-1 flex-wrap">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
              <span>Active Dataset:</span>
              <span className="text-white font-bold bg-[#050810] px-2 py-0.5 rounded border border-[#162032] flex items-center gap-1.5">
                <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
                {dataset.name} ({dataset.points.length} points)
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setIsPasteModalOpen(true)}
                className="px-3 py-1 rounded-lg bg-[#050810] hover:bg-[#0d1626] border border-[#162032] hover:border-slate-600 text-xs font-mono text-slate-300 flex items-center gap-1.5"
              >
                <FileText className="w-3.5 h-3.5 text-sky-400" />
                <span>Paste Raw Text / Table</span>
              </button>

              <button
                type="button"
                onClick={() => setShowDataTable(!showDataTable)}
                className="px-3 py-1 rounded-lg bg-[#050810] hover:bg-[#0d1626] border border-[#162032] hover:border-slate-600 text-xs font-mono text-slate-300 flex items-center gap-1.5"
              >
                <span>{showDataTable ? "Hide Table" : "Inspect Raw Points"}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Preloaded Benchmark Selectors */}
        <div className="lg:col-span-4 bg-[#090e18] rounded-2xl border border-[#162032] p-5 space-y-4 flex flex-col justify-between">
          <div className="border-b border-[#162032] pb-3">
            <span className="text-xs font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-sky-400" />
              Preloaded Benchmark Standards
            </span>
            <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
              Instant NIST / ASTM G5 calibrated datasets for reference verification
            </span>
          </div>

          <div className="space-y-2">
            {TAFEL_BENCHMARK_DATASETS.map((bench) => {
              const isSelected = selectedBenchmarkId === bench.id;
              return (
                <button
                  key={bench.id}
                  type="button"
                  onClick={() => handleSelectBenchmark(bench.id)}
                  className={`w-full p-2.5 rounded-xl border text-left transition-all font-mono text-xs flex items-center justify-between ${
                    isSelected
                      ? "bg-emerald-500/15 border-emerald-400/60 shadow-[0_0_12px_rgba(52,211,153,0.2)] text-white"
                      : "bg-[#050810] border-[#162032] hover:border-slate-600 text-slate-300"
                  }`}
                >
                  <div className="truncate pr-2">
                    <span className={`font-bold block truncate ${isSelected ? "text-emerald-300" : "text-white"}`}>
                      {bench.name}
                    </span>
                    <span className="text-[10px] text-slate-400 block truncate">
                      {bench.metadata.electrolyte}
                    </span>
                  </div>
                  {isSelected ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <ArrowRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                  )}
                </button>
              );
            })}
          </div>

          <div className="p-3 bg-[#050810] rounded-xl border border-[#162032] text-[11px] font-mono text-slate-400 flex items-center justify-between">
            <span>Scan points: {dataset.points.length}</span>
            <span>Range: {dataset.points[0]?.potential} V → {dataset.points[dataset.points.length - 1]?.potential} V</span>
          </div>
        </div>
      </div>

      {/* RAW DATA TABLE INSPECTION (Optional Drawer) */}
      {showDataTable && (
        <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] space-y-3 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-[#162032] pb-2">
            <span className="text-xs font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-sky-400" />
              Raw Polarization Points Preview ({dataset.points.length} points)
            </span>
            <button
              type="button"
              onClick={() => setShowDataTable(false)}
              className="text-slate-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="max-h-60 overflow-y-auto font-mono text-[11px] border border-[#162032] rounded-xl">
            <table className="w-full text-left">
              <thead className="bg-[#050810] text-slate-400 sticky top-0 border-b border-[#162032]">
                <tr>
                  <th className="p-2.5">#</th>
                  <th className="p-2.5">Potential E (V vs Ref)</th>
                  <th className="p-2.5">Potential E (V vs SHE)</th>
                  <th className="p-2.5">Current Density (µA/cm²)</th>
                  <th className="p-2.5">log₁₀|i|</th>
                  <th className="p-2.5">Branch</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#162032] text-slate-300">
                {dataset.points.slice(0, 100).map((p, idx) => {
                  const isEcorr = fitResult.eCorr !== null && Math.abs(p.potential - fitResult.eCorr) < 0.005;
                  return (
                    <tr
                      key={idx}
                      className={`hover:bg-[#0f172a] ${
                        isEcorr ? "bg-emerald-500/20 text-emerald-300 font-bold" : ""
                      }`}
                    >
                      <td className="p-2 text-slate-500">{idx + 1}</td>
                      <td className="p-2 text-white">{p.potential.toFixed(4)} V</td>
                      <td className="p-2 text-slate-400">{p.potentialSHE?.toFixed(4)} V</td>
                      <td className="p-2 text-sky-300">{p.currentDensity_uA_cm2.toFixed(4)}</td>
                      <td className="p-2 text-amber-300">{p.logCurrentDensity.toFixed(3)}</td>
                      <td className="p-2">
                        {p.potential < eCorrAnchor ? (
                          <span className="text-amber-400 text-[10px]">Cathodic (Reduction)</span>
                        ) : (
                          <span className="text-sky-400 text-[10px]">Anodic (Oxidation)</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {dataset.points.length > 100 && (
            <p className="text-[10px] text-slate-500 font-mono text-right">
              Showing first 100 of {dataset.points.length} points. Full dataset is loaded into the fitting engine.
            </p>
          )}
        </div>
      )}

      {/* 4. MAIN WORKBENCH: CHART & INTERACTIVE ECORR/ICORR FINDER */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Specimen Setup & Interactive Sliders */}
        <div className="lg:col-span-4 space-y-5">
          {/* Specimen Configuration */}
          <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[#162032] pb-3">
              <span className="text-xs font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Working Electrode &amp; Cell Config
              </span>
              <span className="text-[10px] font-mono text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-400/30">
                ASTM G102
              </span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              {/* Alloy Selector */}
              <div className="space-y-1">
                <label className="text-slate-300 block">Material Substrate:</label>
                <select aria-label="Material Substrate"
                  value={selectedAlloyId}
                  onChange={(e) => handleAlloyChange(e.target.value)}
                  className="w-full bg-[#050810] border border-[#162032] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400"
                >
                  {COMMON_ALLOYS.map((alloy) => (
                    <option key={alloy.id} value={alloy.id}>
                      {alloy.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Surface Area */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <span className="text-slate-400 block">Area (cm²):</span>
                  <input aria-label="Area (cm²)"
                    type="number"
                    min="0.01"
                    max="1000"
                    step="0.01"
                    value={electrodeAreaCm2}
                    onChange={(e) => setElectrodeAreaCm2(parseFloat(e.target.value) || 1.0)}
                    className="w-full bg-[#050810] border border-[#162032] rounded-lg px-2.5 py-1.5 text-white"
                  />
                </div>
                <div className="space-y-1">
                  <span className="text-slate-400 block">Ref. Electrode:</span>
                  <select aria-label="Ref. Electrode"
                    value={referenceElectrode}
                    onChange={(e) => setReferenceElectrode(e.target.value as ReferenceElectrodeType)}
                    className="w-full bg-[#050810] border border-[#162032] rounded-lg px-2 py-1.5 text-white text-[11px]"
                  >
                    <option value="SCE">SCE (+0.241 V vs SHE)</option>
                    <option value="Ag/AgCl">Ag/AgCl (+0.197 V)</option>
                    <option value="SHE">SHE (0.000 V)</option>
                    <option value="MSE">MSE (+0.640 V)</option>
                  </select>
                </div>
              </div>

              {/* Density and Equivalent Weight */}
              <div className="grid grid-cols-2 gap-3 text-[11px]">
                <div className="space-y-1">
                  <span className="text-slate-400 block">Density (g/cm³):</span>
                  <input aria-label="Density (g/cm³)"
                    type="number"
                    step="0.01"
                    value={customDensity}
                    onChange={(e) => setCustomDensity(parseFloat(e.target.value) || COMMON_ALLOYS[0].density)}
                    className="w-full bg-[#050810] border border-[#162032] rounded px-2 py-1 text-slate-200"
                  />
                </div>
                <div className="space-y-1">
                  <span className="text-slate-400 block">Equiv. Weight (g/eq):</span>
                  <input aria-label="Equiv. Weight (g/eq)"
                    type="number"
                    step="0.01"
                    value={customEW}
                    onChange={(e) => setCustomEW(parseFloat(e.target.value) || COMMON_ALLOYS[0].equivalentWeight)}
                    className="w-full bg-[#050810] border border-[#162032] rounded px-2 py-1 text-slate-200"
                  />
                </div>
              </div>

              {/* Electrolyte description */}
              <div className="space-y-1">
                <span className="text-slate-400 block">Electrolyte Medium:</span>
                <input aria-label="Electrolyte Medium"
                  type="text"
                  value={electrolyteDesc}
                  onChange={(e) => setElectrolyteDesc(e.target.value)}
                  className="w-full bg-[#050810] border border-[#162032] rounded px-2.5 py-1.5 text-slate-200 text-[11px]"
                />
              </div>
            </div>
          </div>

          {/* Interactive Tafel Extrapolation Tuning Controls */}
          <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[#162032] pb-3">
              <span className="text-xs font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                <Sliders className="w-4 h-4 text-sky-400" />
                Tafel Slope &amp; Extrapolation Finder
              </span>
              <button
                type="button"
                onClick={handleResetToAutoFit}
                className="text-[10px] font-mono text-sky-400 hover:text-sky-300 flex items-center gap-1 underline"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Auto-Fit (ASTM G102)</span>
              </button>
            </div>

            <div className="space-y-4 font-mono text-xs">
              {/* Manual Override Switch */}
              <div className="flex items-center justify-between p-2.5 bg-[#050810] rounded-xl border border-[#162032]">
                <div className="space-y-0.5">
                  <span className="text-white font-bold block">Interactive Manual Tuning</span>
                  <span className="text-[10px] text-slate-400 block">Enable manual sliders for Ecorr, Icorr &amp; Slopes</span>
                </div>
                <input aria-label="Interactive Manual Tuning"
                  type="checkbox"
                  checked={isManualOverride}
                  onChange={(e) => setIsManualOverride(e.target.checked)}
                  className="w-4 h-4 accent-emerald-400 cursor-pointer"
                />
              </div>

              {/* Interactive Cathodic Fit Window */}
              <div className="space-y-1.5 bg-[#050810] p-3 rounded-xl border border-amber-500/20">
                <div className="flex justify-between items-center text-amber-300">
                  <span className="font-bold flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400 inline-block"></span>
                    Cathodic Fit Window (E_min → E_max):
                  </span>
                  <span className="font-bold">
                    {fitResult.cathodicRange[0]} V → {fitResult.cathodicRange[1]} V
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  <div>
                    <span className="text-slate-400 block">Cathodic Lower:</span>
                    <input aria-label="Cathodic Lower (V)"
                      type="number"
                      step="0.01"
                      value={customCathodicRange ? customCathodicRange[0] : fitResult.cathodicRange[0]}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setCustomCathodicRange([val, customCathodicRange ? customCathodicRange[1] : fitResult.cathodicRange[1]]);
                      }}
                      className="w-full bg-[#090e18] border border-[#162032] rounded px-2 py-1 text-amber-300"
                    />
                  </div>
                  <div>
                    <span className="text-slate-400 block">Cathodic Upper:</span>
                    <input aria-label="Cathodic Upper (V)"
                      type="number"
                      step="0.01"
                      value={customCathodicRange ? customCathodicRange[1] : fitResult.cathodicRange[1]}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setCustomCathodicRange([customCathodicRange ? customCathodicRange[0] : fitResult.cathodicRange[0], val]);
                      }}
                      className="w-full bg-[#090e18] border border-[#162032] rounded px-2 py-1 text-amber-300"
                    />
                  </div>
                </div>
                <span className="text-[10px] text-slate-500 block">
                  Cathodic Slope β_c: <strong className="text-amber-300">{fmtTafelQuantity(fitResult.betaC_mV_dec, "mV/dec")}</strong> ({fmtTafelR2(fitResult.cathodicR2)})
                </span>
                {fitResult.unavailable?.cathodicBranch && (
                  <span role="status" className="text-[10px] text-rose-300 block">{fitResult.unavailable.cathodicBranch}</span>
                )}
              </div>

              {/* Interactive Anodic Fit Window */}
              <div className="space-y-1.5 bg-[#050810] p-3 rounded-xl border border-sky-500/20">
                <div className="flex justify-between items-center text-sky-300">
                  <span className="font-bold flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-sky-400 inline-block"></span>
                    Anodic Fit Window (E_min → E_max):
                  </span>
                  <span className="font-bold">
                    {fitResult.anodicRange[0]} V → {fitResult.anodicRange[1]} V
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  <div>
                    <span className="text-slate-400 block">Anodic Lower:</span>
                    <input aria-label="Anodic Lower (V)"
                      type="number"
                      step="0.01"
                      value={customAnodicRange ? customAnodicRange[0] : fitResult.anodicRange[0]}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setCustomAnodicRange([val, customAnodicRange ? customAnodicRange[1] : fitResult.anodicRange[1]]);
                      }}
                      className="w-full bg-[#090e18] border border-[#162032] rounded px-2 py-1 text-sky-300"
                    />
                  </div>
                  <div>
                    <span className="text-slate-400 block">Anodic Upper:</span>
                    <input aria-label="Anodic Upper (V)"
                      type="number"
                      step="0.01"
                      value={customAnodicRange ? customAnodicRange[1] : fitResult.anodicRange[1]}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setCustomAnodicRange([customAnodicRange ? customAnodicRange[0] : fitResult.anodicRange[0], val]);
                      }}
                      className="w-full bg-[#090e18] border border-[#162032] rounded px-2 py-1 text-sky-300"
                    />
                  </div>
                </div>
                <span className="text-[10px] text-slate-500 block">
                  Anodic Slope β_a: <strong className="text-sky-300">{fmtTafelQuantity(fitResult.betaA_mV_dec, "mV/dec")}</strong> ({fmtTafelR2(fitResult.anodicR2)})
                </span>
                {fitResult.unavailable?.anodicBranch && (
                  <span role="status" className="text-[10px] text-rose-300 block">{fitResult.unavailable.anodicBranch}</span>
                )}
              </div>

              {/* Manual Micro-Tuning Inputs (Active when manual override checked) */}
              {isManualOverride && (
                <div className="space-y-3 bg-[#0d1626] p-3.5 rounded-xl border border-sky-500/30">
                  <span className="text-sky-300 font-bold block text-[11px] uppercase tracking-wider">
                    Manual Crosshair Positioners
                  </span>

                  <div className="space-y-1">
                    <div className="flex justify-between text-slate-300">
                      <span>E_corr Micro-Tune:</span>
                      <span className="text-emerald-400 font-bold">{(manualEcorr ?? eCorrAnchor).toFixed(4)} V</span>
                    </div>
                    <input aria-label="E_corr Micro-Tune (V)"
                      type="range"
                      min={eCorrAnchor - 0.20}
                      max={eCorrAnchor + 0.20}
                      step="0.001"
                      value={manualEcorr ?? eCorrAnchor}
                      onChange={(e) => setManualEcorr(parseFloat(e.target.value))}
                      className="w-full accent-emerald-400 cursor-pointer"
                    />
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-slate-300">
                      <span>log₁₀(i_corr) Micro-Tune:</span>
                      <span className="text-sky-300 font-bold">{(manualLogIcorr ?? logIcorrAnchor).toFixed(2)} log(µA/cm²)</span>
                    </div>
                    <input aria-label="log₁₀(i_corr) Micro-Tune (log(µA/cm²))"
                      type="range"
                      min={-4.0}
                      max={4.0}
                      step="0.05"
                      value={manualLogIcorr ?? logIcorrAnchor}
                      onChange={(e) => setManualLogIcorr(parseFloat(e.target.value))}
                      className="w-full accent-sky-400 cursor-pointer"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Evans Diagram Chart & Calculated Metrics */}
        <div className="lg:col-span-8 space-y-5">
          {/* Chart Card */}
          <div className="bg-[#090e18] rounded-2xl border border-[#162032] p-5 space-y-4">
            {/* Visualizer Engine Switcher & Python Provenance */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#162032] pb-3">
              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex items-center gap-1 bg-[#050810] p-1 rounded-xl border border-[#162032]">
                  <button
                    type="button"
                    onClick={() => setActiveChartEngine("d3")}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                      activeChartEngine === "d3"
                        ? "bg-sky-500/20 text-sky-300 border border-sky-500/50 shadow-[0_0_12px_rgba(56,189,248,0.25)]"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                    <span>D3.js Interactive Visualizer</span>
                    <span className="px-1.5 py-0.2 rounded text-[9px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      Active
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveChartEngine("recharts")}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                      activeChartEngine === "recharts"
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/50 shadow-[0_0_12px_rgba(52,211,153,0.25)]"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <Activity className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Recharts Classical</span>
                  </button>
                </div>

                {effectiveFitResult.isPythonEngine && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-mono bg-amber-500/10 text-amber-300 border border-amber-500/30">
                    <Cpu className="w-3 h-3 text-amber-400 animate-pulse" />
                    <span>CPython 3.10 Engine ({effectiveFitResult.durationMs?.toFixed(1) || "<1"}ms)</span>
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => runPythonFit(dataset)}
                  disabled={isPythonFitting}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500/20 to-sky-500/20 border border-amber-400/40 hover:border-amber-300 text-amber-300 hover:text-white text-xs font-mono font-bold transition-all disabled:opacity-50"
                  title="Execute high-precision Python CPython 3.10 ASTM G102 Tafel regression"
                >
                  <RefreshCw className={`w-3.5 h-3.5 text-amber-400 ${isPythonFitting ? "animate-spin" : ""}`} />
                  <span>{isPythonFitting ? "Calculating in Python..." : "Recalculate with Python"}</span>
                </button>
              </div>
            </div>

            {pythonFitError && (
              <div role="alert" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-rose-500/10 border border-rose-500/40 text-rose-300 text-xs font-mono">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{pythonFitError} (showing the client-side fit instead; the Python fit was rejected)</span>
              </div>
            )}

            {effectiveFitResult.fitStatus === "unavailable" && (
              <div role="status" className="px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/40 text-amber-200 text-xs font-mono space-y-1">
                <div className="flex items-center gap-2 font-bold">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>Tafel result: {UNAVAILABLE_TEXT}</span>
                </div>
                <p>{effectiveUnavailableReason}</p>
                <p className="text-amber-300/80">
                  Unavailable values are not replaced by assumed slopes, R² or currents. Adjust the fit windows or
                  enter a known E_corr / i_corr with the manual tuning.
                </p>
              </div>
            )}

            {effectiveFitResult.intersectionNote && (
              <div role="status" className="px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/40 text-amber-200 text-xs font-mono">
                E_corr substituted: {effectiveFitResult.intersectionNote}.
              </div>
            )}

            {/* D3.js Interactive Vector Visualizer */}
            {activeChartEngine === "d3" ? (
              <D3TafelPolarizationChart
                dataset={dataset}
                fitResult={effectiveFitResult}
                onRangesChange={(cat, ano) => {
                  setCustomCathodicRange(cat);
                  setCustomAnodicRange(ano);
                }}
                onManualTune={(ecorr, logIcorr) => {
                  setIsManualOverride(true);
                  setManualEcorr(ecorr);
                  setManualLogIcorr(logIcorr);
                }}
                onTriggerPythonRecalculate={() => runPythonFit(dataset)}
                isPythonCalculating={isPythonFitting}
                initialOrientation={chartOrientation}
                height={480}
              />
            ) : (
              <div className="space-y-4">
                {/* Chart Toolbar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#162032] pb-3">
                  <div>
                    <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                      <Activity className="w-4 h-4 text-emerald-400" />
                      {chartOrientation === "evans"
                        ? "Evans Diagram: Potential E (V) vs Log Current Density log₁₀(i)"
                        : "Potentiodynamic Curve: Log Current Density vs Potential E (V)"}
                    </h3>
                    <span className="text-[11px] text-slate-400 font-mono">
                      Intersection at <strong className="text-emerald-300">Ecorr = {fmtTafelQuantity(effectiveFitResult.eCorr, "V")}</strong> &amp;{" "}
                      <strong className="text-sky-300">icorr = {fmtTafelQuantity(effectiveFitResult.iCorr_uA_cm2, "µA/cm²")}</strong>
                    </span>
                  </div>

              {/* View Toggles */}
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => setChartOrientation(chartOrientation === "evans" ? "potentiodynamic" : "evans")}
                  className="px-2.5 py-1 rounded bg-[#050810] hover:bg-[#0d1626] border border-[#162032] text-[11px] font-mono text-slate-300"
                >
                  Flip Axes: {chartOrientation === "evans" ? "E vs log i" : "log i vs E"}
                </button>

                <button
                  type="button"
                  onClick={() => setShowTangentLines(!showTangentLines)}
                  className={`px-2.5 py-1 rounded border text-[11px] font-mono ${
                    showTangentLines
                      ? "bg-sky-500/20 text-sky-300 border-sky-500/40"
                      : "bg-[#050810] text-slate-400 border-[#162032]"
                  }`}
                >
                  Tangents
                </button>

                <button
                  type="button"
                  onClick={() => setShowButlerVolmer(!showButlerVolmer)}
                  className={`px-2.5 py-1 rounded border text-[11px] font-mono ${
                    showButlerVolmer
                      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                      : "bg-[#050810] text-slate-400 border-[#162032]"
                  }`}
                >
                  Butler-Volmer
                </button>
              </div>
            </div>

            {/* Glowing Ecorr / Icorr Highlight Banner */}
            <div className="p-3.5 bg-gradient-to-r from-emerald-950/40 via-[#071322] to-sky-950/40 rounded-xl border border-emerald-500/30 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs font-mono">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center text-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.4)]">
                  <Target className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                    Extrapolated Intersection Point
                  </span>
                  <div className="flex items-center gap-3">
                    <span className="text-emerald-300 font-extrabold text-sm">
                      E_corr = {fitResult.eCorr === null ? UNAVAILABLE_TEXT : `${fitResult.eCorr} V vs ${dataset.metadata.referenceElectrode}`}
                    </span>
                    <span className="text-slate-500">•</span>
                    <span className="text-sky-300 font-extrabold text-sm">
                      i_corr = {fmtTafelQuantity(fitResult.iCorr_uA_cm2, "µA/cm²")}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-full bg-[#050810] border border-[#162032] text-[11px] text-amber-300 font-semibold">
                  Raw Valley: {fitResult.rawEcorrValley} V
                </span>
                <span
                  className={`px-2.5 py-1 rounded-full text-[11px] font-bold border ${
                    fitResult.severity === null
                      ? "bg-slate-500/20 text-slate-300 border-slate-500/40"
                      : fitResult.severity === "Immune / Highly Resistant"
                      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                      : fitResult.severity === "Passivated / Good"
                      ? "bg-sky-500/20 text-sky-300 border-sky-500/40"
                      : fitResult.severity === "Moderate (Caution)"
                      ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                      : "bg-rose-500/20 text-rose-300 border-rose-500/40"
                  }`}
                >
                  {fitResult.severity ?? UNAVAILABLE_TEXT}
                </span>
              </div>
            </div>

            {/* Recharts Chart Canvas */}
            <div className="h-[380px] w-full bg-[#050810] rounded-xl border border-[#162032] p-3 relative">
              {chartOrientation === "evans" ? (
                // ASTM G102 Standard Evans Diagram: X = Log(i), Y = Potential E
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartPoints} margin={{ top: 15, right: 35, left: 15, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#162032" />
                    <XAxis
                      dataKey="logI_exp"
                      type="number"
                      domain={["auto", "auto"]}
                      stroke="#64748b"
                      tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "monospace" }}
                      label={{
                        value: "Log Current Density log₁₀(i, µA/cm²)",
                        position: "bottom",
                        offset: 0,
                        fill: "#94a3b8",
                        fontSize: 11,
                        fontFamily: "monospace",
                      }}
                    />
                    <YAxis
                      dataKey="potential"
                      type="number"
                      domain={["auto", "auto"]}
                      stroke="#64748b"
                      tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "monospace" }}
                      label={{
                        value: `Potential E (V vs ${dataset.metadata.referenceElectrode})`,
                        angle: -90,
                        position: "left",
                        offset: -5,
                        fill: "#94a3b8",
                        fontSize: 11,
                        fontFamily: "monospace",
                      }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#090e18",
                        borderColor: "#1e2d46",
                        borderRadius: 8,
                        fontSize: 11,
                        fontFamily: "monospace",
                      }}
                      formatter={(val: any, name: any) => [
                        typeof val === "number" ? val.toFixed(4) : val,
                        name,
                      ]}
                      labelFormatter={(label) => `log₁₀(i) = ${typeof label === "number" ? label.toFixed(3) : label}`}
                    />
                    <Legend wrapperStyle={{ fontSize: "11px", fontFamily: "monospace" }} />

                    {/* Ecorr Horizontal Reference Line (only when the Evans intersection is available) */}
                    {fitResult.eCorr !== null && (
                      <ReferenceLine
                        y={fitResult.eCorr}
                        stroke="#10b981"
                        strokeWidth={2}
                        strokeDasharray="4 4"
                        label={{
                          value: `E_corr = ${fitResult.eCorr} V`,
                          position: "right",
                          fill: "#10b981",
                          fontSize: 10,
                          fontFamily: "monospace",
                        }}
                      />
                    )}

                    {/* Log(Icorr) Vertical Reference Line (only when i_corr is available) */}
                    {fitResult.logIcorr !== null && (
                      <ReferenceLine
                        x={fitResult.logIcorr}
                        stroke="#38bdf8"
                        strokeWidth={2}
                        strokeDasharray="4 4"
                        label={{
                          value: `i_corr = ${fitResult.iCorr_uA_cm2} µA`,
                          position: "top",
                          fill: "#38bdf8",
                          fontSize: 10,
                          fontFamily: "monospace",
                        }}
                      />
                    )}

                    {/* Experimental Polarization Curve */}
                    <Line
                      type="monotone"
                      dataKey="potential"
                      name="Experimental Scan"
                      stroke="#e2e8f0"
                      strokeWidth={2.2}
                      dot={showRawPoints ? { r: 2, fill: "#e2e8f0" } : false}
                      isAnimationActive={false}
                    />

                    {/* Anodic Tafel Tangent Line */}
                    {showTangentLines && (
                      <Line
                        type="linear"
                        dataKey="tangentAnodic"
                        name={`Anodic Tangent (β_a=${fmtTafelQuantity(fitResult.betaA_mV_dec, "mV")})`}
                        stroke="#38bdf8"
                        strokeWidth={2.5}
                        strokeDasharray="5 3"
                        dot={false}
                        connectNulls={false}
                        isAnimationActive={false}
                      />
                    )}

                    {/* Cathodic Tafel Tangent Line */}
                    {showTangentLines && (
                      <Line
                        type="linear"
                        dataKey="tangentCathodic"
                        name={`Cathodic Tangent (β_c=${fmtTafelQuantity(fitResult.betaC_mV_dec, "mV")})`}
                        stroke="#f59e0b"
                        strokeWidth={2.5}
                        strokeDasharray="5 3"
                        dot={false}
                        connectNulls={false}
                        isAnimationActive={false}
                      />
                    )}

                    {/* Butler-Volmer Synthetic Curve */}
                    {showButlerVolmer && (
                      <Line
                        type="monotone"
                        dataKey="butlerVolmer"
                        name="Butler-Volmer Fit"
                        stroke="#10b981"
                        strokeWidth={1.8}
                        strokeDasharray="2 2"
                        dot={false}
                        isAnimationActive={false}
                      />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                // Potentiodynamic Curve: X = Potential E, Y = Log Current Density
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartPoints} margin={{ top: 15, right: 35, left: 15, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#162032" />
                    <XAxis
                      dataKey="potential"
                      stroke="#64748b"
                      tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "monospace" }}
                      label={{
                        value: `Potential E (V vs ${dataset.metadata.referenceElectrode})`,
                        position: "bottom",
                        offset: 0,
                        fill: "#94a3b8",
                        fontSize: 11,
                        fontFamily: "monospace",
                      }}
                    />
                    <YAxis
                      dataKey="logI_exp"
                      stroke="#64748b"
                      tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "monospace" }}
                      label={{
                        value: "Log Current Density log₁₀(i, µA/cm²)",
                        angle: -90,
                        position: "left",
                        offset: -5,
                        fill: "#94a3b8",
                        fontSize: 11,
                        fontFamily: "monospace",
                      }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#090e18",
                        borderColor: "#1e2d46",
                        borderRadius: 8,
                        fontSize: 11,
                        fontFamily: "monospace",
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: "11px", fontFamily: "monospace" }} />

                    {fitResult.eCorr !== null && (
                      <ReferenceLine x={fitResult.eCorr} stroke="#10b981" strokeWidth={2} strokeDasharray="4 4" />
                    )}
                    {fitResult.logIcorr !== null && (
                      <ReferenceLine y={fitResult.logIcorr} stroke="#38bdf8" strokeWidth={2} strokeDasharray="4 4" />
                    )}

                    <Line
                      type="monotone"
                      dataKey="logI_exp"
                      name="Experimental Scan"
                      stroke="#e2e8f0"
                      strokeWidth={2.2}
                      dot={showRawPoints ? { r: 2, fill: "#e2e8f0" } : false}
                    />
                    {showTangentLines && (
                      <Line
                        type="linear"
                        dataKey="tangentAnodic"
                        name="Anodic Tangent"
                        stroke="#38bdf8"
                        strokeWidth={2.5}
                        strokeDasharray="5 3"
                        dot={false}
                      />
                    )}
                    {showTangentLines && (
                      <Line
                        type="linear"
                        dataKey="tangentCathodic"
                        name="Cathodic Tangent"
                        stroke="#f59e0b"
                        strokeWidth={2.5}
                        strokeDasharray="5 3"
                        dot={false}
                      />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        )}
      </div>

          {/* Detailed ASTM Metrics Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* Ecorr Card */}
            <div className="p-3.5 bg-[#090e18] rounded-xl border border-[#162032] space-y-1 font-mono">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Corrosion Potential (Ecorr)
              </span>
              <div className="text-emerald-400 font-extrabold text-base">
                {fmtTafelQuantity(effectiveFitResult.eCorr, "V")}
              </div>
              <span className="text-[10px] text-slate-500 block">
                {effectiveFitResult.eCorrSHE === null ? UNAVAILABLE_TEXT : `${effectiveFitResult.eCorrSHE} V vs SHE`}
              </span>
            </div>

            {/* Icorr Card */}
            <div className="p-3.5 bg-[#090e18] rounded-xl border border-[#162032] space-y-1 font-mono">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Corrosion Current (icorr)
              </span>
              <div className="text-sky-400 font-extrabold text-base">
                {fmtTafelQuantity(effectiveFitResult.iCorr_uA_cm2, "µA/cm²")}
              </div>
              <span className="text-[10px] text-slate-500 block">
                Total: {fmtTafelQuantity(effectiveFitResult.totalCurrentIcorr_uA, "µA")}
              </span>
            </div>

            {/* Polarization Resistance Rp */}
            <div className="p-3.5 bg-[#090e18] rounded-xl border border-[#162032] space-y-1 font-mono">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Polarization Res. (Rp)
              </span>
              <div className="text-purple-400 font-extrabold text-base">
                {fmtTafelQuantity(effectiveFitResult.rp_ohm_cm2, "Ω·cm²", { grouped: true, digits: 0 })}
              </div>
              <span className="text-[10px] text-slate-500 block">
                B = {fmtTafelQuantity(effectiveFitResult.sternGearyB_V, "V")} (ASTM G59)
              </span>
            </div>

            {/* Faraday Penetration Rate */}
            <div className="p-3.5 bg-[#090e18] rounded-xl border border-[#162032] space-y-1 font-mono">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Corrosion Rate (CR)
              </span>
              <div className="text-amber-400 font-extrabold text-base">
                {fmtTafelQuantity(effectiveFitResult.corrosionRateMmYr, "mm/yr")}
              </div>
              <span className="text-[10px] text-slate-500 block">
                {fmtTafelQuantity(effectiveFitResult.corrosionRateMpy, "mpy")}
              </span>
            </div>
          </div>

          {/* Secondary Telemetry Table */}
          <div className="p-4 bg-[#090e18] rounded-xl border border-[#162032] font-mono text-xs space-y-2">
            <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
              ASTM G102 Electrochemical Kinetics Summary
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-[11px]">
              <div className="p-2.5 bg-[#050810] rounded border border-[#162032]">
                <span className="text-slate-500 block text-[10px]">Anodic Slope (β_a):</span>
                <span className="text-sky-300 font-bold">{fmtTafelQuantity(effectiveFitResult.betaA_mV_dec, "mV/dec")}</span>
                <span className="text-[9px] text-slate-500 block mt-0.5">Fit {fmtTafelR2(effectiveFitResult.anodicR2)}</span>
              </div>
              <div className="p-2.5 bg-[#050810] rounded border border-[#162032]">
                <span className="text-slate-500 block text-[10px]">Cathodic Slope (β_c):</span>
                <span className="text-amber-300 font-bold">{fmtTafelQuantity(effectiveFitResult.betaC_mV_dec, "mV/dec")}</span>
                <span className="text-[9px] text-slate-500 block mt-0.5">Fit {fmtTafelR2(effectiveFitResult.cathodicR2)}</span>
              </div>
              <div className="p-2.5 bg-[#050810] rounded border border-[#162032]">
                <span className="text-slate-500 block text-[10px]">Daily Mass Loss Rate:</span>
                <span className="text-white font-bold">{fmtTafelQuantity(effectiveFitResult.massLoss_g_m2_day, "g/(m²·day)")}</span>
                <span className="text-[9px] text-slate-500 block mt-0.5">Faraday constant F=96485 C</span>
              </div>
              <div className="p-2.5 bg-[#050810] rounded border border-[#162032]">
                <span className="text-slate-500 block text-[10px]">Pitting Breakdown (E_pit):</span>
                <span className={`${effectiveFitResult.pittingPotentialEpit_V ? "text-rose-400 font-bold" : "text-slate-400 font-bold"}`}>
                  {effectiveFitResult.pittingPotentialEpit_V ? `${effectiveFitResult.pittingPotentialEpit_V} V` : "No pit breakdown"}
                </span>
                <span className="text-[9px] text-slate-500 block mt-0.5">
                  {effectiveFitResult.pittingPotentialEpit_V ? "Localized attack onset" : "Passive oxide stable"}
                </span>
              </div>
            </div>
          </div>

          {/* Automated Python ASTM G102 Annual Corrosion Rate Module (Connected to Icorr) */}
          <PythonAnnualCorrosionRateModule
            tafelFit={effectiveFitResult}
            dataset={dataset}
            className="border-[#162032] !bg-[#090e18]"
          />
        </div>
      </div>

      {/* 5. PASTE RAW TEXT MODAL */}
      {isPasteModalOpen && (
        <AccessibleModal
          open
          onClose={() => setIsPasteModalOpen(false)}
          label="Paste polarization data"
          overlayClassName="bg-black/75 p-4 backdrop-blur-sm"
          panelClassName="bg-[#090e18] border border-[#1e2d46] rounded-2xl max-w-2xl w-full p-5 space-y-4 shadow-2xl animate-fadeIn"
        >
            <div className="flex items-center justify-between border-b border-[#162032] pb-3">
              <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                <FileText className="w-4 h-4 text-sky-400" />
                <span>Paste Experimental Potentiodynamic Data</span>
              </h3>
              <button
                type="button"
                onClick={() => setIsPasteModalOpen(false)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-400 font-mono">
              Paste two columns (Potential V and Current A/mA/µA) separated by tabs, commas, or spaces from Excel, Origin, or instrument logs:
            </p>

            <textarea aria-label="Paste two columns (Potential V and Current A/mA/µA)"
              rows={10}
              value={pastedText}
              onChange={(e) => setPastedText(e.target.value)}
              placeholder={`Potential(V)\tCurrent(A)\n-0.600\t1.42e-5\n-0.550\t2.84e-6\n-0.500\t5.12e-7\n-0.450\t8.20e-8\n-0.400\t4.15e-7\n-0.350\t2.20e-6\n-0.300\t1.65e-5\n-0.250\t1.10e-4`}
              className="w-full bg-[#050810] border border-[#162032] rounded-xl p-3 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-400"
            />

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsPasteModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-[#050810] border border-[#162032] text-xs font-mono text-slate-300 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handlePasteSubmit}
                className="px-4 py-2 rounded-xl bg-emerald-500 text-black font-bold text-xs font-mono hover:bg-emerald-400 shadow-[0_0_14px_rgba(52,211,153,0.3)]"
              >
                Ingest &amp; Calculate Ecorr / Icorr
              </button>
            </div>
        </AccessibleModal>
      )}
    </div>
  );
}
