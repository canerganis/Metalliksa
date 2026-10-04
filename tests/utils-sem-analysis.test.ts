import assert from "node:assert/strict";
import test from "node:test";
import {
  astmGrainSizeNumberFromIntercept,
  caliperPhysicalUm,
  caliperScaleMicronsPerPixel,
  pixelsToMicrons,
  rgbToLuminance,
  segmentLengthPx,
} from "../src/utils/semAnalysis";

// The in-browser analyzeSemImage pins and its two todo tests were removed together with the analyzer (micrograph
// rework): the measurement authority is python/micrograph_measure.py, covered by python/test_micrograph_measure.py
// oracles O1-O9. The helpers kept in src/utils/semAnalysis.ts are pinned here.

test("ASTM E112 grain size relation reproduces the published intercept-length table", () => {
  // E112: G = -6.643856 log10(l_bar[mm]) - 3.288. Table: mean intercept l_bar = 320 um / sqrt(2)^G.
  const table: Array<[number, number]> = [
    [0, 320.0], [1, 226.3], [2, 160.0], [3, 113.1], [4, 80.0], [5, 56.6],
    [6, 40.0], [7, 28.3], [8, 20.0], [9, 14.1], [10, 10.0],
  ];
  for (const [g, lUm] of table) {
    const got = astmGrainSizeNumberFromIntercept(lUm);
    assert.ok(Math.abs(got - g) <= 0.1, `G=${g}: l=${lUm} um -> ${got}`);
  }
  // Hand calculation: l = 20 um -> -6.64385 * log10(0.02) - 3.288 = 11.2879 - 3.288 = 8.0
  assert.equal(astmGrainSizeNumberFromIntercept(20), 8);
  assert.equal(astmGrainSizeNumberFromIntercept(5.56), 11.7); // 14.9814 - 3.288 = 11.693
  // Halving the intercept length raises G by 6.64385 * log10(2) = 2.0.
  assert.ok(Math.abs(astmGrainSizeNumberFromIntercept(10) - astmGrainSizeNumberFromIntercept(20) - 2) <= 0.1);
});

test("caliper and ruler calibration conversions", () => {
  assert.equal(caliperPhysicalUm(10, "µm"), 10);
  assert.equal(caliperPhysicalUm(500, "nm"), 0.5);
  assert.equal(caliperPhysicalUm(2, "mm"), 2000);
  assert.equal(segmentLengthPx({ x1: 0, y1: 0, x2: 3, y2: 4 }), 5);
  assert.equal(segmentLengthPx(null), 0);
  // 5 um scale bar across 120 px -> 0.041667 um/px, stored to 5 decimals
  assert.equal(caliperScaleMicronsPerPixel(5, 120), 0.04167);
  // 1 mm across 250 px -> 4 um/px
  assert.equal(caliperScaleMicronsPerPixel(caliperPhysicalUm(1, "mm"), 250), 4);
  // Round trip: the calibrated scale applied to the calibration segment returns the physical length (rounding 1e-2 um)
  const scale = caliperScaleMicronsPerPixel(5, 120);
  assert.ok(Math.abs(pixelsToMicrons(120, scale) - 5) <= 0.01);
  assert.equal(pixelsToMicrons(5, 0.0416), 0.21); // 0.208 -> 0.21
  assert.equal(pixelsToMicrons(0, 0.0416), 0);
});

test("luminance weights are BT.601", () => {
  assert.equal(rgbToLuminance(0, 0, 0), 0);
  assert.equal(rgbToLuminance(255, 255, 255), 255);
  assert.equal(rgbToLuminance(255, 0, 0), 76); // 76.245
  assert.equal(rgbToLuminance(0, 255, 0), 150); // 149.685
  assert.equal(rgbToLuminance(0, 0, 255), 29); // 29.07
});
