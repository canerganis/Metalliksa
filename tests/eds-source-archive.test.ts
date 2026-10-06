import assert from "node:assert/strict";
import test from "node:test";
import {
  archiveEDSSource,
  restoreLatestEDSSource,
  sha256Bytes,
  verifyEDSSourceRecord,
} from "../src/utils/edsSourceArchive";
import type { EDSSourceArchiveStore, EDSSourceRecord } from "../src/utils/edsSourceArchive";

class MapSourceStore implements EDSSourceArchiveStore {
  readonly values = new Map<string, unknown>();
  failRecordWrite = false;
  corruptRecordReadback = false;
  onRecordReadback: (() => Promise<void>) | undefined = undefined;

  async get(key: string): Promise<unknown> {
    const value = this.values.get(key);
    if (key !== "latest-source-sha256" && this.onRecordReadback) {
      const callback = this.onRecordReadback;
      this.onRecordReadback = undefined;
      await callback();
    }
    if (key !== "latest-source-sha256" && this.corruptRecordReadback && value) {
      return { ...(value as object), byteSize: -1 };
    }
    return value;
  }

  async set(key: string, value: unknown): Promise<void> {
    if (key !== "latest-source-sha256" && this.failRecordWrite) {
      throw new Error("injected record write failure");
    }
    this.values.set(key, value);
  }
}

test("EDS source records verify exact bytes and reject payload mutation", async () => {
  const original = new TextEncoder().encode("#FORMAT: EMSA/MAS\n0,12\n").buffer;
  const record: EDSSourceRecord = {
    schemaVersion: 1,
    sha256: await sha256Bytes(original),
    fileName: "sample.emsa",
    mediaType: "text/plain",
    byteSize: original.byteLength,
    importedAt: "2026-09-27T00:00:00.000Z",
    bytes: original,
  };

  assert.equal(await verifyEDSSourceRecord(record), true);
  assert.equal(await verifyEDSSourceRecord({ ...record, bytes: new TextEncoder().encode("tampered").buffer }), false);
  assert.equal(await verifyEDSSourceRecord({ ...record, byteSize: record.byteSize + 1 }), false);
  assert.equal(await verifyEDSSourceRecord(null), false);
  assert.equal(await verifyEDSSourceRecord({ ...record, schemaVersion: 2 }), false);
  assert.equal(await verifyEDSSourceRecord({ ...record, bytes: new Uint8Array([1, 2, 3]) }), false);
  assert.equal(await verifyEDSSourceRecord({ ...record, sha256: 42 }), false);
});

test("failed EDS record write or read-back leaves the previous latest pointer unchanged", async () => {
  for (const failure of ["write", "read-back"] as const) {
    const store = new MapSourceStore();
    const previousLatest = "a".repeat(64);
    await store.set("latest-source-sha256", previousLatest);
    if (failure === "write") store.failRecordWrite = true;
    else store.corruptRecordReadback = true;

    await assert.rejects(
      archiveEDSSource("new.emsa", "text/plain", new TextEncoder().encode("new source").buffer, store),
      failure === "write" ? /injected record write failure/ : /read-back integrity check/,
    );
    assert.equal(await store.get("latest-source-sha256"), previousLatest, `${failure} must not advance latest`);
  }
});

test("superseded EDS archive does not replace the latest source pointer", async () => {
  const store = new MapSourceStore();
  const previousLatest = "a".repeat(64);
  const newerLatest = "b".repeat(64);
  let requestIsCurrent = true;
  await store.set("latest-source-sha256", previousLatest);
  store.onRecordReadback = async () => {
    requestIsCurrent = false;
    await store.set("latest-source-sha256", newerLatest);
  };

  const archived = await archiveEDSSource(
    "older-request.emsa",
    "text/plain",
    new TextEncoder().encode("older request payload").buffer,
    store,
    () => requestIsCurrent,
  );

  assert.equal(await verifyEDSSourceRecord(archived), true);
  assert.equal(await store.get("latest-source-sha256"), newerLatest);
});

test("restore rejects a valid EDS record stored under a different SHA-256 lookup key", async () => {
  const store = new MapSourceStore();
  const bytes = new TextEncoder().encode("archived source").buffer;
  const record: EDSSourceRecord = {
    schemaVersion: 1,
    sha256: await sha256Bytes(bytes),
    fileName: "sample.emsa",
    mediaType: "text/plain",
    byteSize: bytes.byteLength,
    importedAt: "2026-09-27T00:00:00.000Z",
    bytes,
  };
  const wrongKey = "0".repeat(64);
  assert.notEqual(wrongKey, record.sha256);
  await store.set("latest-source-sha256", wrongKey);
  await store.set(wrongKey, record);

  assert.equal(await verifyEDSSourceRecord(record), true);
  await assert.rejects(restoreLatestEDSSource(store), /failed its SHA-256 check/);
});

test("restore rejects malformed latest SHA-256 pointers", async () => {
  const store = new MapSourceStore();
  await store.set("latest-source-sha256", "not-a-sha256");
  await assert.rejects(restoreLatestEDSSource(store), /latest.*invalid/i);
});
