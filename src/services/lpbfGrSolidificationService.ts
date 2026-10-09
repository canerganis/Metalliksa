/**
 * Client for the LPBF G/R solidification coupling (python/lpbf_gr_solidification.py; screening only, not validation).
 * Returns the raw JSON document: callers must pass it through checkedGrSolidification (src/data/lpbfGrSolidification.ts)
 * before rendering. Refusals (HTTP 422 / errorKind "validation") and unreachable-engine failures are thrown as typed
 * errors; nothing is retried or substituted.
 */

export type GrAlloyId = "in718" | "in625";
export type GrCellStatus = "available" | "screening-fallback" | "degenerate-floor" | "unavailable" | "error";
export type GrLocation = "bottom" | "median" | "tail";

export interface GrSolidificationRequest {
  mode: "point" | "map";
  alloyId: GrAlloyId;
  beamDiameter_um: number;
  layer_um: number;
  hatch_um: number;
  preheatTemp_C: number;
  power_W?: number;
  speed_mm_s?: number;
  powers?: number[];
  speeds?: number[];
}

export interface GrFrontLocation {
  G_K_m: number | null;
  R_m_s: number | null;
  GoverR_K_s_m2: number | null;
  GtimesR_K_s: number | null;
  huntBand: string | null;
  coolingRate_K_s?: number | null;
  x_um?: number | null;
  z_um?: number | null;
}

export interface GrRosenthalCenterline {
  status: "available" | "unavailable";
  reason: string | null;
  xTail_um?: number;
  G_K_m?: number;
  R_m_s?: number;
  GoverR_K_s_m2?: number;
  GtimesR_K_s?: number;
  label?: string;
}

export interface GrCetLocation { band: "columnar" | "mixed" | "equiaxed"; G_columnar_K_m: number; G_equiaxed_K_m: number }

export interface GrCetConstant { value: number | null; unit: string; source: string | null; locator: string | null; verified: boolean }

/** One sourced CET constant set of the registry (python/lpbf_cet_screening.py). */
export interface GrCetSet {
  id: string;
  label: string;
  transferLabel: string;
  caveat: string;
  citation: string;
  doi?: string;
  osti?: string;
  equationVerified: boolean;
  equationLocator: string | null;
  phiSource: string;
  note: string;
  constants: Record<"a" | "n" | "N0", GrCetConstant>;
}

/** Per-cell bands of one registry set. */
export interface GrCetSetBands { label: string; transferLabel: string; locations: Record<GrLocation, GrCetLocation | null> }

export interface GrLavesBand {
  R_m_s: number;
  kEff: { min: number; max: number };
  f: { min: number; max: number };
}

export interface GrLavesCell {
  status: "available" | "unavailable";
  reason: string | null;
  equilibriumKBound?: number;
  sampledArcUpperBound?: { R_m_s: number; V_D_m_s: number; kEff: number; f: number; location: GrLocation };
  atMedian?: GrLavesBand | null;
  atTail?: GrLavesBand | null;
  note?: string;
}

export interface GrCellBody {
  status: GrCellStatus;
  reason: string | null;
  regime: string | null;
  regimeNote: string | null;
  normalizedEnthalpy: number | null;
  extentStatus: string | null;
  front: {
    median: GrFrontLocation | null;
    bottom: GrFrontLocation | null;
    tail: GrFrontLocation | null;
    R_range_m_s: number[] | null;
    frontPointCount: number | null;
    gradientSource: string | null;
    usedFieldMap: boolean | null;
    coolingBasis: string;
  };
  rosenthalCenterline: GrRosenthalCenterline;
  morphology: { basis: string; bands: Record<GrLocation, string | null>; label: string };
  cet: {
    status: "available" | "unavailable";
    reason: string | null;
    locations: Record<GrLocation, GrCetLocation | null>;
    sets: Record<string, GrCetSetBands>;
  };
  laves: GrLavesCell;
}

export interface GrCell extends GrCellBody { iP: number; iV: number; power_W: number; speed_mm_s: number }
export interface GrPoint extends GrCellBody { power_W: number; speed_mm_s: number }

export interface GrSolidificationResponse {
  success: true;
  engine: string;
  schema: string;
  mode: "point" | "map";
  alloyId: GrAlloyId;
  materialName: string;
  request: { alloyId: GrAlloyId; beamDiameter_um: number; layer_um: number; hatch_um: number; preheatTemp_C: number; power_W?: number; speed_mm_s?: number };
  grid?: {
    powers_W: number[];
    speeds_mm_s: number[];
    nP: number;
    nV: number;
    nCells: number;
    rangeBasis: Record<string, unknown>;
  };
  point?: GrPoint;
  cells?: GrCell[];
  counts: Record<GrCellStatus, number>;
  cet: {
    modelId: string;
    equation: string;
    equationVerified: boolean;
    equationLocator: string | null;
    phiColumnar: number;
    phiEquiaxed: number;
    note: string;
    transferLabel?: string;
    constantsStatus: {
      status: "available" | "unavailable";
      reason: string | null;
      sets: GrCetSet[];
      candidateSources: Array<{ citation: string; osti?: string; read: boolean }>;
      referenceOnly?: { label: string; source: string; locator: string; constants: Record<"a" | "n" | "N0", GrCetConstant> };
    };
  };
  laves: {
    modelId: string;
    k_e: number;
    C_e_wt: number;
    Nb_nominal_wt: number;
    V_D_m_s: number[];
    equilibriumKBound: number;
    basis: string;
  };
  materialEvidence: Record<string, unknown> | null;
  evidence: { kind: "screening-only"; experimentalValidation: false; statement: string };
  limits: string[];
  provenance: { heatSource: string; solidificationModelId: string; buildJobSolverRevision: string; frozenFilesModified: boolean };
  computeMs: number;
}

/** kind "validation": the engine refused the request (HTTP 422); "engine-unavailable": no usable answer. */
export class GrSolidificationRequestError extends Error {
  readonly kind: "validation" | "engine-unavailable";
  readonly status: number | null;
  constructor(kind: "validation" | "engine-unavailable", status: number | null, message: string) {
    super(message);
    this.name = "GrSolidificationRequestError";
    this.kind = kind;
    this.status = status;
  }
}

export async function runGrSolidification(req: GrSolidificationRequest, signal?: AbortSignal): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch("/api/python/lpbf-gr-solidification", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new GrSolidificationRequestError("engine-unavailable", null, err instanceof Error ? err.message : "Network request failed.");
  }
  let body: any = null;
  try { body = await res.json(); } catch { /* body not JSON */ }
  if (!res.ok) {
    const detail = typeof body?.error === "string" ? body.error : `HTTP ${res.status}`;
    throw new GrSolidificationRequestError(body?.errorKind === "validation" ? "validation" : "engine-unavailable", res.status, detail);
  }
  if (body === null || typeof body !== "object") {
    throw new GrSolidificationRequestError("engine-unavailable", res.status, "The engine returned a non-JSON response.");
  }
  if (body.success !== true) {
    throw new GrSolidificationRequestError(body.errorKind === "validation" ? "validation" : "engine-unavailable", res.status,
      typeof body.error === "string" ? body.error : "The engine returned a failure without a reason.");
  }
  return body;
}
