import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createNistProxyCampaign, listNistProxyCampaigns, previewNistProxyCampaign } from '../src/services/lpbfRunArchiveClient';

const runIds = ['a'.repeat(32), 'b'.repeat(32), 'c'.repeat(32)];
const signal = new AbortController().signal;
const previewSha256 = 'd'.repeat(64);

function campaignDocument() {
  const sourceBinding = { datasetId: 'nist-amb2022-03-optical-table4-local-v1', revision: 4,
    documentSha256: 'f'.repeat(64), artifactPath: 'table4-aggregate-v2.json',
    artifactSha256: 'd1b36dfa2e01a3537093c481e249ce52df6b8879c1c67480ddb9aa10799133da',
    artifactSizeBytes: 4321, caseNumber: '0' };
  const identity = (runId: string, index: number) => ({ runId, runDocumentSha256: String(index + 1).repeat(64),
    resultArtifact: { path: 'capture/result.json', sha256: '8'.repeat(64), size_bytes: 2048 },
    inputSha256: '7'.repeat(64), materialSha256: '6'.repeat(64), materialId: 'in718',
    materialRevisionSha256: '5'.repeat(64), coreContract: { schemaVersion: 1, modelId: 'stationary-enthalpy-conduction-v1',
      solverId: 'enthalpy-fv-6', actualBackend: 'numpy-reference' } });
  return { schemaVersion: 1, kind: 'lpbf-nist-amb2022-03-proxy-campaign', campaignId: 'e'.repeat(32),
    benchmark: 'AMB2022-03-TMPG', caseNumber: '0', sourceBinding,
    claimBoundary: { resultKind: 'thermal-proxy-screening', validationStatus: 'unvalidated',
      experimentalValidation: false, opticalOperatorMatched: false },
    samplingPlan: { coordinateFrame: 'scan-start-relative', scanDirection: '+X', sectionPositions_mm: [4.9, 6],
      expectedTrackCount: 3, expectedObservationCount: 6, replicateSemantics: 'independent-computational-runs-only' },
    tracks: runIds.map((runId, index) => ({ simulatedTrackId: `sim-${runId}`, experimentalTrackId: null,
      replicateKind: 'independent-computational-run',
      runIdentity: identity(runId, index),
      observations: [
        { sectionId: 'x-4p9mm', coordinateFrame: 'scan-start-relative', scanDirection: '+X', distanceFromScanStart_mm: 4.9,
          surfaceZ_m: 0, status: 'thermal-proxy', geometry: { width_um: 100 + index, depth_um: 50 + index },
          operator: { sectionOperatorId: 'section-v1', interpolationOperatorId: 'linear-v1', contourOperatorId: 'crossing-v1', evidenceClass: 'thermal-proxy-only' },
          provenance: { sourceBinding, runIdentity: identity(runId, index) } },
        { sectionId: 'x-6p0mm', coordinateFrame: 'scan-start-relative', scanDirection: '+X', distanceFromScanStart_mm: 6,
          surfaceZ_m: 0, status: 'thermal-proxy', geometry: { width_um: 101 + index, depth_um: 51 + index },
          operator: { sectionOperatorId: 'section-v1', interpolationOperatorId: 'linear-v1', contourOperatorId: 'crossing-v1', evidenceClass: 'thermal-proxy-only' },
          provenance: { sourceBinding, runIdentity: identity(runId, index) } },
      ] })),
  };
}

function v2CampaignDocument() {
  const legacy = campaignDocument();
  const sourceBinding = legacy.sourceBinding;
  return { ...legacy, schemaVersion: 2, beamInputDeclaration: { status: 'published-source-declared',
    definition: 'D4sigma', value_um: 67, mappingStatus: 'conditional-ideal-Gaussian',
    measuredProfileMatched: false, sourceBinding },
  samplingPlan: { ...legacy.samplingPlan, replicateSemantics: 'reproducibility-evidence-not-independent-replicates' },
  tracks: legacy.tracks.map(track => ({ ...track, replicateKind: 'reproducibility-execution' })) };
}

const validation = { schemaVersion: 1, kind: 'lpbf-nist-amb2022-03-proxy-campaign-validation',
  status: 'proxy-screening-only', validationStatus: 'unvalidated', experimentalValidation: false,
  numericalConvergenceStatus: 'not-evaluated', comparisonResiduals: null, observationCount: 6, reasons: [] };

test('proxy campaign preview sends only three archived IDs and case and accepts no residual output', async t => {
  const campaign = campaignDocument();
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ campaign,
    validation, previewSha256 })));
  const result = await previewNistProxyCampaign(runIds, '0', signal);
  assert.equal(result.campaign?.tracks.length, 3);
  const [url, init] = fetchMock.mock.calls[0].arguments as [string, RequestInit];
  assert.equal(url, '/api/lpbf/runs/proxy-campaigns/preview');
  assert.deepEqual(JSON.parse(init.body as string), { runIds, caseNumber: '0' });
});

test('proxy campaign save requires exact preview hash and immutable record identity', async t => {
  const campaign = campaignDocument();
  const record = { campaignId: campaign.campaignId, document: campaign, documentSha256: '9'.repeat(64),
    createdAt: '2026-09-25T10:00:00.000Z' };
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ campaign, validation,
    previewSha256, record })));
  const result = await createNistProxyCampaign(runIds, '0', previewSha256, signal);
  assert.equal(result.record?.campaignId, campaign.campaignId);
  const [url, init] = fetchMock.mock.calls[0].arguments as [string, RequestInit];
  assert.equal(url, '/api/lpbf/runs/proxy-campaigns');
  assert.deepEqual(JSON.parse(init.body as string), { runIds, caseNumber: '0', previewSha256 });
});

test('proxy campaign client accepts v2 declared input while preserving legacy v1 records', async t => {
  const campaign = v2CampaignDocument();
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ campaign, validation, previewSha256 })));
  const result = await previewNistProxyCampaign(runIds, '0', signal);
  assert.equal(result.campaign?.schemaVersion, 2);
  assert.equal(result.campaign?.beamInputDeclaration?.value_um, 67);
  assert.equal(result.campaign?.tracks[0].replicateKind, 'reproducibility-execution');
  t.mock.restoreAll();
});

test('proxy campaign client rejects isolated v2 declaration, root, and replicate mutations', async t => {
  const valid = v2CampaignDocument();
  const invalids: [string, (campaign: any) => void][] = [
    ['wrong definition', campaign => { campaign.beamInputDeclaration.definition = 'FWHM'; }],
    ['wrong mappingStatus', campaign => { campaign.beamInputDeclaration.mappingStatus = 'measured'; }],
    ['missing declaration', campaign => { delete campaign.beamInputDeclaration; }],
    ['unknown root key', campaign => { campaign.unexpected = true; }],
    ['wrong replicateSemantics', campaign => { campaign.samplingPlan.replicateSemantics = 'independent-computational-runs-only'; }],
    ['wrong replicateKind', campaign => { campaign.tracks[0].replicateKind = 'independent-computational-run'; }],
  ];
  for (const [label, mutate] of invalids) {
    const campaign = structuredClone(valid);
    mutate(campaign);
    t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ campaign, validation, previewSha256 })));
    await assert.rejects(previewNistProxyCampaign(runIds, '0', signal), /invalid/i, label);
    t.mock.restoreAll();
  }
});

test('proxy campaign client rejects residuals, validation claims, and untrusted measurements', async t => {
  const campaign = campaignDocument();
  for (const invalid of [
    { campaign, validation: { ...validation, comparisonResiduals: [1] }, previewSha256 },
    { campaign, validation: { ...validation, experimentalValidation: true }, previewSha256 },
    { campaign: { ...campaign, measuredWidth_um: 100 }, validation, previewSha256 },
  ]) {
    t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(invalid)));
    await assert.rejects(previewNistProxyCampaign(runIds, '0', signal), /invalid/i);
    t.mock.restoreAll();
  }
});

test('unavailable proxy campaign retains reasons and disables the create contract', async t => {
  const body = { campaign: null, validation: { schemaVersion: 1,
    kind: 'lpbf-nist-amb2022-03-proxy-campaign-validation', status: 'unavailable',
    validationStatus: 'unvalidated', experimentalValidation: false, numericalConvergenceStatus: 'not-evaluated',
    comparisonResiduals: null, observationCount: null, reasons: ['The archived source binding is unavailable.'] } };
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(body)));
  const result = await previewNistProxyCampaign(runIds, '0', signal);
  assert.equal(result.campaign, null);
  assert.match(result.validation.reasons[0], /source binding/);
});

test('saved proxy campaign list preserves exact run, source and unvalidated record identity', async t => {
  const campaign = campaignDocument();
  const record = { campaignId: campaign.campaignId, document: campaign,
    documentSha256: '9'.repeat(64), createdAt: '2026-09-25T10:00:00.000Z' };
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify([record])));
  const result = await listNistProxyCampaigns(signal);
  assert.equal(result.length, 1);
  assert.equal(result[0].document.campaignId, campaign.campaignId);
  const [url, init] = fetchMock.mock.calls[0].arguments as [string, RequestInit];
  assert.equal(url, '/api/lpbf/runs/proxy-campaigns');
  assert.equal(init.method, undefined);
  t.mock.restoreAll();
  const changed = { ...record, document: { ...campaign, tracks: campaign.tracks.slice(0, 2) } };
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify([changed])));
  await assert.rejects(listNistProxyCampaigns(signal), /invalid/i);
});

test('saved proxy campaign list reads v1 and v2 records with distinct identities', async t => {
  const v1 = campaignDocument();
  const v2 = v2CampaignDocument();
  v2.campaignId = 'f'.repeat(32);
  const records = [v1, v2].map((document, index) => ({ campaignId: document.campaignId, document,
    documentSha256: String(index + 1).repeat(64), createdAt: `2026-09-2${index + 5}T10:00:00.000Z` }));
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(records)));
  const result = await listNistProxyCampaigns(signal);
  assert.deepEqual(result.map(record => record.document.schemaVersion), [1, 2]);
  assert.notEqual(result[0].campaignId, result[1].campaignId);
});
