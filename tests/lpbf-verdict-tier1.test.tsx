import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { BlockingGateSummary, formatIterationGates } from "../src/components/LpbfBayesianOptimizerLab";
import { toActionableReason } from "../src/utils/lpbfActionableReasons";
import type { PythonBayesianOptimizationResult } from "../src/services/pythonComputationService";

const read = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const text = (markup: string) => markup.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/\s+/g, " ");

// Shape and strings from python/lpbf_bayesian_optimizer.py (_iteration_diagnostics, _gate_summary, KEYHOLE_GATE_NOTE).
const PY_OPT = read("python/lpbf_bayesian_optimizer.py");
const KEYHOLE_NOTE = (() => {
  const m = /KEYHOLE_GATE_NOTE = \(\s*((?:'[^']*'\s*)+)\)/.exec(PY_OPT);
  assert.ok(m, "KEYHOLE_GATE_NOTE not found");
  return [...m[1].matchAll(/'([^']*)'/g)].map((x) => x[1]).join("");
})();

test("per-iteration gate cell separates failing, risk and advisory-only gates", () => {
  const d = {
    blockingGates: ["keyhole"], riskGates: ["balling", "literature_pv"], advisoryGates: ["recoater", "distortion"],
    reasons: [], extentStatus: "computed", normalizedEnthalpy: 47.29, aspectRatio_L_over_W: 7.59,
    keyholeRisk: "High", keyholeHigh: true,
  };
  assert.equal(formatIterationGates(d), "fail: keyhole; warn: balling, literature_pv; advisory (no verdict effect): recoater, distortion");
  assert.equal(formatIterationGates({ ...d, blockingGates: [], riskGates: [], advisoryGates: [] }), "none");
});

test("all-zero run shows the dominant blocking gates and the frozen keyhole note", () => {
  const result = {
    success: true, alloyId: "in718", bestScore: 0, iterations: [], converged: false, elapsedMs: 1, nIterations: 20,
    noPositiveScore: true,
    gateSummary: { blockingGateCounts: { keyhole: 15 }, riskGateCounts: { literature_pv: 19, balling: 11 },
      inconclusiveExtentStatusCounts: { "heuristic-width-fallback": 9 } },
    keyholeGateNote: KEYHOLE_NOTE,
  } as PythonBayesianOptimizationResult;
  const t = text(renderToStaticMarkup(<BlockingGateSummary result={result} />));
  assert.match(t, /Do-not-print \(failing gate\): keyhole ×15/);
  assert.match(t, /Inconclusive \(melt-pool extent not resolved\): heuristic-width-fallback ×9/);
  assert.match(t, /balling ×11/);
  assert.match(t, /frozen thermal solver/);
  assert.match(t, /pending a planned implementation bump/);
  // A backend without the summary is reported, not hidden.
  const bare = text(renderToStaticMarkup(<BlockingGateSummary result={{ ...result, gateSummary: undefined, keyholeGateNote: undefined }} />));
  assert.match(bare, /Gate summary not returned/);
  assert.match(bare, /Keyhole gate note not returned/);
});

test("optimizer table has the failing-gate diagnostic columns", () => {
  const src = read("src/components/LpbfBayesianOptimizerLab.tsx");
  for (const col of ["Failing gates", "Extent", "ΔH/hₛ", "L/W", "Keyhole flag"]) assert.match(src, new RegExp(`<th scope="col"[^>]*>${col}</th>`), col);
  assert.ok(src.includes("<BlockingGateSummary result={result} />"));
});

test("advisory reasons get no P/v action; balling screen still gets its action", () => {
  const adv = "Advisory: inherent-strain distortion index 7.59 (≥0.65) — parameter-independent alloy/layer advisory: the frozen distortion index depends only on alloy properties, preheat and layer thickness (not on P, v or hatch); it does not change the verdict.";
  assert.equal(toActionableReason(adv), adv);
  const rec = "Advisory: recoater crash / part curl flag High (distortion index 7.59 > 2.0) — parameter-independent alloy/layer advisory.";
  assert.equal(toActionableReason(rec), rec);
  assert.match(toActionableReason("Plateau–Rayleigh balling screen: L/W = 7.59 (> 3.8) — steady-Rosenthal aspect-ratio screen."), /Action:/);
});

test("Python advisory / balling-screen wording and the 'advisory' gate status reach the TS contract", () => {
  const py = read("python/lpbf_build_job_solver.py");
  assert.match(py, /ADVISORY_GATES = \("recoater", "distortion"\)/);
  assert.match(py, /not a demonstrated balling/);
  assert.match(py, /rec_status = "advisory" if recoater_high else "pass"/);
  assert.match(py, /dist_status = "advisory" if distortion_high else "pass"/);
  const ts = read("src/services/pythonComputationService.ts");
  assert.match(ts, /export type PythonLpbfGateStatus = "pass" \| "warn" \| "fail" \| "unavailable" \| "advisory";/);
  const banner = read("src/components/3d-distortion-lab/IndustrialLPBFDecisionLab.tsx");
  assert.match(banner, /g\.status === "advisory"/);
});
