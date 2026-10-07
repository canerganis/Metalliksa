/// <reference types="vite/client" />
/**
 * The committed calibration scorecard view record, if any. Vite inlines the newest (by file name) of
 * docs/LPBF_CALIBRATION_SCORECARD_*.view.json. When none is committed the glob is empty and the scorecard shows an
 * honest "no scorecard record committed yet" state. Outside Vite (tests under tsx) the glob is unavailable and the
 * record is treated as absent; tests pass documents to the lab explicitly.
 */
import { checkedCalibrationScorecard, type LpbfCalibrationScorecardDocument } from "./lpbfCalibrationScorecard";

let modules: Record<string, unknown> = {};
try {
  modules = import.meta.glob("../../docs/LPBF_CALIBRATION_SCORECARD_*.view.json", { eager: true, import: "default" });
} catch {
  modules = {};
}

const newestKey = Object.keys(modules).sort().at(-1);

/** null when no record is committed; throws (loudly) when a committed record is malformed. */
export const COMMITTED_CALIBRATION_SCORECARD: LpbfCalibrationScorecardDocument | null =
  newestKey === undefined ? null : checkedCalibrationScorecard(modules[newestKey]);
