import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const src = (rel: string) => readFileSync(resolve(process.cwd(), rel), "utf8").replace(/\r/g, "");

test("optimizer result header uses a neutral icon, not a trophy", () => {
  assert.doesNotMatch(src("src/components/LpbfBayesianOptimizerLab.tsx"), /Trophy/);
});

test("dual-unit reporting wording makes no certification claim", () => {
  const text = src("src/components/StandardInfoIcon.tsx");
  assert.doesNotMatch(text, /Dual certified reporting/);
  assert.match(text, /Dual-unit reporting \(EN 10204 certificate units\)/);
});

test("quick conversions grid does not claim live outputs", () => {
  const text = src("src/components/MetallurgicalQuickConversionsGrid.tsx");
  assert.doesNotMatch(text, /live outputs/);
  assert.match(text, /outputs that update as you type/);
});
