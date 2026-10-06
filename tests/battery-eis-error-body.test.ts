import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { pythonDispatchStatus } from "../server/pythonDispatchStatus.ts";

// The EIS solver now answers error returns (unknown action, too few points, ...) with
// {"error": "...", "success": false} and HTTP 200. Callers formerly received success:true + error.
const BODY = { error: "At least 4 frequency points are required for EIS analysis.", success: false, pythonDurationMs: 0.1 };

test("a success:false error body keeps HTTP 200 at the dispatch layer", () => {
  assert.equal(pythonDispatchStatus(BODY), 200);
});

// Each live consumer of the endpoint must surface a failure (throw / reject) or refuse to store the body as a result.
const CONSUMER_GUARDS: Record<string, { pattern: RegExp; minMatches: number; why: string }> = {
  "CorrosionEISKineticsStudio.tsx": { pattern: /if \(data\.error\) \{\s*throw new Error\(data\.error\);\s*\}[^]*?setSimResult\(data\);/g, minMatches: 1, why: "throws data.error before storing the body" },
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
});
