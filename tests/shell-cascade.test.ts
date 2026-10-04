import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { compile } from "tailwindcss";

// Review fix 8: computed layout facts without a browser. src/index.css (+ src/styles/boot.css, imported
// after it in main.tsx) is compiled with the project's Tailwind for the classes the shell uses, then a
// small cascade resolver (cascade layers, specificity, source order) computes `position` and `z-index`
// for the shell children. It understands only the selector shapes used here: `.a`, `.a:not(.b)` and
// `PARENT > CHILD` compounds; anything else is treated as non-matching.

const require = createRequire(import.meta.url);
const SRC = resolve(process.cwd(), "src");
const tailwindIndex = resolve(dirname(require.resolve("tailwindcss/package.json")), "index.css");

async function compiledShellCss(indexCss: string, candidates: string[]): Promise<string> {
  const compiler = await compile(indexCss, {
    base: SRC,
    loadStylesheet: async (id: string, base: string) => {
      const path = id === "tailwindcss" ? tailwindIndex : resolve(base, id);
      return { path, base: dirname(path), content: readFileSync(path, "utf8") };
    },
  });
  return compiler.build(candidates) + "\n" + readFileSync(resolve(SRC, "styles/boot.css"), "utf8");
}

type Rule = { selector: string; decls: Map<string, string>; layer: string | null; conditional: boolean; order: number };

function parseRules(css: string): { rules: Rule[]; layerOrder: string[] } {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const rules: Rule[] = [];
  const layerOrder: string[] = [];
  const addLayer = (name: string) => { if (!layerOrder.includes(name)) layerOrder.push(name); };
  let order = 0;
  function walk(start: number, end: number, layer: string | null, conditional: boolean) {
    let i = start;
    while (i < end) {
      const brace = text.indexOf("{", i);
      const semi = text.indexOf(";", i);
      if (brace === -1 || brace >= end) {
        // trailing statements such as `@layer theme, base, components, utilities;`
        for (const statement of text.slice(i, end).split(";")) {
          const m = /^\s*@layer\s+([^{]+)$/.exec(statement);
          if (m) m[1].split(",").map(s => s.trim()).filter(Boolean).forEach(addLayer);
        }
        return;
      }
      if (semi !== -1 && semi < brace) {
        const statement = text.slice(i, semi).trim();
        const m = /^@layer\s+(.+)$/.exec(statement);
        if (m) m[1].split(",").map(s => s.trim()).forEach(addLayer);
        i = semi + 1;
        continue;
      }
      // find the matching closing brace
      let depth = 0;
      let j = brace;
      for (; j < end; j += 1) {
        if (text[j] === "{") depth += 1;
        else if (text[j] === "}") { depth -= 1; if (depth === 0) break; }
      }
      const prelude = text.slice(i, brace).trim();
      const body = [brace + 1, j] as const;
      if (prelude.startsWith("@layer")) {
        const name = prelude.slice(6).trim();
        addLayer(name);
        walk(body[0], body[1], layer ? `${layer}.${name}` : name, conditional);
      } else if (prelude.startsWith("@media") || prelude.startsWith("@supports") || prelude.startsWith("@container")) {
        walk(body[0], body[1], layer, true);
      } else if (prelude.startsWith("@")) {
        // @property, @keyframes, @font-face: no element rules
      } else {
        const inner = text.slice(body[0], body[1]);
        const decls = new Map<string, string>();
        // Only the rule's own declarations (nested blocks are skipped).
        const flat = inner.replace(/\{[^{}]*\}/g, "");
        for (const decl of flat.split(";")) {
          const k = decl.indexOf(":");
          if (k > 0) decls.set(decl.slice(0, k).trim(), decl.slice(k + 1).trim());
        }
        rules.push({ selector: prelude, decls, layer, conditional, order: order++ });
      }
      i = j + 1;
    }
  }
  walk(0, text.length, null, false);
  return { rules, layerOrder };
}

type El = { classes: string[]; parent?: string[] };
const unescape = (s: string) => s.replace(/\\(.)/g, "$1");

/** Returns [ids, classes, types] specificity when `compound` matches `classes`, else null. */
function matchCompound(compound: string, classes: string[]): [number, number, number] | null {
  let rest = compound.trim();
  let spec: [number, number, number] = [0, 0, 0];
  if (rest.startsWith("*")) rest = rest.slice(1);
  while (rest.length) {
    let m = /^\.((?:\\.|[\w-])+)/.exec(rest);
    if (m) { if (!classes.includes(unescape(m[1]))) return null; spec[1] += 1; rest = rest.slice(m[0].length); continue; }
    m = /^:not\(\.((?:\\.|[\w-])+)\)/.exec(rest);
    if (m) { if (classes.includes(unescape(m[1]))) return null; spec[1] += 1; rest = rest.slice(m[0].length); continue; }
    return null; // unsupported token (pseudo-class, attribute, element type): not ours
  }
  return spec;
}

function matchSelector(selector: string, el: El): [number, number, number] | null {
  let best: [number, number, number] | null = null;
  for (const part of selector.split(/,(?![^(]*\))/)) {
    const pieces = part.split(">").map(s => s.trim());
    let spec: [number, number, number] | null = null;
    if (pieces.length === 1) spec = matchCompound(pieces[0], el.classes);
    else if (pieces.length === 2 && el.parent) {
      const p = matchCompound(pieces[0], el.parent);
      const c = matchCompound(pieces[1], el.classes);
      spec = p && c ? [p[0] + c[0], p[1] + c[1], p[2] + c[2]] : null;
    }
    if (spec && (!best || compareSpec(spec, best) > 0)) best = spec;
  }
  return best;
}
const compareSpec = (a: number[], b: number[]) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2];

function computed(css: string, el: El, property: string): string | undefined {
  const { rules, layerOrder } = parseRules(css);
  const rank = (layer: string | null) => (layer === null ? Number.MAX_SAFE_INTEGER : layerOrder.indexOf(layer.split(".")[0]));
  let winner: { rank: number; spec: [number, number, number]; order: number; value: string } | undefined;
  for (const rule of rules) {
    if (rule.conditional || !rule.decls.has(property)) continue;
    const spec = matchSelector(rule.selector, el);
    if (!spec) continue;
    const candidate = { rank: rank(rule.layer), spec, order: rule.order, value: rule.decls.get(property)! };
    if (!winner || candidate.rank - winner.rank > 0 || (candidate.rank === winner.rank && (compareSpec(spec, winner.spec) > 0 || (compareSpec(spec, winner.spec) === 0 && candidate.order > winner.order)))) winner = candidate;
  }
  return winner?.value;
}

const SHELL = ["mk-shell", "min-h-screen", "text-slate-100"];
const HEADER: El = { classes: ["mk-header", "sticky", "top-0", "z-40", "border-b", "px-4", "py-3"], parent: SHELL };
const ROW: El = { classes: ["flex", "flex-col"], parent: SHELL };
const ENGINE_OVERLAY: El = { classes: ["fixed", "inset-0", "z-50", "flex", "items-center", "justify-center", "bg-slate-950/80", "p-4"], parent: SHELL };
const STRIP: El = { classes: ["mk-telemetry"], parent: SHELL };
const GRID: El = { classes: ["mk-grid-overlay"], parent: SHELL };
const candidates = [...new Set([...SHELL, ...HEADER.classes, ...ROW.classes, ...ENGINE_OVERLAY.classes])];
const indexCss = readFileSync(resolve(SRC, "index.css"), "utf8");

test("compiled shell CSS: header sticky z-40, engine overlay fixed z-50, row not a stacking context, strip z-0", async () => {
  const css = await compiledShellCss(indexCss, candidates);
  const layers = parseRules(css).layerOrder;
  assert.deepEqual(layers.filter(l => ["theme", "base", "components", "utilities"].includes(l)), ["theme", "base", "components", "utilities"]);
  assert.equal(computed(css, HEADER, "position"), "sticky");
  assert.equal(computed(css, HEADER, "z-index"), "40");
  assert.equal(computed(css, ENGINE_OVERLAY, "position"), "fixed");
  assert.equal(computed(css, ENGINE_OVERLAY, "z-index"), "50");
  assert.equal(computed(css, ROW, "position"), "relative", "positioned, so it paints above the fixed decorative layers");
  assert.equal(computed(css, ROW, "z-index"), undefined, "z-index auto: module dialogs inside it can rise above the z-40 header");
  assert.equal(computed(css, STRIP, "position"), "relative");
  assert.equal(computed(css, STRIP, "z-index"), "0");
  assert.equal(computed(css, GRID, "position"), "fixed", "the decorative layers are excluded from the shell rule");
});

test("negative control: the previous unlayered rule makes the header relative and the overlay in-flow", async () => {
  const layered = /@layer components \{\s*\.mk-shell > \*:not\(\.mk-grid-overlay\):not\(\.mk-scanline\) \{\s*position: relative;\s*\}\s*\}/;
  assert.match(indexCss, layered);
  const previous = indexCss.replace(layered, ".mk-shell > *:not(.mk-grid-overlay):not(.mk-scanline) {\n  position: relative;\n  z-index: 1;\n}");
  const css = await compiledShellCss(previous, candidates);
  assert.equal(computed(css, HEADER, "position"), "relative");
  assert.equal(computed(css, ENGINE_OVERLAY, "position"), "relative");
  assert.equal(computed(css, ROW, "z-index"), "1");
});
