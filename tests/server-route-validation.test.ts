import { after, test as baseTest } from "node:test";
import assert from "node:assert/strict";
import express from "express";
import type { AddressInfo } from "node:net";
import type { Server } from "node:http";
import { applySecurity, errorHandler } from "../server/security.ts";
import { characterizationRouter } from "../routes/characterization.ts";
import { copilotRouter } from "../routes/copilot.ts";
import { orchestratorRouter } from "../routes/orchestrator.ts";

// Importing the characterization router starts the persistent Python supervisor (import side
// effect in server/processOrchestrator.ts) which keeps the event loop alive; exit explicitly
// once the tests are done, preserving a failing exit code.
let anyFailed = false;
const test: typeof baseTest = ((name: string, fn: any) =>
  baseTest(name, async (...args: any[]) => {
    try {
      await fn(...args);
    } catch (error) {
      anyFailed = true;
      throw error;
    }
  })) as any;
after(() => {
  setTimeout(() => process.exit(anyFailed ? 1 : 0), 250);
});

interface Harness {
  base: string;
  close: () => Promise<void>;
}

async function start(token: string | null, rate?: { aiLimit?: number; generalLimit?: number }): Promise<Harness> {
  const app = express();
  applySecurity(app, token, { log: () => {}, rate });
  app.use(express.json({ limit: "50mb" }));
  app.get("/api/health", (_req, res) => res.json({ status: "ok" }));
  app.use(characterizationRouter);
  app.use(copilotRouter);
  app.use(orchestratorRouter);
  app.use(errorHandler(() => {}));
  const server: Server = await new Promise((resolve) => {
    const s = app.listen(0, "127.0.0.1", () => resolve(s));
  });
  const port = (server.address() as AddressInfo).port;
  return {
    base: `http://127.0.0.1:${port}`,
    close: () => new Promise<void>((resolve) => { server.close(() => resolve()); (server as any).closeAllConnections?.(); }),
  };
}

async function post(h: Harness, path: string, body: unknown, headers: Record<string, string> = {}) {
  const res = await fetch(h.base + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({}));
  return { status: res.status, json: json as any, headers: res.headers };
}

// The battery/corrosion upload, user-script execution and CNLS HTTP surface had no UI consumer
// and was removed (exec-script ran user-supplied Python). Keep it gone.
test("removed battery/corrosion upload, exec-script and CNLS routes are not served", async () => {
  const h = await start(null);
  try {
    for (const route of ["/api/python/battery-corrosion-upload", "/api/python/battery-corrosion-exec-script",
      "/api/python/cnls-fit", "/api/python/cnls-autofit", "/api/python/cnls-synthetic-noise"]) {
      assert.equal((await post(h, route, { scriptCode: "print(1)" })).status, 404, route);
    }
    assert.equal((await fetch(h.base + "/api/python/battery-corrosion-upload/recent")).status, 404);
    assert.equal((await fetch(h.base + "/api/python/battery-corrosion-upload/all", { method: "DELETE" })).status, 404);
  } finally {
    await h.close();
  }
});

test("consult and diagnose-micrograph enforce input limits before calling the model", async () => {
  const h = await start(null, { aiLimit: 1000 });
  try {
    assert.equal((await post(h, "/api/consult", { prompt: "x".repeat(8001) })).status, 400);
    assert.equal((await post(h, "/api/metallurgy/consult", { prompt: 42 })).status, 400);
    assert.equal((await post(h, "/api/consult", { prompt: "ok", systemInstruction: "x".repeat(2001) })).status, 400);
    assert.equal((await post(h, "/api/consult", { prompt: "ok", context: { blob: "x".repeat(50001) } })).status, 400);

    assert.equal((await post(h, "/api/metallurgy/diagnose-micrograph", { imageBase64: { evil: true } })).status, 400);
    assert.equal((await post(h, "/api/metallurgy/diagnose-micrograph", { imageBase64: "data:image/png;base64," + "A".repeat(14_000_001) })).status, 413);
    assert.equal((await post(h, "/api/metallurgy/diagnose-micrograph", { imageBase64: "data:image/png;base64,AAAA", prompt: "x".repeat(4001) })).status, 400);
    // Existing allowlist behaviour is preserved; the data-URI mime wins over the client mimeType.
    assert.equal((await post(h, "/api/metallurgy/diagnose-micrograph", { imageBase64: "data:image/svg+xml;base64,AAAA", mimeType: "image/png" })).status, 415);
  } finally {
    await h.close();
  }
});

test("collect-source rejects prototype keys, non-strings and long URLs", async () => {
  const h = await start(null, { aiLimit: 1000 });
  try {
    for (const sourceId of ["constructor", "toString", "__proto__", 7, null, { a: 1 }]) {
      const r = await post(h, "/api/orchestrator/collect-source", { sourceId, url: "https://www.nist.gov/a.csv" });
      assert.equal(r.status, 400, `sourceId ${JSON.stringify(sourceId)}`);
    }
    const long = "https://www.nist.gov/" + "a".repeat(2100);
    assert.equal((await post(h, "/api/orchestrator/collect-source", { sourceId: "nistAmbench", url: long })).status, 400);
    assert.equal((await post(h, "/api/orchestrator/collect-source", { sourceId: "nistAmbench", url: 123 })).status, 400);
  } finally {
    await h.close();
  }
});

test("dataset-plan caps string fields", async () => {
  const h = await start(null, { aiLimit: 1000 });
  try {
    const big = "x".repeat(4001);
    assert.equal((await post(h, "/api/orchestrator/dataset-plan", { objective: big })).status, 400);
    assert.equal((await post(h, "/api/orchestrator/dataset-plan", { objective: "ok", constraints: big })).status, 400);
    assert.equal((await post(h, "/api/orchestrator/dataset-plan", { objective: "ok", availableData: big })).status, 400);
    assert.equal((await post(h, "/api/orchestrator/dataset-plan", {})).status, 400);
  } finally {
    await h.close();
  }
});

test("end to end: token auth returns 401 and AI buckets return 429", async () => {
  const h = await start("s3cret", { aiLimit: 2, generalLimit: 1000 });
  try {
    const health = await fetch(h.base + "/api/health");
    assert.equal(health.status, 200);
    assert.ok(health.headers.get("x-request-id"));
    assert.equal(health.headers.get("x-content-type-options"), "nosniff");

    const denied = await post(h, "/api/consult", { prompt: "hi" });
    assert.equal(denied.status, 401);
    assert.ok(denied.json.requestId);
    assert.equal((await post(h, "/api/consult", { prompt: "hi" }, { Authorization: "Bearer wrong" })).status, 401);
  } finally {
    await h.close();
  }

  // Fresh server so the unauthenticated attempts above do not count against this bucket.
  const fresh = await start("s3cret", { aiLimit: 2, generalLimit: 1000 });
  try {
    const auth = { Authorization: "Bearer s3cret" };
    const bad = { prompt: "x".repeat(8001) };
    assert.equal((await post(fresh, "/api/consult", bad, auth)).status, 400);
    // collect-source shares the stricter AI bucket.
    assert.equal((await post(fresh, "/api/orchestrator/collect-source", { sourceId: "constructor", url: "x" }, auth)).status, 400);
    const limited = await post(fresh, "/api/consult", bad, auth);
    assert.equal(limited.status, 429);
    assert.ok(limited.headers.get("retry-after"));
  } finally {
    await fresh.close();
  }
});
