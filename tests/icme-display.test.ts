import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { ICME_UNAVAILABLE_TEXT, formatOptionalValue } from "../src/utils/icmeDisplay";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), ".."); // cwd-independent

test("formatOptionalValue: numbers carry their unit, null/undefined/NaN/Infinity are Unavailable", () => {
  assert.equal(formatOptionalValue(1191.8, "MPa"), "1191.8 MPa");
  assert.equal(formatOptionalValue(0, "mm"), "0 mm");
  for (const v of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
    assert.equal(formatOptionalValue(v, "MPa"), ICME_UNAVAILABLE_TEXT);
  }
});

test("ICME studio and service never show the old overclaiming strings and use the null-safe formatter", () => {
  const studio = readFileSync(join(ROOT, "src", "components", "ICMEMultiScalePipelineStudio.tsx"), "utf8");
  for (const old of ["Calibrated CAE Material Cards", "Passed Yield & Creep", "ASTM E1820", "Ab-Initio / Density Functional Theory",
    "DFT Atomistic", "Macro FEA Component", "Target Component FEA"]) {
    assert.ok(!studio.includes(old), `studio still contains ${old}`);
  }
  assert.ok(studio.includes("formatOptionalValue(pipelineResult.scale3_continuumPlasticity.mechanicalProperties.ultimateTensileStrength_UTS_MPa"));
  assert.ok(studio.includes("formatOptionalValue(pipelineResult.scale3_continuumPlasticity.mechanicalProperties.fractureToughness_K1c_MPa_sqrt_m"));
  assert.ok(studio.includes("lefmDamageTolerance.criticalFlawSize_ac_mm, \"mm\""));
  assert.ok(studio.includes("ultimateTensileStrength_UTS_MPa != null"), "UTS reference line must be conditional");
});

test("ICME solver output (golden) is illustrative with unavailable UTS/K_Ic and a yield-only verdict", () => {
  const doc = JSON.parse(
    readFileSync(join(ROOT, "python", "golden", "phase6a", "icme_multiscale_pipeline_solver", "step_b", "default_payload_in718.json"), "utf8"),
  );
  const out = doc.stdout;
  assert.equal(out.modelStatus, "illustrative");
  assert.equal(out.scale3_continuumPlasticity.mechanicalProperties.ultimateTensileStrength_UTS_MPa, null);
  assert.equal(out.scale3_continuumPlasticity.mechanicalProperties.fractureToughness_K1c_MPa_sqrt_m, null);
  assert.equal(out.scale4_macroComponentFEA.lefmDamageTolerance.criticalFlawSize_ac_mm, null);
  assert.ok(!/creep criteria/i.test(out.scale4_macroComponentFEA.structuralVerdict));
  assert.ok(!/calibrated card/i.test(out.caeExportCards.abaqus));
});
