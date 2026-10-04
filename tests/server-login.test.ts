import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import type { AddressInfo } from "node:net";
import express from "express";
import {
  LOGIN_REFERRER_POLICY,
  LoginAuth,
  buildLoginBannerLines,
  SESSION_COOKIE,
  accessLog,
  applySecurity,
  buildLoginUrl,
  buildTrustProxyWarning,
  errorHandler,
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
    use() {},
    get(path: string, h: any) { routes[`GET ${path}`] = h; },
    head(path: string, h: any) { routes[`HEAD ${path}`] = h; },
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

test("POST /login with a wrong or missing code returns 401 with the form again and no echo or hints", () => {
  const auth = new LoginAuth({ accessCode: "AUTOCODE" });
  for (const code of ["nope", "", null]) {
    const res = login(auth, code);
    assert.equal(res.statusCode, 401);
    assert.match(res.headers["content-type"], /text\/html/);
    assert.match(res.ended, /Login required/);
    assert.match(res.ended, /type="password"/);
    assert.ok(!res.ended.includes("nope") && !res.ended.includes("AUTOCODE"));
    assert.equal(res.headers["set-cookie"], undefined);
  }
});

test("/login (GET and POST) is rate limited per IP", () => {
  const auth = new LoginAuth({ accessCode: "AUTOCODE" });
  for (let i = 0; i < 5; i++) assert.equal(login(auth, "bad").statusCode, 401);
  for (let i = 0; i < 5; i++) assert.equal(getLogin(auth, "bad").statusCode, 200, "a wrong code in a URL only re-shows the form");
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
    assert.equal((await request(port, "GET", "/login?code=wrong")).status, 200);

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
    // A cross-origin form post is rejected before the code is even checked.
    assert.equal((await request(port, "POST", "/login", { ...form, origin: "http://evil.example" }, "code=REALCODE")).status, 403);
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
    const replay = await request(port, "GET", "/login?code=REALCODE");
    assert.ok(!replay.body.includes("REALCODE"), "a spent code is not echoed");
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
  assert.equal(get.statusCode, 200);
  assert.ok(!get.ended.includes("s3cret"), "the token is never echoed into the page");
  assert.ok(!/type="hidden"/.test(get.ended));
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

test("same hostname with a different port or scheme is rejected without a proxy", () => {
  const req = (origin: string, socket: Record<string, unknown> = { remoteAddress: "10.0.0.9" }) =>
    mockReq({ method: "POST", app: express(), socket, headers: { host: "app.local:3000", origin } });
  assert.equal(isSameOrigin(req("http://app.local:3000")), true);
  assert.equal(isSameOrigin(req("http://app.local:4000")), false);
  assert.equal(isSameOrigin(req("http://app.local")), false);
  assert.equal(isSameOrigin(req("https://app.local:3000")), false, "plain-http socket: https Origin is foreign");
  assert.equal(isSameOrigin(req("https://app.local:3000", { remoteAddress: "10.0.0.9", encrypted: true })), true, "direct TLS");
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

function proxyApp(value: boolean | number | string) {
  const app = express();
  app.set("trust proxy", value);
  return app;
}

test("isSameOrigin honours X-Forwarded-Host and -Proto only from trusted peers", () => {
  const req = (app: unknown, headers: Record<string, string>, remoteAddress = "10.1.2.3") =>
    mockReq({ method: "POST", app, socket: { remoteAddress }, headers: { host: "127.0.0.1:3000", ...headers } });
  const fwd = { "x-forwarded-host": "app.example.com, internal", "x-forwarded-proto": "https" };
  const good = { ...fwd, origin: "https://app.example.com" };

  assert.equal(isSameOrigin(req(proxyApp(true), good)), true);
  assert.equal(isSameOrigin(req(express(), good)), false, "ignored when trust proxy is off");
  // Subnet / loopback / hop-count values only trust matching peers.
  assert.equal(isSameOrigin(req(proxyApp("10.0.0.0/8"), good, "10.9.9.9")), true);
  assert.equal(isSameOrigin(req(proxyApp("10.0.0.0/8"), good, "203.0.113.7")), false, "untrusted peer cannot forge the host");
  assert.equal(isSameOrigin(req(proxyApp("loopback"), good, "127.0.0.1")), true);
  assert.equal(isSameOrigin(req(proxyApp("loopback"), good, "198.51.100.4")), false);
  assert.equal(isSameOrigin(req(proxyApp(1), good, "198.51.100.4")), true, "hop count trusts the nearest hop");
  // Scheme is compared; without X-Forwarded-Proto the socket scheme (http) applies.
  assert.equal(isSameOrigin(req(proxyApp(true), { ...fwd, origin: "http://app.example.com" })), false);
  assert.equal(isSameOrigin(req(proxyApp(true), { "x-forwarded-host": "app.example.com", origin: "http://app.example.com" })), true);
  assert.equal(isSameOrigin(req(proxyApp(true), { "x-forwarded-host": "app.example.com", origin: "https://app.example.com" })), false);
  assert.equal(isSameOrigin(req(proxyApp(true), { origin: "http://127.0.0.1:3000" })), true);
  // Still fails closed.
  assert.equal(isSameOrigin(req(proxyApp(true), { ...fwd, origin: "https://evil.example" })), false);
  assert.equal(isSameOrigin(req(proxyApp(true), { ...fwd })), false);
  assert.equal(isSameOrigin(req(proxyApp(true), { ...fwd, origin: "https://127.0.0.1:3000" })), false, "Host is superseded by X-Forwarded-Host");
  assert.equal(isSameOrigin(mockReq({ method: "POST", headers: { host: "h", origin: "http://h" } })), true, "no app/socket falls back to Host and http");
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
    const urlTry = await request(port, "GET", "/login?code=s3cret");
    assert.equal(urlTry.headers["set-cookie"], undefined);
    assert.ok(!urlTry.body.includes("s3cret"));
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

// ---------------------------------------------------------------------------
// Second review round
// ---------------------------------------------------------------------------
test("GET /login without a code serves an accessible sign-in form with status 200 and no secrets", () => {
  const auth = new LoginAuth({ token: "s3cret" });
  const res = getLogin(auth, null);
  assert.equal(res.statusCode, 200);
  assert.match(res.headers["content-type"], /text\/html/);
  assert.match(res.ended, /<html lang="en">/);
  assert.match(res.ended, /<title>Sign in<\/title>/);
  assert.match(res.ended, /<label for="code">/);
  assert.match(res.ended, /<input id="code" name="code" type="password" autocomplete="off"/);
  assert.match(res.ended, /<form method="post" action="\/login">/);
  assert.match(res.ended, />Sign in<\/button>/);
  assert.equal(res.headers["set-cookie"], undefined);
});

// The login pages deliberately use LOGIN_REFERRER_POLICY ("same-origin") instead of "no-referrer":
// under "no-referrer" browsers send "Origin: null" on the same-origin sign-in form POST (Phase 2 D1).
test("every /login response is no-store and carries the login referrer policy (success, failure, throttled, GET, HEAD)", () => {
  const auth = new LoginAuth({ token: "s3cret", loginLimit: 3 });
  const check = (res: any, label: string) => {
    assert.equal(res.headers["cache-control"], "no-store", label);
    assert.equal(res.headers["referrer-policy"], LOGIN_REFERRER_POLICY, label);
  };
  check(login(auth, "s3cret"), "success form");
  check(login(auth, "s3cret", { headers: { "content-type": "application/json" }, ip: "5.5.5.5" }), "success json");
  check(login(auth, "bad"), "failure form");
  const jsonFail = login(auth, "bad", { headers: { "content-type": "application/json" } });
  check(jsonFail, "failure json");
  assert.equal(jsonFail.statusCode, 401);
  assert.equal(jsonFail.headers["content-type"], "text/plain; charset=utf-8", "JSON clients get a plain-text 401");
  assert.equal(jsonFail.ended, "Login required");
  const throttled = login(auth, "bad");
  assert.equal(throttled.statusCode, 429);
  check(throttled, "throttled");
  const plain = getLogin(auth, null);
  assert.equal(plain.statusCode, 200);
  check(plain, "get form");
  check(getLogin(auth, "x", { ip: "6.6.6.6" }), "get with code");
  check(login(auth, "s3cret", { headers: { origin: "http://evil.example", host: "h" }, ip: "7.7.7.7" }), "foreign origin");
  const head = mockRes();
  loginHandlers(auth)["HEAD /login"](mockReq({ method: "HEAD", originalUrl: "/login", url: "/login" }), head);
  check(head, "head");
});

test("plain GET /login visits are free; only requests carrying a code are rate limited", () => {
  const auth = new LoginAuth({ token: "s3cret", loginLimit: 3 });
  for (let i = 0; i < 20; i++) assert.equal(getLogin(auth, null).statusCode, 200, `plain visit ${i}`);
  const statuses = [1, 2, 3, 4, 5].map(() => getLogin(auth, "guess").statusCode);
  assert.deepEqual(statuses, [200, 200, 200, 429, 429]);
  // A throttled address can still load the plain form.
  assert.equal(getLogin(auth, null).statusCode, 200);
});

test("POST /login rejects a present foreign Origin with 403 and accepts same-origin or absent Origin", () => {
  const auth = new LoginAuth({ token: "s3cret" });
  const withOrigin = (origin: string) => login(auth, "s3cret", { headers: { host: "app.local:3000", origin } });
  assert.equal(withOrigin("http://evil.example").statusCode, 403);
  assert.equal(withOrigin("null").statusCode, 403);
  assert.equal(withOrigin("http://app.local:3000").statusCode, 303);
  assert.equal(login(auth, "s3cret").statusCode, 303, "non-browser clients without Origin still work");
  assert.equal(withOrigin("http://evil.example").headers["set-cookie"], undefined);
});

test("login attempt window resets after loginWindowMs", () => {
  let t = 0;
  const auth = new LoginAuth({ loginLimit: 2, loginWindowMs: 1000, now: () => t });
  assert.ok(auth.allowLoginAttempt("a") && auth.allowLoginAttempt("a"));
  assert.equal(auth.allowLoginAttempt("a"), false);
  t = 1000;
  assert.equal(auth.allowLoginAttempt("a"), true);
});

test("login attempt map is hard-capped; expired buckets are swept, live ones are never evicted", () => {
  let t = 0;
  const auth = new LoginAuth({ maxAttemptKeys: 50, loginWindowMs: 1000, now: () => t });
  const size = () => (auth as any).attempts.size;
  for (let i = 0; i < 500; i++) {
    auth.allowLoginAttempt(`ip-${i}`);
    assert.ok(size() <= 50);
  }
  assert.equal(size(), 50);
  assert.equal((auth as any).attempts.has("ip-0"), true, "live buckets are not evicted");
  assert.equal((auth as any).attempts.has("ip-499"), false, "unknown keys overflow into the shared bucket");
  t = 5000; // all expired: the next insert clears them in one bounded sweep
  auth.allowLoginAttempt("fresh");
  assert.equal(size(), 1);
});

test("an exhausted key cannot be reset through eviction churn; new keys work again after expiry", () => {
  let t = 0;
  const auth = new LoginAuth({ maxAttemptKeys: 5, loginLimit: 2, loginWindowMs: 1000, now: () => t });
  assert.ok(auth.allowLoginAttempt("A") && auth.allowLoginAttempt("A"));
  assert.equal(auth.allowLoginAttempt("A"), false);
  for (let i = 0; i < 100; i++) auth.allowLoginAttempt(`churn-${i}`);
  assert.equal(auth.allowLoginAttempt("A"), false, "A stays throttled after churn");
  assert.equal((auth as any).attempts.has("A"), true);
  // Unknown keys beyond the cap share one bucket and fail closed.
  assert.equal(auth.allowLoginAttempt("brand-new"), false);
  t = 1000; // window over: everything is swept and legitimate keys are served again
  assert.equal(auth.allowLoginAttempt("brand-new"), true);
  assert.equal(auth.allowLoginAttempt("A"), true);
});

test("HEAD /login never consumes the one-time code or creates a session; HEAD then GET then POST still works", async () => {
  const app = express();
  const auth = new LoginAuth({ accessCode: "ONCE" });
  applySecurity(app, null, { log: () => {}, auth });
  // Behaviour alone cannot tell the explicit HEAD handler from Express's GET fallback, so also inspect
  // the route stack: an explicit HEAD route must be registered and precede the GET route.
  const routes = (app as any)._router.stack.filter((l: any) => l.route?.path === "/login").map((l: any) => l.route);
  const headIdx = routes.findIndex((r: any) => r.methods.head === true);
  const getIdx = routes.findIndex((r: any) => r.methods.get === true);
  assert.ok(headIdx >= 0, "explicit HEAD /login handler registered");
  assert.ok(headIdx < getIdx, "HEAD handler registered before GET");
  await withServer(app, async (port) => {
    const head = await request(port, "HEAD", "/login?code=ONCE");
    assert.equal(head.status, 200);
    assert.equal(head.headers["set-cookie"], undefined);
    assert.equal(head.headers["cache-control"], "no-store");
    assert.equal(head.headers["referrer-policy"], LOGIN_REFERRER_POLICY);
    assert.equal(auth.checkCode("ONCE"), "auto");
    assert.equal((auth as any).sessions.size, 0);
    const get = await request(port, "GET", "/login?code=ONCE");
    assert.match(get.body, /name="code" value="ONCE"/);
    const form = { "content-type": "application/x-www-form-urlencoded" };
    assert.equal((await request(port, "POST", "/login", form, "code=ONCE")).status, 303);
    assert.equal(auth.checkCode("ONCE"), null);
  });
});

test("real HTTP wiring as in server.ts: static token via resolveBindConfig, form POST, no URL login", async () => {
  const cfg = resolveBindConfig({ METALLIKSA_HOST: "0.0.0.0", METALLIKSA_TOKEN: "static-tok" });
  const auth = new LoginAuth({ token: cfg.token, accessCode: cfg.accessCode });
  const app = express();
  applySecurity(app, cfg.token, { log: () => {}, auth });
  app.get("/api/ping", (_req, res) => res.json({ ok: true }));
  await withServer(app, async (port) => {
    const form = { "content-type": "application/x-www-form-urlencoded" };
    const page = await request(port, "GET", "/login");
    assert.equal(page.status, 200);
    assert.match(page.body, /type="password"/);
    assert.equal((await request(port, "POST", "/login", form, "code=wrong")).status, 401);
    const ok = await request(port, "POST", "/login", form, "code=static-tok");
    assert.equal(ok.status, 303);
    assert.equal((await request(port, "GET", "/api/ping", { cookie: String(ok.headers["set-cookie"]).split(";")[0] })).status, 200);
    assert.equal((await request(port, "GET", "/api/ping", { authorization: "Bearer static-tok" })).status, 200);
  });
});

test("Secure cookie follows X-Forwarded-Proto only from trusted peers (real headers over loopback)", async () => {
  const build = (trust: boolean | string) => {
    const app = express();
    app.set("trust proxy", trust);
    applySecurity(app, null, { log: () => {}, auth: new LoginAuth({ token: "t" }) });
    return app;
  };
  const form = { "content-type": "application/x-www-form-urlencoded", "x-forwarded-proto": "https" };
  for (const [trust, secure] of [["loopback", true], ["10.0.0.0/8", false], [false, false]] as const) {
    await withServer(build(trust), async (port) => {
      const res = await request(port, "POST", "/login", form, "code=t");
      assert.equal(res.status, 303);
      assert.equal(/; Secure/.test(String(res.headers["set-cookie"])), secure, `trust=${String(trust)}`);
    });
  }
});

test("cookie-authenticated POST/PUT/PATCH/DELETE vs missing, foreign and valid Origin over HTTP; HEAD/OPTIONS/GET need none", async () => {
  const app = express();
  const auth = new LoginAuth({ accessCode: "C" });
  applySecurity(app, null, { log: () => {}, auth });
  app.all("/api/ping", (_req, res) => res.json({ ok: true }));
  await withServer(app, async (port) => {
    const id = auth.createSession();
    const cookie = `${SESSION_COOKIE}=${id}`;
    const own = `http://127.0.0.1:${port}`;
    for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
      assert.equal((await request(port, method, "/api/ping", { cookie })).status, 403, `${method} missing Origin`);
      assert.equal((await request(port, method, "/api/ping", { cookie, origin: "http://evil.example" })).status, 403, `${method} foreign`);
      assert.equal((await request(port, method, "/api/ping", { cookie, origin: "null" })).status, 403, `${method} null`);
      assert.equal((await request(port, method, "/api/ping", { cookie, origin: own })).status, 200, `${method} valid`);
    }
    for (const method of ["GET", "HEAD", "OPTIONS"]) {
      assert.equal((await request(port, method, "/api/ping", { cookie })).status, 200, method);
    }
  });
});

test("startup banner: token mode never prints the token or a URL containing it; auto mode prints the one-time URL", () => {
  const tokenCfg = resolveBindConfig({ METALLIKSA_HOST: "0.0.0.0", METALLIKSA_TOKEN: "TOPSECRETTOKEN" });
  const tokenLines = buildLoginBannerLines(tokenCfg, 3000).join(" ");
  assert.ok(!tokenLines.includes("TOPSECRETTOKEN"));
  assert.ok(!/code=/.test(tokenLines));
  assert.match(tokenLines, /http:\/\/localhost:3000\/login(?!\?)/);

  const autoCfg = resolveBindConfig({ METALLIKSA_HOST: "0.0.0.0" });
  const autoLines = buildLoginBannerLines(autoCfg, 3000);
  assert.ok(autoLines.includes(buildLoginUrl("0.0.0.0", 3000, autoCfg.accessCode!)));
  assert.deepEqual(buildLoginBannerLines(resolveBindConfig({}), 3000), []);
});

test("parser failures on /login and /logout carry no-store and the login referrer policy (malformed JSON 400, oversized body 413)", async () => {
  const app = express();
  applySecurity(app, null, { log: () => {}, auth: new LoginAuth({ token: "s3cret" }) });
  app.use(errorHandler(() => {}));
  await withServer(app, async (port) => {
    const json = { "content-type": "application/json" };
    const bad = await request(port, "POST", "/login", json, "{not json");
    assert.equal(bad.status, 400);
    assert.equal(bad.headers["cache-control"], "no-store");
    assert.equal(bad.headers["referrer-policy"], LOGIN_REFERRER_POLICY);
    assert.equal(bad.headers["set-cookie"], undefined);
    assert.equal(JSON.parse(bad.body).code, "BAD_REQUEST");

    const big = await request(port, "POST", "/login", json, JSON.stringify({ code: "x".repeat(8192) }));
    assert.equal(big.status, 413);
    assert.equal(big.headers["cache-control"], "no-store");
    assert.equal(big.headers["referrer-policy"], LOGIN_REFERRER_POLICY);

    const bigForm = await request(port, "POST", "/login", { "content-type": "application/x-www-form-urlencoded" }, "code=" + "x".repeat(8192));
    assert.equal(bigForm.status, 413);
    assert.equal(bigForm.headers["cache-control"], "no-store");

    const logout = await request(port, "POST", "/logout", { origin: `http://127.0.0.1:${port}` });
    assert.equal(logout.headers["cache-control"], "no-store");
  });
});

test("CROSS_ORIGIN 403 hints at METALLIKSA_TRUST_PROXY only when forwarded headers arrive with trust proxy off", async () => {
  const build = (trust: boolean) => {
    const app = express();
    if (trust) app.set("trust proxy", true);
    const auth = new LoginAuth({ accessCode: "C" });
    applySecurity(app, null, { log: () => {}, auth });
    app.put("/api/ping", (_req, res) => res.json({ ok: true }));
    return { app, auth };
  };
  const fwd = { "x-forwarded-proto": "https", "x-forwarded-host": "app.example.com", origin: "https://app.example.com" };

  const off = build(false);
  await withServer(off.app, async (port) => {
    const cookie = `${SESSION_COOKIE}=${off.auth.createSession()}`;
    const hinted = await request(port, "PUT", "/api/ping", { cookie, ...fwd });
    assert.equal(hinted.status, 403);
    const body = JSON.parse(hinted.body);
    assert.equal(body.code, "CROSS_ORIGIN");
    assert.match(body.hint, /METALLIKSA_TRUST_PROXY/);
    const plain = JSON.parse((await request(port, "PUT", "/api/ping", { cookie, origin: "http://evil.example" })).body);
    assert.equal(plain.code, "CROSS_ORIGIN");
    assert.equal(plain.hint, undefined, "no hint without forwarded headers");
    const form = await request(port, "POST", "/login", { "content-type": "application/x-www-form-urlencoded", ...fwd }, "code=C");
    assert.equal(form.status, 403);
    assert.match(form.body, /METALLIKSA_TRUST_PROXY/);
  });

  const on = build(true);
  await withServer(on.app, async (port) => {
    const cookie = `${SESSION_COOKIE}=${on.auth.createSession()}`;
    const res = await request(port, "PUT", "/api/ping", { cookie, ...fwd, origin: "https://evil.example" });
    assert.equal(res.status, 403);
    assert.equal(JSON.parse(res.body).hint, undefined, "trust proxy is on, so the hint would mislead");
  });
});

test("buildTrustProxyWarning fires only for a non-loopback bind with trust proxy off", () => {
  const exposed = resolveBindConfig({ METALLIKSA_HOST: "0.0.0.0", METALLIKSA_TOKEN: "t" });
  const warning = buildTrustProxyWarning(exposed, false);
  assert.ok(warning);
  assert.match(warning!, /METALLIKSA_TRUST_PROXY/);
  assert.match(warning!, /403/);
  assert.ok(!warning!.includes("t\""));
  assert.equal(buildTrustProxyWarning(exposed, true), null);
  assert.equal(buildTrustProxyWarning(exposed, 1), null);
  assert.equal(buildTrustProxyWarning(exposed, "10.0.0.0/8"), null);
  assert.equal(buildTrustProxyWarning(resolveBindConfig({}), false), null);
});

// ---------------------------------------------------------------------------
// Phase 2 D1: browser sign-in through the real form
// ---------------------------------------------------------------------------
/** Effective referrer policy of a served page: a <meta name="referrer"> overrides the response header. */
function effectiveReferrerPolicy(page: { headers: http.IncomingHttpHeaders; body: string }): string {
  const meta = /<meta name="referrer" content="([^"]+)">/.exec(page.body);
  return (meta ? meta[1] : String(page.headers["referrer-policy"] ?? "")).trim().toLowerCase();
}

/**
 * The Origin header a browser sends for a form-submission (non-CORS) POST, per the Fetch standard's
 * "serializing a request origin": the referrer policy of the submitting page decides whether the real
 * origin or the literal "null" is sent, even for a same-origin target.
 */
function browserFormPostOrigin(pageOrigin: string, targetOrigin: string, policy: string): string {
  const page = new URL(pageOrigin);
  const target = new URL(targetOrigin);
  const sameOrigin = page.origin === target.origin;
  const downgrade = page.protocol === "https:" && target.protocol === "http:";
  switch (policy) {
    case "no-referrer":
      return "null";
    case "same-origin":
      return sameOrigin ? page.origin : "null";
    case "no-referrer-when-downgrade":
    case "strict-origin":
    case "strict-origin-when-cross-origin":
    case "":
      return downgrade ? "null" : page.origin;
    default:
      return page.origin;
  }
}

test("D1 model: the old no-referrer login page made browsers send Origin null on the same-origin form POST", () => {
  assert.equal(browserFormPostOrigin("http://h:1", "http://h:1", "no-referrer"), "null");
  assert.equal(browserFormPostOrigin("http://h:1", "http://h:1", "same-origin"), "http://h:1");
  assert.equal(browserFormPostOrigin("http://evil.example", "http://h:1", "same-origin"), "null");
  assert.notEqual(LOGIN_REFERRER_POLICY, "no-referrer");
});

test("D1 real HTTP: sign-in through the served one-time-link form succeeds with the Origin a browser sends", async () => {
  const app = express();
  const auth = new LoginAuth({ accessCode: "FORMCODE" });
  applySecurity(app, null, { log: () => {}, auth });
  app.all("/api/ping", (_req, res) => res.json({ ok: true }));
  await withServer(app, async (port) => {
    const own = `http://127.0.0.1:${port}`;
    const page = await request(port, "GET", "/login?code=FORMCODE");
    assert.equal(page.status, 200);
    const policy = effectiveReferrerPolicy(page);
    assert.equal(policy, LOGIN_REFERRER_POLICY, "meta tag and header agree");
    assert.equal(String(page.headers["referrer-policy"]), LOGIN_REFERRER_POLICY);
    const origin = browserFormPostOrigin(own, own, policy);
    assert.equal(origin, own, "the browser sends the real origin, not null");
    // Chromium on a loopback (potentially trustworthy) origin also sends fetch metadata.
    const headers = { "content-type": "application/x-www-form-urlencoded", origin, "sec-fetch-site": "same-origin", "sec-fetch-mode": "navigate" };
    const ok = await request(port, "POST", "/login", headers, "code=FORMCODE");
    assert.equal(ok.status, 303, ok.body);
    const cookie = String(ok.headers["set-cookie"]).split(";")[0];
    // After sign-in the SPA writes with fetch(), which is CORS mode and always sends the real Origin.
    assert.equal((await request(port, "POST", "/api/ping", { cookie, origin: own, "sec-fetch-site": "same-origin" })).status, 200);
    assert.equal((await request(port, "POST", "/api/ping", { cookie, origin: "null", "sec-fetch-site": "same-origin" })).status, 403, "API writes still need a real Origin");
    assert.equal((await request(port, "POST", "/logout", { cookie, origin: own, "sec-fetch-site": "same-origin" })).status, 200);
  });
});

test("D1 real HTTP: a plain-http LAN address (no fetch metadata) can sign in through the form", async () => {
  const app = express();
  const auth = new LoginAuth({ accessCode: "LANCODE" });
  applySecurity(app, null, { log: () => {}, auth });
  await withServer(app, async (port) => {
    // Browsers omit Sec-Fetch-* on non-trustworthy http origins, so the fix must not rely on them.
    const lan = `http://192.168.1.5:${port}`;
    const host = `192.168.1.5:${port}`;
    const page = await request(port, "GET", "/login?code=LANCODE", { host });
    const origin = browserFormPostOrigin(lan, lan, effectiveReferrerPolicy(page));
    assert.equal(origin, lan);
    const ok = await request(port, "POST", "/login", { host, "content-type": "application/x-www-form-urlencoded", origin }, "code=LANCODE");
    assert.equal(ok.status, 303, ok.body);
  });
});

test("D1 real HTTP: Origin null is accepted only with browser proof (Sec-Fetch-Site same-origin); cross-site stays rejected", async () => {
  const app = express();
  const auth = new LoginAuth({ token: "s3cret", loginLimit: 1000 });
  applySecurity(app, null, { log: () => {}, auth });
  await withServer(app, async (port) => {
    const form = { "content-type": "application/x-www-form-urlencoded" };
    const post = (headers: Record<string, string>) => request(port, "POST", "/login", { ...form, ...headers }, "code=s3cret");
    // A page still rendered under no-referrer (e.g. an older cached copy) sends null plus fetch metadata.
    assert.equal((await post({ origin: "null", "sec-fetch-site": "same-origin" })).status, 303);
    assert.equal((await post({ origin: "null" })).status, 403, "null without browser proof (non-browser client)");
    assert.equal((await post({ origin: "null", "sec-fetch-site": "cross-site" })).status, 403);
    assert.equal((await post({ origin: "null", "sec-fetch-site": "same-site" })).status, 403);
    assert.equal((await post({ origin: "http://evil.example", "sec-fetch-site": "cross-site" })).status, 403);
    assert.equal((await post({ origin: "http://evil.example" })).status, 403);
    assert.equal((await post({ "sec-fetch-site": "cross-site" })).status, 403, "browser-reported cross-site without Origin");
    const sameSite = await post({ origin: `http://127.0.0.1:${port}`, "sec-fetch-site": "same-site" });
    assert.equal(sameSite.status, 403);
    assert.equal(sameSite.headers["set-cookie"], undefined);
    assert.equal((await post({})).status, 303, "non-browser clients without Origin still work (existing contract)");

    const cookieFor = async () => String((await post({})).headers["set-cookie"]).split(";")[0];
    assert.equal((await request(port, "POST", "/logout", { cookie: await cookieFor() })).status, 403, "logout without Origin");
    assert.equal((await request(port, "POST", "/logout", { cookie: await cookieFor(), origin: "null" })).status, 403);
    assert.equal((await request(port, "POST", "/logout", { cookie: await cookieFor(), origin: "null", "sec-fetch-site": "cross-site" })).status, 403);
    assert.equal((await request(port, "POST", "/logout", { cookie: await cookieFor(), origin: "null", "sec-fetch-site": "same-origin" })).status, 200);
  });
});
