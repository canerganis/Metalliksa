# LPBF build-job and archive workflow validation — 2026-09-24

## Scope and result

This is a validation record for the browser/API path from LPBF selection and computation through evidence comparison and durable archive export/restore. It does not establish scientific validation or change any acceptance threshold.

**Status: partial; full browser workflow did not pass.** The API/client/archive tests passed with synthetic fixtures, and the browser showed one real archived transient run with intact material, source, and artifact identities. The selected NIST comparison correctly remained unavailable because the archived process does not satisfy its predeclared case requirements. The browser build-job re-run failed with `'timeout_s'`; the active browser service could not be tied to this checkout, so this is recorded as a runtime compatibility failure requiring root-level triage, not assigned to current product code.

## Automated checks

Running `npx tsx --test ...` failed before executing test bodies because Node's test runner could not spawn workers (`spawn EPERM`, Windows sandbox). Importing the same test modules into one Node process avoids that runner limitation:

```powershell
node --import tsx -e "await import('./tests/lpbf-workflow.test.ts')"
node --import tsx -e "for (const f of ['./tests/lpbf-build-session.test.ts','./tests/lpbf-source-api.test.ts','./tests/lpbf-source-client.test.ts','./tests/lpbf-run-client.test.ts','./tests/lpbf-run-bundle-api.test.ts','./tests/lpbf-run-archive-service.test.ts','./tests/lpbf-run-repository.test.ts']) await import(f)"
```

Results: **6/6 workflow tests PASS; 51/51 build-session, source, run-client, bundle HTTP, archive-service, and repository tests PASS.** The fixtures cover alloy mapping/refusal, request/revision binding, exact source-revision links, immutable run and material/input snapshots, artifact integrity, export/verify/isolated restore, and tamper rejection. They do not exercise one mounted browser session from selected alloy through a real build-job and reload.

## Browser observations

Local UI `http://localhost:3000/?lpbfStage=comparison#/3d-distortion-lab` loaded in the Codex in-app browser. Existing UI state showed Inconel 718, 30 W, 1200 mm/s, 100 µm hatch, and 40 µm layer.

- The archived run `e8e26ffea4784e6288f7ddab5839de01` loaded from the UI as `core-v1-bound`, `unvalidated-model`, and `exact-revision-bound`.
- Its input snapshot records Inconel 718 and the executed 30 W / 1200 mm/s / 80 µm beam process. Its material snapshot records `materialId: in718`, `provenanceClass: estimated-legacy`, and revision SHA-256 `c90d2094ca2b5162b26399347a6fb0f9d703b1a05e8aa0883d9d9672012e8c06`.
- The run retained NIST source revision 1 with document SHA-256 `b312cc286ccf7cd41c2ff8bc2bea3c0cf183af432125f402dfbebdf71b235ee0`, plus a manifest of hashed run artifacts.
- **Compare archived run** completed and returned “Comparison unavailable · unvalidated.” Reported gates included the required 10 mm +X bare-plate track, selected Table 4 power/speed, measured beam identity, the optical section operator, and 3–6 independent mesh and timestep levels. This correctly avoids treating an unrelated short transient run as an experimental comparison.
- On the build-job screening stage, **Re-run Python** returned the literal error `'timeout_s'` and UI guidance to restart the Express app if the build-job route is missing. This prevented verification of selected-alloy build-job result identity in the live UI.
- The checked source files `src/store/useLpbfBuildJobStore.ts`, `python/lpbf_build_job_schema.py`, and `python/lpbf_build_job_solver.py` contain no `timeout_s` reference. The browser service therefore may be stale or from a different checkout; its error is not evidence by itself of a defect in the current source tree.

## Current integration boundary

The durable run archive now labels captures as `build-screening` or
`transient-thermal`; old v1 captures remain readable as `legacy-unspecified`.
Build-job classification is bound to the worker result plus captured
`settings.jobType`, and the NIST optical gate stays unavailable for current and
legacy build-job results. The archive UI displays the kind. Focused tests cover
real queue execution through capture, preview/import classification,
get/list, and bundle kind preservation through restore. They do not yet prove a
single live selected-build-job browser session all the way through evidence
comparison, bundle export, isolated restore, and reloaded display.

## Current-checkout follow-up

The root agent reproduced the worker failure using a server started from this
checkout on port 31893. `Queue.execute` indexed `params["timeout_s"]` although
the build-job request schema does not supply that field. The worker now applies
a bounded 300 s default (`python/lpbf_worker.py`); the focused regression passed
1/1. Two actual HTTP submissions to the current route `/api/lpbf/jobs` then
completed as `in718`, each carrying property snapshot SHA-256
`eee84712f32c3b9c5882f4e18176e1321233fb19c8ca6347667f378862e1995a`.
The Python queue capture helper also produced a byte-verified capture for one
completed build job, labeled `legacy-unbound`; the run/source repository import,
export, and isolated restore path has not been exercised for this result.

The browser observation used the old `/api/python/lpbf-build-job` route and a
different local service. Current checkout API execution and the separate
build-screening archive contract are now verified. The combined selected UI
workflow through bundle export/isolated restore/reload remains open.
