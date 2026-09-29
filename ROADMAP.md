# Metalliksa roadmap

> **Important Navigation Note:** 
> Metalliksa operates on two distinct, parallel roadmaps to separate physical simulation features from commercial and engineering readiness.
> 
> 1. **Physics & Features Roadmap (This Document):** Tracks the technical implementation of physical solvers, simulation models, and algorithms across 21 implementation milestones (Phases 1-21).
> 2. **Engineering & Pilot Roadmap (UI & Code):** Tracks strict software, quality, and pilot qualification gates (Tasks A01-H02 / Gates K0-K4) needed for industrial usage. This is managed in `src/data/engineeringRoadmap.ts` and visible in the application's Engineering Roadmap UI panel.
> 
> *A completed phase in this document is an algorithmic implementation milestone, not a claim of experimental qualification or production readiness (which belongs to the Engineering Roadmap).*

## Current position

- **Latest implementation milestone:** Phase 21 — transient enthalpy-method phase-change solver (FDM).
- **Active worktree:** Phase 22 GPU-accelerated 3D transient enthalpy work is present as uncommitted changes; it is intentionally not treated as a completed milestone here.
- **Application surface:** 30 registered workspaces; the current inventory marks them as Research or Preview, with no module labelled Production.
- **Evidence boundary:** the application is a traceable engineering research workstation. Solver outputs remain screening results unless the matching evidence is recorded in `PROOF.md`.
- **Historical plan:** the previous six-phase roadmap is preserved at [`docs/archive/ROADMAP_LEGACY_PHASES.md`](docs/archive/ROADMAP_LEGACY_PHASES.md).

## Active release goal — V1 Research Workstation

Bring one bounded CPU LPBF workflow to a reproducible, honest, release-ready research tool. V1 does not mean industrial qualification: unsupported comparisons stay unavailable, solver limits remain visible, and other workspaces stay Research/Preview. Freeze new physics phases until this exit path is accepted.

1. **Close claim and provenance gaps.** Do not emit a six-section NIST observation unless each section is tied to an independently simulated track field; do not turn missing melt geometry into a positive measurement. Keep NIST residuals unavailable until the observer and its artifact bindings are implemented and tested.
2. **Freeze separate workflow and numerical references.** Use the archived IN718 `standard/reference` 60 W / 1200 mm/s / 80 µm / 200 °C / 20 µm / 600 µm single-track, single-layer powder-bed case to replay the user path; bind resolved inputs, material revision and solver fingerprint. It is not a numerical-convergence oracle and does not match NIST Table 4. For numerical acceptance, use the existing manufactured-source and mixed-boundary diffusion tests separately: record their `1e-7 K` temperature and `1e-10` energy bounds, distinct realized step counts, monotonically decreasing RMS error and observed order >1. These verify solver operators, not physical IN718 accuracy. Keep real moving-source mesh/time convergence a separate gate; unresolved trends stay `inconclusive` and experimental validity stays `unvalidated`.
3. **Keep one complete user path trustworthy.** Configure → run → inspect provenance and limitations → archive → export → restore → reload. Retain separate acceptance for cancellation, stale inputs, malformed bundles and recovery. The 2026-09-28 workflow record already covers a real CPU round trip; repeat acceptance against the final release commit.
4. **Make the research release reproducible.** Verify clean installation, locked dependencies, supported CPU runtime, visible failure states, traceable report/manifest, and a release/rollback checklist.

**V1 exit evidence:** the same release revision passes the separate numerical-oracle suite, clean-install reproduction, replay of the archived workflow case, one end-to-end browser/archive round trip and critical error/recovery paths; every displayed scientific claim maps to recorded evidence. Report operator-level software checks, scenario-level convergence and experimental validity as separate statuses. NIST residuals, customer pilot, commercial launch, ML performance, GPU speed advantage and production labels are not V1 requirements.

The A01–H02 / K0–K4 matrix in `src/data/engineeringRoadmap.ts` remains the later engineering/industrial-pilot track. Its customer discovery and external validation gates are not inferred from internal software tests.

## Implemented milestones

Phases 1–6 established the data, standards, thermal, optics, powder, and CFD foundations. Phases 7–11 added plume/shielding, solidification microstructure, thermomechanics, experimental traceability, and GPU/optimization workflows. Phases 12–16 added toolpath kinematics, fatigue/fracture screening, spatial defect twin, adaptive feed-forward mitigation, and multi-laser/plume coordination. Phases 17–21 added thermal accumulation, powder-bed compaction, optical tomography/NETD, support optimization, and transient latent-heat phase change.

Each milestone must remain backed by its focused tests and a dated entry in [`PROOF.md`](PROOF.md).

## Remaining product gaps

1. **End-to-end CAD/process contract:** preserve CAD geometry, powder state, machine profile, layer plan, and scan strategy as one versioned process vector.
2. **Baseline comparison:** establish a reproducible GO-MELT or equivalent baseline with declared inputs, mesh/time-step policy, error norms, and wall-clock measurements.
3. **Part-level validation:** separate calibration from holdout validation using measured melt pools and XCT/Archimedes evidence.
4. **Physics maturity:** keep the current analytical and screening models distinct from a fully coupled free-surface, evaporation, recoil, Marangoni, and stress solver.
5. **Production readiness:** move modules from Research/Preview only after runtime, evidence, packaging, and failure-state gates are satisfied.

## Working order

Follow the active V1 release goal above. Start with the observer/provenance correction, then freeze the CPU reference case and release acceptance. Do not add another physics phase until V1 is accepted or a measured research need justifies a bounded new contract.
