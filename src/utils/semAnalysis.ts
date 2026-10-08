// Small helpers kept from the former SEM analyzer (the in-browser image analysis was removed with the
// micrograph module). BT.601 luma, the ASTM E112 G(l_bar) relation
// and the caliper/ruler length helpers used for display.

/** ITU-R BT.601 luma used for the greyscale matrix and the pipette tool (rounded to an integer 0-255). */
export function rgbToLuminance(r: number, g: number, b: number): number {
  return Math.round(0.299 * r + 0.587 * g + 0.114 * b);
}

/**
 * ASTM E112 grain size number from the mean lineal intercept length (given in µm):
 * G = -6.64385 * log10(l_bar in mm) - 3.288, rounded to 0.1.
 */
export function astmGrainSizeNumberFromIntercept(meanInterceptLengthUm: number): number {
  const lBarMm = meanInterceptLengthUm / 1000;
  return Number((-6.64385 * Math.log10(lBarMm) - 3.288).toFixed(1));
}

export type CaliperUnit = "µm" | "nm" | "mm";

export interface ViewportSegment {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

/** Euclidean length in image pixels of a ruler / caliper segment (0 when no segment). */
export function segmentLengthPx(points: ViewportSegment | null): number {
  return points
    ? Math.sqrt(
        Math.pow(points.x2 - points.x1, 2) +
          Math.pow(points.y2 - points.y1, 2)
      )
    : 0;
}

/** Ruler reading in micrometres, rounded to 2 decimals. */
export function pixelsToMicrons(distancePx: number, scaleMicronsPerPixel: number): number {
  return Number((distancePx * scaleMicronsPerPixel).toFixed(2));
}

/** Convert a caliper scale-bar length entered in nm / µm / mm to micrometres. */
export function caliperPhysicalUm(value: number, unit: CaliperUnit): number {
  let physicalUm = value;
  if (unit === "nm") physicalUm = value / 1000;
  if (unit === "mm") physicalUm = value * 1000;
  return physicalUm;
}

/** Calibrated scale (µm per pixel) from a caliper drag across a known scale-bar length, rounded to 5 decimals. */
export function caliperScaleMicronsPerPixel(physicalUm: number, caliperDistancePx: number): number {
  return Number((physicalUm / caliperDistancePx).toFixed(5));
}
