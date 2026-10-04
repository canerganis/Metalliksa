import path from "node:path";
import { existsSync } from "node:fs";
import { spawnSync, type SpawnSyncOptionsWithStringEncoding } from "node:child_process";
import dotenv from "dotenv";

export interface PythonCommand { cmd: string; prefix: string[] }
export interface PythonResolutionOptions {
  platform: string;
  cwd: string;
  env: Record<string, string | undefined>;
  exists: (file: string) => boolean;
  probe: (command: PythonCommand) => boolean;
}

/** Pure selection policy: all environment, filesystem and process operations are injected. */
export function resolvePythonCommand(options: PythonResolutionOptions): PythonCommand {
  const { platform, cwd, env, exists, probe } = options;
  const explicit = env.METALLIX_PYTHON;
  if (explicit) {
    const command = { cmd: explicit, prefix: [] };
    if (!probe(command)) {
      throw new Error("METALLIX_PYTHON failed its Python --version probe. Set it to one executable path without arguments; no fallback was attempted.");
    }
    return command;
  }
  const paths = platform === "win32" ? path.win32 : path.posix;
  const venvPython = (root: string) => paths.join(root, ...(platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"]));
  const candidates: PythonCommand[] = [];
  for (const root of [paths.join(cwd, ".venv"), env.VIRTUAL_ENV]) {
    if (root) {
      const cmd = venvPython(root);
      if (exists(cmd)) candidates.push({ cmd, prefix: [] });
    }
  }
  candidates.push(...(platform === "win32"
    ? [{ cmd: "py", prefix: ["-3"] }, { cmd: "python", prefix: [] }, { cmd: "python3", prefix: [] }]
    : [{ cmd: "python3", prefix: [] }, { cmd: "python", prefix: [] }]));
  for (const command of candidates) if (probe(command)) return command;
  throw new Error("No working host Python found. Configure METALLIX_PYTHON or a project .venv / active VIRTUAL_ENV.");
}

type VersionProbeRunner = (cmd: string, args: string[], options: SpawnSyncOptionsWithStringEncoding) => {
  status: number | null; error?: Error; stdout?: string; stderr?: string;
};

export function probePythonCommand(command: PythonCommand, run: VersionProbeRunner = spawnSync): boolean {
  const result = run(command.cmd, [...command.prefix, "--version"], {
    encoding: "utf8", timeout: 5000, windowsHide: true, shell: false,
  });
  return !result.error && result.status === 0 && /^Python 3\./m.test(`${result.stdout || ""}\n${result.stderr || ""}`);
}

let environmentLoaded = false;
export function loadPythonEnvironment(): void {
  if (!environmentLoaded) {
    // Existing process variables take precedence. Do this before any interpreter selection.
    dotenv.config({ quiet: true, override: false });
    environmentLoaded = true;
  }
}

/** Lazy, cached resolution; importing this module never loads dotenv or probes Python. */
export function createPythonRuntime(options: PythonResolutionOptions, loadEnvironment: () => void): () => PythonCommand {
  let selected: PythonCommand | undefined;
  return () => {
    if (!selected) {
      loadEnvironment();
      selected = resolvePythonCommand(options);
    }
    return { cmd: selected.cmd, prefix: [...selected.prefix] };
  };
}

export const getHostPython = createPythonRuntime({
  platform: process.platform, cwd: process.cwd(), env: process.env,
  exists: existsSync, probe: probePythonCommand,
}, loadPythonEnvironment);

/** Environment for a WSL worker when METALLIKSA_JOB_ROOT is configured. Windows variables reach a wsl.exe
 * child only when WSLENV lists them; without this the WSL worker silently ignored the configured root and used
 * the checkout's .lpbf-jobs. '/p' translates the drive path to /mnt/<drive>/..., which WSL can do only for a
 * drive-letter path, so UNC and \\wsl$ roots are rejected loudly. Returns a new object; never mutates env. */
function wslJobRootEnvironment(env: Record<string, string | undefined>): Record<string, string | undefined> | undefined {
  const configured = env.METALLIKSA_JOB_ROOT;
  if (!configured) return undefined;
  // A leading slash or backslash (UNC, \\wsl$, a Linux path, a root-relative path) would otherwise resolve
  // silently onto the current drive, so it is rejected before resolving; a relative path resolves against cwd.
  const resolved = /^[\\/]/.test(configured) ? configured : path.win32.resolve(configured);
  if (!/^[A-Za-z]:[\\/]/.test(resolved)) {
    throw new Error(`METALLIKSA_JOB_ROOT must be a drive-letter path (for example C:\\lpbf-jobs) for the WSL LPBF worker; UNC, \\\\wsl$ and Linux paths cannot be forwarded: ${configured}`);
  }
  const forwarded = (env.WSLENV ?? "").split(":").filter(entry => entry && entry.split("/")[0] !== "METALLIKSA_JOB_ROOT");
  return { ...env, METALLIKSA_JOB_ROOT: resolved, WSLENV: [...forwarded, "METALLIKSA_JOB_ROOT/p"].join(":") };
}

/** An explicit host executable takes precedence; otherwise keep WSL first on Windows. */
export function lpbfWorkerCommand(options: {
  platform: string; file: string; localFallback: boolean;
  env: Record<string, string | undefined>; hostPython: () => PythonCommand;
}): { cmd: string; args: string[]; env?: Record<string, string | undefined> } {
  if (options.platform === "win32" && !options.localFallback && !options.env.METALLIX_PYTHON) {
    const linuxPath = options.file.replace(/^([A-Za-z]):/, (_, drive: string) => `/mnt/${drive.toLowerCase()}`).replaceAll("\\", "/");
    const command = { cmd: "wsl.exe", args: ["-d", options.env.METALLIKSA_WSL_DISTRO || "Ubuntu-22.04", "--", "python3", "-u", linuxPath] };
    const env = wslJobRootEnvironment(options.env);
    return env ? { ...command, env } : command;
  }
  const python = options.hostPython();
  return { cmd: python.cmd, args: [...python.prefix, "-u", options.file] };
}
