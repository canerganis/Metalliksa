import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { Readable } from 'node:stream';
import { test } from 'node:test';
import { extractRunBundleTar } from '../server/lpbfRunBundleTar';

function entry(name: string, content: string, type = '0'): Buffer {
  const header = Buffer.alloc(512);
  header.write(name, 0, 100, 'utf8');
  header.write('0000600\0', 100, 8, 'ascii');
  header.write('0000000\0', 108, 8, 'ascii'); header.write('0000000\0', 116, 8, 'ascii');
  header.write(content.length.toString(8).padStart(11, '0') + '\0', 124, 12, 'ascii');
  header.write('00000000000\0', 136, 12, 'ascii'); header.fill(0x20, 148, 156);
  header[156] = type.charCodeAt(0); header.write('ustar\0', 257, 6, 'ascii'); header.write('00', 263, 2, 'ascii');
  const checksum = header.reduce((sum, byte) => sum + byte, 0);
  header.write(checksum.toString(8).padStart(6, '0') + '\0 ', 148, 8, 'ascii');
  const data = Buffer.from(content), padding = (512 - data.length % 512) % 512;
  return Buffer.concat([header, data, Buffer.alloc(padding)]);
}

test('portable bundle extractor rejects traversal, links, and duplicate files without leaving a target', async t => {
  const root = mkdtempSync(path.join(tmpdir(), 'lpbf-run-bundle-tar-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const destination = path.join(root, 'isolated');
  const traversal = Buffer.concat([entry('../outside', 'bad'), Buffer.alloc(1024)]);
  await assert.rejects(extractRunBundleTar(Readable.from(traversal), destination));
  assert.equal(existsSync(path.join(root, 'outside')), false);
  assert.equal(existsSync(destination), false);

  const link = Buffer.concat([entry('bundle.json', '{}', '2'), Buffer.alloc(1024)]);
  await assert.rejects(extractRunBundleTar(Readable.from(link), destination));
  assert.equal(existsSync(destination), false);

  const duplicate = Buffer.concat([entry('bundle.json', '{}'), entry('bundle.json', '{}'), Buffer.alloc(1024)]);
  await assert.rejects(extractRunBundleTar(Readable.from(duplicate), destination));
  assert.equal(existsSync(destination), false);
});
