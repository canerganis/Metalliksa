import crypto from "node:crypto";
import express from "express";
import type { Express, NextFunction, Request, Response } from "express";

// Small hand-rolled security middleware (no external dependencies).

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

export function isLoopbackHost(host: string): boolean {
  const h = host.trim().toLowerCase();
  return LOOPBACK_HOSTS.has(h) || /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(h);
}

export interface BindConfig {
  host: string;
  token: string | null;
  loopback: boolean;
  /** Random one-time login code, generated only for a non-loopback bind without METALLIKSA_TOKEN. */
  accessCode: string | null;
}

/**
 * Resolve bind host and token. A non-loopback bind without METALLIKSA_TOKEN is allowed: a random
 * access code is generated (memory only) and the caller prints a login URL for it.
 */
export function resolveBindConfig(env: Record<string, string | undefined>): BindConfig {
  const host = (env.METALLIKSA_HOST || "").trim() || "127.0.0.1";
  const token = (env.METALLIKSA_TOKEN || "").trim() || null;
  const loopback = isLoopbackHost(host);
  const accessCode = !loopback && !token ? crypto.randomBytes(24).toString("base64url") : null;
  return { host, token, loopback, accessCode };
}

/**
 * Parse METALLIKSA_TRUST_PROXY into an Express "trust proxy" value: "true", a hop count, or a
 * subnet/address string. Unset, empty, "false" and "0" mean off (false).
 */
export function resolveTrustProxy(env: Record<string, string | undefined>): boolean | number | string {
  const raw = (env.METALLIKSA_TRUST_PROXY || "").trim();
  if (!raw || raw.toLowerCase() === "false") return false;
  if (raw.toLowerCase() === "true") return true;
  if (/^\d+$/.test(raw)) return Number(raw) > 0 ? Number(raw) : false;
  return raw;
}

/** Login URL printed to the console. Wildcard binds are shown as localhost. */
export function buildLoginUrl(host: string, port: number, code: string): string {
  const h = host.trim();
  const wildcard = h === "0.0.0.0" || h === "::" || h === "[::]";
  const shown = wildcard ? "localhost" : h.includes(":") && !h.startsWith("[") ? `[${h}]` : h;
  return `http://${shown}:${port}/login?code=${encodeURIComponent(code)}`;
}

/** Startup console lines for the login mode. Token mode never prints the token or a URL containing it. */
export function buildLoginBannerLines(cfg: BindConfig, port: number): string[] {
  if (cfg.accessCode) {
    return [
      "Login required. Open this one-time link in your browser and press Sign in (valid until used or restart):",
      buildLoginUrl(cfg.host, port, cfg.accessCode),
    ];
  }
  if (cfg.token) {
    const loginUrl = buildLoginUrl(cfg.host, port, "").replace(/\?code=$/, "");
    return [
      `METALLIKSA_TOKEN is set: API clients send it as 'Authorization: Bearer <token>'; browsers sign in at ${loginUrl} by entering it in the form. It is never accepted in a URL.`,
    ];
  }
  return [];
}

// ---------------------------------------------------------------------------
// Request id
// ---------------------------------------------------------------------------
export function requestId(req: Request, res: Response, next: NextFunction) {
  const id = crypto.randomUUID();
  (req as any).requestId = id;
  res.setHeader("X-Request-Id", id);
  next();
}

export function getRequestId(req: Request): string | undefined {
  return (req as any).requestId;
}

// ---------------------------------------------------------------------------
// Access log: one JSON line per request. Never logs bodies, query strings or headers.
// ---------------------------------------------------------------------------
export function accessLog(write: (line: string) => void = (l) => console.log(l)) {
  return (req: Request, res: Response, next: NextFunction) => {
    const start = process.hrtime.bigint();
    res.on("finish", () => {
      const durationMs = Number(process.hrtime.bigint() - start) / 1e6;
      write(
        JSON.stringify({
          type: "access",
          requestId: getRequestId(req),
          method: req.method,
          path: (req.originalUrl || req.url || "").split("?")[0],
          status: res.statusCode,
          durationMs: Math.round(durationMs * 10) / 10,
          ip: req.ip,
        }),
      );
    });
    next();
  };
}

// ---------------------------------------------------------------------------
// Security headers (no CSP: it would break Vite HMR / inline dev scripts)
// ---------------------------------------------------------------------------
export function securityHeaders(_req: Request, res: Response, next: NextFunction) {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Referrer-Policy", "no-referrer");
  next();
}

// ---------------------------------------------------------------------------
// Bearer token auth
// ---------------------------------------------------------------------------
function digest(value: string): Buffer {
  return crypto.createHash("sha256").update(value).digest();
}

export function tokenMatches(expected: string, header: string | undefined): boolean {
  if (!header) return false;
  const m = /^Bearer\s+(.+)$/i.exec(header.trim());
  if (!m) return false;
  return crypto.timingSafeEqual(digest(expected), digest(m[1].trim()));
}

/**
 * True when the request is authenticated. With no token and no login configured (loopback-only
 * default) every request is considered local and therefore authenticated. A valid Bearer token or
 * a valid session cookie counts.
 */
export function isAuthenticated(req: Request, token: string | null, auth?: LoginAuth | null): boolean {
  if (!token && !auth) return true;
  return authMethod(req, token, auth) !== null;
}

function authMethod(req: Request, token: string | null, auth?: LoginAuth | null): "bearer" | "session" | null {
  if (token && tokenMatches(token, req.headers.authorization)) return "bearer";
  if (auth && auth.hasValidSession(req)) return "session";
  return null;
}

/**
 * True when the direct peer is a trusted proxy according to Express's compiled "trust proxy fn"
 * (so a subnet, loopback or hop-count setting only honours forwarded headers from trusted peers).
 */
function peerIsTrustedProxy(req: Request): boolean {
  const fn = (req as any).app?.get?.("trust proxy fn");
  const addr = (req as any).socket?.remoteAddress;
  if (typeof fn !== "function" || !addr) return false;
  try {
    return Boolean(fn(addr, 0));
  } catch {
    return false;
  }
}

/**
 * Same-origin check for cookie-authenticated mutating requests (CSRF defence). Compares scheme, host
 * and port of the Origin header against the effective request origin. Missing Origin is rejected.
 */
export function isSameOrigin(req: Request): boolean {
  const origin = req.headers.origin;
  let host: unknown = req.headers.host;
  let proto = (req as any).socket?.encrypted ? "https" : "http";
  if (peerIsTrustedProxy(req)) {
    const fwdHost = firstHeaderValue(req.headers["x-forwarded-host"]);
    if (fwdHost) host = fwdHost;
    const fwdProto = firstHeaderValue(req.headers["x-forwarded-proto"])?.toLowerCase();
    if (fwdProto === "http" || fwdProto === "https") proto = fwdProto;
  }
  if (typeof origin !== "string" || !origin || typeof host !== "string" || !host) return false;
  try {
    const o = new URL(origin);
    const effective = new URL(`${proto}://${host}`);
    return o.protocol === effective.protocol && o.host.toLowerCase() === effective.host.toLowerCase();
  } catch {
    return false;
  }
}

function firstHeaderValue(v: string | string[] | undefined): string | null {
  const s = Array.isArray(v) ? v[0] : v;
  if (typeof s !== "string") return null;
  const first = s.split(",")[0].trim();
  return first || null;
}

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

const TRUST_PROXY_HINT =
  "X-Forwarded-* headers were ignored; if this server runs behind a TLS reverse proxy, set METALLIKSA_TRUST_PROXY.";

/** Hint text when a request carries forwarded headers but trust proxy is off (common proxy misconfiguration). */
export function crossOriginHint(req: Request): string | null {
  const h = req.headers || {};
  if (h["x-forwarded-proto"] === undefined && h["x-forwarded-host"] === undefined) return null;
  const setting = (req as any).app?.get?.("trust proxy");
  return setting === undefined || setting === false ? TRUST_PROXY_HINT : null;
}

/** Startup warning for a network-exposed bind without trust proxy, or null when it does not apply. */
export function buildTrustProxyWarning(cfg: BindConfig, trustProxy: boolean | number | string): string | null {
  if (cfg.loopback || trustProxy !== false) return null;
  return (
    "METALLIKSA_TRUST_PROXY is not set. If a TLS-terminating reverse proxy fronts this server, browser sign-in and " +
    "cookie-authenticated API writes will be rejected with 403 (the proxy's https origin does not match the http request it forwards); " +
    "set METALLIKSA_TRUST_PROXY (true, a hop count or a proxy subnet) so X-Forwarded-Proto and X-Forwarded-Host are honoured."
  );
}

export function tokenAuth(token: string | null, auth?: LoginAuth | null) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!token && !auth) return next();
    const p = (req.originalUrl || req.url || "").split("?")[0].toLowerCase();
    // Only API routes are protected; the SPA shell, /login and /api/health stay reachable.
    if (!p.startsWith("/api/") || p === "/api/health") return next();
    const method = authMethod(req, token, auth);
    if (method === "bearer") return next();
    if (method === "session") {
      if (MUTATING_METHODS.has(String(req.method).toUpperCase()) && !isSameOrigin(req)) {
        const hint = crossOriginHint(req);
        return res.status(403).json({ error: "Cross-origin request rejected.", code: "CROSS_ORIGIN", ...(hint ? { hint } : {}), requestId: getRequestId(req) });
      }
      return next();
    }
    res.setHeader("WWW-Authenticate", "Bearer");
    return res.status(401).json({ error: "Authentication required.", code: "UNAUTHORIZED", requestId: getRequestId(req) });
  };
}

// ---------------------------------------------------------------------------
// Login (Jupyter-style): access code -> in-memory session cookie
// ---------------------------------------------------------------------------
export const SESSION_COOKIE = "metalliksa_session";

export interface LoginAuthOptions {
  /** Static METALLIKSA_TOKEN; accepted as a login code only via POST /login. */
  token?: string | null;
  /** Auto-generated one-time code; invalidated after the first successful login. */
  accessCode?: string | null;
  sessionTtlMs?: number;
  maxSessions?: number;
  loginLimit?: number;
  loginWindowMs?: number;
  /** Hard cap on tracked source addresses for the login limiter. */
  maxAttemptKeys?: number;
  now?: () => number;
}

export class LoginAuth {
  private readonly token: string | null;
  private accessCode: string | null;
  private readonly ttlMs: number;
  private readonly maxSessions: number;
  private readonly loginLimit: number;
  private readonly loginWindowMs: number;
  private readonly maxAttemptKeys: number;
  private readonly now: () => number;
  private readonly sessions = new Map<string, number>();
  private readonly attempts = new Map<string, { count: number; resetAt: number }>();
  private overflow: { count: number; resetAt: number } | null = null;

  constructor(opts: LoginAuthOptions = {}) {
    this.token = opts.token || null;
    this.accessCode = opts.accessCode || null;
    this.ttlMs = opts.sessionTtlMs ?? 12 * 60 * 60 * 1000;
    this.maxSessions = opts.maxSessions ?? 1000;
    this.loginLimit = opts.loginLimit ?? 10;
    this.loginWindowMs = opts.loginWindowMs ?? 60_000;
    this.maxAttemptKeys = opts.maxAttemptKeys ?? 5000;
    this.now = opts.now ?? Date.now;
  }

  get ttlSeconds(): number {
    return Math.floor(this.ttlMs / 1000);
  }

  /** Constant-time check against the token and the (still unused) auto code. */
  checkCode(candidate: string | null | undefined): "token" | "auto" | null {
    if (!candidate) return null;
    const d = digest(candidate);
    // Evaluate both comparisons so timing does not reveal which one matched.
    const tokenOk = this.token ? crypto.timingSafeEqual(d, digest(this.token)) : false;
    const autoOk = this.accessCode ? crypto.timingSafeEqual(d, digest(this.accessCode)) : false;
    if (tokenOk) return "token";
    if (autoOk) return "auto";
    return null;
  }

  /** Called after a successful login: auto codes are single use, the static token is not. */
  consume(kind: "token" | "auto") {
    if (kind === "auto") this.accessCode = null;
  }

  createSession(): string {
    const id = crypto.randomBytes(32).toString("base64url");
    const t = this.now();
    if (this.sessions.size >= this.maxSessions) {
      for (const [k, exp] of this.sessions) if (exp <= t) this.sessions.delete(k);
      while (this.sessions.size >= this.maxSessions) {
        const oldest = this.sessions.keys().next().value;
        if (oldest === undefined) break;
        this.sessions.delete(oldest);
      }
    }
    this.sessions.set(digestHex(id), t + this.ttlMs);
    return id;
  }

  isValidSession(id: string | null | undefined): boolean {
    if (!id) return false;
    const key = digestHex(id);
    const exp = this.sessions.get(key);
    if (exp === undefined) return false;
    if (exp <= this.now()) {
      this.sessions.delete(key);
      return false;
    }
    return true;
  }

  deleteSession(id: string | null | undefined) {
    if (id) this.sessions.delete(digestHex(id));
  }

  hasValidSession(req: Request): boolean {
    return this.isValidSession(readCookie(req.headers.cookie, SESSION_COOKIE));
  }

  /**
   * Fixed-window limiter for /login attempts. Returns true when the attempt is allowed. Buckets are kept
   * in window-start order (Map insertion order), so expired ones sit at the front and cleanup is bounded.
   * A live bucket is never evicted: when the map is full of live buckets, unknown addresses share one
   * overflow bucket with the same limit, so enforcement fails closed under key churn.
   */
  allowLoginAttempt(ip: string): boolean {
    const t = this.now();
    let b = this.attempts.get(ip);
    if (!b || b.resetAt <= t) {
      this.attempts.delete(ip);
      for (const [k, old] of this.attempts) {
        if (old.resetAt > t) break;
        this.attempts.delete(k);
      }
      if (this.attempts.size >= this.maxAttemptKeys) {
        if (!this.overflow || this.overflow.resetAt <= t) this.overflow = { count: 0, resetAt: t + this.loginWindowMs };
        b = this.overflow;
      } else {
        b = { count: 0, resetAt: t + this.loginWindowMs };
        this.attempts.set(ip, b);
      }
    }
    b.count += 1;
    return b.count <= this.loginLimit;
  }
}

function digestHex(value: string): string {
  return crypto.createHash("sha256").update(value).digest("hex");
}

export function readCookie(header: string | undefined, name: string): string | null {
  if (!header) return null;
  for (const part of header.split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    if (part.slice(0, i).trim() === name) return part.slice(i + 1).trim() || null;
  }
  return null;
}

function sessionCookie(req: Request, value: string, maxAgeSeconds: number): string {
  const secure = (req as any).secure ? "; Secure" : "";
  return `${SESSION_COOKIE}=${value}; HttpOnly; SameSite=Strict; Path=/; Max-Age=${maxAgeSeconds}${secure}`;
}

/**
 * Referrer policy for /login and /logout. Not "no-referrer": under that policy browsers serialise the
 * Origin of a same-origin form POST as the literal "null", so the sign-in form could never pass the
 * Origin check (Phase 2 defect D1). "strict-origin" still makes browsers send the real Origin but never the
 * path or query, so the one-time code in the URL cannot leak through Referer (same-site or off-site).
 */
export const LOGIN_REFERRER_POLICY = "strict-origin";

/**
 * Browser proof for an "Origin: null" request: Sec-Fetch-Site is a forbidden header that only the
 * browser can set, so "null" plus Sec-Fetch-Site "same-origin" is a same-origin navigation whose Origin
 * was hidden by a referrer policy. Non-browser clients sending "null" without it are not trusted.
 */
export function isNullOriginSameOriginFetch(req: Request): boolean {
  return req.headers.origin === "null" && firstHeaderValue(req.headers["sec-fetch-site"])?.toLowerCase() === "same-origin";
}

/** Sec-Fetch-Site values a browser sets for a request initiated by another origin's page. */
function isCrossSiteFetch(req: Request): boolean {
  const site = firstHeaderValue(req.headers["sec-fetch-site"])?.toLowerCase();
  return site === "cross-site" || site === "same-site";
}

function loginHeaders(res: Response, contentType: string) {
  res.setHeader("Content-Type", contentType);
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Referrer-Policy", LOGIN_REFERRER_POLICY);
}

function sendPlain(res: Response, status: number, body: string) {
  res.statusCode = status;
  loginHeaders(res, "text/plain; charset=utf-8");
  (res as any).end(body);
}

function sendHtml(res: Response, status: number, body: string) {
  res.statusCode = status;
  loginHeaders(res, "text/html; charset=utf-8");
  (res as any).end(body);
}

function escapeHtml(v: string): string {
  return v.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

const PAGE_HEAD =
  '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<meta name="referrer" content="' + LOGIN_REFERRER_POLICY + '"><title>Sign in</title></head><body><main><h1>Sign in</h1>';

/** One-time link interstitial: carries the auto code only in a hidden POST field. */
function loginPage(code: string): string {
  return (
    PAGE_HEAD +
    '<form method="post" action="/login"><input type="hidden" name="code" value="' + escapeHtml(code) + '">' +
    '<button type="submit">Sign in</button></form></main></body></html>'
  );
}

/** Manual sign-in form. Never echoes a submitted code. */
function loginFormPage(error?: string): string {
  return (
    PAGE_HEAD +
    (error ? '<p role="alert">' + escapeHtml(error) + "</p>" : "") +
    '<form method="post" action="/login"><label for="code">Access code or token</label> ' +
    '<input id="code" name="code" type="password" autocomplete="off" required> ' +
    '<button type="submit">Sign in</button></form></main></body></html>'
  );
}

function loginIp(req: Request): string {
  return req.ip || req.socket?.remoteAddress || "unknown";
}

/**
 * Register GET/HEAD /login, POST /login and POST /logout. Express matches paths case-insensitively.
 * GET /login without a code shows a sign-in form. GET /login?code= has no side effect: for the
 * auto-generated code it returns a tiny page with a POST form, so link previews and prefetchers cannot
 * burn the one-time code. HEAD never consumes anything. The static METALLIKSA_TOKEN is accepted only by
 * POST /login (form or JSON body), never in a URL. Every /login response is no-store and carries
 * LOGIN_REFERRER_POLICY.
 */
export function installLogin(app: Express, auth: LoginAuth) {
  // Runs before body parsing so parser failures (400/413) also carry the privacy headers.
  app.use(["/login", "/logout"], (_req: Request, res: Response, next: NextFunction) => {
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("Referrer-Policy", LOGIN_REFERRER_POLICY);
    next();
  });

  // Registered before GET so Express 4 does not dispatch HEAD to the GET handler.
  app.head("/login", (_req: Request, res: Response) => {
    res.statusCode = 200;
    loginHeaders(res, "text/html; charset=utf-8");
    (res as any).end();
  });

  app.get("/login", (req: Request, res: Response) => {
    let code: string | null = null;
    try {
      code = new URL(req.originalUrl || req.url || "", "http://localhost").searchParams.get("code");
    } catch {
      code = null;
    }
    // Plain visits (no code) are free; only code guesses count against the limiter.
    if (code) {
      if (!auth.allowLoginAttempt(loginIp(req))) {
        res.setHeader("Retry-After", "60");
        return sendPlain(res, 429, "Too many login attempts. Try again later.");
      }
      // Only the auto code is honoured in a URL; the static token never is.
      if (auth.checkCode(code) === "auto") return sendHtml(res, 200, loginPage(code));
    }
    return sendHtml(res, 200, loginFormPage());
  });

  app.post("/login", express.urlencoded({ extended: false, limit: "4kb" }), express.json({ limit: "4kb" }), (req: Request, res: Response) => {
    // Browsers always send Origin on cross-site form posts; reject when present and not same-origin
    // (a browser-proven same-origin "null" Origin is accepted), and whenever the browser itself
    // reports a cross-site or same-site initiator. Non-browser clients without Origin still work.
    if ((req.headers.origin !== undefined && !isSameOrigin(req) && !isNullOriginSameOriginFetch(req)) || isCrossSiteFetch(req)) {
      const hint = crossOriginHint(req);
      return sendPlain(res, 403, "Cross-origin request rejected." + (hint ? " " + hint : ""));
    }
    if (!auth.allowLoginAttempt(loginIp(req))) {
      res.setHeader("Retry-After", "60");
      return sendPlain(res, 429, "Too many login attempts. Try again later.");
    }
    const json = /^application\/json/i.test(String(req.headers["content-type"] || ""));
    const raw = (req as any).body?.code;
    const code = typeof raw === "string" ? raw : null;
    const kind = auth.checkCode(code);
    if (!kind) return json ? sendPlain(res, 401, "Login required") : sendHtml(res, 401, loginFormPage("Login required: the code was not accepted."));
    auth.consume(kind);
    const id = auth.createSession();
    res.setHeader("Set-Cookie", sessionCookie(req, id, auth.ttlSeconds));
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("Referrer-Policy", LOGIN_REFERRER_POLICY);
    if (json) {
      res.statusCode = 200;
      res.setHeader("Content-Type", "application/json; charset=utf-8");
      (res as any).end(JSON.stringify({ ok: true }));
      return;
    }
    res.setHeader("Location", "/");
    res.statusCode = 303;
    (res as any).end();
  });

  app.post("/logout", (req: Request, res: Response) => {
    // A cookie-authenticated mutating request must be same-origin (or a browser-proven same-origin
    // "null" Origin); a missing Origin is still rejected.
    if ((!isSameOrigin(req) && !isNullOriginSameOriginFetch(req)) || isCrossSiteFetch(req)) {
      const hint = crossOriginHint(req);
      return res.status(403).json({ error: "Cross-origin request rejected.", code: "CROSS_ORIGIN", ...(hint ? { hint } : {}) });
    }
    auth.deleteSession(readCookie(req.headers.cookie, SESSION_COOKIE));
    res.setHeader("Set-Cookie", sessionCookie(req, "", 0));
    res.status(200).json({ ok: true });
  });
}

// ---------------------------------------------------------------------------
// Fixed-window in-memory rate limit
// ---------------------------------------------------------------------------
const AI_ROUTE_PATTERN = /^\/api\/(metallurgy\/(consult|diagnose-micrograph)|consult|orchestrator\/(dataset-plan|collect-source))\/?$/;

export interface RateLimitOptions {
  windowMs?: number;
  aiLimit?: number;
  generalLimit?: number;
  now?: () => number;
}

export function rateLimit(opts: RateLimitOptions = {}) {
  const windowMs = opts.windowMs ?? 60_000;
  const aiLimit = opts.aiLimit ?? 10;
  const generalLimit = opts.generalLimit ?? 300;
  const now = opts.now ?? Date.now;
  const buckets = new Map<string, { count: number; resetAt: number }>();

  return (req: Request, res: Response, next: NextFunction) => {
    const p = (req.originalUrl || req.url || "").split("?")[0].toLowerCase();
    if (!p.startsWith("/api/")) return next();
    const ai = AI_ROUTE_PATTERN.test(p);
    const limit = ai ? aiLimit : generalLimit;
    const key = `${ai ? "ai" : "gen"}:${req.ip || req.socket?.remoteAddress || "unknown"}`;
    const t = now();

    if (buckets.size > 10_000) {
      for (const [k, b] of buckets) if (b.resetAt <= t) buckets.delete(k);
    }

    let bucket = buckets.get(key);
    if (!bucket || bucket.resetAt <= t) {
      bucket = { count: 0, resetAt: t + windowMs };
      buckets.set(key, bucket);
    }
    bucket.count += 1;
    if (bucket.count > limit) {
      res.setHeader("Retry-After", String(Math.max(1, Math.ceil((bucket.resetAt - t) / 1000))));
      return res.status(429).json({ error: "Too many requests.", code: "RATE_LIMITED", requestId: getRequestId(req) });
    }
    next();
  };
}

// ---------------------------------------------------------------------------
// Error handler: generic message for 5xx, request id always included
// ---------------------------------------------------------------------------
export function errorHandler(log: (...args: unknown[]) => void = console.error) {
  return (err: any, req: Request, res: Response, _next: NextFunction) => {
    const rid = getRequestId(req);
    log(`[ServerError] requestId=${rid} Unhandled Express pipeline error:`, err?.stack || err);
    if (res.headersSent) return;
    const rawStatus = Number(err?.status ?? err?.statusCode);
    const status = Number.isInteger(rawStatus) && rawStatus >= 400 && rawStatus <= 599 ? rawStatus : 500;
    if (status >= 500) {
      return res.status(status).json({ error: "An internal server error occurred.", code: "INTERNAL_SERVER_ERROR", requestId: rid });
    }
    return res.status(status).json({
      error: err?.expose ? String(err.message) : "Bad request.",
      code: err?.code || "BAD_REQUEST",
      requestId: rid,
    });
  };
}

// ---------------------------------------------------------------------------
// Small validation helpers
// ---------------------------------------------------------------------------
export function isStringWithin(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length <= max;
}

export function isOwnKey(obj: object, key: unknown): key is string {
  return typeof key === "string" && Object.prototype.hasOwnProperty.call(obj, key);
}

/**
 * Install the pre-route security stack. Used by server.ts and by route tests so both
 * exercise the same middleware order.
 */
export function applySecurity(
  app: Express,
  token: string | null,
  opts: { log?: (line: string) => void; rate?: RateLimitOptions; auth?: LoginAuth | null } = {},
) {
  app.use(requestId);
  app.use(accessLog(opts.log));
  app.use(securityHeaders);
  app.use(rateLimit(opts.rate));
  if (opts.auth) installLogin(app, opts.auth);
  app.use(tokenAuth(token, opts.auth));
}
