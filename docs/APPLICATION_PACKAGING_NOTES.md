# Application packaging and CI notes

Status: DRAFT, written against commit 95a9e43 and updated on 2026-10-04 with the first Docker run (see "Docker verification" below). The local Windows dry-run at the current CI draft is recorded in [CI_DRYRUN_REPORT.md](CI_DRYRUN_REPORT.md). No workflow ran on GitHub. The Docker `verify` target is green in a linux/amd64 container on a Windows host. The runtime image's start crash was fixed on branch `orch/prod-start-fix`, and the image now serves `/api/health` on a published port (see "Runtime start" below). Neither establishes GitHub Actions behavior.

## Docker verification (2026-10-04)

Docker Desktop 4.91.0, Engine 29.8.0, BuildKit v0.33.0, linux/amd64, Windows 11 host. Branch `orch/docker-verify`. Base images `node:24-bookworm-slim` and `python:3.12-slim-bookworm` (CPython 3.12.15, Node 24.21.0).

- `docker build --target verify -t metalliksa-verify:local .`: **PASS**. `npm ci`; `pip install --require-hashes -r python/requirements-lpbf-linux-py312.lock` (numpy 2.2.6, scipy 1.15.3, pydantic 2.13.5); `npm run lint`; unit tests on 114 of the 115 `tests/*.test.ts(x)` files: 717 tests, 697 pass, 0 fail, 1 skipped (`lpbf-phase4-e2e`, CMU payload absent), 19 todo; `npm run build`; `python/test_eagar_tsai.py`, `python/test_goldak_fabbro.py` (8 tests, 1 skipped, see below) and `python/test_lpbf_meltpool_accuracy.py` pass.
- Defects found and fixed on the way: (1) a Windows checkout with `core.autocrlf=true` turned the Dockerfile heredoc into CRLF (`npm run lint\r`); `.gitattributes` now pins `Dockerfile`, `.dockerignore` and `scripts/ci-unit-tests.txt` to LF. A worktree created before that pin still had a CRLF `scripts/ci-unit-tests.txt`, which made `grep -vxF` exclude nothing: an earlier build therefore ran all 115 files (718 tests, 698 pass, 0 fail), including the excluded worker delete test, which passed once. (2) `AIRGAPPED=1` in the `verify` stage broke 12 unit tests that, like `ci.yml`, expect it unset; it is now set only in the runtime stage.
- Goldak/Fabbro: `calculate_meltpool_physics(..., heat_source="goldak")` uses the GPU powder-bed ray tracer (`python/powder_bed_raytracer.py`, NVIDIA `warp` on `cuda:0`) for the conduction absorptivity when it is importable, otherwise prints `Warning: GPU Powder Bed Ray Tracing failed, using flat plate absorptivity.` and uses the flat-plate value. For the NIST AMB2022-03 IN718 case the ray tracer gives absorptivity 0.581 and width 102.2 um (inside 0.70-1.40 x 136.3 um); the fallback gives 0.38 and 81.7 um (about 40% below NIST). This is a GPU-path dependence, not an OS difference (forcing the fallback on the Windows GPU host also gives 81.7 um). The depth (123.9 um) is the same on both paths. The test thresholds are unchanged: the NIST width check now runs only when ray tracing was actually used and otherwise skips with "requires GPU warp ray tracing; CPU fallback underpredicts width"; a separate test forces the fallback and pins its warning, absorptivity 0.38, width 81.7 um and depth 123.9 um. The fallback is not claimed to match NIST. The GitHub `python` job (CPU pins, no warp) will take the skip.
- `docker build -t metalliksa:local .` (runtime stage): **builds** (image about 1.55 GB, user `metalliksa` uid 10001). As that user `/data`, `/app/.lpbf-runs`, `/app/.lpbf-jobs`, `/app/.research-registry` and `/app/python` are writable, and `/opt/venv/bin/python` imports numpy, scipy and pydantic.
- Runtime start on `orch/docker-verify` (50fa1ee): **FAILED**. `docker run -p 38080:3000 metalliksa:local` exited with code 1 during module load: `TypeError [ERR_INVALID_ARG_TYPE]` from `fileURLToPath(import_meta.url)` in `dist/server.cjs`. `server/lpbfNistProxyCampaignService.ts` and `server/lpbfProxyCampaignBinding.ts` derived `python/` from `import.meta.url`, which esbuild's `--format=cjs` output replaces with an empty object. It was a bundle defect, not a container one: `npm start` (`node dist/server.cjs`) crashed the same way on Windows (reproduced with the locked interpreter). The V1 browser tour had run on the tsx dev server (ESM), which is unaffected.

### Runtime start (2026-10-04, branch `orch/prod-start-fix`)

- Fix: `server/pythonRoot.ts` resolves `python/` against the working directory, like the IPC worker (`server/processOrchestrator.ts`) and the production static root (`server.ts`, `dist/`). The server must therefore be started from the application root (the repository root for `npm run dev` / `npm start`, `/app` in the image). No other `import.meta`, `__dirname`, `__filename` or `fileURLToPath` use exists in `server.ts`, `server/` or `routes/` (checked with `rg`; `src/` is bundled by Vite and `scripts/check-bundle-size.mjs` is ESM, so neither is affected). The esbuild build now prints no `import.meta` warning.
- Regression test: `tests/server-production-bundle.test.ts` bundles `server.ts` with the esbuild flags parsed from the `build` script in `package.json` (an unknown flag fails the test), fails on any `import.meta` warning, then starts the bundle with `NODE_ENV=production` on a free loopback port in an isolated application root and requires `/api/health` and the SPA fallback to answer. It kills the process tree on every path. It fails on the 50fa1ee sources and passes after the fix (about 1 s on Windows, 0.8 s in the verify container).
- Local production path (Windows, Node 24.20.0, locked interpreter `.runtime/lpbf-win-py312`): `npm run build` then `node dist/server.cjs` on 127.0.0.1:3040 with `METALLIX_IPC_PORT=5080` and isolated data roots. `GET /api/health` 200, `GET /api/lpbf/capabilities` 200, `GET /` 200 (the built `index.html`), a built JS asset 200, `GET /api/python/status` 200 (Python 3.12.10, daemon online). The process tree was stopped.
- Bind host: the runtime stage sets `METALLIKSA_HOST=0.0.0.0`; without it the server binds `127.0.0.1` inside the container (`server/security.ts` `resolveBindConfig`) and a published port cannot reach it. A non-loopback bind keeps the login flow ON. Without `METALLIKSA_TOKEN`, a random one-time login link is printed at start (`docker logs <container>`). The link shows `http://localhost:3000/...`, so replace the port with the published host port. With `METALLIKSA_TOKEN`, API clients send `Authorization: Bearer <token>`. Every `/api` route except `/api/health` requires login.
- Healthcheck: the Dockerfile `HEALTHCHECK` and the compose healthcheck call `/api/health` over container loopback. It is the only unauthenticated `/api` route; `/api/python/status`, the previous compose check, answers 401 in login mode. The check does not probe the Python worker. If `METALLIKSA_HOST` is set to one specific interface address, override the check.
- `docker build --target verify -t metalliksa-verify:prodfix .` on the tree committed as 73165f4: **PASS**, 2m06s. Unit tests: 115 of 116 files (the exclusion guard passed), 719 tests, 699 pass, 0 fail, 0 cancelled, 1 skipped, 19 todo. The new bundle test ran and passed on Linux, and the excluded worker delete test does not appear in the log. `npm run build`, Eagar–Tsai, Goldak (`OK (skipped=1)`) and the melt-pool accuracy fixture passed.
- `docker build -t metalliksa:prodfix .`: builds (the verify stage came from cache), image about 1.55 GB, user `metalliksa`, `Healthcheck` present.
- `docker run -d -p 38080:3000 metalliksa:prodfix`, checked from the host:
  - `GET /api/health`: 200 (`airgapped: true`).
  - Unauthenticated `GET /api/lpbf/capabilities`: 401 with `WWW-Authenticate: Bearer`. Unauthenticated `GET /api/python/status`: 401.
  - `GET /`: 200 (the built SPA). `GET /login`: 200.
  - `docker logs` contained exactly one one-time login link line.
  - Using that link's code, `POST /login` returned 303. With the session cookie, `/api/lpbf/capabilities` returned 200 (`platform: linux`) and `/api/python/status` returned 200 (Python 3.12.15, unix socket channel).
  - `docker inspect` health status was `healthy` (exit 0).
  - The container was stopped and removed.
- `docker compose config -q`: valid. `docker compose up` was not run.
- CI exclusion guard: the Dockerfile `verify` stage and `ci.yml` now fail when a `scripts/ci-unit-tests.txt` entry is missing or is still in the run list. The guard re-reads the list with CRs stripped. In a Linux container (`python:3.12-slim-bookworm`, GNU grep), the guard script behaved as follows:
  - LF list: passed, 115 files.
  - A CRLF copy: failed with `exclusion not applied: tests/lpbf-worker-delete-integration.test.ts`. Without the guard, the same CRLF copy left all 116 files in the run list.
  - A stale entry: failed with `lists a missing file`.
  - Git Bash on Windows tolerates the CR, so the CRLF case cannot be reproduced there.
- `.dockerignore` excludes `.orchestra*`. Local `.orchestra-run/` logs no longer enter the build context; the runtime build reused the cached verify stage.
- Not proven: GitHub Actions (no workflow has run); `docker compose up`; a reverse-proxy/TLS deployment (`METALLIKSA_TRUST_PROXY`); restart and volume persistence of the runtime container; long-running jobs inside the container; `tests/lpbf-worker-delete-integration.test.ts` as a deliberate Linux run (still excluded); `python/test_lpbf_engineering.py` (not in the container); the GPU ray-tracing NIST width check on Linux; GPU, WSL and OpenFOAM paths; arm64 or a native Linux host. The proxy-campaign Python calls that use `resolvePythonRoot()` were exercised by the host unit tests (tsx), not through an HTTP request to the bundled server.

## Files

- `.github/workflows/ci.yml`: `node` job (Node from `.nvmrc`, Python 3.12 with the CPU pins, `npm ci`, `npm run lint`, unit tests, `npm run build`) and `python` job (3.11 and 3.12, CPU pins, `npm run test:meltpool`; `test:lpbf:engineering` runs with `continue-on-error`). It never installs `python/requirements.txt` because that pulls torch.
- `scripts/ci-unit-tests.txt`: exclusion list. The unit tests are the `tests/*.test.ts` and `tests/*.test.tsx` glob (same as `npm run test:unit`) minus the files listed there. The workflow and the `verify` Docker stage apply the same shell snippet, followed by a guard that fails if a listed file is missing or was not removed from the run list.
- `.nvmrc`: Node 24 (the Dockerfile uses Node 24; `node:sqlite` tests need at least Node 22.13 without flags).
- `Dockerfile`, `.dockerignore`, `docker-compose.yml`: multi-stage draft (Node 24 + Python 3.12).

## Test exclusions (read from source on 95a9e43; counts rechecked 2026-10-04)

116 test files match the glob (`ls tests/*.test.ts tests/*.test.tsx`) since `tests/server-production-bundle.test.ts` was added on `orch/prod-start-fix`. One is excluded (115 files run):

- `tests/lpbf-worker-delete-integration.test.ts`: starts the real `python/lpbf_worker.py` and relies on process-tree reaping of an execution child and grandchild. Its Python import closure beyond numpy, scipy and pydantic and its Linux behaviour are unverified as a deliberate run (it passed once in a container only because a CRLF exclusion list failed to exclude it).

Files that mention Python, WSL, sqlite, GPU or external data and stay in, with the reason:

- `lpbf-worker-readiness.test.ts`: the "WSL" cases only use fake command names; the child processes are `node -e` protocol fixtures, so it is valid on Linux.
- `python-runtime.test.ts`, `python-status.test.ts`, `lpbf-archive-paths.test.ts`: platform is passed as a parameter (`win32` and `linux`) and the probes are fakes.
- `lpbf-gpu-artifact-reader.test.ts`: the cross-language case runs `python` with numpy from `python/lpbf_gpu_pilot_artifacts.py`; the CI Node job installs the CPU pins for it. The other GPU tests use tracked fixtures under `docs/LPBF_GPU_NATIVE_WORKER_ACCEPTANCE_RETRY_2026-09-27/`, which are tracked.
- `lpbf-phase5-defects.test.ts`, `lpbf-source-in625-catalog.test.ts`: run `python` against stdlib-only modules, so `python` must be on `PATH` (it is in both CI and the image).
- `lpbf-sqlite-compatibility.test.ts`, `lpbf-run-repository.test.ts`, `lpbf-source-repository.test.ts`: use `node:sqlite` (Node >= 22.13).
- `lpbf-phase4-e2e.test.ts`: skips itself unless the gitignored `data/benchmark/cmu-ti64-meltpool-v1/raw` payload is restored, which it is not in CI.
- `server-production-bundle.test.ts`: bundles `server.ts` with esbuild and starts it with `node`; the bundle's Python supervisor needs a host Python at load (it skips with a reason if none resolves). In the image that is `METALLIX_PYTHON=/opt/venv/bin/python`.
- `module-inventory.test.ts`: reads `docs/MODULE_EVIDENCE_INVENTORY.md`, which is tracked (confirmed with `git ls-files`).
- Tests that read `data/benchmark/*` (nist-amb2022-03, nist-amb2022-03-optical, nist-mds2-2923-in718/official, in625-bareplate-screening): the files they read are tracked.

The local Windows dry-run found no evidence to add exclusions. The first Linux run may still reveal platform-dependent tests that cannot be found by reading the source, for example the symlink tests in `lpbf-artifact-store.test.ts` and the Vite/HMR tests.

## Linux Python lock

`python/requirements-lpbf-win-py312.lock` is Windows-only. The Dockerfile uses `python/requirements-lpbf-linux-py312.lock` (committed in cc929b3); it installed with `--require-hashes` in the 2026-10-04 Docker build. CI does not use this lock; it installs the exact pins from `python/requirements-lpbf.in`, which has not run on GitHub.

## Container behaviour (mostly UNVERIFIED; see "Docker verification" for what ran)

- Targets: `verify` (lint, unit tests, build, three CPU meltpool Python tests) and `runtime` (default; copies `dist` from `verify`; non-root uid 10001). `python/test_lpbf_engineering.py` is not in `verify` because its Linux status is unproven; it runs only as a non-blocking CI step.
- Writable paths for the non-root user:
  - Redirected to the `/data` volume: `METALLIKSA_LPBF_SOURCE_ROOT`, `METALLIKSA_LPBF_RUN_ROOT`, `METALLIKSA_LPBF_BUNDLE_ROOT`, `METALLIKSA_JOB_ROOT` and `RESEARCH_REGISTRY_DIR` (variable names read from `server/lpbfSourceArchiveService.ts`, `server/lpbfRunArchiveService.ts`, `server/lpbfRunBundleService.ts`, `python/lpbf_worker.py` and `server/researchEvidenceRegistry.ts`).
  - Relative defaults created in `/app` and chowned to the app user, so they also work if the variables are unset: `.lpbf-sources`, `.lpbf-runs`, `.lpbf-run-bundles`, `.lpbf-jobs`, `.research-registry`, `.runtime`, `.lpbf-surrogates`.
  - `python/` is copied owned by the app user so `python/tmp*` scratch directories can be created. `PYTHONDONTWRITEBYTECODE=1` is set.
- `.lpbf-surrogates/` is tracked (`.lpbf-surrogates/in718_rf_model.pkl`) and is read and written, relative to the working directory, only by `python/phase9_surrogate.py`. That module is imported by offline scripts and tests, not by the server, and it imports `sklearn` and `joblib`, which are absent from the `python/requirements-lpbf-*.lock` files (only `requirements.txt` and the scientific cu128 lock list them). The directory is still copied and not excluded in `.dockerignore`, but it is inert in the runtime image unless scikit-learn is added. The `.lpbf-jobs`, `.lpbf-runs`, `.lpbf-sources`, `.lpbf-run-bundles` and `.research-registry` directories are untracked and excluded.
- `.dockerignore` also excludes tracked agent tooling directories (`.agents`, `.claude`, `.cursor`, `.gemini`, `.github`, `sonkayıtlar`) and the stale tracked `python/__pycache__` files for CPython 3.10 and 3.11. It deliberately does not exclude `*.log`, because tracked evidence logs live under `docs/`.
- Compose: `app` on port 3000 with `METALLIKSA_HOST=0.0.0.0` (login mode) and a healthcheck on `/api/health` (unauthenticated; it does not depend on Python readiness). The `repro` profile only builds the `verify` target. `docker compose up` has not been run.
- Runtime image contents besides `dist` and `node_modules`: `python/`, `data/`, `assets/`, `docs/sources/in625/` (about 18 MB; resolved from the working directory by `server/lpbfPropertySourceCatalog.ts` and archived by `server/lpbfSourceArchiveService.ts`) and `.lpbf-surrogates/`. Other relative-to-cwd paths read by the server: `python/persistent_ipc_service.py` and other Python scripts (`server/processOrchestrator.ts`), `dist/` (`server.ts`), and `data/benchmark/*` plus `data/collected-sources` (`server/lpbfSourceCatalog.ts`, `server/approvedSourceCollector.ts`). `spparks/` and the rest of `docs/` are not read by `server/*.ts` (grep checked) and are not copied.
- GPU, WSL and OpenFOAM paths are out of scope for this image.
