import React, { useState, useMemo } from "react";
import {
  Sliders,
  RotateCcw,
  Zap,
  TrendingUp,
  Flame,
  ShieldAlert,
  Layers,
  DollarSign,
  Plus,
  Trash2,
  Lock,
  Unlock,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import {
  CandidateAlloySolution,
  AlloyComposition,
  calculateThermodynamicProfile,
  calculatePhysicalStrengthBreakdown,
  calculateTemperatureYieldCurve,
  calculateScheilKouMetrics,
  InverseDesignTargets,
} from "../utils/inverseAlloyOptimizer";
import { LME_PRICE_DATABASE } from "../data/lmePrices";
import { useMaterialStore, MATERIAL_PRESETS } from "../store/useMaterialStore";

interface Props {
  candidate: CandidateAlloySolution;
  targets: InverseDesignTargets;
  onApplyTunedComposition?: (newComp: AlloyComposition, newName: string) => void;
}

export const MicroAlloySandbox: React.FC<Props> = ({
  candidate,
  targets,
  onApplyTunedComposition,
}) => {
  const { activeMaterialSpecimen, updateComposition: updateGlobalComposition } = useMaterialStore();

  // Baseline initial composition initialized from shared store or candidate
  const [composition, setComposition] = useState<AlloyComposition>(() => ({
    ...(activeMaterialSpecimen.composition || candidate.compositionWt),
  }));

  // Locked elements that should not auto-adjust during normalization
  const [lockedElements, setLockedElements] = useState<Record<string, boolean>>({});

  // Element to add from dropdown
  const [elementToAdd, setElementToAdd] = useState<string>("Sc");

  // Re-calculate all thermodynamic, physical & mechanical properties in real-time
  const tunedProfile = useMemo(() => {
    // 1. Calculate fundamental thermodynamics
    const thermo = calculateThermodynamicProfile(composition);

    // 2. Base Matrix and reference properties
    const baseMatrix = targets.baseMatrix;

    // 3. Dynamic Yield Strength Model based on composition changes
    // Solute strengthening scaling
    let predictedYield_25C = Math.round(
      candidate.yieldStrength_25C_MPa *
        (1 + (thermo.deltaMismatch - candidate.atomicSizeMismatch_deltaPct) * 0.04)
    );

    // Hardening elements positive multipliers (Al, Ti, Nb, Ta for precipitates; Mo, W for solid solution)
    const gammaFormers =
      (composition["Al"] || 0) +
      (composition["Ti"] || 0) +
      (composition["Nb"] || 0) +
      (composition["Ta"] || 0);
    const origGammaFormers =
      (candidate.compositionWt["Al"] || 0) +
      (candidate.compositionWt["Ti"] || 0) +
      (candidate.compositionWt["Nb"] || 0) +
      (candidate.compositionWt["Ta"] || 0);

    if (baseMatrix === "Nickel" || baseMatrix === "Steel") {
      const diffPpt = gammaFormers - origGammaFormers;
      predictedYield_25C += Math.round(diffPpt * 24);
    }

    predictedYield_25C = Math.max(120, predictedYield_25C);

    // 4. Physical strength breakdown
    const strengthBreakdown = calculatePhysicalStrengthBreakdown(
      baseMatrix,
      composition,
      thermo.deltaMismatch,
      predictedYield_25C
    );

    // 5. Freezing Range & Scheil-Kou
    const freezingRange_C = Math.max(15, Math.round(thermo.avgMeltingPoint * 0.075));
    const scheilKou = calculateScheilKouMetrics(
      thermo.avgMeltingPoint,
      freezingRange_C,
      thermo.deltaMismatch,
      targets.manufacturingRoute
    );

    // 6. TCP Phase / Sigma Phase Instability Flag (PHACOMP approximation)
    // FCC is stable when VEC >= 8.0. If VEC drops below 7.6 or (Cr+Mo+W) > 28 wt%, TCP sigma precipitation risk increases
    const bccSolutes =
      (composition["Cr"] || 0) +
      (composition["Mo"] || 0) +
      (composition["W"] || 0) +
      (composition["V"] || 0) +
      (composition["Nb"] || 0);
    const tcpRisk =
      (baseMatrix === "Nickel" && (thermo.vec < 7.65 || bccSolutes > 28)) ||
      (baseMatrix === "Steel" && (composition["Cr"] || 0) > 26 && (composition["Ni"] || 0) < 6);

    // 7. Specific strength
    const specificStrength = parseFloat((predictedYield_25C / thermo.density).toFixed(2));

    return {
      thermo,
      predictedYield_25C,
      strengthBreakdown,
      scheilKou,
      tcpRisk,
      specificStrength,
      freezingRange_C,
    };
  }, [composition, candidate, targets]);

  // Handle single slider change with intelligent normalization to 100%
  const handleSliderChange = (elem: string, newVal: number) => {
    const clampedVal = Math.max(0, Math.min(100, parseFloat(newVal.toFixed(1))));
    const newComp = { ...composition, [elem]: clampedVal };

    // Calculate sum of all locked elements and the currently modified element
    let fixedSum = 0;
    const adjustableKeys: string[] = [];

    for (const [k, v] of Object.entries(newComp)) {
      const val = Number(v) || 0;
      if (k === elem || lockedElements[k]) {
        fixedSum += val;
      } else {
        adjustableKeys.push(k);
      }
    }

    // Distribute remaining (100 - fixedSum) among unlocked elements
    const remainingToDistribute = Math.max(0, 100 - fixedSum);
    const currentAdjustableSum = adjustableKeys.reduce((sum, k) => sum + newComp[k], 0);

    if (currentAdjustableSum > 0 && adjustableKeys.length > 0) {
      for (const k of adjustableKeys) {
        const ratio = newComp[k] / currentAdjustableSum;
        newComp[k] = parseFloat((ratio * remainingToDistribute).toFixed(1));
      }
    } else if (adjustableKeys.length > 0) {
      // Equal split if all were zero
      const splitVal = parseFloat((remainingToDistribute / adjustableKeys.length).toFixed(1));
      for (const k of adjustableKeys) {
        newComp[k] = splitVal;
      }
    }

    setComposition(newComp);
    // Instant reactive propagation through universal Zustand store to Tab 2 & Tab 3
    updateGlobalComposition(
      newComp,
      undefined,
      { baseMetal: targets.baseMatrix === "Nickel" ? "Ni" : undefined as any },
      "Micro-Alloy Sandbox (Tab 1)"
    );
  };

  // Toggle lock for an element
  const toggleLock = (elem: string) => {
    setLockedElements((prev) => ({ ...prev, [elem]: !prev[elem] }));
  };

  // Add new element to composition
  const handleAddElement = () => {
    if (!elementToAdd || composition[elementToAdd] !== undefined) return;
    const newComp = { ...composition, [elementToAdd]: 1.0 };
    // Adjust primary matrix element
    const matrixElem = Object.entries(newComp).reduce((a, b) => (b[1] > a[1] ? b : a))[0];
    if (matrixElem && matrixElem !== elementToAdd && newComp[matrixElem] > 2) {
      newComp[matrixElem] = parseFloat((newComp[matrixElem] - 1.0).toFixed(1));
    }
    setComposition(newComp);
    updateGlobalComposition(newComp, undefined, undefined, "Micro-Alloy Sandbox (Add Element)");
  };

  // Remove element from composition
  const handleRemoveElement = (elem: string) => {
    if (Object.keys(composition).length <= 2) return; // Keep at least binary
    const removedVal = composition[elem] || 0;
    const newComp = { ...composition };
    delete newComp[elem];

    // Give the weight back to the largest matrix element
    const matrixElem = Object.entries(newComp).reduce((a, b) => (b[1] > a[1] ? b : a))[0];
    if (matrixElem) {
      newComp[matrixElem] = parseFloat((newComp[matrixElem] + removedVal).toFixed(1));
    }
    setComposition(newComp);
    updateGlobalComposition(newComp, undefined, undefined, "Micro-Alloy Sandbox (Remove Element)");
  };

  // Reset to original candidate composition
  const handleReset = () => {
    setComposition({ ...candidate.compositionWt });
    setLockedElements({});
    updateGlobalComposition(
      candidate.compositionWt,
      candidate.name,
      { baseMetal: targets.baseMatrix === "Nickel" ? "Ni" : undefined as any },
      "Alloy Formulator (Reset)"
    );
  };

  // Quick load benchmark Ni superalloy (Ni-16Cr-8.5Co-1.7Mo-2.6W-1.7Ta-3.4Al-3.4Ti)
  const handleLoadBenchmarkNiSuperalloy = () => {
    const preset = MATERIAL_PRESETS["custom-ni-superalloy"];
    if (preset) {
      setComposition({ ...preset.composition });
      setLockedElements({});
      updateGlobalComposition(
        preset.composition,
        preset.name,
        { baseMetal: "Ni", category: preset.category, standardDesignation: preset.standard },
        "Benchmark Nickel Superalloy"
      );
    }
  };

  // Available elements to add
  const availableElementsToAdd = Object.keys(LME_PRICE_DATABASE).filter(
    (el) => composition[el] === undefined
  );

  // Delta comparison values
  const deltaYield = tunedProfile.predictedYield_25C - candidate.yieldStrength_25C_MPa;
  const deltaCost = tunedProfile.thermo.rawCostUSD - candidate.rawCostUSD_kg;
  const deltaDensity = tunedProfile.thermo.density - candidate.density_gcm3;
  const deltaPREN = tunedProfile.thermo.pren - candidate.pren;

  return (
    <div className="space-y-4 pt-1">
      {/* Universal Reactive Specimen Thread Banner */}
      <div className="px-4 py-3 rounded-xl bg-gradient-to-r from-sky-950/40 via-blue-950/20 to-purple-950/30 border border-sky-500/40 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center gap-2.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
          <div>
            <span className="text-white font-bold flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              Universal Reactive Specimen Thread: ACTIVE
            </span>
            <p className="text-[11px] text-slate-300 mt-0.5">
              Updates here propagate in real-time to Tab 2 (CALPHAD Gibbs Minimizer) and Tab 3 (3D LPBF Melt Pool &amp; XRD Lab).
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={handleLoadBenchmarkNiSuperalloy}
            className="px-2.5 py-1.5 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 text-sky-200 border border-sky-400/50 font-bold transition flex items-center gap-1.5"
            title="Load Ni-16Cr-8.5Co-1.7Mo-2.6W-1.7Ta-3.4Al-3.4Ti"
          >
            <Sparkles className="w-3.5 h-3.5 text-sky-400" />
            <span>Load Ni-Superalloy Benchmark</span>
          </button>
        </div>
      </div>

      {/* Header & Controls */}
      <div className="p-4 rounded-xl bg-[#0b1322] border border-[#1d2a44] space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Sliders className="w-5 h-5 text-amber-400" />
              <h3 className="text-sm font-bold text-white font-mono">
                What-If Micro-Alloying Sandbox (Live Composition Tuning)
              </h3>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Adjust elemental concentrations interactively. Thermodynamic phase stability (VEC), PREN, yield strength, cracking risk, and raw cost are calculated dynamically.
            </p>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            <button
              onClick={handleReset}
              className="px-3 py-1.5 rounded-lg bg-[#162032] hover:bg-[#1f2d47] border border-[#273754] text-xs font-mono text-slate-300 hover:text-white flex items-center gap-1.5 transition"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset
            </button>
            {onApplyTunedComposition && (
              <button
                onClick={() =>
                  onApplyTunedComposition(composition, `${candidate.name} (Tuned)`)
                }
                className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-mono font-bold flex items-center gap-1.5 shadow-md shadow-amber-500/20 transition"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                Apply Custom Formulation
              </button>
            )}
          </div>
        </div>

        {/* Live Delta KPI Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 font-mono">
          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032] flex flex-col">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span>Yield Strength (σ_y)</span>
              <span
                className={`font-bold ${
                  deltaYield > 0
                    ? "text-emerald-400"
                    : deltaYield < 0
                    ? "text-rose-400"
                    : "text-slate-400"
                }`}
              >
                {deltaYield > 0 ? `+${deltaYield}` : deltaYield} MPa
              </span>
            </div>
            <div className="text-base font-bold text-white mt-1">
              {tunedProfile.predictedYield_25C} MPa
            </div>
            <span className="text-[9px] text-slate-500 mt-0.5">
              Specific: {tunedProfile.specificStrength} kN·m/kg
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032] flex flex-col">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span>Corrosion Resistance (PREN)</span>
              <span
                className={`font-bold ${
                  deltaPREN > 0
                    ? "text-emerald-400"
                    : deltaPREN < 0
                    ? "text-rose-400"
                    : "text-slate-400"
                }`}
              >
                {deltaPREN > 0 ? `+${deltaPREN.toFixed(1)}` : deltaPREN.toFixed(1)}
              </span>
            </div>
            <div className="text-base font-bold text-sky-400 mt-1">
              {tunedProfile.thermo.pren}
            </div>
            <span className="text-[9px] text-slate-500 mt-0.5">
              CPT: {tunedProfile.thermo.cpt}°C
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032] flex flex-col">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span>LME Raw Material Cost</span>
              <span
                className={`font-bold ${
                  deltaCost < 0
                    ? "text-emerald-400"
                    : deltaCost > 0
                    ? "text-rose-400"
                    : "text-slate-400"
                }`}
              >
                {deltaCost > 0 ? `+$${deltaCost.toFixed(2)}` : `-$${Math.abs(deltaCost).toFixed(2)}`}
              </span>
            </div>
            <div className="text-base font-bold text-emerald-400 mt-1">
              ${tunedProfile.thermo.rawCostUSD.toFixed(2)}{" "}
              <span className="text-xs font-normal text-slate-400">/ kg</span>
            </div>
            <span className="text-[9px] text-slate-500 mt-0.5">
              Density: {tunedProfile.thermo.density} g/cm³
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032] flex flex-col">
            <div className="flex items-center justify-between text-[10px] text-slate-400">
              <span>Kou Cracking &amp; VEC</span>
              <span
                className={`text-[9px] font-bold px-1.5 py-0.2 rounded ${
                  tunedProfile.tcpRisk
                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                    : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                }`}
              >
                {tunedProfile.tcpRisk ? "TCP Phase Risk!" : "Stable Phase"}
              </span>
            </div>
            <div className="text-sm font-bold text-amber-400 mt-1">
              Kou: {tunedProfile.scheilKou.kouCrackingIndex}{" "}
              <span className="text-[10px] text-slate-400">| VEC: {tunedProfile.thermo.vec}</span>
            </div>
            <span className="text-[9px] text-slate-500 mt-0.5">
              Preheat: {tunedProfile.scheilKou.recommendedPreheatTemp_C}°C
            </span>
          </div>
        </div>
      </div>

      {/* Main Sliders Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        {Object.entries(composition).map(([elem, rawWt]) => {
          const wt = Number(rawWt) || 0;
          const isLocked = !!lockedElements[elem];
          const elemData = LME_PRICE_DATABASE[elem];
          const isBase = wt > 30;

          return (
            <div
              key={elem}
              className={`p-3 rounded-xl border transition ${
                isLocked
                  ? "bg-[#090e18] border-amber-500/30"
                  : "bg-[#0c1322] border-[#1a263c] hover:border-[#273754]"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-2 font-mono">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs ${
                      isBase
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        : "bg-sky-500/20 text-sky-300 border border-sky-500/30"
                    }`}
                  >
                    {elem}
                  </span>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <strong className="text-white text-xs">
                        {elemData?.name || elem}
                      </strong>
                      {isBase && (
                        <span className="text-[9px] px-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          Matrix
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-400">
                      ${elemData?.pricePerKgUSD || 0}/kg · ρ={elemData?.density || 0} g/cm³
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => toggleLock(elem)}
                    title={isLocked ? "Unlock (Auto-normalize)" : "Lock (Keep Fixed)"}
                    className={`p-1.5 rounded-lg border text-xs transition ${
                      isLocked
                        ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                        : "bg-[#162032] text-slate-400 hover:text-white border-[#273754]"
                    }`}
                  >
                    {isLocked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
                  </button>

                  {!isBase && Object.keys(composition).length > 2 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveElement(elem)}
                      title="Remove Element"
                      className="p-1.5 rounded-lg bg-[#162032] hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 border border-[#273754] hover:border-rose-500/30 transition text-xs"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}

                  <div className="min-w-[58px] text-right">
                    <span className="text-sm font-bold text-white font-mono">
                      {wt.toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Slider Input */}
              <div className="flex items-center gap-3">
                <input aria-label={`${elem} weight percent slider`}
                  type="range"
                  min="0"
                  max={isBase ? "95" : "45"}
                  step="0.1"
                  value={wt}
                  onChange={(e) => handleSliderChange(elem, parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-amber-400"
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Add New Micro-Alloying Element Tool */}
      {availableElementsToAdd.length > 0 && (
        <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032] flex flex-col sm:flex-row items-center justify-between gap-3 font-mono">
          <div className="flex items-center gap-2">
            <Plus className="w-4 h-4 text-emerald-400" />
            <span className="text-xs text-slate-300">
              Add Micro-Alloying Element to Formula (Dopant / Grain Refiner):
            </span>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <select aria-label="Add Micro-Alloying Element to Formula (Dopant / Grain Refiner)"
              value={elementToAdd}
              onChange={(e) => setElementToAdd(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg bg-[#162032] border border-[#273754] text-xs text-white focus:outline-none focus:border-amber-400 font-mono"
            >
              {availableElementsToAdd.map((el) => {
                const data = LME_PRICE_DATABASE[el];
                return (
                  <option key={el} value={el}>
                    {el} - {data?.name} (${data?.pricePerKgUSD}/kg)
                  </option>
                );
              })}
            </select>

            <button
              onClick={handleAddElement}
              className="px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-bold transition flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5" />
              Add (1.0%)
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
