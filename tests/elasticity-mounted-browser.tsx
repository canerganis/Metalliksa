/** Test-only deferred transport; this page verifies React lifecycle, not physical accuracy. */
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { MaterialsProjectExplorer } from '../src/components/MaterialsProjectExplorer';
import { pythonComputationService, type PythonDFTOutcome } from '../src/services/pythonComputationService';
import fixtures from './fixtures/elasticity-results.json';
import '../src/index.css';

const pending: Array<{ resolve: (outcome: PythonDFTOutcome) => void; reject: (error: Error) => void }> = [];
let changed = () => {};
pythonComputationService.calculateDFTProperties = () => new Promise((resolve, reject) => {
  pending.push({ resolve, reject });
  changed();
});

function Harness() {
  const [, redraw] = useState(0);
  const [mounted, setMounted] = useState(true);
  useEffect(() => {
    changed = () => redraw(value => value + 1);
    return () => { changed = () => {}; };
  }, []);
  return <main className="bg-slate-950 text-white min-h-screen p-6 space-y-4">
    <h1>Test-only deferred elasticity transport</h1>
    <p>Fixtures are synthetic software evidence, not measured material data.</p>
    <output aria-live="polite">Request count: {pending.length}</output>
    <button type="button" onClick={() => setMounted(value => !value)}>{mounted ? 'Unmount form' : 'Mount form'}</button>
    <div className="flex flex-wrap gap-4">
      {pending.map((request, index) => <React.Fragment key={index}>
        <button type="button" onClick={() => request.resolve({
          ...fixtures.libraryNi3Al.result,
          engine: `deferred-request-${index + 1}`,
          isPythonEngine: true,
          computeTimeMs: null,
        } as PythonDFTOutcome)}>Resolve request {index + 1}</button>
        <button type="button" onClick={() => request.reject(new Error(`deferred-error-${index + 1}`))}>Reject request {index + 1}</button>
      </React.Fragment>)}
    </div>
    {mounted && <MaterialsProjectExplorer />}
  </main>;
}

createRoot(document.getElementById('root')!).render(<Harness />);
