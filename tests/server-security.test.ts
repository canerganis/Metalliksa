import test from "node:test";
import assert from "node:assert/strict";
import {
  accessLog,
  errorHandler,
  isLoopbackHost,
  rateLimit,
  requestId,
  resolveBindConfig,
  securityHeaders,
  tokenAuth,
  tokenMatches,
} from "../server/security.ts";

function mockRes() {
  const headers: Record<string, string> = {};
  const listeners: Record<string, () => void> = {};
  const res: any = {
    statusCode: 200,
    body: undefined,
    headersSent: false,
    setHeader(k: string, v: string) { headers[k.toLowerCase()] = v; return res; },
    status(code: number) { res.statusCode = code; return res; },
    json(b: unknown) { res.body = b; return res; },
    on(ev: string, cb: () => void) { listeners[ev] = cb; return res; },
    finish() { listeners.finish?.(); },
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

test("resolveBindConfig defaults to loopback and uses an access code on open bind without token", () => {
  assert.equal(resolveBindConfig({}).host, "127.0.0.1");
  assert.ok(resolveBindConfig({ METALLIKSA_HOST: "0.0.0.0" }).accessCode);
  const cfg = resolveBindConfig({ METALLIKSA_HOST: "0.0.0.0", METALLIKSA_TOKEN: "s3cret" });
  assert.equal(cfg.token, "s3cret");
  assert.equal(isLoopbackHost("localhost"), true);
  assert.equal(isLoopbackHost("192.168.1.5"), false);
});

test("requestId sets header and request property", () => {
  const req = mockReq(); const res = mockRes();
  assert.ok(run(requestId, req, res));
  assert.match(res.headers["x-request-id"], /^[0-9a-f-]{36}$/);
  assert.equal(req.requestId, res.headers["x-request-id"]);
});

test("securityHeaders sets headers without CSP", () => {
  const res = mockRes();
  run(securityHeaders, mockReq(), res);
  assert.equal(res.headers["x-content-type-options"], "nosniff");
  assert.equal(res.headers["x-frame-options"], "DENY");
  assert.ok(res.headers["referrer-policy"]);
  assert.equal(res.headers["content-security-policy"], undefined);
});

test("accessLog emits one JSON line without body or authorization", () => {
  const lines: string[] = [];
  const req = mockReq({ method: "POST", originalUrl: "/api/consult?secret=1", body: { prompt: "TOPSECRET" }, headers: { authorization: "Bearer abc" } });
  const res = mockRes();
  run(accessLog((l) => lines.push(l)), req, res);
  res.finish();
  assert.equal(lines.length, 1);
  const parsed = JSON.parse(lines[0]);
  assert.equal(parsed.path, "/api/consult");
  assert.equal(parsed.method, "POST");
  assert.ok(!lines[0].includes("TOPSECRET") && !lines[0].includes("abc"));
});

test("tokenAuth enforces Bearer on /api except health, and passes when unset", () => {
  const mw = tokenAuth("s3cret");
  let res = mockRes();
  assert.equal(run(mw, mockReq(), res), false);
  assert.equal(res.statusCode, 401);
  res = mockRes();
  assert.equal(run(mw, mockReq({ headers: { authorization: "Bearer wrong" } }), res), false);
  res = mockRes();
  assert.equal(run(mw, mockReq({ headers: { authorization: "Bearer s3cret" } }), res), true);
  assert.equal(run(mw, mockReq({ originalUrl: "/api/health" }), mockRes()), true);
  assert.equal(run(mw, mockReq({ originalUrl: "/index.html" }), mockRes()), true);
  assert.equal(run(tokenAuth(null), mockReq(), mockRes()), true);
  assert.equal(tokenMatches("a", "Bearer"), false);
  assert.equal(tokenMatches("a", undefined), false);
});

test("rateLimit applies stricter limit to AI routes and resets per window", () => {
  let now = 0;
  const mw = rateLimit({ now: () => now, aiLimit: 3, generalLimit: 5, windowMs: 1000 });
  const ai = () => { const r = mockRes(); const ok = run(mw, mockReq({ originalUrl: "/api/consult" }), r); return { ok, r }; };
  assert.ok(ai().ok && ai().ok && ai().ok);
  const blocked = ai();
  assert.equal(blocked.ok, false);
  assert.equal(blocked.r.statusCode, 429);
  assert.ok(blocked.r.headers["retry-after"]);
  // General bucket is independent.
  for (let i = 0; i < 5; i++) assert.ok(run(mw, mockReq(), mockRes()));
  assert.equal(run(mw, mockReq(), mockRes()), false);
  now = 1500;
  assert.ok(ai().ok);
  assert.ok(run(mw, mockReq(), mockRes()));
});

test("errorHandler hides 5xx details and includes request id", () => {
  const h = errorHandler(() => {});
  const res = mockRes();
  h(new Error("db password leaked"), mockReq({ requestId: "rid-1" }), res, () => {});
  assert.equal(res.statusCode, 500);
  assert.equal(res.body.requestId, "rid-1");
  assert.ok(!JSON.stringify(res.body).includes("leaked"));
  const res2 = mockRes();
  h(Object.assign(new Error("bad json"), { status: 400, expose: true }), mockReq({ requestId: "r2" }), res2, () => {});
  assert.equal(res2.statusCode, 400);
  assert.equal(res2.body.error, "bad json");
});

test("tokenAuth and rateLimit treat /api paths case-insensitively (Express routers do)", () => {
  const mw = tokenAuth("s3cret");
  for (const url of ["/API/orchestrator/collect-source", "/Api/Consult", "/api/Consult/"]) {
    const res = mockRes();
    assert.equal(run(mw, mockReq({ originalUrl: url }), res), false, url);
    assert.equal(res.statusCode, 401, url);
  }
  assert.equal(run(mw, mockReq({ originalUrl: "/API/health" }), mockRes()), true);

  const rl = rateLimit({ now: () => 0, aiLimit: 2, generalLimit: 100, windowMs: 1000 });
  const hit = (url: string) => run(rl, mockReq({ originalUrl: url }), mockRes());
  assert.ok(hit("/api/consult") && hit("/API/Consult"));
  assert.equal(hit("/Api/CONSULT"), false);
});
