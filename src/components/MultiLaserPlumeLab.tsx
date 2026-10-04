import React, { useState, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { pythonComputationService } from '../services/pythonComputationService';

export const MultiLaserPlumeLab: React.FC = () => {
  // Shield Gas Flow
  const [gasVelocity, setGasVelocity] = useState(2.0); // m/s
  const [gasAngle, setGasAngle] = useState(0.0);       // deg
  const [gasType, setGasType] = useState('Argon');

  // Laser Trajectory Presets
  const [laserPower, setLaserPower] = useState(300);   // W
  const [laserSpeed, setLaserSpeed] = useState(1000);  // mm/s
  const [beamSeparationY, setBeamSeparationY] = useState(1.5); // mm
  const [downwindOffset, setDownwindOffset] = useState(8.0);   // mm

  // Plume Parameters
  const [sigmaPlume, setSigmaPlume] = useState(2.5);   // mm
  const [decayLength, setDecayLength] = useState(25.0); // mm

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [optimizationResult, setOptimizationResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Build dual-laser toolpaths based on inputs
  const buildVectors = useCallback(() => {
    // Laser 1 scans (0, 0) -> (40, 0)
    const l1 = [[0.0, 0.0, 40.0, 0.0, laserPower, laserSpeed]];
    // Laser 2 scans in the wake (downwindOffset, beamSeparationY) -> (downwindOffset + 40, beamSeparationY)
    const l2 = [[downwindOffset, beamSeparationY, downwindOffset + 40.0, beamSeparationY, laserPower, laserSpeed]];
    return { l1, l2 };
  }, [laserPower, laserSpeed, beamSeparationY, downwindOffset]);

  const handleSimulate = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setOptimizationResult(null);
    const { l1, l2 } = buildVectors();
    try {
      const res = await pythonComputationService.simulateMultiLaserPlume({
        gasFlow: { gasType, velocity_m_s: gasVelocity, angle_deg: gasAngle },
        plumeParams: {
          sigma_plume_mm: sigmaPlume,
          decay_length_mm: decayLength,
          base_extinction_coeff: 0.35,
          min_collision_dist_mm: 1.0,
          attenuation_hazard_threshold: 0.10,
        },
        laser1_vectors: l1,
        laser2_vectors: l2,
        mode: 'simulate',
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Simulation failed');
    } finally {
      setIsLoading(false);
    }
  }, [gasType, gasVelocity, gasAngle, sigmaPlume, decayLength, buildVectors]);

  const handleOptimize = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const { l1, l2 } = buildVectors();
    try {
      const res = await pythonComputationService.simulateMultiLaserPlume({
        gasFlow: { gasType, velocity_m_s: gasVelocity, angle_deg: gasAngle },
        plumeParams: {
          sigma_plume_mm: sigmaPlume,
          decay_length_mm: decayLength,
          base_extinction_coeff: 0.35,
          min_collision_dist_mm: 1.0,
          attenuation_hazard_threshold: 0.10,
        },
        laser1_vectors: l1,
        laser2_vectors: l2,
        mode: 'optimize',
      });
      setOptimizationResult(res);
      setResult(res.unmitigated);
    } catch (err: any) {
      setError(err.message || 'Optimization failed');
    } finally {
      setIsLoading(false);
    }
  }, [gasType, gasVelocity, gasAngle, sigmaPlume, decayLength, buildVectors]);

  const activeDisplay = optimizationResult ? optimizationResult.mitigated : result;

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between p-4 bg-gray-800 border-b border-gray-700">
        <div>
          <h2 className="text-lg font-bold text-white">Multi-Laser Synchronization & Plume Attenuation Lab</h2>
          <p className="text-sm text-gray-400">
            Phase 16: Fluid-Optic Gas Cross-Flow Coupling, Beer-Lambert Plume Shadowing & Downwind De-Confliction
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSimulate}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded text-sm transition-colors"
          >
            {isLoading ? 'Simulating...' : 'Run Simulation'}
          </button>
          <button
            onClick={handleOptimize}
            disabled={isLoading}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium rounded text-sm transition-colors"
          >
            {isLoading ? 'Optimizing...' : 'Optimize De-Confliction'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-900/50 border-b border-red-700 text-red-200 text-sm">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Parameter Panel */}
        <div className="w-80 p-4 border-r border-gray-700 bg-gray-850 flex flex-col gap-4 overflow-y-auto">
          <div>
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-2">Shield Gas Cross-Flow</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-gray-400 mb-1">Inert Gas Type</label>
                <select aria-label="Inert Gas Type"
                  value={gasType}
                  onChange={(e) => setGasType(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded p-1.5 text-white"
                >
                  <option value="Argon">Argon (Ar, High Density)</option>
                  <option value="Nitrogen">Nitrogen (N2)</option>
                </select>
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Cross-Flow Velocity: {gasVelocity} m/s</label>
                <input aria-label="Cross-Flow Velocity"
                  type="range"
                  min="0.5"
                  max="5.0"
                  step="0.1"
                  value={gasVelocity}
                  onChange={(e) => setGasVelocity(parseFloat(e.target.value))}
                  className="w-full accent-blue-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Flow Direction Angle: {gasAngle}°</label>
                <input aria-label="Flow Direction Angle"
                  type="range"
                  min="0"
                  max="360"
                  step="15"
                  value={gasAngle}
                  onChange={(e) => setGasAngle(parseFloat(e.target.value))}
                  className="w-full accent-blue-500"
                />
                <span className="text-[10px] text-gray-500">0° = +X (Left to Right), 90° = +Y</span>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-700 pt-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-2">Dual Laser Configuration</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-gray-400 mb-1">Nominal Power: {laserPower} W</label>
                <input aria-label="Nominal Power"
                  type="range"
                  min="100"
                  max="500"
                  step="10"
                  value={laserPower}
                  onChange={(e) => setLaserPower(parseInt(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Scan Velocity: {laserSpeed} mm/s</label>
                <input aria-label="Scan Velocity"
                  type="range"
                  min="400"
                  max="2000"
                  step="50"
                  value={laserSpeed}
                  onChange={(e) => setLaserSpeed(parseInt(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Laser 2 Downwind X-Offset: {downwindOffset} mm</label>
                <input aria-label="Laser 2 Downwind X-Offset"
                  type="range"
                  min="0"
                  max="30"
                  step="1"
                  value={downwindOffset}
                  onChange={(e) => setDownwindOffset(parseFloat(e.target.value))}
                  className="w-full accent-purple-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Laser 2 Transverse Y-Separation: {beamSeparationY} mm</label>
                <input aria-label="Laser 2 Transverse Y-Separation"
                  type="range"
                  min="0"
                  max="10"
                  step="0.5"
                  value={beamSeparationY}
                  onChange={(e) => setBeamSeparationY(parseFloat(e.target.value))}
                  className="w-full accent-purple-500"
                />
                <span className="text-[10px] text-gray-500">&lt; 1.0 mm triggers collision risk</span>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-700 pt-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-2">Plume Physics Parameters</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-gray-400 mb-1">Plume Width (σ_p): {sigmaPlume} mm</label>
                <input aria-label="Plume Width (σ_p)"
                  type="range"
                  min="1.0"
                  max="5.0"
                  step="0.2"
                  value={sigmaPlume}
                  onChange={(e) => setSigmaPlume(parseFloat(e.target.value))}
                  className="w-full accent-yellow-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Downwind Decay Length: {decayLength} mm</label>
                <input aria-label="Downwind Decay Length"
                  type="range"
                  min="10.0"
                  max="60.0"
                  step="5.0"
                  value={decayLength}
                  onChange={(e) => setDecayLength(parseFloat(e.target.value))}
                  className="w-full accent-yellow-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Analytics and Charts */}
        <div className="flex-1 p-6 flex flex-col gap-6 overflow-y-auto">
          {/* KPI Cards */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-gray-800 p-4 rounded border border-gray-700">
              <div className="text-xs text-gray-400">Collision Hazard</div>
              <div className={`text-xl font-bold mt-1 ${activeDisplay?.collision_hazard_count > 0 ? 'text-red-500' : 'text-emerald-400'}`}>
                {activeDisplay ? (activeDisplay.collision_hazard_count > 0 ? `CRITICAL (${activeDisplay.collision_hazard_count})` : 'CLEAR (SAFE)') : '—'}
              </div>
              <div className="text-[11px] text-gray-500 mt-1">Inter-beam distance threshold 1.0 mm</div>
            </div>

            <div className="bg-gray-800 p-4 rounded border border-gray-700">
              <div className="text-xs text-gray-400">Plume Shadowing Hazard</div>
              <div className={`text-xl font-bold mt-1 ${activeDisplay?.plume_hazard_count > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                {activeDisplay ? (activeDisplay.plume_hazard_count > 0 ? `DETECTED (${activeDisplay.plume_hazard_count})` : 'NOMINAL') : '—'}
              </div>
              <div className="text-[11px] text-gray-500 mt-1">Beer-Lambert loss &gt; 10%</div>
            </div>

            <div className="bg-gray-800 p-4 rounded border border-gray-700">
              <div className="text-xs text-gray-400">Peak Optical Attenuation</div>
              <div className="text-xl font-bold text-yellow-400 mt-1">
                {activeDisplay ? `${activeDisplay.max_attenuation_pct}%` : '—'}
              </div>
              <div className="text-[11px] text-gray-500 mt-1">Max instantaneous power extinction</div>
            </div>

            <div className="bg-gray-800 p-4 rounded border border-gray-700">
              <div className="text-xs text-gray-400">Total Plume Energy Loss</div>
              <div className="text-xl font-bold text-red-400 mt-1">
                {activeDisplay ? `${activeDisplay.total_energy_lost_Joules} J` : '—'}
              </div>
              <div className="text-[11px] text-gray-500 mt-1">Deficit relative to nominal input</div>
            </div>
          </div>

          {/* Optimization Summary Alert if present */}
          {optimizationResult && (
            <div className="bg-emerald-950/40 border border-emerald-700/60 p-4 rounded text-sm text-emerald-200">
              <div className="font-bold flex items-center gap-2 mb-1">
                <span>✓ Downwind-First Scheduling Optimization Applied</span>
              </div>
              <div className="grid grid-cols-3 gap-4 mt-2 text-xs">
                <div>
                  <span className="text-gray-400">Energy Loss Saved: </span>
                  <strong className="text-white">+{optimizationResult.energy_loss_reduction_J} Joules</strong>
                </div>
                <div>
                  <span className="text-gray-400">Plume Hazards Reduced: </span>
                  <strong className="text-white">-{optimizationResult.plume_hazard_reduction_count} instances</strong>
                </div>
                <div>
                  <span className="text-gray-400">Stagger Dwell Delay: </span>
                  <strong className="text-white">{optimizationResult.stagger_delay_applied_ms} ms</strong>
                </div>
              </div>
            </div>
          )}

          {/* Dynamic Laser Time-Series Chart */}
          <div className="bg-gray-800 p-4 rounded border border-gray-700">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">
              Dual-Beam Transmitted Power & Inter-Laser Distance vs Time
            </h3>
            <div className="h-64">
              {activeDisplay?.time_series ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={activeDisplay.time_series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="time_s" stroke="#9ca3af" tickFormatter={(v) => `${(v * 1000).toFixed(0)} ms`} />
                    <YAxis yAxisId="power" domain={[0, laserPower * 1.1]} stroke="#34d399" unit=" W" />
                    <YAxis yAxisId="dist" orientation="right" stroke="#60a5fa" unit=" mm" />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }}
                      formatter={(val: any, name: string) => [
                        typeof val === 'number' ? val.toFixed(2) : val,
                        name
                      ]}
                    />
                    <Legend />
                    <Line
                      yAxisId="power"
                      type="monotone"
                      dataKey="l1_p_eff"
                      name="Laser 1 Eff. Power"
                      stroke="#10b981"
                      dot={false}
                      strokeWidth={2}
                    />
                    <Line
                      yAxisId="power"
                      type="monotone"
                      dataKey="l2_p_eff"
                      name="Laser 2 Eff. Power (In Plume)"
                      stroke="#f59e0b"
                      dot={false}
                      strokeWidth={2}
                    />
                    <Line
                      yAxisId="dist"
                      type="monotone"
                      dataKey="inter_dist_mm"
                      name="Inter-Laser Separation"
                      stroke="#3b82f6"
                      strokeDasharray="4 4"
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500 text-sm">
                  Click "Run Simulation" or "Optimize De-Confliction" to plot multi-beam kinetics.
                </div>
              )}
            </div>
          </div>

          {/* 2D Plume Optical Density Field Visualization */}
          <div className="bg-gray-800 p-4 rounded border border-gray-700">
            <h3 className="text-sm font-semibold text-gray-200 mb-2">
              Chamber Plume Density Field & Gas Streamlines Snapshot
            </h3>
            <p className="text-xs text-gray-400 mb-4">
              Shield gas ({gasType}) flowing at {gasVelocity} m/s at {gasAngle}° deflecting the metal vapor core.
            </p>
            <div className="flex items-center justify-center">
              <svg width="420" height="260" className="bg-gray-950 border border-gray-700 rounded shadow-inner">
                {/* Gas Flow Direction Vector Arrows */}
                <defs>
                  <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" opacity="0.6" />
                  </marker>
                </defs>
                <line x1="30" y1="30" x2="80" y2="30" stroke="#3b82f6" strokeWidth="2" markerEnd="url(#arrow)" />
                <text x="90" y="34" fill="#93c5fd" fontSize="11" fontFamily="sans-serif">
                  u_gas = {gasVelocity} m/s ({gasType})
                </text>

                {/* Laser 1 Position & Plume Wake */}
                <g transform="translate(120, 130)">
                  {/* Gaussian Plume Wake downstream */}
                  <path
                    d="M 0 0 C 40 -25, 120 -35, 180 -15 C 200 -5, 200 5, 180 15 C 120 35, 40 25, 0 0 Z"
                    fill="url(#plumeGrad1)"
                    opacity="0.55"
                  />
                  {/* Laser 1 Spot */}
                  <circle cx="0" cy="0" r="7" fill="#10b981" />
                  <text x="-25" y="-12" fill="#34d399" fontSize="11" fontWeight="bold">Laser 1 (300W)</text>
                </g>

                {/* Laser 2 Position (Interacting with plume) */}
                <g transform={`translate(${120 + downwindOffset * 4}, ${130 + beamSeparationY * 8})`}>
                  <circle cx="0" cy="0" r="7" fill={beamSeparationY < 1.0 ? "#ef4444" : "#f59e0b"} />
                  <text x="12" y="4" fill="#fbbf24" fontSize="11" fontWeight="bold">
                    Laser 2 ({activeDisplay ? `${activeDisplay.max_attenuation_pct}% Atten.` : 'Trailing'})
                  </text>
                </g>

                {/* Gradient for plume */}
                <defs>
                  <linearGradient id="plumeGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#ef4444" stopOpacity="0.8" />
                    <stop offset="40%" stopColor="#f59e0b" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MultiLaserPlumeLab;
