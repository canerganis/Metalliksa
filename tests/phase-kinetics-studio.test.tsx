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
// Lane kin-li: the Li (1998) model is available for the steels inside its composition range (AISI 4140, AISI 4340);
// AISI D2 (outside the range) and the non-steels are unavailable with the reason.
const NON_STEELS = ["in718", "ti6al4v", "al7075", "al7075_aging720"];
const MODELLED = ["aisi4140", "aisi4340", "aisi4340_aging720"];
const UNAVAILABLE = [...NON_STEELS, "aisid2"];
const D2_REASON = "composition outside the Li (1998) model range: C 1.55 wt% (range 0.1 < C < 0.5)";

const render = (key: string, tab: PhaseKineticsStudioTab, coolingRate = 10) =>
  renderToStaticMarkup(
    <PhaseKineticsTTTCCTStudio initialAlloy={ALLOY_OF[key]} initialData={FIXTURE[key]} initialTab={tab} initialCoolingRate={coolingRate} />
  );
const text = (markup: string) =>
  markup.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/&gt;/g, ">").replace(/&lt;/g, "<").replace(/&amp;/g, "&").replace(/\s+/g, " ");
const BAD = /\b(null|NaN|undefined|Infinity)\b/;

test("fixture holds the real solver output for the eight cases", () => {
  assert.deepEqual(Object.keys(FIXTURE), Object.keys(ALLOY_OF));
  for (const key of UNAVAILABLE) assert.equal(FIXTURE[key].kineticsModel?.status, "unavailable", key);
  for (const key of MODELLED) assert.equal(FIXTURE[key].kineticsModel?.status, "available", key);
  for (const key of MODELLED) assert.equal(FIXTURE[key].kineticsModel?.validationStatus, "unvalidated", key);
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

test("TTT tab, unavailable cases: the reason, no curves, no nose numbers, a single non-repeating banner", () => {
  for (const key of UNAVAILABLE) {
    const markup = render(key, "ttt");
    const t = text(markup);
    const reason = key === "aisid2" ? D2_REASON : "kinetics model is steel-only";
    assert.ok(markup.includes("data-ttt-unavailable"), key);
    assert.ok(t.includes(`TTT curves unavailable: ${reason}`), `${key}: ${t}`);
    assert.ok(!markup.includes("data-ttt-floor"), key);
    assert.ok(!/~560|Pearlite Nose|Bainite Nose|Ferrite \d{3} °C \(/.test(t), `${key}: ${t}`);
    assert.ok(markup.includes('data-kinetics-model-status="unavailable"'), key);
    assert.ok(t.includes(`Kinetics model unavailable for this alloy: ${reason}`), key);
    if (key !== "aisid2") assert.ok(!/steel-only\. kinetics model is steel-only/i.test(t), `${key}: the reason is repeated: ${t}`);
  }
});

test("TTT tab, Li-model steels: headline with the labels, nose per phase from the solver points, no floor line", () => {
  for (const key of MODELLED) {
    const markup = render(key, "ttt");
    const t = text(markup);
    assert.ok(!markup.includes("data-ttt-unavailable"), key);
    assert.ok(!markup.includes("data-ttt-floor"), key);
    assert.ok(markup.includes('data-kinetics-model-status="available"'), key);
    assert.ok(t.includes("Li et al. (1998) TTT/CCT model (screening, unvalidated)."), `${key}: ${t}`);
    assert.ok(!t.includes("Illustrative steel template."), key);
    assert.match(t, /Shortest 1 % Start \(Listed Points\): Ferrite \d+ °C \([\d.e+]+ s\) \/ Pearlite \d+ °C \([\d.e+]+ s\) \/ Bainite \d+ °C \([\d.e+]+ s\)/, key);
    assert.ok(t.includes(`Martensite Start: ${FIXTURE[key].criticalTransformationTemperatures.Ms_C} °C (athermal)`), key);
  }
});

test("Critical Temperatures card: Li-model values for 4140, placeholders/steel-only Unavailable, registry values for D2", () => {
  const card = (key: string) => text(render(key, "ttt"));
  assert.match(card("in718"), /Martensite Start \(\$M_s\$\) Unavailable/);
  assert.match(card("al7075"), /Martensite Finish \(\$M_f\$\) Unavailable/);
  assert.match(card("ti6al4v"), /Martensite Start \(\$M_s\$\) 800 °C/);
  assert.match(card("ti6al4v"), /Martensite Finish \(\$M_f\$\) 650 °C/);
  assert.match(card("ti6al4v"), /Eutectoid Unavailable/);
  // AISI 4140: Grange Ae3/Ae1, Li Bs, Kung-Rayment Ms, Mf not modelled, model critical cooling rate (was 780/725/330/180/45)
  assert.match(card("aisi4140"), /780\.3 °C/);
  assert.match(card("aisi4140"), /Eutectoid 739\.9 °C/);
  assert.match(card("aisi4140"), /Bainite Start \(\$B_s\$\) 541\.8 °C/);
  assert.match(card("aisi4140"), /Martensite Start \(\$M_s\$\) 328\.5 °C/);
  assert.match(card("aisi4140"), /Martensite Finish \(\$M_f\$\) Unavailable/);
  assert.match(card("aisi4140"), /19\.81 °C\/s/);
  assert.ok(!/45 °C\/s/.test(card("aisi4140")));
  // AISI D2 is outside the model: registry echoes, no Bs, no critical cooling rate
  assert.match(card("aisid2"), /Bainite Start \(\$B_s\$\) Unavailable/);
  assert.match(card("aisid2"), /Critical Cooling Rate[^]*?Unavailable/);
  assert.match(card("in718"), /Critical Cooling Rate[^]*?Unavailable/);
});

test("CCT tab: Li-model starts for the modelled steels, Unavailable rows otherwise", () => {
  const cells = (key: string) =>
    [...render(key, "cct").matchAll(/<tr[^>]*>(.*?)<\/tr>/g)].slice(1).map((row) =>
      [...row[1].matchAll(/<td[^>]*>(.*?)<\/td>/g)].map((c) => text(c[1]).trim())
    );
  for (const key of UNAVAILABLE) {
    const rows = cells(key);
    assert.equal(rows.length, 10, key);
    for (const row of rows) {
      assert.equal(row[1], "Unavailable", key);
      assert.equal(row[3], "Unavailable", key);
      assert.equal(row[4], "Unavailable", key);
    }
  }
  const rows4140 = cells("aisi4140");
  assert.deepEqual(rows4140.map((r) => `${r[0]} | ${r[1]} | ${r[3]}`), [
    "0.05 °C/s | 721.3 °C | Ferrite",
    "0.2 °C/s | 689.3 °C | Ferrite",
    "1 °C/s | 611.1 °C | Pearlite",
    "5 °C/s | 479.1 °C | Bainite",
    "10 °C/s | 448.6 °C | Bainite",
    "25 °C/s | 328.5 °C | Martensite (Athermal)",
    "50 °C/s | 328.5 °C | Martensite (Athermal)",
    "100 °C/s | 328.5 °C | Martensite (Athermal)",
    "500 °C/s | 328.5 °C | Martensite (Athermal)",
    "2000 °C/s | 328.5 °C | Martensite (Athermal)",
  ]);
  assert.equal(rows4140[0][4], "F 721.3 / P 691.9 / B 531.6 °C");
  assert.equal(rows4140[9][4], "F - / P - / B - °C");
  for (const r of rows4140) assert.equal(r[5], "Unavailable"); // martensite %: fractions not computed
  assert.ok(render("in718", "cct").includes("Unavailable: kinetics model is steel-only."));
  assert.ok(render("aisid2", "cct").includes("Unavailable: the composition is outside the range stated for the Li (1998) model."));
});

test("CALPHAD tab: steel text only for the modelled steels, verdict sentence follows the Li verdict", () => {
  for (const key of UNAVAILABLE) {
    const t = text(render(key, "calphad_vs_kinetics"));
    assert.ok(!/Ferrite \+|Cementite|athermally/.test(t), `${key}: ${t}`);
  }
  assert.ok(text(render("in718", "calphad_vs_kinetics")).includes("Unavailable: kinetics model is steel-only."));
  assert.ok(text(render("aisid2", "calphad_vs_kinetics")).includes(`Unavailable: ${D2_REASON}`));
  const s4140 = text(render("aisi4140", "calphad_vs_kinetics"));
  assert.ok(s4140.includes("Ferrite + Cementite / Equilibrium intermetallics"));
  assert.ok(s4140.includes("Bainite start at 448.6 C (Li 1998 additivity); phase fractions not computed"), s4140);
  assert.ok(s4140.includes("the Li (1998) additivity model reaches a bainite start above Ms; the phase fractions are not computed."));
  assert.ok(s4140.includes("Model Critical Cooling Rate: 19.81 °C/s"));
  assert.ok(!s4140.includes("athermally"));
  const s4340 = text(render("aisi4340", "calphad_vs_kinetics"));
  assert.ok(s4340.includes("no ferrite, pearlite or bainite start is reached above Ms"), s4340);
  assert.ok(s4340.includes("95.2%"), s4340);
  assert.ok(s4140.includes("Fixed steel text; no equilibrium (CALPHAD) calculation is performed."));
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

test("Phase & Hardness tab: fractions and hardness are Unavailable with the reason, never numbers", () => {
  for (const key of MODELLED) {
    const markup = render(key, "microstructure");
    const t = text(markup);
    assert.ok(markup.includes("data-phase-fractions-note"), key);
    assert.ok(t.includes("Phase fractions: Unavailable: phase fractions and hardness are not computed"), key);
    assert.ok(markup.includes("data-hardness-caveat"), key);
    assert.ok(t.includes("HRC: Unavailable"), key);
    assert.ok(!t.includes("Steel lookup by cooling-rate band"), key);
    assert.ok(!/Martensite \d|Bainite \d|\d%/.test(t), `${key}: ${t}`);
  }
  for (const key of UNAVAILABLE) {
    const markup = render(key, "microstructure");
    const t = text(markup);
    assert.ok(markup.includes("data-phase-fractions-note"), key);
    assert.ok(t.includes("HRC: Unavailable"), key);
    assert.ok(!/Martensite \d|Bainite \d|\d%/.test(t), `${key}: ${t}`);
  }
  assert.ok(text(render("in718", "microstructure")).includes("Phase fractions: Unavailable: kinetics model is steel-only."));
});

test("the first render uses the supplied result: the solver is not called", () => {
  const src = readFileSync(new URL("../src/components/PhaseKineticsTTTCCTStudio.tsx", import.meta.url), "utf8");
  assert.match(src, /if \(initialData\) return;/);
});
