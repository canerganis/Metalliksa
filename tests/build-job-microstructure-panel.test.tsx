import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { BuildJobMicrostructurePanel } from "../src/components/3d-distortion-lab/BuildJobMicrostructurePanel";

// Real Python output: python/test_lpbf_build_job.py check_microstructure_fixture() fails when this file differs from
// project_build_job_microstructure (regenerate with `python test_lpbf_build_job.py --write-microstructure-fixture`).
const BLOCKS = JSON.parse(readFileSync(new URL("./fixtures/build-job-microstructure-blocks.json", import.meta.url), "utf8"));
const html = (name: string) => {
  assert.ok(BLOCKS[name], name);
  return renderToStaticMarkup(<BuildJobMicrostructurePanel microstructure={BLOCKS[name]} />);
};
const text = (markup: string) => markup.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/&gt;/g, ">").replace(/\s+/g, " ");

test("available (field map): numbers, correlation names, modelId · gradientSource, keyhole regime note, no fallback note", () => {
  const markup = html("available_in718_285_960");
  const t = text(markup);
  assert.match(markup, /data-micro-status="available"/);
  assert.ok(t.includes("0.67") && t.includes("0.53"), t);
  assert.ok(t.includes("Hunt–Lu 1996 · solidification-front-v1 · solidification-front-v1"), t);
  assert.ok(t.includes("cells have no secondary arms · Kirkwood 1985"), t);
  assert.ok(t.includes("Cellular (Hunt G/R screening)"), t);
  assert.match(markup, /data-micro-note="regime"/);
  assert.ok(t.includes("Keyhole Mode: outside the conduction regime of the G/R field"), t);
  assert.doesNotMatch(markup, /data-micro-note="screening-fallback"/);
  assert.ok(!t.includes("Unavailable"), t);
});

test("screening-fallback: amber note with Python's reason, tail-length-fallback shown, numbers still rendered", () => {
  const markup = html("screening_fallback_in718_60_2000");
  const t = text(markup);
  assert.match(markup, /data-micro-status="screening-fallback"/);
  assert.match(markup, /data-micro-note="screening-fallback"[^>]*>/);
  assert.ok(t.includes(BLOCKS.screening_fallback_in718_60_2000.reason), t);
  assert.ok(t.includes("tail-length-fallback"), t);
  assert.ok(t.includes("2.67"), t);
  assert.ok(t.includes("Kirkwood 1985 · solidification-front-v1 · tail-length-fallback"), t);
  assert.doesNotMatch(markup, /data-micro-note="regime"/);
});

test("unavailable: reason only, no numbers, no PDAS/SDAS tiles", () => {
  const markup = html("unavailable_no_kinetics");
  const t = text(markup);
  assert.match(markup, /data-micro-status="unavailable"/);
  assert.ok(t.includes("Unavailable — thermal.solidificationKinetics missing or non-finite"), t);
  assert.doesNotMatch(markup, /data-micro-metric=/);
});

test("no microstructure block renders nothing", () => {
  assert.equal(renderToStaticMarkup(<BuildJobMicrostructurePanel microstructure={undefined} />), "");
});
