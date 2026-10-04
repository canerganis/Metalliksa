import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useEffect } from "react";
import {
  Activity,
  Cpu,
  RefreshCw,
  Settings,
  Target,
  Trophy,
  AlertTriangle
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend
} from "recharts";
import { pythonComputationService, PythonBayesianOptimizationResult } from "../services/pythonComputationService";
import { useMaterialSpecimenStore } from "../store/useMaterialSpecimenStore";

export const LpbfBayesianOptimizerLab: React.FC = () => {
  const specimen = useMaterialSpecimenStore(s => s.activeSpecimen);
  
  const [bounds, setBounds] = useState({
    laserPower_W: [100.0, 500.0],
    scanSpeed_mms: [200.0, 2000.0],
    hatch_um: [60.0, 200.0],
    layer_um: [20.0, 80.0]
  });
  
  const [nIter, setNIter] = useState(20);
  const [nWarmup, setNWarmup] = useState(5);
  
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<PythonBayesianOptimizationResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleOptimize = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = {
        alloyId: specimen.id,
        paramBounds: bounds,
        nIterations: nIter,
        nWarmup: nWarmup,
        seed: 42
      };
      const res = await pythonComputationService.runLpbfBayesianOptimization(data);
      if (!res.success) throw new Error("Optimization failed.");
      setResult(res);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to run optimization.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Target className="w-5 h-5 text-sky-400" />
            Bayesian Process Window Optimization
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Autonomous closed-loop search for optimal LPBF parameters balancing productivity and defect risk.
          </p>
        </div>
        <button
          onClick={handleOptimize}
          disabled={isLoading}
          className="flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium hover:bg-sky-500 disabled:opacity-50"
        >
          {isLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
          Run Optimization
        </button>
      </div>

      {errorMsg && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <p>{errorMsg}</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <Settings className="w-4 h-4 text-slate-400" />
            Parameter Bounds
          </h3>
          <div className="space-y-4 text-sm">
            <div>
              <label className="mb-1 block text-slate-400">Laser Power (W)</label>
              <div className="flex gap-2">
                <input aria-label="Laser Power (W) minimum" type="number" value={bounds.laserPower_W[0]} onChange={e => setBounds(b => ({...b, laserPower_W: [+e.target.value, b.laserPower_W[1]]}))} className="aero-input w-full" />
                <span className="text-slate-500 self-center">-</span>
                <input aria-label="Laser Power (W) maximum" type="number" value={bounds.laserPower_W[1]} onChange={e => setBounds(b => ({...b, laserPower_W: [b.laserPower_W[0], +e.target.value]}))} className="aero-input w-full" />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-slate-400">Scan Speed (mm/s)</label>
              <div className="flex gap-2">
                <input aria-label="Scan Speed (mm/s) minimum" type="number" value={bounds.scanSpeed_mms[0]} onChange={e => setBounds(b => ({...b, scanSpeed_mms: [+e.target.value, b.scanSpeed_mms[1]]}))} className="aero-input w-full" />
                <span className="text-slate-500 self-center">-</span>
                <input aria-label="Scan Speed (mm/s) maximum" type="number" value={bounds.scanSpeed_mms[1]} onChange={e => setBounds(b => ({...b, scanSpeed_mms: [b.scanSpeed_mms[0], +e.target.value]}))} className="aero-input w-full" />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-slate-400">Hatch Spacing (µm)</label>
              <div className="flex gap-2">
                <input aria-label="Hatch Spacing (µm) minimum" type="number" value={bounds.hatch_um[0]} onChange={e => setBounds(b => ({...b, hatch_um: [+e.target.value, b.hatch_um[1]]}))} className="aero-input w-full" />
                <span className="text-slate-500 self-center">-</span>
                <input aria-label="Hatch Spacing (µm) maximum" type="number" value={bounds.hatch_um[1]} onChange={e => setBounds(b => ({...b, hatch_um: [b.hatch_um[0], +e.target.value]}))} className="aero-input w-full" />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-slate-400">Layer Thickness (µm)</label>
              <div className="flex gap-2">
                <input aria-label="Layer Thickness (µm) minimum" type="number" value={bounds.layer_um[0]} onChange={e => setBounds(b => ({...b, layer_um: [+e.target.value, b.layer_um[1]]}))} className="aero-input w-full" />
                <span className="text-slate-500 self-center">-</span>
                <input aria-label="Layer Thickness (µm) maximum" type="number" value={bounds.layer_um[1]} onChange={e => setBounds(b => ({...b, layer_um: [b.layer_um[0], +e.target.value]}))} className="aero-input w-full" />
              </div>
            </div>
            
            <div className="pt-2 border-t border-slate-800">
              <label className="mb-1 block text-slate-400">Iterations (Total / Warmup)</label>
              <div className="flex gap-2">
                <input aria-label="Iterations (Total)" type="number" value={nIter} onChange={e => setNIter(+e.target.value)} className="aero-input w-full" />
                <span className="text-slate-500 self-center">/</span>
                <input aria-label="Iterations (Warmup)" type="number" value={nWarmup} onChange={e => setNWarmup(+e.target.value)} className="aero-input w-full" />
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-2 space-y-6">
          {result ? (
            <>
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-5">
                <h3 className="text-sm font-semibold text-emerald-300 mb-4 flex items-center gap-2">
                  <Trophy className="w-4 h-4" />
                  Best Discovered Parameters
                </h3>
                {result.bestParams ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="rounded-lg bg-slate-900 p-3 text-center border border-slate-800">
                      <p className="text-xs text-slate-400 mb-1">Laser Power</p>
                      <p className="text-lg font-mono text-emerald-200">{result.bestParams.laserPower_W} <span className="text-xs text-slate-500">W</span></p>
                    </div>
                    <div className="rounded-lg bg-slate-900 p-3 text-center border border-slate-800">
                      <p className="text-xs text-slate-400 mb-1">Scan Speed</p>
                      <p className="text-lg font-mono text-emerald-200">{result.bestParams.scanSpeed_mms} <span className="text-xs text-slate-500">mm/s</span></p>
                    </div>
                    <div className="rounded-lg bg-slate-900 p-3 text-center border border-slate-800">
                      <p className="text-xs text-slate-400 mb-1">Hatch</p>
                      <p className="text-lg font-mono text-emerald-200">{result.bestParams.hatch_um} <span className="text-xs text-slate-500">µm</span></p>
                    </div>
                    <div className="rounded-lg bg-slate-900 p-3 text-center border border-slate-800">
                      <p className="text-xs text-slate-400 mb-1">Layer</p>
                      <p className="text-lg font-mono text-emerald-200">{result.bestParams.layer_um} <span className="text-xs text-slate-500">µm</span></p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">No valid parameters found.</p>
                )}
                <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
                  <p>Peak Score: <span className="text-emerald-300 font-mono">{result.bestScore}</span></p>
                  <p>Time: {result.elapsedMs} ms</p>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
                <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-sky-400" />
                  Optimization Trajectory
                </h3>
                <div className="h-64 w-full">
                  <ResponsiveContainer>
                    <LineChart data={result.iterations}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="iteration" stroke="#94a3b8" fontSize={12} tickMargin={10} />
                      <YAxis stroke="#94a3b8" fontSize={12} tickMargin={10} domain={['auto', 'auto']} />
                      <Tooltip
                        contentStyle={{ backgroundColor: "#0f172a", borderColor: "#1e293b", fontSize: "12px", color: "#e2e8f0" }}
                        formatter={(value: number) => [value, "Score"]}
                        labelFormatter={(label) => `Iteration ${label}`}
                      />
                      <Line type="monotone" dataKey="score" stroke="#38bdf8" strokeWidth={2} dot={{ fill: '#38bdf8', r: 3 }} activeDot={{ r: 5, fill: '#0ea5e9' }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </>
          ) : (
            <div className="h-full min-h-[300px] flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/20 text-slate-500">
              <Cpu className="w-8 h-8 mb-3 opacity-50" />
              <p>Configure bounds and run optimization</p>
              <p className="text-xs mt-1 opacity-75">Bayesian surrogate model will explore the process window</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
