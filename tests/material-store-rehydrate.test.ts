import assert from "node:assert/strict";
import test from "node:test";

// A real zustand rehydration of the Alloy Builder store from a version-0 localStorage blob. The store module is
// imported only after the in-memory localStorage is seeded, so the initial hydration on module load reads the blob.
// Before the fix, hydration threw on the `get activeSpecimen()` getter: saved specimens were discarded on every load
// and the version 0 -> 1 hardness migration never ran.

const STORAGE_KEY = "metallix-material-specimen-store";
const mem = new Map<string, string>();
const storage = {
  getItem: (k: string) => mem.get(k) ?? null,
  setItem: (k: string, v: string) => void mem.set(k, String(v)),
  removeItem: (k: string) => void mem.delete(k),
  clear: () => mem.clear(),
  key: (i: number) => [...mem.keys()][i] ?? null,
  get length() {
    return mem.size;
  },
};
// zustand's default persist storage is window.localStorage; the window is an EventTarget for pipeline events.
const fakeWindow = Object.assign(new EventTarget(), { localStorage: storage });
Object.defineProperty(globalThis, "window", { value: fakeWindow, configurable: true });
Object.defineProperty(globalThis, "localStorage", { value: storage, configurable: true });

// Version-0 records shaped like the 6dd5b73 store wrote them (hardness_HV from the removed rules: 210 for an FCC Fe
// specimen, YS/3.1 for BCC Fe = 307 for Maraging 300, YS/3.05 for Ni = 406 for IN718); no hardnessHVStatus/Note.
const v0Specimen = (name: string, baseMetal: string, crystalSystem: string, composition: Record<string, number>, ys: number, hv: number) => ({
  id: `snapshot-${name}`,
  name,
  chemicalFormula: name,
  composition,
  unit: "wt_pct",
  metadata: { id: name, baseMetal, category: "x", name },
  yieldStrength_25C_MPa: ys,
  uts_25C_MPa: Math.round(ys * 1.3),
  youngsModulus_GPa: 200,
  elongation_pct: 10,
  hardness_HV: hv,
  xrd: { crystalSystem },
  sourceTab: "Alloy Formulator (Tab 1)",
  lastModified: 0,
  isCustomModified: true,
});
const ss316l = v0Specimen("AISI 316L", "Fe", "FCC", { Fe: 65.5, Cr: 17.5, Ni: 12, Mo: 2.4, Mn: 1.8, Si: 0.6, C: 0.02 }, 513, 210);
const maraging = v0Specimen("Maraging 300", "Fe", "BCC", { Fe: 67.5, Ni: 18.5, Co: 9, Mo: 4.8, Ti: 0.6, Al: 0.1, C: 0.01 }, 951, 307);
const in718 = v0Specimen("Inconel 718", "Ni", "FCC", { Ni: 53, Fe: 18.5, Cr: 19, Nb: 5.1, Mo: 3.05, C: 0.04 }, 1238, 406);
const lowAlloy = v0Specimen("4140-type", "Fe", "BCC", { Fe: 97.4, C: 0.4, Mn: 0.9, Cr: 1.0, Mo: 0.2, Si: 0.1 }, 1000, 323);
mem.set(
  STORAGE_KEY,
  JSON.stringify({ state: { activeMaterialSpecimen: ss316l, activeSpecimen: ss316l, savedSpecimens: [maraging, in718, lowAlloy, null] }, version: 0 })
);

test("version-0 blob rehydrates on store creation: saved specimens kept, HV recomputed, blob rewritten as version 1", async () => {
  const { useMaterialStore } = await import("../src/store/useMaterialStore");
  assert.equal(useMaterialStore.persist.hasHydrated(), true);
  const s = useMaterialStore.getState();
  assert.equal(s.activeMaterialSpecimen.name, "AISI 316L");
  assert.equal(s.activeSpecimen, s.activeMaterialSpecimen);
  assert.equal(s.activeMaterialSpecimen.hardness_HV, null); // was 210
  assert.match(s.activeMaterialSpecimen.hardnessHVNote ?? "", /Austenitic stainless steel/);
  assert.deepEqual(s.savedSpecimens.map((x) => x.name), ["Maraging 300", "Inconel 718", "4140-type"]); // null dropped
  assert.equal(s.savedSpecimens[0].hardness_HV, null); // was 307: Ni 18.5 / Co 9 outside the low-alloy data set
  assert.match(s.savedSpecimens[0].hardnessHVNote ?? "", /outside the regression's data set/);
  assert.equal(s.savedSpecimens[1].hardness_HV, null); // was 406
  assert.equal(s.savedSpecimens[2].hardness_HV, 379); // (1000 + 90.7) / 2.876; was 323
  assert.equal(typeof s.updateComposition, "function"); // actions come from the current store, not the blob
  // Any later write stores version 1 with JSON null hardness.
  s.updateName("AISI 316L renamed");
  const blob = JSON.parse(mem.get(STORAGE_KEY)!);
  assert.equal(blob.version, 1);
  assert.equal(blob.state.activeMaterialSpecimen.hardness_HV, null);
  assert.equal(blob.state.savedSpecimens.length, 3);
});
