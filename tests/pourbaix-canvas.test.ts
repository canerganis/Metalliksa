import assert from "node:assert/strict";
import { test } from "node:test";
import {
  CATEGORY_STYLE,
  NERNST_SLOPE_25C,
  availablePourbaixElements,
  POURBAIX_DATA,
  classifyPourbaixPoint,
  clipPolygon,
  computeDomains,
  computeWithheldRegions,
  polygonArea,
  speciesCoefficients,
  waterLines25C,
} from "../src/utils/pourbaixThermodynamics";
import { WITHHELD_HATCH, ZONE_LABEL, drawPourbaixScene, type PourbaixScene } from "../src/utils/pourbaixCanvas";
import { REF_OFFSETS_VS_SHE } from "../src/utils/experimentalPourbaixOverlay";

// The Studio only builds a scene; the drawing is a pure function, so a recording 2D context can check it
// (REVIEW-pbx-code SHOULD-FIX 5: the canvas and interaction paths were unexercised).

interface Call { op: string; args: unknown[]; fillStyle?: unknown; strokeStyle?: unknown; alpha: number }

function recorder() {
  const calls: Call[] = [];
  const state: Record<string, unknown> = { fillStyle: "", strokeStyle: "", globalAlpha: 1, lineWidth: 1, font: "" };
  const ctx = new Proxy({}, {
    get(_t, prop: string) {
      if (prop in state) return state[prop];
      if (prop === "measureText") return (s: string) => ({ width: s.length * 6 });
      return (...args: unknown[]) => { calls.push({ op: prop, args, fillStyle: state.fillStyle, strokeStyle: state.strokeStyle, alpha: state.globalAlpha as number }); };
    },
    set(_t, prop: string, value) { state[prop] = value; return true; },
  }) as unknown as CanvasRenderingContext2D;
  return { ctx, calls };
}

const W = 960, H = 600;
const BOX = POURBAIX_DATA.box;
function scene(element: string, over: Partial<PourbaixScene> = {}): PourbaixScene {
  const coeffs = speciesCoefficients(element, -6);
  const domains = computeDomains(coeffs);
  return {
    width: W, height: H,
    viewBounds: { minPH: BOX.pH_min, maxPH: BOX.pH_max, minE: BOX.E_min_V_SHE, maxE: BOX.E_max_V_SHE },
    refOffset: 0, domains, coeffs, waterLines: waterLines25C(), nernstSlope: NERNST_SLOPE_25C,
    temperature_C: 25, log10Activity: -6, probePH: 7, probePotential_SHE: 0.2,
    probedState: classifyPourbaixPoint(coeffs, 7, 0.2),
    showExperimentalOverlay: true, showTrajectoryPath: true, showPointLabels: true,
    selectedPointId: "p1",
    points: [
      { id: "p1", name: "one", stageName: "Stage one", pH: 3, she: 0.6, category: classifyPourbaixPoint(coeffs, 3, 0.6).category },
      { id: "p2", name: "two", pH: 12, she: -1.2, category: classifyPourbaixPoint(coeffs, 12, -1.2).category },
    ],
    ...over,
  };
}
const xOf = (ph: number) => ((ph - BOX.pH_min) / (BOX.pH_max - BOX.pH_min)) * W;
const yOf = (e: number, off = 0) => H - (((e - off) - BOX.E_min_V_SHE) / (BOX.E_max_V_SHE - BOX.E_min_V_SHE)) * H;

test("every canvas argument is finite and no 'NaN/undefined' string is drawn, for every available element", () => {
  for (const el of availablePourbaixElements()) {
    const { ctx, calls } = recorder();
    drawPourbaixScene(ctx, scene(el));
    assert.ok(calls.length > 100, el);
    for (const c of calls) for (const a of c.args) {
      if (typeof a === "number") assert.ok(Number.isFinite(a), `${el} ${c.op}: ${a}`);
      if (typeof a === "string") assert.ok(!/NaN|undefined|null|Infinity/.test(a), `${el} ${c.op}: ${a}`);
    }
  }
});

test("each domain polygon is filled with its category colour and alpha (a fill that is skipped leaves the map blank)", () => {
  const s = scene("Fe");
  const { ctx, calls } = recorder();
  drawPourbaixScene(ctx, s);
  const fills = calls.filter((c) => c.op === "fill" && c.alpha < 1);
  assert.equal(fills.length, s.domains.length);
  s.domains.forEach((d, i) => {
    assert.equal(fills[i].fillStyle, CATEGORY_STYLE[d.category].color);
    assert.equal(fills[i].alpha, CATEGORY_STYLE[d.category].alpha);
  });
});

test("the displayed reference electrode shifts every drawn potential: pixel y = f(E_SHE - offset); the probe readout shows the displayed value", () => {
  for (const ref of ["SHE", "SCE", "CSE"] as const) {
    const off = REF_OFFSETS_VS_SHE[ref];
    const s = scene("Fe", { refOffset: off });
    const { ctx, calls } = recorder();
    drawPourbaixScene(ctx, s);
    // first polygon, first vertex: moveTo
    const d0 = s.domains[0];
    const firstMove = calls.find((c) => c.op === "moveTo")!;
    void firstMove;
    const polyMoves = calls.filter((c) => c.op === "moveTo");
    assert.ok(polyMoves.some((m) => Math.abs((m.args[0] as number) - xOf(d0.polygon[0][0])) < 1e-9 && Math.abs((m.args[1] as number) - yOf(d0.polygon[0][1], off)) < 1e-9), `${ref} polygon vertex y`);
    // probe circle at (xOf(7), yOf(0.2, off)) with radius 7
    const probe = calls.find((c) => c.op === "arc" && c.args[2] === 7)!;
    assert.ok(Math.abs((probe.args[0] as number) - xOf(7)) < 1e-9 && Math.abs((probe.args[1] as number) - yOf(0.2, off)) < 1e-9, `${ref} probe`);
    const readout = calls.find((c) => c.op === "fillText" && String(c.args[0]).startsWith("pH: 7.00"))!;
    assert.equal(readout.args[0], `pH: 7.00 | E: ${(0.2 - off).toFixed(3)}V`);
    // a test point marker
    const markers = calls.filter((c) => c.op === "arc" && (c.args[2] === 8 || c.args[2] === 10));
    assert.ok(markers.some((m) => Math.abs((m.args[1] as number) - yOf(0.6, off)) < 1e-9), `${ref} marker y`);
  }
});

test("test-point markers carry the category colour of the point in the drawn map, the selected one is larger with a halo", () => {
  const s = scene("Fe");
  const { ctx, calls } = recorder();
  drawPourbaixScene(ctx, s);
  const markers = calls.filter((c) => c.op === "arc" && (c.args[2] === 8 || c.args[2] === 10));
  assert.equal(markers.length, 2);
  s.points.forEach((p, i) => {
    const fill = calls.find((c, k) => c.op === "fill" && calls[k - 1]?.op === "arc" && calls[k - 1].args[0] === markers[i].args[0] && c.fillStyle === CATEGORY_STYLE[p.category!].color);
    assert.ok(fill, `marker ${p.id} colour`);
  });
  assert.equal(markers[0].args[2], 10); // selected
  assert.equal(markers[1].args[2], 8);
  assert.ok(calls.some((c) => c.op === "arc" && c.args[2] === 22), "selection halo");
  // no map: neutral colour, no throw
  const { ctx: c2, calls: calls2 } = recorder();
  drawPourbaixScene(c2, scene("Fe", { coeffs: null, domains: [], probedState: null, points: s.points.map((p) => ({ ...p, category: null })) }));
  assert.ok(calls2.some((c) => c.op === "fillText" && c.args[0] === "No verified data"));
});

test("zone labels: exactly the domains whose view-clipped area exceeds the threshold are labelled, at the polygon centroid", () => {
  for (const el of ["Fe", "Zn", "Al"]) {
    const s = scene(el);
    const { ctx, calls } = recorder();
    drawPourbaixScene(ctx, s);
    const pxPerPhE = (W / (BOX.pH_max - BOX.pH_min)) * (H / (BOX.E_max_V_SHE - BOX.E_min_V_SHE));
    const expected = s.domains.filter((d) => {
      let poly = d.polygon;
      poly = clipPolygon(poly, -1, 0, BOX.pH_min); poly = clipPolygon(poly, 1, 0, -BOX.pH_max);
      poly = clipPolygon(poly, 0, -1, BOX.E_min_V_SHE); poly = clipPolygon(poly, 0, 1, -BOX.E_max_V_SHE);
      return poly.length >= 3 && polygonArea(poly) * pxPerPhE >= 3000 /* px^2, the documented label threshold */;
    });
    const labels = calls.filter((c) => c.op === "fillText" && Object.values(ZONE_LABEL).includes(c.args[0] as string));
    assert.equal(labels.length, expected.length, el);
    assert.ok(expected.length >= 3 && expected.length < s.domains.length + 1, `${el}: ${expected.length} labelled of ${s.domains.length}`);
    expected.forEach((d) => assert.ok(labels.some((l) => l.args[0] === ZONE_LABEL[d.category]), `${el} ${d.speciesId}`));
  }
});

test("the water lines are drawn, the overlay toggles work and nothing is drawn for hidden points", () => {
  const { ctx, calls } = recorder();
  drawPourbaixScene(ctx, scene("Mg"));
  assert.ok(calls.some((c) => c.op === "fillText" && String(c.args[0]).startsWith("(a) H₂/H⁺")));
  assert.ok(calls.some((c) => c.op === "fillText" && String(c.args[0]).startsWith("(b) O₂/H₂O")));
  const off = recorder();
  drawPourbaixScene(off.ctx, scene("Mg", { showExperimentalOverlay: false }));
  assert.equal(off.calls.filter((c) => c.op === "arc" && (c.args[2] === 8 || c.args[2] === 10)).length, 0);
  const noLabels = recorder();
  drawPourbaixScene(noLabels.ctx, scene("Mg", { showPointLabels: false }));
  assert.ok(!noLabels.calls.some((c) => c.op === "fillText" && c.args[0] === "Stage one"));
  assert.ok(calls.some((c) => c.op === "fillText" && c.args[0] === "Stage one"));
});

test("withheld-data regions (Cr, Mo, Ti) are hatched with strokes clipped to each region; the domain fills are unchanged", () => {
  for (const el of ["Cr", "Mo", "Ti"]) {
    const regions = computeWithheldRegions(el, -6);
    assert.ok(regions.length > 0, el);
    const plain = recorder();
    drawPourbaixScene(plain.ctx, scene(el));
    const { ctx, calls } = recorder();
    drawPourbaixScene(ctx, scene(el, { withheldRegions: regions, probeInWithheldRegion: true }));
    assert.equal(calls.filter((c) => c.op === "clip").length, regions.length, `${el}: one clip per region`);
    assert.equal(plain.calls.filter((c) => c.op === "clip").length, 0, `${el}: no hatch without regions`);
    const fills = (cs: Call[]) => cs.filter((c) => c.op === "fill" && c.alpha < 1).length;
    assert.equal(fills(calls), fills(plain.calls), `${el}: the hatch adds no translucent fill`);
    assert.ok(calls.some((c) => c.op === "stroke" && c.strokeStyle === WITHHELD_HATCH.color), `${el}: hatch strokes`);
    assert.ok(calls.some((c) => c.op === "fillText" && c.args[0] === "withheld-data region: map not valid here"), `${el}: probe readout`);
    assert.ok(!plain.calls.some((c) => c.op === "fillText" && c.args[0] === "withheld-data region: map not valid here"));
    // every hatched region starts at the first vertex of its polygon
    for (const r of regions) {
      assert.ok(calls.some((c) => c.op === "moveTo" && Math.abs((c.args[0] as number) - xOf(r.polygon[0][0])) < 1e-9
        && Math.abs((c.args[1] as number) - yOf(r.polygon[0][1])) < 1e-9), `${el} ${r.speciesId}`);
    }
  }
});

test("review Sol 6.1 NIT 1: the water-line equations are written on the displayed reference scale", () => {
  const she = recorder();
  drawPourbaixScene(she.ctx, scene("Fe"));
  assert.ok(she.calls.some((c) => c.op === "fillText" && c.args[0] === `(a) H₂/H⁺: E = 0.000 - ${NERNST_SLOPE_25C.toFixed(3)}·pH V vs SHE`));
  const sce = recorder();
  drawPourbaixScene(sce.ctx, scene("Fe", { refOffset: REF_OFFSETS_VS_SHE.SCE, refLabel: "SCE" }));
  const a = sce.calls.find((c) => c.op === "fillText" && String(c.args[0]).startsWith("(a) H₂/H⁺"))!;
  const b = sce.calls.find((c) => c.op === "fillText" && String(c.args[0]).startsWith("(b) O₂/H₂O"))!;
  assert.equal(a.args[0], `(a) H₂/H⁺: E = -0.241 - ${NERNST_SLOPE_25C.toFixed(3)}·pH V vs SCE`);
  assert.equal(b.args[0], `(b) O₂/H₂O: E = ${(POURBAIX_DATA.water.e0_O2_H2O_V - 0.241).toFixed(3)} - ${NERNST_SLOPE_25C.toFixed(3)}·pH V vs SCE`);
  assert.ok(String(b.args[0]).includes("0.988"));
});
