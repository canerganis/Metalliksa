import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";

// Review Sol S8: the token gate (design-tokens-contrast) only reads --mk-* tokens. Most of the UI colour
// comes from src/styles/theme-porcelain.css, which re-points the Tailwind ramps the 24 module bodies use.
// These are focused regressions for that transformation, not a whole-UI certification.
const read = (p: string) => readFileSync(resolve(process.cwd(), p), "utf8");
const theme = read("src/styles/theme-porcelain.css").replace(/\/\*[\s\S]*?\*\//g, "");
const themeBlock = theme.slice(theme.indexOf("@theme {"), theme.indexOf("}", theme.indexOf("@theme {")));

type Rgb = [number, number, number];
function oklchToRgb(l: number, c: number, h: number): Rgb {
  const a = c * Math.cos((h * Math.PI) / 180), b = c * Math.sin((h * Math.PI) / 180);
  const l_ = l + 0.3963377774 * a + 0.2158037573 * b, m_ = l - 0.1055613458 * a - 0.0638541728 * b, s_ = l - 0.0894841775 * a - 1.291485548 * b;
  const [L, M, S] = [l_ ** 3, m_ ** 3, s_ ** 3];
  const lin = [4.0767416621 * L - 3.3077115913 * M + 0.2309699292 * S, -1.2684380046 * L + 2.6097574011 * M - 0.3413193965 * S, -0.0041960863 * L - 0.7034186147 * M + 1.707614701 * S];
  return lin.map((x) => { const v = Math.min(1, Math.max(0, x)); return Math.round((v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055) * 255); }) as Rgb;
}
const hex = (h: string): Rgb => [0, 2, 4].map((i) => parseInt(h.replace("#", "").slice(i, i + 2), 16)) as Rgb;
const luminance = ([r, g, b]: Rgb) => { const f = (c: number) => { const s = c / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
const contrast = (x: Rgb, y: Rgb) => { const [hi, lo] = [luminance(x), luminance(y)].sort((p, q) => q - p); return (hi + 0.05) / (lo + 0.05); };
const over = (fg: Rgb, alpha: number, bg: Rgb): Rgb => fg.map((c, i) => Math.round(c * alpha + bg[i] * (1 - alpha))) as Rgb;

function ramp(hue: string, step: string): Rgb {
  const m = new RegExp(`--color-${hue}-${step}: oklch\\(([\\d.]+)% ([\\d.]+) ([\\d.]+)\\);`).exec(themeBlock);
  assert.ok(m, `--color-${hue}-${step} missing from the porcelain @theme`);
  return oklchToRgb(Number(m[1]) / 100, Number(m[2]), Number(m[3]));
}

const HUES = ["sky", "cyan", "blue", "indigo", "violet", "purple", "emerald", "green", "teal", "lime", "amber", "yellow", "orange", "red", "rose", "pink", "fuchsia"];
const DARKEST_LIGHT_SURFACE = hex("#e6e8ec");
const PORCELAIN_INK_ON_BUTTON = hex("#f3f5f7"); // text-slate-950 after inversion
const WHITE: Rgb = [255, 255, 255];

test("text steps 200-400 of every inverted chromatic ramp reach 4.5:1 on the darkest light surface", () => {
  const failures: string[] = [];
  for (const hue of HUES) for (const step of ["200", "300", "400"]) {
    const ratio = contrast(ramp(hue, step), DARKEST_LIGHT_SURFACE);
    if (ratio < 4.5) failures.push(`${hue}-${step}: ${ratio.toFixed(2)}`);
  }
  assert.deepEqual(failures, []);
});

test("filled buttons (bg 500/600) carry light labels at >= 4.5:1, both slate-950 and the restored text-white (review S4)", () => {
  const failures: string[] = [];
  for (const hue of HUES) for (const step of ["500", "600"]) {
    const bg = ramp(hue, step);
    for (const [name, fg] of [["slate-950", PORCELAIN_INK_ON_BUTTON], ["white", WHITE]] as const) {
      const ratio = contrast(fg, bg);
      if (ratio < 4.5) failures.push(`${name} on ${hue}-${step}: ${ratio.toFixed(2)}`);
    }
  }
  assert.deepEqual(failures, []);
  assert.match(theme, /:is\([^)]*\.bg-sky-500[^)]*\)\.text-white \{ color: #ffffff; \}/, "a dark-era text-white stays white on filled buttons");
});

test("tinted chips: step 300 text on a 20 % step-500 tint over white reaches 4.5:1 (review S4 chips)", () => {
  const failures: string[] = [];
  for (const hue of HUES) {
    const chip = over(ramp(hue, "500"), 0.2, WHITE);
    const ratio = contrast(ramp(hue, "300"), chip);
    if (ratio < 4.5) failures.push(`${hue}: ${ratio.toFixed(2)}`);
  }
  assert.deepEqual(failures, []);
});

test("translucent coloured text is made opaque: the 9 px amber-500/80 kinematics warning reaches 4.5:1 (review Sol S1)", () => {
  assert.match(theme, /\.text-amber-500\\\/80 \{ color: var\(--color-amber-500\); \}/);
  assert.ok(contrast(ramp("amber", "500"), WHITE) >= 4.5, "amber-500 on white");
  // Every alpha text class used in the sources has an opaque override.
  const used = new Set<string>();
  for (const file of ["src/components/3d-distortion-lab/IndustrialLPBFDecisionLab.tsx"]) {
    for (const m of read(file).matchAll(/\btext-([a-z]+-\d+)\/(\d+)/g)) used.add(`${m[1]}/${m[2]}`);
  }
  for (const cls of used) assert.ok(theme.includes(`.text-${cls.replace("/", "\\/")} {`), `no opaque override for text-${cls}`);
});

test("dark: variants never activate in the light-only app, so white-card islands cannot turn dark (review Sol S2)", () => {
  assert.match(read("src/index.css"), /@custom-variant dark \(&:where\(\.dark, \.dark \*\)\);/);
  const sources = ["src/App.tsx", "index.html"].map(read).join("\n");
  assert.doesNotMatch(sources, /class(Name)?="[^"]*\bdark\b/, "nothing sets the .dark scope");
});
