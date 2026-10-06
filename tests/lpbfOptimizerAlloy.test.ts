import test from "node:test";
import assert from "node:assert/strict";
import { resolveOptimizerAlloy } from "../src/utils/lpbfOptimizerAlloy";

test("optimizer alloy: supported specimen names map to solver keys", () => {
  assert.deepEqual(resolveOptimizerAlloy("Inconel 718 (AMS 5662 / UNS N07718)"), { ok: true, alloyKey: "in718", reason: null });
  assert.deepEqual(resolveOptimizerAlloy("Ti-6Al-4V Grade 23 ELI (ASTM F3001)"), { ok: true, alloyKey: "ti6al4v", reason: null });
  assert.deepEqual(resolveOptimizerAlloy("AISI 316L Stainless Steel (UNS S31603)"), { ok: true, alloyKey: "ss316l", reason: null });
  assert.deepEqual(resolveOptimizerAlloy("AlSi10Mg Additive Lightweight"), { ok: true, alloyKey: "alsi10mg", reason: null });
});

test("optimizer alloy: unmapped or unsupported alloys are refused, not guessed", () => {
  assert.equal(resolveOptimizerAlloy("AeroTurbine-850 (Ni-16Cr)").ok, false);
  assert.equal(resolveOptimizerAlloy("Inconel 625").ok, false);
  assert.equal(resolveOptimizerAlloy(null).ok, false);
});
