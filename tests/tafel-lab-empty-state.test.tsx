import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { TafelPolarizationLab } from "../src/components/TafelPolarizationLab";
import { TAFEL_BENCHMARK_DATASETS } from "../src/utils/tafelParser";

// TAFEL_BENCHMARK_DATASETS is empty since the PRNG-fabricated curves were removed (BUG 1 fix).
// The lab used to read TAFEL_BENCHMARK_DATASETS[0] on first render and crash; it now shows a
// neutral empty state with a file input and renders the full lab only after a file is parsed.
test("TafelPolarizationLab renders an empty state instead of crashing without benchmark data", () => {
  assert.equal(TAFEL_BENCHMARK_DATASETS.length, 0);
  const html = renderToStaticMarkup(<TafelPolarizationLab />);
  assert.match(html, /No benchmark dataset available/);
  assert.match(html, /<input[^>]*aria-label="Load polarization data file"[^>]*type="file"/);
  assert.doesNotMatch(html, /role="alert"/);
});
