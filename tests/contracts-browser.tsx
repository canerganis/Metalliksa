// Manual test harness: real components with explicit synthetic candidate inputs.
import React, { lazy, Suspense, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { HeatTreatmentAgingSimulator } from '../src/components/HeatTreatmentAgingSimulator';
import { solveInverseAlloyCandidates, type InverseDesignTargets } from '../src/utils/inverseAlloyOptimizer';
import '../src/index.css';
import { verifyInputBoundTask } from './input-bound-task-browser';
const EDS = lazy(() => import('../src/components/EDSSpectrumLab').then(m => ({ default: m.EDSSpectrumLab })));
const Circuit = lazy(() => import('../src/components/EquivalentCircuitBuilder').then(m => ({ default: m.EquivalentCircuitBuilder })));
const Noise = lazy(async () => {
  const [{SyntheticNoiseStressStudio}, {STANDARD_CIRCUIT_PRESETS}] = await Promise.all([
    import('../src/components/SyntheticNoiseStressStudio'), import('../src/components/EquivalentCircuitBuilder')]);
  return {default: function NoiseFixture() {
    const [index, setIndex] = useState(0);
    const [exported, setExported] = useState('Not exported');
    return <><button onClick={() => setIndex(i => 1-i)}>Replace noise topology</button>
      <output aria-label="Exported synthetic data">{exported}</output>
      <SyntheticNoiseStressStudio initialTopology={STANDARD_CIRCUIT_PRESETS[index]}
        onExportToCNLS={dataset => setExported(JSON.stringify(dataset))} /></>;
  }};
});
const Fitting = lazy(async () => {
  const [{ CNLSFittingStudio }, { STANDARD_CIRCUIT_PRESETS }] = await Promise.all([
    import('../src/components/CNLSFittingStudio'), import('../src/components/EquivalentCircuitBuilder')]);
  return { default: function FittingFixture() {
    const [index, setIndex] = useState(0);
    const [applied, setApplied] = useState('Not applied');
    return <>
      <button onClick={() => setIndex(i => 1 - i)}>Replace workspace topology</button>
      <output aria-label="Applied circuit">{applied}</output>
      <CNLSFittingStudio currentTopology={STANDARD_CIRCUIT_PRESETS[index]}
        onApplyTopology={topology => setApplied(JSON.stringify(topology.branches.map(b => b.elements.map(e => e.value))))} />
    </>;
  } };
});
const Inverse = lazy(() => import('../src/components/InverseAlloyStudio').then(m => ({ default: m.InverseAlloyStudio })));
const targets: InverseDesignTargets = {
  applicationName: 'Synthetic UI fixture', baseMatrix: 'Nickel',
  targetYieldStrength_25C: 900, targetYieldStrength_Elevated: 700, serviceTemperature_C: 600,
  minElongation_pct: 10, minFractureToughness_K1c: 50, minPREN: 20,
  maxDensity_gcm3: 9, maxCostUSD_kg: 100, manufacturingRoute: 'LPBF 3D Printing',
  elementExclusions: { noCobalt: false, noRhenium: true, noTantalum: true, lowCarbon: true },
};
const candidate = solveInverseAlloyCandidates(targets)[0];
const realFetch = window.fetch.bind(window);
let transport = 'real';
const heldReplies: Array<() => void> = [];
let heldCountChanged = () => {};
window.fetch = async (input, init) => {
  const mode = transport;
  const url = String(input);
  const action = typeof init?.body === 'string' ? JSON.parse(init.body).action ?? 'fit' : '';
  const hold = (mode === 'hold-fit' && ['fit', 'auto_fit'].includes(action) && url.includes('/cnls-'))
    || (mode === 'hold-drt' && action === 'drt') || (mode === 'hold-simulation' && action === 'simulate');
  if (mode === 'failure-simulation' && action === 'simulate') return new Response('{"error":"Controlled simulation failure"}', { status: 503 });
  if (hold) {
    // Deliberately ignore abort to test consumers against a late real reply.
    const response = await realFetch(input, { ...init, signal: undefined });
    return new Promise<Response>(resolve => {
      heldReplies.push(() => resolve(response));
      heldCountChanged();
    });
  }
  if (['/api/python/cnls-fit', '/api/python/cnls-autofit'].includes(String(input)) && init?.body && typeof init.body === 'string') {
    const action = JSON.parse(init.body).action ?? 'fit';
    if (action === 'fit' || action === 'auto_fit') {
      if (transport === 'failure') return new Response(JSON.stringify({ error: 'Controlled test failure' }), { status: 503 });
      if (transport === 'partial') return new Response(JSON.stringify({ success: true }));
    }
  }
  return realFetch(input, init);
};
function Harness() {
  const [lifecycleStatus, setLifecycleStatus] = useState('Not run');
  const [, updateHeldCount] = useState(0);
  heldCountChanged = () => updateHeldCount(n => n + 1);
  const [tab, setTab] = useState('heat');
  const [composition, setComposition] = useState<Record<string, number> | null>(null);
  const [navigation, setNavigation] = useState('');
  return <main className="min-h-screen bg-slate-950 text-white p-5">
    <h1>Component contract tests — synthetic inputs, no experimental evidence</h1>
    <nav className="flex gap-5 my-4">{['heat', 'eds', 'circuit', 'fitting', 'noise', 'inverse'].map(id =>
      <button key={id} onClick={() => setTab(id)}>{id}</button>)}</nav>
    <output aria-label="Transfer result">{composition ? JSON.stringify(composition) : navigation}</output>
    <label className="block mb-3">CNLS test transport <select className="bg-slate-800" defaultValue="real" onChange={e => { transport = e.target.value; }}>
      <option value="real">Real Python</option><option value="failure">HTTP 503</option><option value="partial">Incomplete report</option>
      <option value="hold-fit">Hold real fit reply</option><option value="hold-drt">Hold real DRT reply</option><option value="hold-simulation">Hold real simulation reply</option>
      <option value="failure-simulation">Simulation HTTP 503</option>
    </select></label>
    <button onClick={() => { heldReplies.splice(0).forEach(release => release()); heldCountChanged(); }}>Release held replies ({heldReplies.length})</button>
    <button className="ml-4" onClick={() => {
      try { setLifecycleStatus(verifyInputBoundTask()); } catch (error) { setLifecycleStatus(`FAIL: ${error}`); }
    }}>Test request lifecycle</button>
    <output aria-label="Lifecycle test result">{lifecycleStatus}</output>
    <Suspense fallback={<p>Loading component</p>}>
      {tab === 'heat' && <HeatTreatmentAgingSimulator candidate={candidate} targets={targets} />}
      {tab === 'eds' && <EDS onSendToAlloyBuilder={setComposition} />}
      {tab === 'circuit' && <Circuit />}
      {tab === 'fitting' && <Fitting />}
      {tab === 'noise' && <Noise />}
      {tab === 'inverse' && <Inverse onNavigate={setNavigation} />}
    </Suspense>
  </main>;
}
createRoot(document.getElementById('root')!).render(<Harness />);
