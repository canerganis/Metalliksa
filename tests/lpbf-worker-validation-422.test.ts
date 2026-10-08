import assert from "node:assert/strict";
import type { ChildProcessWithoutNullStreams } from "node:child_process";
import { EventEmitter } from "node:events";
import type { Server } from "node:http";
import type { AddressInfo } from "node:net";
import { createInterface } from "node:readline";
import { PassThrough } from "node:stream";
import { test } from "node:test";
import express from "express";
import {
  LpbfWorkerBridge,
  LpbfWorkerValidationError,
  lpbfWorker,
} from "../server/lpbfWorkerBridge";
import { lpbfSimulationRouter, workerError } from "../routes/lpbfSimulation";

// Phase 6a fix round S1: the fatigue solver's UNKNOWN_ALLOY (input_validation) travels
// through the LPBF worker RPC as an envelope and must become HTTP 422 with that
// envelope, consistent with the migrated solvers on the dispatch routes.
const ENVELOPE = {
  success: false as const,
  error: {
    code: "UNKNOWN_ALLOY",
    field: "alloyName",
    message: "Unknown alloy 'Unobtainium' for domain 'fatigue_fracture'.",
    detail: { name: "'Unobtainium'", domain: "fatigue_fracture", reason: "unknown", suggestions: [] },
  },
  errorKind: "validation" as const,
};

function fakeChild() {
  const emitter = new EventEmitter() as EventEmitter & Record<string, unknown>;
  emitter.pid = 4242;
  emitter.exitCode = null;
  emitter.signalCode = null;
  emitter.stdout = new PassThrough();
  emitter.stderr = new PassThrough();
  emitter.stdin = new PassThrough();
  emitter.kill = () => {
    emitter.exitCode = 0;
    setImmediate(() => emitter.emit("close", 0));
    return true;
  };
  return emitter as unknown as ChildProcessWithoutNullStreams;
}

/** Bridge on a fake worker that answers each request line with `reply(request)`. */
function bridgeWith(reply: (request: { id: number; method: string }) => Record<string, unknown>) {
  const child = fakeChild();
  createInterface({ input: child.stdin as unknown as PassThrough }).on("line", (line) => {
    const request = JSON.parse(line);
    (child.stdout as unknown as PassThrough).write(`${JSON.stringify({ id: request.id, ...reply(request) })}\n`);
  });
  const bridge = new LpbfWorkerBridge({ command: () => ({ cmd: "native-python", args: [] }), spawn: () => child });
  return bridge;
}

test("a worker validation reply rejects with LpbfWorkerValidationError carrying the envelope", async () => {
  const bridge = bridgeWith((request) => request.method === "fatigue-fracture"
    ? { error: ENVELOPE.error.message, errorKind: "validation", validation: ENVELOPE }
    : { data: {} });
  await assert.rejects(bridge.request("fatigue-fracture", { alloyName: "Unobtainium" }), (error: unknown) => {
    assert.ok(error instanceof LpbfWorkerValidationError);
    assert.deepEqual(error.envelope, ENVELOPE);
    assert.equal(error.message, ENVELOPE.error.message);
    return true;
  });
  bridge.close();
});

test("plain or malformed worker errors stay generic errors", async () => {
  const bridge = bridgeWith((request) => request.method === "a"
    ? { error: "Unknown method" }
    : { error: "bad", errorKind: "validation", validation: { errorKind: "validation" } });
  for (const method of ["a", "b"]) {
    await assert.rejects(bridge.request(method, {}), (error: unknown) => {
      assert.ok(error instanceof Error);
      assert.ok(!(error instanceof LpbfWorkerValidationError));
      return true;
    });
  }
  bridge.close();
});

function fakeRes() {
  const out: { status?: number; body?: unknown; headers: Record<string, string> } = { headers: {} };
  const res = {
    status(code: number) { out.status = code; return res; },
    set(name: string, value: string) { out.headers[name] = value; return res; },
    json(body: unknown) { out.body = body; return res; },
  };
  return { res: res as never, out };
}

test("workerError maps the validation error to 422 with the envelope; other errors unchanged", () => {
  let r = fakeRes();
  workerError(r.res, new LpbfWorkerValidationError(ENVELOPE), "x");
  assert.equal(r.out.status, 422);
  assert.deepEqual(r.out.body, ENVELOPE);
  r = fakeRes();
  workerError(r.res, new Error("boom"), "x");
  assert.equal(r.out.status, 400);
  assert.deepEqual(r.out.body, { error: "boom" });
});

test("POST /api/python/lpbf-solidification-microstructure answers 422 with the envelope", async () => {
  const original = lpbfWorker.request;
  const calls: unknown[] = [];
  (lpbfWorker as unknown as { request: unknown }).request = async (method: string, payload: unknown) => {
    calls.push([method, payload]);
    throw new LpbfWorkerValidationError(ENVELOPE);
  };
  const app = express();
  app.use(express.json());
  app.use(lpbfSimulationRouter);
  const server: Server = await new Promise((resolve) => {
    const s = app.listen(0, "127.0.0.1", () => resolve(s));
  });
  try {
    const port = (server.address() as AddressInfo).port;
    const res = await fetch(`http://127.0.0.1:${port}/api/python/lpbf-solidification-microstructure`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alloyName: "Unobtainium" }),
    });
    assert.equal(res.status, 422);
    assert.deepEqual(await res.json(), ENVELOPE);
    assert.deepEqual(calls, [["solidification-microstructure", { alloyName: "Unobtainium" }]]);
  } finally {
    (lpbfWorker as unknown as { request: unknown }).request = original;
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
});
