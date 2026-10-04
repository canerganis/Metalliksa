import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { pythonComputationService } from "../src/services/pythonComputationService";
import type { TafelDataset } from "../src/types/tafel";

// tafelPythonService imports src/utils/tafelParser.ts, which throws at module load
// (pre-existing BUG 1, see tests/tafel-autofit.test.ts). Only that exact signature is
// tolerated: the two executePythonTafelFit tests are then marked todo.
type TafelServiceModule = typeof import("../src/utils/tafelPythonService");
let tafelService: TafelServiceModule | undefined;
let bug1: Error | undefined;
try {
  tafelService = await import("../src/utils/tafelPythonService");
} catch (error) {
  if (error instanceof Error && /Fabrication of Tafel/.test(error.message)) bug1 = error;
  else throw error;
}
const tafelTodo = bug1 ? "BLOCKED by BUG 1: tafelParser.ts throws on import (createBenchmarkDataset)" : false;
const executePythonTafelFit: TafelServiceModule["executePythonTafelFit"] = (...args) => {
  if (!tafelService) throw bug1;
  return tafelService.executePythonTafelFit(...args);
};
import {
  PythonValidationError,
  isPythonValidationError,
  validationErrorFromResponse,
} from "../src/utils/pythonValidationError";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

const POURBAIX_ENVELOPE = {
  success: false,
  error: {
    code: "UNKNOWN_ELEMENT",
    field: "element",
    message: "No Pourbaix system for element 'Mo'; supported: Fe, Cr, Ni, Ti, Al, Cu, Zn, Mg.",
    detail: { element: "'Mo'" },
  },
  errorKind: "validation",
};
const TAFEL_ENVELOPE = {
  success: false,
  error: { code: "UNKNOWN_ALLOY", field: "alloyId", message: "Unknown alloy 'duplex2205' for domain 'corrosion'.", detail: {} },
  errorKind: "validation",
};

function stubFetch(status: number, body: unknown) {
  const calls: string[] = [];
  globalThis.fetch = (async (url: string) => {
    calls.push(String(url));
    return new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }) as any;
  return calls;
}

function stubNetworkError() {
  globalThis.fetch = (async () => {
    throw new TypeError("fetch failed");
  }) as any;
}

test("validationErrorFromResponse only accepts a 422 validation envelope", async () => {
  const err = await validationErrorFromResponse(new Response(JSON.stringify(TAFEL_ENVELOPE), { status: 422 }), "Tafel");
  assert.ok(err instanceof PythonValidationError);
  assert.equal(err!.code, "UNKNOWN_ALLOY");
  assert.equal(err!.field, "alloyId");
  assert.equal(err!.message, "Tafel: Unknown alloy 'duplex2205' for domain 'corrosion'.");
  assert.equal(await validationErrorFromResponse(new Response(JSON.stringify(TAFEL_ENVELOPE), { status: 500 }), "x"), null);
  assert.equal(await validationErrorFromResponse(new Response(JSON.stringify({ error: "x" }), { status: 422 }), "x"), null);
  assert.equal(await validationErrorFromResponse(new Response("not json", { status: 422 }), "x"), null);
});

test("solvePourbaixDiagram throws the envelope message on 422", async () => {
  stubFetch(422, POURBAIX_ENVELOPE);
  await assert.rejects(
    pythonComputationService.solvePourbaixDiagram({ element: "Mo" }),
    (err: unknown) => {
      assert.ok(isPythonValidationError(err));
      assert.equal((err as Error).message,
        "Pourbaix: No Pourbaix system for element 'Mo'; supported: Fe, Cr, Ni, Ti, Al, Cu, Zn, Mg.");
      return true;
    },
  );
});

test("solvePourbaixDiagram keeps the old error for other HTTP failures", async () => {
  stubFetch(500, { error: "boom" });
  await assert.rejects(pythonComputationService.solvePourbaixDiagram({ element: "Fe" }), {
    message: "Pourbaix proxy error: HTTP 500",
  });
});

const TAFEL_INPUT = {
  iCorr_uA_cm2: 2,
  eCorr_V: -0.3,
  betaA: 0.1,
  betaC: 0.12,
  alloyId: "duplex2205",
  specimenAreaCm2: 1,
  initialThicknessMm: 5,
  allowableLossMm: 1.5,
  temperatureC: 25,
} as any;

test("calculateTafelCorrosionRate propagates a 422 instead of using the client formula", async () => {
  stubFetch(422, TAFEL_ENVELOPE);
  await assert.rejects(pythonComputationService.calculateTafelCorrosionRate(TAFEL_INPUT), (err: unknown) => {
    assert.ok(isPythonValidationError(err));
    assert.match((err as Error).message, /^Tafel: Unknown alloy 'duplex2205'/);
    return true;
  });
});

test("calculateTafelCorrosionRate still falls back for 5xx, error bodies and network errors", async () => {
  stubFetch(500, { error: "boom" });
  let res = await pythonComputationService.calculateTafelCorrosionRate(TAFEL_INPUT);
  assert.ok(res.corrosionRateMmYr > 0);
  stubFetch(200, { success: false, error: "internal" });
  res = await pythonComputationService.calculateTafelCorrosionRate(TAFEL_INPUT);
  assert.ok(res.corrosionRateMmYr > 0);
  stubNetworkError();
  res = await pythonComputationService.calculateTafelCorrosionRate(TAFEL_INPUT);
  assert.ok(res.corrosionRateMmYr > 0);
});

// Small deterministic Butler-Volmer-shaped curve (synthetic test input, not data).
const DATASET: TafelDataset = {
  id: "synthetic",
  name: "synthetic",
  sourceFilename: "synthetic.csv",
  sourceInstrument: "csv",
  points: Array.from({ length: 41 }, (_, i) => {
    const e = -0.55 + i * 0.0125;
    const eta = e + 0.3;
    const cd = Math.max(1e-3, Math.abs(2 * (10 ** (eta / 0.08) - 10 ** (-eta / 0.12))));
    return {
      index: i,
      potential: e,
      currentRaw: cd,
      currentUnit: "uA" as const,
      currentDensity_uA_cm2: cd,
      logCurrentDensity: Math.log10(cd),
      signedCurrentDensity_uA_cm2: eta >= 0 ? cd : -cd,
    };
  }),
  metadata: {
    electrodeAreaCm2: 1,
    referenceElectrode: "SCE" as any,
    refOffsetVsSHE: 0.241,
    alloyName: "",
    density_g_cm3: 0,
    equivalentWeight: 0,
    electrolyte: "test",
    temperatureC: 25,
  },
};

test("executePythonTafelFit propagates a 422 instead of the local autoFit", { todo: tafelTodo }, async () => {
  stubFetch(422, TAFEL_ENVELOPE);
  await assert.rejects(executePythonTafelFit(DATASET, { alloyId: "duplex2205" }), (err: unknown) => {
    assert.ok(isPythonValidationError(err));
    assert.match((err as Error).message, /^Tafel fit: Unknown alloy/);
    return true;
  });
});

test("executePythonTafelFit still falls back to the local fit for 5xx and network errors", { todo: tafelTodo }, async () => {
  stubFetch(500, { error: "boom" });
  let res = await executePythonTafelFit(DATASET, { alloyId: "steel-316l" });
  assert.equal(res.isPythonEngine, false);
  assert.equal(res.pythonVersion, "Client Engine (Fallback)");
  stubNetworkError();
  res = await executePythonTafelFit(DATASET, { alloyId: "steel-316l" });
  assert.equal(res.isPythonEngine, false);
});
