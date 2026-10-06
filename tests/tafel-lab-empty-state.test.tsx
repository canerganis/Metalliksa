import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { TafelPolarizationLab } from "../src/components/TafelPolarizationLab";
import * as tafel from "../src/utils/tafelParser";

// No benchmark polarization curves are bundled: the PRNG-fabricated curves and the benchmark list were removed.
// The lab used to read TAFEL_BENCHMARK_DATASETS[0] on first render and crash; it now shows a
// neutral empty state with a file input and renders the full lab only after a file is parsed.
test("TafelPolarizationLab renders an empty state instead of crashing without benchmark data", () => {
  assert.equal("TAFEL_BENCHMARK_DATASETS" in tafel, false);
  const html = renderToStaticMarkup(<TafelPolarizationLab />);
  assert.match(html, /No polarization data loaded\. No benchmark curves are bundled; load a polarization data file\./);
  assert.match(html, /<input[^>]*aria-label="Load polarization data file"[^>]*type="file"/);
  assert.doesNotMatch(html, /role="alert"/);
});
