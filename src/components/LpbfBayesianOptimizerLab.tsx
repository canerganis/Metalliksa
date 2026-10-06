import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useEffect } from "react";
import {
  Activity,
  Cpu,
  RefreshCw,
  Settings,
  Target,
  ListOrdered,
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
import {
  resolveOptimizerAlloy,
  OPTIMIZER_MAX_ITERATIONS,
  OPTIMIZER_DEFAULT_BEAM_DIAMETER_UM,
  OPTIMIZER_DEFAULT_PREHEAT_C,
} from "../utils/lpbfOptimizerAlloy";

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
  // Raw strings so an emptied input is invalid instead of silently becoming 0.
  const [beamText, setBeamText] = useState(String(OPTIMIZER_DEFAULT_BEAM_DIAMETER_UM));
  const [preheatText, setPreheatText] = useState(String(OPTIMIZER_DEFAULT_PREHEAT_C));
  const beamDiameter = beamText.trim() === "" ? NaN : Number(beamText);
  const preheat = preheatText.trim() === "" ? NaN : Number(preheatText);

  const alloy = resolveOptimizerAlloy(specimen.name);
  const iterError =
    !Number.isInteger(nIter) || nIter < 1 || nIter > OPTIMIZER_MAX_ITERATIONS
      ? `Total iterations must be an integer between 1 and ${OPTIMIZER_MAX_ITERATIONS}.`
      : !Number.isInteger(nWarmup) || nWarmup < 1
        ? "Warmup iterations must be an integer of at least 1."
        : null;
  const processError = !(Number.isFinite(beamDiameter) && beamDiameter > 0)
    ? "Beam diameter must be a positive number."
    : !(Number.isFinite(preheat) && preheat >= 0)
      ? "Preheat must be a number, 0 C or higher."
      : null;
  const allRandom = Number.isInteger(nIter) && Number.isInteger(nWarmup) && nWarmup >= nIter;
  const blockReason = alloy.ok ? iterError ?? processError : alloy.reason;
  
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<PythonBayesianOptimizationResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleOptimize = async () => {
    if (!alloy.ok || blockReason) return;
    setIsLoading(true);
    setResult(null);
    setErrorMsg(null);
    try {
      const data = {
        alloyId: alloy.alloyKey,
        paramBounds: bounds,
        nIterations: nIter,
        nWarmup: nWarmup,
        beamDiameter_um: beamDiameter,
        preheatTemp_C: preheat,
        seed: 42
      };
      const res = await pythonComputationService.runLpbfBayesianOptimization(data);
      if (!res.success) throw new Error(res.error || "Optimization failed (no reason returned by the backend).");
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
            Process Parameter Search
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Expected-improvement search over power, speed, hatch and layer thickness. Each candidate is scored by the screening thermal model: verdict score (printable 1, risky 0.5, do-not-print 0, inconclusive/geometry-unresolved 0) multiplied by the normalised v·h (v·h / (v_max·h_max)). This is a screening score, not a validated defect prediction or process window.
          </p>
        </div>
        <button
          onClick={handleOptimize}
          disabled={isLoading || blockReason !== null}
          title={blockReason ?? undefined}
          className="flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium hover:bg-sky-500 disabled:opacity-50"
        >
          {isLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
          Run Optimization
        </button>
      </div>

      <p className="text-xs text-slate-400" data-testid="optimizer-alloy">
        Alloy:{" "}
        {alloy.ok ? (
          <span className="font-mono text-slate-200">{alloy.alloyKey}</span>
        ) : (
          <span className="text-amber-300">unavailable - {alloy.reason}</span>
        )}{" "}
        (from active material "{specimen.name}"). The solver uses its built-in screening properties for this alloy; the active material's own composition and properties are not sent.
      </p>
      {allRandom && alloy.ok && !iterError && (
        <p className="text-xs text-amber-300" data-testid="optimizer-allrandom">Warmup is not smaller than total iterations: every candidate will be a random sample and no surrogate/expected-improvement step will run.</p>
      )}
      {blockReason && alloy.ok && <p className="text-xs text-amber-300">{blockReason}</p>}

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
              <label className="mb-1 block text-slate-400">Fixed process inputs (not searched)</label>
              <div className="flex gap-2">
                <input aria-label="Beam diameter (µm)" type="number" min={1} value={beamText} onChange={e => setBeamText(e.target.value)} className="aero-input w-full" />
                <input aria-label="Preheat temperature (°C)" type="number" min={0} value={preheatText} onChange={e => setPreheatText(e.target.value)} className="aero-input w-full" />
              </div>
              <p className="mt-1 text-xs text-slate-500">Beam diameter (µm) / preheat (°C); defaults {OPTIMIZER_DEFAULT_BEAM_DIAMETER_UM} / {OPTIMIZER_DEFAULT_PREHEAT_C}. Laser wavelength fixed at IR 1064 nm.</p>
            </div>

            <div className="pt-2 border-t border-slate-800">
              <label className="mb-1 block text-slate-400">Iterations (Total / Warmup)</label>
              <div className="flex gap-2">
                <input aria-label="Iterations (Total)" type="number" min={1} max={OPTIMIZER_MAX_ITERATIONS} value={nIter} onChange={e => setNIter(+e.target.value)} className="aero-input w-full" />
                <span className="text-slate-500 self-center">/</span>
                <input aria-label="Iterations (Warmup)" type="number" min={1} max={Number.isInteger(nIter) && nIter >= 1 ? nIter : OPTIMIZER_MAX_ITERATIONS} value={nWarmup} onChange={e => setNWarmup(+e.target.value)} className="aero-input w-full" />
              </div>
              <p className="mt-1 text-xs text-slate-500">Maximum {OPTIMIZER_MAX_ITERATIONS} total iterations; larger values are rejected, not clamped.</p>
            </div>
          </div>
        </div>

        <div className="lg:col-span-2 space-y-6">
          {result ? (
            <>
              <div className={`rounded-xl border p-5 ${result.bestParams ? "border-emerald-500/30 bg-emerald-950/20" : "border-amber-500/30 bg-amber-950/20"}`}>
                <h3 className={`text-sm font-semibold mb-4 flex items-center gap-2 ${result.bestParams ? "text-emerald-300" : "text-amber-300"}`}>
                  <ListOrdered className="w-4 h-4" />
                  Highest screening score among evaluated candidates
                </h3>
                {result.bestParams ? (
                  <>
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
                    <p className="mt-3 text-xs text-slate-400" data-testid="optimizer-best-verdict">Screening verdict of this candidate: <span className="font-mono text-slate-200">{result.bestVerdict ?? "not returned"}</span></p>
                  </>
                ) : (
                  <p className="text-sm text-amber-200" data-testid="optimizer-no-positive">
                    No candidate scored above 0 (every evaluated candidate was do-not-print or inconclusive), so no parameter set is presented.
                  </p>
                )}
                <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
                  <p>Peak Score: <span className="font-mono text-slate-200">{result.bestScore}</span></p>
                  <p>Time: {result.elapsedMs} ms</p>
                </div>
                <p className="mt-2 text-xs text-slate-400">Screening score from a thermal model, not a validated process window or experimental optimum.</p>
                <p className="mt-2 text-xs text-slate-400" data-testid="optimizer-resolved">
                  Resolved alloy: <span className="font-mono">{result.alloyId}</span> · beam {result.beamDiameter_um ?? "not returned"} µm · preheat {result.preheatTemp_C ?? "not returned"} °C · {result.nIterations} iterations ({result.nWarmup ?? "not returned"} warmup, {result.surrogateSteps ?? "not returned"} surrogate steps) · {result.converged ? "last 5 scores within 1e-3" : "last 5 scores not within 1e-3"}
                </p>
                {result.surrogateSteps === 0 && <p className="text-xs text-amber-300">All candidates were random samples; no expected-improvement step ran.</p>}
                <p className="text-xs text-slate-400" data-testid="optimizer-inconclusive">
                  Inconclusive (geometry unresolved, scored 0): <span className="font-mono">{result.nInconclusive ?? "not returned"}</span> of {result.nIterations} iterations
                </p>
                {result.objective && <p className="text-xs text-slate-500">Objective: {result.objective}</p>}
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
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
                <h3 className="text-sm font-semibold text-slate-200 mb-3">Per-iteration verdicts</h3>
                <div className="max-h-64 overflow-auto">
                  <table className="w-full text-xs text-slate-300">
                    <caption className="sr-only">Per-iteration parameters, screening verdict and score</caption>
                    <thead className="text-slate-500 text-left">
                      <tr><th scope="col">#</th><th scope="col">P (W)</th><th scope="col">v (mm/s)</th><th scope="col">h (µm)</th><th scope="col">t (µm)</th><th scope="col">Verdict</th><th scope="col">Score</th></tr>
                    </thead>
                    <tbody>
                      {result.iterations.map(it => (
                        <tr key={it.iteration} className={`border-t border-slate-800 ${it.verdict === "inconclusive" ? "bg-amber-500/10 text-amber-200" : ""}`}>
                          <td>{it.iteration}</td><td>{it.params.laserPower_W}</td><td>{it.params.scanSpeed_mms}</td>
                          <td>{it.params.hatch_um}</td><td>{it.params.layer_um}</td>
                          <td>{it.verdict}</td><td className="font-mono">{it.score}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <div className="h-full min-h-[300px] flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/20 text-slate-500">
              <Cpu className="w-8 h-8 mb-3 opacity-50" />
              <p>Configure bounds and run optimization</p>
              <p className="text-xs mt-1 opacity-75">After the warmup samples, a Gaussian-process surrogate with expected improvement proposes candidates inside the bounds above</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
