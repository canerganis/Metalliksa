import type { MmpdsBasisResult, QualificationTestEvaluation } from "../types";
import { screeningToleranceFactors } from "./toleranceFactors";

/**
 * Pure screening logic extracted verbatim from StandardQualificationEngine.tsx.
 * Everything here is a slider-driven engineering ESTIMATE. It is not an MMPDS
 * handbook allowable, a certificate, or a pass/fail test result.
 */

export interface QualificationMmpdsInputs {
  meanYieldMpa: number;
  meanTensileMpa: number;
  fractureToughnessMpaM: number;
  sampleSizeN: number;
  customScatterCv: number;
}

export function computeQualificationMmpdsStats(inputs: QualificationMmpdsInputs): MmpdsBasisResult {
  const { meanYieldMpa, meanTensileMpa, fractureToughnessMpaM, sampleSizeN, customScatterCv } = inputs;
  const N = Math.max(10, sampleSizeN);
  const cov = Math.max(1.0, customScatterCv) / 100;
  const stdDev = meanYieldMpa * cov;

  // MMPDS One-Sided Tolerance Limit Factors:
  // A-Basis: 99% probability with 95% confidence
  // B-Basis: 90% probability with 95% confidence
  // Classical Natrella / Lieberman-Resnikoff approximation k = (z_p + sqrt(z_p^2 - a b)) / a, shared with
  // AerospaceAuditReportGenerator. (Until 2026-10 this screen divided only the sqrt term by a, which made
  // k_A / k_B 2-11 % too small, i.e. optimistic allowables; see tests/utils-tolerance-factor.test.ts.)
  const { kA, kB } = screeningToleranceFactors(N);

  // A-Basis & B-Basis Yield Strength
  const aBasisYield = Math.max(0, Math.round(meanYieldMpa - kA * stdDev));
  const bBasisYield = Math.max(0, Math.round(meanYieldMpa - kB * stdDev));
  const sBasisYield = Math.max(0, Math.round(meanYieldMpa - 3.0 * stdDev));

  // Tensile Allowables
  const stdDevTensile = meanTensileMpa * cov;
  const aBasisTensile = Math.max(0, Math.round(meanTensileMpa - kA * stdDevTensile));
  const bBasisTensile = Math.max(0, Math.round(meanTensileMpa - kB * stdDevTensile));

  // Secondary MMPDS Derived Allowables
  const shearUltimate = Math.round(aBasisTensile * 0.60);
  const bearingYield = Math.round(aBasisYield * 1.50); // e/D = 1.5
  const bearingUltimate = Math.round(aBasisTensile * 2.00); // e/D = 2.0
  const compressiveYield = Math.round(aBasisYield * 1.04);

  // Process Capability Cpk (assuming specification lower limit is nominal - 15%)
  const specLowerLimit = meanYieldMpa * 0.85;
  const cpk = Number(((meanYieldMpa - specLowerLimit) / (3 * stdDev)).toFixed(2));

  let status: "A-Basis Qualified" | "B-Basis Qualified" | "S-Basis Provisional" | "Insufficient Sampling" = "A-Basis Qualified";
  if (N < 30) {
    status = "S-Basis Provisional";
  } else if (cpk < 1.33 || cov > 0.06) {
    status = "B-Basis Qualified";
  }

  return {
    meanYield: meanYieldMpa,
    meanTensile: meanTensileMpa,
    stdDev: Math.round(stdDev),
    covPct: Number((cov * 100).toFixed(2)),
    sampleSize: N,
    kA,
    kB,
    aBasisYield,
    bBasisYield,
    sBasisYield,
    aBasisTensile,
    bBasisTensile,
    shearUltimate,
    bearingYield,
    bearingUltimate,
    compressiveYield,
    fractureToughnessKic: fractureToughnessMpaM,
    cpk,
    status,
  };
}

export interface QualificationChecklistInputs {
  fractureToughnessMpaM: number;
  serviceTempMin: number;
  serviceTempMax: number;
  operatingStressMpa: number;
  /** Slider-derived Cpk from computeQualificationMmpdsStats (mmpdsStats.cpk). */
  cpk: number;
}

// Qualification protocol checklist (template only: never auto-PASS; every row is "Not executed").
export function buildQualificationChecklist(inputs: QualificationChecklistInputs): QualificationTestEvaluation[] {
  const { fractureToughnessMpaM, serviceTempMin, serviceTempMax, operatingStressMpa } = inputs;
  const mmpdsStats = { cpk: inputs.cpk };
  return [
    {
      id: "mil-salt-fog",
      standard: "MIL-STD-810H",
      methodName: "Method 509.7: Salt Fog Marine Corrosion (5% NaCl)",
      testCategory: "Salt Fog / Marine",
      passProbabilityPct: 0,
      riskLevel: "Low",
      primaryThreat: "Not evaluated — laboratory salt fog is required",
      criticalThreshold: "168 - 336 hrs Continuous Salt Spray (user-attested)",
      mitigationRecommendation: "Checklist item only. This software does not confirm Method 509.7 execution.",
      executionStatus: "Not executed",
    },
    {
      id: "mil-shock",
      standard: "MIL-STD-810H",
      methodName: "Method 516.8: Mechanical Shock and Pyrotechnic Drop (100g/6ms)",
      testCategory: "Mechanical Shock",
      passProbabilityPct: 0,
      riskLevel: "Low",
      primaryThreat: "Not evaluated — shock table data is required",
      criticalThreshold: `User-entered K_IC: ${fractureToughnessMpaM} MPa√m (not a test result)`,
      mitigationRecommendation: "Checklist item only. Fracture toughness sliders do not constitute Method 516.8 PASS.",
      executionStatus: "Not executed",
    },
    {
      id: "mil-thermal-shock",
      standard: "MIL-STD-810H",
      methodName: "Method 503.7: Thermal Shock and Temperature Cycling",
      testCategory: "Thermal Shock",
      passProbabilityPct: 0,
      riskLevel: "Low",
      primaryThreat: "Not evaluated — thermal-cycle testing is required",
      criticalThreshold: `Entered ΔT: ${serviceTempMax - serviceTempMin}°C (user input)`,
      mitigationRecommendation: "Checklist item only. Temperature sliders do not confirm Method 503.7.",
      executionStatus: "Not executed",
    },
    {
      id: "mil-vibration",
      standard: "MIL-STD-810H",
      methodName: "Method 514.8: High-G Random Vibration and Acoustic Fatigue",
      testCategory: "Vibration / High-G",
      passProbabilityPct: 0,
      riskLevel: "Low",
      primaryThreat: "Not evaluated — shaker / acoustic data is required",
      criticalThreshold: `Entered operating stress: ${operatingStressMpa} MPa (user input)`,
      mitigationRecommendation: "Checklist item only. This software does not confirm Method 514.8 execution.",
      executionStatus: "Not executed",
    },
    {
      id: "as9100-cpk",
      standard: "AS9100 Rev D",
      methodName: "Clause 8.5.1: Process Capability Index (Cpk) — template only",
      testCategory: "Process Capability",
      passProbabilityPct: 0,
      riskLevel: "Low",
      primaryThreat: "Not evaluated — production lot evidence is required",
      criticalThreshold: `Slider Cpk: ${mmpdsStats.cpk} (not AS9100 evidence)`,
      mitigationRecommendation: "Checklist item only. Slider Cpk is not an AS9100 lot release.",
      executionStatus: "Not executed",
    },
    {
      id: "nato-scc",
      standard: "NATO STANAG",
      methodName: "STANAG 4370 / MIL-STD-1568: Environmental Stress Corrosion Cracking (SCC)",
      testCategory: "SCC Threshold",
      passProbabilityPct: 0,
      riskLevel: "Low",
      primaryThreat: "Not evaluated — SCC specimens are required",
      criticalThreshold: "User-attested K_ISCC test only",
      mitigationRecommendation: "Checklist item only. PREN / alloy presets do not confirm STANAG SCC.",
      executionStatus: "Not executed",
    },
  ];
}
