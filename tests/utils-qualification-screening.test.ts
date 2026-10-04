import assert from "node:assert/strict";
import test from "node:test";
import { calculateMMPDSToleranceFactor } from "../src/components/uqLabData";
import { buildQualificationChecklist, computeQualificationMmpdsStats } from "../src/utils/qualificationScreening";

// Golden values were first captured from the UNMODIFIED inline useMemo of StandardQualificationEngine.tsx (HEAD faa6684)
// by a differential run over 324 input combinations before the component was wired to this module (verified once by the
// p8-studio-tests lane; script not retained). The k_A / k_B grouping bug was fixed afterwards, and k then switched to
// the exact noncentral-t table for N <= 300 (shared toleranceFactors.ts, same as the aerospace screen); the values
// below are current and the earlier values are kept in the HISTORICAL block at the end of this file.

const base = { meanYieldMpa: 930, meanTensileMpa: 1010, fractureToughnessMpaM: 68, sampleSizeN: 60, customScatterCv: 2.8 };

test("default screening inputs (exact noncentral-t k)", () => {
  assert.deepEqual(computeQualificationMmpdsStats(base), {
    meanYield: 930,
    meanTensile: 1010,
    stdDev: 26,
    covPct: 2.8,
    sampleSize: 60,
    kA: 2.808,
    kB: 1.609,
    aBasisYield: 857,
    bBasisYield: 888,
    sBasisYield: 852,
    aBasisTensile: 931,
    bBasisTensile: 964,
    shearUltimate: 559,
    bearingYield: 1286,
    bearingUltimate: 1862,
    compressiveYield: 891,
    fractureToughnessKic: 68,
    cpk: 1.79,
    status: "A-Basis Qualified",
  });
});

test("golden table: small sample, high scatter and clamped inputs", () => {
  const n20 = computeQualificationMmpdsStats({ ...base, sampleSizeN: 20 });
  assert.deepEqual(
    [n20.kA, n20.kB, n20.aBasisYield, n20.bBasisYield, n20.aBasisTensile, n20.bBasisTensile, n20.status],
    [3.296, 1.926, 844, 880, 917, 956, "S-Basis Provisional"]
  );
  const highCv = computeQualificationMmpdsStats({ ...base, customScatterCv: 8.5 });
  assert.deepEqual(
    [highCv.stdDev, highCv.covPct, highCv.aBasisYield, highCv.bBasisYield, highCv.sBasisYield, highCv.cpk, highCv.status],
    [79, 8.5, 708, 803, 693, 0.59, "B-Basis Qualified"]
  );
  // N below 10 is clamped to 10 and scatter below 1 % is clamped to 1 %.
  const clamped = computeQualificationMmpdsStats({
    meanYieldMpa: 500,
    meanTensileMpa: 600,
    fractureToughnessMpaM: 30,
    sampleSizeN: 5,
    customScatterCv: 0.2,
  });
  assert.equal(clamped.sampleSize, 10);
  assert.equal(clamped.covPct, 1);
  assert.deepEqual(
    [clamped.stdDev, clamped.kA, clamped.kB, clamped.aBasisYield, clamped.bBasisYield, clamped.cpk, clamped.status],
    [5, 3.982, 2.355, 480, 488, 5, "S-Basis Provisional"]
  );
});

test("hand-computed oracle for the allowable arithmetic (given k)", () => {
  const r = computeQualificationMmpdsStats(base);
  const sd = 930 * 0.028; // 26.04 MPa
  assert.equal(r.aBasisYield, Math.round(930 - r.kA * sd));
  assert.equal(r.bBasisYield, Math.round(930 - r.kB * sd));
  assert.equal(r.sBasisYield, Math.round(930 - 3 * sd));
  const sdT = 1010 * 0.028;
  assert.equal(r.aBasisTensile, Math.round(1010 - r.kA * sdT));
  assert.equal(r.shearUltimate, Math.round(r.aBasisTensile * 0.6));
  assert.equal(r.bearingYield, Math.round(r.aBasisYield * 1.5));
  assert.equal(r.bearingUltimate, Math.round(r.aBasisTensile * 2));
  assert.equal(r.compressiveYield, Math.round(r.aBasisYield * 1.04));
  // Cpk = (mean - 0.85 mean) / (3 sd) = 0.05 / cov
  assert.equal(r.cpk, Number((0.05 / 0.028).toFixed(2)));
});

test("allowables never go negative and are ordered S/A <= B <= mean", () => {
  const wild = computeQualificationMmpdsStats({ ...base, customScatterCv: 90, meanYieldMpa: 100, meanTensileMpa: 120 });
  assert.equal(wild.aBasisYield, 0);
  assert.equal(wild.aBasisTensile, 0);
  const r = computeQualificationMmpdsStats(base);
  assert.ok(r.aBasisYield <= r.bBasisYield && r.bBasisYield <= r.meanYield);
});

test("status ladder: N<30 provisional, Cpk<1.33 demotes to B-basis (the cov>6 branch is redundant)", () => {
  const status = (sampleSizeN: number, customScatterCv: number) =>
    computeQualificationMmpdsStats({ ...base, sampleSizeN, customScatterCv }).status;
  assert.equal(status(29, 2.8), "S-Basis Provisional");
  assert.equal(status(30, 2.8), "A-Basis Qualified");
  // Cpk = 0.05/cov crosses 1.33 near cov 3.76 %.
  assert.equal(status(60, 3.7), "A-Basis Qualified"); // cpk 1.35
  assert.equal(status(60, 3.8), "B-Basis Qualified"); // cpk 1.32
  assert.equal(status(60, 6), "B-Basis Qualified");
  // N<30 wins over scatter.
  assert.equal(status(10, 30), "S-Basis Provisional");
});

test("checklist rows are template-only: never a pass, always Not executed", () => {
  const rows = buildQualificationChecklist({
    fractureToughnessMpaM: 68,
    serviceTempMin: -54,
    serviceTempMax: 350,
    operatingStressMpa: 550,
    cpk: 1.79,
  });
  assert.deepEqual(
    rows.map((r) => r.id),
    ["mil-salt-fog", "mil-shock", "mil-thermal-shock", "mil-vibration", "as9100-cpk", "nato-scc"]
  );
  for (const r of rows) {
    assert.equal(r.passProbabilityPct, 0);
    assert.equal(r.executionStatus, "Not executed");
    assert.equal(r.riskLevel, "Low");
    assert.match(r.primaryThreat, /^Not evaluated/);
    assert.match(r.mitigationRecommendation, /^Checklist item only/);
  }
  assert.equal(rows[1].criticalThreshold, "User-entered K_IC: 68 MPa√m (not a test result)");
  assert.equal(rows[2].criticalThreshold, "Entered ΔT: 404°C (user input)");
  assert.equal(rows[3].criticalThreshold, "Entered operating stress: 550 MPa (user input)");
  assert.equal(rows[4].criticalThreshold, "Slider Cpk: 1.79 (not AS9100 evidence)");
});

// ---------------------------------------------------------------------------------------------------------------
// FORMULA BUG FIXED (2026-10). StandardQualificationEngine used to compute the Natrella one-sided tolerance factor as
//   k = z_p + sqrt(z_p^2 - a*b) / a          (the division bound only to the sqrt term)
// whereas the Natrella / Lieberman-Resnikoff formula is
//   k = (z_p + sqrt(z_p^2 - a*b)) / a,   a = 1 - z_g^2/(2(N-1)),  b = z_p^2 - z_g^2/N.
// It now shares toleranceFactors.ts with AerospaceAuditReportGenerator, which uses the EXACT noncentral-t factor for
// N <= 300 (tests/fixtures/one-sided-tolerance-factor-oracle.json, scipy; rounded up) and Natrella above; proof in
// tests/utils-tolerance-factor.test.ts.
//   A-basis N=10: misgrouped 3.528   Natrella 3.940   exact 3.981 -> 3.982     N=60: 2.746  2.801  2.807 -> 2.808
//   B-basis N=10: misgrouped 2.094   Natrella 2.321   exact 2.355 -> 2.355     N=60: 1.574  1.604  1.609 -> 1.609
// ---------------------------------------------------------------------------------------------------------------
test("kA/kB are never below the independent Natrella implementation in uqLabData, and within 1.5 % of it", () => {
  for (const N of [10, 30, 60, 100]) {
    const r = computeQualificationMmpdsStats({ ...base, sampleSizeN: N });
    const kA = calculateMMPDSToleranceFactor(N, 0.99, 0.95)!;
    const kB = calculateMMPDSToleranceFactor(N, 0.9, 0.95)!;
    assert.ok(r.kA >= kA - 0.0005 && r.kA - kA < 0.015 * kA, `N=${N}: kA ${r.kA} vs Natrella ${kA}`);
    assert.ok(r.kB >= kB - 0.0005 && r.kB - kB < 0.015 * kB, `N=${N}: kB ${r.kB} vs Natrella ${kB}`);
  }
});

test("kA/kB values by N (exact noncentral-t, rounded up)", () => {
  const byN = Object.fromEntries(
    [10, 30, 60, 100].map((N) => {
      const r = computeQualificationMmpdsStats({ ...base, sampleSizeN: N });
      return [N, [r.kA, r.kB]];
    })
  );
  assert.deepEqual(byN, { 10: [3.982, 2.355], 30: [3.064, 1.778], 60: [2.808, 1.609], 100: [2.684, 1.527] });
});

// ---------------------------------------------------------------------------------------------------------------
// HISTORICAL (values displayed by StandardQualificationEngine before 2026-10, pinned so reviewers see the delta):
// "misgrouped" = original k = z + sqrt(..)/a; "natrella" = after the grouping fix (ceeed0a), before the exact table.
// Every k-dependent field is pinned in all three versions, so a field the change did not move is asserted EQUAL
// (not just "<="), and the fields k does not enter are checked against their own formulas.
// ---------------------------------------------------------------------------------------------------------------
test("HISTORICAL qualification outputs: misgrouped -> Natrella -> exact table, field by field", () => {
  const K_FIELDS = ["kA", "kB", "aBasisYield", "bBasisYield", "aBasisTensile", "bBasisTensile", "shearUltimate", "bearingYield", "bearingUltimate", "compressiveYield"] as const;
  type Row = Record<(typeof K_FIELDS)[number], number>;
  const cases: Record<string, { input: typeof base; misgrouped: Row; natrella: Row; now: Row }> = {
    defaultN60: {
      input: base,
      misgrouped: { kA: 2.746, kB: 1.574, aBasisYield: 858, bBasisYield: 889, aBasisTensile: 932, bBasisTensile: 965, shearUltimate: 559, bearingYield: 1287, bearingUltimate: 1864, compressiveYield: 892 },
      natrella: { kA: 2.801, kB: 1.604, aBasisYield: 857, bBasisYield: 888, aBasisTensile: 931, bBasisTensile: 965, shearUltimate: 559, bearingYield: 1286, bearingUltimate: 1862, compressiveYield: 891 },
      now: { kA: 2.808, kB: 1.609, aBasisYield: 857, bBasisYield: 888, aBasisTensile: 931, bBasisTensile: 964, shearUltimate: 559, bearingYield: 1286, bearingUltimate: 1862, compressiveYield: 891 },
    },
    n10: {
      input: { ...base, sampleSizeN: 10 },
      misgrouped: { kA: 3.528, kB: 2.094, aBasisYield: 838, bBasisYield: 875, aBasisTensile: 910, bBasisTensile: 951, shearUltimate: 546, bearingYield: 1257, bearingUltimate: 1820, compressiveYield: 872 },
      natrella: { kA: 3.94, kB: 2.321, aBasisYield: 827, bBasisYield: 870, aBasisTensile: 899, bBasisTensile: 944, shearUltimate: 539, bearingYield: 1241, bearingUltimate: 1798, compressiveYield: 860 },
      now: { kA: 3.982, kB: 2.355, aBasisYield: 826, bBasisYield: 869, aBasisTensile: 897, bBasisTensile: 943, shearUltimate: 538, bearingYield: 1239, bearingUltimate: 1794, compressiveYield: 859 },
    },
    n20: {
      input: { ...base, sampleSizeN: 20 },
      misgrouped: { kA: 3.096, kB: 1.812, aBasisYield: 849, bBasisYield: 883, aBasisTensile: 922, bBasisTensile: 959, shearUltimate: 553, bearingYield: 1274, bearingUltimate: 1844, compressiveYield: 883 },
      natrella: { kA: 3.274, kB: 1.91, aBasisYield: 845, bBasisYield: 880, aBasisTensile: 917, bBasisTensile: 956, shearUltimate: 550, bearingYield: 1268, bearingUltimate: 1834, compressiveYield: 879 },
      now: { kA: 3.296, kB: 1.926, aBasisYield: 844, bBasisYield: 880, aBasisTensile: 917, bBasisTensile: 956, shearUltimate: 550, bearingYield: 1266, bearingUltimate: 1834, compressiveYield: 878 },
    },
    n30: {
      input: { ...base, sampleSizeN: 30 },
      misgrouped: { kA: 2.937, kB: 1.705, aBasisYield: 854, bBasisYield: 886, aBasisTensile: 927, bBasisTensile: 962, shearUltimate: 556, bearingYield: 1281, bearingUltimate: 1854, compressiveYield: 888 },
      natrella: { kA: 3.05, kB: 1.767, aBasisYield: 851, bBasisYield: 884, aBasisTensile: 924, bBasisTensile: 960, shearUltimate: 554, bearingYield: 1277, bearingUltimate: 1848, compressiveYield: 885 },
      now: { kA: 3.064, kB: 1.778, aBasisYield: 850, bBasisYield: 884, aBasisTensile: 923, bBasisTensile: 960, shearUltimate: 554, bearingYield: 1275, bearingUltimate: 1846, compressiveYield: 884 },
    },
    n60cv85: {
      input: { ...base, customScatterCv: 8.5 },
      misgrouped: { kA: 2.746, kB: 1.574, aBasisYield: 713, bBasisYield: 806, aBasisTensile: 774, bBasisTensile: 875, shearUltimate: 464, bearingYield: 1070, bearingUltimate: 1548, compressiveYield: 742 },
      natrella: { kA: 2.801, kB: 1.604, aBasisYield: 709, bBasisYield: 803, aBasisTensile: 770, bBasisTensile: 872, shearUltimate: 462, bearingYield: 1064, bearingUltimate: 1540, compressiveYield: 737 },
      now: { kA: 2.808, kB: 1.609, aBasisYield: 708, bBasisYield: 803, aBasisTensile: 769, bBasisTensile: 872, shearUltimate: 461, bearingYield: 1062, bearingUltimate: 1538, compressiveYield: 736 },
    },
  };
  for (const [name, c] of Object.entries(cases)) {
    const r = computeQualificationMmpdsStats(c.input);
    assert.deepEqual(Object.fromEntries(K_FIELDS.map((f) => [f, r[f]])), c.now, name);
    for (const f of K_FIELDS) {
      // k only grew along the history, so no allowable ever rose
      if (f === "kA" || f === "kB") assert.ok(c.misgrouped[f] < c.natrella[f] && c.natrella[f] < c.now[f], `${name}.${f}`);
      else assert.ok(c.misgrouped[f] >= c.natrella[f] && c.natrella[f] >= c.now[f], `${name}.${f}`);
    }
    // fields k does not enter follow their own formulas (unchanged by every k version)
    const cov = c.input.customScatterCv / 100;
    assert.equal(r.stdDev, Math.round(c.input.meanYieldMpa * cov), name);
    assert.equal(r.sBasisYield, Math.round(c.input.meanYieldMpa - 3 * c.input.meanYieldMpa * cov), name);
    assert.equal(r.cpk, Number((0.05 / cov).toFixed(2)), name);
  }
  // values the k changes did not move are pinned as EQUAL: shear at the default N=60 in all three versions,
  // default B-tensile through the grouping fix, B-yield at N=20/30 and B-tensile at N=20/30 through the exact-table switch
  assert.equal(cases.defaultN60.misgrouped.shearUltimate, cases.defaultN60.now.shearUltimate);
  assert.equal(cases.defaultN60.misgrouped.bBasisTensile, cases.defaultN60.natrella.bBasisTensile);
  for (const n of ["n20", "n30"] as const) {
    assert.equal(cases[n].natrella.bBasisYield, cases[n].now.bBasisYield);
    assert.equal(cases[n].natrella.bBasisTensile, cases[n].now.bBasisTensile);
  }
});
