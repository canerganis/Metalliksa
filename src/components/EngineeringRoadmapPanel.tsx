import React from 'react';
import { engineeringRoadmap, summarizeRoadmap, summarizeEngineeringGates, ROADMAP_VERSION, ROADMAP_UPDATED } from '../data/engineeringRoadmap';

export function EngineeringRoadmapPanel() {
  const summary = summarizeRoadmap(engineeringRoadmap);
  const format = (value: number) => `${Number(value.toFixed(2))}%`;
  return <details className="rounded-2xl border border-slate-700 bg-slate-900/50 p-5">
    <summary className="cursor-pointer rounded text-sm text-slate-200 focus-visible:outline-2 focus-visible:outline-sky-300">
      Deferred qualification backlog · {format(summary.earned)} evidenced · {format(summary.remaining)} remaining
    </summary>
    <section aria-label="Engineering development progress" className="mt-5 space-y-5">
      <div className="flex flex-wrap justify-between gap-3"><div><h2 className="text-xl font-medium">Later engineering qualification work</h2><p className="mt-2 text-sm text-slate-400">Deferred while the V1 Research Workstation release is active. {summary.acceptedCount}/{summary.items.length} work packages accepted; this ledger does not establish scientific validation or qualification.</p></div><span className="text-xs text-slate-400">Scope {ROADMAP_VERSION} · Updated {ROADMAP_UPDATED}</span></div>
      <progress aria-label="Evidenced development progress" className="h-3 w-full accent-sky-400" max={100} value={summary.earned}/>
      <p className="text-xs text-slate-400">Credit requires recorded evidence: definition 10%, implementation 35%, testing 30%, independent review 15%, acceptance 10%. This versioned record is updated with completed engineering work; running a simulation does not change it.</p>
      <ul aria-label="Deferred qualification gates" className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">{summarizeEngineeringGates(summary.items).map(gate => {
        return <li key={gate.id} className="rounded-lg border border-slate-700 p-3 text-xs"><strong>{gate.id} · {gate.title}</strong><p className={gate.accepted ? 'mt-2 text-emerald-300' : 'mt-2 text-amber-200'}>{gate.accepted ? 'Accepted' : gate.missingTasks.length ? `${gate.missingTasks.length} packages await acceptance` : 'Awaiting prior gates'}</p>{gate.pendingPredecessors.length > 0 && <p className="mt-2 text-amber-200">Required gates: {gate.pendingPredecessors.join(', ')}</p>}</li>;
      })}</ul>
      <div className="grid gap-3 lg:grid-cols-2">{summary.items.map(task => <details key={task.id} className="rounded-lg border border-slate-700 p-3">
        <summary className="cursor-pointer text-sm focus-visible:outline-2 focus-visible:outline-sky-300">{task.id} · {task.title} <span className="ml-2 text-sky-300">{format(task.percent)}</span>{task.blocker && <span className="ml-2 text-amber-200">Blocked</span>}</summary>
        <p className="mt-3 text-sm text-slate-300">{task.acceptance}</p>
        {task.pendingDependencies.length > 0 && <p className="mt-2 text-xs text-amber-200">Acceptance prerequisites: {task.pendingDependencies.join(', ')}</p>}
        {task.blocker && <p className="mt-2 text-xs text-amber-200">{task.blocker}</p>}
        <p className="mt-2 text-sm text-slate-400">Next: {task.nextAction}</p>
        {task.milestones.length ? <ul className="mt-3 space-y-2 text-xs text-slate-400">{task.milestones.map(m => <li key={m.id}><strong className="text-slate-200">{m.id}</strong> · {m.date} · {m.reviewer}<p className="mt-1 break-words">{m.evidence}</p></li>)}</ul> : <p className="mt-3 text-xs text-slate-500">No milestones credited yet.</p>}
      </details>)}</div>
    </section>
  </details>;
}
