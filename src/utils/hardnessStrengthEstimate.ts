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
//   Data-set references 9-28 are Colorado School of Mines theses on carbon and low-alloy steels only: low-carbon
//   martensite, microalloyed bar/forging steels, HSLA-100 (about 3.5 Ni, 1.6 Cu), A514, API-2Y plate, 4140, 5160,
//   SAE 1012, dual-phase, fire-resistant and medium-carbon steels. No stainless, maraging or high-alloy tool steel.
//
// HV from yield strength inverts the yield regression; it is not a separate fit (HV on YS), and the standard error of
// 102 MPa on YS corresponds to about +-35 HV (102 / 2.876). Outside the scope below the estimate is unavailable (no
// extrapolation, no clamping).
//
// Scope gate (this tool's limits, chosen from the data-set titles above; the paper itself states no composition
// limits): non-austenitic class, C < 0.76 wt% (hypoeutectoid; Fe-C eutectoid at 0.76 wt% C, Callister; alloy shifts
// not modelled), and none of: Cr >= 10.5 (stainless steel by the EN 10088-1 definition), Ni >= 5, Co >= 1 (maraging
// type), Cr >= 3, Mo >= 1.5, W >= 1, V >= 0.5 (tool / high-alloy steels), Mn >= 3 (high-/medium-Mn steels).
// A naive total-alloy cap is not used: HSLA-100 is inside the data set.
//
// Why the old constants were dropped: HV = YS/3.1 means YS(MPa) = 3.1 HV(kgf/mm2), i.e. a Tabor-like constraint factor
// c = 9.807 / 3.1 ~ 3.16 in consistent units; YS/2.9 and YS/3.05 sit in the same 2.8-3.2 spread. They are not a units
// error. They were removed because they had no source, applied the Tabor flow stress (at about 8 % strain) to the 0.2 %
// yield strength, and had no alloy class or range scope. Do not "correct" the code toward the literal sentence in P's
// introduction (c ~ 3 "when H is measured in kgf/mm2 and S in MPa"): read literally it gives S = HV/3, a units slip;
// consistent units give sigma(MPa) ~ HV x 9.807 / 3 ~ 3.27 HV. The removed HV = UTS/3.1, YS/3 + 35 and YS/3 + 30 had no
// source either.
//
// Possible future class (not implemented): S. Matsuoka, Trans. JSME A 70(698) (2004) 1535-1541, 0.2 % proof stress vs
// HV for wrought and cold-worked SUS316 (HV 144-358). It is not validated for LPBF 316L, so austenitic stays unavailable.

import { hardnessMaterialClassLabel, hardnessMaterialClassOf, type HardnessMaterialClass } from "./hardnessConversion";

export const PAVLINA_VAN_TYNE_2008 = {
  citation: "Pavlina & Van Tyne, J. Mater. Eng. Perform. 17 (2008) 888-893, Table 1 (All data)",
  yield: { constant_MPa: -90.7, coefficient: 2.876, standardError_MPa: 102, hvMin: 129, hvMax: 632 },
  tensile: { constant_MPa: -99.8, coefficient: 3.734, standardError_MPa: 112, hvMin: 129, hvMax: 592 },
} as const;

/** Plain Fe-C eutectoid carbon content; the steel relation covers hypoeutectoid steels (C below this) only. */
export const HYPOEUTECTOID_C_MAX_WT_PCT = 0.76;

/**
 * Element limits (wt%) of this tool's low-alloy scope for the steel regression; at or above any of them the estimate is
 * unavailable. Not stated by the paper: chosen from its data-set references (carbon and low-alloy steels, HSLA-100).
 */
export const LOW_ALLOY_SCOPE_LIMITS: ReadonlyArray<{ element: string; limit: number; reason: string }> = [
  { element: "Cr", limit: 10.5, reason: "stainless steel (EN 10088-1: Cr >= 10.5 wt%)" },
  { element: "Ni", limit: 5, reason: "high-nickel / maraging-type steel" },
  { element: "Co", limit: 1, reason: "cobalt-alloyed (maraging-type) steel" },
  { element: "Cr", limit: 3, reason: "high-chromium tool / heat-resistant steel" },
  { element: "Mo", limit: 1.5, reason: "high-molybdenum tool steel" },
  { element: "W", limit: 1, reason: "tungsten tool / high-speed steel" },
  { element: "V", limit: 0.5, reason: "vanadium tool / high-speed steel" },
  { element: "Mn", limit: 3, reason: "high- or medium-manganese steel" },
];

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
  "estimate from yield strength by inverting the Pavlina & Van Tyne (2008) steel regression (carbon and low-alloy steels, HV 129-632; standard error 102 MPa on yield strength, about ±35 HV); not measured";

/** Shown when "load specimen" leaves the measured-hardness inputs unchanged. */
export const SPECIMEN_HARDNESS_NOT_LOADED_NOTE =
  "Hardness not loaded from the active specimen: its record holds no measured hardness (its HV is an estimate from yield strength or unavailable).";

/** One wording for both specimen stores when the composition is in atomic percent. */
export const AT_PCT_HARDNESS_UNAVAILABLE_NOTE =
  "Unavailable: atomic-percent composition; the weight-percent hardness estimate is not evaluated";

const unavailable = (reason: string): HardnessHVEstimate => ({ hv: null, status: "unavailable", note: `Unavailable: ${reason}` });

/** First low-alloy scope limit that a wt% composition reaches, or null when inside the scope. */
export function lowAlloyScopeViolation(composition: Record<string, number>): string | null {
  for (const { element, limit, reason } of LOW_ALLOY_SCOPE_LIMITS) {
    const v = composition[element];
    if (typeof v === "number" && Number.isFinite(v) && v >= limit) {
      return `outside the regression's data set (carbon and low-alloy steels only): ${element} ${v} wt% >= ${limit}, ${reason}`;
    }
  }
  return null;
}

/**
 * Vickers hardness estimated from a yield strength for a carbon or low-alloy, non-austenitic, hypoeutectoid steel
 * (inverse of Pavlina & Van Tyne 2008, Table 1 "All data" yield regression). Every other case is unavailable with a
 * reason. `composition` is in wt%; without it the estimate is unavailable.
 */
export function estimateSteelHvFromYield(
  yieldStrength_MPa: number | null | undefined,
  scope: { materialClass: HardnessMaterialClass; composition: Record<string, number> | null | undefined }
): HardnessHVEstimate {
  if (scope.materialClass !== "non-austenitic-steel") {
    return unavailable(`no verified hardness-strength relation for this alloy class (${hardnessMaterialClassLabel(scope.materialClass)})`);
  }
  const comp = scope.composition;
  const c = comp?.C;
  if (!comp || c === null || c === undefined || !Number.isFinite(c) || c < 0) {
    return unavailable(`carbon content unknown; the steel relation covers hypoeutectoid steels (C < ${HYPOEUTECTOID_C_MAX_WT_PCT} wt%) only`);
  }
  if (c >= HYPOEUTECTOID_C_MAX_WT_PCT) {
    return unavailable(`C = ${c} wt% is not hypoeutectoid; the steel relation covers C < ${HYPOEUTECTOID_C_MAX_WT_PCT} wt% only`);
  }
  const outOfScope = lowAlloyScopeViolation(comp);
  if (outOfScope) return unavailable(outOfScope);
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

/** HV estimate for a material record (base metal, crystal system, composition and its unit, yield strength). */
export function estimateSpecimenHardnessHV(spec: {
  baseMetal?: string;
  crystalSystem?: string;
  composition?: Record<string, number>;
  unit?: string;
  yieldStrength_MPa?: number | null;
}): HardnessHVEstimate {
  if (spec.unit === "at_pct") return { hv: null, status: "unavailable", note: AT_PCT_HARDNESS_UNAVAILABLE_NOTE };
  return estimateSteelHvFromYield(spec.yieldStrength_MPa, {
    materialClass: hardnessMaterialClassOf({ baseMetal: spec.baseMetal, crystalSystem: spec.crystalSystem }),
    composition: spec.composition,
  });
}
