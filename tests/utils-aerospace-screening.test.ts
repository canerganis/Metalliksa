import assert from "node:assert/strict";
import test from "node:test";
import { calculateMMPDSToleranceFactor } from "../src/components/uqLabData";
import { buildAerospaceChecklist, computeAerospaceScreeningStats } from "../src/utils/aerospaceScreening";
import { natrellaOneSidedToleranceFactor } from "../src/utils/toleranceFactors";

// Golden values were first captured from the UNMODIFIED inline useMemo blocks of AerospaceAuditReportGenerator.tsx
// (HEAD faa6684) by a differential run over 324 input combinations (verified once by the p8-studio-tests lane; script not retained).
// In 2026-10 k_A / k_B switched from the Natrella approximation to the exact noncentral-t table for N <= 300
// (src/utils/toleranceFactors.ts); the values below are the new ones, the Natrella-era values are pinned in the
// HISTORICAL block at the end of this file.

const base = { meanYieldMpa: 930, meanTensileMpa: 1010, sampleSizeN: 60, scatterCvPct: 2.8 };

test("default screening inputs (exact noncentral-t k)", () => {
  assert.deepEqual(computeAerospaceScreeningStats(base), {
    kA: 2.808,
    kB: 1.609,
    aBasisYield: 857,
    bBasisYield: 888,
    aBasisTensile: 931,
    bBasisTensile: 964,
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
  assert.deepEqual(pick(computeAerospaceScreeningStats({ ...base, sampleSizeN: 20 })), [3.296, 1.926, 844, 880, 1.79]);
  assert.deepEqual(
    pick(computeAerospaceScreeningStats({ meanYieldMpa: 1100, meanTensileMpa: 1180, sampleSizeN: 100, scatterCvPct: 8.5 })),
    [2.684, 1.527, 849, 957, 0.59]
  );
  // N=5 -> 10 and CV 0.2 % -> 1 %
  assert.deepEqual(
    pick(computeAerospaceScreeningStats({ meanYieldMpa: 500, meanTensileMpa: 600, sampleSizeN: 5, scatterCvPct: 0.2 })),
    [3.982, 2.355, 480, 488, 5]
  );
  // Huge scatter drives every allowable to the zero floor, never negative.
  const floor = computeAerospaceScreeningStats({ meanYieldMpa: 100, meanTensileMpa: 120, sampleSizeN: 60, scatterCvPct: 90 });
  assert.deepEqual(
    [floor.aBasisYield, floor.bBasisYield, floor.aBasisTensile, floor.bBasisTensile, floor.shearUltimate, floor.bearingYield],
    [0, 0, 0, 0, 0, 0]
  );
});

test("k_A / k_B vs the independent Natrella implementation in uqLabData: >= it up to N=300, equal above", () => {
  for (const N of [10, 20, 30, 60, 100, 300, 500]) {
    const r = computeAerospaceScreeningStats({ ...base, sampleSizeN: N });
    const nA = calculateMMPDSToleranceFactor(N, 0.99, 0.95)!;
    const nB = calculateMMPDSToleranceFactor(N, 0.9, 0.95)!;
    if (N <= 300) {
      // exact table (rounded up) is never below the approximation and within 1.5 % of it
      assert.ok(r.kA >= nA - 0.0005 && r.kA - nA < 0.015 * nA, `kA N=${N}`);
      assert.ok(r.kB >= nB - 0.0005 && r.kB - nB < 0.015 * nB, `kB N=${N}`);
    } else {
      // Rounded to 3 dp in the component; z-constants differ in the 7th digit.
      assert.ok(Math.abs(r.kA - nA) < 0.002 && Math.abs(r.kB - nB) < 0.002, `N=${N}`);
    }
  }
});

test("k is the exact non-central-t factor rounded up (never optimistic)", () => {
  // Exact values (tests/fixtures/one-sided-tolerance-factor-oracle.json): k_A(60)=2.807055, k_B(60)=1.608913,
  // k_A(10)=3.981118, k_B(10)=2.354640.
  const r60 = computeAerospaceScreeningStats({ ...base, sampleSizeN: 60 });
  assert.deepEqual([r60.kA, r60.kB], [2.808, 1.609]);
  const r10 = computeAerospaceScreeningStats({ ...base, sampleSizeN: 10 });
  assert.deepEqual([r10.kA, r10.kB], [3.982, 2.355]);
});

test("hand-computed arithmetic of the allowables", () => {
  const r = computeAerospaceScreeningStats(base);
  const sd = 930 * 0.028;
  assert.equal(r.aBasisYield, Math.round(930 - 2.808 * sd)); // 857
  assert.equal(r.bBasisYield, Math.round(930 - 1.609 * sd)); // 888
  assert.equal(r.aBasisTensile, Math.round(1010 - 2.808 * 1010 * 0.028)); // 931
  assert.equal(r.bBasisTensile, Math.round(1010 - 1.609 * 1010 * 0.028)); // 964
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

// ---------------------------------------------------------------------------------------------------------------
// HISTORICAL (Natrella-era values displayed by this screen until 2026-10, pinned so reviewers see the delta).
// Old k from natrellaOneSidedToleranceFactor; allowables recomputed with the screen's own arithmetic.
// ---------------------------------------------------------------------------------------------------------------
test("HISTORICAL aerospace k and allowables before the exact-table switch", () => {
  const old = (N: number, y: number, t: number, cv: number) => {
    const kA = natrellaOneSidedToleranceFactor(2.326348, Math.max(10, N));
    const kB = natrellaOneSidedToleranceFactor(1.281552, Math.max(10, N));
    const c = Math.max(1, cv) / 100;
    return [kA, kB, Math.round(y - kA * y * c), Math.round(y - kB * y * c), Math.round(t - kA * t * c), Math.round(t - kB * t * c)];
  };
  const now = (N: number, y: number, t: number, cv: number) => {
    const r = computeAerospaceScreeningStats({ meanYieldMpa: y, meanTensileMpa: t, sampleSizeN: N, scatterCvPct: cv });
    return [r.kA, r.kB, r.aBasisYield, r.bBasisYield, r.aBasisTensile, r.bBasisTensile];
  };
  // generic preset (N 12) and the four mission presets
  assert.deepEqual([old(12, 880, 950, 4), now(12, 880, 950, 4)], [[3.712, 2.182, 749, 803, 809, 867], [3.748, 2.211, 748, 802, 808, 866]]);
  assert.deepEqual([old(60, 935, 1015, 2.8), now(60, 935, 1015, 2.8)], [[2.801, 1.604, 862, 893, 935, 969], [2.808, 1.609, 861, 893, 935, 969]]);
  assert.deepEqual([old(45, 1185, 1395, 3.4), now(45, 1185, 1395, 3.4)], [[2.889, 1.662, 1069, 1118, 1258, 1316], [2.898, 1.669, 1068, 1118, 1258, 1316]]);
  assert.deepEqual([old(50, 475, 540, 2.4), now(50, 475, 540, 2.4)], [[2.855, 1.64, 442, 456, 503, 519], [2.863, 1.646, 442, 456, 503, 519]]);
  assert.deepEqual([old(35, 1720, 2080, 2.2), now(35, 1720, 2080, 2.2)], [[2.983, 1.724, 1607, 1655, 1943, 2001], [2.995, 1.733, 1607, 1654, 1943, 2001]]);
  // the switch only ever raises k (lowers allowables) for N <= 300 and changes nothing above
  for (let N = 10; N <= 400; N++) {
    const o = old(N, 930, 1010, 2.8);
    const n = now(N, 930, 1010, 2.8);
    assert.ok(n[0] >= o[0] && n[1] >= o[1] && n[2] <= o[2] && n[3] <= o[3], `N=${N}`);
    if (N > 300) assert.deepEqual(n, o);
  }
});
