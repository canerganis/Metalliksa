import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { PourbaixSolveError } from "../src/components/DynamicPourbaixStudio";

test("Pourbaix solver failure renders as an accessible alert with the existing error text only", () => {
  const html = renderToStaticMarkup(<PourbaixSolveError message="Failed to reach Python Pourbaix solver."/>);
  assert.match(html, /^<p role="alert"[^>]*>Failed to reach Python Pourbaix solver\.<\/p>$/);
  assert.equal(renderToStaticMarkup(<PourbaixSolveError message={null}/>), "");
  assert.equal(renderToStaticMarkup(<PourbaixSolveError message=""/>), "");
});

test("the studio renders pythonSolveError next to the diagram controls", () => {
  const source = readFileSync(new URL("../src/components/DynamicPourbaixStudio.tsx", import.meta.url), "utf8");
  const alert = source.indexOf("<PourbaixSolveError message={pythonSolveError} />");
  assert.ok(alert > 0, "error line is rendered");
  assert.ok(alert < source.indexOf("Overlay Toggle Toolbar"), "placed just above the diagram overlay controls");
  assert.ok(alert > source.indexOf("E-pH Pourbaix Diagram"), "inside the diagram panel");
  assert.match(source, /setPythonSolveError\(err\.message \|\| "Failed to reach Python Pourbaix solver\."\)/, "error text unchanged");
});
