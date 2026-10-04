# Clean application reproduction

This procedure verifies a committed application snapshot independently of the active checkout's `node_modules`, `.env`, local edits and running preview. It complements [the CPU Python lock](LPBF_CPU_REPRODUCTION.md). It does not qualify optional scientific solvers or reproduce the CUDA toolchain.

## Create a clean snapshot

The checked host uses Windows x64, Node **24.20.0** and npm **11.19.0**. First prepare the separately [locked CPU Python environment](LPBF_CPU_REPRODUCTION.md). Unit tests launch Python workers, so select that interpreter **before** the test suite, using its absolute path from the original repository root. The resolver does not automatically select `.runtime`; a global interpreter missing `pydantic` is not a supported reproduction environment. Use a new destination for each check:

```powershell
$env:METALLIX_PYTHON = (Resolve-Path -LiteralPath .runtime/lpbf-win-py312/Scripts/python.exe -ErrorAction Stop).Path
$env:PYTHONDONTWRITEBYTECODE = '1'
& $env:METALLIX_PYTHON -B -c "import sys, numpy, pydantic; assert sys.version_info[:2] == (3, 12); print(sys.version); print('NumPy', numpy.__version__, 'pydantic', pydantic.__version__)"
if ($LASTEXITCODE -ne 0) { throw 'Supported CPU interpreter/import check failed' }
& $env:METALLIX_PYTHON -B -m pip check
if ($LASTEXITCODE -ne 0) { throw 'CPU dependency check failed' }
$revision = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve revision' }
$sourceEntries = @(git -c core.quotepath=false ls-tree -r $revision)
if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate tracked source' }
$sourcePaths = @($sourceEntries | Where-Object { $_ -match '^\d{6} blob ' } | ForEach-Object { ($_ -split "`t", 2)[1] })
if ($sourcePaths.Count -eq 0) { throw 'Tracked file inventory is empty' }
$destination = Join-Path (Get-Location) ".runtime/clean-$revision"
$archive = "$destination.zip"
if (Test-Path -LiteralPath $destination) { throw 'Choose a new clean destination' }
git archive --format=zip --output=$archive $revision
if ($LASTEXITCODE -ne 0) { throw 'Archive failed' }
Expand-Archive -LiteralPath $archive -DestinationPath $destination
function Get-LpbfSnapshotHashes([string]$snapshotPath, [string[]]$relativePaths) {
  $inventory = [ordered]@{}
  foreach ($relativePath in $relativePaths) {
    $inventory[$relativePath] = (Get-FileHash -LiteralPath (Join-Path $snapshotPath $relativePath) -Algorithm SHA256 -ErrorAction Stop).Hash
  }
  ConvertTo-Json -InputObject $inventory -Compress
}
$sourceBefore = Get-LpbfSnapshotHashes $destination $sourcePaths
$sourceBefore | Set-Content -LiteralPath "$destination.source-before.json" -Encoding utf8
Push-Location -LiteralPath $destination
try {
  npm ci --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { throw 'Locked Node install failed' }
  npm run lint
  if ($LASTEXITCODE -ne 0) { throw 'Type check failed' }
  npm run test:unit
  if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed' }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw 'Production build failed' }
} finally {
  Pop-Location
  $sourceAfter = Get-LpbfSnapshotHashes $destination $sourcePaths
  $sourceAfter | Set-Content -LiteralPath "$destination.source-after.json" -Encoding utf8
  if ($sourceBefore -cne $sourceAfter) { throw 'Tracked source integrity changed; preserve both manifests and this failed attempt' }
}
```

`npm ci` uses the committed `package-lock.json`; do not replace it with `npm install` when claiming this reproduction. The archive includes tracked files only. Offline raw benchmarks, local tool installations and uncommitted UI changes are excluded. npm may report install-script policy warnings; preserve these with the run evidence and confirm the actual build works under the recorded policy.

The file inventory excludes Git submodule pointers. `git archive` does not include the `spparks` submodule's checkout; this procedure does not reproduce that optional solver or verify its source bytes.

Keep `METALLIX_PYTHON` and `PYTHONDONTWRITEBYTECODE` set for the entire sequence, including child workers. Record the resolved interpreter and compare the tracked-source SHA-256 inventory before and after the checks. A source mismatch is a failed integrity check; restoring a changed file later does not make that attempt pass. Preserve the failed attempt separately and start a fresh guarded sequence when retrying. Python dependency checks alone do not establish source integrity or solver validity.

## Start with an explicit Python interpreter

First install the separately locked CPU environment following the linked guide. From the clean snapshot, assign `METALLIX_PYTHON` its absolute executable path. Assign an unused application port; the Python daemon binds a free loopback port itself (leave `METALLIX_IPC_PORT` unset). Then run:

```powershell
$env:NODE_ENV = 'production'
$env:AIRGAPPED = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PORT = '3016'
# Replace this example with the absolute path of the verified CPU interpreter.
$env:METALLIX_PYTHON = 'C:/verified-environment/Scripts/python.exe'
npm start
```

Run `npm start` from the application root. The server resolves `python/`, `dist/` and the default data directories against the working directory (`server/pythonRoot.ts`, `server/processOrchestrator.ts`, `server.ts`). Started elsewhere, it exits with a message naming the missing `python/persistent_ipc_service.py` or, in production, `dist/index.html` (`server/startupGuard.ts`).

Read `/api/python/status` on the application port. Require the expected interpreter version, `online: true`, and an active transport. On Windows the Python daemon binds HTTP and skips UNIX sockets. `warmModules` records imports only; `subsystemStatus: unverified` explicitly withholds solver availability. `/api/python/ipc-warmup` reports readiness and returns 503 before the daemon is ready; it does not run solver validation.

The Python daemon (`python/persistent_ipc_service.py`) is an internal channel, not an API. `server/processOrchestrator.ts` generates a fresh random secret for every daemon spawn and passes it only through the child environment (`METALLIX_IPC_TOKEN`; an inherited value is deleted at startup). The secret never travels on the wire: each request carries a timestamp, a nonce and an HMAC-SHA256 over the request, and each response an HMAC over the nonce, status and body, so a process that is not the daemon can neither replay a request nor forge solver output the server accepts. The daemon announces its channels in its ready message: an ephemeral loopback HTTP port (bound with `SO_EXCLUSIVEADDRUSE` on Windows) and, on POSIX, a socket (0600) in a fresh 0700 directory. The server uses only channels its own daemon announced; anything else (not ready, a refused or unsigned reply, any status of 400 or more) falls back to an ad-hoc script spawn. The daemon refuses to start without a secret, sends no CORS headers, rejects requests with an `Origin` header or a `Host` other than its own `host:port`, accepts only `application/json` bodies up to 64 MiB, and runs only the `python/<module>.py` scripts that `routes/*.ts` dispatch, resolved inside `python/`. A non-loopback `METALLIX_IPC_HOST` is ignored by the supervisor and refused by the daemon unless `METALLIX_IPC_ALLOW_REMOTE=1`; wildcard addresses are always refused. Residual risk: code running as the same user can read the secret from the process environment or memory. To launch the daemon by hand (diagnostics only), set `METALLIX_IPC_TOKEN` to at least 32 random characters and sign requests as `server/processOrchestrator.ts` does (`signIpcRequest`).

Stop only the processes launched for this check. Keep the original checkout and preview separate.

## WSL boundary verification

The configured default is Ubuntu-22.04. The host Python setting does not select the WSL interpreter. From the original checkout:

```powershell
wsl.exe -d Ubuntu-22.04 -- env PYTHONDONTWRITEBYTECODE=1 python3 -B python/test_lpbf_engineering.py
```

The 2026-09-15 run passed **26/26** tests in **53.334 seconds**, including the compiled OpenFOAM comparison. Capability RPC reported OpenFOAM-14 and thermal binary SHA-256 `1abadcbe9beacbe60a9ad2228d634830f481ce6966b66de65724c172dc1159d7`. The native Windows CPU worker reported `openfoamThermal: false`.

Job root under WSL (changed 2026-10-04): a `METALLIKSA_JOB_ROOT` set in the Windows environment is now forwarded to the WSL worker through `WSLENV` (`METALLIKSA_JOB_ROOT/p`, translated to `/mnt/<drive>/...`). Before this change the WSL worker silently ignored it and used the checkout's `.lpbf-jobs`. Windows operators with a configured job root will therefore no longer see their earlier WSL jobs, which stay in the checkout's `.lpbf-jobs`; nothing is deleted or moved. The value must be a drive-letter path such as `C:\lpbf-jobs`; a UNC, `\\wsl$` or Linux path stops the worker start with an explicit error instead of being ignored. Without `METALLIKSA_JOB_ROOT` nothing changes.

A separate Node bridge process used a deliberately nonexistent `METALLIKSA_WSL_DISTRO` and an isolated job directory. Its initial WSL capability request failed; the bridge returned Windows capabilities through the explicitly selected CPU interpreter. This verifies initial launch fallback, not mid-job migration or queue recovery. The test-owned process tree was stopped. These software/numerical checks are not experimental validation.

## Observed clean application run — 2026-09-15

Snapshot `1fc10dd` installed 354 packages with `npm ci` in 30 seconds. Type checking passed, all 104 unit tests passed, and the production build completed in 1m 40s. The existing large-chunk warning remained. npm 11.19.0 also reported five packages whose install scripts were not covered by its allowScripts configuration; no policy override was needed for this successful build.

The clean snapshot's production server ran on separate ports 3016/5058 with the seven-package CPU Python environment. HTML returned HTTP 200; `/api/python/status` reported Python 3.12.10, HTTP transport, 17 imported modules and unverified subsystem status. Its test process tree was stopped. This snapshot did not include unrelated local UI edits.

The subsequent [full scientific environment record](SCIENTIFIC_ENVIRONMENT_REPRODUCTION.md) completes the separate 94-package offline installation, import/range and GPU checks. Independent review of the accumulated A02 environment evidence is recorded there and in the roadmap; clean CPU/application reproduction alone did not close those requirements.

## Production start regression — 2026-10-04

Builds after the proxy-campaign contract work could not start with `npm start`. Two server modules derived `python/` from `import.meta.url`. In the esbuild CJS bundle (`dist/server.cjs`), `import.meta` is empty, so `node dist/server.cjs` threw `TypeError [ERR_INVALID_ARG_TYPE]` from `fileURLToPath` before it listened. This was reproduced on Windows with the locked interpreter. The V1 browser tour had used the tsx dev server, which does not have this problem.

The fix is on branch `orch/prod-start-fix`. `python/` is now resolved against the working directory. `tests/server-production-bundle.test.ts` bundles the server with the `npm run build` esbuild flags and checks that the bundle loads and answers `/api/health`.

After the fix, `npm run build` and `node dist/server.cjs` were run on 127.0.0.1:3040 / 5080 with the locked interpreter and isolated data roots. These requests returned HTTP 200:
- `/api/health`
- `/api/lpbf/capabilities`
- `/` (the built `index.html`)
- a built asset
- `/api/python/status` (Python 3.12.10, daemon online)

The process tree was then stopped. This is a start-up and serving check only. It is not a scientific or browser workflow check. The container results are in [APPLICATION_PACKAGING_NOTES.md](APPLICATION_PACKAGING_NOTES.md).
