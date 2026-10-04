import assert from "node:assert/strict";
import test from "node:test";
import {
  HARDNESS_CONVERSION_DISCLAIMER,
  HARDNESS_VERIFIED_RANGES,
  convertSteelHardness as convert,
} from "../src/utils/hardnessConversion";

// Reference values, read from the public reproductions cited in src/utils/hardnessConversion.ts:
//   ASTM E140 Table 1 (non-austenitic steels): [A] labtesting.com chart-hardness-c.pdf, [B] andersonlabs.com Rockwell C
//   range table, [C] Struers poster (epsevg.upc.edu) -- identical in all three.
//   ASTM E140 Table 2: [D] andersonlabs.com Rockwell B range table, [E] microstar2000.com MS002.
//   ISO 18265 Table A.1: [F] Bossard D.021, [G] stahlnetz.de Haertevergleichstabelle -- identical Rm/HV pairs.

// HRC, HV, HBW (carbide ball), HK -- a subset of E140 Table 1 rows ([A][B][C])
const E140_T1_ROWS: Array<[number, number, number | null, number]> = [
  [20, 238, 226, 251],
  [25, 266, 253, 278],
  [30, 302, 286, 311],
  [34, 336, 319, 342],
  [40, 392, 371, 402],
  [45, 446, 421, 466],
  [50, 513, 481, 542],
  [55, 595, 560, 630],
  [59, 674, 634, 710],
  [60, 697, null, 732],
  [65, 832, null, 846],
  [68, 940, null, 920],
];

test("HRC -> HV/HBW/HK reproduces ASTM E140 Table 1 rows exactly", () => {
  for (const [hrc, hv, hbw, hk] of E140_T1_ROWS) {
    const r = convert(hrc, "HRC");
    assert.equal(r.HV, hv, `HRC ${hrc} HV`);
    assert.equal(r.HBW, hbw, `HRC ${hrc} HBW`);
    assert.equal(r.HK, hk, `HRC ${hrc} HK`);
    assert.equal(r.HRC, hrc);
  }
});

test("HV -> HRC and HBW -> HRC invert the same rows exactly", () => {
  for (const [hrc, hv, hbw, hk] of E140_T1_ROWS) {
    assert.equal(convert(hv, "HV").HRC, hrc, `HV ${hv}`);
    assert.equal(convert(hk, "HK").HRC, hrc, `HK ${hk}`);
    if (hbw !== null) {
      assert.equal(convert(hbw, "HBW").HRC, hrc, `HBW ${hbw}`);
      assert.equal(convert(hbw, "HBW").HV, hv, `HBW ${hbw} -> HV`);
      assert.equal(convert(hv, "HV").HBW, hbw, `HV ${hv} -> HBW`);
    }
  }
});

// HRB, HV, HK -- a subset of E140 Table 2 rows ([D][E]); HRB 84 -> HV 162 (see the source note in the util)
const E140_T2_ROWS: Array<[number, number, number]> = [
  [55, 100, 112],
  [60, 107, 120],
  [70, 125, 139],
  [80, 150, 164],
  [84, 162, 176],
  [90, 185, 201],
  [95, 210, 226],
  [99, 234, 246],
  [100, 240, 251],
];

test("HRB <-> HV/HK reproduces ASTM E140 Table 2 rows exactly", () => {
  for (const [hrb, hv, hk] of E140_T2_ROWS) {
    const r = convert(hrb, "HRB");
    assert.equal(r.HV, hv, `HRB ${hrb}`);
    assert.equal(convert(hv, "HV").HRB, hrb, `HV ${hv}`);
    if (hrb < 100) assert.equal(r.HK, hk, `HRB ${hrb} HK`); // HRB 100 overlaps HRC 20 (HK 251 at HV 238)
  }
});

test("forward and inverse are consistent: round trips stay within the display rounding", () => {
  let worstHrc = 0;
  for (let i = 200; i <= 680; i++) {
    const hrc = i / 10;
    const hv = convert(hrc, "HRC").HV;
    assert.ok(hv !== null, `HRC ${hrc}`);
    const back = convert(hv, "HV").HRC;
    assert.ok(back !== null);
    worstHrc = Math.max(worstHrc, Math.abs(back - hrc));
  }
  // HV is shown as an integer: +-0.5 HV is at most +-0.1 HRC (steepest step HRC 20->21 = 5 HV), plus 0.05 display rounding
  assert.ok(worstHrc <= 0.15 + 1e-9, `worst HRC round trip ${worstHrc}`);

  for (let hbw = 226; hbw <= 634; hbw++) {
    const hv = convert(hbw, "HBW").HV;
    assert.ok(hv !== null);
    const back = convert(hv, "HV").HBW;
    assert.ok(back !== null && Math.abs(back - hbw) <= 1, `HBW ${hbw} -> HV ${hv} -> HBW ${back}`);
  }
  for (let i = 550; i <= 1000; i++) {
    const hrb = i / 10;
    const hv = convert(hrb, "HRB").HV;
    assert.ok(hv !== null);
    const back = convert(hv, "HV").HRB;
    // steepest step HRB 55->56 = 1 HV, so the integer HV costs up to 0.5 HRB there
    assert.ok(back !== null && Math.abs(back - hrb) <= 0.55 + 1e-9, `HRB ${hrb} -> HV ${hv} -> HRB ${back}`);
  }
});

test("every converted scale is monotone in HV across the verified range", () => {
  const prev: Record<string, number> = {};
  for (let hv = 80; hv <= 940; hv += 0.5) {
    const r = convert(hv, "HV");
    for (const k of ["HRC", "HRB", "HBW", "HK", "tensileRm_MPa"] as const) {
      const v = r[k];
      if (v === null) continue;
      if (prev[k] !== undefined) assert.ok(v >= prev[k], `${k} decreases at HV ${hv}`);
      prev[k] = v;
    }
  }
});

test("outside the tabulated range the result is unavailable (no extrapolation, no clamping)", () => {
  for (const hrc of [19.9, 68.1, 15, 72, Number.NaN]) {
    const r = convert(hrc, "HRC");
    assert.equal(r.HV, null, `HRC ${hrc}`);
    assert.equal(r.HBW, null);
    assert.equal(r.tensileRm_MPa, null);
    assert.equal(r.unavailable.HV, "input outside verified range");
  }
  assert.match(convert(15, "HRC").validRangeNote, /^Input outside verified range \(HRC 20-68\): conversion unavailable\./);
  // the old polynomial clamped HV 300 to HRB 101.8 and HV 230-515 to HRC 18
  assert.equal(convert(300, "HV").HRB, null);
  assert.equal(convert(300, "HV").unavailable.HRB, "outside verified range (HRB 55-100)");
  assert.equal(convert(237, "HV").HRC, null);
  assert.equal(convert(941, "HV").HRC, null);
  assert.equal(convert(2000, "HV").HV, 2000); // the input is echoed, nothing is derived from it
  assert.equal(convert(2000, "HV").HK, null);
  assert.equal(convert(225, "HBW").HV, null);
  assert.equal(convert(635, "HBW").HV, null);
  assert.equal(convert(697, "HV").HBW, null); // HRC 60: Brinell is bracketed / blank in the sources
  assert.equal(convert(54.9, "HRB").HV, null);
  assert.equal(convert(111, "HK").HV, null);
  assert.equal(convert(921, "HK").HV, null);
  assert.deepEqual(HARDNESS_VERIFIED_RANGES.HRC, { min: 20, max: 68 });
});

test("Leeb (HLD) is never converted", () => {
  const fromHld = convert(600, "HLD");
  assert.equal(fromHld.HLD, 600);
  for (const k of ["HV", "HRC", "HRB", "HBW", "HK", "tensileRm_MPa"] as const) assert.equal(fromHld[k], null);
  assert.match(fromHld.unavailable.HV!, /Leeb \(HLD\) conversion unavailable/);
  assert.equal(convert(40, "HRC").HLD, null);
  assert.match(convert(40, "HRC").unavailable.HLD!, /no verified conversion table/);
});

// HV -> Rm (MPa), ISO 18265 Table A.1 ([F][G])
const ISO_RM_ROWS: Array<[number, number]> = [[80, 255], [100, 320], [200, 640], [300, 965], [400, 1290], [500, 1630], [600, 1995], [650, 2180]];

test("tensile strength estimate reproduces ISO 18265 Table A.1 and stops at HV 80 / 650", () => {
  for (const [hv, rm] of ISO_RM_ROWS) {
    assert.equal(convert(hv, "HV").tensileRm_MPa, rm, `HV ${hv}`);
  }
  assert.equal(convert(300, "HV").tensileRm_ksi, 140.0); // 965 MPa * 0.1450377
  assert.equal(convert(305, "HV").tensileRm_MPa, 980); // midway 965..995
  assert.equal(convert(79, "HV").tensileRm_MPa, null);
  assert.equal(convert(651, "HV").tensileRm_MPa, null);
  assert.equal(convert(651, "HV").unavailable.Rm, "outside ISO 18265 Table A.1 range (HV 80-650)");
  assert.equal(convert(90, "HV").HRB, null); // below Table 2 but still inside the Rm table
  assert.equal(convert(90, "HV").tensileRm_MPa, 285);
});

test("independent cross-check: ISO 18265 Table A.1 HRC values ([F]) agree with the E140 interpolation within 0.15 HRC", () => {
  const isoHvHrc: Array<[number, number]> = [[240, 20.3], [300, 29.8], [400, 40.8], [500, 49.1], [600, 55.2], [700, 60.1], [800, 64.0], [900, 67.0]];
  for (const [hv, hrcIso] of isoHvHrc) {
    const got = convert(hv, "HV").HRC;
    assert.ok(got !== null && Math.abs(got - hrcIso) <= 0.15, `HV ${hv}: ${got} vs ISO ${hrcIso}`);
  }
});

test("the result carries the approximate-conversion disclaimer", () => {
  assert.equal(
    HARDNESS_CONVERSION_DISCLAIMER,
    "Approximate conversion for non-austenitic steels per ASTM E140 / ISO 18265 tables; not a substitute for direct testing."
  );
  assert.equal(convert(40, "HRC").validRangeNote, HARDNESS_CONVERSION_DISCLAIMER);
});
