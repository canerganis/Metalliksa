import assert from "node:assert/strict";
import { test } from "node:test";
import { AirgapBlockedError, assertNotAirgapped } from "../server/airgap";
import { researchSearchUrl } from "../server/researchSearch";

async function withAirgap<T>(value: string | undefined, fn: (calls: () => number) => Promise<T> | T): Promise<T> {
  const origFetch = globalThis.fetch;
  const origEnv = process.env.AIRGAPPED;
  const origVite = process.env.VITE_AIRGAPPED;
  let calls = 0;
  globalThis.fetch = (async () => { calls++; return new Response("{}"); }) as typeof fetch;
  delete process.env.VITE_AIRGAPPED;
  if (value === undefined) delete process.env.AIRGAPPED; else process.env.AIRGAPPED = value;
  try { return await fn(() => calls); }
  finally {
    globalThis.fetch = origFetch;
    if (origEnv === undefined) delete process.env.AIRGAPPED; else process.env.AIRGAPPED = origEnv;
    if (origVite !== undefined) process.env.VITE_AIRGAPPED = origVite;
  }
}

test("assertNotAirgapped throws a typed error only when AIRGAPPED=1", async () => {
  await withAirgap("1", () => {
    assert.throws(() => assertNotAirgapped("svc"), (e: unknown) => e instanceof AirgapBlockedError && e.blockedService === "svc" && e.airgapped === true);
  });
  await withAirgap("0", () => { assert.doesNotThrow(() => assertNotAirgapped("svc")); });
});

test("researchSearchUrl refuses when air-gapped and works otherwise", async () => {
  await withAirgap("1", (calls) => {
    assert.throws(() => researchSearchUrl("LPBF fixture"), AirgapBlockedError);
    assert.equal(calls(), 0);
  });
  await withAirgap("0", () => { assert.equal(researchSearchUrl("LPBF fixture").hostname, "api.crossref.org"); });
});
