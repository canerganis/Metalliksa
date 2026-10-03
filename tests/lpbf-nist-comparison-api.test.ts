import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import express from 'express';
import { createLpbfRunsRouter } from '../routes/lpbfRuns';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { LpbfNistComparisonService } from '../server/lpbfNistComparisonService';
import { LpbfNistProxyCampaignService } from '../server/lpbfNistProxyCampaignService';
import { LpbfRunArchiveService } from '../server/lpbfRunArchiveService';
import { LpbfRunBundleService } from '../server/lpbfRunBundleService';
import { LpbfRunRepository } from '../server/lpbfRunRepository';
import { nistOpticalTable4CatalogEntry } from '../server/lpbfSourceCatalog';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';

const sha = (value: string) => createHash('sha256').update(value).digest('hex');
const tableRoot = path.resolve('data/benchmark/nist-amb2022-03-optical');

test('NIST optical HTTP gate uses archived exact source and verified bytes, and withholds pilot errors', async t => {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-nist-http-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const runRoot = path.join(root, 'runs'), sourceRoot = path.join(root, 'sources');
  mkdirSync(runRoot); mkdirSync(sourceRoot);
  const runs = new LpbfRunRepository(path.join(runRoot, 'runs.sqlite'));
  const sources = new LpbfSourceRepository(path.join(sourceRoot, 'metadata.sqlite'));
  const runStore = new LpbfArtifactStore(path.join(runRoot, 'artifacts'));
  const sourceStore = new LpbfArtifactStore(path.join(sourceRoot, 'artifacts'));
  const source = nistOpticalTable4CatalogEntry(tableRoot).loadDocument() as any;
  const artifact = source.artifacts[0];
  await sourceStore.putFile(tableRoot, artifact.relativePath, artifact);
  const revision = sources.save(source, 0);
  const exactLink = { datasetId: source.datasetId, revision: revision.revision, documentSha256: revision.documentSha256 };
  source.source.version = '2.0.0'; sources.save(source, 1);

  const job = path.join(root, 'job'); mkdirSync(job);
  writeFileSync(path.join(job, 'field.bin'), 'abc');
  const runArtifact = { path: 'field.bin', size_bytes: 3, sha256: sha('abc') };
  await runStore.putFile(job, runArtifact.path, { relativePath: runArtifact.path,
    sha256: runArtifact.sha256, byteSize: runArtifact.size_bytes });
  const baseResult = { schemaVersion: 1, requestedMode: 'screening', effectiveMode: 'screening',
    fallbackReason: null, validationStatus: 'unvalidated', productionReady: false, confidence: 'low',
    settings: { backend: 'auto', power_W: 0 }, solver: { id: 'rosenthal+goldak', version: 'enthalpy-fv-6' },
    material: { name: 'Synthetic', quality: 'synthetic', source: 'Unit test only' },
    label: 'Screening', regime: 'test', mainRisk: 'test', recommendation: 'test', riskScope: 'test',
    metrics: { width_um: 0, depth_um: 0, length_um: 0 }, assumptions: ['Synthetic only'],
    analyticalComparison: { goldak: { width_um: 0, depth_um: 0, length_um: 0 } },
    provenance: { executionRuntime: null }, artifacts: [runArtifact] };
  const core = { schemaVersion: 1, modelId: 'analytical-conduction-screening-v1',
    actualBackend: 'analytical', requestedBackend: 'auto', effectiveMode: 'screening',
    solverId: 'rosenthal+goldak', evidenceClass: 'unvalidated-model',
    units: { power: 'W', speed: 'mm/s', length: 'um', preheat: 'degC', temperature: 'K',
      internalLength: 'm', time: 's', energy: 'J', beamDiameter: '1/e2-intensity' },
    resolvedPhysics: { conduction: true, transient: false, latentHeat: false,
      momentum: false, freeSurface: false, evaporation: false },
    inputSha256: sha(JSON.stringify(baseResult.settings)), materialSha256: sha(JSON.stringify(baseResult.material)) };
  function saveRun(runId: string, sourcesForRun: typeof exactLink[], bound: boolean,
    runKind?: 'analytical-screening' | 'build-screening' | 'transient-thermal', buildJob = false) {
    const result: any = { ...baseResult, settings: { ...baseResult.settings } };
    if (buildJob) { result.settings.jobType = 'build-job'; result.verdict = 'screening-only'; }
    if (runKind === 'analytical-screening') {
      result.settings.mode = 'screening';
      result.resolvedPhysics = { transient: false };
    }
    if (runKind) {
      result.runKind = runKind;
    }
    if (bound) result.coreContract = { ...core, inputSha256: sha(JSON.stringify(result.settings)) };
    const capture = { schemaVersion: 1 as const, jobId: runId, resultJson: JSON.stringify(result),
      inputJson: JSON.stringify(result.settings), materialJson: JSON.stringify(result.material),
      contractStatus: (bound ? 'core-v1-bound' : 'legacy-unbound') as 'core-v1-bound' | 'legacy-unbound',
      ...(runKind ? { runKind } : {}) };
    runs.save({ schemaVersion: 1, runId, capture, sources: sourcesForRun });
  }
  const boundId = 'a'.repeat(32), legacyId = 'b'.repeat(32), staleId = 'c'.repeat(32);
  const unlinkedId = 'd'.repeat(32), floatId = 'e'.repeat(32);
  const buildId = 'f'.repeat(32);
  const legacyBuildId = '9'.repeat(32);
  const analyticalId = '8'.repeat(32);
  const gpuPilotIds = ['1', '2', '3'].map(value => value.repeat(32));
  saveRun(boundId, [exactLink], true);
  const bundleService = new LpbfRunBundleService(runRoot, sourceRoot, path.join(root, 'bundles'));
  const exportedBundle = await bundleService.export();
  const restoredBundle = await bundleService.restore(exportedBundle.bundleId);
  saveRun(legacyId, [exactLink], false);
  saveRun(staleId, [{ ...exactLink, documentSha256: sha('stale') }], true);
  saveRun(unlinkedId, [], true);
  saveRun(buildId, [exactLink], false, 'build-screening', true);
  saveRun(legacyBuildId, [exactLink], true, undefined, true);
  saveRun(analyticalId, [exactLink], true, 'analytical-screening');
  for (const runId of gpuPilotIds) saveRun(runId, [exactLink], true, 'transient-thermal');
  // These are Python-canonical snapshot bytes: JSON.parse/JSON.stringify changes
  // floatValue:1.0 to 1 and invalidates both the material revision and core hash.
  const materialJson = '{"floatValue":1.0,"materialId":"in718","materialIdentitySchemaVersion":1,"materialRevisionSha256":"1cb5d6833bedd0a8eb9e29606cf0c08b78c4f391f0e89c97c405b8f3e255dba7","name":"Synthetic","provenanceClass":"estimated-legacy","quality":"synthetic","source":"Unit test only"}';
  const floatResult = { ...baseResult, material: JSON.parse(materialJson),
    coreContract: { ...core, materialSha256: '8888b3f9c97a37d2a8f72dc2192aa49e3556950d31c10579cabfe8bb58ac835b' } };
  const floatResultJson = JSON.stringify(floatResult).replace('"floatValue":1', '"floatValue":1.0');
  assert.match(floatResultJson, /"floatValue":1\.0/);
  runs.save({ schemaVersion: 1, runId: floatId,
    capture: { schemaVersion: 1, jobId: floatId, resultJson: floatResultJson,
      inputJson: JSON.stringify(baseResult.settings), materialJson, contractStatus: 'core-v1-bound' },
    sources: [exactLink] });

  const proxyRunIds = ['4', '5', '6'].map(value => value.repeat(32));
  const malformedProxyRunIds = ['0', '7'].map(value => value.repeat(32)).concat(['a0', 'b0'].map(value => value.repeat(16)));
  const proxyResultJson = new Map<string, string>();
  const tableCase = JSON.parse(readFileSync(path.join(tableRoot, artifact.relativePath), 'utf8'))
    .cases.find((item: any) => item.caseNumber === '0');
  function proxySections(trackIndex: number,
    corruption?: 'distance' | 'operator' | 'x-coordinate' | 'linear-fraction') {
    return [4.9, 6.0].map((distance, sectionIndex) => {
      const xCoordinate = -0.005 + distance * 1e-3;
      const linear = trackIndex === 2;
      const sourcePlaneX = linear ? [xCoordinate - 1e-4, xCoordinate + 1e-4] : [xCoordinate];
      return {
        recordId: sectionIndex === 0 ? 'single-line-x-4p9mm' : 'single-line-x-6p0mm',
        status: 'thermal-proxy',
        operator: corruption === 'operator' && sectionIndex === 0
          ? 'unverified-operator' : 'bare-plate-corridor-accepted-peak-x-linear-section-v1',
        scanLineScope: 'one simulated +X track; not experimental repeats',
        distanceFromScanStart_mm: corruption === 'distance' && sectionIndex === 0 ? 4.8 : distance,
        xCoordinate_m: corruption === 'x-coordinate' && sectionIndex === 0 ? xCoordinate + 1e-4 : xCoordinate,
        scanStartX_m: -0.005,
        interpolationOperator: linear
          ? 'linear-interpolation-between-accepted-peak-temperature-planes-v1' : 'exact-cell-center',
        sourcePlaneIndices: linear ? [Math.round(distance * 10), Math.round(distance * 10) + 1] : [Math.round(distance * 10)],
        sourcePlaneX_m: sourcePlaneX,
        interpolationFraction: linear
          ? corruption === 'linear-fraction' && sectionIndex === 0 ? 0.25 : 0.5 : 0,
        width_um: 140 + trackIndex + sectionIndex,
        depth_um: 120 + trackIndex + sectionIndex,
        location: `section ${distance.toFixed(1)} mm from +X scan start`,
        temporalAggregation: 'accepted-step maximum per source X plane, then spatially interpolated',
        contourOperator: 'linear-liquidus-crossings-between-cell-centers-v1',
        sourcePlaneX_um: sourcePlaneX.map(value => value * 1e6),
        sampleCells: 4,
        evidenceScope: 'Numerical thermal proxy; no etched-boundary or experimental validation; one simulated line only',
      };
    });
  }
  function saveProxyRun(runId: string, trackIndex: number,
    corruption?: 'distance' | 'operator' | 'x-coordinate' | 'linear-fraction') {
    const settings = {
      backend: 'auto',
      power_W: tableCase.laserPower_W, speed_mm_s: tableCase.scanSpeed_mm_s,
      beamDiameter_um: tableCase.beamDiameterD4sigma_um, preheat_C: 23.5,
      surfaceMode: 'bare-plate', tracks: 1, layers: 1, trackLength_um: 10000, scanAngle_deg: 0,
    };
    const material = { materialId: 'in718', materialRevisionSha256: sha('proxy-material-revision'),
      name: 'Inconel 718', quality: 'literature', source: 'synthetic service fixture' };
    const inputJson = JSON.stringify(settings), materialJsonForRun = JSON.stringify(material);
    const result = {
      ...baseResult, runKind: 'transient-thermal', requestedMode: 'standard', effectiveMode: 'standard',
      settings, material,
      solver: { ...baseResult.solver, id: 'enthalpy-fv-6' },
      energyBalance: { input_J: 0, losses_J: 0, stored_J: 0, relativeError: 0 },
      massBalance: { initial_kg: 0, deposited_kg: 0, final_kg: 0, relativeError: 0, scope: 'synthetic fixture' },
      phaseAudit: { activeVolume_m3: 0, liquidVolume_m3: 0, solidVolume_m3: 0,
        minFraction: 0, maxFraction: 0, scope: 'synthetic fixture' },
      coreContract: { ...core, modelId: 'stationary-enthalpy-conduction-v1', effectiveMode: 'standard',
        actualBackend: 'numpy-reference', solverId: 'enthalpy-fv-6',
        resolvedPhysics: { conduction: true, transient: true, latentHeat: true,
          momentum: false, freeSurface: false, evaporation: false },
        inputSha256: sha(inputJson), materialSha256: sha(materialJsonForRun) },
      measuredBeamProfileEvidence: { D4sigma_um: tableCase.beamDiameterD4sigma_um },
      scanPath: [{ start: [-0.005, 0], end: [0.005, 0], start_s: 0,
        end_s: 10 / tableCase.scanSpeed_mm_s }],
      barePlateSectionObservations: proxySections(trackIndex, corruption),
    };
    const resultJson = JSON.stringify(result);
    proxyResultJson.set(runId, resultJson);
    runs.save({ schemaVersion: 1, runId,
      capture: { schemaVersion: 1, jobId: runId, resultJson, inputJson, materialJson: materialJsonForRun,
        contractStatus: 'core-v1-bound', runKind: 'transient-thermal' },
      sources: [exactLink] });
  }
  proxyRunIds.forEach((runId, index) => saveProxyRun(runId, index));
  const corruptions = ['distance', 'operator', 'x-coordinate', 'linear-fraction'] as const;
  malformedProxyRunIds.forEach((runId, index) =>
    saveProxyRun(runId, index === 3 ? 2 : index, corruptions[index]));
  runs.close(); sources.close();

  const app = express();
  app.use(createLpbfRunsRouter(new LpbfRunArchiveService(runRoot, sourceRoot),
    bundleService,
    new LpbfNistComparisonService(runRoot, sourceRoot),
    new LpbfNistProxyCampaignService(runRoot, sourceRoot)));
  const server = app.listen(0, '127.0.0.1');
  t.after(() => server.close());
  await new Promise<void>(resolve => server.once('listening', resolve));
  const address = server.address(); assert.ok(address && typeof address !== 'string');
  const endpoint = `http://127.0.0.1:${address.port}/api/lpbf/runs`;
  async function post(runId: string, body: unknown, headers: Record<string, string> = {}) {
    const response = await fetch(`${endpoint}/${runId}/nist-comparison`, { method: 'POST',
      headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
    return { status: response.status, body: await response.json() };
  }
  async function postCampaignPreview(runIds: string[]) {
    const response = await fetch(`${endpoint}/proxy-campaigns/preview`, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ runIds, caseNumber: '0' }) });
    return { status: response.status, body: await response.json() };
  }

  const proxyPreview = await postCampaignPreview(proxyRunIds);
  assert.equal(proxyPreview.status, 200);
  assert.equal(proxyPreview.body.validation.status, 'proxy-screening-only', JSON.stringify(proxyPreview.body.validation));
  assert.equal(proxyPreview.body.validation.comparisonResiduals, null);
  assert.equal(proxyPreview.body.campaign.claimBoundary.opticalOperatorMatched, false);
  assert.equal(proxyPreview.body.campaign.claimBoundary.experimentalValidation, false);
  assert.equal(proxyPreview.body.campaign.tracks.length, 3);
  for (let index = 0; index < proxyRunIds.length; index++) {
    const runId = proxyRunIds[index];
    const track = proxyPreview.body.campaign.tracks[index];
    const resultJson = proxyResultJson.get(runId)!;
    assert.equal(track.runIdentity.runId, runId);
    assert.equal(track.runIdentity.resultArtifact.path, 'capture/result.json');
    assert.equal(track.runIdentity.resultArtifact.sha256, sha(resultJson));
    assert.equal(track.runIdentity.resultArtifact.size_bytes, Buffer.byteLength(resultJson));
    assert.deepEqual(track.observations.map((item: any) => item.distanceFromScanStart_mm), [4.9, 6.0]);
    assert.deepEqual(track.observations.map((item: any) => item.geometry.width_um), [140 + index, 141 + index]);
    assert.deepEqual(track.observations.map((item: any) => item.geometry.depth_um), [120 + index, 121 + index]);
    assert.ok(track.observations.every((item: any) => item.provenance.runIdentity.runId === runId));
  }
  assert.equal(proxyPreview.body.campaign.tracks[2].observations[0].operator.interpolationOperatorId,
    'linear-interpolation-between-accepted-peak-temperature-planes-v1');

  for (const malformedRunId of malformedProxyRunIds) {
    const malformedProxy = await postCampaignPreview([proxyRunIds[0], proxyRunIds[1], malformedRunId]);
    assert.equal(malformedProxy.status, 200);
    assert.equal(malformedProxy.body.campaign, null,
      'the service must reject malformed source section metadata instead of replacing it with expected values');
    assert.equal(malformedProxy.body.validation.status, 'unavailable');
  }

  const createProxy = await fetch(`${endpoint}/proxy-campaigns`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ runIds: proxyRunIds,
      caseNumber: '0', previewSha256: proxyPreview.body.previewSha256 }) });
  assert.equal(createProxy.status, 200);
  const createdProxy = await createProxy.json();
  assert.deepEqual(createdProxy.campaign, proxyPreview.body.campaign);
  assert.deepEqual(createdProxy.record.document, proxyPreview.body.campaign);
  const listedProxy = await fetch(`${endpoint}/proxy-campaigns`, { cache: 'no-store' });
  assert.equal(listedProxy.status, 200);
  assert.equal((await listedProxy.json()).length, 1);

  const valid = await post(boundId, { caseNumber: '0' });
  assert.equal(valid.status, 200);
  assert.equal(valid.body.status, 'unavailable'); assert.equal(valid.body.errors, null);
  assert.equal(valid.body.sourceBinding.revision, 1);
  assert.equal(valid.body.sourceBinding.documentSha256, exactLink.documentSha256);
  assert.equal(valid.body.sourceBinding.artifactSha256, artifact.sha256);
  assert.match(valid.body.reasons.join(' '), /standard CPU transient core/i);
  assert.doesNotMatch(valid.body.reasons.join(' '), /Table 4 parameter rows differ/i);
  const restoredEndpoint = `${endpoint}/bundles/restores/${restoredBundle.restoreId}/runs/${boundId}/nist-comparison`;
  const restoredResponse = await fetch(restoredEndpoint, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ caseNumber: '0' }) });
  assert.equal(restoredResponse.status, 200);
  assert.deepEqual(await restoredResponse.json(), valid.body);
  const withFloat = await post(floatId, { caseNumber: '0' });
  assert.equal(withFloat.status, 200); assert.equal(withFloat.body.status, 'unavailable');
  assert.equal(withFloat.body.errors, null);
  assert.doesNotMatch(withFloat.body.reasons.join(' '), /Table 4 parameter rows differ|material revision identity mismatch|core contract identity mismatch/i);
  assert.match(withFloat.body.reasons.join(' '), /standard CPU transient core/i);
  const legacy = await post(legacyId, { caseNumber: '0' });
  assert.equal(legacy.status, 200); assert.equal(legacy.body.errors, null);
  assert.match(legacy.body.reasons.join(' '), /legacy/i);
  const stale = await post(staleId, { caseNumber: '0' });
  assert.equal(stale.status, 200); assert.equal(stale.body.errors, null);
  assert.match(stale.body.reasons.join(' '), /revision or document SHA-256/i);
  const unlinked = await post(unlinkedId, { caseNumber: '0' });
  assert.equal(unlinked.status, 200); assert.equal(unlinked.body.errors, null);
  assert.match(unlinked.body.reasons.join(' '), /not bound/i);
  const build = await post(buildId, { caseNumber: '0' });
  assert.equal(build.status, 200); assert.equal(build.body.status, 'unavailable');
  assert.match(build.body.reasons.join(' '), /build-job screening captures are not eligible/i);
  const legacyBuild = await post(legacyBuildId, { caseNumber: '0' });
  assert.equal(legacyBuild.status, 200); assert.equal(legacyBuild.body.status, 'unavailable');
  assert.match(legacyBuild.body.reasons.join(' '), /build-job screening captures are not eligible/i);
  const analytical = await post(analyticalId, { caseNumber: '0' });
  assert.equal(analytical.status, 200); assert.equal(analytical.body.status, 'unavailable');
  assert.equal(analytical.body.errors, null);
  assert.match(analytical.body.reasons.join(' '), /analytical screening has no transient thermal evolution/i);
  // These ordinary CPU rows pass repository validation; the temporary projection isolates
  // the NIST eligibility branch and is not a valid GPU archive fixture.
  const originalGet = LpbfRunRepository.prototype.get;
  LpbfRunRepository.prototype.get = function(runId) {
    const record = originalGet.call(this, runId);
    return record && gpuPilotIds.includes(runId) ? { ...record, runKind: 'gpu-thermal-pilot' } : record;
  };
  try {
    const gpuPilot = await post(gpuPilotIds[0], { caseNumber: '0' });
    assert.equal(gpuPilot.status, 200); assert.equal(gpuPilot.body.status, 'unavailable');
    assert.equal(gpuPilot.body.errors, null);
    assert.match(gpuPilot.body.reasons.join(' '), /GPU thermal-pilot archives.*not eligible for CPU-core NIST optical comparison/i);
    const gpuCampaign = await postCampaignPreview(gpuPilotIds);
    assert.equal(gpuCampaign.status, 200); assert.equal(gpuCampaign.body.campaign, null);
    assert.equal(gpuCampaign.body.validation.status, 'unavailable');
    assert.match(gpuCampaign.body.validation.reasons.join(' '), /GPU pilot .*separate from CPU-core proxy eligibility/i);
  } finally {
    LpbfRunRepository.prototype.get = originalGet;
  }

  const extra = await post(boundId, { caseNumber: '0', documentSha256: sha('fake') });
  assert.equal(extra.status, 400);
  const crossSite = await post(boundId, { caseNumber: '0' }, { Origin: 'https://evil.example' });
  assert.equal(crossSite.status, 403);
  const invalid = await post('bad', { caseNumber: '0' });
  assert.equal(invalid.status, 400);

  const runObject = await runStore.verify({ sha256: runArtifact.sha256, byteSize: 3 });
  writeFileSync(runObject.path, 'bad');
  const brokenRun = await post(boundId, { caseNumber: '0' });
  assert.equal(brokenRun.status, 200); assert.equal(brokenRun.body.errors, null);
  assert.match(brokenRun.body.reasons.join(' '), /run output artifact bytes/i);
  const isolatedResponse = await fetch(restoredEndpoint, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ caseNumber: '0' }) });
  assert.equal(isolatedResponse.status, 200);
  assert.deepEqual(await isolatedResponse.json(), valid.body);
  writeFileSync(runObject.path, 'abc');

  const sourceObject = await sourceStore.verify(artifact);
  const originalBytes = readFileSync(sourceObject.path);
  writeFileSync(sourceObject.path, Buffer.alloc(originalBytes.length, 0));
  const brokenTable = await post(boundId, { caseNumber: '0' });
  assert.equal(brokenTable.status, 200); assert.equal(brokenTable.body.errors, null);
  assert.match(brokenTable.body.reasons.join(' '), /transcription bytes/i);
  writeFileSync(path.join(root, 'bundles', 'restores', restoredBundle.restoreId, 'bundle.json'), 'bad');
  const brokenRestore = await fetch(restoredEndpoint, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ caseNumber: '0' }) });
  assert.equal(brokenRestore.status, 409);
});
