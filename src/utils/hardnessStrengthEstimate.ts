// Hardness <-> strength estimates (screening only; never a measurement).
//
// Source (read 2026-10-04 from the authors' institutional copy):
//   E.J. Pavlina, C.J. Van Tyne, "Correlation of Yield Strength and Tensile Strength with Hardness for Steels",
//   J. Mater. Eng. Perform. 17 (2008) 888-893, doi:10.1007/s11665-008-9225-5,
//   https://wpfiles.mines.edu/wp-content/uploads/aspprc/ResearchMaterials/Publications/386-Pavlina.pdf
//   Table 1, data set "All data" (HV = diamond pyramid hardness in kgf/mm2, strength in MPa):
//     yield:   YS = -90.7 + 2.876 HV   R2 0.9212, standard error 102 MPa, valid HV 129-632 (165 points)
//     tensile: TS = -99.8 + 3.734 HV   R2 0.9347, standard error 112 MPa, valid HV 129-592 (159 points)
//   Data: over 150 non-austenitic, hypoeutectoid steels (ferrite, pearlite, martensite, bainite, multiphase).
//
// HV from yield strength inverts the yield regression; it is not a separate fit, and the standard error of
// 102 MPa on YS corresponds to about 35 HV. Outside the steel class, the carbon limit or the valid HV range the
// estimate is unavailable (no extrapolation, no clamping).
//
// Units trap (why the old constants were dropped): Tabor's H ~ 3 sigma holds with H and sigma in the same units, so
// with HV in kgf/mm2, sigma(MPa) ~ HV x 9.807 / 3 ~ 3.27 HV, and sigma is a flow stress at about 8 % strain, not the
// 0.2 % yield strength. The removed rules HV = YS/3.05 (Ni), YS/2.9 (Ti), YS/3.1 (steel and any alloy),
// HV = UTS/3.1, HV = YS/3 + 35 and YS/3 + 30 had no source.
//
// Hypoeutectoid limit: Fe-C eutectoid at 0.76 wt% C (Callister, Fe-Fe3C diagram); alloying shifts it, which is not
// modelled here.

import { hardnessMaterialClassLabel, hardnessMaterialClassOf, type HardnessMaterialClass } from "./hardnessConversion";

export const PAVLINA_VAN_TYNE_2008 = {
  citation: "Pavlina & Van Tyne, J. Mater. Eng. Perform. 17 (2008) 888-893, Table 1 (All data)",
  yield: { constant_MPa: -90.7, coefficient: 2.876, standardError_MPa: 102, hvMin: 129, hvMax: 632 },
  tensile: { constant_MPa: -99.8, coefficient: 3.734, standardError_MPa: 112, hvMin: 129, hvMax: 592 },
} as const;

/** Plain Fe-C eutectoid carbon content; the steel relation covers hypoeutectoid steels (C below this) only. */
export const HYPOEUTECTOID_C_MAX_WT_PCT = 0.76;

export type HardnessHVEstimateStatus = "estimate-pavlina-van-tyne-2008" | "unavailable";

export interface HardnessHVEstimate {
  /** Whole-number HV estimate, or null when no defensible relation applies. */
  hv: number | null;
  status: HardnessHVEstimateStatus;
  /** Visible explanation: source and validity range for an estimate, or the reason it is unavailable. */
  note: string;
}

const YS_MIN_MPa = PAVLINA_VAN_TYNE_2008.yield.constant_MPa + PAVLINA_VAN_TYNE_2008.yield.coefficient * PAVLINA_VAN_TYNE_2008.yield.hvMin;
const YS_MAX_MPa = PAVLINA_VAN_TYNE_2008.yield.constant_MPa + PAVLINA_VAN_TYNE_2008.yield.coefficient * PAVLINA_VAN_TYNE_2008.yield.hvMax;

export const HV_FROM_YIELD_ESTIMATE_NOTE =
  "estimate from yield strength per Pavlina & Van Tyne (2008) steel regression (non-austenitic hypoeutectoid steels, HV 129-632, standard error 102 MPa on yield strength); not measured";

/** Shown when "load specimen" leaves the measured-hardness inputs unchanged. */
export const SPECIMEN_HARDNESS_NOT_LOADED_NOTE =
  "Hardness not loaded from the active specimen: its record holds no measured hardness (its HV is an estimate from yield strength or unavailable).";

const unavailable = (reason: string): HardnessHVEstimate => ({ hv: null, status: "unavailable", note: `Unavailable: ${reason}` });

/**
 * Vickers hardness estimated from a yield strength for a non-austenitic, hypoeutectoid steel (inverse of Pavlina &
 * Van Tyne 2008, Table 1 "All data" yield regression). Every other case is unavailable with a reason.
 */
export function estimateSteelHvFromYield(
  yieldStrength_MPa: number | null | undefined,
  scope: { materialClass: HardnessMaterialClass; carbonWtPct: number | null | undefined }
): HardnessHVEstimate {
  if (scope.materialClass !== "non-austenitic-steel") {
    return unavailable(`no verified hardness-strength relation for this alloy class (${hardnessMaterialClassLabel(scope.materialClass)})`);
  }
  const c = scope.carbonWtPct;
  if (c === null || c === undefined || !Number.isFinite(c) || c < 0) {
    return unavailable(`carbon content unknown; the steel relation covers hypoeutectoid steels (C < ${HYPOEUTECTOID_C_MAX_WT_PCT} wt%) only`);
  }
  if (c >= HYPOEUTECTOID_C_MAX_WT_PCT) {
    return unavailable(`C = ${c} wt% is not hypoeutectoid; the steel relation covers C < ${HYPOEUTECTOID_C_MAX_WT_PCT} wt% only`);
  }
  if (yieldStrength_MPa === null || yieldStrength_MPa === undefined || !Number.isFinite(yieldStrength_MPa)) {
    return unavailable("no yield strength");
  }
  const { constant_MPa, coefficient, hvMin, hvMax } = PAVLINA_VAN_TYNE_2008.yield;
  const hv = (yieldStrength_MPa - constant_MPa) / coefficient;
  if (hv < hvMin || hv > hvMax) {
    return unavailable(
      `yield strength ${yieldStrength_MPa} MPa is outside the steel relation's range (HV ${hvMin}-${hvMax}, yield strength about ${Math.round(YS_MIN_MPa)}-${Math.round(YS_MAX_MPa)} MPa)`
    );
  }
  return { hv: Math.round(hv), status: "estimate-pavlina-van-tyne-2008", note: `≈ ${Math.round(hv)} HV: ${HV_FROM_YIELD_ESTIMATE_NOTE}` };
}

/** HV estimate for a material record (base metal, crystal system, wt% composition, yield strength). */
export function estimateSpecimenHardnessHV(spec: {
  baseMetal?: string;
  crystalSystem?: string;
  composition?: Record<string, number>;
  yieldStrength_MPa?: number | null;
}): HardnessHVEstimate {
  return estimateSteelHvFromYield(spec.yieldStrength_MPa, {
    materialClass: hardnessMaterialClassOf({ baseMetal: spec.baseMetal, crystalSystem: spec.crystalSystem }),
    carbonWtPct: spec.composition?.C,
  });
}
