import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import type { Server } from "node:http";
import type { AddressInfo } from "node:net";
import baseTest, { after } from "node:test";
import express from "express";
import { MICROGRAPH_MAX_BODY_BYTES, physicsRouter } from "../routes/physics.ts";
import { getHostPython } from "../server/pythonRuntime";

// Micrograph review blocker B1: realistic frame sizes must pass end to end through the real HTTP route and the real
// Python dispatch (IPC daemon or ad-hoc process), not through the serial LPBF worker (1,000,000-character RPC lines).
// The browser decodes PNG/JPEG to 8-bit grey; the route receives exactly these grey bytes, so they are generated here.

// Importing routes/physics.ts starts the persistent Python IPC daemon, which keeps the event loop alive; like
// tests/python-dispatch-status.test.ts this file exits explicitly once its tests are done.
let anyFailed = false;
const test = (name: string, options: { skip: string | false; timeout: number }, fn: () => Promise<void>) =>
  baseTest(name, options, async () => {
    try {
      await fn();
    } catch (error) {
      anyFailed = true;
      throw error;
    }
  });
after(() => {
  setTimeout(() => process.exit(anyFailed ? 1 : 0), 250);
});

const python = getHostPython();
const probe = spawnSync(python.cmd, [...python.prefix, "-c", "import numpy, scipy"], { encoding: "utf8" });
const skip = probe.status === 0 ? false : `host Python lacks numpy/scipy (${python.cmd}): ${probe.stderr?.slice(0, 200)}`;

/** Square grains of pitch `pitch` px with 2-px boundaries (grey 50) on grains (grey 190). */
function gridImage(width: number, height: number, pitch: number) {
  const grey = new Uint8Array(width * height).fill(190);
  const boundary = (v: number) => v % pitch === pitch / 2 - 1 || v % pitch === pitch / 2;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) if (boundary(x) || boundary(y)) grey[y * width + x] = 50;
  return { imageWidth: width, imageHeight: height, imageData: Buffer.from(grey).toString("base64") };
}

async function start() {
  const app = express();
  app.use(express.json({ limit: "50mb" })); // server.ts
  app.use(physicsRouter);
  const server: Server = await new Promise((resolve) => { const s = app.listen(0, "127.0.0.1", () => resolve(s)); });
  const base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  const post = async (body: unknown) => {
    const res = await fetch(`${base}/api/python/micrograph-measure`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- untyped JSON reply, inspected field by field
    const json = (await res.json()) as Record<string, any>;
    return { status: res.status, json };
  };
  return { post, close: () => new Promise<void>((resolve) => { server.close(() => resolve()); server.closeAllConnections?.(); }) };
}

test("1024 x 768 and 4096 x 4096 grey images are measured through the HTTP route", { skip, timeout: 240000 }, async () => {
  const h = await start();
  try {
    for (const [w, ht] of [[1024, 768], [4096, 4096]] as const) {
      const body = { ...gridImage(w, ht, 32), umPerPx: 0.25, calibrationNote: "route test", boundaryMaxGrey: 110,
        darkMaxGrey: 110, darkLabel: "dark class" };
      const size = Buffer.byteLength(JSON.stringify(body));
      assert.ok(size > 1_000_000, "larger than the LPBF worker line limit");
      assert.ok(size <= MICROGRAPH_MAX_BODY_BYTES, `${w} x ${ht} fits the declared route limit (${size} bytes)`);
      const started = Date.now();
      const { status, json } = await h.post(body);
      assert.equal(status, 200, JSON.stringify(json).slice(0, 300));
      assert.equal(json.schema, "micrograph-measure/1");
      assert.deepEqual([json.record.width, json.record.height], [w, ht]);
      assert.equal(json.grainSize.meanIntercept.value, 32 * 0.25, `${w} x ${ht}: l_bar ${json.grainSize.meanIntercept.value}`);
      console.log(`micrograph route ${w}x${ht}: ${size} bytes, ${Date.now() - started} ms`);
    }
  } finally {
    await h.close();
  }
});

test("the route answers 413 above its limit and 422 for an invalid request", { skip, timeout: 120000 }, async () => {
  const h = await start();
  try {
    const big = await h.post({ imageWidth: 4096, imageHeight: 4096, imageData: "A".repeat(MICROGRAPH_MAX_BODY_BYTES) });
    assert.equal(big.status, 413);
    assert.match(big.json.error, /at most 4096 x 4096/);
    const bad = await h.post({ imageWidth: 2 });
    assert.equal(bad.status, 422);
    assert.equal(bad.json.errorKind, "validation");
    assert.match(bad.json.error.message, /imageHeight/);
  } finally {
    await h.close();
  }
});
