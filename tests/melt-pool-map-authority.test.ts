import assert from "node:assert/strict";
import test from "node:test";
import { authorityThermal } from "../src/data/lpbfMaterialAuthority";
import { mapPhaseTemperaturesC } from "../src/utils/meltPoolMapAuthority";

test("map liquidus/solidus come from the material authority for the solver material names", () => {
  for (const [name, id] of [["Inconel 718", "in718"], ["Ti-6Al-4V", "ti6al4v"], ["316L Stainless Steel", "ss316l"], ["AlSi10Mg", "alsi10mg"], ["Inconel 625", "in625"]] as const) {
    const t = mapPhaseTemperaturesC(name);
    assert.ok(t, name);
    assert.equal(t.alloyId, id);
    assert.equal(t.liquidus_C, authorityThermal(id).liquidus_C);
    assert.equal(t.solidus_C, authorityThermal(id).solidus_C);
  }
});

test("liquidus and solidus differ per alloy and from the former fixed 1350/1260 values", () => {
  const al = mapPhaseTemperaturesC("AlSi10Mg");
  assert.ok(al);
  assert.notEqual(al.liquidus_C, 1350);
  assert.notEqual(al.solidus_C, 1260);
});

test("alloys absent from the authority return null (no surrogate, no fixed fallback)", () => {
  for (const name of ["CoCrMo", "Scalmalloy (Al-Mg-Sc-Zr)", "Hastelloy X", "Pure Copper (Cu-OF)", ""]) {
    assert.equal(mapPhaseTemperaturesC(name), null, name);
  }
});
