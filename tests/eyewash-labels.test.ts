import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const src = (path: string) => readFileSync(path, "utf8");

test("EDS canvas: no frame-rate claim; the SNIP background overlay prop is not named deconvolutionPeaks", () => {
  const canvas = src("src/components/WebGLSpectrometerCanvas.tsx");
  assert.doesNotMatch(canvas, /60 FPS|deconvolutionPeaks/);
  assert.match(canvas, /backgroundOverlays/);
  assert.doesNotMatch(src("src/render/webglShaderEngine.ts"), /60 FPS/);
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

test("calculator info text makes no AWS D1.1 preheat prescription or WRC-1992 claim", () => {
  const info = src("src/components/StandardInfoIcon.tsx");
  assert.doesNotMatch(info, /standardCode: "[^"]*(AWS|WRC|ISO 8249)/);
  assert.doesNotMatch(info, /secondaryCodes: \[[^\]]*(ISO 17660|BS 5135|ASME Sec IX|ASTM A240)/);
  assert.doesNotMatch(info, /to prescribe minimum preheat|Preheat recommended when CE|mandatory hydrogen-controlled/);
  assert.match(info, /unsourced in-house heuristic/);
});

test("database contract text no longer describes the removed correlation mode", () => {
  assert.doesNotMatch(src("src/generated/moduleRegistry.json"), /Pearson/);
});
