import assert from "node:assert/strict";
import { test } from "node:test";
import { fetchRuntimeConfig, runtimeConfigProbe } from "../src/components/AirgapBanner";
import { pythonComputationService } from "../src/services/pythonComputationService";

// Start-up fires the banner, the boot check, the telemetry strip and the shell status refresh together.
// Non-forced callers must share one in-flight request instead of sending duplicates.

function gatedFetch(body: unknown) {
  const urls: string[] = [];
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  const stub = (async (input: unknown) => {
    urls.push(String(input));
    await gate;
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  return { urls, release, stub };
}

/** Every call gets its own gate: answer(i, status, body) settles call i. */
function perCallFetch() {
  const calls: Array<(status: number, body: unknown) => void> = [];
  const stub = ((_input: unknown) =>
    new Promise<Response>((resolve) => {
      calls.push((status, body) => resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })));
    })) as typeof fetch;
  return { calls, stub, answer: (i: number, status: number, body: unknown = {}) => calls[i](status, body) };
}
const tickIo = () => new Promise<void>((r) => setImmediate(r));

async function withFetch<T>(stub: typeof fetch, run: () => Promise<T>): Promise<T> {
  const realFetch = globalThis.fetch;
  globalThis.fetch = stub;
  try {
    return await run();
  } finally {
    globalThis.fetch = realFetch;
  }
}

// These two run first: they need an empty runtime-config cache (only failed requests here).
test("fetchRuntimeConfig: after a failed request the next non-forced call sends a NEW request", async () => {
  const f = perCallFetch();
  await withFetch(f.stub, async () => {
    const first = fetchRuntimeConfig();
    await tickIo();
    assert.equal(f.calls.length, 1);
    f.answer(0, 500);
    await first;
    assert.deepEqual(runtimeConfigProbe(), { loaded: false, accessRequired: false, failure: "HTTP 500" });
    const second = fetchRuntimeConfig();
    await tickIo();
    assert.equal(f.calls.length, 2, "the settled in-flight promise was cleared, so a new request is sent");
    f.answer(1, 500);
    await second;
  });
});

test("fetchRuntimeConfig: a forced call while a non-forced one is in flight sends its own request", async () => {
  const f = perCallFetch();
  await withFetch(f.stub, async () => {
    const plain = fetchRuntimeConfig();
    const forced = fetchRuntimeConfig(true);
    const joined = fetchRuntimeConfig();
    await tickIo();
    assert.equal(f.calls.length, 2, "plain + forced; the later plain call joins the forced one");
    f.answer(1, 500);
    f.answer(0, 500);
    await Promise.all([plain, forced, joined]);
    assert.equal(runtimeConfigProbe().loaded, false);
  });
});

test("fetchRuntimeConfig: concurrent calls share one request; cache afterwards; force sends a new one", async () => {
  const realFetch = globalThis.fetch;
  const { urls, release, stub } = gatedFetch({ airgapped: true, blockedServices: ["a"], allowedLocal: [] });
  globalThis.fetch = stub;
  try {
    const all = Promise.all([fetchRuntimeConfig(), fetchRuntimeConfig(), fetchRuntimeConfig()]);
    await new Promise((r) => setImmediate(r));
    assert.equal(urls.length, 1, "one request while one is pending");
    release();
    const [a, b, c] = await all;
    assert.equal(a, b);
    assert.equal(b, c);
    assert.equal(a.airgapped, true);
    assert.equal(runtimeConfigProbe().loaded, true);
    await fetchRuntimeConfig();
    assert.equal(urls.length, 1, "served from cache");
    await fetchRuntimeConfig(true);
    assert.equal(urls.length, 2, "force re-fetches");
  } finally {
    globalThis.fetch = realFetch;
  }
});

test("checkEngineStatus: concurrent non-forced calls share one request; a forced call is not merged", async () => {
  const realFetch = globalThis.fetch;
  const { urls, release, stub } = gatedFetch({ status: "online", pythonVersion: "3.12.10" });
  globalThis.fetch = stub;
  try {
    const shared = Promise.all([pythonComputationService.checkEngineStatus(true), pythonComputationService.checkEngineStatus(false), pythonComputationService.checkEngineStatus(false)]);
    await new Promise((r) => setImmediate(r));
    assert.equal(urls.length, 1, "non-forced calls join the pending request");
    const forced = pythonComputationService.checkEngineStatus(true);
    await new Promise((r) => setImmediate(r));
    assert.equal(urls.length, 2, "force always sends");
    release();
    const [a, b, c] = await shared;
    assert.equal(a, b);
    assert.equal(b, c);
    assert.equal(a.online, true);
    assert.equal((await forced).pythonVersion, "3.12.10");
  } finally {
    globalThis.fetch = realFetch;
  }
});

test("checkEngineStatus: a failed request is cached for 15 s; after expiry the next non-forced call sends a NEW request", async (t) => {
  t.mock.timers.enable({ apis: ["Date"], now: 1_000_000 });
  const f = perCallFetch();
  await withFetch(f.stub, async () => {
    const first = pythonComputationService.checkEngineStatus(true);
    await tickIo();
    f.answer(0, 500);
    assert.equal((await first).status, "client_fallback");
    assert.equal((await pythonComputationService.checkEngineStatus(false)).status, "client_fallback");
    assert.equal(f.calls.length, 1, "within 15 s the failure is served from cache");
    t.mock.timers.tick(15_001);
    const second = pythonComputationService.checkEngineStatus(false);
    await tickIo();
    assert.equal(f.calls.length, 2, "expired cache and a cleared in-flight promise: a new request");
    f.answer(1, 200, { status: "online", pythonVersion: "3.12.10" });
    assert.equal((await second).online, true);
  });
});

test("checkEngineStatus: an older non-forced answer arriving after a newer forced one does not overwrite it", async (t) => {
  t.mock.timers.enable({ apis: ["Date"], now: 5_000_000 });
  const f = perCallFetch();
  await withFetch(f.stub, async () => {
    const older = pythonComputationService.checkEngineStatus(false);
    await tickIo();
    const newer = pythonComputationService.checkEngineStatus(true);
    await tickIo();
    assert.equal(f.calls.length, 2);
    f.answer(1, 200, { status: "online", pythonVersion: "new" });
    assert.equal((await newer).pythonVersion, "new");
    f.answer(0, 200, { status: "online", pythonVersion: "old" });
    assert.equal((await older).pythonVersion, "new", "the stale answer is not applied");
    const cached = await pythonComputationService.checkEngineStatus(false);
    assert.equal(cached.pythonVersion, "new");
    assert.equal(f.calls.length, 2, "served from the newer cache");
  });
});