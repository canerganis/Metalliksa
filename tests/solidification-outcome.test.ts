import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { solidificationOutcome } from "../src/utils/solidificationOutcome";
import type { SolidificationMicrostructureResult } from "../src/services/pythonComputationService";

// Real Python output (the same blocks python/test_lpbf_build_job.py check_microstructure_fixture() pins).
const BLOCKS = JSON.parse(readFileSync(new URL("./fixtures/build-job-microstructure-blocks.json", import.meta.url), "utf8"));
const as = (block: unknown) => block as SolidificationMicrostructureResult;

test("available and screening-fallback pass through with their status", () => {
  const ok = solidificationOutcome(as(BLOCKS.available_in718_285_960));
  assert.ok("result" in ok && ok.result.status === "available");
  const fb = solidificationOutcome(as(BLOCKS.screening_fallback_in718_60_2000));
  assert.ok("result" in fb && fb.result.status === "screening-fallback");
  assert.equal(fb.result.reason, BLOCKS.screening_fallback_in718_60_2000.reason);
});

test("unavailable yields Python's reason and never a result", () => {
  const out = solidificationOutcome(as(BLOCKS.unavailable_no_kinetics));
  assert.deepEqual(out, { error: "thermal.solidificationKinetics missing or non-finite" });
  assert.deepEqual(solidificationOutcome(as({ status: "unavailable" })), { error: "no solidification data" });
});

test("a block without status, null, or non-finite numbers is an error, not a result", () => {
  assert.deepEqual(solidificationOutcome(as({ source: "rosenthal-analytical-screening", G_K_m: 1e4, R_m_s: 0.6, coolingRate_K_s: 6788, PDAS_um: 0.9, SDAS_um: 3.5 })), { error: "legacy result without status" });
  assert.deepEqual(solidificationOutcome(null), { error: "legacy result without status" });
  assert.ok("error" in solidificationOutcome(as({ ...BLOCKS.available_in718_285_960, G_K_m: null })));
  assert.ok("error" in solidificationOutcome(as({ ...BLOCKS.available_in718_285_960, PDAS_um: Number.NaN })));
});

test("the Lab routes every result through the guard", () => {
  const source = readFileSync("src/components/SolidificationMicrostructureLab.tsx", "utf8");
  assert.match(source, /const outcome = solidificationOutcome\(res\);/);
  assert.match(source, /setResult\(outcome\.result\);/);
  assert.ok(!/setResult\(res\)/.test(source));
  assert.ok(!/source\.includes\('rosenthal'\)/.test(source));
  assert.ok(!/Preset supplies k, liquidus and absorptivity/.test(source));
});
