import { createUqRunSession } from '../utils/uqRunSession';
import { useEscapeToClose } from "./AccessibleModal";
import { CouponSummary, CouponWorksheet, formatUqNumber } from './UqCouponReport';
import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Activity,
  Zap,
  TrendingUp,
  Sliders,
  Sparkles,
  Info,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Play,
  Download,
  Upload,
  FileSpreadsheet,
  Check,
  Atom,
  BarChart3,
  Scale,
  Copy,
  Plus,
  Trash2,
  Filter,
  Layers,
  Search,
  FileText,
  Database,
  Cpu,
  Award,
  ArrowRight,
  Split,
  ChevronDown,
  ChevronUp,
  SlidersHorizontal,
  Table as TableIcon
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  AreaChart,
  Area,
  Line,
  ComposedChart,
  Cell
} from "recharts";
import {
  pythonComputationService,
  PythonStochasticUQResult,
  StochasticPropertyStats
} from "../services/pythonComputationService";
import {
  AEROSPACE_MATERIAL_DATASETS,
  MaterialDataset,
  CouponTestSpecimen,
  MMPDSEmpiricalAllowableStats,
  computeMMPDSEmpiricalStats,
  calculateMMPDSToleranceFactor,
  generateSyntheticCoupons,
  parseCSVToCoupons,
  exportCouponsToCSV,
  isSyntheticCouponDataset
} from "./uqLabData";
import { ENGINEERING_ESTIMATE_DISCLAIMER, EngineeringEstimateBanner, SYNTHETIC_COUPON_MMPDS_NOTICE } from "../utils/engineeringDisclaimer";

interface UQLabProps {
  onNavigate?: (tabId: string) => void;
}

export function UQLab({ onNavigate }: UQLabProps) {
  // Active Dataset
  const [datasets, setDatasets] = useState<MaterialDataset[]>(AEROSPACE_MATERIAL_DATASETS);
  const [activeDatasetId, setActiveDatasetId] = useState<string>("inconel718-ams5664");
  
  const activeDataset = useMemo(() => {
    return datasets.find((d) => d.id === activeDatasetId) || datasets[0];
  }, [datasets, activeDatasetId]);

  // Solver Engine Configuration
  const [samplingMethod, setSamplingMethod] = useState<"sobol_qmc" | "pseudo_mc">("sobol_qmc");
  const [scramble, setScramble] = useState<boolean>(true);
  const [mcSamples, setMcSamples] = useState<number>(2500);
  const [seed, setSeed] = useState<number>(42);

  // Active Tab
  const [activeViewTab, setActiveViewTab] = useState<"distribution" | "sensitivity" | "coupons" | "comparison" | "certificate">("distribution");
  const [selectedProperty, setSelectedProperty] = useState<"yieldStrength" | "uts" | "elongation">("yieldStrength");

  // Coupon Search & Filter
  const [searchLot, setSearchLot] = useState<string>("");
  const [couponPage, setCouponPage] = useState<number>(1);
  const couponsPerPage = 10;

  // File Upload Ref
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isSynthesizeModalOpen, setIsSynthesizeModalOpen] = useState<boolean>(false);
  useEscapeToClose(isSynthesizeModalOpen, () => setIsSynthesizeModalOpen(false));
  const [synthSampleSize, setSynthSampleSize] = useState<number>(40);
  const [synthLotCount, setSynthLotCount] = useState<number>(4);

  // Python QMC Computation Result
  const [resultRecord, setResultRecord] = useState<{ key: string; result: PythonStochasticUQResult } | null>(null);
  const requestSession = useRef(createUqRunSession<PythonStochasticUQResult>());
  const requestKey = JSON.stringify({ id: activeDataset.id, chemistry: activeDataset.nominalChemistry, tolerances: activeDataset.chemicalTolerances, thermal: activeDataset.nominalThermal, minima: [activeDataset.specMinYieldMPa, activeDataset.specMinUTSMPa, activeDataset.specMinElongationPct], mcSamples, samplingMethod, scramble, seed });
  const uqResult = resultRecord?.key === requestKey ? resultRecord.result : null;
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastRunTimestamp, setLastRunTimestamp] = useState<string>("");

  // Copy Feedback
  const [copiedNotification, setCopiedNotification] = useState<string | null>(null);

  // --------------------------------------------------------------------------
  // EMPIRICAL DATASET STATS CALCULATION
  // --------------------------------------------------------------------------
  const empiricalStats = useMemo(() => {
    const coupons = activeDataset.coupons;
    const rawLotIds = coupons.map((c) => c.heatLotId);
    const lotIds = rawLotIds.some(id => id.trim()) ? rawLotIds : [];

    let values: number[] = [];
    let specMin = 0;

    if (selectedProperty === "yieldStrength") {
      values = coupons.map((c) => c.yieldStrengthMPa);
      specMin = activeDataset.specMinYieldMPa;
    } else if (selectedProperty === "uts") {
      values = coupons.map((c) => c.utsMPa);
      specMin = activeDataset.specMinUTSMPa;
    } else {
      values = coupons.map((c) => c.elongationPct);
      specMin = activeDataset.specMinElongationPct;
    }

    return computeMMPDSEmpiricalStats(values, specMin, lotIds);
  }, [activeDataset, selectedProperty]);

  const isSyntheticCoupons = isSyntheticCouponDataset(activeDataset);
  const showMmpdsAllowables = !isSyntheticCoupons && empiricalStats.toleranceEligible;

  // --------------------------------------------------------------------------
  // RUN PYTHON QMC SOBOL SOLVER
  // --------------------------------------------------------------------------
  const runQMCSolver = useCallback(async () => {
    const key = requestKey;
    await requestSession.current.run(async () => {
      const res = await pythonComputationService.calculateStochasticUQMMPDS({
        alloyName: activeDataset.name,
        baseMetal: activeDataset.baseMetal,
        coolingRate_nominal: activeDataset.nominalThermal.coolingRate_K_s,
        coolingRate_cov: activeDataset.nominalThermal.coolingRateCov,
        agingTemp_nominal: activeDataset.nominalThermal.agingTemp_C,
        agingTemp_stdDev: activeDataset.nominalThermal.agingTempStd,
        agingTime_nominal: activeDataset.nominalThermal.agingTime_h,
        serviceStress_nominal: activeDataset.nominalThermal.serviceStress_MPa,
        composition_wt: activeDataset.nominalChemistry,
        composition_tolerances: activeDataset.chemicalTolerances,
        specMinYield_MPa: activeDataset.specMinYieldMPa,
        specMinUTS_MPa: activeDataset.specMinUTSMPa,
        specMinElongation_pct: activeDataset.specMinElongationPct,
        mcSamples,
        samplingMethod,
        scramble,
        seed
      });
      if (!res.success) throw new Error('UQ solver did not return a successful result.');
      return res;
    }, state => {
      setIsLoading(state.loading);
      setErrorMsg(state.error);
      setResultRecord(state.result ? { key, result: state.result } : null);
      if (state.result) setLastRunTimestamp(new Date().toLocaleTimeString());
    });
  }, [requestKey]);

  useEffect(() => {
    void runQMCSolver();
    return () => requestSession.current.invalidate();
  }, [runQMCSolver]);

  // --------------------------------------------------------------------------
  // DATASET MODIFICATION HANDLERS
  // --------------------------------------------------------------------------
  const handleCSVUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const datasetId = activeDataset.id;
    if (file.size > 5 * 1024 * 1024) { setErrorMsg('Coupon CSV exceeds the 5 MB limit. Existing coupons were preserved.'); e.target.value = ''; return; }
    setErrorMsg(null);
    const reader = new FileReader();
    reader.onload = evt => {
      try {
        const parsedCoupons = parseCSVToCoupons(String(evt.target?.result ?? ''), datasetId);
        if (!parsedCoupons.length) throw new Error('CSV contains no coupon records.');
        setDatasets(prev => prev.map(d => d.id === datasetId ? { ...d, coupons: parsedCoupons, couponSource: parsedCoupons.some(c => c.evidenceOrigin === 'synthetic') ? 'synthetic' : 'uploaded' } : d));
        setCouponPage(1);
      } catch (error) { setErrorMsg(`${error instanceof Error ? error.message : 'Unable to read coupon CSV.'} Existing coupons were preserved.`); }
    };
    reader.onerror = () => setErrorMsg('Unable to read coupon CSV. Existing coupons were preserved.');
    reader.readAsText(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleExportCSV = () => {
    const csvContent = exportCouponsToCSV(activeDataset.coupons, activeDataset.name);
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `MMPDS_Dataset_${activeDataset.id}_Coupons.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleSynthesizeBatch = () => {
    if (!Number.isInteger(synthSampleSize) || synthSampleSize < 10 || synthSampleSize > 200 || !Number.isInteger(synthLotCount) || synthLotCount < 2 || synthLotCount > 12 || synthLotCount > synthSampleSize) { setErrorMsg("Synthetic samples must be 10–200, with 2–12 lots and no more lots than samples."); return; }
    setErrorMsg(null);
    const newCoupons = generateSyntheticCoupons({
      datasetId: activeDataset.id,
      sampleSize: synthSampleSize,
      lotCount: synthLotCount,
      meanYield: activeDataset.specMinYieldMPa + 80,
      stdYield: 28,
      meanUTS: activeDataset.specMinUTSMPa + 70,
      stdUTS: 24,
      meanElongation: activeDataset.specMinElongationPct + 4.5,
      stdElongation: 1.6,
      testStandard: "ASTM E8M / MMPDS-01"
    });

    setDatasets((prev) =>
      prev.map((d) => (d.id === activeDataset.id ? { ...d, coupons: newCoupons, couponSource: "synthetic" } : d))
    );
    setIsSynthesizeModalOpen(false);
    setCouponPage(1);
  };

  const handleDeleteCoupon = (couponId: string) => {
    setDatasets((prev) =>
      prev.map((d) =>
        d.id === activeDataset.id
          ? { ...d, coupons: d.coupons.filter((c) => c.id !== couponId) }
          : d
      )
    );
  };

  const copyToClipboard = async (text: string, label: string) => {
    try { await navigator.clipboard.writeText(text); setCopiedNotification(label); setTimeout(() => setCopiedNotification(null), 2500); }
    catch { setErrorMsg("Clipboard unavailable. No copy was confirmed."); }
  };

  // Property Metadata Helper
  const propertyMeta = useMemo(() => {
    switch (selectedProperty) {
      case "yieldStrength":
        return {
          title: "Yield Strength (0.2% Offset)",
          symbol: "F_ty / R_p0.2",
          unit: "MPa",
          specMin: activeDataset.specMinYieldMPa,
          stochasticStat: uqResult?.stochasticProperties?.yieldStrength_Rp02
        };
      case "uts":
        return {
          title: "Ultimate Tensile Strength",
          symbol: "F_tu / R_m",
          unit: "MPa",
          specMin: activeDataset.specMinUTSMPa,
          stochasticStat: uqResult?.stochasticProperties?.ultimateTensileStrength_UTS
        };
      case "elongation":
        return {
          title: "Total Elongation at Break",
          symbol: "e / A_%",
          unit: "%",
          specMin: activeDataset.specMinElongationPct,
          stochasticStat: uqResult?.stochasticProperties?.elongationPct
        };
    }
  }, [selectedProperty, activeDataset, uqResult]);

  // Combined Chart Histogram Data
  const chartData = useMemo(() => {
    if (!empiricalStats.histogram || empiricalStats.histogram.length === 0) return [];

    const mean = empiricalStats.mean;
    const s = empiricalStats.stdDev;

    return empiricalStats.histogram.map((bin) => {
      // Gaussian PDF theoretical value
      let gaussianDensity = 0;
      if (s > 0) {
        const z = (bin.midpoint - mean) / s;
        gaussianDensity = (1 / (s * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * z * z);
      }

      return {
        midpoint: bin.midpoint,
        binLabel: `${bin.midpoint}`,
        couponCount: bin.count,
        empiricalDensity: bin.density,
        gaussianCurve: parseFloat((gaussianDensity * empiricalStats.sampleSize * (bin.binEnd - bin.binStart)).toFixed(1))
      };
    });
  }, [empiricalStats]);

  // Filtered Coupons for Tabular View
  const filteredCoupons = useMemo(() => {
    return activeDataset.coupons.filter(
      (c) =>
        !searchLot ||
        c.heatLotId.toLowerCase().includes(searchLot.toLowerCase()) ||
        c.specimenNumber.toLowerCase().includes(searchLot.toLowerCase())
    );
  }, [activeDataset.coupons, searchLot]);

  const totalPages = Math.ceil(filteredCoupons.length / couponsPerPage) || 1;
  useEffect(() => setCouponPage(page => Math.min(page, totalPages)), [totalPages]);
  const paginatedCoupons = useMemo(() => {
    const start = (couponPage - 1) * couponsPerPage;
    return filteredCoupons.slice(start, start + couponsPerPage);
  }, [filteredCoupons, couponPage, couponsPerPage]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {errorMsg && <p role="alert" className="rounded-xl border border-rose-700 bg-rose-950/30 p-3 text-sm text-rose-200">{errorMsg}</p>}
      <p className="text-xs text-slate-400">Coupon edits and uploads are session-only. Export CSV before reloading. Missing measurements and provenance are never inferred from the selected material preset.</p>
      {/* ==================================================================== */}
      {/* 1. HERO HEADER BANNER & QMC BADGES */}
      {/* ==================================================================== */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-slate-900/95 to-slate-950 p-6 md:p-8 border border-slate-800 shadow-2xl">
        <div className="absolute -right-20 -top-20 w-80 h-80 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute right-1/4 -bottom-20 w-60 h-60 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30 flex items-center gap-1.5 shadow-sm">
                <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
                Normal-model statistics (screening)
              </span>

              {samplingMethod === "sobol_qmc" ? (
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5 shadow-sm">
                  <Zap className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
                  Sobol sampling · screening
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                  Pseudo-Random PRNG
                </span>
              )}

              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Coupons: {activeDataset.coupons.length} | Heats: {empiricalStats.lotCount}
              </span>
            </div>

            <h1 className="text-2xl md:text-3xl font-bold text-slate-100 tracking-tight flex items-center gap-2.5">
              <ShieldCheck className="w-7 h-7 text-sky-400" />
              UQ-Lab: Quasi-Monte Carlo & Coupon Scatter
            </h1>

            <p className="text-xs md:text-sm text-slate-400 max-w-3xl leading-relaxed">
              Propagate composition tolerances and thermal scatter using{" "}
              <strong className="text-amber-300">Quasi-Monte Carlo Sobol sequences</strong> for teaching and screening.
              Uploaded CSV values remain unverified; normal-model tolerance estimates do not establish MMPDS handbook allowables.
            </p>
            <EngineeringEstimateBanner className="mt-3 max-w-3xl" />
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={runQMCSolver}
              disabled={isLoading}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 to-sky-400 hover:from-sky-400 hover:to-sky-300 text-slate-950 font-bold text-xs transition flex items-center gap-2 shadow-lg shadow-sky-500/25 disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
              {isLoading ? "Running QMC Sobol..." : "Run QMC Solver"}
            </button>

            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-3.5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5 cursor-pointer"
              title="Upload CSV coupon test data"
            >
              <Upload className="w-3.5 h-3.5 text-sky-400" />
              Upload CSV
            </button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleCSVUpload}
              accept=".csv"
              className="hidden"
            />

            <button
              onClick={() => setIsSynthesizeModalOpen(true)}
              className="px-3.5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5 cursor-pointer"
              title="Generate synthetic lot batches"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              Synthesize Lot
            </button>

            <button
              onClick={handleExportCSV}
              className="px-3.5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5 cursor-pointer"
              title="Export active coupons as CSV"
            >
              <Download className="w-3.5 h-3.5 text-emerald-400" />
              Export
            </button>
          </div>
        </div>

        {/* QMC TELEMETRY STRIP (FROM PYTHON SOLVER) */}
        {uqResult?.samplingMetadata && (
          <div className="mt-5 p-3.5 rounded-2xl bg-slate-950/80 border border-amber-500/30 font-mono text-xs shadow-inner">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="p-1 rounded-md bg-amber-500/20 text-amber-400 border border-amber-500/40">
                  <Zap className="w-3.5 h-3.5" />
                </span>
                <span className="font-bold text-slate-200">
                  {uqResult.samplingMetadata.samplingMethod === "sobol_qmc"
                    ? "Sobol digital-net sampling diagnostics"
                    : "Standard Pseudo-Random Monte Carlo (PRNG)"}
                </span>
                <span className="text-[10px] text-slate-400 hidden md:inline">
                  — {uqResult.samplingMetadata.samplingDescription}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px]">
                  Rate: {uqResult.samplingMetadata.theoreticalConvergenceRate}
                </span>
                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold">
                  Speedup not estimated
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-2.5 text-[11px]">
              <div className="p-2 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[9px] text-slate-400">PROPAGATED SAMPLES</div>
                <div className="font-bold text-amber-300 mt-0.5">
                  {uqResult.sampleSizeN.toLocaleString()}
                  <span className="text-[9px] text-slate-400 font-normal ml-1">
                    (actual N; effective N not estimated)
                  </span>
                </div>
              </div>
              <div className="p-2 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[9px] text-slate-400">CENTERED L2 DISCREPANCY</div>
                <div className="font-bold text-sky-300 mt-0.5">
                  {formatUqNumber(uqResult.samplingMetadata.centeredL2Discrepancy, 5)}
                  <span className="text-[9px] text-emerald-400 font-normal ml-1">
                    (first {uqResult.samplingMetadata.discrepancySampleSize} points)
                  </span>
                </div>
              </div>
              <div className="p-2 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[9px] text-slate-400">VARIANCE REDUCTION (VRR)</div>
                <div className="font-bold text-emerald-300 mt-0.5">
                  Not estimated
                  <span className="text-[9px] text-slate-400 font-normal ml-1">independent replicate comparison required</span>
                </div>
              </div>
              <div className="p-2 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-[9px] text-slate-400">EXECUTION LATENCY</div>
                <div className="font-bold text-purple-300 mt-0.5">
                  {uqResult.computeTimeMs.toFixed(1)} ms
                  <span className="text-[9px] text-slate-400 font-normal ml-1">reported solver time</span>
                </div>
              </div>
            </div>
            <p className="mt-2 text-[11px] text-slate-400">{uqResult.samplingMetadata.diagnosticsLimitations}</p>
          </div>
        )}
      </div>

      {/* ==================================================================== */}
      {/* 2. DATASET SELECTOR & SAMPLING ENGINE CONFIGURATION */}
      {/* ==================================================================== */}
      <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          {/* Material Dataset Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 lg:pb-0">
            <span className="text-xs font-semibold text-slate-400 flex items-center gap-1 shrink-0">
              <Database className="w-3.5 h-3.5 text-sky-400" />
              Dataset:
            </span>
            <div className="flex items-center gap-1.5 shrink-0">
              {datasets.map((d) => (
                <button
                  key={d.id}
                  onClick={() => {
                    setActiveDatasetId(d.id);
                    setCouponPage(1);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium transition cursor-pointer whitespace-nowrap ${
                    activeDatasetId === d.id
                      ? "bg-sky-500 text-slate-950 font-bold shadow-md shadow-sky-500/20"
                      : "bg-slate-800/80 text-slate-300 hover:bg-slate-700 border border-slate-700/60"
                  }`}
                >
                  {d.name.split("(")[0].trim()}
                </button>
              ))}
            </div>
          </div>

          {/* Engine Parameters Controls */}
          <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
            {/* Method Toggle */}
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400">Engine:</span>
              <div className="inline-flex rounded-lg bg-slate-800 p-0.5 border border-slate-700">
                <button
                  onClick={() => setSamplingMethod("sobol_qmc")}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold flex items-center gap-1 transition cursor-pointer ${
                    samplingMethod === "sobol_qmc"
                      ? "bg-amber-500 text-slate-950 shadow"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <Zap className="w-3 h-3" />
                  Sobol QMC
                </button>
                <button
                  onClick={() => setSamplingMethod("pseudo_mc")}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                    samplingMethod === "pseudo_mc"
                      ? "bg-sky-500 text-slate-950 shadow"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Pseudo-MC
                </button>
              </div>
            </div>

            {/* Scrambling */}
            {samplingMethod === "sobol_qmc" && (
              <label className="flex items-center gap-1.5 cursor-pointer text-[11px] text-slate-300 select-none">
                <input
                  type="checkbox"
                  checked={scramble}
                  onChange={(e) => setScramble(e.target.checked)}
                  className="rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-0 w-3.5 h-3.5 cursor-pointer"
                />
                <span>Digital shift</span>
              </label>
            )}

            {/* Samples */}
            <div className="flex items-center gap-1.5 text-slate-400">
              <span>Runs:</span>
              <select
                value={mcSamples}
                onChange={(e) => setMcSamples(parseInt(e.target.value))}
                className="bg-slate-800 border border-slate-700 text-sky-300 rounded-lg px-2 py-1 text-xs"
              >
                <option value="1000">1,000 runs</option>
                <option value="2500">2,500 runs</option>
                <option value="5000">5,000 runs</option>
                <option value="10000">10,000 runs</option>
              </select>
            </div>
          </div>
        </div>

        {/* Dataset Details Metadata */}
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span>
              <strong className="text-slate-400">Spec:</strong>{" "}
              <span className="text-sky-300 font-mono">{activeDataset.specification}</span>
            </span>
            <span>
              <strong className="text-slate-400">MMPDS:</strong>{" "}
              <span className="text-slate-300 font-mono">{activeDataset.mmpdsChapter}</span>
            </span>
            <span>
              <strong className="text-slate-400">Product:</strong>{" "}
              <span className="text-slate-300">{activeDataset.productForm}</span>
            </span>
            <span>
              <strong className="text-slate-400">Heat Treat:</strong>{" "}
              <span className="text-slate-300">{activeDataset.heatTreatment}</span>
            </span>
          </div>

          <div className="flex items-center gap-2 text-[11px] font-mono">
            <span className="text-slate-400">Spec Minimums:</span>
            <span className="px-2 py-0.5 rounded bg-sky-950/60 text-sky-300 border border-sky-800/60">
              F_ty ≥ {activeDataset.specMinYieldMPa} MPa
            </span>
            <span className="px-2 py-0.5 rounded bg-sky-950/60 text-sky-300 border border-sky-800/60">
              F_tu ≥ {activeDataset.specMinUTSMPa} MPa
            </span>
            <span className="px-2 py-0.5 rounded bg-sky-950/60 text-sky-300 border border-sky-800/60">
              e ≥ {activeDataset.specMinElongationPct}%
            </span>
          </div>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* 3. EXECUTIVE ALLOWABLE COMPARISON KPI CARDS */}
      {/* ==================================================================== */}
      <CouponSummary stats={empiricalStats} unit={propertyMeta.unit} synthetic={isSyntheticCoupons} />

      {/* ==================================================================== */}
      {/* 4. WORKFLOW TABS: DISTRIBUTION, SENSITIVITY, COUPONS, CERTIFICATE */}
      {/* ==================================================================== */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2 flex-wrap gap-2">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveViewTab("distribution")}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition cursor-pointer ${
              activeViewTab === "distribution"
                ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            Distribution & Allowables (PDF/CDF)
          </button>

          <button
            onClick={() => setActiveViewTab("sensitivity")}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition cursor-pointer ${
              activeViewTab === "sensitivity"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5" />
            Saltelli-Sobol Global Sensitivity
          </button>

          <button
            onClick={() => setActiveViewTab("coupons")}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition cursor-pointer ${
              activeViewTab === "coupons"
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <TableIcon className="w-3.5 h-3.5" />
            Coupon Test Batch QC ({activeDataset.coupons.length})
          </button>

          <button
            onClick={() => setActiveViewTab("certificate")}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition cursor-pointer ${
              activeViewTab === "certificate"
                ? "bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            Screening report
          </button>
        </div>

        {/* Property Selector for Distribution & Metrics */}
        <div className="flex items-center gap-1.5 text-xs font-mono">
          <span className="text-slate-400">Property:</span>
          <div className="inline-flex rounded-lg bg-slate-800 p-0.5 border border-slate-700">
            <button
              onClick={() => setSelectedProperty("yieldStrength")}
              className={`px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                selectedProperty === "yieldStrength"
                  ? "bg-sky-500 text-slate-950 shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Yield (F_ty)
            </button>
            <button
              onClick={() => setSelectedProperty("uts")}
              className={`px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                selectedProperty === "uts"
                  ? "bg-sky-500 text-slate-950 shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              UTS (F_tu)
            </button>
            <button
              onClick={() => setSelectedProperty("elongation")}
              className={`px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                selectedProperty === "elongation"
                  ? "bg-sky-500 text-slate-950 shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Elongation (e%)
            </button>
          </div>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* TAB 1: DISTRIBUTION & ALLOWABLES (PDF / CDF) */}
      {/* ==================================================================== */}
      {activeViewTab === "distribution" && (
        <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-sky-400" />
                Coupon histogram & normal-model expected counts
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {showMmpdsAllowables
                  ? "Uploaded coupons: A/B cutoffs are screening estimates, not handbook allowables."
                  : isSyntheticCoupons ? SYNTHETIC_COUPON_MMPDS_NOTICE : "Uploaded records have insufficient data for tolerance estimates; existing values remain unverified."}
              </p>
            </div>

            <div className="flex items-center gap-2 text-xs font-mono">
              {showMmpdsAllowables ? (
                <>
                  <span className="flex items-center gap-1 text-sky-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-sky-400" />
                    Approx. normal T99: {formatUqNumber(empiricalStats.aBasisAllowable)} {propertyMeta.unit}
                  </span>
                  <span className="flex items-center gap-1 text-emerald-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                    Approx. normal T90: {formatUqNumber(empiricalStats.bBasisAllowable)} {propertyMeta.unit}
                  </span>
                </>
              ) : (
                <span className="text-amber-200">Tolerance estimates withheld (synthetic or insufficient data)</span>
              )}
              <span className="flex items-center gap-1 text-rose-400">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-400" />
                Spec Min: {propertyMeta.specMin} {propertyMeta.unit}
              </span>
            </div>
          </div>

          {/* Histogram Chart */}
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="midpoint"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  tick={{ fill: "#94a3b8", fontSize: 11, fontFamily: "monospace" }}
                  unit={` ${propertyMeta.unit}`}
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fill: "#94a3b8", fontSize: 11, fontFamily: "monospace" }}
                  label={{ value: "Coupon Count", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    borderColor: "#334155",
                    borderRadius: "0.75rem",
                    fontSize: "12px",
                    fontFamily: "monospace"
                  }}
                  formatter={(value: any, name: string) => {
                    if (name === "couponCount") return [`${value} specimens`, "Coupon Frequency"];
                    if (name === "gaussianCurve") return [`${value}`, "Normal-model expected counts"];
                    return [value, name];
                  }}
                  labelFormatter={(label) => `${propertyMeta.title}: ${label} ${propertyMeta.unit}`}
                />
                <Legend
                  wrapperStyle={{ fontSize: "11px", fontFamily: "monospace", paddingTop: "10px" }}
                />

                {/* Histogram Bars */}
                <Bar
                  yAxisId="left"
                  dataKey="couponCount"
                  name="Coupon Frequency"
                  fill="#0ea5e9"
                  opacity={0.8}
                  radius={[4, 4, 0, 0]}
                >
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        showMmpdsAllowables && entry.midpoint < empiricalStats.aBasisAllowable
                          ? "#ef4444"
                          : "#0ea5e9"
                      }
                    />
                  ))}
                </Bar>

                {/* Gaussian Fit Line */}
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="gaussianCurve"
                  name="Normal-model expected counts"
                  stroke="#fbbf24"
                  strokeWidth={2.5}
                  dot={false}
                />

                {/* Vertical Reference Thresholds */}
                {showMmpdsAllowables && (
                  <>
                <ReferenceLine ifOverflow="extendDomain"
                  yAxisId="left"
                  x={empiricalStats.aBasisAllowable}
                  stroke="#38bdf8"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  label={{
                    value: `Approx. T99 (${formatUqNumber(empiricalStats.aBasisAllowable)})`,
                    fill: "#38bdf8",
                    fontSize: 10,
                    position: "top"
                  }}
                />
                <ReferenceLine ifOverflow="extendDomain"
                  yAxisId="left"
                  x={empiricalStats.bBasisAllowable}
                  stroke="#34d399"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  label={{
                    value: `Approx. T90 (${formatUqNumber(empiricalStats.bBasisAllowable)})`,
                    fill: "#34d399",
                    fontSize: 10,
                    position: "top"
                  }}
                />
                  </>
                )}
                <ReferenceLine ifOverflow="extendDomain"
                  yAxisId="left"
                  x={propertyMeta.specMin}
                  stroke="#f43f5e"
                  strokeWidth={2}
                  label={{
                    value: `Spec Min (${propertyMeta.specMin})`,
                    fill: "#f43f5e",
                    fontSize: 10,
                    position: "insideTopRight"
                  }}
                />
                {empiricalStats.mean != null && <ReferenceLine ifOverflow="extendDomain"
                  yAxisId="left"
                  x={empiricalStats.mean}
                  stroke="#94a3b8"
                  strokeWidth={1.5}
                  strokeDasharray="2 2"
                  label={{
                    value: `Mean (${empiricalStats.mean})`,
                    fill: "#94a3b8",
                    fontSize: 10,
                    position: "bottom"
                  }}
                />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Detailed Statistical Table */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono text-xs">
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-[10px] text-slate-400 block">TOLERANCE k_A:</span>
              <span className="text-sky-300 font-bold text-sm">{formatUqNumber(empiricalStats.mmpds_kA, 3)}</span>
              <span className="text-[9px] text-slate-500 block">n={empiricalStats.sampleSize}</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-[10px] text-slate-400 block">TOLERANCE k_B:</span>
              <span className="text-emerald-300 font-bold text-sm">{formatUqNumber(empiricalStats.mmpds_kB, 3)}</span>
              <span className="text-[9px] text-slate-500 block">n={empiricalStats.sampleSize}</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-[10px] text-slate-400 block">SKEWNESS:</span>
              <span className="text-amber-300 font-bold text-sm">{formatUqNumber(empiricalStats.skewness, 3)}</span>
              <span className="text-[9px] text-slate-500 block">Descriptive moment, not a normality test</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-[10px] text-slate-400 block">KURTOSIS:</span>
              <span className="text-purple-300 font-bold text-sm">{formatUqNumber(empiricalStats.kurtosis, 3)}</span>
              <span className="text-[9px] text-slate-500 block">Excess kurtosis</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-[10px] text-slate-400 block">NORMALITY TEST:</span>
              <span className="text-emerald-300 font-bold text-sm">Not performed</span>
              <span className="text-[9px] text-slate-500 block">No distribution acceptance inferred</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-[10px] text-slate-400 block">TOLERANCE MODEL:</span>
              <span className="text-sky-300 font-bold text-sm">Approximate normal model</span>
              <span className="text-[9px] text-slate-500 block">Normality and independence unverified</span>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 2: SALTELLI-SOBOL GLOBAL SENSITIVITY DECOMPOSITION */}
      {/* ==================================================================== */}
      {activeViewTab === "sensitivity" && uqResult && (
        <div className="p-5 rounded-2xl bg-slate-900/90 border border-amber-500/30 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-amber-300 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-amber-400" />
                Saltelli-Sobol Variance Sensitivity Decomposition
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Quantifies the direct first-order effect (S_i) and total-order effect (S_Ti, including non-linear multi-scale interactions) of each uncertain parameter on Yield Strength scatter.
              </p>
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded bg-amber-950/60 text-amber-300 border border-amber-800/60 flex items-center gap-1.5 self-start sm:self-auto">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              Seeded Monte Carlo pick-freeze sampling
            </span>
          </div>

          <p className="text-xs text-amber-200">{uqResult.sensitivityMetadata?.limitations}</p>
          {/* Bar Chart */}
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={uqResult.sobolSensitivityAnalysis} margin={{ top: 20, right: 30, left: 10, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="parameter" tick={{ fill: "#94a3b8", fontSize: 11, fontFamily: "monospace" }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 11, fontFamily: "monospace" }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    borderColor: "#334155",
                    borderRadius: "0.75rem",
                    fontSize: "12px",
                    fontFamily: "monospace"
                  }}
                  formatter={(value: any, name: string) => {
                    if (name === "sobolFirstOrderIndex") return [value, "First-Order Index (S_i)"];
                    if (name === "sobolTotalOrderIndex") return [value, "Total-Order Index (S_Ti)"];
                    return [value, name];
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "11px", fontFamily: "monospace", paddingTop: "5px" }} />
                <Bar dataKey="sobolFirstOrderIndex" name="First-Order Index (S_i)" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                <Bar dataKey="sobolTotalOrderIndex" name="Total-Order Index (S_Ti)" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60">
            <table className="w-full text-xs font-mono text-left">
              <thead className="text-[10px] text-slate-400 uppercase bg-slate-900/80 border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Uncertain Factor</th>
                  <th className="py-2.5 px-3">Description</th>
                  <th className="py-2.5 px-3 text-amber-300 font-bold">First-Order (S_i)</th>
                  <th className="py-2.5 px-3 text-sky-300 font-bold">Total-Order (S_Ti)</th>
                  <th className="py-2.5 px-3 text-purple-300">Coupled Interaction (S_Ti - S_i)</th>
                  <th className="py-2.5 px-3 text-right">Raw 100 × S_i (%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {uqResult.sobolSensitivityAnalysis.map((s, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30">
                    <td className="py-2 px-3 font-bold text-slate-200">{s.parameter}</td>
                    <td className="py-2 px-3 text-slate-400">{s.description}</td>
                    <td className="py-2 px-3 text-amber-300 font-bold">{formatUqNumber(s.sobolFirstOrderIndex, 3)}</td>
                    <td className="py-2 px-3 text-sky-300 font-bold">{formatUqNumber(s.sobolTotalOrderIndex, 3)}</td>
                    <td className="py-2 px-3 text-purple-300 font-semibold">
                      {formatUqNumber(s.interactionIndex, 3)}
                    </td>
                    <td className="py-2 px-3 text-right font-bold text-slate-200">{formatUqNumber(s.varianceContributionPct)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Actionable Engineering Recommendation */}
          <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-1.5">
            <div className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              Alloy Tolerance Optimization Strategy:
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-mono">
              Finite-sample sensitivity estimates can be negative or exceed one. They are not normalized shares or experimental causal evidence. Review the estimator limitations before changing material tolerances.
            </p>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 3: COUPON TEST BATCH QC & LOT-TO-LOT TABLE */}
      {/* ==================================================================== */}
      {activeViewTab === "coupons" && (
        <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <TableIcon className="w-4 h-4 text-emerald-400" />
                Material Coupon Test Records & Lot Traceability
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Supplied coupon records. Source claims, test methods and lot identity are unverified. Filter by supplied Heat ID or remove specimens.
              </p>
            </div>

            {/* Filter and Actions */}
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Filter Heat/Specimen..."
                  value={searchLot}
                  onChange={(e) => {
                    setSearchLot(e.target.value);
                    setCouponPage(1);
                  }}
                  className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-xs text-slate-200 placeholder:text-slate-500 w-44"
                />
              </div>

              <button
                onClick={handleExportCSV}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 flex items-center gap-1 cursor-pointer"
              >
                <Download className="w-3 h-3 text-emerald-400" />
                CSV
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60">
            <table className="w-full text-xs font-mono text-left">
              <thead className="text-[10px] text-slate-400 uppercase bg-slate-900/80 border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Specimen ID</th>
                  <th className="py-2.5 px-3">Heat / Lot ID</th>
                  <th className="py-2.5 px-3">Orientation</th>
                  <th className="py-2.5 px-3 text-sky-300 font-bold">Yield (MPa)</th>
                  <th className="py-2.5 px-3 text-sky-400 font-bold">UTS (MPa)</th>
                  <th className="py-2.5 px-3 text-emerald-300">Elong (%)</th>
                  <th className="py-2.5 px-3 text-slate-400">RA (%)</th>
                  <th className="py-2.5 px-3 text-slate-400">Hardness</th>
                  <th className="py-2.5 px-3">Spec Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {paginatedCoupons.map((coupon) => {
                  const passesYield = coupon.yieldStrengthMPa >= activeDataset.specMinYieldMPa;
                  const passesUTS = coupon.utsMPa >= activeDataset.specMinUTSMPa;
                  const passesElong = coupon.elongationPct >= activeDataset.specMinElongationPct;
                  const fullyCompliant = passesYield && passesUTS && passesElong;

                  return (
                    <tr key={coupon.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-2.5 px-3 font-bold text-slate-200">{coupon.specimenNumber}</td>
                      <td className="py-2.5 px-3 text-amber-300">{coupon.heatLotId || "Not reported"}</td>
                      <td className="py-2.5 px-3 text-slate-400">{coupon.orientation || "Not reported"}</td>
                      <td className="py-2.5 px-3 font-bold text-sky-300">
                        {coupon.yieldStrengthMPa}
                        {!passesYield && <span className="text-[9px] text-rose-400 ml-1">(!)</span >}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-sky-400">
                        {coupon.utsMPa}
                        {!passesUTS && <span className="text-[9px] text-rose-400 ml-1">(!)</span >}
                      </td>
                      <td className="py-2.5 px-3 text-emerald-300">{coupon.elongationPct}%</td>
                      <td className="py-2.5 px-3 text-slate-400">{coupon.reductionOfAreaPct == null ? "Not reported" : `${coupon.reductionOfAreaPct}%`}</td>
                      <td className="py-2.5 px-3 text-slate-400">{coupon.hardnessHRC != null ? `${coupon.hardnessHRC} HRC` : "Not reported"}</td>
                      <td className="py-2.5 px-3">
                        {fullyCompliant ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                            PASS
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                            OUT-OF-SPEC
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={() => handleDeleteCoupon(coupon.id)}
                          className="text-slate-500 hover:text-rose-400 p-1 rounded transition cursor-pointer"
                          title="Delete specimen"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-2">
            <span>
              Showing {filteredCoupons.length === 0 ? 0 : (couponPage - 1) * couponsPerPage + 1}–
              {Math.min(couponPage * couponsPerPage, filteredCoupons.length)} of {filteredCoupons.length} coupons
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCouponPage((p) => Math.max(1, p - 1))}
                disabled={couponPage === 1}
                className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 cursor-pointer"
              >
                Previous
              </button>
              <span>
                Page {couponPage} of {totalPages}
              </span>
              <button
                onClick={() => setCouponPage((p) => Math.min(totalPages, p + 1))}
                disabled={couponPage >= totalPages}
                className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 cursor-pointer"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 4: MMPDS QUALIFICATION CERTIFICATE */}
      {/* ==================================================================== */}
      {activeViewTab === "certificate" && <CouponWorksheet dataset={activeDataset} onCopy={copyToClipboard} notification={copiedNotification} />}

      {/* ==================================================================== */}
      {/* SYNTHESIZE BATCH MODAL */}
      {/* ==================================================================== */}
      {isSynthesizeModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div role="dialog" aria-modal="true" aria-label="Synthesize coupon data" className="bg-slate-900 border border-slate-700 rounded-3xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            {errorMsg && <p role="alert" className="text-sm text-rose-300">{errorMsg}</p>}
            <div className="flex items-center justify-between">
              <h4 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                Synthesize Lot Coupon Batch
              </h4>
              <button
                onClick={() => setIsSynthesizeModalOpen(false)}
                className="text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Generate a teaching coupon population using Box-Muller sampling. Synthetic n/lot is not MMPDS A/B handbook allowables.
            </p>

            <div className="space-y-3 font-mono text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Coupon Sample Size (N):</label>
                <input
                  type="number"
                  min={10}
                  max={200}
                  value={synthSampleSize}
                  onChange={(e) => setSynthSampleSize(parseInt(e.target.value) || 30)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-200"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Number of Melt Lots / Heats:</label>
                <input
                  type="number"
                  min={2}
                  max={12}
                  value={synthLotCount}
                  onChange={(e) => setSynthLotCount(parseInt(e.target.value) || 4)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-200"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setIsSynthesizeModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleSynthesizeBatch}
                className="px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs cursor-pointer"
              >
                Generate Coupons
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
