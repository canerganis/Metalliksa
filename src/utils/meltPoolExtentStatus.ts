/**
 * Single mapping of the Python melt-pool `extentStatus` (python/lpbf_thermal_solver.py,
 * result.meltPoolGeometry) to what a view may show. Only "computed" is a closed, unfloored
 * liquidus isotherm; every other status is a screening substitute or a bound and must carry a
 * visible label and be excluded from literature error percentages.
 */
export type MeltPoolExtentStatus =
  | "computed"
  | "heuristic-width-fallback"
  | "width-floor-applied"
  | "search-box-limited";

export interface MeltPoolExtentFields {
  extentStatus?: string | null;
  extentNote?: string | null;
}

export interface MeltPoolExtentInfo {
  /** true only for extentStatus === "computed". A missing status is never treated as computed. */
  computed: boolean;
  /** The Python status string (or "not-reported" when the producer sent none). */
  status: string;
  /** Short human description of what the numbers are. */
  description: string;
  note: string | null;
}

const DESCRIPTIONS: Record<MeltPoolExtentStatus, string> = {
  computed: "closed liquidus isotherm",
  "heuristic-width-fallback": "no resolvable melt; W/D/L are a screening heuristic, not an isotherm",
  "width-floor-applied": "width is the 0.55 x beam-diameter floor, not the isotherm",
  "search-box-limited": "extent is a lower bound (search box reached)",
};

export function meltPoolExtentInfo(geometry: MeltPoolExtentFields | null | undefined): MeltPoolExtentInfo {
  const status = geometry?.extentStatus ? String(geometry.extentStatus) : "not-reported";
  const known = Object.prototype.hasOwnProperty.call(DESCRIPTIONS, status);
  return {
    computed: status === "computed",
    status,
    description: known ? DESCRIPTIONS[status as MeltPoolExtentStatus] : "melt-pool extent status not reported by the solver",
    note: geometry?.extentNote ? String(geometry.extentNote) : null,
  };
}

export function isComputedMeltPoolExtent(geometry: MeltPoolExtentFields | null | undefined): boolean {
  return meltPoolExtentInfo(geometry).computed;
}

/** Replacement text for a literature % error when the geometry is not a computed isotherm; null when computed. */
export function literatureErrorUnavailableText(geometry: MeltPoolExtentFields | null | undefined): string | null {
  const info = meltPoolExtentInfo(geometry);
  return info.computed ? null : `not computed — ${info.status}`;
}
