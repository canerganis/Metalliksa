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
import {
  calphadUnavailableHeadline,
  formatCoverageRow,
  formatModelCache,
  formatPartitionK,
  formatTimings,
  calphadTemperatureWindow,
} from "../src/utils/calphadResultDisplay";
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
  // calphad-use lane: an unavailable answer is never filled with client screening numbers
  assert.match(text, /Unavailable: no thermodynamic database for this system/);
  assert.match(text, /No equilibrium numbers are shown for this request/);
  assert.match(text, /No equilibrium result/);
  assert.doesNotMatch(text, /Liquidus \(T_liq\):/);
  assert.doesNotMatch(text, /Equilibrium Phase Mole Fractions/);
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

test("Scheil tab: a client screening curve with no temperature axis says why instead of an empty chart", () => {
  const client = { ...clientBase(), multiElementScheil: clientBase().multiElementScheil.map((pt) => ({ ...pt, temperatureC: null })) };
  client.criticalTemperatures = { liquidusC: 1689.5, solidusC: null, freezingRangeC: null };
  client.criticalTemperatureStatus = { solidusC: { status: "unavailable", reason: "no liquid appears inside the temperature grid" } };
  const markup = renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={client} initialSubTab="multi_scheil" />);
  const text = textOf(markup);
  assert.ok(markup.includes('data-testid="scheil-unavailable"'));
  assert.match(text, /No temperature axis: the screening curve needs both the liquidus and the solidus\./);
  assert.match(text, /Solidus unavailable: no liquid appears inside the temperature grid/);
  assert.match(text, /not a CALPHAD Scheil calculation/);
});

test("Scheil tab: an unavailable pycalphad Scheil path shows its reason and no chart", () => {
  const result = pycalphadResult({
    multiElementScheil: [],
    scheilSolidification: { status: "unavailable", reason: "the liquidus is not available on this grid, so there is no start temperature", evidence: "unvalidated" },
  });
  const markup = renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={result} initialSubTab="multi_scheil" />);
  const text = textOf(markup);
  assert.match(text, /Scheil-Gulliver path unavailable: the liquidus is not available on this grid/);
  assert.match(text, /Evidence: unvalidated/);
  assert.ok(!markup.includes("recharts-wrapper"));
  assert.doesNotMatch(text, /screening curve/);
});

test("Scheil tab: a computed pycalphad path shows the engine's own numbers with validity and evidence", () => {
  const result = pycalphadResult({
    criticalTemperatures: { liquidusC: 616.2, solidusC: 576.8, freezingRangeC: 39.4 },
    multiElementScheil: [
      { fractionSolid: 0, temperatureC: 616.5, liquidCompositions: { Al: 93, Si: 7 }, solidCompositions: null, solidPhases: [] },
      { fractionSolid: 0.48, temperatureC: 577.0, liquidCompositions: { Al: 87.5, Si: 12.5 }, solidCompositions: { Al: 98.6, Si: 1.4 }, solidPhases: ["FCC_A1"] },
      { fractionSolid: 1, temperatureC: 576.5, liquidCompositions: null, solidCompositions: { Al: 87.5, Si: 12.5 }, solidPhases: ["DIAMOND_A4", "FCC_A1"] },
    ],
    scheilSolidification: {
      status: "pycalphad-scheil-gulliver",
      terminationReason: "liquid-exhausted-within-step",
      startTemperatureC: 616.5,
      terminalTemperatureC: 576.5,
      terminalBracketC: [576.5, 577.0],
      remainingLiquidFraction: 0,
      stepC: 0.5,
      steps: 80,
      phaseAmounts: { DIAMOND_A4: 0.0556, FCC_A1: 0.9444 },
      massBalanceMaxAbsError: 2e-16,
      fractionBasis: "mole fraction of atoms",
      validity: "Scheil-Gulliver limit: no diffusion in the solid, complete mixing in the liquid.",
      evidence: "unvalidated",
    },
  });
  const text = textOf(renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={result} initialSubTab="multi_scheil" />));
  assert.match(text, /Scheil-Gulliver solidification path \(pycalphad equilibria of the remaining liquid\)/);
  assert.match(text, /End of solidification between 576\.5 and 577 °C \(liquid-exhausted-within-step\)\./);
  assert.match(text, /Solid formed \(mole fraction of atoms\): DIAMOND_A4 5\.6 %, FCC_A1 94\.4 %/);
  assert.match(text, /mass balance error 2\.0e-16/);
  assert.match(text, /Validity: Scheil-Gulliver limit/);
  assert.match(text, /Evidence: unvalidated/);
  assert.doesNotMatch(text, /not a CALPHAD Scheil calculation/);
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

// ---- calphad-use lane: provenance, cold/warm models, loading state, coverage, partition table ----

test("model cache and timings are shown as reported, never invented", () => {
  assert.equal(formatModelCache(undefined), "Model cache: not reported");
  assert.match(formatModelCache({ status: "warm" }), /^Models: warm/);
  assert.match(formatModelCache({ status: "cold", workspaceBuildMs: 604.3 }), /model construction 604 ms/);
  assert.match(formatModelCache({ status: "not-cached" }), /not cached/);
  assert.equal(formatTimings(undefined), null);
  assert.equal(formatTimings({ gridEquilibrium: 414.57, scheil: 525.9, total: 1439.9, databaseLoad: 0.48 }),
    "database 0.5 ms, grid 415 ms, Scheil path 526 ms, total 1440 ms");
});

test("unavailable headline: no database, no pycalphad, unreachable service", () => {
  const h = (kind: string) => calphadUnavailableHeadline({ unavailableKind: kind, reason: "r", reasons: ["r"] });
  assert.equal(h("no-database-covers-elements"), "Unavailable: no thermodynamic database for this system");
  assert.equal(h("database-not-assessed-for-base"), "Unavailable: no thermodynamic database for this system");
  assert.equal(h("elements-missing-from-database"), "Unavailable: no thermodynamic database for this system");
  assert.match(h("pycalphad-not-installed"), /pycalphad is not installed/);
  assert.match(h("engine-unreachable"), /did not answer/);
});

test("a 5xx or network failure is an unavailable state, not a silent client equilibrium", async () => {
  stubFetch(500, { error: "boom" });
  const res = await pythonComputationService.solveCalphadEquilibrium(ALLOY, 500, 1450, 50);
  assert.equal(res.pythonUnavailable?.unavailableKind, "engine-unreachable");
  assert.match(res.pythonUnavailable?.reason ?? "", /HTTP 500/);
  const text = textOf(renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={res} />));
  assert.match(text, /Unavailable: the Python CALPHAD service did not answer/);
  assert.doesNotMatch(text, /Liquidus \(T_liq\):/);
});

test("Studio shows provenance with the database hash, warm/cold models and measured timings", () => {
  const result = pycalphadResult({
    pycalphadVersion: "0.11.2",
    modelCache: { status: "warm", databaseSha256: "0123456789abcdef0123", workspaceBuildMs: 0 },
    timingsMs: { databaseLoad: 0.5, workspaceBuild: 0.1, gridEquilibrium: 414.6, boundaryRefinement: 489.7, scheil: 525.9, total: 1439.9 },
  });
  const markup = renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={result} />);
  const text = textOf(markup);
  assert.ok(markup.includes('data-testid="calphad-provenance"'));
  assert.match(text, /Provenance: pycalphad 0\.11\.2 equilibrium on COST 507 Comprehensive Light Alloys Database \(TDB SHA-256 0123456789ab…\)/);
  assert.match(text, /not validated against experiment/);
  assert.match(text, /Models: warm \(compiled models reused by this worker\)/);
  assert.match(text, /Measured: database 0\.5 ms, models 0\.1 ms, grid 415 ms, liquidus\/solidus refinement 490 ms, Scheil path 526 ms, total 1440 ms\./);
  // a client screening result has no provenance strip
  assert.ok(!renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={clientBase()} />).includes("calphad-provenance"));
});

test("Studio calculating state shows measured elapsed time, no invented progress, and marks old results", () => {
  const markup = renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={pycalphadResult()} initialSolving />);
  const text = textOf(markup);
  assert.ok(markup.includes('data-testid="calphad-solving"'));
  assert.match(text, /Calculating with pycalphad… 0\.0 s elapsed/);
  assert.match(text, /No completion estimate exists/);
  assert.match(text, /belong to the previous input/);
  assert.doesNotMatch(text, /\d+ ?%\s*complete/i);
  assert.ok(markup.includes('aria-busy="true"'));
});

test("Studio lists database coverage with unavailable systems and known deviations", () => {
  const coverage = [
    { id: "in718", label: "Inconel 718 (UNS N07718)", baseElement: "Ni", elements: ["Ni", "Cr"], status: "unavailable" as const,
      reason: "no thermodynamic database for this system: ...", missingElements: ["Cr", "Fe"] },
    { id: "ti6al4v", label: "Ti-6Al-4V (UNS R56400)", baseElement: "Ti", elements: ["Ti", "Al", "V"], status: "covered" as const,
      databaseId: "cost507", databaseUsed: "COST 507 Comprehensive Light Alloys Database", knownDeviation: "beta transus about 925 vs 995 degC" },
  ];
  const text = textOf(renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={pycalphadResult()} initialCoverage={coverage} />));
  assert.match(text, /Database coverage: 1 of 2 reference alloy systems/);
  assert.match(text, /Inconel 718 \(UNS N07718\): unavailable, no thermodynamic database for this system \(missing: Cr, Fe\)/);
  assert.match(text, /Ti-6Al-4V \(UNS R56400\): covered by COST 507 Comprehensive Light Alloys Database \(not validated for this alloy here\)/);
  assert.match(text, /Known deviation: beta transus about 925 vs 995 degC/);
  assert.equal(formatCoverageRow({ ...coverage[0], missingElements: [] }), "Inconel 718 (UNS N07718): unavailable, no thermodynamic database for this system");
});

test("partition table: pycalphad k with phase and temperature, null k as Unavailable with the reason", () => {
  const result = pycalphadResult({
    solutePartitioning: [
      { element: "SI", partitionCoefficient_k: 0.1123, partitionCoefficientSource: "scheil-primary-phase-tie-line", temperatureC: 615.5,
        primarySolidPhase: "FCC_A1", role: "Rejected into the liquid (k < 1): enriches the last liquid / interdendritic regions" },
      { element: "MG", partitionCoefficient_k: null, partitionCoefficientSource: "unavailable", reason: "needs the Scheil-Gulliver path",
        temperatureC: null, primarySolidPhase: null, role: null },
    ],
  });
  const markup = renderToStaticMarkup(<CALPHADMultiComponentStudio initialResult={result} initialSubTab="solute_partitioning" />);
  const text = textOf(markup);
  assert.match(text, /k = 0\.112/);
  assert.match(text, /FCC_A1 at 615\.5 °C/);
  assert.match(text, /Unavailable/);
  assert.match(text, /needs the Scheil-Gulliver path/);
  assert.doesNotMatch(text, /Matrix \(γ\) wt%/);
  assert.doesNotMatch(text, /screening value, not CALPHAD/);
  assert.equal(formatPartitionK(null), "Unavailable");
});

test("the request temperature window follows the base element so the melting range is on the grid", () => {
  assert.deepEqual(calphadTemperatureWindow({ Al: 89.5, Si: 10, Mg: 0.5 }), { tMin: 400, tMax: 750, tStep: 10 });
  assert.deepEqual(calphadTemperatureWindow({ Ti: 90, Al: 6, V: 4 }), { tMin: 600, tMax: 1750, tStep: 25 });
  assert.deepEqual(calphadTemperatureWindow({ Mg: 92, Al: 8 }), { tMin: 350, tMax: 700, tStep: 10 });
  assert.deepEqual(calphadTemperatureWindow({ Ni: 53, Cr: 19, Fe: 18 }), { tMin: 500, tMax: 1550, tStep: 25 });
  // at most 80 grid points in each window (the engine's cap)
  for (const w of [calphadTemperatureWindow({ Al: 1 }), calphadTemperatureWindow({ Ti: 1 }), calphadTemperatureWindow({ Ni: 1 })]) {
    assert.ok((w.tMax - w.tMin) / w.tStep + 1 <= 80);
  }
});
