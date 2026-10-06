/**
 * UQ-Lab material presets (no bundled measurements) and descriptive statistics with approximate normal-model
 * one-sided tolerance limits. These calculations do not certify allowables.
 */

export interface CouponTestSpecimen {
  id: string;
  specimenNumber: string;
  heatLotId: string;
  testTempC: number | null;
  yieldStrengthMPa: number;
  utsMPa: number;
  elongationPct: number;
  reductionOfAreaPct: number | null;
  hardnessHRC?: number;
  testStandard: string;
  orientation?: "L" | "LT" | "ST" | "Z";
  evidenceOrigin?: "synthetic" | "user-reported" | "unknown";
}

/**
 * Provenance of a preset's reference minimums. `status` is never "cited" unless the exact table, product form and
 * condition were checked against the specification text; none of the bundled presets meet that bar.
 */
export interface SpecMinimumSource {
  status: "unverified-reference" | "no-source";
  // "no-source": the preset carries no minimums at all (they are null) and every comparison is unavailable.
  /** What the minimums are claimed to refer to, and what was not verified. */
  citation: string;
}

export const SPEC_MINIMUM_LABEL = "Reference minimums (unverified)";
export const SPEC_MINIMUM_UNAVAILABLE = "No sourced minimum; comparison unavailable";
export const SPEC_MINIMUM_BADGE_BASIS = "vs reference minimum (unverified, not a specification check)";

export interface MaterialDataset {
  id: string;
  /**
   * Neutral slug for user-visible file names. Optional: `id` is a stable lookup key shared with the Python alias map
   * (python/alloy_data_kinetics_uq_fatigue.py) and for two presets embeds a specification number that is not verified,
   * so it must not be shown to users.
   */
  displaySlug?: string;
  name: string;
  materialClass: "Superalloy" | "Titanium" | "Aluminum" | "Steel" | "Additive Metal";
  baseMetal: "Ni" | "Fe" | "Ti" | "Al";
  specification: string;
  /** MMPDS chapter that covers this alloy family, or null when no MMPDS chapter is cited for the preset. */
  mmpdsChapter: string | null;
  productForm: string;
  heatTreatment: string;
  /**
   * Reference minimums carried with the preset (used as solver inputs and for the per-coupon comparison).
   * They are NOT tied to a verified table of the named specification; see `specMinSource`.
   */
  specMinYieldMPa: number | null;
  specMinUTSMPa: number | null;
  specMinElongationPct: number | null;
  specMinReductionAreaPct: number | null;
  specMinSource: SpecMinimumSource;
  nominalChemistry: Record<string, number>;
  chemicalTolerances: Record<string, number>;
  nominalThermal: {
    coolingRate_K_s: number;
    coolingRateCov: number;
    agingTemp_C: number;
    agingTempStd: number;
    agingTime_h: number;
    serviceStress_MPa: number;
  };
  description: string;
  coupons: CouponTestSpecimen[];
  /** "none": preset with no coupon records; "uploaded": user-supplied CSV; "synthetic": rows flagged synthetic. */
  couponSource: "none" | "synthetic" | "uploaded";
}

export interface MMPDSEmpiricalAllowableStats {
  sampleSize: number;
  lotCount: number | null;
  status: "ready" | "insufficient-data" | "invalid-data";
  issues: string[];
  toleranceEligible: boolean;
  normality: { status: "not-tested"; method: null; pValue: null; reason: string };
  mean: number | null;
  stdDev: number | null;
  variance: number | null;
  covPct: number | null;
  median: number | null;
  min: number | null;
  max: number | null;
  range: number | null;
  skewness: number | null;
  kurtosis: number | null;
  andersonDarlingPVal: null;
  isNormalDistribution: null;
  mmpds_kA: number | null;
  mmpds_kB: number | null;
  aBasisAllowable: number | null;
  bBasisAllowable: number | null;
  aBasisAllowable95CI: null;
  bBasisAllowable95CI: null;
  standardError_A: null;
  standardError_B: null;
  cpl: number | null;
  conformancePct: number | null;
  marginOfSafetyPct: number | null;
  histogram: {
    binStart: number;
    binEnd: number;
    midpoint: number;
    count: number;
    density: number | null;
  }[];
}

/**
 * Natrella (1963) approximate one-sided normal tolerance factor, as presented
 * by NIST: https://www.itl.nist.gov/div898/handbook/prc/section2/prc263.htm
 * This is not an exact noncentral-t calculation or a certified MMPDS allowable.
 * Only the explicitly tabulated coverage/confidence probabilities are supported.
 * Small samples (n <= 10) can differ materially from the exact method.
 * The legacy export name is retained for callers.
 */
export function calculateMMPDSToleranceFactor(n: number, p: number = 0.99, gamma: number = 0.95): number | null {
  const quantiles: Record<string, number> = {
    "0.9": 1.2815515655446004,
    "0.95": 1.6448536269514722,
    "0.99": 2.3263478740408408,
  };
  const zp = quantiles[String(p)];
  const zGamma = quantiles[String(gamma)];
  if (!Number.isSafeInteger(n) || n < 3 || zp === undefined || zGamma === undefined) return null;
  const a = 1 - zGamma ** 2 / (2 * (n - 1));
  const b = zp ** 2 - zGamma ** 2 / n;
  const discriminant = zp ** 2 - a * b;
  if (a <= 0 || discriminant < 0) return null;
  return finiteOrNull((zp + Math.sqrt(discriminant)) / a);
}

function finiteOrNull(value: number): number | null {
  return Number.isFinite(value) ? value : null;
}

function empiricalHistogram(values: number[], min: number, max: number): MMPDSEmpiricalAllowableStats["histogram"] {
  let edges: number[];
  if (min === max) {
    // A single finite-width bin is sufficient for a point mass. Avoid reversed
    // final bins and preserve all observations, including a constant zero set.
    const padding = Math.max(1, Math.abs(min) * 1e-6);
    const left = Number.isFinite(min - padding) ? min - padding : min;
    const right = Number.isFinite(max + padding) ? max + padding : max;
    edges = [left, right];
  } else {
    const binCount = Math.min(14, Math.max(8, Math.round(Math.sqrt(values.length)) + 2));
    // Remove edges that collapse to the same IEEE-754 value for tiny ranges.
    edges = [...new Set(Array.from({ length: binCount + 1 }, (_, i) =>
      i === binCount ? max : min + (max - min) * (i / binCount)))];
  }
  const histogram = edges.slice(0, -1).map((binStart, i) => ({
    binStart,
    binEnd: edges[i + 1],
    midpoint: binStart + (edges[i + 1] - binStart) / 2,
    count: 0,
    density: null as number | null,
  }));
  for (const value of values) {
    const index = histogram.findIndex((bin, i) => value >= bin.binStart
      && (value < bin.binEnd || (i === histogram.length - 1 && value <= bin.binEnd)));
    if (index >= 0) histogram[index].count += 1;
  }
  for (const bin of histogram) {
    bin.density = finiteOrNull((bin.count / values.length) / (bin.binEnd - bin.binStart));
  }
  return histogram;
}

/**
 * Descriptive sample statistics and conditional normal-model screening limits.
 * No rows are silently dropped. Normality, independence and representative
 * lot sampling are not established by this function. Legacy A/B field names
 * refer only to approximate 99%/95% and 90%/95% lower tolerance limits.
 */
export function computeMMPDSEmpiricalStats(
  values: (number | null)[],
  specMin: number | null,
  lotIds: string[] = []
): MMPDSEmpiricalAllowableStats {
  const n = values.length;
  const issues: string[] = [];
  const result: MMPDSEmpiricalAllowableStats = {
    sampleSize: n,
    lotCount: null,
    status: "insufficient-data",
    issues,
    toleranceEligible: false,
    normality: {
      status: "not-tested", method: null, pValue: null,
      reason: "No validated normality test is implemented; normality and independent representative sampling remain assumptions.",
    },
    mean: null, stdDev: null, variance: null, covPct: null,
    median: null, min: null, max: null, range: null,
    skewness: null, kurtosis: null,
    andersonDarlingPVal: null, isNormalDistribution: null,
    mmpds_kA: null, mmpds_kB: null,
    aBasisAllowable: null, bBasisAllowable: null,
    aBasisAllowable95CI: null, bBasisAllowable95CI: null,
    standardError_A: null, standardError_B: null,
    cpl: null, conformancePct: null, marginOfSafetyPct: null,
    histogram: [],
  };
  if (values.some(value => typeof value !== "number" || !Number.isFinite(value))) {
    issues.push("Every selected property value must be finite and present; no rows were excluded.");
    result.status = "invalid-data";
  }
  // null = no sourced minimum: descriptive statistics still run, minimum-based outputs (Cpl, conformance, margin) stay unavailable.
  const minimum = specMin === null ? null : specMin;
  if (minimum !== null && !Number.isFinite(minimum)) {
    issues.push("The lower specification limit must be finite.");
    result.status = "invalid-data";
  }
  if (lotIds.length > 0) {
    if (lotIds.length !== n || lotIds.some(id => typeof id !== "string" || id.trim().length === 0)) {
      issues.push("Lot IDs must contain one nonempty identifier per selected value.");
      result.status = "invalid-data";
    } else {
      result.lotCount = new Set(lotIds.map(id => id.trim())).size;
    }
  } else {
    issues.push("Lot identifiers were not supplied; lot count and sampling representativeness are unknown.");
  }
  if (result.status === "invalid-data") return result;
  if (n === 0) {
    issues.push("No observations are available.");
    return result;
  }
  // Validation above guarantees the cast; retain the original row count.
  const numericValues = values as number[];
  const sorted = [...numericValues].sort((a, b) => a - b);
  const min = sorted[0];
  const max = sorted[n - 1];
  const range = max - min;
  // Center before summing to preserve tiny scatter around a large offset.
  const mean = min + numericValues.reduce((acc, value) => acc + (value - min) / n, 0);
  const ss = numericValues.reduce((acc, value) => acc + (value - mean) ** 2, 0);
  const variance = n > 1 ? ss / (n - 1) : null;
  if (!Number.isFinite(mean) || !Number.isFinite(range) || (variance !== null && !Number.isFinite(variance))) {
    result.status = "invalid-data";
    issues.push("The selected numeric range exceeds supported floating-point arithmetic.");
    return result;
  }
  const stdDev = variance === null ? null : Math.sqrt(variance);
  Object.assign(result, {
    mean, min, max, range, variance, stdDev,
    median: n % 2 === 0 ? sorted[n / 2 - 1] + (sorted[n / 2] - sorted[n / 2 - 1]) / 2 : sorted[Math.floor(n / 2)],
    covPct: stdDev !== null && mean !== 0 ? finiteOrNull(stdDev / Math.abs(mean) * 100) : null,
    conformancePct: minimum === null ? null : numericValues.filter(value => value >= minimum).length / n * 100,
    histogram: empiricalHistogram(numericValues, min, max),
  });
  if (stdDev !== null && stdDev > 0) {
    const z = numericValues.map(value => (value - mean) / stdDev);
    // Adjusted Fisher-Pearson skewness and bias-corrected excess kurtosis.
    result.skewness = n >= 3 ? finiteOrNull(n / ((n - 1) * (n - 2)) * z.reduce((sum, value) => sum + value ** 3, 0)) : null;
    result.kurtosis = n >= 4 ? finiteOrNull(n * (n + 1) / ((n - 1) * (n - 2) * (n - 3))
      * z.reduce((sum, value) => sum + value ** 4, 0) - 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))) : null;
    result.cpl = minimum === null ? null : finiteOrNull((mean - minimum) / (3 * stdDev));
  }
  if (n < 3) issues.push("At least three observations are needed for the approximate tolerance calculation.");
  if (stdDev === 0) issues.push("Zero sample variance cannot establish a tolerance limit or capability index.");
  if (n >= 3 && stdDev !== null && stdDev > 0) {
    const kA = calculateMMPDSToleranceFactor(n, 0.99, 0.95);
    const kB = calculateMMPDSToleranceFactor(n, 0.90, 0.95);
    const aBasis = kA === null ? null : finiteOrNull(mean - kA * stdDev);
    const bBasis = kB === null ? null : finiteOrNull(mean - kB * stdDev);
    if (aBasis !== null && bBasis !== null) {
      Object.assign(result, {
        status: "ready", toleranceEligible: true,
        mmpds_kA: kA, mmpds_kB: kB,
        aBasisAllowable: aBasis, bBasisAllowable: bBasis,
        marginOfSafetyPct: minimum !== null && minimum > 0 ? finiteOrNull((aBasis - minimum) / minimum * 100) : null,
      });
      if (n <= 10) issues.push("For n <= 10, this approximation can differ materially from the exact noncentral-t method.");
    } else {
      issues.push("The approximate tolerance calculation is outside its supported numeric range.");
    }
  }
  return result;
}
/** True only when the preset carries all three minimums; otherwise every minimum-based comparison is unavailable. */
export function hasSourcedMinimums(dataset: Pick<MaterialDataset, "specMinYieldMPa" | "specMinUTSMPa" | "specMinElongationPct">): boolean {
  return dataset.specMinYieldMPa !== null && dataset.specMinUTSMPa !== null && dataset.specMinElongationPct !== null;
}

export function datasetExportSlug(dataset: Pick<MaterialDataset, "id" | "displaySlug">): string {
  return dataset.displaySlug ?? dataset.id;
}

export function isSyntheticCouponDataset(dataset: MaterialDataset): boolean {
  return dataset.couponSource === "synthetic" || dataset.coupons.some(c => c.evidenceOrigin === "synthetic");
}

// --------------------------------------------------------------------------
// MATERIAL CONTEXT PRESETS. They carry spec context and illustrative solver
// inputs only. No coupon measurements are bundled: upload a coupon CSV.
// --------------------------------------------------------------------------

export const AEROSPACE_MATERIAL_DATASETS: MaterialDataset[] = [
  {
    id: "inconel718-ams5664",
    name: "Inconel 718 Forged Turbine Disks (AMS 5664)",
    materialClass: "Superalloy",
    baseMetal: "Ni",
    specification: "AMS 5664 / MMPDS-01 Ch. 6",
    mmpdsChapter: null, // MMPDS chapter title/number not verified against the handbook; none is cited.
    productForm: "Forged Bar & Ring (Section <= 5.00 in)",
    heatTreatment: "Solution 980°C / 1h + Age 720°C / 8h + Furnace Cool to 620°C / 8h",
    specMinYieldMPa: 1103, // 160 ksi
    specMinUTSMPa: 1379, // 200 ksi
    specMinElongationPct: 12.0,
    specMinReductionAreaPct: 15.0,
    specMinSource: { status: "unverified-reference", citation: "AMS 5664 (SAE), Inconel 718 forgings/bar: values are preset reference numbers; the governing table, product form and test direction were not verified against the specification text. Confirm against the controlling document before use." },
    nominalChemistry: { Cr: 19.0, Fe: 18.0, Nb: 5.1, Mo: 3.05, Ti: 0.95, Al: 0.52, C: 0.04, Si: 0.18 },
    chemicalTolerances: { Cr: 1.0, Fe: 1.0, Nb: 0.35, Mo: 0.30, Ti: 0.15, Al: 0.10, C: 0.015, Si: 0.08 },
    nominalThermal: {
      coolingRate_K_s: 150000,
      coolingRateCov: 0.25,
      agingTemp_C: 720,
      agingTempStd: 6.0,
      agingTime_h: 8,
      serviceStress_MPa: 780
    },
    description: "Forged nickel superalloy preset. Carries no coupon data; upload a coupon CSV.",
    coupons: [],
    couponSource: "none"
  },
  {
    id: "ti64-ams4928",
    name: "Ti-6Al-4V Grade 5 Airframe Billets (AMS 4928)",
    materialClass: "Titanium",
    baseMetal: "Ti",
    specification: "AMS 4928 / MIL-T-9047",
    mmpdsChapter: null, // MMPDS chapter title/number not verified against the handbook; none is cited.
    productForm: "Rolled & Annealed Airframe Structural Billet",
    heatTreatment: "Alpha-Beta Anneal 730°C / 2h Air Cool",
    specMinYieldMPa: 828, // 120 ksi
    specMinUTSMPa: 896, // 130 ksi
    specMinElongationPct: 10.0,
    specMinReductionAreaPct: 25.0,
    specMinSource: { status: "unverified-reference", citation: "AMS 4928 (SAE), Ti-6Al-4V annealed bar: values are preset reference numbers; the governing table, product form and test direction were not verified against the specification text. Confirm against the controlling document before use." },
    nominalChemistry: { Al: 6.1, V: 4.05, Fe: 0.22, C: 0.035, O: 0.16, N: 0.015 },
    chemicalTolerances: { Al: 0.35, V: 0.30, Fe: 0.08, C: 0.015, O: 0.03, N: 0.008 },
    nominalThermal: {
      coolingRate_K_s: 250000,
      coolingRateCov: 0.30,
      agingTemp_C: 550,
      agingTempStd: 8.0,
      agingTime_h: 4,
      serviceStress_MPa: 620
    },
    description: "Ti-6Al-4V airframe billet preset: specification context only, no batch data bundled. Upload a coupon CSV.",
    coupons: [],
    couponSource: "none"
  },
  {
    id: "al7075-t651",
    name: "Al 7075-T651 Aerospace Plate (AMS 4045)",
    materialClass: "Aluminum",
    baseMetal: "Al",
    specification: "AMS 4045 / MMPDS-01 Ch. 3",
    mmpdsChapter: null, // MMPDS chapter title/number not verified against the handbook; none is cited.
    productForm: "Stretched & Artificially Aged Plate (t = 1.000 to 2.000 in)",
    heatTreatment: "Solution 470°C / Water Quench + Age 120°C / 24h",
    specMinYieldMPa: 462, // 67 ksi (L)
    specMinUTSMPa: 538, // 78 ksi (L)
    specMinElongationPct: 7.0,
    specMinReductionAreaPct: 14.0,
    specMinSource: { status: "unverified-reference", citation: "AMS 4045 (SAE), Al 7075-T651 plate; the (L) direction note refers to longitudinal minimums: values are preset reference numbers; the governing table, product form and test direction were not verified against the specification text. Confirm against the controlling document before use." },
    nominalChemistry: { Zn: 5.6, Mg: 2.5, Cu: 1.6, Cr: 0.23, Fe: 0.28, Si: 0.18, Mn: 0.10 },
    chemicalTolerances: { Zn: 0.40, Mg: 0.25, Cu: 0.20, Cr: 0.05, Fe: 0.08, Si: 0.06, Mn: 0.04 },
    nominalThermal: {
      coolingRate_K_s: 450000,
      coolingRateCov: 0.20,
      agingTemp_C: 120,
      agingTempStd: 3.0,
      agingTime_h: 24,
      serviceStress_MPa: 340
    },
    description: "Al 7075-T651 plate preset: specification context only, no lot data bundled. Upload a coupon CSV.",
    coupons: [],
    couponSource: "none"
  },
  {
    id: "steel4340-ams6414",
    name: "AISI 4340 Ultra-High Strength VAR (AMS 6414)",
    materialClass: "Steel",
    baseMetal: "Fe",
    specification: "AMS 6414 / MMPDS-01 Ch. 2",
    mmpdsChapter: null, // MMPDS chapter title/number not verified against the handbook; none is cited.
    productForm: "Vacuum Arc Remelted (VAR) Landing Gear Bar Stock",
    heatTreatment: "Austenitize 845°C / Oil Quench + Temper 480°C / 2h",
    specMinYieldMPa: 1379, // 200 ksi
    specMinUTSMPa: 1517, // 220 ksi
    specMinElongationPct: 9.0,
    specMinReductionAreaPct: 35.0,
    specMinSource: { status: "unverified-reference", citation: "AMS 6414 (SAE), 4340 VAR bar: values are preset reference numbers; the governing table, product form and test direction were not verified against the specification text. Confirm against the controlling document before use." },
    nominalChemistry: { C: 0.40, Cr: 0.82, Ni: 1.82, Mo: 0.26, Mn: 0.72, Si: 0.25 },
    chemicalTolerances: { C: 0.03, Cr: 0.10, Ni: 0.15, Mo: 0.05, Mn: 0.08, Si: 0.05 },
    nominalThermal: {
      coolingRate_K_s: 250,
      coolingRateCov: 0.15,
      agingTemp_C: 480,
      agingTempStd: 5.0,
      agingTime_h: 2,
      serviceStress_MPa: 950
    },
    description: "AISI 4340 VAR bar preset: specification context only, no heat data bundled. Upload a coupon CSV.",
    coupons: [],
    couponSource: "none"
  },
  {
    id: "alsi10mg-lpbf-ams4215", // stable key shared with the Python alias map and golden case; not shown to users (see displaySlug)
    displaySlug: "alsi10mg-lpbf",
    name: "AlSi10Mg Additive LPBF As-Built & SR (ASTM F3318)",
    materialClass: "Additive Metal",
    baseMetal: "Al",
    specification: "ASTM F3318 (AlSi10Mg powder bed fusion; minimums not sourced)",
    mmpdsChapter: null, // No MMPDS chapter is cited for this additive preset.
    productForm: "Laser Powder Bed Fusion (LPBF) Additive Build Jobs",
    heatTreatment: "Stress Relief 300°C / 2h Air Cool (Retaining fine cellular Si-eutectic)",
    specMinYieldMPa: null,
    specMinUTSMPa: null,
    specMinElongationPct: null,
    specMinReductionAreaPct: null,
    specMinSource: { status: "no-source", citation: "No sourced minimum is known for this preset: ASTM F3318 was not checked, so no minimum is shown, no coupon is graded and no Cpl or margin is computed." },
    nominalChemistry: { Si: 10.0, Mg: 0.45, Fe: 0.14, Ti: 0.04, Mn: 0.02 },
    chemicalTolerances: { Si: 0.50, Mg: 0.08, Fe: 0.04, Ti: 0.02, Mn: 0.01 },
    nominalThermal: {
      coolingRate_K_s: 600000,
      coolingRateCov: 0.35,
      agingTemp_C: 160,
      agingTempStd: 4.0,
      agingTime_h: 6,
      serviceStress_MPa: 180
    },
    description: "AlSi10Mg LPBF preset: specification context only, no build data bundled. Upload a coupon CSV.",
    coupons: [],
    couponSource: "none"
  },
  {
    id: "hastelloy-x-ams5754", // stable key; not shown to users (see displaySlug)
    displaySlug: "hastelloy-x-sheet",
    name: "Hastelloy X Combustor Sheet",
    materialClass: "Superalloy",
    baseMetal: "Ni",
    specification: "Hastelloy X sheet (governing specification not verified)",
    mmpdsChapter: null, // MMPDS chapter title/number not verified against the handbook; none is cited.
    productForm: "Cold Rolled & Solution Heat Treated Sheet (t = 0.063 in)",
    heatTreatment: "Solution Anneal 1177°C / Rapid Air Cool",
    specMinYieldMPa: null,
    specMinUTSMPa: null,
    specMinElongationPct: null,
    specMinReductionAreaPct: null,
    specMinSource: { status: "no-source", citation: "No sourced minimum: the former AMS 5754 pairing is dropped because that specification is understood to cover bar, forgings and rings, not the sheet form of this preset, and no sheet specification table was checked. No minimum is shown, no coupon is graded and no Cpl or margin is computed." },
    nominalChemistry: { Cr: 22.0, Fe: 18.5, Mo: 9.0, Co: 1.5, W: 0.6, C: 0.08, Si: 0.40 },
    chemicalTolerances: { Cr: 1.2, Fe: 1.2, Mo: 0.6, Co: 0.4, W: 0.2, C: 0.02, Si: 0.15 },
    nominalThermal: {
      coolingRate_K_s: 120000,
      coolingRateCov: 0.22,
      agingTemp_C: 650,
      agingTempStd: 7.0,
      agingTime_h: 4,
      serviceStress_MPa: 240
    },
    description: "Hastelloy X sheet preset: specification context only, no lot data bundled. Upload a coupon CSV.",
    coupons: [],
    couponSource: "none"
  }
];

export { parseCSVToCoupons, exportCouponsToCSV } from "../utils/uqCouponCsv";
