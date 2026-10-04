import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ALLOY_PRESETS,
  DEFAULT_ALLOY_ID,
  ION_ACTIVITY_OPTIONS,
  NERNST_SLOPE_25C,
  PASSIVATION_NOTE,
  POURBAIX_DATA,
  availablePourbaixElements,
  boundaryLine,
  classifyPourbaixPoint,
  computeDomains,
  computeWithheldRegions,
  constituentStates,
  dominantSpecies,
  freePhWindows,
  pointInPolygon,
  polygonArea,
  polygonCentroid,
  pourbaixActivityRange,
  pourbaixUnavailableReason,
  primaryElementOf,
  speciesCoefficients,
  waterLines25C,
  withheldSpeciesAt,
} from "../src/utils/pourbaixThermodynamics";
import { DynamicPourbaixStudio } from "../src/components/DynamicPourbaixStudio";
import { CAPTURED_PROBE_NOTE, CAPTURED_PROBE_STAGE, EXPERIMENTAL_POURBAIX_PRESETS } from "../src/utils/experimentalPourbaixOverlay";
import { pourbaixRequestSignature } from "../src/utils/pourbaixRequest";

const text = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8").replace(/\r\n/g, "\n");

interface FixtureCase { element: string; log10Activity: number; speciesIds: string[]; rows: string[]; withheldRows?: string[] }
interface Fixture { n: number; box: { pH_min: number; pH_max: number; E_min_V_SHE: number; E_max_V_SHE: number }; cases: FixtureCase[] }
const fixture: Fixture = JSON.parse(text("tests/fixtures/pourbaix-grid-200x200.json"));

function decode(row: string): string[] {
  const out: string[] = [];
  for (const run of row.split(",")) {
    const [token, count] = run.split(":");
    for (let k = 0; k < Number(count); k++) out.push(token);
  }
  return out;
}
const centres = () => {
  const { box, n } = fixture;
  return {
    phs: Array.from({ length: n }, (_, i) => box.pH_min + (i + 0.5) * ((box.pH_max - box.pH_min) / n)),
    es: Array.from({ length: n }, (_, j) => box.E_min_V_SHE + (j + 0.5) * ((box.E_max_V_SHE - box.E_min_V_SHE) / n)),
  };
};

// ---------------------------------------------------------------------------------------------
// Parity with the Python engine (tests/fixtures/pourbaix-grid-200x200.json, python/tools/pourbaix_ts_fixture.py)
// ---------------------------------------------------------------------------------------------

test("the fixture covers every available element at two activities on a 200 x 200 grid", () => {
  assert.equal(fixture.n, 200);
  assert.deepEqual(fixture.box, POURBAIX_DATA.box);
  const got = fixture.cases.map((c) => `${c.element}@${c.log10Activity}`).sort();
  // the second activity is -3, or the element's upper limit when that is lower (Mo: -4)
  const want = availablePourbaixElements().flatMap((e) => [-6, Math.min(-3, pourbaixActivityRange(e)[1])].map((a) => `${e}@${a}`)).sort();
  assert.deepEqual(got, want);
  assert.ok(got.includes("Mo@-4") && got.includes("Cr@-3") && got.includes("Ti@-3"));
});

test("the TS withheld-data flags (dataValidity) equal the Python engine's on every fixture cell >= 1 mV from a candidate boundary", () => {
  const { phs, es } = centres();
  let flagged = 0, compared = 0;
  for (const c of fixture.cases) {
    const hasSets = (POURBAIX_DATA.elements[c.element] as { candidateSets?: unknown[] }).candidateSets?.length ?? 0;
    assert.equal(c.withheldRows !== undefined, hasSets > 0, `${c.element}: withheld rows iff candidate sets`);
    if (!c.withheldRows) continue;
    c.withheldRows.forEach((row, j) => {
      if (j % 2) return;
      decode(row).forEach((token, i) => {
        if (token === ".") return;
        const ts = withheldSpeciesAt(c.element, c.log10Activity, phs[i], es[j]).length > 0;
        if (ts !== (token === "1")) assert.fail(`${c.element}@${c.log10Activity} pH ${phs[i]} E ${es[j]}: TS ${ts}, Python ${token}`);
        flagged += ts ? 1 : 0;
        compared++;
      });
    });
  }
  assert.ok(compared > 100000 && flagged > 1000, `${compared} compared, ${flagged} flagged`);
});

test("the TS port classifies every fixture cell >= 1 mV from a boundary exactly as the Python engine", () => {
  const { phs, es } = centres();
  let compared = 0;
  for (const c of fixture.cases) {
    const coeffs = speciesCoefficients(c.element, c.log10Activity);
    assert.deepEqual(coeffs.map((s) => s.id), c.speciesIds, `${c.element} table order`);
    assert.equal(c.rows.length, 200);
    let compareCount = 0;
    c.rows.forEach((row, j) => {
      const cells = decode(row);
      assert.equal(cells.length, 200);
      cells.forEach((token, i) => {
        if (token === ".") return;
        const sp = dominantSpecies(coeffs, phs[i], es[j]);
        if (sp.id !== c.speciesIds[Number(token)]) assert.fail(`${c.element}@${c.log10Activity} pH ${phs[i]} E ${es[j]}: TS ${sp.id}, Python ${c.speciesIds[Number(token)]}`);
        const state = classifyPourbaixPoint(coeffs, phs[i], es[j]);
        assert.equal(state.speciesId, sp.id);
        assert.equal(state.category, POURBAIX_DATA.roles[sp.role]);
        compareCount++;
      });
    });
    assert.ok(compareCount > 39000, `${c.element}@${c.log10Activity}: ${compareCount} cells compared`);
    compared += compareCount;
  }
  assert.ok(compared > 390000);
});

test("every compared fixture cell lies inside the polygon of its species and no other polygon (canvas fills polygons)", () => {
  const { phs, es } = centres();
  for (const c of fixture.cases) {
    const coeffs = speciesCoefficients(c.element, c.log10Activity);
    const domains = computeDomains(coeffs);
    const byId = new Map(domains.map((d) => [d.speciesId, d]));
    for (let j = 0; j < 200; j += 2) {
      decode(c.rows[j]).forEach((token, i) => {
        if (token === ".") return;
        const id = c.speciesIds[Number(token)];
        const own = byId.get(id);
        assert.ok(own, `${c.element}: ${id} has a domain`);
        assert.ok(pointInPolygon(own.polygon, phs[i], es[j]), `${c.element} ${id} pH ${phs[i]} E ${es[j]} inside own polygon`);
        for (const d of domains) if (d.speciesId !== id) assert.ok(!pointInPolygon(d.polygon, phs[i], es[j]), `${c.element} ${id} also inside ${d.speciesId}`);
      });
    }
  }
});

test("the domains of an element tile the box exactly (convex polygons, area sum = box area)", () => {
  const box = POURBAIX_DATA.box;
  const boxArea = (box.pH_max - box.pH_min) * (box.E_max_V_SHE - box.E_min_V_SHE);
  for (const el of availablePourbaixElements()) {
    for (const logA of [-6, -4, -3, -1, 0].filter((a) => a <= pourbaixActivityRange(el)[1])) {
      const domains = computeDomains(speciesCoefficients(el, logA));
      const total = domains.reduce((s, d) => s + polygonArea(d.polygon), 0);
      assert.ok(Math.abs(total - boxArea) < 1e-6, `${el}@${logA}: ${total} vs ${boxArea}`);
      for (const d of domains) {
        const [cx, cy] = polygonCentroid(d.polygon);
        assert.ok(pointInPolygon(d.polygon, cx, cy), `${el} ${d.speciesId} centroid lies in its own polygon`);
      }
    }
  }
});

// ---------------------------------------------------------------------------------------------
// Numbers from SPEC-pourbaix-opus.md section 3 (a = 1e-6 unless noted): the port derives them from the table
// ---------------------------------------------------------------------------------------------

const near = (actual: number, expected: number, tol: number, label: string) =>
  assert.ok(Math.abs(actual - expected) <= tol, `${label}: ${actual} vs ${expected} (tol ${tol})`);

function sloped(el: string, a: string, b: string, e0: number, slope: number, logA = -6) {
  const line = boundaryLine(speciesCoefficients(el, logA), a, b);
  assert.equal(line?.type, "sloped", `${el} ${a}/${b}`);
  if (line?.type === "sloped") {
    near(line.E_V_SHE_at_pH0, e0, 0.001, `${el} ${a}/${b} intercept`);
    near(line.slope_V_per_pH, slope, 0.0005, `${el} ${a}/${b} slope`);
  }
}
function vertical(el: string, a: string, b: string, ph: number) {
  const line = boundaryLine(speciesCoefficients(el, -6), a, b);
  assert.equal(line?.type, "vertical", `${el} ${a}/${b}`);
  if (line?.type === "vertical") near(line.pH, ph, 0.01, `${el} ${a}/${b} pH`);
}

test("Fe boundary lines match the spec oracle (intercepts +/-1 mV, slopes +/-0.0005, verticals +/-0.01 pH)", () => {
  sloped("Fe", "Fe", "Fe2+", -0.6176, 0);
  sloped("Fe", "Fe2+", "Fe3+", 0.7706, 0);
  vertical("Fe", "Fe3+", "Fe2O3", 1.759);
  sloped("Fe", "Fe2+", "Fe2O3", 1.0828, -0.1775);
  sloped("Fe", "Fe2+", "Fe3O4", 1.5138, -0.2366);
  sloped("Fe", "Fe3O4", "Fe2O3", 0.2209, -0.0592);
  sloped("Fe", "Fe", "Fe3O4", -0.0848, -0.0592);
  sloped("Fe", "Fe3O4", "HFeO2-", -1.2867, 0.0296);
  sloped("Fe", "Fe", "HFeO2-", 0.3159, -0.0887);
  sloped("Fe", "Fe2O3", "FeO4^2-", 2.0959, -0.0986);
  // unit activity: the activity term reaches the solid/aqueous lines only
  sloped("Fe", "Fe", "Fe2+", -0.4401, 0, 0);
  sloped("Fe", "Fe2+", "Fe2O3", 0.7279, -0.1775, 0);
  sloped("Fe", "Fe2+", "Fe3+", 0.7706, 0, 0);
});

test("other elements: regression pins of the spec", () => {
  // Ni: NEA-TDB set (Gamsjager 2005); the atlas pins of the spec (-0.4275, 9.088, 12.204, 0.1101) are superseded
  sloped("Ni", "Ni", "Ni2+", -0.4147, 0);
  vertical("Ni", "Ni2+", "Ni(OH)2", 8.514);
  vertical("Ni", "Ni(OH)2", "HNiO2-", 12.171);
  sloped("Ni", "Ni", "Ni(OH)2", 0.0890, -0.0592);
  sloped("Cu", "Cu", "Cu2+", 0.1619, 0);
  vertical("Cu", "Cu2+", "CuO", 6.674);
  sloped("Cu", "Cu", "Cu2O", 0.4722, -0.0592);
  sloped("Cu", "Cu2O", "CuO", 0.6412, -0.0592);
  vertical("Cu", "CuO", "HCuO2-", 12.978);
  vertical("Cu", "HCuO2-", "CuO2^2-", 13.122);
  sloped("Zn", "Zn", "Zn2+", -0.9396, 0);
  vertical("Zn", "Zn2+", "ZnO", 8.772);
  vertical("Zn", "ZnO", "HZnO2-", 11.228);
  vertical("Zn", "HZnO2-", "ZnO2^2-", 12.77);
  sloped("Mg", "Mg", "Mg2+", -2.5343, 0);
  vertical("Mg", "Mg2+", "Mg(OH)2", 11.37);
});

test("Al (available since WP-Al: OBIGT TS01 + gibbsite): the engine's pins at a = 1e-6 and 1", () => {
  const ids = speciesCoefficients("Al", -6).map((s) => s.id);
  assert.deepEqual(ids, ["Al", "Al3+", "Al(OH)3", "Al(OH)4-"]);
  sloped("Al", "Al", "Al3+", -1.8024, 0);
  vertical("Al", "Al3+", "Al(OH)3", 4.577);
  vertical("Al", "Al(OH)3", "Al(OH)4-", 9.118);
  sloped("Al", "Al", "Al(OH)3", -1.5317, -0.0592);
  sloped("Al", "Al", "Al(OH)4-", -1.3519, -0.0789);
  // unit activity
  sloped("Al", "Al", "Al3+", -1.6841, 0, 0);
  sloped("Al", "Al", "Al(OH)4-", -1.2335, -0.0789, 0);
  const line = boundaryLine(speciesCoefficients("Al", 0), "Al3+", "Al(OH)3");
  assert.equal(line?.type, "vertical");
  if (line?.type === "vertical") near(line.pH, 2.577, 0.01, "Al3+/gibbsite pH at a = 1");
  // the passive (gibbsite) domain sits between the two vertical boundaries inside the water window
  const al = speciesCoefficients("Al", -6);
  assert.equal(classifyPourbaixPoint(al, 7, -0.2).speciesId, "Al(OH)3");
  assert.equal(classifyPourbaixPoint(al, 7, -0.2).category, "Passivation (thermodynamic)");
  assert.equal(classifyPourbaixPoint(al, 2, 0).speciesId, "Al3+");
  assert.equal(classifyPourbaixPoint(al, 11, -0.3).speciesId, "Al(OH)4-");
  assert.equal(classifyPourbaixPoint(al, 11, -0.3).category, "Corrosion (alkaline)");
  assert.equal(classifyPourbaixPoint(al, 7, -2.2).speciesId, "Al");
});

test("an exact tie goes to the earlier table row (metal, cations, solids, anions)", () => {
  const mk = (id: string) => ({ id, formula: id, phase: "aq" as const, role: "cation" as const, category: "Corrosion (acid)" as const, c0: 5, cpH: -3, cE: -2 });
  const [a, b] = [mk("first"), mk("second")];
  assert.equal(dominantSpecies([a, b], 4, 1).id, "first");
  assert.equal(dominantSpecies([b, a], 4, 1).id, "second");
  const lower = { ...mk("lower"), c0: 4 };
  assert.equal(dominantSpecies([a, b, lower], 4, 1).id, "lower");
});

test("the three audit spot points: Fe2+ (not passivation) at pH 6/-0.40 and pH 8/-0.55, Fe2O3 (not active) at pH 3/+0.60", () => {
  const fe = speciesCoefficients("Fe", -6);
  assert.equal(classifyPourbaixPoint(fe, 6, -0.4).speciesId, "Fe2+");
  assert.equal(classifyPourbaixPoint(fe, 6, -0.4).category, "Corrosion (acid)");
  assert.equal(classifyPourbaixPoint(fe, 8, -0.55).speciesId, "Fe2+");
  assert.equal(classifyPourbaixPoint(fe, 3, 0.6).speciesId, "Fe2O3");
  assert.equal(classifyPourbaixPoint(fe, 3, 0.6).category, "Passivation (thermodynamic)");
});

test("default-case drift: UI default Fe marine preset points at 25 C (SHE) land in the documented species", () => {
  const fe = speciesCoefficients("Fe", -6);
  const she = (pt: { pH: number; potential_V: number; refElectrode: keyof typeof offsets }) => pt.potential_V + offsets[pt.refElectrode];
  const offsets = { SHE: 0, SCE: 0.241, "Ag/AgCl (3M KCl)": 0.207, "Ag/AgCl (Sat KCl)": 0.197, CSE: 0.316, MMS: 0.64 } as const;
  const expected: Record<string, string> = { fe_p1: "Fe2O3", fe_p2: "Fe2+", fe_p3: "Fe2+", fe_p4: "Fe" };
  for (const pt of EXPERIMENTAL_POURBAIX_PRESETS[0].points) {
    assert.equal(classifyPourbaixPoint(fe, pt.pH, she(pt as any)).speciesId, expected[pt.id], pt.id);
  }
});

test("water lines and Nernst slope at 25 C: E = -k pH and 1.2288 - k pH", () => {
  near(NERNST_SLOPE_25C, 0.0591597, 1e-6, "k");
  const w = waterLines25C();
  for (const ph of [-2, 0, 7, 14]) {
    near(w.herLine.e_at_ph0 + w.herLine.slope * ph, -0.0591597 * ph, 0.001, `HER at pH ${ph}`);
    near(w.oerLine.e_at_ph0 + w.oerLine.slope * ph, 1.2288 - 0.0591597 * ph, 0.001, `OER at pH ${ph}`);
  }
  const fe = speciesCoefficients("Fe", -6);
  assert.equal(classifyPourbaixPoint(fe, 7, 0.2).isInsideWaterStability, true);
  assert.equal(classifyPourbaixPoint(fe, 7, -0.6).isInsideWaterStability, false); // below -k*7 = -0.414
  assert.equal(classifyPourbaixPoint(fe, 7, 0.9).isInsideWaterStability, false); // above 1.2288 - 0.414 = 0.815
});

// ---------------------------------------------------------------------------------------------
// Availability, defaults and the removal of the old rule trees
// ---------------------------------------------------------------------------------------------

test("engine v5: Cr, Mo and Ti have a map (with withheld-data regions); elements absent from the table stay unavailable", () => {
  assert.deepEqual(availablePourbaixElements().sort(), ["Al", "Cr", "Cu", "Fe", "Mg", "Mo", "Ni", "Ti", "Zn"]);
  for (const el of ["Cr", "Ti", "Mo", "Fe", "Al"]) assert.equal(pourbaixUnavailableReason(el), null, el);
  for (const el of ["Xx", "V", "Nb", "Co", "Mn"]) {
    assert.ok(pourbaixUnavailableReason(el), `${el}: an element absent from the table is unavailable, not Fe`);
    assert.throws(() => speciesCoefficients(el, -6), /No verified/);
  }
  assert.deepEqual(pourbaixActivityRange("Cr"), [-6, -2]);
  assert.deepEqual(pourbaixActivityRange("Mo"), [-6, -4]);
  assert.deepEqual(pourbaixActivityRange("Ti"), [-6, 0]);
  assert.deepEqual(pourbaixActivityRange("Fe"), [-6, 0]);
});

test("Cr, Mo, Ti: the port's lines and free pH windows equal the Python engine's (NBS set, NECTAR constants)", () => {
  // values from python/test_pourbaix_ticrmo.py (recomputed there from the primary constants)
  sloped("Cr", "Cr", "Cr2O3", -0.5989, -0.0592);
  sloped("Cr", "Cr2O3", "HCrO4-", 1.1156, -0.0789);
  sloped("Cr", "Cr2O3", "CrO4^2-", 1.2433, -0.0986);
  vertical("Cr", "HCrO4-", "CrO4^2-", 6.473);
  sloped("Mo", "Mo", "MoO2", -0.1522, -0.0592);
  sloped("Mo", "MoO2", "MoO4^2-", 0.7085, -0.1183);
  vertical("Mo", "H2MoO4", "HMoO4-", 3.65);
  vertical("Mo", "HMoO4-", "MoO4^2-", 4.47);
  sloped("Ti", "Ti", "Ti2O3", -1.2486, -0.0592);
  sloped("Ti", "Ti2O3", "TiO2", -0.558, -0.0592);
  const want: Record<string, [number, number][]> = { Cr: [[4.778, 14.405]], Mo: [[1.991, 16]], Ti: [[1.21, 14.92]], Fe: [[-2, 16]] };
  for (const [el, w] of Object.entries(want)) {
    const got = freePhWindows(computeWithheldRegions(el, -6));
    assert.equal(got.length, w.length, el);
    got.forEach(([a, b], i) => { near(a, w[i][0], 0.001, `${el} window start`); near(b, w[i][1], 0.001, `${el} window end`); });
  }
  // point classification and validity flags (same points as the Python test)
  const cr = speciesCoefficients("Cr", -6);
  assert.equal(classifyPourbaixPoint(cr, 2, 0).speciesId, "Cr2O3");
  assert.deepEqual(withheldSpeciesAt("Cr", -6, 2, 0).map((h) => h.speciesId), ["Cr3+[CRC]", "Cr3+[SSWS97]", "Cr3+[LLNL]", "Cr3+[BN98]"]);
  assert.deepEqual(withheldSpeciesAt("Cr", -6, 7, 0.2), []);
  assert.equal(classifyPourbaixPoint(cr, 7, 1.0).category, "Transpassive");
  const ti = speciesCoefficients("Ti", -6);
  assert.equal(classifyPourbaixPoint(ti, 7, -1.8).speciesId, "Ti");
  assert.ok(withheldSpeciesAt("Ti", -6, 7, -1.8).some((h) => h.speciesId === "TiH2"), "the Ti metal domain is a TiH2 region");
  const mo = speciesCoefficients("Mo", -6);
  assert.deepEqual([[7, 0.2], [7, -0.4], [2, 0.6]].map(([p, e]) => classifyPourbaixPoint(mo, p, e).speciesId), ["MoO4^2-", "MoO2", "H2MoO4"]);
  for (const el of ["Fe", "Ni", "Cu", "Zn", "Mg", "Al"]) assert.deepEqual(computeWithheldRegions(el, -6), [], el);
});

test("availability is read from the generated JSON, not from a list in the TS sources", () => {
  const json = JSON.parse(text("src/generated/pourbaixSpecies25C.json")) as { elements: Record<string, { available: boolean; reason?: string; species?: unknown[] }> };
  const fromJson = Object.entries(json.elements).filter(([, v]) => v.available).map(([k]) => k).sort();
  assert.deepEqual(availablePourbaixElements().sort(), fromJson);
  for (const [el, v] of Object.entries(json.elements)) {
    assert.equal(pourbaixUnavailableReason(el), v.available ? null : v.reason, el);
    assert.equal(v.available, Array.isArray(v.species) && v.species.length > 0, `${el}: available iff it has species`);
  }
  const thermo = text("src/utils/pourbaixThermodynamics.ts");
  const studio = text("src/components/DynamicPourbaixStudio.tsx");
  assert.ok(!/\[\s*"Fe"\s*,\s*"Ni"/.test(thermo + studio), "no hard-coded list of available elements");
  assert.ok(!/available[A-Za-z]*\s*=\s*\[/.test(thermo + studio));
});

test("the default alloy exists, is pure Fe and agrees with the default experimental preset element", () => {
  assert.equal(DEFAULT_ALLOY_ID, "pure-fe");
  const alloy = ALLOY_PRESETS.find((a) => a.id === DEFAULT_ALLOY_ID);
  assert.ok(alloy, "pure-fe preset exists");
  assert.equal(ALLOY_PRESETS.some((a) => a.id === "carbon-steel"), false);
  assert.equal(primaryElementOf(alloy!.composition), "Fe");
  assert.equal(EXPERIMENTAL_POURBAIX_PRESETS[0].element, "Fe");
  assert.equal(primaryElementOf({ Ni: 53, Cr: 19, Fe: 18 }), "Ni");
});

test("the old rule trees, Kw/Psat view, Epit line, hand-entered data and composite verdict are gone", () => {
  const thermo = text("src/utils/pourbaixThermodynamics.ts");
  const studio = text("src/components/DynamicPourbaixStudio.tsx");
  for (const gone of ["extrapolateDeltaG0_T", "hasPassivatingElement", "evaluateMulticomponentAlloyAtPoint", "evaluateElementThermodynamicsAtPoint",
    "deltaH0_298_kJ_mol", "s0_298_J_mol_K", "vaporPressure", "logKw", "Criss-Cobble", "pittingSensitivity_k", "MoO4_2_aq"]) {
    assert.ok(!thermo.includes(gone), `pourbaixThermodynamics.ts still contains ${gone}`);
  }
  for (const gone of ["carbon-steel", "Epit", "E_pit", "hasPassivatingElement", "Hydrothermal", "Cocktail", "ΔG°", "calculateWaterStabilityLines",
    "Temperature & Salinity Envelopes", "Chloro-Complex", "Pitting Breakdown", "Dynamic Pourbaix"]) {
    assert.ok(!studio.includes(gone), `DynamicPourbaixStudio.tsx still contains ${gone}`);
  }
  assert.ok(!/ELEMENT_THERMODYNAMICS/.test(thermo + studio));
});

// ---------------------------------------------------------------------------------------------
// Visible text
// ---------------------------------------------------------------------------------------------

const render = (props: { initialAlloyId?: string; initialProbePH?: number; initialProbePotential_SHE?: number } = {}) => renderToStaticMarkup(React.createElement(DynamicPourbaixStudio, props));
const plain = (html: string) => html.replace(/<!-- -->/g, "").replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&#x27;/g, "'").replace(/\s+/g, " ");

test("default studio (pure Fe): relabelled title, subtitle, tabs, fixed 25 C temperature and the passivation caveat", () => {
  const html = render();
  const t = plain(html);
  assert.match(t, /Pourbaix E–pH Studio \(25 °C\)/);
  assert.match(t, /Single-element M–H₂O equilibrium by minimum Gibbs energy \(25 °C, dissolved activity 10ⁿ, γ = 1\); overlays illustrative preset E–pH points \(not measured data\) and points you add\./);
  for (const label of ["2D Pourbaix E-pH Diagram", "Equilibrium boundaries (25 °C)", "Element selector (no alloy equilibrium)"]) assert.ok(t.includes(label), label);
  assert.match(t, /Fe–H₂O \( ?Pure Iron \/ Carbon Steel \(Fe\) ?\) • E-pH Pourbaix Diagram/);
  assert.match(html, /aria-label="Temperature \(25 °C data only\)"[^>]*disabled/);
  assert.ok(t.includes("25 °C data only"));
  assert.equal(t.split(PASSIVATION_NOTE).length - 1, 2, "caveat under the legend and in the probe card (default probe is a passivation point)");
  assert.match(html, /<canvas/);
  for (const gone of ["Dynamic Pourbaix", "Hydrothermal", "ΔG°(T)", "Cocktail", "Multicomponent Alloy Formulator", "Temperature & Salinity", "Epit", "Pitting Breakdown", "Chloro-Complex", "0°C to 300°C", "carbon-steel"]) {
    assert.ok(!t.includes(gone), `visible text still contains ${gone}`);
  }
  assert.match(html, /<option value="pure-fe" selected="">/);
  assert.match(html, /<option value="Fe" selected="">Fe \(100% wt\)<\/option>/);
});

test("Ti-6Al-4V draws the Ti map with the data-validity note (no reason panel); Inconel 718 maps Ni and offers Cr and Mo", () => {
  const ti = render({ initialAlloyId: "ti-6al-4v" });
  const t = plain(ti);
  assert.match(ti, /<canvas/);
  assert.match(t, /Ti–H₂O \( ?Ti-6Al-4V/);
  assert.ok(!t.includes("POURBAIX_DATA_UNAVAILABLE") && !t.includes("No verified Ti–H₂O data"));
  assert.match(t, /Data validity \(Ti, dissolved activity 10\^-6 to 10\^0 M\): hatched = withheld-data region/);
  assert.match(t, /free of withheld-data regions for pH 1\.21 to 14\.92 at a\(M\) = 10\^-6/);
  assert.match(t, /TiH2 \(NBS; hydride outside the oxide\/ion table\)/);
  assert.equal(t.split(PASSIVATION_NOTE).length - 1, 2, "legend caveat + probe-card caveat (pH 7 / 0.2 V is a TiO2 point)");
  const inconel = render({ initialAlloyId: "inconel-718" });
  assert.match(inconel, /<canvas/);
  assert.match(plain(inconel), /Ni–H₂O \(Inconel 718/);
  for (const el of ["Al \\(0\\.5% wt\\)", "Cr \\(19% wt\\)", "Mo \\(3% wt\\)"]) {
    assert.match(plain(inconel), new RegExp(`${el} (?!- no verified data)`), el);
  }
  assert.match(plain(inconel), /Nb \(5\.1% wt\) - no verified data/, "Nb has no table");
  assert.ok(!/Data validity \(/.test(plain(inconel)), "Ni has no withheld candidate sets");
});

test("pure Cr / Mo presets draw their maps; Mo offers only 1e-6 and 1e-4; the withheld regions are named in the note", () => {
  const cr = render({ initialAlloyId: "pure-cr" });
  assert.match(cr, /<canvas/);
  assert.match(plain(cr), /Data validity \(Cr, dissolved activity 10\^-6 to 10\^-2 M\)/);
  assert.match(plain(cr), /free of withheld-data regions for pH 4\.78 to 14\.40/);
  assert.match(plain(cr), /Cr\(III\)\/Cr\(II\) with hydrolysis, CRC values/);
  const crOptions = [...cr.matchAll(/<option value="([0-9.e-]+)"[^>]*>10|<option value="([0-9.e-]+)"[^>]*>1\.0 M/g)].map((m) => Number(m[1] ?? m[2]));
  assert.deepEqual(crOptions, [1e-6, 1e-4, 1e-3]);
  const mo = render({ initialAlloyId: "pure-mo" });
  assert.match(mo, /<canvas/);
  const moOptions = [...mo.matchAll(/<option value="([0-9.e-]+)"[^>]*>10|<option value="([0-9.e-]+)"[^>]*>1\.0 M/g)].map((m) => Number(m[1] ?? m[2]));
  assert.deepEqual(moOptions, [1e-6, 1e-4]);
  assert.match(plain(mo), /Not represented in the table: MoO₂²⁺ \(cationic Mo\(VI\) species/);
  assert.match(plain(mo), /Mo\(V\) \(no aqueous Mo\(V\) species with a sourced value\)/);
  // review pbxt-sol N-1: the excluded Cr(OH)3(am) shows its reason, not "no sourced value"
  assert.match(plain(cr), /Cr\(OH\)₃ \(amorphous\) \(metastable solid: Cr\(OH\)3\(s\) \+ 3H\+ = Cr3\+ \+ 3H2O log K 9\.41/);
  assert.ok(!plain(cr).includes("no sourced value):"));
  const fe = render();
  const feOptions = [...fe.matchAll(/<option value="([0-9.e-]+)"[^>]*>10|<option value="([0-9.e-]+)"[^>]*>1\.0 M/g)].map((m) => Number(m[1] ?? m[2]));
  assert.deepEqual(feOptions, [1e-6, 1e-4, 1e-3, 1]);
});

test("Al-7075 selects Al and draws the gibbsite map (no reason panel); Al in other compositions is no longer flagged \"no verified data\"", () => {
  const html = render({ initialAlloyId: "al-7075-t6" });
  const t = plain(html);
  assert.match(html, /<canvas/);
  assert.match(t, /Al–H₂O \( ?Aluminum 7075-T6/);
  assert.ok(!t.includes("POURBAIX_DATA_UNAVAILABLE"));
  assert.ok(!t.includes("No verified Al–H₂O data"));
  assert.equal(t.split(PASSIVATION_NOTE).length - 1, 2, "legend caveat + probe-card caveat (the default probe pH 7 / 0.2 V is a gibbsite point)");
});

test("Corrosion lab tab and the Python service comment use the new wording", () => {
  assert.ok(text("src/components/CorrosionEngineeringLab.tsx").includes("<span>Pourbaix E–pH (25 °C)</span>"));
  assert.ok(!text("src/components/CorrosionEngineeringLab.tsx").includes("Dynamic Pourbaix (E-pH-T-Salinity)</span>"));
  assert.match(text("src/services/pythonComputationService.ts").split("\n").slice(0, 6).join("\n"), /single-element Pourbaix E–pH at 25 °C/);
});

// ---------------------------------------------------------------------------------------------
// Fix round (REVIEW-pbx-sci / REVIEW-pbx-code)
// ---------------------------------------------------------------------------------------------

test("S2: the activity range is limited to 1e-6 .. 1 in the generated JSON, the Python engine text and the UI options", () => {
  const json = JSON.parse(text("src/generated/pourbaixSpecies25C.json")) as { activity: { log10Range: number[] } };
  assert.deepEqual(json.activity.log10Range, [-6, 0]);
  const studio = text("src/components/DynamicPourbaixStudio.tsx");
  const options = ION_ACTIVITY_OPTIONS.map((o) => Math.log10(o.value));
  assert.ok(options.length >= 3);
  for (const o of options) assert.ok(o >= json.activity.log10Range[0] && o <= json.activity.log10Range[1], `option 10^${o} outside the engine range`);
  assert.match(studio, /ION_ACTIVITY_OPTIONS\.filter\(\(o\) => activityInRange\(selectedElement, Math\.log10\(o\.value\)\)\)/);
  assert.ok(!studio.includes("1e-8"), "the refused 1e-8 option is gone");
  assert.match(plain(render()), /Mononuclear hydrolysis species \(MOH⁺, M\(OH\)₂\(aq\)\) are not in the species table for any element/);
});

test("S4: the studio no longer calls preset points measured; the preset note is shown and the presets say illustrative", () => {
  const t = plain(render());
  assert.ok(!/overlays measured/.test(t));
  assert.ok(t.includes("Preset points are illustrative scenarios, not measured data: no source is cited."));
  for (const p of EXPERIMENTAL_POURBAIX_PRESETS) assert.match(p.description, /^Illustrative scenario, not measured data/, p.id);
});

test("S5: preset descriptions make no passivity, immunity, resistance or synergy claim; compositions are nominal and reach every available element", () => {
  const banned = /immunity|resistance|passivity|synergy|protective|self-healing|superb|outstanding|spontaneous|benchmark|caustic|strong/i;
  for (const a of ALLOY_PRESETS) {
    assert.ok(!banned.test(a.description), `${a.id}: ${a.description}`);
    assert.ok(!banned.test(a.recommendedApplication), a.id);
    const sum = Object.values(a.composition).reduce((s, v) => s + v, 0);
    assert.ok(sum >= 99 && sum <= 100.5, `${a.id}: composition sums to ${sum}`);
  }
  const reachable = new Set(ALLOY_PRESETS.flatMap((a) => Object.keys(a.composition)));
  for (const el of availablePourbaixElements()) assert.ok(reachable.has(el), `${el} cannot be reached from any preset`);
  const al7075 = ALLOY_PRESETS.find((a) => a.id === "al-7075-t6")!;
  assert.ok(al7075.composition.Zn > 5 && al7075.composition.Mg > 2, "7075 carries its Zn and Mg");
  for (const id of ["pure-zn", "pure-mg", "pure-cu", "pure-al"]) assert.ok(ALLOY_PRESETS.some((a) => a.id === id), id);
  // AlCoCrFeNi is equiatomic: wt% from the atomic masses
  const hea = ALLOY_PRESETS.find((a) => a.id === "al-co-cr-fe-ni-hea")!;
  const mass: Record<string, number> = { Al: 26.98, Co: 58.93, Cr: 52.0, Fe: 55.85, Ni: 58.69 };
  const total = Object.values(mass).reduce((s, v) => s + v, 0);
  assert.deepEqual(Object.keys(hea.composition).sort(), Object.keys(mass).sort());
  for (const el of Object.keys(mass)) near(hea.composition[el], (100 * mass[el]) / total, 0.05, `HEA ${el} wt%`);
  // the Zn and Mg presets render a map, not a reason panel
  for (const id of ["pure-zn", "pure-mg", "pure-cu"]) assert.match(render({ initialAlloyId: id }), /<canvas/, id);
});

test("C4/C7: solver echoes are never merged into the points, so the request signature cannot change by itself; unavailable elements send no request", () => {
  const studio = text("src/components/DynamicPourbaixStudio.tsx");
  const dispatch = studio.slice(studio.indexOf("async function dispatchPythonSolver"), studio.indexOf("return dispatchPythonSolver();"));
  assert.ok(dispatch.length > 200);
  assert.ok(!/setExperimentalPoints|\.\.\.p, \.\.\.analyzed|experimentalOverlay/.test(dispatch), "the solver callback must not touch the points");
  assert.equal(studio.split("setExperimentalPoints(").length - 1, 1, "only 'capture probe as point' writes points");
  assert.ok(!/potential_V_SHE \?\?/.test(studio) && !/riskLevel/.test(studio), "points are classified by the port, not by solver echoes");
  assert.match(dispatch, /if \(pourbaixUnavailableReason\(primaryElement\) !== null\) \{/);
  // what the loop looked like: a mojibake echo of `notes` changes the signature (cp1254 reads UTF-8 bytes as other text)
  const base = { primaryElement: "Fe", temperature_C: 25, ionActivity: 1e-6, chlorideActivity: 0.54 };
  const pts = (notes: string) => [{ id: "a", name: "a", pH: 7, potential_V: 0, refElectrode: "SHE" as const, notes }];
  assert.notEqual(
    pourbaixRequestSignature({ ...base, experimentalPoints: pts("Fe²⁺") }),
    pourbaixRequestSignature({ ...base, experimentalPoints: pts(Buffer.from("Fe²⁺", "utf8").toString("latin1")) }),
  );
});

test("C5: the canvas is redrawn whenever it is mounted again (tab switch, element with data)", () => {
  const studio = text("src/components/DynamicPourbaixStudio.tsx");
  assert.match(studio, /const canvasMounted = activeTab === "diagram" && unavailableReason === null;/);
  assert.match(studio, /useEffect\(\(\) => \{\s*if \(canvasMounted\) renderPourbaixCanvas\(\);\s*\}, \[renderPourbaixCanvas, canvasMounted\]\);/);
});

test("NIT: accessible canvas label, no '+ 0.0000·pH', no internal process words in reasons, one Ti message", () => {
  const html = render();
  assert.match(html, /<canvas[^>]*role="img"[^>]*aria-label="Fe–H₂O E–pH map at 25 °C, dissolved activity 10\^-6; probe at pH 7\.00, 0\.200 V SHE: Fe₂O₃/);
  assert.ok(text("src/components/DynamicPourbaixStudio.tsx").includes("independent of pH"));
  assert.ok(!/0\.0000·pH/.test(text("src/components/DynamicPourbaixStudio.tsx")));
  const json = JSON.parse(text("src/generated/pourbaixSpecies25C.json")) as { elements: Record<string, { sourceSetNote?: string }> };
  for (const el of ["Cr", "Ti", "Mo"]) assert.ok(!/WP-|Blocked until/.test(json.elements[el].sourceSetNote!), el);
  const hea = plain(render({ initialAlloyId: "al-co-cr-fe-ni-hea" }));  // primary element Co: no table
  assert.equal(hea.split(pourbaixUnavailableReason("Co")!).length - 1, 1, "the Co reason is shown once");
  assert.ok(!hea.includes("Test Points Overlaid"), "no 'test points overlaid' badge without a map");
});

test("preset points of another element are labelled as reclassified; unavailable maps show no point readout", () => {
  const ni = plain(render({ initialAlloyId: "inconel-718" }));
  assert.match(ni, /The points of the preset (?:"|&quot;)Carbon Steel \(AISI 1018\).*?(?:"|&quot;) belong to Fe; they are only reclassified here in the Ni–H₂O map\./);
  assert.ok(!/belong to Fe; they are only reclassified/.test(plain(render())), "no notice on the Fe map");
  assert.ok(!/Selected test point/.test(plain(render({ initialAlloyId: "al-co-cr-fe-ni-hea" }))));
});

test("second re-review: every tab has a render branch, preset point labels are neutral, the error is tied to its element, the ad-hoc stdout is decoded as a stream, Zn is named in the UI note", () => {
  const studio = text("src/components/DynamicPourbaixStudio.tsx");
  const ids = [...studio.matchAll(/id: "([a-z-]+)",\s+label:|\{ id: "([a-z-]+)", label:/g)].map((m) => m[1] ?? m[2]);
  assert.deepEqual(ids.sort(), ["alloy-formulator", "diagram", "experimental-overlay", "reactions"]);
  for (const id of ids) assert.ok(studio.includes(`activeTab === "${id}" &&`), `tab ${id} has no render branch`);
  assert.ok(!studio.includes("Open Mechanism Matrix") && !studio.includes("Overlay & Mechanisms"));
  for (const p of EXPERIMENTAL_POURBAIX_PRESETS) {
    for (const pt of p.points) {
      assert.match(pt.stageName ?? "", /^Point \d+ \(illustrative\)$/, pt.id);
      assert.equal(pt.notes, "Illustrative scenario point; no measurement.", pt.id);
    }
  }
  assert.match(studio, /solveErrorState && solveErrorState\.element === selectedElement/);
  assert.match(text("server/processOrchestrator.ts"), /pyProcess\.stdout\.setEncoding\("utf8"\);\s*pyProcess\.stderr\.setEncoding\("utf8"\);/);
  assert.match(plain(render()), /Zn is constant-dependent \(with the wateq4f \/ Baes & Mesmer Zn\(OH\)₂\(aq\) constant the whole ZnO domain would vanish, with IUPAC 2013 it stays\)/);
  assert.match(plain(renderToStaticMarkup(React.createElement(DynamicPourbaixStudio, { initialSolveError: "boom" }))), /boom/);
});

test("review Sol 6.1 SF-1: illustrative and captured points are test points, never measurements", () => {
  const t = plain(render());
  assert.ok(t.includes("Capture probe as test point"));
  assert.ok(t.includes("Test points:"));
  for (const gone of ["Experimental Points", "Capture as Experimental Test Point", "Probed Sample", "Probed Test Point"]) {
    assert.ok(!t.includes(gone), `visible text still contains ${gone}`);
  }
  const studio = text("src/components/DynamicPourbaixStudio.tsx");
  const capture = studio.slice(studio.indexOf("const handleAddProbedCoordinateAsPoint"), studio.indexOf("const selectElement"));
  assert.match(capture, /stageName: CAPTURED_PROBE_STAGE,/);
  assert.match(capture, /notes: `\$\{CAPTURED_PROBE_NOTE\} /);
  assert.match(capture, /name: `Computed probe coordinate/);
  assert.match(CAPTURED_PROBE_STAGE, /not measured/);
  assert.match(CAPTURED_PROBE_NOTE, /not a measurement/);
  for (const p of EXPERIMENTAL_POURBAIX_PRESETS) for (const pt of p.points) assert.ok(!/(?<!not )measured/i.test(`${pt.name} ${pt.stageName} ${pt.notes}`), pt.id);
  assert.ok(!text("python/pourbaix_solver.py").includes("measured point"));
  assert.ok(!text("python/tools/pourbaix_golden_check.py").includes("measured point"));
});

test("review pbxt-sol SF-2: constituent cards carry their own withheld-data validity (ss-316l, Fe selected, pH 2, E 0 V SHE, 1e-6)", () => {
  const states = constituentStates(["Fe", "Cr", "Ni", "Mo", "Mn"], -6, 2, 0);
  assert.equal(states.Cr.state?.speciesId, "Cr2O3");
  assert.deepEqual(states.Cr.withheld.map((h) => h.speciesId), ["Cr3+[CRC]", "Cr3+[SSWS97]", "Cr3+[LLNL]", "Cr3+[BN98]"]);
  assert.deepEqual(states.Fe.withheld, []);
  assert.deepEqual(states.Ni.withheld, []);
  assert.equal(states.Mn.reason, "unavailable");
  const html = render({ initialAlloyId: "ss-316l", initialProbePH: 2, initialProbePotential_SHE: 0 });
  const t = plain(html);
  assert.match(t, /Fe–H₂O \( ?Stainless Steel 316L/);
  assert.match(t, /Cr 17% wt Cr₂O₃ Passivation \(thermodynamic\) map not valid here \(withheld data\)/);
  assert.ok(!/Fe 66\.5% wt \S+ \S+[^C]*map not valid here/.test(t.split("Cr 17% wt")[0].slice(-200)), "the Fe card is not flagged");
  assert.equal(t.split("map not valid here (withheld data)").length - 1, 1, "only the Cr card is flagged");
  // at the default probe (pH 7, 0.2 V) no card is flagged
  assert.ok(!plain(render({ initialAlloyId: "ss-316l" })).includes("map not valid here (withheld data)"));
});
