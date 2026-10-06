import React, { useState, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { pythonComputationService } from '../services/pythonComputationService';

const AVAILABLE_ALLOYS = ["Ti-6Al-4V", "316L SS", "Inconel 718", "AlSi10Mg"];

/** Paris-law life label without any safety verdict. */
export function parisLifeLabel(paris: { status: string; cycles_to_failure: number; final_crack_size_um?: number }): string {
  if (paris.status === 'non_propagating') return 'ΔK < ΔK_th (no growth computed)';
  if (paris.status === 'runout') {
    // Closed-form Paris life: a runout only means the cycle limit was reached before K_max = K_IC.
    const size = typeof paris.final_crack_size_um === 'number' ? `; crack size ${paris.final_crack_size_um} µm` : '';
    return `No fracture when integration stopped at N = ${paris.cycles_to_failure.toLocaleString('en-US')} cycles (cycle limit reached${size})`;
  }
  return `${paris.cycles_to_failure.toLocaleString('en-US')} cycles`;
}

export interface FatigueRequestInputs {
  stressAmplitude_MPa: number;
}

/** Attach the inputs a result was computed from, so later slider moves cannot be mixed with it. */
export function withRequestInputs<T extends object>(result: T, inputs: FatigueRequestInputs): T & { requestInputs: FatigueRequestInputs } {
  return { ...result, requestInputs: { ...inputs } };
}

/**
 * The fatigue-limit criterion (σ_a vs corrected limit) and the Paris threshold criterion
 * (ΔK vs ΔK_th) are independent; return a message when they point in opposite directions.
 * Uses the σ_a the result was computed with (result.requestInputs), never the live slider.
 */
export function fatigueCriteriaDisagreement(result: any): string | null {
  const limit = result?.fatigue_limit?.fatigue_limit_corrected_MPa;
  const status = result?.paris_crack_growth?.status;
  const stressAmplitude_MPa = result?.requestInputs?.stressAmplitude_MPa;
  if (typeof limit !== 'number' || !status || typeof stressAmplitude_MPa !== 'number') return null;
  const aboveLimit = stressAmplitude_MPa > limit;
  const grows = status !== 'non_propagating';
  if (aboveLimit && !grows) {
    return `σ_a = ${stressAmplitude_MPa} MPa exceeds the fatigue limit ${limit} MPa, but ΔK is below ΔK_th so the Paris model predicts no growth.`;
  }
  if (!aboveLimit && grows) {
    return `σ_a = ${stressAmplitude_MPa} MPa is below the fatigue limit ${limit} MPa, but ΔK exceeds ΔK_th so the Paris model predicts crack growth.`;
  }
  return null;
}

export const MurakamiFatigueLab: React.FC = () => {
  const [selectedAlloy, setSelectedAlloy] = useState("Ti-6Al-4V");
  const [sqrtArea, setSqrtArea] = useState(45);
  const [location, setLocation] = useState<"surface" | "sub-surface" | "internal">("internal");
  const [stressRatio, setStressRatio] = useState(-1.0);
  const [stressAmplitude, setStressAmplitude] = useState(240);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCompute = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await pythonComputationService.computeMurakamiFatigue({
        alloyName: selectedAlloy,
        sqrtArea_um: sqrtArea,
        location,
        stressRatio_R: stressRatio,
        stressAmplitude_MPa: stressAmplitude,
      });
      setResult(withRequestInputs(res, { stressAmplitude_MPa: stressAmplitude }));
    } catch (err: any) {
      setResult(null);
      setError(err.message || 'Fatigue computation failed');
    } finally {
      setIsLoading(false);
    }
  }, [selectedAlloy, sqrtArea, location, stressRatio, stressAmplitude]);

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-200">
      <div className="flex items-center justify-between p-4 bg-gray-800 border-b border-gray-700">
        <div>
          <h2 className="text-lg font-bold text-white">Defect Fatigue & Crack Growth</h2>
          <p className="text-sm text-gray-400">Phase 13: Kitagawa-Takahashi Diagram, El-Haddad Short Cracks & Paris Law Life</p>
          <p data-testid="murakami-not-statement" className="text-xs text-amber-300">Steel-derived formula; surface roughness not modelled. R enters only through an empirical power-law factor on the fatigue limit, the peak stress used for the critical crack size and the ASTM E647 range convention (ΔK = K_max for R ≤ 0); the Paris growth rate has no further R (mean-stress) correction. ΔK uses Murakami's √area factor (Y = 0.65 surface/sub-surface, 0.5 internal) from the defect size; a sub-surface defect is treated as a surface defect of the same √area (no ligament / virtual-area input).</p>
          <p data-testid="murakami-unsourced-constants" className="text-xs text-amber-300">Unsourced constants: per-alloy hardness, smooth fatigue limit, ΔK_th, K_IC and Paris C, m are internal table values (alloy_registry fatigue_fracture domain) with no literature citation.</p>
        </div>
        <button
          onClick={handleCompute}
          disabled={isLoading}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-medium disabled:opacity-50"
        >
          {isLoading ? 'Computing Fracture...' : 'Calculate Fatigue Limit'}
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sol Panel: Parametreler */}
        <div className="w-84 p-4 border-r border-gray-700 overflow-y-auto space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase mb-1">Alloy System</label>
            <select aria-label="Alloy System"
              value={selectedAlloy}
              onChange={e => setSelectedAlloy(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-xs text-white"
            >
              {AVAILABLE_ALLOYS.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase mb-1">Defect Location</label>
            <div className="grid grid-cols-3 gap-1">
              {(["surface", "sub-surface", "internal"] as const).map(loc => (
                <button
                  key={loc}
                  type="button"
                  onClick={() => setLocation(loc)}
                  className={`py-1.5 text-[11px] capitalize rounded border ${location === loc ? 'bg-emerald-600 border-emerald-500 text-white font-semibold' : 'bg-gray-800 border-gray-700 text-gray-400'}`}
                >
                  {loc}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3 pt-2 border-t border-gray-800">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Defect & Stress Specs</h3>

            <label className="block text-xs">
              <span className="text-gray-400">Defect Size (√area µm)</span>
              <input
                type="range" min={1} max={250} step={2}
                value={sqrtArea} onChange={e => setSqrtArea(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-white text-xs">{sqrtArea} µm</div>
            </label>

            <label className="block text-xs">
              <span className="text-gray-400">Stress Ratio (R = σ_min / σ_max)</span>
              <div className="flex gap-2 mt-1">
                {[-1.0, 0.0, 0.1].map(r => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setStressRatio(r)}
                    className={`flex-1 py-1 text-xs rounded border ${stressRatio === r ? 'bg-blue-600 border-blue-500 text-white' : 'bg-gray-800 border-gray-700 text-gray-400'}`}
                  >
                    R = {r}
                  </button>
                ))}
              </div>
            </label>

            <label className="block text-xs">
              <span className="text-gray-400">Cyclic Stress Amplitude (σ_a MPa)</span>
              <input
                type="range" min={50} max={600} step={10}
                value={stressAmplitude} onChange={e => setStressAmplitude(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-white text-xs">{stressAmplitude} MPa</div>
            </label>
          </div>

          <div className="p-3 rounded bg-emerald-950/40 border border-emerald-800 text-[11px] text-emerald-300">
            <strong>El-Haddad Correction:</strong> Reconciles LEFM (Linear Elastic Fracture Mechanics) with small fatigue defects; prevents infinite stress predictions as pore size approaches zero.
          </div>
        </div>

        {/* Sağ Panel: Grafikler & Çıktılar */}
        <div className="flex-1 p-6 overflow-y-auto bg-gray-950">
          {error && (
            <div className="mb-4 p-4 bg-red-900/40 border border-red-700 text-red-200 rounded text-sm">
              {error}
            </div>
          )}

          {!result && !isLoading && !error && (
            <div className="flex h-full items-center justify-center text-gray-500 text-sm">
              Configure defect geometry and click 'Calculate Fatigue Limit' to evaluate Kitagawa-Takahashi thresholds.
            </div>
          )}

          {result && (
            <div className="space-y-6">
              {/* Metrik Rozetleri */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Fatigue Limit (R={result.fatigue_limit.stress_ratio_R})</span>
                  <span className="text-lg font-mono font-bold text-emerald-400">
                    {result.fatigue_limit.fatigue_limit_corrected_MPa} MPa
                  </span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">El-Haddad a₀</span>
                  <span className="text-lg font-mono font-bold text-white">
                    {result.fatigue_limit.el_haddad_a0_um} µm
                  </span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Hardness (HV)</span>
                  <span className="text-lg font-mono font-bold text-blue-400">
                    {result.fatigue_limit.hardness_HV} HV
                  </span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Paris Life (Cycles)</span>
                  <span className={`text-lg font-mono font-bold ${result.paris_crack_growth.status === 'fractured' ? 'text-amber-400' : 'text-gray-200'}`}>
                    {parisLifeLabel(result.paris_crack_growth)}
                  </span>
                </div>
              </div>

              {(() => {
                const disagreement = fatigueCriteriaDisagreement(result);
                return disagreement ? (
                  <div role="alert" data-testid="murakami-criteria-disagree" className="p-3 bg-amber-900/30 border border-amber-700 rounded text-xs text-amber-200">
                    Criteria disagree: {disagreement}
                  </div>
                ) : null;
              })()}

              {/* Kitagawa-Takahashi Diyagramı */}
              <div className="bg-gray-800 border border-gray-700 rounded p-4 h-80 flex flex-col">
                <h3 className="text-sm font-semibold text-white mb-2">Kitagawa-Takahashi Diagram (Defect Size vs. Fatigue Limit)</h3>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={result.kitagawa_takahashi_curve}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="defect_sqrt_area_um" stroke="#9ca3af" label={{ value: '√area (µm)', position: 'insideBottomRight', offset: -5, fill: '#9ca3af' }} />
                    <YAxis stroke="#9ca3af" label={{ value: 'Fatigue Limit (MPa)', angle: -90, position: 'insideLeft', fill: '#9ca3af' }} />
                    <Tooltip contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#f3f4f6' }} />
                    <ReferenceLine x={result.fatigue_limit.sqrt_area_um} stroke="#ef4444" strokeDasharray="3 3" label={{ value: `Selected: ${result.fatigue_limit.sqrt_area_um} µm`, fill: '#ef4444' }} />
                    <Line type="monotone" dataKey="fatigue_limit_MPa" stroke="#10b981" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Paris Çatlak İlerlemesi */}
              <div className="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 className="text-sm font-semibold text-white mb-2">Paris-Erdogan Crack Propagation Analysis</h3>
                <p className="text-xs text-gray-400 mb-3">
                  Status: <strong className="text-white capitalize">{result.paris_crack_growth.status}</strong> | Initial Flaw: <strong>{result.paris_crack_growth.initial_crack_size_um} µm</strong> | Final Size: <strong>{result.paris_crack_growth.final_crack_size_um} µm</strong>
                </p>
                {result.paris_crack_growth.status === 'non_propagating' ? (
                  <div className="p-3 bg-gray-900 border border-gray-700 rounded text-xs text-gray-300">
                    The initial defect gives a stress intensity range (ΔK) below the tabulated threshold ΔK_th, so the Paris integration does not start. This is a screening result with unsourced constants, not a life guarantee.
                  </div>
                ) : result.paris_crack_growth.status === 'runout' ? (
                  <div className="p-3 bg-gray-900 border border-gray-700 rounded text-xs text-gray-300">
                    ΔK exceeds threshold ΔK_th, but the critical crack size was not reached: {parisLifeLabel(result.paris_crack_growth)}. Not a life guarantee.
                  </div>
                ) : (
                  <div className="p-3 bg-amber-950/30 border border-amber-800 rounded text-xs text-amber-300">
                    ΔK exceeds threshold ΔK_th. The Paris integration reaches the critical crack size (K_max = K_IC) at <strong>{result.paris_crack_growth.cycles_to_failure.toLocaleString('en-US')} cycles</strong> (unsourced constants).
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
