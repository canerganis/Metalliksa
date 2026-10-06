import React, { useEffect, useState } from 'react';
import { FlaskConical, Info } from 'lucide-react';
import { sourceMeasurements } from '../services/lpbfSourceService';
import { useLpbfEngineeringStore } from '../store/useLpbfEngineeringStore';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceDot } from 'recharts';

export const ExperimentalValidationLab: React.FC = () => {
  const job = useLpbfEngineeringStore(state => state.job);
  const [data, setData] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    sourceMeasurements('cmu-ti64-meltpool-v1', controller.signal)
      .then(res => {
        if (!controller.signal.aborted) {
          setData(res.data.filter((d: any) => d.power_W === 370));
        }
      })
      .catch(err => {
        if (!controller.signal.aborted) setError(err.message);
      });
    return () => controller.abort();
  }, []);

  const simResult = job?.result?.metrics;
  const simInput = job?.result?.settings;

  return (
    <section aria-labelledby="lpbf-experiment-heading" className="max-w-5xl mx-auto p-4 space-y-4">
      <div className="flex items-center gap-3 bg-cyan-950/40 p-4 rounded-xl border border-cyan-800/50">
        <FlaskConical aria-hidden="true" className="w-8 h-8 text-cyan-400 shrink-0" />
        <div>
          <h2 id="lpbf-experiment-heading" className="text-lg font-bold text-white">Melt Pool vs Measurements</h2>
          <p className="text-sm text-cyan-100">Compare traceable measurements with an identified simulation.</p>
        </div>
      </div>
      
      <div className="bg-slate-900/80 p-5 rounded-xl border border-slate-700 space-y-4">
        <h3 className="text-base font-semibold text-white">CMU Ti-6Al-4V Meltpool Comparison (Power: 370 W)</h3>
        {error ? (
          <p className="text-rose-400">Failed to load experimental data: {error}</p>
        ) : data.length === 0 ? (
          <p className="text-slate-400">Loading experimental data...</p>
        ) : (
          <div className="h-96 w-full mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" dataKey="velocity_mms" name="Velocity" unit=" mm/s" stroke="#94a3b8" domain={['auto', 'auto']} />
                <YAxis type="number" dataKey="value" name="Dimension" unit=" µm" stroke="#94a3b8" />
                <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} />
                <Legend />
                <Scatter name="Exp Width" data={data.map(d => ({ ...d, value: d.width_um }))} fill="#38bdf8" />
                <Scatter name="Exp Depth" data={data.map(d => ({ ...d, value: d.depth_um }))} fill="#fbbf24" />
                
                {simResult && simInput && Math.abs(simInput.power_W - 370) < 5 && (
                  <>
                    <ReferenceDot x={simInput.speed_mm_s} y={simResult.width_um} r={6} fill="#0ea5e9" stroke="white" />
                    <ReferenceDot x={simInput.speed_mm_s} y={simResult.depth_um} r={6} fill="#d97706" stroke="white" />
                  </>
                )}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}
        
        <div className="bg-slate-800 p-4 rounded-lg text-sm text-slate-300">
          <p><strong>Note:</strong> The chart plots experimental width and depth measurements against scanning velocity for Ti-6Al-4V at 370W.</p>
          <p>If you run a simulation in the Engineering workspace with Power=370W and a corresponding velocity, its results will appear as outlined dots on this chart.</p>
        </div>
      </div>
    </section>
  );
};
