/**
 * Pure screening logic extracted verbatim from AerospaceAuditReportGenerator.tsx.
 * Slider-derived engineering ESTIMATES only: not MMPDS handbook allowables, not a
 * certificate, not a pass/fail test result.
 */

import { screeningToleranceFactors } from "./toleranceFactors";

export interface AerospaceScreeningInputs {
  meanYieldMpa: number;
  meanTensileMpa: number;
  sampleSizeN: number;
  scatterCvPct: number;
}

export function computeAerospaceScreeningStats({ meanYieldMpa, meanTensileMpa, sampleSizeN, scatterCvPct }: AerospaceScreeningInputs) {
  const N = Math.max(10, sampleSizeN);
  const cov = Math.max(1.0, scatterCvPct) / 100;
  const stdDev = meanYieldMpa * cov;

  // Natrella one-sided tolerance factors (shared with StandardQualificationEngine; same expression and rounding).
  const { kA, kB } = screeningToleranceFactors(N);

  const aBasisYield = Math.max(0, Math.round(meanYieldMpa - kA * stdDev));
  const bBasisYield = Math.max(0, Math.round(meanYieldMpa - kB * stdDev));

  const stdDevTensile = meanTensileMpa * cov;
  const aBasisTensile = Math.max(0, Math.round(meanTensileMpa - kA * stdDevTensile));
  const bBasisTensile = Math.max(0, Math.round(meanTensileMpa - kB * stdDevTensile));

  const shearUltimate = Math.round(aBasisTensile * 0.6);
  const bearingYield = Math.round(aBasisYield * 1.5);
  const bearingUltimate = Math.round(aBasisTensile * 2.0);
  const compressiveYield = Math.round(aBasisYield * 1.04);

  const specLower = meanYieldMpa * 0.85;
  const cpk = Number(((meanYieldMpa - specLower) / (3 * stdDev)).toFixed(2));

  return {
    kA,
    kB,
    aBasisYield,
    bBasisYield,
    aBasisTensile,
    bBasisTensile,
    shearUltimate,
    bearingYield,
    bearingUltimate,
    compressiveYield,
    cpk,
    status: "Screening estimate (not MMPDS handbook)",
  };
}

export interface AerospaceChecklistInputs {
  fractureToughnessMpaM: number;
  serviceTempMin: number;
  serviceTempMax: number;
  operatingStressMpa: number;
  /** Slider-derived Cpk (mmpdsStats.cpk). */
  cpk: number;
}

// Qualification protocol checklist (not auto-PASS from sliders)
export function buildAerospaceChecklist({ fractureToughnessMpaM, serviceTempMin, serviceTempMax, operatingStressMpa, cpk }: AerospaceChecklistInputs) {
  const mmpdsStats = { cpk };
  return [
    {
      standard: "MIL-STD-810H",
      methodName: "Method 509.7: Salt Fog Marine Corrosion Resistance (336h 5% NaCl)",
      testCategory: "Corrosion & Marine Passivity",
      passProbabilityPct: 0,
      riskLevel: "Not executed",
      primaryThreat: "Not evaluated in software",
      criticalThreshold: "User-attested laboratory exposure only",
      mitigationRecommendation: "Checklist item — this app does not confirm salt-fog testing.",
      executionStatus: "Not executed",
    },
    {
      standard: "MIL-STD-810H",
      methodName: "Method 516.8: Mechanical Shock & Dynamic Impact (100g / 6ms Sawtooth)",
      testCategory: "Mechanical Dynamic Shock",
      passProbabilityPct: 0,
      riskLevel: "Not executed",
      primaryThreat: "Not evaluated in software",
      criticalThreshold: `Reference K_IC input: ${fractureToughnessMpaM} MPa√m (not a test result)`,
      mitigationRecommendation: "Checklist item — shock spectra are not confirmed by this software.",
      executionStatus: "Not executed",
    },
    {
      standard: "MIL-STD-810H",
      methodName: "Method 503.7: Multi-Cycle Thermal Shock",
      testCategory: "Thermal Expansion & CTE Strain",
      passProbabilityPct: 0,
      riskLevel: "Not executed",
      primaryThreat: "Not evaluated in software",
      criticalThreshold: `Entered ΔT: ${serviceTempMax - serviceTempMin}°C (user input, not a test)`,
      mitigationRecommendation: "Checklist item — thermal-shock testing is not confirmed by this software.",
      executionStatus: "Not executed",
    },
    {
      standard: "MIL-STD-810H",
      methodName: "Method 514.8: High-G Random Vibration & Acoustic Fatigue",
      testCategory: "High-Cycle Fatigue (HCF)",
      passProbabilityPct: 0,
      riskLevel: "Not executed",
      primaryThreat: "Not evaluated in software",
      criticalThreshold: `Entered operating stress: ${operatingStressMpa} MPa (user input)`,
      mitigationRecommendation: "Checklist item — vibration testing is not confirmed by this software.",
      executionStatus: "Not executed",
    },
    {
      standard: "AS9100 Rev D",
      methodName: "Clause 8.5.1: Process Capability Index (Cpk) — template only",
      testCategory: "Statistical Process Quality",
      passProbabilityPct: 0,
      riskLevel: "Not executed",
      primaryThreat: "Not evaluated in software",
      criticalThreshold: `Computed Cpk from sliders: ${mmpdsStats.cpk} (not AS9100 evidence)`,
      mitigationRecommendation: "Checklist item — Cpk from screening sliders is not an AS9100 lot release.",
      executionStatus: "Not executed",
    },
    {
      standard: "NATO STANAG",
      methodName: "STANAG 4370 / ASTM G38: Stress Corrosion Cracking (SCC) — template only",
      testCategory: "SCC Threshold & Marine Passivity",
      passProbabilityPct: 0,
      riskLevel: "Not executed",
      primaryThreat: "Not evaluated in software",
      criticalThreshold: "User-attested SCC test only",
      mitigationRecommendation: "Checklist item — SCC immunity is not confirmed by this software.",
      executionStatus: "Not executed",
    },
  ];
}
