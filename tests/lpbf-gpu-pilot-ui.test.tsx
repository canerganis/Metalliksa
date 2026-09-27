import React from 'react';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { renderToStaticMarkup } from 'react-dom/server';
import { GpuPilotArchiveAction, GpuPilotExecutedInputSummary, LpbfEngineeringSimulation, gpuPilotRuntimeLabel } from '../src/components/3d-distortion-lab/LpbfEngineeringSimulation';
import { GpuPilotParityTable, gpuPilotEngineLabel } from '../src/components/LpbfRunArchivePanel';
import { buildGpuPilotInput, parseGpuPilotJob, type GpuPilotInput } from '../src/services/lpbfSimulationService';

test('engineering screen keeps the CUDA pilot visibly separate from standard CPU results', () => {
  const html = renderToStaticMarkup(<LpbfEngineeringSimulation input={{
    material: 'Inconel 718', power_W: 60, speed_mm_s: 1200,
    beamDiameter_um: 80, preheat_C: 25, layer_um: 80, hatch_um: 100,
  }}/>);
  for (const text of ['CUDA thermal parity pilot', 'Run CUDA parity pilot',
    'Explicit CUDA device', 'Numerical CPU/GPU parity only',
    'Experimental validation and qualification are unavailable',
    'A completed bound GPU result can be imported with Save to Archive below',
    'field bytes and numerical evidence are rechecked during import and bundle restore', 'Run simulation']) {
    assert.ok(html.includes(text), text);
  }
  assert.ok(!html.includes('Permanent archive export and restoration remain unavailable'));
  assert.match(html, /aria-label="CUDA device"/);
  assert.match(html, /aria-label="GPU engine"/);
  assert.ok(html.includes('NVIDIA Warp candidate · v2'));
  assert.ok(html.includes('pattern="cuda:[0-9]+"'));
  assert.match(html, /type="submit"/);
});

test('completed bound GPU jobs expose an archive action for that job only', () => {
  const actual = JSON.parse(readFileSync(new URL(
    '../docs/LPBF_GPU_NATIVE_WORKER_ACCEPTANCE_RETRY_2026-09-27/2bcb01e5799041ec9458a947506d491f/result.json',
    import.meta.url), 'utf8')) as { settings: GpuPilotInput } & Record<string, unknown>;
  const jobId = '2bcb01e5799041ec9458a947506d491f';
  const job = parseGpuPilotJob({
    id: jobId, status: 'completed', progress: 1, log: '', error: null,
    requestSummary: { jobType: 'gpu-thermal-pilot', backend: actual.settings.backend,
      mode: actual.settings.mode, material: actual.settings.material },
    result: actual,
  });
  const html = renderToStaticMarkup(<GpuPilotArchiveAction job={job}/>);
  assert.match(html, /aria-label="Archive completed CUDA pilot"/);
  assert.match(html, new RegExp(`data-gpu-job-id="${jobId}"`));
  assert.match(html, /Save to Archive/);
  assert.match(html, /Loading imported source revisions/);

  const unfinished = renderToStaticMarkup(<GpuPilotArchiveAction job={{...job, status: 'running', result: undefined}}/>);
  assert.equal(unfinished, '');

  const legacyResult = {...actual, artifacts: []};
  delete legacyResult.gpuRunContract;
  delete legacyResult.gpuFieldArtifacts;
  const legacy = parseGpuPilotJob({
    id: jobId, status: 'completed', progress: 1, log: '', error: null,
    requestSummary: { jobType: 'gpu-thermal-pilot', backend: actual.settings.backend,
      mode: actual.settings.mode, material: actual.settings.material },
    result: legacyResult,
  });
  assert.equal(renderToStaticMarkup(<GpuPilotArchiveAction job={legacy}/>), '');
});

test('saved CUDA results show their executed inputs and label changed current controls', () => {
  const actual = JSON.parse(readFileSync(new URL(
    '../docs/LPBF_GPU_NATIVE_WORKER_ACCEPTANCE_RETRY_2026-09-27/2bcb01e5799041ec9458a947506d491f/result.json',
    import.meta.url), 'utf8')) as { settings: GpuPilotInput };
  const saved = actual.settings;
  const input = { material: 'Inconel 718', power_W: 60, speed_mm_s: 1200,
    beamDiameter_um: 80, preheat_C: 80, layer_um: 80, hatch_um: 100 };
  const current = buildGpuPilotInput(input, {
    mesh_um: 40, maxDt_s: 2e-7, tracks: 1, layers: 1, trackLength_um: 200,
    stripeWidth_um: 500, islandSize_um: 200, cooling_s: 2e-5, dwell_s: 0,
    scanAngle_deg: 0, layerRotation_deg: 67, timeout_s: 300, packingFraction: .55,
    powderConductivityRatio: .12, convection_W_m2K: 20,
  }, 'cuda:0', 'Inconel 718', 'stripe');
  const matching = renderToStaticMarkup(<GpuPilotExecutedInputSummary
    saved={saved} current={current} bound/>);
  assert.match(matching, /Inputs used by this saved CUDA job/);
  assert.match(matching, /Mesh spacing · µm/);
  assert.match(matching, />40</);
  assert.match(matching, /Stripe width · µm/);
  assert.match(matching, /Island size · µm/);
  assert.match(matching, /Bare-plate geometry/);
  assert.match(matching, /Absorptivity/);
  assert.match(matching, /Omitted\/defaulted fields are not compared/);

  const changed = buildGpuPilotInput(input, {
    mesh_um: 20, maxDt_s: 2e-7, tracks: 1, layers: 1, trackLength_um: 200,
    stripeWidth_um: 500, islandSize_um: 200, cooling_s: 2e-5, dwell_s: 0,
    scanAngle_deg: 0, layerRotation_deg: 67, timeout_s: 300, packingFraction: .55,
    powderConductivityRatio: .12, convection_W_m2K: 20,
  }, 'cuda:0', 'Inconel 718', 'stripe');
  const stale = renderToStaticMarkup(<GpuPilotExecutedInputSummary
    saved={saved} current={changed} bound/>);
  assert.match(stale, /Current submitted fields differ from this saved result: mesh_um/);
  assert.match(stale, /displayed result still belongs to the saved run/);
  assert.match(stale, />40</);

  const legacy = renderToStaticMarkup(<GpuPilotExecutedInputSummary
    saved={saved} current={changed} bound={false}/>);
  assert.match(legacy, /no exact request binding/);
});

test('GPU engine label requires matching outer capture, contract, runtime, settings and solver identities', () => {
  const actual = JSON.parse(readFileSync(new URL(
    '../docs/LPBF_GPU_NATIVE_WORKER_ACCEPTANCE_RETRY_2026-09-27/2bcb01e5799041ec9458a947506d491f/result.json',
    import.meta.url), 'utf8'));
  const torchCapture = {
    schemaVersion: 1, runKind: 'gpu-thermal-pilot',
    contractStatus: 'gpu-pilot-v1-bound',
    inputJson: actual.gpuRunContract.serializedInputs.requestJson,
    materialJson: actual.gpuRunContract.serializedInputs.materialJson,
  };
  assert.equal(gpuPilotEngineLabel(torchCapture, actual), 'PyTorch CUDA · v1');
  const torchRuntimeLabel = gpuPilotRuntimeLabel(actual);
  assert.match(torchRuntimeLabel, /^PyTorch .+ · CUDA runtime .+$/);
  assert.ok(!torchRuntimeLabel.includes('CUDA toolkit'));
  assert.equal(gpuPilotEngineLabel(torchCapture,
    {...actual, solver: {...actual.solver, id: 'enthalpy-fv-6-warp-candidate-1'}}), 'GPU engine unverified');
  const torchCudaSource = structuredClone(actual);
  torchCudaSource.solver.sourceIntegrationDevice = 'cuda:0';
  torchCudaSource.solver.sourceTimestepLimiterDevice = 'cuda:0';
  torchCudaSource.provenance.deviceEvidence.sourceIntegration = 'cuda:0';
  torchCudaSource.provenance.deviceEvidence.sourceTimestepLimiter = 'cuda:0';
  assert.equal(gpuPilotEngineLabel(torchCapture, torchCudaSource), 'PyTorch CUDA · v1');
  const detachedSource = structuredClone(torchCudaSource);
  detachedSource.provenance.deviceEvidence.sourceTimestepLimiter = 'cpu';
  assert.equal(gpuPilotEngineLabel(torchCapture, detachedSource), 'GPU engine unverified');

  const warp = structuredClone(actual);
  warp.settings.executionEngine = 'warp';
  warp.solver.id = 'enthalpy-fv-6-warp-candidate-1';
  warp.solver.modelId = 'stationary-enthalpy-conduction-layer-conforming-v1';
  warp.gpuRunContract.schemaVersion = 2;
  warp.gpuRunContract.capture.contractStatus = 'gpu-pilot-v2-warp-bound';
  warp.gpuRunContract.capture.engineId = 'warp';
  warp.gpuRunContract.capture.modelId = warp.solver.modelId;
  warp.gpuRunContract.serializedInputs.requestJson = JSON.stringify(warp.settings);
  warp.gpuRunContract.hashes.requestHash = createHash('sha256').update(warp.gpuRunContract.serializedInputs.requestJson).digest('hex');
  warp.provenance.inputHash = warp.gpuRunContract.hashes.requestHash;
  warp.provenance.deviceEvidence.engineId = 'warp';
  warp.provenance.deviceEvidence.warp = '1.17.0';
  warp.provenance.deviceEvidence.warpCudaToolkitVersion = '12.9';
  warp.provenance.deviceEvidence.cudaDriverVersion = '13.4';
  delete warp.provenance.deviceEvidence.torch;
  delete warp.provenance.deviceEvidence.cudaRuntime;
  const warpCapture = {
    ...torchCapture, contractStatus: 'gpu-pilot-v2-warp-bound',
    inputJson: warp.gpuRunContract.serializedInputs.requestJson,
  };
  assert.equal(gpuPilotEngineLabel(warpCapture, warp), 'NVIDIA Warp candidate · v2');
  assert.equal(gpuPilotRuntimeLabel(warp), 'Warp 1.17.0 · CUDA toolkit 12.9 · CUDA driver 13.4');
  assert.ok(!gpuPilotRuntimeLabel(warp).includes('CUDA runtime'));
  assert.equal(gpuPilotEngineLabel(torchCapture, warp), 'GPU engine unverified');
  const ambiguousRuntime = structuredClone(warp);
  ambiguousRuntime.provenance.deviceEvidence.cudaRuntime = '12.6';
  assert.equal(gpuPilotEngineLabel(warpCapture, ambiguousRuntime), 'GPU engine unverified');

  const warpJob = parseGpuPilotJob({ id: '2bcb01e5799041ec9458a947506d491f', status: 'completed', progress: 1,
    log: '', error: null, requestSummary: { jobType: 'gpu-thermal-pilot', backend: warp.settings.backend,
      mode: 'standard', material: warp.settings.material, executionEngine: 'warp' }, result: warp });
  const table = renderToStaticMarkup(<GpuPilotParityTable captureValue={warpCapture} resultValue={warpJob.result}/>);
  assert.match(table, /CPU and Warp numerical parity/);
  assert.match(table, /numerical\/model parity · pass/);
  assert.match(table, /experimental validation/);
  assert.match(table, /finalTemperatureField/);
  assert.equal((table.match(/scope="row"/g) ?? []).length, 10);
  assert.match(table, /CPU<!-- -->:|CPU/);
  assert.match(table, /0\.000186667 s · 934 steps/);
  assert.match(table, /Expected end/);
  assert.match(table, /L2 .*Lmax/);
  assert.match(table, /dimensionless/);
  assert.equal(renderToStaticMarkup(<GpuPilotParityTable captureValue={torchCapture} resultValue={warpJob.result}/>), '');
  assert.equal(renderToStaticMarkup(<GpuPilotParityTable captureValue={warpCapture} resultValue={actual}/>), '');
  for (const version of ['0.0', '00.9']) {
    const malformedVersion = structuredClone(warp);
    malformedVersion.provenance.deviceEvidence.cudaDriverVersion = version;
    assert.equal(gpuPilotEngineLabel(warpCapture, malformedVersion), 'GPU engine unverified');
  }
});
