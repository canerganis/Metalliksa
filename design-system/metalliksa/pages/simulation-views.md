# Page: Simulation views (stub)

> Overrides `../MASTER.md` for simulation and analysis views. Full spec: DESIGN-9 sections 5-6. Owner: Phase 9 packages D and E.

- Motifs: thermal = magma ramp with a labelled °C/K colorbar; tracks = plasma toolpath lines, scan order by lightness; lattice/phase = categorical; evidence = document cards with a provenance rail; network = node graphs.
- Data-viz: viridis/cividis for magnitudes, Okabe-Ito for categories, diverging only around a physical zero, no rainbow/jet.
- Every chart header shows units, source and the evidence badge (`--mk-evidence-unvalidated` for unvalidated). Glow never sits on data marks; glass never sits behind charts.
- Unavailable series render as hatched "no data", never interpolated.
- Long jobs show progress only from backend steps ("step i/N" + elapsed); without N, an indeterminate bar + elapsed + phase name.
- Changed inputs: the old result is dimmed and badged "Stale — inputs changed"; the badge itself stays at full contrast.
