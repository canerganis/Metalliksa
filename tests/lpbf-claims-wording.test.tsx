import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { energyChangeLabel, rotationPreviewDeg, rotationPreviewText, toolpathDefaultsError, toolpathWarnings, zeroFlagCaveat } from "../src/components/LpbfToolpathStudioLab";
import { fatigueCriteriaDisagreement, parisLifeLabel, withRequestInputs } from "../src/components/MurakamiFatigueLab";
import {
  attachmentDownloadHref,
  createUnresolvedDigitalTwin,
  labelTwinEvidence,
  withEditedComposition,
} from "../src/utils/digitalTwinEvidence";
import { keyholeMeshForBeam, missedPowerWarning } from "../src/components/KeyholeRaytracingLab";
import { DISTORTION_HEURISTIC_CONSTANTS, DISTORTION_HEURISTIC_NOTE } from "../src/utils/distortionHeuristic";

const read = (path: string) => readFileSync(resolve(import.meta.dirname, "..", path), "utf8");

test("toolpath studio: zero-cruise skywriting is a warning, never 'sufficient'", () => {
  assert.deepEqual(toolpathWarnings(null), []);
  assert.deepEqual(toolpathWarnings({ warnings: [], laser_never_fires: false }), []);
  const engine = ["1 of 1 marking vectors ... the laser never fires on them (0 J deposited)."];
  assert.deepEqual(toolpathWarnings({ warnings: engine, laser_never_fires: true }), engine);
  // A result that only carries the flag still yields an explicit warning.
  assert.match(toolpathWarnings({ laser_never_fires: true }).join(" "), /never fires/);
  const src = read("src/components/LpbfToolpathStudioLab.tsx");
  assert.doesNotMatch(src, /Skywriting or vector length is sufficient/);
  assert.doesNotMatch(src, /triggering local keyhole porosity/);
  assert.doesNotMatch(src, /hotspots\) are mitigated/);
  // Recharts came back with the merged feed-forward tab: exactly one chart (its power bars), none in the kinematics tab.
  assert.equal((src.match(/<BarChart /g) ?? []).length, 1, "no unused chart imports; one chart, in the feed-forward panel");
  assert.ok(src.indexOf("<BarChart ") > src.indexOf("export const ToolpathFeedforwardPanel"), "the chart belongs to the feed-forward panel");
  assert.match(src, /aria-label="Default Laser Power"/);
  assert.match(src, /aria-label="Default Scan Speed"/);
  assert.doesNotMatch(src, /Overheating Hotspots/);
  assert.doesNotMatch(src, /Thermal Overheating/);
});

test("toolpath studio: skywriting no-energy caveat only when skywriting is on", () => {
  const skyOn = { hotspot_count: 0, skywriting_mitigation_active: true, no_cruise_segment_count: 3, laser_never_fires: true, warnings: ["w"] };
  assert.match(zeroFlagCaveat(skyOn) ?? "", /skywriting on/);
  const skyOff = { hotspot_count: 0, skywriting_mitigation_active: false, no_cruise_segment_count: 3, laser_never_fires: false, warnings: ["triangular velocity profile"] };
  const off = zeroFlagCaveat(skyOff) ?? "";
  assert.match(off, /never reach their commanded speed/);
  assert.doesNotMatch(off, /skywriting/i);
  assert.equal(zeroFlagCaveat({ hotspot_count: 0, warnings: [] }), null);
  assert.equal(zeroFlagCaveat({ hotspot_count: 2, warnings: ["x"] }), null);
});

test("toolpath studio: non-positive default power/speed is rejected before the engine", () => {
  assert.equal(toolpathDefaultsError(280, 1000), null);
  assert.match(toolpathDefaultsError(0, 1000) ?? "", /power/);
  assert.match(toolpathDefaultsError(280, 0) ?? "", /speed/);
  assert.match(toolpathDefaultsError(Number(""), 1000) ?? "", /power/);
  assert.match(toolpathDefaultsError(280, Number.NaN) ?? "", /speed/);
});

test("adaptive mitigation: open-loop wording, no machine-readiness or texture claims", () => {
  assert.equal(rotationPreviewDeg(true, 1), 67);
  assert.equal(rotationPreviewDeg(true, 2), 134);
  assert.equal(rotationPreviewDeg(false, 5), 0);
  assert.equal(rotationPreviewText(false, 5), "Rotation disabled (0°)");
  assert.equal(rotationPreviewText(true, 2), "Rotation applied = 67° × 2 = 134°");
  assert.equal(energyChangeLabel(0), "0 % (no vector scaled)");
  assert.equal(energyChangeLabel(12.5), "−12.5 %");
  assert.equal(energyChangeLabel(undefined), "unavailable");
  const src = read("src/components/LpbfToolpathStudioLab.tsx");
  assert.doesNotMatch(src, /Ready for Machine/);
  assert.doesNotMatch(src, /Suppresses grain texture/);
  assert.doesNotMatch(src, /Energy Peak Reduction/);
  assert.match(src, /Not machine-validated/);
  assert.match(src, /power is not ramped along the acceleration and deceleration phases/);
  assert.match(src, /aria-label="Layer Index"/);
  for (const stale of ["Unmitigated Power", "Adaptive Power", "Mitigation computation failed", "Overheating Test Pattern"]) {
    assert.ok(!src.includes(stale), stale);
  }
  const py = read("python/lpbf_adaptive_feedforward.py");
  assert.doesNotMatch(py, /Mitigated Toolpath/);
  assert.doesNotMatch(py, /End of layer mitigation/);
  assert.doesNotMatch(read("python/lpbf_adaptive_feedforward.py"), /Closed-Loop/);
  assert.doesNotMatch(read("src/services/pythonComputationService.ts"), /Closed-Loop Feed-Forward/);
});

test("murakami fatigue: no safety verdict, R handling stated, criteria disagreement flagged", () => {
  assert.equal(parisLifeLabel({ status: "non_propagating", cycles_to_failure: 10_000_000 }), "ΔK < ΔK_th (no growth computed)");
  assert.doesNotMatch(parisLifeLabel({ status: "non_propagating", cycles_to_failure: 10_000_000 }), /Safe/);
  const runout = parisLifeLabel({ status: "runout", cycles_to_failure: 4_200_000 });
  assert.match(runout, /No fracture when integration stopped at N = 4,200,000 cycles/);
  assert.match(runout, /\(cycle limit reached\)/);
  assert.doesNotMatch(runout, /negligible growth rate/);
  assert.match(
    parisLifeLabel({ status: "runout", cycles_to_failure: 4_200_000, final_crack_size_um: 812.5 }),
    /cycle limit reached; crack size 812\.5 µm/,
  );
  assert.doesNotMatch(runout, /^>/);
  assert.equal(parisLifeLabel({ status: "fractured", cycles_to_failure: 12345 }), "12,345 cycles");

  const result = (limit: number, status: string, sa = 240) => withRequestInputs({
    fatigue_limit: { fatigue_limit_corrected_MPa: limit },
    paris_crack_growth: { status },
  }, { stressAmplitude_MPa: sa });
  assert.match(fatigueCriteriaDisagreement(result(200, "non_propagating")) ?? "", /Paris model predicts no growth/);
  assert.match(fatigueCriteriaDisagreement(result(300, "fractured")) ?? "", /Paris model predicts crack growth/);
  assert.equal(fatigueCriteriaDisagreement(result(200, "fractured")), null);
  assert.equal(fatigueCriteriaDisagreement(result(300, "non_propagating")), null);
  // Only the σ_a the result was computed with is used; a bare result has no comparison.
  assert.equal(fatigueCriteriaDisagreement({ fatigue_limit: { fatigue_limit_corrected_MPa: 200 }, paris_crack_growth: { status: "non_propagating" } }), null);
  assert.equal(fatigueCriteriaDisagreement(result(200, "non_propagating", 150)), null);

  const src = read("src/components/MurakamiFatigueLab.tsx");
  assert.doesNotMatch(src, /\(Safe\)/);
  assert.doesNotMatch(src, /R-ratio not modelled/);
  assert.match(src, /Unsourced constants/);
});

test("specimen records: synthetic stats scrubbed, derived chemistry cleared, downloads complete", () => {
  const base = createUnresolvedDigitalTwin();
  const demo = labelTwinEvidence(
    { ...base, mechanical: { ...base.mechanical, mmpdsStatisticalBasis: { basisLevel: "Not assessed", sampleCountN: 128, cpkReliability: 1.62 } } },
    [base.id],
  );
  assert.equal(demo.evidence?.kind, "demo");
  assert.equal(demo.mechanical.mmpdsStatisticalBasis.cpkReliability, null);
  assert.equal(demo.mechanical.mmpdsStatisticalBasis.sampleCountN, null);

  const withDerived = {
    ...base,
    chemistry: {
      ...base.chemistry,
      nominalComposition: { Fe: 70, Cr: 18, Ni: 12 },
      schaefflerCoordinates: { crEq: 18, niEq: 12, estimatedFerriteNumber: 5, matrixPrediction: "Austenite" },
      carbonEquivalent: { ceIIW: 0.5 },
    },
    thermodynamics: { ...base.thermodynamics, liquidusTemperatureC: 1450, solidusTemperatureC: 1400, freezingRangeC: 50 },
  };
  const edited = withEditedComposition(withDerived, { Fe: 60, Cr: 25, Ni: 15 });
  assert.deepEqual(edited.chemistry.nominalComposition, { Fe: 60, Cr: 25, Ni: 15 });
  assert.equal(edited.chemistry.schaefflerCoordinates, undefined);
  assert.equal(edited.chemistry.carbonEquivalent, undefined);
  assert.equal(edited.thermodynamics.liquidusTemperatureC, null);
  assert.equal(edited.thermodynamics.solidusTemperatureC, null);
  assert.equal(edited.thermodynamics.freezingRangeC, null);

  const big = "x".repeat(5000) + "é";
  const href = attachmentDownloadHref(big);
  assert.equal(decodeURIComponent(href.slice(href.indexOf(",") + 1)), big, "no truncation");
  assert.equal(attachmentDownloadHref("data:text/plain;base64,QUJD"), "data:text/plain;base64,QUJD");

  const src = read("src/components/DigitalTwinHub.tsx");
  for (const claim of ["IndexedDB Engine", "10⁶-point", '"0.5 MB"', "generate synthetic benchmarks", "btoa(", "New Twin", "No 5MB Limit", "Uncapped"]) {
    assert.ok(!src.includes(claim), claim);
  }
  assert.match(src, /Unavailable: synthetic record has no coupon population/);
});

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
