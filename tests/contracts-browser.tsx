// Manual test harness: real components with explicit synthetic candidate inputs.
import React, { lazy, Suspense, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { HeatTreatmentAgingSimulator } from '../src/components/HeatTreatmentAgingSimulator';
import { solveInverseAlloyCandidates, type InverseDesignTargets } from '../src/utils/inverseAlloyOptimizer';
import '../src/index.css';
import { verifyInputBoundTask } from './input-bound-task-browser';
const EDS = lazy(() => import('../src/components/EDSSpectrumLab').then(m => ({ default: m.EDSSpectrumLab })));
const Inverse = lazy(() => import('../src/components/InverseAlloyStudio').then(m => ({ default: m.InverseAlloyStudio })));
const targets: InverseDesignTargets = {
  applicationName: 'Synthetic UI fixture', baseMatrix: 'Nickel',
  targetYieldStrength_25C: 900, targetYieldStrength_Elevated: 700, serviceTemperature_C: 600,
  minElongation_pct: 10, minFractureToughness_K1c: 50, minPREN: 20,
  maxDensity_gcm3: 9, maxCostUSD_kg: 100, manufacturingRoute: 'LPBF 3D Printing',
  elementExclusions: { noCobalt: false, noRhenium: true, noTantalum: true, lowCarbon: true },
};
const candidate = solveInverseAlloyCandidates(targets)[0];
function Harness() {
  const [lifecycleStatus, setLifecycleStatus] = useState('Not run');
  const [tab, setTab] = useState('heat');
  const [composition, setComposition] = useState<Record<string, number> | null>(null);
  const [navigation, setNavigation] = useState('');
  return <main className="min-h-screen bg-slate-950 text-white p-5">
    <h1>Component contract tests — synthetic inputs, no experimental evidence</h1>
    <nav className="flex gap-5 my-4">{['heat', 'eds', 'inverse'].map(id =>
      <button key={id} onClick={() => setTab(id)}>{id}</button>)}</nav>
    <output aria-label="Transfer result">{composition ? JSON.stringify(composition) : navigation}</output>
    <button className="ml-4" onClick={() => {
      try { setLifecycleStatus(verifyInputBoundTask()); } catch (error) { setLifecycleStatus(`FAIL: ${error}`); }
    }}>Test request lifecycle</button>
    <output aria-label="Lifecycle test result">{lifecycleStatus}</output>
    <Suspense fallback={<p>Loading component</p>}>
      {tab === 'heat' && <HeatTreatmentAgingSimulator candidate={candidate} targets={targets} />}
      {tab === 'eds' && <EDS onSendToAlloyBuilder={setComposition} />}
      {tab === 'inverse' && <Inverse onNavigate={setNavigation} />}
    </Suspense>
  </main>;
}
createRoot(document.getElementById('root')!).render(<Harness />);
