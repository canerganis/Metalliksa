/**
 * Shared engine-status wording (boot row, telemetry strip, engine-status modal). Kept tiny and
 * separate so the eager App shell can use it without pulling the lazy boot chunk.
 */
import type { PythonEngineStatus } from "../services/pythonComputationService";

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
