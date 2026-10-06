import React from "react";
import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { CorrosionEISKineticsStudio } from "../src/components/CorrosionEISKineticsStudio";
import { TafelPolarizationLab } from "../src/components/TafelPolarizationLab";

const text = (m: string) => m.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

test("EIS kinetics studio renders without coating charts, a coating selector or a Python-code tab", () => {
  const t = text(renderToStaticMarkup(<CorrosionEISKineticsStudio />));
  assert.ok(t.length > 100);
  assert.doesNotMatch(t, /Brasher|Coating (Type|Timeline)|Nyquist|Python Engine Code/i);
});

test("Tafel lab renders without the preloaded-benchmark claim", () => {
  const t = text(renderToStaticMarkup(<TafelPolarizationLab />));
  assert.ok(t.length > 20);
  assert.doesNotMatch(t, /Preloaded Benchmark|NIST \/ ASTM G5 calibrated|Zero-noise filtering/);
});
