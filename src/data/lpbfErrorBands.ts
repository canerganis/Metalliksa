/// <reference types="vite/client" />
/**
 * Published-track error bands of the frozen LPBF melt-pool screening kernels: the TypeScript reader and wording of
 * `python/lpbf_error_bands.py` (REPORTING ONLY; SCREENING ONLY; NOT VALIDATION).
 *
 * The data is the small summary written next to the committed, hashed artefact
 * (`data/calibration/lpbf-meltpool-error-bands-v1.summary.json`; `python/tools/lpbf_error_bands.py --check` fails when
 * it drifts, and `tests/lpbf-error-bands.test.tsx` fails when its implementation hash is not the pinned fingerprint).
 *
 * Honesty rules kept here:
 * - the number a surface shows is never changed; no band is derived for D/W or L/W; no label, verdict or gate reads a band;
 * - the sentence always carries n, the sources, the per-source median errors and the measured held-out coverage, and
 *   never a bare "+/- x %": the band is a 10-90 % range of the published-track error, and the leave-one-source-out
 *   coverage shows it does not transfer between sources;
 * - when the summary is absent nothing is rendered (no greyed placeholder: that would itself be a claim);
 * - `bandSentence` is a port of `band_sentence` and is pinned to the same golden fixture
 *   (`tests/fixtures/lpbf-error-band-sentences.json`).
 */

export const BAND_STATES = ["band", "band-under-covers", "insufficient-data"] as const;
export type BandState = (typeof BAND_STATES)[number];
export type BandQuantity = "depth" | "width";
export type BandRegime = "conduction" | "transition" | "keyhole" | "all";

/** Maintainer-approved wording (2026-10-07); identical to LABEL_LINE in python/lpbf_error_bands.py. */
export const BAND_LABEL_LINE = "Screening only · typical published-data error shown; transfer to another lab not established";

export interface BandEnvelope {
  readonly laserPower_W: readonly [number, number];
  readonly scanSpeed_mm_s: readonly [number, number];
  readonly beamDiameter_um: readonly [number, number];
}

export interface BandCell {
  readonly quantity: BandQuantity;
  readonly kernel: string;
  readonly family: string;
  readonly regime: BandRegime;
  readonly alloys: readonly string[];
  readonly n: number;
  readonly nSets: number;
  readonly nSources: number;
  readonly sources: readonly string[];
  readonly rowsPerSource: Readonly<Record<string, number>>;
  readonly nBalling: number;
  readonly sentinelOnly: boolean;
  readonly digitizedSources: readonly string[];
  readonly eligible: boolean;
  readonly state: BandState;
  readonly median: number;
  readonly p10: number;
  readonly p90: number;
  readonly sourceMedian: Readonly<Record<string, number>>;
  readonly loso: { readonly coverageEqualWeight: number; readonly coveragePooled: number; readonly coverageBySource: Readonly<Record<string, number>> } | null;
  readonly widened: { readonly p10: number; readonly p90: number; readonly informative: boolean; readonly sdLeak: boolean; readonly coverageEqualWeight: number } | null;
  readonly envelope: BandEnvelope;
}

export interface BandSource {
  readonly source: string;
  readonly name: string;
  readonly materials: readonly string[];
  readonly doi: string | null;
  readonly role: string | null;
  readonly digitized: boolean;
  readonly sentinel: boolean;
  readonly rows: number;
}

export interface ErrorBandsSummary {
  readonly bandsId: string;
  readonly contentSha256: string;
  readonly implementationHash: string;
  readonly generatedAt: string;
  readonly labelLine: string;
  readonly config: {
    readonly thresholds: readonly [number, number];
    readonly coverageFloor: number;
    readonly nominalCoverage: number;
    readonly notInformativeRatio: number;
    readonly families: Readonly<Record<string, string>>;
    readonly sourceNames: Readonly<Record<string, string>>;
    readonly digitizedSources: readonly string[];
    readonly sentinelSources: readonly string[];
  };
  readonly sources: readonly BandSource[];
  readonly cells: readonly BandCell[];
}

let modules: Record<string, unknown> = {};
try {
  modules = import.meta.glob("../../data/calibration/lpbf-meltpool-error-bands-v1.summary.json", { eager: true, import: "default" });
} catch {
  modules = {};
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStrArr = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === "string");
const isPair = (v: unknown): v is [number, number] => Array.isArray(v) && v.length === 2 && isNum(v[0]) && isNum(v[1]);

function parseCell(raw: unknown): BandCell | null {
  if (!isObj(raw)) return null;
  const c = raw;
  if ((c.quantity !== "depth" && c.quantity !== "width") || typeof c.kernel !== "string" || typeof c.family !== "string") return null;
  if (!["conduction", "transition", "keyhole", "all"].includes(c.regime as string)) return null;
  if (!(BAND_STATES as readonly unknown[]).includes(c.state)) return null;
  if (!isStrArr(c.alloys) || !isStrArr(c.sources) || !isStrArr(c.digitizedSources) || !isNum(c.n) || !isNum(c.nSources)) return null;
  if (!isObj(c.sourceMedian) || !isObj(c.rowsPerSource) || !isObj(c.envelope)) return null;
  const env = c.envelope;
  if (!isPair(env.laserPower_W) || !isPair(env.scanSpeed_mm_s) || !isPair(env.beamDiameter_um)) return null;
  for (const s of c.sources) if (!isNum((c.sourceMedian as Record<string, unknown>)[s])) return null;
  if (!isNum(c.median) || !isNum(c.p10) || !isNum(c.p90)) return null;
  if (c.state !== "insufficient-data") {
    const loso = c.loso;
    if (!isObj(loso) || !isNum(loso.coverageEqualWeight)) return null;
  }
  return c as unknown as BandCell;
}

/** Validates the summary. Anything that is not a screening-only, non-validating, unpromoted summary is refused. */
export function summarizeErrorBands(raw: unknown): ErrorBandsSummary | null {
  if (!isObj(raw)) return null;
  const s = raw;
  if (s.schema !== "lpbf-meltpool-error-bands-summary-1" || s.evidenceKind !== "screening-only") return null;
  if (s.experimentalValidation !== false || s.labelPromotionProposed !== "none") return null;
  if (typeof s.bandsId !== "string" || typeof s.contentSha256 !== "string" || typeof s.implementationHash !== "string") return null;
  if (typeof s.labelLine !== "string" || s.labelLine !== BAND_LABEL_LINE) return null;
  if (!isObj(s.config) || !Array.isArray(s.cells) || !Array.isArray(s.sources)) return null;
  const cfg = s.config;
  if (!isPair(cfg.thresholds) || !isNum(cfg.coverageFloor) || !isNum(cfg.nominalCoverage) || !isNum(cfg.notInformativeRatio)
    || !isObj(cfg.families) || !isObj(cfg.sourceNames) || !isStrArr(cfg.digitizedSources) || !isStrArr(cfg.sentinelSources)) return null;
  const cells: BandCell[] = [];
  for (const rc of s.cells) {
    const cell = parseCell(rc);
    if (!cell) return null;
    cells.push(cell);
  }
  return {
    bandsId: s.bandsId, contentSha256: s.contentSha256, implementationHash: s.implementationHash,
    generatedAt: typeof s.generatedAt === "string" ? s.generatedAt : "", labelLine: s.labelLine,
    config: cfg as unknown as ErrorBandsSummary["config"], sources: s.sources as BandSource[], cells,
  };
}

export const COMMITTED_ERROR_BANDS: ErrorBandsSummary | null = summarizeErrorBands(Object.values(modules)[0]);

// ---------------------------------------------------------------------------------------------
// lookup
// ---------------------------------------------------------------------------------------------
/** Screening regime class of an input from its normalised enthalpy at the default absorptivity (thresholds 15 / 30). */
export function bandRegimeClass(enthalpy: number, thresholds: readonly [number, number] = [15, 30]): "conduction" | "transition" | "keyhole" {
  return enthalpy < thresholds[0] ? "conduction" : enthalpy < thresholds[1] ? "transition" : "keyhole";
}

/** The alloy-family cell for (kernel, alloy, regime class of the input, quantity), or null. */
export function bandFor(
  summary: ErrorBandsSummary | null, kernel: string, material: string, regime: BandRegime, quantity: BandQuantity,
): BandCell | null {
  if (!summary) return null;
  const family = summary.config.families[material];
  if (!family) return null;
  return summary.cells.find((c) => c.kernel === kernel && c.family === family && c.regime === regime && c.quantity === quantity) ?? null;
}

// ---------------------------------------------------------------------------------------------
// wording (port of band_sentence / band_short; golden fixture shared with the Python test)
// ---------------------------------------------------------------------------------------------
const roundHalfUp = (x: number): number => Math.floor(Math.abs(x) + 0.5) * (x >= 0 ? 1 : -1);
const signed = (n: number): string => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : "0");
export const fmtPct = (rel: number): string => signed(roundHalfUp(rel * 100));
export const fmtCov = (cov: number): string => String(roundHalfUp(cov * 100));

export function bandSourceLabel(source: string, cell: Pick<BandCell, "digitizedSources">, summary?: ErrorBandsSummary | null): string {
  const names = summary?.config.sourceNames ?? DEFAULT_SOURCE_NAMES;
  let name = names[source] ?? source;
  if (cell.digitizedSources.includes(source)) name += " (digitized)";
  if ((summary?.config.sentinelSources ?? ["nist-amb2022-03"]).includes(source)) name += " (catalog sentinel)";
  return name;
}

const DEFAULT_SOURCE_NAMES: Readonly<Record<string, string>> = {
  "hofmann-316l-2026": "Hofmann", "ku-leuven-316l-2021": "KU Leuven", "ku-leuven-ti64-2021": "KU Leuven",
  "trapp-316l-2017": "Trapp", "totis-ti64-2021": "Totis", "ghosh-in625-2018": "Ghosh", "lane-in625-2020": "Lane",
  "nist-amb2022-03": "NIST AMB2022-03",
};

const perSource = (cell: BandCell, summary?: ErrorBandsSummary | null): string =>
  cell.sources.map((s) => `${bandSourceLabel(s, cell, summary)} ${fmtPct(cell.sourceMedian[s])} %`).join(", ");

export interface BandInputs { readonly laserPower_W?: number; readonly scanSpeed_mm_s?: number; readonly beamDiameter_um?: number }

export function bandOutsideEnvelope(cell: BandCell, inputs?: BandInputs | null): boolean {
  if (!inputs) return false;
  const pairs: Array<[number | undefined, readonly [number, number]]> = [
    [inputs.laserPower_W, cell.envelope.laserPower_W], [inputs.scanSpeed_mm_s, cell.envelope.scanSpeed_mm_s],
    [inputs.beamDiameter_um, cell.envelope.beamDiameter_um]];
  return pairs.some(([v, [lo, hi]]) => typeof v === "number" && Number.isFinite(v) && !(lo <= v && v <= hi));
}

/** The display sentence of the three states (band / band-under-covers / insufficient-data). Never a bare +/- x %. */
export function bandSentence(
  cell: BandCell | null, valueUm: number, quantity: BandQuantity, inputs?: BandInputs | null,
  opts: { material?: string | null; summary?: ErrorBandsSummary | null; nominalCoverage?: number } = {},
): string {
  const nominal = fmtCov(opts.summary?.config.nominalCoverage ?? opts.nominalCoverage ?? 0.8);
  const head = `${quantity} ≈ ${roundHalfUp(valueUm)} µm`;
  let body: string;
  if (cell === null || cell.state === "insufficient-data") {
    const n = cell === null ? 0 : cell.n;
    const k = cell === null ? 0 : cell.nSources;
    body = `published-track error: insufficient data (${k} source${k === 1 ? "" : "s"}, ${n} rows`;
    if (cell !== null && cell.sources.length > 0) body += `: ${perSource(cell, opts.summary)} median`;
    body += ")";
  } else {
    const lo = fmtPct(cell.p10);
    const hi = fmtPct(cell.p90);
    const med = fmtPct(cell.median);
    const cov = fmtCov(cell.loso?.coverageEqualWeight ?? 0);
    const nb = `${cell.n} rows, ${cell.nSources} sources`;
    if (cell.state === "band") {
      body = `typical error on published tracks, 10–90 % range ${lo} / ${hi} % (median ${med} %; ${nb}; per-source median error ${perSource(cell, opts.summary)}; a held-out source fell inside the band ${cov} % of the time, nominal ${nominal} %)`;
    } else {
      const w = cell.widened;
      const wide = w && w.informative
        ? `Widened by the between-source spread: ${fmtPct(w.p10)} / ${fmtPct(w.p90)} %.`
        : "No informative bound from published data.";
      body = `published-track error 10–90 % range ${lo} / ${hi} % (median ${med} %; ${nb}) — this band does NOT transfer between sources: a held-out source fell inside only ${cov} % of the time (nominal ${nominal} %); per-source median error ${perSource(cell, opts.summary)}. ${wide} Only measurements on your own machine can bound this.`;
    }
  }
  const material = opts.material;
  if (cell !== null && material && cell.alloys.length > 0 && !(cell.alloys.length === 1 && cell.alloys[0] === material)) {
    body += ` Pooled alloys in this cell: ${cell.alloys.join(", ")}.`;
  }
  let out = `${head} · ${body}`;
  if (cell !== null && bandOutsideEnvelope(cell, inputs)) out += " · input outside the published range of this cell";
  return `${out} · ${BAND_LABEL_LINE}`;
}

/** Tile-sized form; the full sentence is the visible detail and the tooltip. */
export function bandShort(cell: BandCell | null, quantity: BandQuantity): string {
  const tag = quantity === "depth" ? "D" : "W";
  if (cell === null || cell.state === "insufficient-data") {
    return `${tag} err. n/a (${cell === null ? 0 : cell.nSources} src, ${cell === null ? 0 : cell.n} rows)`;
  }
  return `${tag} err. ${fmtPct(cell.p10)}/${fmtPct(cell.p90)} % (cov ${fmtCov(cell.loso?.coverageEqualWeight ?? 0)} %)`;
}

// ---------------------------------------------------------------------------------------------
// from a thermal-solver result (Build Job, Melt Pool lab, process-window cell)
// ---------------------------------------------------------------------------------------------
export interface BandSubject {
  readonly material: string;
  readonly kernel: string;
  readonly enthalpy: number;
  readonly inputs: BandInputs;
  readonly width_um: number | null;
  readonly depth_um: number | null;
}

export interface BandDisplay {
  readonly quantity: BandQuantity;
  readonly value_um: number;
  readonly cell: BandCell | null;
  readonly state: BandState;
  readonly short: string;
  readonly sentence: string;
}

/** Subject from a PythonLPBFResult-shaped object; null unless the melt-pool extent was computed (an unresolved extent carries no number). */
export function bandSubjectFromThermal(t: {
  material?: string;
  processParameters?: { heatSource?: string; normalizedEnthalpy?: number | null; laserPower_W?: number; scanSpeed_mm_s?: number; beamDiameter_um?: number };
  meltPoolGeometry?: { width_um?: number | null; depth_um?: number | null; extentStatus?: string | null };
} | null | undefined): BandSubject | null {
  if (!t || !t.material || !t.processParameters || !t.meltPoolGeometry) return null;
  const pp = t.processParameters;
  if (t.meltPoolGeometry.extentStatus !== "computed" || typeof pp.heatSource !== "string" || !isNum(pp.normalizedEnthalpy)) return null;
  return {
    material: t.material, kernel: pp.heatSource, enthalpy: pp.normalizedEnthalpy,
    inputs: { laserPower_W: pp.laserPower_W, scanSpeed_mm_s: pp.scanSpeed_mm_s, beamDiameter_um: pp.beamDiameter_um },
    width_um: isNum(t.meltPoolGeometry.width_um) ? t.meltPoolGeometry.width_um : null,
    depth_um: isNum(t.meltPoolGeometry.depth_um) ? t.meltPoolGeometry.depth_um : null,
  };
}

/** Registry alloy id of the process-window / optimizer engines -> the material name the bands are keyed by. */
export const BAND_MATERIAL_OF_ALLOY_ID: Readonly<Record<string, string>> = {
  ss316l: "316L Stainless Steel", ti6al4v: "Ti-6Al-4V", in718: "Inconel 718", alsi10mg: "AlSi10Mg",
};

/** Kernel id of an engine model id such as "rosenthal-screening-v1", "eagar-tsai-v2" or "goldak-half-space-v3"; null when unknown. */
export function bandKernelOfModelId(modelId: string | null | undefined): string | null {
  const id = (modelId ?? "").toLowerCase();
  if (id.startsWith("rosenthal")) return "rosenthal";
  if (id.startsWith("eagar-tsai")) return "eagar-tsai";
  if (id.startsWith("goldak")) return "goldak";
  return null;
}

/** Subject of one process-window cell (null unless its melt-pool extent was computed and the engine model is a known kernel). */
export function bandSubjectFromProcessWindowCell(
  cell: { power_W: number; speed_mm_s: number; extentStatus: string | null; normalizedEnthalpy: number | null; width_um: number | null; depth_um: number | null },
  context: { alloyId: string; modelId: string | null | undefined; beamDiameter_um: number },
): BandSubject | null {
  const material = BAND_MATERIAL_OF_ALLOY_ID[context.alloyId];
  const kernel = bandKernelOfModelId(context.modelId);
  if (!material || !kernel || cell.extentStatus !== "computed" || !isNum(cell.normalizedEnthalpy)) return null;
  return {
    material, kernel, enthalpy: cell.normalizedEnthalpy,
    inputs: { laserPower_W: cell.power_W, scanSpeed_mm_s: cell.speed_mm_s, beamDiameter_um: context.beamDiameter_um },
    width_um: isNum(cell.width_um) ? cell.width_um : null, depth_um: isNum(cell.depth_um) ? cell.depth_um : null,
  };
}

/** Width and depth displays for one subject; empty when the summary is absent (nothing is rendered then). */
export function bandDisplays(summary: ErrorBandsSummary | null, subject: BandSubject | null): BandDisplay[] {
  if (!summary || !subject) return [];
  const regime = bandRegimeClass(subject.enthalpy, summary.config.thresholds);
  const out: BandDisplay[] = [];
  for (const quantity of ["depth", "width"] as const) {
    const value = quantity === "depth" ? subject.depth_um : subject.width_um;
    if (value === null) continue;
    const cell = bandFor(summary, subject.kernel, subject.material, regime, quantity);
    out.push({
      quantity, value_um: value, cell, state: cell ? cell.state : "insufficient-data", short: bandShort(cell, quantity),
      sentence: bandSentence(cell, value, quantity, subject.inputs, { material: subject.material, summary }),
    });
  }
  return out;
}

/** Sources of a cell with ids and DOIs from the artefact (run report block). */
export function bandSourcesOf(summary: ErrorBandsSummary, cell: BandCell): Array<{ id: string; name: string; doi: string | null; rows: number }> {
  return cell.sources.map((id) => {
    const info = summary.sources.find((s) => s.source === id);
    return { id, name: bandSourceLabel(id, cell, summary), doi: info?.doi ?? null, rows: cell.rowsPerSource[id] ?? 0 };
  });
}

// ---------------------------------------------------------------------------------------------
// run report block (hashed with the dossier)
// ---------------------------------------------------------------------------------------------
export const BAND_REPORT_STATEMENT =
  "Bands describe published single tracks; they are not a tolerance and not validation (experimentalValidation false).";

export interface PublishedTrackBandsReport {
  readonly bandsId: string;
  readonly contentSha256: string;
  readonly implementationHash: string;
  readonly kernel: string;
  readonly material: string;
  readonly regime: string;
  readonly evidenceKind: "screening-only";
  readonly experimentalValidation: false;
  readonly statement: string;
  readonly entries: ReadonlyArray<{
    readonly quantity: BandQuantity;
    readonly value_um: number;
    readonly state: BandState;
    readonly cell: string | null;
    readonly sentence: string;
    readonly sources: ReadonlyArray<{ id: string; name: string; doi: string | null; rows: number }>;
  }>;
}

/** The "Published-track error bands" block of the run report; null when the summary is absent or no band applies (nothing is invented). */
export function publishedTrackBandsReport(summary: ErrorBandsSummary | null, subject: BandSubject | null): PublishedTrackBandsReport | null {
  const displays = bandDisplays(summary, subject);
  if (!summary || !subject || displays.length === 0) return null;
  return {
    bandsId: summary.bandsId, contentSha256: summary.contentSha256, implementationHash: summary.implementationHash,
    kernel: subject.kernel, material: subject.material, regime: bandRegimeClass(subject.enthalpy, summary.config.thresholds),
    evidenceKind: "screening-only", experimentalValidation: false, statement: BAND_REPORT_STATEMENT,
    entries: displays.map((d) => ({
      quantity: d.quantity, value_um: d.value_um, state: d.state,
      cell: d.cell ? `${d.cell.kernel} / ${d.cell.family} / ${d.cell.regime}` : null,
      sentence: d.sentence, sources: d.cell ? bandSourcesOf(summary, d.cell) : [],
    })),
  };
}
