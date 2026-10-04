import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Terminal,
  Cpu,
  Layers,
  Clock,
  Shield,
  Copy,
  Check,
  RefreshCw,
  TrendingDown,
  Info,
  ChevronRight,
  Sliders,
  BarChart3,
  Calendar,
  Zap,
} from "lucide-react";
import {
  TafelPythonCorrosionRateInput,
  TafelPythonCorrosionRateResult,
  TafelFitResult,
  TafelDataset,
} from "../types/tafel";
import { calculatePythonTafelCorrosionRate } from "../services/pythonComputationService";
import { isPythonValidationError } from "../utils/pythonValidationError";

interface Props {
  tafelFit?: TafelFitResult | null;
  dataset?: TafelDataset | null;
  className?: string;
  onNavigateToTafel?: () => void;
}

const ALLOY_PRESETS = [
  { id: "steel-316l", name: "AISI 316L Stainless Steel", density: 7.98, ew: 25.68, category: "Stainless" },
  { id: "steel-304", name: "AISI 304 Stainless Steel", density: 7.93, ew: 25.12, category: "Stainless" },
  { id: "steel-1018", name: "Carbon Steel (AISI 1018)", density: 7.87, ew: 27.92, category: "Carbon Steel" },
  { id: "ti-6al-4v", name: "Titanium Ti-6Al-4V (Grade 5)", density: 4.43, ew: 11.97, category: "Titanium" },
  { id: "al-7075", name: "Aerospace Al 7075-T6", density: 2.81, ew: 9.15, category: "Aluminum" },
  { id: "al-6061", name: "Structural Al 6061-T6", density: 2.70, ew: 9.02, category: "Aluminum" },
  { id: "cu-c110", name: "Pure Copper (ETP C11000)", density: 8.94, ew: 31.77, category: "Copper" },
  { id: "inconel-718", name: "Inconel 718 Superalloy", density: 8.19, ew: 26.45, category: "Nickel" },
  { id: "az31b", name: "Magnesium Alloy AZ31B", density: 1.77, ew: 12.28, category: "Magnesium" },
];

export const PythonAnnualCorrosionRateModule: React.FC<Props> = ({
  tafelFit,
  dataset,
  className = "",
  onNavigateToTafel,
}) => {
  // Input parameters state, initialized from tafelFit and dataset if available
  const [alloyId, setAlloyId] = useState<string>("steel-316l");
  const [customDensity, setCustomDensity] = useState<number>(7.98);
  const [customEw, setCustomEw] = useState<number>(25.68);
  const [initialThicknessMm, setInitialThicknessMm] = useState<number>(5.0);
  const [allowableLossMm, setAllowableLossMm] = useState<number>(1.5);
  const [temperatureC, setTemperatureC] = useState<number>(25.0);
  const [manualIcorr, setManualIcorr] = useState<number>(1.25);
  const [overrideIcorr, setOverrideIcorr] = useState<boolean>(false);

  // Python Calculation State
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<TafelPythonCorrosionRateResult | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"summary" | "timeline" | "temperature" | "pythonCode">("summary");
  const [copiedCode, setCopiedCode] = useState<boolean>(false);

  // Sync with dataset metadata if changed
  useEffect(() => {
    if (dataset?.metadata) {
      if (dataset.metadata.density_g_cm3) {
        setCustomDensity(dataset.metadata.density_g_cm3);
      }
      if (dataset.metadata.equivalentWeight) {
        setCustomEw(dataset.metadata.equivalentWeight);
      }
      if (dataset.metadata.temperatureC !== undefined) {
        setTemperatureC(dataset.metadata.temperatureC);
      }
    }
  }, [dataset]);

  // Determine active Icorr value: either manual override or from Tafel fit
  const activeIcorr = useMemo(() => {
    if (overrideIcorr) return manualIcorr;
    if (tafelFit?.iCorr_uA_cm2 && tafelFit.iCorr_uA_cm2 > 0) {
      return tafelFit.iCorr_uA_cm2;
    }
    return manualIcorr;
  }, [overrideIcorr, manualIcorr, tafelFit]);

  const activeEcorr = tafelFit?.eCorr ?? -0.35;
  const activeBetaA = tafelFit?.betaA_V_dec ?? 0.12;
  const activeBetaC = tafelFit?.betaC_V_dec ?? 0.10;
  const activeArea = dataset?.metadata.electrodeAreaCm2 ?? 1.0;

  // Handler to update preset selection
  const handleAlloyChange = (newId: string) => {
    setAlloyId(newId);
    const found = ALLOY_PRESETS.find((p) => p.id === newId);
    if (found) {
      setCustomDensity(found.density);
      setCustomEw(found.ew);
    }
  };

  // Dispatches to Python calculation engine
  const executePythonCalculation = useCallback(async () => {
    setLoading(true);
    const selectedPreset = ALLOY_PRESETS.find((p) => p.id === alloyId);
    const inputPayload: TafelPythonCorrosionRateInput = {
      iCorr_uA_cm2: activeIcorr,
      eCorr_V: activeEcorr,
      betaA: activeBetaA,
      betaC: activeBetaC,
      alloyId,
      alloyName: selectedPreset?.name || "Custom Substrate",
      density_g_cm3: customDensity,
      equivalentWeight: customEw,
      specimenAreaCm2: activeArea,
      initialThicknessMm,
      allowableLossMm,
      temperatureC,
    };

    try {
      const res = await calculatePythonTafelCorrosionRate(inputPayload);
      setResult(res);
      setValidationError(null);
    } catch (err) {
      if (isPythonValidationError(err)) {
        // Rejected input: do not keep showing a result computed for other inputs.
        setResult(null);
        setValidationError(err.message);
      }
      console.error("Failed to calculate annual corrosion rate in Python:", err);
    } finally {
      setLoading(false);
    }
  }, [
    activeIcorr,
    activeEcorr,
    activeBetaA,
    activeBetaC,
    alloyId,
    customDensity,
    customEw,
    activeArea,
    initialThicknessMm,
    allowableLossMm,
    temperatureC,
  ]);

  // Automatically recalculate whenever Icorr or parameters update
  useEffect(() => {
    executePythonCalculation();
  }, [executePythonCalculation]);

  const handleCopyCode = () => {
    if (!result?.pythonCode) return;
    navigator.clipboard.writeText(result.pythonCode);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const getSeverityBadgeClass = (level?: string) => {
    switch (level?.toLowerCase()) {
      case "outstanding":
        return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20";
      case "excellent":
        return "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20";
      case "good":
        return "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20";
      case "fair":
        return "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20";
      default:
        return "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20";
    }
  };

  return (
    <div
      id="python-annual-corrosion-rate-module"
      className={`bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm overflow-hidden ${className}`}
    >
      {/* Module Header */}
      <div className="p-5 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-500/10 dark:bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Annual Corrosion Rate Engine
              </h2>
              <span className="px-2 py-0.5 text-xs font-mono font-medium rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <Cpu className="w-3 h-3" />
                Python 3.10 Active
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 font-mono">
                ASTM G102 / G59
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Automated Faraday penetration & Stern-Geary kinetics driven by Tafel extrapolated Icorr
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {result?.durationMs !== undefined && (
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {result.durationMs} ms
            </span>
          )}
          <button
            onClick={executePythonCalculation}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700 flex items-center gap-1.5 transition-colors"
            title="Recalculate via Python"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Re-run Python
          </button>
        </div>
      </div>

      {/* Main Container Layout */}
      <div className="p-5 space-y-6">
        {validationError && (
          <div role="alert" className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{validationError}</span>
          </div>
        )}
        {/* Source Icorr Banner */}
        <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-700 dark:text-slate-300">Tafel Fit Coupling:</span>
            {tafelFit ? (
              <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Active fit available (Ecorr = {tafelFit.eCorr.toFixed(3)} V, Icorr ={" "}
                {tafelFit.iCorr_uA_cm2.toFixed(4)} μA/cm²)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                <Info className="w-3.5 h-3.5" />
                No active fit loaded yet (using benchmark reference values)
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 cursor-pointer select-none text-slate-600 dark:text-slate-400">
              <input
                type="checkbox"
                checked={overrideIcorr}
                onChange={(e) => setOverrideIcorr(e.target.checked)}
                className="rounded border-slate-300 dark:border-slate-600 text-indigo-600 focus:ring-indigo-500"
              />
              <span>Manual Icorr Tuning</span>
            </label>
            {onNavigateToTafel && (
              <button
                onClick={onNavigateToTafel}
                className="text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-0.5"
              >
                Go to Tafel Curve <ChevronRight className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Primary Hero Metrics Card */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Hero Annual Rate Metric */}
          <div className="lg:col-span-6 p-5 rounded-xl bg-gradient-to-br from-indigo-50/50 via-white to-slate-50 dark:from-indigo-950/20 dark:via-slate-900 dark:to-slate-800/50 border border-indigo-100 dark:border-indigo-900/40 relative">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-indigo-700 dark:text-indigo-400">
                Annual Corrosion Penetration Rate
              </span>
              {result?.severity && (
                <span
                  className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border ${getSeverityBadgeClass(
                    result.severity.level
                  )}`}
                >
                  {result.severity.level}
                </span>
              )}
            </div>

            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-4xl sm:text-5xl font-extrabold tracking-tight font-mono text-slate-900 dark:text-slate-100">
                {result ? result.corrosionRateMmYr.toFixed(5) : "—"}
              </span>
              <span className="text-base font-semibold text-slate-600 dark:text-slate-400">mm / year</span>
            </div>

            {/* Equivalent Unit Representations */}
            <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-indigo-100/60 dark:border-slate-800 text-xs">
              <div>
                <span className="text-slate-500 dark:text-slate-400 block">Mils / Year (mpy)</span>
                <span className="font-mono font-bold text-slate-800 dark:text-slate-200 text-sm">
                  {result ? result.corrosionRateMpy.toFixed(3) : "—"}
                </span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400 block">Penetration (μm/yr)</span>
                <span className="font-mono font-bold text-slate-800 dark:text-slate-200 text-sm">
                  {result ? result.corrosionRateUmYr.toFixed(2) : "—"}
                </span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400 block">Mass Loss (g/m²·day)</span>
                <span className="font-mono font-bold text-slate-800 dark:text-slate-200 text-sm">
                  {result ? result.massLoss_g_m2_day.toFixed(4) : "—"}
                </span>
              </div>
            </div>

            {/* Description note */}
            {result?.severity && (
              <p className="mt-3 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                {result.severity.description}
              </p>
            )}
          </div>

          {/* Substrate & Kinetic Parameters Card */}
          <div className="lg:col-span-6 p-5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Electrochemical Kinetic Factors
                </span>
                <span className="text-xs font-mono text-slate-600 dark:text-slate-400">
                  i_corr = {activeIcorr.toFixed(4)} μA/cm²
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <span className="text-slate-500 dark:text-slate-400 block">Polarization Resistance (Rp)</span>
                  <span className="text-sm font-mono font-bold text-slate-900 dark:text-slate-100">
                    {result ? result.rp_ohm_cm2.toLocaleString() : "—"} Ω·cm²
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <span className="text-slate-500 dark:text-slate-400 block">Stern-Geary B Constant</span>
                  <span className="text-sm font-mono font-bold text-slate-900 dark:text-slate-100">
                    {result ? result.sternGearyB_V.toFixed(4) : "—"} V
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <span className="text-slate-500 dark:text-slate-400 block">Equivalent Weight (EW)</span>
                  <span className="text-sm font-mono font-bold text-slate-900 dark:text-slate-100">
                    {customEw.toFixed(2)} g/eq
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <span className="text-slate-500 dark:text-slate-400 block">Substrate Density (ρ)</span>
                  <span className="text-sm font-mono font-bold text-slate-900 dark:text-slate-100">
                    {customDensity.toFixed(2)} g/cm³
                  </span>
                </div>
              </div>
            </div>

            {/* Service Life Summary */}
            <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700/60 flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                <Shield className="w-3.5 h-3.5 text-indigo-500" />
                <span>RUL Uniform ({allowableLossMm} mm allowance):</span>
              </div>
              <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400 text-sm">
                {result?.rulUniformYears !== undefined ? `${result.rulUniformYears} Years` : "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Interactive Parameter Controls Accordion / Panel */}
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700/50">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5" />
              Substrate & Operating Conditions Control
            </span>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              Live updates propagate to Python calculation
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            {/* Alloy Preset */}
            <div>
              <label className="block text-slate-600 dark:text-slate-400 mb-1 font-medium">
                Alloy Substrate
              </label>
              <select aria-label="Alloy Substrate"
                value={alloyId}
                onChange={(e) => handleAlloyChange(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-medium"
              >
                {ALLOY_PRESETS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Density & EW */}
            <div>
              <label className="block text-slate-600 dark:text-slate-400 mb-1 font-medium">
                Density (g/cm³) / EW (g/eq)
              </label>
              <div className="grid grid-cols-2 gap-1.5">
                <input aria-label="Density (g/cm³)"
                  type="number"
                  step="0.01"
                  value={customDensity}
                  onChange={(e) => setCustomDensity(parseFloat(e.target.value) || 7.98)}
                  className="w-full px-2 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs"
                  placeholder="Density"
                />
                <input aria-label="EW (g/eq)"
                  type="number"
                  step="0.01"
                  value={customEw}
                  onChange={(e) => setCustomEw(parseFloat(e.target.value) || 25.68)}
                  className="w-full px-2 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs"
                  placeholder="EW"
                />
              </div>
            </div>

            {/* Thickness & Allowance */}
            <div>
              <label className="block text-slate-600 dark:text-slate-400 mb-1 font-medium">
                Thickness / Allowance (mm)
              </label>
              <div className="grid grid-cols-2 gap-1.5">
                <input aria-label="Thickness (mm)"
                  type="number"
                  step="0.1"
                  value={initialThicknessMm}
                  onChange={(e) => setInitialThicknessMm(parseFloat(e.target.value) || 5.0)}
                  className="w-full px-2 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs"
                  placeholder="Thickness"
                />
                <input aria-label="Allowance (mm)"
                  type="number"
                  step="0.1"
                  value={allowableLossMm}
                  onChange={(e) => setAllowableLossMm(parseFloat(e.target.value) || 1.5)}
                  className="w-full px-2 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs"
                  placeholder="Allowance"
                />
              </div>
            </div>

            {/* Temperature & Icorr Override */}
            <div>
              <label className="block text-slate-600 dark:text-slate-400 mb-1 font-medium">
                Temperature (°C) {overrideIcorr ? "| Icorr (μA/cm²)" : ""}
              </label>
              <div className="grid grid-cols-2 gap-1.5">
                <input aria-label="Temperature (°C)"
                  type="number"
                  step="1"
                  value={temperatureC}
                  onChange={(e) => setTemperatureC(parseFloat(e.target.value) || 25)}
                  className="w-full px-2 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs"
                  placeholder="Temp °C"
                />
                <input aria-label="Icorr (μA/cm²)"
                  type="number"
                  step="0.01"
                  disabled={!overrideIcorr}
                  value={overrideIcorr ? manualIcorr : +activeIcorr.toFixed(4)}
                  onChange={(e) => setManualIcorr(parseFloat(e.target.value) || 1.0)}
                  className={`w-full px-2 py-1.5 rounded-lg border font-mono text-xs ${
                    overrideIcorr
                      ? "bg-white dark:bg-slate-900 border-indigo-400 text-slate-900 dark:text-slate-100"
                      : "bg-slate-100 dark:bg-slate-800/80 border-slate-300 dark:border-slate-700 text-slate-500 cursor-not-allowed"
                  }`}
                  placeholder="Icorr"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Tab Navigation for Detailed Sections */}
        <div>
          <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2">
            <button
              onClick={() => setActiveTab("summary")}
              className={`pb-2.5 text-xs font-semibold flex items-center gap-1.5 border-b-2 transition-colors ${
                activeTab === "summary"
                  ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
                  : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              Engineering Summary & Standards
            </button>
            <button
              onClick={() => setActiveTab("timeline")}
              className={`pb-2.5 text-xs font-semibold flex items-center gap-1.5 border-b-2 transition-colors ${
                activeTab === "timeline"
                  ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
                  : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              25-Year Wall Thinning Projection
            </button>
            <button
              onClick={() => setActiveTab("temperature")}
              className={`pb-2.5 text-xs font-semibold flex items-center gap-1.5 border-b-2 transition-colors ${
                activeTab === "temperature"
                  ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
                  : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
              }`}
            >
              <Flame className="w-3.5 h-3.5" />
              Arrhenius Thermal Sensitivity
            </button>
            <button
              onClick={() => setActiveTab("pythonCode")}
              className={`pb-2.5 text-xs font-semibold flex items-center gap-1.5 border-b-2 transition-colors ${
                activeTab === "pythonCode"
                  ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
                  : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              Executable Python Script
            </button>
          </div>

          {/* Tab 1: Engineering Summary */}
          {activeTab === "summary" && (
            <div className="pt-4 space-y-4 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
                  <h4 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                    <Shield className="w-4 h-4 text-indigo-500" />
                    ASTM G102 Standard Governing Equation
                  </h4>
                  <p className="text-slate-600 dark:text-slate-400 leading-relaxed font-mono bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-700/60">
                    CR (mm/year) = [ K1 · i_corr · EW ] / ρ
                  </p>
                  <ul className="space-y-1.5 text-slate-600 dark:text-slate-400">
                    <li>• <span className="font-mono font-medium">K1</span> = 3.27 × 10⁻³ mm·g / (μA·cm·year)</li>
                    <li>• <span className="font-mono font-medium">i_corr</span> = {activeIcorr.toFixed(4)} μA/cm² (Extrapolated Tafel current density)</li>
                    <li>• <span className="font-mono font-medium">EW</span> = {customEw.toFixed(2)} g/equivalent (Equivalent weight of {ALLOY_PRESETS.find(p => p.id === alloyId)?.name})</li>
                    <li>• <span className="font-mono font-medium">ρ</span> = {customDensity.toFixed(2)} g/cm³ (Alloy bulk density)</li>
                  </ul>
                </div>

                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
                  <h4 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    Industrial Recommendation & Mitigations
                  </h4>
                  <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-800 dark:text-amber-300">
                    <p className="font-medium">{result?.severity.recommendation}</p>
                  </div>
                  <div className="space-y-1 text-slate-600 dark:text-slate-400">
                    <div>• Uniform Remaining Useful Life: <strong className="text-slate-900 dark:text-slate-100 font-mono">{result?.rulUniformYears} years</strong></div>
                    <div>• Localized Pitting Risk Lifespan: <strong className="text-slate-900 dark:text-slate-100 font-mono">{result?.rulPittingYears} years</strong></div>
                    <div>• Mass loss rate: <strong className="text-slate-900 dark:text-slate-100 font-mono">{result?.massLoss_mdd} mg/(dm²·day)</strong></div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: 25-Year Wall Thinning */}
          {activeTab === "timeline" && (
            <div className="pt-4 overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 bg-slate-50/50 dark:bg-slate-800/40">
                    <th className="py-2.5 px-3 font-semibold">Horizon</th>
                    <th className="py-2.5 px-3 font-semibold">Uniform Loss (mm)</th>
                    <th className="py-2.5 px-3 font-semibold">Remaining Wall (mm)</th>
                    <th className="py-2.5 px-3 font-semibold">Wall Loss %</th>
                    <th className="py-2.5 px-3 font-semibold">Pitting Loss (mm)</th>
                    <th className="py-2.5 px-3 font-semibold">Allowance Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                  {result?.timelineProjections?.map((proj) => (
                    <tr
                      key={proj.year}
                      className={`hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors ${
                        proj.exceedsAllowance ? "bg-rose-50/30 dark:bg-rose-950/10" : ""
                      }`}
                    >
                      <td className="py-2.5 px-3 font-medium text-slate-900 dark:text-slate-100 font-sans">
                        Year {proj.year}
                      </td>
                      <td className="py-2.5 px-3 text-indigo-600 dark:text-indigo-400 font-bold">
                        {proj.lossUniformMm} mm
                      </td>
                      <td className="py-2.5 px-3 text-slate-800 dark:text-slate-200">
                        {proj.remainingWallMm} mm
                      </td>
                      <td className="py-2.5 px-3">
                        <div className="flex items-center gap-2">
                          <span>{proj.wallLossPct}%</span>
                          <div className="w-16 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${
                                proj.exceedsAllowance ? "bg-rose-500" : "bg-indigo-500"
                              }`}
                              style={{ width: `${Math.min(100, proj.wallLossPct)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-amber-600 dark:text-amber-400">
                        {proj.lossPittingMm} mm
                      </td>
                      <td className="py-2.5 px-3 font-sans">
                        {proj.exceedsAllowance ? (
                          <span className="inline-flex items-center gap-1 text-rose-600 dark:text-rose-400 font-semibold">
                            <AlertTriangle className="w-3 h-3" /> Breach Limit
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                            <Check className="w-3 h-3" /> Safe
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Tab 3: Arrhenius Temperature Sensitivity */}
          {activeTab === "temperature" && (
            <div className="pt-4 space-y-3">
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Corrosion rate thermal acceleration modelled using Arrhenius activation energy (Ea = 32 kJ/mol).
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 bg-slate-50/50 dark:bg-slate-800/40">
                      <th className="py-2 px-3 font-semibold">Temp (°C)</th>
                      <th className="py-2 px-3 font-semibold">Arrhenius Factor</th>
                      <th className="py-2 px-3 font-semibold">Icorr (μA/cm²)</th>
                      <th className="py-2 px-3 font-semibold">Corrosion Rate (mm/yr)</th>
                      <th className="py-2 px-3 font-semibold">Rate (mpy)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                    {result?.temperatureSensitivity?.map((t) => (
                      <tr
                        key={t.tempC}
                        className={`hover:bg-slate-50/80 dark:hover:bg-slate-800/30 ${
                          t.tempC === temperatureC ? "bg-indigo-50/50 dark:bg-indigo-950/20 font-bold" : ""
                        }`}
                      >
                        <td className="py-2 px-3 text-slate-900 dark:text-slate-100 font-sans">
                          {t.tempC}°C {t.tempC === temperatureC && "(Current)"}
                        </td>
                        <td className="py-2 px-3 text-slate-600 dark:text-slate-400">{t.arrheniusFactor}x</td>
                        <td className="py-2 px-3 text-slate-800 dark:text-slate-200">{t.iCorr_uA_cm2}</td>
                        <td className="py-2 px-3 text-indigo-600 dark:text-indigo-400">{t.corrosionRateMmYr}</td>
                        <td className="py-2 px-3 text-slate-700 dark:text-slate-300">{t.corrosionRateMpy}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Tab 4: Python Script */}
          {activeTab === "pythonCode" && (
            <div className="pt-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  Exact Python script executing on backend CPython 3.10 runtime:
                </span>
                <button
                  onClick={handleCopyCode}
                  className="px-2.5 py-1 text-xs font-medium rounded-md bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 flex items-center gap-1 transition-colors"
                >
                  {copiedCode ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                  {copiedCode ? "Copied!" : "Copy Python Code"}
                </button>
              </div>
              <pre className="p-4 rounded-xl bg-slate-950 text-slate-100 font-mono text-xs overflow-x-auto border border-slate-800 leading-relaxed">
                <code>{result?.pythonCode || "# Calculating..."}</code>
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
