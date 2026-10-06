import React, { useEffect, useState, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Line } from '@react-three/drei';
import * as THREE from 'three';
import { useMaterialSpecimenStore } from '../store/useMaterialSpecimenStore';

interface RaytracingResult {
  status: string;
  model_id: string;
  device: string;
  solve_time_ms: number;
  total_absorbed_W: number;
  total_escaped_W: number;
  total_truncated_W: number;
  absorption_efficiency: number;
  energy_balance_relative_error: number;
  sampling: { seed: number; num_rays: number; absorption_efficiency_standard_error: number; uncertainty_scope: string };
  limitations: string[];
  mesh: { vertices: number[]; indices: number[] };
  ray_paths: { points: [number, number, number][]; powers: number[] }[];
}

export const KeyholeRaytracingLab: React.FC = () => {
  const process = useMaterialSpecimenStore(state => state.activeSpecimen.lpbf);
  const updateProcess = useMaterialSpecimenStore(state => state.updateLpbfProcess);
  const [optics, setOptics] = useState({ keyhole_depth_um: 120, base_absorption: 0.35, max_bounces: 5, num_rays: 4096, seed: 0, device: 'cpu' });
  const [reply, setReply] = useState<{ request: string; data: RaytracingResult } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const request = JSON.stringify({ ...optics, power_W: process.laserPower_W, beam_radius_um: process.beamDiameter_um / 2, ui_ray_limit: 150 });
  // Hide old results in the same render that changes the inputs.
  const result = reply?.request === request ? reply.data : null;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setReply(null);
    setError(null);
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const response = await fetch('/api/python/lpbf-keyhole-raytracing', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: request, signal: controller.signal,
        });
        const data = await response.json();
        if (!response.ok || data.status !== 'success') throw new Error(data.error || 'Ray tracing failed');
        if (active) setReply({ request, data });
      } catch (failure) {
        if (active) setError(failure instanceof Error ? failure.message : 'Ray tracing failed');
      } finally {
        if (active) setLoading(false);
      }
    }, 300);
    // HTTP abort discards stale responses; cancelling worker computation still
    // requires queue integration, tracked separately in the Phase 0 audit.
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [request, attempt]);

  const geometry = useMemo(() => {
    if (!result) return null;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(result.mesh.vertices, 3));
    geo.setIndex(result.mesh.indices);
    geo.computeVertexNormals();
    return geo;
  }, [result]);
  useEffect(() => () => { geometry?.dispose(); }, [geometry]);

  const numberControl = (label: string, value: number, min: number, max: number, step: number, change: (value: number) => void) => (
    <label className="flex flex-col gap-1 text-xs text-gray-300">
      {label}
      <input aria-label={label} type="number" value={value} min={min} max={max} step={step}
        className="rounded border border-gray-600 bg-gray-800 p-2 text-white"
        onChange={event => { const next = event.currentTarget.valueAsNumber; if (Number.isFinite(next)) change(next); }} />
    </label>
  );

  return (
    <div className="grid min-h-[700px] grid-cols-1 gap-4 lg:grid-cols-[340px_1fr]">
      <section className="mk-plate space-y-4 p-5" aria-label="Keyhole optics controls and results">
        <h1 className="text-xl font-semibold">Keyhole Ray Tracing</h1>
        <p className="text-sm text-gray-400">Prescribed cavity optics. Power and beam diameter use the shared LPBF process.</p>
        <div className="grid grid-cols-2 gap-3">
          {numberControl('Laser power (W)', process.laserPower_W, 0, 1000, 10, value => updateProcess({ laserPower_W: value }))}
          {numberControl('Beam diameter (µm, 1/e²)', process.beamDiameter_um, 40, 300, 2, value => updateProcess({ beamDiameter_um: value }))}
          {numberControl('Cavity depth (µm)', optics.keyhole_depth_um, 0, 300, 5, value => setOptics(old => ({ ...old, keyhole_depth_um: value })))}
          {numberControl('Base absorption', optics.base_absorption, 0, 1, 0.01, value => setOptics(old => ({ ...old, base_absorption: value })))}
          {numberControl('Maximum bounces', optics.max_bounces, 1, 32, 1, value => setOptics(old => ({ ...old, max_bounces: value })))}
          {numberControl('Rays', optics.num_rays, 32, 100000, 256, value => setOptics(old => ({ ...old, num_rays: value })))}
          {numberControl('Random seed', optics.seed, 0, 4294967295, 1, value => setOptics(old => ({ ...old, seed: value })))}
          <label className="flex flex-col gap-1 text-xs text-gray-300">Backend
            <select aria-label="Backend" value={optics.device} className="rounded border border-gray-600 bg-gray-800 p-2" onChange={event => setOptics(old => ({ ...old, device: event.target.value }))}>
              <option value="cpu">Warp CPU</option><option value="cuda:0">Warp CUDA 0</option>
            </select>
          </label>
        </div>
        <p role="status" className="text-sm text-gray-400">{loading ? 'Computing ray paths…' : result ? `Computed on ${result.device}` : 'No computed result'}</p>
        {error && <div role="alert" className="rounded border border-red-700 p-3 text-sm text-red-300">{error}<button className="ml-3 underline" onClick={() => setAttempt(value => value + 1)}>Retry</button></div>}
        {result && <>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt>Absorption</dt><dd>{(result.absorption_efficiency * 100).toFixed(2)}%</dd>
            <dt>Absorbed power</dt><dd>{result.total_absorbed_W.toFixed(3)} W</dd>
            <dt>Escaped power</dt><dd>{result.total_escaped_W.toFixed(3)} W</dd>
            <dt>Bounce-limited power</dt><dd>{result.total_truncated_W.toFixed(3)} W</dd>
            <dt>Energy closure error</dt><dd>{(result.energy_balance_relative_error * 100).toExponential(2)}%</dd>
            <dt>Sampling standard error</dt><dd>{(result.sampling.absorption_efficiency_standard_error * 100).toFixed(3)} pp</dd>
            <dt>Solve time</dt><dd>{result.solve_time_ms.toFixed(1)} ms</dd>
          </dl>
          <p className="text-xs text-gray-400">{result.model_id} · seed {result.sampling.seed} · {result.sampling.num_rays} rays</p>
          <p className="text-xs text-gray-400">{result.sampling.uncertainty_scope}</p>
          <ul className="list-disc space-y-1 pl-4 text-xs text-amber-300">{result.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul>
        </>}
      </section>
      <div className="mk-labglass mk-hud min-h-[500px]" aria-label="Computed ray paths and prescribed cavity">
        <Canvas camera={{ position: [0.0003, 0.0003, 0.0002], fov: 45, near: 0.000001, far: 0.01 }}>
          {/* Light lab-glass viewport (porcelain): pearl background, graphite grid, cobalt cavity, laser-orange rays. */}
          <color attach="background" args={['#eef0f3']} />
          <ambientLight intensity={0.8} />
          <directionalLight position={[1, 1, 1]} intensity={1.5} />
          <OrbitControls target={[0, 0, -0.00005]} makeDefault />
          {geometry && <mesh geometry={geometry}><meshStandardMaterial color="#2346b0" transparent opacity={0.55} roughness={0.35} metalness={0.2} side={THREE.DoubleSide} /></mesh>}
          {result?.ray_paths.filter(path => path.points.length > 1).map((path, index) => (
            <Line key={index} points={path.points} color="#ff5b1f" lineWidth={1} transparent opacity={0.55} />
          ))}
          <gridHelper args={[0.001, 20, '#9aa1ab', '#c9ced6']} rotation={[Math.PI / 2, 0, 0]} />
        </Canvas>
      </div>
    </div>
  );
};
