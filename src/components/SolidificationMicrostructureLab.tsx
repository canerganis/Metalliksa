/**
 * SolidificationMicrostructureLab.tsx — Phase 8
 * LPBF solidification analysis with G/R map, dendrite spacing, morphology,
 * and diagnostics. Numerical work remains in pythonComputationService.
 */

import React, { useState, useCallback } from 'react';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, BarChart, Bar, Cell,
  PieChart, Pie, Legend, LabelList,
} from 'recharts';
import { pythonComputationService } from '../services/pythonComputationService';
import type { SolidificationMicrostructureResult } from '../services/pythonComputationService';

const ALLOY_DEFAULTS: Record<string, { k_WmK: number; liquidus_K: number; absorptivity: number }> = {
  'Inconel 718': { k_WmK: 14.7, liquidus_K: 1609, absorptivity: 0.35 },
  'Ti-6Al-4V': { k_WmK: 7.0, liquidus_K: 1933, absorptivity: 0.40 },
  'AlSi10Mg': { k_WmK: 160.0, liquidus_K: 850, absorptivity: 0.09 },
  '316L SS': { k_WmK: 16.0, liquidus_K: 1727, absorptivity: 0.35 },
};

const MORPHOLOGY_COLORS: Record<string, string> = {
  columnar: '#75b8ff', equiaxed: '#70d8b0', mixed: '#f0bd73',
};

// Hunt G/R boundary curves: columnar/mixed G/R = 1e8; mixed/equiaxed G/R = 1e6.
const GR_SCATTER = Array.from({ length: 40 }, (_, i) => {
  const R = Math.exp(Math.log(1e-5) + (i / 39) * Math.log(2 / 1e-5));
  return { R_ms: R, G_col: 1e8 * R, G_eq: 1e6 * R };
});

const panelClass = 'rounded-2xl border border-white/10 bg-[#111b25] shadow-[0_18px_50px_rgba(0,0,0,.18)]';
const mutedText = 'text-slate-400';

const Metric: React.FC<{ label: string; value: string; unit?: string; accent: string; detail?: string }> = ({ label, value, unit, accent, detail }) => (
  <div className="min-w-0 rounded-xl border border-white/[0.08] bg-[#0c151e] px-4 py-3">
    <div className="mb-2 flex items-center gap-2">
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: accent, boxShadow: `0 0 12px ${accent}88` }} />
      <span className="truncate text-[11px] font-semibold uppercase tracking-[.12em] text-slate-400">{label}</span>
    </div>
    <div className="flex flex-wrap items-baseline gap-x-1.5">
      <span className="font-mono text-xl font-semibold tracking-tight text-slate-100">{value}</span>
      {unit && <span className="text-xs text-slate-500">{unit}</span>}
    </div>
    {detail && <p className="mt-1 text-[11px] text-slate-500">{detail}</p>}
  </div>
);

interface Props {
  onSendToModule?: (moduleId: string, data: unknown) => void;
}

type ChartTab = 'gr-map' | 'spacing' | 'morphology' | 'diagnostics';

export const SolidificationMicrostructureLab: React.FC<Props> = () => {
  const [laserPower, setLaserPower] = useState(285);
  const [scanSpeed, setScanSpeed] = useState(960);
  const [hatch, setHatch] = useState(110);
  const [layerThickness, setLayerThickness] = useState(40);
  const [selectedAlloy, setSelectedAlloy] = useState('Inconel 718');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<SolidificationMicrostructureResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ChartTab>('gr-map');

  const alloyProps = ALLOY_DEFAULTS[selectedAlloy] ?? ALLOY_DEFAULTS['Inconel 718'];
  const invalidateResult = () => {
    setResult(null);
    setError(null);
  };

  const handleCompute = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await pythonComputationService.computeSolidificationMicrostructure({
        params: {
          power_W: laserPower,
          speed_mm_s: scanSpeed,
          hatch_um: hatch,
          layerThickness_um: layerThickness,
        },
        material: {
          k_WmK: alloyProps.k_WmK,
          liquidus_K: alloyProps.liquidus_K,
          absorptivity: alloyProps.absorptivity,
        },
      });
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Computation failed. Check the service and try again.');
    } finally {
      setIsLoading(false);
    }
  }, [laserPower, scanSpeed, hatch, layerThickness, alloyProps]);

  const grPoint = result ? [{ R_ms: result.R_m_s, G_K_m: result.G_K_m }] : [];
  const spacingData = result ? [
    { name: 'PDAS · λ₁', value: result.PDAS_um },
    { name: 'SDAS · λ₂', value: result.SDAS_um },
  ] : [];
  const morphData = result
    ? (Object.entries(result.morphologyFractions) as [string, number][])
      .filter(([, value]) => value > 0.005)
      .map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        value: parseFloat((value * 100).toFixed(1)),
        fill: MORPHOLOGY_COLORS[name] ?? '#9aa7b5',
      }))
    : [];
  const morphColor = result ? MORPHOLOGY_COLORS[result.morphology] ?? '#9aa7b5' : '#9aa7b5';

  const tabs: { id: ChartTab; label: string; index: string }[] = [
    { id: 'gr-map', label: 'G–R map', index: '01' },
    { id: 'spacing', label: 'Dendrite spacing', index: '02' },
    { id: 'morphology', label: 'Morphology', index: '03' },
    { id: 'diagnostics', label: 'Diagnostics', index: '04' },
  ];

  const numberField = (label: string, value: number, min: number, max: number, step: number, unit: string, update: (value: number) => void) => (
    <label className="block min-w-0">
      <span className="mb-2 flex items-center justify-between gap-2 text-xs font-medium text-slate-300">
        <span>{label}</span><span className="text-[10px] font-normal text-slate-500">{unit}</span>
      </span>
      <input
        type="number" value={value} min={min} max={max} step={step}
        aria-label={`${label} (${unit})`}
        onChange={event => {
          if (event.target.value === '') return;
          const next = Number(event.target.value);
          update(Number.isFinite(next) ? next : min);
          invalidateResult();
        }}
        onBlur={event => {
          const next = Number(event.target.value);
          const bounded = Number.isFinite(next) ? Math.min(max, Math.max(min, next)) : min;
          if (bounded !== value) {
            update(bounded);
            invalidateResult();
          }
        }}
        className="w-full rounded-lg border border-white/10 bg-[#0b141d] px-3 py-2.5 font-mono text-sm text-slate-100 outline-none transition focus:border-cyan-300/60 focus:ring-2 focus:ring-cyan-300/10"
      />
      <span className="mt-1.5 block text-[10px] text-slate-500">{min}–{max} {unit}</span>
    </label>
  );

  return (
    <div className="flex h-full min-h-0 flex-col gap-5 overflow-y-auto bg-[#0a1118] p-4 text-slate-100 sm:p-6 lg:p-7">
      <header className={`${panelClass} relative isolate overflow-hidden p-5 sm:p-7`}>
        <div aria-hidden="true" className="pointer-events-none absolute -right-20 -top-32 -z-10 h-80 w-80 rounded-full border border-cyan-200/10 bg-[radial-gradient(circle_at_center,rgba(90,195,214,.16),rgba(90,195,214,0)_68%)]" />
        <div aria-hidden="true" className="pointer-events-none absolute bottom-0 right-[8%] -z-10 h-px w-2/5 bg-gradient-to-l from-cyan-200/40 to-transparent" />
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-3xl">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-cyan-100/15 bg-cyan-100/[.06] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[.19em] text-cyan-100/80">Phase 08 · Microstructure</span>
              <span className="text-[10px] uppercase tracking-[.15em] text-slate-500">LPBF process study</span>
            </div>
            <h1 className="font-serif text-3xl font-medium tracking-tight text-white sm:text-4xl">Solidification atlas</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400 sm:text-[15px]">
              Follow the thermal gradient into the solidification front, then read its signature in dendrite spacing and morphology.
            </p>
          </div>
          <div className="flex min-w-[152px] items-center gap-3 rounded-xl border border-white/[.08] bg-black/15 px-3 py-2.5">
            <span className={`relative flex h-2.5 w-2.5 ${isLoading ? '' : 'animate-pulse'}`}>
              <span className={`absolute inline-flex h-full w-full rounded-full ${isLoading ? 'bg-amber-300/50' : 'bg-emerald-300/40'}`} />
              <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${isLoading ? 'bg-amber-300' : 'bg-emerald-300'}`} />
            </span>
            <div>
              <div className="text-xs font-semibold text-slate-200">{isLoading ? 'Solver running' : result ? 'Analysis ready' : 'Ready to analyse'}</div>
              <div className="mt-0.5 text-[10px] text-slate-500">{result ? `${result.frontCellCount.toLocaleString()} front cells` : 'Configure the process below'}</div>
            </div>
          </div>
        </div>
        <div className="mt-6 grid max-w-3xl grid-cols-3 gap-2 border-t border-white/[.08] pt-4 sm:gap-6">
          {[
            ['01', 'THERMAL FIELD'], ['02', 'DENDRITE SCALE'], ['03', 'GRAIN CHARACTER'],
          ].map(([step, title]) => (
            <div key={step} className="flex items-center gap-2 sm:gap-3">
              <span className="font-mono text-xs text-cyan-200/75">{step}</span>
              <span className="text-[9px] font-semibold tracking-[.09em] text-slate-500 sm:text-[10px]">{title}</span>
            </div>
          ))}
        </div>
      </header>

      <section className={`${panelClass} p-4 sm:p-5`} aria-labelledby="process-heading">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-[.17em] text-cyan-200/70">01 / Process definition</div>
            <h2 id="process-heading" className="text-lg font-semibold tracking-tight text-slate-100">Set the operating point</h2>
          </div>
          <p className="max-w-md text-xs leading-5 text-slate-500">Changing a setting clears the previous result so the displayed analysis always matches these inputs.</p>
        </div>

        <div className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2 xl:grid-cols-6">
          <label className="block min-w-0 xl:col-span-2">
            <span className="mb-2 flex items-center justify-between text-xs font-medium text-slate-300"><span>Material preset</span><span className="text-[10px] text-slate-500">THERMAL PROPERTIES</span></span>
            <select
              aria-label="Material preset"
              className="w-full rounded-lg border border-white/10 bg-[#0b141d] px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-cyan-300/60 focus:ring-2 focus:ring-cyan-300/10"
              value={selectedAlloy}
              onChange={event => { setSelectedAlloy(event.target.value); invalidateResult(); }}
            >
              {Object.keys(ALLOY_DEFAULTS).map(alloy => <option key={alloy} value={alloy}>{alloy}</option>)}
            </select>
            <span className="mt-1.5 block text-[10px] text-slate-500">Preset supplies k, liquidus and absorptivity</span>
          </label>
          {numberField('Laser power', laserPower, 50, 1000, 5, 'W', setLaserPower)}
          {numberField('Scan speed', scanSpeed, 100, 3000, 10, 'mm/s', setScanSpeed)}
          {numberField('Hatch spacing', hatch, 50, 300, 5, 'µm', setHatch)}
          {numberField('Layer thickness', layerThickness, 20, 120, 5, 'µm', setLayerThickness)}
        </div>

        <div className="mt-5 flex flex-col-reverse gap-3 border-t border-white/[.07] pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-[11px] leading-5 text-slate-500">Model properties: <span className="font-mono text-slate-400">k {alloyProps.k_WmK} W/m·K</span><span className="mx-2 text-slate-700">·</span><span className="font-mono text-slate-400">Tₗ {alloyProps.liquidus_K} K</span><span className="mx-2 text-slate-700">·</span><span className="font-mono text-slate-400">A {alloyProps.absorptivity}</span></p>
          <button
            type="button" onClick={handleCompute} disabled={isLoading}
            className="group inline-flex min-h-11 items-center justify-center gap-3 rounded-lg border border-cyan-100/20 bg-gradient-to-r from-cyan-200/15 to-blue-300/10 px-5 text-sm font-semibold text-cyan-50 shadow-[0_8px_24px_rgba(26,156,180,.08)] transition hover:border-cyan-100/40 hover:from-cyan-200/20 hover:to-blue-300/15 disabled:cursor-wait disabled:opacity-60"
          >
            <span aria-hidden="true" className={isLoading ? 'animate-spin' : ''}>{isLoading ? '◌' : '↗'}</span>
            {isLoading ? 'Calculating field…' : 'Run solidification analysis'}
          </button>
        </div>
      </section>

      {error && (
        <section role="alert" className="flex items-start gap-3 rounded-xl border border-rose-300/20 bg-rose-400/[.07] px-4 py-3.5 text-sm text-rose-100">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-rose-200/30 text-xs">!</span>
          <div className="min-w-0"><h2 className="font-semibold">Analysis could not be completed</h2><p className="mt-1 break-words text-xs leading-5 text-rose-100/70">{error}</p></div>
        </section>
      )}

      {isLoading && (
        <section role="status" aria-live="polite" className={`${panelClass} flex min-h-48 flex-col items-center justify-center gap-4 px-5 py-8 text-center`}>
          <div className="relative flex h-12 w-12 items-center justify-center rounded-full border border-cyan-100/20">
            <span className="absolute inset-1 animate-spin rounded-full border border-transparent border-t-cyan-200/80" />
            <span className="h-2 w-2 rounded-full bg-cyan-100 shadow-[0_0_18px_5px_rgba(103,221,232,.3)]" />
          </div>
          <div><h2 className="font-medium text-slate-100">Tracing the solidification front</h2><p className="mt-1 text-xs text-slate-500">Estimating thermal gradients, growth rate and microstructure scales…</p></div>
          <div className="h-1 w-48 overflow-hidden rounded-full bg-white/[.07]"><div className="h-full w-2/3 animate-pulse rounded-full bg-gradient-to-r from-cyan-300/30 via-cyan-200 to-blue-300/30" /></div>
        </section>
      )}

      {!result && !isLoading && !error && (
        <section className={`${panelClass} relative flex min-h-56 items-center overflow-hidden px-5 py-8 sm:min-h-64 sm:px-10`}>
          <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-0 hidden w-2/5 opacity-70 sm:block">
            <div className="absolute right-12 top-1/2 h-48 w-48 -translate-y-1/2 rounded-full border border-cyan-100/[.08]" />
            <div className="absolute right-20 top-1/2 h-32 w-32 -translate-y-1/2 rounded-full border border-cyan-100/[.12]" />
            <div className="absolute right-28 top-1/2 h-16 w-16 -translate-y-1/2 rounded-full border border-cyan-100/[.2] bg-[radial-gradient(circle,rgba(96,210,222,.2),rgba(96,210,222,0)_70%)]" />
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 420 220" fill="none" aria-hidden="true">
              <path d="M5 173C76 170 82 48 156 53s79 119 143 98 66-87 116-91" stroke="rgba(111,215,224,.42)" strokeWidth="1.3" />
              <path d="M10 195c70-2 85-100 145-95 65 5 79 82 136 68 53-13 79-68 123-71" stroke="rgba(111,215,224,.18)" strokeWidth="1" strokeDasharray="3 6" />
              <path d="M80 26v166M164 26v166M248 26v166M332 26v166" stroke="rgba(255,255,255,.045)" />
            </svg>
          </div>
          <div className="relative max-w-lg">
            <div className="mb-3 text-[10px] font-semibold uppercase tracking-[.18em] text-cyan-100/70">Your analysis canvas</div>
            <h2 className="text-xl font-semibold tracking-tight text-slate-100 sm:text-2xl">A process window, made visible.</h2>
            <p className="mt-2 max-w-md text-sm leading-6 text-slate-400">Choose a material and operating point, then run the analysis to reveal the G–R regime, dendrite scales and estimated morphology.</p>
            <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-[11px] text-slate-500"><span><b className="mr-1.5 text-cyan-100/70">01</b>Thermal field</span><span><b className="mr-1.5 text-cyan-100/70">02</b>Cell spacing</span><span><b className="mr-1.5 text-cyan-100/70">03</b>Morphology</span></div>
          </div>
        </section>
      )}

      {result && !isLoading && (
        <>
          <section aria-label="Analysis summary" className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            <Metric label="Thermal gradient" value={result.G_K_m.toExponential(2)} unit="K/m" accent="#75b8ff" detail="mean at front" />
            <Metric label="Solidification rate" value={result.R_m_s.toExponential(2)} unit="m/s" accent="#70d8b0" detail="local growth rate" />
            <Metric label="Cooling rate" value={result.coolingRate_K_s.toExponential(2)} unit="K/s" accent="#f08080" detail="thermal response" />
            <Metric label="Primary spacing · λ₁" value={result.PDAS_um.toFixed(2)} unit="µm" accent="#bba3f4" detail="PDAS estimate" />
            <Metric label="Secondary spacing · λ₂" value={result.SDAS_um.toFixed(2)} unit="µm" accent="#f0bd73" detail="SDAS estimate" />
            <Metric label="Front morphology" value={result.morphology} accent={morphColor} detail={result.source.includes('rosenthal') ? 'analytical source' : 'CFD source'} />
          </section>

          <section className={`${panelClass} min-h-[420px] overflow-hidden`} aria-label="Analysis visualisations">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[.07] px-4 py-4 sm:px-5">
              <div><div className="text-[10px] font-semibold uppercase tracking-[.17em] text-cyan-100/65">02 / Read the result</div><h2 className="mt-1 text-base font-semibold text-slate-100">Solidification response</h2></div>
              <nav className="flex max-w-full gap-1 overflow-x-auto rounded-xl border border-white/[.07] bg-[#0b141d] p-1" aria-label="Result views">
                {tabs.map(tab => (
                  <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} aria-current={activeTab === tab.id ? 'page' : undefined}
                    className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs transition ${activeTab === tab.id ? 'bg-cyan-100/[.12] text-cyan-50 shadow-sm' : 'text-slate-500 hover:text-slate-200'}`}>
                    <span className="mr-1.5 font-mono text-[9px] opacity-55">{tab.index}</span>{tab.label}
                  </button>
                ))}
              </nav>
            </div>

            <div className="px-4 pb-5 pt-4 sm:px-5">
              {activeTab === 'gr-map' && <>
                <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                  <div><h3 className="text-sm font-medium text-slate-200">Thermal gradient vs. growth rate</h3><p className="mt-1 text-xs text-slate-500">Hunt morphology regime map · logarithmic axes</p></div>
                  <div className="flex flex-wrap gap-3 text-[10px] text-slate-400"><span className="flex items-center gap-1.5"><i className="h-0.5 w-4 bg-blue-300" />Columnar / mixed</span><span className="flex items-center gap-1.5"><i className="h-0.5 w-4 bg-emerald-300" />Mixed / equiaxed</span><span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full" style={{ background: morphColor }} />Operating point</span></div>
                </div>
                <div className="h-[300px] w-full sm:h-[360px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 10, right: 18, bottom: 16, left: 12 }}>
                      <CartesianGrid strokeDasharray="2 6" stroke="#263744" />
                      <XAxis dataKey="R_ms" type="number" scale="log" domain={[1e-5, 2]} name="R (m/s)" tickFormatter={v => Number(v).toExponential(0)} tick={{ fill: '#8595a3', fontSize: 10 }} axisLine={{ stroke: '#3a4a57' }} tickLine={false} label={{ value: 'Growth rate R (m/s)', position: 'insideBottom', offset: -8, fill: '#91a0ad', fontSize: 11 }} />
                      <YAxis dataKey="G_K_m" type="number" scale="log" domain={[1e4, 1e10]} name="G (K/m)" tickFormatter={v => Number(v).toExponential(0)} tick={{ fill: '#8595a3', fontSize: 10 }} axisLine={false} tickLine={false} label={{ value: 'Thermal gradient G (K/m)', angle: -90, position: 'insideLeft', fill: '#91a0ad', fontSize: 11 }} />
                      <Tooltip cursor={{ stroke: '#9ab5c5', strokeDasharray: '3 4' }} formatter={(value: number, name: string) => [Number(value).toExponential(3), name]} contentStyle={{ background: '#111b25', border: '1px solid #354653', borderRadius: '10px', color: '#edf4f7', fontSize: 12 }} />
                      {GR_SCATTER.slice(0, -1).map((point, index) => <ReferenceLine key={`columnar-${index}`} segment={[{ x: point.R_ms, y: point.G_col }, { x: GR_SCATTER[index + 1].R_ms, y: GR_SCATTER[index + 1].G_col }]} stroke="#75b8ff" strokeDasharray="4 4" strokeOpacity={0.55} />)}
                      {GR_SCATTER.slice(0, -1).map((point, index) => <ReferenceLine key={`equiaxed-${index}`} segment={[{ x: point.R_ms, y: point.G_eq }, { x: GR_SCATTER[index + 1].R_ms, y: GR_SCATTER[index + 1].G_eq }]} stroke="#70d8b0" strokeDasharray="4 4" strokeOpacity={0.55} />)}
                      <Scatter data={grPoint} dataKey="G_K_m" fill={morphColor} name="Operating point" shape="star" />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-2 border-t border-white/[.06] pt-3 text-[11px] leading-5 text-slate-500">Boundary curves show Hunt G/R criteria (G/R = 10⁸ and 10⁶); the marker locates this operating point. They indicate a model regime, not a measured grain structure.</p>
              </>}

              {activeTab === 'spacing' && <>
                <div className="mb-3"><h3 className="text-sm font-medium text-slate-200">Dendrite spacing estimates</h3><p className="mt-1 text-xs text-slate-500">Primary and secondary arm spacing returned by the selected model.</p></div>
                <div className="h-[300px] w-full sm:h-[350px]">
                  <ResponsiveContainer width="100%" height="100%"><BarChart data={spacingData} margin={{ top: 24, right: 18, bottom: 8, left: 4 }}>
                    <CartesianGrid vertical={false} strokeDasharray="2 6" stroke="#263744" />
                    <XAxis dataKey="name" tick={{ fill: '#aab7c1', fontSize: 12 }} axisLine={{ stroke: '#3a4a57' }} tickLine={false} />
                    <YAxis unit=" µm" tick={{ fill: '#8595a3', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <Tooltip formatter={(value: number) => [`${value.toFixed(2)} µm`, 'Estimate']} contentStyle={{ background: '#111b25', border: '1px solid #354653', borderRadius: '10px', color: '#edf4f7', fontSize: 12 }} />
                    <Bar dataKey="value" name="Spacing" radius={[7, 7, 2, 2]} maxBarSize={96}>
                      {spacingData.map((entry, index) => <Cell key={entry.name} fill={index === 0 ? '#bba3f4' : '#f0bd73'} />)}
                      <LabelList dataKey="value" position="top" formatter={(value: number) => `${value.toFixed(2)} µm`} fill="#dbe6ec" fontSize={11} />
                    </Bar>
                  </BarChart></ResponsiveContainer>
                </div>
                <p className="mt-2 border-t border-white/[.06] pt-3 text-[11px] leading-5 text-slate-500">Typical LPBF literature ranges (PDAS 1–30 µm; SDAS 0.5–15 µm) are context only and are not acceptance limits for this result.</p>
              </>}

              {activeTab === 'morphology' && <>
                <div className="mb-3"><h3 className="text-sm font-medium text-slate-200">Estimated morphology fractions</h3><p className="mt-1 text-xs text-slate-500">Classification at the solidification front from the G/R criterion.</p></div>
                <div className="grid items-center gap-4 md:grid-cols-[minmax(0,1fr)_minmax(220px,.8fr)]">
                  <div className="h-[280px] w-full sm:h-[340px]"><ResponsiveContainer width="100%" height="100%"><PieChart>
                    <Pie data={morphData} cx="50%" cy="50%" outerRadius="76%" innerRadius="54%" paddingAngle={3} dataKey="value" stroke="#111b25" strokeWidth={3}>
                      {morphData.map((entry, index) => <Cell key={`morph-${index}`} fill={entry.fill} />)}
                    </Pie>
                    <Tooltip formatter={(value: number) => [`${value}%`, 'Estimated fraction']} contentStyle={{ background: '#111b25', border: '1px solid #354653', borderRadius: '10px', color: '#edf4f7', fontSize: 12 }} />
                  </PieChart></ResponsiveContainer></div>
                  <div className="space-y-2">
                    {morphData.map(item => <div key={item.name} className="flex items-center justify-between gap-3 rounded-xl border border-white/[.07] bg-[#0b141d] px-4 py-3"><div className="flex items-center gap-2.5"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.fill }} /><span className="text-sm text-slate-300">{item.name}</span></div><span className="font-mono text-sm text-slate-100">{item.value.toFixed(1)}%</span></div>)}
                    {!morphData.length && <p className="text-sm text-slate-400">No morphology fractions above the display threshold.</p>}
                  </div>
                </div>
                <p className="mt-2 border-t border-white/[.06] pt-3 text-[11px] leading-5 text-slate-500">Fractions are model estimates; they should not be interpreted as direct microscopy measurements.</p>
              </>}

              {activeTab === 'diagnostics' && <>
                <div className="mb-3"><h3 className="text-sm font-medium text-slate-200">Model diagnostics</h3><p className="mt-1 text-xs text-slate-500">Field summary, result provenance and scientific caveats.</p></div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-white/[.07] bg-[#0b141d] p-4">
                    <h4 className="mb-3 text-[10px] font-semibold uppercase tracking-[.16em] text-cyan-100/70">Thermal field</h4>
                    <dl className="space-y-2">
                      {[
                        ['G · mean', `${result.G_K_m.toExponential(3)} K/m`], ['G · max', `${result.maxG_K_m.toExponential(3)} K/m`],
                        ['R · mean', `${result.R_m_s.toExponential(3)} m/s`], ['R · max', `${result.maxR_m_s.toExponential(3)} m/s`],
                        ['Cooling rate', `${result.coolingRate_K_s.toExponential(3)} K/s`],
                      ].map(([label, value]) => <div key={label} className="flex justify-between gap-3 border-b border-white/[.05] pb-2 text-xs"><dt className="text-slate-500">{label}</dt><dd className="font-mono text-slate-200">{value}</dd></div>)}
                    </dl>
                  </div>
                  <div className="rounded-xl border border-white/[.07] bg-[#0b141d] p-4">
                    <h4 className="mb-3 text-[10px] font-semibold uppercase tracking-[.16em] text-cyan-100/70">Microstructure & provenance</h4>
                    <dl className="space-y-2">
                      {[
                        ['PDAS · λ₁', `${result.PDAS_um.toFixed(2)} µm`], ['SDAS · λ₂', `${result.SDAS_um.toFixed(2)} µm`],
                        ['Morphology', result.morphology], ['Front cells', result.frontCellCount.toLocaleString()],
                        ['Calculation source', result.source.includes('rosenthal') ? 'Rosenthal analytical' : 'OpenFOAM CFD'],
                      ].map(([label, value]) => <div key={label} className="flex justify-between gap-3 border-b border-white/[.05] pb-2 text-xs"><dt className="text-slate-500">{label}</dt><dd className="text-right font-mono text-slate-200">{value}</dd></div>)}
                    </dl>
                  </div>
                </div>
                <div className="mt-3 rounded-xl border border-amber-100/10 bg-amber-100/[.035] p-4">
                  <h4 className="mb-1 text-xs font-semibold text-amber-100/80">Interpret with care</h4>
                  <p className="text-xs leading-5 text-slate-400">{result.disclaimer}</p>
                </div>
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-[10px] text-slate-500"><span>Hunt–Lu PDAS · DOI {result.doi.pdas}</span><span>Kirkwood SDAS · DOI {result.doi.sdas}</span><span>Hunt morphology · DOI {result.doi.morphology}</span></div>
              </>}
            </div>
          </section>
          <p className="px-1 pb-2 text-[10px] leading-5 text-slate-600">Results are model-derived estimates. Use the diagnostic notes and calculation source when interpreting comparisons; this view does not replace experimental validation.</p>
        </>
      )}
    </div>
  );
};

export default SolidificationMicrostructureLab;
