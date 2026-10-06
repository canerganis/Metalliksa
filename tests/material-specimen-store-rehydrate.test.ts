import assert from "node:assert/strict";
import test from "node:test";

// Real zustand rehydration of the shared specimen store from a version-2 blob (heuristic properties persisted).
// The store module is imported after localStorage is seeded so its first hydration reads the blob.
const STORAGE_KEY = "metallix_active_material_specimen_v2";
const mem = new Map<string, string>();
const storage = {
  getItem: (k: string) => mem.get(k) ?? null,
  setItem: (k: string, v: string) => void mem.set(k, String(v)),
  removeItem: (k: string) => void mem.delete(k),
};
const fakeWindow = Object.assign(new EventTarget(), { localStorage: storage });
Object.defineProperty(globalThis, "window", { value: fakeWindow, configurable: true });
Object.defineProperty(globalThis, "localStorage", { value: storage, configurable: true });

const lpbf = {
  recommendedLaserPower_W: 280, recommendedScanSpeed_mms: 940, recommendedHatch_um: 100, recommendedLayer_um: 40,
  recommendedPreheatTemp_C: 200, thermalConductivity_k_WmK: 11, density_rho_kgm3: 8167, specificHeat_Cp_JkgK: 435,
  laserAbsorptivity: 0.58, thermalExpansion_CTE_10e6: 13, criticalGradient_G_Km: 1.5e7, hotTearingSusceptibility: "High",
  crackingMechanism: "", mitigationRecommendation: "",
  laserPower_W: 311, scanSpeed_mms: 777, hatch_um: 90, layer_um: 30, beamDiameter_um: 70, preheatTemp_C: 120,
  scanStrategy: "island", beamProfile: "gaussian", cadAssetName: "part.stl", specimenDoi: "", processSeed: 5,
  inclineAngle_deg: 0, downskinOverhang_deg: 0,
};
mem.set(STORAGE_KEY, JSON.stringify({
  version: 2,
  state: {
    activeSpecimen: {
      id: "persisted-in718", name: "Persisted IN718", chemicalFormula: "Ni-19Cr", category: "Nickel Superalloy", baseMetal: "Ni",
      composition: { Ni: 52.5, Cr: 19, Fe: 18.5, Nb: 5.15, Mo: 3.05, Ti: 0.95, Al: 0.55, C: 0.04, Co: 0.35 }, unit: "wt_pct",
      liquidus_C: 1336, solidus_C: 1250, freezingRange_C: 86, solvus_C: 1100, stablePhases: ["austenite-fcc"],
      yieldStrength_25C_MPa: 1050, uts_25C_MPa: 1466, density_gcm3: 8.167, youngsModulus_GPa: 216, elongation_pct: 18,
      lpbf, xrd: { crystalSystem: "FCC", spaceGroup: "Fm-3m (225)", latticeA_A: 3.6, targetPhases: [], microstrain_pct: 0.22, crystalliteSize_nm: 32 },
      sourceTab: "t", lastModified: 1, isCustomModified: true,
    },
  },
}));

test("version-2 specimen blob hydrates as version 3: heuristic properties null, live LPBF vector intact", async () => {
  const { useMaterialSpecimenStore } = await import("../src/store/useMaterialSpecimenStore");
  assert.equal(useMaterialSpecimenStore.persist.hasHydrated(), true);
  const s = useMaterialSpecimenStore.getState().activeSpecimen;
  assert.equal(s.name, "Persisted IN718");
  for (const field of ["liquidus_C", "solidus_C", "freezingRange_C", "solvus_C", "yieldStrength_25C_MPa", "uts_25C_MPa", "youngsModulus_GPa", "elongation_pct"] as const) {
    assert.equal(s[field], null, field);
  }
  assert.deepEqual(s.lpbf, lpbf);
  useMaterialSpecimenStore.getState().updateLpbfProcess({ laserPower_W: 312 });
  const blob = JSON.parse(mem.get(STORAGE_KEY)!);
  assert.equal(blob.version, 3);
  assert.equal(blob.state.activeSpecimen.yieldStrength_25C_MPa, null);
  assert.equal(blob.state.activeSpecimen.lpbf.laserPower_W, 312);
});
