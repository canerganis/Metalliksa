# Reproduce the Windows CPU LPBF baseline

This setup covers the CPU LPBF build/slicer screening path, the Python thermal reference solver and the offline CMU importer. It does not install CUDA, CALPHAD, micrograph models, OpenFOAM, Node dependencies or a full deployment environment. The existing broad `python/requirements.txt` is unchanged.

The checked platform is **Windows x64, CPython 3.12.10**, with venv bootstrap pip 25.0.1. `python/requirements-lpbf.in` declares three direct dependencies. `python/requirements-lpbf-win-py312.lock` fixes all seven resolved distributions and the SHA-256 of the corresponding Windows/Python 3.12 wheels. The lock is intentionally platform-specific; unsupported platforms need a separate verified lock.

## Download and install

Run from the repository root with Python 3.12 installed. The download step needs access to the configured Python package index; the installation step is offline. `.runtime/` is ignored by Git.

```powershell
py -3.12 -m pip download --only-binary=:all: --require-hashes --dest .runtime/lpbf-wheels -r python/requirements-lpbf-win-py312.lock
if ($LASTEXITCODE -ne 0) { throw 'Wheel download failed' }
if (Test-Path .runtime/lpbf-win-py312) { throw 'Use a new directory for a clean reproduction check' }
py -3.12 -m venv .runtime/lpbf-win-py312
if ($LASTEXITCODE -ne 0) { throw 'Environment creation failed' }
& ./.runtime/lpbf-win-py312/Scripts/python.exe -m pip install --no-index --find-links .runtime/lpbf-wheels --require-hashes -r python/requirements-lpbf-win-py312.lock
if ($LASTEXITCODE -ne 0) { throw 'Locked installation failed' }
& ./.runtime/lpbf-win-py312/Scripts/python.exe -m pip check
```

Do not overwrite an existing environment when reporting a clean installation. Keep the downloaded wheels with your deployment archive if offline recovery is required. The lock verifies dependency artifacts, not the operating system or Python installer.

## Verify the workload

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
& ./.runtime/lpbf-win-py312/Scripts/python.exe -B python/test_lpbf_build_job.py
if ($LASTEXITCODE -ne 0) { throw 'Build-job tests failed' }
& ./.runtime/lpbf-win-py312/Scripts/python.exe -B python/test_lpbf_engineering.py
if ($LASTEXITCODE -ne 0) { throw 'Thermal tests failed' }
& ./.runtime/lpbf-win-py312/Scripts/python.exe -B python/test_cmu_ti64_import.py
```

The engineering suite can skip its compiled OpenFOAM comparison on native Windows. That skip must remain visible; it is not a pass for the WSL worker. These tests establish software/numerical regression behavior, not experimental accuracy or process qualification.

### Observed clean run — 2026-09-15

All seven packages installed from the local wheel directory with `--no-index --require-hashes`; `pip check` passed. The build-job fast suite passed, the engineering suite passed 25 tests with one explicit compiled-OpenFOAM skip (26 total), and all eight CMU importer tests passed. The existing application Python microservice was also launched with this exact interpreter on a separately checked port 5058. Its health endpoint reported online, Python 3.12.10 and 17 warm modules. The test-owned service was then stopped. Warm imports are not proof that optional CALPHAD/ML dependencies or every module's computations work; no workload request was sent to that temporary service.

## Select this interpreter explicitly

```powershell
$env:METALLIX_PYTHON = (Resolve-Path .runtime/lpbf-win-py312/Scripts/python.exe).Path
# Launch the application from this same shell after its usual Node setup.
```

The shared resolver does not automatically select this `.runtime` environment. Existing GPU settings and global Python packages are preserved. When running an additional local server, assign a distinct `PORT`; the Python daemon binds a free port by default (if you set **`METALLIX_IPC_PORT`**, keep it distinct). `METALLIX_IPC_SOCK` is not the Python HTTP-port setting. Identify existing workers before starting another.

## Lock maintenance

Dependency changes require downloading the intended compatible wheels, reviewing their versions and SHA-256 values, updating both direct inputs and the complete lock, and repeating the fresh-environment tests. Do not substitute a plain `pip freeze` list for artifact hashes. This lock does not imply that the broad scientific environment's remaining dependencies are complete.
