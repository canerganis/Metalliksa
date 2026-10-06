import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { toolpathWarnings } from "../src/components/LpbfToolpathStudioLab";
import { rotationPreviewDeg } from "../src/components/LpbfAdaptiveMitigationLab";
import { fatigueCriteriaDisagreement, parisLifeLabel } from "../src/components/MurakamiFatigueLab";
import {
  attachmentDownloadHref,
  createUnresolvedDigitalTwin,
  labelTwinEvidence,
  withEditedComposition,
} from "../src/utils/digitalTwinEvidence";
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
  assert.doesNotMatch(src, /from 'recharts'/, "unused chart imports removed");
  assert.match(src, /aria-label="Default Laser Power"/);
  assert.match(src, /aria-label="Default Scan Speed"/);
});

test("adaptive mitigation: open-loop wording, no machine-readiness or texture claims", () => {
  assert.equal(rotationPreviewDeg(true, 1), 67);
  assert.equal(rotationPreviewDeg(true, 2), 134);
  assert.equal(rotationPreviewDeg(false, 5), 0);
  const src = read("src/components/LpbfAdaptiveMitigationLab.tsx");
  assert.doesNotMatch(src, /Ready for Machine/);
  assert.doesNotMatch(src, /Suppresses grain texture/);
  assert.doesNotMatch(src, /Energy Peak Reduction/);
  assert.match(src, /Not machine-validated/);
  assert.match(src, /power is not ramped along the acceleration and deceleration phases/);
  assert.match(src, /aria-label="Layer Index"/);
  assert.doesNotMatch(read("python/lpbf_adaptive_feedforward.py"), /Closed-Loop/);
  assert.doesNotMatch(read("src/services/pythonComputationService.ts"), /Closed-Loop Feed-Forward/);
});

test("murakami fatigue: no safety verdict, R handling stated, criteria disagreement flagged", () => {
  assert.equal(parisLifeLabel({ status: "non_propagating", cycles_to_failure: 10_000_000 }), "ΔK < ΔK_th (no growth computed)");
  assert.doesNotMatch(parisLifeLabel({ status: "non_propagating", cycles_to_failure: 10_000_000 }), /Safe/);
  assert.match(parisLifeLabel({ status: "runout", cycles_to_failure: 10_000_000 }), /integration limit/);
  assert.equal(parisLifeLabel({ status: "fractured", cycles_to_failure: 12345 }), "12,345 cycles");

  const result = (limit: number, status: string) => ({
    fatigue_limit: { fatigue_limit_corrected_MPa: limit },
    paris_crack_growth: { status },
  });
  assert.match(fatigueCriteriaDisagreement(result(200, "non_propagating"), 240) ?? "", /Paris model predicts no growth/);
  assert.match(fatigueCriteriaDisagreement(result(300, "fractured"), 240) ?? "", /Paris model predicts crack growth/);
  assert.equal(fatigueCriteriaDisagreement(result(200, "fractured"), 240), null);
  assert.equal(fatigueCriteriaDisagreement(result(300, "non_propagating"), 240), null);

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

test("ICME: no scale theatre, verdict, CAE cards or pulsing latency; 422 messages surface", () => {
  const src = read("src/components/ICMEMultiScalePipelineStudio.tsx");
  for (const claim of ["5-SCALE THREAD", "10⁻¹⁰ m", "Standard Benchmark Preset", "Solver latency", "structuralVerdict", "caeExportCards", "animate-pulse"]) {
    assert.ok(!src.includes(claim), claim);
  }
  assert.match(src, /No pass\/warning verdict is shown/);
  const service = read("src/services/pythonComputationService.ts");
  const icme = service.slice(service.indexOf("async calculateICMEMultiScalePipeline"), service.indexOf("async calculateStochasticUQMMPDS"));
  assert.match(icme, /validationErrorFromResponse\(res, "ICME input rejected"\)/);
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
  assert.match(read("src/components/3d-distortion-lab/MeltPool3DCrossSectionLab.tsx"), /DISTORTION_HEURISTIC_NOTE/);
  const keyhole = read("src/components/KeyholeRaytracingLab.tsx");
  assert.match(keyhole, /Missed power \(outside mesh\)/);
  assert.match(keyhole, /total_missed_W/);
});
