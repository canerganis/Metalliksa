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
  isSameOrigin,
  resolveBindConfig,
  resolveTrustProxy,
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

/** Capture the GET /login, POST /login and POST /logout handlers registered by installLogin. */
function loginHandlers(auth: LoginAuth) {
  const routes: Record<string, any> = {};
  const fakeApp: any = {
    get(path: string, h: any) { routes[`GET ${path}`] = h; },
    // POST /login registers body parsers before the handler; the handler is always last.
    post(path: string, ...hs: any[]) { routes[`POST ${path}`] = hs[hs.length - 1]; },
  };
  installLogin(fakeApp, auth);
  return routes;
}

/** POST /login with a parsed body (what the body parsers would produce). */
function login(auth: LoginAuth, code: string | null, over: Record<string, unknown> = {}) {
  const res = mockRes();
  const body = code === null ? {} : { code };
  loginHandlers(auth)["POST /login"](mockReq({ method: "POST", originalUrl: "/login", url: "/login", body, ...over }), res);
  return res;
}

/** GET /login?code=... (interstitial only; never creates a session). */
function getLogin(auth: LoginAuth, code: string | null, over: Record<string, unknown> = {}) {
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

test("POST /login with the right code sets a hardened cookie, redirects and invalidates the auto code", () => {
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

test("POST /login adds Secure on https and accepts METALLIKSA_TOKEN repeatedly", () => {
  const auth = new LoginAuth({ token: "s3cret" });
  assert.match(login(auth, "s3cret", { secure: true }).headers["set-cookie"], /; Secure/);
  assert.equal(login(auth, "s3cret").statusCode, 303);
});

test("POST /login with a wrong or missing code returns a plain 401 without hints", () => {
  const auth = new LoginAuth({ accessCode: "AUTOCODE" });
  for (const code of ["nope", "", null]) {
    const res = login(auth, code);
    assert.equal(res.statusCode, 401);
    assert.equal(res.ended, "Login required");
    assert.equal(res.headers["set-cookie"], undefined);
  }
});

test("/login (GET and POST) is rate limited per IP", () => {
  const auth = new LoginAuth({ accessCode: "AUTOCODE" });
  for (let i = 0; i < 5; i++) assert.equal(login(auth, "bad").statusCode, 401);
  for (let i = 0; i < 5; i++) assert.equal(getLogin(auth, "bad").statusCode, 401);
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
function request(port: number, method: string, path: string, headers: Record<string, string> = {}, body?: string) {
  return new Promise<{ status: number; headers: http.IncomingHttpHeaders; body: string }>((resolve, reject) => {
    const r = http.request({ host: "127.0.0.1", port, method, path, headers }, (res) => {
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () => resolve({ status: res.statusCode ?? 0, headers: res.headers, body }));
    });
    r.on("error", reject);
    r.end(body);
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

    // GET (and HEAD) only show the interstitial: the one-time code is not consumed.
    const page = await request(port, "GET", "/login?code=REALCODE");
    assert.equal(page.status, 200);
    assert.match(String(page.headers["content-type"]), /text\/html/);
    assert.equal(page.headers["set-cookie"], undefined);
    assert.match(page.body, /<form method="post" action="\/login">/);
    assert.match(page.body, /name="code" value="REALCODE"/);
    assert.equal((await request(port, "HEAD", "/login?code=REALCODE")).status, 200);
    assert.equal((await request(port, "OPTIONS", "/login")).headers["set-cookie"], undefined);

    const form = { "content-type": "application/x-www-form-urlencoded" };
    assert.equal((await request(port, "POST", "/login", form, "code=wrong")).status, 401);
    const ok = await request(port, "POST", "/login", form, "code=REALCODE");
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
    // The one-time code cannot be replayed, by GET or POST.
    assert.equal((await request(port, "GET", "/login?code=REALCODE")).status, 401);
    assert.equal((await request(port, "POST", "/login", form, "code=REALCODE")).status, 401);

    assert.equal((await request(port, "POST", "/logout", { cookie, origin })).status, 200);
    assert.equal((await request(port, "GET", "/api/ping", { cookie })).status, 401);
  } finally {
    await new Promise<void>((r) => server.close(() => r()));
  }
});

// ---------------------------------------------------------------------------
// Review follow-ups
// ---------------------------------------------------------------------------
test("GET /login serves an interstitial for the auto code and never consumes it", () => {
  const auth = new LoginAuth({ token: "s3cret", accessCode: "AUTO<\"&" });
  const page = getLogin(auth, "AUTO<\"&");
  assert.equal(page.statusCode, 200);
  assert.match(page.headers["content-type"], /text\/html/);
  assert.equal(page.headers["set-cookie"], undefined);
  assert.ok(page.ended.includes('value="AUTO&lt;&quot;&amp;"'), "code is HTML-escaped");
  assert.match(page.ended, />Sign in</);
  // Still usable after any number of GETs.
  getLogin(auth, "AUTO<\"&");
  assert.equal(auth.checkCode("AUTO<\"&"), "auto");
  assert.equal(login(auth, "AUTO<\"&").statusCode, 303);
  assert.equal(login(auth, "AUTO<\"&").statusCode, 401);
});

test("the static token is never accepted in a URL but works via POST (form or JSON)", () => {
  const auth = new LoginAuth({ token: "s3cret" });
  const get = getLogin(auth, "s3cret");
  assert.equal(get.statusCode, 401);
  assert.equal(get.headers["set-cookie"], undefined);
  const form = login(auth, "s3cret");
  assert.equal(form.statusCode, 303);
  const json = login(auth, "s3cret", { headers: { "content-type": "application/json" } });
  assert.equal(json.statusCode, 200);
  assert.equal(json.ended, '{"ok":true}');
  assert.ok(auth.isValidSession(sessionIdFrom(json)));
  // Non-string codes are rejected.
  assert.equal(login(auth, null, { body: { code: ["s3cret"] } }).statusCode, 401);
});

test("checkCode with token and auto code: the token never consumes the auto code", () => {
  const auth = new LoginAuth({ token: "s3cret", accessCode: "AUTOCODE" });
  assert.equal(auth.checkCode("s3cret"), "token");
  auth.consume("token");
  assert.equal(auth.checkCode("AUTOCODE"), "auto", "auto code survives token logins");
  assert.equal(auth.checkCode("s3cret"), "token");
  auth.consume("auto");
  assert.equal(auth.checkCode("AUTOCODE"), null);
  assert.equal(auth.checkCode("s3cret"), "token", "token is reusable");
});

test("session eviction drops expired sessions before live ones", () => {
  let t = 0;
  const auth = new LoginAuth({ maxSessions: 3, sessionTtlMs: 1000, now: () => t });
  const s1 = auth.createSession();
  t = 1;
  const s2 = auth.createSession();
  t = 2;
  const s3 = auth.createSession();
  t = 1001.5; // s1 and s2 expired, s3 live
  const s4 = auth.createSession();
  assert.equal((auth as any).sessions.size, 2, "both expired sessions purged, live one kept");
  assert.equal(auth.isValidSession(s1), false);
  assert.equal(auth.isValidSession(s2), false);
  assert.equal(auth.isValidSession(s3), true);
  assert.equal(auth.isValidSession(s4), true);
  // With only live sessions the oldest goes first.
  const s5 = auth.createSession();
  const s6 = auth.createSession();
  assert.equal(auth.isValidSession(s3), false);
  assert.equal(auth.isValidSession(s6), true);
  assert.equal(auth.isValidSession(s5), true);
});

test("same hostname with a different port is rejected; scheme is not compared without a proxy", () => {
  const req = (origin: string) => mockReq({ method: "POST", headers: { host: "app.local:3000", origin } });
  assert.equal(isSameOrigin(req("http://app.local:3000")), true);
  assert.equal(isSameOrigin(req("http://app.local:4000")), false);
  assert.equal(isSameOrigin(req("http://app.local")), false);
  assert.equal(isSameOrigin(req("https://app.local:3000")), true, "Host-only mode ignores the scheme");
});

test("PUT, PATCH and DELETE with a cookie and a foreign Origin are rejected; HEAD and OPTIONS need no Origin", () => {
  const auth = new LoginAuth({ accessCode: "C" });
  const mw = tokenAuth(null, auth);
  const id = auth.createSession();
  const headers = { host: "app.local:3000", cookie: `${SESSION_COOKIE}=${id}` };
  for (const method of ["PUT", "PATCH", "DELETE"]) {
    const res = mockRes();
    assert.equal(run(mw, mockReq({ method, headers: { ...headers, origin: "http://evil.example" } }), res), false, method);
    assert.equal(res.statusCode, 403);
    assert.equal(run(mw, mockReq({ method, headers }), mockRes()), false, `${method} without Origin`);
    assert.equal(run(mw, mockReq({ method, headers: { ...headers, origin: "http://app.local:3000" } }), mockRes()), true, `${method} same-origin`);
  }
  for (const method of ["HEAD", "OPTIONS", "GET"]) {
    assert.equal(run(mw, mockReq({ method, headers }), mockRes()), true, method);
  }
});

test("resolveTrustProxy accepts true, hop counts and subnet strings; unset is off", () => {
  const r = (v?: string) => resolveTrustProxy({ METALLIKSA_TRUST_PROXY: v });
  assert.equal(r(undefined), false);
  assert.equal(r(""), false);
  assert.equal(r("false"), false);
  assert.equal(r("0"), false);
  assert.equal(r("true"), true);
  assert.equal(r("2"), 2);
  assert.equal(r("loopback, 10.0.0.0/8"), "loopback, 10.0.0.0/8");
});

test("isSameOrigin honours X-Forwarded-Host and -Proto only when trust proxy is on", () => {
  const trusted = { get: (k: string) => (k === "trust proxy" ? true : undefined) };
  const untrusted = { get: () => false };
  const req = (app: unknown, headers: Record<string, string>) => mockReq({ method: "POST", app, headers: { host: "127.0.0.1:3000", ...headers } });
  const fwd = { "x-forwarded-host": "app.example.com, internal", "x-forwarded-proto": "https" };

  assert.equal(isSameOrigin(req(trusted, { ...fwd, origin: "https://app.example.com" })), true);
  assert.equal(isSameOrigin(req(untrusted, { ...fwd, origin: "https://app.example.com" })), false, "ignored when trust proxy is off");
  // Scheme is compared when X-Forwarded-Proto is present.
  assert.equal(isSameOrigin(req(trusted, { ...fwd, origin: "http://app.example.com" })), false);
  // Without X-Forwarded-Proto the scheme is not compared; without X-Forwarded-Host the Host header is used.
  assert.equal(isSameOrigin(req(trusted, { "x-forwarded-host": "app.example.com", origin: "http://app.example.com" })), true);
  assert.equal(isSameOrigin(req(trusted, { origin: "http://127.0.0.1:3000" })), true);
  // Still fails closed: foreign or missing Origin, wrong forwarded host.
  assert.equal(isSameOrigin(req(trusted, { ...fwd, origin: "https://evil.example" })), false);
  assert.equal(isSameOrigin(req(trusted, { ...fwd })), false);
  assert.equal(isSameOrigin(req(trusted, { ...fwd, origin: "https://127.0.0.1:3000" })), false, "Host is superseded by X-Forwarded-Host");
});

async function withServer(app: express.Express, fn: (port: number) => Promise<void>) {
  const server = http.createServer(app);
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  try {
    await fn((server.address() as AddressInfo).port);
  } finally {
    await new Promise<void>((r) => server.close(() => r()));
  }
}

test("loopback passthrough: applySecurity without auth leaves /api open and /login unregistered", async () => {
  const app = express();
  applySecurity(app, null, { log: () => {} });
  app.get("/api/ping", (_req, res) => res.json({ ok: true }));
  app.post("/api/ping", (_req, res) => res.json({ ok: true }));
  await withServer(app, async (port) => {
    assert.equal((await request(port, "GET", "/api/ping")).status, 200);
    assert.equal((await request(port, "POST", "/api/ping")).status, 200, "no Origin needed without login");
    assert.equal((await request(port, "GET", "/login?code=x")).status, 404);
    assert.equal((await request(port, "POST", "/login")).status, 404);
  });
});

test("real HTTP: Bearer and session cookie both authenticate; Bearer writes need no Origin", async () => {
  const app = express();
  const auth = new LoginAuth({ token: "s3cret" });
  applySecurity(app, "s3cret", { log: () => {}, auth });
  app.get("/api/ping", (_req, res) => res.json({ ok: true }));
  app.put("/api/ping", (_req, res) => res.json({ ok: true }));
  await withServer(app, async (port) => {
    const origin = `http://127.0.0.1:${port}`;
    const bearer = { authorization: "Bearer s3cret" };
    assert.equal((await request(port, "GET", "/api/ping", { authorization: "Bearer wrong" })).status, 401);
    assert.equal((await request(port, "GET", "/api/ping", bearer)).status, 200);
    assert.equal((await request(port, "PUT", "/api/ping", bearer)).status, 200);
    assert.equal((await request(port, "PUT", "/api/ping", { ...bearer, origin: "http://evil.example" })).status, 200);

    // The token in a URL does not log in; in a JSON body it does.
    assert.equal((await request(port, "GET", "/login?code=s3cret")).status, 401);
    const res = await request(port, "POST", "/login", { "content-type": "application/json" }, JSON.stringify({ code: "s3cret" }));
    assert.equal(res.status, 200);
    const cookie = String(res.headers["set-cookie"]).split(";")[0];
    assert.equal((await request(port, "GET", "/api/ping", { cookie })).status, 200);
    assert.equal((await request(port, "PUT", "/api/ping", { cookie })).status, 403);
    assert.equal((await request(port, "PUT", "/api/ping", { cookie, origin })).status, 200);
  });
});

test("real HTTP behind a TLS proxy: Secure cookie and forwarded-host same-origin need trust proxy", async () => {
  const build = (trust: boolean) => {
    const app = express();
    if (trust) app.set("trust proxy", true);
    applySecurity(app, null, { log: () => {}, auth: new LoginAuth({ accessCode: "C" }) });
    app.put("/api/ping", (_req, res) => res.json({ ok: true }));
    return app;
  };
  const form = { "content-type": "application/x-www-form-urlencoded", "x-forwarded-proto": "https", "x-forwarded-host": "app.example.com" };

  await withServer(build(true), async (port) => {
    const res = await request(port, "POST", "/login", form, "code=C");
    assert.equal(res.status, 303);
    assert.match(String(res.headers["set-cookie"]), /; Secure/);
    const cookie = String(res.headers["set-cookie"]).split(";")[0];
    const fwd = { cookie, "x-forwarded-proto": "https", "x-forwarded-host": "app.example.com" };
    assert.equal((await request(port, "PUT", "/api/ping", { ...fwd, origin: "https://app.example.com" })).status, 200);
    assert.equal((await request(port, "PUT", "/api/ping", { ...fwd, origin: "http://app.example.com" })).status, 403);
    assert.equal((await request(port, "PUT", "/api/ping", { ...fwd, origin: "https://evil.example" })).status, 403);
  });

  await withServer(build(false), async (port) => {
    const res = await request(port, "POST", "/login", form, "code=C");
    assert.equal(res.status, 303);
    assert.ok(!/Secure/.test(String(res.headers["set-cookie"])), "no Secure flag without trust proxy");
    const cookie = String(res.headers["set-cookie"]).split(";")[0];
    const fwd = { cookie, "x-forwarded-proto": "https", "x-forwarded-host": "app.example.com", origin: "https://app.example.com" };
    assert.equal((await request(port, "PUT", "/api/ping", fwd)).status, 403, "forwarded headers ignored by default");
  });
});
