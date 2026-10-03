# Application packaging and CI notes

Status: DRAFT, written against commit 95a9e43. The local Windows dry-run at the current CI draft is recorded in [CI_DRYRUN_REPORT.md](CI_DRYRUN_REPORT.md). No workflow ran on GitHub, Docker was not run, and no test suite was run on Linux. The Windows run does not establish Linux or GitHub Actions behavior.

## Files

- `.github/workflows/ci.yml`: `node` job (Node from `.nvmrc`, Python 3.12 with the CPU pins, `npm ci`, `npm run lint`, unit tests, `npm run build`) and `python` job (3.11 and 3.12, CPU pins, `npm run test:meltpool`; `test:lpbf:engineering` runs with `continue-on-error`). It never installs `python/requirements.txt` because that pulls torch.
- `scripts/ci-unit-tests.txt`: exclusion list. The unit tests are the `tests/*.test.ts` and `tests/*.test.tsx` glob (same as `npm run test:unit`) minus the files listed there. The workflow and the `verify` Docker stage apply the same shell snippet.
- `.nvmrc`: Node 24 (the Dockerfile uses Node 24; `node:sqlite` tests need at least Node 22.13 without flags).
- `Dockerfile`, `.dockerignore`, `docker-compose.yml`: multi-stage draft (Node 24 + Python 3.12).

## Test exclusions (read from source on 95a9e43)

94 test files match the glob. One is excluded (93 files run):

- `tests/lpbf-worker-delete-integration.test.ts`: starts the real `python/lpbf_worker.py` and relies on process-tree reaping of an execution child and grandchild. Its Python import closure beyond numpy, scipy and pydantic and its Linux behaviour are unverified.

Files that mention Python, WSL, sqlite, GPU or external data and stay in, with the reason:

- `lpbf-worker-readiness.test.ts`: the "WSL" cases only use fake command names; the child processes are `node -e` protocol fixtures, so it is valid on Linux.
- `python-runtime.test.ts`, `python-status.test.ts`, `lpbf-archive-paths.test.ts`: platform is passed as a parameter (`win32` and `linux`) and the probes are fakes.
- `lpbf-gpu-artifact-reader.test.ts`: the cross-language case runs `python` with numpy from `python/lpbf_gpu_pilot_artifacts.py`; the CI Node job installs the CPU pins for it. The other GPU tests use tracked fixtures under `docs/LPBF_GPU_NATIVE_WORKER_ACCEPTANCE_RETRY_2026-09-27/`, which are tracked.
- `lpbf-phase5-defects.test.ts`, `lpbf-source-in625-catalog.test.ts`: run `python` against stdlib-only modules, so `python` must be on `PATH` (it is in both CI and the image).
- `lpbf-sqlite-compatibility.test.ts`, `lpbf-run-repository.test.ts`, `lpbf-source-repository.test.ts`: use `node:sqlite` (Node >= 22.13).
- `lpbf-phase4-e2e.test.ts`: skips itself unless the gitignored `data/benchmark/cmu-ti64-meltpool-v1/raw` payload is restored, which it is not in CI.
- `module-inventory.test.ts`: reads `docs/MODULE_EVIDENCE_INVENTORY.md`, which is tracked (confirmed with `git ls-files`).
- Tests that read `data/benchmark/*` (nist-amb2022-03, nist-amb2022-03-optical, nist-mds2-2923-in718/official, in625-bareplate-screening): the files they read are tracked.

The local Windows dry-run found no evidence to add exclusions. The first Linux run may still reveal platform-dependent tests that cannot be found by reading the source, for example the symlink tests in `lpbf-artifact-store.test.ts` and the Vite/HMR tests.

## Blocking prerequisite: Linux Python lock

`python/requirements-lpbf-win-py312.lock` is Windows-only. The Dockerfile references `python/requirements-lpbf-linux-py312.lock`, which **does not exist** and **must be generated first** on Linux x86_64 with CPython 3.12 (for example `pip-compile --generate-hashes python/requirements-lpbf.in`), reviewed, and committed. Until then `docker build` fails at the `py-deps` stage. CI does not use this lock; it installs the exact pins from `python/requirements-lpbf.in`, which was also not run.

## Container behaviour (UNVERIFIED)

- Targets: `verify` (lint, unit tests, build, three CPU meltpool Python tests) and `runtime` (default; copies `dist` from `verify`; non-root uid 10001). `python/test_lpbf_engineering.py` is not in `verify` because its Linux status is unproven; it runs only as a non-blocking CI step.
- Writable paths for the non-root user:
  - Redirected to the `/data` volume: `METALLIKSA_LPBF_SOURCE_ROOT`, `METALLIKSA_LPBF_RUN_ROOT`, `METALLIKSA_LPBF_BUNDLE_ROOT`, `METALLIKSA_JOB_ROOT` and `RESEARCH_REGISTRY_DIR` (variable names read from `server/lpbfSourceArchiveService.ts`, `server/lpbfRunArchiveService.ts`, `server/lpbfRunBundleService.ts`, `python/lpbf_worker.py` and `server/researchEvidenceRegistry.ts`).
  - Relative defaults created in `/app` and chowned to the app user, so they also work if the variables are unset: `.lpbf-sources`, `.lpbf-runs`, `.lpbf-run-bundles`, `.lpbf-jobs`, `.research-registry`, `.runtime`, `.lpbf-surrogates`.
  - `python/` is copied owned by the app user so `python/tmp*` scratch directories can be created. `PYTHONDONTWRITEBYTECODE=1` is set.
- `.lpbf-surrogates/` is tracked (`.lpbf-surrogates/in718_rf_model.pkl`) and is read and written, relative to the working directory, only by `python/phase9_surrogate.py`. That module is imported by offline scripts and tests, not by the server, and it imports `sklearn` and `joblib`, which are absent from the `python/requirements-lpbf-*.lock` files (only `requirements.txt` and the scientific cu128 lock list them). The directory is still copied and not excluded in `.dockerignore`, but it is inert in the runtime image unless scikit-learn is added. The `.lpbf-jobs`, `.lpbf-runs`, `.lpbf-sources`, `.lpbf-run-bundles` and `.research-registry` directories are untracked and excluded.
- `.dockerignore` also excludes tracked agent tooling directories (`.agents`, `.claude`, `.cursor`, `.gemini`, `.github`, `sonkayıtlar`) and the stale tracked `python/__pycache__` files for CPython 3.10 and 3.11. It deliberately does not exclude `*.log`, because tracked evidence logs live under `docs/`.
- Compose: `app` on port 3000 with a healthcheck on `/api/python/status` (route in `routes/physics.ts`); it passes only if that route returns a 2xx status, which depends on Python readiness. The `repro` profile only builds the `verify` target.
- Runtime image contents besides `dist` and `node_modules`: `python/`, `data/`, `assets/`, `docs/sources/in625/` (about 18 MB; resolved from the working directory by `server/lpbfPropertySourceCatalog.ts` and archived by `server/lpbfSourceArchiveService.ts`) and `.lpbf-surrogates/`. Other relative-to-cwd paths read by the server: `python/persistent_ipc_service.py` and other Python scripts (`server/processOrchestrator.ts`), `dist/` (`server.ts`), and `data/benchmark/*` plus `data/collected-sources` (`server/lpbfSourceCatalog.ts`, `server/approvedSourceCollector.ts`). `spparks/` and the rest of `docs/` are not read by `server/*.ts` (grep checked) and are not copied.
- GPU, WSL and OpenFOAM paths are out of scope for this image.
