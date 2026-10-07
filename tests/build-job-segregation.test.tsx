import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { BuildJobSegregationPanel } from "../src/components/3d-distortion-lab/BuildJobSegregationPanel";
import { BuildJobMicrostructurePanel } from "../src/components/3d-distortion-lab/BuildJobMicrostructurePanel";

// Real Python output: python/test_lpbf_build_job.py check_segregation_fixture() fails when this file differs from
// build_job_segregation (regenerate with `python test_lpbf_build_job.py --write-segregation-fixture`).
const BLOCKS = JSON.parse(readFileSync(new URL("./fixtures/build-job-segregation-blocks.json", import.meta.url), "utf8"));
const MICRO = JSON.parse(readFileSync(new URL("./fixtures/build-job-microstructure-blocks.json", import.meta.url), "utf8"));
const html = (name: string) => {
  assert.ok(BLOCKS[name], name);
  return renderToStaticMarkup(<BuildJobSegregationPanel segregation={BLOCKS[name]} />);
};
const text = (markup: string) =>
  markup
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&gt;/g, ">")
    .replace(/&lt;/g, "<")
    .replace(/\s+/g, " ");
const LABEL_PREFIX = "Literature estimate (screening)";

test("available (IN718): label chip as text, k with citation, Nb band, risk class, ratio, copied G/R, validity, upper bound", () => {
  const block = BLOCKS.available_in718_285_960;
  assert.equal(block.status, "available");
  const markup = html("available_in718_285_960");
  const t = text(markup);
  assert.match(markup, /data-seg-status="available"/);
  assert.match(markup, /data-seg-label/);
  assert.ok(t.includes(block.evidenceLabel), t);
  assert.ok(block.evidenceLabel.startsWith(LABEL_PREFIX));
  assert.ok(t.includes("k Nb = 0.46"), t);
  assert.ok(t.includes("DuPont, C.V. Robino, A.R. Marder") && t.includes("Table 3"), t);
  // Nb band rows min / nominal / max with Python's fractions (%, one decimal).
  for (const p of block.band) {
    assert.match(markup, new RegExp(`data-seg-band-row="${p.label}"`));
    assert.ok(t.includes(`${(p.binaryUpperBound.fLaves * 100).toFixed(1)} %`), `${p.label} ${t}`);
    assert.ok(t.includes(`${(p.pseudoTernaryAtCmax.fLaves * 100).toFixed(1)} %`), `${p.label} ${t}`);
  }
  assert.ok(t.includes("upper bound"), t);
  assert.ok(t.includes(`Laves risk class: ${block.riskClass}`), t);
  assert.ok(t.includes("core k·C 0 = 0.46"), t);
  assert.ok(t.includes("capped at the γ/Laves composition"), t);
  // Process coupling: G, R and morphology copied from the build job's microstructure block.
  assert.match(markup, /data-seg-coupling="available"/);
  assert.ok(t.includes(block.processCoupling.G_K_m.toExponential(2)), t);
  assert.ok(t.includes(block.processCoupling.R_m_s.toFixed(4)), t);
  assert.ok(t.includes(block.processCoupling.morphology), t);
  // Validity warning and the upper-bound wording.
  assert.match(markup, /data-seg-validity/);
  assert.ok(t.includes("Outside the source regime"), t);
  for (const r of block.validity.outsideSourceCompositionReasons) assert.ok(t.includes(r), r);
  assert.match(markup, /data-seg-upper-bound/);
  assert.ok(t.includes(block.upperBoundNote), t);
  for (const word of ["Validated", "Calibrated", "Measured"]) assert.ok(!t.includes(word), word);
});

test("degenerate-floor microstructure: composition result still shown, process coupling reason only", () => {
  const block = BLOCKS.in718_degenerate_floor_synthetic;
  assert.equal(block.processCoupling.status, "unavailable");
  const markup = html("in718_degenerate_floor_synthetic");
  const t = text(markup);
  assert.match(markup, /data-seg-coupling="unavailable"/);
  assert.ok(t.includes(`Process coupling unavailable — ${block.processCoupling.reason}`), t);
  assert.ok(!t.includes("K/m"), t);
});

test("unavailable (IN625): reason only, no numbers, no band", () => {
  const block = BLOCKS.in625_unavailable;
  assert.equal(block.status, "unavailable");
  const markup = html("in625_unavailable");
  const t = text(markup);
  assert.match(markup, /data-seg-status="unavailable"/);
  assert.ok(t.includes(`Unavailable — ${block.reason}`), t);
  assert.doesNotMatch(markup, /data-seg-band|data-seg-k|data-seg-coupling|data-seg-risk/);
  assert.ok(!/\d+\.\d+ %/.test(t), t);
  assert.ok(!t.includes("k Nb"), t);
});

test("not-applicable (316L): reason only, no numbers", () => {
  const block = BLOCKS.ss316l_not_applicable;
  assert.equal(block.status, "not-applicable");
  const markup = html("ss316l_not_applicable");
  const t = text(markup);
  assert.match(markup, /data-seg-status="not-applicable"/);
  assert.ok(t.includes(`Not applicable — ${block.reason}`), t);
  assert.doesNotMatch(markup, /data-seg-band|data-seg-label|data-seg-coupling/);
  assert.ok(!/\d/.test(t.replace(/316L/g, "")), t);
});

test("unknown status or malformed block is never shown as available", () => {
  const markup = renderToStaticMarkup(
    <BuildJobSegregationPanel segregation={{ ...BLOCKS.available_in718_285_960, status: "ok" }} />,
  );
  assert.match(markup, /data-seg-status="unavailable"/);
  assert.doesNotMatch(markup, /data-seg-band/);
  assert.equal(renderToStaticMarkup(<BuildJobSegregationPanel segregation={null} />), "");
  assert.equal(renderToStaticMarkup(<BuildJobSegregationPanel segregation={[1, 2]} />), "");
});

test("rendered inside the microstructure panel via the optional prop, absent without it", () => {
  const micro = MICRO.available_in718_285_960;
  const withSeg = renderToStaticMarkup(
    <BuildJobMicrostructurePanel micro={micro} segregation={BLOCKS.available_in718_285_960} />,
  );
  assert.match(withSeg, /data-micro-status="available"[\s\S]*data-seg-status="available"/);
  assert.match(withSeg, /<section[^>]*aria-labelledby="[^"]+"/);
  const without = renderToStaticMarkup(<BuildJobMicrostructurePanel micro={micro} />);
  assert.doesNotMatch(without, /data-seg-status/);
});
