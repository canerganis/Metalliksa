# LPBF core baseline — bounded current-source review

Baseline: application `2ce1abc`, owner `01a0c36f-7006-7eb3-992d-73265a0a354d`.
Initial audit remains open. This is entry-point wiring plus a deeper thermal-contract
review, not an exhaustive scientific audit of all specialist implementations.

## Evidence method

Codebase Memory project `C-Users-can02-Projects-metalliksaa-Metalliksa-1` was
confirmed against the LOCAL root. Generation `2026-09-18T15:50:24Z` is stale.
The bounded LPBF function query returned all 26 matches (no further page); the
simulation-file query returned zero and was not used as absence evidence.
Coverage on core, adapters, UI, routes and named tests reported changed metadata
or untracked paths; App line166 and EngineeringSimulation line167 had parse gaps.
Those source ranges were read directly. The routes scope had no recorded gaps;
direct routes/server search still checked the missing GPU endpoint. Coverage
responses are retained under .runtime/phase0-audit/coverage-*-01a0c36f.json.
Local Graft map and both directions of `run` callers supplied navigation; direct
current source supersedes old graph cards. Dynamic calls through `thermal_solver`
are inspected in source, not inferred absent from Graft's outgoing edges.

## Current entry-point map

App's LPBF switch contains the following 16 module entries. Component filenames
are under `src/components/`; service is `src/services/pythonComputationService.ts`
unless stated otherwise. `W` means `routes/lpbfSimulation.ts` →
`server/lpbfWorkerBridge.ts` → `python/lpbf_worker.py`; `P` means
`routes/physics.ts` host Python dispatch. Test names are located contracts,
**not a claim that every test was rerun or establishes physical validity**.

| UI component | API → implementation under `python/` | Material/data boundary; located tests |
| --- | --- | --- |
| LpbfEngineeringWorkspace / 3d-distortion-lab/LpbfEngineeringSimulation | `lpbfSimulationService.ts` → W `/api/lpbf/jobs` → `lpbf_simulation.run` → NumPy reference or `lpbf_openfoam.thermal`; estimate/get/cancel/artifact endpoints | `lpbf_material_registry` from four-alloy authority plus explicitly secondary alloys or supplied table; `test_lpbf_engineering`, heat_source, peak, overlap; TypeScript lpbf-contract/fields/workflow |
| LpbfBayesianOptimizerLab | P `/api/python/lpbf-bayesian-optimize` → `lpbf_bayesian_optimizer` | Four-alloy lookup; surrogate objective is not measured truth; `test_phase6` |
| SolidificationMicrostructureLab | W `/api/python/lpbf-solidification-microstructure` → `lpbf_solidification_microstructure` | Caller material/G/R or Rosenthal screening with defaults; `test_phase8` |
| ThermomechanicalDistortionLab | W `/api/python/lpbf-thermomechanical-distortion` → `lpbf_thermomechanical` | Caller properties plus default elastic/thermal values, inherent strain; `test_phase9` |
| ExperimentalValidationLab | W `/api/python/lpbf-experimental-validation` → `lpbf_experimental_validation` | UI hardcodes simulation PDAS1.5/depth120 and Ti64/P250/v1000; backend always returns `validated`, even no paired metrics. OPEN evidence defect; `test_phase10` currently accepts heuristic thresholds |
| ModulusFNOLab | W `/api/python/lpbf-modulus-fno` → `lpbf_modulus_fno` | Predict function deliberately raises without trained/validated checkpoint; `test_phase11` tests rejection |
| LpbfToolpathStudioLab | W `/api/python/lpbf-toolpath-kinematics` → `lpbf_toolpath_kinematics` | Parsed CLI/G-code vectors, mm/mm-s/us scanner controls; `test_phase12` |
| MurakamiFatigueLab | W `/api/python/lpbf-fatigue-fracture` → `lpbf_fatigue_fracture` | Separate fatigue constants, defect/position/load assumptions; `test_phase13` |
| LpbfDefectTwinLab | W `/api/python/lpbf-stl-voxelize` → `stl_voxelizer` | STL plus supplied defects; does not predict physical pores; `test_phase14` |
| LpbfAdaptiveMitigationLab | W `/api/python/lpbf-adaptive-feedforward` → `lpbf_adaptive_feedforward` | Scanner profile and toolpath, feedforward screening; `test_phase15` |
| MultiLaserPlumeLab | W `/api/python/lpbf-multilaser-plume` → `lpbf_multilaser_plume` | Prescribed gas/plume parameters; worker supplies example vectors when absent; `test_phase16` |
| MultiTrackThermalLab | W `/api/python/lpbf-thermal-accumulation` → `lpbf_thermal_accumulation` | Worker resolves four-alloy authority; direct dataclass still has Ti64 defaults. Constant-property Green-function superposition, not FV enthalpy; `test_phase17`, `test_lpbf_thermal_materials` |
| PowderDEMCompactionLab | W `/api/python/lpbf-powder-dem-compaction` → `lpbf_powder_dem_compaction` | Worker calls `generate_psd_deterministic`, returning radii; it does NOT call the packing implementation. Separate integration gap; `test_phase18` |
| OpticalTomographyLab | W `/api/python/lpbf-optical-tomography` → `lpbf_optical_tomography` | Prescribed emissivity/sensor/noise, not NIST calibration operator; `test_phase19` |
| TransientEnthalpy3DGPULab | service `/api/python/transient-3d-gpu` has NO route; W method exists → `lpbf_transient_3d_gpu` | UI duplicates four material tables; worker accepts loose scalar properties. Separate unverified Warp model; `test_phase22` is legacy smoke, not numerical equivalence |
| KeyholeRaytracingLab | direct W `/api/python/lpbf-keyhole-raytracing` → `lpbf_keyhole_raytracing` | Prescribed surface/optics, seeded rays, explicit device and unresolved power; `test_keyhole_contract`, `test_phase26`, lpbf-keyhole-api |

Workspace subpaths also include P `/api/python/lpbf-build-job` →
`lpbf_build_job_solver` → `lpbf_thermal_solver` + slicer, using the four-alloy
authority and `rosenthal-screening-v1`. Legacy thermal labs use
`/api/python/lpbf-thermal[-solver]`, Goldak/Eagar–Tsai/Fabbro adaptations; those
must not silently alter Build Job verdicts. W also exposes support optimization
and 2D transient FDM; neither is a separate App LPBF module in this switch.
The 2D FDM implementation is a stationary pulse with fixed30um radius/.4
absorption despite a speed argument; it is not the shared moving FV solver.

Source archive route/service/repository/artifact bundle are already implemented
and reviewed in `LPBF_SOURCE_ARCHIVE.md`. They persist source bytes/revisions,
not complete simulation/experiment records. Source SHA checks prove byte identity,
not valid calibration. Current HDF5 review leaves temperature conversion null.

## Shared seams and constraints

| Concern | Current thermal authority | Integration constraint / gap |
| --- | --- | --- |
| Identity/properties | `four_alloy_materials.py` → `lpbf_material_registry.material` | Estimated interpolated endpoints; source text not independent verification. Registry overwrites version with `lpbf-materials-1`; retain the complete resolved table in a content-addressed snapshot |
| Units/beam | `lpbf_simulation.validate`; SI inside transient | Public mm/s, um, Celsius; 1/e² intensity diameter. A D4sigma dataset label is not a universal beam-convention conversion |
| Enthalpy | `lpbf_material_registry.enthalpy_table/property_at` | Piecewise-linear cp integral from273.15K, linear mushy latent fraction, pure-metal1K regularization. Legacy 2D/Warp enthalpy origins/laws differ |
| Heating | `lpbf_heat_source` | Cell-integrated Gaussian, two time quadrature nodes, penetration=layer thickness, normalized represented absorbed power; capture diagnostic is not measured absorptivity |
| Boundaries/mass | `lpbf_simulation.transient`, matching OpenFOAM adapter | Fixed reference density with powder packing; whole-cell layer activation; isothermal bottom, insulated sides, top convection/radiation. Boiling fails; no evaporation/free surface |
| Numerics | local row-sum stability, source increment limiter, explicit Euler | 600000 cells,250000 steps; mesh/time errors not implied by energy closure; two melting meshes differ materially |
| Output/audits | `lpbf_evidence`, `lpbf_peak`, `lpbf_overlap` | Energy≤.01; stationary mass/phase closure≤1e-10. Earliest maximum molten volume over accepted steps; sparse playback. G/R are crossing-derived averages, not microstructure validation |
| Runtime/jobs | worker Queue SQLite + filesystem; bridge20s RPC | Queued thermal jobs have subprocess lifecycle; direct specialist requests execute in stdin loop. HTTP abort does not cancel those calculations |
| Identity/storage | fingerprint hashes Python sources plus version/input/material | `implementationHash` currently also depends on input/material; do not call it a source-only hash. Need separate stable contract/material/input hashes for future run records |

The old Warp solver is not a drop-in GPU backend: automatic cuda/cpu selection,
float32, different enthalpy law, hardcoded30um radius/.4 absorption, velocity/recoil
clamps and10 Jacobi iterations, unmeasured divergence/energy closure, loose
toolpath/property validation. Its return fields lack the FV audit/provenance
contract. Keep it isolated until bounded inputs, explicit device, same thermal
case/operator and measured conservation/equivalence are established. No new route
was enabled by this review.

## Fresh resource measurement

40W IN718,800mm/s,80um 1/e² diameter,80°C preheat,200um single track,40um layer,
.1ms cooling, no dwell; estimated material absorption.38/emissivity.35.
Windows Python3.12.10/NumPy2.2.6, `.runtime/lpbf-win-py312/Scripts/python.exe`,
explicit `backend=reference`, actual `enthalpy-fv-6`. No GPU/VRAM measurement.

| Requested mesh | Cells / steps | Solver wall / imports+solver | Peak process working set | Solver artifacts | Peak K / molten volume um³ | Energy relative error |
| --- | --- | --- | --- | --- | --- | --- |
| 40um |1089 /407|2.3170s /2.6874s|244932608 bytes|64 files,319141 bytes|2119.8101 /192000|5.71e-16|
| 20um |8228 /659|4.8926s /5.3690s|244813824 bytes|65 files,2179754 bytes|2803.3077 /256000|4.57e-16|

Liquidus1609.15K, boiling3123.15K. Independently reading float32 saved frames
found maxima2118.9023K and2803.3076K above liquidus. W/D changed40/40→80/20um:
**no mesh convergence accepted**. These are small bounded synthetic melting
resource profiles, not representative full-build performance or experiment.
Peak memory includes imported libraries over process lifetime, excluding shell;
artifact totals include solver-produced files, excluding added result/profile JSON.
Wall time is one observation per mesh, not a statistical benchmark.

Harness .runtime/phase0-audit/profile_melting_01a0c36f.py; successful folders
`lpbf-melting-40um-r2-01a0c36f` and `lpbf-melting-20um-01a0c36f` contain complete
resolved inputs, runtime, manifest SHA256s, result and profile JSON. First40um
attempt failed only in profiler's fieldSeries parsing after solving; its partial
folder is retained and excluded. Prior `lpbf-reference-profile-01a0c339/profile.json`
actually records **10W**, not40W as repeated in earlier handoff notes;1175.58K
was nonmelting. This correction supersedes that description.

## Fresh regression and remaining gates

Windows CPU: engineering25PASS/1OpenFOAMskip; heat source7PASS/1skip;
peak4PASS/1skip; overlap5PASS/2skip; thermal-material RPC3PASS. Total44PASS/5skip.
Logs .runtime/phase0-audit/test_*-permitted-01a0c36f.log. Initial sandbox runs
failed temporary-directory access; permission-scoped reruns passed. Windows skips
are explicit Linux/OpenFOAM conditions. Previous task's WSL engineering26PASS
is separate historical evidence; the new source/peak/overlap groups have not yet
been rerun in WSL here. No numerical acceptance threshold changed.

Still open: specialist evidence defects above, primary calibration equation and
measurement operator, melting mesh/time convergence, matched CPU/GPU proof,
run/experiment persistence and complete bundle restoration. Phase baseline
coverage is substantially improved, but no later-phase acceptance is implied.
