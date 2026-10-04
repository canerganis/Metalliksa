import React, { useState } from 'react';
import { Layers, Activity, AlertTriangle, CheckCircle, ShieldCheck } from 'lucide-react';
import { pythonComputationService } from '../services/pythonComputationService';

export const IndustrialCertificationLab: React.FC = () => {
  const [power, setPower] = useState<number>(300);
  const [speed, setSpeed] = useState<number>(1000);
  const [alloy, setAlloy] = useState<string>('IN718');
  
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<any>(null);

  const handleSimulate = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/python/lpbf-industrial-fatigue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alloy, power_W: power, speed_mms: speed, layer_um: 30.0, hatch_um: 100.0 })
      });
      const data = await response.json();
      setResult(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  return (
    <div className="flex flex-col gap-6 p-6 max-w-5xl mx-auto h-full overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
        <h2 className="text-2xl font-bold text-white mb-2 flex items-center gap-3">
          <ShieldCheck className="text-emerald-400 w-8 h-8" />
          Industrial Certification & AI Fatigue Life (Phases 9 & 10)
        </h2>
        <p className="text-slate-400 mb-4">
          Predict manufacturing quality and fatigue limits in milliseconds using the Phase 9 meta-model and Phase 10 Gumbel extreme-value and Murakami methods.
        </p>
        <div className="mb-6 flex items-center gap-2">
          <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 text-xs font-bold rounded-full border border-emerald-500/30">
            Powered by Phase 15 Hybrid Dataset (1296 Dense Physical Points)
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-700/50">
            <label className="block text-sm text-slate-400 mb-2">Laser Power (W)</label>
            <input aria-label="Laser Power (W)" 
              type="range" min="50" max="600" value={power} 
              onChange={(e) => setPower(Number(e.target.value))}
              className="w-full accent-blue-500"
            />
            <div className="text-right text-white font-mono mt-1">{power} W</div>
          </div>
          
          <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-700/50">
            <label className="block text-sm text-slate-400 mb-2">Scan Speed (mm/s)</label>
            <input aria-label="Scan Speed (mm/s)" 
              type="range" min="200" max="2500" value={speed} 
              onChange={(e) => setSpeed(Number(e.target.value))}
              className="w-full accent-blue-500"
            />
            <div className="text-right text-white font-mono mt-1">{speed} mm/s</div>
          </div>

          <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-700/50">
            <label className="block text-sm text-slate-400 mb-2">Alloy</label>
            <select aria-label="Alloy" 
              value={alloy} onChange={(e) => setAlloy(e.target.value)}
              className="w-full bg-slate-900 text-white border border-slate-700 rounded-md p-2"
            >
              <option value="IN718">Inconel 718</option>
              <option value="Inconel 625">Inconel 625</option>
              <option value="Ti6Al4V">Ti-6Al-4V</option>
              <option value="AlSi10Mg">AlSi10Mg</option>
              <option value="316L SS">316L Stainless Steel</option>
              <option value="CoCrMo">CoCrMo (Cobalt-Chrome)</option>
              <option value="Hastelloy X">Hastelloy X</option>
            </select>
          </div>
        </div>

        <button 
          onClick={handleSimulate}
          disabled={loading}
          className="w-full py-4 bg-gradient-to-r from-blue-600 to-emerald-600 hover:from-blue-500 hover:to-emerald-500 text-white font-bold rounded-lg shadow-lg transition-all flex items-center justify-center gap-2"
        >
          {loading ? <Activity className="animate-spin w-5 h-5" /> : <Layers className="w-5 h-5" />}
          {loading ? 'AI is calculating...' : 'Run Certification Analysis'}
        </button>
      </div>

      {result && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* AI Meltpool */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
            <h3 className="text-lg font-bold text-blue-400 mb-4 border-b border-slate-800 pb-2">AI Melt Pool Estimate</h3>
            <div className="space-y-4">
              <div>
                <div className="text-sm text-slate-400">Mean Depth</div>
                <div className="text-2xl text-white font-mono">{result.AI_Meltpool?.Mean_Depth_um} µm</div>
              </div>
              <div>
                <div className="text-sm text-slate-400">Uncertainty (Standard Deviation)</div>
                <div className="text-xl text-yellow-400 font-mono">±{result.AI_Meltpool?.Uncertainty_Std_um} µm</div>
              </div>
            </div>
          </div>

          {/* Gumbel Statistics */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
            <h3 className="text-lg font-bold text-orange-400 mb-4 border-b border-slate-800 pb-2">Gumbel Probabilities</h3>
            <div className="space-y-4">
              <div>
                <div className="text-sm text-slate-400">Maximum Simulated Pore</div>
                <div className="text-xl text-white font-mono">{result.Defect_Simulation?.Max_Simulated_Defect_um} µm</div>
              </div>
              <div>
                <div className="text-sm text-slate-400">Characteristic Maximum Critical Defect</div>
                <div className="text-2xl text-red-400 font-mono font-bold flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5" />
                  {result.Defect_Simulation?.Gumbel_Predicted_Largest_Defect_um} µm
                </div>
              </div>
            </div>
          </div>

          {/* Fatigue Limit */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
            <h3 className="text-lg font-bold text-emerald-400 mb-4 border-b border-slate-800 pb-2">Fatigue Limit</h3>
            <div className="space-y-4">
              <div>
                <div className="text-sm text-slate-400">Expected Fatigue Limit</div>
                <div className="text-xl text-white font-mono">{result.Certification_Limits?.Expected_Fatigue_Limit_MPa} MPa</div>
              </div>
              <div>
                <div className="text-sm text-slate-400">99% Survival Design Limit</div>
                <div className="text-3xl text-emerald-400 font-mono font-bold flex items-center gap-2">
                  <CheckCircle className="w-6 h-6" />
                  {result.Certification_Limits?.['99_Percent_Survival_Design_Limit_MPa']} MPa
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
