import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useEffect, useMemo } from "react";
import {
  Flame,
  Zap,
  Cpu,
  Clock,
  Layers,
  ArrowRight,
  RefreshCw,
  Sliders,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Atom,
  Info,
  ChevronRight,
  ShieldAlert,
  Activity,
  FileSpreadsheet
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  BarChart,
  Bar,
  Cell,
  PieChart,
  Pie,
  ReferenceLine,
  AreaChart,
  Area
} from "recharts";
import { pythonComputationService, PythonKineticsResult } from "../services/pythonComputationService";

interface PhaseKineticsTTTCCTStudioProps {
  initialAlloy?: string;
  onSendToModule?: (target: string, payload: any) => void;
}

export const PhaseKineticsTTTCCTStudio: React.FC<PhaseKineticsTTTCCTStudioProps> = ({
  initialAlloy = "AISI 4140",
  onSendToModule
}) => {
  const [selectedAlloy, setSelectedAlloy] = useState<string>(initialAlloy);
  const [coolingRate, setCoolingRate] = useState<number>(10.0);
  const [grainSize, setGrainSize] = useState<number>(25.0);
  const [austTemp, setAustTemp] = useState<number>(860.0);
  const [agingTemp, setAgingTemp] = useState<number>(720.0);
  const [agingTime, setAgingTime] = useState<number>(8.0);
  const [activeViewTab, setActiveViewTab] = useState<"ttt" | "cct" | "calphad_vs_kinetics" | "lsw_aging" | "microstructure">("ttt");
  
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [kineticsData, setKineticsData] = useState<PythonKineticsResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const alloyOptions = [
    { id: "AISI 4140", name: "AISI 4140 (Cr-Mo Structural Steel)", type: "Low-Alloy Steel", defAust: 860 },
    { id: "AISI 4340", name: "AISI 4340 (Ni-Cr-Mo High Hardenability)", type: "High-Strength Steel", defAust: 845 },
    { id: "AISI D2", name: "AISI D2 (Ledeburitic Tool Steel)", type: "Cold-Work Tool Steel", defAust: 1020 },
    { id: "Inconel 718", name: "Inconel 718 (Ni-Fe Superalloy)", type: "Ni Superalloy", defAust: 980 },
    { id: "Ti-6Al-4V", name: "Ti-6Al-4V (Grade 5 Alpha-Beta)", type: "Titanium Alloy", defAust: 1050 },
    { id: "Al 7075", name: "Al 7075-T6 (Al-Zn-Mg-Cu)", type: "Aerospace Aluminum", defAust: 475 }
  ];

  const handleAlloyChange = (alloyName: string) => {
    setSelectedAlloy(alloyName);
    const opt = alloyOptions.find(o => o.id === alloyName);
    if (opt) {
      setAustTemp(opt.defAust);
    }
  };

  const runKineticsCalculation = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await pythonComputationService.calculatePhaseKineticsTTTCCT({
        alloy: selectedAlloy,
        coolingRate_C_s: coolingRate,
        grainSize_um: grainSize,
        austTemp_C: austTemp,
        agingTemp_C: agingTemp,
        agingTime_h: agingTime
      });
      setKineticsData(res);
    } catch (err: any) {
      console.error("Kinetics calculation failed:", err);
      setErrorMsg(err?.message || "Failed to solve transformation kinetics.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    runKineticsCalculation();
  }, [selectedAlloy]);

  // Formatted TTT data for Recharts (Log10 time x-axis mapping)
  const formattedTTTData = useMemo(() => {
    if (!kineticsData?.tttIsothermalCurves) return [];
    return kineticsData.tttIsothermalCurves.map((pt) => ({
      temperature: pt.temperature_C,
      phase: pt.phase,
      log_tStart: Math.log10(Math.max(0.0001, pt.tStart_s)),
      log_t50: Math.log10(Math.max(0.0002, pt.t50_s)),
      log_tFinish: Math.log10(Math.max(0.0003, pt.tFinish_s)),
      tStart_s: pt.tStart_s,
      t50_s: pt.t50_s,
      tFinish_s: pt.tFinish_s
    }));
  }, [kineticsData]);

  // CCT cooling curve overlay path for the user-selected cooling rate
  const userCoolingTrajectory = useMemo(() => {
    if (!kineticsData) return [];
    const pts = [];
    const t0 = austTemp;
    const cr = coolingRate;
    // Log time steps from 0.01s to 1000s
    for (let logT = -2; logT <= 4; logT += 0.2) {
      const t_s = Math.pow(10, logT);
      const temp = Math.max(25, t0 - cr * t_s);
      pts.push({
        log_t: logT,
        time_s: t_s,
        temperature: temp
      });
    }
    return pts;
  }, [kineticsData, austTemp, coolingRate]);

  // Phase fractions pie chart colors
  const phaseColors: Record<string, string> = {
    Martensite: "#ef4444",
    Bainite: "#f59e0b",
    Pearlite_Ferrite: "#3b82f6",
    RetainedAustenite: "#8b5cf6"
  };

  const currentCCTMatch = useMemo(() => {
    if (!kineticsData?.cctContinuousCoolingMap) return null;
    // Find closest cooling rate in table
    const sorted = [...kineticsData.cctContinuousCoolingMap].sort(
      (a, b) => Math.abs(a.coolingRate_C_s - coolingRate) - Math.abs(b.coolingRate_C_s - coolingRate)
    );
    return sorted[0];
  }, [kineticsData, coolingRate]);

  const pieData = useMemo(() => {
    if (!currentCCTMatch) return [];
    const pf = currentCCTMatch.phaseFractions;
    return [
      { name: "Martensite", value: pf.Martensite_pct, color: phaseColors.Martensite },
      { name: "Bainite", value: pf.Bainite_pct, color: phaseColors.Bainite },
      { name: "Pearlite / Ferrite", value: pf.Pearlite_Ferrite_pct, color: phaseColors.Pearlite_Ferrite },
      { name: "Retained Austenite", value: pf.RetainedAustenite_pct, color: phaseColors.RetainedAustenite }
    ].filter(d => d.value > 0);
  }, [currentCCTMatch]);

  return (
    <div className="w-full bg-[#070e1a] text-slate-100 min-h-screen p-4 md:p-6 font-sans">
      {/* Top Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-white tracking-wide">
                  TTT / CCT & Diffusion Phase Transformation Kinetics Studio
                </h1>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  DICTRA / JMAK / LSW
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  PYTHON 3.10 HPC
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Bridging the R&D Gap: <span className="text-sky-300">Thermodynamic Equilibrium (CALPHAD)</span> vs. <span className="text-amber-300">Non-Equilibrium Kinetics (Cooling Rate dT/dt, JMAK Nucleation & LSW Coarsening)</span>
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={runKineticsCalculation}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-slate-950 font-bold text-xs shadow-lg shadow-amber-500/20 transition-all cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>{isLoading ? "Solving Kinetics..." : "Re-Calculate TTT/CCT"}</span>
          </button>
        </div>
      </div>

      {/* Critical R&D Conceptual Banner */}
      <div className="mt-4 p-3.5 rounded-xl bg-slate-900/90 border border-amber-500/30 flex items-start gap-3 text-xs">
        <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="text-slate-300 leading-relaxed">
          <strong className="text-amber-300 font-semibold">R&amp;D Metallurgist Note:</strong> CALPHAD describes <span className="underline decoration-sky-400">"where the system wants to go"</span> (thermodynamic equilibrium), while TTT/CCT kinetics dictates <span className="underline decoration-amber-400">"whether it has time to get there"</span> (diffusion barriers &amp; cooling rates). In real heat treatment, welding, and LPBF additive processes, cooling rates reach 1 – 1,000,000 K/s, fully suppressing equilibrium phases in favor of metastable structures (Martensite, SSSS, γ'').
        </div>
      </div>

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-6">
        {/* Left Column: Kinetic Controls (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Alloy & Material Selection */}
          <div className="p-4 rounded-xl bg-[#0b1322] border border-slate-800">
            <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-2">
              1. Select Alloy System
            </label>
            <select aria-label="1. Select Alloy System"
              value={selectedAlloy}
              onChange={(e) => handleAlloyChange(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-semibold text-white focus:outline-none focus:border-amber-500"
            >
              {alloyOptions.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>

            {kineticsData?.alloyMetadata && (
              <div className="mt-3 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-[11px] space-y-1">
                <div className="text-slate-400 flex justify-between">
                  <span>Alloy Class:</span>
                  <span className="text-white font-medium">{kineticsData.alloyMetadata.type}</span>
                </div>
                <div className="text-slate-400 flex justify-between">
                  <span>Activation Energy $Q$:</span>
                  <span className="text-amber-300 font-mono font-medium">{kineticsData.alloyMetadata.Q_diff_kJ_mol} kJ/mol</span>
                </div>
                <div className="text-slate-400 flex justify-between">
                  <span>Critical Cooling Rate ($v_&#123;crit&#125;$):</span>
                  <span className="text-emerald-400 font-mono font-bold">{kineticsData.alloyMetadata.critical_cooling_rate_C_s} °C/s</span>
                </div>
              </div>
            )}
          </div>

          {/* Heat Treatment & Kinetic Parameters */}
          <div className="p-4 rounded-xl bg-[#0b1322] border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                2. Continuous Cooling Rate ($\dot&#123;T&#125;$)
              </label>
              <span className="text-xs font-mono font-bold text-amber-300 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                {coolingRate} °C/s
              </span>
            </div>
            <input aria-label="2. Continuous Cooling Rate (°C/s)"
              type="range"
              min="0.1"
              max="500"
              step="0.5"
              value={coolingRate}
              onChange={(e) => setCoolingRate(parseFloat(e.target.value))}
              className="w-full accent-amber-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>0.1 °C/s (Furnace)</span>
              <span>10 °C/s (Air)</span>
              <span>100 °C/s (Oil)</span>
              <span>500 °C/s (Water/AM)</span>
            </div>

            {/* Quick cooling rate presets */}
            <div className="grid grid-cols-4 gap-1.5 pt-1">
              {[
                { label: "Furnace", val: 0.1 },
                { label: "Air Cool", val: 2.5 },
                { label: "Oil Quench", val: 25.0 },
                { label: "Water/LPBF", val: 250.0 }
              ].map((p) => (
                <button
                  key={p.label}
                  onClick={() => setCoolingRate(p.val)}
                  className={`px-2 py-1 rounded text-[10px] font-medium border transition-all cursor-pointer ${
                    coolingRate === p.val
                      ? "bg-amber-500/20 border-amber-500/50 text-amber-300"
                      : "bg-slate-900 border-slate-800 text-slate-400 hover:text-white"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            <div className="border-t border-slate-800 pt-3 space-y-3">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">Austenitizing / Solution Temp ($T_\gamma$):</span>
                  <span className="text-white font-mono font-bold">{austTemp} °C</span>
                </div>
                <input aria-label="Austenitizing / Solution Temp (°C)"
                  type="range"
                  min="400"
                  max="1200"
                  step="5"
                  value={austTemp}
                  onChange={(e) => setAustTemp(parseFloat(e.target.value))}
                  className="w-full accent-sky-500"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">Prior Grain Size ($d_\gamma$):</span>
                  <span className="text-white font-mono font-bold">{grainSize} µm</span>
                </div>
                <input aria-label="Prior Grain Size (µm)"
                  type="range"
                  min="5"
                  max="100"
                  step="1"
                  value={grainSize}
                  onChange={(e) => setGrainSize(parseFloat(e.target.value))}
                  className="w-full accent-sky-500"
                />
              </div>
            </div>
          </div>

          {/* Aging & LSW Controls */}
          <div className="p-4 rounded-xl bg-[#0b1322] border border-slate-800 space-y-3">
            <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              3. Isothermal Aging (LSW Coarsening)
            </label>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="text-[10px] text-slate-400 block mb-1">Aging Temp (°C)</span>
                <input aria-label="Aging Temp (°C)"
                  type="number"
                  value={agingTemp}
                  onChange={(e) => setAgingTemp(parseFloat(e.target.value) || 200)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-white"
                />
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block mb-1">Aging Time (hours)</span>
                <input aria-label="Aging Time (hours)"
                  type="number"
                  value={agingTime}
                  onChange={(e) => setAgingTime(parseFloat(e.target.value) || 1)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-white"
                />
              </div>
            </div>
          </div>

          {/* Critical Transformation Points Card */}
          {kineticsData?.criticalTransformationTemperatures && (
            <div className="p-4 rounded-xl bg-[#0b1322] border border-slate-800">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-sky-400" />
                <span>Critical Temperatures</span>
              </h3>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                  <div className="text-[10px] text-slate-500">$A_&#123;e3&#125;$ / $\beta_&#123;transus&#125;$</div>
                  <div className="text-sky-300 font-bold text-sm">
                    {kineticsData.criticalTransformationTemperatures.Ae3_BetaTransus_GammaSolvus_C} °C
                  </div>
                </div>
                <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                  <div className="text-[10px] text-slate-500">$A_&#123;e1&#125;$ Eutectoid</div>
                  <div className="text-slate-300 font-bold text-sm">
                    {kineticsData.criticalTransformationTemperatures.Ae1_C} °C
                  </div>
                </div>
                <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                  <div className="text-[10px] text-slate-500">Martensite Start ($M_s$)</div>
                  <div className="text-red-400 font-bold text-sm">
                    {kineticsData.criticalTransformationTemperatures.Ms_C} °C
                  </div>
                </div>
                <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                  <div className="text-[10px] text-slate-500">Martensite Finish ($M_f$)</div>
                  <div className="text-red-500 font-bold text-sm">
                    {kineticsData.criticalTransformationTemperatures.Mf_C} °C
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Visualization Tabs (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          {/* View Mode Tabs */}
          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[#0b1322] border border-slate-800 overflow-x-auto">
            {[
              { id: "ttt", label: "1. TTT Isothermal Diagram", icon: Clock },
              { id: "cct", label: "2. CCT Continuous Cooling", icon: TrendingUp },
              { id: "calphad_vs_kinetics", label: "3. CALPHAD vs. Kinetics Gap", icon: AlertTriangle },
              { id: "lsw_aging", label: "4. LSW Aging & Orowan", icon: Atom },
              { id: "microstructure", label: "5. Phase & Hardness", icon: Layers }
            ].map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveViewTab(tab.id as any)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                    activeViewTab === tab.id
                      ? "bg-amber-500 text-slate-950 shadow-md font-bold"
                      : "text-slate-400 hover:text-white hover:bg-slate-900"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* TAB 1: TTT ISOTHERMAL DIAGRAM */}
          {activeViewTab === "ttt" && (
            <div className="p-5 rounded-2xl bg-[#0b1322] border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>Time-Temperature-Transformation (TTT) Diagram</span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/30">
                      JMAK Nucleation & Growth C-Curves
                    </span>
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Isothermal transformation kinetics: $X(t) = 1 - \exp(-k \cdot t^n)$
                  </p>
                </div>
                <div className="flex items-center gap-3 text-[11px] font-mono">
                  <span className="flex items-center gap-1 text-emerald-400">
                    <span className="w-2.5 h-0.5 bg-emerald-400 inline-block"></span> 1% (Start)
                  </span>
                  <span className="flex items-center gap-1 text-amber-400">
                    <span className="w-2.5 h-0.5 bg-amber-400 inline-block"></span> 50% Transformed
                  </span>
                  <span className="flex items-center gap-1 text-red-400">
                    <span className="w-2.5 h-0.5 bg-red-400 inline-block"></span> 99% (Finish)
                  </span>
                </div>
              </div>

              {/* TTT Chart */}
              <div className="h-[420px] w-full pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={formattedTTTData}
                    layout="vertical"
                    margin={{ top: 10, right: 30, left: 10, bottom: 20 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                      type="number"
                      dataKey="log_tStart"
                      domain={[-3, 5]}
                      tickFormatter={(val) => `10^${val}s`}
                      label={{ value: "Time (seconds, Log Scale)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                      stroke="#475569"
                    />
                    <YAxis
                      type="number"
                      dataKey="temperature"
                      domain={[100, 900]}
                      label={{ value: "Temperature (°C)", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }}
                      stroke="#475569"
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const d = payload[0].payload;
                          return (
                            <div className="p-3 rounded-xl bg-slate-900 border border-slate-700 shadow-xl text-xs font-mono">
                              <div className="font-bold text-white mb-1">{d.temperature} °C ({d.phase})</div>
                              <div className="text-emerald-400">1% Start: {d.tStart_s} s</div>
                              <div className="text-amber-400">50% Trans: {d.t50_s} s</div>
                              <div className="text-red-400">99% Finish: {d.tFinish_s} s</div>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    {/* Critical Temperature Reference Lines */}
                    {kineticsData && (
                      <>
                        <ReferenceLine y={kineticsData.criticalTransformationTemperatures.Ae3_BetaTransus_GammaSolvus_C} stroke="#38bdf8" strokeDasharray="4 4" label={{ value: "Ae3", fill: "#38bdf8", fontSize: 10 }} />
                        <ReferenceLine y={kineticsData.criticalTransformationTemperatures.Ms_C} stroke="#f87171" strokeDasharray="4 4" label={{ value: "Ms", fill: "#f87171", fontSize: 10 }} />
                      </>
                    )}
                    <Line type="monotone" dataKey="log_tStart" stroke="#10b981" strokeWidth={2} dot={false} name="1% Start" />
                    <Line type="monotone" dataKey="log_t50" stroke="#f59e0b" strokeWidth={2} strokeDasharray="4 2" dot={false} name="50% Trans" />
                    <Line type="monotone" dataKey="log_tFinish" stroke="#ef4444" strokeWidth={2} dot={false} name="99% Finish" />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between text-xs">
                <span className="text-slate-400">
                  Nose Temperature (Shortest Incubation): <strong className="text-amber-300">~560 °C (Pearlite Nose) / ~420 °C (Bainite Nose)</strong>
                </span>
                <span className="text-slate-400">
                  Martensite Transformation: <strong className="text-red-400">Athermal (Diffusionless, Koistinen-Marburger)</strong>
                </span>
              </div>
            </div>
          )}

          {/* TAB 2: CCT CONTINUOUS COOLING TRANSFORMATION */}
          {activeViewTab === "cct" && (
            <div className="p-5 rounded-2xl bg-[#0b1322] border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>Continuous Cooling Transformation (CCT) Map</span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                      Scheil Additivity Rule ∫ (dt / τ(T)) = 1
                    </span>
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Cooling rate dependency across quenching regimes from 0.05 °C/s to 2000 °C/s
                  </p>
                </div>
              </div>

              {/* CCT Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border border-slate-800 rounded-xl overflow-hidden font-mono">
                  <thead className="bg-slate-900 text-slate-400 text-[10px] uppercase">
                    <tr>
                      <th className="p-2.5">Cooling Rate ($\dot&#123;T&#125;$)</th>
                      <th className="p-2.5">Start Temp</th>
                      <th className="p-2.5">Incubation Time</th>
                      <th className="p-2.5">Microstructure Product</th>
                      <th className="p-2.5">Martensite %</th>
                      <th className="p-2.5">Hardness</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
                    {kineticsData?.cctContinuousCoolingMap.map((row, idx) => {
                      const isSelected = Math.abs(row.coolingRate_C_s - coolingRate) < 1.0;
                      return (
                        <tr
                          key={idx}
                          className={`${
                            isSelected
                              ? "bg-amber-500/15 border-l-4 border-amber-400 font-bold"
                              : "hover:bg-slate-900/40"
                          } transition-all`}
                        >
                          <td className="p-2.5 text-amber-300">{row.coolingRate_C_s} °C/s</td>
                          <td className="p-2.5 text-slate-200">{row.transformedStartTemp_C} °C</td>
                          <td className="p-2.5 text-slate-300">{row.transformedStartTime_s} s</td>
                          <td className="p-2.5">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              row.primaryMicrostructure === "Martensite" || row.primaryMicrostructure.includes("Martensite")
                                ? "bg-red-500/20 text-red-300 border border-red-500/30"
                                : row.primaryMicrostructure === "Bainite"
                                ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                                : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                            }`}>
                              {row.primaryMicrostructure}
                            </span>
                          </td>
                          <td className="p-2.5 text-red-400 font-bold">{row.phaseFractions.Martensite_pct}%</td>
                          <td className="p-2.5 text-emerald-400 font-bold">{row.predictedHardness_HRC} HRC ({row.predictedHardness_HV} HV)</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: CALPHAD VS KINETICS GAP (CORE R&D CRITIQUE) */}
          {activeViewTab === "calphad_vs_kinetics" && (
            <div className="p-5 rounded-2xl bg-[#0b1322] border border-slate-800 space-y-5">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span>Thermodynamic Equilibrium (CALPHAD) vs. Kinetic Reality Gap Analysis</span>
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Direct comparison illustrating why CALPHAD equilibrium assumptions fail in real heat treatment & additive manufacturing.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* CALPHAD View */}
                <div className="p-4 rounded-xl bg-slate-900/90 border border-sky-500/30 space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                    <span className="text-xs font-bold text-sky-300 uppercase tracking-wide">
                      CALPHAD (Equilibrium, $t \rightarrow \infty$)
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20">
                      Gibbs Minimization
                    </span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Assumed Cooling Rate:</span>
                      <span className="text-sky-300 font-mono font-bold">0.000 °C/s (Infinitely Slow)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Predicted RT Phases:</span>
                      <span className="text-white font-medium">Ferrite + Cementite / Equilibrium Phase</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Martensite Fraction:</span>
                      <span className="text-red-400 font-mono font-bold">0.0% (Thermodynamically Forbidden)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Solute Supersaturation:</span>
                      <span className="text-slate-300 font-mono">0.00% (Complete Partitioning)</span>
                    </div>
                  </div>
                  <div className="p-2.5 rounded bg-sky-950/40 border border-sky-500/20 text-[11px] text-sky-200">
                    💡 <em>CALPHAD computes the ground-state global minimum of the Gibbs energy surface, completely ignoring diffusion time scales.</em>
                  </div>
                </div>

                {/* Kinetic Reality View */}
                <div className="p-4 rounded-xl bg-slate-900/90 border border-amber-500/30 space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                    <span className="text-xs font-bold text-amber-300 uppercase tracking-wide">
                      KINETIC REALITY (dT/dt = {coolingRate} °C/s)
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                      JMAK & Scheil
                    </span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Actual Cooling Rate:</span>
                      <span className="text-amber-300 font-mono font-bold">{coolingRate} °C/s</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Diffusion Suppression Index:</span>
                      <span className="text-emerald-400 font-mono font-bold">
                        {kineticsData?.calphadVsKineticsGap.kineticRealityAtSelectedCooling.diffusionSuppressionIndex} (1.0 = Frozen)
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Actual Martensite Formed:</span>
                      <span className="text-red-400 font-mono font-bold">
                        {kineticsData?.calphadVsKineticsGap.kineticRealityAtSelectedCooling.predictedMartensite_pct}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Microstructural Verdict:</span>
                      <span className="text-amber-300 font-semibold">
                        {kineticsData?.calphadVsKineticsGap.kineticRealityAtSelectedCooling.verdict}
                      </span>
                    </div>
                  </div>
                  <div className="p-2.5 rounded bg-amber-950/40 border border-amber-500/20 text-[11px] text-amber-200">
                    ⚡ <em>At {coolingRate} °C/s, carbon and alloying atoms cannot diffuse across grain boundaries in time; austenite is forced to transform athermally via shear.</em>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: LSW PRECIPITATE AGING & OROWAN */}
          {activeViewTab === "lsw_aging" && (
            <div className="p-5 rounded-2xl bg-[#0b1322] border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>Lifshitz-Slyozov-Wagner (LSW) Precipitate Coarsening</span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/30">
                      r³(t) - r₀³ = K_LSW · t
                    </span>
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Precipitate particle radius growth and transition from Dislocation Cutting to Orowan Looping.
                  </p>
                </div>
              </div>

              {/* LSW Coarsening Chart */}
              <div className="h-[320px] w-full pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={kineticsData?.lswPrecipitateCoarsening || []}
                    margin={{ top: 10, right: 30, left: 10, bottom: 20 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                      dataKey="agingTime_h"
                      label={{ value: "Aging Time (hours)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                      stroke="#475569"
                    />
                    <YAxis
                      yAxisId="left"
                      label={{ value: "Mean Precipitate Radius (nm)", angle: -90, position: "insideLeft", fill: "#a855f7", fontSize: 11 }}
                      stroke="#a855f7"
                    />
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      label={{ value: "Orowan Strengthening Δσ (MPa)", angle: 90, position: "insideRight", fill: "#10b981", fontSize: 11 }}
                      stroke="#10b981"
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const d = payload[0].payload;
                          return (
                            <div className="p-3 rounded-xl bg-slate-900 border border-slate-700 shadow-xl text-xs font-mono">
                              <div className="font-bold text-white mb-1">Aging Time: {d.agingTime_h} h</div>
                              <div className="text-purple-400">Mean Radius: {d.meanRadius_nm} nm</div>
                              <div className="text-emerald-400">Strength Boost: +{d.precipitationHardening_MPa} MPa</div>
                              <div className="text-slate-400 mt-1 text-[10px]">Mechanism: {d.strengtheningMechanism}</div>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Line yAxisId="left" type="monotone" dataKey="meanRadius_nm" stroke="#a855f7" strokeWidth={2.5} name="Mean Radius (nm)" />
                    <Line yAxisId="right" type="monotone" dataKey="precipitationHardening_MPa" stroke="#10b981" strokeWidth={2.5} strokeDasharray="3 3" name="Orowan Yield Boost (MPa)" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* TAB 5: MICROSTRUCTURE & HARDNESS PREDICTOR */}
          {activeViewTab === "microstructure" && (
            <div className="p-5 rounded-2xl bg-[#0b1322] border border-slate-800 space-y-5">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <span>Room-Temperature Retained Phase Distribution & Hardness</span>
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Predicted phase fractions and Vickers/Rockwell hardness at cooling rate {coolingRate} °C/s
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                {/* Pie Chart */}
                <div className="h-[260px] w-full flex items-center justify-center">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={90}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(val: number) => [`${val}%`, "Fraction"]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                {/* Hardness & Summary */}
                <div className="space-y-3">
                  <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider">PREDICTED HARDNESS AT RT</div>
                    <div className="flex items-baseline gap-3">
                      <span className="text-2xl font-bold font-mono text-emerald-400">
                        {currentCCTMatch?.predictedHardness_HRC || 52} HRC
                      </span>
                      <span className="text-sm font-mono text-slate-400">
                        ({currentCCTMatch?.predictedHardness_HV || 550} HV)
                      </span>
                    </div>
                  </div>

                  <div className="space-y-1.5 text-xs font-mono">
                    {pieData.map((p) => (
                      <div key={p.name} className="flex items-center justify-between p-2 rounded bg-slate-900/40">
                        <div className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: p.color }}></span>
                          <span className="text-slate-300">{p.name}</span>
                        </div>
                        <span className="font-bold text-white">{p.value}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
