import React from "react";
import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { MicrographLab } from "../src/components/MicrographLab";
import { MicrographMeasureResults } from "../src/components/MicrographMeasureResults";
import type { MicrographMeasureResult, MeasuredQuantity } from "../src/services/micrographMeasureService";
import {
  DEFAULT_SETTINGS,
  TIFF_MESSAGE,
  buildExportRecord,
  buildMeasureRequest,
  exportCsv,
  greyFromRgba,
  manualCounts,
  runBlocker,
  syntheticDiscs,
  syntheticSquareGrid,
  unpackMask,
  unsupportedImageReason,
  type CalibrationInput,
} from "../src/utils/micrographInput";

// Micrograph rework, W3: the view decodes and assembles inputs, python/micrograph_measure.py computes. These tests
// pin the view-side rules: calibration gates the run, TIFF is refused before decoding, the result component shows
// the authority's numbers unchanged, and the export carries the calibration source and both SHA-256 values.

const q = (value: number | null, unit: string | null, extra: Partial<MeasuredQuantity> = {}): MeasuredQuantity =>
  ({ value, unit, ...extra });

function mockResult(calibrated: boolean): MicrographMeasureResult {
  const um = (v: number, ci?: [number, number]) => calibrated ? q(v, "µm", { method: "m", ...(ci ? { ci95: ci } : {}) })
    : q(null, "µm", { reason: "uncalibrated: no length without a scale" });
  return {
    schema: "micrograph-measure/1",
    methodVersion: "micrograph-measure-1.0.0",
    record: {
      generatedBy: "python/micrograph_measure.py", pixelSha256: "ab".repeat(32), pixelSha256Basis: "basis",
      width: 200, height: 240, roi: { x0: 0, y0: 0, x1: 200, y1: 200 }, roiAreaPx: 40000,
      calibration: calibrated
        ? { calibrated: true, method: "scale-bar", barLengthUm: 50, barLengthPx: 100, umPerPx: 0.5, note: "bar", derivation: "umPerPx = barLengthUm / barLengthPx" }
        : { calibrated: false, method: null, umPerPx: null, reason: "uncalibrated: no scale bar or pixel size was supplied" },
      classes: {}, options: {},
    },
    calibrationRequired: calibrated ? null : "uncalibrated: no scale bar or pixel size was supplied",
    testLines: [{ index: 0, orientation: "h", position: 22, lengthPx: 200, roiOffset: [0, 0] }],
    classes: {
      dark: {
        label: "pores", threshold: { label: "pores", rule: "grey <= maxGrey", maxGrey: 67 },
        areaFraction: {
          pixelFraction: q(0.0213, "1", { method: "pixel count", ci95: [0.0187, 0.0239] }),
          fieldToField: { tiles: "4x4", n: 16, tileFractions: [], mean: 0.0213, sd: 0.0049, tCritical: 2.131, halfWidth: 0.0026, note: "" },
          thresholdSensitivity: { deltaGrey: 10, fractionAtThresholdMinusDelta: 0.0201, fractionAtThresholdPlusDelta: 0.0225, note: "" },
          classArea: calibrated ? q(213, "µm²", { method: "m" }) : q(null, "µm²", { reason: "uncalibrated: no area in µm² without a scale" }),
          pixelCount: 852,
        },
        particles: {
          connectivity: 8, minAreaPx: 4, componentsBelowMinArea: 3, count: 42, countTouchingRoiEdge: 2, numberPerMegapixel: 1050,
          shapeClasses: { "near-circular": 30, irregular: 8, elongated: 2, "too-small-to-classify": 2 }, shapeClassRule: "rule.",
          sizeStatisticsBasis: "interior", particleList: [], particleListTruncated: false,
          detectionLimitEcdUm: um(1.128), numberDensity: calibrated ? q(4200, "1/mm²", { method: "m" }) : q(null, "1/mm²", { reason: "uncalibrated" }),
          meanEcd: um(3.75), medianEcd: um(3.5), maxEcd: um(9.25), sdEcd: um(1.5),
          interceptsPerPixelLine: 0.01, meanFreePath: um(48.9),
        },
      },
    },
    grainSize: {
      mode: "automatic: boundaries darker than grains", lines: 16, totalLengthPx: 3200, totalIntersections: 128,
      warnings: [], countingRule: "ASTM E112 intersection count", meanInterceptPx: 25,
      meanIntercept: um(12.5, [12.25, 12.75]),
      astmG: calibrated ? q(9.3, null, { method: "G", ci95: [9.25, 9.35] }) : q(null, null, { reason: "uncalibrated: no length or ASTM G without a scale" }),
      relativeAccuracyPct: 2.5,
    },
    grainSizeManual: null,
    limitations: ["Measurement software verified only against synthetic images."],
  };
}

const scaleBar = (segment: { x1: number; y1: number; x2: number; y2: number } | null, barValue: number): CalibrationInput =>
  ({ mode: "scale-bar", segment, barValue, barUnit: "µm" });

test("the run stays blocked until an image and a calibration exist", () => {
  const grid = syntheticSquareGrid();
  const dark = { ...DEFAULT_SETTINGS, dark: { ...DEFAULT_SETTINGS.dark, enabled: true } };
  assert.match(runBlocker(null, scaleBar(null, NaN), dark, null)!, /Load an image/);
  assert.match(runBlocker(grid, scaleBar(null, 50), dark, null)!, /^Calibration required: Draw the caliper/);
  assert.match(runBlocker(grid, scaleBar({ x1: 50, y1: 220, x2: 150, y2: 220 }, NaN), dark, null)!, /^Calibration required: Enter the scale-bar length/);
  assert.match(runBlocker(grid, { mode: "pixel-size", umPerPx: 0.5, note: " " }, dark, null)!, /^Calibration required: State where/);
  assert.match(runBlocker(grid, scaleBar({ x1: 50, y1: 220, x2: 150, y2: 220 }, 50), DEFAULT_SETTINGS, null)!, /at least one measurement/);
  assert.equal(runBlocker(grid, scaleBar({ x1: 50, y1: 220, x2: 150, y2: 220 }, 50), dark, null), null);
  assert.equal(runBlocker(grid, { mode: "pixel-size", umPerPx: 0.5, note: "SEM record" }, dark, null), null);
});

test("TIFF is refused with an explicit message before any decoding (no hang)", () => {
  assert.equal(unsupportedImageReason("sample.tif", "image/tiff"), TIFF_MESSAGE);
  assert.equal(unsupportedImageReason("SAMPLE.TIFF", ""), TIFF_MESSAGE);
  assert.match(TIFF_MESSAGE, /cannot be decoded in the browser/);
  assert.equal(unsupportedImageReason("a.png", "image/png"), null);
  assert.match(unsupportedImageReason("a.svg", "image/svg+xml")!, /unsupported type image\/svg\+xml/);
});

test("the result view shows the authority's numbers unchanged (no recomputation)", () => {
  const html = renderToStaticMarkup(<MicrographMeasureResults result={mockResult(true)} stale={false} />);
  for (const text of ["9.3", "9.25 to 9.35", "12.5 µm", "12.25 to 12.75 µm", "2.13 %", "1.87 % to 2.39 %", "3.75 µm",
    "48.9 µm", "4200 1/mm²", "42 (2 touch the ROI edge; 3 below 4 px not counted)", "2.01 % / 2.25 %", "0.5 µm/px"]) {
    assert.ok(html.includes(text), `missing ${text}`);
  }
  assert.doesNotMatch(html, /confidence|hardness|yield|cooling|Hall|certif|compliant|qualif/i);
  const stale = renderToStaticMarkup(<MicrographMeasureResults result={mockResult(true)} stale />);
  assert.match(stale, /out of date/);
});

test("uncalibrated results render every length and G as unavailable with the reason", () => {
  const html = renderToStaticMarkup(<MicrographMeasureResults result={mockResult(false)} stale={false} />);
  assert.match(html, /Unavailable: uncalibrated: no length or ASTM G without a scale/);
  assert.doesNotMatch(html, /µm<\/span>/);
  assert.ok(html.includes("2.13 %"), "fractions remain");
});

test("request assembly: calibration, crop, classes and manual counts; image bytes are the grey bytes", () => {
  const grid = syntheticSquareGrid();
  const settings = { ...DEFAULT_SETTINGS, crop: { ...DEFAULT_SETTINGS.crop, bottom: grid.dataBarRows },
    grains: { enabled: true, boundaryMaxGrey: 120 } };
  const cal = scaleBar({ x1: grid.scaleBar.x1, y1: grid.scaleBar.y, x2: grid.scaleBar.x2, y2: grid.scaleBar.y }, 50);
  const clicks = [{ line: 0, x: 12, y: 22, weight: 1 }, { line: 0, x: 37, y: 22, weight: 0.5 }, { line: 3, x: 1, y: 2, weight: 1 }];
  const req = buildMeasureRequest(grid, cal, settings, { clicks });
  assert.equal(req.barLengthUm, 50);
  assert.equal(req.barLengthPx, 100);
  assert.equal(req.cropBottomPx, 40);
  assert.equal(req.boundaryMaxGrey, 120);
  assert.equal(req.darkMaxGrey, undefined);
  assert.deepEqual(req.manualCounts, manualCounts(clicks, 16));
  assert.deepEqual(req.manualCounts!.slice(0, 4), [1.5, 0, 0, 1]);
  assert.deepEqual(Uint8Array.from(Buffer.from(req.imageData, "base64")), grid.grey);
  const mm = buildMeasureRequest(grid, { mode: "scale-bar", segment: { x1: 0, y1: 0, x2: 100, y2: 0 }, barValue: 500, barUnit: "nm" },
    { ...settings, dark: { ...settings.dark, enabled: true } }, null);
  assert.equal(mm.barLengthUm, 0.5);
  assert.equal(mm.darkMaxGrey, DEFAULT_SETTINGS.dark.maxGrey);
});

test("export record carries the calibration source, both SHA-256 values and no image bytes or masks", () => {
  const result = mockResult(true);
  result.classes.dark!.maskPackedBase64 = "AAAA";
  const grid = syntheticSquareGrid();
  const request = buildMeasureRequest(grid, scaleBar({ x1: 50, y1: 220, x2: 150, y2: 220 }, 50),
    { ...DEFAULT_SETTINGS, dark: { ...DEFAULT_SETTINGS.dark, enabled: true } }, null);
  const source = { fileName: "x.png", fileSha256: "cd".repeat(32), kind: "uploaded-file" as const, convertedFromColour: false };
  const record = buildExportRecord(result, request, source, "2026-10-04T00:00:00.000Z");
  const json = JSON.stringify(record);
  assert.equal(record.calibrationSource.method, "scale-bar");
  assert.equal(record.calibrationSource.barLengthUm, 50);
  assert.equal(record.pixelSha256, "ab".repeat(32));
  assert.equal(record.source.fileSha256, "cd".repeat(32));
  assert.ok(!json.includes(request.imageData.slice(0, 64)), "image bytes are not exported");
  assert.ok(!json.includes("maskPackedBase64"));
  const csv = exportCsv(result, source);
  assert.match(csv, new RegExp(`source_file_sha256,${"cd".repeat(32)}`));
  assert.match(csv, new RegExp(`pixel_sha256,${"ab".repeat(32)}`));
  assert.match(csv, /calibration_um_per_px,0.5,µm\/px/);
  assert.match(csv, /grain_auto\.astm_g,9\.3,,9\.25,9\.35/);
});

test("mask unpacking follows numpy packbits big bit order; grey conversion is BT.601", () => {
  assert.deepEqual([...unpackMask(btoa(String.fromCharCode(0b10100000, 0b00000001)), 4, 4)],
    [1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]);
  const g = greyFromRgba([255, 0, 0, 255, 10, 10, 10, 255], 2, 1);
  assert.deepEqual([...g.grey], [76, 10]);
  assert.equal(g.wasColour, true);
});

test("synthetic test patterns are deterministic and state their known answer", () => {
  const grid = syntheticSquareGrid();
  assert.equal(grid.width, 200);
  assert.equal(grid.height, 240);
  assert.equal(grid.grey[22 * 200 + 12], 40);  // boundary column 12 on test row 22
  assert.equal(grid.grey[22 * 200 + 20], 200); // grain
  assert.match(grid.knownAnswer, /25 px/);
  const a = syntheticDiscs(), b = syntheticDiscs();
  assert.deepEqual(a.grey, b.grey);
  assert.match(a.knownAnswer, /generated dark area \d+ of 120000 px/);
});

test("the module view has no invented samples, AI scan wording or property estimates", () => {
  const html = renderToStaticMarkup(<MicrographLab />);
  assert.match(html, /Micrograph Analysis/);
  assert.match(html, /Load image/);
  assert.match(html, /Synthetic test pattern/);
  assert.doesNotMatch(html, /authentic|AI Scanning|Hall-Petch|cooling rate|inspection report|certif|Calibrated standard/i);
});
