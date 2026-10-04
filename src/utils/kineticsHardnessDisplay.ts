// Display text for the kinetics solver's predicted hardness (python/kinetics_ttt_cct_solver.py, CCT map rows).
// predictedHardness_HV is an ASTM E140 Table 1 conversion of the predicted HRC for non-austenitic steels only; it is
// null for other alloy classes and outside HRC 20-68. A missing or null value is shown as "Unavailable", never as an
// invented number.
import { UNAVAILABLE_TEXT } from "./hardnessConversion";

export interface KineticsHardnessRow {
  predictedHardness_HRC?: number | null;
  predictedHardness_HV?: number | null;
  predictedHardness_HV_status?: string | null;
}

export const KINETICS_HV_STATUS_NOTES: Readonly<Record<string, string>> = {
  "converted-astm-e140-table1":
    "HV converted from the predicted HRC per ASTM E140 Table 1 (non-austenitic steels); approximate, not measured.",
  "unavailable-outside-e140-table1-hrc-20-68":
    "HV unavailable: the predicted HRC is outside the ASTM E140 Table 1 range (HRC 20-68).",
  "unavailable-no-verified-table-for-alloy-class":
    "HV unavailable: no verified HRC-HV conversion table for this alloy class.",
};

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export interface KineticsHardnessText {
  /** "58" or "Unavailable" (bare value, e.g. for a metric tile labelled "Hardness (HRC)") */
  hrcValue: string;
  /** "653" or "Unavailable" */
  hvValue: string;
  /** "58 HRC" or "HRC: Unavailable" */
  hrc: string;
  /** "653 HV" or "HV: Unavailable" */
  hv: string;
  /** Why the HV is (un)available, from the solver status; "" when no row was given. */
  note: string;
}

export function kineticsHardnessText(row: KineticsHardnessRow | null | undefined): KineticsHardnessText {
  const hrc = row?.predictedHardness_HRC;
  const hv = row?.predictedHardness_HV;
  const status = row?.predictedHardness_HV_status ?? "";
  return {
    hrcValue: finite(hrc) ? String(hrc) : UNAVAILABLE_TEXT,
    hvValue: finite(hv) ? String(hv) : UNAVAILABLE_TEXT,
    hrc: finite(hrc) ? `${hrc} HRC` : `HRC: ${UNAVAILABLE_TEXT}`,
    hv: finite(hv) ? `${hv} HV` : `HV: ${UNAVAILABLE_TEXT}`,
    note: KINETICS_HV_STATUS_NOTES[status] ?? (row && !finite(hv) ? "HV unavailable." : ""),
  };
}

// ---------------------------------------------------------------------------------------------------------------
// LPBF build-job kinetics block (python/lpbf_build_job_solver.py build_job_kinetics). Alloys without a kinetics
// model of their own (316L, AlSi10Mg) carry {status: "unavailable", reason} instead of a substituted alloy.

export interface BuildJobCctRow extends KineticsHardnessRow {
  coolingRate_C_s?: number | null;
  primaryMicrostructure?: string | null;
}

/** Python's choice of CCT row for the build cooling rate (lpbf_build_job_solver.build_cooling_rate_cct_row). */
export interface BuildCoolingRateCctRow {
  status?: string | null;
  reason?: string | null;
  rowIndex?: number | null;
  rowCoolingRate_C_s?: number | null;
  buildCoolingRate_C_s?: number | null;
  mapRange_C_s?: [number, number] | null;
}

export interface BuildJobKineticsLike {
  status?: string | null;
  reason?: string | null;
  buildCoolingRate_C_s?: number | null;
  buildCoolingRateCctRow?: BuildCoolingRateCctRow | null;
  cctContinuousCoolingMap?: BuildJobCctRow[] | null;
  calphadVsKineticsGap?: {
    kineticRealityAtSelectedCooling?: { predictedMartensite_pct?: number | null; verdict?: string | null } | null;
  } | null;
}

/** Whether the build-job kinetics block holds a computed result; otherwise the reason it is unavailable. */
export function buildJobKineticsAvailability(
  kinetics: BuildJobKineticsLike | null | undefined
): { available: boolean; reason: string } {
  if (!kinetics) return { available: false, reason: "No kinetics block in the build-job result." };
  if (kinetics.status === "unavailable") {
    return { available: false, reason: kinetics.reason || "Kinetics unavailable for this alloy." };
  }
  if (!kinetics.calphadVsKineticsGap?.kineticRealityAtSelectedCooling) {
    return { available: false, reason: "The kinetics block has no result at the build cooling rate." };
  }
  return { available: true, reason: "" };
}

/** "0.05", "2000", "1.1e+6" (rates of 10^4 and above in exponent form). */
export function formatCoolingRate(rate: number): string {
  return Math.abs(rate) >= 1e4 ? rate.toExponential(1) : String(rate);
}

export interface BuildJobCctRowSelection {
  /** The CCT map row the solver selected for the build cooling rate, or null. */
  row: BuildJobCctRow | null;
  /** Which cooling rate the row corresponds to, or why no row is shown. */
  label: string;
}

/**
 * The CCT row the Python build job selected (nearest on a log scale to the build cooling rate, never extrapolated
 * beyond the tabulated rates). The UI does not re-select; without a selected row the tiles show "Unavailable".
 */
export function buildJobCctRow(kinetics: BuildJobKineticsLike | null | undefined): BuildJobCctRowSelection {
  const sel = kinetics?.buildCoolingRateCctRow;
  const map = kinetics?.cctContinuousCoolingMap;
  const index = sel?.rowIndex;
  if (sel?.status === "selected" && Number.isSafeInteger(index) && map && map[index as number]) {
    const row = map[index as number];
    const rowRate = finite(row.coolingRate_C_s) ? formatCoolingRate(row.coolingRate_C_s) : "?";
    const build = finite(sel.buildCoolingRate_C_s) ? formatCoolingRate(sel.buildCoolingRate_C_s) : "?";
    return {
      row,
      label: `CCT row ${rowRate} °C/s (nearest on a log scale to the build cooling rate ${build} °C/s).`,
    };
  }
  return { row: null, label: `No CCT row: ${sel?.reason || "the solver selected no row for the build cooling rate"}.` };
}
