import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";

// Static contrast and a11y guard for the boot screen and telemetry strip (Phase 9 slice 1).
// Same pattern as tests/design-tokens-contrast.test.ts: values are read from the CSS sources,
// so a palette or stylesheet edit that breaks AA, adds a literal color or an external URL fails here.
const read = (p: string) => readFileSync(resolve(process.cwd(), p), "utf8");
const TOKEN_FILES = ["src/index.css", "src/styles/tokens.css"];
const BOOT_CSS = "src/styles/boot.css";
const NEW_TSX = ["src/components/BootSequence.tsx", "src/components/BootHero.tsx", "src/components/TelemetryStrip.tsx"];
const NEW_TS = ["src/utils/bootSequence.ts", "src/services/bootSteps.ts"];

// Surfaces the boot screen and strip may paint on; all are covered by the token contrast gate.
const ALLOWED_BACKGROUNDS = ["--mk-bg", "--mk-surface", "--mk-surface-raised", "--mk-glass-bg", "--mk-fill-panel", "--mk-fill-deep"];
// Decorative separators (no contrast requirement, never the only boundary of a control).
const DECORATIVE_LINES = ["--mk-line-subtle", "--mk-border"];
// Perceivable component boundaries need 3:1.
const UI_BOUNDARIES = ["--mk-border-strong", "--mk-focus-color"];

type Rgba = [number, number, number, number];

function tokens(): Map<string, string> {
  const map = new Map<string, string>();
  for (const file of TOKEN_FILES) {
    const css = read(file).replace(/\/\*[\s\S]*?\*\//g, "");
    for (const block of css.matchAll(/:root\s*\{([^}]*)\}/g)) {
      for (const decl of block[1].matchAll(/(--mk-[\w-]+)\s*:\s*([^;]+);/g)) map.set(decl[1], decl[2].trim());
    }
  }
  return map;
}

function parse(value: string): Rgba {
  const hex = /^#([0-9a-f]{6})$/i.exec(value);
  if (hex) return [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16)).concat(1) as Rgba;
  const rgb = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i.exec(value);
  assert.ok(rgb, `unparseable color ${value}`);
  return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3]), rgb[4] === undefined ? 1 : Number(rgb[4])];
}

function color(map: Map<string, string>, name: string, depth = 0): Rgba {
  const raw = map.get(name);
  assert.ok(raw !== undefined && depth < 10, `token ${name} is not defined`);
  const ref = /^var\((--mk-[\w-]+)\)$/.exec(raw);
  return ref ? color(map, ref[1], depth + 1) : parse(raw);
}

const over = (fg: Rgba, bg: Rgba): Rgba => [0, 1, 2].map((i) => fg[i] * fg[3] + bg[i] * (1 - fg[3])).concat(1) as Rgba;
function luminance([r, g, b]: Rgba): number {
  const lin = (c: number) => (c / 255 <= 0.03928 ? c / 255 / 12.92 : ((c / 255 + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function contrast(a: Rgba, b: Rgba): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const css = read(BOOT_CSS).replace(/\/\*[\s\S]*?\*\//g, "");
const declTokens = (prop: RegExp) =>
  [...css.matchAll(/([\w-]+)\s*:\s*([^;{}]+);/g)]
    .filter((m) => prop.test(m[1]))
    .flatMap((m) => [...m[2].matchAll(/var\((--mk-[\w-]+)\)/g)].map((v) => v[1]));

test("boot.css uses token colors only and no external resources", () => {
  assert.doesNotMatch(css, /#[0-9a-f]{3,8}\b/i, "literal hex color");
  assert.doesNotMatch(css, /\b(rgba?|hsla?)\(/i, "literal rgb/hsl color");
  assert.doesNotMatch(css, /url\(|@import|https?:\/\//i, "external resource");
  const defined = tokens();
  for (const ref of css.matchAll(/var\((--mk-[\w-]+)\)/g)) assert.ok(defined.has(ref[1]), `${ref[1]} is not defined in the token sources`);
});

test("every text color in boot.css reaches 4.5:1 on every surface it can sit on", () => {
  const map = tokens();
  const page = color(map, "--mk-bg");
  const backgrounds = [...new Set(declTokens(/^background(-color)?$/))];
  assert.ok(backgrounds.length >= 3, "expected overlay, panel and strip surfaces");
  for (const bg of backgrounds) assert.ok(ALLOWED_BACKGROUNDS.includes(bg), `${bg} is not a covered surface token`);
  const texts = [...new Set(declTokens(/^color$/))];
  assert.ok(texts.length >= 8, `expected the boot/telemetry text tokens, found ${texts.length}`);
  const failures: string[] = [];
  for (const bgName of backgrounds) {
    const bg = over(color(map, bgName), page);
    for (const fg of texts) {
      const ratio = contrast(over(color(map, fg), bg), bg);
      if (ratio < 4.5) failures.push(`${fg} on ${bgName}: ${ratio.toFixed(2)}`);
    }
  }
  assert.deepEqual(failures, []);
});

test("borders and focus ring: component boundaries reach 3:1, other lines are decorative tokens", () => {
  const map = tokens();
  const page = color(map, "--mk-bg");
  const lines = [...new Set(declTokens(/^(border(-\w+)?|outline(-color)?)$/))].filter((n) => !/-(width|offset)$/.test(n));
  assert.ok(lines.includes("--mk-focus-color") && lines.includes("--mk-border-strong"));
  for (const name of lines) {
    if (DECORATIVE_LINES.includes(name)) continue;
    assert.ok(UI_BOUNDARIES.includes(name), `${name} is neither a decorative line nor a 3:1 boundary token`);
    for (const bgName of ALLOWED_BACKGROUNDS) {
      const bg = over(color(map, bgName), page);
      assert.ok(contrast(over(color(map, name), bg), bg) >= 3, `${name} on ${bgName} below 3:1`);
    }
  }
  assert.match(css, /\.mk-boot-skip\s*\{[^}]*border:\s*1px solid var\(--mk-border-strong\)/, "skip button boundary must be 3:1");
  assert.match(css, /:focus-visible\s*\{[^}]*outline:\s*var\(--mk-focus-width\) solid var\(--mk-focus-color\)/);
  for (const m of css.matchAll(/transition\s*:\s*([^;]+);/g)) assert.doesNotMatch(m[1], /outline|box-shadow|all/, "focus ring must never animate");
});

test("new boot and telemetry components use no literal or palette colors and no external URLs", () => {
  const palette = /\b(text|bg|border|ring|fill|stroke|from|via|to)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black)\b/;
  for (const file of [...NEW_TSX, ...NEW_TS]) {
    const text = read(file);
    assert.doesNotMatch(text, /#[0-9a-f]{6}\b|#[0-9a-f]{3}\b|\brgba?\(/i, `${file} has a literal color`);
    assert.doesNotMatch(text, palette, `${file} uses a Tailwind palette color instead of tokens`);
    assert.doesNotMatch(text, /https?:\/\//, `${file} references an external URL`);
  }
});

test("boot rows are a plain list with one live k/N region, the overlay reuses AccessibleModal, the hero stays lazy", () => {
  const boot = read("src/components/BootSequence.tsx");
  assert.equal((boot.match(/aria-live=/g) ?? []).length, 1, "exactly one live region");
  assert.match(boot, /<p id="boot-count" className="mk-boot-count" role="status" aria-live="polite">/);
  assert.match(boot, /<li key=\{row\.id\} className="mk-boot-row"/);
  assert.doesNotMatch(boot, /<li[^>]*role=/, "list items keep listitem semantics");
  assert.match(boot, /<AccessibleModal[\s\S]*labelledBy="boot-title"/);
  assert.ok(!boot.includes("fixed inset-0"), "use AccessibleModal, not a hand-made overlay");
  assert.match(boot, /lazy\(\(\) => import\("\.\/BootHero"\)\)/);
  for (const file of ["src/App.tsx", "src/components/BootSequence.tsx", "src/main.tsx"]) {
    assert.doesNotMatch(read(file), /^import [^;]*["']\.\/(components\/)?BootHero["']/m, `${file} imports BootHero eagerly`);
  }
  assert.doesNotMatch(boot, /%|percent/i, "progress is a discrete k/N count, never a percent");
});

test("boot and telemetry text never claims validation or readiness (strings in any quote style and JSX text)", () => {
  const claim = /\b(validated|ready|certified|qualified)\b/i;
  for (const file of [...NEW_TSX, ...NEW_TS]) {
    // Whole source minus comments: covers "..." '...' `...` literals and JSX text nodes alike.
    const code = read(file).replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1").replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
    const hits = code.split(/\r?\n/).filter((line) => claim.test(line));
    assert.deepEqual(hits, [], `${file} claims validation/readiness`);
  }
  // Self-check: the scan sees single-quoted strings and JSX text.
  assert.ok(claim.test("<p>Engine ready</p>") && claim.test("'validated'"));
});

test("hero is labelled illustrative and respects DPR, visibility and disposal budgets", () => {
  const hero = read("src/components/BootHero.tsx");
  assert.match(hero, /Illustrative — not a simulation result/);
  assert.match(hero, /Math\.min\(window\.devicePixelRatio \|\| 1, 1\.5\)/);
  assert.match(hero, /visibilitychange/);
  for (const call of ["renderer.dispose()", "renderer.forceContextLoss()", "observer?.disconnect()", "cancelAnimationFrame(raf)"]) {
    assert.ok(hero.includes(call), `missing ${call}`);
  }
});
