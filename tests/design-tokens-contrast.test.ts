import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";

// WCAG 2.x contrast gate for the Metalliksa design tokens.
// Tokens are read from the CSS sources, so a palette edit that breaks AA fails here.
const CSS_FILES = ["src/index.css", "src/styles/tokens.css"].map((p) => resolve(process.cwd(), p));

const TEXT_MIN = 4.5;
const UI_MIN = 3;

// Opaque page backgrounds and translucent fills composited over --mk-bg.
const BACKGROUNDS = ["--mk-bg", "--mk-surface", "--mk-surface-raised", "--mk-glass-bg", "--mk-fill-panel", "--mk-fill-deep"];

// Every token whose name matches these prefixes is used as text and must reach 4.5:1.
const TEXT_PATTERN = /^--mk-(text|muted|signal-|evidence-)/;
// Accent colors also appear as label text (scope badge, links), so they are text tokens too.
const TEXT_ACCENTS = ["--mk-ice", "--mk-plasma", "--mk-amber"];
// Non-text UI: component boundaries and the focus ring need 3:1.
const UI_TOKENS = ["--mk-border-strong", "--mk-focus-color"];

type Rgba = [number, number, number, number];

function readTokens(): Map<string, string> {
  const tokens = new Map<string, string>();
  for (const file of CSS_FILES) {
    const css = readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
    for (const block of css.matchAll(/:root\s*\{([^}]*)\}/g)) {
      for (const decl of block[1].matchAll(/(--mk-[\w-]+)\s*:\s*([^;]+);/g)) {
        tokens.set(decl[1], decl[2].trim());
      }
    }
  }
  return tokens;
}

function resolveValue(tokens: Map<string, string>, name: string, depth = 0): string {
  const raw = tokens.get(name);
  assert.ok(raw !== undefined, `token ${name} is not defined`);
  assert.ok(depth < 10, `token ${name} has a var() cycle`);
  const ref = /^var\((--mk-[\w-]+)\)$/.exec(raw);
  return ref ? resolveValue(tokens, ref[1], depth + 1) : raw;
}

function parseColor(value: string): Rgba | null {
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value);
  if (hex) {
    const h = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join("") : hex[1];
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).concat(1) as Rgba;
  }
  const rgb = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i.exec(value);
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3]), rgb[4] === undefined ? 1 : Number(rgb[4])];
  return null;
}

function color(tokens: Map<string, string>, name: string): Rgba {
  const parsed = parseColor(resolveValue(tokens, name));
  assert.ok(parsed, `token ${name} is not a parseable color`);
  return parsed;
}

function over(fg: Rgba, bg: Rgba): Rgba {
  const a = fg[3];
  return [0, 1, 2].map((i) => fg[i] * a + bg[i] * (1 - a)).concat(1) as Rgba;
}

function luminance([r, g, b]: Rgba): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(a: Rgba, b: Rgba): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function backgrounds(tokens: Map<string, string>): Array<[string, Rgba]> {
  const page = color(tokens, "--mk-bg");
  assert.equal(page[3], 1, "--mk-bg must be opaque");
  return BACKGROUNDS.map((name) => [name, over(color(tokens, name), page)]);
}

function textTokens(tokens: Map<string, string>): string[] {
  return [...tokens.keys()].filter((n) => TEXT_PATTERN.test(n)).concat(TEXT_ACCENTS);
}

test("contrast helper matches WCAG reference values", () => {
  assert.equal(contrast([0, 0, 0, 1], [255, 255, 255, 1]).toFixed(2), "21.00");
  assert.equal(contrast([119, 119, 119, 1], [255, 255, 255, 1]).toFixed(2), "4.48");
});

test("required status and evidence tokens are defined", () => {
  const tokens = readTokens();
  for (const name of ["--mk-signal-ok", "--mk-signal-warn", "--mk-signal-fail", "--mk-evidence-unvalidated"]) {
    assert.ok(tokens.has(name), `${name} missing`);
  }
});

test("every text token reaches 4.5:1 on every background token", () => {
  const tokens = readTokens();
  const failures: string[] = [];
  const fgs = textTokens(tokens);
  assert.ok(fgs.length >= 15, `expected the full text ramp, found ${fgs.length}`);
  for (const [bgName, bg] of backgrounds(tokens)) {
    for (const fgName of fgs) {
      const ratio = contrast(over(color(tokens, fgName), bg), bg);
      if (ratio < TEXT_MIN) failures.push(`${fgName} on ${bgName}: ${ratio.toFixed(2)}`);
    }
  }
  assert.deepEqual(failures, []);
});

test("UI boundary and focus tokens reach 3:1 on every background token", () => {
  const tokens = readTokens();
  const failures: string[] = [];
  for (const [bgName, bg] of backgrounds(tokens)) {
    for (const fgName of UI_TOKENS) {
      const ratio = contrast(over(color(tokens, fgName), bg), bg);
      if (ratio < UI_MIN) failures.push(`${fgName} on ${bgName}: ${ratio.toFixed(2)}`);
    }
  }
  assert.deepEqual(failures, []);
});

// Before/after proof for the slate overrides in src/index.css: each token must keep the
// literal the override used before tokenization, so the computed colors are unchanged.
const OVERRIDE_LITERALS: Record<string, [string, string]> = {
  ".text-slate-600": ["--mk-text-faint", "#94a3b8"],
  ".text-slate-500": ["--mk-text-dim", "#a8b7c7"],
  ".text-slate-400": ["--mk-text-subtle", "#c3d0dc"],
  ".text-slate-300": ["--mk-text-soft", "#e2edf5"],
  ".text-slate-200": ["--mk-text-strong", "#f0f7fb"],
  ".text-cyan-200\\/55": ["--mk-text-cyan-soft", "rgba(207, 250, 254, 0.8)"],
  ".text-cyan-200\\/45": ["--mk-text-cyan-faint", "rgba(207, 250, 254, 0.74)"],
  ".border-slate-800": ["--mk-line-subtle", "rgba(125, 211, 252, 0.24)"],
  ".border-slate-700": ["--mk-line-neutral", "rgba(148, 163, 184, 0.38)"],
  ".bg-slate-900\\/40": ["--mk-fill-panel", "rgba(15, 23, 42, 0.72)"],
  ".bg-slate-950\\/80": ["--mk-fill-deep", "rgba(2, 6, 14, 0.9)"],
  ".divide-slate-800": ["--mk-line-divider", "rgba(125, 211, 252, 0.22)"],
};

test("tokenized slate overrides keep their previous computed colors", () => {
  const tokens = readTokens();
  const indexCss = readFileSync(CSS_FILES[0], "utf8");
  for (const [selector, [token, literal]] of Object.entries(OVERRIDE_LITERALS)) {
    assert.deepEqual(color(tokens, token), parseColor(literal), `${token} drifted from ${literal}`);
    const line = indexCss.split(/\r?\n/).find((l) => l.startsWith(`${selector} `));
    assert.ok(line, `${selector} override missing`);
    assert.match(line, new RegExp(`var\\(${token}\\) !important`), `${selector} must use ${token}`);
  }
});

test("focus ring tokens are static (no motion tokens referenced)", () => {
  const tokens = readTokens();
  for (const name of ["--mk-focus-color", "--mk-focus-width", "--mk-focus-offset", "--mk-focus-halo"]) {
    assert.doesNotMatch(resolveValue(tokens, name), /ms|cubic-bezier|var\(--mk-(dur|ease)/);
  }
});
