// Manual test harness: real components with explicit synthetic candidate inputs.
import React, { lazy, Suspense, useState } from 'react';
import { createRoot } from 'react-dom/client';
import '../src/index.css';
import { verifyInputBoundTask } from './input-bound-task-browser';
const EDS = lazy(() => import('../src/components/EDSSpectrumLab').then(m => ({ default: m.EDSSpectrumLab })));
// The heat-treatment and inverse-alloy tabs were removed on 2026-10-04 with the InverseAlloyStudio subtree.
function Harness() {
  const [lifecycleStatus, setLifecycleStatus] = useState('Not run');
  const [tab, setTab] = useState('eds');
  const [composition, setComposition] = useState<Record<string, number> | null>(null);
  const [navigation, setNavigation] = useState('');
  return <main className="min-h-screen bg-slate-950 text-white p-5">
    <h1>Component contract tests — synthetic inputs, no experimental evidence</h1>
    <nav className="flex gap-5 my-4">{['eds'].map(id =>
      <button key={id} onClick={() => setTab(id)}>{id}</button>)}</nav>
    <output aria-label="Transfer result">{composition ? JSON.stringify(composition) : navigation}</output>
    <button className="ml-4" onClick={() => {
      try { setLifecycleStatus(verifyInputBoundTask()); } catch (error) { setLifecycleStatus(`FAIL: ${error}`); }
    }}>Test request lifecycle</button>
    <output aria-label="Lifecycle test result">{lifecycleStatus}</output>
    <Suspense fallback={<p>Loading component</p>}>
      {tab === 'eds' && <EDS onSendToAlloyBuilder={setComposition} />}
    </Suspense>
  </main>;
}
createRoot(document.getElementById('root')!).render(<Harness />);
