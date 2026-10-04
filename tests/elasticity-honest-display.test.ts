import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { isDftUnavailable, pythonComputationService } from "../src/services/pythonComputationService";
import { UNAVAILABLE_TEXT, directionLabel, formatOrUnavailable, formatZener, provenanceLine } from "../src/utils/elasticityDisplay";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const stubFetch = (body: unknown, status = 200) =>
  (async () => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })) as typeof fetch;

async function withFetch<T>(impl: typeof fetch, run: () => Promise<T>): Promise<T> {
  const previousFetch = globalThis.fetch;
  const previousWarn = console.warn;
  console.warn = () => {};
  globalThis.fetch = impl;
  try {
    return await run();
  } finally {
    globalThis.fetch = previousFetch;
    console.warn = previousWarn;
  }
}

test("formatters render null / NaN as Unavailable, never 0 or a default", () => {
  assert.equal(formatOrUnavailable(467.3, "K"), "467.3 K");
  assert.equal(formatOrUnavailable(0, "K"), "0 K");
  for (const bad of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
    assert.equal(formatOrUnavailable(bad as number | null | undefined, "K"), UNAVAILABLE_TEXT);
  }
  assert.equal(formatZener(3.21), "3.21");
  assert.equal(formatZener(null), "n/a (cubic crystals only)");
  assert.equal(directionLabel({ direction: "[110]", hkl: [1, 1, 0], label: "(1,1,0) Cartesian", youngsModulusGPa: 1, ratioToAverage: 1 }), "(1,1,0) Cartesian");
  assert.equal(directionLabel({ direction: "[110]", hkl: [1, 1, 0], youngsModulusGPa: 1, ratioToAverage: 1 }), "[110]");
});

test("provenance line carries the not-DFT label and the reference status", () => {
  const line = provenanceLine({
    label: "Continuum elasticity: Voigt-Reuss-Hill homogenisation (not a DFT calculation)",
    sourceNotes: "Built-in elastic-constants library entry",
    referenceStatus: "unverified",
  });
  assert.match(line, /not a DFT calculation/);
  assert.match(line, /reference status: unverified/);
  assert.doesNotMatch(provenanceLine({}), /Authentic/);
});

test("an unavailable Python body is returned as unavailable, with the reason and no numbers", async () => {
  const body = { success: false, status: "unavailable", unavailableCode: "NO_ELASTIC_CONSTANTS", reason: "no exact library entry", engine: "fixture", isDft: false };
  const result = await withFetch(stubFetch(body), () => pythonComputationService.calculateDFTProperties({ formula: "Al2O3" }));
  assert.equal(isDftUnavailable(result), true);
  assert.equal(result.success, false);
  assert.equal((result as { reason: string }).reason, "no exact library entry");
  assert.equal("acousticAndThermalProperties" in result, false);
  assert.equal("elasticStiffnessMatrix_Cij_GPa" in result, false);
});

test("Python unreachable / HTTP error / empty body: unavailable, not the old invented client numbers", async () => {
  const unreachable = await withFetch((async () => { throw new Error("offline"); }) as typeof fetch, () => pythonComputationService.calculateDFTProperties({ formula: "Ni" }));
  const http500 = await withFetch(stubFetch({ error: "boom" }, 500), () => pythonComputationService.calculateDFTProperties({ formula: "Ni" }));
  const noTensor = await withFetch(stubFetch({ success: true }), () => pythonComputationService.calculateDFTProperties({ formula: "Ni" }));
  for (const [outcome, code] of [[unreachable, "PYTHON_UNREACHABLE"], [http500, "PYTHON_HTTP_ERROR"], [noTensor, "PYTHON_BAD_RESPONSE"]] as const) {
    assert.equal(isDftUnavailable(outcome), true, code);
    assert.equal((outcome as { unavailableCode: string }).unavailableCode, code);
    for (const key of ["acousticAndThermalProperties", "voigtReussHillModuli", "elasticStiffnessMatrix_Cij_GPa"]) {
      assert.equal(key in outcome, false, `${code}: ${key}`);
    }
  }
  const notRequested = await pythonComputationService.calculateDFTProperties({ formula: "Ni" }, false);
  assert.equal(isDftUnavailable(notRequested), true);
});

test("a genuine Python result is passed through unchanged and marked available", async () => {
  const body = {
    success: true, status: "available", engine: "fixture", computeTimeMs: 3.5, isDft: false,
    elasticStiffnessMatrix_Cij_GPa: [[1]],
    acousticAndThermalProperties: { debyeTemperature_K: null, reason: "no density" },
  };
  const result = await withFetch(stubFetch(body), () => pythonComputationService.calculateDFTProperties({ formula: "Ni" }));
  assert.equal(isDftUnavailable(result), false);
  assert.equal(result.isPythonEngine, true);
  assert.equal(result.computeTimeMs, 3.5);
  assert.equal((result as { acousticAndThermalProperties: { debyeTemperature_K: number | null } }).acousticAndThermalProperties.debyeTemperature_K, null);
});

test("the explorer sends no stand-in K/G/density/nsites and shows no DFT claim for the engine tab", () => {
  const source = readFileSync(join(ROOT, "src", "components", "MaterialsProjectExplorer.tsx"), "utf8");
  assert.doesNotMatch(source, /k_vrh:\s*selectedDoc\.k_vrh\s*\|\|/);
  assert.doesNotMatch(source, /g_vrh:\s*selectedDoc\.g_vrh\s*\|\|/);
  assert.doesNotMatch(source, /density:\s*selectedDoc\.density\s*\|\|/);
  assert.doesNotMatch(source, /nsites:\s*selectedDoc\.nsites/);
  assert.doesNotMatch(source, /Python DFT HPC Engine|ab-initio 6x6/);
  assert.doesNotMatch(source, /computeTimeMs\s*\|\|\s*10/);
  const service = readFileSync(join(ROOT, "src", "services", "pythonComputationService.ts"), "utf8");
  assert.doesNotMatch(service, /debyeTemperature_K:\s*450/);
  assert.doesNotMatch(service, /Client-Symmetry-Continuum/);
});
