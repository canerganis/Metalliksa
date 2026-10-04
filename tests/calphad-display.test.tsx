import React from "react";
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { pythonComputationService } from "../src/services/pythonComputationService";
import {
  calphadProvenanceLabels,
  formatCalphadUnavailable,
  formatCriticalTemperature,
  formatFreezingRange,
  parseCalphadUnavailable,
  partitionSourceNote,
} from "../src/utils/calphadDisplay";
import { CALPHADMultiComponentStudio } from "../src/components/CALPHADMultiComponentStudio";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

// Real envelope of python/calphad_solver.py on the locked interpreter (no pycalphad), trimmed.
const UNAVAILABLE = {
  success: false,
  status: "unavailable",
  unavailableKind: "pycalphad-not-installed",
  reason: "pycalphad not installed",
  reasons: ["pycalphad not installed"],
  engine: "pycalphad-open-tdb",
  pycalphadAvailable: false,
  pycalphadVersion: null,
  databaseId: "cost507",
  databaseUsed: "COST 507 Comprehensive Light Alloys Database",
  databaseStatus: "assessment",
};
const ALLOY = { name: "Ti-6Al-4V", elements: { Ti: 90, Al: 6, V: 4 }, unit: "wt_pct" as const };

function stubFetch(status: number, body: unknown) {
  globalThis.fetch = (async () =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })) as any;
}

test("parseCalphadUnavailable accepts only the unavailable envelope", () => {
  const u = parseCalphadUnavailable({ ...UNAVAILABLE, missingElements: ["Al"] });
  assert.ok(u);
  assert.equal(u!.reason, "pycalphad not installed");
  assert.deepEqual(u!.missingElements, ["Al"]);
  assert.equal(formatCalphadUnavailable(u!), "Python CALPHAD (pycalphad) unavailable: pycalphad not installed.");
  assert.equal(parseCalphadUnavailable({ success: true, equilibriumProfile: [] }), null);
  assert.equal(parseCalphadUnavailable(null), null);
});

test("a null critical temperature renders Unavailable with its reason, never a number or an empty unit", () => {
  const shown = formatCriticalTemperature(null, { status: "unavailable", reason: "the solver reached the grid bound" });
  assert.equal(shown.text, "Unavailable");
  assert.equal(shown.title, "the solver reached the grid bound");
  assert.equal(shown.available, false);
  assert.equal(formatCriticalTemperature(1689.5).text, "1689.5°C");
  assert.equal(formatFreezingRange(null), "Unavailable");
  assert.equal(formatFreezingRange(100), "100 K");
});

test("a client screening result is never labelled as pycalphad", () => {
  const client = calphadProvenanceLabels({ isPythonEngine: false, isEmpirical: true, thermodynamicModel: "x", databaseUsed: "y" });
  assert.equal(client.isPycalphad, false);
  assert.match(client.model, /not CALPHAD/);
  assert.match(client.database, /not an assessment/);
  const python = calphadProvenanceLabels({ isPythonEngine: true, isEmpirical: false, thermodynamicModel: "CEF", databaseUsed: "COST 507" });
  assert.equal(python.isPycalphad, true);
  assert.equal(python.database, "COST 507");
  assert.equal(partitionSourceNote("default-table-not-thermodynamic"), "default screening value, not CALPHAD");
  assert.equal(partitionSourceNote("tie-line"), null);
});

test("solveCalphadEquilibrium keeps the Python reason and labels the client numbers truthfully", async () => {
  stubFetch(200, UNAVAILABLE);
  const res = await pythonComputationService.solveCalphadEquilibrium(ALLOY, 500, 1450, 50);
  assert.equal(res.isPythonEngine, false);
  assert.equal(res.isEmpirical, true);
  assert.equal(res.pythonUnavailable?.reason, "pycalphad not installed");
  assert.equal(res.pythonUnavailable?.unavailableKind, "pycalphad-not-installed");
  assert.match(res.thermodynamicModel ?? "", /not CALPHAD/);
  assert.doesNotMatch(res.thermodynamicModel ?? "", /pycalphad CEF/);
  assert.notEqual(res.engine, "pycalphad-open-tdb");
});

test("a Python success passes through with null solidus and gamma-prime untouched", async () => {
  stubFetch(200, {
    success: true,
    engine: "pycalphad-open-tdb",
    isEmpirical: false,
    equilibriumProfile: [{ temperatureC: 600, phases: [], totalGibbsEnergy_kJ_mol: -1 }],
    criticalTemperatures: { liquidusC: 1689.5, solidusC: null, freezingRangeC: null, gammaPrimeSolvusC: null },
    criticalTemperatureStatus: { solidusC: { status: "unavailable", reason: "grid bound" } },
  });
  const res = await pythonComputationService.solveCalphadEquilibrium(ALLOY);
  assert.equal(res.isPythonEngine, true);
  assert.equal(res.criticalTemperatures.solidusC, null);
  assert.equal(res.criticalTemperatureStatus?.solidusC?.reason, "grid bound");
  assert.equal(res.pythonUnavailable, undefined);
});

test("Studio first paint says the numbers are not CALPHAD and no longer claims a pycalphad guarantee", () => {
  const markup = renderToStaticMarkup(<CALPHADMultiComponentStudio />);
  const text = markup.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/&amp;/g, "&").replace(/\s+/g, " ");
  assert.doesNotMatch(text, /True CALPHAD/);
  assert.doesNotMatch(text, /Rigorous Thermodynamic Trust Guarantee/);
  assert.doesNotMatch(text, /Simplified Solvus Minimizer/);
  assert.match(text, /not an assessment/);
});
