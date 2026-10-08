import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MODULES } from "../src/data/workspaces";

const read = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const mod = (id: string) => MODULES.find(m => m.id === id)!;

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

test("weakest LPBF engines are at most Research maturity and state in one plain sentence what they are not", () => {
  for (const id of ["keyhole-raytracing"]) {
    assert.ok(["Research", "Preview"].includes(mod(id).scope), `${id} must not exceed Research`);
  }
  assert.match(mod("keyhole-raytracing").description, /prescribed cavity, not a solved free surface; empirical absorption law is not calibrated/);
  assert.match(read("src/components/KeyholeRaytracingLab.tsx"), /Prescribed cavity, not a solved free surface; the absorption law is empirical and not calibrated\./);
});

test("airgap banner does not claim an external DFT source", () => {
  assert.doesNotMatch(read("src/components/AirgapBanner.tsx"), /external DFT/);
});
