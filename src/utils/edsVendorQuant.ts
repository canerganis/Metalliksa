// Import of a vendor EDS quantification table (the element / wt% report that the microscope or its
// EDS software already produced). This is the ONLY path in this module that may send a composition to
// the Alloy Builder: the numbers come from the vendor software, they are not computed here.
//
// File format (UTF-8 text, comma / semicolon / tab / whitespace separated):
//
//   # instrument: <instrument name>          optional header rows; the form fields below override them
//   # software: <quantification software and version>
//   # analysis_type: spot | area
//   Element,wt%,sigma                         optional column-title row (first cell: Element / Symbol)
//   Fe,68.2,0.4                               element symbol, wt%, optional 1-sigma uncertainty in wt%
//   Cr,17.1,0.2
//
// Rejection (nothing is imported, every offending row is reported with its 1-based line number):
// unknown element symbol, duplicate element, wt% that is not a finite number, negative or above 100,
// uncertainty that is not a finite non-negative number, no data rows, or a missing instrument,
// software or analysis type. A total outside 95-105 wt% is only a warning.

import { sha256Bytes } from "./edsSourceArchive";

export type VendorAnalysisType = "spot" | "area";

export interface VendorQuantMetadataInput {
  instrument?: string;
  software?: string;
  analysisType?: VendorAnalysisType | "";
}

export interface VendorQuantRow {
  /** 1-based line number in the source file. */
  row: number;
  element: string;
  weightPct: number;
  sigmaWeightPct?: number;
}

export interface VendorQuantIssue {
  /** 1-based line number; 0 for problems that belong to the whole file. */
  row: number;
  message: string;
  text?: string;
}

export interface VendorQuantProvenance {
  fileName: string;
  sha256: string;
  instrument: string;
  software: string;
  analysisType: VendorAnalysisType;
  importedAt: string;
}

export interface VendorQuantResult {
  rows: VendorQuantRow[];
  errors: VendorQuantIssue[];
  warnings: string[];
  totalWeightPct: number;
  /** Element symbol to wt%, only when the import was accepted. */
  composition: Record<string, number>;
  /** Present only when the import was accepted. */
  provenance?: VendorQuantProvenance;
  transferLabel?: string;
  accepted: boolean;
}

export const VENDOR_TOTAL_WARN_MIN = 95;
export const VENDOR_TOTAL_WARN_MAX = 105;

const ELEMENT_SYMBOLS = new Set((
  "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr " +
  "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu " +
  "Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr " +
  "Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"
).split(" "));

const DECIMAL_TOKEN = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

export function isElementSymbol(symbol: string): boolean {
  return ELEMENT_SYMBOLS.has(symbol);
}

export function vendorQuantTransferLabel(provenance: Pick<VendorQuantProvenance, "software" | "instrument" | "analysisType">): string {
  return `Measured locally by ${provenance.software} on ${provenance.instrument} (${provenance.analysisType}), not bulk composition`;
}

function normaliseSymbol(token: string): string {
  const trimmed = token.trim();
  return trimmed ? trimmed[0].toUpperCase() + trimmed.slice(1).toLowerCase() : trimmed;
}

function parseNumberCell(token: string, allowedPrefix: RegExp): number {
  const cleaned = token.trim().replace(allowedPrefix, "").replace(/%$/, "").trim();
  if (!DECIMAL_TOKEN.test(cleaned)) return Number.NaN;
  return Number(cleaned);
}

/**
 * Parse and validate a vendor quantification table. `sha256` is the digest of the exact bytes that
 * were decoded to `text` (see importVendorQuant).
 */
export function parseVendorQuantText(
  text: string,
  fileName: string,
  sha256: string,
  input: VendorQuantMetadataInput = {},
  now: Date = new Date(),
): VendorQuantResult {
  const errors: VendorQuantIssue[] = [];
  const warnings: string[] = [];
  const rows: VendorQuantRow[] = [];
  const seen = new Map<string, number>();
  const header: { instrument?: string; software?: string; analysisType?: string } = {};

  const lines = text.replace(/^﻿/, "").split(/\r?\n/);
  lines.forEach((rawLine, index) => {
    const row = index + 1;
    const line = rawLine.trim();
    if (!line) return;
    if (line.startsWith("#")) {
      const meta = line.replace(/^#+\s*/, "").match(/^(instrument|software|analysis[_ ]?type)\s*[:=]\s*(.+)$/i);
      if (meta) {
        const key = meta[1].toLowerCase().replace(/[_ ]/g, "");
        if (key === "instrument") header.instrument = meta[2].trim();
        else if (key === "software") header.software = meta[2].trim();
        else header.analysisType = meta[2].trim().toLowerCase();
      }
      return;
    }
    const fields = (/[,;\t]/.test(line) ? line.split(/[,;\t]/) : line.split(/\s+/)).map(cell => cell.trim());
    if (/^(element|symbol|el)$/i.test(fields[0])) return;
    if (fields.length < 2 || fields.length > 3) {
      errors.push({ row, text: line, message: `Expected 2 or 3 columns (element, wt%, optional sigma), found ${fields.length}.` });
      return;
    }
    const element = normaliseSymbol(fields[0]);
    let rowFailed = false;
    if (!ELEMENT_SYMBOLS.has(element)) {
      errors.push({ row, text: line, message: `Unknown element symbol '${fields[0]}'.` });
      rowFailed = true;
    } else if (seen.has(element)) {
      errors.push({ row, text: line, message: `Duplicate element ${element} (first listed on row ${seen.get(element)}).` });
      rowFailed = true;
    }
    const weightPct = parseNumberCell(fields[1], /^$/);
    if (!Number.isFinite(weightPct)) {
      errors.push({ row, text: line, message: `wt% '${fields[1]}' is not a finite number.` });
      rowFailed = true;
    } else if (weightPct < 0) {
      errors.push({ row, text: line, message: `wt% ${weightPct} is negative.` });
      rowFailed = true;
    } else if (weightPct > 100) {
      errors.push({ row, text: line, message: `wt% ${weightPct} is above 100.` });
      rowFailed = true;
    }
    let sigmaWeightPct: number | undefined;
    if (fields.length === 3 && fields[2] !== "") {
      sigmaWeightPct = parseNumberCell(fields[2], /^(?:±|\+\/-)/);
      if (!Number.isFinite(sigmaWeightPct) || sigmaWeightPct < 0) {
        errors.push({ row, text: line, message: `Uncertainty '${fields[2]}' is not a finite non-negative number.` });
        rowFailed = true;
      }
    }
    if (rowFailed) return;
    seen.set(element, row);
    rows.push({ row, element, weightPct, ...(sigmaWeightPct !== undefined ? { sigmaWeightPct } : {}) });
  });

  if (rows.length === 0 && errors.length === 0) {
    errors.push({ row: 0, message: "The file contains no element / wt% rows." });
  }

  const instrument = (input.instrument?.trim() || header.instrument || "").trim();
  const software = (input.software?.trim() || header.software || "").trim();
  const analysisRaw = (input.analysisType || header.analysisType || "").toString().trim().toLowerCase();
  if (!instrument) errors.push({ row: 0, message: "Instrument name is required (form field or '# instrument:' header row)." });
  if (!software) errors.push({ row: 0, message: "Quantification software name is required (form field or '# software:' header row)." });
  if (analysisRaw !== "spot" && analysisRaw !== "area") {
    errors.push({ row: 0, message: "Analysis type must be 'spot' or 'area' (form field or '# analysis_type:' header row)." });
  }

  const totalWeightPct = rows.reduce((sum, entry) => sum + entry.weightPct, 0);
  if (rows.length > 0 && (totalWeightPct < VENDOR_TOTAL_WARN_MIN || totalWeightPct > VENDOR_TOTAL_WARN_MAX)) {
    warnings.push(
      `Total is ${totalWeightPct.toFixed(2)} wt%, outside ${VENDOR_TOTAL_WARN_MIN}-${VENDOR_TOTAL_WARN_MAX} wt%. ` +
      "Missing elements (for example light elements the software did not report) or a poor analysis are possible; the values are imported unchanged.",
    );
  }

  const accepted = errors.length === 0;
  const result: VendorQuantResult = {
    rows, errors, warnings, totalWeightPct, composition: {}, accepted,
  };
  if (accepted) {
    const provenance: VendorQuantProvenance = {
      fileName, sha256, instrument, software, analysisType: analysisRaw as VendorAnalysisType,
      importedAt: now.toISOString(),
    };
    result.composition = Object.fromEntries(rows.map(entry => [entry.element, entry.weightPct]));
    result.provenance = provenance;
    result.transferLabel = vendorQuantTransferLabel(provenance);
  }
  return result;
}

/** Decode, hash and parse a vendor quantification file from its exact bytes. */
export async function importVendorQuant(
  bytes: ArrayBuffer,
  fileName: string,
  input: VendorQuantMetadataInput = {},
  now: Date = new Date(),
): Promise<VendorQuantResult> {
  const sha256 = await sha256Bytes(bytes);
  const text = new TextDecoder("utf-8").decode(bytes);
  return parseVendorQuantText(text, fileName, sha256, input, now);
}
