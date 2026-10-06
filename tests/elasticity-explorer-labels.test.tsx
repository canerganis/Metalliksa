import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { MaterialsProjectExplorer } from "../src/components/MaterialsProjectExplorer";
import { ElasticityResultPanel } from "../src/components/MaterialsProjectElasticityPanel";
import type { PythonDFTOutcome } from "../src/services/pythonComputationService";

// Real Python output: python/test_elasticity_oracle.py FixtureTest fails when this file differs from the
// module (the payloads are stored next to each result).
const FIXTURES = JSON.parse(readFileSync(new URL("./fixtures/elasticity-results.json", import.meta.url), "utf8"));
const outcome = (name: string, computeTimeMs: number | null): PythonDFTOutcome => ({
  ...FIXTURES[name].result,
  isPythonEngine: true,
  computeTimeMs,
});
const panel = (o: PythonDFTOutcome | null, computing = false) =>
  renderToStaticMarkup(<ElasticityResultPanel outcome={o} computing={computing} />);
const text = (markup: string) =>
  markup.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/&amp;/g, "&").replace(/\s+/g, " ");
const count = (haystack: string, needle: string) => haystack.split(needle).length - 1;
const BANNED = [/ab-initio/i, /Authentic/, /DFT HPC/, /Python DFT/, /Python 6x6/];

test("Explorer starts with blank user inputs and identifies continuum elasticity, not DFT", () => {
  const raw = renderToStaticMarkup(<MaterialsProjectExplorer />);
  const markup = text(raw);
  assert.ok(markup.includes("Elastic-constants calculator (user-supplied constants)"), "module label");
  assert.ok(markup.includes("Continuum Elasticity Homogenization"), "model label");
  assert.ok(markup.includes("Not a DFT Calculation"), "claim boundary");
  assert.ok(markup.includes("Calculate Elasticity"));
  assert.ok(!raw.includes('value="Fe3C"'), "no canned initial formula");
  assert.ok(markup.includes("Unavailable"), "no result before user calculation");
  assert.ok(!markup.includes("Python 6x6 C_ij"), "old tab label");
});

test("available library result: provenance line says not DFT, one reference status, real numbers", () => {
  const out = text(panel(outcome("libraryNi3Al", 1.5)));
  assert.ok(out.includes("not a DFT calculation"), "provenance label");
  assert.ok(out.includes("Built-in elastic-constants library entry"));
  assert.equal(count(out, "reference status: experimental-single-crystal"), 1, "reference status once");
  assert.ok(out.includes("Kayser & Stassis"));
  assert.ok(out.includes("Compute Time: 1.5 ms"));
  assert.ok(/Debye Temp \(\$\\Theta_D\$\) \d+(\.\d+)? K/.test(out), out.slice(0, 600));
  assert.ok(!out.includes("Unavailable"));
  assert.ok(out.includes("Zener Factor $A_Z$: 3.324"));
  for (const banned of BANNED) assert.doesNotMatch(out, banned);
});

test("no compute time is shown when the engine reported none (no invented 0 ms)", () => {
  for (const name of ["libraryNi3Al", "unavailableAl2O3"]) {
    const markup = panel(outcome(name, null));
    assert.ok(!markup.includes("Compute Time"), name);
    assert.ok(!/\b0 ms\b/.test(text(markup)), name);
  }
});

test("unavailable outcome: the reason is shown, no tensor, no compute time, no number", () => {
  const markup = panel(outcome("unavailableAl2O3", null));
  const out = text(markup);
  assert.ok(markup.includes('data-testid="elasticity-unavailable"'));
  assert.ok(out.includes("Unavailable"));
  assert.ok(out.includes("no exact library entry for this formula"));
  assert.ok(!out.includes("Stiffness Tensor"));
  assert.ok(!markup.includes("elasticity-provenance"));
});

test("no composition: Debye is Unavailable with its reason, non-cubic Zener n/a, Cartesian direction labels", () => {
  const markup = panel(outcome("hexCustomNoComposition", 2));
  const out = text(markup);
  assert.ok(out.includes("Debye Temp ($\\Theta_D$) Unavailable"));
  assert.ok(markup.includes("there is no default molar mass"), "reason tooltip");
  assert.ok(out.includes("n/a (cubic crystals only)"));
  assert.ok(out.includes("(1,1,0) Cartesian"));
  assert.ok(out.includes("Custom User Elastic Constants"));
  assert.equal(count(out, "reference status: supplied-by-caller"), 1);
});

test("unstable tensor: velocities and E(n) are Unavailable with the reason", () => {
  const out = text(panel(outcome("unstableCubic", 2)));
  assert.ok(out.includes("Unavailable: the stiffness tensor is not mechanically stable"));
  assert.ok(/Longitudinal \$v_l\$ Unavailable/.test(out));
  assert.ok(!out.includes("NaN") && !out.includes("undefined") && !out.includes("null"));
});

test("computing state and empty state do not show a result", () => {
  assert.ok(text(panel(null, true)).includes("Homogenising the 6x6 stiffness tensor"));
  assert.ok(!text(panel(null, false)).includes("Stiffness Tensor"));
});
