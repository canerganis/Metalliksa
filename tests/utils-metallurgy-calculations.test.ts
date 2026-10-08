import assert from "node:assert/strict";
import test from "node:test";
import {
  calculateCarbonEquivalent,
  calculateHallPetch,
  calculatePREN,
  calculatePillingBedworth,
  calculateSchaeffler,
  calculateTransformationTemps,
  calculateXrdPeaks,
  erf,
  erfinv,
  simulateCarburizingDiffusion,
} from "../src/utils/metallurgyCalculations";
import { astmGrainSizeNumberFromIntercept } from "../src/utils/semAnalysis";
import { convertSteelHardness } from "../src/utils/hardnessConversion";

// Independent high-precision erf (Maclaurin series, |x| < 3) used as the oracle for the A&S approximation.
function erfSeries(x: number): number {
  let sum = 0;
  let term = x; // x^(2n+1)/n!
  for (let n = 0; n < 60; n++) {
    sum += term / (2 * n + 1);
    term *= (-x * x) / (n + 1);
  }
  return (2 / Math.sqrt(Math.PI)) * sum;
}

function near(actual: number, expected: number, tol: number, msg = "") {
  assert.ok(Math.abs(actual - expected) <= tol, `${msg} ${actual} differs from ${expected} by more than ${tol}`);
}

test("erf matches the series oracle within the Abramowitz-Stegun bound (1.5e-7) and is odd", () => {
  assert.equal(Math.abs(erf(0)) < 1e-9, true);
  for (const x of [0.1, 0.5, 1, 1.5, 2, 2.5]) {
    near(erf(x), erfSeries(x), 2e-7, `erf(${x})`);
    near(erf(-x), -erf(x), 1e-12);
  }
  near(erf(0.5), 0.5204999, 2e-7); // tabulated
  near(erf(1), 0.8427008, 2e-7);
});

test("erfinv (Winitzki approximation) inverts erf to better than 4e-3 and matches tabulated values", () => {
  near(erfinv(0.5), 0.4769363, 4e-3);
  near(erfinv(0.95), 1.3859038, 4e-3);
  near(erfinv(0.99), 1.8213864, 4e-3); // Winitzki a = 0.147: relative error up to ~2e-3
  near(erfinv(-0.5), -erfinv(0.5), 1e-12);
  for (const x of [0.1, 0.3, 0.6, 0.9, 0.95]) near(erfSeries(erfinv(x)), x, 2e-3, `round trip ${x}`);
});

// Pocket Calculators' convertHardness (same polynomials as the unit converter: HRC 30 -> HV 532, HRC 40 -> 715) was
// removed; the tab now calls the shared convertSteelHardness (ASTM E140 Table 1 / ISO 18265 Table A.1 interpolation,
// tests/utils-hardness-conversion.test.ts). The former todo is a real test here.
test("pocket-calculator HRC -> HV matches the ASTM E140 Table 1 rows (old polynomial: 532 / 715 / 925 / 1162)", () => {
  for (const [hrc, hv] of [[30, 302], [40, 392], [50, 513], [60, 697]] as Array<[number, number]>) {
    assert.equal(convertSteelHardness(hrc, "HRC").HV, hv, `HRC ${hrc}`);
  }
  // default tab input HRC 30: no clamping, no HRB above HV 240, Rm from ISO 18265 Table A.1
  const r = convertSteelHardness(30, "HRC");
  assert.deepEqual([r.HV, r.HRC, r.HRB, r.HBW, r.HK, r.tensileRm_MPa, r.tensileRm_ksi], [302, 30, null, 286, 311, 971, 140.8]);
  assert.equal(convertSteelHardness(5, "HRC").HV, null); // old: clamped to the HRC 20 value
  assert.equal(convertSteelHardness(1550, "HV").HRC, null); // "Tungsten Carbide WC" preset: outside every steel table
});

// ---------------------------------------------------------------------------------------------------------------
// Carbon equivalent (IIW, Pcm, CEN) and preheat bands
// ---------------------------------------------------------------------------------------------------------------

test("carbon equivalent: hand-computed IIW / Pcm for the Pocket Calculators default composition", () => {
  const comp = { C: 0.22, Mn: 1.35, Si: 0.35, Cr: 0.25, Mo: 0.15, V: 0.05, Ni: 0.2, Cu: 0.15, Nb: 0.02, B: 0.0005 };
  const r = calculateCarbonEquivalent(comp, 30);
  // IIW = 0.22 + 1.35/6 + (0.25+0.15+0.05)/5 + (0.20+0.15)/15 = 0.22 + 0.225 + 0.09 + 0.02333 = 0.55833
  assert.equal(r.ceIIW, 0.558);
  // Pcm = 0.22 + 0.35/30 + (1.35+0.15+0.25)/20 + 0.2/60 + 0.15/15 + 0.05/10 + 5*0.0005 = 0.34
  assert.equal(r.pcm, 0.34);
  // CEN: A(C) = 0.75 + 0.25 tanh(20 (0.22 - 0.12)) = 0.75 + 0.25 tanh(2) = 0.99100
  const ac = 0.75 + 0.25 * Math.tanh(2);
  const expectedCen = 0.22 + ac * (0.35 / 24 + 1.35 / 6 + 0.15 / 15 + 0.2 / 20 + (0.25 + 0.15 + 0.05 + 0.02) / 5 + 5 * 0.0005);
  assert.equal(r.cen, Number(expectedCen.toFixed(3)));
  assert.match(r.weldabilityLevel, /^Poor/);
  // > 0.50: max(200, round(150 + 0.058 * 400 + 2 * 30)) = 233
  assert.equal(r.recommendedPreheatTemp, 233);
});

test("carbon equivalent: weldability bands and preheat rules (inclusive upper bounds, 25 mm section limit)", () => {
  assert.equal(calculateCarbonEquivalent({ C: 0.1, Mn: 0.4 }).weldabilityLevel, "Excellent"); // 0.167
  const ce035 = calculateCarbonEquivalent({ C: 0.35, Mn: 0 }); // exactly 0.35
  assert.equal(ce035.weldabilityLevel, "Excellent");
  const good = calculateCarbonEquivalent({ C: 0.25, Mn: 1.0 }, 30); // 0.4167
  assert.equal(good.weldabilityLevel, "Good");
  assert.equal(good.recommendedPreheatTemp, 50);
  assert.equal(calculateCarbonEquivalent({ C: 0.25, Mn: 1.0 }, 25).recommendedPreheatTemp, 20);
  const moderate = calculateCarbonEquivalent({ C: 0.3, Mn: 1.0 }, 20); // 0.4667
  assert.match(moderate.weldabilityLevel, /^Moderate/);
  assert.equal(moderate.recommendedPreheatTemp, Math.max(100, Math.round(100 + (0.467 - 0.42) * 500 + 20 * 1.5)));
  assert.equal(moderate.recommendedPreheatTemp, 154);
  assert.equal(calculateCarbonEquivalent({ C: 0.6, Mn: 1 }, 5).recommendedPreheatTemp, 267); // CE 0.767: 150 + 0.267 * 400 + 2 * 5 = 266.8
});

// ---------------------------------------------------------------------------------------------------------------
// Schaeffler / DeLong
// ---------------------------------------------------------------------------------------------------------------

test("Schaeffler equivalents and ferrite number (hand computed)", () => {
  // 304-type default: Creq = 19.5 + 0.4 + 1.5*0.6 + 0 = 20.8; Nieq = 9.8 + 30*0.05 + 30*0.04 + 0.5*1.7 = 13.35
  const s304 = calculateSchaeffler({ C: 0.05, Cr: 19.5, Ni: 9.8, Mo: 0.4, Si: 0.6, Mn: 1.7, Nb: 0, N: 0.04 });
  assert.equal(s304.crEq, 20.8);
  assert.equal(s304.niEq, 13.35);
  assert.equal(s304.primaryPhase, "Austenite + Ferrite");
  // FN = round(3 (20.8 - 0.93*13.35 - 6.7)) = round(3 * 1.6845) = 5
  assert.equal(s304.ferriteNumberEstimated, 5);
  assert.equal(s304.hotCrackingRisk, "Low");
  // 316L-type with N = 0.03 supplied: Creq 20.25, Nieq 14.25, FN = round(3*0.2975) = 1 -> hot-cracking Moderate
  const s316 = calculateSchaeffler({ C: 0.02, Cr: 17, Ni: 12, Mo: 2.5, Si: 0.5, Mn: 1.5, N: 0.03 });
  assert.equal(s316.crEq, 20.25);
  assert.equal(s316.niEq, 14.25);
  assert.equal(s316.ferriteNumberEstimated, 1);
  assert.equal(s316.hotCrackingRisk, "Moderate");
});

test("Schaeffler regions: fully austenitic, ferritic, martensitic", () => {
  const auste = calculateSchaeffler({ C: 0.03, Cr: 18, Ni: 20, Mo: 0, Si: 0.3, Mn: 2 });
  assert.equal(auste.primaryPhase, "Austenite");
  assert.equal(auste.hotCrackingRisk, "High");
  const ferrite = calculateSchaeffler({ C: 0.02, Cr: 26, Ni: 1, Mo: 0, Si: 0.5, Mn: 0.5 });
  assert.equal(ferrite.primaryPhase, "Ferrite");
  assert.equal(ferrite.ferriteNumberEstimated, 80);
  const mart = calculateSchaeffler({ C: 0.1, Cr: 10, Ni: 0.5, Mo: 0, Si: 0.3, Mn: 0.5 });
  assert.equal(mart.primaryPhase, "Martensite");
  assert.equal(mart.martensiticHardeningRisk, "High");
});

// ---------------------------------------------------------------------------------------------------------------
// Transformation temperatures
// ---------------------------------------------------------------------------------------------------------------

test("Andrews / Steven-Haynes temperatures (hand computed, 4140-like default)", () => {
  const r = calculateTransformationTemps({ C: 0.42, Mn: 0.85, Cr: 1.05, Mo: 0.22, Ni: 0.2, Si: 0.25, V: 0.02 });
  // Ms (Andrews 1965, with the -7.5 Si term) = 539 - 423(0.42) - 30.4(0.85) - 17.7(0.2) - 12.1(1.05) - 7.5(0.22) - 7.5(0.25)
  //    = 317.6 - 1.875 = 315.7
  assert.equal(r.ms, 316);
  assert.equal(r.mf, 136); // Ms - 180
  // Bs = 830 - 270(0.42) - 90(0.85) - 37(0.2) - 70(1.05) - 83(0.22) = 540.94
  assert.equal(r.bs, 541);
  // Ac1 = 723 - 10.7(0.85) - 16.9(0.2) + 29.1(0.25) + 16.9(1.05) = 735.545
  assert.equal(r.ac1, 736);
  // Ac3 = 910 - 203 sqrt(0.42) - 15.2(0.2) + 44.7(0.25) + 104(0.02) + 31.5(0.22) - 30(0.85) = 770.07
  assert.equal(r.ac3, 770);
  assert.ok(r.ms < r.bs && r.bs < r.ac1 && r.ac1 < r.ac3);
  // plain carbon steel 1045: Ac3 ~ 910 - 203*sqrt(0.45) + 44.7*0.25 - 30*0.75 = 762 (text-book 770-780)
  const c1045 = calculateTransformationTemps({ C: 0.45, Mn: 0.75, Si: 0.25 });
  assert.equal(c1045.ac3, Math.round(910 - 203 * Math.sqrt(0.45) + 44.7 * 0.25 - 30 * 0.75));
});

// ---------------------------------------------------------------------------------------------------------------
// Carburizing diffusion (Fick's 2nd law, semi-infinite solid)
// ---------------------------------------------------------------------------------------------------------------

test("carburizing: Arrhenius diffusivity, case depths and profile (hand-computed oracle)", () => {
  const r = simulateCarburizingDiffusion(930, 6, 1.05, 0.2, 0.4);
  // D = 2.3e-5 exp(-148000 / (8.314 * 1203.15)) m2/s
  const D = 2.3e-5 * Math.exp(-148000 / (8.314 * 1203.15));
  near(r.diffusivity / D, 1, 1e-12);
  near(r.diffusivity, 8.6e-12, 0.1e-12); // ~8.6e-12 m2/s for gamma-Fe at 930 C (Callister parameters)
  const sqrtDt2 = 2 * Math.sqrt(D * 6 * 3600);
  // total case depth: C = core + 5 % of the surface-core difference -> erf(z) = 0.95 -> z = 1.38590
  near(r.caseDepth, sqrtDt2 * 1.3859038 * 1000, 0.01);
  assert.equal(r.caseDepth, 1.2);
  // effective case depth at 0.40 % C: erf(z) = 1 - (0.4-0.2)/(1.05-0.2) = 0.76471 (oracle by bisection on the series erf)
  let lo = 0, hi = 3;
  for (let i = 0; i < 80; i++) { const mid = (lo + hi) / 2; if (erfSeries(mid) < 1 - 0.2 / 0.85) lo = mid; else hi = mid; }
  near(r.effectiveCaseDepth, sqrtDt2 * lo * 1000, 0.015);
  assert.equal(r.effectiveCaseDepth, 0.72);
  // profile: starts at the surface carbon, monotonically decreasing, never below the core
  assert.equal(r.profileData.length, 31);
  assert.equal(r.profileData[0].depthMm, 0);
  assert.equal(r.profileData[0].concentrationPct, 1.05);
  for (let i = 1; i < r.profileData.length; i++) {
    assert.ok(r.profileData[i].concentrationPct <= r.profileData[i - 1].concentrationPct);
    assert.ok(r.profileData[i].concentrationPct >= 0.2);
  }
  assert.equal(r.profileData[30].depthMm, Math.max(3, r.effectiveCaseDepth * 2.2));
});

test("carburizing: case depth scales with sqrt(time) and rises with temperature (Q = 148 kJ/mol)", () => {
  const t6 = simulateCarburizingDiffusion(930, 6).caseDepth;
  const t24 = simulateCarburizingDiffusion(930, 24).caseDepth;
  near(t24 / t6, 2, 0.02);
  const d900 = simulateCarburizingDiffusion(900, 6).diffusivity;
  const d1000 = simulateCarburizingDiffusion(1000, 6).diffusivity;
  near(d1000 / d900, Math.exp((148000 / 8.314) * (1 / 1173.15 - 1 / 1273.15)), 1e-9);
});

// ---------------------------------------------------------------------------------------------------------------
// Hall-Petch
// ---------------------------------------------------------------------------------------------------------------

test("Hall-Petch: sigma_y = sigma_0 + k_y / sqrt(d) (hand computed) and the grain-size clamp", () => {
  const r = calculateHallPetch(25);
  // k_y = 18.5 * sqrt(1000) = 585.0 MPa um^0.5 ; 585.0 / 5 = 117.0 ; + 70 = 187
  assert.equal(r.strengtheningIncrement, 117);
  assert.equal(r.yieldStrengthMpa, 187);
  assert.equal(calculateHallPetch(1).yieldStrengthMpa, 70 + 585); // 585.0 -> 655
  assert.equal(calculateHallPetch(0.01).grainSizeMicrons, 0.1); // d >= 0.1 um
  // finer grains are stronger
  assert.ok(calculateHallPetch(5).yieldStrengthMpa > calculateHallPetch(50).yieldStrengthMpa);
  assert.equal(calculateHallPetch(100, 100, 20).yieldStrengthMpa, Math.round(100 + (20 * Math.sqrt(1000)) / 10));
});

// FIXED (2026-10): calculateHallPetch used G = -3.322 log10(d_mm) - 2.95. 3.322 = 1/log10(2) is the coefficient for
// log10 of an AREA (or area count); d is a length, so the coefficient is 2/log10(2) = 6.643856, and the constant is
// now the exact 2.954 derived below. G is clamped to -3..16 like the unit converter's E112 card.
//
// First-principles oracle (ASTM E112 definition only, no tables):
//   N_AE = 2^(G-1) grains per square inch at 100x.  At 1x a field 1 in^2 is 100^2 times larger in area, and
//   1 in^2 = 25.4^2 = 645.16 mm^2, so N_A = 2^(G-1) * 100^2 / 645.16 grains/mm^2.
//   Relation relied on: the average grain diameter shown in the calculator ("Average Grain Diameter (d, planimetric)")
//   is the planimetric diameter d = sqrt(mean grain area) = 1/sqrt(N_A).  Solving for G:
//   G = 1 + log2(645.16e-4) - 2 log2(d_mm) = -6.643856 log10(d_mm) - 2.9542.
// The unit converter's E112 card takes the mean lineal INTERCEPT l instead and uses -3.288 (E112 intercept relation);
// both are right for their own input (l = 2^(-(3.288 - 2.954)/2) d = 0.89 d).
function e112PlanimetricG(dUm: number): number {
  const dMm = dUm / 1000;
  const NA = 1 / (dMm * dMm); // grains per mm^2 at 1x
  const NAE = (NA * 645.16) / 100 ** 2; // grains per in^2 at 100x
  return Math.log2(NAE) + 1; // invert N_AE = 2^(G-1)
}

test("Hall-Petch ASTM G equals the E112 planimetric grain size number derived from N_AE = 2^(G-1)", () => {
  // derived constants
  assert.ok(Math.abs(-(1 + Math.log2(645.16e-4)) - 2.9542) < 1e-4);
  assert.ok(Math.abs(2 / Math.log10(2) - 6.643856) < 1e-6);
  for (let d = 0.5; d <= 100; d += 0.5) {
    const code = calculateHallPetch(d).astmG;
    const oracle = Math.max(-3, Math.min(16, e112PlanimetricG(d)));
    // displayed to 0.1 (constant 2.954 vs the derived 2.95420: |dG| < 3e-5)
    assert.ok(Math.abs(code - oracle) <= 0.05 + 3e-5, `d=${d} um: code ${code} vs oracle ${oracle}`);
  }
  // clamp: the slider minimum 0.5 um would be G 19.0, shown as 16 (same range as calculateAstmE112FromG)
  assert.equal(calculateHallPetch(0.5).astmG, 16);
  assert.equal(calculateHallPetch(1).astmG, 16);
  assert.equal(calculateHallPetch(1.5).astmG, 15.8);
  assert.equal(calculateHallPetch(10000).astmG, -3);
  // cross-check against the E112 count definition at G = 8: N_AE = 128 /in^2 at 100x -> N_A = 1984.0 /mm^2,
  // d = 1/sqrt(N_A) = 22.45 um (the "22.4 um" planimetric figure). The 22.1 um value of calculateAstmE112FromG
  // used 2^(G+3) = 2048 /mm^2 (16 instead of 15.5 per in^2-at-100x), and the mean lineal intercept at G 8 is 20.0 um.
  const dG8 = 1000 / Math.sqrt((128 * 100 ** 2) / 645.16);
  assert.ok(Math.abs(dG8 - 22.45) < 0.01);
  assert.equal(calculateHallPetch(dG8).astmG, 8);
  assert.equal(calculateHallPetch(22.4).astmG, 8);
});

test("Hall-Petch ASTM G (planimetric d) sits 0.334 above the intercept relation for the same length", () => {
  for (const d of [10, 22.4, 25, 50, 100]) {
    const code = calculateHallPetch(d).astmG;
    const e112 = astmGrainSizeNumberFromIntercept(d);
    // same coefficient, constants 2.954 vs 3.288 -> G differs by 0.334 (+ display rounding)
    assert.ok(Math.abs(code - e112 - 0.334) <= 0.1, `d=${d} um: code G ${code} vs intercept G ${e112}`);
  }
});

// HISTORICAL (values shown in Pocket Calculators before 2026-10, pinned so reviewers see the delta):
// "original" = -3.322 log10(d) - 2.95; "coef" = -6.643856 log10(d) - 2.95 (commit 0727d3c); now = exact 2.954 + clamp.
test("HISTORICAL Hall-Petch ASTM G: original (about half) -> coefficient fix -> exact constant and clamp", () => {
  const original = (dUm: number) => Number((-3.322 * Math.log10(dUm / 1000) - 2.95).toFixed(1));
  const coef = (dUm: number) => Number((-6.643856 * Math.log10(dUm / 1000) - 2.95).toFixed(1));
  const rows = [0.5, 1, 10, 22.4, 24.5, 25, 49, 50, 52.5, 91.5, 98, 100].map((d) => [d, original(d), coef(d), calculateHallPetch(d).astmG]);
  assert.deepEqual(rows, [
    [0.5, 8, 19, 16],
    [1, 7, 17, 16],
    [10, 3.7, 10.3, 10.3],
    [22.4, 2.5, 8, 8],
    [24.5, 2.4, 7.8, 7.7],
    [25, 2.4, 7.7, 7.7],
    [49, 1.4, 5.8, 5.7],
    [50, 1.4, 5.7, 5.7],
    [52.5, 1.3, 5.6, 5.5],
    [91.5, 0.5, 4, 3.9],
    [98, 0.4, 3.8, 3.7],
    [100, 0.4, 3.7, 3.7],
  ]);
  // over the whole slider (0.5..100 um, step 0.5) the 2.95 -> 2.954 + clamp step changes exactly these 7 values
  const changed: number[] = [];
  for (let i = 1; i <= 200; i++) if (coef(i / 2) !== calculateHallPetch(i / 2).astmG) changed.push(i / 2);
  assert.deepEqual(changed, [0.5, 1, 24.5, 49, 52.5, 91.5, 98]);
});

// ---------------------------------------------------------------------------------------------------------------
// XRD (Bragg's law)
// ---------------------------------------------------------------------------------------------------------------

test("XRD: alpha-Fe (BCC, a = 2.8665 A) Cu-K-alpha peaks match the published 2-theta positions", () => {
  const peaks = calculateXrdPeaks("BCC", 2.8665, "Cu-Ka");
  const byHkl = Object.fromEntries(peaks.map((p) => [p.hkl, p]));
  // d(110) = a/sqrt(2) = 2.0269 A; 2-theta = 2 asin(1.5406 / (2 * 2.0269)) = 44.67 deg
  assert.equal(byHkl["(110)"].dSpacing, 2.0269);
  assert.equal(byHkl["(110)"].twoTheta, 44.67);
  assert.equal(byHkl["(200)"].twoTheta, 65.02);
  assert.equal(byHkl["(211)"].twoTheta, 82.33);
  assert.equal(byHkl["(110)"].intensityPct, 100);
  // sorted ascending, Bragg's law satisfied: lambda = 2 d sin(theta)
  for (let i = 1; i < peaks.length; i++) assert.ok(peaks[i].twoTheta > peaks[i - 1].twoTheta);
  for (const p of peaks) near(2 * p.dSpacing * Math.sin((p.twoTheta / 2) * Math.PI / 180), 1.5406, 2e-3, p.hkl);
});

test("XRD: Al (FCC, a = 4.05 A) Cu-K-alpha peaks; reflections beyond the Bragg limit (sin theta > 1) are dropped", () => {
  const al = calculateXrdPeaks("FCC", 4.05, "Cu-Ka");
  assert.deepEqual(al.slice(0, 3).map((p) => [p.hkl, p.twoTheta]), [["(111)", 38.47], ["(200)", 44.72], ["(220)", 65.09]]);
  // Fe-Ka (1.936 A) cannot reach the BCC (222) reflection (d = 0.8275 A < lambda/2): dropped, not NaN
  const fe = calculateXrdPeaks("BCC", 2.8665, "Fe-Ka");
  assert.equal(fe.some((p) => p.hkl === "(222)"), false);
  assert.ok(fe.every((p) => Number.isFinite(p.twoTheta)));
  // a shorter wavelength puts every peak at lower angle
  const mo = calculateXrdPeaks("BCC", 2.8665, "Mo-Ka");
  assert.equal(mo[0].twoTheta, 20.15); // Mo-K-alpha (110) of alpha-Fe, literature 20.2
  assert.equal(mo.length, 6); // all six tabulated BCC reflections are reachable with 0.7093 A
});

test("XRD: HCP and Diamond are declared in the signature but return no peaks (documented gap)", () => {
  assert.deepEqual(calculateXrdPeaks("HCP", 2.95), []);
  assert.deepEqual(calculateXrdPeaks("Diamond", 3.567), []);
});

// ---------------------------------------------------------------------------------------------------------------
// PREN and Pilling-Bedworth
// ---------------------------------------------------------------------------------------------------------------

test("PREN = Cr + 3.3 (Mo + 0.5 W) + 16 N for known grades", () => {
  assert.equal(calculatePREN(17, 2.1), 23.9); // 316L: 17 + 6.93
  assert.equal(calculatePREN(25, 4, 0, 0.27), 42.5); // 2507 super duplex: 25 + 13.2 + 4.32 = 42.52
  assert.equal(calculatePREN(25, 3.5, 0.5, 0.25), Number((25 + 3.3 * (3.5 + 0.25) + 16 * 0.25).toFixed(1))); // 41.4: W counts half
  near(calculatePREN(22, 3.1, 0, 0.17), 34.95, 0.06); // 2205
});

test("Pilling-Bedworth ratio: published oxide ratios and verdict bands", () => {
  // PBR = (M_ox * rho_metal) / (n * M_metal * rho_ox)
  const fe = calculatePillingBedworth(159.69, 7.87, 2, 55.85, 5.24); // Fe2O3, literature ~2.14
  assert.equal(fe.pbr, 2.15);
  near(fe.pbr, 2.14, 0.02);
  assert.equal(fe.verdict, "High Compressive Stress / Spallation Risk");
  const al = calculatePillingBedworth(101.96, 2.7, 2, 26.98, 3.95); // Al2O3, literature 1.28
  assert.equal(al.pbr, 1.29);
  near(al.pbr, 1.28, 0.02);
  assert.equal(al.verdict, "Passivating / Protective");
  const mg = calculatePillingBedworth(40.3, 1.74, 1, 24.31, 3.58); // MgO, literature 0.81
  assert.equal(mg.pbr, 0.81);
  assert.equal(mg.verdict, "Porous / Non-protective");
  assert.equal(calculatePillingBedworth(1, 1, 1, 1, 1).verdict, "Passivating / Protective"); // PBR = 1.0 is protective
  assert.equal(calculatePillingBedworth(2, 1, 1, 1, 1).verdict, "Passivating / Protective"); // PBR = 2.0 is still protective
});

test("Andrews Ms carries the -7.5 Si term (Andrews 1965)", () => {
  const noSi = calculateTransformationTemps({ C: 0.3, Mn: 0.8 });
  const withSi = calculateTransformationTemps({ C: 0.3, Mn: 0.8, Si: 2 });
  // 539 - 423(0.3) - 30.4(0.8) = 387.78 ; with 2 % Si: 387.78 - 15 = 372.78
  assert.equal(noSi.ms, 388);
  assert.equal(withSi.ms, 373);
});

test("Schaeffler: N = 0 is honoured (no invented 0.03 wt% default) and N enters Ni_eq as 30*N", () => {
  const base = { C: 0.02, Cr: 18, Ni: 8, Mo: 0, Si: 0, Mn: 0, Nb: 0 };
  const zero = calculateSchaeffler({ ...base, N: 0 });
  const omitted = calculateSchaeffler(base);
  const some = calculateSchaeffler({ ...base, N: 0.1 });
  assert.equal(zero.niEq, 8.6); // 8 + 30(0.02)
  assert.equal(omitted.niEq, zero.niEq);
  assert.equal(some.niEq, 11.6); // + 30(0.1)
});

