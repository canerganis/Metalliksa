import React, { useEffect, useState } from 'react';
import { useInputBoundTask } from '../hooks/useInputBoundTask';
import { sourceAction, sourceCatalog, type SourceAction, type SourceSnapshot, type LpbfSourceDocument } from '../services/lpbfSourceService';

const button = 'rounded-lg border border-slate-600 px-3 py-2 text-sm hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-sky-300 disabled:opacity-40';

export function LpbfSourceArchivePanel() {
  const [catalog, setCatalog] = useState<{ datasetId: string; title: string }[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(null); setCatalog(null); setSelected('');
    sourceCatalog(controller.signal).then(items => {
      if (!controller.signal.aborted) { setCatalog(items); setSelected(items[0]?.datasetId ?? ''); }
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Source catalog unavailable.'); });
    return () => controller.abort();
  }, [attempt]);
  return <section aria-label="LPBF source archive" className="rounded-2xl border border-slate-700/70 bg-slate-900/40 p-5 space-y-4">
    <div><h3 className="text-lg font-medium">Source archive</h3><p className="mt-1 text-sm text-amber-200">Unreviewed source archive · experimental validation unresolved</p></div>
    <p className="text-sm text-slate-400">Inspect original source conditions before using measurements. Import stores local source files; it does not change the active specimen or process parameters.</p>
    {error ? <div><p role="alert" className="text-rose-300">{error}</p><button className={`${button} mt-3`} onClick={() => setAttempt(value => value + 1)}>Retry source catalog</button></div>
      : catalog === null ? <p role="status">Loading source catalog…</p>
      : catalog.length === 0 ? <p>No local sources configured.</p>
      : <><label className="block text-sm">Local source<select aria-label="Local source" className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 focus-visible:outline-2 focus-visible:outline-sky-300" value={selected} onChange={event => setSelected(event.target.value)}>{catalog.map(item => <option key={item.datasetId} value={item.datasetId}>{item.title}</option>)}</select></label>
        {selected && <SourceRecord key={selected} datasetId={selected}/>}</>}
  </section>;
}

function SourceRecord({ datasetId }: { datasetId: string }) {
  const task = useInputBoundTask<SourceSnapshot>(datasetId);
  const run = async (action: SourceAction) => {
    const preview = task.data?.preview;
    const request = task.begin(action);
    try { request.publish(await sourceAction(datasetId, action, request.signal, preview)); }
    catch (error) { request.fail(error); }
    finally { request.finish(); }
  };
  useEffect(() => { void run('current'); }, [datasetId]);
  const data = task.data;
  const document = data?.preview?.document ?? data?.current?.document;
  return <div className="space-y-4" aria-busy={!!task.pending}>
    <div className="flex flex-wrap gap-2">
      <button className={button} disabled={!!task.pending} onClick={() => void run('current')}>Reload archive</button>
      <button className={button} disabled={!!task.pending} onClick={() => void run('preview')}>Preview local source</button>
      <button className={button} disabled={!!task.pending || !data?.preview} onClick={() => void run('import')}>Import previewed source</button>
      <button className={button} disabled={!!task.pending || !data?.current} onClick={() => void run('verify')}>Verify archived files</button>
    </div>
    <p role="status" className="text-sm text-slate-300">{task.pending ? `Source ${task.pending} in progress… Large files may take time. Leaving this panel discards the response; a server import may still finish.`
      : data?.imported ? 'Import completed. File bytes matched at import; scientific review remains open.'
      : data?.preview ? `Preview checked ${data.preview.artifactCount} files / ${data.preview.byteSize.toLocaleString('en-US')} bytes. Nothing imported by this preview.`
      : data?.verification ? 'Archived file bytes matched at the check time below.'
      : data?.current ? 'Stored metadata loaded. File bytes have not been checked in this view.'
      : data ? 'This source has not been imported. Preview to inspect its conditions and files.' : ''}</p>
    {task.error && <p role="alert" className="text-rose-300">{task.error}</p>}
    {data?.current && <div className="text-sm space-y-1"><p>Stored revision {data.current.revision} · created {data.current.createdAt}</p><p className="break-all">Stored document SHA256: {data.current.documentSha256}</p></div>}
    {data?.preview && <p className="text-xs break-all text-slate-400">Preview SHA256: {data.preview.documentSha256} · expected stored revision {data.preview.expectedRevision}</p>}
    {data?.verification && <div className="border-l-2 border-sky-400 pl-3 text-sm space-y-1"><p>File integrity check · revision {data.verification.revision}</p><p>Checked at {data.verification.verifiedAt}</p><p className="break-all">Checked SHA256: {data.verification.documentSha256}</p><p>Point-in-time byte integrity only; no scientific validation.</p></div>}
    {document && <SourceConditions document={document} preview={!!data?.preview}/>}
  </div>;
}

export function SourceConditions({ document, preview }: { document: LpbfSourceDocument; preview: boolean }) {
  const context = document.sourceContext;
  const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
  const measurement = object(context?.measurement);
  const experiment = object(context?.experiment);
  const transcription = object(context?.transcription);
  const observations = Array.isArray(context?.observations) ? context.observations.map(object) : [];
  const known = (value: unknown, reason?: unknown) => typeof value === 'string' || typeof value === 'number' ? String(value)
    : `Unknown${typeof reason === 'string' ? ` — ${reason}` : ''}`;
  return <div className="space-y-4 border-t border-slate-700 pt-4">
    <h4 className="font-medium">{preview ? 'Preview source conditions' : 'Stored source conditions'}</h4>
    <dl className="grid gap-3 text-sm sm:grid-cols-3">{[
      ['Material', document.materialId.toUpperCase()], ['Process scope', document.processScope], ['Source version', document.source.version],
      ['Archived files', String(document.artifacts.length)], ['Total bytes', document.artifacts.reduce((sum, item) => sum + item.byteSize, 0).toLocaleString('en-US')],
    ].map(([label, value]) => <div key={label}><dt className="text-xs text-slate-400">{label}</dt><dd>{value}</dd></div>)}</dl>
    <p className="text-sm">{document.source.citation}</p>
    <p className="text-xs break-all text-slate-400">Source: {document.source.url}</p>
    <div className="text-sm"><h5 className="font-medium">Source use terms</h5><p className="mt-1 text-slate-400">{document.source.terms ?? `Unknown: ${document.source.termsMissingReason}`}</p></div>
    <p className="text-sm text-amber-200">{context?.publisher_artifact_kind === 'original-optical-cross-section-micrographs-and-publisher-checksums'
      ? 'Original NIST case 0 optical micrographs and their publisher checksums are archived with six mapped width/depth measurements. These are three tracks on each of two sections from one bare-plate specimen; the model has no matching image observation operator, so this is not validation.'
      : context?.publisher_artifact_kind === 'publisher-optical-cross-section-measurements'
      ? 'This NIST publisher workbook contains individual optical cross-section measurements. The model still needs matched conditions, an optical section operator and numerical convergence before a validation claim.'
      : transcription.kind === 'local-transcription-of-published-aggregate-measurements'
      ? 'This local transcription contains published Table 4 optical width and depth aggregates. Individual cross-sections and images are not included. Bare-plate measurements do not establish powder-bed model validation.'
      : 'Raw camera signal is not measured temperature, melt-pool width or depth. Calibration, units and matching measurement definitions require review. Bare-plate data does not establish powder-bed validation.'}</p>
    {context ? <><h5 className="text-sm font-medium">Measurement conditions and unresolved fields</h5>
      <dl className="grid gap-4 text-sm sm:grid-cols-2">{[
        ['Machine', known(experiment.machine)], ['Heat treatment', known(experiment.heat_treatment, experiment.heat_treatment_missing_reason)],
        ['Recorded quantity', known(measurement.quantity)], ['Signal units', known(measurement.unit_source, measurement.unit_missing_reason)],
        ['Temperature conversion', known(measurement.temperature_conversion, measurement.temperature_conversion_missing_reason)],
        ['Beam diameter convention', known(measurement.beam_diameter_definition, measurement.beam_diameter_missing_reason)],
        ['Repeat grouping', known(measurement.repeat_group_rule)], ['Evaluation partition', known(context.split)],
      ].map(([label, value]) => <div key={label}><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-1">{value}</dd></div>)}</dl>
      {observations.length > 0 && <div className="overflow-x-auto"><h5 className="mb-2 text-sm font-medium">Published optical measurements</h5><table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-700 text-xs text-slate-400"><th className="p-2">Section</th><th className="p-2">Track</th><th className="p-2">Width (µm)</th><th className="p-2">Depth (µm)</th><th className="p-2">Image</th></tr></thead><tbody>{observations.map((row, index) => <tr key={`${String(row.imagePath)}-${index}`} className="border-b border-slate-800"><td className="p-2">{String(row.part ?? 'Unknown')}</td><td className="p-2">{String(row.caseAndLine ?? 'Unknown')}</td><td className="p-2">{typeof row.measuredWidth_um === 'number' ? row.measuredWidth_um.toFixed(3) : 'Unknown'}</td><td className="p-2">{typeof row.measuredDepth_um === 'number' ? row.measuredDepth_um.toFixed(3) : 'Unknown'}</td><td className="p-2 font-mono text-xs">{String(row.imagePath ?? 'Unknown')}</td></tr>)}</tbody></table></div>}
      {Array.isArray(context.unresolved) && <ul className="list-disc pl-5 space-y-1 text-sm text-amber-200">{context.unresolved.filter(item => typeof item === 'string').map((item, index) => <li key={index}>{String(item)}</li>)}</ul>}
      <details><summary className="cursor-pointer text-sm">Full source context</summary><pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-300" tabIndex={0} aria-label="Full source context">{JSON.stringify(context, null, 2)}</pre></details></>
      : <p className="text-amber-200">Source context unknown. Measurement conditions have not been established.</p>}
    <details><summary className="cursor-pointer text-sm focus-visible:outline-2 focus-visible:outline-sky-300">Archived file hashes</summary><ul className="mt-3 space-y-3 text-xs">{document.artifacts.map(item => <li key={item.relativePath} className="break-all">{item.relativePath} · {item.byteSize.toLocaleString('en-US')} bytes<br/>SHA256 {item.sha256}</li>)}</ul></details>
  </div>;
}
