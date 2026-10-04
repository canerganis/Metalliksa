import assert from "node:assert/strict";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ModuleNav, navTabStop } from "../src/components/ModuleNav";
import { MODULES } from "../src/data/workspaces";

const mods = [
  { id: "a", workspace: "lpbf" },
  { id: "b", workspace: "lpbf" },
  { id: "c", workspace: "materials" },
];

test("navTabStop: remembered entry only under the module it was focused with; else active; else first", () => {
  assert.equal(navTabStop(mods, { key: "", tab: "a" }, "a"), "a");
  assert.equal(navTabStop(mods, { key: "c", tab: "a" }, "a"), "c", "arrowed to c, still on a");
  assert.equal(navTabStop(mods, { key: "ws:materials", tab: "a" }, "a"), "ws:materials");
  // A navigation from outside (hash change, back button, Next link) moves the stop to the aria-current entry.
  assert.equal(navTabStop(mods, { key: "c", tab: "a" }, "b"), "b");
  // A filter that hides the remembered entry and the active module falls back to the first visible one.
  assert.equal(navTabStop(mods.slice(2), { key: "a", tab: "a" }, "a"), "c");
  assert.equal(navTabStop([], { key: "", tab: "a" }, "a"), undefined);
});

test("rendered navigation has exactly one Tab stop, on the aria-current module", () => {
  const active = MODULES[3];
  const html = renderToStaticMarkup(<ModuleNav modules={[...MODULES]} activeTab={active.id} activeWorkspace={active.workspace} onNavigate={() => undefined} />);
  const buttons = [...html.matchAll(/<button[^>]*>/g)].map(m => m[0]);
  assert.ok(buttons.length > MODULES.length, "module buttons plus workspace headings");
  const stops = buttons.filter(b => /tabindex="0"/.test(b));
  assert.equal(stops.length, 1);
  assert.match(stops[0], /aria-current="page"/);
  assert.ok(buttons.every(b => /tabindex="(0|-1)"/.test(b)));
});

test("every module entry is described by the hint AND its own description; headings by the hint", () => {
  const html = renderToStaticMarkup(<ModuleNav modules={[...MODULES]} activeTab={MODULES[0].id} activeWorkspace={MODULES[0].workspace} onNavigate={() => undefined} />);
  const escape = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
  for (const module of MODULES) {
    assert.match(html, new RegExp(`aria-describedby="module-nav-hint nav-desc-${module.id}"`), module.id);
    assert.ok(html.includes(`<span id="nav-desc-${module.id}">${escape(module.description)}</span>`), `${module.id} description element`);
  }
  assert.match(html, /<div hidden="">/, "descriptions are referenced, not displayed");
  assert.match(html, /<p id="module-nav-hint" class="mk-sr-only">Arrow keys move between modules\.<\/p>/);
  const headings = [...html.matchAll(/<button[^>]*aria-describedby="module-nav-hint"[^>]*>/g)];
  assert.ok(headings.length >= 1 && headings.every(h => !/aria-current/.test(h[0])), "workspace headings: hint only");
});
