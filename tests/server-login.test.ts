import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import type { AddressInfo } from "node:net";
import express from "express";
import {
  LoginAuth,
  SESSION_COOKIE,
  accessLog,
  applySecurity,
  buildLoginUrl,
  installLogin,
  isLoopbackHost,
  resolveBindConfig,
  tokenAuth,
} from "../server/security.ts";

function mockRes() {
  const headers: Record<string, string> = {};
  const res: any = {
    statusCode: 200,
    body: undefined,
    ended: undefined as string | undefined,
    headersSent: false,
    setHeader(k: string, v: string) { headers[k.toLowerCase()] = v; return res; },
    status(code: number) { res.statusCode = code; return res; },
    json(b: unknown) { res.body = b; return res; },
    end(b?: string) { res.ended = b ?? ""; return res; },
    on() { return res; },
    headers,
  };
  return res;
}
function mockReq(over: Record<string, unknown> = {}): any {
  return { method: "GET", originalUrl: "/api/x", url: "/api/x", headers: {}, ip: "1.2.3.4", ...over };
}
function run(mw: any, req: any, res: any) {
  let nexted = false;
  mw(req, res, () => { nexted = true; });
  return nexted;
}

/** Capture the GET /login and POST /logout handlers registered by installLogin. */
function loginHandlers(auth: LoginAuth) {
  const routes: Record<string, any> = {};
  const fakeApp: any = {
    get(path: string, h: any) { routes[`GET ${path}`] = h; },
    post(path: string, h: any) { routes[`POST ${path}`] = h; },
  };
  installLogin(fakeApp, auth);
  return routes;
}

function login(auth: LoginAuth, code: string | null, over: Record<string, unknown> = {}) {
  const url = code === null ? "/login" : `/login?code=${encodeURIComponent(code)}`;
  const res = mockRes();
  loginHandlers(auth)["GET /login"](mockReq({ originalUrl: url, url, ...over }), res);
  return res;
}

function sessionIdFrom(res: any): string {
  const m = new RegExp(`${SESSION_COOKIE}=([^;]+)`).exec(res.headers["set-cookie"]);
  assert.ok(m, "Set-Cookie must carry the session cookie");
  return m![1];
}

test("resolveBindConfig no longer throws on a non-loopback bind and generates an access code", () => {
  const cfg = resolveBindConfig({ METALLIKSA_HOST: "0.0.0.0" });
  assert.equal(cfg.loopback, false);
  assert.equal(cfg.token, null);
  assert.match(cfg.accessCode ?? "", /^[A-Za-z0-9_-]{32}$/);
  assert.notEqual(resolveBindConfig({ METALLIKSA_HOST: "0.0.0.0" }).accessCode, cfg.accessCode);
  // Loopback and explicit-token configurations do not get an auto code.
  assert.equal(resolveBindConfig({}).accessCode, null);
  assert.equal(resolveBindConfig({ METALLIKSA_HOST: "0.0.0.0", METALLIKSA_TOKEN: "s3cret" }).accessCode, null);
  assert.equal(isLoopbackHost("0.0.0.0"), false);
});

test("buildLoginUrl shows wildcard binds as localhost and encodes the code", () => {
  assert.equal(buildLoginUrl("0.0.0.0", 3000, "a_b-c"), "http://localhost:3000/login?code=a_b-c");
  assert.equal(buildLoginUrl("192.168.1.5", 8080, "x y"), "http://192.168.1.5:8080/login?code=x%20y");
});

test("/login with the right code sets a hardened cookie, redirects and invalidates the auto code", () => {
  const auth = new LoginAuth({ accessCode: "AUTOCODE" });
  const res = login(auth, "AUTOCODE");
  assert.equal(res.statusCode, 303);
  assert.equal(res.headers.location, "/");
  const cookie = res.headers["set-cookie"];
  assert.match(cookie, /HttpOnly/);
  assert.match(cookie, /SameSite=Strict/);
  assert.match(cookie, /Path=\//);
  assert.match(cookie, /Max-Age=43200/);
  assert.ok(!/Secure/.test(cookie), "no Secure flag on plain http");
  assert.ok(auth.isValidSession(sessionIdFrom(res)));
  // The auto code is single use.
  assert.equal(login(auth, "AUTOCODE").statusCode, 401);
});

test("/login adds Secure on https and accepts METALLIKSA_TOKEN repeatedly", () => {
  const auth = new LoginAuth({ token: "s3cret" });
  assert.match(login(auth, "s3cret", { secure: true }).headers["set-cookie"], /; Secure/);
  assert.equal(login(auth, "s3cret").statusCode, 303);
});

test("/login with a wrong or missing code returns a plain 401 without hints", () => {
  const auth = new LoginAuth({ accessCode: "AUTOCODE" });
  for (const code of ["nope", "", null]) {
    const res = login(auth, code);
    assert.equal(res.statusCode, 401);
    assert.equal(res.ended, "Login required");
    assert.equal(res.headers["set-cookie"], undefined);
  }
});

test("/login is rate limited per IP", () => {
  const auth = new LoginAuth({ accessCode: "AUTOCODE" });
  for (let i = 0; i < 10; i++) assert.equal(login(auth, "bad").statusCode, 401);
  const blocked = login(auth, "AUTOCODE");
  assert.equal(blocked.statusCode, 429);
  assert.equal(blocked.headers["set-cookie"], undefined);
  // Another IP is unaffected.
  assert.equal(login(auth, "AUTOCODE", { ip: "9.9.9.9" }).statusCode, 303);
});

test("a session cookie grants /api access; unknown and expired sessions do not", () => {
  let t = 1_000;
  const auth = new LoginAuth({ accessCode: "C", sessionTtlMs: 1000, now: () => t });
  const mw = tokenAuth(null, auth);
  const id = auth.createSession();
  const withCookie = (v: string) => mockReq({ headers: { cookie: `a=b; ${SESSION_COOKIE}=${v}; c=d` } });

  assert.equal(run(mw, withCookie(id), mockRes()), true);
  let res = mockRes();
  assert.equal(run(mw, withCookie("unknown"), res), false);
  assert.equal(res.statusCode, 401);
  assert.equal(res.body.code, "UNAUTHORIZED");
  res = mockRes();
  assert.equal(run(mw, mockReq(), res), false);
  assert.equal(res.statusCode, 401);

  t += 1001;
  res = mockRes();
  assert.equal(run(mw, withCookie(id), res), false);
  assert.equal(res.statusCode, 401);
});

test("case-variant /API paths are still protected; SPA shell and health stay reachable", () => {
  const auth = new LoginAuth({ accessCode: "C" });
  const mw = tokenAuth(null, auth);
  for (const p of ["/API/runtime-config", "/Api/consult"]) {
    const res = mockRes();
    assert.equal(run(mw, mockReq({ originalUrl: p, url: p }), res), false, p);
    assert.equal(res.statusCode, 401);
  }
  assert.equal(run(mw, mockReq({ originalUrl: "/", url: "/" }), mockRes()), true);
  assert.equal(run(mw, mockReq({ originalUrl: "/login?code=x", url: "/login?code=x" }), mockRes()), true);
  assert.equal(run(mw, mockReq({ originalUrl: "/api/health", url: "/api/health" }), mockRes()), true);
});

test("cookie-authenticated mutating requests need a same-origin Origin; Bearer is exempt", () => {
  const auth = new LoginAuth({ token: "s3cret", accessCode: null });
  const mw = tokenAuth("s3cret", auth);
  const id = auth.createSession();
  const post = (headers: Record<string, string>) =>
    mockReq({ method: "POST", headers: { host: "app.local:3000", cookie: `${SESSION_COOKIE}=${id}`, ...headers } });

  assert.equal(run(mw, post({ origin: "http://app.local:3000" }), mockRes()), true);

  for (const headers of [{ origin: "http://evil.example" }, { origin: "null" }, {}]) {
    const res = mockRes();
    assert.equal(run(mw, post(headers), res), false, JSON.stringify(headers));
    assert.equal(res.statusCode, 403);
    assert.equal(res.body.code, "CROSS_ORIGIN");
  }

  // GET with the cookie needs no Origin.
  assert.equal(run(mw, mockReq({ headers: { cookie: `${SESSION_COOKIE}=${id}` } }), mockRes()), true);

  // Bearer-authenticated mutating requests are exempt, even with a foreign Origin.
  const bearer = mockReq({ method: "DELETE", headers: { authorization: "Bearer s3cret", origin: "http://evil.example", host: "app.local:3000" } });
  assert.equal(run(mw, bearer, mockRes()), true);
});

test("POST /logout deletes the session and clears the cookie (same-origin only)", () => {
  const auth = new LoginAuth({ accessCode: "C" });
  const id = auth.createSession();
  const handler = loginHandlers(auth)["POST /logout"];
  const base = { method: "POST", headers: { host: "h:1", cookie: `${SESSION_COOKIE}=${id}` } };

  const foreign = mockRes();
  handler(mockReq({ ...base, headers: { ...base.headers, origin: "http://evil.example" } }), foreign);
  assert.equal(foreign.statusCode, 403);
  assert.ok(auth.isValidSession(id));

  const ok = mockRes();
  handler(mockReq({ ...base, headers: { ...base.headers, origin: "http://h:1" } }), ok);
  assert.equal(ok.statusCode, 200);
  assert.match(ok.headers["set-cookie"], /Max-Age=0/);
  assert.equal(auth.isValidSession(id), false);
});

test("the session store is bounded", () => {
  const auth = new LoginAuth({ maxSessions: 3 });
  const ids = [1, 2, 3, 4].map(() => auth.createSession());
  assert.equal(auth.isValidSession(ids[0]), false, "oldest session evicted");
  assert.equal(auth.isValidSession(ids[3]), true);
});

test("accessLog never prints the login code or the session cookie", () => {
  const lines: string[] = [];
  const req = mockReq({
    originalUrl: "/login?code=SUPERSECRETCODE",
    url: "/login?code=SUPERSECRETCODE",
    headers: { cookie: `${SESSION_COOKIE}=SESSIONVALUE123` },
  });
  const listeners: Record<string, () => void> = {};
  const res: any = { statusCode: 303, setHeader() {}, on(ev: string, cb: () => void) { listeners[ev] = cb; } };
  run(accessLog((l) => lines.push(l)), req, res);
  listeners.finish();
  assert.equal(lines.length, 1);
  assert.equal(JSON.parse(lines[0]).path, "/login");
  assert.ok(!lines[0].includes("SUPERSECRETCODE") && !lines[0].includes("SESSIONVALUE123"));
});

// ---------------------------------------------------------------------------
// One real HTTP round trip on an ephemeral port
// ---------------------------------------------------------------------------
function request(port: number, method: string, path: string, headers: Record<string, string> = {}) {
  return new Promise<{ status: number; headers: http.IncomingHttpHeaders; body: string }>((resolve, reject) => {
    const r = http.request({ host: "127.0.0.1", port, method, path, headers }, (res) => {
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () => resolve({ status: res.statusCode ?? 0, headers: res.headers, body }));
    });
    r.on("error", reject);
    r.end();
  });
}

test("real HTTP flow: login, cookie access, CSRF rejection, logout", async () => {
  const app = express();
  const auth = new LoginAuth({ accessCode: "REALCODE" });
  applySecurity(app, null, { log: () => {}, auth });
  app.get("/api/ping", (_req, res) => res.json({ ok: true }));
  app.post("/api/ping", (_req, res) => res.json({ ok: true }));
  app.get("/", (_req, res) => res.send("shell"));
  const server = http.createServer(app);
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const port = (server.address() as AddressInfo).port;
  const origin = `http://127.0.0.1:${port}`;
  try {
    assert.equal((await request(port, "GET", "/")).status, 200);
    assert.equal((await request(port, "GET", "/api/ping")).status, 401);
    assert.equal((await request(port, "GET", "/login?code=wrong")).status, 401);

    const ok = await request(port, "GET", "/login?code=REALCODE");
    assert.equal(ok.status, 303);
    assert.equal(ok.headers.location, "/");
    const setCookie = String(ok.headers["set-cookie"]);
    assert.match(setCookie, /HttpOnly/);
    assert.match(setCookie, /SameSite=Strict/);
    const cookie = setCookie.split(";")[0];

    assert.equal((await request(port, "GET", "/api/ping", { cookie })).status, 200);
    assert.equal((await request(port, "GET", "/API/ping", {})).status, 401);
    assert.equal((await request(port, "POST", "/api/ping", { cookie })).status, 403);
    assert.equal((await request(port, "POST", "/api/ping", { cookie, origin: "http://evil.example" })).status, 403);
    assert.equal((await request(port, "POST", "/api/ping", { cookie, origin })).status, 200);
    // The one-time code cannot be replayed.
    assert.equal((await request(port, "GET", "/login?code=REALCODE")).status, 401);

    assert.equal((await request(port, "POST", "/logout", { cookie, origin })).status, 200);
    assert.equal((await request(port, "GET", "/api/ping", { cookie })).status, 401);
  } finally {
    await new Promise<void>((r) => server.close(() => r()));
  }
});
