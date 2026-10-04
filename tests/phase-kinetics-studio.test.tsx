import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { PhaseKineticsTTTCCTStudio, type PhaseKineticsStudioTab } from "../src/components/PhaseKineticsTTTCCTStudio";
import type { PythonKineticsResult } from "../src/services/pythonComputationService";

// Render test of the Phase Kinetics Studio over REAL solver output (python/test_kinetics_fx.py studio_fixture_results();
// test_committed_fixture_is_the_current_solver_output fails when the fixture is stale). The component takes the result
// and the first tab as props (test seam), so no solver or fetch runs here.
const FIXTURE: Record<string, PythonKineticsResult> = JSON.parse(
  readFileSync(new URL("./fixtures/kinetics-studio-results.json", import.meta.url), "utf8")
);
const ALLOY_OF: Record<string, string> = {
  aisi4140: "AISI 4140", aisi4340: "AISI 4340", aisid2: "AISI D2", in718: "Inconel 718", ti6al4v: "Ti-6Al-4V",
  al7075: "Al 7075", aisi4340_aging720: "AISI 4340", al7075_aging720: "Al 7075",
};
const TABS: PhaseKineticsStudioTab[] = ["ttt", "cct", "calphad_vs_kinetics", "lsw_aging", "microstructure"];
const NON_STEELS = ["in718", "ti6al4v", "al7075", "al7075_aging720"];
const STEELS = ["aisi4140", "aisi4340", "aisid2", "aisi4340_aging720"];

const render = (key: string, tab: PhaseKineticsStudioTab, coolingRate = 10) =>
  renderToStaticMarkup(
    <PhaseKineticsTTTCCTStudio initialAlloy={ALLOY_OF[key]} initialData={FIXTURE[key]} initialTab={tab} initialCoolingRate={coolingRate} />
  );
const text = (markup: string) =>
  markup.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/&gt;/g, ">").replace(/&lt;/g, "<").replace(/&amp;/g, "&").replace(/\s+/g, " ");
const BAD = /\b(null|NaN|undefined|Infinity)\b/;

test("fixture holds the real solver output for the eight cases", () => {
  assert.deepEqual(Object.keys(FIXTURE), Object.keys(ALLOY_OF));
  for (const key of NON_STEELS) assert.equal(FIXTURE[key].kineticsModel?.status, "unavailable", key);
  for (const key of STEELS) assert.equal(FIXTURE[key].kineticsModel?.status, "available", key);
});

test("no tab of any case renders null, NaN or undefined (text or attributes)", () => {
  for (const key of Object.keys(ALLOY_OF)) {
    for (const tab of TABS) {
      const markup = render(key, tab);
      assert.ok(!BAD.test(text(markup)), `${key}/${tab}: ${text(markup).match(BAD)?.[0]}`);
      const attrs = [...markup.matchAll(/ (?:title|data-[a-z-]+|aria-label)="([^"]*)"/g)].map((m) => m[1]);
      for (const a of attrs) assert.ok(!BAD.test(a), `${key}/${tab} attribute: ${a}`);
      assert.ok(!/\d\s*%\s*%|null%/.test(text(markup)), `${key}/${tab}`);
    }
  }
});

test("TTT tab, non-steels: the unavailable reason, no steel nose text, a single non-repeating banner", () => {
  for (const key of NON_STEELS) {
    const markup = render(key, "ttt");
    const t = text(markup);
    assert.ok(markup.includes("data-ttt-unavailable"), key);
    assert.ok(t.includes("TTT curves unavailable: kinetics model is steel-only."), key);
    assert.ok(!markup.includes("data-ttt-floor"), key);
    assert.ok(!/~560|Pearlite Nose|Bainite Nose|Koistinen/.test(t), `${key}: ${t}`);
    assert.equal((t.match(/Unavailable \(kinetics model is steel-only\)/g) ?? []).length, 2, key);
    assert.ok(markup.includes('data-kinetics-model-status="unavailable"'), key);
    assert.ok(t.includes("Kinetics model unavailable for this alloy: kinetics model is steel-only."), key);
    assert.ok(!/steel-only\. kinetics model is steel-only/i.test(t), `${key}: the reason is repeated: ${t}`);
  }
});

test("TTT tab, steels: the floor-hit count line and the steel nose text, no unavailable message", () => {
  const counts: Record<string, string> = { aisi4140: "32 of 40", aisi4340: "27 of 40", aisid2: "26 of 39", aisi4340_aging720: "27 of 40" };
  for (const key of STEELS) {
    const markup = render(key, "ttt");
    const t = text(markup);
    assert.ok(markup.includes("data-ttt-floor"), key);
    assert.ok(t.includes(`${counts[key]} TTT points are on the 0.001 s incubation floor (floorHit)`), `${key}: ${t}`);
    assert.ok(!markup.includes("data-ttt-unavailable"), key);
    assert.ok(t.includes("~560 °C (Pearlite Nose) / ~420 °C (Bainite Nose)"), key);
    assert.ok(markup.includes('data-kinetics-model-status="available"'), key);
    assert.ok(t.includes("Illustrative steel template."), key);
  }
});

test("Critical Temperatures card: placeholders and steel-only values are Unavailable, Ti-6Al-4V keeps its registry Ms/Mf", () => {
  const card = (key: string) => text(render(key, "ttt"));
  assert.match(card("in718"), /Martensite Start \(\$M_s\$\) Unavailable/);
  assert.match(card("al7075"), /Martensite Finish \(\$M_f\$\) Unavailable/);
  assert.match(card("ti6al4v"), /Martensite Start \(\$M_s\$\) 800 °C/);
  assert.match(card("ti6al4v"), /Martensite Finish \(\$M_f\$\) 650 °C/);
  // the eutectoid Ae1 is a steel concept: Unavailable for the non-steels, a number for the steels
  assert.match(card("ti6al4v"), /Eutectoid Unavailable/);
  assert.match(card("aisi4140"), /Eutectoid 725 °C/);
  // the steel critical cooling rate
  assert.match(card("in718"), /Critical Cooling Rate[^]*?Unavailable/);
  assert.match(card("aisi4140"), /45 °C\/s/);
});

test("CCT tab: no diffusional start is reported for any steel row; non-steel rows are Unavailable", () => {
  for (const key of [...STEELS, ...NON_STEELS]) {
    const markup = render(key, "cct");
    assert.ok(!/>\s*(Pearlite|Bainite|Ferrite)\s*</.test(markup), `${key}: a diffusional product is shown`);
    const rows = [...markup.matchAll(/<tr[^>]*>(.*?)<\/tr>/g)].slice(1);
    assert.equal(rows.length, 10, key);
    for (const row of rows) {
      const cells = [...row[1].matchAll(/<td[^>]*>(.*?)<\/td>/g)].map((c) => text(c[1]).trim());
      assert.equal(cells[1], "Unavailable", key);
      assert.equal(cells[3], "Unavailable", key);
    }
  }
  assert.ok(render("aisi4140", "cct").includes("incubation law has no Ae3 asymptote; start not computed."));
  assert.ok(render("in718", "cct").includes("Unavailable: kinetics model is steel-only."));
});

test("CALPHAD tab: steel text only for steels (carbides for D2), verdict sentence follows the verdict", () => {
  for (const key of NON_STEELS) {
    const t = text(render(key, "calphad_vs_kinetics"));
    assert.ok(!/Ferrite|Cementite|Martensitic|athermally/.test(t), `${key}: ${t}`);
    assert.ok(t.includes("Unavailable: kinetics model is steel-only."), key);
  }
  const d2 = text(render("aisid2", "calphad_vs_kinetics"));
  assert.ok(d2.includes("Ferrite + alloy carbides (M7C3 / M23C6)"));
  assert.ok(!d2.includes("Cementite"));
  assert.ok(text(render("aisi4140", "calphad_vs_kinetics")).includes("Ferrite + Cementite / Equilibrium intermetallics"));
  // 4140 at 10 C/s: "Mixed Microstructure": not the athermal-shear sentence; 4340 at 10 C/s: "Full Martensitic"
  const mixed = text(render("aisi4140", "calphad_vs_kinetics"));
  assert.ok(mixed.includes("part of the austenite transforms by shear (martensite) and the rest by diffusion (bainite)"), mixed);
  assert.ok(!mixed.includes("athermally via shear"));
  assert.ok(text(render("aisi4340", "calphad_vs_kinetics")).includes("austenite is forced to transform athermally via shear"));
  assert.ok(text(render("aisi4140", "calphad_vs_kinetics")).includes("Fixed steel text; no equilibrium (CALPHAD) calculation is performed."));
});

test("LSW tab: unavailable above the registry solvus (Al 7075 at 720 C, AISI 4340 above Ae1), chart otherwise", () => {
  const al = render("al7075_aging720", "lsw_aging");
  assert.ok(al.includes("data-lsw-unavailable"));
  assert.ok(text(al).includes("aging temperature 720 C is at or above the registry Ae3 (solvus/transus) of 480 C"));
  assert.ok(!/1884|812\.21|Orowan Dislocation/.test(text(al)));
  const steel = render("aisi4340_aging720", "lsw_aging");
  assert.ok(steel.includes("data-lsw-unavailable"));
  assert.ok(text(steel).includes("at or above the registry Ae1 of 710 C"));
  for (const key of ["aisi4140", "aisi4340", "aisid2", "in718", "ti6al4v", "al7075"]) {
    const markup = render(key, "lsw_aging");
    assert.ok(!markup.includes("data-lsw-unavailable"), key);
    assert.ok(text(markup).includes("one molar volume serves both the matrix concentration and the precipitate"), key);
  }
});

test("Phase & Hardness tab: lookup caveat for steels, steel-only reason and no fractions for non-steels", () => {
  for (const key of STEELS) {
    const markup = render(key, "microstructure");
    assert.ok(markup.includes("data-hardness-caveat"), key);
    assert.ok(text(markup).includes("Steel lookup by cooling-rate band"), key);
    assert.ok(!markup.includes("data-phase-fractions-note"), key);
  }
  for (const key of NON_STEELS) {
    const markup = render(key, "microstructure");
    const t = text(markup);
    assert.ok(markup.includes("data-phase-fractions-note"), key);
    assert.ok(t.includes("Phase fractions: Unavailable: kinetics model is steel-only."), key);
    assert.ok(t.includes("HRC: Unavailable"), key);
    assert.ok(!/Martensite \d|Bainite \d|%/.test(t), `${key}: ${t}`);
  }
});

test("the first render uses the supplied result: the solver is not called", () => {
  const src = readFileSync(new URL("../src/components/PhaseKineticsTTTCCTStudio.tsx", import.meta.url), "utf8");
  assert.match(src, /if \(initialData\) return;/);
});
