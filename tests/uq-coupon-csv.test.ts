import assert from "node:assert/strict";
import { test } from "node:test";
import {
  AEROSPACE_MATERIAL_DATASETS,
  exportCouponsToCSV,
  isSyntheticCouponDataset,
  parseCSVToCoupons,
  type CouponTestSpecimen,
} from "../src/components/uqLabData";

const coreHeader = "Yield_Strength_MPa,UTS_MPa,Elongation_pct";

test("CSV with explicit properties keeps missing metadata unresolved", () => {
  const [coupon] = parseCSVToCoupons(`${coreHeader}\r\n900,1000,12`, "sample");
  assert.equal(coupon.yieldStrengthMPa, 900);
  assert.equal(coupon.utsMPa, 1000);
  assert.equal(coupon.elongationPct, 12);
  assert.equal(coupon.testTempC, null);
  assert.equal(coupon.reductionOfAreaPct, null);
  assert.equal(coupon.hardnessHRC, undefined);
  assert.equal(coupon.orientation, undefined);
  assert.equal(coupon.heatLotId, "");
  assert.equal(coupon.specimenNumber, "");
  assert.equal(coupon.testStandard, "");
  assert.equal(coupon.evidenceOrigin, "unknown");
});

test("CSV roundtrip preserves quotes, commas, multiline metadata, zero and missing values", () => {
  const coupon: CouponTestSpecimen = {
    id: "record-1", specimenNumber: 'Coupon "A", North\r\nsection', heatLotId: "lot,one",
    yieldStrengthMPa: 0, utsMPa: 2.5, elongationPct: 0, reductionOfAreaPct: null,
    hardnessHRC: undefined, testTempC: -196, orientation: undefined,
    testStandard: 'Reported "E8"\nprocedure', evidenceOrigin: "user-reported",
  };
  const csv = exportCouponsToCSV([coupon], 'Dataset "one",\nsecond line');
  assert.deepEqual(parseCSVToCoupons(csv, "different-dataset"), [coupon]);
});

test("synthetic-flagged coupon export/reupload cannot become a measured dataset", () => {
  const dataset = AEROSPACE_MATERIAL_DATASETS[0];
  const row: CouponTestSpecimen = { id: "u-1", specimenNumber: "S1", heatLotId: "H1", testTempC: 25, yieldStrengthMPa: 900, utsMPa: 1000, elongationPct: 12, reductionOfAreaPct: null, hardnessHRC: undefined, testStandard: "ASTM E8", orientation: "L", evidenceOrigin: "synthetic" };
  const parsed = parseCSVToCoupons(exportCouponsToCSV([row], dataset.name), "upload");
  assert.ok(parsed.length === 1 && parsed.every(r => r.evidenceOrigin === "synthetic"));
  assert.equal(isSyntheticCouponDataset({ ...dataset, coupons: parsed, couponSource: "uploaded" }), true);
  assert.throws(() => parseCSVToCoupons(`${coreHeader},Evidence_Origin
900,1000,12,verified`, "upload"), /cannot certify/);
});

test("missing property columns, missing values and unlabelled or conflicting units are rejected", () => {
  for (const csv of [
    "Yield_Strength_MPa,Elongation_pct\n900,12",
    "Yield_Strength_MPa,UTS_MPa\n900,1000",
    "Yield,UTS,Elongation\n900,1000,12",
    "Yield_Strength_ksi,UTS_MPa,Elongation_pct\n130,1000,12",
    `${coreHeader}\n900,,12`,
    `${coreHeader}\n900,1000,`,
    `${coreHeader},Yield_MPa\n900,1000,12,900`,
    `${coreHeader},Mystery\n900,1000,12,value`,
  ]) assert.throws(() => parseCSVToCoupons(csv, "bad"));
});

test("a later invalid row fails the entire import instead of silently dropping coupons", () => {
  for (const value of ["NaN", "Infinity", "1e999", "900 MPa", "900junk", "0x10", "--2", ""]) {
    assert.throws(() => parseCSVToCoupons(`${coreHeader}\n900,1000,12\n${value},1000,12`, "bad"), /row 3/);
  }
  for (const badRow of ["900,1000", "900,1000,12,extra", '"900,1000,12', '"900"oops,1000,12', '9"00,1000,12', ""]) {
    assert.throws(() => parseCSVToCoupons(`${coreHeader}\n${badRow}\n900,1000,12`, "bad"));
  }
});

test("optional numeric values and orientation are validated rather than replaced", () => {
  for (const [header, value] of [
    ["Test_Temp_C", "room temperature"], ["Reduction_of_Area_pct", "25%"],
    ["Hardness_HRC", "NaN"], ["Orientation", "diagonal"],
  ]) assert.throws(() => parseCSVToCoupons(`${coreHeader},${header}\n900,1000,12,${value}`, "bad"));
  assert.throws(() => parseCSVToCoupons(`${coreHeader},Record_ID\n900,1000,12,id\n910,1010,13,id`, "bad"), /duplicate Record_ID/);
});

test("formula-like text is protected and reversibly escaped, without stripping external apostrophes", () => {
  const seed = parseCSVToCoupons(`${coreHeader}\n900,1000,12`, "sample")[0];
  for (const text of ["=SUM(A1:A2)", "+1", "-1", "@command", "  =1", "\t=1", "\r=1", "\n=1", "'literal", "ordinary"]) {
    const coupon = { ...seed, specimenNumber: text, heatLotId: text, testStandard: text, id: text };
    const csv = exportCouponsToCSV([coupon], "formulas");
    if (text !== "ordinary") assert.ok(csv.includes(`'${text.replace(/"/g, '""')}`));
    assert.deepEqual(parseCSVToCoupons(csv, "sample"), [coupon]);
  }
  const [external] = parseCSVToCoupons(`${coreHeader},Specimen_ID\n900,1000,12,'original`, "external");
  assert.equal(external.specimenNumber, "'original");
});

test("legacy leading metadata and BOM are accepted but embedded comment rows never disappear", () => {
  const csv = `\uFEFF# MetalliX legacy export\r\n# Exported: 2026-09-13\r\n${coreHeader}\r\n9e2,1e3,1.2e1\r\n`;
  assert.equal(parseCSVToCoupons(csv, "legacy")[0].yieldStrengthMPa, 900);
  assert.throws(() => parseCSVToCoupons(`${coreHeader}\n900,1000,12\n# bad coupon`, "bad"));
  assert.throws(() => parseCSVToCoupons(`# Text_Escaping: future-v9\n${coreHeader}\n900,1000,12`, "bad"), /version/);
});

test("CSV imports are bounded in text size, cell size and coupon count", () => {
  assert.throws(() => parseCSVToCoupons(" ".repeat(2_000_001), "bad"), /2 million/);
  assert.throws(() => parseCSVToCoupons(`${coreHeader},Specimen_ID\n900,1000,12,${"a".repeat(32_001)}`, "bad"), /cell/);
  assert.throws(() => parseCSVToCoupons(`${coreHeader}\n${"900,1000,12\n".repeat(10_001)}`, "bad"), /10000/);
});
