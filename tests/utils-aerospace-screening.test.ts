import assert from "node:assert/strict";
import test from "node:test";
import { calculateMMPDSToleranceFactor } from "../src/components/uqLabData";
import { buildAerospaceChecklist, computeAerospaceScreeningStats } from "../src/utils/aerospaceScreening";

// Golden values captured from the UNMODIFIED inline useMemo blocks of AerospaceAuditReportGenerator.tsx (HEAD faa6684)
// by a differential run over 324 input combinations before the component was wired to this module.

const base = { meanYieldMpa: 930, meanTensileMpa: 1010, sampleSizeN: 60, scatterCvPct: 2.8 };

test("default screening inputs reproduce the pre-extraction numbers exactly", () => {
  assert.deepEqual(computeAerospaceScreeningStats(base), {
    kA: 2.801,
    kB: 1.604,
    aBasisYield: 857,
    bBasisYield: 888,
    aBasisTensile: 931,
    bBasisTensile: 965,
    shearUltimate: 559,
    bearingYield: 1286,
    bearingUltimate: 1862,
    compressiveYield: 891,
    cpk: 1.79,
    status: "Screening estimate (not MMPDS handbook)",
  });
});

test("golden table across sample size, scatter and clamping", () => {
  const pick = (r: ReturnType<typeof computeAerospaceScreeningStats>) => [r.kA, r.kB, r.aBasisYield, r.bBasisYield, r.cpk];
  assert.deepEqual(pick(computeAerospaceScreeningStats({ ...base, sampleSizeN: 20 })), [3.274, 1.91, 845, 880, 1.79]);
  assert.deepEqual(
    pick(computeAerospaceScreeningStats({ meanYieldMpa: 1100, meanTensileMpa: 1180, sampleSizeN: 100, scatterCvPct: 8.5 })),
    [2.68, 1.524, 849, 958, 0.59]
  );
  // N=5 -> 10 and CV 0.2 % -> 1 %
  assert.deepEqual(
    pick(computeAerospaceScreeningStats({ meanYieldMpa: 500, meanTensileMpa: 600, sampleSizeN: 5, scatterCvPct: 0.2 })),
    [3.94, 2.321, 480, 488, 5]
  );
  // Huge scatter drives every allowable to the zero floor, never negative.
  const floor = computeAerospaceScreeningStats({ meanYieldMpa: 100, meanTensileMpa: 120, sampleSizeN: 60, scatterCvPct: 90 });
  assert.deepEqual(
    [floor.aBasisYield, floor.bBasisYield, floor.aBasisTensile, floor.bBasisTensile, floor.shearUltimate, floor.bearingYield],
    [0, 0, 0, 0, 0, 0]
  );
});

test("k_A / k_B equal the Natrella one-sided tolerance factors (independent implementation in uqLabData)", () => {
  for (const N of [10, 20, 30, 60, 100, 500]) {
    const r = computeAerospaceScreeningStats({ ...base, sampleSizeN: N });
    // Rounded to 3 dp in the component; z-constants differ in the 7th digit.
    assert.ok(Math.abs(r.kA - calculateMMPDSToleranceFactor(N, 0.99, 0.95)!) < 0.002, `kA N=${N}`);
    assert.ok(Math.abs(r.kB - calculateMMPDSToleranceFactor(N, 0.9, 0.95)!) < 0.002, `kB N=${N}`);
  }
});

test("Natrella k is a close but not exact stand-in for the non-central-t factor", () => {
  // Exact values (scipy.stats.nct, 95 % confidence): k_A(60)=2.8071, k_B(60)=1.6089, k_A(10)=3.9811, k_B(10)=2.3546.
  const r60 = computeAerospaceScreeningStats({ ...base, sampleSizeN: 60 });
  assert.ok(Math.abs(r60.kA - 2.8071) < 0.01 && Math.abs(r60.kB - 1.6089) < 0.01);
  const r10 = computeAerospaceScreeningStats({ ...base, sampleSizeN: 10 });
  assert.ok(Math.abs(r10.kA - 3.9811) < 0.05 && Math.abs(r10.kB - 2.3546) < 0.05);
  assert.ok(r10.kA < 3.9811, "approximation is slightly optimistic at N=10");
});

test("hand-computed arithmetic of the allowables", () => {
  const r = computeAerospaceScreeningStats(base);
  const sd = 930 * 0.028;
  assert.equal(r.aBasisYield, Math.round(930 - 2.801 * sd)); // 857
  assert.equal(r.bBasisYield, Math.round(930 - 1.604 * sd)); // 888
  assert.equal(r.aBasisTensile, Math.round(1010 - 2.801 * 1010 * 0.028)); // 931
  assert.equal(r.shearUltimate, Math.round(r.aBasisTensile * 0.6));
  assert.equal(r.bearingYield, Math.round(r.aBasisYield * 1.5));
  assert.equal(r.bearingUltimate, Math.round(r.aBasisTensile * 2));
  assert.equal(r.compressiveYield, Math.round(r.aBasisYield * 1.04));
  assert.equal(r.cpk, Number((0.05 / 0.028).toFixed(2)));
  assert.ok(r.aBasisYield < r.bBasisYield && r.bBasisYield < 930);
});

test("status string never claims handbook qualification", () => {
  for (const N of [10, 60, 500]) {
    assert.equal(computeAerospaceScreeningStats({ ...base, sampleSizeN: N }).status, "Screening estimate (not MMPDS handbook)");
  }
});

test("checklist rows are template-only: never a pass, always Not executed", () => {
  const rows = buildAerospaceChecklist({
    fractureToughnessMpaM: 68,
    serviceTempMin: -54,
    serviceTempMax: 350,
    operatingStressMpa: 550,
    cpk: 1.79,
  });
  assert.equal(rows.length, 6);
  for (const r of rows) {
    assert.equal(r.passProbabilityPct, 0);
    assert.equal(r.riskLevel, "Not executed");
    assert.equal(r.executionStatus, "Not executed");
    assert.equal(r.primaryThreat, "Not evaluated in software");
    assert.match(r.mitigationRecommendation, /^Checklist item/);
  }
  assert.equal(rows[1].criticalThreshold, "Reference K_IC input: 68 MPa√m (not a test result)");
  assert.equal(rows[2].criticalThreshold, "Entered ΔT: 404°C (user input, not a test)");
  assert.equal(rows[3].criticalThreshold, "Entered operating stress: 550 MPa (user input)");
  assert.equal(rows[4].criticalThreshold, "Computed Cpk from sliders: 1.79 (not AS9100 evidence)");
});
