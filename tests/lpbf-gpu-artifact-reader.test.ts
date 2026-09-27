import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test, type TestContext } from 'node:test';
import { readGpuPilotArtifacts, readGpuPilotArtifactBytes } from '../server/lpbfGpuPilotArtifacts';
import { verifyLocalArtifact } from '../server/lpbfArtifactStore';
import { getHostPython } from '../server/pythonRuntime';
import { GPU_ARTIFACT_UNITS, type GpuPilotArtifactDescriptor } from '../src/types/lpbfGpuArtifacts';

async function fixture(t: TestContext) {
  const root = await mkdtemp(path.join(tmpdir(), 'lpbf-gpu-artifact-read-'));
  t.after(async () => {
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    await rm(root, { recursive: true, force: true });
  });
  await mkdir(path.join(root, 'gpu-pilot'));
  const descriptor: GpuPilotArtifactDescriptor = { schemaVersion: 1, kind: 'lpbf-final-field-parity-evidence',
    encoding: 'float64-le', order: 'C', enthalpyReference: 'volumetric-excess-relative-to-initial-temperature', states: {} as any };
  for (const backend of ['cpu', 'gpu'] as const) {
    const values = { coordinates_m: [-0, 1, 2, 3, 4, 5], temperature_K: [300, 301],
      enthalpy_J_m3: [-1, 2], density_kg_m3: [8440, 8440],
      accepted_dt_s: backend === 'cpu' ? [.25, .25, .25, .25] : [.5, .5] };
    const state = { cells: 2, steps: values.accepted_dt_s.length, time_s: 1,
      initial_temperature_K: 300, cell_volume_m3: 1e-12, fields: {} as any };
    for (const quantity of Object.keys(GPU_ARTIFACT_UNITS) as (keyof typeof GPU_ARTIFACT_UNITS)[]) {
      const bytes = Buffer.alloc(values[quantity].length * 8);
      values[quantity].forEach((value, i) => bytes.writeDoubleLE(value, i * 8));
      const relative = `gpu-pilot/${backend}-${quantity}.f64le.bin`;
      await writeFile(path.join(root, relative), bytes);
      state.fields[quantity] = { path: relative, sha256: createHash('sha256').update(bytes).digest('hex'),
        size_bytes: bytes.length, units: GPU_ARTIFACT_UNITS[quantity],
        shape: quantity === 'coordinates_m' ? [2, 3] : [values[quantity].length] };
    }
    descriptor.states[backend] = state;
  }
  return { root, descriptor };
}

test('GPU artifact reader preserves f64 values and differing accepted step sequences', async t => {
  const { root, descriptor } = await fixture(t);
  const decoded = await readGpuPilotArtifacts(root, descriptor);
  assert.ok(Object.is(decoded.cpu.arrays.coordinates_m[0], -0));
  assert.deepEqual(Array.from(decoded.gpu.arrays.enthalpy_J_m3), [-1, 2]);
  assert.equal(decoded.cpu.arrays.accepted_dt_s.length, 4);
  assert.equal(decoded.gpu.arrays.accepted_dt_s.length, 2);
});

test('GPU artifact reader rejects corrupted bytes and invalid numeric payloads even with matching hashes', async t => {
  const { root, descriptor } = await fixture(t);
  const ref = descriptor.states.cpu.fields.temperature_K;
  const corrupt = Buffer.alloc(16);
  corrupt.writeDoubleLE(NaN, 0); corrupt.writeDoubleLE(301, 8);
  await writeFile(path.join(root, ref.path), corrupt);
  await assert.rejects(readGpuPilotArtifacts(root, descriptor), /integrity/i);
  ref.sha256 = createHash('sha256').update(corrupt).digest('hex');
  await assert.rejects(readGpuPilotArtifacts(root, descriptor), /Invalid GPU pilot temperature_K/);
});

test('GPU artifact reader rejects a final time detached from accepted timesteps', async t => {
  const { root, descriptor } = await fixture(t);
  descriptor.states.cpu.time_s = 2;
  await assert.rejects(readGpuPilotArtifacts(root, descriptor), /timestep sum/);
});

test('GPU artifact decoding rejects a file that grows after initial verification', async t => {
  const { root, descriptor } = await fixture(t);
  const ref = descriptor.states.cpu.fields.temperature_K;
  const identity = { sha256: ref.sha256, byteSize: ref.size_bytes };
  const verified = await verifyLocalArtifact(root, ref.path, identity);
  await writeFile(verified.path, Buffer.alloc(ref.size_bytes + 1024));
  await assert.rejects(readGpuPilotArtifactBytes(verified.path, identity), /size changed before decoding/);
});

test('GPU artifacts reject positive steps that cannot advance the unfinished clock', async t => {
  const { root, descriptor } = await fixture(t);
  const ref = descriptor.states.gpu.fields.accepted_dt_s;
  const bytes = Buffer.alloc(16);
  bytes.writeDoubleLE(1, 0); bytes.writeDoubleLE(Number.MIN_VALUE, 8);
  await writeFile(path.join(root, ref.path), bytes);
  ref.sha256 = createHash('sha256').update(bytes).digest('hex');
  await assert.rejects(readGpuPilotArtifacts(root, descriptor), /does not advance/);
});

test('Python writes deterministic f64 artifacts that TypeScript decodes without precision or clock loss', async t => {
  const root = await mkdtemp(path.join(tmpdir(), 'lpbf-gpu-cross-language-'));
  t.after(async () => {
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    await rm(root, { recursive: true, force: true });
  });
  const python = getHostPython();
  // Synthetic cross-language fixture, deliberately not a solver/parity claim.
  const script = `
import copy, json, sys
import numpy as np
from lpbf_gpu_pilot_artifacts import write_pilot_artifacts
cpu = dict(coordinates_m=np.asfortranarray([[-0., 1., 2.], [3., 4., 5.]]).astype('>f8'),
           temperature_K=np.array([300.1234567890123, 299.]),
           enthalpy_J_m3=np.array([2e7, -2e7]), density_kg_m3=np.array([8000., 4400.]),
           accepted_dt_s=np.array([.1]), time_s=.1,
           initial_temperature_K=300., cell_volume_m3=1e-15)
gpu = copy.deepcopy(cpu)
gpu['accepted_dt_s'] = np.full(100000, 1e-6)
gpu['time_s'] = 0.
for dt in gpu['accepted_dt_s']:
    gpu['time_s'] += float(dt)
print(json.dumps(write_pilot_artifacts(sys.argv[1], cpu, gpu)))
`;
  const generated = spawnSync(python.cmd, [...python.prefix, '-c', script, root], {
    cwd: path.resolve('python'), encoding: 'utf8', timeout: 20000, windowsHide: true, shell: false,
  });
  assert.equal(generated.error, undefined);
  assert.equal(generated.status, 0, generated.stderr);
  const parsed = JSON.parse(generated.stdout);
  const decoded = await readGpuPilotArtifacts(root, parsed);
  assert.ok(Object.is(decoded.cpu.arrays.coordinates_m[0], -0));
  assert.equal(decoded.cpu.arrays.temperature_K[0], 300.1234567890123);
  assert.deepEqual(Array.from(decoded.gpu.arrays.enthalpy_J_m3), [2e7, -2e7]);
  assert.equal(decoded.gpu.arrays.accepted_dt_s.length, 100000);
  let replayed = 0;
  for (const dt of decoded.gpu.arrays.accepted_dt_s) replayed += dt;
  assert.equal(decoded.gpu.metadata.time_s, replayed);
  assert.notEqual(decoded.gpu.metadata.time_s, decoded.cpu.metadata.time_s);
});
