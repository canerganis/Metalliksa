import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { requestPythonAnalysis } from "../src/services/pythonAnalysis";
import { pythonComputationService } from "../src/services/pythonComputationService";
import { pythonDispatchStatus } from "../server/pythonDispatchStatus.ts";

// The EIS solver now answers error returns (unknown action, too few points, ...) with
// {"error": "...", "success": false} and HTTP 200. Callers formerly received success:true + error.
const BODY = { error: "At least 4 frequency points are required for EIS analysis.", success: false, pythonDurationMs: 0.1 };

const stubFetch = (body: unknown) => (async () => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch;

test("a success:false error body keeps HTTP 200 and is rejected by the shared analysis client", async () => {
  assert.equal(pythonDispatchStatus(BODY), 200);
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = stubFetch(BODY);
    await assert.rejects(requestPythonAnalysis("/api/python/battery-corrosion-eis", "{}", new AbortController().signal), /At least 4 frequency points are required for EIS analysis\./);
    globalThis.fetch = stubFetch({ success: false });
    await assert.rejects(requestPythonAnalysis("/api/python/battery-corrosion-eis", "{}", new AbortController().signal), /Python analysis failed/);
  } finally { globalThis.fetch = previous; }
});

// /api/python/bisquert-tlm-identify is served by the same solver. Intended behaviour: a success:false body is NOT a
// Python result (it used to arrive as success:true + error and was returned as an "isPythonEngine" result carrying an
// error key). identifyBisquertTLMCircuit falls back to the client engine, which either computes a real client-side result
// (isPythonEngine false) or, for too few points, throws its own explicit error.
test("bisquert-tlm-identify: a Python error body falls back to the client engine instead of becoming a result", async () => {
  const previousFetch = globalThis.fetch;
  const previousWarn = console.warn;
  console.warn = () => {};
  const frequencies = [1e5, 3e4, 1e4, 3e3, 1e3, 3e2, 1e2, 3e1, 1e1, 3, 1];
  const zReal = frequencies.map(f => 1 + 4 / (1 + (f / 500) ** 2));
  const zImag = frequencies.map(f => -4 * (f / 500) / (1 + (f / 500) ** 2));
  try {
    const requests: string[] = [];
    globalThis.fetch = (async (url: string) => { requests.push(url); return new Response(JSON.stringify({ error: "Insufficient points", success: false }), { status: 200 }); }) as typeof fetch;
    const result = await pythonComputationService.identifyBisquertTLMCircuit({ frequencies, zReal, zImag });
    assert.deepEqual(requests, ["/api/python/bisquert-tlm-identify"]);
    assert.equal(result.isPythonEngine, false, "client engine result, not the Python error body");
    assert.equal("error" in result, false);
    assert.equal(result.success, true);
    // Too few points: Python's error is not masked as a result; the client engine reports it explicitly.
    await assert.rejects(pythonComputationService.identifyBisquertTLMCircuit({ frequencies: frequencies.slice(0, 3), zReal: zReal.slice(0, 3), zImag: zImag.slice(0, 3) }),
      /At least 4 frequency points are required for Bisquert TLM analysis\./);
    // A genuine Python success is still used as is.
    globalThis.fetch = stubFetch({ success: true, circuitModel: "Bisquert fixture", engine: "fixture" });
    const python = await pythonComputationService.identifyBisquertTLMCircuit({ frequencies, zReal, zImag });
    assert.equal(python.isPythonEngine, true);
    assert.equal((python as { circuitModel?: string }).circuitModel, "Bisquert fixture");
  } finally { globalThis.fetch = previousFetch; console.warn = previousWarn; }
});

// Each live consumer of the endpoint must surface a failure (throw / reject) or refuse to store the body as a result.
const CONSUMER_GUARDS: Record<string, { pattern: RegExp; minMatches: number; why: string }> = {
  "BatteryEISDegradationStudio.tsx": { pattern: /if \(data\.error\) \{\s*throw new Error\(data\.error\);\s*\}\s*setSimResult\(data\);/g, minMatches: 1, why: "throws data.error before storing the body" },
  "CorrosionEISKineticsStudio.tsx": { pattern: /if \(data\.error\) \{\s*throw new Error\(data\.error\);\s*\}[^]*?setSimResult\(data\);/g, minMatches: 1, why: "throws data.error before storing the body" },
  "AdvancedBatteryPhysicsStudio.tsx": { pattern: /if \(data\.success\) \{\s*set(?:P2dData|LliLamData|ThermalData)\(data\);/g, minMatches: 3, why: "stores the body only when success is true (3 actions)" },
  "TransportKineticsLab.tsx": { pattern: /if \(resData\.success\) \{\s*setData\(resData\);/g, minMatches: 1, why: "stores the body only when success is true" },
  "CNLSFittingStudio.tsx": { pattern: /await requestPythonAnalysis\("\/api\/python\/battery-corrosion-eis"/g, minMatches: 1, why: "requestPythonAnalysis rejects on error/success:false" },
  "EquivalentCircuitBuilder.tsx": { pattern: /await requestPythonAnalysis\("\/api\/python\/battery-corrosion-eis"/g, minMatches: 1, why: "requestPythonAnalysis rejects on error/success:false" },
  "EISUploadInsightsStudio.tsx": { pattern: /usePythonAnalysis\("\/api\/python\/battery-corrosion-eis"/g, minMatches: 1, why: "usePythonAnalysis goes through requestPythonAnalysis" },
};

test("every live consumer of the battery/corrosion EIS endpoint surfaces or refuses a success:false/error body", () => {
  const dir = new URL("../src/components/", import.meta.url);
  const consumers = readdirSync(dir).filter(name => /\.tsx$/.test(name) && readFileSync(new URL(name, dir), "utf8").includes("/api/python/battery-corrosion-eis"));
  assert.deepEqual(consumers.sort(), Object.keys(CONSUMER_GUARDS).sort(), "a new or removed consumer must get (or lose) an explicit guard entry here");
  for (const name of consumers) {
    const { pattern, minMatches, why } = CONSUMER_GUARDS[name];
    const matches = readFileSync(new URL(name, dir), "utf8").match(pattern) ?? [];
    assert.ok(matches.length >= minMatches, `${name} must ${why} (found ${matches.length}, need ${minMatches})`);
  }
  // The shared client really rejects on every failure shape it is trusted for.
  const client = readFileSync(new URL("../src/services/pythonAnalysis.ts", import.meta.url), "utf8");
  assert.match(client, /!response\.ok \|\| data\?\.error \|\| data\?\.success === false\) \{\s*throw new Error/);
  const hook = readFileSync(new URL("../src/hooks/usePythonAnalysis.ts", import.meta.url), "utf8");
  assert.match(hook, /requestPythonAnalysis\(url, body, controller\.signal\)/);
});
