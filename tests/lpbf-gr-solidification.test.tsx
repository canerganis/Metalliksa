import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { GrSolidificationMapCard, GrHeatmap, GrCellDetail } from "../src/components/GrSolidificationMapCard";
import {
  NO_VALUE_STYLE,
  checkedGrSolidification,
  isOutsideRegime,
  metricRange,
  metricValue,
  moveCell,
  scaleStyle,
  bandStyle,
} from "../src/data/lpbfGrSolidification";
import type { GrCell, GrSolidificationResponse } from "../src/services/lpbfGrSolidificationService";

// SYNTHETIC fixture: it exercises the validator and the view only. No number here is a model or measurement result.
const HUNT_COLUMNAR = "Columnar dendritic (Hunt G/R screening)";
const CET_REASON = "SYNTHETIC reason: no CET constants for this alloy.";

function loc(g: number, r: number) {
  return { G_K_m: g, R_m_s: r, GoverR_K_s_m2: g / r, GtimesR_K_s: g * r, huntBand: HUNT_COLUMNAR };
}

function body(status: GrCell["status"], opts: { keyhole?: boolean; g?: number } = {}) {
  const computed = status === "available";
  const g = opts.g ?? 1e7;
  const median = computed ? { ...loc(g, 0.1), coolingRate_K_s: g * 0.1 } : null;
  return {
    status,
    reason: computed ? null : "SYNTHETIC reason for a cell without a value",
    regime: opts.keyhole ? "Keyhole Mode" : "Conduction Mode",
    regimeNote: opts.keyhole ? "Keyhole Mode: outside the conduction regime of the G/R field" : null,
    normalizedEnthalpy: 10,
    extentStatus: "computed",
    front: {
      median, bottom: computed ? loc(g * 2, 0.02) : null, tail: computed ? loc(g / 2, 0.3) : null,
      R_range_m_s: computed ? [0.02, 0.3] : null, frontPointCount: 9, gradientSource: "solidification-front-v1",
      usedFieldMap: true, coolingBasis: "median of the solver's per-sample G*R (coolingRate_K_s), not G_median * R_median",
    },
    rosenthalCenterline: computed
      ? { status: "available" as const, reason: null, xTail_um: 1000, G_K_m: 9e5, R_m_s: 0.9, GoverR_K_s_m2: 1e6, GtimesR_K_s: 8e5, label: "SYNTHETIC reference" }
      : { status: "unavailable" as const, reason: "SYNTHETIC" },
    morphology: {
      basis: "hunt-g-over-r-screening",
      bands: { bottom: computed ? HUNT_COLUMNAR : null, median: computed ? HUNT_COLUMNAR : null, tail: computed ? HUNT_COLUMNAR : null },
      label: "Hunt G/R screening band (uncalibrated), not a CET prediction",
    },
    cet: { status: "unavailable" as const, reason: CET_REASON, locations: { bottom: null, median: null, tail: null }, sets: {} },
    laves: computed
      ? {
        status: "available" as const, reason: null, equilibriumKBound: 0.0647,
        sampledArcUpperBound: { R_m_s: 0.02, V_D_m_s: 0.31, kEff: 0.47, f: 0.05, location: "bottom" as const },
        atMedian: null, atTail: null, note: "SYNTHETIC laves note",
      }
      : { status: "unavailable" as const, reason: "SYNTHETIC" },
  };
}

function fixture(): GrSolidificationResponse {
  const powers = [100, 200];
  const speeds = [500, 900];
  const specs: Array<[GrCell["status"], { keyhole?: boolean; g?: number }]> = [
    ["available", { g: 1e7 }], ["available", { keyhole: true, g: 3e7 }], ["error", {}], ["unavailable", {}],
  ];
  const cells: GrCell[] = specs.map(([status, opts], i) => ({
    iP: Math.floor(i / 2), iV: i % 2, power_W: powers[Math.floor(i / 2)], speed_mm_s: speeds[i % 2], ...body(status, opts),
  }));
  return {
    success: true, engine: "lpbf_gr_solidification", schema: "lpbf-gr-solidification-1", mode: "map", alloyId: "in718",
    materialName: "Inconel 718",
    request: { alloyId: "in718", beamDiameter_um: 80, layer_um: 40, hatch_um: 110, preheatTemp_C: 80 },
    grid: { powers_W: powers, speeds_mm_s: speeds, nP: 2, nV: 2, nCells: 4, rangeBasis: {} },
    cells,
    counts: { available: 2, "screening-fallback": 0, "degenerate-floor": 0, unavailable: 1, error: 1 },
    cet: {
      modelId: "SYNTHETIC", equation: "G^n/V = a*[...]^n", equationVerified: false, equationLocator: null, phiColumnar: 0.0066,
      phiEquiaxed: 0.49, note: "SYNTHETIC",
      constantsStatus: { status: "unavailable", reason: CET_REASON, sets: [], candidateSources: [] },
    },
    laves: { modelId: "SYNTHETIC", k_e: 0.45, C_e_wt: 23.1, Nb_nominal_wt: 5.125, V_D_m_s: [0.23, 0.31], equilibriumKBound: 0.0647, basis: "SYNTHETIC" },
    materialEvidence: null,
    evidence: { kind: "screening-only", experimentalValidation: false, statement: "Screening only. SYNTHETIC statement." },
    limits: ["SYNTHETIC limit"],
    provenance: { heatSource: "rosenthal", solidificationModelId: "SYNTHETIC", buildJobSolverRevision: "SYNTHETIC", frozenFilesModified: false },
    computeMs: 1,
  };
}

const clone = (): any => JSON.parse(JSON.stringify(fixture()));

test("checkedGrSolidification accepts a valid response", () => {
  const out = checkedGrSolidification(fixture());
  assert.equal(out.cells?.length, 4);
});

test("checkedGrSolidification rejects dishonest or malformed responses", () => {
  const cases: Array<[string, (r: any) => void]> = [
    ["evidence kind", r => { r.evidence.kind = "validated"; }],
    ["experimentalValidation", r => { r.evidence.experimentalValidation = true; }],
    ["cet sets missing", r => { delete r.cells[0].cet.sets; }],
    ["unavailable cet that lists sets", r => { r.cells[0].cet.sets = { x: { label: "x", transferLabel: "t", locations: {} } }; }],
    ["cet set without transfer label", r => {
      r.cells[0].cet.status = "available"; r.cells[0].cet.reason = null;
      r.cells[0].cet.sets = { x: { label: "x", transferLabel: "", locations: {} } };
    }],
    ["constants status without sets", r => { delete r.cet.constantsStatus.sets; }],
    ["constants set without transfer label", r => {
      r.cet.constantsStatus.status = "available";
      r.cet.constantsStatus.sets = [{ id: "x", transferLabel: "", citation: "c", equationVerified: false, constants: {} }];
    }],
    ["cet status outside the set", r => { r.cells[0].cet.status = "estimated"; }],
    ["unknown cell status", r => { r.cells[0].status = "great"; }],
    ["cell count", r => { r.cells.pop(); }],
    ["counts mismatch", r => { r.counts.available = 3; }],
    ["unavailable cet without reason", r => { r.cells[0].cet.reason = null; }],
    ["position mismatch", r => { r.cells[1].iV = 0; }],
    ["not success", r => { r.success = false; }],
  ];
  for (const [name, mutate] of cases) {
    const r = clone();
    mutate(r);
    assert.throws(() => checkedGrSolidification(r), /rejected/, name);
  }
});

test("colour scale maps null to the no-value style, never the low end", () => {
  const range = { min: 1, max: 5 };
  assert.deepEqual(scaleStyle(null, range), NO_VALUE_STYLE);
  assert.deepEqual(scaleStyle(1, null), NO_VALUE_STYLE);
  assert.deepEqual(bandStyle(null), NO_VALUE_STYLE);
  assert.equal(NO_VALUE_STYLE.outlined, true);
  assert.equal(NO_VALUE_STYLE.fill, "none");
  assert.notEqual(scaleStyle(1, range).fill, "none");
  assert.notEqual(scaleStyle(1, range).fill, scaleStyle(5, range).fill);
});

test("metric values are null for cells without a computed result", () => {
  const r = fixture();
  const cells = r.cells as GrCell[];
  assert.equal(metricValue(cells[2], "goverr"), null);
  assert.equal(metricValue(cells[3], "laves"), null);
  const v = metricValue(cells[0], "goverr") as number;
  assert.ok(Math.abs(v - Math.log10(1e8)) < 1e-9);
  assert.equal(metricValue(cells[0], "laves"), 0.05);
  const range = metricRange(cells, "goverr");
  assert.ok(range && range.max > range.min);
});

test("keyhole cells carry the outside-regime marker", () => {
  const r = fixture();
  const cells = r.cells as GrCell[];
  assert.equal(isOutsideRegime(cells[1]), true);
  assert.equal(isOutsideRegime(cells[0]), false);
  const html = renderToStaticMarkup(<GrHeatmap result={r} metric="goverr" selected={null} />);
  assert.match(html, /data-testid="gr-cell-0-1"[^>]*data-outside-regime="true"/);
  assert.match(html, /data-testid="gr-cell-0-0"[^>]*data-outside-regime="false"/);
  assert.equal((html.match(/data-testid="gr-keyhole-marker"/g) ?? []).length, 1);
  // error and unavailable cells are outlined empty cells
  assert.match(html, /data-testid="gr-cell-1-0"[^>]*data-no-value="true"/);
  assert.match(html, /data-testid="gr-cell-1-1"[^>]*data-no-value="true"/);
});

test("the grid is keyboard navigable (role grid, one tab stop) and moveCell is reused", () => {
  const html = renderToStaticMarkup(<GrHeatmap result={fixture()} metric="goverr" selected={{ iP: 0, iV: 0 }} />);
  assert.match(html, /role="grid"[^>]*tabindex="0"|tabindex="0"[^>]*role="grid"/);
  assert.match(html, /role="gridcell"/);
  assert.deepEqual(moveCell({ iP: 0, iV: 0 }, "ArrowRight", 2, 2), { iP: 0, iV: 1 });
  assert.deepEqual(moveCell({ iP: 0, iV: 1 }, "ArrowRight", 2, 2), { iP: 0, iV: 1 });
});

test("the card renders the honesty banner, CET unavailability and the Hunt band wording", () => {
  const html = renderToStaticMarkup(<GrSolidificationMapCard initialResult={fixture()} />);
  assert.match(html, /Screening only/);
  assert.match(html, /CET: unavailable/);
  assert.match(html, /Hunt G\/R screening band/);
  assert.doesNotMatch(html, /predicted grain structure/i);
});

test("the card starts empty: no result and IN718 prefilled with the default 7 x 7 box", () => {
  const html = renderToStaticMarkup(<GrSolidificationMapCard />);
  assert.doesNotMatch(html, /data-testid="gr-result"/);
  assert.match(html, /value="60"/);
  assert.match(html, /value="450"/);
  assert.match(html, /Nothing runs until you click Compute/);
});

function in718CetFixture(): GrSolidificationResponse {
  const r = clone();
  const bands = (g: number) => ({
    bottom: { band: "columnar", G_columnar_K_m: g, G_equiaxed_K_m: g / 5 },
    median: { band: "columnar", G_columnar_K_m: g * 2, G_equiaxed_K_m: g / 2 },
    tail: null,
  });
  const constant = (value: number, unit: string, locator: string) => ({ value, unit, source: "SYNTHETIC", locator, verified: true });
  const set = (id: string, label: string, verified: boolean) => ({
    id, label, transferLabel: "EBM-calibrated, transferred to LPBF", caveat: "SYNTHETIC caveat about the transfer", citation: "SYNTHETIC citation",
    equationVerified: verified, equationLocator: "SYNTHETIC locator", note: "SYNTHETIC note",
    constants: { a: constant(4.5, "K^n s/m", "SYNTHETIC loc"), n: constant(2, "-", "SYNTHETIC loc"), N0: constant(2.65e14, "m^-3", "SYNTHETIC loc") },
  });
  for (const cell of r.cells) {
    if (cell.status !== "available") continue;
    cell.cet = {
      status: "available", reason: null, locations: { bottom: null, median: null, tail: null },
      sets: {
        setA: { label: "SYNTHETIC set A", transferLabel: "EBM-calibrated, transferred to LPBF", locations: bands(1e5) },
        setB: { label: "SYNTHETIC set B", transferLabel: "EBM-calibrated, transferred to LPBF", locations: bands(7e5) },
      },
    };
  }
  r.cet.equationVerified = false;
  r.cet.constantsStatus = {
    status: "available", reason: null, candidateSources: [],
    sets: [set("setA", "SYNTHETIC set A", true), set("setB", "SYNTHETIC set B", false)],
    referenceOnly: { label: "SYNTHETIC reference only", source: "S", locator: "SYNTHETIC ref locator", constants: set("r", "r", false).constants },
  };
  return r;
}

test("IN718 sets validate and the card shows both sets with source, transfer caveat and the boundary", () => {
  const r = in718CetFixture();
  checkedGrSolidification(r);
  const html = renderToStaticMarkup(<GrSolidificationMapCard initialResult={r} />);
  assert.match(html, /data-testid="gr-cet-source-setA"/);
  assert.match(html, /data-testid="gr-cet-source-setB"/);
  assert.match(html, /EBM-calibrated, transferred to LPBF/);
  assert.match(html, /SYNTHETIC caveat about the transfer/);
  assert.match(html, /SYNTHETIC citation/);
  assert.match(html, /Checked against printed limits: yes/);
  assert.match(html, /Checked against printed limits: no/);
  assert.match(html, /SYNTHETIC reference only/);
  assert.match(html, /Gäumann 2001 PDF read: no/);
  assert.match(html, /not a CET prediction/);
  const detail = renderToStaticMarkup(<GrCellDetail body={r.cells![0]} result={r} />);
  assert.match(detail, /data-testid="gr-cet-set-setA"/);
  assert.match(detail, /data-testid="gr-cet-set-setB"/);
  assert.match(detail, /columnar above G/);
  assert.match(detail, /EBM-calibrated, transferred to LPBF/);
});

test("without sets (IN625) the card shows no CET boundary and the unavailable reason", () => {
  const html = renderToStaticMarkup(<GrSolidificationMapCard initialResult={fixture()} />);
  assert.doesNotMatch(html, /columnar above G/);
  assert.doesNotMatch(html, /data-testid="gr-cet-sets"/);
  const f = fixture();
  const detail = renderToStaticMarkup(<GrCellDetail body={f.cells![0]} result={f} />);
  assert.doesNotMatch(detail, /columnar above G/);
  assert.match(detail, /CET: unavailable/);
  assert.match(html, /CET: unavailable/);
});
