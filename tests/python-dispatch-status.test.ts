import { after, test as baseTest } from "node:test";
import assert from "node:assert/strict";
import express from "express";
import type { AddressInfo } from "node:net";
import type { Server } from "node:http";
import { pythonDispatchStatus } from "../server/pythonDispatchStatus.ts";
import { physicsDeps, physicsRouter } from "../routes/physics.ts";
import { characterizationDeps, characterizationRouter } from "../routes/characterization.ts";

// Importing the routers starts the persistent Python supervisor (import side effect in
// server/processOrchestrator.ts); exit explicitly once done, preserving a failing exit code.
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

const ENVELOPE = {
  success: false,
  error: { code: "UNKNOWN_ALLOY", field: "alloyId", message: "Unknown alloy 'x'.", detail: { name: "'x'" } },
  errorKind: "validation",
};

test("pythonDispatchStatus maps validation to 422, failures to 500, success to 200", () => {
  assert.equal(pythonDispatchStatus(ENVELOPE, 2), 422);
  // The envelope decides even if a runner did not report the exit code.
  assert.equal(pythonDispatchStatus(ENVELOPE, undefined), 422);
  assert.equal(pythonDispatchStatus({ success: false, error: "boom", errorKind: "internal" }, 1), 500);
  assert.equal(pythonDispatchStatus({ success: true, value: 1 }, 1), 500);
  assert.equal(pythonDispatchStatus({ success: true }, null), 500);
  assert.equal(pythonDispatchStatus({ error: "Empty stdin payload" }, 0), 500);
  assert.equal(pythonDispatchStatus({ error: "no exit code reported" }, undefined), 500);
  assert.equal(pythonDispatchStatus({ success: true, value: 1 }, 0), 200);
  assert.equal(pythonDispatchStatus({ success: true, error: null }, 0), 200);
  assert.equal(pythonDispatchStatus({ success: true, error: "partial warning" }, 0), 200);
  assert.equal(pythonDispatchStatus({ success: false }, 0), 200);
  assert.equal(pythonDispatchStatus({ rawOutput: "not json" }, 0), 200);
  assert.equal(pythonDispatchStatus({ success: false }, undefined), 200);
  assert.equal(pythonDispatchStatus(null, 0), 200);
  assert.equal(pythonDispatchStatus([1, 2], 0), 200);
});

interface Harness {
  base: string;
  close: () => Promise<void>;
}

async function start(): Promise<Harness> {
  const app = express();
  app.use(express.json({ limit: "5mb" }));
  app.use(physicsRouter);
  app.use(characterizationRouter);
  const server: Server = await new Promise((resolve) => {
    const s = app.listen(0, "127.0.0.1", () => resolve(s));
  });
  const port = (server.address() as AddressInfo).port;
  return {
    base: `http://127.0.0.1:${port}`,
    close: () => new Promise<void>((resolve) => { server.close(() => resolve()); (server as any).closeAllConnections?.(); }),
  };
}

async function post(h: Harness, path: string, body: unknown) {
  const res = await fetch(h.base + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { status: res.status, json: (await res.json()) as any };
}

type Reply = { stdout: string; exitCode: number | null };

async function withRunners(reply: Reply, fn: (h: Harness, seen: string[]) => Promise<void>) {
  const h = await start();
  const seen: string[] = [];
  const fake = (async (script: string) => {
    seen.push(script);
    return { stdout: reply.stdout, stderr: "", exitCode: reply.exitCode, durationMs: 1 };
  }) as any;
  const originalPhysics = physicsDeps.runPythonScript;
  const originalCharacterization = characterizationDeps.runPythonScript;
  physicsDeps.runPythonScript = fake;
  characterizationDeps.runPythonScript = fake;
  try {
    await fn(h, seen);
  } finally {
    physicsDeps.runPythonScript = originalPhysics;
    characterizationDeps.runPythonScript = originalCharacterization;
    await h.close();
  }
}

const ROUTES = [
  ["/api/python/pourbaix-diagram", "python/pourbaix_solver.py"],
  ["/api/python/tafel-corrosion-rate", "python/tafel_corrosion_rate_solver.py"],
] as const;

test("validation envelope (exit 2) is relayed as HTTP 422 by both route handlers", async () => {
  await withRunners({ stdout: JSON.stringify(ENVELOPE) + "\n", exitCode: 2 }, async (h, seen) => {
    for (const [route, script] of ROUTES) {
      const r = await post(h, route, { element: "Xx" });
      assert.equal(r.status, 422, route);
      assert.deepEqual(r.json, ENVELOPE, route);
      assert.equal(seen.at(-1), script);
    }
  });
});

test("internal errors (exit 1) and top-level error payloads become HTTP 500", async () => {
  const internal = { success: false, error: "Insufficient data points", isPythonEngine: true, durationMs: 0, errorKind: "internal" };
  await withRunners({ stdout: JSON.stringify(internal), exitCode: 1 }, async (h) => {
    for (const [route] of ROUTES) {
      const r = await post(h, route, {});
      assert.equal(r.status, 500, route);
      assert.deepEqual(r.json, internal, route);
    }
  });
  await withRunners({ stdout: JSON.stringify({ error: "Empty stdin payload" }), exitCode: 0 }, async (h) => {
    for (const [route] of ROUTES) {
      const r = await post(h, route, {});
      assert.equal(r.status, 500, route);
      assert.equal(r.json.error, "Empty stdin payload");
    }
  });
});

test("successful solver output is still HTTP 200 and unchanged", async () => {
  const ok = { success: true, element: "Fe", nested: { a: [1, 2.5] } };
  await withRunners({ stdout: JSON.stringify(ok), exitCode: 0 }, async (h) => {
    for (const [route] of ROUTES) {
      const r = await post(h, route, { element: "Fe" });
      assert.equal(r.status, 200, route);
      assert.deepEqual(r.json, ok, route);
    }
  });
});
