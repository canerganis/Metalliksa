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
