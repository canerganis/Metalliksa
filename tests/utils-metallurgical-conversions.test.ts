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
  convertMetallurgicalHardness,
  convertMicroLength,
  convertStress,
  convertTemperature,
  interpretHardness,
  interpretStressMpa,
  type TempUnit,
} from "../src/utils/metallurgicalConversions";

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

test("dual-unit report reproduces the pre-extraction numbers (default scratchpad inputs)", () => {
  assert.deepEqual(computeDualUnitReport({ yieldMpa: 880, utsMpa: 950, hardnessHrc: 34, cvnJ: 42, testTempC: 23 }), {
    yieldKsi: 127.6,
    utsKsi: 137.8,
    hv: 602, // see the HRC->HV bug todo below
    hbw: 573,
    cvnFtLbf: 31,
    tempF: 73.4,
    tempK: 296.1,
  });
  const cold = computeDualUnitReport({ yieldMpa: 0, utsMpa: 0, hardnessHrc: 20, cvnJ: 27, testTempC: -40 });
  assert.equal(cold.tempF, -40);
  assert.equal(cold.tempK, 233.1); // 233.15 is stored as 233.14999.. so toFixed(1) gives 233.1
  assert.equal(cold.cvnFtLbf, 19.9);
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
// Hardness
// ---------------------------------------------------------------------------------------------------------------

test("hardness from HV: HBW = HV/1.05, HK = 1.03 HV, Rm = 3.25 HV (the parts that are consistent today)", () => {
  const r = convertMetallurgicalHardness(300, "HV");
  assert.equal(r.HV, 300);
  assert.equal(r.HBW, 286); // 285.7
  assert.equal(r.HK, 309);
  assert.equal(r.tensileRm_MPa, 975); // 300 * 3.25
  assert.equal(r.tensileRm_ksi, 141.4);
  assert.equal(r.validRangeNote, "ASTM E140 & ISO 18265 calibrated correlation");
  // HK <-> HV round trip
  assert.equal(convertMetallurgicalHardness(1000, "HK").HV, 971); // 1000 / 1.03
  assert.equal(convertMetallurgicalHardness(convertMetallurgicalHardness(500, "HV").HK, "HK").HV, 500);
  // input clamps
  assert.equal(convertMetallurgicalHardness(5, "HV").HV, 40);
  assert.equal(convertMetallurgicalHardness(5000, "HV").HV, 2000);
});

test("hardness out-of-range notices", () => {
  assert.match(convertMetallurgicalHardness(19, "HRC").validRangeNote, /outside ASTM E140 certified HRC range/);
  assert.match(convertMetallurgicalHardness(69, "HRC").validRangeNote, /outside ASTM E140 certified HRC range/);
  assert.equal(convertMetallurgicalHardness(40, "HRC").validRangeNote, "ASTM E140 & ISO 18265 calibrated correlation");
  assert.match(convertMetallurgicalHardness(39, "HRB").validRangeNote, /HRB ball indenter range/);
});

test("hardness interpretation bands", () => {
  assert.match(interpretHardness(159).condition, /^Dead Soft/);
  assert.match(interpretHardness(160).condition, /^Normalized/);
  assert.match(interpretHardness(449).condition, /^Quenched & Tempered/);
  assert.match(interpretHardness(450).condition, /^Fully Hardened/);
  assert.match(interpretHardness(750).condition, /^Super-Hard/);
});

test("pins today's HRC <-> HV outputs (these disagree with ASTM E140; see the todo tests below)", () => {
  const hrc40 = convertMetallurgicalHardness(40, "HRC");
  assert.deepEqual([hrc40.HV, hrc40.HRC, hrc40.HBW, hrc40.tensileRm_MPa], [715, 26.5, 681, 2323]);
  const hv392 = convertMetallurgicalHardness(392, "HV");
  assert.equal(hv392.HRC, 18); // clamped floor
  assert.equal(convertMetallurgicalHardness(300, "HV").HRC, 18);
});

// BUG (reported, NOT fixed: scientific-calculation changes need the user). The Rockwell C <-> Vickers polynomials
//   HV  = 142.8 + 8.94 HRC + 0.134 HRC^2        (HRC -> HV)
//   HRC = -20.6 + 0.098 HV - 0.000045 HV^2      (HV -> HRC, clamped to [18, 70])
// do not reproduce the ASTM E140 / ISO 18265 tables for steel, and are not inverses of each other:
//   HRC 30: code HV 532, E140 302   | HRC 40: code 715, E140 392   | HRC 50: code 925, E140 513
//   HRC 60: code 1162, E140 697     | the default report input HRC 34 shows HV 602 / HBW 573 (E140: ~336 HV)
//   HV 302 -> code HRC 18 (clamp floor), E140 HRC 30;  HV 392 -> 18 (E140 40);  HV 513 -> 18.0 (E140 50)
//   Round trip HRC 40 -> HV 715 -> HRC 26.5.  Also HV 300 -> HRB 101.8 although HRB tops out near HV 240.
// The same polynomials are duplicated in metallurgyCalculations.convertHardness (Pocket Calculators).
// Reference anchors (non-austenitic steel, E140 Table 1 / ISO 18265 Table A.1): HRC 20=238 HV, 30=302, 40=392,
// 50=513, 60=697.
const E140_HRC_HV: Array<[number, number]> = [[20, 238], [30, 302], [40, 392], [50, 513], [60, 697]];

test(
  "HRC -> HV matches the ASTM E140 steel table within 3 %",
  { todo: "BUG: polynomial 142.8 + 8.94 HRC + 0.134 HRC^2 over-predicts HV by 30-130 %; see comment block" },
  () => {
    for (const [hrc, hv] of E140_HRC_HV) {
      const got = convertMetallurgicalHardness(hrc, "HRC").HV;
      assert.ok(Math.abs(got - hv) / hv < 0.03, `HRC ${hrc}: ${got} vs E140 ${hv}`);
    }
  }
);

test(
  "HV -> HRC matches the ASTM E140 steel table within 1 HRC",
  { todo: "BUG: polynomial -20.6 + 0.098 HV - 0.000045 HV^2 returns the clamp floor 18 for HV 230-515; see comment block" },
  () => {
    for (const [hrc, hv] of E140_HRC_HV) {
      const got = convertMetallurgicalHardness(hv, "HV").HRC;
      assert.ok(got !== undefined && Math.abs(got - hrc) <= 1, `HV ${hv}: ${got} vs E140 ${hrc}`);
    }
  }
);

test(
  "HRC -> HV -> HRC round trip returns the input within 1 HRC",
  { todo: "BUG: the two polynomials are not inverses (HRC 40 -> HV 715 -> HRC 26.5)" },
  () => {
    for (const hrc of [25, 30, 40, 50, 60]) {
      const hv = convertMetallurgicalHardness(hrc, "HRC").HV;
      const back = convertMetallurgicalHardness(hv, "HV").HRC;
      assert.ok(back !== undefined && Math.abs(back - hrc) <= 1, `HRC ${hrc} -> HV ${hv} -> HRC ${back}`);
    }
  }
);

// Minor: HV = 1.05 HBW - 5 is inverted as HBW = HV / 1.05 (the -5 offset is not undone): HBW 200 -> HV 205 -> HBW 195.
test(
  "HBW -> HV -> HBW round trip is the identity",
  { todo: "BUG (minor): forward HV = 1.05 HBW - 5, inverse HBW = HV / 1.05; HBW 200 -> HV 205 -> HBW 195" },
  () => {
    for (const hbw of [120, 200, 300, 450]) {
      assert.equal(convertMetallurgicalHardness(hbw, "HBW").HBW, hbw);
    }
  }
);
