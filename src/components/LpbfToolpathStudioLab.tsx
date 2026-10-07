import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { pythonComputationService } from '../services/pythonComputationService';
import {
  SAMPLE_FEEDFORWARD_GCODE, TOOLPATH_TABS, energyChangeLabel, nextToolpathTab, rotationPreviewDeg, rotationPreviewText,
  toolpathTabFromHash, toolpathTabHash, type ToolpathSharedInputs, type ToolpathTab,
} from './toolpathFeedforward';

export { energyChangeLabel, rotationPreviewDeg, rotationPreviewText };

const SAMPLE_GCODE = `; MetalliX Thin Wall Lattice Cross-Section (Phase 14 -> Phase 12)
; Each vector is 15 mm long. At the default 1000 mm/s and 40000 mm/s^2 a vector needs 25 mm to
; reach speed and slow down, so none of them has a constant-velocity cruise phase (triangular profile).
; Without Skywriting the laser fires through the ramps and the energy-density hotspots are reported.
; With Skywriting the laser would fire only during cruise, so here it never fires (0 J):
; that is NOT a mitigation. Lower the speed or use longer vectors to get a cruise phase.

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

/** Warnings produced by the kinematics engine (e.g. skywriting with no cruise phase), if any. */
export function toolpathWarnings(result: any): string[] {
  if (!result) return [];
  const w: string[] = Array.isArray(result.warnings) ? [...result.warnings] : [];
  if (result.laser_never_fires && !w.some(x => /never fires/i.test(x))) {
    w.push('The laser never fires in this toolpath under skywriting (0 J deposited).');
  }
  return w;
}

/** Returns an input error for the process defaults, or null when they are usable. */
export function toolpathDefaultsError(defaultPower: number, defaultSpeed: number): string | null {
  if (!Number.isFinite(defaultPower) || defaultPower <= 0) {
    return 'Default laser power must be a positive number (W).';
  }
  if (!Number.isFinite(defaultSpeed) || defaultSpeed <= 0) {
    return 'Default scan speed must be a positive number (mm/s).';
  }
  return null;
}

/**
 * Text shown when no segment is flagged. Null means there is no caveat beyond the
 * threshold statement. The skywriting no-energy explanation is shown only when the
 * engine reports skywriting was on and vectors lacked a cruise phase.
 */
export function zeroFlagCaveat(result: any): string | null {
  if (!result || result.hotspot_count !== 0) return null;
  const noCruise = Number(result.no_cruise_segment_count) || 0;
  if (result.laser_never_fires || (result.skywriting_mitigation_active && noCruise > 0)) {
    return 'Zero flags reported, but see the warning above: with skywriting on, vectors without a cruise phase deposit no energy, so zero flags here means no exposure, not an acceptable exposure.';
  }
  if (toolpathWarnings(result).length > 0) {
    return 'Zero flags reported; see the warning above about vectors that never reach their commanded speed.';
  }
  return null;
}

const ToolpathKinematicsPanel: React.FC<ToolpathSharedInputs> = ({
  toolpathText, setToolpathText, format, setFormat, defaultPower, setDefaultPower, defaultSpeed, setDefaultSpeed,
  accelMax, setAccelMax, jumpSpeed, setJumpSpeed,
}) => {
  const [skywriting, setSkywriting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const inputError = toolpathDefaultsError(defaultPower, defaultSpeed);

  const handleSimulate = useCallback(async () => {
    if (toolpathDefaultsError(defaultPower, defaultSpeed)) return;
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
          <p className="text-sm text-gray-400">Trapezoidal / triangular scanner velocity profiles and a linear-energy-density screen (no thermal field is solved)</p>
        </div>
        <button
          onClick={handleSimulate}
          disabled={isLoading || inputError !== null}
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
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Process Defaults</h3>
            <p className="text-[10px] text-gray-500">Used for vectors without an explicit power (S) or feed (F) word. Scanner delays (laser-on, mark, jump) use the engine defaults and are not editable here.</p>
            <label className="block text-xs">
              <span className="text-gray-400">Default Laser Power (W)</span>
              <input aria-label="Default Laser Power" type="number" min={1} step={10}
                value={defaultPower} onChange={e => setDefaultPower(Number(e.target.value))}
                className="w-full mt-1 bg-gray-950 border border-gray-700 rounded p-1 font-mono text-white" />
            </label>
            <label className="block text-xs">
              <span className="text-gray-400">Default Scan Speed (mm/s)</span>
              <input aria-label="Default Scan Speed" type="number" min={1} step={50}
                value={defaultSpeed} onChange={e => setDefaultSpeed(Number(e.target.value))}
                className="w-full mt-1 bg-gray-950 border border-gray-700 rounded p-1 font-mono text-white" />
            </label>
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider pt-2">Galvo Scanner Dynamics</h3>

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
          {inputError && (
            <div role="alert" className="mb-4 p-4 bg-red-900/40 border border-red-700 text-red-200 rounded text-sm">
              {inputError}
            </div>
          )}
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
              {toolpathWarnings(result).map((w, i) => (
                <div key={i} role="alert" className="p-3 bg-amber-900/30 border border-amber-700 rounded text-xs text-amber-200">
                  Warning: {w}
                </div>
              ))}
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
                  <span className="text-xs text-gray-400 mb-1">LED Screen Flags (&gt;1.25x nominal)</span>
                  {result.laser_never_fires ? (
                    <span className="text-lg font-mono font-bold text-amber-400">no exposure</span>
                  ) : (
                    <span className={`text-lg font-mono font-bold ${result.hotspot_count > 0 ? 'text-red-400' : 'text-gray-200'}`}>
                      {result.hotspot_count}
                    </span>
                  )}
                </div>
              </div>

              {/* Hotspot & Energy Density Analizi */}
              <div className="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 className="text-sm font-semibold text-white mb-2">Average-LED Screen Flags</h3>
                <p className="text-xs text-gray-400 mb-4">
                  Galvanometer deceleration at vector endpoints causes average Linear Energy Density (LED = P/v) to exceed the nominal value. A segment is flagged when its average LED is more than 1.25x nominal; this is a screening rule and does not predict porosity or any melt-pool outcome.
                </p>

                {zeroFlagCaveat(result) ? (
                  <div className="p-3 bg-amber-900/20 border border-amber-800 rounded text-xs text-amber-200">
                    {zeroFlagCaveat(result)}
                  </div>
                ) : result.hotspot_count === 0 ? (
                  <div className="p-3 bg-gray-900 border border-gray-700 rounded text-xs text-gray-300">
                    No segment exceeds the 1.25x nominal LED screening threshold for the entered inputs.
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
                          <th className="p-2">LED above nominal</th>
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

/**
 * Feed-forward power tab (moved from the former Corner Power Compensation module): open-loop per-vector power
 * scaling from scanner kinematics, no sensor feedback. Toolpath text, format, default power/speed, acceleration and
 * jump speed are shared with the Kinematics tab.
 */
export const ToolpathFeedforwardPanel: React.FC<ToolpathSharedInputs> = ({
  toolpathText, setToolpathText, format, setFormat, defaultPower, setDefaultPower, defaultSpeed, setDefaultSpeed,
  accelMax, setAccelMax, jumpSpeed, active = true,
}) => {
  const [apply67Deg, setApply67Deg] = useState(true);
  const [layerIndex, setLayerIndex] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const inputError = toolpathDefaultsError(defaultPower, defaultSpeed);

  const handleMitigate = useCallback(async () => {
    if (toolpathDefaultsError(defaultPower, defaultSpeed)) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await pythonComputationService.processAdaptiveFeedforward({
        content: toolpathText,
        format,
        defaultPower_W: defaultPower,
        defaultSpeed_mms: defaultSpeed,
        accelMax_mms2: accelMax,
        jumpSpeed_mms: jumpSpeed,
        apply67DegRotation: apply67Deg,
        layerIndex,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Power scaling computation failed');
    } finally {
      setIsLoading(false);
    }
  }, [toolpathText, format, defaultPower, defaultSpeed, accelMax, jumpSpeed, apply67Deg, layerIndex]);

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-200">
      <div className="flex items-center justify-between p-4 bg-gray-800 border-b border-gray-700">
        <div>
          <h2 className="text-lg font-bold text-white">Corner Power Compensation</h2>
          <p className="text-sm text-gray-400">Open-loop per-vector power scaling from scanner kinematics (no sensor feedback) and optional 67° × layer scan rotation</p>
        </div>
        <button
          type="button"
          onClick={handleMitigate}
          disabled={isLoading || inputError !== null}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded font-medium disabled:opacity-50"
        >
          {isLoading ? 'Scaling Toolpath...' : 'Generate Power-Scaled G-Code'}
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-88 p-4 border-r border-gray-700 overflow-y-auto space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-300 uppercase mb-1">Source G-Code</label>
            <textarea aria-label="Source G-Code"
              rows={7}
              value={toolpathText}
              onChange={e => setToolpathText(e.target.value)}
              className="w-full bg-gray-950 font-mono text-[11px] p-2 rounded border border-gray-700 text-gray-200 focus:outline-none focus:border-indigo-500"
            />
            <div className="flex gap-2 mt-2">
              <button type="button" aria-pressed={format === 'gcode'} onClick={() => setFormat('gcode')}
                className={`flex-1 py-1 text-xs rounded border ${format === 'gcode' ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-gray-800 border-gray-700 text-gray-400'}`}>
                G-Code
              </button>
              <button type="button" aria-pressed={format === 'cli'} onClick={() => setFormat('cli')}
                className={`flex-1 py-1 text-xs rounded border ${format === 'cli' ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-gray-800 border-gray-700 text-gray-400'}`}>
                Common Layer (.cli)
              </button>
            </div>
            <button type="button" onClick={() => { setFormat('gcode'); setToolpathText(SAMPLE_FEEDFORWARD_GCODE); }}
              className="mt-2 w-full py-1 text-xs rounded border bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700">
              Load short-vector sample
            </button>
            <p className="text-[10px] text-gray-500 mt-1">The toolpath text, format, nominal power and speed, and acceleration are shared with the Kinematics tab.</p>
          </div>

          <div className="space-y-3 pt-2 border-t border-gray-800">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Scaling Controls</h3>

            <label className="block text-xs">
              <span className="text-gray-400">Nominal Laser Power (W)</span>
              <input
                type="range" min={100} max={600} step={10}
                value={Math.min(600, Math.max(100, defaultPower))} onChange={e => setDefaultPower(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-white text-xs">{defaultPower} W</div>
            </label>

            <label className="block text-xs">
              <span className="text-gray-400">Nominal Scan Speed (mm/s)</span>
              <input
                type="range" min={400} max={2500} step={50}
                value={Math.min(2500, Math.max(400, defaultSpeed))} onChange={e => setDefaultSpeed(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="text-right font-mono text-white text-xs">{defaultSpeed} mm/s</div>
            </label>

            <label className="block text-xs">
              <span className="text-gray-400">Galvo Max Acceleration (mm/s²)</span>
              <input
                type="range" min={10000} max={100000} step={5000}
                value={Math.min(100000, Math.max(10000, accelMax))} onChange={e => setAccelMax(Number(e.target.value))}
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
              <span className="text-[10px] text-gray-500 block mt-1">{rotationPreviewText(apply67Deg, layerIndex)}</span>
            </label>

            <p className="text-[10px] text-gray-500">
              Power is scaled once per vector as P × min(1, v_peak / v_nominal), so only vectors that never reach their commanded speed are scaled; vectors that do reach it keep nominal power at their deceleration ends. One S-word is written per vector; power is not ramped along the acceleration and deceleration phases inside a vector.
            </p>
          </div>
        </div>

        <div className="flex-1 p-6 overflow-y-auto bg-gray-950">
          {inputError && (
            <div role="alert" className="mb-4 p-4 bg-red-900/40 border border-red-700 text-red-200 rounded text-sm">
              {inputError}
            </div>
          )}
          {error && (
            <div role="alert" className="mb-4 p-4 bg-red-900/40 border border-red-700 text-red-200 rounded text-sm">
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
                    {energyChangeLabel(result.overall_energy_reduction_pct)}
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

              {active && (
                <div className="bg-gray-800 border border-gray-700 rounded p-4 h-72 flex flex-col">
                  <h3 className="text-sm font-semibold text-white mb-2">Per-Vector Power Scaling, first 25 segments (W)</h3>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={result.sample_segments}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="nominal_power_W" stroke="#9ca3af" tickFormatter={(_, idx) => `#${idx + 1}`} />
                      <YAxis stroke="#9ca3af" label={{ value: 'Laser Power (W)', angle: -90, position: 'insideLeft', fill: '#9ca3af' }} />
                      <Tooltip contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#f3f4f6' }} />
                      <Legend />
                      <Bar dataKey="nominal_power_W" name="Nominal Power (W)" fill="#ef4444" />
                      <Bar dataKey="compensated_power_W" name="Scaled Power (W)" fill="#10b981" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              <div className="bg-gray-800 border border-gray-700 rounded p-4">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="text-sm font-semibold text-white">Power-Scaled G-Code Output</h3>
                  <button
                    type="button"
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

const TOOLPATH_HASH = /^#\/?toolpath-studio(\?|$)/;

/** Scan Path Kinematics view: Kinematics and Feed-forward power tabs over one shared set of toolpath inputs. */
export const LpbfToolpathStudioLab: React.FC = () => {
  const [tab, setTab] = useState<ToolpathTab>(() =>
    typeof window === 'undefined' ? 'kinematics' : toolpathTabFromHash(window.location.hash));
  const [visited, setVisited] = useState<ReadonlySet<ToolpathTab>>(() => new Set<ToolpathTab>([tab]));
  const [toolpathText, setToolpathText] = useState(SAMPLE_GCODE);
  const [format, setFormat] = useState<'gcode' | 'cli'>('gcode');
  const [accelMax, setAccelMax] = useState(40000);
  const [jumpSpeed, setJumpSpeed] = useState(3000);
  const [defaultPower, setDefaultPower] = useState(280);
  const [defaultSpeed, setDefaultSpeed] = useState(1000);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const show = (next: ToolpathTab) => {
    setTab(next);
    setVisited(previous => new Set([...previous, next]));
  };
  const select = (next: ToolpathTab, focus = false) => {
    show(next);
    if (focus) refs.current[next]?.focus();
    try {
      if (TOOLPATH_HASH.test(window.location.hash)) window.history.replaceState(null, '', toolpathTabHash(next));
    } catch { /* The tab still switches without a shareable hash. */ }
  };
  // Back/forward and in-app links to #/toolpath-studio?tab=... select the tab.
  useEffect(() => {
    const onHash = () => {
      if (TOOLPATH_HASH.test(window.location.hash)) show(toolpathTabFromHash(window.location.hash));
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  const onKeyDown = (event: React.KeyboardEvent) => {
    const next = nextToolpathTab(tab, event.key);
    if (next === null) return;
    event.preventDefault();
    select(next, true);
  };

  const shared: ToolpathSharedInputs = {
    toolpathText, setToolpathText, format, setFormat, defaultPower, setDefaultPower, defaultSpeed, setDefaultSpeed,
    accelMax, setAccelMax, jumpSpeed, setJumpSpeed,
  };
  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-200">
      <div role="tablist" aria-label="Scan Path Kinematics" className="flex flex-wrap gap-2 border-b border-gray-700 bg-gray-900 px-4 pt-2" onKeyDown={onKeyDown}>
        {TOOLPATH_TABS.map(t => (
          <button
            key={t.id} ref={el => { refs.current[t.id] = el; }} type="button" role="tab" id={`toolpath-tab-${t.id}`}
            aria-selected={tab === t.id} aria-controls={`toolpath-panel-${t.id}`} tabIndex={tab === t.id ? 0 : -1}
            onClick={() => select(t.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${tab === t.id ? 'border-sky-400 text-sky-200' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="toolpath-panel-kinematics" aria-labelledby="toolpath-tab-kinematics" hidden={tab !== 'kinematics'} className="flex-1 min-h-0">
        {visited.has("kinematics") && <ToolpathKinematicsPanel {...shared} active={tab === "kinematics"} />}
      </div>
      <div role="tabpanel" id="toolpath-panel-feedforward" aria-labelledby="toolpath-tab-feedforward" hidden={tab !== 'feedforward'} className="flex-1 min-h-0">
        {visited.has("feedforward") && <ToolpathFeedforwardPanel {...shared} active={tab === "feedforward"} />}
      </div>
    </div>
  );
};
