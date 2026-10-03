# Metalliksa roadmap

> **Single active plan:** this document governs current Metalliksa work. The only active release objective is the V1 Research Workstation below; historical solver phases and the A01–H02 / K0–K4 engineering ledger are reference records, not parallel active plans or V1 acceptance gates. The in-app ledger is a deferred qualification backlog and cannot imply industrial, customer-pilot, or commercial readiness.

## Current position

- **Latest implementation milestone:** V1 Research Workstation hardening — latest V1 LPBF milestone is the fail-closed NIST 3707 Table 5 proxy preflight (`f06359a`), after archived proxy section metadata validation (`c38f933`) and the fail-closed optical geometry guard (`f46dc8c`); the newest code commit on this integration line is `ab7a55b` (v2 security, packaging, a11y, bundle and air-gap hardening); the full V1 exit is not yet accepted.
- **Active goal:** V1 Research Workstation (see below); new physics phases, including GPU-accelerated 3D transient enthalpy work, stay frozen until its exit path is accepted.
- **Application surface:** the current workspace inventory marks modules as Research or Preview; none is labelled Production.
- **Evidence boundary:** the application is a traceable engineering research workstation. Solver outputs remain screening results unless the matching evidence is recorded in `PROOF.md`.
- **Plan authority:** this ROADMAP owns sequencing and acceptance. `STATUS.md` records the latest verified state; `docs/ACTIVE_WORK.md` and the in-app engineering ledger preserve dated history/deferred qualification work.
- **Historical plan:** the previous six-phase roadmap is preserved at [`docs/archive/ROADMAP_LEGACY_PHASES.md`](docs/archive/ROADMAP_LEGACY_PHASES.md).

## Active release goal — V1 Research Workstation

Bring one bounded CPU LPBF workflow to a reproducible, honest, release-ready research tool. V1 does not mean industrial qualification: unsupported comparisons stay unavailable, solver limits remain visible, and other workspaces stay Research/Preview. Freeze new physics phases until this exit path is accepted.

1. **Close claim and provenance gaps.** Do not emit a six-section NIST observation unless each section is tied to an independently simulated track field; do not turn missing melt geometry into a positive measurement. Keep NIST residuals unavailable until the observer and its artifact bindings are implemented and tested.
2. **Freeze separate workflow and numerical references.** Use the archived IN718 `standard/reference` 60 W / 1200 mm/s / 80 µm / 200 °C / 20 µm / 600 µm single-track, single-layer powder-bed case to replay the user path; bind resolved inputs, material revision and solver fingerprint. It is not a numerical-convergence oracle and does not match NIST Table 4. For numerical acceptance, use the existing manufactured-source and mixed-boundary diffusion tests separately: record the uniform/nonuniform manufactured final-temperature absolute-error bound `1e-7 K`, the all-case relative energy-error bound `1e-10`, distinct realized step counts, and the diffusion test's monotonically decreasing RMS error and observed order >1. The `1e-7 K` bound is not a diffusion RMS or piecewise sampled-temperature bound. These verify solver operators, not physical IN718 accuracy. Keep real moving-source mesh/time convergence a separate gate; unresolved trends stay `inconclusive` and experimental validity stays `unvalidated`.
3. **Keep one complete user path trustworthy.** Configure → run → inspect provenance and limitations → archive → export → restore → reload. Retain separate acceptance for cancellation, stale inputs, malformed bundles and recovery; record the result against the exact release revision.
4. **Make the research release reproducible.** Verify clean installation, locked dependencies, supported CPU runtime, visible failure states and traceable report/manifest using [application reproduction](docs/APPLICATION_REPRODUCTION.md) and [CPU LPBF reproduction](docs/LPBF_CPU_REPRODUCTION.md); follow the release/rollback checklist below.

**V1 exit evidence:** the same release revision passes the separate numerical-oracle suite, clean-install reproduction, replay of the archived workflow case, one end-to-end browser/archive round trip and critical error/recovery paths; every displayed scientific claim maps to recorded evidence. Report operator-level software checks, scenario-level convergence and experimental validity as separate statuses. NIST residuals, customer pilot, commercial launch, ML performance, GPU speed advantage and production labels are not V1 requirements.

## Release and rollback checklist

Before accepting a V1 release, record the exact Git revision and confirm that a clean tracked-source archive passes locked dependency installation, type checking, the full unit suite and production build. Run the documented CPU runtime smoke check and one browser workflow through archive, portable `.tar` download, upload/import, integrity verification, isolated restore and reload. Record run/source IDs, archive SHA-256, test counts, skipped checks and scientific limitations in `STATUS.md`; an unavailable or skipped scientific comparison must stay unavailable, not count as validation.

For rollback, stop writes and stop only the service processes started for the failed release. Preserve the failed release, logs, and every configured run/source/bundle root identified by `METALLIKSA_LPBF_*_ROOT`. Select the last recorded known-good revision and its matching locked runtime. Before reconnecting persistent stores, verify their compatibility with that revision or restore a pre-release backup into an isolated location and verify its integrity there. Re-run the documented health and archived-run read checks before reopening writes. If compatibility or integrity is uncertain, keep writes disabled and retain the stores for recovery; do not overwrite or delete them during rollback.

The A01–H02 / K0–K4 matrix in `src/data/engineeringRoadmap.ts` is a deferred qualification backlog. It becomes active only through an explicit later scope decision; its customer discovery and external validation gates are never inferred from internal software tests.

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
