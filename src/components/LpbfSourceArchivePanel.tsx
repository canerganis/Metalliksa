import React, { useEffect, useState } from 'react';
import { useInputBoundTask } from '../hooks/useInputBoundTask';
import { allSourceRevisions, sourceAction, sourceCatalog, sourceRevision, type SourceAction, type SourceSnapshot, type LpbfSourceDocument, type SourceRevisionSummary } from '../services/lpbfSourceService';

const button = 'rounded-lg border border-slate-600 px-3 py-2 text-sm hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-sky-300 disabled:opacity-40';
const SELECTED_SOURCE_KEY = 'metalliksa.lpbf.sourceArchive.selectedDataset.v1';
const SELECTED_REVISION_KEY = 'metalliksa.lpbf.sourceArchive.selectedRevision.v1';

export function sourceSelectionForCatalog(datasetIds: string[], savedId: string | null): string {
  return savedId && datasetIds.includes(savedId) ? savedId : datasetIds[0] ?? '';
}

function savedSourceId(): string | null {
  try { return window.localStorage.getItem(SELECTED_SOURCE_KEY); } catch { return null; }
}

export function persistSourceId(datasetId: string): void {
  if (!datasetId) return;
  try { window.localStorage.setItem(SELECTED_SOURCE_KEY, datasetId); } catch { /* Keep the selection for this view. */ }
}

export function sourceRevisionSelectionForHistory(revisions: SourceRevisionSummary[], saved: { revision: number; documentSha256: string } | null) {
  if (saved) return revisions.find(item => item.revision === saved.revision && item.documentSha256 === saved.documentSha256) ?? null;
  return revisions.reduce<SourceRevisionSummary | null>((latest, item) => !latest || item.revision > latest.revision ? item : latest, null);
}

function savedRevision(datasetId: string): { revision: number; documentSha256: string } | null {
  try {
    const value = window.localStorage.getItem(`${SELECTED_REVISION_KEY}.${datasetId}`);
    if (!value) return null;
    const parsed = JSON.parse(value);
    return Number.isSafeInteger(parsed?.revision) && parsed.revision > 0
      && typeof parsed.documentSha256 === 'string' && /^[a-f0-9]{64}$/.test(parsed.documentSha256)
      ? parsed : null;
  } catch { return null; }
}

function persistRevision(datasetId: string, revision: SourceRevisionSummary | null) {
  if (!revision) return;
  try { window.localStorage.setItem(`${SELECTED_REVISION_KEY}.${datasetId}`, JSON.stringify({ revision: revision.revision, documentSha256: revision.documentSha256 })); }
  catch { /* Keep the exact selection in component state. */ }
}

export function LpbfSourceArchivePanel() {
  const [catalog, setCatalog] = useState<{ datasetId: string; title: string }[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(null); setCatalog(null); setSelected('');
    sourceCatalog(controller.signal).then(items => {
      if (!controller.signal.aborted) {
        setCatalog(items);
        const datasetId = sourceSelectionForCatalog(items.map(item => item.datasetId), savedSourceId());
        setSelected(datasetId); persistSourceId(datasetId);
      }
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Source catalog unavailable.'); });
    return () => controller.abort();
  }, [attempt]);
  return <section aria-label="LPBF source archive" className="rounded-2xl border border-slate-700/70 bg-slate-900/40 p-5 space-y-4">
    <div><h3 className="text-lg font-medium">Source archive</h3><p className="mt-1 text-sm text-amber-200">Unreviewed source archive · experimental validation unresolved</p></div>
    <p className="text-sm text-slate-400">Inspect original source conditions before using measurements. Import stores local source files; it does not change the active specimen or process parameters.</p>
    {error ? <div><p role="alert" className="text-rose-300">{error}</p><button className={`${button} mt-3`} onClick={() => setAttempt(value => value + 1)}>Retry source catalog</button></div>
      : catalog === null ? <p role="status">Loading source catalog…</p>
      : catalog.length === 0 ? <p>No local sources configured.</p>
      : <><label className="block text-sm">Local source<select aria-label="Local source" className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 focus-visible:outline-2 focus-visible:outline-sky-300" value={selected} onChange={event => { setSelected(event.target.value); persistSourceId(event.target.value); }}>{catalog.map(item => <option key={item.datasetId} value={item.datasetId}>{item.title}</option>)}</select></label>
        {selected && <SourceRecord key={selected} datasetId={selected}/>}</>}
  </section>;
}

function SourceRecord({ datasetId }: { datasetId: string }) {
  const task = useInputBoundTask<SourceSnapshot>(datasetId);
  const [history, setHistory] = useState<SourceRevisionSummary[] | null>(null);
  const [selectedRevision, setSelectedRevision] = useState<SourceRevisionSummary | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<{ revision: number; documentSha256: string; document: LpbfSourceDocument } | null>(null);
  const [revisionError, setRevisionError] = useState<string | null>(null);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyAttempt, setHistoryAttempt] = useState(0);
  const run = async (action: SourceAction) => {
    const preview = task.data?.preview;
    const request = task.begin(action);
    try {
      const snapshot = await sourceAction(datasetId, action, request.signal, preview);
      if (action === 'import') setHistoryAttempt(value => value + 1);
      request.publish(snapshot);
    }
    catch (error) { request.fail(error); }
    finally { request.finish(); }
  };
  useEffect(() => { void run('current'); }, [datasetId]);
  useEffect(() => {
    const controller = new AbortController();
    setHistory(null); setSelectedRevision(null); setHistoryError(null);
    allSourceRevisions(datasetId, controller.signal).then(revisions => {
      if (controller.signal.aborted) return;
      setHistory(revisions);
      const saved = savedRevision(datasetId);
      const selected = sourceRevisionSelectionForHistory(revisions, saved);
      setSelectedRevision(selected);
      setSelectionError(saved && !selected ? 'The saved source revision is no longer available. Choose a retained revision explicitly; no newer revision was substituted.' : null);
      if (!saved) persistRevision(datasetId, selected);
    }).catch(error => { if (!controller.signal.aborted) { setHistory([]); setHistoryError(error instanceof Error ? error.message : 'Retained source revisions are unavailable.'); } });
    return () => controller.abort();
  }, [datasetId, historyAttempt]);
  useEffect(() => {
    const controller = new AbortController();
    setSelectedDocument(null); setRevisionError(null);
    if (!selectedRevision) return () => controller.abort();
    sourceRevision(datasetId, selectedRevision.revision, controller.signal).then(value => {
      if (!controller.signal.aborted) {
        if (value.documentSha256 !== selectedRevision.documentSha256) throw new Error('Selected source revision hash changed.');
        setSelectedDocument(value);
      }
    }).catch(error => { if (!controller.signal.aborted) setRevisionError(error instanceof Error ? error.message : 'Selected source revision unavailable.'); });
    return () => controller.abort();
  }, [datasetId, selectedRevision]);
  const data = task.data;
  const archivedDocument = selectedRevision && selectedDocument?.revision === selectedRevision.revision
    && selectedDocument.documentSha256 === selectedRevision.documentSha256 ? selectedDocument.document : null;
  return <div className="space-y-4" aria-busy={!!task.pending}>
    {history && history.length > 0 && <label className="block text-sm">Archived source revision<select aria-label="Archived source revision" className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 focus-visible:outline-2 focus-visible:outline-sky-300"
      value={selectedRevision ? `${selectedRevision.revision}:${selectedRevision.documentSha256}` : ''} onChange={event => {
        const revision = history.find(item => `${item.revision}:${item.documentSha256}` === event.target.value) ?? null;
        setSelectedRevision(revision); setSelectionError(null); persistRevision(datasetId, revision);
      }}>{history.map(item => <option key={`${item.revision}:${item.documentSha256}`} value={`${item.revision}:${item.documentSha256}`}>
        {datasetId} · revision {item.revision} · {item.createdAt} · SHA-256 {item.documentSha256}</option>)}</select></label>}
    {selectionError && <p role="alert" className="text-xs text-amber-200">{selectionError}</p>}
    {history === null && <p role="status" className="text-xs text-slate-400">Loading retained source revisions…</p>}
    {historyError && <p role="alert" className="text-xs text-rose-300">{historyError} Reload the archive to retry.</p>}
    {history?.length === 0 && !historyError && <p className="text-xs text-amber-200">No source revisions have been imported yet.</p>}
    {selectedRevision && <p className="break-all text-xs text-slate-400">Selected source identity: {datasetId} · revision {selectedRevision.revision} · SHA-256 {selectedRevision.documentSha256}</p>}
    {revisionError && <p role="alert" className="text-xs text-rose-300">{revisionError}</p>}
    <div className="flex flex-wrap gap-2">
      <button className={button} disabled={!!task.pending} onClick={() => { void run('current'); setHistoryAttempt(value => value + 1); }}>Reload archive</button>
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
    {data?.current && <div className="text-sm space-y-1"><p>Latest stored revision {data.current.revision} · created {data.current.createdAt}</p><p className="break-all">Latest stored document SHA256: {data.current.documentSha256}</p></div>}
    {data?.preview && <p className="text-xs break-all text-slate-400">Preview SHA256: {data.preview.documentSha256} · expected stored revision {data.preview.expectedRevision}</p>}
    {data?.verification && <div className="border-l-2 border-sky-400 pl-3 text-sm space-y-1"><p>File integrity check · revision {data.verification.revision}</p><p>Checked at {data.verification.verifiedAt}</p><p className="break-all">Checked SHA256: {data.verification.documentSha256}</p><p>Point-in-time byte integrity only; no scientific validation.</p></div>}
    {selectedRevision && archivedDocument && <SourceConditions document={archivedDocument} preview={false}/>}
    {selectedRevision && !archivedDocument && !revisionError && <p role="status" className="text-xs text-slate-400">Loading the selected archived revision…</p>}
    {data?.preview?.document && <SourceConditions document={data.preview.document} preview/>}
    {!selectedRevision && !data?.preview?.document && data?.current?.document
      && <SourceConditions document={data.current.document} preview={false}/>}
  </div>;
}

export function SourceConditions({ document, preview }: { document: LpbfSourceDocument; preview: boolean }) {
  const context = document.sourceContext;
  const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
  const measurement = object(context?.measurement);
  const experiment = object(context?.experiment);
  const transcription = object(context?.transcription);
  const observations = Array.isArray(context?.observations) ? context.observations.map(object) : [];
  const propertySource = document.processScope === 'material-characterization';
  const properties = Array.isArray(context?.property_measurements) ? context.property_measurements.map(object) : [];
  const specimen = object(context?.specimen);
  const absorptanceSource = context?.publisher_artifact_kind === 'publisher-calibrated-absorptance-and-challenge-tables';
  const hasAluminiumRows = observations.some(row => typeof row.material === 'string' && row.material.startsWith('aluminium'));
  const number = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? String(Number(value.toPrecision(4))) : null;
  const known = (value: unknown, reason?: unknown) => typeof value === 'string' || typeof value === 'number' ? String(value)
    : typeof reason === 'string' && reason.startsWith('Not applicable') ? reason
    : `Unknown${typeof reason === 'string' ? ` — ${reason}` : ''}`;
  return <div className="space-y-4 border-t border-slate-700 pt-4">
    <h4 className="font-medium">{preview ? 'Preview source conditions' : 'Stored source conditions'}</h4>
    <dl className="grid gap-3 text-sm sm:grid-cols-3">{[
      ['Material', absorptanceSource && hasAluminiumRows
        ? `${document.materialId.toUpperCase()} (Ti-6Al-4V rows only; aluminium NIST SRM 1241c challenge rows are listed separately and are not an application material)`
        : document.materialId.toUpperCase()], ['Process scope', document.processScope], ['Source version', document.source.version],
      ['Archived files', String(document.artifacts.length)], ['Total bytes', document.artifacts.reduce((sum, item) => sum + item.byteSize, 0).toLocaleString('en-US')],
    ].map(([label, value]) => <div key={label}><dt className="text-xs text-slate-400">{label}</dt><dd>{value}</dd></div>)}</dl>
    <p className="text-sm">{document.source.citation}</p>
    <p className="text-xs break-all text-slate-400">Source: {document.source.url}</p>
    <div className="text-sm"><h5 className="font-medium">Source use terms</h5><p className="mt-1 text-slate-400">{document.source.terms ?? `Unknown: ${document.source.termsMissingReason}`}</p></div>
    <p className="text-sm text-amber-200">{propertySource
      ? 'Primary thermophysical property evidence — unverified candidate for material admission. Measured, derived and fitted quantities are identified separately. This archive does not update the material model, enable full-transient/build-job calculations or establish melt-pool validation.'
      : absorptanceSource
      ? 'NIST measured laser absorptance (integrating sphere) on polished bare Ti-6Al-4V (NIST SRM 654b) and on aluminium (NIST SRM 1241c) challenge tables. Values are measured for the NIST experiment only. The Ti-6Al-4V window means use local analysis windows, not NIST-published phase boundaries. Aluminium has no application material counterpart. This is not validation.'
      : context?.publisher_artifact_kind === 'publisher-workbook-and-readme'
      ? 'These are published NIST bare-plate IN718 measurements with reported expanded uncertainty. Their depth-to-spot-radius ratios are above 3, outside the current conduction-model window, so this source is not eligible for model comparison.'
      : context?.publisher_artifact_kind === 'original-optical-cross-section-micrographs-and-publisher-checksums'
      ? 'Original NIST case 0 optical micrographs and their publisher checksums are archived with six mapped width/depth measurements. These are three tracks on each of two sections from one bare-plate specimen; the model has no matching image observation operator, so this is not validation.'
      : context?.publisher_artifact_kind === 'publisher-optical-cross-section-measurements'
      ? 'This NIST publisher workbook contains individual optical cross-section measurements. The model still needs matched conditions, an optical section operator and numerical convergence before a validation claim.'
      : transcription.kind === 'local-transcription-of-published-aggregate-measurements'
      ? 'This local transcription contains published Table 4 optical width and depth aggregates. Individual cross-sections and images are not included. Bare-plate measurements do not establish powder-bed model validation.'
      : 'Raw camera signal is not measured temperature, melt-pool width or depth. Calibration, units and matching measurement definitions require review. Bare-plate data does not establish powder-bed validation.'}</p>
    {context ? <><h5 className="text-sm font-medium">Measurement conditions and unresolved fields</h5>
      {propertySource ? <>
        <dl className="grid gap-4 text-sm sm:grid-cols-2">{[
          ['Specimen', known(specimen.description)], ['Lot', known(specimen.lot)],
          ['Chemistry', known(specimen.chemistry)], ['Heat treatment', known(specimen.heat_treatment)],
          ['Measurement method', known(measurement.method)], ['Repeat grouping', known(measurement.repeat_group_rule)],
        ].map(([label, value]) => <div key={label}><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-1">{value}</dd></div>)}</dl>
        <div className="overflow-x-auto"><h5 className="mb-2 text-sm font-medium">Thermophysical property evidence</h5>
          <table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-700 text-xs text-slate-400">
            {['Property / units', 'Evidence type', 'Reported temperature coverage', 'Uncertainty', 'Source locator'].map(label => <th key={label} className="p-2">{label}</th>)}
          </tr></thead><tbody>{properties.map((row, index) => <tr key={index} className="border-b border-slate-800">
            <td className="p-2">{known(row.property)} · {known(row.unit)}</td><td className="p-2">{known(row.evidence_type)}</td>
            <td className="p-2">{Array.isArray(row.temperature_range_K) && row.temperature_range_K.length === 2 && row.temperature_range_K.every(value => typeof value === 'number' && Number.isFinite(value))
              ? `${row.temperature_range_K.join('–')} K` : 'Not established; no extrapolation'}</td>
            <td className="p-2">{known(row.uncertainty)}</td><td className="p-2">{known(row.source_locator)}</td>
          </tr>)}</tbody></table></div>
      </> : <dl className="grid gap-4 text-sm sm:grid-cols-2">{[
        ['Machine', known(experiment.machine)], ['Heat treatment', known(experiment.heat_treatment, experiment.heat_treatment_missing_reason)],
        ['Recorded quantity', known(measurement.quantity)], ['Signal units', known(measurement.unit_source, measurement.unit_missing_reason)],
        ['Temperature conversion', known(measurement.temperature_conversion, measurement.temperature_conversion_missing_reason)],
        ['Beam diameter convention', known(measurement.beam_diameter_definition, measurement.beam_diameter_missing_reason)],
        ['Repeat grouping', known(measurement.repeat_group_rule)], ['Evaluation partition', known(context.split)],
      ].map(([label, value]) => <div key={label}><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-1">{value}</dd></div>)}</dl>}
      {absorptanceSource && observations.length > 0 && <div className="overflow-x-auto"><h5 className="mb-2 text-sm font-medium">Published and locally windowed absorptance observations</h5>
        <table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-700 text-xs text-slate-400">
          {['Observation', 'Material', 'Value ± std (unit)', 'Origin / window', 'Comparable with app models'].map(label => <th key={label} className="p-2">{label}</th>)}
        </tr></thead><tbody>{observations.map((row, index) => {
          const value = number(row.value);
          const std = number(row.std_dev);
          const unit = typeof row.unit === 'string' ? row.unit : null;
          const stdUnit = typeof row.std_dev_unit === 'string' ? row.std_dev_unit : unit;
          const window = Array.isArray(row.window_ms) && row.window_ms.length === 2 && row.window_ms.every(item => typeof item === 'number')
            ? `${row.window_ms[0]}–${row.window_ms[1]} ms` : null;
          return <tr key={`${String(row.label)}-${index}`} className="border-b border-slate-800">
            <td className="p-2">{known(row.label)}{typeof row.n === 'number' ? ` · n=${row.n}` : ''}</td>
            <td className="p-2">{known(row.material)}</td>
            <td className="p-2">{value === null ? 'Unavailable — no numeric value in the source record'
              : `${value}${unit ? ` ${unit}` : ''}${std === null ? '' : ` ± ${std}${stdUnit ? ` ${stdUnit}` : ''}`}`}</td>
            <td className="p-2">{row.derived_locally === true ? `Derived locally${window ? `, window ${window} from first laser-on` : ''}` : row.derived_locally === false ? 'NIST-published table value' : 'Origin not recorded'}</td>
            <td className="p-2">{row.comparable_to_app_models === true ? 'Yes' : 'No'}{typeof row.comparable_reason === 'string' ? ` — ${row.comparable_reason}` : ''}</td>
          </tr>;
        })}</tbody></table></div>}
      {!propertySource && !absorptanceSource && observations.length > 0 && <div className="overflow-x-auto"><h5 className="mb-2 text-sm font-medium">Published optical measurements</h5><table className="w-full text-left text-sm"><thead><tr className="border-b border-slate-700 text-xs text-slate-400"><th className="p-2">Machine / section</th><th className="p-2">Track / conditions</th><th className="p-2">Width (µm)</th><th className="p-2">Depth (µm)</th><th className="p-2">Source locator</th></tr></thead><tbody>{observations.map((row, index) => <tr key={`${String(row.imagePath)}-${index}`} className="border-b border-slate-800"><td className="p-2">{String(row.part ?? 'Unknown')}{typeof row.observationCount === 'number' ? ` · n=${row.observationCount}` : ''}</td><td className="p-2">{String(row.caseAndLine ?? 'Unknown')}</td><td className="p-2">{typeof row.measuredWidth_um === 'number' ? `${row.measuredWidth_um.toFixed(3)}${typeof row.widthUncertainty_k2_um === 'number' ? ` ± ${row.widthUncertainty_k2_um.toFixed(3)} (k=2)` : ''}` : 'Unknown'}</td><td className="p-2">{typeof row.measuredDepth_um === 'number' ? `${row.measuredDepth_um.toFixed(3)}${typeof row.depthUncertainty_k2_um === 'number' ? ` ± ${row.depthUncertainty_k2_um.toFixed(3)} (k=2)` : ''}` : 'Unknown'}</td><td className="p-2 font-mono text-xs">{String(row.imagePath ?? 'Unknown')}</td></tr>)}</tbody></table></div>}
      {Array.isArray(context.unresolved) && <ul className="list-disc pl-5 space-y-1 text-sm text-amber-200">{context.unresolved.filter(item => typeof item === 'string').map((item, index) => <li key={index}>{String(item)}</li>)}</ul>}
      <details><summary className="cursor-pointer text-sm">Full source context</summary><pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-300" tabIndex={0} aria-label="Full source context">{JSON.stringify(context, null, 2)}</pre></details></>
      : <p className="text-amber-200">Source context unknown. Measurement conditions have not been established.</p>}
    <details><summary className="cursor-pointer text-sm focus-visible:outline-2 focus-visible:outline-sky-300">Archived file hashes</summary><ul className="mt-3 space-y-3 text-xs">{document.artifacts.map(item => <li key={item.relativePath} className="break-all">{item.relativePath} · {item.byteSize.toLocaleString('en-US')} bytes<br/>SHA256 {item.sha256}</li>)}</ul></details>
  </div>;
}
