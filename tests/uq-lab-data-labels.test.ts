import assert from "node:assert/strict";
import test from "node:test";
import { AEROSPACE_MATERIAL_DATASETS } from "../src/components/uqLabData";

test("AlSi10Mg LPBF UQ dataset does not claim SAE AMS 4215 (a C355.0 casting specification)", () => {
  const dataset = AEROSPACE_MATERIAL_DATASETS.find(d => d.id === "alsi10mg-lpbf-ams4215");
  assert.ok(dataset, "dataset id is kept as a stable lookup key");
  assert.ok(!/AMS\s*4215/i.test(dataset.name), dataset.name);
  assert.ok(!/AMS\s*4215/i.test(dataset.specification), dataset.specification);
  assert.match(dataset.specification, /ASTM F3318/);
});

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as uqLabData from "../src/components/uqLabData";
import { computeMMPDSEmpiricalStats, isSyntheticCouponDataset } from "../src/components/uqLabData";

const readSrc = (rel: string) => readFileSync(resolve(process.cwd(), rel), "utf8").replace(/\r/g, "");

test("no preset ships coupon records, so no synthetic coupon is presented as data", () => {
  for (const d of AEROSPACE_MATERIAL_DATASETS) {
    assert.equal(d.coupons.length, 0, d.id);
    assert.equal(d.couponSource, "none", d.id);
    assert.ok(!/synthetic|Box-Muller/i.test(d.description), d.id);
    assert.equal(isSyntheticCouponDataset(d), false, d.id);
  }
});

test("the fake synthetic coupon generator and its modal are gone", () => {
  assert.equal("generateSyntheticCoupons" in uqLabData, false);
  const ui = readSrc("src/components/UQLab.tsx");
  assert.doesNotMatch(ui, /Box-Muller|Synthesize|generateSyntheticCoupons/);
  assert.doesNotMatch(ui, /"comparison"|lastRunTimestamp|onNavigate/);
  assert.match(ui, /No coupon data loaded/);
});

test("the Sobol run is explicit and labelled illustrative, with no UTS/K_Ic/flaw outputs rendered", () => {
  const ui = readSrc("src/components/UQLab.tsx");
  assert.doesNotMatch(ui, /useEffect\(\(\) => \{\s*void runQMCSolver\(\)/);
  assert.match(ui, /UQ_ILLUSTRATIVE_MODEL_NOTE/);
  assert.doesNotMatch(ui, /stochasticProperties|fractureToughness|criticalFlaw/);
});

test("uploaded-coupon statistics are computed from the supplied values only", () => {
  const stats = computeMMPDSEmpiricalStats([100, 102, 98, 101, 99], 90, []);
  assert.equal(stats.sampleSize, 5);
  close5(stats.mean, 100);
});

function close5(actual: number | null, expected: number) {
  assert.ok(actual !== null && Math.abs(actual - expected) < 1e-9, `${actual}`);
}
