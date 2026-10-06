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
