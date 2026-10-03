# CI draft local dry-run

Date: 2026-10-03
Checkout: `orch/ci` at `81694c3df5a8696513bbf4d3f28ab297d006f0ea`
Host: Windows x64, Node from the machine PATH, Python 3.12.10. The `node_modules` junction points to `C:\Users\can02\Projects\metalliksaa\Metalliksa-1\node_modules`; no npm install was run.

This is a local Windows dry-run of the draft commands. **The workflow has not run on GitHub, and these results do not prove Linux behavior.** Durations are wall-clock measurements on this machine.

## Results

| CI step | Command | Result | Duration | Notes |
| --- | --- | --- | ---: | --- |
| Lint | `npm run lint` | PASS | 31 s | `tsc --noEmit`, exit 0. |
| Unit tests | `node node_modules/tsx/dist/cli.mjs --test <93 non-excluded test files>` | FAIL | 53 s | 451 tests: 432 passed, 1 failed, 1 skipped. The one failure was `LPBF source select, CPU compute, unvalidated compare, export and restore preserve identities and bytes` (`tests/lpbf-run-workflow-roundtrip.test.ts`): its launched Python process reported `No module named 'pydantic'`, then the expected completed run was `failed`. This is a local subprocess/interpreter environment mismatch: the shell Python 3.12.10 successfully imports numpy 2.5.3, scipy 1.18.1 and pydantic 2.13.5, while the test-launched interpreter did not. CI installs `python/requirements-lpbf.in` into its Python 3.12; Linux result remains unverified. |
| Build | `npm run build` | PASS | 35 s | Vite emitted the existing large-chunk warning; esbuild warned that `import.meta` is unavailable in CJS output. Exit 0. This was the only build run. |
| Python fast job | `npm run test:meltpool` | PASS | 28 s | Eagar–Tsai, Goldak/Fabbro, and melt-pool accuracy scripts passed. Local Python package probes passed for numpy 2.5.3, scipy 1.18.1, pydantic 2.13.5. |
| Python engineering job (CI non-blocking) | `npm run test:lpbf:engineering` | FAIL (3 errors) | 76 s | 39 tests, 1 skipped; 3 tests errored with `ValueError: Unknown material property fields`: `test_source_validity_range_is_separate_and_must_cover_model_table`, `test_supplied_data_for_additional_alloy`, and `test_supplied_material_revision_changes_with_source_and_is_unverified`. This is a reproducible application/test contract failure on this host, not a missing-package or Linux-only failure. CI already marks this job `continue-on-error: true`. |

The initial attempt to invoke `node_modules/.bin/tsx` directly from PowerShell passed the file list as one argument and did not start tests. The successful measured invocation above calls the same installed `tsx` CLI through Node with PowerShell's argument array. The test exclusion file still excludes only `tests/lpbf-worker-delete-integration.test.ts`; this run gave no evidence that another test is Ubuntu-incompatible or requires GPU/WSL/Python extras. Its stale file-count comment was updated to the current glob count (94 matched, 93 run).

Tafel parser checks appeared as TODO diagnostics in the Node test output and were not counted as failures by the test runner. The one counted failure is listed above. One test was skipped because the optional CMU benchmark payload was not restored.

## Not executed: Linux lock generation

`python/requirements-lpbf-linux-py312.lock` is a Docker build prerequisite and is absent. Generate and review it on Linux x86_64 with CPython 3.12, then commit the resulting file. For example, in that Linux environment:

```sh
python -m pip install pip-tools
pip-compile --generate-hashes --output-file=python/requirements-lpbf-linux-py312.lock python/requirements-lpbf.in
```

Alternatively use uv on Linux x86_64:

```sh
uv pip compile --python-version 3.12 --python-platform x86_64-manylinux_2_28 --generate-hashes --output-file python/requirements-lpbf-linux-py312.lock python/requirements-lpbf.in
```

Neither command was executed here. Review platform markers, pinned versions and hashes before accepting the generated lock.

## Not executed: Docker build

Docker CLI 29.8.0 is installed, but no image build was run. After the Linux lock exists, run from the repository root:

```sh
docker build --target verify -t metalliksa-ci-verify .
docker build -t metalliksa-runtime .
```

The first command exercises the Docker `verify` stage; the second builds the default runtime target. Neither Docker build nor a container start was executed for this dry-run.
