# DESIGN 5c: LPBF simulation cleanup and the single planned fingerprint bump

> **Status and user decisions (recorded 2026-10-04).** Copied unchanged from branch
> `orch/p5c-design` (commit 528168d) except for this note and the stage-P gate update in 3.3.
> The user approved:
> - deleting the dead `use_cfd` / `openfoam-cfd` branch (B1') and moving the test-only CFD
>   case writers out of `lpbf_cfd.py` (B1);
> - labelling the hard-coded CFD metal constants as verification-case constants (wording only,
>   no value change);
> - deferring the material-authority migration (section 4, B5) to a later bump;
> - after the bump, re-recording only the V1 60 W replay and G2 (no Table 4 case 0 runs).
>
> Stage P is implemented on `orch/p5c-prep`: `python/lpbf_implementation_fingerprint.expected`
> with `test_lpbf_implementation_fingerprint_pin`, `tools/lpbf_parity_check.py` (the P2
> harness; named differently from `capture_lpbf_parity_golden.py` below) with goldens in
> `python/golden/lpbf_parity/`, `tools/lpbf_bump_record.py`, and the package-aware closure
> test. Parity goldens are valid only in the recorded environment (reference machine, locked
> `.runtime/lpbf-win-py312`); elsewhere `--check` reports SKIP (exit 3), never PASS.

Design only. Nothing here is implemented. Base: app HEAD `cac331b` (V1 acceptance is bound to `10e3005`; see STATUS.md top).
Current LPBF implementation fingerprint (verified in this worktree with the locked interpreter): `7482697c458b6c1aa2a77829f2fbce0c4ce4ac9466e9a3583e97b9a799b5e483`.

Labels used below: **[V]** verified in this worktree (command or file:line given), **[A]** assumption that has not been verified, **[Q]** question for the user.

## 0. Corrections to the plan text

- **[V]** The manifest `python/lpbf_simulation.py:44-82` has **37** entries, not 38. `python/test_phase6a_leaf_modules.py` `test_manifest_has_37_entries` pins this count.
- **[V]** The vector `f3cf15f2…` in `python/test_lpbf_source_identity.py:77,138` is a synthetic raw-v2 framing vector over a two-file fixture (`z.py`, `a.py`, version `solver-v6`). It does **not** depend on the real manifest, so the bump does not break it. It breaks only if `lpbf_source_identity.py` framing changes, and that file must not be touched.
- **[V]** No test pins the real fingerprint `7482697c…`. The value appears only in `STATUS.md`, `PROOF.md` and the data fixture `tests/fixtures/lpbf-real-bare-plate-100W-capture.json`. That fixture is historical data: no test compares it with the current fingerprint. Today an unplanned bump is caught only by the manual lane check, so stage P adds a pin.
- **[V]** `numpy.interp` has no `out=` parameter. The locked runtime has numpy 2.2.6, signature `(x, xp, fp, left=None, right=None, period=None)`. The plan item "np.interp out=" cannot be done as written. Section 1.3 gives the bit-identical alternatives.
- **[V]** Worker dispatch is already done (`lpbf_worker_rpc.py`, commits `5e5ff7d` and `c174efb`). `python/lpbf_json_utils.py` does not exist yet.
- **[V]** `LaserSourceConfig` (`python/lpbf_multilaser_plume.py:45`) is **not** in the manifest. Removing it is non-manifest prep, not part of the bump.

## 1. Inventory

### 1.1 The 37 manifest files

Line counts and bytes come from `wc`. Every file is CRLF; the canonical-v3 identity normalises CRLF to LF. "Prod" counts production (non-test) Python importers found with `rg`.

| File | Lines | Bytes | Role | Prod importers | 5c action |
|---|---:|---:|---|---:|---|
| four_alloy_materials.py | 441 | 15497 | Four locked alloys (thermal, Marangoni, ISM, P-v, melt-pool cases, U95), resolver, `canonical_material_source` | 13 | **Becomes a view** (section 4) |
| eagar_tsai_solver.py | 115 | 4478 | Eagar-Tsai analytical field | 1 | none |
| fabbro_keyhole.py | 74 | 2294 | Fabbro keyhole screening | 1 | none |
| goldak_solver.py | 135 | 4952 | Goldak field used by `screening()` | 2 | none |
| in625_gpu_thermal_material.py | 178 | 7363 | IN625 CPU/CUDA constitutive adapter | **0** (test only) | [Q] keep in manifest or drop |
| in625_thermal_material.py | 359 | 16191 | IN625 snapshot (TS pin `f47b07e4…`, archive restore equality) | 6 | **do not touch** |
| lpbf_core_contract.py | 147 | 8785 | Core identity binding; `enforce_core_contract` re-derives from archived data | 6 | **do not touch** (archive backward compatibility) |
| lpbf_core_physics.py | 288 | 14687 | Source quadrature, scan segments, SI inputs | 15 | remove dead `evaluate_material_properties` (279-288) |
| lpbf_cfd.py | 2690 | 81047 | OpenFOAM VOF case writer and runner; production path unreachable (1.4) | 1 | move test-only code out (~2313 lines) |
| lpbf_defect_diagnostics.py | 167 | 8484 | Geometric screening | 5 | none |
| lpbf_evidence.py | 234 | 14284 | Audits, balances, artifacts, `FieldRecorder` | 8 | none (validators used on restore) |
| lpbf_evaporation_marangoni.py | 96 | 4088 | Opt-in evaporation / k_eff path | 1 | none |
| lpbf_gpu_pilot_artifacts.py | 223 | 11283 | GPU pilot artifact integrity | 2 | none |
| lpbf_gpu_pilot_numerics.py | 436 | 23687 | GPU pilot numeric recomputation; has a recursive `_strict_json_equal` (76) | 2 | none (section 1.3) |
| lpbf_gpu_thermal.py | 970 | 56115 | CUDA pilot and archive validator; has a JSON-dump `_strict_json_equal` (808) and `_strict_json_object` (48) | 6 | none (no CUDA to verify here, [A]) |
| lpbf_gpu_thermal_warp.py | 575 | 27256 | Warp pilot | 3 | none |
| lpbf_heat_source.py | 59 | 2784 | Source-limited step, capture gate | 4 | none |
| lpbf_layered_conduction.py | 97 | 4582 | Layered-plate conduction | 1 | none |
| lpbf_material_registry.py | 197 | 10861 | `material()` snapshot plus `materialRevisionSha256`; imports `SECONDARY_THERMOPHYSICAL_DB` from a solver | 6 | optional data re-point (4.5) |
| marangoni_screening.py | 82 | 3150 | Heiple-Roper screening | 1 | none |
| lpbf_openfoam.py | 190 | 13291 | OpenFOAM thermal backend | 4 | none |
| lpbf_overlap.py | 220 | 10207 | Overlap diagnostics | 2 | none |
| lpbf_peak.py | 670 | 38185 | Peak tracker and corridor NPZ writer | 12 | none |
| lpbf_run_progress.py | 197 | 8757 | CPU progress (stdlib leaf); one reference gate at 39 | 3 | leave inline (keep it a leaf) |
| lpbf_source_identity.py | 100 | 4759 | Fingerprint framing (raw-v2, canonical-v3) | 2 | **do not touch** |
| powder_packer.py | 64 | 2647 | Packing helper | 1 | none |
| powder_bed_raytracer.py | 166 | 5497 | Absorptivity helper | 1 | none |
| lpbf_simulation.py | 1155 | 72101 | Validate, run, CPU transient, fingerprint, manifest | 28 | gate helper, loop hoists, CFD dead branch [Q] |
| lpbf_ss304_support_material.py | 114 | 5205 | SS304 support snapshot | 2 | none |
| lpbf_thermal_solver.py | 907 | 39608 | Legacy analytical / build-job solver; `SECONDARY_THERMOPHYSICAL_DB` (32-159) | 9 | optional data move (4.5) |
| lpbf_transient_3d_gpu.py | 1747 | 80586 | Warp keyhole solver; `import warp` and `wp.init()` at import | 1 (rpc) | none in this bump |
| lpbf_verification.py | 34 | 2334 | Numeric comparison helpers | 2 | none |
| solidification_front.py | 272 | 9884 | G, R, G·R | 1 | none |
| warp_thermal_solver.py | 92 | 2247 | Warp Rosenthal slice | 1 | none |
| openfoam/Make/files | 3 | 59 | build list | – | none |
| openfoam/Make/options | 5 | 135 | build flags | – | none |
| openfoam/metalliksaThermal.C | 305 | 15855 | OpenFOAM thermal solver source | – | none |

### 1.2 Cleanup candidates, checked line by line

**(a) Duplicated "standard + reference" gates. [V]** The conjunction `p["mode"] != "standard" or p["backend"] != "reference"` occurs **10 times**:
- `lpbf_simulation.py`: 158, 222, 415, 423, 440, 900, 907, 921
- `lpbf_run_progress.py`: 39
- `lpbf_gpu_thermal.py`: 467

Six of these are the same observer gate (`study == "none"`, `surfaceMode == "powder-layer"`, not layered):
- In `transient()`: 415, 423, 440.
- In `run()`: 900, 907, 921. These add the extra clause `thermal_solver is not transient`.

Plan:
- Add one private helper in `lpbf_simulation.py`, `_require_reference_powder_observer(p, message, thermal_solver=None)`. It must keep the **exact error strings** and the same short-circuit order.
- Replace only the six observer gates.
- Leave 158, 222 and 467 inline. They carry different clauses and messages.
- Leave `lpbf_run_progress.py:39` inline. It is a stdlib leaf, and importing `lpbf_core_physics` there would pull numpy into it.
- Value: readability only. It touches no numbers.

**(b) CPU transient loop. [V]** Loop: `lpbf_simulation.py:541-735`. Profile of the V1 60 W case at HEAD (cProfile, 24.8 s with the profiler, 2421 accepted steps):

| Function | Time |
|---|---|
| `_conduction_rate_and_diagonal` | 4.9 s |
| `transient` self time | 4.4 s |
| `np.interp` | 2.67 s over 9695 calls (4 per step) |
| `gaussian_interval` via `_evaluate` → `math.erfc` per element | about 4-5 s (2.77 M erfc calls) |
| All ufunc reductions (`.max` / `.min` / `.sum`) together | 0.9 s |
| `np.asarray` | 0.38 s |

Bit-identical candidates (pure hoisting of loop-invariant or repeated values):
- Compute `float(T.max())` once per step and reuse it at 720, 731 and 733.
- Hoist the per-run constant `np.interp(m["boiling_K"], tt, hh)` (611, 622) out of the loop.
- Pre-convert `m["table"]` once. `property_at` calls `np.asarray(m["table"])` twice per step (`lpbf_material_registry.py:185-187`).
- Expected gain is small, **< 3 %** [A, estimated from the profile].

**Not allowed under bit parity**:
- Replacing `math.erfc` with a vectorised `scipy.special.erfc`.
- Sharing one `searchsorted` between the two `property_at` interpolations.
- Writing a custom piecewise-linear interpolant.
- Any algebraic re-association.

Each of these changes the floating-point results, even though they are the only large speed-ups. Section 6 covers them as a separate, explicitly drifted option.

**(c) `lpbf_cfd.py` test-only code. [V]** Callers were found with `rg`. Only `test_lpbf_cfd.py` uses:

| Code | Lines |
|---|---|
| `verify_cfd_capability` | 69-100 |
| `run_wsl_command` | 101-113 |
| `setup_droplet_case` | 114-461 |
| `setup_stefan_case` | 462-764 |
| `run_cfd_simulation` | 765-798 |
| `read_foam_scalar_field` | 799-831 |
| `read_foam_vector_field` | 832-865 |
| `stefan_analytical_solution` | 866-890 |
| `setup_darcy_damping_case` | 891-1191 |
| `setup_thermal_parity_case` | 1192-1448 |
| `setup_marangoni_case` | 1449-1772 |
| `knight_analytical_recoil_pressure` | 1773-1790 |
| `setup_recoil_case` | 1791-2123 |
| `setup_laser_case` | 2124-2381 |

Totals: setup functions 2124 lines plus helpers 189 lines, **2313 of 2690**. About 377 lines stay: constants, `is_linux`, `to_wsl_path`, `foam_header`, `setup_cfd_multiphysics_case` (2382) and `cfd_multiphysics` (2635).

The move also takes the stale absolute path `WSL_SOLVER_BIN = "/mnt/c/Users/can02/OneDrive/Desktop/Uşağım/..."` (`lpbf_cfd.py:30`, used at 73, 74, 89, 776) out of the manifest. Production uses the relative `BINARY_CFD` (2645).

Target: one flat, non-manifest module `python/lpbf_cfd_cases.py`. Use a flat module, not a package, because of the closure-test gap in P4. It imports from `lpbf_cfd`, never the other way round.

Also noticed:
- `test_lpbf_cfd.py` defines `test_09_moving_laser_surface_heating` twice (456, 507), so the first definition never runs. Not a manifest file.

**(d) Dead code. [V]**
- `lpbf_core_physics.evaluate_material_properties` (279-288) has no callers anywhere.
- `LaserSourceConfig` is dead but non-manifest (see section 0).

**(e) `_strict_json_*` duplicates. [V]** The two manifest copies are **semantically different**, so merging them is not behaviour-preserving:
- `lpbf_gpu_pilot_numerics.py:76` is recursive and type-strict:
  - `-0.0 == 0.0` is true.
  - tuple ≠ list.
  - NaN ≠ NaN.
- `lpbf_gpu_thermal.py:808` compares `json.dumps(sort_keys, allow_nan=False)` strings:
  - `-0.0` ≠ `0.0`.
  - tuple == list.
  - NaN → False through the exception path.
  - Non-string keys are coerced.
- `_strict_json_object` (`lpbf_gpu_thermal.py:48`) is a parse hook, not a duplicate.

The other copies (`_sha256*`, `_write_json`) live only in non-manifest `run_*.py` diagnostic runners. Some docs protocols bind those runners by path or hash [A: not checked file by file].

**Recommendation:**
- Do **not** add `lpbf_json_utils.py` to the manifest in this bump.
- Document the two semantics with a comment-free rename, or leave them as they are.
- Deduplicate the runner helpers only after checking their evidence references.

**(f) The OpenFOAM CFD branch is unreachable. [V]**
- `validate()` rejects `backend="openfoam-cfd"` (`lpbf_simulation.py:179`).
- `run()` calls `validate(raw)` first (863).
- So `use_cfd` (883-893) and the `lpbf_cfd` import (892) can never execute through `run()`.
- No TS/server code sends `openfoam-cfd` (`rg` found nothing).
- `cfd_multiphysics` is called only by `test_phase7.py` and `test_phase8.py`.
- `lpbf_solidification_microstructure.py:138` mentions it only in a docstring.

Separately, `setup_cfd_multiphysics_case` writes **hard-coded metal properties that ignore the selected alloy** (`lpbf_cfd.py:2477-2500`): `rho 4000`, `kMetal 30`, `cpMetal 500`, `latentHeat 2.86e5`, `sigma 1.52`, `dSigmaDT -2.6e-4`, `latentHeatVap 7.4e6`. Only solidus, liquidus and boiling come from `m`. This breaks the single-material-authority rule. Fixing it changes the science, so it is **not** part of this bump [Q].

**(g) Manifest coverage gaps. [V]**
- The CFD solver sources `python/openfoam/meltPoolFoam/*.C/*.H` and its `Make/*` are tracked in git but **not** in the manifest.
- Git also tracks build outputs (`meltPoolFoam/Make/linux64GccDPInt32Opt/*.o`, `*.dep`).
- These are harmless while the CFD backend stays unreachable [Q].

### 1.3 Already done / out of scope

- Worker dispatch table: done.
- GPU archive-validator unification (4 copies): separate plan item.
- `_FIELDS` blob → LFS: needs user approval.
- `python/diagnostics/` move: separate.

None of these is needed for the bump.

## 2. Parity strategy

### 2.1 What "bit-equal" means here

For each golden case, run at the pre-bump HEAD (fingerprint `7482697c…`) and after every bump commit. The comparison object is the result dict with these keys removed:
- `provenance.createdAt`
- `runtime_s`
- worker-only fields when comparing direct `run()` with worker output: `provenance.executionRuntime`, `provenance.runtime_s`, `runKind`, the `input.json` artifact entry
- the `capabilities.json` artifact, which depends on the environment

`provenance.implementationHash` is compared separately: it must change **only** at bump commits and must be the only remaining difference.

Everything else must be **equal byte for byte** as canonical JSON (`sort_keys=True`, `allow_nan=False`):
- every number
- assumptions and labels
- `validationStatus` and `productionReady`
- `coreContract.inputSha256` / `materialSha256` / `solverId`
- the material snapshot and its `materialRevisionSha256`
- each artifact's SHA-256

### 2.2 Feasibility evidence (run here, at HEAD, locked interpreter)

**V1 workflow case** (IN718, 60 W, 1200 mm/s, 80 µm, 200 °C, 20 µm mesh, 600 µm track, powder-layer, reference):
- Two independent runs gave the same stripped-result digest `2f41ba4d0ff6806a…` (one under cProfile, 24.8 s; one plain, 13.3 s).
- `materialRevisionSha256 = 5c9179e9…`, which equals the TS pin in `tests/lpbf-run-workflow-roundtrip.test.ts:136`.
- `coreContract.materialSha256 = 6a8d7bde…`, which equals the STATUS V1 record.
- `inputSha256` here is `be26d954…`, not the STATUS value `fc8325d9…`. The UI request carries more fields, so the parity case must use the archived `inputJson`, not a hand-written request [V].

**In-repo real bare-plate fixture** (`tests/fixtures/lpbf-real-bare-plate-100W-capture.json`, job `7ec9dc57…`, 100 W, 10 mm, 40 µm, corridor):
- Running `run(json.loads(inputJson), artifact_dir=…)` at HEAD reproduced:
  - all **67 field artifacts** (`field-coordinates.bin`, every `field-frame-*.bin`, and the rest) by SHA-256
  - the NPZ **byte-identical** to `tests/fixtures/lpbf-real-bare-plate-100W-section-fields.npz`
  - equal input and material SHAs
- The only leaf differences were the worker-only fields listed in 2.1.
- Each run took 106 s; the run was done twice.
- NPZ output is deterministic: `np.savez_compressed` produced the same bytes 2.2 s apart, because zip entries get the 1980 default timestamp.

### 2.3 Golden case matrix (captured once at `7482697c…`, before any manifest edit)

| # | Case | Exercises | Est. time |
|---|---|---|---|
| G1 | V1 workflow 60 W, from the archived `inputJson` | powder-layer reference, layer-conforming grid, screening analytical comparison | ~15-25 s |
| G2 | Bare-plate 100 W fixture (above) | corridor, NPZ, 67 field artifacts | ~106 s (**slow**) |
| G3 | Short multi-track/multi-layer powder run (stripe and island; dwell; rotation) | `scan_segments`, overlap tracker | < 60 s [A] |
| G4 | Layered-plate `layered-plate-enthalpy-v1` | SS304 support, `lpbf_layered_conduction` | < 60 s [A] |
| G5 | `evaporationModel=True`, short track | the `lpbf_evaporation_marangoni` path | < 60 s [A] |
| G6 | `mode=screening` and `mode=high-fidelity` fallback | Goldak/Rosenthal and honest fallback labels | seconds |
| G7 | Mesh study (`study=mesh`), smallest admissible | study path, failed-fine-mesh behaviour | [A] |
| G8 | Observer paths: final-state, selected-time, local-history, `CpuRunProgress` | the gates being refactored, including error messages for rejected combinations | seconds |
| G9 | Material snapshots | see below | < 1 s |
| G10 | OpenFOAM case generation (no solver run) | file-tree SHA-256 per case | seconds [A: setup functions do not shell out; checked by `rg`] |
| G11 | `lpbf_thermal_solver` / build job | via the existing `test_lpbf_build_job` plus a JSON golden of 3 fixed payloads | seconds |
| G12 | Analytical modules (Eagar-Tsai, Fabbro, Marangoni screening, solidification front) | fixed inputs, JSON digest | < 1 s |

G9 covers:
- `material(n)` for every catalogue name
- `canonical_material_source(a)` for the four alloys
- `thermal_props`, `slicer_props`, `marangoni_props`, `inherent_strain_props`
- `LITERATURE_PV_WINDOWS`, `LITERATURE_MELT_POOL_CASES`, `four_alloy_u95_at_temperature` on a grid
- `four_alloy_thermophysical_db()`
- the IN625 and SS304 snapshots

All of these are serialised **without** `sort_keys` as well, so key order is pinned too.

G10 covers:
- the seven `setup_*_case` functions
- `setup_cfd_multiphysics_case` for one fixed `p`, `m`
- the `lpbf_openfoam` thermal case writer

The GPU (CUDA/Warp) numerics cannot be verified on this machine [A: no CUDA device confirmed]. The rule is therefore: **do not edit `lpbf_gpu_thermal.py`, `lpbf_gpu_thermal_warp.py`, `lpbf_transient_3d_gpu.py` or `lpbf_gpu_pilot_*.py` in this bump.**

Existing oracle suites still run at every step, but they are tolerance oracles, not parity proofs:
- `test_lpbf_production_transient_manufactured` (4)
- `test_lpbf_engineering` (40 plus 1 skip)
- `test_lpbf_build_job`
- `test_lpbf_conduction_manufactured`
- `test_lpbf_layered_conduction`
- `test_lpbf_cfd` (case generation)
- `test_phase6`, `test_phase7`, `test_phase8`
- `test_alloy_registry`
- `test_phase6a_leaf_modules`
- `test_lpbf_implementation_fingerprint`
- `test_lpbf_source_identity`

TS checks:
- `tests/lpbf-real-bare-plate-archive.test.ts`
- `lpbf-run-workflow-roundtrip`, which runs a real CPU job and pins `5c9179e9…` and `enthalpy-fv-6`
- `lpbf-run-bundle`, `lpbf-run-repository`, `lpbf-source-in625-catalog` (pin `f47b07e4…`), `lpbf-nist-comparison-api`
- the full tsx suite

### 2.4 How the bump propagates

| Item | Effect of the bump | Action |
|---|---|---|
| `provenance.implementationHash` (`lpbf_simulation.py:934`; GPU pilots at `lpbf_gpu_thermal.py:746`, `lpbf_gpu_warp_pilot.py:366`) | New runs carry the new hash | expected |
| `VERSION = "enthalpy-fv-6"` (`lpbf_simulation.py:37`) | Part of the fingerprint preimage and of `solverId` / `coreContract` | **Keep unchanged** (numerics identical). Then `coreContract`, `inputSha256` and `materialSha256` stay equal and archives stay comparable [Q] |
| Thermal cache key `fingerprint(p,m)` (`lpbf_simulation.py:251-260`; used in `lpbf_worker.py:949`) | Includes the implementation hash, so old completed jobs no longer give cache hits; old job rows stay readable | none (fail-safe) |
| Legacy broad cache (`_legacy_broad_cache_fingerprint`, 263-274; jobType jobs) | Hashes **all** `python/*.py`, so every prep commit already invalidates build-job/GPU caches | none; note it in the record |
| `test_lpbf_source_identity` `f3cf15f2…` | Unaffected (synthetic vector) | do not touch `lpbf_source_identity.py` |
| `test_phase6a_leaf_modules.test_manifest_has_37_entries` and the leaf guards | Break if the manifest grows or a manifest file imports a registry module | update in the bump |
| `tests/fixtures/lpbf-real-bare-plate-100W-capture.json` | Keeps `7482697c…` as historical data; its tests check only internal consistency | do not rewrite; it becomes the "pre-bump" side of the parity proof |
| Comments in `tests/lpbf-real-bare-plate-archive.test.ts:13-16` cite `lpbf_simulation.py` lines 880 / 524 / 769 / 1091 | Become stale | update the comment in the same commit |
| Diagnostic protocols (`docs/LPBF_FIXED_EVENT_*_PROTOCOL.json`, `docs/LPBF_NIST_3707_TABLE5_PROXY_2026-10-02_PROTOCOL.json`) | Already pin older hashes (`d7e5c4e3…`, `fbef0bde…`, `05ac6db2…` and others) and already refuse to run (STATUS 2026-10-03) | historical; no change |
| `docs/*_SUPPORT/` manifests | Bound to older revisions; none contains `7482697c` (checked with `rg`) | historical; no change |
| Run archive / bundles (`server/lpbfRunRepository.ts`, `lpbfRunBundle.ts`, `lpbfRunImport.ts`) | Never compare `implementationHash` with current code (`rg`). `runIdentity` keys (`lpbfRunRepository.ts:257-259`) do not include `implementationHash` | old archives stay importable, verifiable and restorable |
| IN625 restore (`lpbf_run_capture.py:29`, `material != in625_lpbf_thermal_snapshot()`) | Compares with **current** code | `in625_thermal_material.py` must stay byte-stable in behaviour (G9 plus TS pin) |
| Core-contract restore (`lpbf_core_contract.py:141`) and GPU restore (`lpbf_gpu_thermal.py:156-164`) | Re-derive with current code | do not touch these validators |
| STATUS / PROOF / ROADMAP item 2 ("bind … solver fingerprint") | V1 replay is bound to `7482697c` | new PROOF entry plus the claim run in 2.5; do not edit old entries |
| `.orchestra/claude-lanes-common.txt` frozen value; Agent Memory | Out of date after the bump | update after merge (untracked) |

### 2.5 Claim runs after the merge

- **Required (recommended):** V1 workflow replay at the merge SHA, through the real app (API or UI), then archive it. Acceptance against the `10e3005` record:
  - `inputJson` and `materialJson` byte-identical
  - `materialRevisionSha256 = 5c9179e9…`
  - `materialSha256 = 6a8d7bde…`
  - `resultJson` differs **only** in `createdAt`, `runtime_s` and `implementationHash`
- **Required:** G2 rerun at the merge SHA, with all 67 artifacts and the NPZ byte-identical to the in-repo fixture.
- **Not recommended:** Table 4 case 0 runs. They fail closed at the boiling limit, the status is `unavailable`, and a rerun cannot change that [Q].
- **Bump record:** `docs/LPBF_IMPLEMENTATION_BUMP_<date>.json` containing:
  - `fromHash` (`7482697c…`) and `toHash`, plus `VERSION`
  - the manifest diff (entries added and removed)
  - every golden case's stripped-result digest before and after (equal)
  - artifact digests
  - interpreter and numpy versions
  - commit SHAs

  This is what keeps pre-bump archived runs **traceable** to the new code without rewriting them.

## 3. Risks, stages, effort

### 3.1 Risk ranking

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | The material migration changes snapshot bytes: `materialRevisionSha256`, `materialSha256`, IN625 restore, TS pins `5c9179e9` / `f47b07e4`, the V1 replay comparison | High | G9 golden including key order; keep `MATERIAL_AUTHORITY="four_alloy_materials.py"` and every evidence string; keep Python types (float vs int) |
| R2 | A "harmless" refactor changes floating-point results (re-association, a different interp, erfc) | High | Full stripped-result and artifact parity for G1-G12 at every commit; whitelist only pure hoists |
| R3 | Gate refactor changes error text or check order, so archived failure records or tests diverge | Medium | Exact strings; G8 includes the rejection messages |
| R4 | Touching restore validators breaks backward compatibility for archived runs | Medium | Freeze `lpbf_core_contract.py`, `lpbf_evidence.py` validators, GPU validators and `in625_thermal_material.py` |
| R5 | Closure-test gap: `test_manifest_covers_static_local_python_import_closure` checks only `<module>.py`, so a package import from a manifest file would go unseen | Medium | Use a flat `lpbf_cfd_cases.py`; make the test also detect `<module>/__init__.py` (prep) |
| R6 | GPU paths cannot be verified locally | Medium | Do not edit GPU files |
| R7 | Several intermediate fingerprints exist on the branch | Process | Only the `--no-ff` merge is "the bump"; intermediate hashes are never claimed |
| R8 | Stale line references in docs and test comments | Low | Update the test comment; historical docs stay |

### 3.2 Staged order

**Stage P: prep. Fingerprint stays `7482697c…`. Merge first and review on its own.**
1. P1 **Fingerprint pin.** Add `python/lpbf_implementation_fingerprint.expected` (one line) and a test asserting `implementation_fingerprint()` equals it. Also add a fixed **canonical-v3** framing vector test next to the raw-v2 one. Effort 0.25 d.
2. P2 **Parity harness.** Add `python/tools/capture_lpbf_parity_golden.py`, `python/golden/lpbf_parity/<case>.json` (stripped result, digests, artifact SHA-256, decoded NPZ array digests) and `python/test_lpbf_parity_golden.py`. G2 sits behind a slow flag. Capture twice and prove the two captures are equal. Effort 1-1.5 d.
3. P3 **Material and case-generation goldens.** G9 and G10. Effort 0.5 d.
4. P4 **Guard tests.**
   - The closure test also detects packages.
   - Add "no manifest file imports `lpbf_cfd_cases`".
   - Make the leaf guard data-driven (allowed manifest set listed in one place).

   Effort 0.25 d.
5. P5 **Non-manifest dead code.** Remove `LaserSourceConfig` and the duplicate `test_09`. Effort 0.1 d.

**Stage B: bump branch. One branch; small commits; each commit passes the gates in section 3.3; merged once.**
1. B1 Move the test-only `lpbf_cfd` code (2313 lines) to `lpbf_cfd_cases.py`. Update `test_lpbf_cfd` imports. G10 file trees must be equal. Effort 0.5 d. Mechanical work (Sonnet-level) with Opus review.
2. B1' [Q] Remove the unreachable `use_cfd` branch (`lpbf_simulation.py:883-893`) and drop `lpbf_cfd.py` from the manifest. The CFD code then becomes experimental and non-manifest. Effort 0.25 d. Opus.
3. B2 Remove `evaluate_material_properties`. Effort 0.1 d.
4. B3 Observer-gate helper (six sites). Effort 0.5 d. Opus.
5. B4 (optional) Pure hoists (`T.max` reuse, boiling enthalpy, table array). Effort 0.25 d. Opus; skip it if any digest moves.
6. B5 Material authority migration (section 4). Effort 2-3 d. **Fable-level care** (provenance honesty, byte identity) with Opus.
7. B6 Bookkeeping:
   - update the `.expected` pin
   - update the manifest count and leaf guard
   - fix the test comment line numbers
   - add the bump-record JSON
   - add the PROOF entry and STATUS

   Effort 0.5 d.

**Stage C: after the merge.** Claim runs (2.5): V1 replay archive and G2 at the merge SHA. Then the lane file and memory update. Effort 0.5 d.

Total about 6-8 working days including two independent reviews (Opus plus a second reviewer).

### 3.3 Gates for each bump commit

- Every B commit: `python -B tools/lpbf_parity_check.py --check --expect-unpinned` (fast cases).
  Only the fingerprint/pin mismatch is a warning on the bump branch; every observation diff
  fails. Add `--slow` (G2, real bare-plate fixture) at **B1, B3, B4, B5 and B6**. At B6, after
  re-pinning, run `--check --slow` without `--expect-unpinned`.
- `test_lpbf_implementation_fingerprint_pin` is red on the bump branch from the first B commit
  until B6 re-pins it, so Phase B merges to main only as ONE atomic merge after B6.
- B6 writes the bump record with
  `tools/lpbf_bump_record.py --from-revision <pre-bump sha> --with-parity-check --slow`.
- All parity commands run in the recorded environment; a SKIP is not a PASS.
- `test_lpbf_implementation_fingerprint`, `test_lpbf_source_identity`, `test_phase6a_leaf_modules`, `test_alloy_registry`.
- `test_lpbf_engineering`, `test_lpbf_production_transient_manufactured`, `test_lpbf_build_job`.
- `test_lpbf_cfd`, `test_phase6`, `test_phase7`, `test_phase8`.
- `npx tsc --noEmit`, the TS LPBF tests above, then the full tsx suite at B6.
- `git diff --stat docs/` shows only the new bump record and PROOF entry.

## 4. Material authority migration contract

### 4.1 Options

- **A (literal): `four_alloy_materials` imports `alloy_registry`.**
  - The closure forces `alloy_registry.py`, `physical_constants.py`, `alloy_data_kinetics_uq_fatigue.py` and `alloy_data_calphad_battery_icme.py` into the manifest. `alloy_registry.py:56-57` and `597` / `713` import them.
  - The import becomes circular, because `alloy_registry` imports `four_alloy_materials`.
  - Every later non-LPBF registry edit (kinetics, corrosion EW, fatigue) would then bump the LPBF fingerprint. **Not recommended.**
- **C (recommended): split a manifested core out of the registry.**
  1. Create `python/alloy_registry_core.py`: stdlib only, manifested, +1 entry, so 38 total.
     - It holds `SOURCE_TYPES`, `Validity`, `ValueRecord` and the unit maps for the LPBF domains.
     - It holds the **four locked alloys' value tables** as the single numeric source: `lpbf_thermal`, `marangoni`, `inherent_strain` and `pv_window` records.
  2. `four_alloy_materials.py` becomes a **view**. At import it materialises the same public objects from the core records:
     - `_THERMAL`, `_MARANGONI`, `_ISM`, `LITERATURE_PV_WINDOWS`, `FOUR_ALLOY_IDS`, `THERMAL_NAME`, `SLICER_NAME`, `ALLOY_MATERIALS`, `_ALIAS`
     - every function, unchanged in signature and behaviour
     - plain dicts with the same key order and the same Python types
  3. `alloy_registry.py` (not manifested) projects the four alloys from `alloy_registry_core` instead of from `four_alloy_materials`. This removes the reverse dependency. Secondary domains stay outside the fingerprint.

  This keeps "one numeric source plus typed provenance per value" inside the LPBF core. Non-LPBF registry edits then do not touch the LPBF fingerprint.

### 4.2 Hard constraints (parity and honesty)

1. **Byte identity of the snapshots:**
   - `canonical_material_source(a)` digests unchanged; this needs `MATERIAL_AUTHORITY == "four_alloy_materials.py"` and `MATERIAL_AUTHORITY_SCHEMA_VERSION == 1`.
   - `material(n)` output unchanged, including `source="Existing four_alloy_materials.py / lpbf_thermal_solver.py; endpoint provenance not independently verified"`, `quality="estimated"`, `provenanceClass="estimated-legacy"`, `version="lpbf-materials-1"`, `materialAuthority`.
   - So `materialRevisionSha256` (`5c9179e9…` for IN718) and `coreContract.materialSha256` (`6a8d7bde…`) stay as they are.
   - Any change to these strings is a **scientific-wording change and needs the user's decision** [Q].
2. **source_type honesty.** All four-alloy values stay `estimated`, matching `alloy_registry._record` today (`alloy_registry.py:299-301`) and RULES.md section 2:
   - Identifiers such as `LITERATURE_PV_WINDOWS` and `LITERATURE_MELT_POOL_CASES` keep their names for API stability.
   - Their records must not be relabelled `literature` without a per-value citation in `source_ref`.
   - `validity=None` means "no stated range".
3. **No new values and no silent fallback.**
   - `resolve_alloy_id` returns `None` for unknown names exactly as today.
   - Unknown names still raise wherever they raise today.
   - `alloy_registry`'s stricter resolver stays a separate API.
4. **Mutability unchanged.** `thermal_props()` returns the module-level dict object, as it does now. Switching to `MappingProxyType` is deferred, because whether any consumer mutates it is not checked [A].
5. **Scope.** In this bump these stay where they are: `LITERATURE_MELT_POOL_CASES`, `FOUR_ALLOY_U95_BUDGET` and `SECONDARY_THERMOPHYSICAL_DB` (`lpbf_thermal_solver.py:32-159`, imported by `lpbf_material_registry.py:15`). Option 4.5 covers moving the secondary table.
6. **Tests:**
   - Key-by-key and type-by-type equality between the view and the core.
   - `test_alloy_registry` digest test still green.
   - Leaf guard updated: core allowed in the manifest; `alloy_registry`, `physical_constants`, `input_validation` and the `alloy_data_*` modules still forbidden in manifest files.
   - G9 golden equal.
   - `REGISTRY_VERSION` → `alloy-registry-3` only if registry metadata (`source_ref` strings) changes.

### 4.3 Out of scope for the bump

Moving free solvers (Phase 6a steps) and adding new alloys or values.

### 4.4 Effort and care

2-3 days. Fable-level care on the provenance labels and byte identity; Opus implements; two reviewers.

### 4.5 Optional, value-identical

Move `SECONDARY_THERMOPHYSICAL_DB` into the core as well, so that `lpbf_material_registry` stops importing a solver module for data. This adds G9 coverage for the secondary names [Q].

## 5. Open questions for the user

1. **Claim runs.** Re-record only the V1 60 W replay plus the G2 bare-plate parity rerun after the bump? Or also attempt Table 4 case 0 (expected: closed fail at boiling, status stays `unavailable`)?
2. **Archived pre-bump runs.** They remain importable, verifiable and restorable unchanged (verified: no current-hash comparison exists). Is a bump-record JSON (old → new hash with parity digests) enough? Or should the UI also flag "computed by previous implementation `7482697c` (parity-attested)", which is a new feature outside the bump?
3. **`VERSION` / `solverId`.** Keep `enthalpy-fv-6` (recommended; numerics identical)?
4. **CFD.** Only move the test-only code (B1)? Or also delete the unreachable `openfoam-cfd` branch and drop `lpbf_cfd.py` from the manifest (B1')?
5. **CFD material constants.** Separately, should the hard-coded CFD metal constants (`rho 4000`, `k 30`, `cp 500` and the others) be replaced by registry values later (scientific change, own drift record) or the CFD path be retired?
6. **`in625_gpu_thermal_material.py`.** It has no production importer. Keep it in the manifest or drop it?
7. **meltPoolFoam sources.** Should the OpenFOAM meltPoolFoam sources join the manifest? Should the tracked `.o` / `.dep` build outputs be removed (needs deletion approval)?
8. **Material migration shape.** Option C (manifested `alloy_registry_core.py`, so `four_alloy_materials` is a view) instead of a literal import of `alloy_registry`?
9. **Wording.** Keep the material evidence strings byte-identical, even though the numbers will physically live in the core module? Changing them changes `materialRevisionSha256` for every alloy.
10. **Bit-changing speed-ups.** Vectorised erfc and shared interpolation index are expected to give larger gains than the cleanup items. They stay out of this bump; do you want them later as a separate, explained-drift change with new claim runs?
11. **Campaign identity.** `runIdentity` in proxy campaigns does not bind `implementationHash` (`lpbfRunRepository.ts:257-259`). Should a campaign be forbidden from mixing pre- and post-bump runs?

## 6. Explicitly not in this bump

- Bit-changing performance work: vectorised `erfc` or source quadrature, a custom interpolant, GPU device-side step limiter.
- New physics.
- Evidence-label or status changes.
- Edits to restore validators or GPU files.
- Rewriting historical docs, fixtures or PROOF entries.

## 7. Verification log (this design session)

All commands ran in `C:/Users/can02/Projects/metalliksaa/Metalliksa-1-orch-p5c-design/python` with `PYTHONDONTWRITEBYTECODE=1` and the locked `.runtime/lpbf-win-py312` interpreter, using `-B`.

- `python -B -c "from lpbf_simulation import implementation_fingerprint as f; print(f())"` → `7482697c458b6c1aa2a77829f2fbce0c4ce4ac9466e9a3583e97b9a799b5e483`.
- `python -B -m unittest test_lpbf_implementation_fingerprint test_lpbf_source_identity test_phase6a_leaf_modules test_alloy_registry` → `Ran 68 tests … OK (skipped=1)`.
- numpy `2.2.6`; `inspect.signature(numpy.interp)` → `(x, xp, fp, left=None, right=None, period=None)`.
- V1 60 W case: two runs, stripped digest `2f41ba4d0ff6806a` both times; profile as in 1.2(b).
- Bare-plate fixture rerun (twice, 106 s each): every reference artifact equal except the worker-written `input.json` (absent in a direct `run()`); NPZ byte-identical to the fixture; leaf diffs only in `provenance.executionRuntime`, `provenance.runtime_s` and `runKind`.
- NPZ determinism: identical bytes 2.2 s apart.
- Not run: the full Python or TS suites, GPU tests, OpenFOAM (no compiled OpenFOAM), browser. No product code was changed.

## 8. Stage P as implemented (orch/p5c-prep)

- Parity cases (`python -B tools/lpbf_parity_check.py --list`): G1 V1 replay (equal to the
  archived 066b6b9 run), G2 real bare-plate fixture (slow), G3 stripe/island/meander/
  unidirectional, G4 layered plate, G5 evaporation, G6 screening and fallbacks, G7 mesh and
  timestep studies, G8 observers and rejection messages, G9 materials, G10 OpenFOAM case
  writers, G11 build-job melt pool, G12 analytical modules, G13 source-quadrature
  refinement, G14 calibration, G15 square bare plate with opticalObserver, G16 non-IN718
  transients, NPZ determinism.
- B5 step 2 (orch/b5-goldens): all goldens re-recorded twice at `edddf0dc…` in a commit of
  their own (observations unchanged; only the recorded hash, git head and timings moved).
  New cases recorded at `edddf0dc…` document today's behaviour for the corrected-physics bump:
  - G17 `evaporationModel=True` for Ti-6Al-4V and 316L (80 W) and AlSi10Mg (500 W), all at
    the default Marangoni multiplier and speed. (AlSi10Mg does not boil at 400 W on the small
    grid; at 600 W its maximum vapour fraction saturates at 1.0 for both L_v values, at 500 W
    it does not.) Every alloy passes IN718's 6.4e6 J/kg to the enthalpy inversion (authority:
    8.9e6, 6.25e6, 1.05e7). A harness-side probe with the authority value gives a bit-equal
    result: the inversion's vapour fraction is discarded, so today L_v does not reach any
    result byte; the D1 fix should drift only `evaporation.latentHeatVapUsed_J_kg` and
    `evaporation.maxVaporFraction`. The probe wraps today's call shape; a bump that changes
    the call must update the wrapper in the same branch (an unknown shape is recorded as a
    note, not a crash).
  - G18 IN625 fusion latent heat per path: the Rosenthal melt-pool path
    (`calculate_meltpool_physics`) uses 260 kJ/kg, the screening snapshot 290 kJ/kg, the
    transient specification 227 kJ/kg. The build job resolves only the four alloys
    (`resolve_alloy_id("Inconel 625")` is None), so it never reaches the 260 kJ/kg table.
  - G19 the registry emissivity literal 0.35 echoed into `p`/`m` for every alloy, the override
    bounds, and the core-contract rejection of a 0.36 override after the solve.
  - The silent `resolve_alloy_id(...) or "in718"` P-v fallback stays pinned by G9.
  None of the NOT COVERED items below was closed by these cases. `recordedGitHead` is the
  HEAD at recording time; for goldens recorded from a working tree it may predate the case
  code (G17-G19 were re-checked bit-equal at their committing HEAD).
- Planned drift (for the corrected-physics bump): `--check --expect-drift ENTRY[,ENTRY...]`
  and `tools/lpbf_bump_record.py ... --expect-drift` (same semantics). ENTRY is `CASE` or
  `CASE:KEY_GLOB` (fnmatch on the observation key).
  - Only matched observations may drift (status DRIFT, before -> after values, and leaf-level
    raw values from the golden's `rawValues`, the pre-hash value of small digest observations;
    never compared). Every other diff fails; pin, implementationHash and golden problems fail.
  - An entry that matches no drifted observation, or names a case that is not run, is stale
    and fails.
  - Identity digests (`*materialRevisionSha256*`, `*materialSha256*`, `*inputSha256*`) fail in
    every case unless an entry names that exact key.
  - G1, G2 and G4 (reference transients) are refused as whole cases; their numerics (metrics,
    thermalHistory, energyBalance, field*, artifacts, NPZ, fixture equality) fail whatever
    the allowlist. Named G1 observations such as `result.key.analyticalComparison`, the two
    whole-result digests and `v1Archive.strippedResultEqual` can be allowed one by one.
  - With `--allow-environment-mismatch` a drift run ends DIAGNOSTIC (exit 3), never PASS.
  - After the merge, the drifted goldens are re-recorded at the new fingerprint in a commit
    of their own.
- Valid only in the recorded environment (Python, numpy, OS, locked runtime, CPU brand,
  numpy SIMD dispatch, BLAS); elsewhere every case is SKIP and `--check` exits 3. Not in CI.
  CI runs `test_lpbf_implementation_fingerprint_pin`, `test_lpbf_implementation_fingerprint`
  and `test_lpbf_source_identity`.
- **NOT COVERED** by the goldens (B commits touching these need their own evidence):
  - GPU numerics (`lpbf_gpu_*`, `lpbf_transient_3d_gpu.py`, `warp_thermal_solver.py`,
    `powder_bed_raytracer.py`, the IN625 CUDA adapter).
  - OpenFOAM execution (`lpbf_openfoam.thermal()`, `cfd_multiphysics()`,
    `metalliksaThermal.C`); only case generation is pinned. Also `backend="auto"` with the
    `openfoamThermal` capability.
  - `setup_cfd_multiphysics_case` beyond the powder-packer `NotImplementedError`.
  - User-supplied material properties.
  - Layered plate with `isothermal-at-preheat` support boundary or a non-zero incidence
    azimuth.
  - Worker-side consumers of `opticalObserver` / NIST section operators (not in the manifest).
  - `CpuRunProgress` source-work budget failures.
  - G11 and G18 when `warp` is installed: they are skipped.
