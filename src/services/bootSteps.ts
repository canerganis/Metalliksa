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

export function describeEngine(status: PythonEngineStatus): BootOutcome {
  if (!status.online) {
    const reason = status.status === "client_fallback" ? "status request failed" : `status: ${status.status}`;
    return { state: "unavailable", detail: `Engine unavailable (${reason}); continuing in limited mode` };
  }
  const counts = subsystemCount(status);
  const version = status.pythonVersion ? `Python ${status.pythonVersion}` : "Python version not reported";
  const subsystems = counts ? `${counts.available}/${counts.total} subsystems available` : "subsystems not reported";
  const full = counts !== null && counts.available === counts.total;
  return { state: full ? "ok" : "limited", detail: `Python engine online · ${version} · ${subsystems}` };
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
      id: "modules",
      label: "Module registry",
      run: async () => {
        const n = deps.moduleCount();
        return n > 0 ? { state: "ok", detail: `${n} modules registered` } : { state: "unavailable", detail: "No modules registered" };
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

let controller: BootController | null = null;

/** One controller per page load, shared by the boot overlay and the telemetry strip. */
export function getBootController(deps: () => BootStepDeps): BootController {
  controller ??= createBootController({
    steps: buildBootSteps(deps()),
    reducedMotion: prefersReducedMotion(),
    skipAnimation: readSkipFlag(),
  });
  return controller;
}
