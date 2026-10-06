import assert from "node:assert/strict";
import test from "node:test";
import {
  MELT_POOL_LITERATURE_CASES,
  isLoadableLiteratureCase,
  matchesLoadableLiteratureCase,
} from "../src/data/meltPoolLiteratureCases";
import opticalTable4 from "../data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json";

test("NIST AMB2022-03 bare-plate measurements cannot be loaded as powder-layer cases", () => {
  const nist = MELT_POOL_LITERATURE_CASES.filter((c) => c.id.startsWith("nist-amb2022-03-"));
  assert.equal(nist.length, 7);
  assert.deepEqual(nist.map(c => [c.laserPower_W, c.scanSpeed_mm_s, c.beamDiameter_um,
    c.publishedWidth_um, c.widthStdDev_um, c.publishedDepth_um, c.depthStdDev_um]),
  opticalTable4.cases.map(row => [row.laserPower_W, row.scanSpeed_mm_s, row.beamDiameterD4sigma_um,
    row.widthMean_um, row.widthStdDev_um, row.depthMean_um, row.depthStdDev_um]));
  assert.deepEqual(nist.map(c => [c.publishedWidth_um, c.widthStdDev_um, c.publishedDepth_um, c.depthStdDev_um]), [
    [136.3, 2.9, 139.7, 1.9], [106.2, 3.6, 227.2, 3.2], [141.7, 1.8, 102.4, 1.1],
    [112.9, 1.7, 109.7, 1.7], [156.1, 4.9, 176.5, 2.6], [134.3, 2.5, 166.1, 2.0],
    [129.4, 1.6, 116.9, 1.2],
  ]);
  for (const c of nist) {
    assert.equal(c.processScope, "bare-plate");
    assert.equal(c.beamDiameterDefinition, "D4sigma");
    assert.equal(c.layerThickness_um, null);
    assert.equal(c.hatchSpacing_um, null);
    assert.equal(c.measurementCount, 6);
    assert.equal(c.publishedRegime, null);
    assert.equal(isLoadableLiteratureCase(c), false);
    assert.equal(matchesLoadableLiteratureCase(c, c.material, {
      laserPower_W: c.laserPower_W!, scanSpeed_mm_s: c.scanSpeed_mm_s!,
      beamDiameter_um: c.beamDiameter_um!, preheatTemp_C: c.preheatTemp_C!,
      layerThickness_um: 40, hatchSpacing_um: 110,
    }), false);
  }
});

test("a loadable measurement matches all six process inputs", () => {
  const c = MELT_POOL_LITERATURE_CASES.find((row) => row.id === "guo-316l-n01")!;
  const process = {
    laserPower_W: c.laserPower_W!, scanSpeed_mm_s: c.scanSpeed_mm_s!,
    beamDiameter_um: c.beamDiameter_um!, preheatTemp_C: c.preheatTemp_C!,
    layerThickness_um: c.layerThickness_um!, hatchSpacing_um: c.hatchSpacing_um!,
  };
  assert.equal(matchesLoadableLiteratureCase(c, c.material, process), true);
  for (const key of Object.keys(process) as Array<keyof typeof process>) {
    assert.equal(matchesLoadableLiteratureCase(c, c.material, { ...process, [key]: process[key] + 2 }), false, key);
  }
  assert.equal(matchesLoadableLiteratureCase(c, "Inconel 718", process), false);
});
