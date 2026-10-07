import React from "react";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { LEGACY_MODULE_REDIRECTS, MODULES, isModuleId, legacyRedirectHash, moduleFromHash, resolveModuleId } from "../src/data/workspaces";
import { LpbfToolpathStudioLab } from "../src/components/LpbfToolpathStudioLab";
import { TOOLPATH_TABS, nextToolpathTab, toolpathTabFromHash, toolpathTabHash } from "../src/components/toolpathFeedforward";

const read = (relative: string) => readFileSync(resolve(import.meta.dirname, "..", relative), "utf8");

function renderAt(hash: string | null): string {
  const g = globalThis as { window?: unknown };
  const before = g.window;
  if (hash !== null) g.window = { location: { hash } };
  try { return renderToStaticMarkup(<LpbfToolpathStudioLab />); } finally { g.window = before; }
}

test("the tablist offers Kinematics and Feed-forward power with roving tabindex", () => {
  assert.deepEqual(TOOLPATH_TABS.map(t => t.label), ["Kinematics", "Feed-forward power"]);
  const html = renderAt(null);
  assert.match(html, /role="tablist"/);
  assert.match(html, /id="toolpath-tab-kinematics"[^>]*aria-selected="true"[^>]*tabindex="0"/);
  assert.match(html, /id="toolpath-tab-feedforward"[^>]*aria-selected="false"[^>]*tabindex="-1"/);
  assert.match(html, /role="tabpanel"[^>]*id="toolpath-panel-feedforward"[^>]*hidden/);
  assert.match(html, /Toolpath &amp; Scanner Kinematics Studio/);
  assert.doesNotMatch(html, /Generate Power-Scaled G-Code/, "the feed-forward panel is not mounted until its tab is visited");
});

test("tablist keys: arrows wrap, Home and End jump, other keys are ignored", () => {
  assert.equal(nextToolpathTab("kinematics", "ArrowRight"), "feedforward");
  assert.equal(nextToolpathTab("feedforward", "ArrowRight"), "kinematics");
  assert.equal(nextToolpathTab("kinematics", "ArrowLeft"), "feedforward");
  assert.equal(nextToolpathTab("feedforward", "ArrowLeft"), "kinematics");
  assert.equal(nextToolpathTab("feedforward", "Home"), "kinematics");
  assert.equal(nextToolpathTab("kinematics", "End"), "feedforward");
  assert.equal(nextToolpathTab("kinematics", "Enter"), null);
  assert.equal(nextToolpathTab("kinematics", "ArrowDown"), null);
  const src = read("src/components/LpbfToolpathStudioLab.tsx");
  assert.match(src, /nextToolpathTab\(tab, event\.key\)/);
  assert.match(src, /refs\.current\[next\]\?\.focus\(\)/);
});

test("deep link #/toolpath-studio?tab=feedforward selects the Feed-forward power tab", () => {
  assert.equal(toolpathTabFromHash("#/toolpath-studio?tab=feedforward"), "feedforward");
  assert.equal(toolpathTabFromHash("#/toolpath-studio"), "kinematics");
  assert.equal(toolpathTabFromHash("#/toolpath-studio?tab=nonsense"), "kinematics");
  assert.equal(toolpathTabHash("feedforward"), "#/toolpath-studio?tab=feedforward");
  assert.equal(toolpathTabHash("kinematics"), "#/toolpath-studio");
  const html = renderAt("#/toolpath-studio?tab=feedforward");
  assert.match(html, /id="toolpath-tab-feedforward"[^>]*aria-selected="true"/);
  assert.match(html, /Generate Power-Scaled G-Code/);
  assert.match(html, /id="toolpath-panel-kinematics"[^>]*hidden/);
  assert.equal(moduleFromHash("#/toolpath-studio?tab=feedforward"), "toolpath-studio");
});

test("the feed-forward panel keeps its honesty wording and shares the toolpath inputs", () => {
  const html = renderAt("#/toolpath-studio?tab=feedforward");
  assert.match(html, /Open-loop per-vector power scaling from scanner kinematics \(no sensor feedback\)/);
  assert.match(html, /power is not ramped along the acceleration and deceleration phases inside a vector/);
  assert.match(html, /no texture or microstructure effect is computed/);
  assert.match(html, /Rotation applied = 67° × 1 = 67°/);
  assert.match(html, /aria-label="Layer Index"/);
  assert.match(html, /aria-label="Source G-Code"/);
  assert.match(html, /shared with the Kinematics tab/);
  const src = read("src/components/LpbfToolpathStudioLab.tsx");
  assert.match(src, /Not machine-validated\. Travel moves carry an explicit S0 while M3 stays on/);
  assert.match(src, /not a peak or local energy value/);
  assert.doesNotMatch(src, /Ready for Machine|Suppresses grain texture|Energy Peak Reduction|Closed-Loop/);
  // One source of truth for the shared inputs: both panels receive the same props object.
  assert.match(src, /<ToolpathKinematicsPanel \{\.\.\.shared\} active=/);
  assert.match(src, /<ToolpathFeedforwardPanel \{\.\.\.shared\} active=/);
});

test("the legacy adaptive-mitigation id redirects to the feed-forward tab and is never a module", () => {
  assert.deepEqual(LEGACY_MODULE_REDIRECTS["adaptive-mitigation"], { id: "toolpath-studio", tab: "feedforward" });
  assert.equal(isModuleId("adaptive-mitigation"), false);
  assert.ok(!MODULES.some(module => module.id === ("adaptive-mitigation" as string)), "the palette and navigation derive from MODULES");
  assert.equal(moduleFromHash("#/adaptive-mitigation"), "toolpath-studio");
  assert.equal(moduleFromHash("#adaptive-mitigation"), "toolpath-studio");
  assert.equal(legacyRedirectHash("#/adaptive-mitigation"), "#/toolpath-studio?tab=feedforward");
  assert.equal(legacyRedirectHash("#/toolpath-studio"), null);
  assert.equal(legacyRedirectHash("#/unknown"), null);
  assert.equal(resolveModuleId("adaptive-mitigation"), "toolpath-studio", "saved last-module state follows the redirect");
  assert.equal(resolveModuleId("toolpath-studio"), "toolpath-studio");
  assert.equal(resolveModuleId("constructor"), null, "prototype keys are not redirects");
  assert.equal(moduleFromHash("#/constructor"), null);
  const app = read("src/App.tsx");
  assert.match(app, /replaceState/);
  assert.doesNotMatch(app, /LpbfAdaptiveMitigationLab/);
  assert.equal(MODULES.find(module => module.id === "murakami-fatigue")?.next, "keyhole-raytracing");
});
