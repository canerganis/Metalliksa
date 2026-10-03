# Metalliksa Design System — Master

> Page files in `design-system/metalliksa/pages/` override this file for their page only.
> Source of truth for values: `src/index.css` (base palette) and `src/styles/tokens.css` (token layer).
> Contrast gate: `tests/design-tokens-contrast.test.ts`.

**Identity:** dark mission-control research workstation (Phase 9, DESIGN-9 sections 1-2).
**Rule zero:** motion and light decorate real state. They never replace, delay or de-emphasize an evidence label.

---

## 1. Principles

1. **Honest telemetry.** Every number on screen traces to an API response or a user input. No placeholder values, ticking clocks or fake progress. Missing data reads "unavailable".
2. **Calm density.** Dense information on a quiet dark field; hierarchy comes from type and spacing before color.
3. **Light = energy.** Glow and bright accents mark active, focused or energised state only (laser, live engine, current selection). Idle chrome stays matte.
4. **Evidence first.** Labels such as `unavailable`, `inconclusive` and `unvalidated` always render at full text contrast. No opacity, blur, glow, truncation or reduced size may hide them.

## 2. Air-gap and fonts

- No external URLs in CSS, HTML or docs snippets. No Google Fonts or CDN imports.
- Fonts are self-hosted with `@fontsource/fira-sans` and `@fontsource/fira-code`, **latin + latin-ext subsets only**, imported in `src/main.tsx`.
- `--mk-font-sans`: `"Fira Sans", ui-sans-serif, system-ui, sans-serif`
- `--mk-font-mono`: `"Fira Code", ui-monospace, SFMono-Regular, monospace`

## 3. Color tokens

### Base palette (`src/index.css`)

| Token | Value | Role |
|---|---|---|
| `--mk-bg` | `#020409` | Page background |
| `--mk-surface` | `#06111c` | Panels |
| `--mk-surface-raised` | `#0a1827` | Cards, popovers |
| `--mk-border` | `rgba(34,211,238,.18)` | Decorative separators |
| `--mk-border-bright` | `rgba(34,211,238,.54)` | Hover borders |
| `--mk-ice` | `#67e8f9` | Primary accent, focus |
| `--mk-plasma` | `#38bdf8` | Secondary accent, toolpaths |
| `--mk-amber` | `#f5b84b` | Energy, warnings, air-gap notice |
| `--mk-text` | `#f4fdff` | Primary text |
| `--mk-muted` | `#c7d7e2` | Secondary text |

### Token layer (`src/styles/tokens.css`)

| Token | Value | Role |
|---|---|---|
| `--mk-text-strong` | `#f0f7fb` | Emphasised body text |
| `--mk-text-soft` | `#e2edf5` | Body text |
| `--mk-text-subtle` | `#c3d0dc` | Secondary text |
| `--mk-text-dim` | `#a8b7c7` | Captions |
| `--mk-text-faint` | `#94a3b8` | Lowest text tier (still AA) |
| `--mk-text-cyan-soft` / `-faint` | `rgba(207,250,254,.8 / .74)` | Cyan captions |
| `--mk-line-subtle` / `-neutral` / `-divider` | translucent | Decorative lines (no contrast requirement) |
| `--mk-fill-panel` / `-deep` | translucent | Panel fills over `--mk-bg` |
| `--mk-border-strong` | `#4f87a8` | Component boundaries that must be perceivable (≥3:1) |

### Status and evidence

| Token | Value | Meaning |
|---|---|---|
| `--mk-signal-ok` | `#6ee7b7` | Check passed / online |
| `--mk-signal-warn` | `#f5b84b` | Degraded, limited mode, air-gap notice (not an error) |
| `--mk-signal-fail` | `#fb7185` | Failed, error, timed out |
| `--mk-evidence-unvalidated` | `#f0abfc` | Not experimentally validated, preview scope |

Status color is never the only signal: always pair it with a text label and, where useful, an icon.
`unavailable` and `inconclusive` use the text ramp at `--mk-text-subtle` or stronger, never a faded style.

### Contrast rules

- Text tokens (`--mk-text*`, `--mk-muted`, `--mk-signal-*`, `--mk-evidence-*`, `--mk-ice`, `--mk-plasma`, `--mk-amber`): **≥4.5:1** on `--mk-bg`, `--mk-surface`, `--mk-surface-raised`, `--mk-glass-bg`, `--mk-fill-panel`, `--mk-fill-deep`.
- UI tokens (`--mk-border-strong`, `--mk-focus-color`): **≥3:1** on the same backgrounds.
- Enforced by `npx tsx --test tests/design-tokens-contrast.test.ts`. Any new text or UI color token must be added under a covered name.

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

- Numbers and units: `--mk-font-mono` with `font-variant-numeric: tabular-nums`.
- Uppercase tracking: `--mk-tracking-caps` (0.12em), never above `--mk-tracking-caps-max` (0.18em).
- Headings: line-height 1.18; body: 1.45.

## 5. Spacing

`--mk-space-1..7` = 4 / 8 / 12 / 16 / 24 / 32 / 48 px. Use these steps only.

## 6. Glass, glow, elevation

- **Glass:** `--mk-glass-bg` `rgba(6,17,28,.72)` + `blur(var(--mk-glass-blur))` (12px). Shell chrome only (header, sidebar, palette). Never behind charts, plots or data marks.
- **Glow:** `--mk-glow-sm`, `--mk-glow-md`. Active and focus states only; never on data marks or evidence labels.
- **Elevation:** border + shadow, no stacked blur.

| Token | Use |
|---|---|
| `--mk-elev-0` | Flat, inline content |
| `--mk-elev-1` | Cards |
| `--mk-elev-2` | Popovers, menus |
| `--mk-elev-3` | Modals |

## 7. Motion

| Token | Value | Use |
|---|---|---|
| `--mk-dur-fast` | 120ms | Hover, press |
| `--mk-dur-base` | 200ms | Panels, toggles |
| `--mk-dur-slow` | 420ms | Enter/exit of large surfaces |
| `--mk-ease-out` | `cubic-bezier(.16,1,.3,1)` | Entering |
| `--mk-ease-inout` | `cubic-bezier(.65,0,.35,1)` | Moving, looping sweeps |

- `prefers-reduced-motion: reduce` collapses animation and transition (global rule in `src/index.css`).
- Motion never gates content: a label is readable before any animation finishes.
- No percent tweens for progress; progress comes only from backend steps.

## 8. Focus

- `outline: var(--mk-focus-width) solid var(--mk-focus-color)` (2px ice), `outline-offset: var(--mk-focus-offset)` (3px), optional halo `box-shadow: var(--mk-focus-halo)` (4px `rgba(103,232,249,.25)`).
- The focus ring **never animates or transitions**. Do not include `outline` or the halo in a `transition` list.
- Focus is always visible on `:focus-visible` for buttons, links, inputs, selects, textareas and summaries.

## 9. Shell and components (summary)

Shell, boot, placeholders and viz palette are owned by later Phase 9 packages (DESIGN-9 sections 3-7). Until they land, components keep the existing classes (`aero-panel`, `mk-header`, `mk-sidebar`, `mk-status`, `mk-scope-badge`, `mk-hud-chip`) and adopt tokens incrementally without visual change.

## 10. QA gates

- [ ] Contrast test passes (≥4.5:1 text, ≥3:1 UI).
- [ ] No external URLs; fonts only from `@fontsource` latin + latin-ext.
- [ ] Evidence labels visible at full contrast in every screenshot.
- [ ] Focus ring visible and static on keyboard navigation.
- [ ] Reduced motion respected.
- [ ] Viewports 375×812, 768×1024, 1440×900; no horizontal scroll on mobile.
- [ ] No emojis as icons; use `lucide-react`.
