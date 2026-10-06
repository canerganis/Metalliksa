import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { UQ_TOLERANCE_ESTIMATE_LABEL, UqModelStatusNote } from "../src/components/UqCouponReport";
import { MODULES } from "../src/data/workspaces";

const read = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const mod = (id: string) => MODULES.find(m => m.id === id)!;

test("UQ solver output is labelled an illustrative tolerance estimate on an uncalibrated response law, never an MMPDS allowable", () => {
  assert.equal(UQ_TOLERANCE_ESTIMATE_LABEL, "Illustrative tolerance estimate (uncalibrated response law)");
  const html = renderToStaticMarkup(<UqModelStatusNote modelStatus="Illustrative, not calibrated: toy model." />);
  assert.match(html, /Illustrative tolerance estimate \(uncalibrated response law\)/);
  assert.match(html, /Illustrative strength model, not calibrated/, "existing model-status text kept");
  assert.match(html, /toy model/);
  assert.match(mod("uq-lab").description, /illustrative tolerance estimate \(uncalibrated response law\), not an MMPDS allowable/);
  assert.doesNotMatch(read("src/components/UQLab.tsx"), /Distribution & Allowables/);
  assert.doesNotMatch(read("src/services/pythonComputationService.ts"), /Aerospace MMPDS Allowables Solver/);
});

test("build-job printable / risky / do-not-print verdict is labelled a screening indication and keeps its value", async () => {
  const { VerdictBanner } = await import("../src/components/3d-distortion-lab/IndustrialLPBFDecisionLab");
  const { PRINT_VERDICT_SCREENING_LABEL } = await import("../src/utils/lpbfIndustrialDecision");
  assert.equal(PRINT_VERDICT_SCREENING_LABEL, "Screening indication (not validated against build outcomes)");
  for (const verdict of ["printable", "risky", "do-not-print"] as const) {
    const html = renderToStaticMarkup(<VerdictBanner verdict={verdict} headline={`Headline ${verdict}`} reasons={[]} />);
    assert.match(html, /Screening indication \(not validated against build outcomes\)/, verdict);
    assert.match(html, new RegExp(`Headline ${verdict}`), "headline (underlying value) unchanged");
  }
});
