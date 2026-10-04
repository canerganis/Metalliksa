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
// LPBF build-job kinetics block (python/lpbf_build_job_solver.py build_job_kinetics). Python decides everything
// here; the UI only displays it. `status` is the field to trust ("available" / "unavailable"); `success: false` on
// an unavailable block is a legacy envelope shape, not a failed build job. Unavailable cases: alloys without a
// kinetics model of their own (316L, AlSi10Mg; never a substituted alloy), no finite build cooling rate, and the
// 1 K/s floor of a degenerate solidification front.

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

/** Martensite fraction / verdict at the build rate (lpbf_build_job_solver.build_rate_martensite). */
export interface BuildRateMartensite {
  status?: string | null;
  reason?: string | null;
  predictedMartensite_pct?: number | null;
  verdict?: string | null;
  coolingRate_C_s?: number | null;
}

export interface BuildJobKineticsLike {
  status?: string | null;
  reason?: string | null;
  buildCoolingRate_C_s?: number | null;
  buildCoolingRateCctRow?: BuildCoolingRateCctRow | null;
  buildRateMartensite?: BuildRateMartensite | null;
  cctContinuousCoolingMap?: BuildJobCctRow[] | null;
}

/** Python reasons have no final period; add one for display. */
const sentence = (text: string): string => (/[.!?]$/.test(text) ? text : `${text}.`);

/** Whether the build-job kinetics block holds a computed result; otherwise the reason it is unavailable. */
export function buildJobKineticsAvailability(
  kinetics: BuildJobKineticsLike | null | undefined
): { available: boolean; reason: string } {
  if (!kinetics) return { available: false, reason: "No kinetics block in the build-job result." };
  if (kinetics.status !== "available") {
    return { available: false, reason: sentence(kinetics.reason || "Kinetics unavailable for this build") };
  }
  return { available: true, reason: "" };
}

/** "0.05", "2000", "30.1", "1.09e+6": at most 3-4 significant digits, never a long float. */
export function formatCoolingRate(rate: number): string {
  return Math.abs(rate) >= 1e4 ? rate.toExponential(2) : String(Number(rate.toPrecision(4)));
}

export interface BuildJobCctRowSelection {
  /** The CCT map row the solver selected for the build cooling rate, or null. */
  row: BuildJobCctRow | null;
  /** Which cooling rate the row corresponds to, or why no row is shown. */
  label: string;
}

/**
 * The CCT row the Python build job selected (nearest on a log scale to the build cooling rate, never extrapolated
 * beyond the tabulated rates). The UI does not re-select; a selection that does not match its map row is not
 * trusted. Without a selected row the tiles show "Unavailable".
 */
export function buildJobCctRow(kinetics: BuildJobKineticsLike | null | undefined): BuildJobCctRowSelection {
  const sel = kinetics?.buildCoolingRateCctRow;
  const map = kinetics?.cctContinuousCoolingMap;
  const index = sel?.rowIndex;
  if (sel?.status === "selected" && Number.isSafeInteger(index) && Array.isArray(map)) {
    const row = map[index as number];
    if (
      row &&
      finite(row.coolingRate_C_s) &&
      row.coolingRate_C_s === sel.rowCoolingRate_C_s &&
      finite(sel.buildCoolingRate_C_s)
    ) {
      return {
        row,
        label:
          `CCT row ${formatCoolingRate(row.coolingRate_C_s)} °C/s (nearest on a log scale to the build ` +
          `cooling rate ${formatCoolingRate(sel.buildCoolingRate_C_s)} °C/s).`,
      };
    }
  }
  return { row: null, label: `No CCT row: ${sentence(sel?.reason || "the solver selected no row for the build cooling rate")}` };
}

export interface BuildJobMartensiteText {
  /** "12.5%" or "Unavailable"; never "null%". */
  value: string;
  /** Martensite-based verdict, or null when withheld. */
  verdict: string | null;
  /** Why the fraction / verdict is withheld; "" when shown. */
  reason: string;
  /** "At build rate 30 °C/s" when shown. */
  hint: string;
}

/** Martensite tile text from Python's buildRateMartensite; the raw calphadVsKineticsGap is never read here. */
export function buildJobMartensiteText(kinetics: BuildJobKineticsLike | null | undefined): BuildJobMartensiteText {
  const m = kinetics?.buildRateMartensite;
  if (m?.status === "available" && finite(m.predictedMartensite_pct)) {
    return {
      value: `${m.predictedMartensite_pct}%`,
      verdict: m.verdict || null,
      reason: "",
      hint: finite(m.coolingRate_C_s) ? `At build rate ${formatCoolingRate(m.coolingRate_C_s)} °C/s` : "At build rate",
    };
  }
  return {
    value: UNAVAILABLE_TEXT,
    verdict: null,
    reason: sentence(m?.reason || "no martensite fraction for the build cooling rate"),
    hint: "Reason below",
  };
}
