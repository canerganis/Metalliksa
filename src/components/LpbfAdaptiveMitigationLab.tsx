import React, { useState, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { pythonComputationService } from '../services/pythonComputationService';

const SAMPLE_GCODE = `; LPBF Turnaround Overheating Test Pattern
G0 X0.0 Y0.0
M3 S280
G1 X15.0 Y0.0 F60000
G1 X15.0 Y0.15 F60000
G1 X0.0 Y0.15 F60000
G1 X0.0 Y0.3 F60000
G1 X15.0 Y0.3 F60000
M5
G0 X0.0 Y0.0
`;

/** Rotation the engine applies: 67° × layer index when enabled, else 0. */
export function rotationPreviewDeg(enabled: boolean, layerIndex: number): number {
  return enabled ? Math.round(67 * layerIndex * 10) / 10 : 0;
}

export const LpbfAdaptiveMitigationLab: React.FC = () => {
  const [gcodeText, setGcodeText] = useState(SAMPLE_GCODE);
  const [nominalPower, setNominalPower] = useState(280);
  const [nominalSpeed, setNominalSpeed] = useState(1000);
  const [accelMax, setAccelMax] = useState(40000);
  const [apply67Deg, setApply67Deg] = useState(true);
  const [layerIndex, setLayerIndex] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleMitigate = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await pythonComputationService.processAdaptiveFeedforward({
        content: gcodeText,
        format: 'gcode',
        defaultPower_W: nominalPower,
        defaultSpeed_mms: nominalSpeed,
        accelMax_mms2: accelMax,
        apply67DegRotation: apply67Deg,
        layerIndex,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Mitigation computation failed');
    } finally {
      setIsLoading(false);
    }
  }, [gcodeText, nominalPower, nominalSpeed, accelMax, apply67Deg, layerIndex]);

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-200">
      <div className="flex items-center justify-between p-4 bg-gray-800 border-b border-gray-700">
        <div>
          <h2 className="text-lg font-bold text-white">Corner Power Compensation</h2>
          <p className="text-sm text-gray-400">Open-loop per-vector power scaling from scanner kinematics (no sensor feedback) and optional 67° × layer scan rotation</p>
        </div>
        <button
          onClick={handleMitigate}
          disabled={isLoading}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded font-medium disabled:opacity-50"
        >
          {isLoading ? 'Scaling Toolpath...' : 'Generate Power-Scaled G-Code'}
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sol Panel: G-Code ve Ayarlar */}
        <div className="w-88 p-4 border-r border-gray-700 overflow-y-auto space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase mb-1">Source G-Code</label>
            <textarea aria-label="Source G-Code"
              rows={7}
              value={gcodeText}
              onChange={e => setGcodeText(e.target.value)}
              className="w-full bg-gray-950 font-mono text-[11px] p-2 rounded border border-gray-700 text-gray-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="space-y-3 pt-2 border-t border-gray-800">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Scaling Controls</h3>

            <label className="block text-xs">
              <span className="text-gray-400">Nominal Laser Power (W)</span>
              <input
                type="range" min={100} max={600} step={10}
                value={nominalPower} onChange={e => setNominalPower(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-white text-xs">{nominalPower} W</div>
            </label>

            <label className="block text-xs">
              <span className="text-gray-400">Nominal Scan Speed (mm/s)</span>
              <input
                type="range" min={400} max={2500} step={50}
                value={nominalSpeed} onChange={e => setNominalSpeed(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-white text-xs">{nominalSpeed} mm/s</div>
            </label>

            <label className="block text-xs">
              <span className="text-gray-400">Galvo Max Acceleration (mm/s²)</span>
              <input
                type="range" min={10000} max={80000} step={5000}
                value={accelMax} onChange={e => setAccelMax(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-white text-xs">{accelMax.toLocaleString()} mm/s²</div>
            </label>

            <div className="flex items-center justify-between p-2 rounded bg-gray-800 border border-gray-700">
              <div>
                <span className="text-xs font-medium text-white block">67° Interlayer Rotation</span>
                <span className="text-[10px] text-gray-400 block">Rotates the toolpath by 67° × layer index about the origin; no texture or microstructure effect is computed</span>
              </div>
              <input aria-label="67° Interlayer Rotation"
                type="checkbox"
                checked={apply67Deg}
                onChange={e => setApply67Deg(e.target.checked)}
                className="h-4 w-4 rounded bg-gray-900 border-gray-700 text-indigo-600 focus:ring-0"
              />
            </div>

            <label className="block text-xs">
              <span className="text-gray-400">Layer Index</span>
              <input aria-label="Layer Index" type="number" min={0} step={1}
                value={layerIndex} disabled={!apply67Deg}
                onChange={e => setLayerIndex(Math.max(0, Math.round(Number(e.target.value) || 0)))}
                className="w-full mt-1 bg-gray-950 border border-gray-700 rounded p-1 font-mono text-white disabled:opacity-50" />
              <span className="text-[10px] text-gray-500 block mt-1">Rotation applied = 67° × {layerIndex} = {rotationPreviewDeg(apply67Deg, layerIndex)}°</span>
            </label>

            <p className="text-[10px] text-gray-500">
              Power is scaled once per vector as P × min(1, v_peak / v_nominal). One S-word is written per vector; power is not ramped along the acceleration and deceleration phases inside a vector.
            </p>
          </div>
        </div>

        {/* Sağ Panel: Çıktılar & G-Code */}
        <div className="flex-1 p-6 overflow-y-auto bg-gray-950">
          {error && (
            <div className="mb-4 p-4 bg-red-900/40 border border-red-700 text-red-200 rounded text-sm">
              {error}
            </div>
          )}

          {!result && !isLoading && !error && (
            <div className="flex h-full items-center justify-center text-gray-500 text-sm">
              Input toolpath and click 'Generate Power-Scaled G-Code' to compute open-loop per-vector power scaling.
            </div>
          )}

          {result && (
            <div className="space-y-6">
              {/* Metrik Rozetleri */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Power-Scaled Vectors</span>
                  <span className="text-xl font-mono font-bold text-emerald-400">
                    {result.mitigated_hotspots_count}
                  </span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1 text-center">Total Commanded Energy Change</span>
                  <span className="text-xl font-mono font-bold text-indigo-400">
                    -{result.overall_energy_reduction_pct} %
                  </span>
                  <span className="text-[10px] text-gray-500 text-center mt-1">Σ P·L/v_nominal, scaled vs nominal power; not a peak or local energy value</span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Layer Scan Rotation</span>
                  <span className="text-lg font-mono font-bold text-white">
                    {result.rotation_angle_deg}°
                  </span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Total Segments</span>
                  <span className="text-lg font-mono font-bold text-gray-300">
                    {result.total_segments}
                  </span>
                </div>
              </div>

              {/* Güç Karşılaştırma Grafiği */}
              <div className="bg-gray-800 border border-gray-700 rounded p-4 h-72 flex flex-col">
                <h3 className="text-sm font-semibold text-white mb-2">Per-Vector Power Scaling, first 25 segments (W)</h3>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={result.sample_segments}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="nominal_power_W" stroke="#9ca3af" tickFormatter={(_, idx) => `#${idx + 1}`} />
                    <YAxis stroke="#9ca3af" label={{ value: 'Laser Power (W)', angle: -90, position: 'insideLeft', fill: '#9ca3af' }} />
                    <Tooltip contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#f3f4f6' }} />
                    <Legend />
                    <Bar dataKey="nominal_power_W" name="Unmitigated Power (W)" fill="#ef4444" />
                    <Bar dataKey="compensated_power_W" name="Adaptive Power (W)" fill="#10b981" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Üretilen Düzeltilmiş G-Code */}
              <div className="bg-gray-800 border border-gray-700 rounded p-4">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="text-sm font-semibold text-white">Power-Scaled G-Code Output</h3>
                  <button
                    onClick={() => navigator.clipboard.writeText(result.mitigated_gcode)}
                    className="px-2.5 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded text-gray-200"
                  >
                    Copy G-Code
                  </button>
                </div>
                <p className="text-[10px] text-amber-300 mb-2">
                  Not machine-validated. Travel moves carry an explicit S0 while M3 stays on; check the controller laser mode, S-word scaling and delays before any use on a machine.
                </p>
                <pre className="p-3 bg-gray-950 rounded border border-gray-800 text-[11px] font-mono text-emerald-300 overflow-x-auto max-h-52">
                  {result.mitigated_gcode}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
