import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { keyholeMeshForBeam, missedPowerWarning } from "../src/components/KeyholeRaytracingLab";
import { DISTORTION_HEURISTIC_CONSTANTS, DISTORTION_HEURISTIC_NOTE } from "../src/utils/distortionHeuristic";

const read = (path: string) => readFileSync(resolve(import.meta.dirname, "..", path), "utf8");

test("solidification status dot pulses only while loading", () => {
  const src = read("src/components/SolidificationMicrostructureLab.tsx");
  assert.match(src, /\$\{isLoading \? 'animate-pulse' : ''\}/);
  assert.doesNotMatch(src, /isLoading \? '' : 'animate-pulse'/);
});

test("distortion heuristic and keyhole missed power are labelled", () => {
  assert.equal(DISTORTION_HEURISTIC_CONSTANTS.stressKnockdown, 0.72);
  assert.match(DISTORTION_HEURISTIC_NOTE, /not a stress or distortion solve/);
  assert.match(DISTORTION_HEURISTIC_NOTE, /uncited constants/);
  assert.match(DISTORTION_HEURISTIC_NOTE, /ΔT = max\(10 K, T_solidus − T_preheat\)/);
  assert.match(DISTORTION_HEURISTIC_NOTE, /max\(0\.01, 1 − ν\)/);
  assert.equal(DISTORTION_HEURISTIC_CONSTANTS.deltaTFloor_K, 10);
  // Pin the constants to the frozen solver source so the label cannot drift from it.
  const solver = read("python/lpbf_thermal_solver.py");
  assert.match(solver, /delta_t_stress = max\(10\.0, T_sol - T_preheat\)/);
  assert.match(solver, /max\(0\.01, 1\.0 - nu\)/);
  assert.match(solver, /elastic_stress_max_mpa \* 0\.72/);
  assert.match(read("src/components/3d-distortion-lab/MeltPool3DCrossSectionLab.tsx"), /DISTORTION_HEURISTIC_NOTE/);
  const keyhole = read("src/components/KeyholeRaytracingLab.tsx");
  assert.match(keyhole, /Missed power \(outside mesh\)/);
  assert.match(keyhole, /total_missed_W/);
});

test("keyhole: mesh aperture spans at least 3x the beam radius across the UI range", () => {
  for (let diameter = 40; diameter <= 300; diameter += 2) {
    const r = diameter / 2;
    const mesh = keyholeMeshForBeam(r);
    const halfExtent_um = ((mesh.nx - 1) * mesh.dx) / 2 * 1e6;
    assert.ok(halfExtent_um >= 3 * r - 1e-9, `d=${diameter}: ±${halfExtent_um} um`);
    assert.equal(mesh.dx, mesh.dy);
    assert.ok(mesh.dx >= 2e-6 && mesh.dx <= 1e-3, "within solver bounds");
    assert.ok(mesh.nx >= 2 && mesh.nx <= 256);
  }
  assert.equal(missedPowerWarning(0), null);
  assert.equal(missedPowerWarning(0.005), null);
  assert.match(missedPowerWarning(0.64) ?? "", /64\.0% of the input power falls outside the mesh/);
  const src = read("src/components/KeyholeRaytracingLab.tsx");
  assert.match(src, /Absorption \(of total input\)/);
  assert.match(src, /Absorption \(of intercepted power\)/);
  assert.match(src, /\.\.\.keyholeMeshForBeam\(beamRadius_um\)/);
  assert.doesNotMatch(read("python/lpbf_keyhole_raytracing.py"), /enlarge the mesh/);
});
