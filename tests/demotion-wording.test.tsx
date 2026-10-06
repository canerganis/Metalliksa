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

test("weakest LPBF engines are at most Research maturity and state in one plain sentence what they are not", () => {
  for (const id of ["keyhole-raytracing", "murakami-fatigue", "icme-motor"]) {
    assert.ok(["Research", "Preview"].includes(mod(id).scope), `${id} must not exceed Research`);
  }
  assert.match(mod("keyhole-raytracing").description, /prescribed cavity, not a solved free surface; empirical absorption law is not calibrated/);
  assert.match(mod("murakami-fatigue").description, /steel-derived formula; surface roughness is not modelled; R enters only through an empirical power-law factor/);
  assert.match(mod("icme-motor").description, /not a calibrated strength prediction for any alloy/);
  assert.match(read("src/components/KeyholeRaytracingLab.tsx"), /Prescribed cavity, not a solved free surface; the absorption law is empirical and not calibrated\./);
  assert.match(read("src/components/MurakamiFatigueLab.tsx"), /Steel-derived formula; surface roughness not modelled\./);
  assert.match(read("src/components/ICMEMultiScalePipelineStudio.tsx"), /Not a calibrated strength prediction: tabulated constants are not matched to your alloy/);
});

test("TTT/CCT module label and header say steel heat-treatment only, not for LPBF cooling rates or alloys", () => {
  assert.equal(mod("ttt-cct-kinetics").label, "Steel-only TTT / CCT (not for LPBF alloys)");
  assert.match(mod("ttt-cct-kinetics").description, /not applicable to LPBF cooling rates or the LPBF alloys/);
  const studio = read("src/components/PhaseKineticsTTTCCTStudio.tsx");
  assert.match(studio, /Steel-only TTT \/ CCT Kinetics \(Illustrative\)/);
  assert.match(studio, /Steel heat-treatment kinetics only; not applicable to LPBF cooling rates or to the LPBF alloys\./);
});

test("elastic-constants module is labelled a calculator on user-supplied constants, not DFT", () => {
  assert.equal(mod("materials-project").label, "Elastic-constants calculator (user-supplied constants)");
  assert.doesNotMatch(read("src/components/AirgapBanner.tsx"), /external DFT/);
});
