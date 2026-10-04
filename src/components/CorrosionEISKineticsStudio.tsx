import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useEffect } from "react";
import { useDebouncedLatestTask } from "../hooks/useDebouncedLatestTask";
import {
  ShieldAlert,
  ShieldCheck,
  Droplets,
  Activity,
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  RefreshCw,
  Sliders,
  Layers,
  Code,
  Zap,
  Flame,
  ArrowRight,
  Sparkles,
  Compass
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
  ReferenceLine
} from "recharts";

interface CorrosionEISKineticsStudioProps {
  onSendToCNLS?: (points: any[], name: string) => void;
}

export function CorrosionEISKineticsStudio({ onSendToCNLS }: CorrosionEISKineticsStudioProps) {
  const [metalId, setMetalId] = useState<string>("steel-316l");
  const [betaA, setBetaA] = useState<number>(0.12);
  const [betaC, setBetaC] = useState<number>(0.10);
  const [i0Corr, setI0Corr] = useState<number>(0.15); // uA/cm2
  const [ePit, setEPit] = useState<number>(0.45); // V
  const [e0, setE0] = useState<number>(0.08); // V
  const [exposureDays, setExposureDays] = useState<number>(60);
  const [coatingType, setCoatingType] = useState<string>("epoxy");

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [simResult, setSimResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<"coating_nyquist" | "water_uptake" | "pore_decay" | "python_code">("coating_nyquist");

  const runPythonSimulation = async (signal?: AbortSignal): Promise<boolean> => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const response = await fetch("/api/python/battery-corrosion-eis", {
        signal,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "corrosion_kinetics",
          metalId,
          betaA,
          betaC,
          i0Corr_uA: i0Corr,
          ePit,
          e0,
          exposureDays,
        }),
      });

      if (!response.ok) {
        throw new Error(`Python solver HTTP error: ${response.statusText}`);
      }

      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }
      if (signal?.aborted) return false;
      setSimResult(data);
      return true;
    } catch (err: any) {
      if (signal?.aborted) return false;
      console.error("Corrosion EIS simulation error:", err);
      setErrorMsg(err.message || "Failed to execute Python corrosion kinetics solver.");
      return false;
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  };

  // Debounced, visibility-gated and abortable. coatingType is not part of the request body, so it is not
  // part of the input signature (changing it never produced a different request).
  const corrosionInputSignature = JSON.stringify([metalId, betaA, betaC, i0Corr, ePit, e0, exposureDays]);
  useEffect(() => {
    setSimResult(null);
  }, [corrosionInputSignature]);
  const { runNow: runPythonSimulationNow } = useDebouncedLatestTask(corrosionInputSignature, (_signature, signal) => runPythonSimulation(signal), 200);

  const currentCoatingStage = simResult?.coatingTimeline?.slice(-1)[0];

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="p-4 rounded-2xl bg-[#090e18] border border-[#162032] flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-md">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
                Corrosion EIS, ASTM G59 Polarization &amp; Coating Delamination Engine
              </h3>
              <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-mono border border-amber-500/40">
                CPython 3.10+ Stern-Geary &amp; Brasher-Kingsbury
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Calculates R_p polarization resistance, corrosion rate (mm/yr &amp; mpy), and barrier coating water uptake φ(t)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {onSendToCNLS && simResult?.coatingNyquist?.[0] && (
            <button
              type="button"
              onClick={() => {
                const latestSpec = simResult.coatingNyquist.slice(-1)[0]?.spectrum || [];
                const points = latestSpec.map((pt: any) => ({
                  frequency: pt.frequency,
                  zReal: pt.zReal,
                  zImag: -pt.minusZImag,
                  minusZImag: pt.minusZImag,
                  zMag: Math.sqrt(pt.zReal * pt.zReal + pt.minusZImag * pt.minusZImag),
                  phaseDeg: (Math.atan2(-pt.minusZImag, pt.zReal) * 180) / Math.PI,
                }));
                onSendToCNLS(points, `Corrosion_Coating_${metalId.toUpperCase()}_Day${exposureDays}`);
              }}
              className="px-3.5 py-1.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm"
            >
              <Zap className="w-3.5 h-3.5 fill-current" />
              <span>Send Spectrum to CNLS Studio</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => runPythonSimulationNow()}
            disabled={isLoading}
            className="px-3 py-1.5 rounded-xl bg-[#050810] border border-[#1e2d46] hover:border-amber-500 text-slate-200 text-xs font-mono flex items-center gap-1.5 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-amber-400" : ""}`} />
            <span>Re-Solve</span>
          </button>
        </div>
      </div>

      {/* Grid: Controls & Output */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column Controls */}
        <div className="lg:col-span-4 space-y-4">
          <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-4">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block border-b border-[#162032] pb-2 flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-amber-400" />
              Alloy &amp; Electrochemical Parameters
            </span>

            {/* Metal Selection */}
            <div>
              <label className="text-[10px] text-slate-400 block mb-1">Substrate Alloy</label>
              <select aria-label="Substrate Alloy"
                value={metalId}
                onChange={(e) => {
                  const m = e.target.value;
                  setMetalId(m);
                  if (m === "steel-316l") { setEPit(0.45); setE0(0.08); setI0Corr(0.12); }
                  else if (m === "al-7075") { setEPit(-0.68); setE0(-1.66); setI0Corr(1.85); }
                  else if (m === "mg-az31b") { setEPit(-1.42); setE0(-2.37); setI0Corr(6.5); }
                  else if (m === "ti-6al4v") { setEPit(1.80); setE0(0.20); setI0Corr(0.01); }
                  else if (m === "steel-1018") { setEPit(-0.15); setE0(-0.44); setI0Corr(4.2); }
                }}
                className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
              >
                <option value="steel-316l">Stainless Steel 316L (Cr-Ni-Mo)</option>
                <option value="al-7075">Aerospace Aluminum 7075-T6 (Al-Zn-Mg)</option>
                <option value="mg-az31b">Magnesium AZ31B (Sacrificial/Active)</option>
                <option value="ti-6al4v">Titanium Ti-6Al-4V (Self-Healing TiO₂)</option>
                <option value="steel-1018">Carbon Steel AISI 1018 (Uniform Rust)</option>
              </select>
            </div>

            {/* Tafel Slopes */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Anodic Slope β_a (V/dec)</label>
                <input aria-label="Anodic Slope β_a (V/dec)"
                  type="number"
                  step="0.01"
                  value={betaA}
                  onChange={(e) => setBetaA(parseFloat(e.target.value) || 0.1)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Cathodic Slope β_c (V/dec)</label>
                <input aria-label="Cathodic Slope β_c (V/dec)"
                  type="number"
                  step="0.01"
                  value={betaC}
                  onChange={(e) => setBetaC(parseFloat(e.target.value) || 0.1)}
                  className="w-full bg-[#050810] border border-[#1e2d46] rounded-xl px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>

            {/* Baseline i_corr */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Corrosion Current i_corr</span>
                <span className="text-amber-400 font-bold font-mono">{i0Corr} µA/cm²</span>
              </div>
              <input aria-label="Corrosion Current i_corr"
                type="range"
                min={0.01}
                max={10.0}
                step={0.05}
                value={i0Corr}
                onChange={(e) => setI0Corr(parseFloat(e.target.value))}
                className="w-full accent-amber-500 h-1.5 bg-[#162032] rounded-lg cursor-pointer"
              />
            </div>

            {/* Exposure Days */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400 flex items-center gap-1">
                  <Droplets className="w-3 h-3 text-sky-400" />
                  Electrolyte Exposure
                </span>
                <span className="text-sky-300 font-bold font-mono">{exposureDays} days</span>
              </div>
              <input aria-label="Electrolyte Exposure"
                type="range"
                min={0}
                max={180}
                step={5}
                value={exposureDays}
                onChange={(e) => setExposureDays(parseInt(e.target.value))}
                className="w-full accent-sky-400 h-1.5 bg-[#162032] rounded-lg cursor-pointer"
              />
            </div>
          </div>

          {/* Quick Metrics Cards */}
          {simResult && (
            <div className="grid grid-cols-2 gap-2.5">
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-[9px] text-slate-400 block">Polarization Resistance (R_p)</span>
                <span className="text-base font-bold text-amber-400 font-mono">
                  {simResult.polarizationResistance_Rp_Ohm_cm2?.toLocaleString()} Ω·cm²
                </span>
                <span className="text-[9px] text-slate-500 block">ASTM G59</span>
              </div>
              <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032]">
                <span className="text-[9px] text-slate-400 block">Penetration Rate (CR)</span>
                <span className="text-base font-bold text-rose-400 font-mono">{simResult.corrosionRate_mm_yr} mm/yr</span>
                <span className="text-[9px] text-slate-500 block">({simResult.corrosionRate_mpy} mpy)</span>
              </div>
            </div>
          )}

          {/* Pitting Susceptibility Alert */}
          {simResult && (
            <div
              className={`p-3 rounded-xl border text-xs flex items-start gap-2.5 ${
                simResult.deltaE_pit_V < 0.15
                  ? "bg-rose-500/10 border-rose-500/30 text-rose-300"
                  : "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
              }`}
            >
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block uppercase text-[10px]">
                  Pitting Margin: ΔE_pit = {simResult.deltaE_pit_V} V
                </span>
                <p className="text-[11px] opacity-90 mt-0.5">
                  Assessment: <strong>{simResult.pittingAssessment}</strong>
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Visualization */}
        <div className="lg:col-span-8 p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-3">
          <div className="flex items-center justify-between border-b border-[#162032] pb-2 flex-wrap gap-2">
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setActiveSubTab("coating_nyquist")}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  activeSubTab === "coating_nyquist"
                    ? "bg-amber-500/20 border border-amber-400 text-amber-200"
                    : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                }`}
              >
                Coating Nyquist Impedance
              </button>
              <button
                type="button"
                onClick={() => setActiveSubTab("water_uptake")}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  activeSubTab === "water_uptake"
                    ? "bg-amber-500/20 border border-amber-400 text-amber-200"
                    : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                }`}
              >
                Water Uptake φ(t) (Brasher-Kingsbury)
              </button>
              <button
                type="button"
                onClick={() => setActiveSubTab("pore_decay")}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  activeSubTab === "pore_decay"
                    ? "bg-amber-500/20 border border-amber-400 text-amber-200"
                    : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                }`}
              >
                Pore Resistance Decay R_pore(t)
              </button>
              <button
                type="button"
                onClick={() => setActiveSubTab("python_code")}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  activeSubTab === "python_code"
                    ? "bg-amber-500/20 border border-amber-400 text-amber-200"
                    : "bg-[#050810] border border-[#162032] text-slate-400 hover:text-slate-200"
                }`}
              >
                Python Engine Code
              </button>
            </div>

            {simResult?.pythonDurationMs && (
              <span className="text-[10px] text-amber-400 font-mono">
                CPython solved in {simResult.pythonDurationMs} ms
              </span>
            )}
          </div>

          {/* Sub-Tab 1: Coating Nyquist */}
          {activeSubTab === "coating_nyquist" && (
            <div className="h-[360px] w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" />
                  <XAxis
                    dataKey="zReal"
                    type="number"
                    stroke="#64748b"
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    label={{ value: "Z' Real (Ω)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                  />
                  <YAxis
                    dataKey="minusZImag"
                    type="number"
                    stroke="#64748b"
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    label={{ value: "-Z'' Imag (Ω)", angle: -90, position: "insideLeft", offset: 10, fill: "#94a3b8", fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", borderRadius: "12px", fontSize: "11px", color: "#f8fafc" }}
                  />
                  <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "5px" }} />
                  {simResult?.coatingNyquist?.map((group: any, idx: number) => {
                    const colors = ["#10b981", "#38bdf8", "#f43f5e"];
                    const color = colors[idx % colors.length];
                    return (
                      <Line
                        key={idx}
                        data={group.spectrum}
                        type="monotone"
                        dataKey="minusZImag"
                        stroke={color}
                        strokeWidth={2.5}
                        dot={false}
                        name={`Day ${group.day} Exposure`}
                      />
                    );
                  })}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Sub-Tab 2: Water Uptake */}
          {activeSubTab === "water_uptake" && (
            <div className="h-[360px] w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={simResult?.coatingTimeline || []} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" />
                  <XAxis
                    dataKey="day"
                    stroke="#64748b"
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    label={{ value: "Exposure Time (Days)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                  />
                  <YAxis
                    stroke="#38bdf8"
                    domain={[0, 6]}
                    tick={{ fontSize: 10, fill: "#38bdf8" }}
                    label={{ value: "Water Uptake φ (Vol %)", angle: -90, position: "insideLeft", offset: 10, fill: "#38bdf8", fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", borderRadius: "12px", fontSize: "11px", color: "#f8fafc" }}
                  />
                  <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "5px" }} />
                  <Line type="monotone" dataKey="waterUptakePct" stroke="#38bdf8" strokeWidth={2.5} dot={{ r: 3 }} name="Water Uptake φ (%)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Sub-Tab 3: Pore Resistance Decay */}
          {activeSubTab === "pore_decay" && (
            <div className="h-[360px] w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={simResult?.coatingTimeline || []} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" />
                  <XAxis
                    dataKey="day"
                    stroke="#64748b"
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    label={{ value: "Exposure Time (Days)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }}
                  />
                  <YAxis
                    stroke="#f43f5e"
                    tick={{ fontSize: 10, fill: "#f43f5e" }}
                    label={{ value: "Pore Resistance R_pore (kΩ·cm²)", angle: -90, position: "insideLeft", offset: 10, fill: "#f43f5e", fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#090e18", borderColor: "#1e2d46", borderRadius: "12px", fontSize: "11px", color: "#f8fafc" }}
                  />
                  <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "5px" }} />
                  <Line type="monotone" dataKey="poreResistance_kOhm_cm2" stroke="#f43f5e" strokeWidth={2.5} dot={{ r: 3 }} name="R_pore (kΩ·cm²)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Sub-Tab 4: Python Code */}
          {activeSubTab === "python_code" && (
            <div className="h-[360px] overflow-y-auto bg-[#050810] border border-[#162032] rounded-xl p-4 font-mono text-[11px] text-slate-300 leading-relaxed space-y-2">
              <div className="text-amber-400 font-bold"># Python 3.10+ ASTM G59 &amp; Brasher-Kingsbury Solver</div>
              <pre className="text-slate-300 whitespace-pre-wrap">
{`import math

def simulate_corrosion_kinetics(beta_a=${betaA}, beta_c=${betaC}, i0_corr_ua=${i0Corr}, days=${exposureDays}):
    # Stern-Geary Constant B (V)
    b_val = (beta_a * beta_c) / (2.303 * (beta_a + beta_c))
    
    # Polarization Resistance R_p (Ohm*cm2)
    i_corr_a = i0_corr_ua * 1e-6
    r_p = b_val / i_corr_a
    
    # Brasher-Kingsbury Water Uptake
    # phi = log10(C_t / C_0) / log10(80)
    phi_water = 4.8 * (1.0 - math.exp(-days / 12.0))
    return {"b_val": b_val, "r_p": r_p, "phi_water": phi_water}
`}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
