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
}

/** Resolve bind host and token. Throws when a non-loopback bind has no token. */
export function resolveBindConfig(env: Record<string, string | undefined>): BindConfig {
  const host = (env.METALLIKSA_HOST || "").trim() || "127.0.0.1";
  const token = (env.METALLIKSA_TOKEN || "").trim() || null;
  const loopback = isLoopbackHost(host);
  if (!loopback && !token) {
    throw new Error(
      `Refusing to bind to non-loopback host "${host}" without METALLIKSA_TOKEN. ` +
        `Set METALLIKSA_TOKEN to a strong secret or bind to 127.0.0.1.`,
    );
  }
  return { host, token, loopback };
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
 * True when the request is authenticated. With no token configured (loopback-only
 * default) every request is considered local and therefore authenticated.
 */
export function isAuthenticated(req: Request, token: string | null): boolean {
  if (!token) return true;
  return tokenMatches(token, req.headers.authorization);
}

export function tokenAuth(token: string | null) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!token) return next();
    const p = (req.originalUrl || req.url || "").split("?")[0];
    // Only API routes are protected; the SPA shell and /api/health stay reachable.
    if (!p.startsWith("/api/") || p === "/api/health") return next();
    if (isAuthenticated(req, token)) return next();
    res.setHeader("WWW-Authenticate", "Bearer");
    return res.status(401).json({ error: "Authentication required.", code: "UNAUTHORIZED", requestId: getRequestId(req) });
  };
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
    const p = (req.originalUrl || req.url || "").split("?")[0];
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
export function applySecurity(app: Express, token: string | null, opts: { log?: (line: string) => void; rate?: RateLimitOptions } = {}) {
  app.use(requestId);
  app.use(accessLog(opts.log));
  app.use(securityHeaders);
  app.use(rateLimit(opts.rate));
  app.use(tokenAuth(token));
}
