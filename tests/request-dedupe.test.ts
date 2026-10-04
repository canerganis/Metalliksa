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
