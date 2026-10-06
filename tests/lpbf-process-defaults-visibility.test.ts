import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { LPBF_PROCESS_FALLBACKS, migrateMaterialSpecimenStoreState, useMaterialSpecimenStore, withLpbfProcessDefaults } from "../src/store/useMaterialSpecimenStore";
import { LpbfDefaultsNote } from "../src/components/LpbfDefaultsNote";

const base = { recommendedLaserPower_W: 200, recommendedScanSpeed_mms: 900, recommendedHatch_um: 100, recommendedLayer_um: 40, recommendedPreheatTemp_C: 80 };

test("every filled default is listed in defaultsApplied and numeric values are unchanged", () => {
  const v = withLpbfProcessDefaults(base);
  assert.equal(v.thermalConductivity_k_WmK, 11.5);
  assert.equal(v.density_rho_kgm3, 8200);
  assert.equal(v.specificHeat_Cp_JkgK, 435);
  assert.equal(v.laserAbsorptivity, 0.58);
  assert.equal(v.thermalExpansion_CTE_10e6, 13);
  assert.equal(v.criticalGradient_G_Km, 1.5e7);
  assert.equal(v.beamDiameter_um, 80);
  assert.deepEqual([...v.defaultsApplied!].sort(), Object.keys(LPBF_PROCESS_FALLBACKS).sort());
});

test("explicit values are not flagged", () => {
  const v = withLpbfProcessDefaults({ ...base, thermalConductivity_k_WmK: 6.7, beamDiameter_um: 100 });
  assert.equal(v.thermalConductivity_k_WmK, 6.7);
  assert.ok(!v.defaultsApplied!.includes("thermalConductivity_k_WmK"));
  assert.ok(!v.defaultsApplied!.includes("beamDiameter_um"));
  assert.ok(v.defaultsApplied!.includes("density_rho_kgm3"));
});

test("a flag survives unrelated patches and is cleared only by an explicit edit of that field", () => {
  const store = useMaterialSpecimenStore.getState();
  store.loadPreset("inconel-718");
  assert.ok(useMaterialSpecimenStore.getState().activeSpecimen.lpbf.defaultsApplied!.includes("beamDiameter_um"));
  useMaterialSpecimenStore.getState().updateLpbfProcess({ laserPower_W: 250 });
  assert.ok(useMaterialSpecimenStore.getState().activeSpecimen.lpbf.defaultsApplied!.includes("beamDiameter_um"));
  useMaterialSpecimenStore.getState().updateLpbfProcess({ beamDiameter_um: 90 });
  const l = useMaterialSpecimenStore.getState().activeSpecimen.lpbf;
  assert.equal(l.beamDiameter_um, 90);
  assert.ok(!l.defaultsApplied!.includes("beamDiameter_um"));
  // the user value is carried across a composition change and stays unflagged
  const spec = useMaterialSpecimenStore.getState().activeSpecimen;
  useMaterialSpecimenStore.getState().updateComposition(spec.composition, spec.name, spec.baseMetal);
  const after = useMaterialSpecimenStore.getState().activeSpecimen.lpbf;
  assert.equal(after.beamDiameter_um, 90);
  assert.ok(!after.defaultsApplied!.includes("beamDiameter_um"));
});

test("derived class heuristics are flagged on the normal preset path, values unchanged", () => {
  useMaterialSpecimenStore.getState().loadPreset("inconel-718");
  const l = useMaterialSpecimenStore.getState().activeSpecimen.lpbf;
  for (const key of ["criticalGradient_G_Km", "laserAbsorptivity", "thermalExpansion_CTE_10e6", "thermalConductivity_k_WmK", "specificHeat_Cp_JkgK"] as const) assert.ok(l.defaultsApplied!.includes(key), key);
  assert.equal(l.criticalGradient_G_Km, 1.5e7);
  assert.equal(l.laserAbsorptivity, 0.58);
  useMaterialSpecimenStore.getState().loadPreset("ti-6al-4v");
  const ti = useMaterialSpecimenStore.getState().activeSpecimen.lpbf;
  assert.equal(ti.laserAbsorptivity, 0.68);
  assert.ok(ti.defaultsApplied!.includes("laserAbsorptivity"));
});

test("legacy persisted record without defaultsApplied is flagged as unknown provenance, user edits are not", () => {
  const legacy = {
    version: 3,
    state: { activeSpecimen: { name: "Legacy IN718", baseMetal: "Ni", composition: { Ni: 52.5, Cr: 19, Fe: 18.5, Nb: 5.15, Mo: 3.05, Ti: 0.95, Al: 0.55, C: 0.04, Co: 0.35 },
      lpbf: { ...withLpbfProcessDefaults(base), defaultsApplied: undefined, beamDiameter_um: 70, thermalConductivity_k_WmK: 11.5, laserAbsorptivity: 0.9 } } },
  };
  const migrated = migrateMaterialSpecimenStoreState(legacy.state, 3) as { activeSpecimen: { lpbf: { defaultsApplied?: string[]; beamDiameter_um: number } } };
  const flags = migrated.activeSpecimen.lpbf.defaultsApplied!;
  assert.ok(flags.includes("thermalConductivity_k_WmK"), "fallback-equal value flagged");
  assert.ok(flags.includes("criticalGradient_G_Km"));
  assert.ok(flags.includes("density_rho_kgm3"));
  assert.ok(!flags.includes("beamDiameter_um"), "an edited value is not flagged");
  assert.ok(!flags.includes("laserAbsorptivity"), "an edited value is not flagged");
  assert.equal(migrated.activeSpecimen.lpbf.beamDiameter_um, 70);
  // already versioned records are untouched
  assert.equal(migrateMaterialSpecimenStoreState(legacy.state, 4), legacy.state);
});

test("the disclosure renders human labels with the substituted value and unit", () => {
  const lpbf = withLpbfProcessDefaults(base);
  const html = renderToStaticMarkup(React.createElement(LpbfDefaultsNote, { lpbf }));
  assert.match(html, /lpbf-defaults-applied/);
  assert.match(html, /Beam diameter 80 µm/);
  assert.match(html, /Thermal conductivity 11\.5 W\/m·K/);
  assert.match(html, /Critical gradient G 15000000 K\/m/);
  assert.doesNotMatch(html, /thermalConductivity_k_WmK/);
  assert.equal(renderToStaticMarkup(React.createElement(LpbfDefaultsNote, { lpbf: { ...lpbf, defaultsApplied: [] } })), "");
});

test("the workspace context bar and the App trust panel both disclose defaults", () => {
  const ws = readFileSync(resolve(process.cwd(), "src/components/LpbfEngineeringWorkspace.tsx"), "utf8");
  assert.match(ws, /<LpbfDefaultsNote lpbf=\{specimen\.lpbf\}/);
  const app = readFileSync(resolve(process.cwd(), "src/App.tsx"), "utf8");
  assert.match(app, /<LpbfDefaultsNote/);
  assert.match(app, /unsourced default/);
});
