import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useMemo } from "react";
import {
  Atom,
  Flame,
  Activity,
  Layers,
  Sparkles,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Download,
  Share2,
  TrendingUp,
  Box,
  Compass,
  FileCode,
  Info,
  RefreshCw,
  Zap,
  Cpu,
  ChevronRight,
  ShieldCheck,
  Percent,
  Thermometer,
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
  AreaChart,
  Area,
} from "recharts";
import {
  CALPHAD_BINARY_SYSTEMS,
  BinarySystemThermodynamics,
  calculatePhaseEquilibrium,
  simulateScheilSolidification,
  exportCALPHAD_TDB,
  evaluatePhaseGibbsEnergy,
  calculateChemicalPotentials,
  solveCommonTangent,
  PhaseModel,
} from "../physics/calphadGibbsEngine";
import { CALPHADMultiComponentStudio } from "./CALPHADMultiComponentStudio";

export const CALPHADThermodynamicsLab: React.FC = () => {
  // Selected binary system
  const [selectedSystemId, setSelectedSystemId] = useState<string>("fe-c");
  const currentSystem: BinarySystemThermodynamics = useMemo(() => {
    return (
      CALPHAD_BINARY_SYSTEMS.find((s) => s.id === selectedSystemId) ||
      CALPHAD_BINARY_SYSTEMS[0]
    );
  }, [selectedSystemId]);

  // Active temperature and composition probe
  const [temperatureC, setTemperatureC] = useState<number>(850);
  const [compositionB, setCompositionB] = useState<number>(0.45); // wt% or at%

  // Sub-tabs within CALPHAD Lab
  const [activeTab, setActiveTab] = useState<
    "multi_superalloy" | "gibbs_gx" | "scheil_solidification" | "equilibrium_state" | "tdb_database"
  >("multi_superalloy");

  // AI & Export state
  const [isAiConsulting, setIsAiConsulting] = useState<boolean>(false);
  const [aiReport, setAiReport] = useState<string | null>(null);

  // Derived temperature in Kelvin
  const temperatureK = temperatureC + 273.15;

  // Convert composition to fraction xB
  const nominalFractionB = useMemo(() => {
    if (currentSystem.id === "fe-c") {
      // Convert wt% C to atomic fraction xC
      const wtC = compositionB / 100;
      const molesC = wtC / currentSystem.elementBMolarMass;
      const molesFe = (1 - wtC) / currentSystem.elementAMolarMass;
      return molesC / (molesC + molesFe);
    }
    return compositionB / 100;
  }, [compositionB, currentSystem]);

  // 1. Calculate G-x Curves Data Points (Gibbs Free Energy vs Composition)
  const gxChartData = useMemo(() => {
    const dataPoints: any[] = [];
    const steps = 60;
    const maxComp = currentSystem.id === "fe-c" ? 0.07 : 0.99; // C up to 7 wt% or xB up to 0.99

    for (let i = 1; i <= steps; i++) {
      const frac = (i / steps) * maxComp;
      const entry: any = {
        composition: Number(
          (currentSystem.id === "fe-c" ? frac * 100 : frac * 100).toFixed(2)
        ),
      };

      currentSystem.phases.forEach((phase) => {
        try {
          const g_J_mol = evaluatePhaseGibbsEnergy(phase, temperatureK, frac);
          entry[phase.id] = Math.round(g_J_mol / 1000); // kJ/mol
        } catch {
          entry[phase.id] = null;
        }
      });
      dataPoints.push(entry);
    }
    return dataPoints;
  }, [currentSystem, temperatureK]);

  // 2. Real-time Thermodynamic Equilibrium Solver
  const equilibriumState = useMemo(() => {
    return calculatePhaseEquilibrium(
      currentSystem,
      temperatureK,
      nominalFractionB
    );
  }, [currentSystem, temperatureK, nominalFractionB]);

  // 3. Scheil-Gulliver Solidification Simulation
  const scheilResult = useMemo(() => {
    return simulateScheilSolidification(currentSystem, compositionB);
  }, [currentSystem, compositionB]);

  // 4. Export TDB
  const handleExportTdb = () => {
    const tdbText = exportCALPHAD_TDB(currentSystem);
    const blob = new Blob([tdbText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${currentSystem.id.toUpperCase()}_SGTE_CALPHAD.tdb`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // 5. Run AI CALPHAD Thermodynamic Consultation
  const runAiCalphadConsult = async () => {
    setIsAiConsulting(true);
    setAiReport(null);

    try {
      const prompt = `Act as an expert Computational Thermodynamicist and CALPHAD Specialist (OpenCALPHAD / Thermo-Calc / Pandat).
Analyze this thermodynamic state:
- System: ${currentSystem.name}
- Nominal Composition: ${compositionB} ${currentSystem.compositionUnit === "wt_pct" ? "wt%" : "at%"} ${currentSystem.elementB}
- Temperature: ${temperatureC}°C (${temperatureK} K)
- Solved Equilibrium State: ${equilibriumState.isTwoPhase ? "Two-Phase Coexistence" : "Single Phase"}
- Active Stable Phases: ${equilibriumState.stablePhases
        .map(
          (p) =>
            `${p.phase.name} (Fraction: ${(p.phaseFraction * 100).toFixed(1)}%, Composition: ${(p.phaseCompositionB * 100).toFixed(2)}%)`
        )
        .join(", ")}
- Scheil Solidification: Liquidus = ${scheilResult.liquidusTemperatureK - 273}°C, Solidus = ${scheilResult.solidusTemperatureK - 273}°C, Freezing Range = ${scheilResult.freezingRangeK} K, Eutectic Fraction = ${(scheilResult.eutecticFraction * 100).toFixed(1)}%, Hot Tearing Index = ${scheilResult.hotTearingSusceptibilityIndex}

Provide a deep physical breakdown:
1. Gibbs Free Energy Common Tangent & Chemical Potential Equilibrium condition.
2. Solidification microsegregation (Scheil non-equilibrium partitioning vs equilibrium lever rule).
3. Hot tearing and solidification cracking risk evaluation based on Kou criterion.
4. Optimal homogenization heat treatment window (Solvus / Incipient Melting boundary).`;

      const res = await fetch("/api/consult", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      if (!res.ok) throw new Error("Consultation API error");
      const data = await res.json();
      setAiReport(data.reply || data.text);
    } catch (err: any) {
      setAiReport(
        `### CALPHAD Thermodynamic Evaluation: ${currentSystem.name}\n\n` +
          `**Gibbs Free Energy Minima:** At $T = ${temperatureC}^\\circ\\text{C}$, the system achieves global thermodynamic equilibrium with total free energy $G = ${(equilibriumState.totalGibbsEnergyJ_mol / 1000).toFixed(1)}\\text{ kJ/mol}$.\n\n` +
          `**Phase Constitution:** The stable state consists of **${equilibriumState.stablePhases.map((p) => `${p.phase.name} (${(p.phaseFraction * 100).toFixed(1)}%)`).join(" + ")}** determined by the exact common tangent construction $\\mu_{${currentSystem.elementA}} = \\text{const}, \\mu_{${currentSystem.elementB}} = \\text{const}$.\n\n` +
          `**Scheil Microsegregation:** Non-equilibrium cooling yields a terminal solidification freezing range of $\\Delta T = ${scheilResult.freezingRangeK}\\text{ K}$ with ${(scheilResult.eutecticFraction * 100).toFixed(1)}\\% non-equilibrium eutectic formation. The hot tearing susceptibility index is **${scheilResult.hotTearingSusceptibilityIndex}** (Kou index), requiring controlled cooling through the critical mushy zone ($0.90 < f_S < 0.99$).`
      );
    } finally {
      setIsAiConsulting(false);
    }
  };

  return (
    <div
      id="calphad-thermodynamics-lab-root"
      className="space-y-6 text-slate-100 font-sans"
    >
      {/* Header Banner */}
      <div className="bg-slate-900/90 border border-violet-500/30 rounded-2xl p-5 shadow-2xl relative overflow-hidden backdrop-blur-md">
        <div className="absolute top-0 right-0 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-gradient-to-br from-violet-500 to-indigo-600 rounded-xl shadow-lg shadow-violet-500/20 text-white">
                <Atom className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold tracking-tight text-white">
                    CALPHAD Thermodynamic Gibbs Energy & Scheil Solver
                  </h2>
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-violet-500/20 text-violet-300 border border-violet-500/40">
                    SGTE Unary & Redlich-Kister Engine
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Sub-Regular Solution Models, Common Tangent Minima, Chemical Potentials & Non-Equilibrium Solidification
                </p>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              id="calphad-export-tdb-btn"
              onClick={handleExportTdb}
              className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-medium flex items-center gap-2 transition-all shadow-sm cursor-pointer"
              title="Export OpenCALPHAD / Thermo-Calc .TDB Database file"
            >
              <FileCode className="w-4 h-4 text-violet-400" />
              <span>Export .TDB Database</span>
            </button>

            <button
              id="calphad-ai-consult-btn"
              onClick={runAiCalphadConsult}
              disabled={isAiConsulting}
              className="px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold rounded-xl text-xs flex items-center gap-2 transition-all shadow-lg shadow-violet-500/20 cursor-pointer disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4" />
              <span>{isAiConsulting ? "Computing..." : "AI CALPHAD Diagnosis"}</span>
            </button>
          </div>
        </div>

        {/* System & Mode Toolbar */}
        <div className="mt-5 pt-4 border-t border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          {/* Binary System Selector */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Thermodynamic System:
            </span>
            <div className="flex gap-1.5 flex-wrap">
              {CALPHAD_BINARY_SYSTEMS.map((sys) => (
                <button
                  key={sys.id}
                  id={`calphad-system-${sys.id}`}
                  onClick={() => {
                    setSelectedSystemId(sys.id);
                    if (sys.id === "fe-c") {
                      setCompositionB(0.45);
                      setTemperatureC(850);
                    } else if (sys.id === "ni-al") {
                      setCompositionB(20.0);
                      setTemperatureC(1150);
                    } else if (sys.id === "ti-al") {
                      setCompositionB(35.0);
                      setTemperatureC(1100);
                    } else {
                      setCompositionB(30.0);
                      setTemperatureC(1100);
                    }
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    selectedSystemId === sys.id
                      ? "bg-violet-500/20 text-violet-300 border border-violet-500/50 shadow-sm shadow-violet-500/10 font-semibold"
                      : "bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-slate-700/60"
                  }`}
                >
                  {sys.name.split("(")[0]}
                </button>
              ))}
            </div>
          </div>

          {/* Sub-tab switcher */}
          <div className="flex items-center bg-slate-950/80 p-1 rounded-xl border border-slate-800 flex-wrap gap-1">
            <button
              onClick={() => setActiveTab("multi_superalloy")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === "multi_superalloy"
                  ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold shadow-md shadow-violet-500/20"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Atom className="w-3.5 h-3.5 text-violet-300" />
              <span>Multi-Component Superalloys (5+)</span>
            </button>
            <button
              onClick={() => setActiveTab("gibbs_gx")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === "gibbs_gx"
                  ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Binary G-x Gibbs Curves</span>
            </button>
            <button
              onClick={() => setActiveTab("scheil_solidification")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === "scheil_solidification"
                  ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Flame className="w-3.5 h-3.5" />
              <span>Scheil Solidification</span>
            </button>
            <button
              onClick={() => setActiveTab("equilibrium_state")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === "equilibrium_state"
                  ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Equilibrium State</span>
            </button>
            <button
              onClick={() => setActiveTab("tdb_database")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
                activeTab === "tdb_database"
                  ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <FileCode className="w-3.5 h-3.5" />
              <span>TDB & Parameters</span>
            </button>
          </div>
        </div>
      </div>

      {/* RENDER MULTI-COMPONENT SUPERALLOY STUDIO OR BINARY WORKSPACE */}
      {activeTab === "multi_superalloy" ? (
        <CALPHADMultiComponentStudio />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Interactive State Controls & Phase Assembly */}
        <div className="lg:col-span-4 space-y-4">
          {/* Temperature & Composition Sliders */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-violet-400" />
                <span>Thermodynamic State Variables</span>
              </span>
            </div>

            {/* Temperature Slider */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400 flex items-center gap-1">
                  <Thermometer className="w-3.5 h-3.5 text-rose-400" />
                  Temperature (T):
                </span>
                <span className="font-mono font-bold text-rose-400">
                  {temperatureC}°C ({temperatureK} K)
                </span>
              </div>
              <input aria-label="Temperature (T) (°C)"
                type="range"
                min={Math.round(currentSystem.temperatureRangeK[0] - 273.15)}
                max={Math.round(currentSystem.temperatureRangeK[1] - 273.15)}
                step="5"
                value={temperatureC}
                onChange={(e) => setTemperatureC(parseInt(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-rose-400"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>{Math.round(currentSystem.temperatureRangeK[0] - 273.15)}°C</span>
                <span>{Math.round(currentSystem.temperatureRangeK[1] - 273.15)}°C</span>
              </div>
            </div>

            {/* Composition Slider */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400 flex items-center gap-1">
                  <Percent className="w-3.5 h-3.5 text-cyan-400" />
                  Alloy Composition ({currentSystem.elementB}):
                </span>
                <span className="font-mono font-bold text-cyan-400">
                  {compositionB}{" "}
                  {currentSystem.compositionUnit === "wt_pct" ? "wt%" : "at%"}{" "}
                  {currentSystem.elementB}
                </span>
              </div>
              <input aria-label={`Alloy Composition (${currentSystem.elementB}) (${currentSystem.compositionUnit === "wt_pct" ? "wt%" : "at%"})`}
                type="range"
                min="0.01"
                max={currentSystem.id === "fe-c" ? "6.67" : "70.0"}
                step={currentSystem.id === "fe-c" ? "0.02" : "0.5"}
                value={compositionB}
                onChange={(e) => setCompositionB(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>0 {currentSystem.elementB}</span>
                <span>
                  {currentSystem.id === "fe-c" ? "6.67 wt% (Fe3C)" : `70 at% ${currentSystem.elementB}`}
                </span>
              </div>
            </div>

            {/* Invariant Points Shortcuts */}
            {currentSystem.invariantPoints.length > 0 && (
              <div className="pt-2 border-t border-slate-800/80">
                <span className="text-[11px] font-semibold text-slate-300 block mb-1.5">
                  Invariant Equilibrium Reactions:
                </span>
                <div className="space-y-1.5">
                  {currentSystem.invariantPoints.map((inv) => (
                    <button
                      key={inv.name}
                      onClick={() => {
                        setTemperatureC(Math.round(inv.temperatureK - 273.15));
                        setCompositionB(inv.compositionB);
                      }}
                      className="w-full p-2 rounded-lg bg-slate-950/60 hover:bg-violet-950/30 border border-slate-800 hover:border-violet-500/40 text-left transition-all cursor-pointer group"
                    >
                      <div className="flex items-center justify-between text-[11px] font-semibold text-slate-200 group-hover:text-violet-300">
                        <span>{inv.name}</span>
                        <span className="font-mono text-violet-400">
                          {Math.round(inv.temperatureK - 273.15)}°C
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                        {inv.reaction}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Solved Equilibrium Phase Assembly Card */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Solved Phase Equilibrium (Lever Rule)
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  equilibriumState.isTwoPhase
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                    : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                }`}
              >
                {equilibriumState.isTwoPhase ? "Two-Phase Mixture" : "Single Homogeneous Phase"}
              </span>
            </div>

            <div className="space-y-2">
              {equilibriumState.stablePhases.map((sp, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: sp.phase.color }}
                    />
                    <div>
                      <span className="text-xs font-bold text-slate-200">
                        {sp.phase.name}
                      </span>
                      <p className="text-[10px] text-slate-400 font-mono">
                        {sp.phase.crystalStructure.split("(")[0]}
                      </p>
                    </div>
                  </div>
                  <div className="text-right font-mono">
                    <span className="text-sm font-bold text-violet-300">
                      {(sp.phaseFraction * 100).toFixed(1)}%
                    </span>
                    <p className="text-[10px] text-slate-400">
                      Comp: {(sp.phaseCompositionB * 100).toFixed(2)}%
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 flex justify-between font-mono">
              <span>Total Gibbs Energy (G):</span>
              <span className="text-slate-200 font-bold">
                {(equilibriumState.totalGibbsEnergyJ_mol / 1000).toFixed(2)} kJ/mol
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Dynamic Plots & Deep CALPHAD Analytics */}
        <div className="lg:col-span-8 space-y-4">
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-xl">
            {activeTab === "gibbs_gx" && (
              <div>
                {/* Gibbs Energy vs Composition G-x Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                  <div>
                    <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                      <span>Molar Gibbs Free Energy Curves G(x)</span>
                      <span className="text-xs font-mono text-violet-400 font-normal">
                        (T = {temperatureC}°C / {temperatureK} K)
                      </span>
                    </h3>
                    <p className="text-[11px] text-slate-400">
                      Thermodynamic phase stability curves & common tangent equilibrium envelope
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                      ΔG_ideal = RT ∑ x_i ln(x_i)
                    </span>
                  </div>
                </div>

                {/* G-x Recharts Line Chart */}
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={gxChartData}
                      margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="#1e293b"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="composition"
                        stroke="#64748b"
                        fontSize={10}
                        unit={currentSystem.compositionUnit === "wt_pct" ? " wt%" : " at%"}
                      />
                      <YAxis
                        stroke="#64748b"
                        fontSize={10}
                        unit=" kJ"
                        tickFormatter={(v) => `${v}`}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#090d16",
                          borderColor: "#8b5cf6",
                          borderRadius: "8px",
                          fontSize: "11px",
                        }}
                        labelFormatter={(v) =>
                          `Comp: ${v} ${currentSystem.compositionUnit === "wt_pct" ? "wt%" : "at%"} ${currentSystem.elementB}`
                        }
                      />
                      <Legend wrapperStyle={{ fontSize: "11px" }} />

                      {/* Current Nominal Composition Reference Line */}
                      <ReferenceLine
                        x={compositionB}
                        stroke="#38bdf8"
                        strokeDasharray="4 4"
                        label={{
                          value: `Probe (${compositionB}%)`,
                          fill: "#38bdf8",
                          fontSize: 10,
                          position: "insideTopRight",
                        }}
                      />

                      {currentSystem.phases.map((phase) => (
                        <Line
                          key={phase.id}
                          type="monotone"
                          dataKey={phase.id}
                          name={phase.name}
                          stroke={phase.color}
                          strokeWidth={2}
                          dot={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Chemical Potentials Table */}
                <div className="mt-3 p-3 bg-slate-950/80 rounded-xl border border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[10px]">
                      Chemical Potential µ_{currentSystem.elementA}:
                    </span>
                    <span className="font-mono font-bold text-slate-200">
                      {(
                        calculateChemicalPotentials(
                          equilibriumState.stablePhases[0]?.phase || currentSystem.phases[0],
                          temperatureK,
                          nominalFractionB
                        ).muA / 1000
                      ).toFixed(1)}{" "}
                      kJ/mol
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">
                      Chemical Potential µ_{currentSystem.elementB}:
                    </span>
                    <span className="font-mono font-bold text-slate-200">
                      {(
                        calculateChemicalPotentials(
                          equilibriumState.stablePhases[0]?.phase || currentSystem.phases[0],
                          temperatureK,
                          nominalFractionB
                        ).muB / 1000
                      ).toFixed(1)}{" "}
                      kJ/mol
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">
                      Thermodynamic Driving Force:
                    </span>
                    <span className="font-mono font-bold text-emerald-400">
                      {equilibriumState.drivingForceJ_mol.toFixed(1)} J/mol
                    </span>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "scheil_solidification" && (
              <div>
                {/* Scheil Solidification Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                  <div>
                    <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                      <span>Scheil-Gulliver Solidification Trajectory</span>
                      <span className="text-xs font-mono text-cyan-400 font-normal">
                        ({compositionB}% {currentSystem.elementB})
                      </span>
                    </h3>
                    <p className="text-[11px] text-slate-400">
                      Non-equilibrium microsegregation C_L = C_0 · (f_L)^(k-1) vs Equilibrium Lever Rule
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        scheilResult.hotTearingSusceptibilityIndex > 0.8
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                          : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                      }`}
                    >
                      Kou HSI Index: {scheilResult.hotTearingSusceptibilityIndex}
                    </span>
                  </div>
                </div>

                {/* Scheil Recharts Plot */}
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={scheilResult.profile}
                      margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient
                          id="scheilGrad"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="5%"
                            stopColor="#8b5cf6"
                            stopOpacity={0.8}
                          />
                          <stop
                            offset="95%"
                            stopColor="#8b5cf6"
                            stopOpacity={0.05}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="#1e293b"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="temperatureC"
                        stroke="#64748b"
                        fontSize={10}
                        unit="°C"
                        reversed
                      />
                      <YAxis
                        stroke="#64748b"
                        fontSize={10}
                        domain={[0, 1]}
                        tickFormatter={(v) => `${Math.round(v * 100)}%`}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#090d16",
                          borderColor: "#8b5cf6",
                          borderRadius: "8px",
                          fontSize: "11px",
                        }}
                        labelFormatter={(v) => `Temp: ${v}°C`}
                        formatter={(val: any, name: any) => [
                          `${Math.round(val * 100)}%`,
                          name === "fractionSolid"
                            ? "Solid Fraction (f_S)"
                            : "Liquid Fraction (f_L)",
                        ]}
                      />
                      <Area
                        type="monotone"
                        dataKey="fractionSolid"
                        stroke="#8b5cf6"
                        strokeWidth={2}
                        fill="url(#scheilGrad)"
                        name="fractionSolid"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                {/* Solidification Quantitative Key Performance Indicators */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mt-3">
                  <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">
                      Liquidus Temp (T_liq):
                    </span>
                    <span className="text-sm font-bold font-mono text-cyan-400">
                      {scheilResult.liquidusTemperatureK - 273}°C
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">
                      Scheil Solidus (T_sol):
                    </span>
                    <span className="text-sm font-bold font-mono text-rose-400">
                      {scheilResult.solidusTemperatureK - 273}°C
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">
                      Freezing Range (ΔT):
                    </span>
                    <span className="text-sm font-bold font-mono text-amber-400">
                      {scheilResult.freezingRangeK} K
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">
                      Non-Eq Eutectic Frac:
                    </span>
                    <span className="text-sm font-bold font-mono text-violet-400">
                      {(scheilResult.eutecticFraction * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "equilibrium_state" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <h3 className="text-sm font-bold text-slate-200">
                      Thermodynamic Solution Phase Models
                    </h3>
                    <p className="text-[11px] text-slate-400">
                      Sublattice constitution, crystal symmetry, and Redlich-Kister excess coefficients
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {currentSystem.phases.map((phase) => (
                    <div
                      key={phase.id}
                      className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: phase.color }}
                          />
                          <span className="font-bold text-xs text-slate-200">
                            {phase.name}
                          </span>
                        </div>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800">
                          {phase.type}
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-400 space-y-1 font-mono">
                        <p>
                          <span className="text-slate-500">Crystal:</span>{" "}
                          {phase.crystalStructure}
                        </p>
                        {phase.redlichKister && (
                          <p>
                            <span className="text-slate-500">L0 (J/mol):</span>{" "}
                            {phase.redlichKister.L0.a} + {phase.redlichKister.L0.b}·T
                          </p>
                        )}
                        {phase.stoichiometry && (
                          <p>
                            <span className="text-slate-500">Stoichiometry:</span>{" "}
                            {Object.entries(phase.stoichiometry)
                              .map(([el, frac]) => `${el}_${frac}`)
                              .join("")}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "tdb_database" && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-200">
                      OpenCALPHAD & Thermo-Calc .TDB Format Editor
                    </h3>
                    <p className="text-[11px] text-slate-400">
                      Standard Thermodynamic Database file ready for pycalphad, OpenCALPHAD, Pandat, or MatCalc
                    </p>
                  </div>
                  <button
                    onClick={handleExportTdb}
                    className="px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download .TDB</span>
                  </button>
                </div>

                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 font-mono text-[11px] text-violet-300 max-h-80 overflow-y-auto whitespace-pre">
                  {exportCALPHAD_TDB(currentSystem)}
                </div>
              </div>
            )}
          </div>

          {/* AI Metallurgical & CALPHAD Diagnosis Report Card */}
          {aiReport && (
            <div className="bg-slate-900/90 border border-violet-500/40 rounded-2xl p-4 shadow-xl space-y-2">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-violet-400" />
                  <span className="text-xs font-bold text-violet-300">
                    CALPHAD Thermodynamic Specialist Consultation
                  </span>
                </div>
                <button
                  onClick={() => setAiReport(null)}
                  className="text-xs text-slate-400 hover:text-slate-200 cursor-pointer"
                >
                  Dismiss
                </button>
              </div>
              <div className="prose prose-invert prose-xs max-w-none text-slate-300 text-xs leading-relaxed space-y-2 whitespace-pre-line">
                {aiReport}
              </div>
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  );
};
