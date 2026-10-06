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
