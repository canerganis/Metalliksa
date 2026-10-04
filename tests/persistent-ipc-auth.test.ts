import { after, test as baseTest } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { spawnSync } from "node:child_process";
import type { AddressInfo } from "node:net";

// Mutual authentication and channel ownership between server/processOrchestrator.ts and
// python/persistent_ipc_service.py. Importing the orchestrator starts the persistent Python
// supervisor (import side effect) with the defaults under test (ephemeral HTTP port, private
// socket directory), so the test exits explicitly at the end.
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

delete process.env.METALLIX_IPC_PORT;
delete process.env.METALLIX_IPC_SOCK;
delete process.env.METALLIX_IPC_HOST;
process.env.METALLIX_IPC_WORKERS = "1";
process.env.METALLIX_IPC_TOKEN = "stale-value-from-the-environment"; // must be scrubbed at startup

const orchestrator = await import("../server/processOrchestrator.ts");
const {
  generateIpcToken, buildIpcSpawnSpec, resolveIpcHost, isLoopbackHost, assertDispatchableScript,
  ipcRequestMac, ipcResponseMac, signIpcRequest, verifyIpcResponseMac, buildUnixFrame, parseUnixResponse,
  PersistentPythonIPCSupervisor, pythonIPCSupervisor, runPythonScript,
} = orchestrator;
const supervisor = pythonIPCSupervisor as any;
const extraSupervisors: any[] = [];

function killDaemon(sup: any) {
  const pid = sup?.child?.pid;
  if (pid && process.platform === "win32") spawnSync("taskkill", ["/T", "/F", "/PID", String(pid)], { windowsHide: true });
  else sup?.child?.kill("SIGTERM");
}

after(() => {
  // Kill daemons together with their pool workers (TerminateProcess alone orphans them on Windows).
  for (const sup of [supervisor, ...extraSupervisors]) killDaemon(sup);
  setTimeout(() => process.exit(anyFailed ? 1 : 0), 250);
});

// Same vectors as python/test_persistent_ipc_security.py (computed with plain hmac/hashlib).
const V_TOKEN = "k".repeat(64);
const V_NONCE = "0123456789abcdef0123456789abcdef";

test("request/response MACs match the Python implementation byte for byte", () => {
  assert.equal(ipcRequestMac(V_TOKEN, "POST", "/execute", "1700000000000", V_NONCE, Buffer.from('{"script":"python/pourbaix_solver.py"}')),
    "00622ace5f176a373bda15f2e964903e74d6457c8a60d5907f17b10e34773ffe");
  assert.equal(ipcResponseMac(V_TOKEN, V_NONCE, 200, Buffer.from('{"stdout": "x"}')),
    "3baf7d40b3db8b160d35c8e4caf1338cad617f030cb908dd06c0e87bd128973c");
});

test("signIpcRequest uses a fresh nonce and verifyIpcResponseMac rejects anything not from the token holder", () => {
  const token = generateIpcToken();
  const body = Buffer.from("{}");
  const a = signIpcRequest(token, "POST", "/execute", body, 1);
  const b = signIpcRequest(token, "POST", "/execute", body, 1);
  assert.match(a.nonce, /^[0-9a-f]{32}$/);
  assert.notEqual(a.nonce, b.nonce);
  assert.equal(a.mac, ipcRequestMac(token, "POST", "/execute", "1", a.nonce, body));
  const good = ipcResponseMac(token, a.nonce, 200, body);
  assert.equal(verifyIpcResponseMac(token, a.nonce, 200, body, good), true);
  assert.equal(verifyIpcResponseMac(token, a.nonce, 403, body, good), false);         // status bound
  assert.equal(verifyIpcResponseMac(token, b.nonce, 200, body, good), false);         // nonce bound
  assert.equal(verifyIpcResponseMac(token, a.nonce, 200, Buffer.from("[]"), good), false); // body bound
  assert.equal(verifyIpcResponseMac(generateIpcToken(), a.nonce, 200, body, good), false);
  for (const bad of [undefined, "", "A".repeat(64), "0".repeat(63), ["x"]]) assert.equal(verifyIpcResponseMac(token, a.nonce, 200, body, bad), false);
});

test("UNIX frames: signed request; one policy for replies (unsigned or status >= 400 is a channel failure)", () => {
  const token = generateIpcToken();
  const { line, nonce } = buildUnixFrame(token, { action: "execute", script: "python/pourbaix_solver.py" });
  const frame = JSON.parse(line);
  assert.ok(line.endsWith("\n"));
  assert.equal(frame.v, 1);
  assert.equal(frame.nonce, nonce);
  assert.equal(frame.mac, ipcRequestMac(token, "UNIX", "/", frame.ts, nonce, Buffer.from(frame.body, "utf8")));
  assert.ok(!line.includes(token));

  const reply = (status: number, bodyObj: unknown, signer = token, n = nonce) => {
    const body = JSON.stringify(bodyObj);
    return JSON.stringify({ v: 1, status, body, mac: ipcResponseMac(signer, n, status, Buffer.from(body, "utf8")) });
  };
  assert.deepEqual(parseUnixResponse(token, nonce, reply(200, { stdout: "ok", exitCode: 0 })), { stdout: "ok", exitCode: 0 });
  for (const status of [400, 401, 403, 404, 413, 500]) {
    assert.throws(() => parseUnixResponse(token, nonce, reply(status, { code: "X" })), /refused the request/, String(status));
  }
  assert.throws(() => parseUnixResponse(token, nonce, reply(200, { stdout: "forged" }, generateIpcToken())), /not signed/);
  assert.throws(() => parseUnixResponse(token, nonce, reply(200, { stdout: "forged" }, token, "f".repeat(32))), /not signed/);
  assert.throws(() => parseUnixResponse(token, nonce, JSON.stringify({ v: 1, status: 200, body: "{}" })), /not signed/);
  assert.throws(() => parseUnixResponse(token, nonce, JSON.stringify({ status: 401, error: "x" })), /not signed/);
  assert.throws(() => parseUnixResponse(token, nonce, "not json"), /malformed/);
});

test("buildIpcSpawnSpec passes the token via env only; ephemeral port and private socket by default", () => {
  const base = { PATH: "x", METALLIX_IPC_TOKEN: "stale-user-value", METALLIX_IPC_SOCK: "/tmp/old.sock" };
  const token = generateIpcToken();
  const spec = buildIpcSpawnSpec({ cmd: "py", prefix: ["-3"] }, "/repo/python/persistent_ipc_service.py", base, {
    port: 0, host: "127.0.0.1", token,
  });
  assert.deepEqual(spec.args, ["-3", "/repo/python/persistent_ipc_service.py"]);
  assert.ok(!spec.args.some((a) => a.includes(token)));
  assert.equal(spec.env.METALLIX_IPC_TOKEN, token);
  assert.equal(spec.env.METALLIX_IPC_PORT, "0");
  assert.equal(spec.env.METALLIX_IPC_SOCK, undefined);
  assert.equal(base.METALLIX_IPC_TOKEN, "stale-user-value"); // caller's env untouched
  const explicit = buildIpcSpawnSpec({ cmd: "py", prefix: [] }, "s.py", base, { socketPath: "/run/me/s.sock", port: 5099, host: "::1", token });
  assert.equal(explicit.env.METALLIX_IPC_SOCK, "/run/me/s.sock");
  assert.equal(explicit.env.METALLIX_IPC_PORT, "5099");
});

test("isLoopbackHost / resolveIpcHost: loopback by default, never a wildcard, remote only by override", () => {
  for (const h of ["127.0.0.1", "127.8.9.10", "localhost", "LOCALHOST", "::1", "[::1]"]) assert.equal(isLoopbackHost(h), true, h);
  for (const h of ["0.0.0.0", "::", "192.168.1.5", "10.0.0.1", "example.com", "127.0.0.1.nip.io", ""]) assert.equal(isLoopbackHost(h), false, h);

  const warnings: string[] = [];
  const warn = (m: string) => warnings.push(m);
  assert.equal(resolveIpcHost({}, warn), "127.0.0.1");
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "localhost" }, warn), "localhost");
  assert.equal(warnings.length, 0);
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "192.168.1.5" }, warn), "127.0.0.1");
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "0.0.0.0", METALLIX_IPC_ALLOW_REMOTE: "1" }, warn), "127.0.0.1");
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "::", METALLIX_IPC_ALLOW_REMOTE: "1" }, warn), "127.0.0.1");
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "192.168.1.5", METALLIX_IPC_ALLOW_REMOTE: "true" }, warn), "127.0.0.1");
  assert.equal(warnings.length, 4);
  assert.match(warnings[1], /wildcard/);
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "192.168.1.5", METALLIX_IPC_ALLOW_REMOTE: "1" }, warn), "192.168.1.5");
  assert.match(warnings[4], /WARNING.*NON-LOOPBACK/);
});

test("assertDispatchableScript only allows python/<module>.py", async () => {
  assertDispatchableScript("python/pourbaix_solver.py");
  for (const bad of ["python/../../x.py", "pourbaix_solver.py", "/abs/python/x.py", "python\\x.py",
    "C:/python/x.py", "python/sub/x.py", "python/x.pyc", ""]) {
    assert.throws(() => assertDispatchableScript(bad), /Refusing to dispatch/, bad);
  }
  await assert.rejects(runPythonScript("python/../../outside/pwn.py", {}), /Refusing to dispatch/);
});

test("startup scrubs an inherited METALLIX_IPC_TOKEN; the daemon gets its own token in env, never argv", () => {
  assert.equal(process.env.METALLIX_IPC_TOKEN, undefined);
  const child = supervisor.child;
  assert.ok(child, "supervisor spawned a daemon");
  const token: string = supervisor.ipcToken;
  assert.match(token, /^[0-9a-f]{64}$/);
  assert.ok(!child.spawnargs.some((a: string) => a.includes(token)));
});

test("HTTP client signs requests, never sends the token, and refuses unsigned or non-200 replies", async () => {
  const seen: { headers: http.IncomingHttpHeaders; body: Buffer }[] = [];
  let reply: { status: number; body: string } = { status: 200, body: "" };
  const fake = http.createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => {
      seen.push({ headers: req.headers, body: Buffer.concat(chunks) });
      res.writeHead(reply.status, { "Content-Type": "application/json" });
      res.end(reply.body);
    });
  });
  await new Promise<void>((resolve) => fake.listen(0, "127.0.0.1", () => resolve()));
  const port = (fake.address() as AddressInfo).port;
  try {
    // A listener without the token (squatter) answers 200 with forged output: rejected.
    reply = { status: 200, body: JSON.stringify({ stdout: '{"success": true, "FORGED": true}', exitCode: 0 }) };
    await assert.rejects(supervisor.executeViaHttp(port, "python/pourbaix_solver.py", { element: "Fe" }, [], 5000),
      /not signed by this server's daemon \(HTTP 200\)/);
    reply = { status: 401, body: JSON.stringify({ code: "UNAUTHORIZED" }) };
    await assert.rejects(supervisor.executeViaHttp(port, "python/pourbaix_solver.py", {}, [], 5000), /not signed/);
  } finally {
    await new Promise<void>((resolve) => fake.close(() => resolve()));
  }
  const token: string = supervisor.ipcToken;
  const first = seen[0];
  assert.equal(first.headers.authorization, undefined);
  assert.equal(first.headers.origin, undefined);
  assert.equal(first.headers.host, `127.0.0.1:${port}`); // matches the daemon's Host allowlist
  assert.equal(first.headers["content-type"], "application/json");
  assert.equal(first.headers["x-metallix-mac"], ipcRequestMac(token, "POST", "/execute",
    String(first.headers["x-metallix-ts"]), String(first.headers["x-metallix-nonce"]), first.body));
  for (const s of seen) {
    assert.ok(!JSON.stringify(s.headers).includes(token));
    assert.ok(!s.body.toString("utf8").includes(token));
  }
});

test("channels are used only after this server's own daemon announced them", () => {
  const sup = Object.create(PersistentPythonIPCSupervisor.prototype) as any;
  sup.isReady = false;
  sup.readiness = { unixActive: true, httpActive: true, unixSocketPath: "/x/ipc.sock", httpPort: 5055 };
  assert.equal(sup.unixTarget(), null);
  assert.equal(sup.httpTarget(), null);
  sup.isReady = true;
  sup.readiness = { unixActive: false, httpActive: false, unixSocketPath: "/x/ipc.sock", httpPort: 5055 };
  assert.equal(sup.unixTarget(), null);
  assert.equal(sup.httpTarget(), null);
  sup.readiness = { unixActive: true, httpActive: true, unixSocketPath: null, httpPort: null };
  assert.equal(sup.unixTarget(), null);
  assert.equal(sup.httpTarget(), null);
  sup.readiness = { unixActive: true, httpActive: true, unixSocketPath: "/x/ipc.sock", httpPort: 61234 };
  assert.equal(sup.unixTarget(), "/x/ipc.sock");
  assert.equal(sup.httpTarget(), 61234);
});

async function waitFor(pred: () => boolean, timeoutMs: number): Promise<boolean> {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (pred()) return true;
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

function rawRequest(port: number, method: string, reqPath: string, headers: Record<string, string>, body: string) {
  return new Promise<{ status: number; acao: string | undefined; mac: string | undefined; raw: Buffer }>((resolve, reject) => {
    const req = http.request({ hostname: "127.0.0.1", port, path: reqPath, method,
      headers: { ...headers, "Content-Length": String(Buffer.byteLength(body)) } }, (res) => {
      const chunks: Buffer[] = [];
      res.on("data", (c: Buffer) => chunks.push(c));
      res.on("end", () => resolve({ status: res.statusCode ?? 0, acao: res.headers["access-control-allow-origin"] as string | undefined,
        mac: res.headers["x-metallix-mac"] as string | undefined, raw: Buffer.concat(chunks) }));
    });
    req.on("error", reject);
    req.end(body);
  });
}

test("end to end: the real daemon on its announced channel accepts our signature and refuses everyone else", { timeout: 240000 }, async () => {
  assert.ok(await waitFor(() => pythonIPCSupervisor.getStatus().status === "online", 180000),
    `daemon did not come online: ${JSON.stringify(pythonIPCSupervisor.getStatus())}`);
  const status = pythonIPCSupervisor.getStatus();
  const port: number = supervisor.readiness.httpPort;
  assert.ok(port > 0);
  assert.equal(status.channels.httpMicroservice.url, `http://127.0.0.1:${port}`);

  const res = await runPythonScript("python/pourbaix_solver.py", { element: "Fe" }, [], 60000);
  assert.equal(res.channel, process.platform === "win32" ? "http_microservice" : "unix_socket", res.stderr);
  assert.ok(res.stdout.trim().startsWith("{"), res.stderr);

  const body = JSON.stringify({ script: "python/pourbaix_solver.py", payload: { element: "Fe" } });
  const json = { "Content-Type": "application/json" };
  const noAuth = await rawRequest(port, "POST", "/execute", json, body);
  assert.equal(noAuth.status, 401);
  const bearer = await rawRequest(port, "POST", "/execute", { ...json, Authorization: `Bearer ${supervisor.ipcToken}` }, body);
  assert.equal(bearer.status, 401); // the token itself is no longer a credential on the wire
  const browser = await rawRequest(port, "POST", "/execute", { "Content-Type": "text/plain", Origin: "https://evil.example" },
    JSON.stringify({ script: "python/../../outside/pwn.py" }));
  assert.equal(browser.status, 403);
  for (const r of [noAuth, bearer, browser]) {
    assert.equal(r.acao, undefined);
    assert.equal(r.mac, undefined); // unauthenticated replies are never signed
  }

  const auth = signIpcRequest(supervisor.ipcToken, "POST", "/execute", Buffer.from(body));
  const signedHeaders = { ...json, "X-Metallix-Ts": auth.ts, "X-Metallix-Nonce": auth.nonce, "X-Metallix-Mac": auth.mac };
  const good = await rawRequest(port, "POST", "/execute", signedHeaders, body);
  assert.equal(good.status, 200);
  assert.equal(verifyIpcResponseMac(supervisor.ipcToken, auth.nonce, 200, good.raw, good.mac), true);
  const replay = await rawRequest(port, "POST", "/execute", signedHeaders, body);
  assert.equal(replay.status, 401);
});

test("a squatter on a configured fixed port never receives a request or gets its output accepted", { timeout: 240000 }, async () => {
  let squatterHits = 0;
  const squatter = http.createServer((req, res) => {
    squatterHits++;
    req.resume();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ stdout: '{"success": true, "FORGED_BY_SQUATTER": true}', exitCode: 0 }));
  });
  await new Promise<void>((resolve) => squatter.listen(0, "127.0.0.1", () => resolve()));
  const port = (squatter.address() as AddressInfo).port;
  process.env.METALLIX_IPC_PORT = String(port);
  let sup: any;
  try {
    sup = new PersistentPythonIPCSupervisor();
    sup.maxRestartAttempts = 0; // one daemon only for this test
    extraSupervisors.push(sup);
  } finally {
    delete process.env.METALLIX_IPC_PORT;
  }
  try {
    // Windows: exclusive bind fails, HTTP is the only channel, the daemon exits before warm-up.
    // POSIX: the daemon announces only its private UNIX socket.
    assert.ok(await waitFor(() => sup.child === null || sup.isReady, 180000), "daemon neither exited nor became ready");
    assert.equal(sup.httpTarget(), null);
    const res = await sup.execute("python/pourbaix_solver.py", { element: "Fe" }, [], 60000);
    assert.notEqual(res.channel, "http_microservice");
    assert.ok(!res.stdout.includes("FORGED_BY_SQUATTER"));
    assert.equal(squatterHits, 0);
  } finally {
    killDaemon(sup);
    await new Promise<void>((resolve) => squatter.close(() => resolve()));
  }
});
