import React from "react";
import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { MetallurgicalUnitConverter } from "../src/components/MetallurgicalUnitConverter";

const text = (m: string) => m.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

test("stress matrix: the psi cell shows a number, not 'unavailable'", () => {
  const t = text(renderToStaticMarkup(<MetallurgicalUnitConverter />));
  const m = t.match(/Pounds\/sq\.in \(psi\)\s+([^\s]+)\s+psi/);
  assert.ok(m, t.slice(0, 600));
  assert.match(m[1], /^[\d,.]+$/);
});
