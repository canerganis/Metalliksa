import assert from "node:assert/strict";
import test from "node:test";
import { calculateMMPDSToleranceFactor } from "../src/components/uqLabData";
import { buildQualificationChecklist, computeQualificationMmpdsStats } from "../src/utils/qualificationScreening";

// Golden values were captured from the UNMODIFIED inline useMemo of StandardQualificationEngine.tsx (HEAD faa6684)
// by a differential run over 324 input combinations before the component was wired to this module.

const base = { meanYieldMpa: 930, meanTensileMpa: 1010, fractureToughnessMpaM: 68, sampleSizeN: 60, customScatterCv: 2.8 };

test("default screening inputs reproduce the pre-extraction numbers exactly", () => {
  assert.deepEqual(computeQualificationMmpdsStats(base), {
    meanYield: 930,
    meanTensile: 1010,
    stdDev: 26,
    covPct: 2.8,
    sampleSize: 60,
    kA: 2.746,
    kB: 1.574,
    aBasisYield: 858,
    bBasisYield: 889,
    sBasisYield: 852,
    aBasisTensile: 932,
    bBasisTensile: 965,
    shearUltimate: 559,
    bearingYield: 1287,
    bearingUltimate: 1864,
    compressiveYield: 892,
    fractureToughnessKic: 68,
    cpk: 1.79,
    status: "A-Basis Qualified",
  });
});

test("golden table: small sample, high scatter and clamped inputs", () => {
  const n20 = computeQualificationMmpdsStats({ ...base, sampleSizeN: 20 });
  assert.deepEqual(
    [n20.kA, n20.kB, n20.aBasisYield, n20.bBasisYield, n20.aBasisTensile, n20.bBasisTensile, n20.status],
    [3.096, 1.812, 849, 883, 922, 959, "S-Basis Provisional"]
  );
  const highCv = computeQualificationMmpdsStats({ ...base, customScatterCv: 8.5 });
  assert.deepEqual(
    [highCv.stdDev, highCv.covPct, highCv.aBasisYield, highCv.bBasisYield, highCv.sBasisYield, highCv.cpk, highCv.status],
    [79, 8.5, 713, 806, 693, 0.59, "B-Basis Qualified"]
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
    [5, 3.528, 2.094, 482, 490, 5, "S-Basis Provisional"]
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
// FORMULA BUG (reported, NOT fixed: scientific-calculation changes need the user).
// StandardQualificationEngine computes the Natrella one-sided tolerance factor as
//   k = z_p + sqrt(z_p^2 - a*b) / a          (the division binds only to the sqrt term)
// whereas the Natrella / Lieberman-Resnikoff formula is
//   k = (z_p + sqrt(z_p^2 - a*b)) / a,   a = 1 - z_g^2/(2(N-1)),  b = z_p^2 - z_g^2/N.
// AerospaceAuditReportGenerator has the correct grouping. Evidence at 99 %/95 % (A-basis):
//   N=10:  engine 3.528   Natrella 3.940   exact non-central t 3.981 (scipy.stats.nct)
//   N=30:  engine 2.937   Natrella 3.050   exact 3.064
//   N=60:  engine 2.746   Natrella 2.8006  exact 2.807
//   N=100: engine 2.648   Natrella 2.680   exact 2.684
// The engine therefore under-states k_A (and k_B: N=60 engine 1.574, Natrella 1.604, exact 1.609),
// i.e. its A/B-basis estimates are optimistic by up to ~11 % in k at small N.
// ---------------------------------------------------------------------------------------------------------------
test(
  "kA/kB match the Natrella formula (engine mis-groups the division)",
  { todo: "BUG: k = z + sqrt(..)/a instead of (z + sqrt(..))/a; see comment block above" },
  () => {
    for (const N of [10, 30, 60, 100]) {
      const r = computeQualificationMmpdsStats({ ...base, sampleSizeN: N });
      const kA = calculateMMPDSToleranceFactor(N, 0.99, 0.95)!;
      const kB = calculateMMPDSToleranceFactor(N, 0.9, 0.95)!;
      assert.ok(Math.abs(r.kA - kA) < 0.01, `N=${N}: kA ${r.kA} vs Natrella ${kA}`);
      assert.ok(Math.abs(r.kB - kB) < 0.01, `N=${N}: kB ${r.kB} vs Natrella ${kB}`);
    }
  }
);

test("documents today's kA/kB values (pins the unmodified behaviour until the formula is approved for change)", () => {
  const byN = Object.fromEntries(
    [10, 30, 60, 100].map((N) => {
      const r = computeQualificationMmpdsStats({ ...base, sampleSizeN: N });
      return [N, [r.kA, r.kB]];
    })
  );
  assert.deepEqual(byN, { 10: [3.528, 2.094], 30: [2.937, 1.705], 60: [2.746, 1.574], 100: [2.648, 1.506] });
});
