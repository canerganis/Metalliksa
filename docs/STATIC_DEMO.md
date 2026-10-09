# Static demo: what it is and what it is not

The static demo is a read-only viewer built with `npm run build:demo` into `dist-demo/`. Its design and work packages are in [DEMO_STATIC_DESIGN.md](DEMO_STATIC_DESIGN.md).

## What it is

- A set of recorded snapshots. Each response the demo answers was produced by this app's own engine at a fixed commit, then stored in `demo/snapshots/` and copied into `dist-demo/demo-snapshots/`.
- A screening view. Process window maps, calibration scorecards and benchmark tables are shown with the same evidence labels and limits as the full app.
- Version stamped. The banner on every screen gives the app version and commit that recorded the snapshots. A fingerprint mismatch with the bundled error bands puts the banner in a warning state and hides the process window and calibration cards.

## What it is not

- Not a solver. Nothing is computed in the browser or on a server at run time. Inputs that would need a new calculation are locked to the recorded values, and requests with no snapshot show "Not available in the static demo."
- Not a validation. The demo adds no evidence and promotes no label. `experimentalValidation` stays `false`, and the calibration scorecard enables no cells.
- Not a recipe. The guided NIST IN718 case at 285 W and 960 mm/s is a recorded demonstration of the workflow, not a recommended process.
- Not complete. The Bayesian optimizer, the solidification microstructure lab, CALPHAD and phase diagrams, characterization, research and AI consultation, materials import, the experiment lab, the registry, sources and runs, the job queue, and exports that write to disk are not in the demo.

## Panels in the demo

| Module | Rendered from snapshots | Shows "Not available in the static demo." |
| --- | --- | --- |
| 3D distortion lab | setup, material, thermal, melt pool, qualification | defects, build, comparison, specialists |
| LPBF optimizer | process window map | search, plan |
| LPBF dataset comparison | bundled views | none |
| LPBF calibration scorecard | bundled record | none |
| Keyhole raytracing | bundled benchmark view | none |

The module and panel allowlist is in `src/demo/demoModules.ts`.
