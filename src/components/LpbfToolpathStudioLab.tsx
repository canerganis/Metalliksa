import React, { useState, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import { pythonComputationService } from '../services/pythonComputationService';

const SAMPLE_GCODE = `; MetalliX Thin Wall Lattice Cross-Section (Phase 14 -> Phase 12)
; This geometry forces severe galvo mirror deceleration at sharp corners.
; Toggle "Skywriting" to see how the kinematic energy spikes (Hotspots) are mitigated.

; --- X-Aligned Lattice Walls ---
G0 X-7.5 Y-7.5
M3 S280
G1 X7.5 Y-7.5 F60000
M5
G0 X-7.5 Y-3.75
M3 S280
G1 X7.5 Y-3.75 F60000
M5
G0 X-7.5 Y0.0
M3 S280
G1 X7.5 Y0.0 F60000
M5
G0 X-7.5 Y3.75
M3 S280
G1 X7.5 Y3.75 F60000
M5
G0 X-7.5 Y7.5
M3 S280
G1 X7.5 Y7.5 F60000
M5

; --- Y-Aligned Lattice Walls (Crossing the X walls) ---
G0 X-7.5 Y-7.5
M3 S280
G1 X-7.5 Y7.5 F60000
M5
G0 X-3.75 Y-7.5
M3 S280
G1 X-3.75 Y7.5 F60000
M5
G0 X0.0 Y-7.5
M3 S280
G1 X0.0 Y7.5 F60000
M5
G0 X3.75 Y-7.5
M3 S280
G1 X3.75 Y7.5 F60000
M5
G0 X7.5 Y-7.5
M3 S280
G1 X7.5 Y7.5 F60000
M5
G0 X0.0 Y0.0`;

export const LpbfToolpathStudioLab: React.FC = () => {
  const [toolpathText, setToolpathText] = useState(SAMPLE_GCODE);
  const [format, setFormat] = useState<'gcode' | 'cli'>('gcode');
  const [accelMax, setAccelMax] = useState(40000);
  const [jumpSpeed, setJumpSpeed] = useState(3000);
  const [skywriting, setSkywriting] = useState(false);
  const [defaultPower, setDefaultPower] = useState(280);
  const [defaultSpeed, setDefaultSpeed] = useState(1000);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSimulate = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await pythonComputationService.simulateToolpathKinematics({
        content: toolpathText,
        format,
        defaultPower_W: defaultPower,
        defaultSpeed_mms: defaultSpeed,
        accelMax_mms2: accelMax,
        jumpSpeed_mms: jumpSpeed,
        skywritingEnabled: skywriting,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Kinematics simulation failed');
    } finally {
      setIsLoading(false);
    }
  }, [toolpathText, format, defaultPower, defaultSpeed, accelMax, jumpSpeed, skywriting]);

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-200">
      <div className="flex items-center justify-between p-4 bg-gray-800 border-b border-gray-700">
        <div>
          <h2 className="text-lg font-bold text-white">Toolpath & Scanner Kinematics Studio</h2>
          <p className="text-sm text-gray-400">Phase 12: Galvo Mirror Acceleration, Delays & Thermal Overheating Prediction</p>
        </div>
        <button
          onClick={handleSimulate}
          disabled={isLoading}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-medium disabled:opacity-50"
        >
          {isLoading ? 'Simulating Physics...' : 'Simulate Kinematics'}
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sol Panel: Parametreler & G-Code / CLI Girişi */}
        <div className="w-96 p-4 border-r border-gray-700 overflow-y-auto space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase mb-1">Format</label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setFormat('gcode')}
                className={`flex-1 py-1.5 text-xs rounded border ${format === 'gcode' ? 'bg-blue-600 border-blue-500 text-white' : 'bg-gray-800 border-gray-700 text-gray-400'}`}
              >
                G-Code
              </button>
              <button
                type="button"
                onClick={() => setFormat('cli')}
                className={`flex-1 py-1.5 text-xs rounded border ${format === 'cli' ? 'bg-blue-600 border-blue-500 text-white' : 'bg-gray-800 border-gray-700 text-gray-400'}`}
              >
                Common Layer (.cli)
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase mb-1">Toolpath Text</label>
            <textarea aria-label="Toolpath Text"
              rows={8}
              value={toolpathText}
              onChange={e => setToolpathText(e.target.value)}
              className="w-full bg-gray-950 font-mono text-xs p-2 rounded border border-gray-700 text-gray-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="space-y-3 pt-2 border-t border-gray-800">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Galvo Scanner Dynamics</h3>

            <label className="block text-xs">
              <span className="text-gray-400">Max Acceleration (mm/s²)</span>
              <input
                type="range" min={10000} max={100000} step={5000}
                value={accelMax} onChange={e => setAccelMax(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-white text-xs">{accelMax.toLocaleString()} mm/s²</div>
            </label>

            <label className="block text-xs">
              <span className="text-gray-400">Jump Speed (mm/s)</span>
              <input
                type="range" min={1000} max={6000} step={250}
                value={jumpSpeed} onChange={e => setJumpSpeed(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-white text-xs">{jumpSpeed} mm/s</div>
            </label>

            <div className="flex items-center justify-between p-2 rounded bg-gray-800 border border-gray-700">
              <div>
                <span className="text-xs font-medium text-white block">Skywriting Mode</span>
                <span className="text-[10px] text-gray-400 block">Laser only fires at steady-state velocity</span>
              </div>
              <input aria-label="Skywriting Mode"
                type="checkbox"
                checked={skywriting}
                onChange={e => setSkywriting(e.target.checked)}
                className="h-4 w-4 rounded bg-gray-900 border-gray-700 text-blue-600 focus:ring-0"
              />
            </div>
          </div>
        </div>

        {/* Sağ Panel: Çıktılar & Analiz */}
        <div className="flex-1 p-6 overflow-y-auto bg-gray-950">
          {error && (
            <div className="mb-4 p-4 bg-red-900/40 border border-red-700 text-red-200 rounded text-sm">
              {error}
            </div>
          )}

          {!result && !isLoading && !error && (
            <div className="flex h-full items-center justify-center text-gray-500 text-sm">
              Load G-Code / CLI toolpath and click 'Simulate Kinematics' to compute mirror dynamics.
            </div>
          )}

          {result && (
            <div className="space-y-6">
              {/* Özet Metrik Kartları */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Total Build Time</span>
                  <span className="text-lg font-mono font-bold text-white">{result.total_build_time_s} s</span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Laser Duty Cycle</span>
                  <span className="text-lg font-mono font-bold text-blue-400">{result.duty_cycle_pct} %</span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Total Energy Input</span>
                  <span className="text-lg font-mono font-bold text-amber-400">{result.total_energy_input_J} J</span>
                </div>
                <div className="p-3 bg-gray-800 border border-gray-700 rounded flex flex-col items-center">
                  <span className="text-xs text-gray-400 mb-1">Overheating Hotspots</span>
                  <span className={`text-lg font-mono font-bold ${result.hotspot_count > 0 ? 'text-red-400' : 'text-green-400'}`}>
                    {result.hotspot_count}
                  </span>
                </div>
              </div>

              {/* Hotspot & Energy Density Analizi */}
              <div className="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 className="text-sm font-semibold text-white mb-2">Turnaround Thermal Overheating Hotspots</h3>
                <p className="text-xs text-gray-400 mb-4">
                  Galvanometer deceleration at vector endpoints causes actual Linear Energy Density (LED = P/v) to surge beyond nominal values, triggering local keyhole porosity.
                </p>

                {result.hotspot_count === 0 ? (
                  <div className="p-3 bg-green-900/20 border border-green-800 rounded text-xs text-green-300">
                    No critical deceleration hotspots detected. Skywriting or vector length is sufficient to maintain steady-state laser velocity.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left text-gray-300">
                      <thead className="bg-gray-900 text-gray-400 uppercase">
                        <tr>
                          <th className="p-2">Segment</th>
                          <th className="p-2">Position (X, Y)</th>
                          <th className="p-2">Nominal LED</th>
                          <th className="p-2">Actual LED</th>
                          <th className="p-2">Energy Surge</th>
                          <th className="p-2">Root Cause</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-700">
                        {result.hotspots.map((h: any, idx: number) => (
                          <tr key={idx} className="hover:bg-gray-750">
                            <td className="p-2 font-mono">#{h.segment_index}</td>
                            <td className="p-2 font-mono">({h.x.toFixed(2)}, {h.y.toFixed(2)}) mm</td>
                            <td className="p-2 font-mono">{h.nominal_led_J_mm} J/mm</td>
                            <td className="p-2 font-mono text-red-400 font-bold">{h.actual_led_J_mm} J/mm</td>
                            <td className="p-2 font-mono text-amber-400 font-bold">+{((h.overheating_ratio - 1) * 100).toFixed(0)}%</td>
                            <td className="p-2 text-gray-400">{h.cause}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
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
