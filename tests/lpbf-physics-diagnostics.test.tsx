import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { LpbfPhysicsDiagnostics } from "../src/components/3d-distortion-lab/LpbfPhysicsDiagnostics";
import { parseSimulationJob, type SimulationResult } from "../src/services/lpbfSimulationService";

const result = {
  requestedMode: "screening", effectiveMode: "screening", fallbackReason: null,
  schemaVersion: 1, validationStatus: "unvalidated", productionReady: false, confidence: "low",
  settings: {}, solver: { id: "synthetic-test", version: "1" },
  material: { name: "fixture", quality: "synthetic", source: "Not experimental" },
  label: "Screening only", regime: "test", mainRisk: "test", recommendation: "test", riskScope: "test",
  metrics: { width_um: 120, depth_um: 60, length_um: 200 }, assumptions: [], analyticalComparison: {},
  numericalDiagnostics: { sourceIntegration: "cell-integrated-gaussian-gl2-v1", stabilityLimit: "local-conductance-row-sum",
    minimumCapturedSourceFraction: .9, maximumSourceRenormalization: 1/.9, maximumSurfaceOffset_um: 2,
    maximumTimestep_s: 1e-6, maximumEnthalpyIncrement_K: 24, sourceTimestepRetries: 2,
    acceptedTimestepDistribution: { methodId: "accepted-timestep-distribution-v1", count: 3,
      total_s: 2.5e-7, sumSquared_s2: 2.25e-14, mean_s: 2.5e-7/3,
      minimum_s: .5e-7, p50_s: 1e-7, p90_s: 1e-7, p99_s: 1e-7, maximum_s: 1e-7,
      eulerFirstOrderWeightedDt_s: .9e-7, requestedMaxDt_s: 1e-7, requestedMaxDtHitFraction: 2/3,
      sourceLimitedStepCount: 1, sourceTimestepRetries: 2 } },
  geometricDefectScreen: { modelId: "elliptic-overlap-screening-v2", scope: "single-track-cross-section", status: "geometry-screened",
    limitations: ["Synthetic fixture, not experimental evidence"], lackOfFusion: {
      status: "lack-of-fusion-screened", ellipseIndex: 1.14, signedMargin: -.14, overlapDepth_um: 33,
      maximumHatch_um: 89, riskScreened: true, reason: "Idealized geometry only" } },
};
const parse = (patch = {}) => parseSimulationJob({ id: "c".repeat(32), status: "completed", progress: 1, log: "", error: null, result: { ...result, ...patch } });

test("accepted-step peak provenance preserves zero melt and rejects inconsistent indices", () => {
  const d = { ...result.numericalDiagnostics, meltPoolExtraction: "accepted-step-molten-volume-v1",
    peakMeltTime_s: .0002, peakMeltStep: 20, meltPoolObservedSteps: 100,
    sampledPeakMeltVolume_um3: 16, peakMeltSamplingLossFraction: 1/3 };
  assert.equal(parse({ numericalDiagnostics: d }).result!.numericalDiagnostics!.peakMeltStep, 20);
  assert.equal(parse({ numericalDiagnostics: { ...d, peakMeltTime_s: null, peakMeltStep: null,
    sampledPeakMeltVolume_um3: 0, peakMeltSamplingLossFraction: 0 } }).result!.numericalDiagnostics!.peakMeltTime_s, null);
  for (const patch of [{ peakMeltStep: 101 }, { peakMeltStep: 1.5 }, { peakMeltTime_s: null },
    { meltPoolExtraction: "sampled" }, { peakMeltSamplingLossFraction: 1.1 }, { sampledPeakMeltVolume_um3: -1 }]) {
    assert.throws(() => parse({ numericalDiagnostics: { ...d, ...patch } }), /melt pool extraction/);
  }
});

test("physics diagnostics retain numerical limits and do not claim porosity", () => {
  const parsed = parse().result!;
  const html = renderToStaticMarkup(<LpbfPhysicsDiagnostics result={parsed}/>);
  assert.match(html, /90%/);
  assert.match(html, /Accepted timestep distribution/);
  assert.match(html, /Euler weighted timestep/);
  assert.match(html, /first-order/);
  assert.match(html, /lack of fusion screened/);
  assert.match(html, /porosity remain unresolved/);
  assert.match(html, /not a recommended process setting/);
  assert.match(html, /Harkin/);
});

test("LPBF result parsing accepts the versioned adaptive Gaussian source diagnostics", () => {
  const diagnostics = { ...result.numericalDiagnostics,
    sourceIntegration: "cell-integrated-gaussian-adaptive-gl-v2" };
  assert.equal(parse({ numericalDiagnostics: diagnostics }).result!.numericalDiagnostics!.sourceIntegration,
    "cell-integrated-gaussian-adaptive-gl-v2");
  const html = renderToStaticMarkup(<LpbfPhysicsDiagnostics result={parse({ numericalDiagnostics: diagnostics }).result!}/>);
  assert.match(html, /Adaptive Gauss-Legendre source integration/);
  assert.doesNotMatch(html, /two-point time integration/);
});

test("source integration label follows the recorded method and handles absent or unknown identifiers", () => {
  const legacy = parse().result!;
  assert.match(renderToStaticMarkup(<LpbfPhysicsDiagnostics result={legacy}/>), /Two-point Gauss-Legendre source integration/);

  const renderWithSourceIntegration = (sourceIntegration: unknown) => renderToStaticMarkup(
    <LpbfPhysicsDiagnostics result={{ ...legacy, numericalDiagnostics: {
      ...legacy.numericalDiagnostics!, sourceIntegration,
    } } as SimulationResult}/>);
  assert.match(renderWithSourceIntegration(undefined), /Source integration method unavailable/);
  assert.match(renderWithSourceIntegration("future-integrator-v3"),
    /Source integration method unavailable · recorded identifier: future-integrator-v3/);
  assert.match(renderWithSourceIntegration("future <integrator>"),
    /future &lt;integrator&gt;/);
});

test("aggregate geometry presents unknown overlap without fake zero values", () => {
  const geometricDefectScreen = { ...result.geometricDefectScreen, scope: "aggregate-multi-track", status: "unresolved",
    lackOfFusion: { status: "unresolved", ellipseIndex: null, signedMargin: null, overlapDepth_um: null,
      maximumHatch_um: null, riskScreened: null, reason: "Aggregate geometry cannot identify local overlap" } };
  const html = renderToStaticMarkup(<LpbfPhysicsDiagnostics result={parse({ geometricDefectScreen }).result!}/>);
  assert.equal((html.match(/Unresolved/g) || []).length, 3);
  assert.doesNotMatch(html, /Unresolved µm/);
  assert.equal(renderToStaticMarkup(<LpbfPhysicsDiagnostics result={{} as SimulationResult}/>), "");
});

test("invalid source and overlap contracts are rejected before rendering", () => {
  for (const patch of [{ minimumCapturedSourceFraction: 0 }, { minimumCapturedSourceFraction: 1.1 },
    { maximumSourceRenormalization: .9 }, { sourceTimestepRetries: .5 }, { maximumTimestep_s: Infinity },
    { sourceIntegration: "fake-CFD" }]) {
    assert.throws(() => parse({ numericalDiagnostics: { ...result.numericalDiagnostics, ...patch } }));
  }
  for (const patch of [{ mean_s: 1 }, { sumSquared_s2: 0 }, { p90_s: .4e-7 },
    { requestedMaxDtHitFraction: 1.1 }, { sourceTimestepRetries: 0 }]) {
    assert.throws(() => parse({ numericalDiagnostics: { ...result.numericalDiagnostics,
      acceptedTimestepDistribution: { ...result.numericalDiagnostics.acceptedTimestepDistribution, ...patch } } }));
  }
  assert.throws(() => parse({ geometricDefectScreen: { ...result.geometricDefectScreen, limitations: "invalid" } }));
  assert.throws(() => parse({ geometricDefectScreen: { ...result.geometricDefectScreen, lackOfFusion: { ...result.geometricDefectScreen.lackOfFusion, ellipseIndex: "1.14" } } }));
});

test("field-resolved inter-track overlap renders correctly and rejects invalid values", () => {
  const fieldOverlapDiagnostics = {
    modelId: "field-inter-track-overlap-v1", scope: "multi-track-field",
    tracks: 2, layers: 1, trackOverlapRatio: 0.354, meanInterTrackOverlapRatio: 0.354,
    minInterTrackOverlapRatio: 0.354, pairwiseOverlapRatios: [0.354],
    interTrackGapVolume_um3: 0, hasInterTrackGap: false, interTrackLackOfFusion: false,
    midpointPenetrationDepth_um: 52, interLayerPenetrationDepth_um: 18, interLayerRemeltRatio: 0.22,
    globalRemeltRatio: 0.42, totalMeltVolume_um3: 150000, totalRemeltVolume_um3: 63000,
    status: "fused-inter-track", note: "Continuous fused volume across hatch spacing."
  };
  const parsed = parse({ fieldOverlapDiagnostics }).result!;
  const html = renderToStaticMarkup(<LpbfPhysicsDiagnostics result={parsed}/>);
  assert.match(html, /Field-resolved inter-track overlap/);
  assert.match(html, /35\.4%/);
  assert.match(html, /Continuous fused volume/);
  assert.match(html, /fused inter track/);

  for (const patch of [
    { modelId: "unverified" }, { tracks: 0 }, { trackOverlapRatio: 1.5 },
    { interTrackGapVolume_um3: -1 }, { globalRemeltRatio: 1.2 }
  ]) {
    assert.throws(() => parse({ fieldOverlapDiagnostics: { ...fieldOverlapDiagnostics, ...patch } }));
  }
});
