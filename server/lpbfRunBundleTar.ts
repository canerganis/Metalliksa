/** Minimal streaming USTAR transport for verified LPBF run bundles. */
import { createReadStream, lstatSync } from 'node:fs';
import { mkdir, open, readdir, rm } from 'node:fs/promises';
import { Readable } from 'node:stream';
import path from 'node:path';
import { artifactDirectory, artifactRelativePath } from './lpbfArtifactStore';

const BLOCK = 512;
export const MAX_RUN_BUNDLE_BYTES = 16 * 1024 * 1024 * 1024;
const MAX_ENTRIES = 100_000;

function allowedBundlePath(relative: string): string {
  artifactRelativePath(relative);
  const valid = relative === 'bundle.json' || relative === 'runs.sqlite'
    || relative === 'sources/bundle.json' || relative === 'sources/metadata.sqlite'
    || /^artifacts\/objects\/[a-f0-9]{2}\/[a-f0-9]{64}$/.test(relative)
    || /^sources\/artifacts\/objects\/[a-f0-9]{2}\/[a-f0-9]{64}$/.test(relative);
  if (!valid) throw new Error('Unexpected run bundle archive path');
  return relative;
}

function writeOctal(header: Buffer, offset: number, length: number, value: number) {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Invalid tar numeric field');
  const encoded = value.toString(8);
  if (encoded.length > length - 1) throw new Error('Tar numeric field exceeds USTAR limits');
  header.write(encoded.padStart(length - 1, '0') + '\0', offset, length, 'ascii');
}

function tarHeader(relative: string, byteSize: number, modifiedAt: number): Buffer {
  const safe = allowedBundlePath(relative);
  const header = Buffer.alloc(BLOCK);
  const basename = path.posix.basename(safe), directory = path.posix.dirname(safe);
  const prefix = directory === '.' ? '' : directory;
  if (Buffer.byteLength(basename) > 100 || Buffer.byteLength(prefix) > 155) throw new Error('Run bundle path exceeds USTAR limits');
  header.write(basename, 0, 100, 'utf8');
  writeOctal(header, 100, 8, 0o600);
  writeOctal(header, 108, 8, 0);
  writeOctal(header, 116, 8, 0);
  writeOctal(header, 124, 12, byteSize);
  writeOctal(header, 136, 12, Math.floor(modifiedAt / 1000));
  header.fill(0x20, 148, 156);
  header[156] = 0x30;
  header.write('ustar\0', 257, 6, 'ascii');
  header.write('00', 263, 2, 'ascii');
  if (prefix) header.write(prefix, 345, 155, 'utf8');
  const checksum = header.reduce((sum, value) => sum + value, 0);
  header.write(checksum.toString(8).padStart(6, '0') + '\0 ', 148, 8, 'ascii');
  return header;
}

async function* files(root: string, current = ''): AsyncGenerator<{ relative: string; filename: string }> {
  const absolute = current ? path.join(root, ...current.split('/')) : root;
  for (const entry of await readdir(absolute, { withFileTypes: true })) {
    const relative = current ? `${current}/${entry.name}` : entry.name;
    const filename = path.join(absolute, entry.name), stat = lstatSync(filename);
    if (stat.isSymbolicLink()) throw new Error('Run bundle archives cannot contain links');
    if (stat.isDirectory()) yield* files(root, relative);
    else if (stat.isFile()) { allowedBundlePath(relative); yield { relative, filename }; }
    else throw new Error('Run bundle archives accept regular files only');
  }
}

/** Return a back-pressure-aware USTAR stream; no bundle contents are buffered in memory. */
export function createRunBundleTar(rootPath: string): Readable {
  const root = artifactDirectory(rootPath);
  return Readable.from((async function* () {
    let entries = 0, bytes = 1024;
    for await (const file of files(root)) {
      const stat = lstatSync(file.filename);
      entries++;
      bytes += BLOCK + Math.ceil(stat.size / BLOCK) * BLOCK;
      if (entries > MAX_ENTRIES || bytes > MAX_RUN_BUNDLE_BYTES) throw new Error('Run bundle exceeds the portable archive limit');
      yield tarHeader(file.relative, stat.size, stat.mtimeMs);
      for await (const chunk of createReadStream(file.filename)) yield chunk as Buffer;
      const padding = (BLOCK - (stat.size % BLOCK)) % BLOCK;
      if (padding) yield Buffer.alloc(padding);
    }
    yield Buffer.alloc(2 * BLOCK);
  })());
}

class TarReader {
  private iterator: AsyncIterator<Buffer>;
  private chunk = Buffer.alloc(0);
  private offset = 0;
  byteCount = 0;
  constructor(stream: Readable) {
    this.iterator = (async function* () { for await (const raw of stream) yield Buffer.isBuffer(raw) ? raw : Buffer.from(raw); })();
  }
  async readExactly(length: number): Promise<Buffer | null> {
    if (length === 0) return Buffer.alloc(0);
    const parts: Buffer[] = []; let collected = 0;
    while (collected < length) {
      if (this.offset >= this.chunk.length) {
        const next = await this.iterator.next();
        if (next.done) return collected ? null : null;
        this.chunk = next.value; this.offset = 0;
      }
      const take = Math.min(length - collected, this.chunk.length - this.offset);
      parts.push(this.chunk.subarray(this.offset, this.offset + take));
      this.offset += take; collected += take; this.byteCount += take;
      if (this.byteCount > MAX_RUN_BUNDLE_BYTES) throw new Error('Run bundle exceeds the portable archive limit');
    }
    return parts.length === 1 ? parts[0] : Buffer.concat(parts, length);
  }
  async hasTrailingBytes(): Promise<boolean> {
    if (this.offset < this.chunk.length) return true;
    const next = await this.iterator.next();
    return !next.done && next.value.length > 0;
  }
}

function readOctal(header: Buffer, offset: number, length: number): number {
  const raw = header.subarray(offset, offset + length).toString('ascii').replace(/\0.*$/, '').trim();
  if (!/^[0-7]+$/.test(raw)) throw new Error('Invalid tar numeric field');
  const value = Number.parseInt(raw, 8);
  if (!Number.isSafeInteger(value)) throw new Error('Tar numeric field is unsafe');
  return value;
}

function field(header: Buffer, offset: number, length: number): string {
  const raw = header.subarray(offset, offset + length);
  const end = raw.indexOf(0), value = raw.subarray(0, end < 0 ? length : end);
  const decoded = value.toString('utf8');
  if (!Buffer.from(decoded, 'utf8').equals(value)) throw new Error('Invalid tar path encoding');
  return decoded;
}

function verifyHeader(header: Buffer) {
  const expected = readOctal(header, 148, 8), copy = Buffer.from(header);
  copy.fill(0x20, 148, 156);
  if (copy.reduce((sum, value) => sum + value, 0) !== expected
    || header.toString('ascii', 257, 263) !== 'ustar\0'
    || !['\0', '0'].includes(String.fromCharCode(header[156]))) throw new Error('Invalid portable run bundle tar header');
  const name = field(header, 0, 100), prefix = field(header, 345, 155);
  const relative = allowedBundlePath(prefix ? `${prefix}/${name}` : name);
  if (!name || name.includes('/') || name.includes('\\')) throw new Error('Invalid portable run bundle filename');
  return { relative, byteSize: readOctal(header, 124, 12), modifiedAt: readOctal(header, 136, 12) };
}

/** Extract only regular USTAR files into a new isolated directory, rejecting links, traversal, duplicates and oversized payloads. */
export async function extractRunBundleTar(stream: Readable, destinationPath: string): Promise<void> {
  const destination = path.resolve(destinationPath), parent = artifactDirectory(path.dirname(destination));
  const root = path.join(parent, path.basename(destination));
  const reader = new TarReader(stream), seen = new Set<string>();
  let entries = 0, expandedBytes = 0;
  let created = false;
  try {
    await mkdir(root, { mode: 0o700 }); created = true;
    for (;;) {
      const header = await reader.readExactly(BLOCK);
      if (!header) throw new Error('Truncated run bundle tar archive');
      if (header.every(value => value === 0)) {
        const second = await reader.readExactly(BLOCK);
        if (!second || !second.every(value => value === 0) || await reader.hasTrailingBytes()) throw new Error('Invalid run bundle tar terminator');
        break;
      }
      const item = verifyHeader(header), key = item.relative.toLowerCase();
      if (seen.has(key)) throw new Error('Duplicate run bundle archive path');
      seen.add(key); entries++; expandedBytes += item.byteSize;
      if (entries > MAX_ENTRIES || expandedBytes > MAX_RUN_BUNDLE_BYTES || reader.byteCount + item.byteSize > MAX_RUN_BUNDLE_BYTES) {
        throw new Error('Run bundle exceeds the portable archive limit');
      }
      const filename = path.join(root, ...item.relative.split('/'));
      await mkdir(path.dirname(filename), { recursive: true, mode: 0o700 });
      const output = await open(filename, 'wx', 0o600);
      try {
        let remaining = item.byteSize;
        while (remaining > 0) {
          const chunk = await reader.readExactly(Math.min(1024 * 1024, remaining));
          if (!chunk) throw new Error('Truncated run bundle file');
          await output.writeFile(chunk); remaining -= chunk.length;
        }
        await output.sync();
      } finally { await output.close(); }
      const padding = (BLOCK - (item.byteSize % BLOCK)) % BLOCK;
      if (padding && !await reader.readExactly(padding)) throw new Error('Truncated run bundle padding');
    }
    if (!entries) throw new Error('Run bundle archive is empty');
  } catch (error) {
    if (created) await rm(root, { recursive: true, force: true });
    throw error;
  }
}
