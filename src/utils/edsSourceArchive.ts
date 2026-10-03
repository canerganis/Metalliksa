import { createStore, get, set } from "idb-keyval";

const STORE_NAME = "metalliksa-eds-source-v1";
const LATEST_KEY = "latest-source-sha256";
const MAX_SOURCE_BYTES = 25 * 1024 * 1024;
const sourceStore = createStore(STORE_NAME, "source-files");

export interface EDSSourceArchiveStore {
  get(key: string): Promise<unknown>;
  set(key: string, value: unknown): Promise<void>;
}

const browserSourceArchiveStore: EDSSourceArchiveStore = {
  get: key => get<unknown>(key, sourceStore),
  set: async (key, value) => { await set(key, value, sourceStore); },
};

export interface EDSSourceRecord {
  schemaVersion: 1;
  sha256: string;
  fileName: string;
  mediaType: string;
  byteSize: number;
  importedAt: string;
  bytes: ArrayBuffer;
}

export async function sha256Bytes(bytes: ArrayBuffer): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new Error("SHA-256 is unavailable in this browser context.");
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("");
}

export async function verifyEDSSourceRecord(record: unknown): Promise<boolean> {
  if (!record || typeof record !== "object" || Array.isArray(record)) return false;
  const value = record as unknown as Record<string, unknown>;
  const bytes = value.bytes;
  if (value.schemaVersion !== 1
    || typeof value.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(value.sha256)
    || typeof value.fileName !== "string" || !value.fileName.trim()
    || typeof value.mediaType !== "string" || !value.mediaType.trim()
    || typeof value.importedAt !== "string" || !Number.isFinite(Date.parse(value.importedAt))
    || !(bytes instanceof ArrayBuffer)
    || !Number.isSafeInteger(value.byteSize) || (value.byteSize as number) <= 0
    || (value.byteSize as number) > MAX_SOURCE_BYTES
    || value.byteSize !== bytes.byteLength) return false;
  return await sha256Bytes(bytes) === value.sha256;
}

export async function archiveEDSSource(
  fileName: string,
  mediaType: string,
  bytes: ArrayBuffer,
  store: EDSSourceArchiveStore = browserSourceArchiveStore,
  isCurrent: () => boolean = () => true,
): Promise<EDSSourceRecord> {
  if (typeof fileName !== "string" || !fileName.trim()) throw new Error("An EDS source filename is required.");
  if (typeof mediaType !== "string") throw new Error("EDS source media type must be a string.");
  if (!(bytes instanceof ArrayBuffer) || bytes.byteLength === 0 || bytes.byteLength > MAX_SOURCE_BYTES) {
    throw new Error("EDS source file must be between 1 byte and 25 MiB to archive.");
  }
  const record: EDSSourceRecord = {
    schemaVersion: 1,
    sha256: await sha256Bytes(bytes),
    fileName,
    mediaType: mediaType.trim() ? mediaType : "application/octet-stream",
    byteSize: bytes.byteLength,
    importedAt: new Date().toISOString(),
    bytes: bytes.slice(0),
  };
  await store.set(record.sha256, record);
  const stored = await store.get(record.sha256);
  if (!stored || (stored as EDSSourceRecord).sha256 !== record.sha256
    || !(await verifyEDSSourceRecord(stored as EDSSourceRecord))) {
    throw new Error("Archived EDS source did not pass its read-back integrity check.");
  }
  if (isCurrent()) await store.set(LATEST_KEY, record.sha256);
  return stored as EDSSourceRecord;
}

export async function restoreLatestEDSSource(
  store: EDSSourceArchiveStore = browserSourceArchiveStore,
): Promise<EDSSourceRecord | null> {
  const pointer = await store.get(LATEST_KEY);
  if (pointer === undefined) return null;
  if (typeof pointer !== "string" || !/^[a-f0-9]{64}$/.test(pointer)) {
    throw new Error("The latest archived EDS source pointer is invalid.");
  }
  const record = await store.get(pointer);
  if (!record || (record as EDSSourceRecord).sha256 !== pointer
    || !(await verifyEDSSourceRecord(record as EDSSourceRecord))) {
    throw new Error("The latest archived EDS source is missing or failed its SHA-256 check.");
  }
  return record as EDSSourceRecord;
}
