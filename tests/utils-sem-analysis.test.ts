import assert from "node:assert/strict";
import test from "node:test";
import {
  analyzeSemImage,
  astmGrainSizeNumberFromIntercept,
  caliperPhysicalUm,
  caliperScaleMicronsPerPixel,
  pixelsToMicrons,
  rgbToLuminance,
  segmentLengthPx,
  type SemAnalysisParams,
} from "../src/utils/semAnalysis";

// Golden numbers below were first cross-checked against hand calculations (see comments) and against the UNMODIFIED
// inline algorithm in SEMAutoAnalyzerStudio.tsx (HEAD faa6684): a differential run over 1944 synthetic images and
// parameter sets was bit-identical before the component was wired to this module.

type Img = { data: Uint8ClampedArray; width: number; height: number };

function makeImage(width: number, height: number, lum: (x: number, y: number) => number): Img {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      const v = lum(x, y);
      data[i] = v;
      data[i + 1] = v;
      data[i + 2] = v;
      data[i + 3] = 255;
    }
  }
  return { data, width, height };
}

const sample = { material: "Ti-6Al-4V", category: "Titanium & Aerospace Alloys" } as SemAnalysisParams["selectedSample"];
const lpbfSample = { material: "Inconel 718", category: "Additive Manufacturing (LPBF)" } as SemAnalysisParams["selectedSample"];

function run(img: Img, over: Partial<SemAnalysisParams> = {}) {
  return analyzeSemImage({
    ...img,
    scaleMicronsPerPixel: 0.5,
    poreThreshold: 40,
    matrixLowerThreshold: 41,
    matrixUpperThreshold: 145,
    precipitateUpperThreshold: 205,
    grainSensitivity: 50,
    visiblePhases: { matrix: true, precipitates: true, carbides: true, pores: true },
    pointGridDensity: 64,
    selectedSample: sample,
    ...over,
  });
}

// 100 x 80 image: vertical stripes 10 px wide alternating 100 (matrix) / 200 (precipitate);
// the bottom 8 rows (10 % banner) are 255 and must be ignored.
const stripes = makeImage(100, 80, (x, y) => (y >= 72 ? 255 : Math.floor(x / 10) % 2 === 0 ? 100 : 200));

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

test("striped image: hand-computed Heyn intercept, grain size and stereology", () => {
  const { results: r, effectiveHeight } = run(stripes);
  assert.equal(effectiveHeight, 72);
  // 8 test lines, each crossing the 9 stripe boundaries (cols 10..90) -> 72 intercepts, total line 8*100*0.5 = 400 um.
  assert.equal(r.interceptCount, 72);
  assert.equal(r.meanInterceptLengthUm, 5.56); // 400/72 = 5.5556
  assert.equal(r.astmGrainSizeNumber, 11.7);
  assert.equal(r.subgrainCellSpacingUm, 2.34); // 5.56 * 0.42
  assert.equal(r.inferredCoolingRateKs, Math.round(Math.pow(2.34 / 50, -3) * 1000));
  // Phase fractions: five matrix stripes, five precipitate stripes inside the 72 analysed rows.
  const frac = Object.fromEntries(r.phaseFractions.map((p) => [p.phase, p.fractionPct]));
  assert.deepEqual(frac, { "Primary Matrix": 50, Precipitates: 50, "Carbides / Intermetallics": 0, "Micro-Voids": 0 });
  assert.equal(r.totalAreaUm2, 1800); // 100 * 72 * 0.5^2
  assert.equal(r.totalPorosityPct, 0);
  assert.equal(r.defectCount, 0);
  assert.equal(r.meanPoreDiameterUm, 0.8); // no pores -> documented fallback constants
  assert.equal(r.maxPoreDiameterUm, 1.5);
  assert.equal(r.luminanceHistogram[100], 5 * 10 * 72);
  assert.equal(r.luminanceHistogram[255], 100 * 8);
});

test("Hall-Petch style strength estimates follow the documented heuristic", () => {
  const { results: r } = run(stripes);
  // increment = round(180 / sqrt(5.56)) = 76; base 750 MPa (non-LPBF)
  assert.equal(r.estimatedYieldStrengthMpa, 826);
  assert.equal(r.estimatedTensileStrengthMpa, 1033); // round(826 * 1.25) = round(1032.5)
  assert.equal(r.estimatedHardnessHv, 333); // round(1033 / 3.1)
  const lpbf = run(stripes, { selectedSample: lpbfSample }).results;
  assert.equal(lpbf.estimatedYieldStrengthMpa, 1026); // base 950 for LPBF
  assert.equal(lpbf.estimatedTensileStrengthMpa, 1283);
  assert.equal(lpbf.estimatedHardnessHv, 414);
});

test("calibration scales lengths and areas: doubling um/px doubles l_bar and lowers G by 2", () => {
  const a = run(stripes, { scaleMicronsPerPixel: 0.5 }).results;
  const b = run(stripes, { scaleMicronsPerPixel: 1 }).results;
  assert.equal(b.meanInterceptLengthUm, 11.11); // 800/72
  assert.ok(Math.abs(a.astmGrainSizeNumber - b.astmGrainSizeNumber - 2) <= 0.1);
  assert.equal(b.totalAreaUm2, a.totalAreaUm2 * 4);
  assert.equal(b.interceptCount, a.interceptCount);
});

test("grain sensitivity changes the intercept detection threshold ((100 - s) * 0.4)", () => {
  // Step height 100 grey levels: detected for every s >= 0 here.
  assert.equal(run(stripes, { grainSensitivity: 0 }).results.interceptCount, 72);
  // A faint 10-level stripe pattern: threshold at s=50 is 20 (not detected, floor of 4 per line applies),
  // at s=90 it is 4 (detected).
  const faint = makeImage(100, 80, (x) => (Math.floor(x / 10) % 2 === 0 ? 100 : 110));
  assert.equal(run(faint, { grainSensitivity: 50 }).results.interceptCount, 32); // 8 lines * max(4, 0)
  assert.equal(run(faint, { grainSensitivity: 90 }).results.interceptCount, 72);
});

test("flat image: minimum of 4 intercepts per line", () => {
  const flat = makeImage(100, 80, () => 128);
  const { results: r } = run(flat);
  assert.equal(r.interceptCount, 32);
  assert.equal(r.meanInterceptLengthUm, 12.5); // 400 / 32
  assert.deepEqual(r.phaseFractions.map((p) => p.fractionPct), [100, 0, 0, 0]);
});

test("pore blobs: area, equivalent diameter, circularity and defect classification (hand computed)", () => {
  const img = makeImage(100, 80, (x, y) => {
    if (x >= 20 && x < 30 && y >= 20 && y < 30) return 10; // 10x10 square void
    if (x >= 40 && x < 70 && y >= 40 && y < 42) return 10; // 30x2 slit
    return 128;
  });
  const { results: r } = run(img);
  assert.equal(r.defectCount, 2);
  const [sq, slit] = r.defects;
  // Square: area 100 px = 25 um2; d_eq = 2*sqrt(25/pi) = 5.64 um; perimeter px = 36 (boundary ring);
  // circularity = 4*pi*100/36^2 = 0.97; aspect 1 -> spherical gas pore.
  assert.deepEqual(
    [sq.areaPx, sq.areaUm2, sq.equivalentDiameterUm, sq.perimeterPx, sq.circularity, sq.aspectRatio, sq.defectType],
    [100, 25, 5.64, 36, 0.97, 1, "Gas Pore (Spherical)"]
  );
  // Slit: 60 px = 15 um2; d_eq = 4.37 um; every pixel is a boundary pixel (perimeter 60);
  // circularity = 4*pi*60/3600 = 0.21; aspect 15 -> lack of fusion.
  assert.deepEqual(
    [slit.areaPx, slit.areaUm2, slit.equivalentDiameterUm, slit.perimeterPx, slit.circularity, slit.aspectRatio, slit.defectType],
    [60, 15, 4.37, 60, 0.21, 15, "Lack of Fusion (Irregular)"]
  );
  // Porosity = 160 px of 100*72 analysed px = 2.222 %
  assert.equal(r.totalPorosityPct, 2.222);
  assert.deepEqual(r.poreClassification, { gasPoresPct: 50, lackOfFusionPct: 50, keyholePct: 0 });
  assert.deepEqual(r.poreSizeDistribution.map((s) => s.count), [0, 0, 1, 1, 0]); // < 1, 1-3, 3-5, 5-10, > 10 um
  assert.ok(Math.abs(r.meanPoreDiameterUm - (5.64 + 4.37) / 2) <= 0.01);
  assert.equal(r.maxPoreDiameterUm, 5.64);
});

test("blobs smaller than 5 px are discarded as noise", () => {
  const img = makeImage(100, 80, (x, y) => (x >= 20 && x < 22 && y >= 20 && y < 22 ? 10 : 128)); // 4 px
  const { results: r } = run(img);
  assert.equal(r.defectCount, 0);
  assert.equal(r.totalPorosityPct, 0.056); // still counted in the area fraction: 4/7200
});

test("point-count grid and 95 % confidence statistics (ASTM E562)", () => {
  const { results: r } = run(stripes, { pointGridDensity: 64 });
  // 8x8 grid, V_v(precipitate) = 0.5: CI95 = 1.96*sqrt(0.5*0.5/64)*100 = 12.25 %, rel. accuracy = CI/0.5 = 24.5 %.
  assert.equal(r.pointCountStats.gridSize, 64);
  assert.equal(r.pointCountStats.confidenceInterval95Pct, 12.25);
  assert.equal(r.pointCountStats.relativeAccuracyPct, 24.5);
  const p = r.pointCountStats;
  assert.equal(p.matrixPoints + p.precipitatePoints + p.carbidePoints + p.porePoints, 64);
  assert.equal(run(stripes, { pointGridDensity: 16 }).results.pointCountStats.gridSize, 16);
});

test("phase composition rows carry labels by material and threshold bounds", () => {
  const ti = run(stripes).results.phaseComposition;
  assert.deepEqual(ti.map((p) => p.id), ["matrix", "precipitates", "carbides", "pores"]);
  assert.equal(ti[0].formula, "α / Prior-β");
  assert.equal(ti[1].formula, "Acicular α' Martensite");
  assert.deepEqual([ti[0].minLum, ti[0].maxLum, ti[1].minLum, ti[1].maxLum, ti[2].minLum, ti[2].maxLum], [41, 145, 146, 205, 206, 255]);
  const inco = run(stripes, { selectedSample: lpbfSample }).results.phaseComposition;
  assert.equal(inco[0].formula, "γ (fcc Ni-Cr-Fe)");
  assert.equal(inco[2].formula, "Laves / MC Carbides");
  const hidden = run(stripes, { visiblePhases: { precipitates: false } }).results.phaseComposition;
  assert.deepEqual(hidden.map((p) => p.visible), [true, false, true, true]);
});

test("precipitate particle metrics for the striped image", () => {
  const { results: r } = run(stripes);
  const pr = r.phaseComposition[1];
  // Sampling grid y=4..66 step 2 (32 rows) x precipitate columns {10-18,30-38,50-58,70-78,90-94} even (23) = 736 particles
  assert.equal(pr.particleCount, 736);
  assert.equal(pr.particleDensityPer1000Um2, 408.9); // 736 / 1800 * 1000
  assert.equal(pr.areaUm2, 900); // 50 % of 1800
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
