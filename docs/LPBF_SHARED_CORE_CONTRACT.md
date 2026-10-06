# Shared LPBF core contract

This is the incremental design following the dated [core baseline](archive/LPBF_CORE_BASELINE_2026-09-21.md).
The authorized goal is shared LPBF physics/data integration. The initial audit stays open;
this contract does not qualify a model, accept later phases or enable old GPU CFD.

Implemented first deliverable: `python/lpbf_core_contract.py`, attached by `run`
and checked by the evidence boundary on new/restored results. Client checks
structure/model consistency, not cryptographic SHA binding. Python8PASS;
WSL core/engineering/source/peak/overlap54PASS with actual OpenFOAM and no skips.
Prechange40W numerical sections and64artifact hashes are unchanged.
This is a consistency binding, not a signature or protection against a party
rewriting both data and hashes. Genuine legacy absence is intentionally accepted;
the future run importer must label it explicitly and never silently upgrade it.

## First deliverable: bound thermal result identity

Add optional `coreContract` to existing schemaVersion1 results without changing
numerics or the legacy fingerprint. New solver results always include it. Older
saved results remain readable as legacy records with no inferred contract.
Do not synthesize a contract on read or silently upgrade an old cache entry.

Contract v1 binds `settings`, the entire resolved `material` object, solver ID,
effective mode and requested backend. SHA256 uses Python JSON with sorted keys,
compact separators, UTF-8, ASCII escapes and nonfinite rejection. This hash
format is explicitly versioned; it is not a cross-language canonical-JSON claim.

Fields: `schemaVersion:1`, `modelId`, `actualBackend`, `requestedBackend`,
`effectiveMode`, `solverId`, `inputSha256`, `materialSha256`, `units`,
`resolvedPhysics`, `evidenceClass:'unvalidated-model'`.

Allowlisted mapping:

| Effective mode / solver | Model / actual backend |
| --- | --- |
| screening / rosenthal+goldak | analytical-conduction-screening-v1 / analytical |
| standard or calibration / enthalpy-fv-6 | stationary-enthalpy-conduction-v1 / numpy-reference |
| standard or calibration / metalliksaThermal-OpenFOAM14-6 | stationary-enthalpy-conduction-v1 / openfoam-thermal |

Requested high-fidelity that falls back to screening uses the first row. Requested
backend `auto` does not identify execution; actual solver identity does. Unknown
solver/mode combinations fail instead of receiving another model's contract.
Thermal requested reference/openfoam must agree with actual backend; analytical
screening may ignore a thermal backend request, explicitly reported in the result.

Units describe the resolved settings boundary: power W, speed mm/s, length um,
preheat degC; internal temperature K, distance m, time s, energy J; beam diameter
`1/e2-intensity`. Physics flags: analytical or transient conduction, latent heat
only for transient; momentum/freeSurface/evaporation false for both. Boundary
details remain existing assumptions; material source/quality is preserved.

Before publication and on restore, recompute this contract from the result and
require exact equality when present. Null, unknown version, changed material,
changed settings, forged backend/model/evidence/units are errors. Absence is a
legacy state, not a verification pass. Keep existing energy/mass/phase checks.

## Next persistence deliverable (separate package)

Introduce a run record around the existing worker result, without a second job
queue. Persist immutable resolved input/material/result snapshots and explicit
links to `{datasetId, revision, documentSha256}` in the source repository.
Referenced source identity must exist unchanged, but its unreviewed scientific
status stays unreviewed. Capture execution/backend/library/source hashes and
artifact manifests separately from scientific evaluation.

The worker owns execution lifecycle. Node owns durable publication and source
links after a completed result passes parsing, contract verification and byte
checks. Publish metadata only after all referenced bytes exist; failed import
must not create a completed run. Use expected-revision conflict semantics and
the existing immutable byte store. Simulation records are not Sample measured
Properties. Qualification links retain Build→ProcessParams→Sample→Properties→Source.

Legacy import is explicit dry-run→new immutable record, preserving original
provenance and a `legacy-unbound` status. Never invent missing input/material/
source links or overwrite live records. Full run bundles must include result,
resolved settings/material, all output artifacts and exact source revisions;
restore to a new directory and reject missing/modified bytes. Existing source-only
bundles remain source-only. UI integration needs current-input identity, visible
unavailable state, no implicit activeSpecimen mutation and actual browser checks.

## Shared physics extraction and GPU boundary

Extract existing material, SI adapter, scan schedule, cell-integrated source,
enthalpy and boundary/audit functions incrementally behind the above identity.
First freeze parity fixtures, then move a single seam, rerun numerical suites and
compare operator/units/model identity. Do not replace analytical specialist laws
with transient laws under an unchanged model ID. Their material adapters may
reuse data while keeping explicit property temperature/optical conventions.

Extraction checkpoint (2026-09-23): `lpbf_core_physics.py` exposes shared
material interpolation, enthalpy, mesh-domain, scan-schedule, and cell-integrated
Gaussian source APIs. `lpbf_simulation.scan_segments` and the old
`lpbf_heat_source` names remain import-compatible; timestep limiting and the
conduction operator remain in `lpbf_heat_source`. Solver diagnostics use the
shared `cell-integrated-gaussian-gl2-v1` identity. Both extractions moved existing
implementations without equation, timing, unit, or quadrature changes.
Verification after the source extraction: core-contract, engineering and
heat-source suites passed 40 of 42 tests on Windows Python3.12; two
OpenFOAM/Linux-only cases were skipped there. OpenFOAM 14 reference parity and
all eight heat-source tests passed on Ubuntu 22.04 WSL with the compiled worker.

Material snapshots now add `materialId`, `provenanceClass`,
`materialIdentitySchemaVersion`, and `materialRevisionSha256`. The revision
digest covers the complete normalized material snapshot before the digest field
is added. `coreContract.materialSha256` continues to bind that complete object.
Supplied property objects have their identity metadata discarded and recomputed
for the requested alloy. Legacy snapshots without a revision digest remain
accepted. These hashes identify content; they do not establish source integrity,
experimental provenance, or scientific validation. Legacy estimates are marked
`estimated-legacy`; supplied tables are `user-supplied-unverified`; the result
contract remains `evidenceClass='unvalidated-model'`.

The reference transient solver and thermal OpenFOAM adapter now share
`thermal_si_inputs(p, material)` for preheat K, layer m, scan speed m/s, and
absorbed power W. The analytical screening route retains its own assumptions;
the separate free-surface CFD route is outside this conversion seam. The
conversion-only change preserves the existing solver equations and model IDs.

GPU candidate is a thermal-only implementation of the same stationary reference
contract. Require explicit device, no silent fallback, equal scenario/material/
source/boundaries, timestep/mesh studies, energy closure and CPU comparisons
before speed claims. The existing Warp flow prototype does not satisfy this
contract and remains isolated. Calibration ambiguity does not block these
independent numerical tasks. No temperature conversion is guessed for NIST.

## Build-job alloy identity boundary

The build-job route accepts only the four locked alloy identities through an
exact normalized alias allowlist and checks that the specimen base metal agrees.
Unsupported, contradictory, or compound specimen identities do not submit a
surrogate. Python validates explicit thermal and slicer material names against
the resolved alloy before cache lookup, then passes canonical names to both
solvers and canonicalizes those fields in the cache key. For backward
compatibility, an omitted or blank `alloyId` still
defaults to IN718. This is an identity-consistency guard; it does not yet bind
the worker result to a complete resolved thermal/slicer property snapshot or
establish scientific provenance. The shared thermal-registry revision digest
does not apply to build-job properties.
