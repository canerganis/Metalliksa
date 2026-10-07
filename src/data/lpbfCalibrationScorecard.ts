/**
 * Typed, read-only loader for the Python-generated LPBF calibration scorecard view record
 * (docs/LPBF_CALIBRATION_SCORECARD_<date>.view.json, schema "lpbf-calibration-scorecard-view-1").
 *
 * Python is the result authority (python/tools/lpbf_calibration_fit.py): every number the scorecard shows
 * (held-out errors, skill intervals, coverage, fitted parameters, confusion matrices, the Guo N01 sentinel) is read
 * from that JSON. This module validates shape and honesty flags only; it computes no physics and no statistics.
 * It is a held-out calibration scorecard of nuisance parameters, not experimental validation.
 */

export const LPBF_CALIBRATION_SCORECARD_SCHEMA = "lpbf-calibration-scorecard-view-1";

export type GateStatus = "enabled" | "within-source-only" | "rejected" | "no-data";
export const GATE_STATUSES: readonly GateStatus[] = ["enabled", "within-source-only", "rejected", "no-data"];

export interface ScorecardInterval {
  readonly coverage: number | null;
  readonly k: number;
  readonly n: number;
  readonly wilson95: readonly [number, number] | null;
}

export interface ScorecardP2Row {
  readonly heldOut: string;
  readonly trainedOn: readonly string[];
  readonly rung: string;
  readonly nRows: number;
  readonly nSets: number;
  readonly mapeDefault: number | null;
  readonly mapeServed: number | null;
  readonly skill: number | null;
  readonly skillCi95: readonly [number, number] | null;
  readonly verdictVsDefault?: string;
  readonly unresolvedDefault: number;
  readonly unresolvedServed: number;
  readonly coverage90: ScorecardInterval | null;
  readonly widthRatio90?: number | null;
  readonly intervalNotInformative90?: boolean | null;
  readonly mapePowerlaw?: number | null;
  readonly verdictVsPowerlaw?: string | null;
  /** v2 records: "trainable fold" or "test-only" (scored with the alloy's final served fit, never trained). */
  readonly role?: string | null;
  /** v2 records: the nuisance reading of a test-only source (e.g. assumed spot size), "stated" when none. */
  readonly reading?: string | null;
}

export interface ScorecardP1Row {
  readonly source: string;
  readonly nRows: number;
  readonly nSets: number;
  readonly skill: number | null;
  readonly skillCi95: readonly [number, number] | null;
  readonly mapeDefault: number | null;
  readonly mapeServed: number | null;
}

export interface ScorecardParams {
  readonly etaW?: number | null;
  readonly etaD?: number | null;
  readonly etaJoint?: number | null;
  readonly etaW_ci90?: readonly [number, number] | null;
  readonly etaD_ci90?: readonly [number, number] | null;
  readonly etaJoint_ci90?: readonly [number, number] | null;
  readonly cD?: Readonly<Record<string, number>> | null;
  readonly boundHitFractionW?: number | null;
  readonly boundHitFractionD?: number | null;
  readonly etaPrior?: number | null;
}

export interface ScorecardHeadlineRow {
  readonly kernel: string;
  readonly material: string;
  readonly quantity: "width" | "depth";
  readonly status: GateStatus;
  readonly reasons: readonly string[];
  readonly servedRung: string | null;
  readonly flags: readonly string[];
  readonly flagNotes: readonly string[];
  /** Diagnostics are computed for every fitted cell; false = shown only, the served rung is `default`. */
  readonly gateRelevant?: boolean;
  readonly diagnostics?: {
    readonly boundHitBootstrapFraction?: number | null;
    readonly etaSplitLn?: number | null;
    readonly maxAbsCd?: number | null;
    readonly absorptanceMismatch?: readonly { readonly class: string; readonly eta: number; readonly band: readonly number[] }[] | null;
  };
  readonly headline: {
    readonly equalSourceWeight: { readonly mapeDefault: number | null; readonly mapeServed: number | null };
    readonly rowWeighted: { readonly mapeDefault: number | null; readonly mapeServed: number | null };
  } | null;
  readonly p2: readonly ScorecardP2Row[];
  readonly p1: readonly ScorecardP1Row[];
  readonly params: ScorecardParams | null;
  readonly beamStatuses?: Readonly<Record<string, string>> | null;
  /** v2 records only. */
  readonly v1Status?: GateStatus | null;
  readonly statusTrainableOnly?: GateStatus | null;
  readonly readingStatuses?: Readonly<Record<string, string>> | null;
}

export interface ScorecardVersionComparisonRow {
  readonly kernel: string;
  readonly material: string;
  readonly quantity: string;
  readonly v1: GateStatus | null;
  readonly v2TrainableOnly: GateStatus;
  readonly v2: GateStatus;
  readonly changed: boolean;
}

export interface ScorecardConfusion {
  readonly labels: readonly string[];
  readonly matrix: Readonly<Record<string, Readonly<Record<string, number>>>>;
  readonly n: number;
  readonly accuracy: number | null;
  readonly keyholeOnly: {
    readonly tp: number; readonly fp: number; readonly fn: number; readonly tn: number;
    readonly precision: number | null; readonly recall: number | null;
  };
}

export interface ScorecardN01Rung {
  readonly width_um: number | null;
  readonly depth_um: number | null;
  readonly widthFactor: number | null;
  readonly depthFactor: number | null;
  readonly insideFactor2: boolean;
  readonly depthInsideFactor2: boolean;
}

export interface ScorecardN01 {
  readonly kernel: string;
  readonly measured: { readonly width_um: number; readonly depth_um: number };
  readonly rungs: Readonly<Record<string, ScorecardN01Rung>>;
  readonly statement: string;
}

export interface ScorecardSource {
  readonly source: string;
  readonly role: string;
  readonly material: string;
  readonly rowsUsed: number;
  readonly parameterSets: number;
  readonly doi?: string | null;
  readonly tableSha256?: string | null;
}

export interface ScorecardCoverageRow {
  readonly kernel: string;
  readonly material: string;
  readonly quantity: string;
  readonly heldOut: string;
  readonly level: number;
  readonly k: number;
  readonly n: number;
  readonly coverage: number | null;
  readonly wilson95: readonly [number, number] | null;
  readonly widthRatio?: number | null;
  readonly notInformative?: boolean | null;
}

export interface ScorecardUnresolvedRow {
  readonly kernel: string;
  readonly source: string;
  readonly role: string;
  readonly rowsUsed: number;
  readonly resolvedAtDefault: number;
  readonly unresolvedAtDefault: number;
  readonly statusAtDefault: Readonly<Record<string, number>>;
}

export interface LpbfCalibrationScorecardDocument {
  readonly schema: typeof LPBF_CALIBRATION_SCORECARD_SCHEMA;
  readonly generatedAt: string;
  readonly implementationHash: string;
  readonly configSha256: string;
  readonly quick?: boolean;
  readonly evidence: {
    readonly kind: "screening-only";
    readonly label: string;
    readonly labelPromotionProposed: string;
    readonly experimentalValidation: false;
    readonly opticalOperatorMatched: false;
    readonly statement: string;
  };
  readonly gateSummary: Readonly<Record<string, number>>;
  readonly headline: readonly ScorecardHeadlineRow[];
  readonly sources: readonly ScorecardSource[];
  readonly regimeConfusion: {
    readonly labelSource: string;
    readonly byAlloy: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
  };
  readonly n01: readonly ScorecardN01[];
  readonly catalogSentinels: { readonly title: string; readonly note: string };
  readonly coverage: readonly ScorecardCoverageRow[];
  readonly unresolved: {
    readonly perKernelSource: readonly ScorecardUnresolvedRow[];
    readonly rule: string;
    readonly loader: readonly { readonly source: string; readonly loaderRows: number; readonly excludedByLoader: readonly { readonly rowId: string; readonly reason: string }[] }[];
    readonly notGeometrySources: readonly { readonly source: string; readonly reason: string }[];
  };
  readonly betweenSource?: Readonly<Record<string, unknown>>;
  /** Present on calibration v2 records (a new pre-registered version that supersedes v1; v1 stays committed). */
  readonly calibrationVersion?: string;
  readonly preRegistration?: { readonly doc: string; readonly config: string; readonly configCommit?: string | null; readonly statement: string };
  readonly supersedes?: { readonly record?: string | null; readonly configSha256?: string | null; readonly calibrationId?: string | null; readonly note?: string };
  readonly v1Comparison?: readonly ScorecardVersionComparisonRow[];
  readonly reproducesV1TrainableOnly?: boolean | null;
  readonly notes: readonly string[];
  readonly provenance: {
    readonly codeRevision: Readonly<Record<string, unknown>>;
    readonly tool: { readonly path: string; readonly sha256: string };
    readonly kernel: Readonly<Record<string, unknown>>;
  };
}

function fail(reason: string): never {
  throw new Error(`lpbf calibration scorecard record rejected: ${reason}`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteOrNull(value: unknown): boolean {
  return value === null || value === undefined || (typeof value === "number" && Number.isFinite(value));
}

function requireArray(value: unknown, where: string): unknown[] {
  if (!Array.isArray(value)) fail(`${where} is not an array`);
  return value;
}

function requireString(value: unknown, where: string): string {
  if (typeof value !== "string" || value.length === 0) fail(`${where} is not a non-empty string`);
  return value;
}

/** Validates a parsed view record; throws (loudly) on any malformed or dishonest field. */
export function checkedCalibrationScorecard(raw: unknown): LpbfCalibrationScorecardDocument {
  if (!isRecord(raw)) fail("not an object");
  if (raw.schema !== LPBF_CALIBRATION_SCORECARD_SCHEMA) fail(`schema ${String(raw.schema)}`);
  for (const key of ["generatedAt", "implementationHash", "configSha256", "evidence", "gateSummary", "headline", "sources",
    "regimeConfusion", "n01", "catalogSentinels", "coverage", "unresolved", "notes", "provenance"]) {
    if (!(key in raw)) fail(`missing key ${key}`);
  }
  requireString(raw.generatedAt, "generatedAt");
  requireString(raw.implementationHash, "implementationHash");
  const evidence = raw.evidence;
  if (!isRecord(evidence)) fail("evidence is not an object");
  if (evidence.kind !== "screening-only") fail("evidence.kind must be screening-only");
  if (evidence.experimentalValidation !== false) fail("evidence.experimentalValidation must be false");
  if (evidence.opticalOperatorMatched !== false) fail("evidence.opticalOperatorMatched must be false");
  requireString(evidence.statement, "evidence.statement");
  requireString(evidence.label, "evidence.label");
  requireString(evidence.labelPromotionProposed, "evidence.labelPromotionProposed");
  const headline = requireArray(raw.headline, "headline");
  for (const [i, row] of headline.entries()) {
    if (!isRecord(row)) fail(`headline[${i}] is not an object`);
    requireString(row.kernel, `headline[${i}].kernel`);
    requireString(row.material, `headline[${i}].material`);
    if (row.quantity !== "width" && row.quantity !== "depth") fail(`headline[${i}].quantity`);
    if (!GATE_STATUSES.includes(row.status as GateStatus)) fail(`headline[${i}].status ${String(row.status)}`);
    requireArray(row.reasons, `headline[${i}].reasons`);
    requireArray(row.flags, `headline[${i}].flags`);
    for (const [j, p] of requireArray(row.p2, `headline[${i}].p2`).entries()) {
      if (!isRecord(p)) fail(`headline[${i}].p2[${j}] is not an object`);
      for (const f of ["mapeDefault", "mapeServed", "skill"]) {
        if (!isFiniteOrNull(p[f])) fail(`headline[${i}].p2[${j}].${f} is not finite`);
      }
    }
    requireArray(row.p1, `headline[${i}].p1`);
  }
  const n01 = requireArray(raw.n01, "n01");
  for (const [i, n] of n01.entries()) {
    if (!isRecord(n) || !isRecord(n.rungs) || !isRecord(n.measured)) fail(`n01[${i}] is malformed`);
  }
  const summary = raw.gateSummary;
  if (!isRecord(summary)) fail("gateSummary is not an object");
  for (const [k, v] of Object.entries(summary)) {
    if (!GATE_STATUSES.includes(k as GateStatus) || typeof v !== "number") fail(`gateSummary.${k}`);
  }
  requireArray(raw.sources, "sources");
  requireArray(raw.coverage, "coverage");
  requireArray(raw.notes, "notes");
  if (!isRecord(raw.unresolved) || !Array.isArray(raw.unresolved.perKernelSource)) fail("unresolved block is malformed");
  if (!isRecord(raw.regimeConfusion) || !isRecord(raw.regimeConfusion.byAlloy)) fail("regimeConfusion is malformed");
  if (!isRecord(raw.provenance)) fail("provenance is not an object");
  if (raw.calibrationVersion !== undefined) {
    requireString(raw.calibrationVersion, "calibrationVersion");
    if (!isRecord(raw.preRegistration)) fail("a versioned record must carry its preRegistration block");
    requireString(raw.preRegistration.doc, "preRegistration.doc");
    if (!isRecord(raw.supersedes)) fail("a versioned record must say which record it supersedes");
  }
  if (raw.v1Comparison !== undefined) {
    for (const [i, row] of requireArray(raw.v1Comparison, "v1Comparison").entries()) {
      if (!isRecord(row)) fail(`v1Comparison[${i}] is not an object`);
      for (const f of ["v2TrainableOnly", "v2"]) {
        if (!GATE_STATUSES.includes(row[f] as GateStatus)) fail(`v1Comparison[${i}].${f}`);
      }
      if (row.v1 !== null && !GATE_STATUSES.includes(row.v1 as GateStatus)) fail(`v1Comparison[${i}].v1`);
    }
  }
  return raw as unknown as LpbfCalibrationScorecardDocument;
}

export function statusCounts(doc: LpbfCalibrationScorecardDocument): Record<GateStatus, number> {
  const out: Record<GateStatus, number> = { enabled: 0, "within-source-only": 0, rejected: 0, "no-data": 0 };
  for (const row of doc.headline) out[row.status] += 1;
  return out;
}
