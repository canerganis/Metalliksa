# Environment readiness

## Latest verified boundary — 2026-09-15

The [clean application record](APPLICATION_REPRODUCTION.md) and [full scientific/CUDA reproduction](SCIENTIFIC_ENVIRONMENT_REPRODUCTION.md) supersede the earlier open environment items below. A new Python environment installed 94 hash-locked wheels offline and matched all locked versions. Package consistency, all 18 imports and requirement ranges, CUDA training smoke, selected LPBF/importer regressions and a clean Node application's live API passed. WSL passed all 26 engineering tests including compiled OpenFOAM; initial WSL failure to Windows fallback was exercised separately. Independent source/artifact review found no remaining material acceptance gap. A02 is accepted for technical workstation/software reproduction; no model qualification is implied.

The [CPU LPBF guide](LPBF_CPU_REPRODUCTION.md) remains a separate seven-package baseline. [Versioned evidence](evidence/a02-environment-2026-09-15.json) preserves the clean interpreter scope and lock hash. Earlier snapshots below are historical observations, not current availability.

## Tool execution verified — 2026-09-15 continuation

Docker Desktop was started using its installed CLI. The `desktop-linux` engine responded with version 29.8.0. The official `hello-world` image ran successfully in a disposable container with networking disabled, a read-only root filesystem, no Linux capabilities and no project mounts. Image digest: `sha256:5e23090353324d887c48ad5e5c56d294eab81588df9605b07d1afe895f9cc8f8`. The engine was left running. This establishes container execution, not a reproducible Metalliksa container image.

The portable ParaView 6.1.0 installation responded to `pvpython --version`. Its Python runtime executed `python/check_paraview.py`: an independently written literal VTI fixture was read through `XMLImageDataReader`, yielding eight points, one cell and the exact eight synthetic scalar values with range 300–1900 K. Temporary files are scoped to a newly created directory and removed after the check.

Run the same check with your installed ParaView interpreter:

```powershell
& 'C:/path/to/ParaView/bin/pvpython.exe' -B python/check_paraview.py
```

This checks headless VTI file reading. It does not verify the ParaView GUI, GPU rendering, real solver export compatibility or scientific accuracy. Portable ParaView and Docker may still be absent from an already-running shell's PATH; these checks used explicit executable paths and changed no persistent PATH settings.

At this earlier tool-only checkpoint, locking, remaining packages and Node/WSL verification were still open. The latest verified boundary above supersedes that partial status.

## Continuation verification — 2026-09-15

The existing GPU venv was repaired with Pydantic 2.13.5, NumPy 2.2.6 and SciPy 1.15.3. `pip check` passed. These three versions satisfy the repository ranges; this does not mean all repository dependencies are installed. At that earlier checkpoint the doctor reported 12 missing optional/domain dependencies, ParaView/pvpython outside PATH, and an unavailable Docker engine; the latest verified boundary supersedes those gaps.

The actual production Node server was started with an explicit `METALLIX_PYTHON` override to that venv on local port 3015. Its Python supervisor loaded 17 scientific modules successfully, including the modules previously blocked by missing Pydantic. The HTTP microservice used port 5055; `METALLIX_IPC_SOCK` does not change that HTTP port. A fresh CUDA smoke passed three training steps on RTX 4060 Laptop, with finite losses 4.215446 → 4.025282 → 3.844670 and updated weights. No trained scientific predictor or experimental validation is claimed.

Those items remained open at this historical checkpoint and were subsequently verified within the scopes above. The resolver's fallback policy has 14 passing unit tests; the actual host supervisor launch was separately verified.

Run the doctor with the exact interpreter that will run the workload, from the repository root:

```powershell
py -3 -B python/environment_doctor.py
& 'C:\path\to\venv\Scripts\python.exe' -B python/environment_doctor.py --gpu-smoke --paraview-version --timeout 30
```

The only output on stdout is a JSON report. Dependency imports run in isolated subprocesses under `sys.executable`, with bytecode writes disabled and a timeout per probe. All distributions in `python/requirements.txt` have an import mapping, including `sklearn`, `cv2`, and `segmentation_models_pytorch`. Versions are reported; requirement ranges are **not** validated. A successful import does not prove solver accuracy or scientific validation.

The doctor installs nothing, reads no `.env` files, writes no reports/checkpoints, and starts no services. Third-party imports and version commands can have their own initialization side effects; this is a diagnostic tool, not an operating-system sandbox. Imports inherit the current process environment but the report does not dump it. Docker diagnostics address the currently configured Docker context.

## Actual server interpreter configuration

`server/pythonRuntime.ts` is the shared host resolver used by the process orchestrator and LPBF local fallback. Importing the resolver does not load environment files or start probes. Before first host resolution, dotenv loads configuration with `override: false` so existing process variables win. The orchestrator also loads it before reading its IPC settings. This fixes the previous ordering where imports resolved Python before the `dotenv.config()` call in `server.ts`.

Host selection is cached after the first successful resolution:

1. A nonempty `METALLIX_PYTHON` is probed as one executable, with no prefix arguments. An invalid explicit value throws a clear error, without trying another interpreter.
2. The project `.venv` is tried (`Scripts/python.exe` on Windows, `bin/python` elsewhere), relative to the server's working directory. Start the server from the repository root.
3. The active `VIRTUAL_ENV` is tried using the same platform-specific layout.
4. Windows then tries `py -3`, `python`, `python3`; other platforms try `python3`, `python`.
5. Missing virtual-environment executables are skipped; failed automatic candidates proceed to the next candidate. If none works, resolution throws a clear configuration error.

Each probe runs `--version` without a shell, with a five-second timeout and `windowsHide: true`. It requires a successful exit and a Python 3 version response. It does not import scientific dependencies. The selection policy accepts injected environment, path checks, and probes for testing without touching real `.env` files.

Set `METALLIX_PYTHON` to an executable path, **not** a command containing arguments. Restart the Node server after changing it. For example, in the same PowerShell session used to start the server:

```powershell
$env:METALLIX_PYTHON = 'C:\path\to\venv\Scripts\python.exe'
& $env:METALLIX_PYTHON -B python/environment_doctor.py --gpu-smoke
```

An existing GPU environment is available at the following supplied path; use an explicit override to select it without creating or installing a new environment:

```powershell
$env:METALLIX_PYTHON = 'C:/Users/can02/Documents/Codex/2026-09-15/referenced-chatgpt-conversation-this-is-an-2/.venv/Scripts/python.exe'
& $env:METALLIX_PYTHON -B python/environment_doctor.py --gpu-smoke --timeout 30
npm run dev
```

The path is an existing workstation configuration, not a portable repository default. The doctor's `interpreter.executable` identifies the Python actually tested; the doctor does not query a running server's interpreter. The system-interpreter snapshot below does not describe this GPU environment.

The LPBF worker remains **WSL-first on Windows** for OpenFOAM. It launches `wsl.exe -d <distribution> -- python3 -u <worker path>`, where `METALLIKSA_WSL_DISTRO` selects the distribution and defaults to `Ubuntu-22.04`. The host override does not change the interpreter inside WSL. If the initial capabilities request fails, it retries locally using the shared host resolver, preserving any launcher prefix before `-u <worker path>`. Non-Windows LPBF launches use the shared host resolver directly. No new host-mode switch is introduced. Test the WSL interpreter separately, for example:

```powershell
wsl.exe -d Ubuntu-22.04 -- python3 -B '/mnt/c/Users/can02/OneDrive/Desktop/Uşağım/metalliksaa/Metalliksa-1/python/environment_doctor.py'
```

Use your configured distribution and checkout path. A successful host report does not establish WSL readiness.

## Reading the report

- `dependencies`: actual import results and installed versions; native-load errors remain visible.
- `cuda`: PyTorch version, build CUDA version, device availability/count and names. This does not establish that training kernels work.
- `gpu_smoke`: skipped by default. `--gpu-smoke` performs three small CUDA forward/backward/SGD updates on synthetic tensors, checks finite losses/gradients/weights, synchronizes CUDA, and verifies weight changes. No downloads or CPU fallback. This is a training execution check, not a benchmark or model validation.
- `tools.docker`: Docker client version. `docker_engine`: separate `docker info` result. A working client with an inaccessible daemon is a gap.
- `tools.paraview` and `tools.pvpython`: PATH availability by default; `--paraview-version` opts into bounded version commands. Installations outside PATH are not discovered.
- `tools.node`, `tools.git`, `tools.nvidia-smi`: tool availability and command output.
- `gaps`: unavailable, failed, or timed-out capabilities, including optional tools. No universal readiness claim is made.

Exit status is 0 for a completed diagnostic report even with gaps; `--strict` returns 1 if any reported capability has a gap. CLI usage errors return 2. `--timeout` must be finite and positive; it applies to each subprocess, not the whole report. Heavy cold imports may need a larger value. CPU screening can still be useful when optional CUDA, Docker, or visualization tools are absent.

## Tests

### Observed workstation snapshot (2026-09-15)

Both host commands were run with `--gpu-smoke --paraview-version --timeout 30`:

- `py -3` selected Python **3.14.5**. Only NumPy 2.5.3 and Pydantic 2.13.5 imported among the 18 checked dependencies; the remaining 16 imports failed with missing-module errors.
- `python` selected Python **3.12.10**. NumPy 2.5.3, SciPy 1.18.1, tqdm 4.70.1, and Pydantic 2.13.5 imported; the remaining 14 imports failed with missing-module errors.
- Both interpreters lack PyTorch, so neither CUDA probe nor requested training smoke could execute. No successful GPU training claim is made.
- NVIDIA tooling reported an RTX 4060 Laptop GPU and driver 610.88. Docker client 29.8.0 responded, but the engine connection failed because the named pipe was absent. ParaView and pvpython were not on PATH. Node 24.20.0 and Git 2.55.0 responded.
- Comparing the reported versions manually with `python/requirements.txt`, NumPy 2.5.3 exceeds the `<2.3` bound in both interpreters; SciPy 1.18.1 exceeds `<1.16` in Python 3.12. Successful imports alone therefore do not establish requirement compatibility.

This snapshot does not inspect `.env` contents, a running Node server's environment, other virtual environments, or WSL. It does not imply that the server currently uses either tested interpreter if `METALLIX_PYTHON` overrides the default.

### Test command

```powershell
py -3 -B -m unittest discover -s python -p test_environment_doctor.py -v
node node_modules/tsx/dist/cli.mjs --test tests/python-runtime.test.ts
```

Tests use the standard library and bounded real child-process checks; tool/CUDA reporting branches use mocks so the suite also runs on machines without a GPU or Docker. Run the opt-in smoke on the target interpreter for actual CUDA execution evidence.
