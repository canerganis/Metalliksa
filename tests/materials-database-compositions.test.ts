import assert from "node:assert/strict";
import test from "node:test";
import { MATERIALS_DATABASE } from "../src/data/materialsDatabase";

// Physics audit MD-8. The reference database fed "Send to Module" with nominal compositions
// whose balance element was not computed by difference (6061-T6 summed to 100.93, 2024-T3 to
// 101.0, C17200 100.55, C93200 101.0, CMSX-4 100.8), listed WE43 with the pseudo-element "RE",
// and gave AISI 4140 its normalized tensile values (655 / 1020 MPa) under a Q&T 540 °C label.

const ELEMENT_SYMBOL = /^[A-Z][a-z]?$/;
const NOT_ELEMENTS = new Set(["RE", "Mm", "Ln"]); // rare-earth / mischmetal labels

function numericSum(composition: Record<string, unknown>): number {
  let sum = 0;
  for (const value of Object.values(composition)) {
    if (typeof value === "number") sum += value;
    else return Number.NaN; // ranged entries are not nominal point compositions
  }
  return sum;
}

test("every nominal point composition sums to 100 wt% (balance element by difference)", () => {
  let checked = 0;
  for (const spec of MATERIALS_DATABASE) {
    const sum = numericSum(spec.composition as Record<string, unknown>);
    if (Number.isNaN(sum)) continue;
    checked += 1;
    assert.ok(Math.abs(sum - 100) < 1e-6, `${spec.id} sums to ${sum.toFixed(4)} wt%`);
  }
  assert.ok(checked >= 30, `only ${checked} compositions checked`);
});

test("the five audited entries no longer overshoot 100 wt%", () => {
  const expectedBalance: Record<string, [string, number]> = {
    "al-6061-t6": ["Al", 96.97], // was 97.9 -> sum 100.93
    "al-2024-t3": ["Al", 92.5], // was 93.5 -> 101.0
    "cu-c17200": ["Cu", 97.55], // was 98.1 -> 100.55
    "cu-c93200": ["Cu", 82.0], // was 83.0 -> 101.0
    "cmsx-4": ["Ni", 61.7], // was 62.5 -> 100.8
  };
  for (const [id, [el, value]] of Object.entries(expectedBalance)) {
    const spec = MATERIALS_DATABASE.find((m) => m.id === id);
    assert.ok(spec, id);
    assert.equal((spec!.composition as Record<string, number>)[el], value, id);
  }
});

test("every composition key is a chemical element symbol (no 'RE' rare-earth label)", () => {
  for (const spec of MATERIALS_DATABASE) {
    for (const key of Object.keys(spec.composition)) {
      assert.match(key, ELEMENT_SYMBOL, `${spec.id}: ${key}`);
      assert.ok(!NOT_ELEMENTS.has(key), `${spec.id}: ${key} is not an element`);
    }
  }
  const we43 = MATERIALS_DATABASE.find((m) => m.id === "mg-we43")!;
  assert.deepEqual(we43.composition, { Mg: 93.3, Y: 4.0, Nd: 2.25, Zr: 0.45 });
});

test("AISI 4140 tensile values match its Q&T 540 °C label (ASM Vol. 1), not the normalized ones", () => {
  const s = MATERIALS_DATABASE.find((m) => m.id === "aisi-4140")!;
  assert.match(s.hardness, /Quenched & Tempered @ 540/);
  assert.equal(s.yieldStrength, 986); // was 655 (normalized)
  assert.equal(s.tensileStrength, 1075); // was 1020 (normalized)
  assert.equal(s.elongation, 15.5); // was 18
});
