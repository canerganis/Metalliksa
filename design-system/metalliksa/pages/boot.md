# Page: Boot sequence (stub)

> Overrides `../MASTER.md` for the boot screen only. Full spec: DESIGN-9 section 4. Owner: Phase 9 package C.

- Steps are real checks, shown as a discrete checklist `k/6` with `role="status"` text rows: shell painted, runtime config, access, air-gap, Python engine, module registry.
- Status colors: done `--mk-signal-ok`, air-gap ON and limited mode `--mk-signal-warn` (a notice, not an error), failure or timeout `--mk-signal-fail`. Every color is paired with a text label.
- No percent tween, no minimum duration, no placeholder numbers. Exit 300 ms after the last step; 8 s per-step timeout reads "timed out" and boot continues.
- Esc or click skips the animation, never the checks. A 401 stops boot at "Sign-in required".
- Reduced motion: static checklist, no hero, instant fade.
- Optional hero is labelled "Illustrative — not a simulation result" and never covers the checklist.
- Inline pre-paint shell uses `--mk-bg` and no external URLs.
