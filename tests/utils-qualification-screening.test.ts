import assert from "node:assert/strict";
import test from "node:test";
import { calculateMMPDSToleranceFactor } from "../src/components/uqLabData";
import { buildQualificationChecklist, computeQualificationMmpdsStats } from "../src/utils/qualificationScreening";

// Golden values were first captured from the UNMODIFIED inline useMemo of StandardQualificationEngine.tsx (HEAD faa6684)
// by a differential run over 324 input combinations before the component was wired to this module. The k_A / k_B
// grouping bug was fixed afterwards (shared toleranceFactors.ts, identical to the aerospace screen); the values
// below are the corrected ones and the pre-fix values are kept in the HISTORICAL block at the end of this file.

const base = { meanYieldMpa: 930, meanTensileMpa: 1010, fractureToughnessMpaM: 68, sampleSizeN: 60, customScatterCv: 2.8 };

test("default screening inputs (corrected Natrella k)", () => {
  assert.deepEqual(computeQualificationMmpdsStats(base), {
    meanYield: 930,
    meanTensile: 1010,
    stdDev: 26,
    covPct: 2.8,
    sampleSize: 60,
    kA: 2.801,
    kB: 1.604,
    aBasisYield: 857,
    bBasisYield: 888,
    sBasisYield: 852,
    aBasisTensile: 931,
    bBasisTensile: 965,
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
    [3.274, 1.91, 845, 880, 917, 956, "S-Basis Provisional"]
  );
  const highCv = computeQualificationMmpdsStats({ ...base, customScatterCv: 8.5 });
  assert.deepEqual(
    [highCv.stdDev, highCv.covPct, highCv.aBasisYield, highCv.bBasisYield, highCv.sBasisYield, highCv.cpk, highCv.status],
    [79, 8.5, 709, 803, 693, 0.59, "B-Basis Qualified"]
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
    [5, 3.94, 2.321, 480, 488, 5, "S-Basis Provisional"]
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
// It now shares toleranceFactors.ts with AerospaceAuditReportGenerator. Proof against the EXACT non-central-t factor
// (tests/fixtures/one-sided-tolerance-factor-oracle.json, scipy) is in tests/utils-tolerance-factor.test.ts.
//   A-basis N=10: old 3.528   fixed 3.940   exact 3.981      N=60: old 2.746  fixed 2.801  exact 2.807
//   B-basis N=10: old 2.094   fixed 2.321   exact 2.355      N=60: old 1.574  fixed 1.604  exact 1.609
// ---------------------------------------------------------------------------------------------------------------
test("kA/kB match the Natrella formula (independent implementation in uqLabData)", () => {
  for (const N of [10, 30, 60, 100]) {
    const r = computeQualificationMmpdsStats({ ...base, sampleSizeN: N });
    const kA = calculateMMPDSToleranceFactor(N, 0.99, 0.95)!;
    const kB = calculateMMPDSToleranceFactor(N, 0.9, 0.95)!;
    assert.ok(Math.abs(r.kA - kA) < 0.001, `N=${N}: kA ${r.kA} vs Natrella ${kA}`);
    assert.ok(Math.abs(r.kB - kB) < 0.001, `N=${N}: kB ${r.kB} vs Natrella ${kB}`);
  }
});

test("corrected kA/kB values by N", () => {
  const byN = Object.fromEntries(
    [10, 30, 60, 100].map((N) => {
      const r = computeQualificationMmpdsStats({ ...base, sampleSizeN: N });
      return [N, [r.kA, r.kB]];
    })
  );
  assert.deepEqual(byN, { 10: [3.94, 2.321], 30: [3.05, 1.767], 60: [2.801, 1.604], 100: [2.68, 1.524] });
});

// ---------------------------------------------------------------------------------------------------------------
// HISTORICAL (pre-fix values, pinned so reviewers see the delta). Displayed by StandardQualificationEngine before
// the k grouping fix; the old formula is re-implemented and checked against the exact factor in
// tests/utils-tolerance-factor.test.ts ("HISTORICAL old qualification k").
// ---------------------------------------------------------------------------------------------------------------
test("HISTORICAL pre-fix qualification outputs differ from the corrected ones exactly where k enters", () => {
  const before = {
    default: { kA: 2.746, kB: 1.574, aBasisYield: 858, bBasisYield: 889, aBasisTensile: 932, bBasisTensile: 965, bearingYield: 1287, bearingUltimate: 1864, compressiveYield: 892 },
    n20: { kA: 3.096, kB: 1.812, aBasisYield: 849, bBasisYield: 883, aBasisTensile: 922, bBasisTensile: 959 },
    cv85: { aBasisYield: 713, bBasisYield: 806 },
    n10clamped: { kA: 3.528, kB: 2.094, aBasisYield: 482, bBasisYield: 490 },
  };
  const now = {
    default: computeQualificationMmpdsStats(base),
    n20: computeQualificationMmpdsStats({ ...base, sampleSizeN: 20 }),
    cv85: computeQualificationMmpdsStats({ ...base, customScatterCv: 8.5 }),
    n10clamped: computeQualificationMmpdsStats({ meanYieldMpa: 500, meanTensileMpa: 600, fractureToughnessMpaM: 30, sampleSizeN: 5, customScatterCv: 0.2 }),
  };
  for (const [name, old] of Object.entries(before)) {
    const cur = now[name as keyof typeof now] as unknown as Record<string, number>;
    for (const [field, oldValue] of Object.entries(old)) {
      // corrected k is larger, so every allowable is lower or equal (never optimistic relative to the old screen)
      if (field === "kA" || field === "kB") assert.ok(cur[field] > oldValue, `${name}.${field}`);
      else assert.ok(cur[field] <= oldValue, `${name}.${field}: ${cur[field]} vs old ${oldValue}`);
    }
  }
});
