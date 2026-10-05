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
const NEW_TSX = ["src/components/BootSequence.tsx", "src/components/BootHero.tsx", "src/components/TelemetryStrip.tsx", "src/components/SilentBoundary.tsx"];
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

test("boot rows are a plain list with a live k/N line and a persistent announcer, the overlay reuses AccessibleModal, the hero stays lazy", () => {
  const boot = read("src/components/BootSequence.tsx");
  assert.equal((boot.match(/aria-live=/g) ?? []).length, 2, "the overlay k/N line and the persistent announcer only");
  assert.match(boot, /<p id="boot-count" className="mk-boot-count" role="status" aria-live=\{bootCountLive\(snap\.phase\)\}>/);
  assert.match(boot, /<p className="mk-sr-only" role="status" aria-live="polite">\s*\{bootAnnouncement\(snap, open\)\}\s*<\/p>\s*\{open && \(/,
    "announcer is a stable first child; only the overlay is conditional (a remounted live region would not announce)");
  assert.doesNotMatch(boot, /if \(!open\) return/);
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

/** Lines of `source` (comments removed) that claim validation or readiness. */
function claimHits(source: string): string[] {
  const claim = /\b(validated|ready|certified|qualified)\b/i;
  // Whole source minus comments: covers "..." '...' `...` literals and JSX text nodes alike.
  const code = source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
  return code.split(/\r?\n/).filter((line) => claim.test(line)).map((line) => line.trim());
}

test("the claim scan itself: finds every quote style and JSX text, ignores comments", () => {
  const sample = [
    "// the engine is ready (line comment, ignored)",
    "/* validated in a block comment, ignored */",
    "const a = 'Engine validated';",
    'const b = "certified";',
    "const c = `qualified ${x}`;",
    "return <p>Engine ready</p>;",
    "{/* ready in a JSX comment, ignored */}",
    'const url = "http://x"; // ready after a URL string, ignored',
  ].join("\n");
  assert.deepEqual(claimHits(sample), [
    "const a = 'Engine validated';",
    'const b = "certified";',
    "const c = `qualified ${x}`;",
    "return <p>Engine ready</p>;",
  ]);
});

test("boot and telemetry text never claims validation or readiness (strings in any quote style and JSX text)", () => {
  for (const file of [...NEW_TSX, ...NEW_TS]) assert.deepEqual(claimHits(read(file)), [], `${file} claims validation/readiness`);
});

test("the boot artwork is always captioned illustrative, independent of WebGL; the hero respects DPR, visibility, motion and disposal budgets", () => {
  // Review B1: the caption lives on the picture (FoundryStage), outside its masked/animated layer, so a
  // static start, missing WebGL or a lazy-loading spark layer can never show the picture without it.
  const stage = read("src/components/FoundryStage.tsx");
  assert.match(stage, /export const FOUNDRY_CAPTION = 'Illustrative — not a simulation result';/);
  assert.match(stage, /caption = FOUNDRY_CAPTION/, "the caption has a default, so no host can forget it");
  const pictureStart = stage.indexOf("<div className={`mk-foundry$");
  const captionAt = stage.indexOf('<p className="mk-foundry-caption">');
  assert.ok(pictureStart > 0 && captionAt > pictureStart, "caption follows the picture layer");
  assert.match(stage.slice(pictureStart, captionAt), /<\/div>\s*<\/div>\s*$/, "caption is a sibling of the picture layer, not inside it");
  const boot = read("src/components/BootSequence.tsx");
  assert.match(boot, /<FoundryStage className="mk-boot-art"/, "boot shows the stage");
  assert.doesNotMatch(boot, /<FoundryStage[^>]*caption=/, "boot never overrides the caption");
  const foundryCss = read("src/styles/foundry.css").replace(/\/\*[\s\S]*?\*\//g, "");
  const captionRule = foundryCss.match(/\.mk-foundry-caption \{([^}]*)\}/)?.[1] ?? "";
  assert.match(captionRule, /background: #ffffff;/, "opaque pill");
  assert.doesNotMatch(captionRule, /opacity|animation|filter/, "never faded or animated");
  for (const file of ["src/styles/atrium.css", "src/styles/boot.css", "src/styles/foundry.css"]) {
    assert.doesNotMatch(read(file), /\.mk-foundry-caption[^{]*\{[^}]*(opacity|mask|animation)/, `${file} must not fade the caption`);
    assert.doesNotMatch(read(file), /\.mk-foundry-host[^{]*\{[^}]*(opacity|mask-image|animation)/, `${file}: the host (caption parent) is never masked or faded`);
  }
  // Module mastheads carry no artwork (the reticle is pure ornament), so there is no uncaptioned picture.
  assert.doesNotMatch(read("src/index.css"), /metalliksa-foundry-art/);
  const hero = read("src/components/BootHero.tsx");
  assert.match(hero, /prefers-reduced-motion: reduce/, "a reduced-motion change stops the sparks");
  assert.match(hero, /Math\.min\(window\.devicePixelRatio \|\| 1, 1\.5\)/);
  assert.match(hero, /visibilitychange/);
  for (const call of ["renderer.dispose()", "renderer.forceContextLoss()", "observer?.disconnect()", "cancelAnimationFrame(raf)"]) {
    assert.ok(hero.includes(call), `missing ${call}`);
  }
});
