import path from "path";
import { PythonReadiness } from "./pythonStatus.ts";
import net from "net";
import http from "http";
import crypto from "crypto";
import { spawn, ChildProcess } from "child_process";
import { getHostPython, loadPythonEnvironment } from "./pythonRuntime.ts";

// =========================================================================
// IPC security helpers (python/persistent_ipc_service.py enforces the other side)
// Protocol metallix-ipc-v1: the per-spawn token never travels on the wire. Each request carries
// ts, nonce and HMAC-SHA256(token, request); each response carries HMAC-SHA256(token, nonce,
// status, body). A listener that is not our daemon learns nothing reusable and cannot forge a
// response we accept.
// =========================================================================

export const IPC_PROTOCOL = "metallix-ipc-v1";
const HEX64 = /^[0-9a-f]{64}$/;

/** Fresh per-spawn shared secret (64 hex chars); passed to the daemon via env, never argv. */
export function generateIpcToken(): string {
  return crypto.randomBytes(32).toString("hex");
}

export function ipcRequestMac(token: string, method: string, reqPath: string, ts: string, nonce: string, body: Buffer): string {
  return crypto.createHmac("sha256", token)
    .update(Buffer.from(`${IPC_PROTOCOL}\nreq\n${method}\n${reqPath}\n${ts}\n${nonce}\n`, "utf8"))
    .update(body)
    .digest("hex");
}

export function ipcResponseMac(token: string, nonce: string, status: number, body: Buffer): string {
  return crypto.createHmac("sha256", token)
    .update(Buffer.from(`${IPC_PROTOCOL}\nresp\n${nonce}\n${status}\n`, "utf8"))
    .update(body)
    .digest("hex");
}

export function signIpcRequest(token: string, method: string, reqPath: string, body: Buffer, now: number = Date.now()) {
  const ts = String(now);
  const nonce = crypto.randomBytes(16).toString("hex");
  return { ts, nonce, mac: ipcRequestMac(token, method, reqPath, ts, nonce, body) };
}

/** Constant-time check that a response really comes from the daemon holding our token. */
export function verifyIpcResponseMac(token: string, nonce: string, status: number, body: Buffer, mac: unknown): boolean {
  if (typeof mac !== "string" || !HEX64.test(mac)) return false;
  const expected = ipcResponseMac(token, nonce, status, body);
  return crypto.timingSafeEqual(Buffer.from(mac, "ascii"), Buffer.from(expected, "ascii"));
}

/** One UNIX-socket request frame (newline-terminated) and the nonce its response must echo. */
export function buildUnixFrame(token: string, request: unknown, now: number = Date.now()): { line: string; nonce: string } {
  const body = JSON.stringify(request);
  const { ts, nonce, mac } = signIpcRequest(token, "UNIX", "/", Buffer.from(body, "utf8"), now);
  return { line: JSON.stringify({ v: 1, ts, nonce, mac, body }) + "\n", nonce };
}

/**
 * Verifies a UNIX-socket response frame. Channel policy (same as HTTP): an unsigned or badly
 * signed frame, or any status >= 400, is a channel failure and the caller falls back.
 */
export function parseUnixResponse(token: string, nonce: string, line: string): any {
  let frame: any;
  try { frame = JSON.parse(line); } catch { throw new Error("UNIX socket IPC returned a malformed frame"); }
  const status = Number.isInteger(frame?.status) ? frame.status : NaN;
  if (typeof frame?.body !== "string" || !Number.isFinite(status)
    || !verifyIpcResponseMac(token, nonce, status, Buffer.from(frame.body, "utf8"), frame.mac)) {
    throw new Error(`UNIX socket IPC response is not signed by this server's daemon${Number.isFinite(status) ? ` (status ${status})` : ""}`);
  }
  if (status >= 400) {
    let code = "";
    try { code = String(JSON.parse(frame.body)?.code ?? ""); } catch { /* non-JSON error body */ }
    throw new Error(`UNIX socket IPC refused the request (status ${status}${code ? ` ${code}` : ""})`);
  }
  return JSON.parse(frame.body);
}

export function isLoopbackHost(host: string): boolean {
  const h = host.trim().toLowerCase().replace(/^\[|\]$/g, "");
  if (h === "localhost" || h === "::1" || h === "0:0:0:0:0:0:0:1") return true;
  return net.isIPv4(h) && h.split(".")[0] === "127";
}

/**
 * The daemon binds loopback unless METALLIX_IPC_ALLOW_REMOTE=1. A non-loopback
 * METALLIX_IPC_HOST without that override is replaced by 127.0.0.1 (loud warning).
 */
export function resolveIpcHost(
  env: Record<string, string | undefined>,
  warn: (message: string) => void = console.warn
): string {
  const requested = (env.METALLIX_IPC_HOST || "127.0.0.1").trim();
  if (isLoopbackHost(requested)) return requested;
  if (env.METALLIX_IPC_ALLOW_REMOTE === "1") {
    warn(`[Python-Supervisor] WARNING: IPC daemon bound to NON-LOOPBACK host ${requested} (METALLIX_IPC_ALLOW_REMOTE=1); HMAC-authenticated only.`);
    return requested;
  }
  warn(`[Python-Supervisor] WARNING: ignoring non-loopback METALLIX_IPC_HOST=${requested}; binding 127.0.0.1 (set METALLIX_IPC_ALLOW_REMOTE=1 to override).`);
  return "127.0.0.1";
}

/**
 * Spawn spec for the daemon: the token travels only in the child's environment. Port 0 (the
 * default) lets the daemon bind an ephemeral port; without a socket path the daemon creates a
 * private 0700 directory. Both actual addresses come back in its ready message.
 */
export function buildIpcSpawnSpec(
  python: { cmd: string; prefix: string[] },
  scriptPath: string,
  baseEnv: NodeJS.ProcessEnv,
  ipc: { socketPath?: string; port: number; host: string; token: string }
): { cmd: string; args: string[]; env: NodeJS.ProcessEnv } {
  const env: NodeJS.ProcessEnv = {
    ...baseEnv,
    METALLIX_IPC_PORT: String(ipc.port),
    METALLIX_IPC_HOST: ipc.host,
    METALLIX_IPC_TOKEN: ipc.token,
  };
  if (ipc.socketPath) env.METALLIX_IPC_SOCK = ipc.socketPath;
  else delete env.METALLIX_IPC_SOCK;
  return { cmd: python.cmd, args: [...python.prefix, scriptPath], env };
}

/** Only the fixed `python/<module>.py` form used by routes/*.ts is dispatched. */
const SCRIPT_REF = /^python\/[A-Za-z_][A-Za-z0-9_]*\.py$/;
export function assertDispatchableScript(scriptRelativePath: string): void {
  if (typeof scriptRelativePath !== "string" || !SCRIPT_REF.test(scriptRelativePath)) {
    throw new Error(`Refusing to dispatch Python script path ${JSON.stringify(scriptRelativePath)}; expected python/<module>.py`);
  }
}

function parsePort(value: string | undefined): number {
  const port = Number.parseInt(value ?? "0", 10);
  return Number.isInteger(port) && port >= 0 && port <= 65535 ? port : 0;
}

// Python Execution Result Interface
export interface PythonExecResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
  durationMs: number;
  warm?: boolean;
  channel?: "unix_socket" | "http_microservice" | "ad_hoc_fallback";
}

export interface IPCDaemonStatus {
  status: "online" | "restarting" | "initializing" | "fallback_mode";
  isPersistent: boolean;
  channels: {
    unixSocket: {
      path: string;
      active: boolean;
    };
    httpMicroservice: {
      url: string;
      active: boolean;
    };
  };
  requestsProcessed: number;
  avgLatencyMs: number;
  uptimeSeconds: number;
  warmModulesCount: number;
  warmModules: string[];
  pythonVersion: string | null;
  lastError: string | null;
}

// =========================================================================
// Persistent Python IPC Supervisor & Worker Daemon Manager
// Keeps Python scientific modules (CALPHAD, EIS, DFT, XRD, LPBF, etc.) warm in RAM
// =========================================================================
export class PersistentPythonIPCSupervisor {
  private child: ChildProcess | null = null;
  private isReady: boolean = false;
  private isRestarting: boolean = false;
  private restartAttempts: number = 0;
  private maxRestartAttempts: number = 10;
  // Requested addresses; the channels actually used come from the child's ready message.
  private configuredSocketPath: string | undefined;
  private configuredPort: number;
  private httpHost: string;
  private startTime: number = Date.now();
  private requestsHandled: number = 0;
  private totalDurationMs: number = 0;
  private readiness = new PythonReadiness();
  private lastError: string | null = null;
  // Regenerated on every spawn; never logged, put on the command line or sent on the wire.
  private ipcToken: string = generateIpcToken();

  constructor() {
    loadPythonEnvironment();
    this.configuredSocketPath = process.env.METALLIX_IPC_SOCK || undefined;
    this.configuredPort = parsePort(process.env.METALLIX_IPC_PORT);
    this.httpHost = resolveIpcHost(process.env);

    this.startWorker();
    this.registerCleanupHooks();
  }

  private startWorker() {
    if (this.child && !this.child.killed) {
      return;
    }

    console.log("[Python-Supervisor] Launching persistent Python IPC microservice daemon...");
    const scriptPath = path.join(process.cwd(), "python", "persistent_ipc_service.py");

    this.ipcToken = generateIpcToken();
    this.readiness.reset();
    const spec = buildIpcSpawnSpec(getHostPython(), scriptPath, process.env, {
      socketPath: this.configuredSocketPath,
      port: this.configuredPort,
      host: this.httpHost,
      token: this.ipcToken,
    });
    const child = spawn(spec.cmd, spec.args, {
      windowsHide: true,
      env: spec.env,
      stdio: ["ignore", "pipe", "pipe"],
    });
    this.child = child;

    // Readiness (and with it the channel addresses) is taken only from this spawn's own stdout.
    child.stdout?.on("data", (data) => {
      if (child !== this.child) return;
      if (this.readiness.consume(data.toString())) {
        this.isReady = this.readiness.ready;
        if (this.isReady) {
          this.isRestarting = false;
          this.restartAttempts = 0;
          this.lastError = null;
        }
        console.log(`[Python-Supervisor] Daemon ${this.isReady ? "ONLINE" : "UNAVAILABLE"}; ${this.readiness.warmModules.length} modules imported.`);
      }
    });

    child.stderr?.on("data", (data) => {
      const msg = data.toString().trim();
      if (msg.includes("[PersistentIPC]")) {
        console.log(msg);
      } else if (msg) {
        console.warn(`[Python-Worker stderr] ${msg}`);
      }
    });

    child.on("error", (err) => {
      console.error("[Python-Supervisor] Worker process error:", err);
      this.lastError = err.message;
      if (child === this.child) this.handleProcessExit();
    });

    child.on("exit", (code, signal) => {
      console.warn(`[Python-Supervisor] Persistent Python worker exited (code=${code}, signal=${signal})`);
      if (child === this.child) this.handleProcessExit();
    });
  }

  private handleProcessExit() {
    this.isReady = false;
    this.readiness.reset();
    this.child = null;

    if (!this.isRestarting && this.restartAttempts < this.maxRestartAttempts) {
      this.isRestarting = true;
      this.restartAttempts++;
      const delay = Math.min(1000 * Math.pow(1.5, this.restartAttempts), 10000);
      console.log(`[Python-Supervisor] Scheduling worker restart #${this.restartAttempts} in ${delay}ms...`);
      setTimeout(() => {
        this.isRestarting = false;
        this.startWorker();
      }, delay);
    }
  }

  private registerCleanupHooks() {
    const shutdown = () => {
      if (this.child && !this.child.killed) {
        console.log("[Python-Supervisor] Terminating persistent Python microservice worker...");
        this.child.kill("SIGTERM");
      }
    };

    process.on("SIGINT", shutdown);
    process.on("SIGTERM", shutdown);
    process.on("exit", shutdown);
  }

  /** The UNIX socket path, only when this server's own daemon announced an active socket. */
  private unixTarget(): string | null {
    return this.isReady && this.readiness.unixActive && this.readiness.unixSocketPath ? this.readiness.unixSocketPath : null;
  }

  /** The HTTP port, only when this server's own daemon announced an active HTTP listener. */
  private httpTarget(): number | null {
    return this.isReady && this.readiness.httpActive && this.readiness.httpPort ? this.readiness.httpPort : null;
  }

  /**
   * Dispatches script execution to the persistent Python daemon over UNIX domain socket
   */
  private executeViaUnixSocket(
    socketPath: string,
    script: string,
    payload: any,
    args: string[],
    timeoutMs: number
  ): Promise<PythonExecResult> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      const token = this.ipcToken;
      const socket = net.createConnection(socketPath);
      let buffer = "";
      let nonce = "";

      const timer = setTimeout(() => {
        socket.destroy();
        reject(new Error(`UNIX socket IPC timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      socket.on("connect", () => {
        const frame = buildUnixFrame(token, { action: "execute", script, payload, args, timeoutMs });
        nonce = frame.nonce;
        socket.write(frame.line);
      });

      socket.on("data", (chunk) => {
        buffer += chunk.toString();
        if (buffer.includes("\n")) {
          clearTimeout(timer);
          socket.end();

          const line = buffer.substring(0, buffer.indexOf("\n")).trim();
          try {
            const parsed = parseUnixResponse(token, nonce, line);
            const durationMs = Date.now() - startTime;
            resolve({
              stdout: parsed.stdout ?? "",
              stderr: parsed.stderr ?? "",
              exitCode: parsed.exitCode ?? 0,
              durationMs,
              warm: true,
              channel: "unix_socket",
            });
          } catch (e: any) {
            reject(e instanceof Error ? e : new Error(String(e)));
          }
        }
      });

      socket.on("error", (err) => {
        clearTimeout(timer);
        reject(err);
      });
    });
  }

  /**
   * HTTP loopback channel (port announced by this server's daemon). Policy, same as the UNIX
   * socket: a response without a valid daemon signature, or any status other than 200, is a
   * channel failure and the caller falls back to an ad-hoc spawn.
   */
  private executeViaHttp(
    port: number,
    script: string,
    payload: any,
    args: string[],
    timeoutMs: number
  ): Promise<PythonExecResult> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      const token = this.ipcToken;
      const body = Buffer.from(JSON.stringify({ script, payload, args, timeoutMs }), "utf8");
      const auth = signIpcRequest(token, "POST", "/execute", body);

      const req = http.request(
        {
          hostname: this.httpHost.replace(/^\[|\]$/g, ""),
          port,
          path: "/execute",
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Content-Length": body.length,
            "X-Metallix-Ts": auth.ts,
            "X-Metallix-Nonce": auth.nonce,
            "X-Metallix-Mac": auth.mac,
          },
          timeout: timeoutMs,
        },
        (res) => {
          const chunks: Buffer[] = [];
          res.on("data", (chunk: Buffer) => chunks.push(chunk));
          res.on("end", () => {
            const raw = Buffer.concat(chunks);
            const status = res.statusCode ?? 0;
            if (!verifyIpcResponseMac(token, auth.nonce, status, raw, res.headers["x-metallix-mac"])) {
              reject(new Error(`HTTP microservice response is not signed by this server's daemon (HTTP ${status})`));
              return;
            }
            if (status !== 200) {
              let code = "";
              try { code = String(JSON.parse(raw.toString("utf8"))?.code ?? ""); } catch { /* non-JSON error body */ }
              reject(new Error(`HTTP microservice refused the request (HTTP ${status}${code ? ` ${code}` : ""})`));
              return;
            }
            try {
              const parsed = JSON.parse(raw.toString("utf8"));
              const durationMs = Date.now() - startTime;
              resolve({
                stdout: parsed.stdout ?? "",
                stderr: parsed.stderr ?? "",
                exitCode: parsed.exitCode ?? 0,
                durationMs,
                warm: true,
                channel: "http_microservice",
              });
            } catch (err: any) {
              reject(new Error(`HTTP microservice JSON parse error: ${err.message}`));
            }
          });
        }
      );

      req.on("timeout", () => {
        req.destroy();
        reject(new Error(`HTTP microservice request timed out after ${timeoutMs}ms`));
      });

      req.on("error", (err) => reject(err));
      req.write(body);
      req.end();
    });
  }

  /**
   * Fail-safe fallback: ad-hoc process spawn if persistent daemon is rebooting
   */
  private executeViaAdHocSpawn(
    scriptRelativePath: string,
    inputJson: any,
    args: string[],
    timeoutMs: number
  ): Promise<PythonExecResult> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      const scriptPath = path.join(process.cwd(), scriptRelativePath);

      const python = getHostPython();
      const pyProcess = spawn(python.cmd, [...python.prefix, scriptPath, ...args], { windowsHide: true });
      let stdout = "";
      let stderr = "";

      const timer = setTimeout(() => {
        pyProcess.kill("SIGKILL");
        reject(new Error(`Ad-hoc Python execution timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      if (inputJson !== null && inputJson !== undefined) {
        const payload = typeof inputJson === "string" ? inputJson : JSON.stringify(inputJson);
        pyProcess.stdin.write(payload);
        pyProcess.stdin.end();
      }

      pyProcess.stdout.on("data", (data) => {
        stdout += data.toString();
      });

      pyProcess.stderr.on("data", (data) => {
        stderr += data.toString();
      });

      pyProcess.on("close", (code) => {
        clearTimeout(timer);
        const durationMs = Date.now() - startTime;
        resolve({
          stdout,
          stderr,
          exitCode: code,
          durationMs,
          warm: false,
          channel: "ad_hoc_fallback",
        });
      });

      pyProcess.on("error", (err) => {
        clearTimeout(timer);
        reject(err);
      });
    });
  }

  /**
   * Primary unified execution dispatcher. Only channels announced by this server's own daemon
   * are used; anything else (not ready, channel inactive, refused or unsigned reply) falls back
   * to an ad-hoc spawn.
   */
  public async execute(
    scriptRelativePath: string,
    inputJson: any,
    args: string[] = [],
    timeoutMs: number = 15000
  ): Promise<PythonExecResult> {
    assertDispatchableScript(scriptRelativePath);
    const t0 = Date.now();
    const failures: string[] = [];

    const socketPath = this.unixTarget();
    if (socketPath) {
      try {
        const result = await this.executeViaUnixSocket(socketPath, scriptRelativePath, inputJson, args, timeoutMs);
        this.recordSuccess(Date.now() - t0);
        return result;
      } catch (err: any) {
        failures.push(err?.message || String(err));
      }
    } else {
      failures.push("no UNIX socket announced by this server's daemon");
    }

    const port = this.httpTarget();
    if (port) {
      try {
        const httpResult = await this.executeViaHttp(port, scriptRelativePath, inputJson, args, timeoutMs);
        this.recordSuccess(Date.now() - t0);
        return httpResult;
      } catch (err: any) {
        failures.push(err?.message || String(err));
      }
    } else {
      failures.push("no HTTP listener announced by this server's daemon");
    }

    console.warn(`[Python-Supervisor] IPC channels unavailable (${failures.join(" / ")}). Falling back to ad-hoc spawn...`);
    const spawnResult = await this.executeViaAdHocSpawn(scriptRelativePath, inputJson, args, timeoutMs);
    this.recordSuccess(Date.now() - t0);
    return spawnResult;
  }

  private recordSuccess(durationMs: number) {
    this.requestsHandled++;
    this.totalDurationMs += durationMs;
  }

  public getStatus(): IPCDaemonStatus {
    const avgDuration =
      this.requestsHandled > 0 ? (this.totalDurationMs / this.requestsHandled).toFixed(2) : "0.00";
    const httpPort = this.readiness.httpPort;
    const host = this.httpHost.includes(":") && !this.httpHost.startsWith("[") ? `[${this.httpHost}]` : this.httpHost;
    return {
      status: this.isReady ? "online" : this.isRestarting ? "restarting" : "initializing",
      isPersistent: true,
      channels: {
        unixSocket: {
          path: this.readiness.unixSocketPath ?? this.configuredSocketPath ?? "",
          active: this.unixTarget() !== null,
        },
        httpMicroservice: {
          url: httpPort ? `http://${host}:${httpPort}` : "",
          active: this.httpTarget() !== null,
        },
      },
      requestsProcessed: this.requestsHandled,
      avgLatencyMs: parseFloat(avgDuration),
      uptimeSeconds: Math.round((Date.now() - this.startTime) / 1000),
      warmModulesCount: this.readiness.warmModules.length,
      warmModules: [...this.readiness.warmModules],
      pythonVersion: this.readiness.pythonVersion,
      lastError: this.lastError,
    };
  }
}

// Global Singleton IPC Supervisor
export const pythonIPCSupervisor = new PersistentPythonIPCSupervisor();

/**
 * Express middleware for subprocess lifecycle management & orchestration.
 * Injects IPC supervisor telemetry into response headers, isolates process errors,
 * and ensures sub-process resource tracing per request.
 */
export function processOrchestrationMiddleware(
  req: import("express").Request,
  res: import("express").Response,
  next: import("express").NextFunction
) {
  // Attach IPC supervisor telemetry headers
  const status = pythonIPCSupervisor.getStatus();
  res.setHeader("X-Python-IPC-Status", status.status);
  res.setHeader("X-Python-IPC-Warm-Modules", String(status.warmModulesCount));

  // Trace execution duration for process-heavy routes
  const startTime = Date.now();
  res.on("finish", () => {
    if (req.path.startsWith("/api/python/")) {
      const elapsed = Date.now() - startTime;
      if (elapsed > 8000) {
        console.warn(`[ProcessOrchestrator] Long-running process request ${req.method} ${req.path} took ${elapsed}ms`);
      }
    }
  });

  next();
}

/**
 * Drop-in helper for running python scripts using persistent warm IPC worker
 */
export function runPythonScript(
  scriptRelativePath: string,
  inputJson: any,
  args: string[] = [],
  timeoutMs: number = 15000
): Promise<PythonExecResult> {
  return pythonIPCSupervisor.execute(scriptRelativePath, inputJson, args, timeoutMs);
}
