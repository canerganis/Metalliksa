import {
  TafelDataset,
  TafelFitComplete,
  TafelFitCompleteKeys,
  TafelFitResult,
  TafelRawPoint,
  ReferenceElectrodeType,
} from "../types/tafel";
import { MILS_PER_MM, fmtTafelNumber, fmtTafelQuantity, tafelUnavailableReason } from "./tafelDisplay";
import { FARADAY_CONSTANT } from "./physicalConstants";

export const REFERENCE_ELECTRODES: Record<ReferenceElectrodeType, { name: string; offsetVsSHE: number }> = {
  SHE: { name: "Standard Hydrogen Electrode (SHE)", offsetVsSHE: 0.000 },
  SCE: { name: "Saturated Calomel Electrode (SCE)", offsetVsSHE: 0.241 },
  "Ag/AgCl": { name: "Silver/Silver Chloride (Ag/AgCl sat. KCl)", offsetVsSHE: 0.197 },
  MSE: { name: "Mercury-Mercurous Sulfate (MSE sat. K2SO4)", offsetVsSHE: 0.640 },
  Custom: { name: "Custom Reference Electrode", offsetVsSHE: 0.000 },
};

export interface AlloyMaterialPreset {
  id: string;
  name: string;
  density: number; // g/cm³
  equivalentWeight: number; // g/eq (M / n)
  valency: number;
  atomicMass: number;
}

// density and equivalentWeight mirror python/alloy_registry.py (domain "corrosion"; EW is
// computed there with the ASTM G102 practice (elements >= 1 % by mass, renormalised) from
// composition, in-house valences and CIAAW 2021 atomic weights,
// Phase 6a step b). python/test_phase6a_migration.py checks every row against the registry.
// duplex2205 has NO registry record: its numbers are unsourced UI defaults that reach the
// Python solver only as caller-supplied metadata (an unknown alloyId without them is a 422).
// valency and atomicMass are display-only and not read by any calculation.
export const COMMON_ALLOYS: AlloyMaterialPreset[] = [
  { id: "ss316l", name: "AISI 316L Stainless Steel", density: 7.98, equivalentWeight: 24.8205, valency: 2.16, atomicMass: 55.47 },
  { id: "ss304", name: "AISI 304 Stainless Steel", density: 7.93, equivalentWeight: 25.1088, valency: 2.21, atomicMass: 55.51 },
  { id: "steel1018", name: "AISI 1018 Carbon Steel", density: 7.87, equivalentWeight: 27.9225, valency: 2.00, atomicMass: 55.85 },
  { id: "ti64", name: "Ti-6Al-4V Grade 5 Titanium", density: 4.43, equivalentWeight: 11.8715, valency: 4.00, atomicMass: 47.88 },
  { id: "al7075", name: "Al 7075-T6 Aerospace Aluminum", density: 2.81, equivalentWeight: 9.5583, valency: 3.00, atomicMass: 26.98 },
  { id: "al6061", name: "Al 6061-T6 Structural Aluminum", density: 2.70, equivalentWeight: 9.0179, valency: 3.00, atomicMass: 26.98 },
  { id: "cu_c110", name: "C11000 Electrolytic Tough Pitch Copper", density: 8.94, equivalentWeight: 31.773, valency: 2.00, atomicMass: 63.55 },
  { id: "inconel718", name: "Inconel 718 Superalloy", density: 8.19, equivalentWeight: 25.0598, valency: 2.30, atomicMass: 58.23 },
  { id: "az31b", name: "AZ31B Magnesium Alloy", density: 1.77, equivalentWeight: 12.101, valency: 2.00, atomicMass: 24.31 },
  { id: "duplex2205", name: "2205 Duplex Stainless Steel", density: 7.80, equivalentWeight: 25.40, valency: 2.18, atomicMass: 55.37 },
];

/**
 * Parses user-uploaded potentiodynamic polarization file into TafelDataset.
 * Supports BioLogic (.mpt), Gamry (.DTA), Autolab (.txt/.csv), PAR VersaStudio, and generic CSV/TSV/TXT formats.
 */
export function parseTafelFile(
  rawText: string,
  filename: string = "uploaded_polarization.csv",
  customAreaCm2: number = 1.0,
  defaultMaterial?: AlloyMaterialPreset
): TafelDataset {
  if (!rawText || !rawText.trim()) {
    throw new Error("File content is empty.");
  }

  const lines = rawText.split(/\r?\n/);
  let instrument: TafelDataset["sourceInstrument"] = "csv";
  let refElectrode: ReferenceElectrodeType = "SCE";
  let scanRateMv_s: number | undefined;

  // 1. Detect instrument signature from headers
  const headerSample = lines.slice(0, 80).join("\n").toLowerCase();
  if (headerSample.includes("ec-lab") || headerSample.includes("nb header lines") || headerSample.includes("ewe/v")) {
    instrument = "biologic";
  } else if (headerSample.includes("gamry") || headerSample.includes("dta") || headerSample.includes("curve	table")) {
    instrument = "gamry";
  } else if (headerSample.includes("autolab") || headerSample.includes("nova")) {
    instrument = "autolab";
  } else if (headerSample.includes("par") || headerSample.includes("versastudio")) {
    instrument = "par";
  }

  // Look for scan rate or area in headers
  for (let i = 0; i < Math.min(lines.length, 100); i++) {
    const line = lines[i].toLowerCase();
    if (line.includes("scan rate") || line.includes("d(e)/dt")) {
      const match = line.match(/([\d.,]+)\s*(mv\/s|v\/s)/);
      if (match) {
        let val = parseFloat(match[1].replace(",", "."));
        if (match[2] === "v/s") val *= 1000;
        if (!isNaN(val)) scanRateMv_s = val;
      }
    }
    if (line.includes("ag/agcl")) refElectrode = "Ag/AgCl";
    else if (line.includes("sce") || line.includes("calomel")) refElectrode = "SCE";
    else if (line.includes("she") || line.includes("nhe")) refElectrode = "SHE";
  }

  // 2. Identify data header line and column indexes
  let headerRowIndex = -1;
  let potentialColIdx = -1;
  let currentColIdx = -1;
  let isCurrentDensityDeclared = false;
  let detectedCurrentUnit: "A" | "mA" | "uA" | "nA" = "A";

  // Regex patterns to identify potential and current columns
  const potentialPatterns = [
    /\b(ewe|potential|voltage|e|e\(v\)|ewe\/v|potential\/v|v|e_vs_ref)\b/i,
    /poten/i,
  ];
  const currentPatterns = [
    /\b(<i\>|current|im|i|i\(a\)|i\/a|curr|current\/a|i_a)\b/i,
    /\b(i\/ma|current\/ma|i\(ma\)|i_ma)\b/i,
    /\b(i\/ua|current\/ua|i\(ua\)|i_ua|i\/µa)\b/i,
    /\b(i\/na|current\/na|i\(na\)|i_na)\b/i,
    /\b(log\s*\(?i\)?|log\(i\)|log_i)\b/i,
  ];

  for (let i = 0; i < Math.min(lines.length, 250); i++) {
    const line = lines[i].trim();
    if (!line || line.startsWith("#") || line.startsWith("//")) continue;

    const tokens = splitLineToTokens(line);
    if (tokens.length < 2) continue;

    let potIdx = -1;
    let curIdx = -1;

    for (let c = 0; c < tokens.length; c++) {
      const colName = tokens[c].toLowerCase();
      // Test potential
      if (potIdx === -1 && potentialPatterns.some((p) => p.test(colName))) {
        potIdx = c;
      }
      // Test current
      if (curIdx === -1) {
        if (colName.includes("µa") || colName.includes("ua")) {
          detectedCurrentUnit = "uA";
          curIdx = c;
        } else if (colName.includes("ma")) {
          detectedCurrentUnit = "mA";
          curIdx = c;
        } else if (colName.includes("na")) {
          detectedCurrentUnit = "nA";
          curIdx = c;
        } else if (currentPatterns.some((p) => p.test(colName))) {
          curIdx = c;
        }
        if (colName.includes("/cm2") || colName.includes("/cm²") || colName.includes("density")) {
          isCurrentDensityDeclared = true;
        }
      }
    }

    if (potIdx !== -1 && curIdx !== -1) {
      headerRowIndex = i;
      potentialColIdx = potIdx;
      currentColIdx = curIdx;
      break;
    }
  }

  // Fallback: If no header matches, test row with numeric data
  const dataStartLine = headerRowIndex !== -1 ? headerRowIndex + 1 : 0;
  const rawDataRows: { pot: number; cur: number }[] = [];

  for (let i = dataStartLine; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line || line.startsWith("#") || line.startsWith("//") || line.startsWith(";")) continue;

    const tokens = splitLineToTokens(line);
    if (tokens.length < 2) continue;

    let potVal: number | null = null;
    let curVal: number | null = null;

    if (potentialColIdx !== -1 && currentColIdx !== -1) {
      potVal = parseNumericToken(tokens[potentialColIdx]);
      curVal = parseNumericToken(tokens[currentColIdx]);
    } else {
      // Try column 0 & 1 or 1 & 2
      const num0 = parseNumericToken(tokens[0]);
      const num1 = parseNumericToken(tokens[1]);
      if (num0 !== null && num1 !== null) {
        // If one is clearly between -3.0 and +3.0 V, and the other is either very small or scientific
        if (Math.abs(num0) <= 5.0 && (Math.abs(num1) > 5.0 || Math.abs(num1) < 1.0)) {
          potVal = num0;
          curVal = num1;
        } else if (Math.abs(num1) <= 5.0 && (Math.abs(num0) > 5.0 || Math.abs(num0) < 1.0)) {
          potVal = num1;
          curVal = num0;
        } else {
          potVal = num0;
          curVal = num1;
        }
      }
    }

    if (potVal !== null && curVal !== null && !isNaN(potVal) && !isNaN(curVal)) {
      rawDataRows.push({ pot: potVal, cur: curVal });
    }
  }

  if (rawDataRows.length < 10) {
    throw new Error(
      `Could not parse sufficient polarization data (found only ${rawDataRows.length} points). Please ensure the file contains Potential (V) and Current (A, mA, or µA) columns.`
    );
  }

  // 3. Determine current magnitude and unit if not explicit
  // Analyze current values:
  const absValues = rawDataRows.map((r) => Math.abs(r.cur)).filter((v) => v > 0);
  const medianCurrent = absValues.sort((a, b) => a - b)[Math.floor(absValues.length / 2)] || 1e-6;

  let unitMultiplier = 1e6; // Default assuming Amperes -> uA (1 A = 10^6 uA)
  if (detectedCurrentUnit === "uA") {
    unitMultiplier = 1.0;
  } else if (detectedCurrentUnit === "mA") {
    unitMultiplier = 1000.0;
  } else if (detectedCurrentUnit === "nA") {
    unitMultiplier = 0.001;
  } else {
    // Infer from values:
    if (medianCurrent > 10.0) {
      // Likely already in uA
      detectedCurrentUnit = "uA";
      unitMultiplier = 1.0;
    } else if (medianCurrent > 0.05) {
      // Likely in mA
      detectedCurrentUnit = "mA";
      unitMultiplier = 1000.0;
    } else {
      // Likely in A
      detectedCurrentUnit = "A";
      unitMultiplier = 1e6;
    }
  }

  const effectiveArea = customAreaCm2 > 0 ? customAreaCm2 : 1.0;
  const areaFactor = isCurrentDensityDeclared ? 1.0 : effectiveArea;
  const refOffset = REFERENCE_ELECTRODES[refElectrode]?.offsetVsSHE ?? 0.241;

  // Build points array
  const points: TafelRawPoint[] = rawDataRows.map((r, idx) => {
    const rawVal = r.cur;
    const absVal = Math.abs(rawVal);
    // Convert to uA
    const current_uA = absVal * unitMultiplier;
    // Current density in uA/cm2
    const currentDensity_uA_cm2 = current_uA / areaFactor;
    // Prevent log(0)
    const safeCurrentDensity = Math.max(1e-10, currentDensity_uA_cm2);
    const logCurrentDensity = Math.log10(safeCurrentDensity);

    return {
      index: idx,
      potential: r.pot,
      potentialSHE: r.pot + refOffset,
      currentRaw: rawVal,
      currentUnit: detectedCurrentUnit,
      currentDensity_uA_cm2: safeCurrentDensity,
      logCurrentDensity,
      signedCurrentDensity_uA_cm2: rawVal >= 0 ? safeCurrentDensity : -safeCurrentDensity,
    };
  });

  const material = defaultMaterial || COMMON_ALLOYS[0];

  return {
    id: `tafel_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    name: filename.replace(/\.[^/.]+$/, "").replace(/_/g, " "),
    sourceFilename: filename,
    sourceInstrument: instrument,
    points,
    metadata: {
      electrodeAreaCm2: effectiveArea,
      referenceElectrode: refElectrode,
      refOffsetVsSHE: refOffset,
      alloyName: material.name,
      density_g_cm3: material.density,
      equivalentWeight: material.equivalentWeight,
      electrolyte: "3.5 wt% NaCl (Simulated Marine)",
      temperatureC: 25,
      scanRateMv_s: scanRateMv_s || 1.0,
      notes: `Ingested ${points.length} potentiodynamic polarization points. Detected unit: ${detectedCurrentUnit}.`,
    },
  };
}

/**
 * Splits line by comma, tab, semicolon, or multi-spaces
 */
function splitLineToTokens(line: string): string[] {
  // If line contains tabs
  if (line.includes("\t")) {
    return line.split("\t").map((t) => t.trim());
  }
  // If line contains semicolons
  if (line.includes(";")) {
    return line.split(";").map((t) => t.trim());
  }
  // If line contains commas
  if (line.includes(",")) {
    // Whitespace-separated numeric fields may use decimal commas (e.g. "-0,3 1,2e-6").
    // Require complete numbers: "-0.3, 1e-6" must remain comma-delimited CSV.
    const whitespaceParts = line.split(/\s+/);
    const numericField = /^[+-]?(?:\d+(?:\.\d*|,\d+)?|[.,]\d+)(?:e[+-]?\d+)?$/i;
    if (whitespaceParts.length >= 2 && whitespaceParts.every(t => numericField.test(t))) {
      return whitespaceParts;
    }
    return line.split(",").map((t) => t.trim());
  }
  // Split on multiple whitespace
  return line.split(/\s+/).map((t) => t.trim());
}

/**
 * Parses numeric token supporting European decimal commas (e.g., -0,245)
 */
function parseNumericToken(token?: string): number | null {
  if (!token) return null;
  const clean = token.replace(/['"()]/g, "").trim();
  // Replace comma with dot if there is no other dot
  let normalized = clean;
  if (normalized.includes(",") && !normalized.includes(".")) {
    normalized = normalized.replace(",", ".");
  }
  const val = parseFloat(normalized);
  return isNaN(val) ? null : val;
}

/**
 * Linear least-squares regression: y = m * x + b
 */
export function linearRegression(xArr: number[], yArr: number[]): { m: number; b: number; r2: number } {
  const n = xArr.length;
  if (n < 2) {
    return { m: 0, b: yArr[0] || 0, r2: 0 };
  }

  let sumX = 0;
  let sumY = 0;
  let sumXY = 0;
  let sumXX = 0;
  let sumYY = 0;

  for (let i = 0; i < n; i++) {
    const x = xArr[i];
    const y = yArr[i];
    sumX += x;
    sumY += y;
    sumXY += x * y;
    sumXX += x * x;
    sumYY += y * y;
  }

  const denominator = n * sumXX - sumX * sumX;
  if (Math.abs(denominator) < 1e-15) {
    return { m: 0, b: sumY / n, r2: 0 };
  }

  const m = (n * sumXY - sumX * sumY) / denominator;
  const b = (sumY - m * sumX) / n;

  // Compute R2
  const meanY = sumY / n;
  let ssTot = 0;
  let ssRes = 0;
  for (let i = 0; i < n; i++) {
    const y = yArr[i];
    const yPred = m * xArr[i] + b;
    ssTot += (y - meanY) * (y - meanY);
    ssRes += (y - yPred) * (y - yPred);
  }

  const r2 = ssTot > 0 ? Math.max(0, 1 - ssRes / ssTot) : 1;
  return { m, b, r2 };
}

/** Fewest data points a Tafel branch window must hold for a fit (same rule as python/tafel_corrosion_rate_solver.py). */
export const MIN_TAFEL_BRANCH_POINTS = 3;

/** Why a Tafel branch cannot be fitted, or null when it can. Mirrors the Python engine's reasons. */
export function tafelBranchUnavailableReason(
  branch: "Anodic" | "Cathodic",
  window: [number, number],
  pointCount: number,
  slope: number
): string | null {
  const lo = Math.min(window[0], window[1]);
  const hi = Math.max(window[0], window[1]);
  if (pointCount < MIN_TAFEL_BRANCH_POINTS) {
    return (
      `${branch} branch unavailable: ${pointCount} data point(s) in the fit window ` +
      `[${lo.toFixed(3)}, ${hi.toFixed(3)}] V (at least ${MIN_TAFEL_BRANCH_POINTS} are required)`
    );
  }
  if (branch === "Anodic" && slope <= 0) {
    return (
      `Anodic branch unavailable: the fitted log i vs E slope is ${slope.toFixed(3)} (not > 0), ` +
      `so the data in the window do not show anodic Tafel behaviour`
    );
  }
  if (branch === "Cathodic" && slope >= 0) {
    return (
      `Cathodic branch unavailable: the fitted log i vs E slope is ${slope.toFixed(3)} (not < 0), ` +
      `so the data in the window do not show cathodic Tafel behaviour`
    );
  }
  return null;
}

/** The fit values a complete Tafel fit carries (see TafelFitComplete). */
export const TAFEL_COMPLETE_KEYS: readonly TafelFitCompleteKeys[] = [
  "eCorr", "eCorrSHE", "iCorr_uA_cm2", "logIcorr", "totalCurrentIcorr_uA",
  "betaA_V_dec", "betaA_mV_dec", "betaC_V_dec", "betaC_mV_dec", "sternGearyB_V", "rp_ohm_cm2",
  "corrosionRateMmYr", "corrosionRateMpy", "massLoss_g_m2_day",
  "cathodicR2", "anodicR2", "cathodicSlope_m", "cathodicIntercept_b", "anodicSlope_m", "anodicIntercept_b",
  "severity", "astmClassification",
];

/** True when every value of a complete fit is present (both branches fitted, i_corr and the substrate known). */
export function isTafelFitComplete(fit: TafelFitResult | null | undefined): fit is TafelFitComplete {
  if (!fit || fit.fitStatus === "unavailable") return false;
  return TAFEL_COMPLETE_KEYS.every((k) => fit[k] !== null && fit[k] !== undefined);
}

/** Thrown by autoFitTafel when the fit is unavailable; `fit` carries the partial result and the reasons. */
export class TafelFitUnavailableError extends Error {
  readonly fit: TafelFitResult;
  constructor(fit: TafelFitResult) {
    super(fit.unavailableReason || "Tafel fit unavailable");
    this.name = "TafelFitUnavailableError";
    this.fit = fit;
  }
}

/**
 * Automatic Tafel Extrapolation & Kinetics Solver (ASTM G102 & G59).
 * Detects the minimum current valley ($E_{corr}^{valley}$), fits linear Tafel lines
 * on the cathodic and anodic branches, solves for their intersection $(E_{corr}, I_{corr})$,
 * and calculates all Stern-Geary and Faraday corrosion rates.
 *
 * A branch whose window holds fewer than 3 points, or whose slope has the wrong sign, is
 * unavailable: its slope, beta and R2 are null (never an assumed 100 mV/dec with R2 0.85), and
 * without both branches there is no Evans intersection, so Ecorr/icorr, Stern-Geary, Rp, the
 * Faraday rate and the severity are null too (fitStatus "unavailable" with the reasons), unless
 * the caller supplies manual Ecorr / icorr overrides. A missing substrate (equivalent weight or
 * density <= 0) makes the Faraday rate unavailable instead of substituting the 316L preset.
 * Same rules as python/tafel_corrosion_rate_solver.py fit_tafel_curve.
 */
export function tryAutoFitTafel(
  dataset: TafelDataset,
  customCathodicRange?: [number, number],
  customAnodicRange?: [number, number],
  manualEcorrOverride?: number,
  manualIcorrOverride?: number
): TafelFitResult {
  const points = dataset.points;
  if (!points || points.length < 5) {
    throw new Error("Dataset contains insufficient points for Tafel fitting.");
  }

  // 1. Find Raw Minimum Current Point (The Apex / Valley of the Evans Diagram)
  let minCurrentDensity = Infinity;
  let minIdx = 0;

  for (let i = 0; i < points.length; i++) {
    if (points[i].currentDensity_uA_cm2 < minCurrentDensity) {
      minCurrentDensity = points[i].currentDensity_uA_cm2;
      minIdx = i;
    }
  }

  const rawEcorr = points[minIdx].potential;
  const rawIcorr = points[minIdx].currentDensity_uA_cm2;

  // Potential range of entire scan
  const allPotentials = points.map((p) => p.potential);
  const minScanE = Math.min(...allPotentials);
  const maxScanE = Math.max(...allPotentials);

  // 2. Determine Anodic & Cathodic Fit Windows
  // By standard ASTM practice:
  // Cathodic zone is between -250 mV and -50 mV relative to Ecorr
  // Anodic zone is between +50 mV and +250 mV relative to Ecorr
  let cathMinE = rawEcorr - 0.25;
  let cathMaxE = rawEcorr - 0.05;
  let anodMinE = rawEcorr + 0.05;
  let anodMaxE = rawEcorr + 0.25;

  if (customCathodicRange) {
    cathMinE = customCathodicRange[0];
    cathMaxE = customCathodicRange[1];
  } else {
    cathMinE = Math.max(minScanE, rawEcorr - 0.22);
    cathMaxE = Math.min(rawEcorr - 0.04, cathMinE + 0.15);
  }

  if (customAnodicRange) {
    anodMinE = customAnodicRange[0];
    anodMaxE = customAnodicRange[1];
  } else {
    anodMinE = Math.max(rawEcorr + 0.04, anodMinE);
    anodMaxE = Math.min(maxScanE, rawEcorr + 0.22);
  }

  // Filter cathodic points
  const cathPoints = points.filter(
    (p) => p.potential >= Math.min(cathMinE, cathMaxE) && p.potential <= Math.max(cathMinE, cathMaxE)
  );

  // Filter anodic points
  const anodPoints = points.filter(
    (p) => p.potential >= Math.min(anodMinE, anodMaxE) && p.potential <= Math.max(anodMinE, anodMaxE)
  );

  // 3. Fit Linear Slopes: log(i) = m * E + b
  // Note: For anodic, m > 0 (as E increases, i increases), so betaA = 1 / m (V/dec)
  // For cathodic, m < 0 (as E decreases below Ecorr, i increases), so betaC = -1 / m (V/dec)
  const cathRegression = linearRegression(
    cathPoints.map((p) => p.potential),
    cathPoints.map((p) => p.logCurrentDensity)
  );

  const anodRegression = linearRegression(
    anodPoints.map((p) => p.potential),
    anodPoints.map((p) => p.logCurrentDensity)
  );

  // Branch validity: an unusable branch is unavailable, never replaced by an assumed slope or R2.
  const cathReason = tafelBranchUnavailableReason("Cathodic", [cathMinE, cathMaxE], cathPoints.length, cathRegression.m);
  const anodReason = tafelBranchUnavailableReason("Anodic", [anodMinE, anodMaxE], anodPoints.length, anodRegression.m);
  const cathFit = cathReason ? null : cathRegression;
  const anodFit = anodReason ? null : anodRegression;
  const bothBranches = cathFit !== null && anodFit !== null;

  // 4. Solve for Intersection: (Ecorr, log(Icorr)); needs both branches
  // log(i) = m_c * E + b_c
  // log(i) = m_a * E + b_a
  // m_c * E + b_c = m_a * E + b_a => E_intersect = (b_c - b_a) / (m_a - m_c)
  let extrapolatedEcorr: number | null = null;
  let extrapolatedLogIcorr: number | null = null;
  // An unusable intersection (parallel branches, or more than 0.15 V from the measured valley) falls back to the
  // measured valley as E_corr; that substitution is reported (intersectionStatus / intersectionNote), never silent.
  let intersectionNote: string | null = null;

  if (cathFit && anodFit) {
    extrapolatedEcorr = rawEcorr;
    const denom = anodFit.m - cathFit.m;
    if (Math.abs(denom) > 1e-6) {
      const eInter = (cathFit.b - anodFit.b) / denom;
      // Keep within reasonable range of the raw minimum
      if (Math.abs(eInter - rawEcorr) <= 0.15) {
        extrapolatedEcorr = eInter;
      } else {
        intersectionNote =
          `the Evans intersection of the fitted branches is at ${eInter.toFixed(3)} V, ` +
          `${Math.abs(eInter - rawEcorr).toFixed(3)} V from the measured current valley (limit 0.15 V); the measured ` +
          `valley ${rawEcorr.toFixed(4)} V is used as E_corr and i_corr is read from the anodic line there`;
      }
    } else {
      intersectionNote =
        `the fitted branches are parallel, so they do not intersect; the measured current valley ` +
        `${rawEcorr.toFixed(4)} V is used as E_corr and i_corr is read from the anodic line there`;
    }
    extrapolatedLogIcorr = anodFit.m * extrapolatedEcorr + anodFit.b;
  }

  // Manual Overrides if provided
  if (typeof manualEcorrOverride === "number") {
    extrapolatedEcorr = manualEcorrOverride;
  }
  if (typeof manualIcorrOverride === "number") {
    extrapolatedLogIcorr = Math.log10(Math.max(1e-9, manualIcorrOverride));
  }

  const extrapolatedIcorr_uA_cm2 = extrapolatedLogIcorr === null ? null : Math.pow(10, extrapolatedLogIcorr);

  // Tafel Slopes
  // betaA (V/dec) = 1 / m_a
  // betaC (V/dec) = -1 / m_c
  const betaA_V_dec = anodFit ? Math.abs(1 / anodFit.m) : null;
  const betaC_V_dec = cathFit ? Math.abs(1 / cathFit.m) : null;
  const betaA_mV_dec = betaA_V_dec === null ? null : betaA_V_dec * 1000;
  const betaC_mV_dec = betaC_V_dec === null ? null : betaC_V_dec * 1000;

  // 5. Stern-Geary Polarization Resistance (ASTM G59): needs both slopes and i_corr
  // B = (beta_a * beta_c) / (ln(10) * (beta_a + beta_c))
  // i_corr in A/cm2 = extrapolatedIcorr_uA_cm2 * 1e-6
  let sternGearyB_V: number | null = null;
  let rp_ohm_cm2: number | null = null;
  if (betaA_V_dec !== null && betaC_V_dec !== null && extrapolatedIcorr_uA_cm2 !== null) {
    sternGearyB_V = (betaA_V_dec * betaC_V_dec) / (Math.LN10 * (betaA_V_dec + betaC_V_dec));
    rp_ohm_cm2 = sternGearyB_V / (extrapolatedIcorr_uA_cm2 * 1e-6);
  }

  // 6. Faraday's Law Corrosion Penetration Rate (ASTM G102): needs i_corr and the substrate
  // CR (mm/year) = (K1 * i_corr (µA/cm²) * EW) / density (g/cm³), K1 = 1e-6 * s/yr * 10 / F
  // (0.0032707148 with the exact F; the Python solver uses the same K1). The substrate comes from
  // the dataset metadata only: a missing equivalent weight or density is unavailable, never the 316L preset.
  const EW = dataset.metadata.equivalentWeight;
  const density = dataset.metadata.density_g_cm3;
  const area = dataset.metadata.electrodeAreaCm2 || 1.0;
  const substrateKnown = typeof EW === "number" && EW > 0 && typeof density === "number" && density > 0;

  let cr_mm_yr: number | null = null;
  let cr_mpy: number | null = null;
  let massLoss_g_m2_day: number | null = null;
  if (extrapolatedIcorr_uA_cm2 !== null && substrateKnown) {
    const K1 = (1e-6 * 31557600.0 * 10.0) / FARADAY_CONSTANT;
    cr_mm_yr = (K1 * extrapolatedIcorr_uA_cm2 * EW) / density;
    cr_mpy = cr_mm_yr * MILS_PER_MM; // mils per year (1 mil = 0.0254 mm exactly)
    // Mass loss: g / (m² · day); i_corr in A/m² = (i_corr in A/cm²) * 10^4
    massLoss_g_m2_day = (extrapolatedIcorr_uA_cm2 * 1e-6 * 10000 * EW * 86400) / FARADAY_CONSTANT;
  }

  // 7. Potential vs SHE
  const refOffset = dataset.metadata.refOffsetVsSHE ?? 0.241;
  const eCorrSHE = extrapolatedEcorr === null ? null : extrapolatedEcorr + refOffset;

  // 8. Generate Tangent Extrapolation Lines for Charting (only for the branches that were fitted)
  // Extend across the scan window
  const refE = extrapolatedEcorr ?? rawEcorr;
  const eMinPlot = Math.min(minScanE, refE - 0.35);
  const eMaxPlot = Math.max(maxScanE, refE + 0.35);
  const nTangentSteps = 50;
  const tangentLines: TafelFitResult["tangentLines"] = [];

  for (let i = 0; i <= nTangentSteps; i++) {
    const e = eMinPlot + (eMaxPlot - eMinPlot) * (i / nTangentSteps);
    // Show anodic line in its upper half (down to ~20mV below Ecorr)
    const showAnodic = anodFit !== null && e >= refE - 0.03 && e <= anodMaxE + 0.15;
    // Show cathodic line in its lower half (up to ~20mV above Ecorr)
    const showCathodic = cathFit !== null && e <= refE + 0.03 && e >= cathMinE - 0.15;

    tangentLines.push({
      potential: parseFloat(e.toFixed(4)),
      // Anodic tangent line: log(i) = m_a * e + b_a; cathodic: log(i) = m_c * e + b_c
      logI_anodic: showAnodic && anodFit ? parseFloat((anodFit.m * e + anodFit.b).toFixed(3)) : null,
      logI_cathodic: showCathodic && cathFit ? parseFloat((cathFit.m * e + cathFit.b).toFixed(3)) : null,
    });
  }

  // 9. Reconstruct Synthetic Butler-Volmer Curve (needs both slopes, Ecorr and i_corr)
  // i_BV(E) = i_corr * | 10^((E - Ecorr) / betaA) - 10^(-(E - Ecorr) / betaC) |
  const syntheticButlerVolmer: TafelFitResult["syntheticButlerVolmer"] = [];
  if (betaA_V_dec !== null && betaC_V_dec !== null && extrapolatedEcorr !== null && extrapolatedIcorr_uA_cm2 !== null) {
    for (let i = 0; i <= 60; i++) {
      const e = eMinPlot + (eMaxPlot - eMinPlot) * (i / 60);
      const overpotential = e - extrapolatedEcorr;
      const iA = Math.pow(10, overpotential / betaA_V_dec);
      const iC = Math.pow(10, -overpotential / betaC_V_dec);
      const netI = Math.abs(iA - iC);
      const totalCurrentDensity = extrapolatedIcorr_uA_cm2 * netI;
      const logVal = Math.log10(Math.max(1e-6, totalCurrentDensity));

      syntheticButlerVolmer.push({
        potential: parseFloat(e.toFixed(4)),
        logI_model: parseFloat(logVal.toFixed(3)),
      });
    }
  }

  // 10. Severity Classification (needs a corrosion rate)
  let severity: TafelFitResult["severity"] = null;
  let astmClassification: string | null = null;

  if (cr_mm_yr !== null) {
    if (cr_mm_yr < 0.02) {
      severity = "Immune / Highly Resistant";
      astmClassification = "Immune / Outstanding Corrosion Resistance (CR < 0.02 mm/yr)";
    } else if (cr_mm_yr < 0.10) {
      severity = "Passivated / Good";
      astmClassification = "Passivated Stable Barrier (0.02 - 0.10 mm/yr)";
    } else if (cr_mm_yr < 0.50) {
      severity = "Moderate (Caution)";
      astmClassification = "Moderate Dissolution (0.10 - 0.50 mm/yr - Sacrificial/Protection Required)";
    } else {
      severity = "Severe Rapid Corrosion";
      astmClassification = "Severe Rapid Degradation (CR > 0.50 mm/yr - Immediate Failure Hazard)";
    }
  }

  // Pitting detection in anodic branch
  let pittingPotentialEpit: number | null = null;
  const highAnodicPoints = points.filter((p) => p.potential > refE + 0.15);
  for (let i = 1; i < highAnodicPoints.length; i++) {
    const dLogI = highAnodicPoints[i].logCurrentDensity - highAnodicPoints[i - 1].logCurrentDensity;
    const dE = highAnodicPoints[i].potential - highAnodicPoints[i - 1].potential;
    if (dE > 0 && dLogI / dE > 25.0 && highAnodicPoints[i].currentDensity_uA_cm2 > 100) {
      pittingPotentialEpit = highAnodicPoints[i].potential;
      break;
    }
  }

  const round = (v: number | null, digits: number): number | null => (v === null ? null : parseFloat(v.toFixed(digits)));

  const result: TafelFitResult = {
    eCorr: round(extrapolatedEcorr, 4),
    eCorrSHE: round(eCorrSHE, 4),
    iCorr_uA_cm2: round(extrapolatedIcorr_uA_cm2, 4),
    logIcorr: round(extrapolatedLogIcorr, 3),
    totalCurrentIcorr_uA: extrapolatedIcorr_uA_cm2 === null ? null : parseFloat((extrapolatedIcorr_uA_cm2 * area).toFixed(4)),

    betaA_V_dec: round(betaA_V_dec, 4),
    betaA_mV_dec: round(betaA_mV_dec, 1),
    betaC_V_dec: round(betaC_V_dec, 4),
    betaC_mV_dec: round(betaC_mV_dec, 1),
    sternGearyB_V: round(sternGearyB_V, 4),
    rp_ohm_cm2: round(rp_ohm_cm2, 1),

    corrosionRateMmYr: round(cr_mm_yr, 5),
    corrosionRateMpy: round(cr_mpy, 3),
    massLoss_g_m2_day: round(massLoss_g_m2_day, 4),

    cathodicRange: [parseFloat(cathMinE.toFixed(3)), parseFloat(cathMaxE.toFixed(3))],
    anodicRange: [parseFloat(anodMinE.toFixed(3)), parseFloat(anodMaxE.toFixed(3))],
    cathodicR2: cathFit ? parseFloat(cathFit.r2.toFixed(4)) : null,
    anodicR2: anodFit ? parseFloat(anodFit.r2.toFixed(4)) : null,
    cathodicSlope_m: cathFit ? parseFloat(cathFit.m.toFixed(3)) : null,
    cathodicIntercept_b: cathFit ? parseFloat(cathFit.b.toFixed(3)) : null,
    anodicSlope_m: anodFit ? parseFloat(anodFit.m.toFixed(3)) : null,
    anodicIntercept_b: anodFit ? parseFloat(anodFit.b.toFixed(3)) : null,

    rawEcorrValley: parseFloat(rawEcorr.toFixed(4)),
    rawIcorrValley: parseFloat(rawIcorr.toFixed(4)),

    tangentLines,
    syntheticButlerVolmer,

    pittingPotentialEpit_V: pittingPotentialEpit !== null ? parseFloat(pittingPotentialEpit.toFixed(3)) : null,
    severity,
    astmClassification,
  };

  const reasons: NonNullable<TafelFitResult["unavailable"]> = {};
  if (anodReason) reasons.anodicBranch = anodReason;
  if (cathReason) reasons.cathodicBranch = cathReason;
  if (!bothBranches && extrapolatedIcorr_uA_cm2 === null) {
    reasons.iCorr_uA_cm2 =
      "the Evans intersection needs both Tafel branches; no corrosion current density is invented " +
      "(use the manual i_corr override to enter a known value)";
  }
  if (extrapolatedIcorr_uA_cm2 !== null && !substrateKnown) {
    reasons.substrate =
      "the dataset has no equivalent weight / density, so the Faraday rate is unavailable (no alloy is substituted)";
  }
  if (intersectionNote && !(typeof manualEcorrOverride === "number" && typeof manualIcorrOverride === "number")) {
    result.intersectionStatus = "substituted-measured-valley";
    result.intersectionNote = intersectionNote;
  }
  if (Object.keys(reasons).length > 0) {
    result.fitStatus = "unavailable";
    result.unavailable = reasons;
    result.unavailableReason = Object.values(reasons).join("; ");
  }
  return result;
}

/**
 * Complete Tafel fit or an error: returns the fit only when every value is available, otherwise throws
 * TafelFitUnavailableError (its `fit` holds the partial result). Use tryAutoFitTafel to show partial results.
 */
export function autoFitTafel(
  dataset: TafelDataset,
  customCathodicRange?: [number, number],
  customAnodicRange?: [number, number],
  manualEcorrOverride?: number,
  manualIcorrOverride?: number
): TafelFitComplete {
  const fit = tryAutoFitTafel(dataset, customCathodicRange, customAnodicRange, manualEcorrOverride, manualIcorrOverride);
  if (!isTafelFitComplete(fit)) throw new TafelFitUnavailableError(fit);
  return fit;
}

/**
 * Exports the Tafel dataset and fit result as CSV. The header names the ASTM G102 / G59
 * relations used for the computed quantities; the export is not checked against an ASTM field list.
 */
export function exportTafelToCSV(dataset: TafelDataset, fitResult: TafelFitResult): string {
  const meta = dataset.metadata;
  const header = [
    `# =========================================================================`,
    `# MetalliX Electrochemical Tafel Polarization Report (ASTM G102 / ASTM G59)`,
    `# Dataset: ${dataset.name}`,
    `# Material Substrate: ${meta.alloyName}`,
    `# Specimen Area: ${meta.electrodeAreaCm2} cm2`,
    `# Reference Electrode: ${meta.referenceElectrode} (Offset: ${meta.refOffsetVsSHE} V vs SHE)`,
    `# Electrolyte: ${meta.electrolyte}`,
    `# Scan Rate: ${meta.scanRateMv_s || 1.0} mV/s`,
    `# Temperature: ${meta.temperatureC} °C`,
    `# `,
    `# TAFEL EXTRAPOLATION KINETIC RESULTS:`,
    `# Corrosion Potential (E_corr): ${fmtTafelQuantity(fitResult.eCorr, "V")} vs ${meta.referenceElectrode} (${fmtTafelQuantity(fitResult.eCorrSHE, "V")} vs SHE)`,
    `# Corrosion Current Density (i_corr): ${fmtTafelQuantity(fitResult.iCorr_uA_cm2, "uA/cm2")} (log10 = ${fmtTafelNumber(fitResult.logIcorr)})`,
    `# Total Corrosion Current (I_corr): ${fmtTafelQuantity(fitResult.totalCurrentIcorr_uA, "uA")}`,
    `# Anodic Tafel Slope (Beta_a): ${fmtTafelQuantity(fitResult.betaA_mV_dec, "mV/decade")} (R2: ${fmtTafelNumber(fitResult.anodicR2)})`,
    `# Cathodic Tafel Slope (Beta_c): ${fmtTafelQuantity(fitResult.betaC_mV_dec, "mV/decade")} (R2: ${fmtTafelNumber(fitResult.cathodicR2)})`,
    `# Stern-Geary B Constant: ${fmtTafelQuantity(fitResult.sternGearyB_V, "V")}`,
    `# Polarization Resistance (R_p): ${fmtTafelQuantity(fitResult.rp_ohm_cm2, "Ohm*cm2")}`,
    `# Faraday Penetration Rate: ${fmtTafelQuantity(fitResult.corrosionRateMmYr, "mm/year")} (${fmtTafelQuantity(fitResult.corrosionRateMpy, "mpy")})`,
    `# Daily Mass Loss: ${fmtTafelQuantity(fitResult.massLoss_g_m2_day, "g/(m2*day)")}`,
    `# Classification: ${fitResult.astmClassification ?? fmtTafelNumber(null)}`,
    ...(tafelUnavailableReason(fitResult) ? [`# Unavailable: ${tafelUnavailableReason(fitResult)}`] : []),
    `# =========================================================================`,
    `Potential_V,Potential_SHE_V,CurrentDensity_uA_cm2,log10_CurrentDensity,SignedCurrentDensity_uA_cm2`,
  ].join("\n");

  const dataRows = dataset.points
    .map(
      (p) =>
        `${p.potential},${p.potentialSHE || p.potential + meta.refOffsetVsSHE},${p.currentDensity_uA_cm2},${p.logCurrentDensity},${p.signedCurrentDensity_uA_cm2}`
    )
    .join("\n");

  return `${header}\n${dataRows}`;
}
