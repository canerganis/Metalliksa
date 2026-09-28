import React, { useEffect, useState } from 'react';
import { useInputBoundTask } from '../hooks/useInputBoundTask';
import { listRuns, getRun, getRestoredRun, listRestoredRuns, previewRun, importRun, exportRunBundle, downloadRunBundle,
  importRunBundle, restoreImportedRunBundle, verifyRunBundle, restoreRunBundle,
  compareNistOpticalRun, listNistProxyCampaigns, previewNistProxyCampaign, createNistProxyCampaign,
  type RunPreview, type RunArchiveList, type ExportedRunBundle, type VerifiedRunBundle,
  type RestoredRunBundle, type ImportedRunBundle, type NistProxyCampaignPreview, type NistProxyCampaignRecord } from '../services/lpbfRunArchiveClient';
import { allSourceRevisions, sourceCatalog } from '../services/lpbfSourceService';
import type { RunRecord, RunSourceLink, NistOpticalCaseNumber, NistOpticalReport } from '../types/lpbfRun';

const button = 'rounded-lg border border-slate-600 px-3 py-2 text-sm hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-sky-300 disabled:opacity-40';
const RESTORE_ID_STORAGE_KEY = 'metalliksa.lpbf.lastRestoreId.v1';
const SELECTED_RUN_STORAGE_KEY = 'metalliksa.lpbf.runArchive.selectedRun.v1';
const GPU_ENGINE_UNVERIFIED = 'GPU engine unverified';

type UnknownRecord = Record<string, unknown>;
const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const isSha256 = (value: unknown): value is string =>
  typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
function sameJsonValue(left: unknown, right: unknown): boolean {
  if (left === null || right === null || typeof left !== 'object' || typeof right !== 'object') {
    return Object.is(left, right);
  }
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length
      && left.every((value, index) => sameJsonValue(value, right[index]));
  }
  const leftRecord = left as UnknownRecord;
  const rightRecord = right as UnknownRecord;
  const leftKeys = Object.keys(leftRecord).sort();
  const rightKeys = Object.keys(rightRecord).sort();
  return leftKeys.length === rightKeys.length
    && leftKeys.every((key, index) => key === rightKeys[index]
      && sameJsonValue(leftRecord[key], rightRecord[key]));
}

/** Return an engine label only when the outer archive capture and every v1/v2 engine identity agree. */
export function gpuPilotEngineLabel(captureValue: unknown, resultValue: unknown): string {
  if (!isRecord(captureValue) || !isRecord(resultValue)) return GPU_ENGINE_UNVERIFIED;
  const capture = captureValue;
  const result = resultValue;
  const contract = result.gpuRunContract;
  const settings = result.settings;
  const solver = result.solver;
  const provenance = result.provenance;
  const evidence = isRecord(provenance) ? provenance.deviceEvidence : undefined;
  const contractCapture = isRecord(contract) ? contract.capture : undefined;
  const serialized = isRecord(contract) ? contract.serializedInputs : undefined;
  const hashes = isRecord(contract) ? contract.hashes : undefined;
  const backend = isRecord(settings) ? settings.backend : undefined;
  const cpuSourcesMatch = isRecord(solver) && isRecord(evidence)
    && solver.sourceIntegrationDevice === 'cpu' && solver.sourceTimestepLimiterDevice === 'cpu'
    && evidence.sourceIntegration === 'cpu'
    && (evidence.sourceTimestepLimiter === undefined || evidence.sourceTimestepLimiter === 'cpu');
  const cudaSourcesMatch = typeof backend === 'string'
    && isRecord(solver) && isRecord(evidence)
    && solver.sourceIntegrationDevice === backend && solver.sourceTimestepLimiterDevice === backend
    && evidence.sourceIntegration === backend && evidence.sourceTimestepLimiter === backend;
  if (!isRecord(contract) || !isRecord(contractCapture) || !isRecord(serialized)
      || !isRecord(hashes) || !isRecord(settings) || !isRecord(solver)
      || !isRecord(result.material) || !isRecord(provenance) || !isRecord(evidence)
      || capture.schemaVersion !== 1 || capture.runKind !== 'gpu-thermal-pilot'
      || capture.runKind !== contract.runKind || result.runKind !== 'gpu-thermal-pilot'
      || result.jobType !== 'gpu-thermal-pilot' || settings.jobType !== 'gpu-thermal-pilot'
      || result.requestedMode !== 'standard' || result.effectiveMode !== 'gpu-pilot'
      || result.validationStatus !== 'unvalidated' || result.productionReady !== false
      || result.confidence !== 'low' || Object.hasOwn(result, 'coreContract')
      || capture.inputJson !== serialized.requestJson || capture.materialJson !== serialized.materialJson
      || !isSha256(hashes.requestHash) || !isSha256(hashes.materialHash)
      || !isSha256(hashes.implementationHash) || !isSha256(provenance.inputHash)
      || !isSha256(provenance.implementationHash)
      || hashes.requestHash !== provenance.inputHash
      || hashes.implementationHash !== provenance.implementationHash
      || typeof serialized.requestJson !== 'string' || typeof serialized.materialJson !== 'string'
      || typeof settings.backend !== 'string' || !/^cuda:[0-9]+$/.test(settings.backend)
      || contractCapture.backend !== settings.backend || contractCapture.device !== settings.backend
      || contractCapture.dtype !== 'float64' || solver.dtype !== 'float64'
      || solver.actualBackend !== settings.backend || solver.thermalEvolutionDevice !== settings.backend
      || evidence.selected !== settings.backend || evidence.thermalEvolution !== settings.backend
      || typeof evidence.name !== 'string' || !evidence.name.trim()
      || !Array.isArray(evidence.computeCapability) || evidence.computeCapability.length !== 2
      || evidence.computeCapability.some(value => !Number.isSafeInteger(value) || value < 0)
      || evidence.synchronizedAfterSolve !== true || evidence.engineId !== contractCapture.engineId) {
    return GPU_ENGINE_UNVERIFIED;
  }
  try {
    if (!sameJsonValue(JSON.parse(serialized.requestJson as string), settings)
        || !sameJsonValue(JSON.parse(serialized.materialJson as string), result.material)) {
      return GPU_ENGINE_UNVERIFIED;
    }
  } catch {
    return GPU_ENGINE_UNVERIFIED;
  }

  if (contract.schemaVersion === 2 && contractCapture.contractStatus === 'gpu-pilot-v2-warp-bound'
      && capture.contractStatus === 'gpu-pilot-v2-warp-bound'
      && contractCapture.engineId === 'warp' && settings.executionEngine === 'warp'
      && evidence.engineId === 'warp' && typeof evidence.warp === 'string' && evidence.warp.trim()
      && !Object.hasOwn(evidence, 'torch') && !Object.hasOwn(evidence, 'cudaRuntime')
      && solver.id === 'enthalpy-fv-6-warp-candidate-1'
      && cpuSourcesMatch
      && solver.modelId === 'stationary-enthalpy-conduction-layer-conforming-v1'
      && contractCapture.modelId === solver.modelId
      && typeof evidence.warpCudaToolkitVersion === 'string'
      && /^[1-9][0-9]*\.[0-9]+$/.test(evidence.warpCudaToolkitVersion)
      && typeof evidence.cudaDriverVersion === 'string'
      && /^[1-9][0-9]*\.[0-9]+$/.test(evidence.cudaDriverVersion)) {
    return 'NVIDIA Warp candidate · v2';
  }

  if (contract.schemaVersion === 1 && contractCapture.contractStatus === 'gpu-pilot-v1-bound'
      && capture.contractStatus === 'gpu-pilot-v1-bound'
      && contractCapture.engineId === undefined && settings.executionEngine === undefined
      && evidence.engineId === undefined && typeof evidence.torch === 'string' && evidence.torch.trim()
      && !Object.hasOwn(evidence, 'warp') && !Object.hasOwn(evidence, 'warpCudaToolkitVersion')
      && !Object.hasOwn(evidence, 'cudaDriverVersion')
      && solver.id === 'enthalpy-fv-6-cuda-pilot-1'
      && solver.modelId === 'stationary-enthalpy-conduction-layer-conforming-v1'
      && contractCapture.modelId === solver.modelId
      && (cpuSourcesMatch || cudaSourcesMatch)
      && typeof evidence.cudaRuntime === 'string' && evidence.cudaRuntime.trim()) {
    return 'PyTorch CUDA · v1';
  }

  return GPU_ENGINE_UNVERIFIED;
}

function parseCapturedResult(resultJson: string): unknown {
  try { return JSON.parse(resultJson); } catch { return undefined; }
}

const MATERIAL_PROVENANCE_FIELDS = [
  ['quality', 'Data quality'],
  ['provenanceClass', 'Provenance class'],
  ['source', 'Source'],
  ['uncertaintyNote', 'Uncertainty note'],
  ['materialRevisionSha256', 'Material revision SHA-256'],
] as const;

function materialProvenanceValue(material: UnknownRecord | undefined, key: string): string {
  const value = material?.[key];
  return typeof value === 'string' && value.trim() ? value : 'Not reported';
}

/** Show only provenance recorded on the executed material snapshot. */
export function ExecutedMaterialProvenance({ material, materialPropertySnapshot, materialPropertySha256 }: {
  material: unknown;
  materialPropertySnapshot?: unknown;
  materialPropertySha256?: unknown;
}) {
  const snapshot = isRecord(material) ? material : undefined;
  const buildJobSnapshot = isRecord(materialPropertySnapshot) ? materialPropertySnapshot : undefined;
  const buildJobSnapshotText = buildJobSnapshot ? JSON.stringify(buildJobSnapshot, null, 2) : undefined;
  return <section aria-label="Executed material provenance" className="rounded-lg border border-slate-700/60 p-3 text-sm">
    <h4 className="font-medium">Executed material provenance</h4>
    <p className="mt-1 text-xs text-amber-200">Recorded material metadata. The model remains unvalidated.</p>
    <dl className="mt-3 grid gap-3 sm:grid-cols-2">
      {MATERIAL_PROVENANCE_FIELDS.map(([key, label]) => <div key={key}>
        <dt className="text-xs text-slate-400">{label}</dt>
        <dd className="mt-1 break-all">{materialProvenanceValue(snapshot, key)}</dd>
      </div>)}
    </dl>
    {buildJobSnapshot && <section aria-label="Build-job material property snapshot" className="mt-4 border-t border-slate-700/60 pt-3">
      <h5 className="font-medium">Build-job material property snapshot</h5>
      <p className="mt-1 text-xs text-slate-400">Captured effective identity and properties. This snapshot does not establish source validation.</p>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        <div><dt className="text-xs text-slate-400">Snapshot alloy identity</dt><dd className="mt-1 break-all">{materialProvenanceValue(buildJobSnapshot, 'alloyId')}</dd></div>
        <div><dt className="text-xs text-slate-400">Snapshot schema version</dt><dd className="mt-1">{typeof buildJobSnapshot.schemaVersion === 'number' ? buildJobSnapshot.schemaVersion : 'Not reported'}</dd></div>
        <div className="sm:col-span-2"><dt className="text-xs text-slate-400">Recorded property SHA-256</dt><dd className="mt-1 break-all">{typeof materialPropertySha256 === 'string' && materialPropertySha256.trim() ? materialPropertySha256 : 'Not reported'}</dd></div>
      </dl>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs">Captured thermal and slicer properties</summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded bg-slate-950/60 p-3 text-xs leading-5">{buildJobSnapshotText}</pre>
      </details>
    </section>}
  </section>;
}

/** Decode the archived result snapshot directly; malformed legacy payloads remain display-safe. */
export function ArchivedRunMaterialProvenance({ resultJson }: { resultJson: string }) {
  const result = parseCapturedResult(resultJson);
  return <ExecutedMaterialProvenance
    material={isRecord(result) ? result.material : undefined}
    materialPropertySnapshot={isRecord(result) ? result.materialPropertySnapshot : undefined}
    materialPropertySha256={isRecord(result) ? result.materialPropertySha256 : undefined}
  />;
}

const GPU_PARITY_FIELDS = ['finalSampling', 'finalTemperatureField', 'peakTemperature_K', 'input_J', 'losses_J',
  'stored_J', 'width_um', 'depth_um', 'length_um', 'volume_um3'] as const;
const displayedNumber = (value: unknown) => typeof value === 'number' && Number.isFinite(value)
  ? value.toPrecision(6) : '—';
const displayedCount = (value: unknown) => typeof value === 'number' && Number.isSafeInteger(value) && value > 0
  ? String(value) : '—';

function gpuParityRow(key: typeof GPU_PARITY_FIELDS[number], item: UnknownRecord | undefined,
  targets: UnknownRecord | undefined) {
  const reportedStatus = item && (item.status === 'pass' || item.status === 'failed' || item.status === 'inconclusive')
    ? item.status : 'unavailable';
  if (!item) return { unit: '—', status: 'unavailable', cpu: '—', warp: '—', difference: '—' };
  if (key === 'finalSampling') {
    const complete = ['cpuFinalTime_s', 'gpuFinalTime_s', 'expectedEnd_s'].every(name =>
      typeof item[name] === 'number' && Number.isFinite(item[name]))
      && ['cpuSteps', 'gpuSteps', 'cellCount'].every(name =>
        typeof item[name] === 'number' && Number.isSafeInteger(item[name]) && (item[name] as number) > 0);
    return { unit: 's · steps · cells', status: reportedStatus === 'pass' && !complete ? 'unverified' : reportedStatus,
      cpu: `${displayedNumber(item.cpuFinalTime_s)} s · ${displayedCount(item.cpuSteps)} steps`,
      warp: `${displayedNumber(item.gpuFinalTime_s)} s · ${displayedCount(item.gpuSteps)} steps`,
      difference: `Expected end ${displayedNumber(item.expectedEnd_s)} s · ${displayedCount(item.cellCount)} cells` };
  }
  if (key === 'finalTemperatureField') {
    const l2 = item.relativeRiseL2, maximum = item.relativeRiseMax;
    const l2Target = targets?.fieldRiseL2RelativeMax, maximumTarget = targets?.fieldRiseMaxRelativeMax;
    const complete = [l2, maximum, l2Target, maximumTarget].every(value =>
      typeof value === 'number' && Number.isFinite(value) && value >= 0)
      && typeof item.cpuEncoding === 'string' && !!item.cpuEncoding
      && typeof item.gpuEncoding === 'string' && !!item.gpuEncoding;
    const reason = typeof item.reason === 'string' && item.reason.trim() ? ` · ${item.reason}` : '';
    return { unit: 'dimensionless', status: reportedStatus === 'pass' && !complete ? 'unverified' : reportedStatus,
      cpu: typeof item.cpuEncoding === 'string' ? item.cpuEncoding : '—',
      warp: typeof item.gpuEncoding === 'string' ? item.gpuEncoding : '—',
      difference: complete
        ? `L2 ${displayedNumber(l2)} / ${displayedNumber(l2Target)} target · Lmax ${displayedNumber(maximum)} / ${displayedNumber(maximumTarget)} target${reason}`
        : reason ? reason.slice(3) : 'Field norms unavailable' };
  }
  const unit = key === 'peakTemperature_K' ? 'K'
    : ['input_J', 'losses_J', 'stored_J'].includes(key) ? 'J'
    : key === 'volume_um3' ? 'µm³' : 'µm';
  const differenceValue = item.relativeDifference ?? item.absoluteDifference_um;
  const differenceUnit = item.relativeDifference !== undefined ? 'relative' : 'µm';
  const complete = typeof item.cpu === 'number' && Number.isFinite(item.cpu)
    && typeof item.gpu === 'number' && Number.isFinite(item.gpu)
    && typeof differenceValue === 'number' && Number.isFinite(differenceValue);
  return { unit, status: reportedStatus === 'pass' && !complete ? 'unverified' : reportedStatus,
    cpu: displayedNumber(item.cpu), warp: displayedNumber(item.gpu),
    difference: complete ? `${displayedNumber(differenceValue)} ${differenceUnit}` : 'Delta unavailable' };
}

export function GpuPilotParityTable({ captureValue, resultValue }: { captureValue: unknown; resultValue: unknown }) {
  const pilot = isRecord(resultValue) && isRecord(resultValue.gpuPilot) ? resultValue.gpuPilot : undefined;
  const comparisons = pilot && isRecord(pilot.comparisons) ? pilot.comparisons : undefined;
  if (gpuPilotEngineLabel(captureValue, resultValue) !== 'NVIDIA Warp candidate · v2' || !comparisons) return null;
  const targets = isRecord(pilot.targets) ? pilot.targets : undefined;
  const rows = GPU_PARITY_FIELDS.map(key => gpuParityRow(key,
    isRecord(comparisons[key]) ? comparisons[key] : undefined, targets));
  const reportedModelStatus = pilot.status === 'pass' || pilot.status === 'failed' || pilot.status === 'inconclusive'
    ? pilot.status : 'unavailable';
  const modelStatus = reportedModelStatus === 'pass' && rows.some(row => row.status !== 'pass')
    ? 'unverified' : reportedModelStatus;
  return <section aria-label="CPU and Warp numerical parity" className="space-y-2 rounded-xl border border-slate-700 p-4 text-sm">
    <div><h4 className="font-medium">CPU ↔ Warp numerical/model parity · {modelStatus}</h4>
      <p className="text-xs text-amber-200">Recorded numerical comparison only. This does not establish experimental validation.</p></div>
    <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs">
      <thead><tr className="border-b border-slate-700 text-slate-300">
        <th className="p-2">Quantity</th><th className="p-2">Unit</th><th className="p-2">Status</th>
        <th className="p-2">CPU</th><th className="p-2">Warp</th><th className="p-2">Difference / criterion</th>
      </tr></thead>
      <tbody>{GPU_PARITY_FIELDS.map((key, index) => {
        const row = rows[index];
        return <tr key={key} className="border-b border-slate-800">
          <th scope="row" className="p-2 font-medium">{key}</th><td className="p-2">{row.unit}</td>
          <td className="p-2">{row.status}</td><td className="p-2 font-mono">{row.cpu}</td>
          <td className="p-2 font-mono">{row.warp}</td><td className="p-2 font-mono">{row.difference}</td>
        </tr>;
      })}</tbody>
    </table></div>
  </section>;
}

function savedRestoreId(): string {
  try {
    const value = window.localStorage.getItem(RESTORE_ID_STORAGE_KEY) ?? '';
    return /^[a-f0-9]{32}$/.test(value) ? value : '';
  } catch { return ''; }
}

export function runSelectionForArchive(runIds: string[], savedId: string | null): string {
  return savedId && runIds.includes(savedId) ? savedId : runIds[0] ?? '';
}

type RunSelectionStorage = Pick<Storage, 'getItem' | 'setItem'>;

export function persistRunSelectionForArchive(runId: string,
  getStorage: () => RunSelectionStorage = () => window.localStorage): void {
  if (!/^[a-f0-9]{32}$/.test(runId)) return;
  try { getStorage().setItem(SELECTED_RUN_STORAGE_KEY, runId); } catch { /* Keep the selection for this view. */ }
}

export function restoreRunSelectionForArchive(runIds: string[],
  getStorage: () => RunSelectionStorage = () => window.localStorage): string {
  let storage: RunSelectionStorage | null = null;
  let savedId: string | null = null;
  try {
    storage = getStorage();
    savedId = storage.getItem(SELECTED_RUN_STORAGE_KEY);
  } catch { /* Use the available archive order if browser storage is unavailable. */ }
  const selected = runSelectionForArchive(runIds, savedId && /^[a-f0-9]{32}$/.test(savedId) ? savedId : null);
  if (selected) persistRunSelectionForArchive(selected, () => storage ?? getStorage());
  return selected;
}

function restoredBundleRunSelectionKey(restoreId: string): string {
  return `metalliksa.lpbf.restoredBundle.${restoreId}.selectedRun.v1`;
}

export function restoreRunSelectionForBundle(restoreId: string, runIds: string[],
  getStorage: () => RunSelectionStorage = () => window.localStorage): string {
  const fallback = runIds[0] ?? '';
  if (!/^[a-f0-9]{32}$/.test(restoreId)) return fallback;
  let storage: RunSelectionStorage;
  let savedId: string | null;
  try {
    storage = getStorage();
    savedId = storage.getItem(restoredBundleRunSelectionKey(restoreId));
  } catch { return fallback; }
  const selected = runSelectionForArchive(runIds, savedId && /^[a-f0-9]{32}$/.test(savedId) ? savedId : null);
  if (selected) {
    try { storage.setItem(restoredBundleRunSelectionKey(restoreId), selected); } catch { /* Preserve the verified stored selection in memory. */ }
  }
  return selected;
}

export function persistRunSelectionForBundle(restoreId: string, runId: string,
  getStorage: () => RunSelectionStorage = () => window.localStorage): void {
  if (!/^[a-f0-9]{32}$/.test(restoreId) || !/^[a-f0-9]{32}$/.test(runId)) return;
  try { getStorage().setItem(restoredBundleRunSelectionKey(restoreId), runId); } catch { /* Keep the selection for this view. */ }
}

export function portableBundleSelectionKey(file: Pick<File, 'name' | 'size' | 'lastModified'> | null,
  selectionRevision: number): string {
  return file ? `${selectionRevision}:${file.name}:${file.size}:${file.lastModified}` : `no-file:${selectionRevision}`;
}

export function LpbfRunArchivePanel() {
  const [runs, setRuns] = useState<RunArchiveList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(null); setRuns(null); setSelected('');
    listRuns(controller.signal).then(items => {
      if (!controller.signal.aborted) {
        setRuns(items);
        const runId = restoreRunSelectionForArchive(items.map(item => item.runId));
        setSelected(runId);
      }
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Run archive unavailable.'); });
    return () => controller.abort();
  }, [attempt]);

  return <section aria-label="LPBF run archive" className="rounded-2xl border border-slate-700/70 bg-slate-900/40 p-5 space-y-4">
    <div><h3 className="text-lg font-medium">Simulation Run Archive</h3><p className="mt-1 text-sm text-sky-200">Immutable execution history</p></div>
    <p className="text-sm text-slate-400">Inspect archived simulation runs and import current simulation jobs into the permanent archive.</p>
    {error ? <div><p role="alert" className="text-rose-300">{error}</p><button className={`${button} mt-3`} onClick={() => setAttempt(value => value + 1)}>Retry run archive</button></div>
      : runs === null ? <p role="status">Loading run archive…</p>
      : runs.length === 0 ? <p>No simulation runs archived yet.</p>
      : <><label className="block text-sm">Archived run<select aria-label="Archived run" className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 focus-visible:outline-2 focus-visible:outline-sky-300" value={selected} onChange={event => { setSelected(event.target.value); persistRunSelectionForArchive(event.target.value); }}>{runs.map(item => <option key={item.runId} value={item.runId}>{item.runId.slice(0,8)}... · {item.runKind} · {item.createdAt}</option>)}</select></label>
        {selected && <ArchivedRunRecord key={selected} runId={selected}/>}</>}
    {runs && <NistProxyCampaign runs={runs} />}
    <RunBundleControls />
  </section>;
}

function RunBundleControls() {
  const [bundleId, setBundleId] = useState('');
  const [portableFile, setPortableFile] = useState<File | null>(null);
  const [portableSelectionRevision, setPortableSelectionRevision] = useState(0);
  const [restored, setRestored] = useState<RestoredRunBundle | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [restoreSelection, setRestoreSelection] = useState(() => {
    const restoreId = typeof window === 'undefined' ? '' : savedRestoreId();
    return { input: restoreId, active: restoreId };
  });
  const exportTask = useInputBoundTask<ExportedRunBundle>('run-bundle-export');
  const verifyTask = useInputBoundTask<VerifiedRunBundle>(bundleId);
  const restoreTask = useInputBoundTask<RestoredRunBundle>(bundleId);
  const importTask = useInputBoundTask<ImportedRunBundle>(portableBundleSelectionKey(portableFile, portableSelectionRevision));
  const importedRestoreTask = useInputBoundTask<RestoredRunBundle>(importTask.data?.importId ?? 'no-import');
  const busy = !!(exportTask.pending || verifyTask.pending || restoreTask.pending || importTask.pending || importedRestoreTask.pending);
  const verified = verifyTask.data?.bundleId === bundleId;
  const downloadableBundleId = verified ? bundleId : exportTask.data?.bundleId;

  const rememberRestore = (restoreId: string) => {
    setRestoreSelection({ input: restoreId, active: restoreId });
    try { window.localStorage.setItem(RESTORE_ID_STORAGE_KEY, restoreId); } catch { /* Session state still keeps the restore accessible. */ }
  };

  const runExport = async () => {
    const request = exportTask.begin('export');
    try {
      const result = await exportRunBundle(request.signal);
      if (request.isCurrent()) setBundleId(result.bundleId);
      request.publish(result);
    } catch (error) { request.fail(error); }
    finally { request.finish(); }
  };

  const runVerify = async () => {
    const request = verifyTask.begin('verify');
    try { request.publish(await verifyRunBundle(bundleId, request.signal)); }
    catch (error) { request.fail(error); }
    finally { request.finish(); }
  };

  const runRestore = async () => {
    if (!verified) return;
    const request = restoreTask.begin('restore');
    try {
      const result = await restoreRunBundle(bundleId, request.signal);
      if (request.isCurrent()) rememberRestore(result.restoreId);
      request.publish(result);
    }
    catch (error) { request.fail(error); }
    finally { request.finish(); }
  };

  const runImport = async () => {
    if (!portableFile) return;
    const request = importTask.begin('verify-import');
    try { request.publish(await importRunBundle(portableFile, request.signal)); }
    catch (error) { request.fail(error); }
    finally { request.finish(); }
  };

  const runImportedRestore = async () => {
    const imported = importTask.data;
    if (!imported) return;
    const request = importedRestoreTask.begin('restore-import');
    try {
      const result = await restoreImportedRunBundle(imported.importId, request.signal);
      if (request.isCurrent()) { setRestored(result); rememberRestore(result.restoreId); }
      request.publish(result);
    } catch (error) { request.fail(error); }
    finally { request.finish(); }
  };

  const download = () => {
    if (!downloadableBundleId) return;
    try { downloadRunBundle(downloadableBundleId); setDownloadError(null); }
    catch (error) { setDownloadError(error instanceof Error ? error.message : 'Bundle download failed.'); }
  };

  return <div className="space-y-3 border-t border-slate-700 pt-4" aria-label="Run bundle controls">
    <h4 className="font-medium">Portable run evidence bundle</h4>
    <p className="text-sm text-slate-400">Create and download a portable copy, then upload it on another installation to verify and restore it into an isolated archive. The live run archive remains unchanged.</p>
    <p className="text-xs text-amber-200">Bundle integrity does not validate the model. Runs without archived source links remain legacy-unlinked.</p>
    <button type="button" className={button} disabled={busy} onClick={() => void runExport()}>Create bundle on this installation</button>
    {exportTask.pending && <p role="status">Creating bundle on server…</p>}
    {exportTask.error && <p role="alert" className="text-rose-300">{exportTask.error}</p>}
    {exportTask.data && <p role="status" className="text-emerald-200">Bundle created: {exportTask.data.bundleId}. {exportTask.data.manifest.runCount} runs, {exportTask.data.manifest.artifactCount} run artifacts, {exportTask.data.manifest.sourceLinkCount} source links.</p>}
    {downloadableBundleId && <button type="button" className={button} disabled={busy} onClick={download}>Download portable .tar bundle</button>}
    {downloadError && <p role="alert" className="text-rose-300">{downloadError}</p>}
    <label className="block text-sm">Server-local bundle ID
      <input type="text" aria-label="Server-local bundle ID" spellCheck={false} autoComplete="off" maxLength={32}
        className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 font-mono text-sm focus-visible:outline-2 focus-visible:outline-sky-300"
        value={bundleId} onChange={event => setBundleId(event.target.value.trim())} placeholder="32-character bundle ID" />
    </label>
    <div className="flex flex-wrap gap-2">
      <button type="button" className={button} disabled={busy || !/^[a-f0-9]{32}$/.test(bundleId)} onClick={() => void runVerify()}>Verify bundle</button>
      <button type="button" className={button} disabled={busy || !verified} onClick={() => void runRestore()}>Restore verified copy</button>
    </div>
    {verifyTask.pending && <p role="status">Verifying bundle bytes and references…</p>}
    {verifyTask.error && <p role="alert" className="text-rose-300">{verifyTask.error}</p>}
    {verified && <p role="status" className="text-emerald-200">Bundle verified: {verifyTask.data!.manifest.runCount} runs and {verifyTask.data!.manifest.sourceLinkCount} source links.</p>}
    {restoreTask.pending && <p role="status">Restoring to an isolated server directory…</p>}
    {restoreTask.error && <p role="alert" className="text-rose-300">{restoreTask.error}</p>}
    {restoreTask.data && <p role="status" className="text-emerald-200">Verified copy restored on this server (restore ID: {restoreTask.data.restoreId}). The live archive is unchanged.</p>}
    <div className="space-y-2 border-t border-slate-700 pt-3">
      <h5 className="font-medium">Open an isolated restored archive</h5>
      <label className="block text-sm">Restore ID
        <input type="text" aria-label="Restore ID" spellCheck={false} autoComplete="off" maxLength={32}
          className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 font-mono text-sm focus-visible:outline-2 focus-visible:outline-sky-300"
          value={restoreSelection.input} onChange={event => setRestoreSelection(current => ({ ...current, input: event.target.value.trim() }))}
          placeholder="32-character restore ID" />
      </label>
      <button type="button" className={button} disabled={busy || !/^[a-f0-9]{32}$/.test(restoreSelection.input)}
        onClick={() => {
          const restoreId = restoreSelection.input;
          setRestoreSelection(current => ({ ...current, active: restoreId }));
          try { window.localStorage.setItem(RESTORE_ID_STORAGE_KEY, restoreId); } catch { /* Session state still keeps the restore accessible. */ }
        }}>Open restored archive</button>
    </div>
    {restoreSelection.active && <RestoredBundleRuns key={restoreSelection.active} restoreId={restoreSelection.active} />}
    <div className="space-y-2 border-t border-slate-700 pt-3">
      <h5 className="font-medium">Restore a portable bundle</h5>
      <label className="block text-sm">Run bundle file
        <input type="file" aria-label="Run bundle file" accept=".tar,application/x-tar" className="mt-2 block w-full text-sm"
          onChange={event => { setPortableSelectionRevision(revision => revision + 1); setPortableFile(event.currentTarget.files?.[0] ?? null); setRestored(null); }} />
      </label>
      <button type="button" className={button} disabled={busy || !portableFile} onClick={() => void runImport()}>Upload and verify bundle</button>
      {importTask.pending && <p role="status">Uploading bundle and checking file hashes, run identities, and source revisions…</p>}
      {importTask.error && <p role="alert" className="text-rose-300">{importTask.error}</p>}
      {importTask.data && <p role="status" className="text-emerald-200">Portable bundle verified: {importTask.data.manifest.runCount} runs, {importTask.data.manifest.artifactCount} run artifacts, {importTask.data.manifest.sourceLinkCount} source links.</p>}
      <button type="button" className={button} disabled={busy || !importTask.data} onClick={() => void runImportedRestore()}>Restore verified bundle into isolated archive</button>
      {importedRestoreTask.pending && <p role="status">Restoring a separate, verified copy…</p>}
      {importedRestoreTask.error && <p role="alert" className="text-rose-300">{importedRestoreTask.error}</p>}
      {restored && <p role="status" className="text-emerald-200">Restored copy is ready to open above (restore ID: {restored.restoreId}).</p>}
    </div>
  </div>;
}

function RestoredBundleRuns({ restoreId }: { restoreId: string }) {
  const [runs, setRuns] = useState<RunArchiveList | null>(null);
  const [runId, setRunId] = useState('');
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    listRestoredRuns(restoreId, controller.signal).then(items => {
      if (!controller.signal.aborted) { setRuns(items); setRunId(restoreRunSelectionForBundle(restoreId, items.map(item => item.runId))); }
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Restored records unavailable.'); });
    return () => controller.abort();
  }, [restoreId]);
  return <div className="space-y-2 rounded-lg border border-emerald-500/30 p-3">
    <h5 className="font-medium text-emerald-200">Restored bundle · {restoreId}</h5>
    {error && <p role="alert" className="text-rose-300">{error}</p>}
    {runs === null && !error ? <p role="status">Loading restored run records…</p>
      : runs?.length === 0 ? <p>No run records are present in this bundle.</p>
      : runs && <>
        <label className="block text-sm">Open a restored run<select aria-label="Open a restored run" className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"
          value={runId} onChange={event => { setRunId(event.target.value); persistRunSelectionForBundle(restoreId, event.target.value); }}>{runs.map(item => <option key={item.runId} value={item.runId}>{item.runId.slice(0, 8)}… · {item.runKind} · {item.createdAt}</option>)}</select></label>
        {runId && <ArchivedRunRecord key={runId} restoreId={restoreId} runId={runId} />}
      </>}
  </div>;
}

function ArchivedRunRecord({ runId, restoreId }: { runId: string; restoreId?: string }) {
  const task = useInputBoundTask<RunRecord>(runId);
  
  const run = async (action: 'current') => {
    const request = task.begin(action);
    try {
      request.publish(restoreId ? await getRestoredRun(restoreId, runId, request.signal) : await getRun(runId, request.signal));
    } catch (error) { request.fail(error); }
    finally { request.finish(); }
  };
  useEffect(() => { void run('current'); }, [runId]);
  
  const record = task.data;
  const archivedResult = record ? parseCapturedResult(record.document.capture.resultJson) : undefined;
  const capturedResult = record?.runKind === 'gpu-thermal-pilot' ? archivedResult : undefined;
  const gpuEngine = record?.runKind === 'gpu-thermal-pilot'
    ? gpuPilotEngineLabel(record.document.capture, capturedResult)
    : GPU_ENGINE_UNVERIFIED;
  return <div className="space-y-4" aria-busy={!!task.pending}>
    <div className="flex flex-wrap gap-2">
      <button className={button} disabled={!!task.pending} onClick={() => void run('current')}>Reload run</button>
    </div>
    {task.error && <p role="alert" className="text-rose-300">{task.error}</p>}
    {task.pending && <p role="status" className="text-sm text-slate-300">Loading run record...</p>}
    {record && <div className="text-sm space-y-1">
      <p>Created at {record.createdAt}</p>
      <p>Model status: Unvalidated model</p>
      <p>Run kind: {record.runKind}</p>
      <p>Contract: {record.document.capture.contractStatus === 'gpu-pilot-v2-warp-bound' ? 'Warp GPU pilot v2 bound'
        : record.document.capture.contractStatus === 'gpu-pilot-v1-bound' ? 'PyTorch CUDA pilot v1 bound'
        : record.document.capture.contractStatus === 'legacy-unbound' ? 'Legacy run · core contract unbound' : 'Core v1 bound'}</p>
      <p>Source binding: {record.sourceBindingStatus === 'exact-revision-bound' ? 'Exact archived source revision'
        : record.sourceBindingStatus === 'unverified-source-link' ? 'Unverified source link · archived revision is missing or its hash does not match'
        : 'Legacy run · no archived source revision'}</p>
      <p>Job ID: {record.document.capture.jobId}</p>
      <details><summary className="cursor-pointer font-medium mt-3">Document Payload</summary>
      <pre className="text-xs bg-slate-950 p-3 overflow-auto mt-2 text-slate-300">{JSON.stringify(record.document, null, 2)}</pre>
      </details>
    </div>}
    {record && (record.runKind === 'gpu-thermal-pilot' || (isRecord(archivedResult) && isRecord(archivedResult.material)))
      && <ArchivedRunMaterialProvenance resultJson={record.document.capture.resultJson} />}
    {record?.runKind === 'gpu-thermal-pilot'
      ? <><p className="rounded-lg border border-sky-500/30 p-3 text-sm text-sky-100">GPU thermal pilot · {gpuEngine} parity evidence is archived separately from CPU core runs. NIST optical and CPU proxy comparisons are unavailable for this run kind.</p>
        <GpuPilotParityTable captureValue={record.document.capture} resultValue={capturedResult}/></>
      : record && <NistOpticalComparison record={record} restoreId={restoreId} />}
  </div>;
}

const opticalCases: { id: NistOpticalCaseNumber; label: string }[] = [
  { id: '0', label: 'Case 0 · 285 W · 960 mm/s · 67 µm' },
  { id: '1.1', label: 'Case 1.1 · 285 W · 960 mm/s · 49 µm' },
  { id: '1.2', label: 'Case 1.2 · 285 W · 960 mm/s · 82 µm' },
  { id: '2.1', label: 'Case 2.1 · 285 W · 1200 mm/s · 67 µm' },
  { id: '2.2', label: 'Case 2.2 · 285 W · 800 mm/s · 67 µm' },
  { id: '3.1', label: 'Case 3.1 · 325 W · 960 mm/s · 67 µm' },
  { id: '3.2', label: 'Case 3.2 · 245 W · 960 mm/s · 67 µm' },
];

export function NistOpticalComparison({ record, restoreId }: { record: RunRecord; restoreId?: string }) {
  const [caseNumber, setCaseNumber] = useState<NistOpticalCaseNumber>('0');
  const requestKey = `${restoreId ?? 'live'}:${record.document.runId}:${record.documentSha256}:${caseNumber}`;
  const task = useInputBoundTask<NistOpticalReport>(requestKey);
  const link = record.document.sources.find(source => source.datasetId === 'nist-amb2022-03-optical-table4-local-v1');

  const compare = async () => {
    const request = task.begin('compare');
    try { request.publish(await compareNistOpticalRun(record, caseNumber, request.signal, restoreId)); }
    catch (error) { request.fail(error); }
    finally { request.finish(); }
  };

  const report = task.data;
  return <section aria-label="NIST optical Table 4 comparison" className="space-y-3 rounded-xl border border-slate-700 p-4 text-sm">
    <div><h4 className="font-medium">NIST AMB2022-03 · optical Table 4</h4>
      <p className="text-xs text-amber-200">Literature-model screening · unvalidated. Table 4 is a local transcription of published aggregate measurements.</p></div>
    <p>Run: <span className="font-mono">{record.document.runId}</span></p>
    <p>Run kind: {record.runKind}</p>
    <p>Core contract: {record.document.capture.contractStatus === 'core-v1-bound' ? 'Bound' : 'Legacy unbound'}</p>
    <p>Archived Table 4 link: {link ? <>revision {link.revision} · document SHA-256 <span className="font-mono break-all">{link.documentSha256}</span></>
      : 'Unavailable · this run has no Table 4 source revision link'}</p>
    <label className="block">Published process case
      <select aria-label="NIST Table 4 case" value={caseNumber}
        className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 focus-visible:outline-2 focus-visible:outline-sky-300"
        onChange={event => setCaseNumber(event.target.value as NistOpticalCaseNumber)}>
        {opticalCases.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select>
    </label>
    <button type="button" className={button} disabled={!!task.pending} onClick={() => void compare()}>Compare archived run</button>
    {task.pending && <p role="status">Checking archived run and Table 4 bytes…</p>}
    {task.error && <p role="alert" className="text-rose-300">{task.error}</p>}
    {report && <NistOpticalResult report={report} />}
  </section>;
}

export function NistOpticalResult({ report }: { report: NistOpticalReport }) {
  return <div aria-live="polite" className="space-y-2">
      <p className="font-medium">{report.status === 'unavailable' ? 'Comparison unavailable' : 'Comparable screening result'} · unvalidated</p>
      <p>Verified Table 4 binding: {report.sourceBinding
        ? <>revision {report.sourceBinding.revision} · document SHA-256 <span className="font-mono break-all">{report.sourceBinding.documentSha256}</span></>
        : 'Unavailable'}</p>
      {report.status === 'unavailable' ? <ul className="list-disc space-y-1 pl-5 text-amber-200">
        {report.reasons.map((reason, index) => <li key={`${index}:${reason}`}>{reason}</li>)}
      </ul> : report.errors && <div className="space-y-1 text-slate-200">
        {(['width', 'depth'] as const).map(quantity => <p key={quantity}>
          {quantity === 'width' ? 'Width' : 'Depth'}: signed error {report.errors![quantity].signed_um.toFixed(2)} µm;
          absolute error {report.errors![quantity].absolute_um.toFixed(2)} µm;
          measured mean {report.errors![quantity].measuredMean_um.toFixed(2)} µm;
          published SD {report.errors![quantity].publishedStdDev_um.toFixed(2)} µm.
        </p>)}
      </div>}
    </div>;
}

const proxyCampaignCases: { id: NistOpticalCaseNumber; label: string }[] = [
  { id: '0', label: 'Case 0 · 285 W · 960 mm/s · 67 µm' },
  { id: '1.1', label: 'Case 1.1 · 285 W · 960 mm/s · 49 µm' },
  { id: '1.2', label: 'Case 1.2 · 285 W · 960 mm/s · 82 µm' },
  { id: '2.1', label: 'Case 2.1 · 285 W · 1200 mm/s · 67 µm' },
  { id: '2.2', label: 'Case 2.2 · 285 W · 800 mm/s · 67 µm' },
  { id: '3.1', label: 'Case 3.1 · 325 W · 960 mm/s · 67 µm' },
  { id: '3.2', label: 'Case 3.2 · 245 W · 960 mm/s · 67 µm' },
];

export function NistProxyCampaign({ runs }: { runs: RunArchiveList }) {
  const candidates = runs.filter(run => run.runKind === 'transient-thermal');
  const [savedCampaigns, setSavedCampaigns] = useState<NistProxyCampaignRecord[]>([]);
  const [savedCampaignError, setSavedCampaignError] = useState<string | null>(null);
  const candidateKey = candidates.map(run => run.runId).join(':');
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>(() => candidates.slice(0, 3).map(run => run.runId));
  const [caseNumber, setCaseNumber] = useState<NistOpticalCaseNumber>('0');
  const [selectionKey, setSelectionKey] = useState(candidateKey);
  const currentRunIds = selectionKey === candidateKey ? selectedRunIds : candidates.slice(0, 3).map(run => run.runId);
  useEffect(() => {
    if (selectionKey !== candidateKey) {
      setSelectedRunIds(candidates.slice(0, 3).map(run => run.runId));
      setSelectionKey(candidateKey);
    }
  }, [candidateKey, selectionKey]);
  const inputKey = `${currentRunIds.join(':')}:${caseNumber}`;
  const previewTask = useInputBoundTask<NistProxyCampaignPreview>(inputKey);
  const createTask = useInputBoundTask<{ preview: NistProxyCampaignPreview; record: NistProxyCampaignRecord | null }>(inputKey);
  const canPreview = currentRunIds.length === 3 && currentRunIds.every(Boolean)
    && new Set(currentRunIds).size === 3 && candidates.length >= 3;
  const preview = previewTask.data;
  const saved = createTask.data?.record ?? null;

  useEffect(() => {
    const controller = new AbortController();
    listNistProxyCampaigns(controller.signal).then(items => {
      if (!controller.signal.aborted) setSavedCampaigns(items);
    }).catch(error => {
      if (!controller.signal.aborted) setSavedCampaignError(error instanceof Error ? error.message : 'Saved proxy campaigns unavailable.');
    });
    return () => controller.abort();
  }, []);

  const runPreview = async () => {
    if (!canPreview) return;
    const request = previewTask.begin('preview');
    try { request.publish(await previewNistProxyCampaign(currentRunIds, caseNumber, request.signal)); }
    catch (error) { request.fail(error); }
    finally { request.finish(); }
  };

  const saveCampaign = async () => {
    if (!preview?.campaign || !preview.previewSha256) return;
    const request = createTask.begin('save');
    try {
      const result = await createNistProxyCampaign(currentRunIds, caseNumber, preview.previewSha256, request.signal);
      request.publish({ preview: result, record: result.record ?? null });
      if (result.record) setSavedCampaigns(current => [result.record!, ...current.filter(item => item.campaignId !== result.record!.campaignId)]);
    } catch (error) { request.fail(error); }
    finally { request.finish(); }
  };

  return <section aria-label="NIST proxy campaign" className="space-y-3 rounded-xl border border-slate-700 p-4 text-sm">
    <div><h4 className="font-medium">NIST AMB2022-03 · six-section thermal proxy campaign</h4>
      <p className="mt-1 text-xs text-amber-200">Proxy screening only · unvalidated. This flow records six simulated section observations from three archived runs. It does not calculate optical residuals or claim experimental validation.</p></div>
    {candidates.length < 3 ? <p className="text-slate-300">Three archived transient-thermal runs are required. Available: {candidates.length}.</p>
      : <>
        {currentRunIds.map((runId, index) => <label key={index} className="block">Archived thermal run {index + 1}
          <select aria-label={`Archived thermal run ${index + 1}`} value={runId}
            className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 focus-visible:outline-2 focus-visible:outline-sky-300"
            onChange={event => setSelectedRunIds(current => current.map((value, row) => row === index ? event.target.value : value))}>
            <option value="">Select an archived run</option>{candidates.map(item => <option key={item.runId} value={item.runId}
              disabled={currentRunIds.some((chosen, row) => row !== index && chosen === item.runId)}>{item.runId.slice(0, 8)}… · {item.createdAt}</option>)}
          </select>
        </label>)}
        <label className="block">Published process case
          <select aria-label="NIST proxy campaign case" value={caseNumber}
            className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 focus-visible:outline-2 focus-visible:outline-sky-300"
            onChange={event => setCaseNumber(event.target.value as NistOpticalCaseNumber)}>
            {proxyCampaignCases.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={button} disabled={!canPreview || !!previewTask.pending || !!createTask.pending}
            onClick={() => void runPreview()}>Preview proxy campaign</button>
          <button type="button" className={button} disabled={!preview?.campaign || !preview.previewSha256 || !!previewTask.pending || !!createTask.pending}
            onClick={() => void saveCampaign()}>Archive proxy campaign</button>
        </div>
        {previewTask.pending && <p role="status">Checking the three archived runs and exact Table 4 source revision…</p>}
        {previewTask.error && <p role="alert" className="text-rose-300">{previewTask.error}</p>}
        {preview && <ProxyCampaignSummary result={preview} />}
        {createTask.pending && <p role="status">Saving the immutable proxy campaign record…</p>}
        {createTask.error && <p role="alert" className="text-rose-300">{createTask.error}</p>}
        {saved && <p role="status" className="text-emerald-200">Proxy campaign archived: {saved.campaignId} · SHA-256 {saved.documentSha256}. Status remains unvalidated.</p>}
      </>}
    {savedCampaignError && <p role="alert" className="text-rose-300">Saved proxy campaign archive unavailable: {savedCampaignError}</p>}
    {savedCampaigns.length > 0 && <div aria-label="Saved NIST proxy campaigns" className="space-y-2 border-t border-slate-700 pt-3">
      <h5 className="font-medium">Saved proxy campaigns · unvalidated</h5>
      {savedCampaigns.map(record => <details key={record.campaignId} className="rounded-lg border border-slate-700 p-3">
        <summary className="cursor-pointer">Case {record.document.caseNumber} · {record.createdAt} · {record.campaignId.slice(0, 8)}…</summary>
        <p className="mt-2 text-xs text-slate-300">Thermal proxy screening only · no experimental validation · no optical residuals · SHA-256 {record.documentSha256}</p>
        <ul className="mt-2 space-y-1">{record.document.tracks.flatMap(track => track.observations.map(observation =>
          <li key={`${track.simulatedTrackId}:${observation.sectionId}`}>{track.runIdentity.runId.slice(0, 8)}… · {observation.distanceFromScanStart_mm} mm · simulated width {observation.geometry.width_um.toFixed(2)} µm · depth {observation.geometry.depth_um.toFixed(2)} µm</li>))}</ul>
      </details>)}
    </div>}
  </section>;
}

function ProxyCampaignSummary({ result }: { result: NistProxyCampaignPreview }) {
  if (!result.campaign) return <div className="space-y-2" role="status">
    <p className="font-medium text-amber-200">Proxy campaign unavailable · unvalidated</p>
    <ul className="list-disc space-y-1 pl-5 text-amber-200">{result.validation.reasons.map((reason, index) => <li key={`${index}:${reason}`}>{reason}</li>)}</ul>
  </div>;
  return <div className="space-y-2" aria-live="polite">
    <p className="font-medium">Six thermal-proxy observations · proxy screening only · unvalidated</p>
    <p>Case {result.campaign.caseNumber}; exact archived Table 4 revision {result.campaign.sourceBinding.revision}.</p>
    <p className="text-xs text-slate-300">Experimental validation: no · numerical convergence: not evaluated · comparison residuals: not calculated.</p>
    <ul className="space-y-1 text-slate-200">{result.campaign.tracks.flatMap(track => track.observations.map(observation =>
      <li key={`${track.simulatedTrackId}:${observation.sectionId}`}>
        {track.runIdentity.runId.slice(0, 8)}… · {observation.sectionId === 'x-4p9mm' ? '4.9' : '6.0'} mm · simulated width {observation.geometry.width_um.toFixed(2)} µm · depth {observation.geometry.depth_um.toFixed(2)} µm
      </li>))}</ul>
  </div>;
}

interface ArchivedSourceOption { key: string; label: string; link: RunSourceLink }

export function LpbfJobArchiver({ jobId }: { jobId: string }) {
  const [sourceState, setSources] = useState<{ jobId: string; options: ArchivedSourceOption[] } | null>(null);
  const [sourceError, setSourceError] = useState<{ jobId: string; message: string } | null>(null);
  const [sourceAttempt, setSourceAttempt] = useState(0);
  const [selection, setSelection] = useState<{ jobId: string; key: string } | null>(null);
  const [previewState, setPreview] = useState<{ key: string; value: RunPreview } | null>(null);
  const [importedState, setImported] = useState<{ key: string; value: RunRecord } | null>(null);
  const options = sourceState?.jobId === jobId ? sourceState.options : null;
  const selected = options?.find(item => item.key === (selection?.jobId === jobId ? selection.key : '')) ?? null;
  const requestKey = `${jobId}:${selected?.key ?? ''}`;
  const task = useInputBoundTask<RunPreview | RunRecord>(requestKey);
  const preview = previewState?.key === requestKey && selected ? previewState.value : null;
  const imported = importedState?.key === requestKey && selected ? importedState.value : null;

  useEffect(() => {
    const controller = new AbortController();
    setSources(null); setSourceError(null); setSelection(null); setPreview(null); setImported(null);
    sourceCatalog(controller.signal).then(async catalog => {
      const retained = await Promise.all(catalog.map(async item => ({ item,
        revisions: await allSourceRevisions(item.datasetId, controller.signal) })));
      if (controller.signal.aborted) return;
      const options: ArchivedSourceOption[] = retained.flatMap(({ item, revisions }) => revisions.map(revision => {
        const link = { datasetId: item.datasetId, revision: revision.revision, documentSha256: revision.documentSha256 };
        return { key: `${link.datasetId}:${link.revision}:${link.documentSha256}`,
          label: `${item.title} (${item.datasetId}) · revision ${link.revision} · SHA-256 ${link.documentSha256}`, link };
      }));
      setSources({ jobId, options });
    }).catch(error => {
      if (!controller.signal.aborted) setSourceError({ jobId,
        message: error instanceof Error ? error.message : 'Source revisions unavailable.' });
    });
    return () => controller.abort();
  }, [jobId, sourceAttempt]);

  const runPreview = async () => {
    if (!selected) return;
    const request = task.begin('preview');
    try {
      const result = await previewRun(jobId, [selected.link], request.signal);
      if (request.isCurrent()) setPreview({ key: requestKey, value: result });
      request.publish(result);
    } catch (error) { request.fail(error); }
    finally { request.finish(); }
  };

  const runImport = async () => {
    if (!selected || !preview) return;
    const request = task.begin('import');
    try {
      const result = await importRun(jobId, [selected.link], request.signal);
      if (request.isCurrent()) setImported({ key: requestKey, value: result });
      request.publish(result);
    } catch (error) { request.fail(error); }
    finally { request.finish(); }
  };

  if (imported) {
    return <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-emerald-200">
      <p>Job archived successfully (Run ID: {imported.document.runId.slice(0,8)}...). Model remains unvalidated.</p>
    </div>;
  }

  return <div className="space-y-3 rounded-xl border border-slate-700 p-4">
    <h4 className="font-medium text-sm">Save to Archive</h4>
    <p className="text-xs text-slate-400">Choose an imported source revision for this run. Source archives are unreviewed; linking one does not validate the model.</p>
    {sourceError?.jobId === jobId ? <p role="alert" className="text-xs text-rose-300">{sourceError.message}</p>
      : options === null ? <p role="status" className="text-xs text-slate-400">Loading imported source revisions…</p>
      : options.length === 0 ? <p className="text-xs text-amber-200">No imported source revisions are available. Import a source in the Source archive first.</p>
      : <label className="block text-sm">Imported source revision<select aria-label="Imported source revision"
        className="mt-2 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 focus-visible:outline-2 focus-visible:outline-sky-300"
        value={selected?.key ?? ''} onChange={event => {
          setSelection(event.target.value ? { jobId, key: event.target.value } : null);
          setPreview(null); setImported(null);
        }}><option value="">Select a source revision</option>{options.map(item =>
          <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>}
    {selected && <p className="break-all text-xs text-slate-400">Exact source binding: {selected.link.datasetId} · revision {selected.link.revision} · SHA-256 {selected.link.documentSha256}</p>}
    <button className={button} onClick={() => {
      setSources(null); setSelection(null); setPreview(null); setImported(null);
      setSourceAttempt(value => value + 1);
    }}>Refresh source revisions</button>
    <div className="flex gap-2">
      <button className={button} disabled={!!task.pending || !selected} onClick={runPreview}>Preview Archive</button>
      <button className={button} disabled={!!task.pending || !preview} onClick={runImport}>Archive Job</button>
    </div>
    {task.pending && <p className="text-xs text-slate-400">Processing...</p>}
    {task.error && <p className="text-xs text-rose-300">{task.error}</p>}
    {preview && <div className="text-xs text-slate-300 space-y-1">
      <p>Preview ready: {preview.artifactCount} artifacts, {(preview.byteSize / 1024 / 1024).toFixed(2)} MB.</p>
      <p>Run kind: {preview.document.capture.runKind ?? 'legacy-unspecified'}.</p>
      <p>{preview.document.capture.contractStatus === 'gpu-pilot-v2-warp-bound' ? 'Warp GPU pilot v2 contract bound; complete field artifacts and numerical evidence are checked during archive.'
        : preview.document.capture.contractStatus === 'gpu-pilot-v1-bound' ? 'PyTorch CUDA pilot v1 contract bound; complete field artifacts and numerical evidence are checked during archive.'
        : preview.document.capture.contractStatus === 'legacy-unbound' ? 'Legacy run: core contract unbound.' : 'Core v1 contract bound.'} Model remains unvalidated.</p>
      {preview.quota.approachingLimit && <p className="text-amber-300">Warning: Archive is approaching its capacity limit.</p>}
      <p className="text-slate-500">Archive size: {(preview.quota.totalArchiveSizeBytes / 1024 / 1024 / 1024).toFixed(2)} GB / 15 GB</p>
    </div>}
  </div>;
}
