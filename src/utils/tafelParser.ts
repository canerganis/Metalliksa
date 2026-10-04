import { TafelDataset, TafelFitResult, TafelRawPoint, ReferenceElectrodeType } from "../types/tafel";
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
  const refOffset = REFERENCE_ELECTRODES[refElectrode]?.offsetVsSHE || 0.241;

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
    // Check if comma is decimal separator (e.g. "1,234   2,567")
    const parts = line.split(",");
    if (parts.length > 2) {
      return parts.map((t) => t.trim());
    }
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

/**
 * Automatic Tafel Extrapolation & Kinetics Solver (ASTM G102 & G59).
 * Detects the minimum current valley ($E_{corr}^{valley}$), fits linear Tafel lines
 * on the cathodic and anodic branches, solves for their intersection $(E_{corr}, I_{corr})$,
 * and calculates all Stern-Geary and Faraday corrosion rates.
 */
export function autoFitTafel(
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
  let cathFit = linearRegression(
    cathPoints.map((p) => p.potential),
    cathPoints.map((p) => p.logCurrentDensity)
  );

  let anodFit = linearRegression(
    anodPoints.map((p) => p.potential),
    anodPoints.map((p) => p.logCurrentDensity)
  );

  // Guard: Ensure slope directions are physically sound
  // Cathodic slope should be negative: d(log i)/dE < 0
  if (cathFit.m >= 0 || cathPoints.length < 3) {
    // Fallback standard cathodic slope: 100 mV/dec -> m = -10.0
    const mFall = -8.33; // 120 mV/dec
    const bFall = (points[minIdx]?.logCurrentDensity || 0) - mFall * rawEcorr + 0.5;
    cathFit = { m: mFall, b: bFall, r2: 0.85 };
  }

  // Anodic slope should be positive: d(log i)/dE > 0
  if (anodFit.m <= 0 || anodPoints.length < 3) {
    // Fallback standard anodic slope: 100 mV/dec -> m = +10.0
    const mFall = 10.0; // 100 mV/dec
    const bFall = (points[minIdx]?.logCurrentDensity || 0) - mFall * rawEcorr + 0.5;
    anodFit = { m: mFall, b: bFall, r2: 0.85 };
  }

  // 4. Solve for Intersection: (Ecorr, log(Icorr))
  // log(i) = m_c * E + b_c
  // log(i) = m_a * E + b_a
  // m_c * E + b_c = m_a * E + b_a => E_intersect = (b_c - b_a) / (m_a - m_c)
  let extrapolatedEcorr = rawEcorr;
  let extrapolatedLogIcorr = Math.log10(rawIcorr);

  const denom = anodFit.m - cathFit.m;
  if (Math.abs(denom) > 1e-6) {
    const eInter = (cathFit.b - anodFit.b) / denom;
    // Keep within reasonable range of the raw minimum
    if (Math.abs(eInter - rawEcorr) <= 0.15) {
      extrapolatedEcorr = eInter;
    }
  }

  extrapolatedLogIcorr = anodFit.m * extrapolatedEcorr + anodFit.b;

  // Manual Overrides if provided
  if (typeof manualEcorrOverride === "number") {
    extrapolatedEcorr = manualEcorrOverride;
  }
  if (typeof manualIcorrOverride === "number") {
    extrapolatedLogIcorr = Math.log10(Math.max(1e-9, manualIcorrOverride));
  }

  const extrapolatedIcorr_uA_cm2 = Math.pow(10, extrapolatedLogIcorr);

  // Tafel Slopes
  // betaA (V/dec) = 1 / m_a
  // betaC (V/dec) = -1 / m_c
  const betaA_V_dec = Math.abs(1 / anodFit.m);
  const betaC_V_dec = Math.abs(1 / cathFit.m);
  const betaA_mV_dec = betaA_V_dec * 1000;
  const betaC_mV_dec = betaC_V_dec * 1000;

  // 5. Stern-Geary Polarization Resistance (ASTM G59)
  // B = (beta_a * beta_c) / (2.302585 * (beta_a + beta_c))
  const sternGearyB_V = (betaA_V_dec * betaC_V_dec) / (2.302585 * (betaA_V_dec + betaC_V_dec));
  // i_corr in A/cm2 = extrapolatedIcorr_uA_cm2 * 1e-6
  const iCorr_A_cm2 = extrapolatedIcorr_uA_cm2 * 1e-6;
  const rp_ohm_cm2 = sternGearyB_V / iCorr_A_cm2;

  // 6. Faraday's Law Corrosion Penetration Rate (ASTM G102)
  // CR (mm/year) = (K1 * i_corr (µA/cm²) * EW) / density (g/cm³), K1 = 1e-6 * s/yr * 10 / F
  // (0.0032707148 with the exact F; the Python solver uses the same K1). Missing metadata
  // falls back to the 316L preset (COMMON_ALLOYS[0], registry values).
  const EW = dataset.metadata.equivalentWeight || COMMON_ALLOYS[0].equivalentWeight;
  const density = dataset.metadata.density_g_cm3 || COMMON_ALLOYS[0].density;
  const area = dataset.metadata.electrodeAreaCm2 || 1.0;

  const K1 = (1e-6 * 31557600.0 * 10.0) / FARADAY_CONSTANT;
  const cr_mm_yr = (K1 * extrapolatedIcorr_uA_cm2 * EW) / density;
  const cr_mpy = cr_mm_yr * 39.3701; // mils per year

  // Mass loss: g / (m² · day)
  // i_corr in A/m² = (i_corr in A/cm²) * 10^4
  const massLoss_g_m2_day = (iCorr_A_cm2 * 10000 * EW * 86400) / FARADAY_CONSTANT;

  // 7. Potential vs SHE
  const refOffset = dataset.metadata.refOffsetVsSHE || 0.241;
  const eCorrSHE = extrapolatedEcorr + refOffset;

  // 8. Generate Tangent Extrapolation Lines for Charting
  // Extend across the scan window
  const eMinPlot = Math.min(minScanE, extrapolatedEcorr - 0.35);
  const eMaxPlot = Math.max(maxScanE, extrapolatedEcorr + 0.35);
  const nTangentSteps = 50;
  const tangentLines: TafelFitResult["tangentLines"] = [];

  for (let i = 0; i <= nTangentSteps; i++) {
    const e = eMinPlot + (eMaxPlot - eMinPlot) * (i / nTangentSteps);
    // Anodic tangent line: log(i) = m_a * e + b_a
    // Cathodic tangent line: log(i) = m_c * e + b_c
    const logIa = anodFit.m * e + anodFit.b;
    const logIc = cathFit.m * e + cathFit.b;

    // Show anodic line in its upper half (down to ~20mV below Ecorr)
    const showAnodic = e >= extrapolatedEcorr - 0.03 && e <= anodMaxE + 0.15;
    // Show cathodic line in its lower half (up to ~20mV above Ecorr)
    const showCathodic = e <= extrapolatedEcorr + 0.03 && e >= cathMinE - 0.15;

    tangentLines.push({
      potential: parseFloat(e.toFixed(4)),
      logI_anodic: showAnodic ? parseFloat(logIa.toFixed(3)) : null,
      logI_cathodic: showCathodic ? parseFloat(logIc.toFixed(3)) : null,
    });
  }

  // 9. Reconstruct Synthetic Butler-Volmer Curve
  // i_BV(E) = i_corr * | 10^((E - Ecorr) / betaA) - 10^(-(E - Ecorr) / betaC) |
  const syntheticButlerVolmer: TafelFitResult["syntheticButlerVolmer"] = [];
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

  // 10. Severity Classification
  let severity: TafelFitResult["severity"] = "Passivated / Good";
  let astmClassification = "Passivated Stable Barrier";

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

  // Pitting detection in anodic branch
  let pittingPotentialEpit: number | null = null;
  const highAnodicPoints = points.filter((p) => p.potential > extrapolatedEcorr + 0.15);
  for (let i = 1; i < highAnodicPoints.length; i++) {
    const dLogI = highAnodicPoints[i].logCurrentDensity - highAnodicPoints[i - 1].logCurrentDensity;
    const dE = highAnodicPoints[i].potential - highAnodicPoints[i - 1].potential;
    if (dE > 0 && dLogI / dE > 25.0 && highAnodicPoints[i].currentDensity_uA_cm2 > 100) {
      pittingPotentialEpit = highAnodicPoints[i].potential;
      break;
    }
  }

  return {
    eCorr: parseFloat(extrapolatedEcorr.toFixed(4)),
    eCorrSHE: parseFloat(eCorrSHE.toFixed(4)),
    iCorr_uA_cm2: parseFloat(extrapolatedIcorr_uA_cm2.toFixed(4)),
    logIcorr: parseFloat(extrapolatedLogIcorr.toFixed(3)),
    totalCurrentIcorr_uA: parseFloat((extrapolatedIcorr_uA_cm2 * area).toFixed(4)),

    betaA_V_dec: parseFloat(betaA_V_dec.toFixed(4)),
    betaA_mV_dec: parseFloat(betaA_mV_dec.toFixed(1)),
    betaC_V_dec: parseFloat(betaC_V_dec.toFixed(4)),
    betaC_mV_dec: parseFloat(betaC_mV_dec.toFixed(1)),
    sternGearyB_V: parseFloat(sternGearyB_V.toFixed(4)),
    rp_ohm_cm2: parseFloat(rp_ohm_cm2.toFixed(1)),

    corrosionRateMmYr: parseFloat(cr_mm_yr.toFixed(5)),
    corrosionRateMpy: parseFloat(cr_mpy.toFixed(3)),
    massLoss_g_m2_day: parseFloat(massLoss_g_m2_day.toFixed(4)),

    cathodicRange: [parseFloat(cathMinE.toFixed(3)), parseFloat(cathMaxE.toFixed(3))],
    anodicRange: [parseFloat(anodMinE.toFixed(3)), parseFloat(anodMaxE.toFixed(3))],
    cathodicR2: parseFloat(cathFit.r2.toFixed(4)),
    anodicR2: parseFloat(anodFit.r2.toFixed(4)),
    cathodicSlope_m: parseFloat(cathFit.m.toFixed(3)),
    cathodicIntercept_b: parseFloat(cathFit.b.toFixed(3)),
    anodicSlope_m: parseFloat(anodFit.m.toFixed(3)),
    anodicIntercept_b: parseFloat(anodFit.b.toFixed(3)),

    rawEcorrValley: parseFloat(rawEcorr.toFixed(4)),
    rawIcorrValley: parseFloat(rawIcorr.toFixed(4)),

    tangentLines,
    syntheticButlerVolmer,

    pittingPotentialEpit_V: pittingPotentialEpit !== null ? parseFloat(pittingPotentialEpit.toFixed(3)) : null,
    severity,
    astmClassification,
  };
}

/**
 * Benchmark datasets. Empty: the former entries were Tafel curves fabricated with PRNG
 * noise by createBenchmarkDataset(), which is disabled (see below). They were built at
 * module load, so importing this module threw (BUG 1); no measured benchmark curves
 * exist to replace them, so none are listed. Consumers must handle an empty list.
 */
export const TAFEL_BENCHMARK_DATASETS: TafelDataset[] = [];

export interface BenchmarkParams {
  id: string;
  name: string;
  material: AlloyMaterialPreset;
  eCorrTrue: number;
  iCorrTrue: number;
  betaA: number;
  betaC: number;
  eStart: number;
  eEnd: number;
  nPoints: number;
  hasPitting: boolean;
  ePit?: number;
  noiseLevel: number;
}

// Disabled on purpose: synthetic (PRNG-noise) polarization curves must not be presented
// as benchmark data. Nothing calls it any more; it is kept so that the refusal stays
// explicit if a caller is ever reintroduced.
export function createBenchmarkDataset(_params: BenchmarkParams): TafelDataset {
  throw new Error("Fabrication of Tafel potentiodynamic polarization curves via PRNG noise is disabled.");
}

/**
 * Exports Tafel dataset and fit result as an ASTM-compliant CSV report
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
    `# Corrosion Potential (E_corr): ${fitResult.eCorr} V vs ${meta.referenceElectrode} (${fitResult.eCorrSHE} V vs SHE)`,
    `# Corrosion Current Density (i_corr): ${fitResult.iCorr_uA_cm2} uA/cm2 (log10 = ${fitResult.logIcorr})`,
    `# Total Corrosion Current (I_corr): ${fitResult.totalCurrentIcorr_uA} uA`,
    `# Anodic Tafel Slope (Beta_a): ${fitResult.betaA_mV_dec} mV/decade (R2: ${fitResult.anodicR2})`,
    `# Cathodic Tafel Slope (Beta_c): ${fitResult.betaC_mV_dec} mV/decade (R2: ${fitResult.cathodicR2})`,
    `# Stern-Geary B Constant: ${fitResult.sternGearyB_V} V`,
    `# Polarization Resistance (R_p): ${fitResult.rp_ohm_cm2} Ohm*cm2`,
    `# Faraday Penetration Rate: ${fitResult.corrosionRateMmYr} mm/year (${fitResult.corrosionRateMpy} mpy)`,
    `# Daily Mass Loss: ${fitResult.massLoss_g_m2_day} g/(m2*day)`,
    `# Classification: ${fitResult.astmClassification}`,
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
