import {
  CarbonEquivalentResult,
  DiffusionResult,
  SchaefflerResult,
  TransformationTempsResult,
  XrdPeak,
} from "../types";

// Error function approximation (Abramowitz and Stegun 7.1.26, max error 1.5e-7)
export function erf(x: number): number {
  const sign = x >= 0 ? 1 : -1;
  const absX = Math.abs(x);

  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;

  const t = 1.0 / (1.0 + p * absX);
  const y =
    1.0 -
    ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-absX * absX);

  return sign * y;
}

// Inverse Error Function approximation for case depth at specific carbon level
export function erfinv(x: number): number {
  const a = 0.147;
  const logTerm = Math.log(1 - x * x);
  const term1 = 2 / (Math.PI * a) + logTerm / 2;
  const innerSqrt = term1 * term1 - logTerm / a;
  const sign = x < 0 ? -1 : 1;
  return sign * Math.sqrt(Math.sqrt(innerSqrt) - term1);
}

// --- 1. Hardness conversion: moved to ./hardnessConversion (convertSteelHardness, shared with the unit converter) ---

// --- 2. Carbon Equivalents & heuristic preheat estimate (NOT an AWS D1.1 procedure) ---
export interface CompositionInput {
  C: number;
  Mn: number;
  Si?: number;
  Cr?: number;
  Ni?: number;
  Mo?: number;
  V?: number;
  Cu?: number;
  Nb?: number;
  B?: number;
  N?: number;
  W?: number;
  Co?: number;
}

export function calculateCarbonEquivalent(
  comp: CompositionInput,
  thicknessMm: number = 25
): CarbonEquivalentResult {
  const C = comp.C || 0;
  const Mn = comp.Mn || 0;
  const Si = comp.Si || 0;
  const Cr = comp.Cr || 0;
  const Ni = comp.Ni || 0;
  const Mo = comp.Mo || 0;
  const V = comp.V || 0;
  const Cu = comp.Cu || 0;
  const Nb = comp.Nb || 0;
  const B = comp.B || 0;

  // IIW Formula: CE = C + Mn/6 + (Cr+Mo+V)/5 + (Ni+Cu)/15
  const ceIIW = Number((C + Mn / 6 + (Cr + Mo + V) / 5 + (Ni + Cu) / 15).toFixed(3));

  // Ito-Besseyo Formula for lower carbon steels: Pcm = C + Si/30 + (Mn+Cu+Cr)/20 + Ni/60 + Mo/15 + V/10 + 5B
  const pcm = Number(
    (C + Si / 30 + (Mn + Cu + Cr) / 20 + Ni / 60 + Mo / 15 + V / 10 + 5 * B).toFixed(3)
  );

  // Yurioka CEN Formula
  const A_C = 0.75 + 0.25 * Math.tanh(20 * (C - 0.12));
  const cen = Number(
    (C + A_C * (Si / 24 + Mn / 6 + Cu / 15 + Ni / 20 + (Cr + Mo + V + Nb) / 5 + 5 * B)).toFixed(3)
  );

  let weldabilityLevel: CarbonEquivalentResult["weldabilityLevel"] = "Excellent";
  // recommendedPreheatTemp is an unsourced in-house heuristic keyed on IIW CE bands and thickness. It is not the AWS D1.1
  // Annex H/I method (those need hydrogen level, restraint and heat input) and must not be presented as a code value.
  let recommendedPreheatTemp = 20; // Room temp
  const riskNotes: string[] = [];

  if (ceIIW <= 0.35) {
    weldabilityLevel = "Excellent";
    recommendedPreheatTemp = 20;
    riskNotes.push("Minimal risk of hydrogen-induced cold cracking (HICC).");
  } else if (ceIIW <= 0.42) {
    weldabilityLevel = "Good";
    recommendedPreheatTemp = thicknessMm > 25 ? 50 : 20;
    riskNotes.push("Good weldability. Preheat recommended for heavy sections (>25mm).");
  } else if (ceIIW <= 0.50) {
    weldabilityLevel = "Moderate (Preheat required)";
    recommendedPreheatTemp = Math.max(100, Math.round(100 + (ceIIW - 0.42) * 500 + thicknessMm * 1.5));
    riskNotes.push(
      "Susceptible to HAZ martensite formation. Strict preheat and low-hydrogen electrodes (H4/H8) essential."
    );
  } else {
    weldabilityLevel = "Poor (High preheat & strict low hydrogen required)";
    recommendedPreheatTemp = Math.max(200, Math.round(150 + (ceIIW - 0.50) * 400 + thicknessMm * 2));
    riskNotes.push(
      "High risk of Underbead/Cold Cracking. Mandatory preheat 200°C+, interpass temperature control, and Post-Weld Heat Treatment (PWHT) stress relief."
    );
  }

  return {
    ceIIW,
    pcm,
    cen,
    weldabilityLevel,
    recommendedPreheatTemp,
    riskNotes,
  };
}

// --- 3. Schaeffler & DeLong Constitution Diagram Coordinates ---
export function calculateSchaeffler(comp: CompositionInput): SchaefflerResult {
  const C = comp.C || 0;
  const Cr = comp.Cr || 0;
  const Mo = comp.Mo || 0;
  const Si = comp.Si || 0;
  const Nb = comp.Nb || 0;
  const Ni = comp.Ni || 0;
  const Mn = comp.Mn || 0;
  // N is used as supplied; an omitted N counts as 0 (the former `|| 0.03` invented 0.03 wt% and made N = 0 impossible).
  const N = comp.N ?? 0;

  // Schaeffler equivalents
  const crEq = Number((Cr + Mo + 1.5 * Si + 0.5 * Nb).toFixed(2));
  const niEq = Number((Ni + 30 * C + 30 * N + 0.5 * Mn).toFixed(2));

  // Determine constitutional phase region
  let primaryPhase: SchaefflerResult["primaryPhase"] = "Austenite";
  let ferriteNumberEstimated = 0;
  let hotCrackingRisk: SchaefflerResult["hotCrackingRisk"] = "Low";
  let martensiticHardeningRisk: SchaefflerResult["martensiticHardeningRisk"] = "Low";

  if (niEq > 18 && crEq < 22) {
    primaryPhase = "Austenite";
    ferriteNumberEstimated = 0;
    hotCrackingRisk = "High"; // Fully austenitic weld metals are prone to hot cracking
  } else if (crEq > 22 && niEq < 8) {
    primaryPhase = "Ferrite";
    ferriteNumberEstimated = 80;
  } else if (crEq < 12 && niEq < 12) {
    primaryPhase = "Martensite";
    ferriteNumberEstimated = 0;
    martensiticHardeningRisk = "High";
  } else if (crEq >= 16 && niEq >= 8 && niEq <= 16) {
    primaryPhase = "Austenite + Ferrite";
    // Rule-based linear estimate, not the DeLong / WRC-1992 FN formulation
    ferriteNumberEstimated = Math.max(
      0,
      Math.min(100, Math.round(3.0 * (crEq - 0.93 * niEq - 6.7)))
    );
    if (ferriteNumberEstimated < 3) {
      hotCrackingRisk = "Moderate";
    }
  } else if (crEq < 18 && niEq < 16) {
    primaryPhase = "Martensite + Austenite + Ferrite";
    martensiticHardeningRisk = "Moderate";
  } else {
    primaryPhase = "Austenite + Ferrite";
    ferriteNumberEstimated = 15;
  }

  return {
    crEq,
    niEq,
    primaryPhase,
    ferriteNumberEstimated,
    hotCrackingRisk,
    martensiticHardeningRisk,
  };
}

// --- 4. Critical Transformation Temperatures (Andrews & Steven-Haynes) ---
export function calculateTransformationTemps(comp: CompositionInput): TransformationTempsResult {
  const C = comp.C || 0;
  const Mn = comp.Mn || 0;
  const Ni = comp.Ni || 0;
  const Cr = comp.Cr || 0;
  const Mo = comp.Mo || 0;
  const Si = comp.Si || 0;
  const V = comp.V || 0;

  // Andrews (1965) linear Ms equation: Ms (°C) = 539 - 423*C - 30.4*Mn - 17.7*Ni - 12.1*Cr - 7.5*Mo + 10*Co - 7.5*Si
  // (K. W. Andrews, J. Iron Steel Inst. 203 (1965) 721-727; wt%, low-alloy steels).
  const ms = Math.round(
    539 - 423 * C - 30.4 * Mn - 17.7 * Ni - 12.1 * Cr - 7.5 * Mo + 10 * (comp.Co || 0) - 7.5 * Si
  );

  // Mf is roughly 150 - 200°C below Ms
  const mf = ms - 180;

  // Steven & Haynes Formula for Bainite Start: Bs (°C) = 830 - 270*C - 90*Mn - 37*Ni - 70*Cr - 83*Mo
  const bs = Math.round(830 - 270 * C - 90 * Mn - 37 * Ni - 70 * Cr - 83 * Mo);

  // Grange / Andrews formulas for Ac1 and Ac3
  const ac1 = Math.round(723 - 10.7 * Mn - 16.9 * Ni + 29.1 * Si + 16.9 * Cr);
  const ac3 = Math.round(
    910 - 203 * Math.sqrt(C) - 15.2 * Ni + 44.7 * Si + 104 * V + 31.5 * Mo - 30 * Mn
  );

  return { ms, mf, bs, ac1, ac3 };
}

// --- 5. Fick's 2nd Law Case Hardening & Diffusion Simulation ---
export function simulateCarburizingDiffusion(
  tempCelsius: number = 930,
  timeHours: number = 6,
  surfaceCarbonPct: number = 1.0,
  coreCarbonPct: number = 0.20,
  targetDepthCarbon: number = 0.40
): DiffusionResult {
  const tempK = tempCelsius + 273.15;
  const timeSeconds = timeHours * 3600;

  // Arrhenius parameters for Carbon diffusion in FCC γ-Austenite
  // D = D0 * exp(-Q / RT), where D0 = 2.3e-5 m^2/s, Q = 148,000 J/mol, R = 8.314 J/(mol*K)
  const D0 = 2.3e-5;
  const Q = 148000;
  const R = 8.314;
  const D = D0 * Math.exp(-Q / (R * tempK)); // in m^2/s

  // Total Case depth x where C(x,t) reaches effective case depth (0.40% C)
  // (C(x,t) - C0) / (Cs - C0) = 1 - erf(x / (2*sqrt(Dt)))
  // erf(x / 2*sqrt(Dt)) = 1 - (Ctarget - C0)/(Cs - C0)
  const targetFraction = (targetDepthCarbon - coreCarbonPct) / (surfaceCarbonPct - coreCarbonPct);
  const erfArg = erfinv(Math.max(0.001, Math.min(0.999, 1 - targetFraction)));
  const effectiveCaseDepthMeters = 2 * Math.sqrt(D * timeSeconds) * erfArg;
  const effectiveCaseDepthMm = Number((effectiveCaseDepthMeters * 1000).toFixed(2));

  // Generate concentration depth profile points (from 0 to 3.5 mm)
  const profileData: { depthMm: number; concentrationPct: number }[] = [];
  const maxPlotDepthMm = Math.max(3.0, effectiveCaseDepthMm * 2.2);

  for (let i = 0; i <= 30; i++) {
    const depthMm = (i / 30) * maxPlotDepthMm;
    const depthMeters = depthMm / 1000;
    const z = depthMeters / (2 * Math.sqrt(D * timeSeconds));
    const c = surfaceCarbonPct - (surfaceCarbonPct - coreCarbonPct) * erf(z);
    profileData.push({
      depthMm: Number(depthMm.toFixed(2)),
      concentrationPct: Number(Math.max(coreCarbonPct, c).toFixed(3)),
    });
  }

  // Total case depth where C = Core + 0.05
  const totalCaseDepthMm = Number(
    (2 * Math.sqrt(D * timeSeconds) * erfinv(0.95) * 1000).toFixed(2)
  );

  return {
    caseDepth: totalCaseDepthMm,
    effectiveCaseDepth: effectiveCaseDepthMm,
    profileData,
    diffusivity: D,
  };
}

// --- 6. Hall-Petch Strength & ASTM Grain Size Predictor ---
export function calculateHallPetch(
  grainSizeMicrons: number,
  sigma0: number = 70, // Friction stress for pure Fe in MPa
  ky: number = 18.5 // Hall-Petch slope in MPa * mm^1/2 (approx 585 MPa * µm^1/2)
) {
  // ky in MPa * µm^(1/2) ≈ 18.5 * sqrt(1000) = 585
  const kyMicrons = ky * Math.sqrt(1000);
  const d = Math.max(0.1, grainSizeMicrons);
  const yieldStrengthMpa = Math.round(sigma0 + kyMicrons / Math.sqrt(d));

  // ASTM E112 grain size number from the average (planimetric) grain diameter d = sqrt(mean grain area):
  // N_AE = 2^(G-1) grains/in^2 at 100x  =>  N_A = 2^(G-1) * 1e4 / 645.16 grains/mm^2 at 1x = 1/d_mm^2
  //   =>  G = -6.643856 * log10(d_mm) - 2.954  (6.643856 = 2/log10(2): G is defined on an area count, d is a length).
  // Note: the unit converter's E112 card (calculateAstmE112FromDiameterUm) takes the mean lineal INTERCEPT l and uses
  // G = -6.643856 * log10(l_mm) - 3.288; both relations are right for their own input (l is about 0.89 d).
  // G is clamped to -3..16 like the converter's E112 card. Until 2026-10 the coefficient was 3.322 (the area-count
  // coefficient, which roughly halved G) and the constant 2.95.
  const dMm = d / 1000;
  const astmG = Number(Math.max(-3, Math.min(16, -6.643856 * Math.log10(dMm) - 2.954)).toFixed(1));

  return {
    grainSizeMicrons: d,
    yieldStrengthMpa,
    astmG,
    strengtheningIncrement: Math.round(kyMicrons / Math.sqrt(d)),
  };
}

// --- 7. Bragg's Law & XRD Peak Calculator ---
export function calculateXrdPeaks(
  crystalStructure: "BCC" | "FCC" | "HCP" | "Diamond",
  latticeParameterA: number, // in Angstroms (e.g. 2.8665 for α-Fe, 3.59 for γ-Fe, 4.05 for Al)
  xrayTarget: "Cu-Ka" | "Mo-Ka" | "Co-Ka" | "Fe-Ka" = "Cu-Ka"
): XrdPeak[] {
  // X-ray wavelengths in Angstroms
  const wavelengths = {
    "Cu-Ka": 1.5406,
    "Mo-Ka": 0.7093,
    "Co-Ka": 1.789,
    "Fe-Ka": 1.936,
  };
  const lambda = wavelengths[xrayTarget];

  const peaks: XrdPeak[] = [];

  // Systematic extinction rules based on Bravais lattice selection rules
  if (crystalStructure === "BCC") {
    // BCC: h + k + l must be even
    const planes = [
      { h: 1, k: 1, l: 0, mult: 12, relInt: 100 },
      { h: 2, k: 0, l: 0, mult: 6, relInt: 20 },
      { h: 2, k: 1, l: 1, mult: 24, relInt: 35 },
      { h: 2, k: 2, l: 0, mult: 12, relInt: 12 },
      { h: 3, k: 1, l: 0, mult: 24, relInt: 15 },
      { h: 2, k: 2, l: 2, mult: 8, relInt: 6 },
    ];

    for (const p of planes) {
      const d = latticeParameterA / Math.sqrt(p.h * p.h + p.k * p.k + p.l * p.l);
      const sinTheta = lambda / (2 * d);
      if (sinTheta <= 1.0) {
        const thetaRad = Math.asin(sinTheta);
        const twoThetaDeg = (2 * thetaRad * 180) / Math.PI;
        peaks.push({
          hkl: `(${p.h}${p.k}${p.l})`,
          twoTheta: Number(twoThetaDeg.toFixed(2)),
          dSpacing: Number(d.toFixed(4)),
          intensityPct: p.relInt,
        });
      }
    }
  } else if (crystalStructure === "FCC") {
    // FCC: h, k, l must be unmixed (all even or all odd)
    const planes = [
      { h: 1, k: 1, l: 1, mult: 8, relInt: 100 },
      { h: 2, k: 0, l: 0, mult: 6, relInt: 45 },
      { h: 2, k: 2, l: 0, mult: 12, relInt: 25 },
      { h: 3, k: 1, l: 1, mult: 24, relInt: 22 },
      { h: 2, k: 2, l: 2, mult: 8, relInt: 8 },
      { h: 4, k: 0, l: 0, mult: 6, relInt: 5 },
    ];

    for (const p of planes) {
      const d = latticeParameterA / Math.sqrt(p.h * p.h + p.k * p.k + p.l * p.l);
      const sinTheta = lambda / (2 * d);
      if (sinTheta <= 1.0) {
        const thetaRad = Math.asin(sinTheta);
        const twoThetaDeg = (2 * thetaRad * 180) / Math.PI;
        peaks.push({
          hkl: `(${p.h}${p.k}${p.l})`,
          twoTheta: Number(twoThetaDeg.toFixed(2)),
          dSpacing: Number(d.toFixed(4)),
          intensityPct: p.relInt,
        });
      }
    }
  }

  return peaks.sort((a, b) => a.twoTheta - b.twoTheta);
}

// --- 8. PREN & Pilling-Bedworth Ratio ---
export function calculatePREN(cr: number, mo: number, w: number = 0, n: number = 0): number {
  return Number((cr + 3.3 * (mo + 0.5 * w) + 16 * n).toFixed(1));
}

export function calculatePillingBedworth(
  mOxide: number,
  densityMetal: number,
  nMetalAtomsInOxide: number,
  mMetal: number,
  densityOxide: number
): { pbr: number; verdict: "Passivating / Protective" | "Porous / Non-protective" | "High Compressive Stress / Spallation Risk" } {
  const pbr = (mOxide * densityMetal) / (nMetalAtomsInOxide * mMetal * densityOxide);
  const roundedPbr = Number(pbr.toFixed(2));

  let verdict: "Passivating / Protective" | "Porous / Non-protective" | "High Compressive Stress / Spallation Risk" = "Passivating / Protective";
  if (pbr < 1.0) {
    verdict = "Porous / Non-protective";
  } else if (pbr > 2.0) {
    verdict = "High Compressive Stress / Spallation Risk";
  }

  return { pbr: roundedPbr, verdict };
}
