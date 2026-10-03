import crypto from "node:crypto";
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

/** Login URL printed to the console. Wildcard binds are shown as localhost. */
export function buildLoginUrl(host: string, port: number, code: string): string {
  const h = host.trim();
  const wildcard = h === "0.0.0.0" || h === "::" || h === "[::]";
  const shown = wildcard ? "localhost" : h.includes(":") && !h.startsWith("[") ? `[${h}]` : h;
  return `http://${shown}:${port}/login?code=${encodeURIComponent(code)}`;
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

/** Same-origin check for cookie-authenticated mutating requests (CSRF defence). Missing Origin is rejected. */
export function isSameOrigin(req: Request): boolean {
  const origin = req.headers.origin;
  const host = req.headers.host;
  if (typeof origin !== "string" || !origin || typeof host !== "string" || !host) return false;
  try {
    return new URL(origin).host.toLowerCase() === host.toLowerCase();
  } catch {
    return false;
  }
}

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

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
        return res.status(403).json({ error: "Cross-origin request rejected.", code: "CROSS_ORIGIN", requestId: getRequestId(req) });
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
  /** Static METALLIKSA_TOKEN; also accepted as a login code. */
  token?: string | null;
  /** Auto-generated one-time code; invalidated after the first successful login. */
  accessCode?: string | null;
  sessionTtlMs?: number;
  maxSessions?: number;
  loginLimit?: number;
  loginWindowMs?: number;
  now?: () => number;
}

export class LoginAuth {
  private readonly token: string | null;
  private accessCode: string | null;
  private readonly ttlMs: number;
  private readonly maxSessions: number;
  private readonly loginLimit: number;
  private readonly loginWindowMs: number;
  private readonly now: () => number;
  private readonly sessions = new Map<string, number>();
  private readonly attempts = new Map<string, { count: number; resetAt: number }>();

  constructor(opts: LoginAuthOptions = {}) {
    this.token = opts.token || null;
    this.accessCode = opts.accessCode || null;
    this.ttlMs = opts.sessionTtlMs ?? 12 * 60 * 60 * 1000;
    this.maxSessions = opts.maxSessions ?? 1000;
    this.loginLimit = opts.loginLimit ?? 10;
    this.loginWindowMs = opts.loginWindowMs ?? 60_000;
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

  /** Fixed-window limiter for /login attempts. Returns true when the attempt is allowed. */
  allowLoginAttempt(ip: string): boolean {
    const t = this.now();
    if (this.attempts.size > 10_000) {
      for (const [k, b] of this.attempts) if (b.resetAt <= t) this.attempts.delete(k);
    }
    let b = this.attempts.get(ip);
    if (!b || b.resetAt <= t) {
      b = { count: 0, resetAt: t + this.loginWindowMs };
      this.attempts.set(ip, b);
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

function sendPlain(res: Response, status: number, body: string) {
  res.statusCode = status;
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  (res as any).end(body);
}

/** Register GET /login and POST /logout. Express matches paths case-insensitively. */
export function installLogin(app: Express, auth: LoginAuth) {
  app.get("/login", (req: Request, res: Response) => {
    const ip = req.ip || req.socket?.remoteAddress || "unknown";
    if (!auth.allowLoginAttempt(ip)) {
      res.setHeader("Retry-After", "60");
      return sendPlain(res, 429, "Too many login attempts. Try again later.");
    }
    let code: string | null = null;
    try {
      code = new URL(req.originalUrl || req.url || "", "http://localhost").searchParams.get("code");
    } catch {
      code = null;
    }
    const kind = auth.checkCode(code);
    if (!kind) return sendPlain(res, 401, "Login required");
    auth.consume(kind);
    const id = auth.createSession();
    res.setHeader("Set-Cookie", sessionCookie(req, id, auth.ttlSeconds));
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("Location", "/");
    res.statusCode = 303;
    (res as any).end();
  });

  app.post("/logout", (req: Request, res: Response) => {
    // A cookie-authenticated mutating request must be same-origin.
    if (!isSameOrigin(req)) {
      return res.status(403).json({ error: "Cross-origin request rejected.", code: "CROSS_ORIGIN" });
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
