import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { coCHardnessText } from "../src/utils/exportAerospaceCoC";

// Review S5: the generic (non-demo) Ti-6Al-4V preset carried measuredHardnessHV 320 with a Ti hardness-to-strength
// "prediction" at 80 % "correlation confidence", printed in the CoC under "Experimental Measurement" with a ?? 330 HV
// fallback. No verified Ti HV-YS relation exists, so the prediction fields are removed and preset values are labelled.

test("CoC hardness cell never reads as a measurement", () => {
  assert.equal(coCHardnessText(undefined), "Not entered (no hardness test of this lot)");
  assert.equal(
    coCHardnessText({ illustrativeHardnessHV: 338, indentationStandard: "ASTM E384 method (illustrative demo value)" }),
    "338 HV (illustrative preset value, not measured)"
  );
});

test("generator and CoC sources carry no hardness-based strength prediction or invented fallback", () => {
  const coc = readFileSync(new URL("../src/utils/exportAerospaceCoC.ts", import.meta.url), "utf8");
  const gen = readFileSync(new URL("../src/components/AerospaceAuditReportGenerator.tsx", import.meta.url), "utf8");
  for (const [name, src] of [["exportAerospaceCoC.ts", coc], ["AerospaceAuditReportGenerator.tsx", gen]] as const) {
    assert.doesNotMatch(src, /measuredHardnessHV|predictedYieldMpa|predictedUtsMpa|correlationConfidencePct/, name);
    assert.doesNotMatch(src, /\?\? 330/, name);
    assert.doesNotMatch(src, /Tabor-Cahoon Indentation/, name);
  }
  // the generic screening preset has no hardness entry at all
  const generic = gen.slice(gen.indexOf("const GENERIC_SCREENING_PRESET"), gen.indexOf("const DEMO_SCENARIO_PRESETS"));
  assert.doesNotMatch(generic, /taborTest:/);
});
