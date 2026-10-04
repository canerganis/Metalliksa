import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";
import { DISPLAY_LOCALE, formatDisplayNumber, formatExactNumber } from "../src/utils/numberFormat";
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

test("only the presentation changes: the previous rounding, written out by hand", () => {
  // Expected strings are literal (not recomputed with toLocaleString): previous output in an en-US browser.
  const cases: [number, number, string][] = [
    [1200, 1, "1,200"], [31.25, 2, "31.25"], [26.041666, 2, "26.04"], [0.05, 1, "0.1"], [1e6 / 3, 1, "333,333.3"],
    [3055.149, 1, "3,055.1"], [80, 1, "80"], [74.4680851, 2, "74.47"], [58.333333, 2, "58.33"], [200, 1, "200"], [9.96, 1, "10"],
  ];
  for (const [value, digits, expected] of cases) assert.equal(formatDisplayNumber(value, digits), expected, `${value}`);
});

test("formatExactNumber groups thousands without rounding or changing any digit", () => {
  const cases: [number, string][] = [
    [1200, "1,200"], [940, "940"], [280, "280"], [0.0005, "0.0005"], [1200.25, "1,200.25"], [12345.678901, "12,345.678901"],
    [-1500.5, "-1,500.5"], [0, "0"], [1e-7, "1e-7"], [1e21, "1e+21"], [Number.NaN, "NaN"], [0.1 + 0.2, "0.30000000000000004"],
    [-0.0000030576843023300163, "-0.0000030576843023300163"], // 22 fraction digits: returned as String() shows it
  ];
  for (const [value, expected] of cases) assert.equal(formatExactNumber(value), expected, `${value}`);
  // Property check: the digits are exactly String(value) for many doubles.
  let seed = 42;
  const next = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
  for (let i = 0; i < 2000; i += 1) {
    const value = (next() - 0.3) * 10 ** Math.floor(next() * 12 - 4);
    if (/e/i.test(String(value))) continue;
    assert.equal(formatExactNumber(value).replace(/,/g, ""), String(value), `${value}`);
  }
});

test("process-vector summaries use the exact formatter (same digits, en-US grouping)", () => {
  const read = (rel: string) => readFileSync(resolve(process.cwd(), rel), "utf8");
  assert.match(read("src/App.tsx"), /\{formatExactNumber\(specimen\.lpbf\.laserPower_W\)\} W \/ \{formatExactNumber\(specimen\.lpbf\.scanSpeed_mms\)\} mm\/s/);
  assert.match(read("src/components/3d-distortion-lab/LpbfEngineeringSimulation.tsx"), /Shared vector · \{formatExactNumber\(input\.power_W\)\} W \/ \{formatExactNumber\(input\.speed_mm_s\)\} mm\/s/);
  assert.match(read("src/components/LpbfEngineeringWorkspace.tsx"), /\{formatExactNumber\(specimen\.lpbf\.laserPower_W\)\} W \/ \{formatExactNumber\(specimen\.lpbf\.scanSpeed_mms\)\} mm\/s \/ h/);
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

test("shell and thermal-stage sources do not format numbers with the browser locale", () => {
  for (const rel of ["src/App.tsx", "src/utils/scientificContext.ts", "src/components/LpbfEngineeringWorkspace.tsx", "src/components/3d-distortion-lab/LpbfEngineeringSimulation.tsx", "src/components/3d-distortion-lab/LpbfResultPresentation.tsx", "src/components/3d-distortion-lab/LpbfPhysicsDiagnostics.tsx", "src/components/3d-distortion-lab/ResolvedThermalViewer.tsx"]) {
    const text = readFileSync(resolve(process.cwd(), rel), "utf8");
    assert.doesNotMatch(text, /toLocaleString\(\s*(undefined|\))/, `${rel} uses the browser locale`);
    assert.doesNotMatch(text, /Intl\.NumberFormat\(\s*(undefined|\))/, `${rel} uses the browser locale`);
  }
});
