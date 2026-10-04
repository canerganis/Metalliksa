import { after, test as baseTest } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import type { AddressInfo } from "node:net";

// Token plumbing between server/processOrchestrator.ts and python/persistent_ipc_service.py.
// Importing the orchestrator starts the persistent Python supervisor (import side effect), so
// the daemon is pointed at a free port / private socket first and the test exits explicitly.
let anyFailed = false;
const test: typeof baseTest = ((name: string, opts: any, fn?: any) => {
  const body = fn ?? opts;
  const wrapped = async (...args: any[]) => {
    try {
      await body(...args);
    } catch (error) {
      anyFailed = true;
      throw error;
    }
  };
  return fn ? baseTest(name, opts, wrapped) : baseTest(name, wrapped);
}) as any;

async function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const port = (srv.address() as AddressInfo).port;
      srv.close(() => resolve(port));
    });
  });
}

const ipcPort = await freePort();
process.env.METALLIX_IPC_PORT = String(ipcPort);
process.env.METALLIX_IPC_SOCK = path.join(os.tmpdir(), `metallix-ipc-test-${process.pid}.sock`);
process.env.METALLIX_IPC_WORKERS = "1";
delete process.env.METALLIX_IPC_HOST;
delete process.env.METALLIX_IPC_TOKEN;

const orchestrator = await import("../server/processOrchestrator.ts");
const {
  generateIpcToken, buildIpcSpawnSpec, resolveIpcHost, isLoopbackHost,
  ipcAuthorizationHeader, assertDispatchableScript, pythonIPCSupervisor, runPythonScript,
} = orchestrator;
const supervisor = pythonIPCSupervisor as any;

after(() => {
  // Kill the daemon together with its pool workers (TerminateProcess alone orphans them on Windows).
  const pid = supervisor.child?.pid;
  if (pid && process.platform === "win32") spawnSync("taskkill", ["/T", "/F", "/PID", String(pid)], { windowsHide: true });
  setTimeout(() => process.exit(anyFailed ? 1 : 0), 250);
});

test("generateIpcToken returns 32 random bytes as hex, fresh each call", () => {
  const a = generateIpcToken();
  const b = generateIpcToken();
  assert.match(a, /^[0-9a-f]{64}$/);
  assert.notEqual(a, b);
});

test("buildIpcSpawnSpec passes the token via env only, overriding any inherited value", () => {
  const base = { PATH: "x", METALLIX_IPC_TOKEN: "stale-user-value" };
  const token = generateIpcToken();
  const spec = buildIpcSpawnSpec({ cmd: "py", prefix: ["-3"] }, "/repo/python/persistent_ipc_service.py", base, {
    socketPath: "/tmp/s.sock", port: 5099, host: "127.0.0.1", token,
  });
  assert.equal(spec.cmd, "py");
  assert.deepEqual(spec.args, ["-3", "/repo/python/persistent_ipc_service.py"]);
  assert.ok(!spec.args.some((a) => a.includes(token)));
  assert.equal(spec.env.METALLIX_IPC_TOKEN, token);
  assert.equal(spec.env.METALLIX_IPC_PORT, "5099");
  assert.equal(spec.env.METALLIX_IPC_HOST, "127.0.0.1");
  assert.equal(spec.env.PATH, "x");
  assert.equal(base.METALLIX_IPC_TOKEN, "stale-user-value"); // caller's env untouched
});

test("isLoopbackHost / resolveIpcHost keep the daemon on loopback unless explicitly overridden", () => {
  for (const h of ["127.0.0.1", "127.8.9.10", "localhost", "LOCALHOST", "::1", "[::1]"]) assert.equal(isLoopbackHost(h), true, h);
  for (const h of ["0.0.0.0", "::", "192.168.1.5", "10.0.0.1", "example.com", "127.0.0.1.nip.io", ""]) assert.equal(isLoopbackHost(h), false, h);

  const warnings: string[] = [];
  const warn = (m: string) => warnings.push(m);
  assert.equal(resolveIpcHost({}, warn), "127.0.0.1");
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "localhost" }, warn), "localhost");
  assert.equal(warnings.length, 0);
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "0.0.0.0" }, warn), "127.0.0.1");
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "0.0.0.0", METALLIX_IPC_ALLOW_REMOTE: "true" }, warn), "127.0.0.1");
  assert.equal(warnings.length, 2);
  assert.match(warnings[0], /WARNING.*non-loopback/);
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "0.0.0.0", METALLIX_IPC_ALLOW_REMOTE: "1" }, warn), "0.0.0.0");
  assert.match(warnings[2], /WARNING.*NON-LOOPBACK/);
});

test("ipcAuthorizationHeader and assertDispatchableScript", async () => {
  assert.equal(ipcAuthorizationHeader("abc"), "Bearer abc");
  assertDispatchableScript("python/pourbaix_solver.py");
  for (const bad of ["python/../../x.py", "pourbaix_solver.py", "/abs/python/x.py", "python\\x.py",
    "C:/python/x.py", "python/sub/x.py", "python/x.pyc", ""]) {
    assert.throws(() => assertDispatchableScript(bad), /Refusing to dispatch/, bad);
  }
  await assert.rejects(runPythonScript("python/../../outside/pwn.py", {}), /Refusing to dispatch/);
});

test("the spawned daemon gets the token in its environment, never on its command line", () => {
  const child = supervisor.child;
  assert.ok(child, "supervisor spawned a daemon");
  const token: string = supervisor.ipcToken;
  assert.match(token, /^[0-9a-f]{64}$/);
  assert.ok(!child.spawnargs.some((a: string) => a.includes(token)));
  assert.ok(child.spawnargs.some((a: string) => a.endsWith("persistent_ipc_service.py")));
});

test("HTTP client sends the bearer token and treats a non-200 reply as a channel failure", async () => {
  const seen: http.IncomingHttpHeaders[] = [];
  const fake = http.createServer((req, res) => {
    seen.push(req.headers);
    req.resume();
    req.on("end", () => {
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Missing or invalid IPC token", code: "UNAUTHORIZED" }));
    });
  });
  await new Promise<void>((resolve) => fake.listen(0, "127.0.0.1", () => resolve()));
  const realPort = supervisor.httpPort;
  const fakePort = (fake.address() as AddressInfo).port;
  supervisor.httpPort = fakePort;
  try {
    await assert.rejects(
      supervisor.executeViaHttp("python/pourbaix_solver.py", { element: "Fe" }, [], 5000),
      /HTTP 401 UNAUTHORIZED/
    );
  } finally {
    supervisor.httpPort = realPort;
    await new Promise<void>((resolve) => fake.close(() => resolve()));
  }
  assert.equal(seen.length, 1);
  assert.equal(seen[0].authorization, `Bearer ${supervisor.ipcToken}`);
  assert.equal(seen[0]["content-type"], "application/json");
  assert.equal(seen[0].origin, undefined);
  assert.equal(seen[0].host, `127.0.0.1:${fakePort}`); // matches the daemon's Host allowlist
});

async function waitOnline(timeoutMs: number): Promise<boolean> {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (pythonIPCSupervisor.getStatus().status === "online") return true;
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

function rawPost(headers: Record<string, string>, body: string): Promise<{ status: number; acao: string | undefined; json: any }> {
  return new Promise((resolve, reject) => {
    const req = http.request({ hostname: "127.0.0.1", port: ipcPort, path: "/execute", method: "POST",
      headers: { ...headers, "Content-Length": String(Buffer.byteLength(body)) } }, (res) => {
      let text = "";
      res.on("data", (c) => (text += c));
      res.on("end", () => {
        let json: any = null;
        try { json = JSON.parse(text); } catch { json = text; }
        resolve({ status: res.statusCode ?? 0, acao: res.headers["access-control-allow-origin"] as string | undefined, json });
      });
    });
    req.on("error", reject);
    req.end(body);
  });
}

test("end to end: the real daemon accepts the supervisor's token and refuses everyone else", { timeout: 240000 }, async () => {
  assert.ok(await waitOnline(180000), `daemon did not come online: ${JSON.stringify(pythonIPCSupervisor.getStatus())}`);

  const res = await runPythonScript("python/pourbaix_solver.py", { element: "Fe" }, [], 60000);
  assert.equal(res.channel, process.platform === "win32" ? "http_microservice" : "unix_socket", res.stderr);
  assert.ok(res.stdout.trim().startsWith("{"), res.stderr);

  const body = JSON.stringify({ script: "python/pourbaix_solver.py", payload: { element: "Fe" } });
  const json = { "Content-Type": "application/json" };
  const noToken = await rawPost(json, body);
  assert.equal(noToken.status, 401);
  const wrong = await rawPost({ ...json, Authorization: `Bearer ${"0".repeat(64)}` }, body);
  assert.equal(wrong.status, 401);
  const browser = await rawPost({ "Content-Type": "text/plain", Origin: "https://evil.example" },
    JSON.stringify({ script: "python/../../outside/pwn.py" }));
  assert.equal(browser.status, 403);
  for (const r of [noToken, wrong, browser]) assert.equal(r.acao, undefined);

  const good = await rawPost({ ...json, Authorization: ipcAuthorizationHeader(supervisor.ipcToken) }, body);
  assert.equal(good.status, 200);
  assert.equal(typeof good.json.exitCode, "number");
  const traversal = await rawPost({ ...json, Authorization: ipcAuthorizationHeader(supervisor.ipcToken) },
    JSON.stringify({ script: "python/../../outside/pwn.py" }));
  assert.equal(traversal.status, 400);
});
