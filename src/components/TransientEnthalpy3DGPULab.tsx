import React, { useState } from 'react';
import { Activity, Flame, Layers, Play } from 'lucide-react';
import { pythonComputationService } from '../services/pythonComputationService';
import { transientGpuMaterialInputs, type AuthorityAlloyId } from '../data/lpbfMaterialAuthority';

type SlotProps = { children: React.ReactNode; className?: string };
const Card = ({ children, className = '' }: SlotProps) => <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>{children}</section>;
const CardHeader = ({ children, className = '' }: SlotProps) => <header className={`border-b border-slate-100 bg-slate-50 p-4 ${className}`}>{children}</header>;
const CardContent = ({ children, className = '' }: SlotProps) => <div className={`p-4 ${className}`}>{children}</div>;
const CardTitle = ({ children, className = '' }: SlotProps) => <h2 className={`font-semibold text-slate-800 ${className}`}>{children}</h2>;
const Button = (props: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button {...props} className={`rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50 ${props.className ?? ''}`} />;
const Input = (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} className={`w-full rounded border border-slate-300 px-2 py-1.5 text-sm ${props.className ?? ''}`} />;
const Select = (props: React.SelectHTMLAttributes<HTMLSelectElement>) => <select {...props} className={`w-full rounded border border-slate-300 px-2 py-1.5 text-sm bg-white ${props.className ?? ''}`} />;
const Label = ({ children }: SlotProps) => <span className="block text-xs text-slate-500">{children}</span>;

// Material inputs come from the Python authority (src/generated/lpbfMaterialAuthority.json); no alloy numbers here.
const MATERIALS = {
  "Ti-6Al-4V": "ti6al4v",
  "IN718": "in718",
  "316L": "ss316l",
  "AlSi10Mg": "alsi10mg",
} as const satisfies Record<string, AuthorityAlloyId>;

export function TransientEnthalpy3DGPULab() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [params, setParams] = useState({
    nx: 64, ny: 64, nz: 32,
    dx: 2.0, dy: 2.0, dz: 2.0,
    power_W: 200.0,
    T_preheat_K: 300.0,
    material: "Ti-6Al-4V" as keyof typeof MATERIALS
  });

  const handleSimulate = async () => {
    setLoading(true);
    try {
      const mat = transientGpuMaterialInputs(MATERIALS[params.material]);
      const dx_m = params.dx * 1e-6;
      const dy_m = params.dy * 1e-6;
      const dz_m = params.dz * 1e-6;
      setResult(await pythonComputationService.computeTransient3DGPU({
        nx: params.nx, ny: params.ny, nz: params.nz,
        dx: dx_m, dy: dy_m, dz: dz_m,
        power_W: params.power_W,
        T_preheat_K: params.T_preheat_K,
        toolpath: {
          t: [0.0, 100e-6],
          x: [params.nx * dx_m * 0.25, params.nx * dx_m * 0.75],
          y: [params.ny * dy_m * 0.5, params.ny * dy_m * 0.5],
          p: [params.power_W, params.power_W]
        },
        rho: mat.rho,
        L_f: mat.L_f,
        T_solidus: mat.T_solidus,
        T_liquidus: mat.T_liquidus,
        cp_solid: mat.cp_solid,
        cp_liquid: mat.cp_liquid,
        k_solid: mat.k_solid,
        k_liquid: mat.k_liquid
      }));
    } finally {
      setLoading(false);
    }
  };

  return <div className="mx-auto max-w-6xl space-y-6 p-6">
    <header>
      <h1 className="flex items-center gap-2 text-3xl font-bold text-slate-800"><Flame className="h-8 w-8 text-blue-600" />Phase 22: Transient 3D GPU Solver</h1>
      <p className="mt-1 text-slate-500">High-performance 3D melt pool simulation using NVIDIA Warp.</p>
    </header>
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <Card><CardHeader><CardTitle className="flex items-center gap-2 text-lg"><Layers className="h-5 w-5" />Simulation Parameters</CardTitle></CardHeader><CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <label className="space-y-1 text-sm"><Label>Material</Label><Select value={params.material} onChange={e => setParams({...params, material: e.target.value as any})}><option value="Ti-6Al-4V">Ti-6Al-4V</option><option value="IN718">IN718</option><option value="316L">316L</option><option value="AlSi10Mg">AlSi10Mg</option></Select></label>
          <label className="space-y-1 text-sm"><Label>Power (W)</Label><Input type="number" value={params.power_W} onChange={e => setParams({...params, power_W: Number(e.target.value)})} /></label>
          <label className="space-y-1 text-sm"><Label>Preheat Temp (K)</Label><Input type="number" value={params.T_preheat_K} onChange={e => setParams({...params, T_preheat_K: Number(e.target.value)})} /></label>
          <label className="space-y-1 text-sm"><Label>Grid Nx</Label><Input type="number" value={params.nx} onChange={e => setParams({...params, nx: Number(e.target.value)})} /></label>
          <label className="space-y-1 text-sm"><Label>Grid Ny</Label><Input type="number" value={params.ny} onChange={e => setParams({...params, ny: Number(e.target.value)})} /></label>
          <label className="space-y-1 text-sm"><Label>Grid Nz</Label><Input type="number" value={params.nz} onChange={e => setParams({...params, nz: Number(e.target.value)})} /></label>
          <label className="space-y-1 text-sm"><Label>Cell dx (µm)</Label><Input type="number" step="0.1" value={params.dx} onChange={e => setParams({...params, dx: Number(e.target.value)})} /></label>
          <label className="space-y-1 text-sm"><Label>Cell dz (µm)</Label><Input type="number" step="0.1" value={params.dz} onChange={e => setParams({...params, dz: Number(e.target.value)})} /></label>
        </div>
        <Button onClick={handleSimulate} disabled={loading} className="w-full">{loading ? <Activity className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}Run GPU Simulation</Button>
      </CardContent></Card>
      <Card className="lg:col-span-2"><CardHeader><CardTitle>Results & Diagnostics</CardTitle></CardHeader><CardContent>
        {!result ? <div className="py-24 text-center text-slate-400"><p>Configure parameters and run the 3D solver.</p></div> : <div className="grid grid-cols-2 md:grid-cols-3 gap-6 text-center">
          <div><p className="text-sm text-slate-500">Melt Volume</p><p className="text-2xl font-bold">{result.melt_volume_um3?.toExponential(2)} µm³</p></div>
          <div><p className="text-sm text-slate-500">Max Temperature</p><p className="text-2xl font-bold">{result.max_temperature_K?.toFixed(0)} K</p></div>
          <div><p className="text-sm text-slate-500">Keyhole Depth</p><p className="text-2xl font-bold">{result.keyhole_depth_um?.toFixed(1)} µm</p></div>
          <div><p className="text-sm text-slate-500">Compute Time</p><p className="text-2xl font-bold">{result.sim_time_s?.toFixed(3)} s</p></div>
          <div><p className="text-sm text-slate-500">Time Steps</p><p className="text-2xl font-bold">{result.steps}</p></div>
          <div><p className="text-sm text-slate-500">Device</p><p className="text-lg font-bold truncate px-2">{result.device}</p></div>
        </div>}
      </CardContent></Card>
    </div>
  </div>;
}
