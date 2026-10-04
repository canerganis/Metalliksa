import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";
import { DISPLAY_LOCALE, formatDisplayNumber } from "../src/utils/numberFormat";
import { buildScientificContext } from "../src/utils/scientificContext";
import type { ActiveSpecimenState } from "../src/store/useMaterialSpecimenStore";

// D3 (Phase 2 record): a Turkish browser showed "1.200 mm/s" and "31,25 J/mm³" next to English "1,201 steps".
test("one fixed display locale: comma groups thousands, point marks decimals", () => {
  assert.equal(DISPLAY_LOCALE, "en-US");
  assert.equal(formatDisplayNumber(1200), "1,200");
  assert.equal(formatDisplayNumber(31.25, 2), "31.25");
  assert.equal(formatDisplayNumber(0.5), "0.5");
  assert.equal(formatDisplayNumber(-1234567.891, 2), "-1,234,567.89");
  // The browser-locale formats it replaces would read differently; this output never does.
  assert.equal((1200).toLocaleString("tr-TR"), "1.200");
  assert.equal((31.25).toLocaleString("tr-TR"), "31,25");
});

test("only the presentation changes: same rounding (maximumFractionDigits) as before, same value", () => {
  for (const [value, digits] of [[1200, 1], [31.25, 2], [26.041666, 2], [0.05, 1], [1e6 / 3, 1], [3055.149, 1], [80, 1]] as const) {
    const shown = formatDisplayNumber(value, digits);
    const expected = Number(value.toLocaleString("en-US", { maximumFractionDigits: digits, useGrouping: false }));
    assert.equal(Number(shown.replace(/,/g, "")), expected, `${value} -> ${shown}`);
  }
});

test("thermal-stage scientific context shows en-US numbers for the D3 process vector", () => {
  const specimen = {
    name: "IN625 fixture", baseMetal: "Ni", stablePhases: ["gamma"],
    lpbf: { laserPower_W: 60, scanSpeed_mms: 1200, hatch_um: 80, layer_um: 20, preheatTemp_C: 200, thermalConductivity_k_WmK: 9 },
    xrd: { crystalSystem: "FCC" },
  } as unknown as ActiveSpecimenState;
  const context = buildScientificContext("3d-distortion-lab", specimen);
  assert.match(context.observation, /60 W, 1,200 mm\/s, 80 µm hatch, 20 µm layer\./);
  assert.ok(context.variables.includes("Computed VED: 31.25 J/mm³"), context.variables.join(" | "));
  assert.ok(context.variables.includes("Preheat: 200 °C"));
});

test("thermal-stage sources do not format numbers with the browser locale", () => {
  for (const rel of ["src/utils/scientificContext.ts", "src/components/3d-distortion-lab/LpbfEngineeringSimulation.tsx"]) {
    const text = readFileSync(resolve(process.cwd(), rel), "utf8");
    assert.doesNotMatch(text, /toLocaleString\(\s*(undefined|\))/, `${rel} uses the browser locale`);
    assert.doesNotMatch(text, /Intl\.NumberFormat\(\s*(undefined|\))/, `${rel} uses the browser locale`);
  }
});
