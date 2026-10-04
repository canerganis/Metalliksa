/**
 * Request-target variants against the real security stack over real HTTP (raw request lines on a socket).
 * Regression for an auth bypass: tokenAuth checked the raw req.originalUrl, so an absolute-form target
 * ("GET http://host/api/... HTTP/1.1") skipped login while Express still routed it to the API handler.
 */
import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import net from "node:net";
import type { AddressInfo } from "node:net";
import express from "express";
import {
  LoginAuth,
  applySecurity,
  canonicalRequestPath,
  isProtectedApiTarget,
  rawRequestPath,
} from "../server/security.ts";

const TOKEN = "request-target-test-token";

async function startApp(auth: LoginAuth, token: string | null) {
  const app = express();
  applySecurity(app, token, { auth, log: () => {}, rate: { generalLimit: 10_000 } });
  app.get("/api/health", (_req, res) => { res.json({ status: "ok" }); });
  app.get("/api/lpbf/capabilities", (_req, res) => { res.json({ secret: "capabilities" }); });
  app.get("/api/lpbf/jobs/:id", (req, res) => { res.json({ secret: "job", id: req.params.id }); });
  app.all("/api/*", (_req, res) => { res.status(404).json({ error: "not found" }); });
  app.get("*", (_req, res) => { res.type("html").send("<!doctype html><title>spa</title>"); });
  const server = http.createServer(app);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  return { server, port: (server.address() as AddressInfo).port };
}

/** One raw HTTP/1.1 request; returns the status code and body. */
function rawRequest(port: number, target: string, headers: Record<string, string> = {}): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const socket = net.connect(port, "127.0.0.1");
    let data = "";
    socket.setEncoding("utf8");
    socket.on("data", (chunk) => { data += chunk; });
    socket.on("error", reject);
    socket.on("end", () => {
      const m = /^HTTP\/1\.1 (\d{3})/.exec(data);
      if (!m) return reject(new Error(`no status line for ${target}: ${JSON.stringify(data.slice(0, 80))}`));
      resolve({ status: Number(m[1]), body: data.split("\r\n\r\n").slice(1).join("\r\n\r\n") });
    });
    const extra = Object.entries(headers).map(([k, v]) => `${k}: ${v}\r\n`).join("");
    socket.write(`GET ${target} HTTP/1.1\r\nHost: 127.0.0.1:${port}\r\n${extra}Connection: close\r\n\r\n`);
  });
}

const variants = (port: number) => [
  `http://127.0.0.1:${port}/api/lpbf/capabilities`,
  "http://localhost/api/lpbf/capabilities",
  "HTTP://LOCALHOST/API/LPBF/CAPABILITIES",
  "/API/lpbf/capabilities",
  "/Api/Lpbf/Capabilities",
  "//api/lpbf/capabilities",
  "///api/lpbf/capabilities",
  "/api/%2e/lpbf/capabilities",
  "/api/./lpbf/capabilities",
  "/api;x/lpbf/capabilities",
  "/%61pi/lpbf/capabilities",
  "/%2fapi/lpbf/capabilities",
  "/./api/lpbf/capabilities",
  "/x/../api/lpbf/capabilities",
  "/x/%2e%2e/api/lpbf/capabilities",
  "/api\\lpbf\\capabilities",
  "/api/lpbf/capabilities/",
  "/api/lpbf/capabilities?x=/api/health",
  // A normalised alias of the /api/health exemption must not unlock another route.
  "/api/lpbf/jobs/..%2f..%2f..%2fapi%2fhealth",
  "/api/lpbf/jobs/%2e%2e%2f%2e%2e%2f%2e%2e%2fapi%2fhealth",
  "/api%2fhealth",
  "/api/health/../lpbf/capabilities",
  "/api",
  "/api/%zz",
  "*",
];

for (const [label, auth, token] of [
  ["one-time access code (non-loopback default)", new LoginAuth({ accessCode: "AUTOCODE-request-target" }), null],
  ["METALLIKSA_TOKEN", new LoginAuth({ token: TOKEN }), TOKEN],
] as const) {
  test(`login required (${label}): every request-target variant of an /api route is 400 or 401`, async () => {
    const { server, port } = await startApp(auth, token);
    try {
      for (const target of variants(port)) {
        const { status, body } = await rawRequest(port, target);
        assert.ok(status === 400 || status === 401, `${target} -> ${status} ${body.slice(0, 80)}`);
        assert.ok(!body.includes("secret"), `${target} leaked a protected body`);
      }
      // The exemption and the SPA shell stay reachable without login.
      assert.equal((await rawRequest(port, "/api/health")).status, 200);
      assert.equal((await rawRequest(port, "/API/health")).status, 200);
      assert.equal((await rawRequest(port, "/api/health?probe=1")).status, 200);
      const spa = await rawRequest(port, "/some/client/route");
      assert.equal(spa.status, 200);
      assert.match(spa.body, /spa/);
    } finally {
      server.close();
    }
  });
}

test("a valid bearer token still reaches the API; absolute-form stays 400 even with it", async () => {
  const { server, port } = await startApp(new LoginAuth({ token: TOKEN }), TOKEN);
  try {
    const auth = { Authorization: `Bearer ${TOKEN}` };
    const ok = await rawRequest(port, "/api/lpbf/capabilities", auth);
    assert.equal(ok.status, 200);
    assert.match(ok.body, /capabilities/);
    assert.equal((await rawRequest(port, "/API/lpbf/capabilities", auth)).status, 200);
    assert.equal((await rawRequest(port, `http://127.0.0.1:${port}/api/lpbf/capabilities`, auth)).status, 400);
  } finally {
    server.close();
  }
});

test("absolute-form targets are rejected even on the open loopback default (no login)", async () => {
  const app = express();
  applySecurity(app, null, { log: () => {} });
  app.get("/api/health", (_req, res) => { res.json({ status: "ok" }); });
  const server = http.createServer(app);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  try {
    assert.equal((await rawRequest(port, "/api/health")).status, 200);
    assert.equal((await rawRequest(port, `http://127.0.0.1:${port}/api/health`)).status, 400);
    assert.equal((await rawRequest(port, "*")).status, 400);
  } finally {
    server.close();
  }
});

test("the rate limiter counts request-target aliases of /api routes", async () => {
  const app = express();
  applySecurity(app, null, { log: () => {}, rate: { generalLimit: 2 } });
  app.get("*", (_req, res) => { res.send("x"); });
  const server = http.createServer(app);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  try {
    assert.equal((await rawRequest(port, "//api/a")).status, 200);
    assert.equal((await rawRequest(port, "/x/../api/b")).status, 200);
    assert.equal((await rawRequest(port, "/%61pi/c")).status, 429);
  } finally {
    server.close();
  }
});

test("canonicalRequestPath and isProtectedApiTarget", () => {
  assert.equal(rawRequestPath("http://h/api/x"), null);
  assert.equal(canonicalRequestPath("http://h/api/x"), null);
  assert.equal(canonicalRequestPath("/api/%zz"), null);
  assert.equal(canonicalRequestPath("//API//x/./y/../z/?q=1"), "/api/x/z/");
  assert.equal(canonicalRequestPath("/../.."), "/");
  assert.equal(canonicalRequestPath("/%2fapi%2Fx"), "/api/x");
  assert.equal(isProtectedApiTarget("/api/health"), false);
  assert.equal(isProtectedApiTarget("/API/Health?x=1"), false);
  assert.equal(isProtectedApiTarget("/api/x/../health"), true);
  assert.equal(isProtectedApiTarget("/api%2fhealth"), true);
  assert.equal(isProtectedApiTarget("/apix"), false);
  assert.equal(isProtectedApiTarget("/assets/index.js"), false);
  assert.equal(isProtectedApiTarget("/login"), false);
  assert.equal(isProtectedApiTarget("/api;x"), true);
  assert.equal(isProtectedApiTarget("*"), true);
});
