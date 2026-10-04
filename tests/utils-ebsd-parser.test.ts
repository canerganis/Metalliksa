import assert from "node:assert/strict";
import test from "node:test";
import { parseEBSDOrGrainFile } from "../src/utils/ebsdParser";

// parseEBSDOrGrainFile is not reachable from the UI today (no importer); these tests pin its grain-size maths.

// First-principles oracle (ASTM E112 definition only): N_AE = 2^(G-1) grains per in^2 at 100x. At 1x a 1 in^2 field
// is 100^2 times larger and 1 in^2 = 645.16 mm^2, so N_A = 2^(G-1) * 100^2 / 645.16 grains per mm^2. In the
// planimetric (Jeffries) sense N_A = 1 / (mean grain area), which is what the parser has per grain.
function e112GFromMeanAreaUm2(meanAreaUm2: number): number {
  const NA = 1e6 / meanAreaUm2; // grains per mm^2 at 1x
  const NAE = (NA * 645.16) / 100 ** 2; // grains per in^2 at 100x
  return Math.log2(NAE) + 1;
}

test("ASTM G from the mean grain area matches the E112 planimetric definition", () => {
  // rows "area diameter aspect" (area > diameter -> first column is the area)
  const rows = ["400 22.6 1.1", "500 25.2 1.2", "612 27.9 1.3"];
  const r = parseEBSDOrGrainFile(rows.join("\n"), "grains.csv");
  assert.equal(r.totalGrains, 3);
  const meanArea = (400 + 500 + 612) / 3; // 504 um^2
  assert.ok(Math.abs(r.astm_G - e112GFromMeanAreaUm2(meanArea)) <= 0.005 + 1e-4, `${r.astm_G}`);
  // 504 um^2 = 1/1984 mm^2 is the E112 count for G = 8 (N_AE = 128)
  assert.ok(Math.abs(e112GFromMeanAreaUm2(1e6 / ((128 * 100 ** 2) / 645.16)) - 8) < 1e-12);
  assert.equal(r.astm_G, 8);
});

// a row needs two columns; "d d" (second column not smaller) is read as a diameter with the circle area
test("diameter rows: area is the circle area and G follows the same relation", () => {
  const r = parseEBSDOrGrainFile(["10 10", "20 20", "30 30"].join("\n"), "d.txt");
  const meanArea = (Math.PI / 4) * ((10 ** 2 + 20 ** 2 + 30 ** 2) / 3);
  // per-grain area is stored rounded to 0.01 um^2; G moves by < 1e-4 from that
  assert.ok(Math.abs(r.astm_G - e112GFromMeanAreaUm2(meanArea)) <= 0.005 + 1e-4, `${r.astm_G}`);
  assert.equal(r.meanDiameter_um, 20);
  // halving every diameter quarters the area: G rises by exactly 2
  const half = parseEBSDOrGrainFile(["5 5", "10 10", "15 15"].join("\n"), "d.txt");
  assert.ok(Math.abs(half.astm_G - r.astm_G - 2) <= 0.011);
});

// HISTORICAL: before 2026-10 the parser used G = -3.3219 log10(meanDiameter_mm) - 3.288 (area coefficient on a
// length, intercept constant). Same inputs as above: G 8 grains (mean area 504 um^2, mean ECD 25.2 um) gave 2.02.
test("HISTORICAL ebsdParser G before the fix (pinned old formula on the same input)", () => {
  const oldG = (meanDiameterUm: number) => +(-3.3219 * Math.log10(meanDiameterUm / 1000) - 3.288).toFixed(2);
  const r = parseEBSDOrGrainFile(["400 22.6 1.1", "500 25.2 1.2", "612 27.9 1.3"].join("\n"), "grains.csv");
  assert.deepEqual([r.meanDiameter_um, oldG(r.meanDiameter_um), r.astm_G], [25.23, 2.02, 8]);
});
