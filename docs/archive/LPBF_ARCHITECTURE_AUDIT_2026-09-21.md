# LPBF architecture audit — 2026-09-12

## Baseline before implementation

The working tree was clean except for the unrelated, untracked `.cursor/mcp.json`, which must not be committed. The existing analytical Rosenthal, Goldak, Eagar–Tsai, Fabbro and Marangoni paths stay available.

The engineering panel already connects HTTP → JSON-lines bridge → WSL Python → SQLite queue → isolated process. There are two independently implemented explicit enthalpy finite-volume kernels: NumPy Cartesian arrays and OpenFOAM 14 mesh face exchange. Neither solves continuity, momentum, gas, VOF, evaporation, recoil or stress. Registering a free-surface solver without its verification suite would misrepresent capability.

Ubuntu-22.04 / WSL2 and `foamVersion = OpenFOAM-14` were verified. Sandbox WSL access required elevated execution. Baseline TypeScript lint and analytical melt-pool tests passed. Baseline engineering tests: 13 passed, one OpenFOAM skip on Windows, one temporary-directory/SQLite permission failure in the Windows sandbox; repeat on WSL and outside that sandbox before attributing it to the queue.

## Findings

- Source penetration depends on mesh size, confounding mesh sensitivity with a changed physical source. Source position is evaluated before the final source-driven timestep restriction.
- Thermal kernels conserve fixed reference mass; density(T) is diagnostic, not a continuity solution. No active deposition mass audit or interface audit exists.
- Top-surface detection in the OpenFOAM kernel can select more than one layer of cells when the physical surface does not coincide with a mesh face.
- Aggregate dimensions cannot establish local fusion across tracks. Scan-normal voxel support is underestimated for rotated scans. Cross-section is a YZ grid section.
- Calibration accepts width/depth/source but has no enforceable same-process check, uncertainty or holdout metadata.
- Full fields are stored outside JSON, but artifact manifest, size/checksum and retention declaration are absent.
- Refresh loses the current job. Polling loses cache-hit state. Completed result integrity is not checked before reuse. Cancellation can race timeout/shutdown terminal states.
- The engineering panel labels screening correctly; adjacent CAD stress labels and the ground-truth panel's unconditional cooling-rate/martensite statement overstate model scope and need qualification. Numerical convergence is not experimental validation.

## Implementable phases and gates

1. Strengthen the existing thermal foundation: mesh-independent source depth, source integration timing, strict schema/evidence checks, active mass bookkeeping, field artifacts and independent backend comparisons. Gate: numerical tests, actual wmake/case, contract and browser smoke.
2. Keep free-surface capability explicitly unresolved. A future metal/gas solver must pass bounded interface advection, static droplet pressure, spurious-current and phase-volume tests before registration. No invented interface results.
3. Keep flow, evaporation, recoil and keyhole metrics null. Future momentum coupling requires Marangoni cavity and evaporation mass/energy tests before exposing any flow vectors or cavities.
4. Strengthen thermal process history and event traceability, preserving deposition and dwell timing. Local track defects must remain unresolved where only aggregate extents exist.
5. Improve the existing panel, not add decorative dashboards: engineering summary, auditable balances, persistent jobs, explicit mode scope, resource estimates, evidence and artifacts. Gate: lint/build, API, browser states.

Each completed change set records proof and operational status, then commits only task files. Final delivery explicitly distinguishes delivered thermal capability from unresolved research phases.

Scientific basis: [OpenFOAM Foundation 14](https://openfoam.org/version/14/), [NIST model uncertainty](https://www.nist.gov/publications/identifying-uncertainty-laser-powder-bed-fusion-models), and the enthalpy references already recorded in LPBF_ENGINEERING.md. No new experimental measurements are introduced.


## 2026-09-12 follow-up: resolved field workspace
Audit: the thermal backends already solve transient enthalpy conduction. The UI primarily exposes static slices beside analytical geometry, and the application eagerly imports all modules. No momentum or gas interface is available.
Plan: (1) export bounded, checksum-tracked sampled cell-temperature artifacts from both real thermal backends; (2) add an isolated 3D cell-field viewer with time selection, phase coloring and section controls, without interpolated flow; (3) simplify navigation, persist workspace selection and load modules on demand; (4) test artifact contracts, actual OpenFOAM cases, browser interaction, lint/build, then commit/push. Numerical outputs and analytical models remain unchanged.


## 2026-09-13 audit and implemented corrections

The current code review covers `lpbf_simulation.py`, `lpbf_openfoam.py`, `lpbf_worker.py`, `metalliksaThermal.C`, both frontend services, all four requested Melt Pool components, the analytical kernel calls, persistent queue/bridge, engineering documentation and previous proof/operational records.

- **Solved:** stationary 3D transient enthalpy conduction with moving Gaussian deposition, temperature-dependent cp/k, phase fraction, effective powder, preheat, boundary losses and scan/layer history. OpenFOAM uses actual mesh internal-face fluxes; the independent reference uses Cartesian face differences. Neither has a momentum/continuity/free-surface solve.
- **Extracted from thermal fields:** liquidus-cell dimensions/volume/area, sampled cell-temperature files, peak temperature, cooling crossings G/R/cooling, and remelting. Density(T) and viscosity(T) remain constitutive information, not solved mass transport or flow.
- **Analytical/screening:** retained Rosenthal, Goldak, Eagar–Tsai, Fabbro and Heiple–Roper paths; geometric defect indicators, Ma and laser-motion Pe. No calibrated physical probability or resolved keyhole is implied.
- **Excess confidence:** one-cell widths/depths can yield impressive but unreliable geometric ratios. The header now explicitly warns when a positive width or depth spans at most two cells. Legacy illustrative vortex loops could be mistaken for solved recirculation; they and their toggle are removed, while the numerical Marangoni screening model remains.
- **Numerical defect:** gradients included inactive future powder at preheat. Both kernels now exclude inactive faces and use available one-sided differences at the deposition boundary. This changes G/R extraction, not stored enthalpy or laser energy.
- **Integrity defect:** mass and phase accounting were descriptive only. Thermal result publication, restored results and the frontend now recompute closure; failed/missing balances cannot masquerade as completed thermal results. A corrupt restored result becomes a failed job without a result.
- **Execution defect:** process exit between polling and deadline evaluation could be accepted after timeout. Final completion now checks deadline/shutdown and transitions only a running job. Cache identity refreshes the binary hash for long-lived workers. Artifact reads check byte size as well as SHA-256.
- **First-glance comprehension:** each principal metric now has its source, and missing screening peak temperature explicitly says unresolved. Compact process settings expose the shared vector without opening the form. Local edits during a run are labelled separately; submission failure no longer replaces the saved job's input signature.
- **Visual weaknesses:** the old phase palette did not match its legend; cell cubes were arbitrarily shrunk and the section plane was invisible. The new shared fixed palette, exact-sized cubes, translucent mushy cells, visible cut plane, reconstructed liquidus section and camera presets make the field inspectable. Per-frame L/W/D guides come from backend-extracted molten-cell bounds and explicitly differ from the header's maximum-volume sample. Field time drives the thermal-history marker. No time interpolation, flow vectors, cavities or pores are introduced.
- **Density/repetition:** settings stay collapsed by default and the analytical studio stays separate. The evidence areas remain expandable; no decorative dashboard cards were added. The visual language retains navy/slate, blue/cyan information, amber thermal thresholds, and magenta only for unresolved boiling.

Remaining limits: uniform mesh, coarse voxel extents, sampled temporal geometry, approximate absorption depth/material tables, fixed reference mass, no domain-size or temporal-sampling independence proof, no experimentally verified 15-alloy property library. Free-surface, capillary/Marangoni momentum, evaporation/recoil, pore trapping and stress remain unavailable. Capillary/Courant/interface limits and their physical benchmarks are not applicable to the registered thermal solver and must not receive passing badges.
