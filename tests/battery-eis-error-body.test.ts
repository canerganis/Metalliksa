import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { requestPythonAnalysis } from "../src/services/pythonAnalysis";
import { pythonDispatchStatus } from "../server/pythonDispatchStatus.ts";

// The EIS solver now answers error returns (unknown action, too few points, ...) with
// {"error": "...", "success": false} and HTTP 200. Callers formerly received success:true + error.
const BODY = { error: "At least 4 frequency points are required for EIS analysis.", success: false, pythonDurationMs: 0.1 };

test("a success:false error body keeps HTTP 200 and is rejected by the shared analysis client", async () => {
  assert.equal(pythonDispatchStatus(BODY), 200);
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = (async () => new Response(JSON.stringify(BODY), { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch;
    await assert.rejects(requestPythonAnalysis("/api/python/battery-corrosion-eis", "{}", new AbortController().signal), /At least 4 frequency points are required for EIS analysis\./);
    globalThis.fetch = (async () => new Response(JSON.stringify({ success: false }), { status: 200 })) as typeof fetch;
    await assert.rejects(requestPythonAnalysis("/api/python/battery-corrosion-eis", "{}", new AbortController().signal), /Python analysis failed/);
  } finally { globalThis.fetch = previous; }
});

test("every live consumer of the battery/corrosion EIS endpoint rejects or ignores a success:false/error body", () => {
  const dir = new URL("../src/components/", import.meta.url);
  const consumers = readdirSync(dir).filter(name => /\.tsx$/.test(name) && readFileSync(new URL(name, dir), "utf8").includes("/api/python/battery-corrosion-eis"));
  assert.ok(consumers.length >= 1);
  for (const name of consumers) {
    const source = readFileSync(new URL(name, dir), "utf8");
    const guarded = /requestPythonAnalysis|usePythonAnalysis/.test(source) || /\b(data|resData)\.error\b/.test(source) || /\b(data|resData)\.success\b/.test(source);
    assert.ok(guarded, `${name} must not treat a success:false body as a result`);
  }
});
