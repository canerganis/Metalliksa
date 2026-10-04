/**
 * Real start-up checks for the boot sequence (Phase 9, DESIGN-9 section 4).
 *
 * Every row text is derived from what a request actually returned. Wording rules:
 * - "Python engine online" only when the status endpoint reports online.
 * - No step claims validation or readiness of any physical model.
 * - Missing data reads "unavailable" or "not reported", never a placeholder number.
 */
import type { RuntimeConfig } from "../components/AirgapBanner";
import type { PythonEngineStatus } from "./pythonComputationService";
import {
  BOOT_SKIP_STORAGE_KEY,
  createBootController,
  type BootController,
  type BootOptions,
  type BootOutcome,
  type BootStep,
} from "../utils/bootSequence";

export interface BootStepDeps {
  loadConfig: () => Promise<RuntimeConfig>;
  probe: () => { loaded: boolean; accessRequired: boolean; failure: string | null };
  engineStatus: () => Promise<PythonEngineStatus>;
  moduleCount: () => number;
}

/** "k/N" for subsystems the engine reported, or null when it reported none. */
export function subsystemCount(status: PythonEngineStatus | null | undefined): { available: number; total: number } | null {
  const entries = Object.values(status?.subsystems ?? {}) as Array<{ available?: boolean } | undefined>;
  if (!entries.length) return null;
  return { available: entries.filter((s) => s?.available === true).length, total: entries.length };
}

/**
 * Subsystem wording when the engine sent no per-subsystem map. The server currently sends
 * subsystemStatus "unverified"; that is reported verbatim as "unverified (server)", in a neutral
 * tone, and never turned into a count.
 */
export function subsystemQualifier(status: PythonEngineStatus): string {
  return status.subsystemStatus ? `${status.subsystemStatus} (server)` : "not reported";
}

export function describeEngine(status: PythonEngineStatus): BootOutcome {
  if (!status.online) {
    const reason = status.status === "client_fallback" ? "status request failed" : `status: ${status.status}`;
    return { state: "unavailable", detail: `Engine unavailable (${reason}); continuing in limited mode` };
  }
  // "online" comes only from the status call; subsystems never upgrade or downgrade it unless counted.
  const counts = subsystemCount(status);
  const version = status.pythonVersion ? `Python ${status.pythonVersion}` : "Python version not reported";
  const subsystems = counts ? `${counts.available}/${counts.total} subsystems available` : `subsystems: ${subsystemQualifier(status)}`;
  const missing = counts !== null && counts.available < counts.total;
  return { state: missing ? "limited" : "ok", detail: `Python engine online · ${version} · ${subsystems}` };
}

export function buildBootSteps(deps: BootStepDeps): BootStep[] {
  let config: RuntimeConfig | null = null;
  const failure = () => deps.probe().failure ?? "no answer yet";
  return [
    {
      id: "runtime-config",
      label: "Runtime configuration",
      run: async () => {
        const cfg = await deps.loadConfig();
        if (!deps.probe().loaded) return { state: "limited", detail: `Config unavailable (${failure()}); using defaults` };
        config = cfg;
        return { state: "ok", detail: "Loaded from the local server" };
      },
    },
    {
      id: "access",
      label: "Access",
      run: async () => {
        const probe = deps.probe();
        if (probe.accessRequired) return { state: "blocked", detail: "Sign-in required" };
        if (!probe.loaded) return { state: "unavailable", detail: `Not confirmed (${failure()})` };
        return { state: "ok", detail: "Local server accepted the request" };
      },
    },
    {
      id: "airgap",
      label: "Air-gap",
      run: async () => {
        if (!config) return { state: "unavailable", detail: "Unknown: runtime config unavailable" };
        if (!config.airgapped) return { state: "ok", detail: "Air-gap OFF" };
        const cut = config.blockedServices.length;
        return { state: "limited", detail: cut ? `Air-gap ON · ${cut} services cut` : "Air-gap ON · cut services not listed" };
      },
    },
    {
      id: "engine",
      label: "Python engine",
      run: async () => describeEngine(await deps.engineStatus()),
    },
    {
      // Not a probe: the registry is bundled with the app, so this row only reports that it loaded and
      // its size. DESIGN-9 also proposed preloading the first module chunk here; that check was dropped
      // (it would delay boot and module chunk errors are already caught by ModuleBoundary).
      id: "modules",
      label: "Module registry",
      run: async () => {
        const n = deps.moduleCount();
        return n > 0 ? { state: "ok", detail: `Registry loaded · ${n} modules` } : { state: "unavailable", detail: "Registry empty" };
      },
    },
  ];
}

export function prefersReducedMotion(): boolean {
  try {
    return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
  } catch {
    return false;
  }
}

export function readSkipFlag(): boolean {
  try {
    return typeof sessionStorage !== "undefined" && sessionStorage.getItem(BOOT_SKIP_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function writeSkipFlag(): void {
  try {
    sessionStorage.setItem(BOOT_SKIP_STORAGE_KEY, "1");
  } catch {
    /* Optional storage: the next load animates again. */
  }
}

/**
 * Controller options from the environment. The remembered flag and reduced motion only switch the
 * animation off; the steps are always the full list and always run.
 */
export function bootOptions(deps: BootStepDeps): BootOptions {
  return {
    steps: buildBootSteps(deps),
    reducedMotion: prefersReducedMotion(),
    skipAnimation: readSkipFlag(),
    remember: writeSkipFlag,
  };
}

let controller: BootController | null = null;

/** One controller per page load, shared by the boot overlay and the telemetry strip. */
export function getBootController(deps: () => BootStepDeps): BootController {
  controller ??= createBootController(bootOptions(deps()));
  return controller;
}
