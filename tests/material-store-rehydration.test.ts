import assert from "node:assert/strict";
import test from "node:test";

const STORAGE_KEY = "metallix-material-specimen-store";
const mem = new Map<string, string>();
const storage = {
  getItem: (key: string) => mem.get(key) ?? null,
  setItem: (key: string, value: string) => void mem.set(key, String(value)),
  removeItem: (key: string) => void mem.delete(key),
};
const fakeWindow = Object.assign(new EventTarget(), {localStorage: storage});
Object.defineProperty(globalThis, "window", {value: fakeWindow, configurable: true});
Object.defineProperty(globalThis, "localStorage", {value: storage, configurable: true});

const specimen = (composition: Record<string, number>, name: string) => ({
  id: `saved-${name}`,
  name,
  chemicalFormula: name,
  composition,
  unit: "wt_pct",
  metadata: {id: name, baseMetal: "Ni", category: "test", name},
  sourceTab: "persisted test",
  lastModified: 42,
  isCustomModified: true,
  liquidus_C: 1234,
});

test("rehydration drops malformed legacy active material and retains valid saved specimen", async () => {
  const malformed = specimen({Ni: 101}, "invalid legacy alloy");
  const validSaved = specimen({Ni: 70, Cr: 60}, "valid saved alloy");
  mem.set(STORAGE_KEY, JSON.stringify({state: {
    activeMaterialSpecimen: malformed,
    activeSpecimen: malformed,
    savedSpecimens: [validSaved, {composition: [101]}, null],
  }, version: 0}));

  const {useMaterialStore} = await import("../src/store/useMaterialStore");
  const active = useMaterialStore.getState().activeMaterialSpecimen;
  assert.notEqual(active.name, malformed.name);
  assert.equal(Object.values(active.composition).some((value) => value > 100), false);
  assert.notEqual(active.liquidus_C, malformed.liquidus_C);
  assert.deepEqual(useMaterialStore.getState().savedSpecimens.map((item) => item.name), ["valid saved alloy"]);
  assert.deepEqual(useMaterialStore.getState().savedSpecimens[0].composition, {Ni: 70, Cr: 60});
  assert.deepEqual(useMaterialStore.getState().savedSpecimens[0], validSaved);
  assert.strictEqual(useMaterialStore.getState().activeSpecimen, active);
});
