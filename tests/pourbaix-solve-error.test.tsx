import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { DynamicPourbaixStudio, PourbaixSolveError } from "../src/components/DynamicPourbaixStudio";

test("Pourbaix solver failure renders as an accessible alert with the existing error text only", () => {
  const html = renderToStaticMarkup(<PourbaixSolveError message="Failed to reach Python Pourbaix solver."/>);
  assert.match(html, /^<p role="alert"[^>]*>Failed to reach Python Pourbaix solver\.<\/p>$/);
  assert.equal(renderToStaticMarkup(<PourbaixSolveError message={null}/>), "");
  assert.equal(renderToStaticMarkup(<PourbaixSolveError message=""/>), "");
});

interface Node { tag: string; attrs: string; children: (Node | string)[]; parent?: Node }
/** Minimal static-markup parser (the studio renders no void elements other than input/br/hr/img/path-like self closers). */
function parse(html: string): Node {
  const root: Node = { tag: "#root", attrs: "", children: [] };
  let current = root;
  const re = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)((?:[^>"']|"[^"]*"|'[^']*')*?)(\/?)>|([^<]+)/g;
  const VOID = new Set(["input", "br", "hr", "img", "meta", "link"]);
  for (let m = re.exec(html); m; m = re.exec(html)) {
    if (m[5] !== undefined) { current.children.push(m[5]); continue; }
    const [, closing, tag, attrs, self] = m;
    if (closing) { if (current.parent) current = current.parent; continue; }
    const node: Node = { tag: tag.toLowerCase(), attrs, children: [], parent: current };
    current.children.push(node);
    if (!VOID.has(node.tag) && !self) current = node;
  }
  return root;
}
const text = (node: Node | string): string => typeof node === "string" ? node : node.children.map(text).join("");
const find = (node: Node, predicate: (n: Node) => boolean, out: Node[] = []): Node[] => {
  for (const child of node.children) if (typeof child !== "string") { if (predicate(child)) out.push(child); find(child, predicate, out); }
  return out;
};

test("the studio renders the solver error as an alert inside the diagram panel, directly above the overlay controls", () => {
  const ERROR = "Failed to reach Python Pourbaix solver.";
  const tree = parse(renderToStaticMarkup(<DynamicPourbaixStudio initialSolveError={ERROR}/>));
  const alerts = find(tree, n => /\brole="alert"/.test(n.attrs));
  const solver = alerts.filter(n => text(n).trim() === ERROR);
  assert.equal(solver.length, 1, "exactly one alert carries the solver error");
  const alert = solver[0];
  assert.equal(alert.tag, "p");
  const panel = alert.parent!;
  // The panel is the diagram column: it holds the E-pH diagram heading and the overlay toolbar.
  assert.match(text(panel), /E-pH Pourbaix Diagram/);
  const siblings = panel.children.filter((c): c is Node => typeof c !== "string");
  const index = siblings.indexOf(alert);
  assert.ok(index > 0, "the alert follows the diagram header");
  assert.match(text(siblings[index - 1]), /E-pH Pourbaix Diagram/, "directly after the diagram header");
  assert.match(text(siblings[index + 1]), /Show Test Data Overlay/, "directly before the overlay toolbar");
  // Without an error nothing is rendered in that slot.
  const clean = parse(renderToStaticMarkup(<DynamicPourbaixStudio/>));
  assert.equal(find(clean, n => /\brole="alert"/.test(n.attrs) && text(n).includes(ERROR)).length, 0);
});
