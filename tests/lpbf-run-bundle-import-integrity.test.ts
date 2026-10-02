import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { LpbfArtifactStore } from '../server/lpbfArtifactStore';
import { LpbfRunBundleService } from '../server/lpbfRunBundleService';
import { LpbfRunRepository } from '../server/lpbfRunRepository';
import { LpbfSourceRepository } from '../server/lpbfSourceRepository';

function tarEntry(relative: string, content: Buffer): Buffer {
  const header = Buffer.alloc(512);
  const slash = relative.lastIndexOf('/');
  const name = slash < 0 ? relative : relative.slice(slash + 1);
  const prefix = slash < 0 ? '' : relative.slice(0, slash);
  header.write(name, 0, 100, 'utf8');
  header.write('0000600\0', 100, 8, 'ascii');
  header.write('0000000\0', 108, 8, 'ascii');
  header.write('0000000\0', 116, 8, 'ascii');
  header.write(content.length.toString(8).padStart(11, '0') + '\0', 124, 12, 'ascii');
  header.write('00000000000\0', 136, 12, 'ascii');
  header.fill(0x20, 148, 156);
  header[156] = 0x30;
  header.write('ustar\0', 257, 6, 'ascii');
  header.write('00', 263, 2, 'ascii');
  header.write(prefix, 345, 155, 'utf8');
  const checksum = header.reduce((sum, byte) => sum + byte, 0);
  header.write(checksum.toString(8).padStart(6, '0') + '\0 ', 148, 8, 'ascii');
  const padding = (512 - content.length % 512) % 512;
  return Buffer.concat([header, content, Buffer.alloc(padding)]);
}

async function readStream(stream: AsyncIterable<Buffer>): Promise<Buffer> {
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks);
}

test('portable import rejects an unreferenced allowed artifact and removes its isolated import directory', async t => {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-run-bundle-import-integrity-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const runRoot = path.join(root, 'live-runs');
  const sourceRoot = path.join(root, 'live-sources');
  const bundleRoot = path.join(root, 'bundles');
  mkdirSync(runRoot);
  mkdirSync(sourceRoot);
  const runs = new LpbfRunRepository(path.join(runRoot, 'runs.sqlite'));
  const sources = new LpbfSourceRepository(path.join(sourceRoot, 'metadata.sqlite'));
  runs.close();
  sources.close();
  new LpbfArtifactStore(path.join(runRoot, 'artifacts'));
  new LpbfArtifactStore(path.join(sourceRoot, 'artifacts'));

  const liveRunBytes = readFileSync(path.join(runRoot, 'runs.sqlite'));
  const liveSourceBytes = readFileSync(path.join(sourceRoot, 'metadata.sqlite'));
  const ids = ['a'.repeat(32), 'b'.repeat(32)];
  const bundles = new LpbfRunBundleService(runRoot, sourceRoot, bundleRoot, () => ids.shift()!);
  const exported = await bundles.export();
  const cleanTar = await readStream(await bundles.download(exported.bundleId));
  assert.ok(cleanTar.length >= 1024);
  assert.ok(cleanTar.subarray(-1024).every(byte => byte === 0), 'exported tar has its canonical terminator');

  const orphanHash = 'c'.repeat(64);
  const orphan = tarEntry(`artifacts/objects/${orphanHash.slice(0, 2)}/${orphanHash}`, Buffer.from('orphan'));
  const tamperedTar = Buffer.concat([cleanTar.subarray(0, -1024), orphan, Buffer.alloc(1024)]);
  await assert.rejects(bundles.importPortable((await import('node:stream')).Readable.from(tamperedTar)),
    /portable run bundle integrity verification failed/i);

  assert.equal(existsSync(path.join(bundleRoot, 'imports', 'b'.repeat(32))), false,
    'failed post-extraction verification removes the allocated import directory');
  assert.deepEqual(readFileSync(path.join(runRoot, 'runs.sqlite')), liveRunBytes,
    'portable import never changes the live run database');
  assert.deepEqual(readFileSync(path.join(sourceRoot, 'metadata.sqlite')), liveSourceBytes,
    'portable import never changes the live source database');
});
