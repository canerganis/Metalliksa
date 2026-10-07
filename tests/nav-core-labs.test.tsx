import assert from "node:assert/strict";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { registerHooks } from "node:module";
import type { AtriumProps } from "../src/components/Atrium";
import { ModuleNav, labHeadingTarget, navTabStop } from "../src/components/ModuleNav";
import { CORE_FLOW, CORE_MODULE_IDS, LAB_MODULES, MODULES, WORKSPACES, isCoreModule } from "../src/data/workspaces";

// Atrium imports stylesheets, which plain Node cannot load: stub .css modules before importing it.
registerHooks({
  resolve: (specifier, context, next) => specifier.endsWith(".css") ? { url: "data:text/javascript,export default {}", shortCircuit: true } : next(specifier, context),
});

const nav = (activeTab: string, modules = [...MODULES]) => {
  const active = MODULES.find(m => m.id === activeTab)!;
  return renderToStaticMarkup(<ModuleNav modules={modules} activeTab={active.id} activeWorkspace={active.workspace} onNavigate={() => undefined} />);
};
const buttons = (html: string) => [...html.matchAll(/<button[^>]*>/g)].map(m => m[0]);
const moduleButtons = (html: string, ids: readonly string[]) => ids.filter(id => html.includes(`aria-describedby="module-nav-hint nav-desc-${id}"`));

test("core and labs partition the listed modules; core ids are listed and in flow order", () => {
  const listed = MODULES.map(m => m.id);
  for (const id of listed) assert.equal([isCoreModule(id), LAB_MODULES.some(m => m.id === id)].filter(Boolean).length, 1, `${id} is in exactly one of core/labs`);
  assert.equal(CORE_MODULE_IDS.length + LAB_MODULES.length, MODULES.length);
  assert.deepEqual([...CORE_MODULE_IDS, ...LAB_MODULES.map(m => m.id)].sort(), [...listed].sort());
  for (const id of CORE_MODULE_IDS) assert.ok(listed.includes(id), `${id} is a listed module`);
  assert.deepEqual(CORE_FLOW.map(step => step.id), [...CORE_MODULE_IDS]);
  assert.deepEqual(CORE_FLOW.map(step => step.verb), ["Set up and run", "Screen the process window", "Compare with published data", "Check the scorecard"]);
});

test("collapsed render (active core module): core buttons, Labs aria-expanded=false, no lab buttons", () => {
  const html = nav(CORE_MODULE_IDS[0]);
  assert.match(html, /Core - LPBF screening flow/);
  assert.deepEqual(moduleButtons(html, CORE_MODULE_IDS), [...CORE_MODULE_IDS]);
  assert.deepEqual(moduleButtons(html, LAB_MODULES.map(m => m.id)), []);
  const toggle = buttons(html).find(b => /aria-controls="module-nav-labs"/.test(b))!;
  assert.match(toggle, /aria-expanded="false"/);
  assert.ok(html.includes(`Labs (${LAB_MODULES.length})`), "Labs (N) label");
  assert.equal(buttons(html).filter(b => /tabindex="0"/.test(b)).length, 1);
});

test("active lab module expands Labs, owns aria-current and the single tabindex=0", () => {
  const lab = LAB_MODULES[0];
  const html = nav(lab.id);
  const all = buttons(html);
  assert.match(all.find(b => /aria-controls="module-nav-labs"/.test(b))!, /aria-expanded="true"/);
  assert.deepEqual(moduleButtons(html, LAB_MODULES.map(m => m.id)), LAB_MODULES.map(m => m.id));
  assert.equal(all.filter(b => /aria-current="page"/.test(b)).length, 1);
  const stops = all.filter(b => /tabindex="0"/.test(b));
  assert.equal(stops.length, 1);
  assert.match(stops[0], /aria-current="page"/);
  assert.ok(stops[0].includes(`nav-desc-${lab.id}`));
});

test("a filtered list is expanded; the Core heading is hidden when search hides every core entry", () => {
  const html = nav(CORE_MODULE_IDS[0], [...LAB_MODULES].slice(0, 2).concat(MODULES.filter(m => m.id === CORE_MODULE_IDS[0])));
  assert.match(buttons(html).find(b => /aria-controls="module-nav-labs"/.test(b))!, /aria-expanded="true"/);
  const labsOnly = renderToStaticMarkup(<ModuleNav modules={[...LAB_MODULES]} activeTab={LAB_MODULES[0].id} activeWorkspace={LAB_MODULES[0].workspace} onNavigate={() => undefined} />);
  assert.doesNotMatch(labsOnly, /Core - LPBF screening flow/);
});

test("a throwing localStorage still renders (collapsed by default)", () => {
  const g = globalThis as unknown as { window?: unknown };
  const previous = g.window;
  g.window = { localStorage: { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } } };
  try {
    const html = nav(CORE_MODULE_IDS[1]);
    assert.match(buttons(html).find(b => /aria-controls="module-nav-labs"/.test(b))!, /aria-expanded="false"/);
  } finally {
    if (previous === undefined) delete g.window; else g.window = previous;
  }
});

test("Atrium: four flow steps in order with registry labels, the screening note and the Labs count", async () => {
  const { Atrium } = await import("../src/components/Atrium");
  const props: AtriumProps = { continueId: CORE_MODULE_IDS[0], engine: null, engineChecking: false, shortcutLabel: "Ctrl K", onNavigate: () => undefined, onSearch: () => undefined };
  const html = renderToStaticMarkup(<Atrium {...props} />);
  const flow = html.slice(html.indexOf('class="mk-at-flow"'), html.indexOf("</ol>", html.indexOf('class="mk-at-flow"')));
  assert.equal((flow.match(/<li/g) ?? []).length, 4);
  let from = 0;
  for (const step of CORE_FLOW) {
    const module = MODULES.find(m => m.id === step.id)!;
    const at = flow.indexOf(module.label.replace(/&/g, "&amp;"), from);
    assert.ok(at >= from, `${module.label} follows the previous step`);
    assert.ok(flow.includes(step.verb));
    from = at;
  }
  assert.ok(flow.includes("Module maturity; this is not a validation claim"), "maturity badge title");
  assert.ok(html.includes("Flagship - LPBF melt-pool and process screening"));
  assert.ok(html.includes("Start the LPBF flow"));
  assert.ok(html.includes("Screening only. No result in this flow is experimental validation."));
  const counts = [...html.matchAll(/class="mk-at-count">(?:<!-- -->)?(\d+)(?:<!-- -->)? labs/g)].map(m => Number(m[1]));
  assert.equal(counts.reduce((a, b) => a + b, 0), LAB_MODULES.length);
  assert.match(html, new RegExp(`class="mk-at-section-label"><span>(?:<!-- -->)?0?${LAB_MODULES.length}(?:<!-- -->)?</span>Labs`));
});

test("stored preference expands Labs for a core module; still one tabindex=0", () => {
  const g = globalThis as unknown as { window?: unknown };
  const previous = g.window;
  g.window = { localStorage: { getItem: () => "1", setItem() { /* unused */ } } };
  try {
    const html = nav(CORE_MODULE_IDS[0]);
    assert.match(buttons(html).find(b => /aria-controls="module-nav-labs"/.test(b))!, /aria-expanded="true"/);
    assert.deepEqual(moduleButtons(html, LAB_MODULES.map(m => m.id)), LAB_MODULES.map(m => m.id));
    assert.equal(buttons(html).filter(b => /tabindex="0"/.test(b)).length, 1);
  } finally {
    if (previous === undefined) delete g.window; else g.window = previous;
  }
});

test("no Labs heading targets a core module", () => {
  for (const workspace of WORKSPACES) {
    const entries = LAB_MODULES.filter(m => m.workspace === workspace.id);
    if (!entries.length) continue;
    const target = labHeadingTarget(workspace.id, workspace.defaultModule, entries);
    assert.ok(!isCoreModule(target), `${workspace.id} heading target ${target} is a lab`);
    assert.ok(entries.some(m => m.id === target));
  }
});

test("focus key 'labs' with a core-only filtered list leaves exactly one Tab stop", () => {
  const core = MODULES.filter(m => m.id === CORE_MODULE_IDS[0]);
  assert.equal(navTabStop(core, { key: "labs", tab: CORE_MODULE_IDS[0] }, CORE_MODULE_IDS[0], false), CORE_MODULE_IDS[0]);
  assert.equal(navTabStop(core, { key: "labs", tab: CORE_MODULE_IDS[0] }, CORE_MODULE_IDS[0], true), "labs");
});

test("forced-open Labs toggle is aria-disabled with a reason", () => {
  const html = nav(LAB_MODULES[0].id);
  const toggle = buttons(html).find(b => /aria-controls="module-nav-labs"/.test(b))!;
  assert.match(toggle, /aria-disabled="true"/);
  assert.ok(html.includes("Labs stay open while a lab is active or a search is applied."));
});
