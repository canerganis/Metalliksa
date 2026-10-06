import assert from "node:assert/strict";
import test from "node:test";
import { colourScalePeak_C, peakTemperatureBasisLabel } from "../src/utils/peakTemperatureDisplay";

// Wave B D1/D10: the Rosenthal peak (LA-2 regularised point source) is shown with its basis but must not set the colour scale.
const result = (peak: number, surface: number | undefined, basis?: string) => ({
  hydrodynamicsAndRecoil: {
    peakTemperature_C: peak, surfaceTemperature_C: surface, peakTemperatureBasis: basis,
    knudsenRecoilPressure_kPa: 54.7, marangoniNumber: 2014, pecletThermalNumber: 1, powderDenudationWidth_um: 250,
  },
});

test("colour scale top is capped at max(T_vap, 1.5 liquidus) when the peak saturates", () => {
  // IN718 200/800 Rosenthal after LA-2: peak ~35 097 C, surface (= T_vap) 2850 C, liquidus 1336 C.
  assert.equal(colourScalePeak_C(result(35097, 2850, "regularised-singular-source-value"), 1336), 2850);
  // Low-boiling alloy: 1.5*liquidus above T_vap wins.
  assert.equal(colourScalePeak_C(result(9000, 1500), 1200), 1800);
});

test("an unsaturated or unlabelled peak keeps its own value as the scale top", () => {
  assert.equal(colourScalePeak_C(result(1840, 1840), 1336), 1840);
  assert.equal(colourScalePeak_C(result(2500, undefined), 1336), 2500);
});

test("basis label text, null for results without the Wave B label", () => {
  assert.match(peakTemperatureBasisLabel(result(35097, 2850, "regularised-singular-source-value")) ?? "", /regularised point-source centre value, not a wall temperature/);
  assert.match(peakTemperatureBasisLabel(result(19000, 2850, "distributed-source-conduction-centre-value")) ?? "", /not a wall temperature/);
  assert.equal(peakTemperatureBasisLabel(result(2500, 2500)), null);
});
