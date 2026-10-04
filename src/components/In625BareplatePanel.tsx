import { useEffect, useMemo, useState } from 'react';
import { LpbfJobArchiver } from './LpbfRunArchivePanel';
import { useVisiblePolling } from '../hooks/useVisiblePolling';
import {
  in625BareplateApi, type In625BareplateConfig, type In625BareplateInput,
  fetchIn625BareplateTemperatureField, type In625BareplateJob, type In625BareplateResult,
} from '../services/lpbfSimulationService';

const defaultConfig: In625BareplateConfig = {
  shapeXYZ: [16, 12, 6], cellSizeM: [0.00025, 0.00025, 0.00025],
  initialTemperatureK: 298.15, dtS: 1e-5, steps: 10,
  absorbedPowerW: 20, spotSigmaM: 0.0004, scanStartXM: 0.001,
  scanYM: 0.0015, scanVelocityXMS: 0,
};
const storageKey = 'metalliksa.in625BareplateJob.v1';
const inputClass = 'mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm tabular-nums';
const buttonClass = 'rounded-lg border border-slate-500 px-3 py-2 text-sm disabled:opacity-40';
const fmt = (value: number) => Number.isFinite(value) ? Number(value.toPrecision(6)).toString() : '—';

export function buildIn625BareplateInput(config: In625BareplateConfig, backend: In625BareplateInput['backend']): In625BareplateInput {
  return {
    jobType: 'in625-bareplate-field',
    backend,
    config: {
      shapeXYZ: [...config.shapeXYZ], cellSizeM: [...config.cellSizeM],
      initialTemperatureK: config.initialTemperatureK, dtS: config.dtS, steps: config.steps,
      absorbedPowerW: config.absorbedPowerW, spotSigmaM: config.spotSigmaM,
      scanStartXM: config.scanStartXM, scanYM: config.scanYM, scanVelocityXMS: config.scanVelocityXMS,
    },
  };
}

const validConfig = (config: In625BareplateConfig) => {
  const cells = config.shapeXYZ.reduce((product, count) => product * count, 1);
  const work = cells * config.steps;
  return config.shapeXYZ.every(value => Number.isInteger(value) && value >= 2)
    && Number.isSafeInteger(cells) && Number.isSafeInteger(work)
    && config.cellSizeM.every(value => Number.isFinite(value) && value > 0)
    && [config.initialTemperatureK, config.dtS, config.absorbedPowerW, config.spotSigmaM,
      config.scanStartXM, config.scanYM, config.scanVelocityXMS].every(Number.isFinite)
    && config.initialTemperatureK >= 273.15 && config.initialTemperatureK < 1623.15
    && config.dtS > 0 && config.absorbedPowerW >= 0 && config.spotSigmaM > 0
    && Number.isInteger(config.steps) && config.steps >= 1 && config.steps <= 25_000
    && cells <= 1_000_000 && work <= 2_000_000;
};

function compareResults(cpu?: In625BareplateResult, cuda?: In625BareplateResult) {
  if (!cpu || !cuda || JSON.stringify(cpu.settings.config) !== JSON.stringify(cuda.settings.config)
    || cpu.settings.backend !== 'cpu' || cuda.settings.backend === 'cpu'
    || cpu.material.materialId !== cuda.material.materialId
    || cpu.material.materialRevisionSha256 !== cuda.material.materialRevisionSha256
    || cpu.solver.id !== cuda.solver.id || cpu.solver.modelId !== cuda.solver.modelId
    || cpu.solver.revision !== cuda.solver.revision || cpu.runKind !== cuda.runKind) return undefined;
  const metrics = Object.keys(cpu.metrics).filter(key => key !== 'cells'
    && typeof cpu.metrics[key as keyof In625BareplateResult['metrics']] === 'number'
    && typeof cuda.metrics[key as keyof In625BareplateResult['metrics']] === 'number');
  const energy = ['input_J', 'losses_J', 'stored_J', 'relativeError'] as const;
  return [
    ...metrics.map(key => ({
      key,
      cpu: cpu.metrics[key as keyof In625BareplateResult['metrics']] as number,
      cuda: cuda.metrics[key as keyof In625BareplateResult['metrics']] as number,
    })),
    ...energy.map(key => ({ key: `energyBalance.${key}`, cpu: cpu.energyBalance[key], cuda: cuda.energyBalance[key] })),
  ].map(row => ({ ...row, absoluteDifference: Math.abs(row.cpu - row.cuda) }));
}

export function compareTemperatureFields(
  cpuField: { shapeXYZ: number[]; temperaturesK: Float64Array },
  cudaField: { shapeXYZ: number[]; temperaturesK: Float64Array },
) {
  if (JSON.stringify(cpuField.shapeXYZ) !== JSON.stringify(cudaField.shapeXYZ)
    || cpuField.temperaturesK.length !== cudaField.temperaturesK.length) {
    throw new Error('CPU/CUDA field dimensions differ despite matching inputs');
  }
  let squaredSum = 0;
  let maximum = 0;
  for (let index = 0; index < cpuField.temperaturesK.length; index += 1) {
    const difference = Math.abs(cpuField.temperaturesK[index] - cudaField.temperaturesK[index]);
    maximum = Math.max(maximum, difference); squaredSum += difference * difference;
  }
  return { maxAbsoluteDifferenceK: maximum,
    rmsDifferenceK: Math.sqrt(squaredSum / cpuField.temperaturesK.length), cells: cpuField.temperaturesK.length };
}

export function In625BareplatePanel() {
  const [config, setConfig] = useState(defaultConfig);
  const [device, setDevice] = useState('cuda:0');
  const [job, setJob] = useState<In625BareplateJob>();
  const [runs, setRuns] = useState<{ cpu?: { id: string; result: In625BareplateResult }; cuda?: { id: string; result: In625BareplateResult } }>({});
  const [fieldComparison, setFieldComparison] = useState<{ maxAbsoluteDifferenceK: number; rmsDifferenceK: number; cells: number }>();
  const [fieldComparisonError, setFieldComparisonError] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const active = job?.status === 'queued' || job?.status === 'running';
  const validDevice = /^cuda:[0-9]+$/.test(device);
  const valid = validConfig(config);
  const comparison = useMemo(() => compareResults(runs.cpu?.result, runs.cuda?.result), [runs]);

  useEffect(() => {
    const cpu = runs.cpu;
    const cuda = runs.cuda;
    if (!cpu || !cuda || !compareResults(cpu.result, cuda.result)) {
      setFieldComparison(undefined); setFieldComparisonError('');
      return;
    }
    let live = true;
    setFieldComparison(undefined); setFieldComparisonError('');
    Promise.all([
      fetchIn625BareplateTemperatureField(cpu.id, cpu.result),
      fetchIn625BareplateTemperatureField(cuda.id, cuda.result),
    ]).then(([cpuField, cudaField]) => {
      if (!live) return;
      setFieldComparison(compareTemperatureFields(cpuField, cudaField));
    }).catch(error => {
      if (live) setFieldComparisonError(error instanceof Error ? error.message : 'Could not verify CPU/CUDA temperature fields');
    });
    return () => { live = false; };
  }, [runs]);

  useEffect(() => {
    let live = true;
    let saved = '';
    try { saved = localStorage.getItem(storageKey) || ''; } catch { /* Storage may be disabled. */ }
    if (/^[a-f0-9]{32}$/.test(saved)) {
      in625BareplateApi.get(saved).then(next => {
        if (!live) return;
        setJob(next);
        if (next.status === 'completed' && next.result) {
          setConfig(next.result.settings.config);
          setRuns(previous => ({ ...previous, [next.result!.settings.backend === 'cpu' ? 'cpu' : 'cuda']:
            { id: next.id, result: next.result! } }));
        }
      }).catch(e => { if (live) setError(`Saved IN625 screen unavailable: ${e instanceof Error ? e.message : 'Worker connection failed'}`); });
    }
    return () => { live = false; };
  }, []);

  // Paused while the module is hidden; becoming visible again polls at once to catch up.
  useVisiblePolling(async (isLive) => {
    if (!job) return null;
    try {
      const next = await in625BareplateApi.get(job.id);
      if (!isLive()) return null;
      setJob(next); setError('');
      if (next.status === 'completed' && next.result) {
        const key = next.result.settings.backend === 'cpu' ? 'cpu' : 'cuda';
        setRuns(previous => ({ ...previous, [key]: { id: next.id, result: next.result! } }));
        return null;
      }
      return next.status === 'queued' || next.status === 'running' ? 1500 : null;
    } catch (e) {
      if (!isLive()) return null;
      setError(e instanceof Error ? e.message : 'IN625 bare-plate job polling failed');
      return 3000;
    }
  }, !!job && active, `${job?.id}:${job?.status}`);

  const submit = async (backend: In625BareplateInput['backend']) => {
    if (submitting || active || !valid || (backend !== 'cpu' && !validDevice)) return;
    setSubmitting(true); setError('');
    const input = buildIn625BareplateInput(config, backend);
    try {
      const next = await in625BareplateApi.submit(input);
      setJob(next);
      try { localStorage.setItem(storageKey, next.id); } catch { /* The live job remains available. */ }
      if (backend !== 'cpu') setDevice(backend);
    } catch (e) { setError(e instanceof Error ? e.message : 'IN625 bare-plate submission failed'); }
    finally { setSubmitting(false); }
  };
  const cancel = async () => {
    if (!job || !active || cancelling) return;
    setCancelling(true);
    try { setJob(await in625BareplateApi.cancel(job.id)); }
    catch (e) { setError(e instanceof Error ? e.message : 'IN625 screen cancellation failed'); }
    finally { setCancelling(false); }
  };
  const currentResult = job?.status === 'completed' ? job.result : undefined;
  const setScalar = (key: keyof Omit<In625BareplateConfig, 'shapeXYZ' | 'cellSizeM'>, value: number) =>
    setConfig(previous => ({ ...previous, [key]: value }));
  const setVector = (key: 'shapeXYZ' | 'cellSizeM', axis: number, value: number) =>
    setConfig(previous => ({ ...previous, [key]: previous[key].map((item, index) => index === axis ? value : item) as [number, number, number] }));
  const fields: Array<[keyof Omit<In625BareplateConfig, 'shapeXYZ' | 'cellSizeM'>, string, number, number, string]> = [
    ['initialTemperatureK', 'Initial temperature · K', 273.15, 1623.14, 'any'],
    ['dtS', 'Timestep · s', 1e-12, 1, 'any'],
    ['steps', 'Steps', 1, 25000, '1'],
    ['absorbedPowerW', 'Absorbed power · W', 0, 10000, 'any'],
    ['spotSigmaM', 'Gaussian sigma · m', 1e-9, 1, 'any'],
    ['scanStartXM', 'Scan start X · m', 0, 100, 'any'],
    ['scanYM', 'Scan Y · m', 0, 100, 'any'],
    ['scanVelocityXMS', 'Scan velocity X · m/s', -100, 100, 'any'],
  ];

  return <section className="rounded-2xl border border-amber-400/30 bg-slate-900/50 p-4 md:p-5 space-y-4" aria-label="IN625 bare-plate thermal screening">
    <div><h3 className="font-medium">IN625 bare-plate thermal screen</h3>
      <p className="mt-2 text-sm text-slate-300">Separate bounded model · 3D enthalpy conduction · bare substrate · adiabatic on all six faces.</p>
      <p className="mt-2 text-xs leading-5 text-amber-200">273.15–1623.15 K model range. Constant density 8440 kg/m³ is a supplier-bulletin assumption, not lot-matched. No powder, melt-pool flow, optical coupling, evaporation, or experimental validation. Screening only; no claim of process qualification.</p>
    </div>
    <div className="grid gap-3 sm:grid-cols-3" aria-label="Grid dimensions">
      {config.shapeXYZ.map((value, axis) => <label key={`shape-${axis}`} className="text-xs">Cells {['X', 'Y', 'Z'][axis]}<input className={inputClass} aria-label={`Cells ${['X', 'Y', 'Z'][axis]}`} type="number" min="2" step="1" value={value} onChange={e => setVector('shapeXYZ', axis, e.currentTarget.valueAsNumber)}/></label>)}
    </div>
    <div className="grid gap-3 sm:grid-cols-3" aria-label="Cell size">
      {config.cellSizeM.map((value, axis) => <label key={`cell-${axis}`} className="text-xs">Cell size {['X', 'Y', 'Z'][axis]} · m<input className={inputClass} aria-label={`Cell size ${['X', 'Y', 'Z'][axis]} in m`} type="number" min="0" step="any" value={value} onChange={e => setVector('cellSizeM', axis, e.currentTarget.valueAsNumber)}/></label>)}
    </div>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{fields.map(([key, label, min, max, step]) => <label key={key} className="text-xs">{label}<input className={inputClass} aria-label={label} type="number" min={min} max={max} step={step} value={config[key]} onChange={e => setScalar(key, e.currentTarget.valueAsNumber)}/></label>)}</div>
    <p className={`text-xs ${valid ? 'text-slate-400' : 'text-red-300'}`} role="status">{valid ? 'Stability, source capture, and temperature bounds are checked by the solver.' : 'Correct the inputs; limits are 1,000,000 cells, 2,000,000 cell-steps, and 25,000 steps.'}</p>
    <div className="flex flex-wrap items-end gap-3">
      <button type="button" className={buttonClass} disabled={!valid || submitting || active} onClick={() => void submit('cpu')}>{submitting ? 'Submitting…' : 'Run CPU screen'}</button>
      <label className="text-xs">Explicit CUDA device<input aria-label="IN625 CUDA device" className={inputClass} value={device} pattern="cuda:[0-9]+" aria-invalid={!validDevice} onChange={e => setDevice(e.currentTarget.value)}/></label>
      <button type="button" className={buttonClass} disabled={!valid || !validDevice || submitting || active} onClick={() => void submit(device as `cuda:${number}`)}>Run CUDA screen</button>
      {active && <button type="button" className={buttonClass} disabled={cancelling} onClick={() => void cancel()}>{cancelling ? 'Cancelling…' : 'Cancel screen'}</button>}
    </div>
    <p className="text-xs text-slate-400">CUDA availability is checked for the exact selected device when submitted. There is no CPU fallback. CPU and CUDA runs are separate jobs.</p>
    {error && <p role="alert" className="rounded-lg border border-red-400/40 p-3 text-sm text-red-200">{error}</p>}
    {job && <p role="status" className="text-sm">IN625 bare-plate job {job.id} · {job.status}{job.cacheHit ? ' · cached' : ''}{job.error ? ` · ${job.error}` : ''}</p>}
    {currentResult && <div className="space-y-3 text-sm">
      <p className="text-amber-200">{currentResult.label} · {currentResult.validationStatus} · {currentResult.modelScope}</p>
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(currentResult.metrics).map(([key, value]) => <div key={key}><dt className="text-xs text-slate-400">{key}</dt><dd className="tabular-nums">{fmt(value)}</dd></div>)}</dl>
      <p className="text-xs text-slate-400">Energy closure {fmt(currentResult.energyBalance.relativeError * 100)}% · input {fmt(currentResult.energyBalance.input_J)} J · stored {fmt(currentResult.energyBalance.stored_J)} J. Closure checks arithmetic conservation only; it does not validate the physical model.</p>
      <p className="text-xs text-slate-400">Solver {currentResult.solver.modelId} rev {currentResult.solver.revision} · {currentResult.solver.actualBackend} · material SHA-256 {currentResult.material.materialRevisionSha256} · field SHA-256 {currentResult.field.sha256}</p>
      {job && <a className="underline underline-offset-4" href={`/api/lpbf/jobs/${encodeURIComponent(job.id)}/artifacts/${encodeURIComponent(currentResult.field.artifact)}`} download>Download final temperature field</a>}
      <a className="ml-4 underline underline-offset-4" href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(currentResult, null, 2))}`} download={`in625-bareplate-${currentResult.solver.actualBackend.replace(':', '-')}.json`}>Export result JSON</a>
      <details className="border-t border-slate-700/50 pt-2"><summary className="cursor-pointer">Energy history</summary><div className="mt-2 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-xs"><thead><tr>{['Time · s', 'Total enthalpy · J', 'Peak temperature · K', 'Energy residual · J'].map(item => <th key={item} className="pr-3 py-2">{item}</th>)}</tr></thead><tbody>{currentResult.energyHistory.map((row, index) => <tr key={index} className="border-t border-slate-700/50"><td className="py-2 pr-3">{fmt(row.time_s)}</td><td className="py-2 pr-3">{fmt(row.totalEnthalpy_J)}</td><td className="py-2 pr-3">{fmt(row.peakTemperature_K)}</td><td className="py-2 pr-3">{fmt(row.energyResidual_J)}</td></tr>)}</tbody></table></div></details>
      {comparison && <details className="border-t border-slate-700/50 pt-2" open><summary className="cursor-pointer">Same-configuration CPU/CUDA scalar comparison</summary><p className="my-2 text-xs text-amber-200">Descriptive scalar comparison for exact same-model, same-material-revision, same-configuration runs. No tolerance-based pass/fail target is defined here; this is not experimental validation.</p><div className="overflow-x-auto"><table className="w-full min-w-[520px] text-left text-xs"><thead><tr>{['Quantity', 'CPU', 'CUDA', 'Absolute difference'].map(item => <th key={item} className="pr-3 py-2">{item}</th>)}</tr></thead><tbody>{comparison.map(row => <tr key={row.key} className="border-t border-slate-700/50"><th scope="row" className="py-2 pr-3 font-normal">{row.key}</th><td className="py-2 pr-3">{fmt(row.cpu)}</td><td className="py-2 pr-3">{fmt(row.cuda)}</td><td className="py-2 pr-3">{fmt(row.absoluteDifference)}</td></tr>)}</tbody></table></div>
        <div className="mt-4 border-t border-slate-700/50 pt-3"><p className="text-xs font-medium">Final temperature field comparison · X fastest, then Y, then Z</p>
          {!fieldComparison && !fieldComparisonError && <p role="status" className="mt-2 text-xs text-slate-400">Fetching both archived fields and verifying size and SHA-256…</p>}
          {fieldComparisonError && <p role="alert" className="mt-2 text-xs text-red-300">Field comparison unavailable: {fieldComparisonError}</p>}
          {fieldComparison && <p role="status" className="mt-2 text-xs text-slate-300">{fieldComparison.cells} cells · maximum absolute difference {fmt(fieldComparison.maxAbsoluteDifferenceK)} K · RMS difference {fmt(fieldComparison.rmsDifferenceK)} K. This numerical parity check does not establish experimental validity.</p>}
        </div>
      </details>}
      {currentResult.assumptions.map((assumption, index) => <p key={index} className="text-xs text-slate-400">{assumption}</p>)}
      {job && <LpbfJobArchiver jobId={job.id} />}
    </div>}
  </section>;
}
