import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
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
import { computeMMPDSEmpiricalStats, isSyntheticCouponDataset, parseCSVToCoupons } from "../src/components/uqLabData";
import {
  CouponSummary,
  CouponWorksheet,
  UQ_ILLUSTRATIVE_MODEL_NOTE,
  UQ_NO_COUPONS_MESSAGE,
  UqEmptyCouponState,
  UqRunSettings,
  UqSensitivityNotRun,
  couponProvenance,
  couponWorksheetText,
} from "../src/components/UqCouponReport";

const readSrc = (rel: string) => readFileSync(resolve(process.cwd(), rel), "utf8").replace(/\r/g, "");
const emptyPreset = AEROSPACE_MATERIAL_DATASETS[0];

test("no preset ships coupon records, so no synthetic coupon is presented as data", () => {
  for (const d of AEROSPACE_MATERIAL_DATASETS) {
    assert.equal(d.coupons.length, 0, d.id);
    assert.equal(d.couponSource, "none", d.id);
    assert.ok(!/synthetic|Box-Muller/i.test(d.description), d.id);
    // descriptions must not narrate production batches that are not in the app
    assert.ok(!/printed on|forging batches|batch(es)? (of|across)/i.test(d.description), d.description);
    assert.equal(isSyntheticCouponDataset(d), false, d.id);
  }
});

test("the fake synthetic coupon generator and its modal are gone", () => {
  assert.equal("generateSyntheticCoupons" in uqLabData, false);
  const ui = readSrc("src/components/UQLab.tsx");
  assert.doesNotMatch(ui, /Box-Muller|Synthesize|generateSyntheticCoupons/);
  assert.doesNotMatch(ui, /"comparison"|lastRunTimestamp|onNavigate/);
  assert.match(ui, /UqEmptyCouponState/);
});

test("the Sobol run starts only from the button: runQMCSolver is defined once and referenced once, as onClick", () => {
  const ui = readSrc("src/components/UQLab.tsx");
  const refs = ui.match(/runQMCSolver/g) ?? [];
  assert.equal(refs.length, 2, "definition + onClick only; any effect/auto-run would add a reference");
  assert.match(ui, /const runQMCSolver = useCallback\(/);
  assert.match(ui, /onClick=\{runQMCSolver\}/);
  assert.doesNotMatch(ui, /useEffect\([^)]*runQMCSolver/);
});

test("no UTS/K_Ic/flaw output and no overclaiming copy is rendered in the UQ view", () => {
  const ui = readSrc("src/components/UQLab.tsx");
  assert.doesNotMatch(ui, /stochasticProperties|fractureToughness|criticalFlaw/);
  assert.doesNotMatch(ui, /Optimization Strategy|multi-scale|animate-pulse|Sparkles/i);
  assert.doesNotMatch(ui, /sampleSizeN\.toLocaleString\(\)\} samples/);
  assert.doesNotMatch(UQ_ILLUSTRATIVE_MODEL_NOTE, /\d\.\d GPa|3\.5/);
  assert.match(UQ_ILLUSTRATIVE_MODEL_NOTE, /not measured or calibrated/);
});

test("the Runs selector is gone: nothing offers 1,000-10,000 runs that the displayed estimate ignores", () => {
  const ui = readSrc("src/components/UQLab.tsx");
  assert.doesNotMatch(ui, /aria-label="Runs"|setMcSamples|10,000 runs/);
});

test("empty preset: no 'User-supplied'/'Uploaded records' wording, a no-coupons message instead", () => {
  assert.equal(couponProvenance(emptyPreset), UQ_NO_COUPONS_MESSAGE);
  const text = couponWorksheetText(emptyPreset);
  assert.match(text, /No coupon records loaded/);
  assert.doesNotMatch(text, /User-supplied|Uploaded|Cpl=|n=0/);
  const summary = renderToStaticMarkup(React.createElement(CouponSummary, { stats: computeMMPDSEmpiricalStats([], emptyPreset.specMinYieldMPa), unit: "MPa", synthetic: false }));
  assert.match(summary, /No coupon records loaded/);
  assert.doesNotMatch(summary, /Uploaded records are unverified/);
  const sheet = renderToStaticMarkup(React.createElement(CouponWorksheet, { dataset: emptyPreset, onCopy: () => {}, notification: null }));
  assert.match(sheet, /No coupon records loaded/);
  assert.doesNotMatch(sheet, /<table|Copy Report|User-supplied|Not assessed/);
  const ui = readSrc("src/components/UQLab.tsx");
  assert.match(ui, /disabled=\{activeDataset\.coupons\.length === 0\}/);
});

test("empty-state and not-run panels guide the user and carry the illustrative label", () => {
  const empty = renderToStaticMarkup(React.createElement(UqEmptyCouponState, { materialName: "Inconel 718", onUpload: () => {} }));
  assert.match(empty, /No coupon data loaded for Inconel 718/);
  assert.match(empty, /Upload coupon CSV/);
  assert.match(empty, /Nothing is generated or assumed/);
  const idle = renderToStaticMarkup(React.createElement(UqSensitivityNotRun, { isLoading: false }));
  assert.match(idle, /not run/);
  assert.match(idle, /Press Run illustrative sensitivity/);
  assert.match(idle, /not measured or calibrated/);
  assert.match(renderToStaticMarkup(React.createElement(UqSensitivityNotRun, { isLoading: true })), /Running the illustrative model/);
});

test("run settings show the solver's own sample counts and the placeholder thermal inputs that were sent", () => {
  const thermal = emptyPreset.nominalThermal;
  const markup = renderToStaticMarkup(React.createElement(UqRunSettings, {
    sensitivityMetadata: { method: "Centered Saltelli first-order / Jansen total-order", baseSampleSize: 350, evaluationCount: 3150 },
    thermal, seed: 42,
  }));
  assert.match(markup, /350 base samples/);
  assert.match(markup, /3,150 model evaluations/);
  assert.match(markup, /placeholder input, not sourced/);
  assert.match(markup, new RegExp(`cooling rate ${thermal.coolingRate_K_s.toLocaleString("en-US").replace(/[.,]/g, "\\$&")} K/s`));
  assert.doesNotMatch(markup, /2,500|10,000/);
  const missing = renderToStaticMarkup(React.createElement(UqRunSettings, { thermal, seed: 42 }));
  assert.match(missing, /reported no sensitivity sample counts/);
});

test("a changed input clears the stale solver error but not an upload error", () => {
  const ui = readSrc("src/components/UQLab.tsx");
  assert.match(ui, /useEffect\(\(\) => \{ requestSession\.current\.invalidate\(\); setIsLoading\(false\); setErrorMsg\(null\); \}, \[requestKey\]\)/);
  assert.match(ui, /setUploadError\(/);
  assert.doesNotMatch(ui.replace(/setErrorMsg\(state\.error\)|setErrorMsg\(null\)|useState<string \| null>\(null\)/g, ""), /setErrorMsg\(['"`]/);
});

test("uploaded-coupon CSV statistics are unchanged: pinned values for a fixed CSV", () => {
  const csv = "Yield_Strength_MPa,UTS_MPa,Elongation_pct,Heat_Lot_ID\n1000,1100,12,A\n1010,1112,13,A\n990,1090,11,B\n1005,1105,12.5,B\n995,1095,11.5,C\n1002,1101,12.2,C";
  const coupons = parseCSVToCoupons(csv, "pinned");
  const stats = computeMMPDSEmpiricalStats(coupons.map(c => c.yieldStrengthMPa), 950, coupons.map(c => c.heatLotId));
  const near = (actual: number | null, expected: number) => assert.ok(actual !== null && Math.abs(actual - expected) < 1e-9, `${actual} vs ${expected}`);
  assert.equal(stats.sampleSize, 6);
  assert.equal(stats.lotCount, 3);
  assert.equal(stats.status, "ready");
  assert.equal(stats.toleranceEligible, true);
  near(stats.mean, 6002 / 6);                       // independent: sum / n
  near(stats.variance, 253.33333333333334 / 5);     // independent: sum of squared deviations / (n - 1)
  near(stats.stdDev, 7.118052168020874);
  near(stats.mmpds_kA, 5.024950313632908);          // Natrella approximation, p = 0.99, gamma = 0.95, n = 6
  near(stats.mmpds_kB, 2.962403978279672);          // p = 0.90
  near(stats.aBasisAllowable, 6002 / 6 - 5.024950313632908 * 7.118052168020874);
  near(stats.cpl, (6002 / 6 - 950) / (3 * 7.118052168020874));
  assert.equal(stats.conformancePct, 100);
  assert.equal(stats.normality.status, "not-tested");
  assert.equal(stats.andersonDarlingPVal, null);
});

test("every preset's minimums carry a provenance record and none claims a verified citation", () => {
  for (const d of AEROSPACE_MATERIAL_DATASETS) {
    assert.ok(d.specMinSource && d.specMinSource.citation.length > 20, d.id);
    assert.ok(["unverified-reference", "no-source"].includes(d.specMinSource.status), d.id);
    assert.match(d.specMinSource.citation, /not verified|No source/, d.id);
  }
});

test("AlSi10Mg LPBF preset has no invented MMPDS chapter and its minimums are flagged as not sourced", () => {
  const d = AEROSPACE_MATERIAL_DATASETS.find(x => x.id === "alsi10mg-lpbf-ams4215")!;
  assert.equal(d.mmpdsChapter, null);
  assert.equal(d.specMinSource.status, "no-source");
  assert.doesNotMatch(JSON.stringify(d), /Additive Qualification Protocol|MMPDS Sec\. 9/);
});

test("UQ Lab UI labels minimums and the coupon badge as unverified reference comparisons", () => {
  const ui = readSrc("src/components/UQLab.tsx");
  assert.doesNotMatch(ui, />\s*PASS\s*</);
  assert.doesNotMatch(ui, /OUT-OF-SPEC|Spec Minimums:|F_ty ≥|Spec Status/);
  assert.match(ui, /uq-spec-min-source/);
  assert.match(ui, /below ref\. min/);
  // "Speedup not estimated" is neutral, not a success badge.
  const i = ui.indexOf("Speedup not estimated");
  assert.doesNotMatch(ui.slice(i - 260, i), /emerald/);
});
