// Source-declared EMSA/MAS and delimited EDS spectra. Opaque binary SPC calibration is not guessed.

import { CHARACTERISTIC_XRAY_LINES, SpectrumPoint } from "../data/edsReferenceData";

const DECIMAL_TOKEN = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

function parseFiniteNumberToken(token: string, label: string): number {
  const trimmed = token.trim();
  if (!DECIMAL_TOKEN.test(trimmed)) throw new Error(`Invalid ${label} numeric token '${token}'.`);
  const value = Number(trimmed);
  if (!Number.isFinite(value)) throw new Error(`${label} must be a finite number.`);
  return value;
}

function parseNonnegativeNumberToken(token: string, label: string): number {
  const value = parseFiniteNumberToken(token, label);
  if (value < 0) {
    throw new Error(`${label} must be a finite, nonnegative number.`);
  }
  return value;
}

function parsePositiveMetadata(token: string, label: string): number {
  const value = parseNonnegativeNumberToken(token, label);
  if (value <= 0) throw new Error(`${label} must be greater than zero.`);
  return value;
}

function parseDeadTimeMetadata(token: string, label: string): number {
  const value = parseNonnegativeNumberToken(token, label);
  if (value > 100) throw new Error(`${label} must be within [0, 100].`);
  return value;
}

function isNumericLookingToken(token: string): boolean {
  return /^[+-]?(?:\d|\.\d|Infinity|NaN)/i.test(token.trim());
}

export interface ParsedEDSSpectrum {
  fileName: string;
  sampleTitle?: string;
  beamEnergyKv?: number;
  liveTimeSec?: number;
  deadTimePct?: number;
  energyCalibrationSource?: string;
  points: SpectrumPoint[];
  detectedPeaks: {
    energyKeV: number;
    counts: number;
    matchedElement?: string;
    matchedLine?: string;
    confidence: number;
  }[];
  estimatedComposition?: {
    symbol: string;
    weightPct: number;
    atomicPct: number;
  }[];
}

/**
 * Universal EDS File Parser supporting:
 * - EMSA / MAS standard spectrum files (.emsa, .msa)
 * - Calibrated EMSA / MAS energy spectra (.emsa, .msa)
 * - 2-Column Delimited spectra with a declared eV or keV energy axis (.csv, .txt, .dat)
 */
export function parseRawEDSFile(
  fileContent: string | ArrayBuffer,
  fileName: string
): ParsedEDSSpectrum {
  let rawPoints: { energy: number; counts: number }[] = [];
  let beamEnergyKv: number | undefined;
  let liveTimeSec: number | undefined;
  let deadTimePct: number | undefined;
  let energyCalibrationSource: string | undefined;
  let sampleTitle = fileName.replace(/\.[^/.]+$/, "");

  if (typeof fileContent !== "string") {
    // Binary .spc or binary spectrum
    parseBinarySpc(fileContent, fileName);
  } else {
    // Check if it's an EMSA format
    if (fileContent.includes("#FORMAT") || fileContent.includes("#EMSA") || fileContent.includes("#NPOINTS") || fileContent.includes("#XPERCHAN")) {
      const emsaResult = parseEMSAFile(fileContent, fileName);
      rawPoints = emsaResult.points;
      if (emsaResult.beamEnergyKv !== undefined) beamEnergyKv = emsaResult.beamEnergyKv;
      if (emsaResult.liveTimeSec !== undefined) liveTimeSec = emsaResult.liveTimeSec;
      if (emsaResult.deadTimePct !== undefined) deadTimePct = emsaResult.deadTimePct;
      energyCalibrationSource = emsaResult.energyCalibrationSource;
      if (emsaResult.sampleTitle) sampleTitle = emsaResult.sampleTitle;
    } else {
      // General ASCII text parser (supporting .spc ASCII, .csv, .txt)
      const textResult = parseDelimitedEDS(fileContent, fileName);
      rawPoints = textResult.points;
      if (textResult.beamEnergyKv !== undefined) beamEnergyKv = textResult.beamEnergyKv;
      if (textResult.liveTimeSec !== undefined) liveTimeSec = textResult.liveTimeSec;
      if (textResult.deadTimePct !== undefined) deadTimePct = textResult.deadTimePct;
      energyCalibrationSource = textResult.energyCalibrationSource;
      if (textResult.sampleTitle) sampleTitle = textResult.sampleTitle;
    }
  }

  // If no points parsed, generate error
  if (rawPoints.length === 0) {
    throw new Error(
      `Could not detect valid calibrated energy and counts in "${fileName}". Supported formats: calibrated .emsa/.msa or delimited data declaring eV/keV.`
    );
  }

  // Sort by energy ascending
  rawPoints.sort((a, b) => a.energy - b.energy);

  // Preserve the imported counts. Background subtraction requires a declared
  // model or an instrument-provided background; do not invent one at ingest.
  const points: SpectrumPoint[] = rawPoints.map((p) => {
    return {
      energyKeV: p.energy,
      counts: p.counts,
      background: 0,
      netCounts: p.counts,
    };
  });

  // Peak detection (local maxima)
  const detectedPeaks: ParsedEDSSpectrum["detectedPeaks"] = [];
  for (let i = 2; i < points.length - 2; i++) {
    const p = points[i];
    if (p.netCounts > 200 && p.netCounts > points[i - 1].netCounts && p.netCounts > points[i + 1].netCounts) {
      if (p.netCounts > points[i - 2].netCounts && p.netCounts > points[i + 2].netCounts) {
        // Match with known characteristic X-ray lines
        let bestMatch: string | undefined;
        let bestLine: string | undefined;
        let minDiff = 0.08; // 80 eV tolerance

        Object.entries(CHARACTERISTIC_XRAY_LINES).forEach(([sym, elem]) => {
          if (elem.lines.kAlpha && Math.abs(elem.lines.kAlpha - p.energyKeV) < minDiff) {
            minDiff = Math.abs(elem.lines.kAlpha - p.energyKeV);
            bestMatch = sym;
            bestLine = `Kα (${elem.lines.kAlpha.toFixed(2)} keV)`;
          }
          if (elem.lines.lAlpha && Math.abs(elem.lines.lAlpha - p.energyKeV) < minDiff) {
            minDiff = Math.abs(elem.lines.lAlpha - p.energyKeV);
            bestMatch = sym;
            bestLine = `Lα (${elem.lines.lAlpha.toFixed(2)} keV)`;
          }
        });

        detectedPeaks.push({
          energyKeV: p.energyKeV,
          counts: p.counts,
          matchedElement: bestMatch,
          matchedLine: bestLine,
          confidence: bestMatch ? 90 : 50,
        });
      }
    }
  }

  return {
    fileName,
    sampleTitle,
    beamEnergyKv,
    liveTimeSec,
    deadTimePct,
    energyCalibrationSource,
    points,
    detectedPeaks,
  };
}

/**
 * Parses EMSA/MAS format (.emsa, .msa) files.
 */
function parseEMSAFile(fileContent: string, fileName: string) {
  const lines = fileContent.split(/\r?\n/);
  const points: { energy: number; counts: number }[] = [];
  let beamEnergyKv: number | undefined;
  let liveTimeSec: number | undefined;
  let deadTimePct: number | undefined;
  let sampleTitle = fileName.replace(/\.[^/.]+$/, "");

  let nPoints = 0;
  let xPerChan: number | undefined;
  let offset: number | undefined;
  let xUnits: string | undefined;
  let isSpectrum = false;
  let channelIdx = 0;
  let realTimeSec: number | undefined;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    if (line.startsWith("#")) {
      const upper = line.toUpperCase();
      const parts = line.split(":");
      const tag = parts[0].trim().toUpperCase();
      const val = parts.slice(1).join(":").trim();

      if (tag.includes("TITLE") || tag.includes("SAMPLE")) {
        if (val) sampleTitle = val;
      } else if (tag.includes("NPOINTS")) {
        if (!/^\d+$/.test(val)) throw new Error(`Invalid EMSA NPOINTS value '${val}'.`);
        nPoints = Number(val);
      } else if (tag.includes("XPERCHAN")) {
        const parsed = parseNonnegativeNumberToken(val, "EMSA XPERCHAN");
        if (parsed <= 0) throw new Error("EMSA XPERCHAN must be greater than zero.");
        xPerChan = parsed;
      } else if (tag.includes("OFFSET")) {
        offset = parseFiniteNumberToken(val, "EMSA OFFSET");
      } else if (tag.includes("XUNITS")) {
        xUnits = val.toUpperCase().trim();
      } else if (tag.includes("BEAMKV") || tag.includes("HV")) {
        beamEnergyKv = parsePositiveMetadata(val, "EMSA BEAMKV");
      } else if (tag.includes("LIVETIME") || tag.includes("LIVE_TIME")) {
        liveTimeSec = parsePositiveMetadata(val, "EMSA LIVETIME");
      } else if (tag.includes("DEADTIME") || tag.includes("DEAD_TIME")) {
        deadTimePct = parseDeadTimeMetadata(val, "EMSA DEADTIME");
      } else if (tag.includes("REALTIME") || tag.includes("REAL_TIME")) {
        realTimeSec = parsePositiveMetadata(val, "EMSA REALTIME");
      } else if (upper.includes("SPECTRUM")) {
        isSpectrum = true;
      }
      continue;
    }

    if (isSpectrum || /^[0-9]/.test(line)) {
      // Numbers separated by comma or whitespace (can be 1 column or multiple numbers per line)
      const tokens = line.split(/[,\s;\t]+/).filter(Boolean);
      for (const token of tokens) {
        if (!token) throw new Error("EMSA spectrum contains an empty count value.");
        const count = parseNonnegativeNumberToken(token, "EMSA count");
        // Calculate energy based on channel index
        if (xPerChan === undefined || offset === undefined || xUnits === undefined) {
          throw new Error("EMSA spectrum is missing source-declared XPERCHAN, OFFSET, or XUNITS; energy calibration is unavailable.");
        }
        if (xUnits !== "EV" && xUnits !== "KEV") {
          throw new Error(`EMSA XUNITS '${xUnits}' is not an energy unit supported for EDS preview.`);
        }
        const energyInDeclaredUnits = offset + channelIdx * xPerChan;
        const energyKeV = xUnits === "KEV" ? energyInDeclaredUnits : energyInDeclaredUnits / 1000;
        // A finite source offset can place the initial calibrated channels below zero.
        if (!Number.isFinite(energyKeV)) throw new Error("EMSA calibrated energy must be finite.");
        points.push({ energy: energyKeV, counts: count });
        channelIdx++;
      }
    }
  }

  if (nPoints <= 0 || points.length !== nPoints) {
    throw new Error(`EMSA NPOINTS does not match the imported spectrum (${nPoints} declared, ${points.length} parsed).`);
  }
  if (xPerChan === undefined || offset === undefined || xUnits === undefined) {
    throw new Error("EMSA spectrum is missing source-declared XPERCHAN, OFFSET, or XUNITS; energy calibration is unavailable.");
  }
  if (xUnits !== "EV" && xUnits !== "KEV") {
    throw new Error(`EMSA XUNITS '${xUnits}' is not an energy unit supported for EDS preview.`);
  }

  if (deadTimePct === undefined && realTimeSec !== undefined && liveTimeSec !== undefined
      && liveTimeSec <= realTimeSec) {
    deadTimePct = ((realTimeSec - liveTimeSec) / realTimeSec) * 100;
  }

  return { points, beamEnergyKv, liveTimeSec, deadTimePct, sampleTitle,
    energyCalibrationSource: "EMSA source-declared XPERCHAN/OFFSET/XUNITS" };
}

/** Reject opaque binary SPC payloads until the vendor header calibration is decoded. */
function parseBinarySpc(buffer: ArrayBuffer, fileName: string) {
  if (buffer.byteLength < 128) throw new Error("Binary .spc file is too small to contain an EDS spectrum.");
  throw new Error(`Binary SPC calibration metadata is not decoded for '${fileName}'. Export as EMSA/MAS with energy calibration or as a delimited file with an explicit energy unit.`);
}

/**
 * Parses delimited text EDS files (.csv, .txt, .dat, or ASCII .spc).
 */
function parseDelimitedEDS(fileContent: string, fileName: string) {
  const lines = fileContent.split(/\r?\n/);
  const points: { energy: number; counts: number }[] = [];
  let beamEnergyKv: number | undefined;
  let liveTimeSec: number | undefined;
  let deadTimePct: number | undefined;
  let realTimeSec: number | undefined;
  let energyUnit: "EV" | "KEV" | undefined;
  let sampleTitle = fileName.replace(/\.[^/.]+$/, "");

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    // Header inspection
    if (trimmed.startsWith("#") || trimmed.startsWith("$") || trimmed.startsWith("/")) {
      const upper = trimmed.toUpperCase();
      const declaredUnit = upper.match(/(?:XUNITS|ENERGY(?:_UNIT)?|ENERGY AXIS)\s*[:=]\s*(KEV|EV)\b/);
      if (declaredUnit) energyUnit = declaredUnit[1] as "EV" | "KEV";
      const metadata = trimmed.replace(/^[#$/]+\s*/, "").match(
        /^(BEAMKV|ACCELERATING_VOLTAGE|HV|LIVETIME|LIVE_TIME|DEADTIME|DEAD_TIME|REALTIME|REAL_TIME)\b(.*)$/i,
      );
      if (metadata) {
        const tag = metadata[1].toUpperCase();
        const value = metadata[2].replace(/^\s*[:=]?\s*/, "");
        if (['BEAMKV', 'ACCELERATING_VOLTAGE', 'HV'].includes(tag)) {
          beamEnergyKv = parsePositiveMetadata(value, `Delimited ${tag}`);
        } else if (['LIVETIME', 'LIVE_TIME'].includes(tag)) {
          liveTimeSec = parsePositiveMetadata(value, `Delimited ${tag}`);
        } else if (['DEADTIME', 'DEAD_TIME'].includes(tag)) {
          deadTimePct = parseDeadTimeMetadata(value, `Delimited ${tag}`);
        } else {
          realTimeSec = parsePositiveMetadata(value, `Delimited ${tag}`);
        }
      }
      if (upper.includes("TITLE") || upper.includes("SAMPLE")) {
        sampleTitle = trimmed.split(":")[1]?.trim() || sampleTitle;
      }
      continue;
    }

    // Coordinate parsing
    const headerUnit = trimmed.match(/\b(KEV|EV)\b/i);
    if (!/^[-+]?\d/.test(trimmed) && headerUnit && /ENERGY|X\s*[-_ ]?AXIS/i.test(trimmed)) {
      energyUnit = headerUnit[1].toUpperCase() as "EV" | "KEV";
      continue;
    }

    const explicitDelimiter = /[,;\t]/.test(trimmed);
    const parts = trimmed.split(explicitDelimiter ? /[,;\t]/ : /\s+/).map((p) => p.trim());
    const numericLike = parts.some(isNumericLookingToken);
    if (numericLike || (explicitDelimiter && parts.some(part => !part))) {
      if (parts.length !== 2 || parts.some(part => !part)) {
        throw new Error(`Delimited EDS row must contain exactly two nonempty columns: '${trimmed}'.`);
      }
      const col1 = parseNonnegativeNumberToken(parts[0], "Delimited energy");
      const col2 = parseNonnegativeNumberToken(parts[1], "Delimited count");
      if (!energyUnit) continue;
      const energy = energyUnit === "EV" ? col1 / 1000 : col1;
      if (!Number.isFinite(energy)) throw new Error("Delimited energy must be finite.");
      points.push({ energy, counts: col2 });
    }
  }

  if (!energyUnit) {
    throw new Error("Delimited EDS data must declare an energy unit (eV or keV) in its header; channel numbers cannot be treated as calibrated energy.");
  }
  if (points.length === 0) throw new Error("Delimited EDS data contains no numeric energy/count rows.");

  if (deadTimePct === undefined && realTimeSec !== undefined && liveTimeSec !== undefined
      && liveTimeSec <= realTimeSec) {
    deadTimePct = ((realTimeSec - liveTimeSec) / realTimeSec) * 100;
  }

  return { points, beamEnergyKv, liveTimeSec, deadTimePct, sampleTitle,
    energyCalibrationSource: "Delimited source-declared energy unit" };
}
