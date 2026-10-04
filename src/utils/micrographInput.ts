// Input preparation and bookkeeping for the micrograph measurement view. Nothing here computes a measurement:
// the image is decoded to 8-bit grey (BT.601 luma), user inputs are assembled into the request for
// python/micrograph_measure.py, and the returned result is packaged for export. Lengths, fractions, counts
// and G shown in the view come from the Python result only.
import { caliperPhysicalUm, rgbToLuminance, segmentLengthPx, type CaliperUnit, type ViewportSegment } from "./semAnalysis";
import type { MicrographMeasureRequest, MicrographMeasureResult } from "../services/micrographMeasureService";

/** Largest side the authority accepts (python/micrograph_measure.py MAX_SIDE_PX). */
export const MAX_SIDE_PX = 4096;
export const DECODABLE_TYPES = ["image/png", "image/jpeg", "image/bmp", "image/gif", "image/webp"] as const;
export const TIFF_MESSAGE =
  "TIFF cannot be decoded in the browser, so it is not loaded. Export the micrograph as PNG (lossless) or JPEG from " +
  "the instrument software and enter the scale from its scale bar. Pixel-size metadata in TIFF tags is not read.";

/** Explicit refusal before any decoding is attempted; null when the file type is decodable. */
export function unsupportedImageReason(name: string, type: string): string | null {
  const lower = name.toLowerCase();
  if (type === "image/tiff" || lower.endsWith(".tif") || lower.endsWith(".tiff")) return TIFF_MESSAGE;
  if (!(DECODABLE_TYPES as readonly string[]).includes(type)) {
    return `${name}: unsupported type ${type || "unknown"}; load PNG, JPEG, BMP, GIF or WebP.`;
  }
  return null;
}

export interface GreyImage {
  width: number;
  height: number;
  grey: Uint8Array;
  /** true when some pixel had R, G and B not all equal (converted with BT.601 luma). */
  wasColour: boolean;
}

/** RGBA (ImageData layout) to 8-bit grey with the BT.601 luma used everywhere in this module. */
export function greyFromRgba(data: ArrayLike<number>, width: number, height: number): GreyImage {
  const grey = new Uint8Array(width * height);
  let wasColour = false;
  for (let i = 0, p = 0; i < grey.length; i++, p += 4) {
    const r = data[p], g = data[p + 1], b = data[p + 2];
    if (r !== g || g !== b) wasColour = true;
    grey[i] = rgbToLuminance(r, g, b);
  }
  return { width, height, grey, wasColour };
}

/** 256-bin grey histogram of the loaded image (an input display for picking thresholds, not a result). */
export function greyHistogram(grey: Uint8Array): number[] {
  const bins = new Array<number>(256).fill(0);
  for (let i = 0; i < grey.length; i++) bins[grey[i]]++;
  return bins;
}

export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  return btoa(binary);
}

export async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes as unknown as ArrayBuffer);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

export type CalibrationInput =
  | { mode: "scale-bar"; segment: ViewportSegment | null; barValue: number; barUnit: CaliperUnit }
  | { mode: "pixel-size"; umPerPx: number; note: string };

/** Calibration keys of the request, or the reason why no calibration exists yet. */
export function calibrationRequestKeys(input: CalibrationInput):
  { keys: Pick<MicrographMeasureRequest, "barLengthUm" | "barLengthPx" | "umPerPx" | "calibrationNote"> } | { reason: string } {
  if (input.mode === "scale-bar") {
    const px = segmentLengthPx(input.segment);
    if (px < 2) return { reason: "Draw the caliper over the image scale bar (two clicks on the bar ends)." };
    if (!(Number.isFinite(input.barValue) && input.barValue > 0)) return { reason: "Enter the scale-bar length printed on the image." };
    return { keys: { barLengthUm: caliperPhysicalUm(input.barValue, input.barUnit), barLengthPx: px,
      calibrationNote: `scale bar ${input.barValue} ${input.barUnit} measured with the caliper` } };
  }
  if (!(Number.isFinite(input.umPerPx) && input.umPerPx > 0)) return { reason: "Enter a positive pixel size in µm/px." };
  if (!input.note.trim()) return { reason: "State where the pixel size comes from (instrument record, calibration)." };
  return { keys: { umPerPx: input.umPerPx, calibrationNote: input.note.trim() } };
}

export interface MeasureSettings {
  crop: { top: number; bottom: number; left: number; right: number };
  dark: { enabled: boolean; label: string; maxGrey: number };
  bright: { enabled: boolean; label: string; minGrey: number };
  grains: { enabled: boolean; boundaryMaxGrey: number };
  tiles: number;
  sensitivityDeltaGrey: number;
  minAreaPx: number;
  linesPerDirection: number;
}

export const DEFAULT_SETTINGS: MeasureSettings = {
  crop: { top: 0, bottom: 0, left: 0, right: 0 },
  dark: { enabled: false, label: "pores / voids", maxGrey: 60 },
  bright: { enabled: false, label: "second phase", minGrey: 200 },
  grains: { enabled: false, boundaryMaxGrey: 90 },
  tiles: 4,
  sensitivityDeltaGrey: 10,
  minAreaPx: 4,
  linesPerDirection: 8,
};

export interface ManualCounting {
  clicks: { line: number; x: number; y: number; weight: number }[];
}

/** Why a run is not possible yet (the button stays disabled), or null. Calibration is mandatory in the view. */
export function runBlocker(image: GreyImage | null, calibration: CalibrationInput, settings: MeasureSettings,
  manual: ManualCounting | null): string | null {
  if (!image) return "Load a micrograph image first.";
  const cal = calibrationRequestKeys(calibration);
  if ("reason" in cal) return `Calibration required: ${cal.reason}`;
  if (!settings.dark.enabled && !settings.bright.enabled && !settings.grains.enabled && !manual) {
    return "Choose at least one measurement (dark class, bright class, grain intercepts or manual counting).";
  }
  if (settings.dark.enabled && settings.bright.enabled && settings.dark.maxGrey >= settings.bright.minGrey) {
    return "The dark threshold must be below the bright threshold.";
  }
  return null;
}

/** Per-line intersection counts from the user's clicks (bookkeeping of clicks; sums of 1 and 1/2 weights). */
export function manualCounts(clicks: ManualCounting["clicks"], lineCount: number): number[] {
  const counts = new Array<number>(lineCount).fill(0);
  for (const click of clicks) if (click.line >= 0 && click.line < lineCount) counts[click.line] += click.weight;
  return counts;
}

export function buildMeasureRequest(image: GreyImage, calibration: CalibrationInput, settings: MeasureSettings,
  manual: ManualCounting | null): MicrographMeasureRequest {
  const cal = calibrationRequestKeys(calibration);
  if ("reason" in cal) throw new Error(cal.reason);
  const request: MicrographMeasureRequest = {
    imageWidth: image.width, imageHeight: image.height, imageData: bytesToBase64(image.grey),
    cropTopPx: settings.crop.top, cropBottomPx: settings.crop.bottom, cropLeftPx: settings.crop.left, cropRightPx: settings.crop.right,
    ...cal.keys,
    tiles: settings.tiles, sensitivityDeltaGrey: settings.sensitivityDeltaGrey, minAreaPx: settings.minAreaPx,
    linesPerDirection: settings.linesPerDirection, returnMasks: true,
  };
  if (settings.dark.enabled) Object.assign(request, { darkMaxGrey: settings.dark.maxGrey, darkLabel: settings.dark.label.trim() || "dark class" });
  if (settings.bright.enabled) Object.assign(request, { brightMinGrey: settings.bright.minGrey, brightLabel: settings.bright.label.trim() || "bright class" });
  if (settings.grains.enabled) request.boundaryMaxGrey = settings.grains.boundaryMaxGrey;
  if (manual) {
    request.manualCounts = manualCounts(manual.clicks, 2 * settings.linesPerDirection);
    request.manualClicks = manual.clicks;
  }
  return request;
}

/** Identity of everything that changes the result; a result whose signature differs is stale. */
export function requestSignature(imageKey: string | null, calibration: CalibrationInput, settings: MeasureSettings,
  manual: ManualCounting | null): string {
  return JSON.stringify([imageKey, calibration, settings, manual]);
}

/** Unpack a numpy packbits (big bit order) mask of width x height into 0/1 bytes. */
export function unpackMask(base64: string, width: number, height: number): Uint8Array {
  const packed = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const out = new Uint8Array(width * height);
  for (let i = 0; i < out.length; i++) out[i] = (packed[i >> 3] >> (7 - (i & 7))) & 1;
  return out;
}

export interface SourceProvenance {
  fileName: string;
  /** sha256 of the loaded file bytes. */
  fileSha256: string;
  kind: "uploaded-file";
  convertedFromColour: boolean;
}

/** JSON measurement record: the Python result unchanged plus the source and user inputs (image bytes omitted). */
export function buildExportRecord(result: MicrographMeasureResult, request: MicrographMeasureRequest,
  source: SourceProvenance, exportedAt: string) {
  const { imageData: _omitted, manualClicks, ...inputs } = request;
  void _omitted;
  return {
    recordType: "micrograph-measurement",
    exportedAt,
    source,
    calibrationSource: result.record.calibration,
    pixelSha256: result.record.pixelSha256,
    requestInputs: { ...inputs, manualClicks: manualClicks ?? null },
    result: { ...result, classes: Object.fromEntries(Object.entries(result.classes).map(([key, value]) => {
      if (!value) return [key, value];
      const { maskPackedBase64: _mask, ...rest } = value;
      void _mask;
      return [key, rest];
    })) },
    note: "Measurement software output on one image; synthetic-oracle verification only, no real-image validation.",
  };
}

const csvCell = (value: unknown) => {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

/** Flat CSV (quantity, value, unit, ci95 low, ci95 high, note) of the Python result. */
export function exportCsv(result: MicrographMeasureResult, source: SourceProvenance): string {
  const rows: unknown[][] = [["quantity", "value", "unit", "ci95_low", "ci95_high", "note"]];
  const cal = result.record.calibration;
  rows.push(["source_file", source.fileName, "", "", "", source.kind]);
  rows.push(["source_file_sha256", source.fileSha256 ?? "", "", "", "", ""]);
  rows.push(["pixel_sha256", result.record.pixelSha256, "", "", "", result.record.pixelSha256Basis]);
  rows.push(["calibration_um_per_px", cal.umPerPx ?? "", "µm/px", "", "", `${cal.method ?? "none"}: ${cal.derivation ?? cal.reason ?? ""}`]);
  rows.push(["method_version", result.methodVersion, "", "", "", ""]);
  const q = (name: string, v: { value: number | null; unit: string | null; ci95?: [number | null, number | null]; reason?: string; method?: string }) =>
    rows.push([name, v.value ?? "", v.unit ?? "", v.ci95?.[0] ?? "", v.ci95?.[1] ?? "", v.reason ?? v.method ?? ""]);
  for (const [key, cls] of Object.entries(result.classes)) {
    if (!cls) continue;
    const label = `${key}(${cls.label})`;
    q(`${label}.area_fraction`, cls.areaFraction.pixelFraction);
    rows.push([`${label}.fraction_at_threshold_minus_delta`, cls.areaFraction.thresholdSensitivity.fractionAtThresholdMinusDelta, "1", "", "", ""]);
    rows.push([`${label}.fraction_at_threshold_plus_delta`, cls.areaFraction.thresholdSensitivity.fractionAtThresholdPlusDelta, "1", "", "", ""]);
    rows.push([`${label}.particle_count`, cls.particles.count, "1", "", "", `min area ${cls.particles.minAreaPx} px, 8-connectivity`]);
    q(`${label}.number_density`, cls.particles.numberDensity);
    q(`${label}.mean_ecd`, cls.particles.meanEcd);
    q(`${label}.max_ecd`, cls.particles.maxEcd);
    q(`${label}.mean_free_path`, cls.particles.meanFreePath);
  }
  for (const [name, gs] of [["grain_auto", result.grainSize], ["grain_manual", result.grainSizeManual]] as const) {
    if (!gs) continue;
    rows.push([`${name}.intersections`, gs.totalIntersections, "1", "", "", gs.mode]);
    q(`${name}.mean_intercept`, gs.meanIntercept);
    q(`${name}.astm_g`, gs.astmG);
    rows.push([`${name}.relative_accuracy_pct`, gs.relativeAccuracyPct ?? "", "%", "", "", gs.warnings.join("; ")]);
  }
  return rows.map((row) => row.map(csvCell).join(",")).join("\n");
}
