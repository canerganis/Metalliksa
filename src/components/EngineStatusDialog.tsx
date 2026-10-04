/**
 * Engine availability dialog, opened from the header status button. Its own chunk: it is only needed
 * on demand, so the eager index chunk does not carry it (Phase 9 index budget). Content and wording
 * are unchanged from the former inline App modal.
 */
import React from 'react';
import { Cpu, X } from 'lucide-react';
import { AccessibleModal } from './AccessibleModal';
import type { PythonEngineStatus } from '../services/pythonComputationService';
import { subsystemQualifier } from '../utils/engineStatusText';

export function EngineStatusDialog({ status, statusError, checking, onClose, onRefresh }: {
  status: PythonEngineStatus | null; statusError: string | null; checking: boolean; onClose: () => void; onRefresh: () => void;
}) {
  return <AccessibleModal open onClose={onClose} labelledBy="engine-title" closeOnBackdrop overlayClassName="bg-slate-950/80 p-4" panelClassName="w-full max-w-xl max-h-[85vh] overflow-y-auto rounded-xl border border-slate-700 bg-slate-950 p-6">
        <div className="flex justify-between items-center"><h2 id="engine-title" className="font-semibold flex gap-2 items-center"><Cpu className="w-5 h-5 text-sky-400"/>Engine availability</h2><button aria-label="Close engine status" onClick={onClose}><X className="w-5 h-5"/></button></div>
        <p className="my-4 text-sm text-slate-400">Availability is reported by the backend. An installed solver does not establish a validated physical model.</p>
        {statusError && <p role="alert" className="text-sm text-amber-300">{statusError}</p>}
        <p className="text-sm mb-3">{status?.online ? `Python ${status.pythonVersion ?? 'version unavailable'} · ${status.status}` : 'Python backend unavailable. Check the local server and Python runtime.'}</p>
        <dl className="divide-y divide-slate-800">{(Object.entries(status?.subsystems ?? {}) as [string, { available: boolean }][]).map(([name, subsystem]) => <div key={name} className="py-2 flex justify-between gap-3 text-xs"><dt>{name.replaceAll('_', ' ')}</dt><dd className={subsystem.available ? 'text-sky-300' : 'text-amber-300'}>{subsystem.available ? 'Available' : 'Unavailable'}</dd></div>)}</dl>
        {!status?.subsystems && <p className="text-xs text-slate-500">Subsystems: {status?.online ? subsystemQualifier(status) : 'unavailable'}</p>}
        <button disabled={checking} onClick={onRefresh} className="mt-4 rounded-lg bg-sky-600 px-4 py-2 text-sm disabled:opacity-50">{checking ? 'Checking…' : 'Refresh status'}</button>
    </AccessibleModal>;
}
