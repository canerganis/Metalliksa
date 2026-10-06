import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { LPBF_PROCESS_FALLBACKS, withLpbfProcessDefaults } from "../src/store/useMaterialSpecimenStore";

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

test("a default survives a later patch until the user sets a different value", () => {
  const first = withLpbfProcessDefaults(base);
  const patched = withLpbfProcessDefaults({ ...first, laserPower_W: 250 });
  assert.ok(patched.defaultsApplied!.includes("beamDiameter_um"));
  const edited = withLpbfProcessDefaults({ ...patched, beamDiameter_um: 90 });
  assert.ok(!edited.defaultsApplied!.includes("beamDiameter_um"));
});

test("the LPBF workspace context bar discloses defaults", () => {
  const ui = readFileSync(resolve(process.cwd(), "src/components/LpbfEngineeringWorkspace.tsx"), "utf8");
  assert.match(ui, /lpbf-defaults-applied/);
  assert.match(ui, /defaultsApplied/);
});
