import React from "react";
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { pythonComputationService } from "../src/services/pythonComputationService";
import {
  calphadProvenanceLabels,
  calphadUnavailableDetails,
  formatCalphadUnavailable,
  formatCriticalTemperature,
  formatFreezingRange,
  parseCalphadUnavailable,
  partitionSourceNote,
} from "../src/utils/calphadDisplay";
import { CALPHADMultiComponentStudio } from "../src/components/CALPHADMultiComponentStudio";
import type { PythonCalphadSolveResult } from "../src/services/pythonComputationService";
import { solveMultiComponentEquilibrium } from "../src/physics/calphadMultiComponentSolver";
import { parseTDBFile, PRELOADED_MULTI_COMPONENT_TDB } from "../src/physics/tdbParser";

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

// ---- Studio rendering with a solved result (test seams initialResult / initialSubTab) ----
const textOf = (markup: string) =>
  markup.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/\s+/g, " ");

function clientBase(): PythonCalphadSolveResult {
  const tdb = parseTDBFile(PRELOADED_MULTI_COMPONENT_TDB[0].rawTdbText, PRELOADED_MULTI_COMPONENT_TDB[0].name);
  const client = solveMultiComponentEquilibrium(ALLOY, tdb, 500, 1450, 50);
  return { ...client, engine: "MetalliX-Client-TS-Solver", computeTimeMs: null, isPythonEngine: false, isEmpirical: true };
}

function pycalphadResult(over: Partial<PythonCalphadSolveResult> = {}): PythonCalphadSolveResult {
  const base = clientBase();
  return {
    ...base,
    engine: "pycalphad-open-tdb",
    isPythonEngine: true,
    isEmpirical: false,
    computeTimeMs: 1234,
    thermodynamicModel: "Compound Energy Formalism (CEF) Gibbs minimisation (pycalphad equilibrium)",
    databaseUsed: "COST 507 Comprehensive Light Alloys Database",
    databaseSuitability: "Light-metal alloys with an Al, Mg or Ti base. Ni-, Fe- and Co-base alloys are outside its assessed scope and are refused.",
    criticalTemperatures: { liquidusC: 1689.5, solidusC: null, freezingRangeC: null, gammaPrimeSolvusC: null, betaTransusC: 932.9 },
    criticalTemperatureStatus: {
      solidusC: { status: "unavailable", reason: "no liquid appears inside the temperature grid, so the solidus is above the grid" },
      gammaPrimeSolvusC: { status: "unavailable", reason: "gamma-prime was identified by phase name only" },
    },
    multiElementScheil: base.multiElementScheil.map((pt) => ({ ...pt, temperatureC: null })),
    multiElementScheilNote: "Compositions follow the Scheil equation; the temperature axis is null when either is unavailable.",
    tcpEmbrittlementRisk: null,
    thermodynamicStabilityIndex: null,
    phacompAnalysis: {
      status: "unavailable",
      reason: "New-PHACOMP (Nv/Md TCP screening) applies to Ni-base superalloys only; this alloy is Ti-base",
      n_v_bar: null, m_d_bar: null, tcpEmbrittlementRisk: null, tcpSigmaRiskTemperatureC: null, thermodynamicStabilityIndex: null,
    },
    ...over,
  };
}

test("Studio shows the unavailable banner with the Python reason, scope and missing elements", () => {
  const result = {
    ...clientBase(),
    pythonUnavailable: {
      unavailableKind: "database-not-assessed-for-base",
      reason: "database 'cost507' is not assessed for Ni-base alloys (assessed base elements: AL, MG, TI)",
      reasons: ["database 'cost507' is not assessed for Ni-base alloys (assessed base elements: AL, MG, TI)"],
      missingElements: ["Cr"],
      databaseUsed: "COST 507 Comprehensive Light Alloys Database",
      databaseSuitability: "Light-metal alloys with an Al, Mg or Ti base.",
    },
  } as PythonCalphadSolveResult;
  const text = textOf(renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={result} />));
  assert.match(text, /Python CALPHAD \(pycalphad\) unavailable: database 'cost507' is not assessed for Ni-base alloys/);
  assert.match(text, /Elements missing from the database: Cr\./);
  assert.match(text, /Database scope \(COST 507 Comprehensive Light Alloys Database\): Light-metal alloys with an Al, Mg or Ti base\./);
  assert.match(text, /The numbers below come from the client-side screening model, not from CALPHAD\./);
  assert.match(text, /Compute Time: n\/a/);
  // and no banner without a Python refusal
  const none = textOf(renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={clientBase()} />));
  assert.doesNotMatch(none, /Python CALPHAD \(pycalphad\) unavailable/);
});

test("Studio shows the database scope and Unavailable cards for a pycalphad result", () => {
  const markup = renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={pycalphadResult()} />);
  const text = textOf(markup);
  assert.match(text, /Database scope: Light-metal alloys with an Al, Mg or Ti base\./);
  assert.match(text, /Solidus \(T_sol\): Unavailable/);
  assert.match(text, /γ' Solvus: Unavailable/);
  assert.match(text, /Liquidus \(T_liq\): 1689\.5°C/);
  assert.match(text, /TCP Risk: Unavailable/);
  assert.match(text, /Compute Time: 1234 ms/);
  assert.ok(markup.includes("no liquid appears inside the temperature grid"), "reason is the tooltip");
  assert.doesNotMatch(text, /null/);
});

test("Studio no longer claims adaptive refinement", () => {
  const text = textOf(renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={pycalphadResult()} />));
  assert.doesNotMatch(text, /ADAPTIVE REFINEMENT/);
  assert.doesNotMatch(text, /Adaptive Grid/);
  assert.doesNotMatch(text, /Ultra-Sharp/);
  assert.doesNotMatch(text, /two-pass bisection/);
  assert.match(text, /Liquidus \/ solidus boundary refinement/);
  assert.match(text, /there is no adaptive grid/);
});

test("Studio non-converged grid points are announced, never shown as numbers", () => {
  const text = textOf(renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={pycalphadResult({ nonConvergedPoints: [800, 825] })} />));
  assert.match(text, /2 grid point\(s\) did not converge and are shown as n\/a: 800, 825 °C\./);
});

test("Scheil tab with a null temperature axis says why instead of an empty chart", () => {
  const markup = renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={pycalphadResult()} initialSubTab="multi_scheil" />);
  const text = textOf(markup);
  assert.ok(markup.includes('data-testid="scheil-unavailable"'));
  assert.match(text, /No temperature axis: the curve needs both the liquidus and the solidus\./);
  assert.match(text, /Solidus unavailable: no liquid appears inside the temperature grid/);
  assert.doesNotMatch(text, /Liquidus unavailable/);
  assert.match(text, /not a CALPHAD Scheil calculation/);
  // with both temperatures the notice is absent
  const full = pycalphadResult({
    criticalTemperatures: { liquidusC: 1689.5, solidusC: 1650.0, freezingRangeC: 39.5 },
    multiElementScheil: clientBase().multiElementScheil,
  });
  assert.ok(!renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={full} initialSubTab="multi_scheil" />).includes("scheil-unavailable"));
});

test("no compute time is invented when the engine reports none", async () => {
  stubFetch(200, { success: true, engine: "pycalphad-open-tdb", equilibriumProfile: [{ temperatureC: 600, phases: [], totalGibbsEnergy_kJ_mol: -1 }] });
  const res = await pythonComputationService.solveCalphadEquilibrium(ALLOY);
  assert.equal(res.computeTimeMs, null);
});

test("unavailable details carry the scope, the missing elements and the convergence counts", () => {
  const u = parseCalphadUnavailable({
    status: "unavailable", unavailableKind: "pycalphad-equilibrium-failed",
    reason: "pycalphad equilibrium failed (non-finite results)", nonConvergedPoints: 39, gridPoints: 39,
    databaseSuitability: "Light-metal alloys.", databaseUsed: "COST 507", missingElements: ["Al"],
  });
  assert.ok(u);
  assert.deepEqual(calphadUnavailableDetails(u!), [
    "Elements missing from the database: Al.",
    "Database scope (COST 507): Light-metal alloys.",
    "39 of 39 grid points did not converge.",
  ]);
});
