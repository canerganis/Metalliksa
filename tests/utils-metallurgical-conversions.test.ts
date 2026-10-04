import assert from "node:assert/strict";
import test from "node:test";
import {
  METALLURGICAL_MELTING_PRESETS,
  calculateAstmE112FromDiameterUm,
  calculateAstmE112FromG,
  calculateHomologousTemperature,
  computeDualUnitReport,
  convertCorrosionRate,
  convertDensity,
  convertFractureToughness,
  convertImpactEnergy,
  convertMicroLength,
  convertStress,
  convertTemperature,
  interpretHardness,
  HARDNESS_INTERPRETATION_NOTE,
  HARDNESS_INTERPRETATION_UNAVAILABLE,
  reportHardnessLine,
  interpretStressMpa,
  type TempUnit,
} from "../src/utils/metallurgicalConversions";
import { convertSteelHardness } from "../src/utils/hardnessConversion";

// ---------------------------------------------------------------------------------------------------------------
// Temperature (offset scales): exact definitions K = C + 273.15, F = 1.8 C + 32, R = 1.8 K.
// ---------------------------------------------------------------------------------------------------------------

test("temperature: fixed points of the Celsius/Kelvin/Fahrenheit/Rankine scales", () => {
  assert.deepEqual(convertTemperature(0, "C"), { C: 0, K: 273.15, F: 32, R: 491.67 }); // ice point
  assert.deepEqual(convertTemperature(100, "C"), { C: 100, K: 373.15, F: 212, R: 671.67 }); // steam point
  assert.deepEqual(convertTemperature(-40, "F"), { C: -40, K: 233.15, F: -40, R: 419.67 }); // C = F crossover
  assert.deepEqual(convertTemperature(491.67, "R"), { C: 0, K: 273.15, F: 32, R: 491.67 });
  assert.deepEqual(convertTemperature(273.15, "K"), { C: 0, K: 273.15, F: 32, R: 491.67 });
});

test("temperature: absolute zero is a hard floor", () => {
  const zero = { C: -273.15, K: 0, F: -459.67, R: 0 };
  assert.deepEqual(convertTemperature(0, "K"), zero);
  assert.deepEqual(convertTemperature(-300, "C"), zero);
  assert.deepEqual(convertTemperature(-459.67, "F"), zero);
  assert.deepEqual(convertTemperature(-1000, "K"), zero);
  assert.deepEqual(convertTemperature(NaN, "K"), zero); // NaN -> 0 K
});

test("temperature: round trip through every unit pair stays within rounding (0.01)", () => {
  const units: TempUnit[] = ["C", "K", "F", "R"];
  for (const from of units) {
    for (const seed of [-200, -40, 0, 23, 500, 1500]) {
      const start = convertTemperature(seed, "C")[from];
      const all = convertTemperature(start, from);
      for (const to of units) {
        const back = convertTemperature(all[to], to);
        assert.ok(Math.abs(back.C - all.C) <= 0.011, `${from}->${to} seed ${seed}: ${back.C} vs ${all.C}`);
        assert.ok(Math.abs(back.K - all.K) <= 0.011);
      }
    }
  }
});

test("homologous temperature uses Kelvin and the 0.3 / 0.5 T_m regime boundaries", () => {
  // Cu (T_m 1085 C = 1358.15 K) at 23 C: 296.15 / 1358.15 = 0.218
  const cu = calculateHomologousTemperature(23, 1085);
  assert.equal(cu.th, 0.218);
  assert.equal(cu.regime, "Cold Working (Athermal Plasticity)");
  // T/Tm = 0.3 exactly (Tm = 1000 K) at 26.85 C -> not "cold" (th < 0.3 is strict)
  assert.equal(calculateHomologousTemperature(26.85, 726.85).th, 0.3);
  assert.match(calculateHomologousTemperature(26.85, 726.85).regime, /^Warm Working/);
  // 0.5 boundary is inclusive for "warm"
  assert.match(calculateHomologousTemperature(226.85, 726.85).regime, /^Warm Working/);
  assert.match(calculateHomologousTemperature(500, 1085).regime, /^Hot Working/); // 0.569
  assert.equal(calculateHomologousTemperature(500, 1085).th, 0.569);
});

test("melting presets are internally consistent (T_m[K] = T_m[C] + 273.15)", () => {
  for (const p of METALLURGICAL_MELTING_PRESETS) {
    assert.ok(Math.abs(p.tmK - (p.tmC + 273.15)) < 1e-9, p.name);
  }
});

// ---------------------------------------------------------------------------------------------------------------
// Linear conversions with published factors
// ---------------------------------------------------------------------------------------------------------------

test("stress: published factors (1 ksi = 6.894757 MPa, 1 kgf/mm2 = 9.80665 MPa)", () => {
  assert.deepEqual(convertStress(100, "MPa"), {
    MPa: 100, ksi: 14.5, GPa: 0.1, psi: 14503.8, bar: 1000, kgf_mm2: 10.2, N_mm2: 100,
  });
  const ksi = convertStress(1, "ksi");
  assert.equal(ksi.MPa, 6.89);
  assert.equal(ksi.psi, 1000);
  assert.equal(convertStress(1, "GPa").MPa, 1000);
  assert.equal(convertStress(1, "kgf_mm2").MPa, 9.81);
  assert.equal(convertStress(145.0377377, "psi").MPa, 1); // 1 MPa = 145.0377 psi
  assert.equal(convertStress(10, "bar").MPa, 1);
  assert.equal(convertStress(NaN, "MPa").MPa, 0);
  // N/mm2 is identical to MPa
  assert.equal(convertStress(345, "N_mm2").MPa, 345);
});

test("stress round trip MPa -> ksi -> MPa within 0.1 %", () => {
  for (const mpa of [50, 345, 880, 1500, 2000]) {
    const ksi = convertStress(mpa, "MPa").ksi;
    const back = convertStress(ksi, "ksi").MPa;
    assert.ok(Math.abs(back - mpa) / mpa < 0.001, `${mpa} -> ${ksi} ksi -> ${back}`);
  }
});

test("stress interpretation bands are inclusive at the upper bound", () => {
  assert.match(interpretStressMpa(120).category, /^Low Strength/);
  assert.match(interpretStressMpa(120.01).category, /^Structural Mild Steel/);
  assert.match(interpretStressMpa(850).category, /^High-Strength Structural/);
  assert.match(interpretStressMpa(1400).category, /^High-Strength Quenched/);
  assert.match(interpretStressMpa(1400.1).category, /^Ultra-High/);
});

test("fracture toughness: 1 ksi*sqrt(in) = 1.0988 MPa*sqrt(m); N/mm^1.5 = sqrt(1000) * MPa*sqrt(m)", () => {
  assert.deepEqual(convertFractureToughness(50, "MPa_m05"), { MPa_m05: 50, ksi_in05: 45.5, N_mm15: 1581.1, MPa_mm05: 1581.1 });
  assert.equal(convertFractureToughness(1, "ksi_in05").MPa_m05, 1.1);
  assert.equal(convertFractureToughness(100, "ksi_in05").MPa_m05, 109.88);
  assert.equal(convertFractureToughness(1581.1388, "N_mm15").MPa_m05, 50);
  // round trip
  const k = convertFractureToughness(68, "MPa_m05");
  assert.ok(Math.abs(convertFractureToughness(k.ksi_in05, "ksi_in05").MPa_m05 - 68) < 0.02);
});

test("impact energy: 27 J = 19.9 ft-lbf; Charpy ligament 0.8 cm2 relates J and J/cm2", () => {
  assert.deepEqual(convertImpactEnergy(27, "J"), { J: 27, ft_lbf: 19.9, kgf_m: 2.75, J_cm2: 33.8 });
  assert.equal(convertImpactEnergy(1, "ft_lbf").J, 1.4); // 1.3558 J
  assert.equal(convertImpactEnergy(10, "J_cm2").J, 8); // 10 J/cm2 * 0.8 cm2
  assert.equal(convertImpactEnergy(1, "kgf_m").J, 9.8);
});

test("micro lengths: 1 in = 25400 um, 1 mil = 25.4 um, 1 um = 1000 nm = 10000 angstrom", () => {
  assert.deepEqual(convertMicroLength(1, "in"), { angstrom: 254000000, nm: 25400000, um: 25400, mm: 25.4, in: 1, mil: 1000 });
  assert.deepEqual(convertMicroLength(1, "mil"), { angstrom: 254000, nm: 25400, um: 25.4, mm: 0.0254, in: 0.001, mil: 1 });
  assert.deepEqual(convertMicroLength(1, "um"), { angstrom: 10000, nm: 1000, um: 1, mm: 0.001, in: 0.0000394, mil: 0.0394 });
  assert.equal(convertMicroLength(500, "nm").um, 0.5);
  assert.equal(convertMicroLength(10, "angstrom").nm, 1);
});

test("density: steel 7.85 g/cm3 = 7850 kg/m3 = 0.2836 lb/in3 = 490.06 lb/ft3", () => {
  assert.deepEqual(convertDensity(7.85, "g_cm3"), { g_cm3: 7.85, kg_m3: 7850, lb_in3: 0.2836, lb_ft3: 490.06 });
  assert.equal(convertDensity(2700, "kg_m3").g_cm3, 2.7);
  assert.equal(convertDensity(0.2836, "lb_in3").g_cm3, 7.85);
  assert.equal(convertDensity(490.06, "lb_ft3").g_cm3, 7.85);
});

test("corrosion rate: 1 mm/yr = 39.37 mpy = 1000 um/yr; NACE bands", () => {
  const r = convertCorrosionRate(1, "mm_yr");
  assert.deepEqual([r.mm_yr, r.mpy, r.um_yr], [1, 39.37, 1000]);
  assert.equal(convertCorrosionRate(1, "mpy").mm_yr, 0.0254);
  assert.equal(convertCorrosionRate(25.4, "um_yr").mm_yr, 0.0254);
  // 1 g/(m2 day) on steel (7.85 g/cm3): 0.365 / 7.85 = 0.0465 mm/yr
  assert.equal(convertCorrosionRate(1, "g_m2_day").mm_yr, 0.0465);
  assert.match(convertCorrosionRate(0.9, "mpy").naceRating, /^Outstanding/);
  assert.match(convertCorrosionRate(5, "mpy").naceRating, /^Good/);
  assert.match(convertCorrosionRate(20, "mpy").naceRating, /^Fair/);
  assert.match(convertCorrosionRate(21, "mpy").naceRating, /^Unacceptable/);
  // density changes only the mass-loss column
  const al = convertCorrosionRate(1, "g_m2_day", 2.7);
  assert.equal(al.mm_yr, 0.1352);
});

test("corrosion round trip mpy -> mm/yr -> mpy", () => {
  for (const mpy of [0.5, 5, 20, 120]) {
    const mm = convertCorrosionRate(mpy, "mpy").mm_yr;
    assert.ok(Math.abs(convertCorrosionRate(mm, "mm_yr").mpy - mpy) / mpy < 0.01);
  }
});

// ---------------------------------------------------------------------------------------------------------------
// Dual-unit report (extracted from MetallurgicalUnitConverter.tsx)
// ---------------------------------------------------------------------------------------------------------------

const steel = { hardnessScale: "HRC" as const, hardnessMaterialClass: "non-austenitic-steel" as const };

test("dual-unit report: default scratchpad (Ti-6Al-4V, 34 HRC measured) is NOT converted by the steel table", () => {
  assert.deepEqual(
    computeDualUnitReport({ yieldMpa: 880, utsMpa: 950, hardnessValue: 34, hardnessScale: "HRC", hardnessMaterialClass: "titanium-alloy", cvnJ: 42, testTempC: 23 }),
    {
      yieldKsi: 127.6,
      utsKsi: 137.8,
      hardnessMeasured: "34 HRC",
      hardnessConverted: null, // was 602 HV / 573 HBW (polynomial), then 336 / 319 (steel table applied to titanium)
      hardnessText: "34 HRC (converted values: Unavailable, no conversion table for this alloy class is implemented in this tool)",
      hrc: 34,
      hv: null,
      hbw: null,
      cvnFtLbf: 31,
      tempF: 73.4,
      tempK: 296.1,
    }
  );
});

test("dual-unit report: non-austenitic steel shows the measured value with the E140 conversion in parentheses", () => {
  const r = computeDualUnitReport({ yieldMpa: 0, utsMpa: 0, hardnessValue: 34, ...steel, cvnJ: 0, testTempC: 0 });
  assert.deepEqual([r.hrc, r.hv, r.hbw], [34, 336, 319]); // ASTM E140 Table 1 row HRC 34
  assert.equal(r.hardnessText, "34 HRC (≈ 336 HV / 319 HBW, converted per ASTM E140 tables, not measured)");
  const cold = computeDualUnitReport({ yieldMpa: 0, utsMpa: 0, hardnessValue: 20, ...steel, cvnJ: 27, testTempC: -40 });
  assert.equal(cold.tempF, -40);
  assert.equal(cold.tempK, 233.1); // 233.15 is stored as 233.14999.. so toFixed(1) gives 233.1
  assert.equal(cold.cvnFtLbf, 19.9);
  assert.deepEqual([cold.hv, cold.hbw], [238, 226]); // E140 Table 1, HRC 20
  // outside HRC 20-68 the converted hardness is unavailable instead of clamped, and no "n/a" pair is printed
  const soft = computeDualUnitReport({ yieldMpa: 0, utsMpa: 0, hardnessValue: 15, ...steel, cvnJ: 0, testTempC: 0 });
  assert.deepEqual([soft.hv, soft.hbw, soft.hardnessConverted], [null, null, null]);
  assert.equal(soft.hardnessText, "15 HRC (converted values: Unavailable, outside the verified table range)");
  const hrc62 = computeDualUnitReport({ yieldMpa: 0, utsMpa: 0, hardnessValue: 62, ...steel, cvnJ: 0, testTempC: 0 });
  assert.equal(hrc62.hbw, null); // HBW tabulated to HRC 59
  assert.equal(hrc62.hardnessConverted, "≈ 746 HV"); // only the available scale is listed
  // a synced specimen HV stays primary (old code replaced it by a converted HRC)
  const hv = computeDualUnitReport({ yieldMpa: 0, utsMpa: 0, hardnessValue: 392, hardnessScale: "HV", hardnessMaterialClass: "non-austenitic-steel", cvnJ: 0, testTempC: 0 });
  assert.equal(hv.hardnessText, "392 HV (≈ 40 HRC / 371 HBW, converted per ASTM E140 tables, not measured)");
});

// ---------------------------------------------------------------------------------------------------------------
// ASTM E112
// ---------------------------------------------------------------------------------------------------------------

test("E112: grain number G=8 -> 128 grains/in2 at 100x and 1984 grains/mm2", () => {
  const g8 = calculateAstmE112FromG(8);
  assert.equal(g8.grainsPerSqInch100x, 128); // N_AE = 2^(G-1)
  assert.equal(g8.grainsPerMm2, 1984); // 128 * 15.5
  assert.equal(g8.meanInterceptUm, 20); // l = 10^(-(8 + 3.288)/6.643856) mm = 0.01999 mm (E112 intercept relation)
  assert.match(g8.classification, /^Standard Fine Grain/);
  assert.match(calculateAstmE112FromG(4.9).classification, /^Coarse Grain/);
  assert.match(calculateAstmE112FromG(5).classification, /^Standard Fine Grain/);
  assert.match(calculateAstmE112FromG(12).classification, /^Ultra-Fine/);
  assert.match(calculateAstmE112FromG(12.1).classification, /^Sub-Micron/);
  assert.equal(calculateAstmE112FromG(40).gNumber, 16); // clamp
  assert.equal(calculateAstmE112FromG(-9).gNumber, -3);
});

test("E112: a grain size number step of 1 doubles the grain count", () => {
  for (const g of [0, 3, 5, 8, 10]) {
    const a = calculateAstmE112FromG(g).grainsPerSqInch100x;
    const b = calculateAstmE112FromG(g + 1).grainsPerSqInch100x;
    assert.ok(Math.abs(b / a - 2) < 0.06, `G ${g}->${g + 1}: ${a} -> ${b}`);
  }
});

test("E112: from intercept diameter uses G = -6.643856 log10(d_mm) - 3.288", () => {
  // d = 20 um -> log10(0.02) = -1.69897 -> 11.2879 - 3.288 = 8.0
  assert.equal(calculateAstmE112FromDiameterUm(20).gNumber, 8);
  assert.equal(calculateAstmE112FromDiameterUm(100).gNumber, 3.4); // log10(0.1) = -1 -> 6.643856 - 3.288 = 3.356
  assert.equal(calculateAstmE112FromDiameterUm(1e9).gNumber, calculateAstmE112FromDiameterUm(2000).gNumber); // clamped to 2000 um
  assert.equal(calculateAstmE112FromDiameterUm(0).gNumber, calculateAstmE112FromDiameterUm(0.5).gNumber); // clamped to 0.5 um
});

// FIXED (2026-10): calculateAstmE112FromG returned 1000/sqrt(2^(G+3)) um, a planimetric diameter (with 16 instead of
// E112's 15.5 grains/mm^2 per grain/in^2-at-100x), and labelled it "Mean Intercept (d)", while
// calculateAstmE112FromDiameterUm (input labelled "Mean Intercept Diameter (µm)") inverted the intercept relation
// G = -6.643856 log10(l_mm) - 3.288. Both directions now use that intercept relation, so the labels are true and
// G -> l -> G is the identity. No UI wording changed.
test("E112 round trip G -> intercept -> G is the identity over the whole clamp range", () => {
  for (let i = -30; i <= 160; i++) {
    const g = i / 10;
    const r = calculateAstmE112FromG(g);
    // displayed (rounded to 0.01 um) intercept fed back returns the same displayed G
    // (+ 0 folds -0, which toFixed(1) yields for G = -0.00001; React renders both as "0")
    assert.equal(calculateAstmE112FromDiameterUm(r.meanInterceptUm).gNumber + 0, r.gNumber + 0, `G ${g} -> ${r.meanInterceptUm} um`);
    // unrounded: the forward map is the algebraic inverse of G = -6.643856 log10(l_mm) - 3.288
    const lMm = Math.pow(10, -(g + 3.288) / 6.643856);
    assert.ok(Math.abs(-6.643856 * Math.log10(lMm) - 3.288 - g) < 1e-12);
    assert.equal(r.meanInterceptUm, Number((lMm * 1000).toFixed(2)));
  }
  // and intercept -> G -> intercept returns the input inside the un-clamped range
  for (const d of [2, 5, 10, 20, 22.4, 50, 100, 250, 500, 900]) {
    assert.equal(calculateAstmE112FromDiameterUm(d).meanInterceptUm, d, `d ${d}`);
  }
});

test("E112 intercept table: l = 320 um / sqrt(2)^G (E112 intercept relation, G 0 -> 320 um, G 8 -> 20 um)", () => {
  for (const g of [0, 2, 4, 6, 8, 10, 12]) {
    const expected = 320 / Math.SQRT2 ** g;
    assert.ok(Math.abs(calculateAstmE112FromG(g).meanInterceptUm - expected) <= 0.005 + expected * 1e-4, `G ${g}`);
  }
});

// HISTORICAL (pre-fix "Mean Intercept (d)" values, pinned so reviewers see the delta).
test("HISTORICAL E112 FromG intercept before the fix: planimetric 1000/sqrt(2^(G+3)), round trip 8 -> 22.1 um -> 7.7", () => {
  const oldIntercept = (g: number) => Number((1000 / Math.sqrt(Math.pow(2, g + 3))).toFixed(2));
  assert.deepEqual(
    [4, 6, 8, 10, 12, 14].map((g) => [g, oldIntercept(g), calculateAstmE112FromG(g).meanInterceptUm]),
    [
      [4, 88.39, 79.99],
      [6, 44.19, 40],
      [8, 22.1, 20],
      [10, 11.05, 10],
      [12, 5.52, 5],
      [14, 2.76, 2.5],
    ]
  );
  assert.equal(calculateAstmE112FromDiameterUm(oldIntercept(8)).gNumber, 7.7); // the old inconsistency
  // G from a typed intercept is unchanged by the fix (22.4 um -> 7.7); only the echoed intercept changed (24.75 -> 22.4)
  assert.equal(calculateAstmE112FromDiameterUm(22.4).gNumber, 7.7);
  assert.equal(calculateAstmE112FromDiameterUm(22.4).meanInterceptUm, 22.4);
});

// ---------------------------------------------------------------------------------------------------------------
// Hardness: the unit converter now uses the shared convertSteelHardness (src/utils/hardnessConversion.ts; full
// coverage in tests/utils-hardness-conversion.test.ts). The studio-lane todo tests below are now real tests.
// ---------------------------------------------------------------------------------------------------------------

test("hardness from HV 300: E140 Table 1 interpolation, ISO 18265 Rm, HRB unavailable (old: HRB 101.8, Rm 975)", () => {
  const r = convertSteelHardness(300, "HV");
  assert.equal(r.HV, 300);
  assert.equal(r.HRC, 30); // 29.75 between HRC 29 (294 HV) and 30 (302 HV), reported as a whole number
  assert.equal(r.HBW, 284); // 279 + 7 * 6/8 = 284.25
  assert.equal(r.HK, 309); // 304 + 7 * 6/8 = 309.25
  assert.equal(r.HRB, null);
  assert.equal(r.tensileRm_MPa, 965); // ISO 18265 Table A.1
  assert.equal(r.tensileRm_ksi, 140);
  assert.equal(r.validRangeNote, "Approximate conversion for non-austenitic steels per ASTM E140 / ISO 18265 tables; not a substitute for direct testing.");
  // HK <-> HV is a table now, not HK = 1.03 HV (old: HK 1000 -> HV 971)
  assert.equal(convertSteelHardness(1000, "HK").HV, null); // above HK 920 (HRC 68)
  assert.equal(convertSteelHardness(convertSteelHardness(500, "HV").HK!, "HK").HV, 500);
  // no input clamps (old: HV 5 -> 40, HV 5000 -> 2000): the input is echoed, nothing is derived
  assert.equal(convertSteelHardness(5, "HV").HRC, null);
  assert.equal(convertSteelHardness(5000, "HV").HV, 5000);
  assert.equal(convertSteelHardness(5000, "HV").HRC, null);
});

test("hardness out-of-range notices", () => {
  assert.match(convertSteelHardness(19, "HRC").validRangeNote, /^Input outside verified range \(HRC 20-68\): conversion unavailable\./);
  assert.match(convertSteelHardness(69, "HRC").validRangeNote, /outside verified range \(HRC 20-68\)/);
  assert.doesNotMatch(convertSteelHardness(40, "HRC").validRangeNote, /outside/);
  assert.match(convertSteelHardness(39, "HRB").validRangeNote, /outside verified range \(HRB 55-100\)/);
});

test("hardness interpretation bands (non-austenitic steels only)", () => {
  const steel = (hv: number) => interpretHardness(hv, "non-austenitic-steel")!.condition;
  assert.match(steel(159), /^Dead Soft/);
  assert.match(steel(160), /^Normalized/);
  assert.match(steel(449), /^Quenched & Tempered/);
  assert.match(steel(450), /^Fully Hardened/);
  assert.match(steel(750), /^Super-Hard Nitride Case$/);
  // The bands were applied to any HV, e.g. a measured Ni-alloy 380 HV read "Quenched & Tempered" and an
  // aluminium 120 HV read "Dead Soft / Solution Annealed". Every non-steel class now gets no band.
  for (const cls of ["austenitic-steel", "titanium-alloy", "nickel-alloy", "aluminium-alloy", "hardmetal", "other"] as const) {
    assert.equal(interpretHardness(380, cls), null, cls);
  }
  // No non-steel examples remain in the steel bands.
  for (const hv of [100, 200, 300, 500, 800]) {
    const text = JSON.stringify(interpretHardness(hv, "non-austenitic-steel"));
    assert.doesNotMatch(text, /Inconel|copper|WC-Co|Cemented Carbide/i, String(hv));
  }
  assert.match(HARDNESS_INTERPRETATION_NOTE, /non-austenitic steels only/);
  assert.match(HARDNESS_INTERPRETATION_UNAVAILABLE, /^Unavailable/);
  // Review S2 (sources in metallurgicalConversions.ts): 300M landing gear at 52-55 HRC (~545-595 HV) belongs to the
  // 450-750 band, not 280-450; normalized 4140 (302 HB ~ 318 HV) is not a 160-280 example; >= 750 HV is CBN-turnable;
  // "Solution Annealed" is not a non-austenitic steel condition.
  const band = (hv: number) => JSON.stringify(interpretHardness(hv, "non-austenitic-steel"));
  assert.match(band(570), /300M landing gear/);
  assert.doesNotMatch(band(400), /landing gear/);
  assert.doesNotMatch(band(200), /4140/);
  assert.match(band(318), /normalized or Q&T 4140/);
  assert.match(band(800), /CBN hard turning/);
  assert.doesNotMatch(band(800), /EDM|ultrasonic|only/);
  assert.doesNotMatch(band(100), /Solution Annealed/);
  assert.match(steel(100), /^Dead Soft \/ Annealed$/);
});

test("report hardness line: no placeholder value after 'Load Active Specimen' (review S2 code)", () => {
  assert.equal(reportHardnessLine(true, "34 HRC (…)", null), "34 HRC (…)");
  assert.equal(reportHardnessLine(false, "34 HRC (…)", "Hardness not loaded from the active specimen: x"), "not entered (Hardness not loaded from the active specimen: x)");
  assert.equal(reportHardnessLine(false, "34 HRC", null), "not entered");
});

// Former BUG (studio lane, fixed 2026-10): the polynomials HV = 142.8 + 8.94 HRC + 0.134 HRC^2 and
// HRC = -20.6 + 0.098 HV - 0.000045 HV^2 (clamped 18..70) gave HRC 40 -> HV 715 -> HRC 26.5. They were removed and
// replaced by interpolation in the ASTM E140 Table 1 rows below, read from three public reproductions of the table
// (labtesting.com chart-hardness-c.pdf, andersonlabs.com ASTM-Hardness-Conversion-Table-Rockwell-C-Range.pdf, Struers
// poster at epsevg.upc.edu; identical values; see src/utils/hardnessConversion.ts for the full URLs).
const E140_HRC_HV: Array<[number, number]> = [[20, 238], [30, 302], [40, 392], [50, 513], [60, 697]];

test("HRC -> HV matches the ASTM E140 Table 1 rows exactly", () => {
  for (const [hrc, hv] of E140_HRC_HV) {
    assert.equal(convertSteelHardness(hrc, "HRC").HV, hv, `HRC ${hrc}`);
  }
});

test("HV -> HRC matches the ASTM E140 Table 1 rows exactly (old code: clamp floor 18 for HV 302/392/513)", () => {
  for (const [hrc, hv] of E140_HRC_HV) {
    assert.equal(convertSteelHardness(hv, "HV").HRC, hrc, `HV ${hv}`);
  }
});

test("HRC -> HV -> HRC round trip: whole HRC exact, 0.5 steps within 0.6 HRC (integer HV, whole-number HRC)", () => {
  for (const hrc of [20, 25, 30, 34, 40, 45.5, 50, 55, 60, 67.5, 68]) {
    const hv = convertSteelHardness(hrc, "HRC").HV;
    assert.ok(hv !== null);
    const back = convertSteelHardness(hv, "HV").HRC;
    assert.ok(back !== null && Math.abs(back - hrc) <= (Number.isInteger(hrc) ? 0 : 0.6), `HRC ${hrc} -> HV ${hv} -> HRC ${back}`);
  }
});

// Former minor BUG: HV = 1.05 HBW - 5 inverted as HBW = HV / 1.05 (HBW 200 -> HV 205 -> HBW 195). HBW now comes from
// the E140 Table 1 carbide-ball column (HBW 226-634); HBW 120 and 200 are outside it and unavailable.
test("HBW -> HV -> HBW round trip is the identity on the tabulated range", () => {
  for (const hbw of [226, 300, 371, 450, 634]) {
    const hv = convertSteelHardness(hbw, "HBW").HV;
    assert.ok(hv !== null);
    assert.equal(convertSteelHardness(hv, "HV").HBW, hbw, `HBW ${hbw} -> HV ${hv}`);
  }
  for (const hbw of [120, 200]) assert.equal(convertSteelHardness(hbw, "HBW").HV, null);
});
