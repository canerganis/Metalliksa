# Metalliksa Design System — Master

> Page files in `design-system/metalliksa/pages/` override this file for their page only.
> Source of truth for values: `src/index.css` (base palette), `src/styles/tokens.css` (token layer) and
> `src/styles/theme-porcelain.css` (Tailwind ramp mapping).
> Contrast gate: `tests/design-tokens-contrast.test.ts`.

**Identity:** Porcelain. A light, sci-fi luxury instrument: white titanium and graphite surfaces, one cobalt accent for interaction, and an incandescent laser line used only as ornament.
**Rule zero:** motion and light decorate real state. They never replace, delay or de-emphasize an evidence label.

---

## 1. Principles

1. **Honest telemetry.** Every number on screen traces to an API response, the bundled registry or a user input. No placeholder values, ticking clocks or fake progress. Missing data reads "unavailable".
2. **Calm luxury.** Porcelain surfaces, hairlines and generous space; hierarchy comes from type weight and spacing before colour.
3. **The laser is ornament.** `--mk-laser` marks the brand (logo, filament, active nav spot, boot emblem). It is never a status colour and never text.
4. **Evidence first.** Labels such as `unavailable`, `inconclusive` and `unvalidated` always render at full text contrast. No opacity, blur, glow, truncation or reduced size may hide them; entrance animations move content (transform) and never fade labels in.

## 2. Air-gap and fonts

- No external URLs in CSS, HTML or docs snippets. No Google Fonts or CDN imports.
- Fonts are self-hosted with `@fontsource/fira-sans` (300-800) and `@fontsource/fira-code`, **latin + latin-ext subsets only**, imported in `src/main.tsx`.
- Display titles use Fira Sans 300; HUD labels use Fira Code uppercase.

## 3. Color tokens

### Base palette (`src/index.css`)

| Token | Value | Role |
|---|---|---|
| `--mk-bg` | `#eceef1` | Page (pearl) |
| `--mk-surface` | `#f5f6f8` | Panels |
| `--mk-surface-raised` | `#ffffff` | Cards, popovers |
| `--mk-border` | `rgba(17,22,31,.10)` | Hairlines |
| `--mk-border-bright` | `rgba(17,22,31,.26)` | Pill and input borders |
| `--mk-ice` | `#2346b0` | Cobalt accent, kickers, links |
| `--mk-plasma` | `#0b5f9a` | Secondary accent |
| `--mk-amber` | `#8f4300` | Limitation text, warm notices |
| `--mk-text` | `#0e1116` | Primary text (graphite) |
| `--mk-muted` | `#444b55` | Secondary text |

### Token layer (`src/styles/tokens.css`)

| Token | Value | Role |
|---|---|---|
| `--mk-text-strong` … `--mk-text-faint` | `#0e1116` → `#545b66` | Graphite text ramp (all AA) |
| `--mk-paper`, `--mk-paper-2`, `--mk-well` | `#fff`, `#f7f8fa`, `#f1f3f6` | Card, raised inner, inset well |
| `--mk-hover`, `--mk-hover-2`, `--mk-hair`, `--mk-hair-2` | light greys | Hover fills and hairlines |
| `--mk-chart-axis` | `#8a919c` | SVG axis strokes |
| `--mk-laser`, `--mk-laser-soft` | `#ff5b1f`, `#ffb27a` | Ornament only |
| `--mk-border-strong` | `#78808b` | Component boundaries (≥3:1) |
| `--mk-focus-color` | `#2346b0` | Focus ring |

### Status and evidence

| Token | Value | Meaning |
|---|---|---|
| `--mk-signal-ok` | `#0a6b4b` | Check passed / online |
| `--mk-signal-warn` | `#8a4600` | Degraded, limited mode, air-gap notice (not an error) |
| `--mk-signal-fail` | `#b4232f` | Failed, unavailable, timed out |
| `--mk-evidence-unvalidated` | `#8b1d9c` | Not experimentally validated, preview scope, illustrative |

Status colour is never the only signal: always pair it with a text label and, where useful, a glyph.

### Module palette mapping (`src/styles/theme-porcelain.css`)

Module bodies were authored for a dark UI. The Tailwind ramps are re-pointed instead of editing modules:
- neutral and chromatic ramps are inverted; text steps 200-400 are pushed until they reach 4.6:1 on `#e6e8ec`, step 500 reaches 3:1;
- dark literal surfaces (`bg-[#090e18]` and friends) map to paper / well / hover tokens; dark SVG presentation colours used by D3 and Recharts map to light tokens;
- a solid `bg-white` card and the three light-authored labs (GPU solver, DEM compaction, tomography) get Tailwind's own ramps back inside them;
- canvas and WebGL views keep their own dark backgrounds (instrument screens).

### Contrast rules

- Text tokens: **≥4.5:1** on `--mk-bg`, `--mk-surface`, `--mk-surface-raised`, `--mk-glass-bg`, `--mk-fill-panel`, `--mk-fill-deep`.
- UI tokens (`--mk-border-strong`, `--mk-focus-color`): **≥3:1** on the same backgrounds.
- Enforced by `npx tsx --test tests/design-tokens-contrast.test.ts` and `tests/boot-telemetry-a11y.test.ts`.

## 4. Typography

| Token | Size | Use |
|---|---|---|
| `--mk-fs-2xs` | 11px | Uppercase HUD labels |
| `--mk-fs-xs` | 12px | Captions, table meta |
| `--mk-fs-sm` | 14px | Dense UI body |
| `--mk-fs-md` | 16px | Body, inputs |
| `--mk-fs-lg` | 20px | Section titles |
| `--mk-fs-xl` | 28px | Page titles |
| `--mk-fs-2xl` | 40px | Boot / hero only |

- Module titles: `clamp(1.7rem, …, 2.5rem)`, weight 300. Atrium wordmark: up to 5.4rem, weight 300, tracking 0.16em.
- Numbers and units: `--mk-font-mono` with `tabular-nums`.
- Tracking: body 0; HUD labels 0.16–0.24em; wordmarks 0.36–0.52em (decorative display only).

## 5. Spacing

`--mk-space-1..7` = 4 / 8 / 12 / 16 / 24 / 32 / 48 px.

## 6. Glass, ornament, elevation

- **Glass:** `--mk-glass-bg` `rgba(250,251,252,.76)` + blur on shell chrome only (header, sidebar, telemetry, plates). Never behind charts or data marks.
- **HUD brackets:** `.mk-hud` draws four corner marks as background layers (no DOM). Used on the dossier, boot frame and atrium plates.
- **Elevation:** hairline + soft porcelain shadow (`--mk-elev-1..3`), no stacked blur.

## 7. Motion

| Token | Value | Use |
|---|---|---|
| `--mk-dur-fast` | 120ms | Hover, press |
| `--mk-dur-base` | 200ms | Panels, toggles |
| `--mk-dur-slow` | 420ms | Enter/exit of large surfaces, boot fade |
| `--mk-ease-out` | `cubic-bezier(.16,1,.3,1)` | Entering |
| `--mk-ease-inout` | `cubic-bezier(.65,0,.35,1)` | Sweeps, loops |

- `prefers-reduced-motion: reduce` collapses animation and transition (global rule) and the atrium/boot render their static final drawings.
- Entrances use transform only; no label is faded in.
- Progress is a discrete k/N from backend checks, never a percent tween. The boot intro may hold the overlay up to 2.8 s on the first animated start in a tab; the checks and their labels are on screen from the first frame.

## 8. Focus

- `outline: 2px solid var(--mk-focus-color)` (cobalt), `outline-offset: 3px`, optional halo `--mk-focus-halo`.
- The focus ring never animates or transitions.

## 9. Brand mark

A world built additively: a globe grown bottom-up from graphite layers, meridians cut through the finished layers, the unbuilt cap drawn as a hairline graticule, and a laser from above finishing the current layer. Same drawing in the header (CSS, `.mk-brand-mark`), the boot emblem (SVG, animated) and `public/icon.svg`.

## 10. Shell (summary)

Frosted header with a laser filament; sidebar with numbered workspace headings (CSS counter), a white active plate with a laser spot and a tick rail; module masthead (kicker, light display title, maturity and evidence badges, reticle ornament); scientific-context dossier; atrium start page (`#/home`) with workspace plates; telemetry footer.

## 11. QA gates

- [ ] Contrast tests pass (≥4.5:1 text, ≥3:1 UI).
- [ ] No external URLs; fonts only from `@fontsource` latin + latin-ext.
- [ ] Evidence labels visible at full contrast in every screenshot.
- [ ] Focus ring visible and static on keyboard navigation.
- [ ] Reduced motion respected.
- [ ] Viewports 375×812, 768×1024, 1440×900; no horizontal scroll on mobile.
- [ ] No emojis as icons; use `lucide-react`.
