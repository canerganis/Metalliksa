import path from "path";
import { PythonReadiness } from "./pythonStatus.ts";
import os from "os";
import net from "net";
import http from "http";
import crypto from "crypto";
import { spawn, ChildProcess } from "child_process";
import { getHostPython, loadPythonEnvironment } from "./pythonRuntime.ts";

// =========================================================================
// IPC security helpers (python/persistent_ipc_service.py enforces the other side)
// =========================================================================

/** Fresh per-spawn shared secret (64 hex chars); passed to the daemon via env, never argv. */
export function generateIpcToken(): string {
  return crypto.randomBytes(32).toString("hex");
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
    warn(`[Python-Supervisor] WARNING: IPC daemon bound to NON-LOOPBACK host ${requested} (METALLIX_IPC_ALLOW_REMOTE=1); token-protected only.`);
    return requested;
  }
  warn(`[Python-Supervisor] WARNING: ignoring non-loopback METALLIX_IPC_HOST=${requested}; binding 127.0.0.1 (set METALLIX_IPC_ALLOW_REMOTE=1 to override).`);
  return "127.0.0.1";
}

/** Spawn spec for the daemon: the token travels only in the child's environment. */
export function buildIpcSpawnSpec(
  python: { cmd: string; prefix: string[] },
  scriptPath: string,
  baseEnv: NodeJS.ProcessEnv,
  ipc: { socketPath: string; port: number; host: string; token: string }
): { cmd: string; args: string[]; env: NodeJS.ProcessEnv } {
  return {
    cmd: python.cmd,
    args: [...python.prefix, scriptPath],
    env: {
      ...baseEnv,
      METALLIX_IPC_SOCK: ipc.socketPath,
      METALLIX_IPC_PORT: String(ipc.port),
      METALLIX_IPC_HOST: ipc.host,
      METALLIX_IPC_TOKEN: ipc.token,
    },
  };
}

export function ipcAuthorizationHeader(token: string): string {
  return `Bearer ${token}`;
}

/** Only the fixed `python/<module>.py` form used by routes/*.ts is dispatched. */
const SCRIPT_REF = /^python\/[A-Za-z_][A-Za-z0-9_]*\.py$/;
export function assertDispatchableScript(scriptRelativePath: string): void {
  if (typeof scriptRelativePath !== "string" || !SCRIPT_REF.test(scriptRelativePath)) {
    throw new Error(`Refusing to dispatch Python script path ${JSON.stringify(scriptRelativePath)}; expected python/<module>.py`);
  }
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
  private socketPath: string;
  private httpPort: number;
  private httpHost: string;
  private startTime: number = Date.now();
  private requestsHandled: number = 0;
  private totalDurationMs: number = 0;
  private readiness = new PythonReadiness();
  private lastError: string | null = null;
  // Regenerated on every spawn; never logged or put on the command line.
  private ipcToken: string = generateIpcToken();

  constructor() {
    loadPythonEnvironment();
    this.socketPath =
      process.env.METALLIX_IPC_SOCK ||
      (process.platform === "win32"
        ? path.join(os.tmpdir(), "metallix_python_ipc.sock")
        : "/tmp/metallix_python_ipc.sock");
    this.httpPort = parseInt(process.env.METALLIX_IPC_PORT || "5055", 10);
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
    const spec = buildIpcSpawnSpec(getHostPython(), scriptPath, process.env, {
      socketPath: this.socketPath,
      port: this.httpPort,
      host: this.httpHost,
      token: this.ipcToken,
    });
    this.child = spawn(spec.cmd, spec.args, {
      windowsHide: true,
      env: spec.env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    // Capture stdout for readiness signal
    this.child.stdout?.on("data", (data) => {
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

    this.child.stderr?.on("data", (data) => {
      const msg = data.toString().trim();
      if (msg.includes("[PersistentIPC]")) {
        console.log(msg);
      } else if (msg) {
        console.warn(`[Python-Worker stderr] ${msg}`);
      }
    });

    this.child.on("error", (err) => {
      console.error("[Python-Supervisor] Worker process error:", err);
      this.lastError = err.message;
      this.handleProcessExit();
    });

    this.child.on("exit", (code, signal) => {
      console.warn(`[Python-Supervisor] Persistent Python worker exited (code=${code}, signal=${signal})`);
      this.handleProcessExit();
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

  /**
   * Dispatches script execution to the persistent Python daemon over UNIX domain socket
   */
  private executeViaUnixSocket(
    script: string,
    payload: any,
    args: string[],
    timeoutMs: number
  ): Promise<PythonExecResult> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      const socket = net.createConnection(this.socketPath);
      let buffer = "";

      const timer = setTimeout(() => {
        socket.destroy();
        reject(new Error(`UNIX socket IPC timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      socket.on("connect", () => {
        const req = {
          action: "execute",
          token: this.ipcToken,
          script,
          payload,
          args,
          timeoutMs,
        };
        socket.write(JSON.stringify(req) + "\n");
      });

      socket.on("data", (chunk) => {
        buffer += chunk.toString();
        if (buffer.includes("\n")) {
          clearTimeout(timer);
          socket.end();

          const line = buffer.substring(0, buffer.indexOf("\n")).trim();
          try {
            const parsed = JSON.parse(line);
            if (parsed?.status === 401 || parsed?.code === "UNAUTHORIZED") {
              // e.g. a daemon from another server instance owns this socket path
              reject(new Error("UNIX socket IPC rejected the token (401)"));
              return;
            }
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
            reject(new Error(`Failed to parse IPC JSON response: ${e.message}`));
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
   * Fallback channel: Dispatches via HTTP loopback microservice (http://127.0.0.1:5055/execute)
   */
  private executeViaHttp(
    script: string,
    payload: any,
    args: string[],
    timeoutMs: number
  ): Promise<PythonExecResult> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      const reqPayload = JSON.stringify({ script, payload, args, timeoutMs });

      const req = http.request(
        {
          hostname: this.httpHost,
          port: this.httpPort,
          path: "/execute",
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(reqPayload),
            Authorization: ipcAuthorizationHeader(this.ipcToken),
          },
          timeout: timeoutMs,
        },
        (res) => {
          let body = "";
          res.on("data", (chunk) => (body += chunk));
          res.on("end", () => {
            if (res.statusCode !== 200) {
              // 401: another instance's daemon owns the port; 4xx: refused request.
              // The caller falls back to an ad-hoc spawn.
              let code = "";
              try { code = String(JSON.parse(body)?.code ?? ""); } catch { /* non-JSON error body */ }
              reject(new Error(`HTTP microservice refused the request (HTTP ${res.statusCode}${code ? ` ${code}` : ""})`));
              return;
            }
            try {
              const parsed = JSON.parse(body);
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
      req.write(reqPayload);
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
   * Primary unified execution dispatcher
   */
  public async execute(
    scriptRelativePath: string,
    inputJson: any,
    args: string[] = [],
    timeoutMs: number = 15000
  ): Promise<PythonExecResult> {
    assertDispatchableScript(scriptRelativePath);
    const t0 = Date.now();

    const skipUnix = process.platform === "win32";
    let unixErr: unknown = skipUnix ? new Error("UNIX domain sockets skipped on win32") : null;

    if (!skipUnix) {
      try {
        const result = await this.executeViaUnixSocket(scriptRelativePath, inputJson, args, timeoutMs);
        this.recordSuccess(Date.now() - t0);
        return result;
      } catch (err) {
        unixErr = err;
      }
    }

    try {
      const httpResult = await this.executeViaHttp(scriptRelativePath, inputJson, args, timeoutMs);
      this.recordSuccess(Date.now() - t0);
      return httpResult;
    } catch (httpErr: any) {
      const unixMsg = unixErr instanceof Error ? unixErr.message : String(unixErr);
      console.warn(
        `[Python-Supervisor] IPC channels unavailable (${unixMsg} / ${httpErr?.message || httpErr}). Falling back to ad-hoc spawn...`
      );
      const spawnResult = await this.executeViaAdHocSpawn(scriptRelativePath, inputJson, args, timeoutMs);
      this.recordSuccess(Date.now() - t0);
      return spawnResult;
    }
  }

  private recordSuccess(durationMs: number) {
    this.requestsHandled++;
    this.totalDurationMs += durationMs;
  }

  public getStatus(): IPCDaemonStatus {
    const avgDuration =
      this.requestsHandled > 0 ? (this.totalDurationMs / this.requestsHandled).toFixed(2) : "0.00";
    return {
      status: this.isReady ? "online" : this.isRestarting ? "restarting" : "initializing",
      isPersistent: true,
      channels: {
        unixSocket: {
          path: this.socketPath,
          active: this.isReady && this.readiness.unixActive,
        },
        httpMicroservice: {
          url: `http://${this.httpHost}:${this.httpPort}`,
          active: this.isReady && this.readiness.httpActive,
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
