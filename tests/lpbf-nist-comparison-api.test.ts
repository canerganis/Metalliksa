import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
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
import { getHostPython } from '../server/pythonRuntime';

const sha = (value: string | Uint8Array) => createHash('sha256').update(value).digest('hex');
const tableRoot = path.resolve('data/benchmark/nist-amb2022-03-optical');

function createProxySectionFieldFixture(): { bytes: Buffer; observations: any[] } {
  const python = getHostPython();
  const code = [
    'import base64,json,sys,tempfile',
    'from pathlib import Path',
    'import numpy as np',
    'sys.path.insert(0,"python")',
    'from lpbf_peak import rectangular_corridor_section_samples,rectangular_corridor_section_observations,write_rectangular_corridor_section_field_artifact',
    'mesh=.001; axis_x=-.005+np.arange(11,dtype=np.float64)*mesh',
    'axis_y=np.arange(-.004,.0041,mesh,dtype=np.float64); z=np.arange(-.004,.0001,mesh,dtype=np.float64)',
    'requests=rectangular_corridor_section_samples(axis_x,-.005,.01); fields={}',
    'for index in sorted({i for row in requests for i in row["sourcePlaneIndices"]}):',
    ' field=np.full((len(axis_y),len(z)),300.,dtype=np.float64); field[(np.abs(axis_y)<=.001)[:,None]&((z>=-.003)&(z<=-.001))[None,:]]=1800.; fields[index]=field',
    'observations=rectangular_corridor_section_observations(axis_y,z,fields,requests,mesh,1600.)',
    'with tempfile.TemporaryDirectory() as directory:',
    ' target=Path(directory)/"rectangular-corridor-section-fields.npz"',
    ' write_rectangular_corridor_section_field_artifact(target,axis_x,axis_y,z,observations,fields,mesh,1600.,17)',
    ' print(json.dumps({"bytes":base64.b64encode(target.read_bytes()).decode("ascii"),"observations":observations},allow_nan=False))',
  ].join('\n');
  const generated = spawnSync(python.cmd, [...python.prefix, '-c', code], { encoding: 'utf8', windowsHide: true,
    cwd: process.cwd(), maxBuffer: 4 * 1024 * 1024 });
  if (generated.error || generated.status !== 0) throw generated.error || new Error(`Could not create producer NPZ fixture: ${generated.stderr}`);
  const parsed = JSON.parse(generated.stdout);
  return { bytes: Buffer.from(parsed.bytes, 'base64'), observations: parsed.observations };
}

function alterProxySectionField(bytes: Buffer): Buffer {
  const python = getHostPython();
  const code = [
    'import base64,io,sys',
    'import numpy as np',
    'source=np.load(io.BytesIO(base64.b64decode(sys.stdin.buffer.read())),allow_pickle=False)',
    'arrays={name:source[name].copy() for name in source.files}; source.close()',
    'arrays["temperature_planes_K"][0,2,1]=1801.',
    'output=io.BytesIO(); np.savez_compressed(output,**arrays); sys.stdout.buffer.write(base64.b64encode(output.getvalue()))',
  ].join('\n');
  const changed = spawnSync(python.cmd, [...python.prefix, '-c', code], { input: bytes.toString('base64'),
    encoding: 'utf8', windowsHide: true, cwd: process.cwd(), maxBuffer: 4 * 1024 * 1024 });
  if (changed.error || changed.status !== 0) throw changed.error || new Error(`Could not mutate producer NPZ fixture: ${changed.stderr}`);
  return Buffer.from(changed.stdout.trim(), 'base64');
}

function alterProxySectionArchiveTimestamp(bytes: Buffer): Buffer {
  const python = getHostPython();
  const code = [
    'import base64,io,struct,sys,zipfile',
    'data=bytearray(base64.b64decode(sys.stdin.buffer.read()))',
    'archive=zipfile.ZipFile(io.BytesIO(data),"r")',
    'for info in archive.infolist():',
    ' offset=info.header_offset; timestamp=(1,33)',
    ' if struct.unpack_from("<HH",data,offset+10)!=timestamp: struct.pack_into("<HH",data,offset+10,*timestamp)',
    ' else: timestamp=(2,33); struct.pack_into("<HH",data,offset+10,*timestamp)',
    ' cursor=archive.start_dir; found=False',
    ' while data[cursor:cursor+4]==b"PK\\x01\\x02":',
    '  name_size,extra_size,comment_size=struct.unpack_from("<HHH",data,cursor+28)',
    '  name=data[cursor+46:cursor+46+name_size].decode("utf-8")',
    '  if name==info.filename: struct.pack_into("<HH",data,cursor+12,*timestamp); found=True; break',
    '  cursor+=46+name_size+extra_size+comment_size',
    ' if not found: raise RuntimeError("Could not locate NPZ central-directory entry")',
    'archive.close(); sys.stdout.buffer.write(base64.b64encode(data))',
  ].join('\n');
  const changed = spawnSync(python.cmd, [...python.prefix, '-c', code], { input: bytes.toString('base64'),
    encoding: 'utf8', windowsHide: true, cwd: process.cwd(), maxBuffer: 4 * 1024 * 1024 });
  if (changed.error || changed.status !== 0) throw changed.error || new Error(`Could not mutate NPZ archive metadata: ${changed.stderr}`);
  return Buffer.from(changed.stdout.trim(), 'base64');
}

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
  // Variable (not literal) so the extra relativePath key is not an excess-property error; runtime input is unchanged.
  const runArtifactIdentity = { relativePath: runArtifact.path, sha256: runArtifact.sha256, byteSize: runArtifact.size_bytes };
  await runStore.putFile(job, runArtifact.path, runArtifactIdentity);
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
  const case0ExecutionMutants = ['wrong-diameter', 'wrong-power', 'wrong-speed', 'wrong-preheat',
    'wrong-start', 'wrong-end', 'wrong-timing'] as const;
  const case0ExecutionMutantIds = new Map(case0ExecutionMutants.map((kind, index) => [kind,
    ['d', 'e', 'f'].map(value => `${value}${index}`.repeat(16))]));
  const malformedProxyRunIds = ['0', '7'].map(value => value.repeat(32)).concat(['a0', 'b0', 'c0'].map(value => value.repeat(16)));
  const sectionFailureIds = ['2a', '2b', '2c', '2d', '2e', '2f', '30', '31'].map(value => value.repeat(16));
  const proxyResultJson = new Map<string, string>();
  const tableCase = JSON.parse(readFileSync(path.join(tableRoot, artifact.relativePath), 'utf8'))
    .cases.find((item: any) => item.caseNumber === '0');
  const producerFixture = createProxySectionFieldFixture();
  async function saveProxyRun(runId: string, corruption?: typeof case0ExecutionMutants[number] | 'distance' | 'operator' | 'x-coordinate' | 'linear-fraction'
    | 'missing-descriptor' | 'mismatched-descriptor' | 'missing-manifest'
    | 'changed-width' | 'changed-depth' | 'changed-sample-cells' | 'changed-plane'
    | 'compressed-budget') {
    const settings = {
      backend: 'auto',
      power_W: tableCase.laserPower_W, speed_mm_s: tableCase.scanSpeed_mm_s,
      beamDiameter_um: tableCase.beamDiameterD4sigma_um, preheat_C: 23.5,
      surfaceMode: 'bare-plate', tracks: 1, layers: 1, trackLength_um: 10000, scanAngle_deg: 0, mesh_um: 1000,
    };
    if (corruption === 'wrong-diameter') settings.beamDiameter_um += 1;
    if (corruption === 'wrong-power') settings.power_W += 1;
    if (corruption === 'wrong-speed') settings.speed_mm_s += 1;
    if (corruption === 'wrong-preheat') settings.preheat_C += 2;
    const material = { materialId: 'in718', materialRevisionSha256: sha('proxy-material-revision'),
      name: 'Inconel 718', quality: 'literature', source: 'synthetic service fixture', liquidus_K: 1600 };
    const inputJson = JSON.stringify(settings), materialJsonForRun = JSON.stringify(material);
    const observations = producerFixture.observations.map(row => ({ ...row,
      sourcePlaneIndices: [...row.sourcePlaneIndices], sourcePlaneX_m: [...row.sourcePlaneX_m],
      sourcePlaneX_um: [...row.sourcePlaneX_um] }));
    if (corruption === 'distance') observations[0].distanceFromScanStart_mm = 4.8;
    if (corruption === 'operator') observations[0].operator = 'unverified-operator';
    if (corruption === 'x-coordinate') observations[0].xCoordinate_m += 1e-4;
    if (corruption === 'linear-fraction') observations[0].interpolationFraction = .25;
    if (corruption === 'changed-width') observations[0].width_um += 1;
    if (corruption === 'changed-depth') observations[0].depth_um += 1;
    if (corruption === 'changed-sample-cells') observations[0].sampleCells += 1;
    const sectionBytes = corruption === 'changed-plane' ? alterProxySectionField(producerFixture.bytes)
      : corruption === 'compressed-budget' ? Buffer.concat([producerFixture.bytes, Buffer.alloc(32 * 1024 * 1024)])
        : producerFixture.bytes;
    const sectionJob = path.join(root, `section-${runId}`); mkdirSync(sectionJob);
    writeFileSync(path.join(sectionJob, 'rectangular-corridor-section-fields.npz'), sectionBytes);
    const sectionArtifact = { path: 'rectangular-corridor-section-fields.npz', size_bytes: sectionBytes.length, sha256: sha(sectionBytes) };
    // Variable (not literal) so the extra relativePath key is not an excess-property error; runtime input is unchanged.
    const sectionArtifactIdentity = { relativePath: sectionArtifact.path, sha256: sectionArtifact.sha256, byteSize: sectionArtifact.size_bytes };
    await runStore.putFile(sectionJob, sectionArtifact.path, sectionArtifactIdentity);
    const artifacts = [runArtifact, ...(corruption === 'missing-manifest' ? [] : [sectionArtifact])];
    const scanPath = [{ start: [-0.005, 0], end: [0.005, 0], start_s: 0,
      end_s: 10 / settings.speed_mm_s }];
    if (corruption === 'wrong-start') scanPath[0].start = [-0.004, 0];
    if (corruption === 'wrong-end') scanPath[0].end = [0.004, 0];
    if (corruption === 'wrong-timing') scanPath[0].end_s += 0.1;
    const result = {
      ...baseResult, runKind: 'transient-thermal', requestedMode: 'standard', effectiveMode: 'standard',
      settings, material,
      artifacts,
      discretization: { cells: 1000, mesh_m: .001, steps: 17 },
      barePlateSectionFieldArtifact: corruption === 'missing-descriptor' ? undefined : {
        schemaVersion: 1, status: 'captured',
        path: 'rectangular-corridor-section-fields.npz',
        binding: corruption === 'mismatched-descriptor' ? 'summary-only' : 'accepted-step-maximum-per-source-X-plane',
      },
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
      scanPath,
      barePlateSectionObservations: observations,
    };
    const resultJson = JSON.stringify(result);
    proxyResultJson.set(runId, resultJson);
    runs.save({ schemaVersion: 1, runId,
      capture: { schemaVersion: 1, jobId: runId, resultJson, inputJson, materialJson: materialJsonForRun,
        contractStatus: 'core-v1-bound', runKind: 'transient-thermal' },
      sources: [exactLink] });
  }
  for (const runId of proxyRunIds) await saveProxyRun(runId);
  for (const kind of case0ExecutionMutants) {
    for (const runId of case0ExecutionMutantIds.get(kind)!) await saveProxyRun(runId, kind);
  }
  const corruptions = ['wrong-diameter', 'distance', 'operator', 'x-coordinate', 'linear-fraction'] as const;
  for (let index = 0; index < malformedProxyRunIds.length; index++) await saveProxyRun(malformedProxyRunIds[index], corruptions[index]);
  const sectionCorruptions = ['missing-descriptor', 'mismatched-descriptor', 'missing-manifest',
    'changed-width', 'changed-depth', 'changed-sample-cells', 'changed-plane', 'compressed-budget'] as const;
  const sectionFailureReasons = [
    'Archived run lacks the exact captured section-field artifact descriptor.',
    'Archived run lacks the exact captured section-field artifact descriptor.',
    'Archived run manifest must contain exactly one section-field artifact entry.',
    'result.json section single-line-x-4p9mm width_um is not reproducible',
    'result.json section single-line-x-4p9mm depth_um is not reproducible',
    'result.json section single-line-x-4p9mm status or sampleCells is not reproducible',
    'result.json section single-line-x-4p9mm width_um is not reproducible',
    'compressed-byte budget',
  ];
  for (let index = 0; index < sectionCorruptions.length; index++) await saveProxyRun(sectionFailureIds[index], sectionCorruptions[index]);
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
  async function postCampaignPreview(runIds: string[], caseNumber = '0') {
    const response = await fetch(`${endpoint}/proxy-campaigns/preview`, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ runIds, caseNumber }) });
    return { status: response.status, body: await response.json() };
  }
  async function postCampaignCreate(runIds: string[], caseNumber = '0') {
    const response = await fetch(`${endpoint}/proxy-campaigns`, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ runIds, caseNumber, previewSha256: '0'.repeat(64) }) });
    return { status: response.status, body: await response.json() };
  }

  for (const kind of case0ExecutionMutants) {
    const mutantIds = case0ExecutionMutantIds.get(kind)!;
    const mutantHashes = mutantIds.map(id => JSON.parse(proxyResultJson.get(id)!).coreContract.inputSha256);
    if (kind === 'wrong-diameter' || kind === 'wrong-power' || kind === 'wrong-speed' || kind === 'wrong-preheat') {
      assert.equal(new Set(mutantHashes).size, 1, `${kind} mutant runs share the same recomputed input hash`);
    }
    const mutantPreview = await postCampaignPreview(mutantIds);
    assert.equal(mutantPreview.status, 200, `${kind} mutant returns the service validation envelope`);
    assert.equal(mutantPreview.body.campaign, null, `${kind} mutant must fail service eligibility`);
    assert.ok(mutantPreview.body.validation.reasons.some((reason: string) => reason.includes('required Table 4 case-0 execution settings')),
      `${kind} mutant must fail the shared Table 4 case-0 execution gate`);
    const mutantCreate = await postCampaignCreate(mutantIds);
    assert.equal(mutantCreate.status, 200, `${kind} create mutant returns the service validation envelope`);
    assert.equal(mutantCreate.body.campaign, null, `${kind} mutant must fail service create eligibility`);
    assert.deepEqual(mutantCreate.body.validation.reasons, mutantPreview.body.validation.reasons,
      `${kind} preview and create must use the same eligibility gate`);
  }

  const unsupportedCasePreview = await postCampaignPreview(proxyRunIds, '1.1');
  assert.equal(unsupportedCasePreview.status, 200);
  assert.equal(unsupportedCasePreview.body.campaign, null);
  assert.deepEqual(unsupportedCasePreview.body.validation.reasons, [
    'Proxy campaign v2 currently supports Table 4 case 0 only; other cases are unavailable.',
  ]);

  const proxyPreview = await postCampaignPreview(proxyRunIds);
  assert.equal(proxyPreview.status, 200);
  assert.equal(proxyPreview.body.validation.status, 'proxy-screening-only', JSON.stringify(proxyPreview.body.validation));
  assert.equal(proxyPreview.body.validation.campaignId, proxyPreview.body.campaign.campaignId,
    'successful service validation reports the producer campaign ID');
  assert.equal(proxyPreview.body.validation.comparisonResiduals, null);
  assert.equal(proxyPreview.body.campaign.claimBoundary.opticalOperatorMatched, false);
  assert.equal(proxyPreview.body.campaign.claimBoundary.experimentalValidation, false);
  assert.equal(proxyPreview.body.campaign.tracks.length, 3);
  assert.equal(proxyPreview.body.campaign.schemaVersion, 2);
  const expectedV2CampaignId = sha(JSON.stringify({ schemaVersion: 2, runIds: proxyRunIds, caseNumber: '0',
    revision: proxyPreview.body.campaign.sourceBinding.revision,
    doc: proxyPreview.body.campaign.sourceBinding.documentSha256 })).slice(0, 32);
  const v1FormulaCampaignId = sha(JSON.stringify({ schemaVersion: 1, runIds: proxyRunIds, caseNumber: '0',
    revision: proxyPreview.body.campaign.sourceBinding.revision,
    doc: proxyPreview.body.campaign.sourceBinding.documentSha256 })).slice(0, 32);
  assert.equal(proxyPreview.body.campaign.campaignId, expectedV2CampaignId);
  assert.notEqual(proxyPreview.body.campaign.campaignId, v1FormulaCampaignId,
    'v2 campaign ID is derived from the v2 formula, not the legacy v1 formula');
  assert.deepEqual(proxyPreview.body.campaign.beamInputDeclaration, {
    status: 'published-source-declared', definition: 'D4sigma', value_um: tableCase.beamDiameterD4sigma_um,
    mappingStatus: 'conditional-ideal-Gaussian', measuredProfileMatched: false,
    sourceBinding: proxyPreview.body.campaign.sourceBinding,
  });
  assert.equal(proxyPreview.body.campaign.samplingPlan.replicateSemantics,
    'reproducibility-evidence-not-independent-replicates');
  assert.ok(proxyPreview.body.campaign.tracks.every((track: any) => track.replicateKind === 'reproducibility-execution'));
  for (let index = 0; index < proxyRunIds.length; index++) {
    const runId = proxyRunIds[index];
    const track = proxyPreview.body.campaign.tracks[index];
    const resultJson = proxyResultJson.get(runId)!;
    assert.equal(track.runIdentity.runId, runId);
    assert.equal(track.runIdentity.resultArtifact.path, 'capture/result.json');
    assert.equal(track.runIdentity.resultArtifact.sha256, sha(resultJson));
    assert.equal(track.runIdentity.resultArtifact.size_bytes, Buffer.byteLength(resultJson));
    assert.deepEqual(track.observations.map((item: any) => item.distanceFromScanStart_mm), [4.9, 6.0]);
    assert.deepEqual(track.observations.map((item: any) => item.geometry.width_um),
      producerFixture.observations.map(row => row.width_um));
    assert.deepEqual(track.observations.map((item: any) => item.geometry.depth_um),
      producerFixture.observations.map(row => row.depth_um));
    assert.ok(track.observations.every((item: any) => item.provenance.runIdentity.runId === runId));
  }
  assert.equal(proxyPreview.body.campaign.tracks[0].observations[0].operator.interpolationOperatorId,
    'linear-interpolation-between-accepted-peak-temperature-planes-v1');
  assert.equal(proxyPreview.body.campaign.tracks[0].observations[1].operator.interpolationOperatorId, 'exact-cell-center');

  for (const malformedRunId of malformedProxyRunIds) {
    const malformedProxy = await postCampaignPreview([proxyRunIds[0], proxyRunIds[1], malformedRunId]);
    assert.equal(malformedProxy.status, 200);
    assert.equal(malformedProxy.body.campaign, null,
      'the service must reject malformed source section metadata instead of replacing it with expected values');
    assert.equal(malformedProxy.body.validation.status, 'unavailable');
  }

  for (let index = 0; index < sectionFailureIds.length; index++) {
    const malformedRunId = sectionFailureIds[index];
    const malformedProxy = await postCampaignPreview([proxyRunIds[0], proxyRunIds[1], malformedRunId]);
    assert.equal(malformedProxy.status, 200);
    assert.equal(malformedProxy.body.campaign, null,
      'the service must reject missing bindings and any non-reproducible archived section');
    assert.equal(malformedProxy.body.validation.status, 'unavailable');
    assert.ok(malformedProxy.body.validation.reasons.some((reason: string) => reason.includes(sectionFailureReasons[index])),
      `expected specific section failure reason: ${sectionFailureReasons[index]}`);
  }
  const noPythonReader = new LpbfNistProxyCampaignService(runRoot, sourceRoot, async () => {
    throw new Error('Python NPZ re-derivation reader is unavailable.');
  });
  const unavailablePreview = await noPythonReader.preview(proxyRunIds, '0');
  assert.equal(unavailablePreview.campaign, null);
  assert.equal(unavailablePreview.validation.status, 'unavailable');
  assert.match(unavailablePreview.validation.reasons.join(' '), /section-field artifact verification failed/i);

  const verifiedSection = JSON.parse(proxyResultJson.get(proxyRunIds[0])!).artifacts
    .find((item: any) => item.path === 'rectangular-corridor-section-fields.npz');
  const verifiedSectionPath = path.join(runRoot, 'artifacts', 'objects', verifiedSection.sha256.slice(0, 2), verifiedSection.sha256);
  const originalVerify = LpbfArtifactStore.prototype.verify;
  let sectionVerifications = 0;
  LpbfArtifactStore.prototype.verify = async function(ref) {
    const verified = await originalVerify.call(this, ref);
    if (ref.sha256 === verifiedSection.sha256 && ++sectionVerifications === 4) {
      const sameSizeMutation = alterProxySectionArchiveTimestamp(producerFixture.bytes);
      assert.equal(sameSizeMutation.length, producerFixture.bytes.length, 'NPZ reread mutation must preserve byte length');
      assert.notEqual(sha(sameSizeMutation), sha(producerFixture.bytes), 'NPZ reread mutation must change its digest');
      writeFileSync(verified.path, sameSizeMutation);
    }
    return verified;
  };
  let rereadMismatch;
  try {
    rereadMismatch = await new LpbfNistProxyCampaignService(runRoot, sourceRoot).preview(proxyRunIds, '0');
  } finally {
    LpbfArtifactStore.prototype.verify = originalVerify;
    writeFileSync(verifiedSectionPath, producerFixture.bytes);
  }
  assert.equal(rereadMismatch.campaign, null);
  assert.match(rereadMismatch.validation.reasons.join(' '), /changed or failed SHA-256 verification after store verification/i);

  const sectionArtifactPath = verifiedSectionPath;
  const originalVerifyForReadFailure = LpbfArtifactStore.prototype.verify;
  let sectionReadAttempts = 0;
  LpbfArtifactStore.prototype.verify = async function(ref) {
    if (ref.sha256 === verifiedSection.sha256 && ++sectionReadAttempts === 4) {
      const error = new Error(`ENOENT: no such file or directory, open '${sectionArtifactPath}'`) as NodeJS.ErrnoException;
      error.code = 'ENOENT';
      throw error;
    }
    return originalVerifyForReadFailure.call(this, ref);
  };
  let sanitizedReadFailure;
  try {
    sanitizedReadFailure = await new LpbfNistProxyCampaignService(runRoot, sourceRoot).preview(proxyRunIds, '0');
  } finally {
    LpbfArtifactStore.prototype.verify = originalVerifyForReadFailure;
  }
  assert.equal(sanitizedReadFailure.campaign, null);
  const sanitizedReason = sanitizedReadFailure.validation.reasons.join(' ');
  assert.match(sanitizedReason, /section-field artifact verification failed/i);
  assert.ok(!sanitizedReason.includes(sectionArtifactPath), 'filesystem failure messages must not disclose artifact paths');

  const table4Binding = proxyPreview.body.campaign.sourceBinding;
  const sourceArtifactSha = table4Binding.artifactSha256;
  const originalSourceVerify = LpbfArtifactStore.prototype.verify;
  let sourceArtifactPath = '';
  let originalTable4Bytes: Buffer | null = null;
  let table4Verifications = 0;
  LpbfArtifactStore.prototype.verify = async function(ref) {
    const verified = await originalSourceVerify.call(this, ref);
    if (ref.sha256 === sourceArtifactSha && ++table4Verifications === 1) {
      sourceArtifactPath = verified.path;
      const capturedBytes = readFileSync(verified.path);
      originalTable4Bytes = capturedBytes;
      const originalText = capturedBytes.toString('utf8');
      const changedText = originalText.replace(': ', ':\t');
      assert.notEqual(changedText, originalText, 'fixture must contain JSON whitespace to mutate');
      assert.equal(Buffer.byteLength(changedText), capturedBytes.length, 'Table 4 mutation must preserve byte size');
      assert.deepEqual(JSON.parse(changedText), JSON.parse(originalText), 'case-0 settings and all Table 4 values stay unchanged');
      writeFileSync(verified.path, Buffer.from(changedText, 'utf8'));
    }
    return verified;
  };
  let table4RereadMismatch;
  try {
    table4RereadMismatch = await new LpbfNistProxyCampaignService(runRoot, sourceRoot).preview(proxyRunIds, '0');
  } finally {
    LpbfArtifactStore.prototype.verify = originalSourceVerify;
    if (originalTable4Bytes && sourceArtifactPath) writeFileSync(sourceArtifactPath, originalTable4Bytes);
  }
  assert.equal(table4Verifications, 1, 'test must mutate the source artifact only after its successful store verification');
  assert.equal(table4RereadMismatch.campaign, null);
  assert.match(table4RereadMismatch.validation.reasons.join(' '), /Table 4 source artifact bytes failed exact SHA-256 verification/i);

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
  const forgedDeclaration = await fetch(`${endpoint}/proxy-campaigns/preview`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ runIds: proxyRunIds, caseNumber: '0',
      beamInputDeclaration: proxyPreview.body.campaign.beamInputDeclaration }) });
  assert.equal(forgedDeclaration.status, 400);
  const forgedCreateDeclaration = await fetch(`${endpoint}/proxy-campaigns`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ runIds: proxyRunIds, caseNumber: '0',
      previewSha256: proxyPreview.body.previewSha256,
      beamInputDeclaration: { ...proxyPreview.body.campaign.beamInputDeclaration, value_um: 999 } }) });
  assert.equal(forgedCreateDeclaration.status, 400);

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
