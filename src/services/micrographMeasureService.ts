// Client for the micrograph measurement authority (python/micrograph_measure.py via the LPBF worker route
// POST /api/python/micrograph-measure). The browser only decodes the image and sends user inputs; every
// number shown as a measurement comes back from Python. Nothing here recomputes a result.

export interface MicrographMeasureRequest {
  imageWidth: number;
  imageHeight: number;
  /** 8-bit greyscale bytes, row-major, base64. */
  imageData: string;
  cropTopPx?: number;
  cropBottomPx?: number;
  cropLeftPx?: number;
  cropRightPx?: number;
  umPerPx?: number;
  barLengthUm?: number;
  barLengthPx?: number;
  calibrationNote?: string;
  darkMaxGrey?: number;
  darkLabel?: string;
  brightMinGrey?: number;
  brightLabel?: string;
  boundaryMaxGrey?: number;
  manualCounts?: number[];
  manualClicks?: { line: number; x: number; y: number; weight: number }[];
  tiles?: number;
  sensitivityDeltaGrey?: number;
  minAreaPx?: number;
  linesPerDirection?: number;
  returnMasks?: boolean;
}

/** A measured quantity, or null with the reason it is unavailable. */
export interface MeasuredQuantity {
  value: number | null;
  unit: string | null;
  method?: string;
  ci95?: [number | null, number | null];
  reason?: string;
}

export interface MicrographTestLine {
  index: number;
  orientation: "h" | "v";
  position: number;
  lengthPx: number;
  roiOffset: [number, number];
}

export interface MicrographParticle {
  id: number;
  areaPx: number;
  centroidX: number;
  centroidY: number;
  bbox: [number, number, number, number];
  ecdPx: number;
  ecdUm: number | null;
  perimeterPx: number;
  circularity: number | null;
  aspectRatio: number;
  shapeClass: "near-circular" | "irregular" | "elongated" | "too-small-to-classify";
  touchesRoiEdge: boolean;
}

export interface MicrographClassResult {
  label: string;
  threshold: { label: string; rule: string; maxGrey?: number; minGrey?: number };
  areaFraction: {
    pixelFraction: MeasuredQuantity;
    fieldToField: {
      tiles: string; n: number; tileFractions: number[]; mean: number; sd: number | null;
      tCritical: number | null; halfWidth: number | null; note: string;
    };
    thresholdSensitivity: {
      deltaGrey: number; fractionAtThresholdMinusDelta: number; fractionAtThresholdPlusDelta: number; note: string;
    };
    classArea: MeasuredQuantity;
    pixelCount: number;
  };
  particles: {
    connectivity: number;
    minAreaPx: number;
    componentsBelowMinArea: number;
    count: number;
    countTouchingRoiEdge: number;
    numberPerMegapixel: number;
    shapeClasses: Record<string, number>;
    shapeClassRule: string;
    sizeStatisticsBasis: string;
    particleList: MicrographParticle[];
    particleListTruncated: boolean;
    detectionLimitEcdUm: MeasuredQuantity;
    numberDensity: MeasuredQuantity;
    meanEcd: MeasuredQuantity;
    medianEcd: MeasuredQuantity;
    maxEcd: MeasuredQuantity;
    sdEcd: MeasuredQuantity;
    meanEcdPx?: number;
    interceptsPerPixelLine: number;
    meanFreePath: MeasuredQuantity;
    meanFreePathPx?: number;
  };
  maskPackedBase64?: string;
  maskEncoding?: string;
}

export interface MicrographGrainSize {
  mode: string;
  lines: number;
  totalLengthPx: number;
  totalIntersections: number;
  warnings: string[];
  countingRule: string;
  meanInterceptPx: number | null;
  meanIntercept: MeasuredQuantity;
  astmG: MeasuredQuantity;
  relativeAccuracyPct: number | null;
  perLineIntersections?: number[];
  perLineIntersectionsPerPx?: { mean: number; sd: number | null; n: number; tCritical: number | null; halfWidth: number | null };
  intersections?: { line: number; x: number; y: number; weight: number }[];
  boundaryMaxGrey?: number;
  boundaryNetworkLargestComponentShare?: number;
  boundaryFractionOfRoi?: number;
  ciNote?: string;
  clicks?: { line: number; x: number; y: number; weight: number }[];
}

export interface MicrographMeasureResult {
  schema: string;
  methodVersion: string;
  record: {
    generatedBy: string;
    pixelSha256: string;
    pixelSha256Basis: string;
    width: number;
    height: number;
    roi: { x0: number; y0: number; x1: number; y1: number };
    roiAreaPx: number;
    calibration: {
      calibrated: boolean; method: string | null; umPerPx: number | null; barLengthUm?: number;
      barLengthPx?: number; note?: string | null; derivation?: string; reason?: string;
    };
    classes: Record<string, unknown>;
    options: Record<string, unknown>;
  };
  calibrationRequired: string | null;
  testLines: MicrographTestLine[];
  classes: { dark?: MicrographClassResult; bright?: MicrographClassResult };
  grainSize: MicrographGrainSize | null;
  grainSizeManual: MicrographGrainSize | null;
  limitations: string[];
}

/** POST the request to the Python authority; throws with the server's error message on failure. */
export async function measureMicrograph(request: MicrographMeasureRequest, signal?: AbortSignal): Promise<MicrographMeasureResult> {
  const res = await fetch("/api/python/micrograph-measure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(res.ok ? "Invalid response from the measurement service." : `Measurement failed (${res.status}).`);
  }
  // 422: validation envelope {errorKind: "validation", error: {message}}; 413/500: {error: "..."}; an internal
  // failure of the script arrives as HTTP 200 with errorKind "internal" (routes/physics.ts dispatch mapping).
  const body = data as { error?: unknown; errorKind?: unknown; schema?: unknown };
  const message = typeof body?.error === "string" ? body.error
    : typeof (body?.error as { message?: unknown })?.message === "string" ? (body.error as { message: string }).message : null;
  if (!res.ok || body?.errorKind !== undefined || body?.schema !== "micrograph-measure/1") {
    throw new Error(message ?? `Measurement failed (${res.status}).`);
  }
  return data as MicrographMeasureResult;
}
