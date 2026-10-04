import { after, test as baseTest } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import type { AddressInfo } from "node:net";

// Mutual authentication, channel ownership and retry policy between server/processOrchestrator.ts
// and python/persistent_ipc_service.py. Importing the orchestrator starts the persistent Python
// supervisor (import side effect) with the defaults under test (ephemeral HTTP port on Windows,
// private UNIX socket on POSIX), so the test exits explicitly at the end.
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
delete process.env.METALLIX_IPC_HTTP;
process.env.METALLIX_IPC_WORKERS = "1";
process.env.METALLIX_IPC_TOKEN = "stale-value-from-the-environment"; // must be scrubbed at startup

const orchestrator = await import("../server/processOrchestrator.ts");
const {
  generateIpcToken, buildIpcSpawnSpec, resolveIpcHost, isLoopbackHost, assertDispatchableScript, DISPATCHABLE_SCRIPTS,
  ipcRequestMac, ipcResponseMac, sha256Hex, signIpcRequest, verifyIpcResponse, buildUnixFrame, acceptIpcReply,
  UnixReplyParser, IpcChannelError, MAX_IPC_RESPONSE_BYTES, PersistentPythonIPCSupervisor, pythonIPCSupervisor, runPythonScript,
} = orchestrator;
const supervisor = pythonIPCSupervisor as any;
const extraSupervisors: any[] = [];

function killDaemon(sup: any) {
  const pid = sup?.child?.pid;
  if (pid && process.platform === "win32") spawnSync("taskkill", ["/T", "/F", "/PID", String(pid)], { windowsHide: true });
  else sup?.child?.kill("SIGTERM");
}

after(() => {
  for (const sup of [supervisor, ...extraSupervisors]) killDaemon(sup);
  setTimeout(() => process.exit(anyFailed ? 1 : 0), 250);
});

// Same vectors as python/test_persistent_ipc_security.py (computed with plain hmac/hashlib).
const V_TOKEN = "k".repeat(64);
const V_NONCE = "0123456789abcdef0123456789abcdef";
const V_REQ = Buffer.from('{"script":"python/pourbaix_solver.py"}');
const V_RESP = Buffer.from('{"stdout": "x"}');

test("v2 request/response MACs match the Python implementation byte for byte", () => {
  assert.equal(ipcRequestMac(V_TOKEN, "POST", "/execute", "1700000000000", V_NONCE, V_REQ.length, sha256Hex(V_REQ)),
    "5126140a5094ef571795f7d658d319574d706efc1a2e62e61447f90f99006e3f");
  assert.equal(ipcResponseMac(V_TOKEN, V_NONCE, 200, V_RESP.length, sha256Hex(V_RESP)),
    "fd337f36ff1dc00192e77387e339bb7e347c8eb7b00eee2e5147479b42bd3d77");
});

test("signIpcRequest covers length and body hash; verifyIpcResponse binds nonce, status, length and body", () => {
  const token = generateIpcToken();
  const body = Buffer.from("{}");
  const a = signIpcRequest(token, "POST", "/execute", body, 1);
  const b = signIpcRequest(token, "POST", "/execute", body, 1);
  assert.match(a.nonce, /^[0-9a-f]{32}$/);
  assert.notEqual(a.nonce, b.nonce);
  assert.equal(a.digest, sha256Hex(body));
  assert.equal(a.mac, ipcRequestMac(token, "POST", "/execute", "1", a.nonce, 2, a.digest));
  const reply = Buffer.from('{"ok":1}');
  const d = sha256Hex(reply);
  const good = ipcResponseMac(token, a.nonce, 200, reply.length, d);
  assert.equal(verifyIpcResponse(token, a.nonce, 200, reply, d, good), true);
  assert.equal(verifyIpcResponse(token, a.nonce, 403, reply, d, good), false);
  assert.equal(verifyIpcResponse(token, b.nonce, 200, reply, d, good), false);
  assert.equal(verifyIpcResponse(token, a.nonce, 200, Buffer.from('{"ok":2}'), d, good), false); // hash
  assert.equal(verifyIpcResponse(generateIpcToken(), a.nonce, 200, reply, d, good), false);
  for (const bad of [undefined, "", "A".repeat(64), "0".repeat(63), ["x"]]) {
    assert.equal(verifyIpcResponse(token, a.nonce, 200, reply, d, bad), false);
    assert.equal(verifyIpcResponse(token, a.nonce, 200, reply, bad, good), false);
  }
});

function signedReply(token: string, nonce: string, status: number, obj: unknown) {
  const body = Buffer.from(JSON.stringify(obj));
  const digest = sha256Hex(body);
  return { body, digest, mac: ipcResponseMac(token, nonce, status, body.length, digest) };
}

test("one reply policy for both channels: unsigned or >= 400 means 'not executed'; signed garbage means 'unknown'", () => {
  const token = generateIpcToken();
  const nonce = "f".repeat(32);
  const ok = signedReply(token, nonce, 200, { stdout: "ok", exitCode: 0 });
  assert.deepEqual(acceptIpcReply(token, nonce, 200, ok.body, ok.digest, ok.mac, "X"), { stdout: "ok", exitCode: 0 });
  for (const status of [400, 401, 403, 404, 408, 413, 415, 500]) {
    const r = signedReply(token, nonce, status, { code: "X" });
    assert.throws(() => acceptIpcReply(token, nonce, status, r.body, r.digest, r.mac, "X"),
      (e: any) => e instanceof IpcChannelError && e.executed === false && /before running it/.test(e.message), String(status));
  }
  const forged = signedReply(generateIpcToken(), nonce, 200, { stdout: "forged" });
  assert.throws(() => acceptIpcReply(token, nonce, 200, forged.body, forged.digest, forged.mac, "X"),
    (e: any) => e instanceof IpcChannelError && e.executed === false && /not signed/.test(e.message));
  assert.throws(() => acceptIpcReply(token, nonce, 200, ok.body, ok.digest, undefined, "X"),
    (e: any) => e instanceof IpcChannelError && e.executed === false);
  const garbage = Buffer.from("not json");
  const gd = sha256Hex(garbage);
  assert.throws(() => acceptIpcReply(token, nonce, 200, garbage, gd, ipcResponseMac(token, nonce, 200, garbage.length, gd), "X"),
    (e: any) => e instanceof IpcChannelError && e.executed === "unknown");
});

test("UNIX frames: signed head + body; reply parser is incremental and bounded", () => {
  const token = generateIpcToken();
  const { data, nonce } = buildUnixFrame(token, { action: "execute", script: "python/pourbaix_solver.py" });
  const nl = data.indexOf(0x0a);
  const head = JSON.parse(data.subarray(0, nl).toString());
  const body = data.subarray(nl + 1);
  assert.equal(head.v, 2);
  assert.equal(head.nonce, nonce);
  assert.equal(head.len, body.length);
  assert.equal(head.sha256, sha256Hex(body));
  assert.equal(head.mac, ipcRequestMac(token, "UNIX", "/", head.ts, nonce, body.length, head.sha256));
  assert.ok(!data.toString().includes(token));

  const r = signedReply(token, nonce, 200, { stdout: "ok" });
  const wire = Buffer.concat([Buffer.from(JSON.stringify({ v: 2, status: 200, len: r.body.length, sha256: r.digest, mac: r.mac }) + "\n"), r.body]);
  const parser = new UnixReplyParser();
  let done: any = null;
  for (let i = 0; i < wire.length; i += 3) done = parser.push(wire.subarray(i, i + 3)) ?? done;
  assert.ok(done);
  assert.deepEqual(acceptIpcReply(token, nonce, done.status, done.body, done.sha256, done.mac, "UNIX"), { stdout: "ok" });
  assert.throws(() => new UnixReplyParser().push(Buffer.alloc(5000, 0x41)), /head too large/);
  assert.throws(() => new UnixReplyParser().push(Buffer.from(JSON.stringify({ v: 2, status: 200, len: MAX_IPC_RESPONSE_BYTES + 1 }) + "\n")),
    /reply too large/);
  assert.throws(() => new UnixReplyParser().push(Buffer.from("{nope}\n")), /malformed/);
});

test("buildIpcSpawnSpec: token via env only, stdin watch on, no remote override", () => {
  const base = { PATH: "x", METALLIX_IPC_TOKEN: "stale-user-value", METALLIX_IPC_SOCK: "/tmp/old.sock", METALLIX_IPC_ALLOW_REMOTE: "1" };
  const token = generateIpcToken();
  const spec = buildIpcSpawnSpec({ cmd: "py", prefix: ["-3"] }, "/repo/python/persistent_ipc_service.py", base, {
    port: 0, host: "127.0.0.1", token,
  });
  assert.deepEqual(spec.args, ["-3", "/repo/python/persistent_ipc_service.py"]);
  assert.ok(!spec.args.some((a) => a.includes(token)));
  assert.equal(spec.env.METALLIX_IPC_TOKEN, token);
  assert.equal(spec.env.METALLIX_IPC_PORT, "0");
  assert.equal(spec.env.METALLIX_IPC_STDIN_WATCH, "1");
  assert.equal(spec.env.METALLIX_IPC_SOCK, undefined);
  assert.equal(spec.env.METALLIX_IPC_ALLOW_REMOTE, undefined);
  assert.equal(base.METALLIX_IPC_TOKEN, "stale-user-value"); // caller's env untouched
  const explicit = buildIpcSpawnSpec({ cmd: "py", prefix: [] }, "s.py", base, { socketPath: "/run/me/s.sock", port: 5099, host: "::1", token });
  assert.equal(explicit.env.METALLIX_IPC_SOCK, "/run/me/s.sock");
});

test("isLoopbackHost / resolveIpcHost: loopback only (incl. ::1), everything else becomes 127.0.0.1", () => {
  for (const h of ["127.0.0.1", "127.8.9.10", "localhost", "LOCALHOST", "::1", "[::1]"]) assert.equal(isLoopbackHost(h), true, h);
  for (const h of ["0.0.0.0", "::", "192.168.1.5", "10.0.0.1", "example.com", "127.0.0.1.nip.io", ""]) assert.equal(isLoopbackHost(h), false, h);
  const warnings: string[] = [];
  const warn = (m: string) => warnings.push(m);
  assert.equal(resolveIpcHost({}, warn), "127.0.0.1");
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "localhost" }, warn), "localhost");
  assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: "[::1]" }, warn), "::1");
  assert.equal(warnings.length, 0);
  for (const h of ["0.0.0.0", "::", "192.168.1.5"]) {
    assert.equal(resolveIpcHost({ METALLIX_IPC_HOST: h, METALLIX_IPC_ALLOW_REMOTE: "1" }, warn), "127.0.0.1", h);
  }
  assert.equal(warnings.length, 3);
  assert.match(warnings[0], /WARNING.*only loopback/);
});

test("DISPATCHABLE_SCRIPTS mirrors ALLOWED_SCRIPT_NAMES in the daemon; the ad-hoc path uses the same list", async () => {
  const src = fs.readFileSync(path.join(process.cwd(), "python", "persistent_ipc_service.py"), "utf8");
  const block = /ALLOWED_SCRIPT_NAMES = frozenset\(\{([\s\S]*?)\}\)/.exec(src);
  assert.ok(block, "ALLOWED_SCRIPT_NAMES block not found");
  const pyNames = [...block![1].matchAll(/"([A-Za-z0-9_]+)"/g)].map((m) => m[1]).sort();
  assert.ok(pyNames.length >= 15);
  assert.deepEqual([...DISPATCHABLE_SCRIPTS].sort(), pyNames);

  assertDispatchableScript("python/pourbaix_solver.py");
  for (const bad of ["python/../../x.py", "pourbaix_solver.py", "/abs/python/x.py", "python\\x.py", "C:/python/x.py",
    "python/sub/x.py", "python/x.pyc", "", "python/persistent_ipc_service.py", "python/engine_dispatcher.py", "python/os.py"]) {
    assert.throws(() => assertDispatchableScript(bad), /Refusing to dispatch/, bad);
  }
  await assert.rejects(runPythonScript("python/engine_dispatcher.py", {}), /Refusing to dispatch/);
});

test("startup scrubs an inherited METALLIX_IPC_TOKEN; the daemon gets its own token in env, never argv, and a stdin pipe", () => {
  assert.equal(process.env.METALLIX_IPC_TOKEN, undefined);
  const child = supervisor.child;
  assert.ok(child, "supervisor spawned a daemon");
  const token: string = supervisor.ipcToken;
  assert.match(token, /^[0-9a-f]{64}$/);
  assert.ok(!child.spawnargs.some((a: string) => a.includes(token)));
  assert.ok(child.stdin, "stdin is a pipe held by the supervisor");
  const serverSrc = fs.readFileSync(path.join(process.cwd(), "server.ts"), "utf8");
  assert.match(serverSrc, /dotenv\.config\(\);\s*\n(?:\s*\/\/[^\n]*\n)*\s*delete process\.env\.METALLIX_IPC_TOKEN;/);
});

/** A supervisor without a daemon, whose channels and ad-hoc spawn are controlled by the test. */
function harness(opts: { unix?: () => Promise<any>; http?: () => Promise<any>; port?: number | null; socket?: string | null }) {
  const sup = Object.create(PersistentPythonIPCSupervisor.prototype) as any;
  const calls: string[] = [];
  Object.assign(sup, { requestsHandled: 0, totalDurationMs: 0, ipcToken: generateIpcToken(), httpHost: "127.0.0.1" });
  sup.unixTarget = () => (opts.socket === undefined ? "/x/ipc.sock" : opts.socket);
  sup.httpTarget = () => (opts.port === undefined ? 1 : opts.port);
  sup.executeViaUnixSocket = async () => { calls.push("unix"); return opts.unix ? opts.unix() : Promise.reject(new IpcChannelError("no unix", false)); };
  if (opts.http) sup.executeViaHttp = async (...a: any[]) => { calls.push("http"); return opts.http!.call(sup, ...a); };
  sup.executeViaAdHocSpawn = async () => { calls.push("adhoc"); return { stdout: "adhoc", stderr: "", exitCode: 0, durationMs: 1, channel: "ad_hoc_fallback" }; };
  return { sup, calls };
}

test("a request that may have run is never retried on another channel or spawned again", async () => {
  // Sent on the UNIX socket, then timeout/reset: no HTTP attempt, no ad-hoc spawn.
  let h = harness({ unix: () => Promise.reject(new IpcChannelError("UNIX socket IPC got no reply", "unknown")),
    http: async () => ({ stdout: "http" }) });
  await assert.rejects(h.sup.execute("python/pourbaix_solver.py", {}), /may already have run, so it was not retried/);
  assert.deepEqual(h.calls, ["unix"]);
  // Certainly not executed (connect failure / pre-execution refusal): next channel, then ad hoc.
  h = harness({ unix: () => Promise.reject(new IpcChannelError("ECONNREFUSED", false)),
    http: () => Promise.reject(new IpcChannelError("refused before running it (status 401)", false)) });
  assert.equal((await h.sup.execute("python/pourbaix_solver.py", {})).channel, "ad_hoc_fallback");
  assert.deepEqual(h.calls, ["unix", "http", "adhoc"]);
  // Any non-IpcChannelError (unexpected) is also treated as possibly executed.
  h = harness({ socket: null, http: () => Promise.reject(new Error("boom")) });
  await assert.rejects(h.sup.execute("python/pourbaix_solver.py", {}), /not retried/);
  assert.deepEqual(h.calls, ["http"]);
});

test("HTTP client: hang after send is 'unknown' (no retry); refused connection and unsigned replies are 'not executed'", async () => {
  let hits = 0;
  let mode: "hang" | "forge" | "huge" = "hang";
  const sockets = new Set<any>();
  const fake = http.createServer((req, res) => {
    hits++;
    req.resume();
    if (mode === "forge") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ stdout: '{"success": true, "FORGED": true}', exitCode: 0 }));
    } else if (mode === "huge") {
      res.writeHead(200, { "Content-Type": "application/json", "Content-Length": String(MAX_IPC_RESPONSE_BYTES + 10) });
      res.write("x");
    } // "hang": never answer
  });
  fake.on("connection", (s) => { sockets.add(s); s.on("close", () => sockets.delete(s)); });
  await new Promise<void>((resolve) => fake.listen(0, "127.0.0.1", () => resolve()));
  const port = (fake.address() as AddressInfo).port;
  try {
    const { sup, calls } = harness({ socket: null, port });
    sup.executeViaHttp = PersistentPythonIPCSupervisor.prototype["executeViaHttp" as keyof typeof PersistentPythonIPCSupervisor.prototype];
    // Daemon-side timeoutMs 200 -> client waits 200 ms + grace, then gives up without retrying.
    await assert.rejects(sup.execute("python/pourbaix_solver.py", { element: "Fe" }, [], 200), /may already have run/);
    assert.equal(hits, 1);
    assert.deepEqual(calls, []); // executeViaHttp is the real method (not recorded); no ad-hoc spawn
    mode = "forge";
    const r = await sup.execute("python/pourbaix_solver.py", { element: "Fe" }, [], 2000);
    assert.equal(r.channel, "ad_hoc_fallback"); // unsigned reply: not ours, not executed -> fall back
    assert.ok(!r.stdout.includes("FORGED"));
    mode = "huge";
    await assert.rejects(sup.execute("python/pourbaix_solver.py", {}, [], 2000), /may already have run.*too large/);
  } finally {
    for (const s of sockets) s.destroy();
    await new Promise<void>((resolve) => fake.close(() => resolve()));
  }
  const { sup: closed, calls } = harness({ socket: null, port });
  closed.executeViaHttp = PersistentPythonIPCSupervisor.prototype["executeViaHttp" as keyof typeof PersistentPythonIPCSupervisor.prototype];
  assert.equal((await closed.execute("python/pourbaix_solver.py", {}, [], 2000)).channel, "ad_hoc_fallback"); // ECONNREFUSED
  assert.deepEqual(calls, ["adhoc"]);
});

test("HTTP client signs the head, never sends the token, and sends the exact signed body", async () => {
  const seen: { headers: http.IncomingHttpHeaders; body: Buffer }[] = [];
  const fake = http.createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => { seen.push({ headers: req.headers, body: Buffer.concat(chunks) }); res.writeHead(401); res.end("{}"); });
  });
  await new Promise<void>((resolve) => fake.listen(0, "127.0.0.1", () => resolve()));
  const port = (fake.address() as AddressInfo).port;
  const token: string = supervisor.ipcToken;
  try {
    await assert.rejects(supervisor.executeViaHttp(port, "python/pourbaix_solver.py", { element: "Fe" }, [], 5000),
      (e: any) => e instanceof IpcChannelError && e.executed === false);
  } finally {
    await new Promise<void>((resolve) => fake.close(() => resolve()));
  }
  const { headers, body } = seen[0];
  assert.equal(headers.authorization, undefined);
  assert.equal(headers.origin, undefined);
  assert.equal(headers.host, `127.0.0.1:${port}`);
  assert.equal(headers["x-metallix-body-sha256"], sha256Hex(body));
  assert.equal(headers["x-metallix-mac"], ipcRequestMac(token, "POST", "/execute", String(headers["x-metallix-ts"]),
    String(headers["x-metallix-nonce"]), Number(headers["content-length"]), String(headers["x-metallix-body-sha256"])));
  assert.ok(!JSON.stringify(headers).includes(token));
  assert.ok(!body.toString("utf8").includes(token));
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
  sup.readiness = { unixActive: true, httpActive: true, unixSocketPath: "/x/ipc.sock", httpPort: 61234 };
  assert.equal(sup.unixTarget(), "/x/ipc.sock");
  assert.equal(sup.httpTarget(), 61234);
});

test("after the restart budget is spent the status is fallback_mode with an 'unavailable' reason", () => {
  const sup = Object.create(PersistentPythonIPCSupervisor.prototype) as any;
  Object.assign(sup, {
    child: null, isReady: false, isRestarting: false, restartAttempts: 10, maxRestartAttempts: 10, httpHost: "127.0.0.1",
    startTime: Date.now(), requestsHandled: 0, totalDurationMs: 0, lastError: "Python IPC daemon exited (code=1, signal=null)",
    readiness: { httpPort: null, unixSocketPath: null, warmModules: [], pythonVersion: null, unixActive: false, httpActive: false },
  });
  const st = sup.getStatus();
  assert.equal(st.status, "fallback_mode");
  assert.equal(st.isPersistent, false);
  assert.match(st.lastError, /^unavailable: Python IPC daemon failed 10 restarts/);
  sup.restartAttempts = 3;
  sup.isRestarting = true;
  assert.equal(sup.getStatus().status, "restarting");
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
  return new Promise<{ status: number; headers: http.IncomingHttpHeaders; raw: Buffer }>((resolve, reject) => {
    const req = http.request({ hostname: "127.0.0.1", port, path: reqPath, method, agent: false,
      headers: { ...headers, "Content-Length": String(Buffer.byteLength(body)) } }, (res) => {
      const chunks: Buffer[] = [];
      res.on("data", (c: Buffer) => chunks.push(c));
      res.on("end", () => resolve({ status: res.statusCode ?? 0, headers: res.headers, raw: Buffer.concat(chunks) }));
    });
    req.on("error", reject);
    req.end(body);
  });
}

test("end to end: the real daemon on its announced channel accepts our signature and refuses everyone else", { timeout: 300000 }, async () => {
  assert.ok(await waitFor(() => pythonIPCSupervisor.getStatus().status === "online", 240000),
    `daemon did not come online: ${JSON.stringify(pythonIPCSupervisor.getStatus())}`);
  const res = await runPythonScript("python/pourbaix_solver.py", { element: "Fe" }, [], 60000);
  assert.equal(res.channel, process.platform === "win32" ? "http_microservice" : "unix_socket", res.stderr);
  assert.ok(res.stdout.trim().startsWith("{"), res.stderr);

  const port: number | null = supervisor.readiness.httpPort;
  if (process.platform !== "win32") {
    // POSIX default: UNIX socket only, no TCP listener at all.
    assert.equal(port, null);
    assert.equal(pythonIPCSupervisor.getStatus().channels.httpMicroservice.active, false);
    return;
  }
  assert.ok(port && port > 0);
  assert.equal(pythonIPCSupervisor.getStatus().channels.httpMicroservice.url, `http://127.0.0.1:${port}`);
  const body = JSON.stringify({ script: "python/pourbaix_solver.py", payload: { element: "Fe" } });
  const json = { "Content-Type": "application/json" };
  const noAuth = await rawRequest(port, "POST", "/execute", json, body);
  const bearer = await rawRequest(port, "POST", "/execute", { ...json, Authorization: `Bearer ${supervisor.ipcToken}` }, body);
  const browser = await rawRequest(port, "POST", "/execute", { "Content-Type": "text/plain", Origin: "https://evil.example" },
    JSON.stringify({ script: "python/../../outside/pwn.py" }));
  assert.deepEqual([noAuth.status, bearer.status, browser.status], [401, 401, 403]);
  for (const r of [noAuth, bearer, browser]) {
    assert.equal(r.headers["access-control-allow-origin"], undefined);
    assert.equal(r.headers["x-metallix-mac"], undefined); // unauthenticated replies are never signed
  }
  const auth = signIpcRequest(supervisor.ipcToken, "POST", "/execute", Buffer.from(body));
  const signedHeaders = { ...json, "X-Metallix-Ts": auth.ts, "X-Metallix-Nonce": auth.nonce,
    "X-Metallix-Body-Sha256": auth.digest, "X-Metallix-Mac": auth.mac };
  const good = await rawRequest(port, "POST", "/execute", signedHeaders, body);
  assert.equal(good.status, 200);
  assert.equal(verifyIpcResponse(supervisor.ipcToken, auth.nonce, 200, good.raw, good.headers["x-metallix-body-sha256"], good.headers["x-metallix-mac"]), true);
  const replay = await rawRequest(port, "POST", "/execute", signedHeaders, body);
  assert.equal(replay.status, 401);
});

test("a squatter on a configured fixed port never receives a request or gets its output accepted", { timeout: 300000 }, async () => {
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
  process.env.METALLIX_IPC_HTTP = "1";
  let sup: any;
  try {
    sup = new PersistentPythonIPCSupervisor();
    sup.maxRestartAttempts = 0; // one daemon only for this test
    extraSupervisors.push(sup);
  } finally {
    delete process.env.METALLIX_IPC_PORT;
    delete process.env.METALLIX_IPC_HTTP;
  }
  try {
    // Windows: exclusive bind fails, HTTP is the only channel, the daemon exits before warm-up
    // (status then reports fallback_mode). POSIX: the daemon announces only its UNIX socket.
    assert.ok(await waitFor(() => sup.child === null || sup.isReady, 240000), "daemon neither exited nor became ready");
    assert.equal(sup.httpTarget(), null);
    if (sup.child === null) assert.equal(sup.getStatus().status, "fallback_mode");
    const res = await sup.execute("python/pourbaix_solver.py", { element: "Fe" }, [], 60000);
    assert.notEqual(res.channel, "http_microservice");
    assert.ok(!res.stdout.includes("FORGED_BY_SQUATTER"));
    assert.equal(squatterHits, 0);
  } finally {
    killDaemon(sup);
    await new Promise<void>((resolve) => squatter.close(() => resolve()));
  }
});
