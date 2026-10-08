import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const src = (rel: string) => readFileSync(resolve(process.cwd(), rel), "utf8").replace(/\r/g, "");

test("optimizer result header uses a neutral icon, not a trophy", () => {
  assert.doesNotMatch(src("src/components/LpbfBayesianOptimizerLab.tsx"), /Trophy/);
});

