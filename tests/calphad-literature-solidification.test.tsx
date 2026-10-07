import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { LiteratureSolidificationCard } from "../src/components/LiteratureSolidificationCard";
import { literatureAlloyIdFromName } from "../src/services/pythonComputationService";

// Real Python output of calphad_solver.literature_solidification_block; python/test_calphad_literature_solidification.py
// fails when this file is stale (regenerate with `python test_calphad_literature_solidification.py --write-fixture`).
const BLOCKS = JSON.parse(readFileSync(new URL("./fixtures/calphad-literature-solidification.json", import.meta.url), "utf8"));
const text = (markup: string) =>
  markup
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&gt;/g, ">")
    .replace(/&lt;/g, "<")
    .replace(/\s+/g, " ");
const render = (name: string) => renderToStaticMarkup(<LiteratureSolidificationCard literature={BLOCKS[name]} />);

test("IN718: heading, label, k with citation and locator, band, upper bound, validity, rapid-solidification pointer", () => {
  const b = BLOCKS.in718;
  const markup = render("in718");
  const t = text(markup);
  assert.match(markup, /data-testid="calphad-literature-solidification"/);
  assert.ok(t.includes("Literature solidification estimate (not CALPHAD)"), t);
  assert.ok(t.includes(b.evidenceLabel), t);
  assert.ok(t.includes(b.source), t);
  assert.ok(t.includes("γ Nb = 0.45") && t.includes("γ C = 0.21"), t);
  for (const k of b.kValues) {
    assert.ok(t.includes(k.citation) && t.includes(k.locator), k.id);
  }
  for (const p of b.band) {
    assert.match(markup, new RegExp(`data-lit-band-row="${p.label}"`));
    assert.ok(t.includes(`${(p.binaryUpperBound.fGammaLavesConstituent * 100).toFixed(1)} %`), t);
    assert.ok(t.includes(`${(p.pseudoTernaryAtCmax.fGammaLavesConstituent * 100).toFixed(1)} %`), t);
    assert.ok(t.includes(`${(p.pseudoTernaryAtCmax.fGammaNbCConstituent * 100).toFixed(1)} %`), t);
  }
  assert.ok(t.includes(b.upperBoundNote), t);
  assert.ok(t.includes(b.rapidSolidificationNote) && t.includes("upper bounds"), t);
  assert.ok(t.includes("Outside the source regime"), t);
  for (const r of b.validity.outsideSourceCompositionReasons) assert.ok(t.includes(r), r);
});

test("IN625: Cieslak k values, no carbon column values, k sensitivity", () => {
  const b = BLOCKS.in625;
  const markup = render("in625");
  const t = text(markup);
  assert.ok(t.includes(b.evidenceLabel), t);
  assert.ok(t.includes("γ Nb = 0.51") && t.includes("γ Nb (liquidus/solidus slopes) = 0.54"), t);
  assert.ok(t.includes("Cieslak") && t.includes("Table VIII") && t.includes("Table VII"), t);
  assert.match(markup, /data-lit-k-sensitivity/);
  for (const p of b.band) assert.ok(t.includes(`${(p.binaryUpperBound.fGammaLavesConstituent * 100).toFixed(1)} %`), t);
  assert.ok(t.includes("not modelled"), t);
  assert.ok(!/\bCALPHAD (result|calculation) (shows|gives)/i.test(t));
});

test("no block, wrong shape or unavailable status: nothing invented", () => {
  assert.equal(renderToStaticMarkup(<LiteratureSolidificationCard literature={undefined} />), "");
  const m = renderToStaticMarkup(<LiteratureSolidificationCard literature={{ status: "unavailable", reason: "x" }} />);
  assert.match(m, /data-lit-note="unavailable"/);
  assert.ok(!/data-lit-band/.test(m));
});

test("alloy id mapping: only IN718 and IN625; 316L and others undefined", () => {
  assert.equal(literatureAlloyIdFromName("Inconel 718 (AMS 5662 / UNS N07718)"), "in718");
  assert.equal(literatureAlloyIdFromName("IN718"), "in718");
  assert.equal(literatureAlloyIdFromName("Inconel 625"), "in625");
  assert.equal(literatureAlloyIdFromName("316L stainless steel"), undefined);
  assert.equal(literatureAlloyIdFromName("Ti-6Al-4V"), undefined);
  assert.equal(literatureAlloyIdFromName(undefined), undefined);
});
