import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const src = (path: string) => readFileSync(path, "utf8");

test("TTT/CCT: LSW tab is labelled illustrative and the Gibbs-minimization badge is gone", () => {
  const text = src("src/components/PhaseKineticsTTTCCTStudio.tsx");
  assert.match(text, /LSW Aging & Orowan \(illustrative\)/);
  assert.match(text, /generic LSW \/ Orowan constants/);
  assert.doesNotMatch(text, />\s*Gibbs Minimization\s*</);
});

test("Tafel: no preloaded-benchmark claim, truthful zero-current note and solver method", () => {
  const text = src("src/components/TafelPolarizationLab.tsx");
  assert.doesNotMatch(text, /Preloaded Benchmark Standards|NIST \/ ASTM G5 calibrated|Zero-noise filtering|handleSelectBenchmark/);
  assert.match(text, /Zero currents clamped to 1e-10/);
  assert.doesNotMatch(src("python/tafel_corrosion_rate_solver.py"), /Evans Optimization/);
});

test("Corrosion lab: invented galvanic calculator and unsourced CPT line are removed", () => {
  const text = src("src/components/CorrosionEngineeringLab.tsx");
  assert.doesNotMatch(text, /GALVANIC_METALS|ASTM G82|Galvanic Couple|estimatedCPT|2\.5 \* prenScore|6% FeCl/);
  assert.doesNotMatch(text, /Offshore Seawater Immune|ISO 15156/);
  assert.match(text, /PREN = %Cr/);
});

test("Corrosion kinetics studio: no fixed-constant coating charts, dead selector or hand-written Python tab", () => {
  const text = src("src/components/CorrosionEISKineticsStudio.tsx");
  assert.doesNotMatch(text, /coatingType|coatingNyquist|coatingTimeline|Brasher|python_code|Python Engine Code|exposureDays/);
  assert.match(text, /polarizationResistance_Rp_Ohm_cm2/);
});

test("annual-rate module: no template Python tab, no x3.5 pitting heuristic, no 999-year placeholder", () => {
  const ui = src("src/components/PythonAnnualCorrosionRateModule.tsx");
  assert.doesNotMatch(ui, /pythonCode|Executable Python Script|rulPittingYears|lossPittingMm|> Safe</);
  const py = src("python/tafel_corrosion_rate_solver.py");
  assert.doesNotMatch(py, /pitting_acceleration_factor|999\.0|reproducible_python_code/);
  assert.doesNotMatch(src("src/services/pythonComputationService.ts"), /pittingFactor|K1 = 0\.00327072/);
});

test("EDS canvas: no frame-rate claim; the SNIP background overlay prop is not named deconvolutionPeaks", () => {
  const canvas = src("src/components/WebGLSpectrometerCanvas.tsx");
  assert.doesNotMatch(canvas, /60 FPS|deconvolutionPeaks/);
  assert.match(canvas, /backgroundOverlays/);
  assert.doesNotMatch(src("src/render/webglShaderEngine.ts"), /60 FPS/);
  assert.doesNotMatch(src("src/components/EDSSpectrumLab.tsx"), /deconvolutionPeaks/);
});

test("shell: status chip does not claim engine connection; boot row says the registry is bundled, not probed", () => {
  const app = src("src/App.tsx");
  assert.doesNotMatch(app, /Engine connected/);
  assert.match(app, /Python daemon ready/);
  const boot = src("src/services/bootSteps.ts");
  assert.match(boot, /Module registry \(bundled\)/);
  assert.match(boot, /not probed/);
});

test("database: no 'Calibrated' composition claim and no pooled-family correlation mode", () => {
  assert.doesNotMatch(src("src/components/MaterialsDatabaseView.tsx"), /Calibrated chemical compositions/);
  const heatmap = src("src/components/MaterialsPropertyHeatmapD3.tsx");
  assert.doesNotMatch(heatmap, /property-correlation|Pearson|Correlation \(r\) Matrix|correlationData/);
});
