import type { MicrographSample } from "../types";

// Pure SEM micrograph measurement core extracted verbatim from SEMAutoAnalyzerStudio.tsx.
// Image-derived estimates (ASTM E2109 porosity, E112 line-intercept grain size, E562 point count);
// heuristic screening values, not certified metallography.

export const SEM_HARDNESS_UNAVAILABLE_NOTE =
  "Unavailable: no verified hardness relation for an inferred strength of an unspecified alloy (the steel regression needs a known non-austenitic hypoeutectoid steel)";

/** Shown instead of the former invented 1150 / 1380 MPa (and 1080 MPa card) values before an analysis has run. */
export const SEM_NO_ANALYSIS_TEXT = "Unavailable (no analysis run)";

/** Basis of the inferred Rm: an unsourced 1.25 x yield ratio, not an ASTM E8/E8M tensile test (the old label). */
export const SEM_TENSILE_BASIS_TEXT = "Screening estimate: 1.25 × inferred yield strength (unsourced ratio); not an ASTM E8/E8M test";

export interface SEMDefectBlob {
  id: number;
  x: number;
  y: number;
  width: number;
  height: number;
  areaPx: number;
  areaUm2: number;
  equivalentDiameterUm: number;
  perimeterPx: number;
  circularity: number; // 4*pi*area / perim^2
  aspectRatio: number;
  defectType: "Gas Pore (Spherical)" | "Lack of Fusion (Irregular)" | "Keyhole / Shrinkage";
}

export interface PhaseCompositionItem {
  id: string; // "matrix" | "precipitates" | "carbides" | "pores"
  name: string;
  formula: string;
  color: string;
  minLum: number;
  maxLum: number;
  areaPct: number;
  volumePct: number;
  areaUm2: number;
  meanDiameterUm: number;
  interParticleSpacingUm: number; // Mean free path λ in µm
  particleCount: number;
  particleDensityPer1000Um2: number;
  contrastCharacteristic: string;
  visible: boolean;
}

export interface LegendDetectionData {
  legendDetected: boolean;
  detectedScaleText: string;
  detectedScaleValueUm: number;
  scaleBarPixelLength: number;
  calculatedMicronsPerPixel: number;
  magnification: string;
  acceleratingVoltage: string;
  workingDistance: string;
  detector: string;
  confidenceScore: number;
  legendLocation: string;
  notes?: string;
}

export interface AutomatedCVResults {
  totalPorosityPct: number;
  defectCount: number;
  meanPoreDiameterUm: number;
  maxPoreDiameterUm: number;
  poreClassification: {
    gasPoresPct: number;
    lackOfFusionPct: number;
    keyholePct: number;
  };
  poreSizeDistribution: { range: string; count: number }[];
  phaseFractions: { phase: string; fractionPct: number; color: string }[];
  phaseComposition: PhaseCompositionItem[];
  astmGrainSizeNumber: number;
  meanInterceptLengthUm: number;
  interceptCount: number;
  subgrainCellSpacingUm: number;
  inferredCoolingRateKs: number; // K/s
  estimatedYieldStrengthMpa: number;
  estimatedTensileStrengthMpa: number;
  /** Always null: no defensible HV relation for an alloy-agnostic inferred strength (see SEM_HARDNESS_UNAVAILABLE_NOTE). */
  estimatedHardnessHv: number | null;
  estimatedHardnessNote: string;
  defects: SEMDefectBlob[];
  scaleMicronsPerPixel: number;
  totalAreaUm2: number;
  luminanceHistogram: number[];
  pointCountStats: {
    gridSize: number;
    matrixPoints: number;
    precipitatePoints: number;
    carbidePoints: number;
    porePoints: number;
    relativeAccuracyPct: number;
    confidenceInterval95Pct: number;
  };
}

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

export interface SemAnalysisParams {
  /** RGBA pixel buffer (ImageData.data layout), length >= width * height * 4. */
  data: ArrayLike<number>;
  width: number;
  height: number;
  scaleMicronsPerPixel: number;
  poreThreshold: number;
  matrixLowerThreshold: number;
  matrixUpperThreshold: number;
  precipitateUpperThreshold: number;
  grainSensitivity: number;
  visiblePhases: Record<string, boolean>;
  pointGridDensity: 16 | 64 | 100;
  selectedSample: Pick<MicrographSample, "material" | "category">;
}

export interface SemAnalysisOutput {
  results: AutomatedCVResults;
  grey: Uint8Array;
  phaseMap: Uint8Array;
  effectiveHeight: number;
}

export function analyzeSemImage(params: SemAnalysisParams): SemAnalysisOutput {
  const {
    data,
    width,
    height,
    scaleMicronsPerPixel,
    poreThreshold,
    matrixLowerThreshold,
    matrixUpperThreshold,
    precipitateUpperThreshold,
    grainSensitivity,
    visiblePhases,
    pointGridDensity,
    selectedSample,
  } = params;
  // 1. Convert to Greyscale Luminance Matrix & Histogram
  const totalPixels = width * height;
  const grey = new Uint8Array(totalPixels);
  let sumLuminance = 0;
  const hist = new Array(256).fill(0);

  // Exclude bottom banner area (typically bottom 10-12% of SEM micrograph)
  const bannerHeight = Math.round(height * 0.1);
  const effectiveHeight = height - bannerHeight;
  const effectivePixels = width * effectiveHeight;

  for (let i = 0; i < totalPixels; i++) {
    const r = data[i * 4];
    const g = data[i * 4 + 1];
    const b = data[i * 4 + 2];
    const lum = rgbToLuminance(r, g, b);
    grey[i] = lum;
    hist[lum]++;
    if (Math.floor(i / width) < effectiveHeight) {
      sumLuminance += lum;
    }
  }

  const meanLuminance = sumLuminance / effectivePixels;
  const umPerPx = scaleMicronsPerPixel;
  const totalAreaUm2 = effectivePixels * umPerPx * umPerPx;

  // 2. Multi-Phase Segmentation (ASTM E562 & Delesse Stereology: V_v = A_a)
  let poreCount = 0;
  let matrixCount = 0;
  let precipitateCount = 0;
  let carbideCount = 0;

  // Phase identification masks
  const phaseMap = new Uint8Array(totalPixels); // 0: pore, 1: matrix, 2: precipitate, 3: carbide

  for (let y = 0; y < effectiveHeight; y++) {
    for (let x = 0; x < width; x++) {
      const idx = y * width + x;
      const lum = grey[idx];

      if (lum <= poreThreshold) {
        phaseMap[idx] = 0;
        poreCount++;
      } else if (lum <= matrixUpperThreshold) {
        phaseMap[idx] = 1;
        matrixCount++;
      } else if (lum <= precipitateUpperThreshold) {
        phaseMap[idx] = 2;
        precipitateCount++;
      } else {
        phaseMap[idx] = 3;
        carbideCount++;
      }
    }
  }

  const porePct = Number(((poreCount / effectivePixels) * 100).toFixed(2));
  const matrixPct = Number(((matrixCount / effectivePixels) * 100).toFixed(2));
  const precipitatePct = Number(((precipitateCount / effectivePixels) * 100).toFixed(2));
  const carbidePct = Number(((carbideCount / effectivePixels) * 100).toFixed(2));

  // 3. Morphological Blob Extraction for Precipitates & Pores (Particle Sizing)
  const visited = new Uint8Array(totalPixels);
  const defects: SEMDefectBlob[] = [];
  let totalPorePixels = 0;
  let precipitateParticlesCount = 0;
  let precipitateAreaSumUm2 = 0;
  let carbideParticlesCount = 0;
  let carbideAreaSumUm2 = 0;

  // Connected component labeling (BFS)
  for (let y = 4; y < effectiveHeight - 4; y += 2) {
    for (let x = 4; x < width - 4; x += 2) {
      const idx = y * width + x;
      if (visited[idx] === 0) {
        const pType = phaseMap[idx];
        if (pType === 0) {
          // Dark Pore / Void
          let blobArea = 0;
          let minX = x, maxX = x, minY = y, maxY = y;
          let perimeter = 0;
          const queue: number[] = [idx];
          visited[idx] = 1;

          while (queue.length > 0) {
            const curr = queue.pop()!;
            blobArea++;
            const cy = Math.floor(curr / width);
            const cx = curr % width;

            if (cx < minX) minX = cx;
            if (cx > maxX) maxX = cx;
            if (cy < minY) minY = cy;
            if (cy > maxY) maxY = cy;

            const neighbors = [curr - 1, curr + 1, curr - width, curr + width];
            let isEdge = false;
            for (const n of neighbors) {
              if (n >= 0 && n < width * effectiveHeight) {
                if (phaseMap[n] === 0) {
                  if (visited[n] === 0) {
                    visited[n] = 1;
                    queue.push(n);
                  }
                } else {
                  isEdge = true;
                }
              }
            }
            if (isEdge) perimeter++;
          }

          if (blobArea >= 5 && blobArea < totalPixels * 0.15) {
            totalPorePixels += blobArea;
            const w = maxX - minX + 1;
            const h = maxY - minY + 1;
            const areaUm2 = blobArea * umPerPx * umPerPx;
            const eqDiaUm = 2 * Math.sqrt(areaUm2 / Math.PI);
            const perim = Math.max(perimeter, 4);
            const circularity = Math.min(1.0, (4 * Math.PI * blobArea) / (perim * perim));
            const aspectRatio = Math.max(w, h) / Math.max(1, Math.min(w, h));

            let defectType: "Gas Pore (Spherical)" | "Lack of Fusion (Irregular)" | "Keyhole / Shrinkage" =
              "Keyhole / Shrinkage";
            if (circularity >= 0.65 && aspectRatio < 1.6) {
              defectType = "Gas Pore (Spherical)";
            } else if (circularity < 0.45 || aspectRatio > 2.2) {
              defectType = "Lack of Fusion (Irregular)";
            }

            defects.push({
              id: defects.length + 1,
              x: minX,
              y: minY,
              width: w,
              height: h,
              areaPx: blobArea,
              areaUm2: Number(areaUm2.toFixed(3)),
              equivalentDiameterUm: Number(eqDiaUm.toFixed(2)),
              perimeterPx: perim,
              circularity: Number(circularity.toFixed(2)),
              aspectRatio: Number(aspectRatio.toFixed(2)),
              defectType,
            });
          }
        } else if (pType === 2) {
          // Precipitate Particle
          precipitateParticlesCount++;
          precipitateAreaSumUm2 += umPerPx * umPerPx * 4;
        } else if (pType === 3) {
          // Carbide / Intermetallic Particle
          carbideParticlesCount++;
          carbideAreaSumUm2 += umPerPx * umPerPx * 4;
        }
      }
    }
  }

  // Porosity calculations
  const totalPorosityPct = Number(((poreCount / effectivePixels) * 100).toFixed(3));
  const meanPoreDiameterUm =
    defects.length > 0
      ? Number((defects.reduce((acc, d) => acc + d.equivalentDiameterUm, 0) / defects.length).toFixed(2))
      : 0.8;
  const maxPoreDiameterUm =
    defects.length > 0 ? Math.max(...defects.map((d) => d.equivalentDiameterUm)) : 1.5;

  const gasCount = defects.filter((d) => d.defectType.includes("Gas")).length;
  const lofCount = defects.filter((d) => d.defectType.includes("Lack")).length;
  const keyCount = defects.filter((d) => d.defectType.includes("Keyhole")).length;
  const denom = Math.max(1, defects.length);

  const sizeRanges = [
    { range: "< 1 µm", count: defects.filter((d) => d.equivalentDiameterUm < 1.0).length },
    { range: "1-3 µm", count: defects.filter((d) => d.equivalentDiameterUm >= 1.0 && d.equivalentDiameterUm < 3.0).length },
    { range: "3-5 µm", count: defects.filter((d) => d.equivalentDiameterUm >= 3.0 && d.equivalentDiameterUm < 5.0).length },
    { range: "5-10 µm", count: defects.filter((d) => d.equivalentDiameterUm >= 5.0 && d.equivalentDiameterUm < 10.0).length },
    { range: "> 10 µm", count: defects.filter((d) => d.equivalentDiameterUm >= 10.0).length },
  ];

  // 4. ASTM E112 Heyn Line-Intercept Analysis
  const testLinesCount = 8;
  let totalInterceptions = 0;
  let totalLineLengthUm = 0;

  for (let li = 1; li <= testLinesCount; li++) {
    const testY = Math.round((li * effectiveHeight) / (testLinesCount + 1));
    let prevVal = grey[testY * width];
    let intersectionsInLine = 0;

    for (let tx = 2; tx < width - 2; tx += 2) {
      const currVal = grey[testY * width + tx];
      const diff = Math.abs(currVal - prevVal);
      if (diff > (100 - grainSensitivity) * 0.4) {
        intersectionsInLine++;
        prevVal = currVal;
      }
    }
    totalInterceptions += Math.max(4, intersectionsInLine);
    totalLineLengthUm += width * umPerPx;
  }

  const meanInterceptLengthUm =
    totalInterceptions > 0
      ? Number((totalLineLengthUm / totalInterceptions).toFixed(2))
      : 5.2;

  // ASTM Grain Size Number G = -6.64385 * log10(l_bar in mm) - 3.288
  const astmG = astmGrainSizeNumberFromIntercept(meanInterceptLengthUm);

  // Subgrain / Dendrite Cellular Spacing (SDAS)
  const subgrainCellSpacingUm = Number((meanInterceptLengthUm * 0.42).toFixed(2));
  const inferredCoolingRateKs = Math.round(
    Math.pow(Math.max(0.2, subgrainCellSpacingUm) / 50, -3.0) * 1000
  );

  // 5. Stereological Particle Spacing (Underwood Free Path: λ = (1 - V_v) / N_L)
  const precipVolFrac = precipitatePct / 100;
  const precipIntersections = Math.max(1, Math.round(totalInterceptions * precipVolFrac));
  const meanPrecipFreePathUm = Number(
    (((1 - precipVolFrac) * totalLineLengthUm) / precipIntersections).toFixed(2)
  );

  const meanCarbideFreePathUm = Number(
    (((1 - carbidePct / 100) * totalLineLengthUm) / Math.max(1, Math.round(totalInterceptions * (carbidePct / 100)))).toFixed(2)
  );

  // Mean precipitate particle diameter
  const meanPrecipDiamUm = Number((Math.sqrt((precipitatePct * 0.01 * totalAreaUm2) / Math.max(10, precipitateParticlesCount * 5)) * 1.5).toFixed(2));
  const meanCarbideDiamUm = Number((Math.sqrt((carbidePct * 0.01 * totalAreaUm2) / Math.max(5, carbideParticlesCount * 3)) * 1.8).toFixed(2));

  // 6. Systematic Point Count Grid Simulation (ASTM E562)
  const gridN = Math.round(Math.sqrt(pointGridDensity));
  let ptMatrix = 0, ptPrecip = 0, ptCarbide = 0, ptPore = 0;
  for (let gy = 1; gy <= gridN; gy++) {
    for (let gx = 1; gx <= gridN; gx++) {
      const px = Math.round((gx * width) / (gridN + 1));
      const py = Math.round((gy * effectiveHeight) / (gridN + 1));
      const phase = phaseMap[py * width + px];
      if (phase === 0) ptPore++;
      else if (phase === 1) ptMatrix++;
      else if (phase === 2) ptPrecip++;
      else if (phase === 3) ptCarbide++;
    }
  }
  const totalGridPts = gridN * gridN;
  const relAccuracyPct = Number(((1.96 * Math.sqrt((precipVolFrac * (1 - precipVolFrac)) / totalGridPts) / Math.max(0.01, precipVolFrac)) * 100).toFixed(1));
  const confInterval95Pct = Number((1.96 * Math.sqrt((precipVolFrac * (1 - precipVolFrac)) / totalGridPts) * 100).toFixed(2));

  // Phase Composition Items list
  const phaseComposition: PhaseCompositionItem[] = [
    {
      id: "matrix",
      name: "Primary Matrix Phase",
      formula: selectedSample.material.includes("Inconel")
        ? "γ (fcc Ni-Cr-Fe)"
        : selectedSample.material.includes("Ti")
        ? "α / Prior-β"
        : "Austenite / Ferrite",
      color: "#38bdf8",
      minLum: matrixLowerThreshold,
      maxLum: matrixUpperThreshold,
      areaPct: matrixPct,
      volumePct: matrixPct,
      areaUm2: Number((totalAreaUm2 * (matrixPct / 100)).toFixed(1)),
      meanDiameterUm: meanInterceptLengthUm,
      interParticleSpacingUm: subgrainCellSpacingUm,
      particleCount: totalInterceptions,
      particleDensityPer1000Um2: Number(((totalInterceptions / totalAreaUm2) * 1000).toFixed(1)),
      contrastCharacteristic: "Mid-Gray Continuous Matrix",
      visible: visiblePhases.matrix ?? true,
    },
    {
      id: "precipitates",
      name: "Secondary Hardening Precipitates",
      formula: selectedSample.material.includes("Inconel")
        ? "γ' / γ'' (Ni3Al / Ni3Nb)"
        : selectedSample.material.includes("Ti")
        ? "Acicular α' Martensite"
        : "Carbides / Precipitates",
      color: "#f59e0b",
      minLum: matrixUpperThreshold + 1,
      maxLum: precipitateUpperThreshold,
      areaPct: precipitatePct,
      volumePct: precipitatePct,
      areaUm2: Number((totalAreaUm2 * (precipitatePct / 100)).toFixed(1)),
      meanDiameterUm: Math.max(0.15, meanPrecipDiamUm),
      interParticleSpacingUm: Math.max(0.2, meanPrecipFreePathUm),
      particleCount: precipitateParticlesCount,
      particleDensityPer1000Um2: Number(((precipitateParticlesCount / totalAreaUm2) * 1000).toFixed(1)),
      contrastCharacteristic: "Dispersed Fine Phases",
      visible: visiblePhases.precipitates ?? true,
    },
    {
      id: "carbides",
      name: "Intermetallics & Carbides",
      formula: selectedSample.material.includes("Inconel")
        ? "Laves / MC Carbides"
        : "Intermetallic High-Z Particles",
      color: "#a855f7",
      minLum: precipitateUpperThreshold + 1,
      maxLum: 255,
      areaPct: carbidePct,
      volumePct: carbidePct,
      areaUm2: Number((totalAreaUm2 * (carbidePct / 100)).toFixed(1)),
      meanDiameterUm: Math.max(0.3, meanCarbideDiamUm),
      interParticleSpacingUm: Math.max(0.8, meanCarbideFreePathUm),
      particleCount: carbideParticlesCount,
      particleDensityPer1000Um2: Number(((carbideParticlesCount / totalAreaUm2) * 1000).toFixed(1)),
      contrastCharacteristic: "High Z-Contrast Bright Phases",
      visible: visiblePhases.carbides ?? true,
    },
    {
      id: "pores",
      name: "Pores & Micro-Voids",
      formula: "ASTM E2109 Voids",
      color: "#ef4444",
      minLum: 0,
      maxLum: poreThreshold,
      areaPct: porePct,
      volumePct: porePct,
      areaUm2: Number((totalAreaUm2 * (porePct / 100)).toFixed(2)),
      meanDiameterUm: meanPoreDiameterUm,
      interParticleSpacingUm: Number((Math.sqrt(totalAreaUm2 / Math.max(1, defects.length))).toFixed(1)),
      particleCount: defects.length,
      particleDensityPer1000Um2: Number(((defects.length / totalAreaUm2) * 1000).toFixed(2)),
      contrastCharacteristic: "Dark Zero-Luminance Voids",
      visible: visiblePhases.pores ?? true,
    },
  ];

  const phaseFractions = [
    { phase: "Primary Matrix", fractionPct: matrixPct, color: "#38bdf8" },
    { phase: "Precipitates", fractionPct: precipitatePct, color: "#f59e0b" },
    { phase: "Carbides / Intermetallics", fractionPct: carbidePct, color: "#a855f7" },
    { phase: "Micro-Voids", fractionPct: porePct, color: "#ef4444" },
  ];

  // Mechanical Property Inferences (Hall-Petch)
  const baseYield = selectedSample.category === "Additive Manufacturing (LPBF)" ? 950 : 750;
  const hpIncrement = Math.round(180 / Math.sqrt(Math.max(0.1, meanInterceptLengthUm)));
  const estimatedYieldStrengthMpa = baseYield + hpIncrement;
  const estimatedTensileStrengthMpa = Math.round(estimatedYieldStrengthMpa * 1.25);
  // No HV from the inferred strength. The old HV = UTS/3.1 had no source; the verified steel regression (Pavlina &
  // Van Tyne 2008) needs a known non-austenitic hypoeutectoid steel, and the sample record carries no composition
  // while the Hall-Petch base yield above is not alloy-specific.
  const estimatedHardnessHv: number | null = null;
  const estimatedHardnessNote = SEM_HARDNESS_UNAVAILABLE_NOTE;

  const results: AutomatedCVResults = {
    totalPorosityPct,
    defectCount: defects.length,
    meanPoreDiameterUm,
    maxPoreDiameterUm: Number(maxPoreDiameterUm.toFixed(2)),
    poreClassification: {
      gasPoresPct: Number(((gasCount / denom) * 100).toFixed(1)),
      lackOfFusionPct: Number(((lofCount / denom) * 100).toFixed(1)),
      keyholePct: Number(((keyCount / denom) * 100).toFixed(1)),
    },
    poreSizeDistribution: sizeRanges,
    phaseFractions,
    phaseComposition,
    astmGrainSizeNumber: astmG,
    meanInterceptLengthUm,
    interceptCount: totalInterceptions,
    subgrainCellSpacingUm,
    inferredCoolingRateKs,
    estimatedYieldStrengthMpa,
    estimatedTensileStrengthMpa,
    estimatedHardnessHv,
    estimatedHardnessNote,
    defects,
    scaleMicronsPerPixel,
    totalAreaUm2: Number(totalAreaUm2.toFixed(1)),
    luminanceHistogram: hist,
    pointCountStats: {
      gridSize: totalGridPts,
      matrixPoints: ptMatrix,
      precipitatePoints: ptPrecip,
      carbidePoints: ptCarbide,
      porePoints: ptPore,
      relativeAccuracyPct: relAccuracyPct,
      confidenceInterval95Pct: confInterval95Pct,
    },
  };
  return { results, grey, phaseMap, effectiveHeight };
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
