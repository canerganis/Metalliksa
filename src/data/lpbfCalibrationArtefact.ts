/// <reference types="vite/client" />
/**
 * Which calibrated-mode cells may be served, read from the committed, hashed calibration artefact
 * (data/calibration/lpbf-meltpool-calibration-v1.json, written only by python/tools/lpbf_calibration_fit.py).
 *
 * Only cells whose gate status is "enabled" are ever offered. When no cell is enabled for the chosen kernel and alloy
 * the calibrated-mode control is NOT rendered (no greyed-out toggle: a permanently disabled control would itself be a
 * claim). Screening only, not validation: this module derives no evidence label.
 */

export interface CalibrationCellRef {
  readonly kernel: string;
  readonly material: string;
  readonly quantity: "width" | "depth";
  readonly status: "enabled" | "within-source-only" | "rejected" | "no-data";
}

let modules: Record<string, unknown> = {};
try {
  modules = import.meta.glob("../../data/calibration/lpbf-meltpool-calibration-v1.json", { eager: true, import: "default" });
} catch {
  modules = {};
}

export interface CalibrationArtefactSummary {
  readonly calibrationId: string;
  readonly cells: readonly CalibrationCellRef[];
}

export function summarizeCalibrationArtefact(raw: unknown): CalibrationArtefactSummary | null {
  if (typeof raw !== "object" || raw === null) return null;
  const art = raw as { schema?: unknown; calibrationId?: unknown; cells?: unknown };
  if (art.schema !== "lpbf-meltpool-calibration-1" || typeof art.calibrationId !== "string" || !Array.isArray(art.cells)) return null;
  const cells: CalibrationCellRef[] = [];
  for (const c of art.cells as Record<string, unknown>[]) {
    if (typeof c?.kernel === "string" && typeof c?.material === "string" && (c.quantity === "width" || c.quantity === "depth")
      && (c.status === "enabled" || c.status === "within-source-only" || c.status === "rejected" || c.status === "no-data")) {
      cells.push({ kernel: c.kernel, material: c.material, quantity: c.quantity, status: c.status });
    }
  }
  return { calibrationId: art.calibrationId, cells };
}

export const COMMITTED_CALIBRATION_ARTEFACT: CalibrationArtefactSummary | null =
  summarizeCalibrationArtefact(Object.values(modules)[0]);

/** Enabled cells for a kernel and alloy; empty when none (the caller then renders no control at all). */
export function enabledCellsFor(
  summary: CalibrationArtefactSummary | null, kernel: string, material: string,
): readonly CalibrationCellRef[] {
  if (!summary) return [];
  return summary.cells.filter((c) => c.status === "enabled" && c.kernel === kernel && c.material === material);
}
