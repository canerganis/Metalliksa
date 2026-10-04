import React, { useState, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine
} from 'recharts';
import { pythonComputationService } from '../services/pythonComputationService';

const ALLOY_PRESETS = [
  { name: 'Ti-6Al-4V', desc: 'Titanium Grade 5 (Aerospace standard, low thermal conductivity)' },
  { name: 'IN718', desc: 'Nickel Superalloy (High temperature resistance, very low diffusivity)' },
  { name: '316L', desc: 'Austenitic Stainless Steel (Medium conductivity, high ductility)' },
  { name: 'AlSi10Mg', desc: 'Aluminum alloy (High thermal conductivity, fast dissipation)' },
];

export const MultiTrackThermalLab: React.FC = () => {
  const [alloy, setAlloy] = useState('Ti-6Al-4V');
  const [power, setPower] = useState(280);             // W
  const [velocity, setVelocity] = useState(1000);       // mm/s
  const [beamDiameter, setBeamDiameter] = useState(80); // um
  const [hatchSpacing, setHatchSpacing] = useState(100);// um
  const [trackLength, setTrackLength] = useState(10.0); // mm
  const [numTracks, setNumTracks] = useState(12);
  const [turnaroundDelay, setTurnaroundDelay] = useState(0.4); // ms
  const [maxAllowableDrift, setMaxAllowableDrift] = useState(100.0); // K

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [optResult, setOptResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSimulate = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setOptResult(null);
    try {
      const res = await pythonComputationService.simulateThermalAccumulation({
        material: { name: alloy },
        config: {
          laserPower_W: power,
          scanVelocity_mms: velocity,
          beamDiameter_um: beamDiameter,
          hatchSpacing_um: hatchSpacing,
          trackLength_mm: trackLength,
          numTracks,
          bedTemperature_K: 353.15,
          turnaroundDelay_ms: turnaroundDelay,
        },
        mode: 'simulate',
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Thermal simulation failed');
    } finally {
      setIsLoading(false);
    }
  }, [alloy, power, velocity, beamDiameter, hatchSpacing, trackLength, numTracks, turnaroundDelay]);

  const handleOptimize = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await pythonComputationService.simulateThermalAccumulation({
        material: { name: alloy },
        config: {
          laserPower_W: power,
          scanVelocity_mms: velocity,
          beamDiameter_um: beamDiameter,
          hatchSpacing_um: hatchSpacing,
          trackLength_mm: trackLength,
          numTracks,
          bedTemperature_K: 353.15,
          turnaroundDelay_ms: turnaroundDelay,
        },
        mode: 'optimize',
        maxAllowableDrift_K: maxAllowableDrift,
      });
      setOptResult(res);
      setResult(res.unmitigated);
    } catch (err: any) {
      setError(err.message || 'Dwell optimization failed');
    } finally {
      setIsLoading(false);
    }
  }, [alloy, power, velocity, beamDiameter, hatchSpacing, trackLength, numTracks, turnaroundDelay, maxAllowableDrift]);

  const activeDisplay = optResult ? optResult.mitigated : result;

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between p-4 bg-gray-800 border-b border-gray-700">
        <div>
          <h2 className="text-lg font-bold text-white">Multi-Track Thermal Accumulation & Inter-Pass Drift Lab</h2>
          <p className="text-sm text-gray-400">
            Phase 17: 3D Moving Green's Function Analytical Superposition & Keyhole Transition Thresholding
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSimulate}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded text-sm transition-colors"
          >
            {isLoading ? 'Calculating...' : 'Simulate Hatch Sequence'}
          </button>
          <button
            onClick={handleOptimize}
            disabled={isLoading}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium rounded text-sm transition-colors"
          >
            {isLoading ? 'Optimizing...' : 'Optimize Dwell Delays'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-900/50 border-b border-red-700 text-red-200 text-sm">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Main Container */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Parameters Panel */}
        <div className="w-80 p-4 border-r border-gray-700 bg-gray-850 flex flex-col gap-4 overflow-y-auto">
          <div>
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-2">Alloy Selection</h3>
            <select aria-label="Alloy Selection"
              value={alloy}
              onChange={(e) => setAlloy(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white text-xs"
            >
              {ALLOY_PRESETS.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-gray-400 mt-1">
              {ALLOY_PRESETS.find((p) => p.name === alloy)?.desc}
            </p>
          </div>

          <div className="border-t border-gray-700 pt-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-2">Hatch Process Parameters</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-gray-400 mb-1">Laser Power: {power} W</label>
                <input aria-label="Laser Power"
                  type="range"
                  min="100"
                  max="500"
                  step="10"
                  value={power}
                  onChange={(e) => setPower(parseInt(e.target.value))}
                  className="w-full accent-blue-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Scan Velocity: {velocity} mm/s</label>
                <input aria-label="Scan Velocity"
                  type="range"
                  min="400"
                  max="2000"
                  step="50"
                  value={velocity}
                  onChange={(e) => setVelocity(parseInt(e.target.value))}
                  className="w-full accent-blue-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Hatch Spacing: {hatchSpacing} μm</label>
                <input aria-label="Hatch Spacing"
                  type="range"
                  min="50"
                  max="200"
                  step="5"
                  value={hatchSpacing}
                  onChange={(e) => setHatchSpacing(parseInt(e.target.value))}
                  className="w-full accent-blue-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Vector Length: {trackLength} mm</label>
                <input aria-label="Vector Length"
                  type="range"
                  min="3.0"
                  max="25.0"
                  step="1.0"
                  value={trackLength}
                  onChange={(e) => setTrackLength(parseFloat(e.target.value))}
                  className="w-full accent-blue-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Number of Hatches: {numTracks}</label>
                <input aria-label="Number of Hatches"
                  type="range"
                  min="4"
                  max="24"
                  step="2"
                  value={numTracks}
                  onChange={(e) => setNumTracks(parseInt(e.target.value))}
                  className="w-full accent-blue-500"
                />
              </div>
              <div>
                <label className="block text-gray-400 mb-1">Turnaround Delay: {turnaroundDelay} ms</label>
                <input aria-label="Turnaround Delay"
                  type="range"
                  min="0.1"
                  max="5.0"
                  step="0.1"
                  value={turnaroundDelay}
                  onChange={(e) => setTurnaroundDelay(parseFloat(e.target.value))}
                  className="w-full accent-yellow-500"
                />
                <span className="text-[10px] text-gray-500">Fast turns trap heat; long turns allow dissipation.</span>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-700 pt-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-2">Optimization Threshold</h3>
            <div className="text-xs">
              <label className="block text-gray-400 mb-1">Max Allowable Drift: {maxAllowableDrift} K</label>
              <input aria-label="Max Allowable Drift"
                type="range"
                min="30"
                max="250"
                step="10"
                value={maxAllowableDrift}
                onChange={(e) => setMaxAllowableDrift(parseFloat(e.target.value))}
                className="w-full accent-emerald-500"
              />
            </div>
          </div>
        </div>

        {/* Right Analytics and Charts */}
        <div className="flex-1 p-6 flex flex-col gap-6 overflow-y-auto">
          {/* KPI Summary Cards */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-gray-800 p-4 rounded border border-gray-700">
              <div className="text-xs text-gray-400">Peak Baseline Drift</div>
              <div className={`text-xl font-bold mt-1 ${activeDisplay?.max_baseline_drift_K > 150 ? 'text-red-400' : 'text-amber-400'}`}>
                {activeDisplay ? `+${activeDisplay.max_baseline_drift_K} K` : '—'}
              </div>
              <div className="text-[11px] text-gray-500 mt-1">Accumulated preheating over bed temp</div>
            </div>

            <div className="bg-gray-800 p-4 rounded border border-gray-700">
              <div className="text-xs text-gray-400">Keyhole Transition Risk</div>
              <div className={`text-xl font-bold mt-1 ${activeDisplay?.keyhole_mode_tracks_count > 0 ? 'text-red-500' : 'text-emerald-400'}`}>
                {activeDisplay ? (activeDisplay.keyhole_mode_tracks_count > 0 ? `HIGH (${activeDisplay.keyhole_mode_tracks_count} tracks)` : 'CONDUCTION (SAFE)') : '—'}
              </div>
              <div className="text-[11px] text-gray-500 mt-1">Tracks exceeding alloy boiling temp</div>
            </div>

            <div className="bg-gray-800 p-4 rounded border border-gray-700">
              <div className="text-xs text-gray-400">Material Limits ({alloy})</div>
              <div className="text-sm font-semibold text-gray-300 mt-1">
                {activeDisplay ? `Tm: ${activeDisplay.melting_point_K} K | Tv: ${activeDisplay.boiling_point_K} K` : '—'}
              </div>
              <div className="text-[11px] text-gray-500 mt-1">Liquidus &amp; Evaporation boundaries</div>
            </div>

            <div className="bg-gray-800 p-4 rounded border border-gray-700">
              <div className="text-xs text-gray-400">Total Scan Duration</div>
              <div className="text-xl font-bold text-blue-400 mt-1">
                {activeDisplay ? `${(activeDisplay.total_hatch_time_s * 1000).toFixed(1)} ms` : '—'}
              </div>
              <div className="text-[11px] text-gray-500 mt-1">Motion + inter-track delays</div>
            </div>
          </div>

          {/* Dwell Optimization Card */}
          {optResult && (
            <div className="bg-emerald-950/40 border border-emerald-700/60 p-4 rounded text-sm text-emerald-200">
              <div className="font-bold flex items-center gap-2 mb-1">
                <span>✓ Adaptive Turnaround Dwell Schedule Applied</span>
              </div>
              <div className="grid grid-cols-4 gap-4 mt-2 text-xs">
                <div>
                  <span className="text-gray-400">Original Turnaround: </span>
                  <strong className="text-white">{optResult.original_turnaround_delay_ms} ms</strong>
                </div>
                <div>
                  <span className="text-gray-400">Optimized Turnaround: </span>
                  <strong className="text-white">{optResult.recommended_turnaround_delay_ms} ms</strong>
                </div>
                <div>
                  <span className="text-gray-400">Thermal Drift Reduction: </span>
                  <strong className="text-white">-{optResult.drift_reduction_K} K</strong>
                </div>
                <div>
                  <span className="text-gray-400">Keyhole Hazards Prevented: </span>
                  <strong className="text-white">-{optResult.keyhole_hazards_prevented} tracks</strong>
                </div>
              </div>
            </div>
          )}

          {/* Temperature Evolution Chart */}
          <div className="bg-gray-800 p-4 rounded border border-gray-700">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">
              Per-Track Baseline Preheating Drift &amp; Peak Melt Temperature vs Track Index
            </h3>
            <div className="h-64">
              {activeDisplay?.tracks ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={activeDisplay.tracks}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="track_index" stroke="#9ca3af" label={{ value: 'Track Index', position: 'insideBottom', offset: -4 }} />
                    <YAxis stroke="#9ca3af" unit=" K" domain={['dataMin - 100', 'dataMax + 200']} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }}
                      formatter={(val: any, name: string) => [`${val} K`, name]}
                    />
                    <Legend />
                    {activeDisplay.boiling_point_K && (
                      <ReferenceLine
                        y={activeDisplay.boiling_point_K}
                        stroke="#ef4444"
                        strokeDasharray="4 4"
                        label={{ value: 'Boiling / Keyhole Threshold (Tv)', fill: '#ef4444', fontSize: 11 }}
                      />
                    )}
                    {activeDisplay.melting_point_K && (
                      <ReferenceLine
                        y={activeDisplay.melting_point_K}
                        stroke="#3b82f6"
                        strokeDasharray="3 3"
                        label={{ value: 'Melting Point (Tm)', fill: '#3b82f6', fontSize: 11 }}
                      />
                    )}
                    <Line
                      type="monotone"
                      dataKey="peak_temp_K"
                      name="Peak Melt Temp (K)"
                      stroke="#f59e0b"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="baseline_temp_K"
                      name="Substrate Baseline Temp (K)"
                      stroke="#10b981"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500 text-sm">
                  Click "Simulate Hatch Sequence" to compute multi-track thermal history.
                </div>
              )}
            </div>
          </div>

          {/* Melt Pool Dimensions Evolution */}
          <div className="bg-gray-800 p-4 rounded border border-gray-700">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">
              Melt Pool Geometry Growth (Width &amp; Depth in μm)
            </h3>
            <div className="h-60">
              {activeDisplay?.tracks ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={activeDisplay.tracks}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="track_index" stroke="#9ca3af" />
                    <YAxis stroke="#9ca3af" unit=" μm" />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }}
                      formatter={(val: any, name: string) => [`${val} μm`, name]}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="melt_pool_width_um"
                      name="Melt Pool Width (μm)"
                      stroke="#60a5fa"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="melt_pool_depth_um"
                      name="Melt Pool Depth (μm)"
                      stroke="#ec4899"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500 text-sm">
                  Melt pool width and depth dimensions will be plotted here.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MultiTrackThermalLab;
