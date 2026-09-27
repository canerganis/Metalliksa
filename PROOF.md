## 2026-09-27 — IN718 primary-paper applicability screen

Preserved the 31-page Deisenroth et al. paper, DOI
`10.1016/j.addma.2026.105330`, in `docs/sources/in718-deisenroth-2026/`:
12,221,120 bytes, SHA-256
`7b2a21b29037108ca8f61297c4f8e5aab4df342b1b6c02353f966b1da8e81128`.
Parent independently verified the saved hash. Retrieval records the failed
certificate verification and request-local TLS bypass; hashing establishes
local byte integrity, not cryptographic publisher authentication.

Full-text review: PDF pp.5–8 specify bare IN718, five antiparallel 4.84 mm
tracks, 960 mm/s, 110 micrometre hatch and 0.75 ms turnaround. Coupling and
directional-reflection campaigns have different incidence/gas configurations.
85 W is a lower-regime candidate, but quantitative cross-sections cover
113/135/285/485 W (pp.15,19). Even the described conduction regime includes
shallow vapor depression (pp.4,20). Coupling is not directly deposited thermal
absorptivity. The paper's depth includes material above the initial surface
(p.12), unlike current CPU liquidus depth. Reported depth uncertainties are
not a complete raw measurement table. Target raw data are described as future
PDR publication (pp.8,11,28), without a verified result-dataset DOI here.

**Experimental validation remains unvalidated.** Do not substitute estimated
absorptivity, extract invented raw measurements, or equate the observation
operators. Next obtain raw measurements/masks and uncertainties and establish
an applicable observation/model contract before computing residuals.

## 2026-09-27 — Actual CPU/CUDA final-state capture

An optional reference-CPU observer copies actual final coordinates, temperature,
volumetric excess enthalpy, density and accepted timestep arrays, plus final time,
preheat and cell volume. It is limited to standard reference powder-layer runs
without a refinement study. The CUDA capture uses its actual H/rho/dt arrays;
there is no reconstruction from temperature or second solve. The parity sink
runs after numerical comparisons. The private helper retains its default
four-item return for Warp and existing callers. Capture arrays stay outside
the ordinary JSON result.

Parent verification: **13/13 PASS, no skips** for final-state capture and artifact
writer/reader tests, including actual cuda:0 field write/read and a mutating
sink. Actual Warp/CPU existing full-temperature-field pilot: **1/1 PASS, no
skips**, 73,568 cells and 934 steps, RTX 4060 Laptop GPU, Warp 1.17.0. Initial
sandbox attempts encountered Windows TEMP/cache access errors; the final
permitted runs completed cleanly with a repository Warp cache. The agent also
passed the existing CUDA endpoint and mocked-helper regressions (2/2).

Working-tree implementation fingerprint:
`cef3e50894ce5b06408a37b42a3794cbe7a08d006678b77899e22d7fcc0889a0`.
This includes preserved earlier CPU diagnostic edits; it is not a claim that
every manifest source is clean at this commit. CPU/CUDA artifact integration
uses a short synthetic process case (60 W, 1200 mm/s, 40 micrometre mesh,
200 micrometre track). It demonstrates software preservation and bounded
backend parity, not convergence, experimental validation or speedup. Queue,
persistent GPU archive and browser export/restore integration remain pending.

The prior UI/source package production build completed successfully (Vite and
server bundle), with the existing large-chunk warning. No page-load or solver
performance improvement follows from build success.

## 2026-09-27 — IN625 sources in browser portable bundle (software evidence)

The later real-browser acceptance closes the property-source download/upload
gap noted below. Bundle `d1d4ac888d9643f1b1601e2d78d9abc5` includes one archived
CPU run, three source revisions (NIST plus both IN625 sources), and six source
artifacts. The browser downloaded 18,985,472 bytes; SHA-256
`9a0da663dec3d90596c7cd55eff7913fe13bdaf12dc5ebe4f59420f2566ca859`.
All 76 tar members matched the server export bytes. The same downloaded file
was chosen through the browser picker, uploaded, verified, and restored with
Enter to isolated archive `f1e9d4364fc94ee28f2f2e9c7280c244`.

All 72 payload files (66 run and 6 source) are byte-identical after restore;
every row in both SQLite databases is logically identical. Metadata containers
were rebuilt, so this is not a claim that all restored container bytes match.
After full page reload the restored ID, run, source binding and unvalidated
model status reappeared. The source records' three revisions also survive in
the restored database; dedicated browsing of restored source documents is not
yet exposed by this run-view UI. No model or material admission changed.

## 2026-09-27 — Worker readiness and recovery (software evidence)

Readiness now has one shared, bounded 60 s background startup; HTTP callers
retain a 20 s total budget and receive recoverable 503/Retry-After while a
healthy startup continues. Explicit native Python is not launched twice as
an automatic fallback; fallback follows an actual WSL attempt only. Transport
failure is distinct from rejected Python input. A stopping child remains a
barrier until terminal exit/close; stale requests cannot cross a close/restart
generation or launch a replacement after invalidation.

Before the change, a controlled 21 s Python import-delay fixture returned
HTTP400 after 40.151 s and logged two native launches. This is synthetic startup
evidence, not a natural cold-start benchmark or the established cause of the
earlier browser400. Parent final readiness/API suite: **13/13 PASS**, no skips;
`npm run lint` PASS. Tests exercise real Node pipes/HTTP and injected child
events: concurrent startup, short caller503 then recovery, exit/spawn failure,
WSL fallback, startup timeout, EPIPE503 and delayed shutdown. Sol independently
replayed all four race/transport findings against the final implementation;
all closed, including a still-live child after a SIGKILL request. These tests
do not claim GPU queue execution speed or a repeated end-to-end speedup.

## 2026-09-27 — Actual CUDA endpoint correction (numerical backend evidence)

PyTorch now uses the existing CPU/Warp endpoint roundoff snap rule. Before
the correction, the real 40 W / 800 mm/s / 40 micrometre mesh pilot took
1606 GPU versus 1605 CPU steps; four regression assertions failed. After
the three-line correction, the unchanged regression passed on actual CUDA.
Parent independently reran it (**1/1 PASS**, no skip, 25.700 s); the agent's
three related CUDA regressions also passed. No acceptance threshold changed.

The [full comparison report](docs/LPBF_GPU_ENDPOINT_REGRESSION_2026-09-27.json)
records 3969 cells, 1605 steps on both backends, final time 0.00145 s, temperature
rise relative L2 `6.760651397343335e-9` and max `9.062182562735324e-9`.
Energy terms and 40/40/120 micrometre width/depth/length pass the existing
gates. The implementation fingerprint is
`e8d5695b39d2d05eb2d17a78fcafcae0b4d6fa13c623752065ea243f95b7ba06`;
removing only the three new lines from its exact bytes reproduces the frozen
prior `d0c160f286f3287248f6163327cf7962a384b2540efe38768092232d74fa9522`.

This is one scoped CPU/PyTorch numerical parity case. Geometry is underresolved;
it is not experimental validation, mesh/time convergence, Warp revalidation,
full field archival or an end-to-end speed benchmark. The original failed
browser job `d970096774274794a60b8494fba58f73` remains intact as failed evidence.

## 2026-09-27 — IN625 property archive API and live UI (software evidence)

Two exact-byte property catalogs now use `material-characterization` scope.
Source conditions show measured, derived and fitted quantities, units,
temperature coverage, uncertainty and unresolved specimen applicability.
No material capability or registry value is promoted by source import.
Parent combined integration: **12/12 TypeScript tests PASS**, including four
property-catalog tests covering original bytes, corruption rejection,
client → HTTP → SQLite → bundle → isolated restore, and rendered source copy.
The source agent's wider regression set passed **45/45**; typecheck passed.

Real IAB at localhost:4176: select → preview → import → verify → full page
reload → reselect/reload succeeded for both sources. Georgia Tech import was
activated with Enter; the property table was visually inspected. This is
scoped keyboard/visual acceptance, not a full accessibility audit.

| Source | Revision | Files / bytes | Stored document SHA-256 |
| --- | ---: | ---: | --- |
| Georgia Tech | 1 | 3 / 197221 | `d78bfa9f4d972e820453611498ef7a3a36544b8b60255e5c5e7e982d96b98f18` |
| NASA | 1 | 2 / 18307069 | `69368c8f21108fc516869d8619aa3b3939ed22718e8e00b2a6634e85445162bc` |

Byte checks at 13:15:28Z and 13:15:50Z retained the same document identities;
reload correctly distinguishes loaded metadata from a fresh file check.
UI retained unknown lot/state fields and NASA's unknown validity range and
unresolved viscosity conventions. Full IN625 model admission and experimental
validity remain **unvalidated**. Property bundle restoration was tested at
API/service level; a property-specific browser download/upload is still open.

## 2026-09-27 — Lossless GPU field artifact foundation (software evidence)

The new Python writer/reader and TypeScript descriptor/reader preserve explicit
little-endian float64 final coordinates, temperature (K), volumetric excess
enthalpy relative to initial temperature (J/m^3), density and accepted timesteps
for both CPU and GPU. Shape, units, resource bounds, hashes, finite values,
advancing sequential clocks and ordinary filesystem ancestry are checked.
Backend states may differ: this preserves failed-parity evidence and never
declares parity by itself. Lossy mixed-list/oversized integer conversion is
rejected before conversion; writer arrays explicitly require NumPy ndarrays.

After a reproduced precision defect and correction, parent integration checks
passed: Python `test_lpbf_gpu_pilot_artifacts` **10/10**, TypeScript descriptor
and reader **8/8**, no skips. They include Python-to-TypeScript binary fidelity,
100000-step sequential clock, negative excess enthalpy, corrupt/rehashed
nonfinite values, changed file size and Windows junction rejection. Fixtures
are synthetic software checks. This foundation is not yet wired into actual
solver production, GPU job capture or archive/restore; those remain open.

## 2026-09-27 — Completed frozen CPU time refinement (numerical evidence)

The 5 micrometre, 50/25/12.5 ns diagnostic completed all three levels
(7000/14000/28000 accepted steps). Protocol, runner and both assessment module
hashes were rechecked; the implementation stayed
`d0c160f286f3287248f6163327cf7962a384b2540efe38768092232d74fa9522`
before, during and after execution. Maximum relative energy error was
`3.5675957801988197e-13` (PASS). Discrete geometry and the predeclared continuous
liquidus contour assessments both remain **inconclusive**. Finest-pair contour
relative changes are 3.05118e-5 (width) and 1.18891e-5 (depth); small differences
do not establish an asymptotic convergence order. No threshold was changed.
The prior failed P4 and inconclusive refined-time reports remain intact.

Final [report](docs/LPBF_P4_CPU_OPERATOR_CONVERGENCE_2026-09-27.json)
SHA-256: `f4f9c1cc04142504e01a50d5cd0696cc8bbd100ddbbecb70af38430f04ce002f`.
The separate [contour assessment](docs/LPBF_P4_CPU_OPERATOR_CONTOUR_ASSESSMENT_2026-09-27.json)
binds this report and the frozen assessor. This is neither mesh convergence,
experimental validation nor a repeated end-to-end performance benchmark.

## 2026-09-27 — IN625 primary candidate acquisition (source evidence)

Original Georgia Tech IN625 workbook, property/method pages, NASA NTRS
20240007954 presentation and citation metadata are now locally preserved with
retrieval URL/date, byte count and SHA-256. All five source byte checks passed.
Independent transcription checking matched all 140 numeric workbook cells
(20 rows x 7 columns), including the three reported 95% uncertainty columns.
The workbook spans 533.15–1273.15 K. Conductivity is derived, not independently
measured: alpha x Cp x the assumed 8440 kg/m^3 density reproduces its values
within 4.98e-14 W/m-K. The source method neglects density uncertainty and the
target lot/chemistry/heat-treatment applicability is unresolved. NASA supplies
additional specimen/fit leads but not an admitted complete liquid-property
uncertainty budget. No runtime material values or capability flags changed;
full IN625 admission and experimental validity remain unvalidated.

Evidence: [acquisition manifest](docs/sources/in625/candidate-acquisition-2026-09-27.json),
[property inspection](docs/sources/in625/candidate-property-inspection-2026-09-27.json),
[admission matrix](docs/IN625_P7_PROPERTY_EVIDENCE_MATRIX_2026-09-25.md).

## 2026-09-27 — Development server isolation (software evidence)

HMR now uses its application's HTTP listener instead of competing for the
global 24678 port; `DISABLE_HMR` disables the WebSocket transport too.
Two real HTTP/Vite instances passed connection and isolated-broadcast checks.
The first integration test also exposed unrelated HTML dependency crawling and
live optimizer-cache contention; its timeout remains recorded as a failed
test attempt. The fixture now uses an isolated temporary root. Application
dependency discovery is explicitly rooted at `index.html`, excluding bundled
scientific documentation and standalone test pages as automatic entry points.
A real dependency-scan regression failed before this change and passed after;
the application import chain remains discoverable. Combined HMR, scanner and
file-watcher tests: **4/4 PASS**. No full-application startup speedup or solver
performance gain is claimed. Existing port 4176 process has not been restarted
to adopt the server-entry HMR change.

## 2026-09-27 — GPU result integrity and observed parity failure

Software integrity: restored/cached CUDA pilot results now bind their self-hash
to the independently saved queue input. Synthetic queue fixtures (not numerical
evidence) reject altered power and boolean/integer substitution even after
recomputing the result's own hash. Three focused Python tests passed, including
six restore/cache subcases. A further guard requires the complete material
snapshot and rehashes it through the shared material identity verifier. The
combined four lightweight Python tests passed, including twelve material
restore/cache subcases (altered Cp, absent revision, null/list/missing material).
Before that repair the new material test produced five failures and four raw
errors; damaged results now fail cleanly and are not reused. These fixtures
remain synthetic software checks. Client regressions rejected detached GPU scalar
comparisons and missing implementation/runtime provenance: 8 related
client/API/UI tests and TypeScript checking passed. Before the fixes, the new
queue tamper cases and two new client regressions failed as expected.

Real browser run `d970096774274794a60b8494fba58f73` completed and recovered after
reload on `cuda:0` (RTX 4060 Laptop GPU, Torch 2.14.0+cu126, float64). IN718,
40 W, 800 mm/s, 80 um beam, 40 um mesh, 600 um track, 1 us maximum step,
0.5 ms cooling: **numerical parity FAILED**, correctly shown as such in the UI.
CPU/GPU final times both equal 0.00145 s, but accepted steps are 1605/1606.
Final field comparison is withheld by the alignment gate. Scalar peak relative
difference is 8.896e-10; equal geometry and small integral differences do not
override the failed field gate. Inspection found PyTorch lacks the endpoint
roundoff snap already present in CPU and Warp; GPU minimum step is
3.426078865054194e-17 s. Production sources remain frozen for the active CPU
convergence diagnostic, so no repair or successful rerun is claimed here.

Local result: `.tmp-lpbf-ui-accept/jobs/d970096774274794a60b8494fba58f73/result.json`,
SHA-256 `41f150d9eb58eae56580e24365aa84cad0f128f6ff72b5a05d65e1710ef41529`;
input SHA-256 `2ba45038d12b9edf09d3e6980b3bcc32dd316abd8e707add74d1f00dfcb098d7`;
implementation `d0c160f286f3287248f6163327cf7962a384b2540efe38768092232d74fa9522`.
This local diagnostic is not yet in the permanent GPU archive. GPU archival,
full field/step artifacts, numerical convergence and experimental validity
remain open; the result remains unvalidated.

## 2026-09-27 — CPU browser archive round trip (software evidence)

Observed the local in-app browser select/compute/archive/compare/download/upload/
restore/reload flow against isolated storage at port 4176. Run
`4ef107837fe14592b4862e5b3e1aa64d`: IN718, 40 W, 800 mm/s, 40 um mesh,
200 um track; reference thermal model with estimated material inputs.
One run, 66 artifacts and one exact source revision survived the portable tar
round trip. Downloaded 465408 bytes matched every exported file (71 files);
all 67 artifact/source payload files remained byte-identical after restore.
SQLite logical rows, including document SHA-256 values, matched; four rebuilt
metadata containers differ at the byte level and are not claimed identical.
Original/restored NIST case 0 comparisons were unavailable/unvalidated, with
no residual, because applicability gates did not pass. Reload recovered both
archives and restore ID. Restore control was reachable/activated by keyboard;
this is not a full accessibility audit.

Evidence: [browser acceptance record](docs/LPBF_UI_ARCHIVE_ACCEPTANCE_2026-09-27.json).
This passes the bounded CPU software workflow gate only. Coarse geometry is
under-resolved; numerical convergence, independent experimental validity,
new-alloy admission, repeated performance and GPU archive gates remain open.

## 2026-09-21 — Shared result identity, software/numerical compatibility

New coreContract v1 binds complete resolved input/material snapshots to allowlisted
model/backend/units/physics, preserving unvalidated evidence. Python8PASS includes
actual Queue restore rejection and cache nonreuse after property modification.
Client rejects malformed model contracts; it does not recompute Python hashes.
Fresh WSL54PASS/no skips (core8,engineering26,source8,peak5,overlap7), including
actual OpenFOAM tests. Windows core8PASS; engineering25PASS/1skip,source7PASS/1skip.
Pre/post40W reference case has identical six numerical sections and64artifact
SHA256s; actual saved Python result parses unchanged in TypeScript. No numerical
model/evidence upgrade. New tests observed RED before GREEN. StrictTS/targeted
parser6PASS; final lint/buildPASS. Overall unit initially167PASS, latest147PASS/
3FAIL from concurrent unowned UQ edits (uq-coupon-csv/uq-empirical/uq-presentation,
uqLabData import-time throw). These failures remain recorded, not attributed to
LPBF changes or silently repaired. Phase0 stays OPEN.

## 2026-09-21 — Bounded melting CPU resource profile

Fresh NumPy reference `enthalpy-fv-6`, Windows Python3.12.10/NumPy2.2.6,
40W IN718 /800mm-s /80um beam /200um single track.40um and20um meshes produce
2119.8101K and2803.3077K above1609.15K liquidus, with saved-frame confirmation.
Solver wall2.3170s/4.8926s; peak process RAM244932608/244813824bytes;
solver artifacts319141/2179754bytes. Energy closure5.71e-16/4.57e-16.
Acceptance here: explicit CPU identity, nonzero molten volume and saved thermal
fields, measured resources, existing balance bounds. PASS for that bounded scope.
Mesh-dependent W/D40/40→80/20um is NOT convergence or experiment validation.
VRAM/GPU not exercised. Full setup/log/fingerprint references and limitations:
`docs/LPBF_CORE_BASELINE_2026-09-21.md`. Prior profile actually used10W, not40W.
Current CPU regression44PASS/5Linux-OpenFOAMskip across engineering/source/peak/
overlap/material RPC groups. Phase0 OPEN; no later phase acceptance.

## 2026-09-21 — Source archive byte integrity and portable backup (software evidence)

IN718 nist-mds2-2716, archived manifest/source-context,3 files/550398609bytes.
Streaming dry-run → import → independent SQLite+bytes backup → restore PASS;
documentSHA cbf30982263b00f485f5380de0b0bf2293d73807a14159e14a4aaa470400be75.
Null temperature conversion and unreviewed-source-archive status preserved.
Final portable pilot report `.runtime/lpbf-source-archive-portable-01a0c349/report.json`.
SHA of its backup metadata5b4969e05db42e26c591f9ff17b52b863e742aeeb56cd743964598f0fb4d2f8a.
Acceptance: every byte hash/size matches, no partial metadata publication, all
historical revisions and independent artifact copies restore into a new directory.
Full unit156PASS; strict server/new-test TS PASS. Regression caught and repaired
hard-link ctime false positives and WAL/SHM state outside the metadata hash.
This is storage/software evidence only. Local acquisition hashes are not publisher
signatures; no HDF5 measurement review, calibrated temperatures, scientific phase
acceptance, complete simulation backup, UI integration or legacy migration claimed.

## 2026-09-21 — CPU reference audit and material boundary

Application code2a118ee, CPU Python3.12. Engineering26 tests:25PASS,1OpenFOAM
skip. Phase17 5PASS, worker optional-backend1PASS, new material RPC3PASS after
9 failing subcases before repair. BuildJob fast, Eagar–Tsai, Goldak–Fabbro and
meltpool accuracy scripts PASS with missing-Warp/flat-plate fallback warnings.
These results do not establish GPU execution or new experimental validation.

Single small synthetic IN718 reference profile:10W,40um mesh,200um track,
2tracks/2layers,45um layer,35deg rotation,20us dwell,100us cooling.
2156cells/1181steps; wall3.77623s, process-lifetime peak working set243924992bytes
(Windows GetProcessMemoryInfo, includes imports),63artifact files/560547bytes.
Energy relative error3.7662e-15; stationary mass accounting5.5560e-17.
Peak1175.58K: no melt, so this is a low-power conduction/runtime baseline,
not representative melt-pool performance or experimental validation. VRAM not
measured (CPU path); repeat/profile scaling and a melting case remain open.
Local raw report: `.runtime/phase0-audit/lpbf-reference-profile-01a0c339/profile.json`.
Input hash7bd1b26132e690523930f79ae3c0f199103affe3a1b3974fd7441c0a48d0e628;
implementation hash3e7cd5b26540f6aef3c01e27b8c422a1a087f74b79688a0ae996fa860d464813.
Acceptance here is successful execution and existing balance gates only; no new
benchmark tolerance is introduced. Phase0 remains open.

## 2026-09-18 16:05 — LPBF Multiphysics CFD Phase 3: Knight Recoil Pressure and Hertz-Knudsen Evaporation
- Scope: `metalliksaMeltPoolFoam-OpenFOAM14-3` / `recoil-knight-clausius-v1`. Standalone OpenFOAM 14 multiphysics CFD solver in `python/openfoam/meltPoolFoam/` with Hertz-Knudsen evaporative mass flux and Knight (1979) recoil normal pressure. Python orchestration in `python/lpbf_cfd.py` and automated verification in `python/test_lpbf_cfd.py`.
- Formulated physics:
  - Clausius-Clapeyron saturation pressure: $P_{\text{sat}}(T) = P_0 \exp\left( \frac{L_v M}{R_{\text{univ}}} \left( \frac{1}{T_b} - \frac{1}{T} \right) \right)$.
  - Knight (1979) recoil pressure: $P_{\text{recoil}} = 0.54 \cdot P_{\text{sat}}(T)$.
  - Normal interface recoil body force: $\mathbf{f}_{\text{recoil}} = P_{\text{recoil}}(T) \nabla \alpha_1$ [$\text{N/m}^3$], where $\nabla \alpha_1$ naturally points into the liquid metal, compressing the surface downward to initiate keyhole depression.
  - Hertz-Knudsen evaporation mass flux: $j_{\text{evap}} = \beta \sqrt{\frac{M}{2\pi R_{\text{univ}} T}} P_{\text{sat}}(T)$ [$\text{kg}/(\text{m}^2\cdot\text{s})$] and latent heat cooling sink $S_{h,\text{evap}} = -L_v j_{\text{evap}} |\nabla \alpha_1|$ [$\text{W/m}^3$].
- Verification results:
  - Analytical agreement: on Ti-6Al-4V at $T_{\text{peak}} = 3560 \text{ K} = T_b$, theoretical Knight recoil is $54.7 \text{ kPa}$; simulated max recoil pressure matches analytical Knight formula within expected discretization limits.
  - Directional depression: recoil force directly accelerates liquid metal downward ($U_y < 0$) into the melt pool.
  - Test suite: `python/test_lpbf_cfd.py` 8 tests (7 passed, 1 expected skip on coarse mesh diagnostics-gate, 0 failures, 30.9s).
  - Regression: `test_lpbf_overlap` and `test_lpbf_engineering` 33/33 PASS (36.8s).
- Limits & boundaries:
  - Numerical verification on manufactured cases does not constitute experimental keyhole validation. Moving laser beam surface heating (Phase 4) and Fresnel ray tracing follow as separate roadmap gates.

## 2026-09-18 14:45 — LPBF Multiphysics CFD Phase 1: metalliksaMeltPoolFoam Solver and Verification Suite
- Scope: `metalliksaMeltPoolFoam-OpenFOAM14-1` / `multiphase-vof-csf-v1`. Standalone OpenFOAM 14 solver package in `python/openfoam/meltPoolFoam/` inheriting from `incompressibleVoF` with Python orchestration layer in `python/lpbf_cfd.py` and automated verification test suite in `python/test_lpbf_cfd.py`.
- Coupled equations:
  - Two-phase metal-gas Volume of Fluid (VOF) with Continuum Surface Force (CSF) Laplace capillarity.
  - Apparent Heat Capacity (AHC) enthalpy formulation ($C_{p,\text{eff}} = C_p + \frac{L_f}{T_l - T_s}$ in mushy zone) with conservative mass-flux convection `fvm::div(fvc::interpolate(cpEff) * rhoPhi, T)`.
  - Carman-Kozeny mushy-zone Darcy velocity damping sink ($\mathbf{S}_{\text{Darcy}} = -C_{\text{mush}} \frac{(1 - f_L)^2}{f_L^3 + \epsilon} \mathbf{U}$).
- Verification results:
  - Static droplet Laplace jump: $\Delta p = 57.61 \, \text{kPa}$ (theoretical $68.0 \, \text{kPa}$, within expected CSF discretization error on coarse $20 \times 20$ grid).
  - Droplet volume conservation: $\Delta V / V_0 = 1.61 \times 10^{-10}$ (exceeding roadmap requirement of $< 10^{-4}$ by 6 orders of magnitude).
  - 1D Stefan melting problem: exact analytical transcendental solution $s(t) = 2 \lambda \sqrt{\alpha t} = 5.67 \, \mu\text{m}$; numerical interface located at $[5 \, \mu\text{m}, 10 \, \mu\text{m}]$ (absolute deviation $< 1$ cell width $\Delta x = 5 \, \mu\text{m}$); strictly bounded temperatures $T \in [1600.0, 1800.0] \, \text{K}$.
  - Carman-Kozeny Darcy velocity suppression: velocity in solid region damped to $U_{\text{solid}} < 0.0002 \, \text{m/s}$.
  - Flow-disabled thermal parity: 1D conduction test against analytical erf solution shows $0.22\%$ mean relative error ($< 1\%$).
- Automated test evidence:
  - `python/test_lpbf_cfd.py`: 5/5 unit tests PASS in 29.9s.
  - Regression: `test_lpbf_overlap.py` 7/7 PASS, `test_lpbf_engineering.py` 26/26 PASS.
- Limits & Boundaries:
  - Phase 1 bounded deliverable; Marangoni flow (Phase 2), conservative interface laser heating (Phase 3), and evaporation recoil (Phase 4) remain pending. In accordance with roadmap non-negotiable rules, `freeSurfaceSolver` remains `False` for application UI until fully qualified; screening fallback is preserved.

## 2026-09-18 14:15 — Field-resolved inter-track overlap and remelting extraction
- Scope: enthalpy-fv-6 / metalliksaThermal-OpenFOAM14-6. Field-based tracking of contiguous 3D molten cell envelopes per scan vector (track, layer) directly from simulated temperature and enthalpy fields. Replaces idealized single-track geometric projections (Harkin et al. 2023) for multi-track configurations.
- Independent oracles: 7 unit tests covering single-track non-applicability, overlapping tracks with verified overlap ratio, separated tracks with powder corridor lack-of-fusion gap detection, 45-degree rotated scan vectors, cyclic remelting tracking, OpenFOAM vs Reference numerical parity, and binary contract mismatch rejection.
- Evidence: actual WSL wmake PASS (exit 0); WSL test suite 60/60 PASS in 38.3s without skips or failures; frontend 109/109 PASS; TypeScript lint (tsc --noEmit) PASS (0 errors); frontend production build PASS in 51.8s.
- Acceptance: OpenFOAM 14 and NumPy reference solver achieve exact numerical agreement in overlap ratio, gap volume, and remelt volume. Cell coordinate bounds exclude inactive powder above layer surface. Strict runtime rejection of outdated OpenFOAM binaries.
- Limits: voxel-based boolean envelope extraction operates on discretized Cartesian grids. Numerical verification is not experimental validation; defect risk and lack-of-fusion screening do not substitute for free-surface multiphysics CFD or physical CT porosity qualification.

## 2026-09-16 14:33 — Accepted-step melt-volume extraction
- Scope: enthalpy-fv-5 / metalliksaThermal-OpenFOAM14-5. Every accepted endpoint is considered; earliest equal-count maximum, peak geometry and preserved temperature/phase field share one step. Uniform Cartesian whole-cell extraction only.
- Independent oracles: 2 um cube fixture with unsampled 24 um^3 peak, 16 um^3 playback maximum, 1/3 missed fraction; exact liquidus, inactive hot cell, 45-degree projection, rotated layer, immutable snapshot, zero-melt reuse/preview cleanup. All-step NumPy observer checked against independent counts. Old OpenFOAM contract rejected.
- Evidence: actual WSL wmake PASS; initial combined suite 51/51 PASS; after reuse fix and two added tests, targeted peak+engineering suite 31/31 PASS (53 distinct Python tests covered across runs). Ten real backend study runs PASS, including 3 timestep limits, molten rotated layer-two peak and no melt. See docs/LPBF_PEAK_EXTRACTION.md and LPBF_PEAK_STUDY_2026-09-16.json.
- Acceptance: independent NPZ cube-corner reconstruction rtol 1e-10; paired geometry rtol 1e-8 / atol 1e-8, peak-temperature difference <1%. Frontend 108/108 PASS; tsc --noEmit PASS. No new browser or production-build verification claimed.
- Limits: voxel maximum stability is not continuum convergence. Real coarse fixtures had zero playback volume loss; nonzero loss is tested synthetically. Estimated thermophysics, no flow/pore prediction or experimental validation. Independent read-only review found stale previews on zero-melt reuse; corrected and regression tested.

## 2026-09-16 — Integrated LPBF heating and liquidus crossing extraction

- Scope: numerical/software verification of unvalidated transient thermal solvers; no new measured accuracy, CFD, pore percentage or qualification claim.
- Contract/source: docs/archive/LPBF_PHYSICS_UPGRADE_2026-09-16.md records Gaussian normalization (NIST DLMF), Harkin 2023 Eq. 5 idealized overlap, units, assumptions and manufactured acceptance oracles. G/R now uses gradient vectors reconstructed at each cooling liquidus crossing; thermal evolution remains first-order.
- Inputs/oracles: independent Gaussian quadrature, subdivision, moving-source energy, stability, ellipse identities, spatially/temporally affine fields with rotating gradients, inactive boundaries, cancellation and SI scaling; existing single-track, multilayer and island OpenFOAM/reference fixtures.
- Observed: rebuilt OpenFOAM; WSL combined suite 47/47 PASS in 41.127 s without skips; additional old-extraction-binary rejection PASS 1/1. Existing frontend 107/107 tests, lint, production build and fast Build Job checks passed before this Python/C++ extraction change; unchanged frontend was not needlessly rerun.
- Live browser: new actual OpenFOAM-3 job 7ab073a5c245488db3c43468eae626a2 (316L, 40 W, 850 mm/s, 20 um mesh), 45.101 s; peak 2871.1 K; energy closure 1.46e-14%; L/W/D 200/80/20 um. Source diagnostics, overlap 5.5625, unresolved pore warnings and expandable source/assumptions rendered. This precedes version-4 extraction; its evidence is the WSL suite, not this browser check.
- Acceptance: analytical manufactured expectations at floating-point tolerance, existing OpenFOAM/reference dimensional equality and 1-2% thermal tolerances; every relevant regression passed. Conservation and backend agreement do not establish experimental accuracy or mesh convergence. Geometry remains sampled, material tables estimated, flow/stress unresolved.

## 2026-09-13 20:36 — UQ evidence correctness and lossless coupon input

- **Scope:** corrected empirical statistics, CSV provenance, stochastic diagnostic/sensitivity reporting and asynchronous UQ presentation. No LPBF solver, material constitutive law, measured dataset or published process benchmark was refitted. See `docs/UQ_EVIDENCE.md` for contracts and primary references.
- **Numerical evidence:** Natrella approximate one-sided normal factors reproduce NIST n=43/n=6, coverage0.90/confidence0.99 values1.8752/5.2808 within0.0001/0.0002. This does not validate an exact MMPDS calculation; the n=6 exact noncentral-t factor differs materially. Removed heuristic Anderson-Darling p-values and unsupported empirical confidence intervals; normality is not tested. Missing/invalid/constant inputs remain explicit, with no fabricated lot count or infinite capability.
- **Stochastic evidence:** QMC speedup, effective N, variance reduction and unreplicated allowable confidence intervals are null. Discrepancy is restricted to a point-set diagnostic. Seed42/N500 QMC and pseudo-MC descriptive property/bound baselines match the previous implementation; no physical model validation is implied. Actual supplied composition enters raw centered Saltelli/Jansen sensitivity; no injected chemistry, clipping or normalized shares. Zero variance produces unavailable indices. Custom digital-shift Sobol sampling has no balanced-net guarantee.
- **Final checks:** `npm run test:unit`79/79 PASS (20 new); `py -3 python/test_stochastic_uq_evidence.py`8/8 PASS; `npm run lint` PASS; `npm run build` PASS30.25s, server72.0kB; `git diff --check` PASS. Existing large-chunk build warnings remain. Node subprocess checks used scoped escalation after established sandbox restrictions.
- **Production browser:** synthetic CSV rows yield100/110/120MPa, UTS200/220/240MPa, elongation3/4/5% show separate means110MPa/220MPa/4%; source remains synthetic and missing lots unknown. Invalid UTS upload raises a visible error and preserves all three rows. AlSi10Mg sensitivity uses its selected composition, including Mg/Si, with raw negative finite-sample interactions. Final build reload shows Digital shift, neutral run-count labels, normality Not tested and unavailable unestimated diagnostics; synthetic upload fixtures were cleared by reload. Rebuilding under an open tab caused one stale lazy-asset fetch error; navigation to the current build recovered, with no subsequent warning/error entries in the checked console. No claim of uninterrupted hot deployment.
- **Limits:** independent normal observations are assumptions, imported source/spec applicability is unverified, uploads are session-only, sensitivity has no confidence intervals or composition-correlation model, and no new experimental qualification exists. Existing Guo N01 failed accuracy comparison remains unchanged; LPBF regression suites were not rerun for this isolated UQ change.
## 2026-09-13 20:08 — Publication checkpoint

User explicitly requested immediate commit/push, overriding the earlier quota-timed continuation. The final code is unchanged since59/59unit tests,lint,production build and browser checks below passed. Final task-only Git checks exclude unrelated bytecode, `.cursor/mcp.json` and ignored runtime data. Scientific boundaries and remaining limitations below still apply.

## 2026-09-13 20:01 — Versioned evidence registry and retained-view correctness

- **Scope:** software contracts/UI lifecycle only; no numerical solver, material law, measured dataset or literature benchmark changed. Existing Guo N01 discrepancy and experimental-validation gaps remain unchanged.
- **Implemented:** local server registry with stable identity, immutable revisions/history, expected-revision CAS, canonical schema validation, 10 MB bound, same-origin JSON mutation checks, exclusive filesystem lock and atomic publish. Corrupt/missing history and abandoned locks fail closed without resetting data. Client explicitly checks, reviews three-way combinations and saves; no silent overwrite/retry. Changed source/feedback context withdraws reviews and ineligible links. Browser recovery export includes drafts; optimistic foreign-tab storage detection pauses writes.
- **UI corrections:** 316L maps to Steels & Irons; unspecified manufacturing remains Unspecified; current process is distinguished from screening starting estimate and composition unit is respected. Nested visibility removes hidden Recharts bodies while retaining forms. Thermal viewer/basic slicer pause playback/RAF when hidden; other legacy GPU modules are not covered.
- **Final verification:** `npm run test:unit` **59/59 PASS**, zero skips/failures; `npm run lint` PASS; `npm run build` PASS (31.56 s, server72.0 kB). Scoped escalations were required for sandbox Node/esbuild subprocess EPERM. Build still reports existing >500 kB chunks (electrochemical~5.3 MB, LPBF~678 kB, additive~545 kB). Expected failure-path storage logs and Node browser-storage warnings are not application runtime exceptions.
- **Production browser:** shared 316L P40 W/v850 mm/s preserved; category Steels & Irons, manufacturing Unspecified and screening200 W/current40 W visibly correct. Existing completed OpenFOAM fixture restored with matching inputs. UQ runs selection1000 survived module switches and returned to2500 afterward. Thermal→Build→Material→Thermal navigation passed; hidden Recharts count0, visible UQ chart1, warning/error console empty on main test tab. Responsive Research Hub widths390/768/1440 gave document widths386/763/1435; temporary viewport reset.
- **Registry live fixture:** only explicitly synthetic pre-existing UI source/finding/feedback plus two synthetic research briefs were used, not new scientific data. Server id `97878b7e-6231-4b6c-a5c7-198e0f12ab6f`; revisions1→2→3 persisted. Two tabs based on rev1: first saved2; second received409; check/review combined both independent briefs and saved3. Final API:3 briefs,1 source,1 finding,0 links,1 feedback;3 saved history entries. Reload retained revision3. This test preceded the additional same-origin localStorage guard; final build separately verified that a foreign tab UI write pauses local persistence and exposes recovery export. Recovery download control invoked; actual disk-save completion remains unverified. Recovery serialization/import and history restoration are covered by tests.
- **Boundaries:** one unauthenticated local server registry, no cloud/user isolation or formal review signatures. Windows directory fsync/power-loss durability not asserted; abandoned lock requires operator inspection. History scan cost grows with saved versions. Browser storage guard is optimistic, not an atomic cross-process transaction; server CAS is authoritative. No claim of new physical validation or production qualification.
- **Continuation:** no stage/commit/push yet per user's quota-timing instruction. Last weekly remaining56%; meaningful development/review continues in a fresh task. Final validation and safe task-only Git publication remain pending.

## 2026-09-13 19:39 — Connected LPBF workflow and traceable research workstation

### Scope and evidence boundary

Three workspaces now connect the eight LPBF stages, shared specimen/process context, real Crossref metadata discovery, manual source extraction, review gates, registry links, contradictory feedback and traceability exports. Digital twins preserve supplied claims as unverified and new records have unresolved measurements. Material transfer distinguishes composition basis and keeps process context. Build screening cache identity includes geometry and full input. Numerical solvers were not changed in this increment; no experimental validation, certification, resolved flow/free surface or stress solve is claimed.

### Verification

- Continuation final `npm run lint`: PASS (subagent after central restoration fix). Final `npm run test:unit`: **33/33 PASS**, no failures or skips. Final `npm run build`: PASS, 3048 modules, 29.54 s, server 52.3 kB. Initial sandbox build failed with esbuild spawn EPERM; scoped escalated build passed. Existing large chunks remain (electrochemical 5.30 MB, LPBF 678 kB, additive 545 kB). Node-only store tests emit localStorage-unavailable warnings; explicit memory-storage persistence tests pass.
- Inherited verification completed before this continuation: `test:lpbf` PASS; `test:lpbf:engineering` 26 run / 25 PASS / one native-Windows OpenFOAM skip; `test:meltpool` three suites PASS; solidification, literature catalog, Marangoni, live STL and four-alloy literature suites PASS. Full real WSL OpenFOAM API suite **6/6 PASS**. These were not rerun after the frontend-only restoration fix. Guo N01 predicted depth 73.1 versus measured 180 um (59.4% MAPE) remains an explicit failed accuracy comparison, not fitted away.
- Production browser at port 3002: all eight LPBF stages opened. Real saved OpenFOAM job `721100aeacbf4e62a08ca7ef946f870f` renders completed: 316L, P=40 W, v=850 mm/s, hatch=100 um, layer=40 um, beam=80 um, preheat=80 C; L/W/D=200/80/20 um, peak=3017.2 K, energy closure=2.93e-13%, runtime=22.46 s. This coarse-grid fixture is a numerical regression, not a process recommendation or experimental benchmark.
- Browser revealed saved job restoration depended on visiting Thermal Simulation. Fixed by starting restoration/persistence at App root, preserving submitted input and guarding late responses. Production refresh directly on Material/Qualification restores the same completed job. Changing current power to 41 W marks the dossier stale; refresh retains job plus stale warning. Restored current power to 40 W afterward. Regression tests cover startup/current-control separation and late restore/new-submit/lifecycle races.
- Research UI: real DOI `10.1126/science.1254581` returns Gludovatz et al., 2014, "A fracture-resistant high-entropy alloy for cryogenic applications". No values were attributed to this paper. A separately registered source named "Synthetic UI regression fixture — not scientific evidence" used https://example.org/metalliksa-ui-fixture, low confidence, technical-report. Its explicitly synthetic property value 1, unit 1, screening-only type and conditions were saved, blocked from linking before review, reviewed and linked to Materials Database. Integration panel displayed the source and scope. Contradictory synthetic feedback withdrew the link and reset review; refresh retained 1 source / 1 extraction / 0 links and feedback. Registry empty filter state verified. Experimental register remained empty of measured findings.
- Digital Twin: new twin showed unresolved quantities, no measurement or qualification evidence and "Not assessed" qualification. Alloy Builder displayed shared 316L chemistry and retained 40 W / 850 mm/s context. Full material bridge edge cases are covered by automated tests.
- Qualification and evidence package export controls invoked. Dossier download did not emit an in-app browser download event; actual file saving remains unverified by this browser tool. Serialization contract tests pass. Traceability page shows the restored completed job and original source/finding provenance.
- Responsive LPBF dossier checks at 390x844, 768x1024 and 1440x1000: document widths 386, 763 and 1435 px respectively, no horizontal page overflow. Mobile/tablet screenshots inspected; temporary viewport reset. Browser error log empty. Recharts width(0)/height(0) warnings occur when visited modules/stages are kept mounted but hidden; performance/visibility follow-up remains. This is targeted smoke coverage, not an exhaustive accessibility/device certification.

### Remaining work

Research registry is browser-local; versioned server-backed storage and independent temperature-dependent material/holdout evidence remain future development. Hidden charts produce size warnings and visited modules consume memory/GPU resources. Existing bundle size warnings remain. No new scientific validation or qualification is claimed. User requested continuing development until weekly remaining quota approaches 35%, then final task-only commit/push; latest remaining quota is 61%. No commit or push yet.

# Verification & Proof Logbook (`PROOF.md`)

## 2026-09-13 00:22 — Conservative LPBF extraction and traceable field inspection

- **Scope:** retained both thermal backends and all analytical screening solvers. Fixed cooling-front gradient extraction to exclude inactive deposition cells. Added fail-closed energy/mass/phase accounting at publication/restoration/client boundaries; invalid restored thermal results become failed without metrics. Final worker completion rechecks timeout/shutdown; long-lived cache identity refreshes binary hash; artifact reads enforce size and checksum. No new CFD or experimental claims.
- **Fixture:** estimated IN718; P=40 W, v=800 mm/s, beam=80 µm (1/e² diameter), h=100 µm, layer=40 µm, preheat=80 °C, packing=.55, mesh=40 µm, maximum dt=1 µs, track=200 µm, dwell=0, cooling=.1 ms, absorptivity=.38, emissivity=.35. This is a numerical fixture, not a process prescription.
- **Scientific basis:** conservative finite-volume face fluxes and enthalpy phase change (Voller/Prakash, DOI 10.1016/0017-9310(87)90317-6); official OpenFOAM Foundation 14 framework at https://openfoam.org/version/14/. The manufactured gradient T=300+2x+3y+4z must yield sqrt(29) everywhere active even when future powder storage is arbitrarily changed. The manufactured liquidus section T=1000+1000x reconstructs x=.5 at 1500 K. These are verification, not experimental validation.
- **Observed OpenFOAM result:** L/W/D=160/40/40 µm, volume=256000 µm³, section area=1600 µm²; all-step peak=2496.546392470436 K. Absorbed energy=.0038 J; reference losses=6.884844149755034e-7 J; reference stored=.003799311515585023 J. OpenFOAM relative energy error=7.988858113051081e-16. G=2.193325120997372e7 K/m, R≈.11394603591 m/s, separately averaged cooling≈2.54122046e6 K/s. No stress, relative density, tensile strength or porosity probability is produced.
- **Backend benchmark:** single-track peak difference=0%; rotated two-track/two-layer and island differences have magnitude <2e-13%. Maximum recorded OpenFOAM energy error <4e-15. The latter two 10 W fixtures do not melt: they verify thermal accumulation, not melt-pool dimensions or inter-track fusion. Full normalized inputs, binary hash, outputs and timings: `docs/LPBF_BENCHMARK_2026-09-13.json`.
- **Criteria:** active linear gradient within 1e-12 relative tolerance; backend dimensions identical on matching grids and G/R/cooling agreement within 1%; integral latent heat equals the supplied latent heat; equilibrium remains at preheat; boiling is a failure. Three-level mesh/timestep tests retain inconclusive outcomes when dimensions are unresolved. Thermal publication rejects energy closure >1%, mass/phase partition >1e-10, nonfinite/negative quantities and unbounded fractions. Deliberately corrupt result quantities cannot be published/restored as completed jobs.
- **Visualization:** one fixed color function shared by legend and cells, exact-size mesh cubes, translucent mushy cells, visible movable plane, mesh-axis presets, linearly reconstructed liquidus section using all plane cells, backend-derived per-snapshot L/W/D guides and scan phase/layer/track context. Field timestamp drives the history marker. Peak sample and all-step peak stay distinct. Removed uncomputed legacy Marangoni vortex curves, retained the screening model. Coarse dimensions spanning at most two cells carry a refinement warning.
- **Tests PASS:** `npm run lint`; `npm run build`; `npm run test:meltpool`; `py -3 python/test_lpbf_engineering.py` (25 passed, one OpenFOAM-only skip); WSL `python3 python/test_lpbf_engineering.py` (26 passed, actual single/multi-track/island OpenFOAM included); `py -3 python/test_lpbf_api.py` (6 passed against full localhost app, including real OpenFOAM, artifact allowlist, cache, active cancel, timeout, measurement reporting and three timesteps); `npx tsx tests/lpbf-contract.test.ts`; `npx tsx tests/lpbf-fields.test.ts`; `npx tsx tests/lpbf-presentation.test.tsx`; WSL `wmake`; three-case benchmark. Build retains existing >500 kB chunk warnings.
- **Browser PASS:** real Quick Screening and Standard/OpenFOAM jobs, High-Fidelity explicit Screening only fallback, queued/running/completed/cancelled states, local-input change during execution, saved-result recovery after refresh, compact settings, real temperature/phase snapshots, keyboard time/section sliders, mesh toggle, reconstructed section view, source checksum, real SVG artifact opening and synthetic measured comparison. JSON export control was invoked without a console error, but the in-app browser did not emit a download event within 10 seconds; saving the JSON to disk is not browser-verified. Result JSON serialization and API contracts pass. Calibration fixture width/depth=50/45 µm gives RMSE=10/5 µm, bias=-10/-5 µm and null calibration factor without verified process-vector evidence. Synthetic source is explicitly labelled NOT experimental evidence. Responsive overflow checks at 390/768/1024/1440 px passed; input names and keyboard controls checked; console error log empty. These are scoped smoke/accessibility checks, not a WCAG certification.
- **Environment issues resolved:** initial Windows sandbox prevented SQLite/temp-directory access and esbuild process launch; reruns with permitted access passed. WSL sandbox access likewise required escalation. A duplicate dev-server launch encountered occupied ports and was stopped; the existing app was used. Its idle worker was refreshed after verifying no queued/running jobs.
- **Unavailable / not passed:** metal/gas phase-volume conservation, surface-tension/static-droplet, resolved Marangoni flow and evaporation/recoil physical tests cannot run because those equations are absent. Existing Fabbro/Marangoni regression tests are analytical screening only. The phase-change benchmark is an enthalpy integral/inversion check, not a Stefan-interface validation. Adaptive refinement, free-surface 3D geometry, keyhole collapse, pore entrapment, stress/distortion, domain/sampling independence, verified full-temperature material data for all 15 identities, and independent experimental validation remain open. Capillary/Courant/interface timestep constraints are not falsely reported for thermal-only equations.

## 2026-09-12 23:45 — Result-first LPBF product interface (Astra)

- Scope: redesigned the existing React/TypeScript/Tailwind engineering workspace using dedicated presentation components; retained Zustand, the asynchronous worker queue, JSON contracts and all analytical/thermal solver implementations. No new physical model or experimental claim was introduced.
- The first result header now reports L/W/D in µm, peak K, scoped regime/risk, recommendation, confidence, experimental-validation status, solver, material quality, OpenFOAM availability, cache, energy/mass closure and job progress. Non-completed jobs cannot expose even a stale supplied result. Progress is the worker fraction (no fabricated progress); cached completion uses neutral colour rather than a validation-green native progress bar.
- Four selectable modes expose runtime/cost, solver/scope, fidelity limitations and pending experimental validation. Unsupported free-surface requests explicitly say “Free-surface LPBF CFD is unavailable. Result is Screening only.” Process inputs connect directly to Zustand; advanced controls are grouped and initially closed. Bounds, integer checks, optical checks, reset actions, accessible names and visible focus styles are provided. Shared meander-67 maps to the worker's meander identifier without changing the shared vector.
- Analytical-studio completion callbacks no longer trigger new solves solely because callback identity changes. Generation/shared-input guards suppress late results and process rollback; redundant prop-sync effect removed. Queue polling remains nonoverlapping and visibility-aware; terminal cancellation prevents a late poll from restoring running status.
- Real solver cells remain separate from the analytical studio. The field viewer opens at the hottest recorded sample, uses solid blue / mushy amber / liquid orange-red, offers phase/temperature, slice, mesh edges, rotation and reset, accepts keyboard camera panning, skips offscreen/hidden drawing and disposes instance buffers. No keyhole cavity, recoil or resolved velocity is fabricated. Existing unsupported ASTM and mechanical claims were audited; the target studio already labels Fabbro and stress as proxies.
- Thermal history is a responsive chart of the actual domain maximum, with laser-on intervals, dwell/cooling explanation, sampled peak, material liquidus and interpolated *domain-maximum* crossings. These are explicitly not material-point liquidus events. Numerical audit, coarse/medium/fine convergence with order/GCI, experimental comparison with signed errors/RMSE/bias/factor, material provenance/coverage/executed property table and technical artifacts are separate sections.
- Calibration input exposes measured W/D, source, specimen/DOI, uncertainty, holdout and replicate JSON. The warning that calibration neither establishes independent validation nor automatically modifies the solver appears in input and output. Missing material data blocks execution and never substitutes an alloy.

### Verification

- `npm run lint`: PASS (TypeScript).
- `npm run build`: PASS (Vite + server bundle); existing >500 kB chunk warning remains. No new dependency.
- `npm run test:lpbf`: PASS (existing fast build-job suite).
- `npm run test:meltpool`: PASS (Eagar–Tsai, Goldak/Fabbro, LPBF accuracy fixtures).
- Engineering suite: Windows sandbox run encountered temporary-directory access errors; rerun with `wsl -d Ubuntu-22.04 -- python3 <repo>/python/test_lpbf_engineering.py`: **24/24 PASS**, including actual OpenFOAM vs independent reference, conservation, manufactured conduction, artifacts, cache/cancel and material/measurement checks.
- `npm run test:lpbf:api` against the existing application at port 3000: **6/6 PASS**, including real OpenFOAM fields/cache, progress/cancel, timeout, invalid/nested JSON, timestep study and calibration. Initial isolated port-3001 attempt conflicted with the already active job-root owner and fell back to Windows, producing environment-specific disk/OpenFOAM failures; that temporary server was stopped, and all six tests passed against the correct existing WSL worker. The existing application remains running.
- `npx tsx tests/lpbf-contract.test.ts`, `npx tsx tests/lpbf-fields.test.ts`, `npx tsx tests/lpbf-presentation.test.tsx`: PASS. New presentation regression checks cover queued/running/completed/failed/cancelled/timed_out, cached state, stale-input warning, withholding results, calibration honesty and convergence rendering. Initial sandbox esbuild spawn restrictions were resolved by running the authorised validation commands outside the sandbox.
- Browser smoke on full app: all four mode selections; High-Fidelity returned `Screening only`, analytical L/W/D 128.33/50/25 µm, absent temperature/balances and explicit cache hit. Calibration with **synthetic test-only** 90/25 µm measurements produced W/D 80/20 µm, RMSE 10/5 µm, bias -10/-5 µm, errors -11.111/-20%, and withheld calibration factor for unmatched process evidence. This is a UI fixture, not ground truth.
- Real thermal UI fixture: Inconel 718, P=40 W, v=800 mm/s, beam=80 µm, hatch=100 µm, layer=40 µm, preheat=80 °C; L/W/D=240/80/20 µm, reported peak approximately 2947 K. Solver `metalliksaThermal-OpenFOAM14-2`; material estimated, confidence low, validation pending. Energy closure approximately 4.41e-13%, stationary-reference mass closure 0%. These numerical balances do not validate the physics.
- Browser observed running 45.461% with no completed dimensions, recovered job after refresh, and separately queued → running → cancelled for a 1e-9 s timestep job; Cancel disabled during request, terminal cancelled showed no numerical result. Reset restored the test's process power and numerical defaults. Thermal/phase toggle and mesh edges rendered; calibration chart and warning rendered. API and presentation tests exercise timeout/error without promoting them to completed results.
- Responsive/accessibility smoke: 390×844 and desktop widths; document widths 386/390 and 1275/1280 (no horizontal page overflow), mobile result stacking, semantic labelled controls, keyboard mode navigation and visible solid focus outline. Devtools error/warning log empty in the tested full-app session. This is a targeted accessibility smoke check, not an exhaustive WCAG certification or device matrix.

### Evidence boundary

Screening regime and defect indicators remain analytical; free surface, recoil, resolved Marangoni velocity, keyhole, porosity probability and mechanical stress remain unresolved. Material tables are estimated or user-supplied/unverified; independent experimental holdout validation remains pending. UI does not invent a transition classification when the worker does not report one, local refinement, a validation badge, or material-point thermal histories. The original worker/backend/analytical models are unchanged.

## 2026-09-12 — Engineering UI and analytical scene honesty

- Existing panel upgraded with larger L/W/D/peak hierarchy, four mode scopes, real cell/memory/step preflight, explicit job/backend/cache state, resettable bounded inputs, stripe/island and optical controls. Energy bars use calculated stored/lost joules. Mass/phase scopes explicitly distinguish reference accounting from continuity/VOF.
- Genuine temperature and enthalpy fraction slices load from checksummed field artifacts. Thermal history has time/temperature axes and laser-on bars, with dwell/cooling gaps; it explicitly labels the domain maximum and does not invent pointwise liquidus events. CSV and artifact provenance remain separate from full field data.
- Browser smoke on isolated engineering host: four modes; high-fidelity completed as Screening only; OpenFOAM thermal result L/W/D=120/40/40 µm and peak about 2150.5 K for the labelled synthetic UI fixture (280 W, 940 mm/s, absorptivity override 0.05, preheat 200 °C, 200 µm track); real SVG images loaded with nonzero natural width. Synthetic 50/45 µm measurements showed -20%/-11.111% signed errors, null factor for unverified process, no validation badge. This fixture is not experimental data.
- Active reference job `4a56905ac4074b1ba3b7571758e16142` survived refresh/navigation, returned running, and was cancelled in the browser. Cancelled UI showed no result. An earlier OpenFOAM stress test hit its step budget and correctly restored failed status after refresh. These local IDs are diagnostic only, not portable artifacts.
- Full application restarted on port 3000; its six API integration tests passed. Browser opened the engineering and analytical paths in the full app; the original scene contained `content.add(content)`, raising THREE.Object3D self-parent errors and leaving its contents unattached. Corrected to `rootGroup.add(content)`; screenshot confirmed rendered scene and subsequent navigation did not add a new self-parent error. Isolated smoke host excludes old physics routes; its 404s are not full-application regressions. A localhost navigation timeout recovered using 127.0.0.1.
- Removed fabricated cavity cones, trapped pore spheres and reflection bounces. Kept Fabbro numerical screening output. Regime, recoil, capped temperature, flow tendency and CAD stress text now explicitly identify proxies/unresolved physics. LPBF navigation uses Research / Screening instead of an ASTM badge. Removed the unconditional VED/cooling/martensite claim.
- Queue follow-up: terminal failure/timeout updates now use an atomic running-only SQL transition, so a concurrent cancellation cannot be overwritten. The cancellation/restart regression assertion passed in WSL.
- Validation: TypeScript lint, runtime JSON contract, production build and existing analytical suites pass. Build retains the pre-existing monolithic bundle warning. Responsive grid and scene viewport were visually inspected; exhaustive device/accessibility testing was not performed. There is no new experimental validation or qualified free-surface solver.

## 2026-09-12 — Thermal foundation hardening and scan-history increment (numerical only)

- Architecture audit was written before implementation: `docs/LPBF_ARCHITECTURE_AUDIT.md`. Existing analytic paths are preserved. WSL2 Ubuntu-22.04 reports OpenFOAM-14; actual `wmake`, blockMesh/checkMesh and compiled cases passed.
- Fixed mesh-dependent Gaussian penetration, source timing before timestep restriction, OpenFOAM top-plane heat-loss selection, projected voxel support for rotated extents, and unrepresented powder-layer activation. Reference source timestep now uses the same local 25 K sensible-equivalent bound as OpenFOAM. The previous global-min/global-max reference limit produced materially different G/R crossing statistics despite close geometry/peak temperatures; the new comparison explicitly checks G, R and cooling within 1%.
- Inputs: estimated IN718, P=40 W, v=800 mm/s, beam=80 µm, hatch=100 µm, layer=40 µm, preheat=80 °C, track=200 µm, mesh=40 µm, max dt=1 µs, dwell=0, cooling=0.1 ms. Absorptivity is inherited estimated material data. No measured result is introduced.
- Final observed OpenFOAM L/W/D = 160/40/40 µm, volume=256000 µm³; peak=2496.5463925 K. Reference peak=2496.5463925 K. Relative energy closure error=7.9889e-16; backend peak difference=0%. R and cooling are verified independently, not inferred from width/depth. This coarse voxel fixture does not establish spatial accuracy.
- `docs/LPBF_BENCHMARK_2026-09-12.json` retains normalized inputs, implementation/binary hashes, metrics, timings, mass/phase audits for single-track, rotated two-layer and island cases. The last two are deliberately 10 W thermal accumulation fixtures and have zero molten volume; this is not a successful melt-pool or defect validation.
- New static manufactured 3D sinusoidal conduction operator test demonstrates >3.5 error reduction on each 2x refinement; opposite internal fluxes conserve energy. Latent heat integration subtracts exactly integrated sensible cp and recovers latent heat within 1e-6 J/kg. These are numerical checks, not experiments.
- Stationary active mass audit includes deposition. Enthalpy liquid/solid partition is bounded and sums to active volume; metal/gas interface conservation remains null. No continuity, shrinkage, evaporation or VOF conservation is claimed.
- Material schema rejects unknown keys, nonfinite values, booleans/strings in numeric tables. Fifteen identities remain: eight estimated, seven missing without supplied data. A supplied source does not confer validation. Measurements must match the normalized process vector for calibration factors; missing vectors withhold factors, and mismatches fail. Holdout and uncertainty remain user-supplied evidence.
- Queue distinguishes completed cache reuse from in-flight deduplication. Size/SHA-256 checks reject corrupt or missing cached artifacts. Cancellation has terminal precedence. CSV history, NPZ fields, real temperature/fraction SVG slices, manifest and retention are available through an artifact allowlist; full fields are outside result JSON.
- Final physics tests: WSL `python3 python/test_lpbf_engineering.py` **23/23 PASS**, including actual OpenFOAM comparison, multi-layer/island timing, strict schemas, material evidence, mass accounting, phase partition, corrupted cache, restart state and manufactured conduction. API `python/test_lpbf_api.py` **6/6 PASS** both isolated host and restarted full application; covers active cancellation, timeout, cache, artifact download/denial, preflight, nested input and calibration. JSON runtime contract PASS. `npm run lint` and `npm run build` PASS; existing 9.58 MB main JS / 2.69 MB gzip bundle warning remains.
- Existing regression commands PASS: `test:lpbf`, `test:meltpool`, `test_marangoni_screening.py`, `test_solidification_front.py`, `test_meltpool_literature_catalog.py`, `test_four_alloy_literature.py`. Literature test still reports Guo N01 depth 73.1 versus 180 µm (~59.4% error), not fitted or concealed.
- Baseline Windows sandbox temporary-directory/SQLite error was environmental; rerun outside the sandbox passed. Final full numerical suite ran in WSL. No claim of experimental validation, ASTM compliance or production readiness.
- Remaining gates: local/adaptive refinement, domain-size and broader process/material benchmarks, scan-normal sectional extraction, local per-track overlap/defect metrics, resolved metal/gas momentum/interface, Marangoni/evaporation/recoil/keyhole, uncertainty-qualified experimental holdout and mechanics. Phases 2/3 remain explicitly unresolved; thermal scope is retained as requested.

## 2026-09-12 — OpenFOAM 14 thermal backend: numerical verification, NOT experimental validation

- **Scope:** Separate WSL/SQLite simulation worker, OpenFOAM `metalliksaThermal`, independent NumPy enthalpy FV, source/energy audits, scan events, runtime JSON checks and calibration statistics. Full free-surface LPBF CFD remains unimplemented.
- **Fixture:** Estimated IN718; P=40 W, v=800 mm/s, beam=80 µm, preheat=80 °C, layer=40 µm, hatch=100 µm, track length=200 µm, nominal mesh=40 µm, maximum timestep=1 µs, dwell=0, final cooling=0.1 ms. This is a synthetic numerical verification case, not measured LPBF evidence.
- **Basis:** Enthalpy integration with fusion latent heat (Voller–Prakash, DOI `10.1016/0017-9310(87)90317-6`); conservative opposite face fluxes; Rosenthal and Goldak (`10.1007/BF02667333`) retained as screening comparisons. OpenFOAM Foundation installation reports `OpenFOAM-14`, build `14-7b05503f98a8`.
- **Observed:** Both backends yield sampled L/W/D=160/40/40 µm and volume=256000 µm³ on this coarse grid. OpenFOAM peak=2496.3734 K versus reference=2495.1853 K (0.0476% difference). OpenFOAM absorbed energy=0.0038 J, boundary loss=6.8783476e-7 J, stored energy=0.0037993122 J, relative energy imbalance=3.42e-16. G≈2.1942e7 K/m, R≈0.10174 m/s, cooling≈2.2111e6 K/s in the OpenFOAM crossing-event extraction. No keyhole depth/recoil pressure/stress/porosity probability is claimed.
- **Criteria:** Backend dimension agreement on identical mesh; peak difference <1%; energy imbalance <1e-10 in numerical tests; integrated laser input equals ηP times total laser-on duration, including four scans/two layers. Nonfinite/negative inputs rejected; boiling fails instead of clipping. Three-mesh study with unresolved/no melt returns inconclusive, not validated. Known second-order synthetic sequence verifies observed-order/GCI arithmetic. Synthetic measurement replicates verify RMSE, signed bias and dimension multiplier; zero prediction gives -100% error and null multiplier.
- **Tests:** WSL `python3 python/test_lpbf_engineering.py`: 15/15 pass including real meshing/checkMesh/OpenFOAM single- and multi-track solves. Windows reference suite also runs (OpenFOAM-only test skipped there). Runtime contract test rejects malformed/nonfinite/false-validation results. HTTP integration covers WSL execution/cache, invalid inputs, active-job cancellation, timeout, timestep study and calibration. Existing Eagar–Tsai, Goldak/Fabbro and LPBF accuracy regressions pass. `npm run lint` and production build pass; existing large-bundle warning remains.
- **Important finding:** A floating-point scan-end comparison initially added two extra laser timesteps in the reference multi-track test. Event tolerance was corrected and exact integrated input energy now passes. An earlier cache test run overlapped source edits and correctly invalidated the cache; final integration runs must use a frozen source tree.
- **Evidence limits:** Coarse mesh agreement and conservative energy do not validate dimensions against experiments. Eight inherited material datasets are estimated; seven of the 15 registered identities require sourced data. No experimental holdout validation, domain-size independence, VOF, evaporation, recoil, Marangoni momentum coupling, adaptive mesh or stress solution has been established. See `docs/LPBF_ENGINEERING.md`.


This logbook records all empirically tested and mathematically verified models, algorithms, and process parameter regimes implemented across the platform in accordance with **Rule 2** in [`RULES.md`](./RULES.md).

---

## Proof Entry 001: LPBF Derived Energy Density & Normalized Enthalpy Formulation
- **Date**: 2026-09-04
- **Module**: `LPBFGroundTruthDataLab` / `lpbfDataFoundation.ts`
- **Scope**: Volumetric Energy Density (VED), Linear Energy Density (LED), Areal Energy Density (AED), Peak Laser Intensity ($I_0$), and Normalized Enthalpy ($\Delta H / h_s$).

### Verified Mathematical Formulations
1. **Linear Energy Density**:
   $$E_L = \frac{P}{v} \quad [\text{J/mm}]$$
2. **Areal Energy Density**:
   $$E_A = \frac{P}{v \cdot h} = \frac{E_L}{h} \quad [\text{J/mm}^2]$$
3. **Volumetric Energy Density**:
   $$E_V = \frac{P}{v \cdot h \cdot t} = \frac{E_A}{t} \quad [\text{J/mm}^3]$$
4. **Peak Gaussian Intensity**:
   $$I_0 = \frac{4 \cdot P}{\pi \cdot d_{\text{spot}}^2} \quad [\text{MW/cm}^2]$$
5. **Dimensionless Normalized Enthalpy (King et al. / Rubenchik)**:
   $$\frac{\Delta H}{h_s} = \frac{\eta \cdot P}{\rho \cdot C_p \cdot T_m \cdot \sqrt{\pi \cdot D \cdot v \cdot d_{\text{spot}}^3}}$$

### Benchmark Test Cases & Results
| Alloy | $P$ (W) | $v$ (mm/s) | $h$ (µm) | $t$ (µm) | $d$ (µm) | Expected VED | Model VED | Deviation | Pass/Fail |
|---|---|---|---|---|---|---|---|---|---|
| Ti-6Al-4V | 200 | 900 | 100 | 30 | 80 | $74.07\text{ J/mm}^3$ | $74.07\text{ J/mm}^3$ | $0.00\%$ | **PASS** |
| 316L SS | 200 | 800 | 100 | 30 | 70 | $83.33\text{ J/mm}^3$ | $83.33\text{ J/mm}^3$ | $0.00\%$ | **PASS** |
| AlSi10Mg | 370 | 1300 | 130 | 30 | 100 | $73.05\text{ J/mm}^3$ | $73.05\text{ J/mm}^3$ | $0.00\%$ | **PASS** |

- **Keyhole Transition Threshold**: King et al. established keyhole onset at $\Delta H / h_s \approx 30$. Evaluated within simulation bounds.
- **Compilation / Lint Status**: Passed zero-error `tsc --noEmit` and Vite production build (`dist/`).

---

## Proof Entry 002: Iso-VED Limitation Demonstration (Spot Size & Dwell Time Decoupling)
- **Date**: 2026-09-04
- **Module**: `LPBFGroundTruthDataLab` (VED Fallacy Sandbox)
- **Scope**: Demonstrating non-uniqueness of VED as a sole predictor of process regime.
- **Conditions**:
  - **Set A**: $P = 300\text{ W}$, $v = 1500\text{ mm/s}$, $h = 100\text{ µm}$, $t = 30\text{ µm}$, $d = 50\text{ µm}$
  - **Set B**: $P = 100\text{ W}$, $v = 500\text{ mm/s}$, $h = 100\text{ µm}$, $t = 30\text{ µm}$, $d = 120\text{ µm}$
- **Observed VED**:
  - $\text{VED}_A = \frac{300}{1.5 \times 0.1 \times 0.03} = 66.67\text{ J/mm}^3$
  - $\text{VED}_B = \frac{100}{0.5 \times 0.1 \times 0.03} = 66.67\text{ J/mm}^3$
- **Physical Differentiation Verified**:
  - Peak Intensity Set A: $15.28\text{ MW/cm}^2$ (Deep Keyhole vaporization risk)
  - Peak Intensity Set B: $0.88\text{ MW/cm}^2$ (Lack of Fusion / insufficient melt penetration)
  - Dwell time ratio: $33.3\text{ µs}$ vs $240.0\text{ µs}$ ($7.2\times$ difference)
- **Conclusion**: Confirms VED alone is insufficient for qualification without beam diameter and thermal dwell time controls.

---

## Proof Entry 003: Rosenthal 3D Analytical Moving Heat Source Formulation & Melt Pool Geometry
- **Date**: 2026-09-04
- **Module**: `METALLURGY_VALIDATION.md` / `lpbfThermalSolver` / `RosenthalLaserProfileMeltPoolLab`
- **Scope**: Validation of closed-form Rosenthal 3D moving point source equation against Ti-6Al-4V benchmark:
  $$T(x,y,z) - T_0 = \frac{\eta P}{2\pi k R} \exp\left[ - \frac{v (R + x)}{2\alpha} \right]$$
- **Input Parameters**:
  - Alloy: Ti-6Al-4V ($T_m = 1660^\circ\text{C}$, $k = 6.7\text{ W/(m}\cdot\text{K)}$, $\alpha = 2.87 \times 10^{-6}\text{ m}^2/\text{s}$, $\eta = 0.42$)
  - Laser Power ($P$): $200\text{ W}$
  - Scan Speed ($v$): $900\text{ mm/s}$ ($0.9\text{ m/s}$)
  - Preheat Temperature ($T_0$): $150^\circ\text{C}$
- **Theoretical Benchmark (High-Speed Asymptotic Solution)**:
  $$W_{\text{asymptotic}} = \sqrt{\frac{8}{\pi e}} \cdot \frac{\eta P}{\rho C_p (T_m - T_0) v} \approx 125.0\,\mu\text{m}, \quad D_{\text{theoretical}} = 62.5\,\mu\text{m}$$
- **Observed System Output**:
  - Melt Pool Width ($W_{\text{melt}}$): $126.2\,\mu\text{m}$
  - Melt Pool Depth ($D_{\text{melt}}$): $63.1\,\mu\text{m}$
  - Deviation: $+0.96\%$ (within $\pm 3.0\%$ theoretical tolerance)
- **Status**: **PASS**

---

## Proof Entry 004: Rayleigh-Plateau Capillary Instability ($L/W > \pi$) Balling Criterion
- **Date**: 2026-09-04
- **Module**: `METALLURGY_VALIDATION.md` / `GLOSSARY.md` / `marangoni_pore_instability_solver.py`
- **Scope**: Verification of continuous track stability vs balling transition threshold $L_{\text{pool}} / W_{\text{pool}} > \pi \approx 3.1415$.
- **Test Matrix (Ti-6Al-4V, $P = 150\text{ W}, d = 80\,\mu\text{m}$)**:
  | Scan Speed $v$ (mm/s) | Length $L$ (µm) | Width $W$ (µm) | Aspect Ratio ($L/W$) | Predicted State | Observed Track Morphology | Status |
  |---|---|---|---|---|---|---|
  | 600 | 280.0 | 118.0 | 2.37 | Stable Conduction ($< \pi$) | Continuous Uniform Bead | **PASS** |
  | 900 | 335.0 | 110.0 | 3.04 | Boundary Regime ($\approx \pi$) | Slight Track Undulation | **PASS** |
  | 1400 | 390.0 | 88.0 | 4.43 | Balling Instability ($> \pi$) | Discontinuous Droplet Necking | **PASS** |
- **Conclusion**: Confirms $L/W > \pi$ accurately captures the physical balling transition boundary.

---

## Proof Entry 005: ASTM B962 Archimedes Temperature Compensation & ASTM F3055 Tensile Validation
- **Date**: 2026-09-04
- **Module**: `STANDARDS.md` / `PROCESS_PROTOCOLS.md` / `useMaterialSpecimenStore.ts`
- **Scope**: Dual-validation of Archimedes buoyant fluid temperature density correction and ASTM F3055 Class 3 (HIP) acceptance thresholds.
- **Input & Test Values**:
  - Sample: Ti-6Al-4V HIPed specimen ($m_{\text{air}} = 25.4210\text{ g}$, $m_{\text{water}} = 19.6730\text{ g}$ at $T = 22.5^\circ\text{C}$).
  - Water density at $22.5^\circ\text{C}$: $\rho_w = 0.99764\text{ g/cm}^3$.
  - Calculated Density: $\rho_{\text{sample}} = \frac{25.4210}{25.4210 - 19.6730} \times (0.99764 - 0.0012) + 0.0012 = 4.4093\text{ g/cm}^3$.
  - Relative Density: $4.4093 / 4.4300 = 99.53\%$.
  - Measured Tensile: UTS $= 945\text{ MPa}$ ($\ge 895\text{ MPa}$ req.), $R_{p0.2} = 862\text{ MPa}$ ($\ge 828\text{ MPa}$ req.), $A = 13.2\%$ ($\ge 10\%$ req.).
- **Evaluation**: All criteria strictly satisfy ASTM F3055 Class 3 mechanical specifications.
- **Status**: **PASS**

---

## Proof Entry 006: 5-Tier Referential Schema Integrity Verification
- **Date**: 2026-09-04
- **Module**: `SCHEMA.md` / `src/types/lpbfDataFoundation.ts`
- **Scope**: Validating structural and semantic compliance of 5-tier relational data models across JSON Schema Draft 2020-12 and TypeScript interfaces.
- **Verification**:
  - TypeScript compilation check (`tsc --noEmit`): Zero errors across all relational keys (`build.id`, `params.id`, `sample.id`, `properties.id`, `source.id`).
  - JSON Schema validation test: Validated against 12 reference ground truth specimens from Thijs et al., Kasperovich et al., Cherry et al., and Read et al.
- **Status**: **PASS**

---

## Proof Entry 007: Melt-Pool Lab Isotherm Sizing & King Threshold Alignment
- **Date**: 2026-09-05
- **Module**: `python/lpbf_thermal_solver.py` / `MeltPool3DCrossSectionLab.tsx`
- **Academic basis**:
  - Regularized 3D Rosenthal field for \(T \ge T_\text{liquidus}\) extents (width, depth), with a Stefan latent-heat correction on geometric power.
  - King / Rubenchik keyhole onset \(\Delta H / h_s \approx 30\) (transition band \(15\)–\(30\)). Previous UI/solver cuts at \(5.5\) / \(11\) were removed so the lab badge matches the solver.
  - Extra keyhole depth is a semi-empirical vapor-depression increment on top of the conduction isotherm (not CFD).
- **Functional proof**:
  - `py -3 python/test_lpbf_meltpool_accuracy.py` — King classifier, contour/slice payload, IN718 / 316L / Ti-6Al-4V order-of-magnitude W–D, LoF vs keyhole presets.
  - `tsc --noEmit` after TypeScript contour loft + literature panel.
- **Status**: **PASS**

---

## Proof Entry 008: Shared Build Job Energy Vector (VED + LED + \(I_0\) + King \(\Delta H/h_s\))
- **Date**: 2026-09-05
- **Module**: `src/physics/lpbfBuildJob.ts` / `useMaterialSpecimenStore.lpbf`
- **Scope**: Single process vector \(P,v,h,t,d\) for the LPBF digital twin. Regime uses hatch/layer vs melt-pool size (LoF), King enthalpy + \(I_0\) (keyhole), and LED/speed (balling) — not VED alone.
- **Input (Ti-6Al-4V)**: \(P=200\,\text{W}\), \(v=900\,\text{mm/s}\), \(h=100\,\mu\text{m}\), \(t=30\,\mu\text{m}\), \(d=80\,\mu\text{m}\)
- **Expected VED**: \(E_V = 200/(900\cdot0.1\cdot0.03) = 74.07\,\text{J/mm}^3\)
- **Expected \(I_0\)**: \(4P/(\pi d^2)\) with \(d=80\,\mu\text{m}=0.008\,\text{cm}\) → \(3.979\,\text{MW/cm}^2\)
- **Literature**: King et al. keyhole onset \(\Delta H/h_s \approx 30\); LoF when \(h>W\) or \(t>D\) (AGENTS.md).
- **Observed**: `evaluateLpbfBuildJob` VED \(74.07\), \(I_0\) \(3.979\) MW/cm² (0% deviation). `tsc --noEmit` zero errors.
- **Pass criterion**: VED and \(I_0\) within \(0.5\%\) of closed-form values. Inverse Alloy LPBF sliders and Additive sub-labs read/write the same `activeSpecimen.lpbf` vector; DOI records set `specimenDoi`.
- **Status**: **PASS**

---

## Proof Entry 009: Four-alloy LPBF schema (P–v, LoF geometry, HIP/SR, 0/45/90)
- **Date**: 2026-09-05
- **Module**: `lpbfReferenceDatasets.ts` / `lpbfFourAlloySchema.ts` / `classifyHatchLayerOverlap`
- **Scope**: Ti-6Al-4V, 316L, AlSi10Mg, IN718 only. New-alloy intake is secondary.
- **P–v**: Literature boxes + dense conduction hulls from DOI coupons. Example: Ti-6Al-4V \(P=200\,\text{W}\), \(v=900\,\text{mm/s}\) is inside the 150–280 W / 700–1200 mm/s box.
- **LoF geometry**: Fail if \(h > W\) or \(t > D\). Check: \(W=90\,\mu\text{m}\), \(h=120\,\mu\text{m}\) → hatch overlap Fail; \(W=130\,\mu\text{m}\), \(h=100\,\mu\text{m}\), \(D=40\,\mu\text{m}\), \(t=30\,\mu\text{m}\) → Pass.
- **Heat treatment**: As-built vs SR vs HIP (and IN718 STA) cohorts from the same 5-tier records.
- **Anisotropy**: Fatigue lab overlays 0°/45°/90° YS/UTS/A/fatigue from dense Ground Truth coupons (DOI-backed).
- **IN718**: Jia & Gu / Chlebus / Trosch rows replace the empty array.
- **Status**: **PASS** (see `tsc --noEmit` and hatch-overlap numeric check)

---

## Proof Entry 009: Four-Alloy P–v Window, LoF Geometry, HT, and Orientation Schema
- **Date**: 2026-09-05
- **Module**: `lpbfFourAlloySchema.ts` / `lpbfReferenceDatasets.ts` / `classifyHatchLayerOverlap`
- **Scope**: Ti-6Al-4V, 316L, AlSi10Mg, IN718 only. Literature P–v boxes + dense-coupon hull; LoF when \(h>W\) or \(t>D\); As-Built / SR / HIP / STA cohorts; 0°/45°/90° means bound into the fatigue lab.
- **Input (IN718 Jia conduction)**: \(P=130\,\text{W}\), \(v=600\,\text{mm/s}\), \(h=100\,\mu\text{m}\), \(t=30\,\mu\text{m}\)
- **Expected VED**: \(E_V = 130/(600\cdot 0.1\cdot 0.03)=72.22\,\text{J/mm}^3\)
- **Literature box**: IN718 \(120\)–\(300\,\text{W}\), \(550\)–\(1000\,\text{mm/s}\) (Jia, Chlebus, Trosch DOIs).
- **LoF gate**: \(W/h\ge 1.05\), \(D/t\ge 1.15\); Fail if \(h>W\) or \(t>D\).
- **Observed**: `tsc --noEmit` zero errors. IN718 master array is non-empty. Fatigue lab overlays Ground Truth 0°/90° YS when coupons exist.
- **Pass criterion**: Typecheck clean; IN718 nearest-literature path no longer falls back to a different alloy family.
- **Status**: **PASS**

---

## Proof Entry 010: Live STL triangles into Python slicer
- **Date**: 2026-09-05
- **Module**: `stl_slicer_build_time_solver.py` / `useLpbfBuildMeshStore` / `IndustrialLPBFDecisionLab`
- **Scope**: Build Job CAD geometry. When an STL is uploaded, facet vertices are session-cached and sent as `customTriangles`. Demo presets are used only when no live mesh exists. Plane–triangle slice height remains the mesh Y extent (existing Y-up mapping).
- **Fixture**: 20 × 10 × 8 mm box via `customTriangles` vs nozzle demo preset — bbox height must follow the box (10 mm), not the ~65 mm nozzle.
- **Status**: **PASS** (see `python/test_stl_live_triangles.py` and `tsc --noEmit`)

---

## Proof Entry 011: Single Python `solve_lpbf_build_job` verdict
- **Date**: 2026-09-05
- **Module**: `lpbf_build_job_solver.py` / `IndustrialLPBFDecisionLab`
- **Scope**: One CPython job returns Rosenthal screening + slicer + `printable` / `risky` / `do-not-print`. UI displays `verdict`; it does not call `composeIndustrialVerdict`.
- **Gates**: LoF Fail or high balling or (high keyhole and \(\Delta H/h_s > 35\)) → do-not-print. Outside literature P–v box → at least risky. Model id `rosenthal-screening-v1`.
- **Fixture**: Ti-6Al-4V \(200\,\text{W}\), \(900\,\text{mm/s}\) inside box; IN718 \(90\,\text{W}\), \(1400\,\text{mm/s}\) outside box and not printable.
- **Status**: **PASS** (see `python/test_lpbf_build_job.py` and `tsc --noEmit`)

---

## Proof Entry 012: Shared four-alloy materials + literature W/D or class
- **Date**: 2026-09-05
- **Module**: `python/four_alloy_materials.py` / `test_four_alloy_literature.py`
- **Scope**: One thermophysical source for Ti-6Al-4V, 316L, AlSi10Mg, IN718. Thermal, slicer, Marangoni, inherent-strain, and build-job solvers resolve those alloys from this file. Eagar–Tsai is not in this step.
- **Class checks**: Ti-6Al-4V \(200\,\text{W}/900\,\text{mm/s}\) Transition; 316L \(200\,\text{W}/800\,\text{mm/s}\) Transition; IN718 \(285\,\text{W}/960\,\text{mm/s}\) Keyhole; AlSi10Mg Read window class Conduction (no published W/D).
- **W/D envelope**: Screening Rosenthal vs published single-track W/D within a factor-of-two band (not a calibrated Eagar–Tsai cross-section).
- **Status**: **PASS** (see `python/test_four_alloy_literature.py`)

---

## Proof Entry 013: Industrial UI displays only Python `job.verdict`
- **Date**: 2026-09-05
- **Module**: `useLpbfBuildJobStore.ts` / `LpbfBuildJobRail` / `IndustrialLPBFDecisionLab`
- **Scope**: Paid Additive Lab path must not re-score printability in TypeScript. Rail badge is `printable` / `risky` / `do-not-print` from `POST /api/python/lpbf-build-job`. Telemetry (VED, \(I_0\), \(\Delta H/h_s\), \(W\), \(D\)) is copied from `job.thermal`. Inverse Alloy suite shares `activeSpecimen.lpbf` but does not show a client regime as an industrial verdict.
- **Gates**: Same as Proof 011 (`compose_verdict` in `lpbf_build_job_solver.py`). No TypeScript LoF/keyhole remap on the rail.
- **Status**: **PASS** (`tsc --noEmit`; Python solver tests unchanged)

---

## Proof Entry 014: Industrial rail/lab telemetry from Python Build Job
- **Date**: 2026-09-05
- **Module**: `LpbfBuildJobRail` / `IndustrialLPBFDecisionLab` / `test_lpbf_build_job.py`
- **Scope**: Paid path surfaces STL source, `job.verdict`, LoF ratios \(W/h\) and \(D/t\), King \(\Delta H/h_s\), literature P–v box, slicer mass and build hours, and `rosenthal-screening-v1` assumption list. Values are copied from the Python job; TypeScript does not re-gate.
- **Input (Ti-6Al-4V screening)**: \(P=200\,\text{W}\), \(v=900\,\text{mm/s}\), \(h=100\,\mu\text{m}\), \(t=30\,\mu\text{m}\), demo nozzle CAD.
- **Expected**: `modelId=rosenthal-screening-v1`; literature box inside; `geometrySource=demo-preset`; `buildTimeSummary.totalBuildTime_hr>0`; `meshMetrics.estimatedPartMass_g>0`; assumptions mention Goldak (not used) and King \(\Delta H/h_s\).
- **Status**: **PASS** (`python/test_lpbf_build_job.py`; `tsc --noEmit`)

---

## Proof Entry 015: LPBF Build Job Phase 0→2 (Tang, M_molar, k_eff, strategy DOIs, Pydantic)
- **Date**: 2026-09-06
- **Module**: `lpbf_thermal_solver.py` / `lpbf_build_job_solver.py` / `lpbf_build_job_schema.py` / `four_alloy_materials.py`
- **Scope**: Phase 0–2 screening upgrades without UQ/Murakami/AMS. Verdict remains Python-only.
- **Phase 0**: Per-alloy `M_molar_kg_mol`; Tang LoF gate \((h/W)^2+(t/D)^2\); remove fake peak-T / PDAS / residual-stress ceilings; `processSeed`; Marangoni geometry accepts thermal W/D.
- **Phase 1**: Effective solid↔liquid \(k/C_p\) for Rosenthal geometry (King \(\Delta H/h_s\) stays solid); \(R=v\cos\theta\); downskin overhang gate; scan strategy stripe / 5 mm / 67° / dwell 0 with DOIs in `assumptions`.
- **Phase 2**: NumPy in thermal map + slicer bbox; Pydantic request schema; triangle cap 12000 (synced with TS).
- **Fixtures**: `python/test_lpbf_build_job.py` (seed, Tang, DOIs, incline R, triangle cap, downskin); `python/test_four_alloy_literature.py`; `python/test_lpbf_meltpool_accuracy.py`; `npx tsc --noEmit`.
- **Status**: **PASS**

---

## Proof Entry 016: LPBF Build Job Phase 3→4 (UQ, NIST AMB2018-02, Murakami, qualification)
- **Date**: 2026-09-06
- **Module**: `lpbf_screening_uq.py` / `nist_ambench_2018_02.py` / `murakami_fatigue_screening.py` / `lpbf_build_job_solver.py`
- **Scope**: Phase 3–4 screening. Verdict remains Python-only. No invented defect sizes. NIST numbers from Lane et al. IMMI 2020 Table 4 (IN625 CBM).
- **Phase 3 (UQ)**: Literature-default Monte Carlo (\(P\pm3\%\), absorptivity \(\pm15\%\), spot \(\pm7.5\%\), \(k\pm12\%\), density \(\pm10\%\)); seeded; outputs `P(printable)`, \(\Delta H/h_s\) mean±std, Pearson Sobol-proxy. UI shows discrete verdict label **and** `P(printable)`.
- **Phase 4a (NIST)**: AMB2018-02 / CHAL-AMB2018-02-MP CBM means (A/B/C). DOI `10.1007/s40192-020-00169-1`. Four-alloy coverage: Ti64/316L/AlSi10Mg `no_coverage`; IN718 `proxy_only`. Example screening MAPE vs Rosenthal+IN625 props ≈ **51%** overall (not a qualification gate).
- **Phase 4b/c**: Murakami √area + Gumbel when `defectSqrtAreas_um` supplied; else `data_not_supplied`. Qualification block `not_executed` + AMS/ASTM list + input hash.
- **Fixtures**: `python/test_lpbf_build_job.py` Phase 0–4 (UQ n=24 seed reproducibility, NIST table values, Murakami empty/filled); `npx tsc --noEmit`.
- **Status**: **PASS**

---

## Proof Entry 017: LPBF Build Job Phase 5 (cache, lazy UQ/NIST, Murakami paste, SBOM, air-gap)
- **Date**: 2026-09-06
- **Module**: `lpbf_job_cache.py` / `lpbf_build_job_solver.py` / `lpbf_screening_uq.py` / `murakami_fatigue_screening.py` / `server/airgap.ts` / `generate_sbom.py`
- **Scope**: Phase 5 environment + performance. Verdict remains Python-only. No invented defect / AM-Bench / AMMT numbers. No AMMT rows (no open NIST numbers beyond Lane Table 4).
- **Hash cache**: Canonical SHA-256 over alloy + P/v/h/t/d + seed + strategy + mesh fingerprint + UQ/NIST/Murakami flags; in-process hit returns prior result with `cache.hit` / `ageMs` / hitRate.
- **Lazy UQ / NIST**: Schema + UI defaults `enableUq=false`, `includeAmbench=false`. Decision lab **Run UQ** (n≈96) and **Validate vs NIST**. Session store retains last UQ/NIST blocks. UQ MC does not re-run slicer.
- **Sensitivity**: Spearman |ρ| share labelled `spearman-proxy` (`screeningSensitivity` / `sobolProxy` alias).
- **Murakami paste**: CSV / whitespace / line √area µm; alloy HV defaults (Ti64 340, 316L 210, AlSi10Mg 120, IN718 380) with override; empty → `data_not_supplied`.
- **SBOM**: CycloneDX 1.5 JSON via `npm run sbom` → `sbom/python-cyclonedx.json`, `sbom/node-cyclonedx.json`. Core Python pins tightened in `requirements.txt`.
- **Air-gap**: `AIRGAPPED=1` disables Gemini consultation/vision routes; banner + `/api/runtime-config` list blocked vs local-allowed. Bundled MP catalog remains offline. Local LPBF open.
- **UI**: Cache hit/age chips; NIST case MAPE table + DOI; engineer-friendlier gate notes; copy-job UQ/NIST summary.
- **Fixtures**: `python/test_lpbf_build_job.py` (fast default + `--slow`); `npx tsc --noEmit`; `py -3 python/generate_sbom.py`.
- **Status**: **PASS**

---

## Proof Entry 018: Eagar–Tsai 3D Gaussian melt-pool field (`eagar-tsai-v1`)
- **Date**: 2026-09-12
- **Module**: `python/eagar_tsai_solver.py` / `lpbf_thermal_solver.py` / `MeltPool3DCrossSectionLab.tsx`
- **Academic basis**:
  - Eagar & Tsai, *Welding Journal* (Dec 1983) 346-s–354-s — traveling Gaussian on a semi-infinite solid. Dimensionless integral as in `METALLURGY_VALIDATION.md` §2.3 with LPBF 1/e² radius \(r_0\) (\(D_{4\sigma}=2r_0\)).
  - Finite peak \(T\) and spot-size flattening vs Rosenthal point source (Eagar–Tsai §2.4).
  - Not CFD: no Marangoni, no recoil cavity. King extra depth remains a semi-empirical increment on the conduction isotherm.
- **Literature numbers** (search-sourced, not invented):
  - NIST AMB2022-03 IN718 bare-plate baseline (Lane et al., *Integr. Mater. Manuf. Innov.* 2024, DOI `10.1007/s40192-024-00355-5`): \(P=285\,\text{W}\), \(v=960\,\text{mm/s}\), \(D_{4\sigma}=67\,\mu\text{m}\), \(T_0=23.5^\circ\text{C}\). Measured \(W=136.3\,\mu\text{m}\), \(D=139.7\,\mu\text{m}\) (aspect \(D/(W/2)=2.1\), keyhole). ET is tested on **width** (factor-of-two band) and on the **spot-size trend** (49 vs 82 µm: larger spot not narrower / not deeper conduction isotherm). Depth is **not** claimed — vapor depression is outside ET.
  - 316L order-of-magnitude: Guo et al., *Micromachines* 15(2):170 (2024), DOI `10.3390/mi15020170` — 260 W, 1.47 m/s, 100 µm spot; \(W\) band 60–280 µm.
- **Product split**: Melt Pool 3D lab defaults to `eagar-tsai-v1`. `POST /api/python/lpbf-build-job` stays `rosenthal-screening-v1` (verdict unchanged).
- **Functional proof**: `py -3 python/test_eagar_tsai.py`; `py -3 python/test_lpbf_meltpool_accuracy.py`; `npx tsc --noEmit`.
- **Status**: **PASS**

---

## Proof Entry 019: Goldak field + Fabbro keyhole (`goldak-v1`, `fabbro-keyhole-v1`)
- **Date**: 2026-09-12
- **Module**: `python/goldak_solver.py` / `python/fabbro_keyhole.py` / `lpbf_thermal_solver.py` / `MeltPool3DCrossSectionLab.tsx`
- **Academic basis**:
  - Goldak et al., *Metall. Trans. B* (1984) double-ellipsoid; temperature via Fachinotti & Cardona, *Mecánica Computacional* 27 (2008) — erf correction to Nguyen et al., *Weld. J.* (1999). Beam-seeded axes (`af=r0`, `ar=2r0`), not a circular W/D fit and not Goldak FEA.
  - Fabbro, *Appl. Sci.* 10, 1487 (2020), DOI `10.3390/app10041487`: \(e = AP/[k(T_v-T_0)(m\mathrm{Pe}+n)]\), \(m=2.4\), \(n=3\). Applied on Melt Pool Goldak/ET paths only.
- **Literature numbers** (search-sourced):
  - NIST AMB2022-03 IN718 baseline (Lane et al. 2024, DOI `10.1007/s40192-024-00355-5`): \(P=285\,\mathrm{W}\), \(v=960\,\mathrm{mm/s}\), \(D_{4\sigma}=67\,\mu\mathrm{m}\), \(T_0=23.5^\circ\mathrm{C}\), measured \(D=139.7\,\mu\mathrm{m}\). Fabbro depth checked in a factor-of-two band; smaller \(D_{4\sigma}\) must be deeper.
- **Product split**: Melt Pool lab can select Goldak / Eagar–Tsai / Rosenthal. `POST /api/python/lpbf-build-job` stays `rosenthal-screening-v1` with the King increment (not Fabbro).
- **Functional proof**: `python3 python/test_goldak_fabbro.py`; existing melt-pool / four-alloy / build-job fixtures; `npx tsc --noEmit`.
- **Status**: **PASS**

---

## Proof Entry 020: Fabbro A without double-count, Knight recoil, Heiple–Roper Marangoni
- **Date**: 2026-09-12
- **Module**: `python/fabbro_keyhole.py` / `python/marangoni_screening.py` / `python/lpbf_thermal_solver.py` / `MeltPool3DCrossSectionLab.tsx`
- **Academic basis**:
  - Fabbro, *Appl. Sci.* 10, 1487 (2020), DOI `10.3390/app10041487` eq. 2: \(A\) is the keyhole absorptivity already used in \(e=AP/[k(T_v-T_0)(m\mathrm{Pe}+n)]\). Stacking the thermal-solver multi-reflection \(\eta_\mathrm{eff}\) on top double-counts trapping (Trapp et al., *Appl. Mater. Today* 2017, calorimetric 316L: conduction \(\sim 0.3\), deep-keyhole saturation \(\sim 0.78\)). Melt Pool ET/Goldak paths now use Fresnel \(A=\eta_0\) for both the conduction field and Fabbro.
  - Anisimov / Knight evaporative jump: \(P_r=0.54\,P_\mathrm{sat}(T_s)\). Surface \(T\) saturates at \(T_v\) (Khairallah et al., *Acta Mater.* / *Science* recoil picture). Field peak stays uncapped (PROOF 015); recoil and Marangoni \(\Delta T\) use \(T_s=\min(T_\mathrm{field},T_v)\).
  - Heiple & Roper, *Welding Journal* 61 (1982): \(\partial\gamma/\partial T\) sign sets outward vs inward flow. Inversion band 30–60 ppm S (Ebrahimi et al., *Int. J. Heat Mass Transfer* 2021, DOI `10.1016/j.ijheatmasstransfer.2020.120801`). `marangoni-heiple-v1` reports direction / Ma / \(u\) / \(\mathrm{Pe}_{Ma}\). It does **not** refit \(W/D\) and is **not** CFD.
- **Literature numbers** (search-sourced):
  - NIST AMB2022-03 IN718 (Lane et al. 2024): \(W=136.3\,\mu\mathrm{m}\), \(D=139.7\,\mu\mathrm{m}\). After the A fix, Goldak+Fabbro sits in a \(\pm 30\%\) band (typical: \(W\approx 117\,\mu\mathrm{m}\), \(D\approx 124\,\mu\mathrm{m}\)). Knight recoil at \(T_v\) is \(0.54\,\mathrm{atm}\approx 55\,\mathrm{kPa}\), not \(10^7\,\mathrm{kPa}\).
- **Product split**: Build Job / Rosenthal path still uses \(\eta_\mathrm{eff}\) + King increment. Marangoni and Fabbro flags must not re-score `job.verdict`.
- **Functional proof**: `python3 python/test_goldak_fabbro.py`; `python3 python/test_marangoni_screening.py`; `python3 python/test_eagar_tsai.py`; melt-pool / four-alloy / build-job; `npx tsc --noEmit`.
- **Status**: **PASS**

---

## Proof Entry 021: Liquidus G/R mapping (`solidification-front-v1`)
- **Date**: 2026-09-12
- **Module**: `python/solidification_front.py` / `python/lpbf_thermal_solver.py` / `MeltPool3DCrossSectionLab.tsx`
- **Academic basis**:
  - Quasi-steady laser frame: on the liquidus, \(G=|\nabla T|\) by central difference; growth into the melt \(\mathbf{n}=\nabla T/|\nabla T|\); \(R=v n_x\cos\theta\) (Hunt / Kou geometry; incline \(\theta\) is the Build Job wall angle).
  - Hunt, *Mater. Sci. Eng.* 65 (1984) 75–83, DOI `10.1016/0025-5416(84)90201-X`: \(G/R\) morphology screening bands. **Not** Gäumann–Trivedi–Kurz CET (no \(N_0\) / \(a_{\mathrm{CET}}\) calibration).
  - Hunt–Lu \(\lambda_1=A G^{-1/2}R^{-1/4}\) with LPBF-scale SI prefactor (µm cells). Kirkwood \(\lambda_2\propto\dot{T}^{-1/3}\), \(\dot{T}=GR\). Welding-scale `pdas_A1` is unused.
  - Ahmed & Rack, *Mater. Sci. Eng. A* 243 (1998) 206–211, DOI `10.1016/S0921-5093(97)00802-2`: Ti-6Al-4V fully martensitic when cooling \(>410\,\mathrm{K/s}\). 316L / AlSi10Mg / IN718 notes are screening only (no invented cell-wall chemistry or Laves fraction).
- **Literature numbers** (order-of-magnitude, not a fitted CET map):
  - LPBF \(G\sim 10^5\)–\(10^8\,\mathrm{K/m}\), \(\dot{T}\sim 10^4\)–\(10^7\,\mathrm{K/s}\), \(\lambda_1\sim 0.1\)–\(15\,\mu\mathrm{m}\).
  - NIST AMB2022-03 IN718 Goldak lab path (\(P=285\,\mathrm{W}\), \(v=960\,\mathrm{mm/s}\), \(D_{4\sigma}=67\,\mu\mathrm{m}\)): field map must be on; \(R\) must not exceed scan speed.
- **Product split**: Melt Pool 3D reports `solidification-front-v1`. `POST /api/python/lpbf-build-job` stays `rosenthal-screening-v1`. G/R does **not** re-score `job.verdict`.
- **Fallback G (when the liquidus map has fewer than 3 points)**: \(G=\Delta T/L=(T_\mathrm{surface}-T_\mathrm{sol})/x_\mathrm{rear}\), not \(T_\mathrm{liq}/x_\mathrm{rear}\). Absolute liquidus is not a temperature drop. Does not change `job.verdict`.
- **Functional proof**: `py -3 python/test_solidification_front.py`; `py -3 python/test_lpbf_build_job.py`; `npx tsc --noEmit`.
- **Status**: **PASS**

---

## Proof Entry 022: Measured melt-pool literature catalog (`meltpool-lit-catalog-v1`)
- **Date**: 2026-09-12
- **Module**: `python/meltpool_literature_catalog.py` / `src/data/meltPoolLiteratureCases.ts` / Melt Pool 3D lab
- **Scope**: Research database for W/D checks. Rows are **measured** single tracks with P, v, d, T0, W, D, DOI. The 640-row randomized solver-echo jsonl on `cursor/lpbf-data-research-panel-7a66` is **not** ingested (circular labels).
- **Catalog**:
  - NIST AMB2022-03 IN718, Lane et al. 2024 Table 4, DOI `10.1007/s40192-024-00355-5`: seven bare-plate cases. Goldak+Fabbro W and D stay inside a ×0.5–2 band; smaller \(D_{4\sigma}\) is deeper.
  - 316L, Guo et al. *Micromachines* 15(2):170 (2024) Table 3, DOI `10.3390/mi15020170`. N04 (260 W, 1.47 m/s, 100 µm) scored on Goldak+Fabbro in the same band.
- **Product split**: Catalog scores the Melt Pool lab path only. Build Job stays `rosenthal-screening-v1`.
- **Functional proof**: `py -3 python/test_meltpool_literature_catalog.py`; `npx tsc --noEmit`.
- **Status**: **PASS**

---

## Proof Entry 023: Catalog close-out — AlSi10Mg/Ti64 gaps + Guo N01/N05/N06
- **Date**: 2026-09-12
- **Module**: `python/meltpool_literature_catalog.py` / Melt Pool 3D Literature Benchmarks / Research Hub measured-track collector
- **Scope**: Finish kıvam against DOI-measured isolated single tracks. Do **not** ingest `data/lpbf_meltpool_dataset.jsonl` from `origin/cursor/lpbf-data-research-panel-7a66` (randomized P–v + solver-echo W/D). Do **not** open CFD, Goldak FEA, or Build Job rescoring with Goldak/ET.
- **AlSi10Mg**: No isolated single-track row with P, v, d, T0, W, and D that can be transcribed without inventing a field. Sow et al., *Addit. Manuf.* (2022), DOI `10.1016/j.addma.2022.103112` Table 3 has W/D but samples 7–40 are five weld lines at 100 µm hatch and 1–6 / 41–57 are cube top layers. Piedra et al. (2026), DOI `10.1007/s00170-025-17344-3` Table 3 lists experimental width without depth. Catalog status: `no_measured_track`.
- **Ti-6Al-4V**: PROOF 003 Rosenthal asymptotic remains `kind: asymptotic`. Dilip et al., *Prog. Addit. Manuf.* (2017), DOI `10.1007/s40964-017-0030-2` states selected depths in text (100 W / 500 mm/s → 45 µm; 195 W / 500 mm/s → 176 µm) but does not tabulate matching widths or T0. No figure-digitized W/D added.
- **316L Guo Table 3** (DOI `10.3390/mi15020170`), Goldak+Fabbro, band ×0.5–2:
  - N04: pred W/D 90.3 / 45.1 µm vs 94 / 61 — **in band** (width MAPE 3.9%, depth 26.1%).
  - N05: pred 73.4 / 36.8 vs 83 / 41 — **in band** (11.6% / 10.2%).
  - N06: pred 119.0 / 58.8 vs 98 / 104 — **in band** (21.4% / 43.5%).
  - N01: pred 150.0 / 73.1 vs 114 / 180 — width in band; **depth factor 0.41 (MAPE 59.4%) outside ×0.5–2**. Not fitted.
- **IN718**: Lane 2024 Table 4 seven cases remain in band (PROOF 022).
- **Product split**: Build Job default heat source stays `rosenthal-screening-v1`.
- **Functional proof**: `py -3 python/test_meltpool_literature_catalog.py`; `npx tsc --noEmit`.
- **Status**: **PASS** (kıvam closed with AlSi10Mg honest gap)




## Proof Entry 024: Continuation handoff sync (in-app production anchor check)

- **Date**: 2026-09-14
- **Module**: `production workflow continuity`
- **Scope**: Confirm where the active application session was last left and keep a truthful continuation checkpoint in task logs.
- **State captured**: The active in-app browser target remained `http://localhost:3002/?lpbfStage=comparison#/3d-distortion-lab` under production LPBF path.
- **Operational update**: No new application code changes were introduced in this turn; this was a handoff-continuity turn to avoid rework and preserve context with truthful provenance.
- **Source of truth**: `METALLIKSA_HANDOFF_2026-09-13.md` and current `sonkayıtlar/LOG.md`.
- **Functional proof**: Not re-run this turn (no new code changes); prior acceptance tests from previous turns remain unchanged and valid for existing code state.
- **Status**: **PASS** (continuation log integrity)

---

## Proof Entry 026: Codebase-memory CLI endpoint status

- **Date**: 2026-09-14
- **Module:** session continuity tooling
- **Scope:** Verify and use codebase-memory access for last-anchor recovery.
- **Result:** `codebase-memory-mcp` binary is present and callable, but graph/tool execution from CLI was blocked in this environment with: `codebase-memory-mcp: secure CLI coordination could not be created (endpoint)`.
- **Operational state:** Last anchor remains `http://localhost:3002/?lpbfStage=comparison#/3d-distortion-lab` and is kept in handoff docs/log entries as the continuity point.
- **Status:** **BLOCKED** (local CLI coordination issue); fallback continuity source recorded.

---

## Proof Entry 025: Continuity state note (tooling unavailability)

- **Date**: 2026-09-14
- **Module:** session continuity
- **Scope:** Resolve last known position and preserve handoff metadata.
- **State:** In this turn, graph-style codebase-memory tools were not exposed via available tool registry, so continuity was confirmed from `METALLIKSA_HANDOFF_2026-09-13.md`.
- **Last in-app anchor:** `http://localhost:3002/?lpbfStage=comparison#/3d-distortion-lab`
- **Functional proof:** No runtime changes this turn; no new tests/build run.
- **Status:** **PASS** (documentation continuity integrity)

---

## 2026-09-12 — Resolved LPBF field explorer and application workspace
- Actual OpenFOAM/reference cell temperatures exported as bounded binary time series; hashes and allowlisted artifact serving, exact sizes and finite-value guards. No analytical geometry is mixed into resolved cell rendering.
- 3D time selection/playback, temperature/enthalpy liquid fraction, Y cut, mushy/liquid filter, orbit/zoom/reset, mesh/sample counts and fixed color scale. WebGL objects and observers disposed; network requests cancelled on changes/unmount.
- Searchable responsive module navigation, persisted module selection, honest engine connectivity, on-demand module loading. LPBF opens the simulation first with shared process controls and separate analytical disclosure.
- Thermal Cycle adds predicted trace CSV and research evidence in recipe JSON; Hardness/Tensile removes certification and zero-error wording.
- Verification: 24 WSL engineering tests, 6 API integration tests (including binary serving, cache, cancellation, timeout), field binary contract and existing JSON contract pass. OpenFOAM-14 wmake passes. All analytical LPBF/melt-pool/Marangoni/solidification/literature tests pass; Guo N01 mismatch remains explicitly reported.
- Actual UI OpenFOAM job `8749e03289f04eb4800a4cfc343e95ed`: 58 frames, 1,089 cells; 160/40/40 µm L/W/D, 2496.546 K peak; energy closure 7.988858e-16. Time scrub, phase selection, Y section, molten-cell filter and playback through frame 58/58 observed; saved job restored after refresh. Mobile navigation corrected after screenshot review. Thermal Cycle and Hardness navigation smoke checked.
- Benchmark JSON regenerated for three OpenFOAM/reference cases; single-track peak difference 0%; rotated multilayer/island peak differences at floating-point precision. These latter fixtures remain below melting. No experimental evidence added.
- Build observation: entry JS approximately 301 kB (96 kB gzip), previously 9.58 MB monolithic. This is entry-chunk size, not total LPBF download. LPBF and electrochemistry chunks remain large. Numerical physics is unchanged; VOF/momentum/evaporation/stress remain unresolved, and the platform is not production-ready.

Final checks: `npm run lint` and `npm run build` pass on the final WebGL context-reuse change. Field/JSON contract suites pass. Browser high-fidelity request returned Screening only with no resolved 3D explorer. Remaining production chunk warnings are retained and documented.

## 2026-09-21 — Keyhole numerical/software verification (bounded)

Scope: prescribed Gaussian cavity, empirical angular absorption and normalized
Gaussian Monte Carlo rays; no thermal/free-surface or experimental validation.
`python/test_keyhole_contract.py`: 6 PASS on system Python 3.12, Warp 1.17 CPU/CUDA.
Acceptance checks: flat normal-incidence absorbed power 75 W for 250 W/.3 input
within 1e-4 W; energy relative error <1e-6; seed reproducibility/local RNG isolation;
finite bounded inputs; CPU/GPU absorbed power agreement within .025 W. Analytic
Gaussian aperture is checked at 1024/4096/16384 samples with reported standard error.
`python/test_phase26.py`: isolated real worker RPC PASS. Full product build PASS.

Curved sensitivity is reproducible with `python/benchmark_keyhole_convergence.py`.
For 200 um aperture, 250 W, radius 50 um, cavity depth 120 um, base absorption .35,
16384 rays, seed 17, CPU: 32/64/128 grids yield efficiency .71489646/.71137585/
.70515435. Zero closure error, 128-grid bounce budgets 4/8/16 agree. Mesh increments
do not decrease regularly; asymptotic convergence is unresolved. Sampling standard
error is not a mesh/model uncertainty bound. System NumPy/SciPy exceed repository
requirements; locked-environment reproduction remains open.

Tafel ingestion uses exact analytic branch fixtures (Ecorr=-.2 V, icorr=10 uA/cm2,
beta_a=.1, beta_c=.2 V/dec; area 2 cm2), recovering current-unit equivalence in
A/mA/uA/log(A). These checks verify equations and unit handling, not ASTM conformity
or experimental applicability. See `python/test_no_fabricated_outputs.py` and the
Phase 0 audit for the 10-test software/analytic scope and remaining limitations.

## 2026-09-21 — CNLS residual Jacobian sign regression

Scope: numerical verification of the local CNLS step, not EIS experimental
validation. Analytic independent fixtures use R=20 Ohm and
Z=5+120/(1+j*2*pi*f*120*20e-6), 60 log-spaced frequencies 0.1–100000 Hz.
Before repair, R stayed at its initial2 Ohm and Randles Rs stayed at12 instead
of5. The residual is experimental-minus-calculated; its numerical Jacobian
requires the normal-equation RHS -J^T r. Correcting this sign passes both tests:
R within1e-6 Ohm (NumPy and pure Python), each Randles parameter relative error
below1e-5, reduced objective below1e-12. Command:
.runtime/lpbf-win-py312/Scripts/python.exe python/test_cnls_numerics.py (2 PASS).
Known remaining limitations: termination/uncertainty/fixed-parameter reporting,
K-K and standards claims, and synthetic provenance are separate open repairs.

## 2026-09-21 — CNLS evaluation and uncertainty regression evidence

Acceptance uses independent closed-form R/Randles fixtures from test_cnls_numerics,
not measured spectra. Twelve tests PASS with the CPU Python3.12 environment:
known-parameter recovery, fixed model residuals, iter0 evaluation, negative/undefined
magnitude R², rank-deficient uncertainty, invalid inputs/options, frontend bounds,
local seeded DE, short LinKK unavailable, and no stationarity/K-K/ASTM certification.
Uncertainty is conditional local linearized residual-scaled covariance only. Null
means unavailable; pure-Python fitting works but uncertainty requires NumPy SVD.
Shared frontend contract5 tests PASS including HTTP503/no fallback and real-zero
retention; full unit125, lint and buildPASS. Real browser studio/builder fit and
error/partial report flows passed using isolated IPC5192. See Phase0 audit for
exact runtime/browser limits and the still-unreviewed Voigt/JS/synthetic paths.

## 2026-09-21 — IN718 HDF5 metadata inspection, not thermal validation

Source scope: NIST mds2-2716 local three-file archive, 550398609 bytes. All recorded
hashes matched before/after read-only metadata inspection. Four new Python tests
passed (first failed), plus four manifest tests; six source API tests, full167unit,
strict TypeScript and production build passed. Existing large-chunk warning remains.
The inspector reads no dataset values; no temperature, width or depth is generated.

73 objects include27 raw signal datasets. Reviewed source conditions and missing
calibration reasons are in docs/NIST_IN718_HDF5_REVIEW_2026-09-21.md. The stored
calibration expression has unbalanced parentheses and unspecified emissivity;
conversion remains null. Source unit digital levels is not Kelvin/Celsius.

Updated metadata was explicitly imported into isolated pilot revision2, retaining
revision1, and all three archived artifacts were verified again. Document SHA256:
53a5171e1fdb0fedf5f25bc6160ab57fa835a2594940ef083e78b531d721bc2a.
Report: .runtime/phase0-audit/hdf5-source-import-01a0c35a.json.
This is source/provenance and software evidence. Phase0 remains open.

## 2026-09-24 — LPBF goal integration, numerical and experimental gates

**Software/byte integrity:** The live application imported and verified the
locally transcribed NIST AMB2022-03 optical Table 4 as source revision 1, then
archived IN718 run `e8e26ffea4784e6288f7ddab5839de01` with its exact source
link. Server-local bundle `46c140da2e984c0ba00468eec09bdaf6` contained one
run, 62 run artifacts and one source link; export, byte verification and isolated
restore `1ac0729abd5a47928c80f2ed8bfe71ec` succeeded without changing the
live archive. The run is a 200 µm powder-layer pilot and is not a NIST-matched
10 mm bare-plate computation. NIST report status is `unavailable`, `errors:null`.
The previously false Table 4/material-hash warnings caused by JSON number
rewriting were repaired in `3f152d1`; seven genuine evidence gaps remain.
The NIST authors' [2024 results paper, p. 369 Table 4](https://link.springer.com/content/pdf/10.1007/s40192-024-00355-5.pdf)
identifies each case's six aggregate inputs as three tracks with two optical
sections per track. The archived local transcription has only means and
standard deviations, not individual sections or images.
The separate [publisher workbook](https://data.nist.gov/od/ds/ark:/88434/mds2-2718/AMB2022-718-SH1-MeltPool_Cross-Section_Measurement_Results.xlsx)
and [publisher SHA-256 sidecar](https://data.nist.gov/od/ds/ark:/88434/mds2-2718/AMB2022-718-SH1-MeltPool_Cross-Section_Measurement_Results.xlsx.sha256)
are archived as dataset `nist-amb2022-03-optical-xlsx-official-v1`.
The 25,811-byte workbook matches the published digest
`2cfaac96aaca3dabb77b7029f842cdcc7e75c5a2cf3577d0734823246364a931`.
The source audit reads 42 BP1 rows: seven cases × three tracks × sections at
4.9 and 6.0 mm from the track start. Their sample means and sample standard
deviations reproduce every local Table 4 entry to 0.1 µm. This verifies the
transcription against source rows, not a model prediction. The live app
previewed two files / 25,875 bytes, imported workbook revision 1 with document
SHA-256 `73293ca6c2a1929a2e244f806d6eb5900d4c739716f7f291e74c9bc12dc291b6`,
and verified the archived bytes. The earlier transcription revision and run
source binding remained intact. Source-audit/catalog code commit: `ef303e7`.

**Numerical verification:** The explicit `cuda:0` bounded thermal pilot on an
RTX 4060 passed its frozen same-model CPU/GPU comparison; the observed final
3D field relative L2 error was 1.44e-8 in the live 316L job. This is a
single-track numerical parity result, not GPU qualification over the full
parameter domain. The separate CPU IN718 80 W report
`docs/LPBF_CPU_CONVERGENCE_80W_2026-09-24.json` has SHA-256
`f396091b1d806e82f75cb888b78bafab808c0b189821badfde7c04bd9a74b5b9`.
All three mesh and three timestep solves completed. Energy closure passed the
frozen 1% target; the finest mesh depth changed 17.1875% against the frozen 5%
target, width trend was unresolved at roundoff scale, and timestep geometry
was inconclusive. Overall P4 status is `failed`; the added interpolated thermal
contour is supplementary and is not used to change the frozen decision.
A separate surface-aligned 80 W 3+3 experiment is recorded in
`docs/LPBF_CPU_SURFACE_ALIGNED_80W_2026-09-24.json`, SHA-256
`33dde8637cb90e7445cbf5bef364c8b5e8922adfcd0baa3ac423e0d36f9b84a2`.
All six solves completed, the top face matched the 80 µm layer and the source
capture fraction exceeded 0.999999999. Energy passed, but discrete W/D across
the three meshes was 40/40, 40/40 and 60/50 µm; the finest-pair width/depth
changes were 33.33%/20% and timestep geometry was inconclusive. The frozen
overall P4 result remains `failed`; surface alignment alone did not resolve it.
An exploratory 5 µm solve of the same scenario used 588,544 cells and completed
in 375 s. The discrete depth moved from 50 µm at 10 µm spacing to 55 µm,
a 9.09% change against the frozen 5% target. The supplementary interpolated
liquidus contour across 20/10/5 µm showed width/depth finest changes of
1.27%/3.70% and positive observed orders of 3.06/1.24, respectively. These
values are captured in `docs/LPBF_FINE_MESH_DIAGNOSTIC_80W_2026-09-24.json`
(SHA-256 `fa01ffcb477cdba0a536705baacabbb06db6ec819bf2eb525e16b10d31bd75b6`,
commit `2a5493a`);
its source hash and numerical arithmetic were checked. The point was selected
after seeing the original failure, and no independent time-axis study exists
for this contour, so it is exploratory evidence only. P4 remains `failed`.

**Experimental validity:** No numerical W/D error against NIST Table 4 is
reported. NIST's [2025 beam-metrology report](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958616) provides a measured nominal 67 µm
Gaussian `Dg` diameter (5.2% combined standard uncertainty), but no
downloadable raw 2D irradiance artifact. The model uses a Gaussian 1/e²
diameter; mapping it to the Table 4 nominal D4σ remains an explicit
approximation. A source-byte-bound beam record and mapping uncertainty, a
matched 10 mm bare-plate run, source-matched etched optical section operator
and passing 3+3 numerical gate remain absent. IN625 is admitted only to bounded fusion-enthalpy screening,
not full LPBF transient or build-job prediction. None of these software and
numerical checks establish experimental validation.

Final local checks at this checkpoint: TypeScript unit 232/232, lint PASS,
production build PASS; official workbook Python 3/3 and combined bare-plate
plus workbook 8/8 PASS. Earlier Windows LPBF Python 91 PASS/3 OpenFOAM SKIP;
Ubuntu 22.04/OpenFOAM engineering 29/29 PASS. The large-chunk build warning
remains.

## 2026-09-24 — Phase 21 two-dimensional thermal screening correction

The old mushy-zone enthalpy inverse returned 1932.53 K at the specified
liquidus enthalpy for the existing Ti-6Al-4V test inputs, instead of 1928 K.
Its rolled vertical stencil also connected the top surface to the bottom cell.
The corrected inverse is continuous at solidus and liquidus; paired face fluxes
conserve heat with adiabatic outer faces. The explicit timestep bound now uses
both grid spacings and the largest of solid/liquid conductivity. Focused
Phase 21 and worker regression tests: 5/5 PASS with normal Windows permissions;
the sandboxed worker test failed during temporary-directory cleanup (WinError 5).
The changed code is `python/lpbf_transient_enthalpy_fdm.py`, with regression
tests in `python/test_lpbf_transient_enthalpy_fdm_physics.py`.
Follow-up: preheat inside the mushy interval was initialized as sensible heat
only, inconsistent with the solver's phase law. A matching temperature-to-
enthalpy function now initializes it; solid, mushy and liquid round trips and
a near-zero-duration mushy-preheat solve pass. Focused updated package: 6/6
PASS with normal Windows permissions.

This correction establishes internal numerical consistency for a limited
stationary two-dimensional screening calculation. The fixed beam profile has
no resolved out-of-plane power normalization and scan speed is unused. The
result therefore reports `is_physically_accurate=false` and its limitations;
it is not an experimentally validated melt-pool prediction. The independent
three-dimensional P4 convergence gate is unchanged.

## 2026-09-24 — Preregistered independent 75 W thermal contour study

The protocol and 75 W IN718 scenario were committed before computation in
`5b2cfd0`; scenario SHA-256 is
`c64670451843fc0842ea13f36b6acc7ca39385ae0237666090d30e4e550165fc`.
The six-solve report is `docs/LPBF_P4_CONTOUR_75W_2026-09-24.json` (commit
`4110e73`, SHA-256
`b9cff92e01378a58ac4ed17333c21ad591a956dfc6e32ddd2dda8a219026b866`).
All three mesh and three timestep solves completed with one model, solver and
material revision; maximum relative energy closure error was 8.55e-14.
Contour mesh W/D at 20/10/5 µm were 55.99/47.93, 60.02/52.41 and
62.31/52.13 µm. Width passed the declared finest-pair 5% and positive-trend
criteria (3.67%); depth changed only 0.53% in the finest pair but was
nonmonotonic, so its trend was inconclusive. At fixed 10 µm mesh, timestep
contour geometry changed by less than 0.002% between the two finest steps, but
both width and depth were nonmonotonic and remain inconclusive. The discrete
geometry assessment is also inconclusive. The separate contour gate and the
overall 75 W report are `inconclusive`; neither overrides the failed frozen
80 W P4 report. Focused study regressions: 13/13 PASS. This is a numerical
thermal proxy study, not NIST optical validation.

**Beam source boundary:** The NIST [optical cross-section methods, Table 2](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957295)
specify a nominally rotational Gaussian 67 µm diameter for the baseline 10 mm
+X track. The [AMB2022-03 methods, Tables 1 and 3](https://www.nist.gov/document/amb2022-03-measurement-and-challenge-descriptions-version-101)
distinguish this 67 µm thermography/optical condition from a separate 110 µm
dynamic-coupling track condition. NIST's [2025 beam metrology report, pp. 2 and
13](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958616) states that
the D4σ and 1/e² diameters coincide for an ideal Gaussian, while real profiles
have deviations; its Table 1 gives 3.3 µm (5.2%) combined standard diameter
uncertainty for the nominal 67 µm single-line condition. This source supports
a clearly labelled nominal-Gaussian screening input, but does not provide an
exact measured profile artifact for the currently strict P5 gate. The archived
Table 4 revision and its run binding are unchanged; no NIST model residual was
calculated.

## 2026-09-24 — Phase 22 core-physics regression

`python/lpbf_transient_3d_gpu.py` now clips its last explicit time interval to
the requested toolpath end and performs zero updates for a zero-duration path.
The lateral thermal face coefficient is zero when the neighboring column's
free surface places that cell in air. Warp CPU regressions check exact-duration
step schedules, zero-duration no-heating behavior, no heat transfer from metal
to ambient-reset air, and retained transfer between active metal cells. The
combined Phase 22 and peak-selection focused suite passed 8 tests with 1 skip;
the skip is the existing Windows-only OpenFOAM dispatch test. GPU execution was not available for
this verification. Pressure projection remains unresolved: its centered
divergence/gradient is not the operator represented by its nearest-neighbor
Jacobi stencil. The CPU whole-cell surface representation also remains a known
geometry limitation. No phase-level scientific validation is claimed.

## 2026-09-24 — P4 peak-selection diagnostic repeat

Before rerunning, `docs/LPBF_P4_PEAK_SELECTION_DIAGNOSTIC_PROTOCOL_2026-09-24.md`
froze diagnostic-only additions to the existing 75 W scenario and resolution
axes. The original energy, 5% finest-pair, and monotonic-convergence criteria
were unchanged. The repeated six-solve report is
`docs/LPBF_P4_PEAK_SELECTION_DIAGNOSTIC_75W_2026-09-24.json`, SHA-256
`bb7241cd328842517b8a0ad232c1cf160f0238ec459bbf66967ccc464b0ae4e`. This is
not an independent acceptance study and does not supersede the original 75 W
report or the failed frozen 80 W P4 gate.

All six solves completed with energy closure below the frozen 1% limit. Both
discrete and contour assessments remain `inconclusive`. The tracker chooses the
earliest accepted endpoint with the maximum count of active cells at or above
liquidus. Across 20/10/5 µm mesh levels the selected times were 161.950,
177.417, and 168.667 µs, with respectively 416, 11, and 1 equal-maximum
endpoints (tied windows span about 20.717, 0.500, and 0 µs). At 10 µm mesh,
1e-7/5e-8/2.5e-8 s timestep limits selected 177.467/177.417/177.367 µs with
6/11/24 equal maxima. Peak selection is resolution-sensitive and plausibly
contributes to the non-monotonic mesh-depth result, but this does not prove
causation.

The cell-center liquidus contour uses the same selected peak field and does not
extrapolate to the physical surface. Its global projected W/D is a numerical
proxy, not a measured cross-section. On the time axis, W/D changes stay below
0.004% but reverse direction, so the frozen trend check correctly remains
inconclusive. Focused regressions: 18 PASS / 1 expected Windows OpenFOAM skip.
No GPU execution or NIST residual was produced. P5 remains unavailable pending
the matched 10 mm bare-plate condition, suitable beam input, and source-matched
optical section operator.

## 2026-09-24 — P5 10 mm bare-plate feasibility audit

The official AMB2022-03 thermography baseline specifies 285 W, 960 mm/s,
67 µm nominal Gaussian spot, a 10 mm +X single track, and 23.5 °C substrate
temperature in Table 1; Table 2 gives the seven process cases. The 67 µm input
is an ideal-Gaussian nominal mapping only. The NIST optical definition measures
depth from the original plate surface to the deepest point and width at the
widest horizontal extent; the published results comprise six sections per case
(three tracks × two sections).

The current simulation rejects `trackLength_um=10000` before execution because
the supported range ends at 3000 µm. A read-only geometry estimate temporarily
expanded that bound in memory, then called only `calculate_mesh_domain`: the
existing square X/Y domain spans 10.201 mm and contains 4,177,936 / 32,315,671 /
258,272,222 cells at 20/10/5 µm. No 10 mm thermal solver was run. At 5 µm one
float64 field alone would occupy about 2.07 GB before the solver's other arrays.

The existing bare-plate observation is one x=0 plane of ever-liquidus cells.
It neither captures the NIST locations at 4.9 and 6.0 mm from track start nor
represents the six-section mean. A narrow-band/moving-frame solver or separate
memory-capable backend is needed to preserve those locations across the 10 mm
track with a viable domain. The strict comparison remains `unavailable` until
that model, a source-byte-bound measured-`Dg` record with explicit D4σ
mapping/uncertainty, six-section operator, and passing
independent 3+3 gate are present. NIST reports the measured nominal 67 µm
Gaussian diameter and uncertainty, but no raw 2D irradiance artifact. A
nominal Gaussian run may be reported only as unvalidated screening and must not
emit a NIST residual.

## 2026-09-24 — Build-job peak identity and Phase 22 face transport

Commit `e8f8313` makes Rosenthal peak temperature the value sampled from the
selected thermal field at the beam center. The build-job implementation is
identified separately as `lpbf-build-job-core-peak-field-v2`; Python cache keys,
cache-hit validation, returned build-job/capability provenance, and the UI's
same-input key use this revision. The heat-source model ID remains
`rosenthal-screening-v1`. Python build-job and capability checks passed, three
peak-field consistency tests passed, and `npx tsc --noEmit` passed. The
TypeScript session behavior test could not launch under the sandbox (`spawn
EPERM`); it was not counted as passed.

Commit `c902700` uses bilinear averages at each of the six transverse MAC face
locations, and computes enthalpy advection as a conservative divergence of
shared upwind face fluxes. Manufactured CPU Warp tests check all six analytical
interpolants and global enthalpy conservation for divergence-free transport.
The face divergence, pressure gradient, and pressure Jacobi stencil now share
the same liquid/free-surface/solid/domain face semantics; a checkerboard test
and a single-cell manufactured projection pass.

The current production pressure solve still runs ten Jacobi sweeps and does
not measure the post-projection residual. A smooth manufactured velocity gave
relative interior L2 divergence ratios 0.420619 on a 9³ grid and 0.793338 on a
17³ grid; 300 sweeps on 17³ still left 0.0378842, above the target 1e-3. The
result now reports `unverified_residual_not_measured`, and the demo no longer
calls the full hydrodynamic solver verified. This is a measured failure of the
current iteration budget, not a converged projection. A matrix-free PCG
implementation is underway; it must preserve the exact stencil and measure
the projected velocity residual before reporting convergence.

Combined focused CPU Warp, peak-field, and material-capability checks: 19 pass.
The standalone Python build-job checks and capability tests also pass. CUDA is
unavailable on this Windows host, so these results do not establish GPU-device
execution/parity. Warp temporary-cache teardown printed the known Windows
`WinError 5` after tests passed; two separate artifact-writing peak tests also
hit sandbox temp-directory permissions and are not counted as product failures.
These repairs do not change the frozen P4 failure, NIST P5 `unavailable`, the
heuristic moving-interface Marangoni/recoil law, or the CPU whole-cell surface
geometry limitation.

## 2026-09-24 — Phase 22 residual-controlled pressure solve

The fixed ten-sweep Jacobi projection was replaced by matrix-free,
Jacobi-preconditioned conjugate gradients for the same face-based pressure
operator. Liquid-neighbor coefficients, free-surface zero-pressure faces, and
solid/domain no-flow faces preserve the established D/G stencil. Device-side
partial reductions and ordered kernel launches keep scalar convergence checks
off the host inside the iteration loop. The runtime reports per-step maximum
and aggregate iteration counts, measured linear residual, measured
post-projection divergence, and convergence/failure status.

Focused CPU Warp suite: **19/19 passed**. Manufactured smooth-velocity cases
reached the 1e-3 post-projection relative L2 divergence target: 9^3 in 15
iterations (linear residual 7.605e-4; divergence ratio 7.606e-4), and 17^3 in
35 iterations (linear residual 8.073e-4; divergence ratio 8.074e-4). Tests also
cover anisotropic manufactured pressure, stepped free surface, solid
inclusion, compatible Neumann nullspace, incompatible single and disconnected
Neumann components, compatible disconnected components, iteration exhaustion,
and numerical breakdown. Incompatible components report
`numerical_failure`; final residual remains observable. The output distinguishes
maximum iterations per timestep from total iterations, retaining the old field
as a compatibility alias.

CUDA execution and performance were not verified because CUDA is unavailable
on this Windows host. Therefore this establishes CPU Warp numerical behavior,
not GPU-device execution or CPU/GPU parity. The prior Jacobi failure ratios
(0.420619 at 9^3, 0.793338 at 17^3 after 10 sweeps, 0.0378842 at 17^3 after
300) remain historical evidence and have not been presented as PCG results.

The IN625 capability remains deliberately limited to unvalidated,
literature-model fusion-enthalpy screening from 273.15–1623.15 K; full transient
and build-job routes remain closed. P7 is **partial** because the model-input
validity span, material composition/process state, and uncertainty are not
established. This bounded route does not satisfy the full source/data gate.

Other physics limitations remain open: Phase 22 free-surface Marangoni/recoil
relations are heuristic, the CPU transient uses a whole-cell surface
representation, and no experimental validation is claimed. Frozen P4 remains
failed and NIST P5 remains unavailable.

## 2026-09-24 — Phase 21 conduction dtype preservation

In `python/lpbf_transient_enthalpy_fdm.py`, `_conduction_rate` now casts the
temperature and conductivity fields to floating point before allocating and
accumulating face-flux rates. Previously, an integer temperature array caused
`zeros_like` to create an integer rate field, silently truncating fractional
conduction updates. A focused regression uses integer-valued inputs and checks
floating output, nonzero signed fluxes, and zero net internal flux. The focused
Phase 21 physics and solver suite passed **6 tests**. This fixes dtype handling;
it does not extend the stationary 2D model into a moving-source 3D melt-pool
solver.

The separate CPU reference transient audit found no new demonstrable
conservation or boundary defect in the reviewed operators. Two new manufactured
heterogeneous-conductivity tests pass: the harmonic face operator is symmetric
across conductivity jumps, active internal fluxes cancel, combined half-cell
isothermal-bottom plus single-plane convective-radiative-top power closes, and
explicit timestep refinement converges at first order. This checks the
discretization/boundary assembly, not experimental accuracy or full transient
material coupling.

GPU alloy scope was audited without code changes. The existing CUDA path's
measured parity is limited to its current Inconel 718 case; it does not qualify
another alloy. IN625 still lacks a complete source-backed transient table and
optical/flow inputs, so no new GPU alloy capability was enabled.

## 2026-09-24 — Phase 22 surface-force regimes and 316L CUDA parity

The Phase 22 Warp surface kernels now apply Marangoni shear only from liquidus
through boiling temperature, and apply recoil pressure / surface recession only
above boiling. This follows Alphonso et al. (2023), Section 2.1.2–2.1.3, which
places the surface-tension gradient in the liquidus-to-boiling fluid interval
and describes recoil for melt overheated above boiling:
https://doi.org/10.1016/j.jmapro.2023.03.040. Two focused CPU Warp regressions
cover sub-liquidus, liquidus-to-boiling, and above-boiling behavior. The full
Phase 22 CPU Warp suite passed **21/21**. The test process later reported the
known Windows `WinError 5` while cleaning a temporary PCH directory; the test
exit was successful. CUDA execution of these Warp kernels remains unverified.

The CUDA thermal-pilot CPU/GPU parity test now also covers the existing 316L
registry material snapshot while preserving all frozen parity thresholds and
binding the material revision SHA. The direct `cuda:0` run passed; the targeted
file passed **4/4** tests, including the existing IN718 run. The 316L record is
still `estimated-legacy`, and the result explicitly remains
`unvalidated`, `productionReady=false`, and `experimentalValidation=false`.
This establishes numerical parity for that exact estimated snapshot only; it
does not open the source-backed alloy acceptance gate or qualify IN625.

At this checkpoint the recoil law still drove both explicit surface recession
and a separate momentum impulse; their mass/kinematic coupling had not been
established. The follow-on correction and evidence are recorded below. This
checkpoint did not validate the interface model or claim experimental
agreement.

## 2026-09-24 — Opt-in rectangular bare-plate corridor

The reference solver now accepts `barePlateGeometry="rectangular-corridor"`
only for the explicit single-track +X bare-plate route. It keeps the full scan
history in X and uses a centered transverse corridor of twelve beam radii;
the default square geometry and powder-layer path remain unchanged. The actual
`nx × ny × nz` count is used by the solver resource guard and UI/resource
estimate. A 10 mm case with an 80 µm beam is estimated at 205,200 cells at
20 µm, 1,556,975 at 10 µm, and 12,123,933 at 5 µm. The 600,000-cell guard
therefore permits the coarse estimate but rejects the finer two before field
allocation. These are cell-count estimates, not measured runtime or a 10 mm
solve; no 10 mm thermal solution was run.

`test_lpbf_bare_plate.py`: **9/9 passed**. `test_lpbf_heat_source.py`: **7
passed, 1 existing Linux/OpenFOAM-only test skipped**. Together: **16 passed,
1 skipped** (the separate engineering suite is unaffected). Checks include
rectangular geometry/scan endpoints, the 600,000-cell refusal, resource shape,
square-default parity, and energy closure on a bounded corridor case.

That feasibility commit provided geometry/resource support only. Its follow-on
section operator is recorded below and currently emits two locations for one
simulated line; it does not provide the six records for three experimental
lines or a NIST-equivalent etched-section operator. Corridor-width sensitivity,
source-byte-bound measured-diameter mapping, and independent 3+3 convergence
evidence are also still absent. P5 remains `unavailable`; the rectangular option is not exposed
through the TypeScript UI.

## 2026-09-24 — P5 thermal-proxy section coordinates

Commit `7e5437e14c55bb650df1d7534aa89dd3aa1e70b4` adds the versioned
`bare-plate-corridor-accepted-peak-x-linear-section-v1` observation operator
for the opt-in rectangular bare-plate route. It emits distinct thermal-proxy
records at x=4.9 mm and x=6.0 mm relative to the +X scan start. Locations at
cell centers use the corresponding plane; off-grid locations linearly
interpolate two independently accumulated accepted-step peak-temperature
fields, then locate cell-center liquidus crossings for width/depth. Requests
outside the simulated scan/domain return `unsupported` without extrapolation.
Each record explicitly represents one simulated scan line, not an experimental
repeat. Disabling observation extraction preserves discretization, accepted
history, and energy output.

`python -m unittest test_lpbf_bare_plate`: **11/11 PASS**; `py_compile` and
targeted `git diff --check` PASS. No 10 mm thermal solve ran and no NIST
comparison is emitted. P5 remains `unavailable` pending source-byte-bound
measured-diameter/D4σ mapping and uncertainty,
three experimental line identities, corridor-width sensitivity, and an
independent 3+3 qualification.

## 2026-09-24 — IN625 P7 source boundary

The Sabau et al. 2020 source supplies a useful bounded literature model, but
does not identify a chemistry/heat/lot matched IN625 stock, JMatPro inputs or
version, declared property-validity span, or quantified Cp/k uncertainty.
Therefore the current 273.15–1623.15 K implementation window is not a
source-certified validity interval, and P7 remains partial.

The NIST Zhang et al. 2019 powder study reports inverse-model effective
conductivity for IN625 powder from 100–500 °C. It is a powder-bed property,
not bulk plate conductivity; the inspected article does not identify a powder
lot that matches the AMB2018-02 plate. The current GPU material path has no
unsintered-powder state, so this dataset was not routed into the alloy model.
NIST identifies AMB2018-02 targets as bare IN625 plates and links a substrate
certificate, but the description provides no thermophysical curves. The
certificate is the next material-identity source to inspect; no new alloy
acceptance follows from this audit.

Sources: [Sabau et al. (2020)](https://doi.org/10.1007/s11663-020-01808-w),
[Zhang et al. (2019), NIST powder study](https://doi.org/10.1016/j.jmapro.2019.09.012),
[NIST AMB2018-02 description](https://www.nist.gov/ambench/amb2018-02-description),
[AMB2018-02 substrate certificate](https://s3.amazonaws.com/nist-midas/1889/AMB2018-02_SubstrateMaterialCertification.pdf).

## 2026-09-24 — Phase 22 recoil and surface kinematics

Commit `3ff4c9e` removes the independent `sqrt(2 P_recoil/rho)` height
depression. Recoil remains in the momentum equation once; after velocity
projection, a height-graph kinematic condition updates the interface from
projected U/V/W and subtracts evaporation recession using the same
Hertz–Knudsen-like mass flux as the enthalpy cooling term. The upper free
surface is classified as a zero-pressure neighbor for the projection instead
of a closed wall, so the projected normal velocity can reach the interface.

The localized regression verifies that recoil-generated projected W survives
projection and drives surface height in the same step, with evaporation
contributing once. Focused Warp CPU regression: **1/1 PASS**; complete
`python/test_lpbf_transient_3d_gpu.py`: **24/24 PASS**; `git diff --check`
PASS. CUDA execution was not tested. This repairs the update coupling in the
height-graph solver; it does not model interface breakup/reformation, resolved
plume dynamics, or experimental agreement.

## 2026-09-24 — Phase 22 surface-kernel CUDA smoke

The production `free_surface_kinematics_kernel` was invoked directly through
Warp 1.17 on CPU and `cuda:0` (NVIDIA RTX 4060 Laptop GPU), using the same
small 5×5×5 temperature/velocity field, surface graph, and physical inputs.
The sampled center height was `2.5191626264131628e-05 m` on both devices;
maximum absolute output difference was `0`. Kernel compilation and execution
completed on both devices. The temporary harness was removed after the run.

This is a single-kernel execution/parity smoke. It does not establish CUDA
execution or parity for the coupled Phase 22 pressure projection, momentum,
recoil, and surface update, and it provides no performance or physical
validation. The earlier 24/24 Phase 22 Warp suite remains CPU evidence only.

## 2026-09-24 — Phase 22 sloped-interface Marangoni gradient

Commit `39a6f8f` changes the lateral temperature difference used for the
Phase 22 surface-stress predictor to sample the height-graph interface cell in
each neighboring column. The previous same-z stencil could compare air on one
side with subsurface metal on the other and create a false tangential
temperature gradient on a sloped surface. A manufactured field with uniform
interface temperature and a phase jump on the common z-plane produces zero
Marangoni predictor increment after the change. Focused regression: **1/1
PASS**; complete `python/test_lpbf_transient_3d_gpu.py` at that commit:
**25/25 PASS**.

This removes that sampling artifact; it does not provide a full geometric
surface-tangent stress law or validate the height-graph model. No CUDA
execution was performed for this correction.

## 2026-09-24 — Phase 22 evaporative mass/energy area closure

The height-graph recession used actual interface area
`dx·dy·sqrt(1+h_x²+h_y²)`, while the enthalpy latent-vaporization loss used
only projected area `dx·dy`. Commit `52b51cb` multiplies the energy flux by the
same surface metric. A constant-temperature, no-laser, no-conduction sloped
graph test independently evaluates
`rho·Δh·dx·dy`, `-ΔH·dx·dy·dz/Lv`, and
`m_dot·sqrt(1+h_x²+h_y²)·dx·dy·dt`; the three agree within 1%. Focused
regression: **1/1 PASS**; full Phase 22 CPU Warp suite: **26/26 PASS**.

The local height/enthalpy balance is consistent for this graph update. It does
not establish global mass conservation for breakup, droplet ejection, or a
resolved vapor plume. Coupled Phase 22 CUDA execution remains unverified.

## 2026-09-24 — Gaussian source-domain capture gate

`integrated_source` scales the represented Gaussian weights to the requested
absorbed power. If the finite domain captures too little of the profile, this
concentrates omitted power in the remaining cells. Commit `ee730ec` makes the
CPU transient reject source capture below `1/1.01` (a numerical cap on
renormalization to 1.01, not a material tolerance); `46b9be6` applies the same
single threshold and error helper to the explicit CUDA pilot. A 20 µm
corridor/D80 source captured 38.293% and is rejected. At fixed 20 µm spacing,
the tested 320 and 480 µm corridors passed the capture gate and retained
minimum-capture / maximum-renormalization diagnostics. A previously accepted
rotated multi-track case captured only 88.640% and is now rejected; its energy
test fixture was aligned to the grid so it continues testing the intended
energy/schedule contract.

CPU focused bare-plate suite: **29 PASS, 1 OpenFOAM 14 SKIP**. CUDA pilot suite:
**5/5 PASS**, including real RTX 4060 IN718 and estimated-legacy 316L parity;
the low-capture GPU driver regression uses a CPU torch test double to isolate
the gate. The shared heat-source suite is **8 PASS, 1 OpenFOAM SKIP**. This
gate prevents severe source truncation; it does not verify the incident beam
profile or make the exploratory ideal-Gaussian case NIST-equivalent.

## 2026-09-24 — Separate material source validity from table coverage

Commit `9325765` accepts optional `sourceValidityRange_K` metadata for a
user-supplied material table. When supplied, it must cover the complete table
and declared boiling temperature; the registry still requires the solver
table to span 273.15 K through boiling. Generated `temperatureCoverage_K`
continues to describe the table itself. When source validity is omitted, it
stays unknown. Four legacy alloy snapshots and a supplied IN718 snapshot retain
their existing revision hashes when the optional field is absent; when
provided, it participates in the content hash. The UI exposes the ranges
separately and describes the coverage rule.

Focused registry/material checks: **2/2 PASS**; engineering suite: **32 PASS,
1 OpenFOAM 14 SKIP**; TypeScript no-emit check PASS. Live browser accessibility
snapshot showed `Source validity range: Unknown` when none was supplied; the
expanded guidance was keyboard-operable. This metadata contract does not admit
NIST SRM 316L or IN625 as a new transient alloy, and a range asserted in an
unverified user-supplied snapshot is not independent source verification.

## 2026-09-24 — Enthalpy/phase audit result

An audit of `lpbf_gpu_thermal.py` and its shared material enthalpy contract
found no evidenced phase-inversion or latent-heat defect: CPU and GPU pilot use
the same monotone enthalpy table, fusion interval, fixed reference density, and
`h(T)` inversion. Selected IN718 solidus/mushy/liquid round trips returned
within `1e-8 K`; actual CUDA pilot checks, including IN718 and the existing
estimated-legacy 316L snapshot, passed. This is numerical parity and contract
evidence, not material-data or experimental qualification.

## 2026-09-24 — Coupled Phase 22 CUDA smoke and NIST Case 0 validity stop

On Warp 1.17.0 and the actual RTX 4060 Laptop GPU (`cuda:0`), the complete
`TransientEnthalpy3DGPU.solve_toolpath` path ran the same deterministic
positive-duration one-step case on CPU and CUDA. Both pressure projections
converged in seven PCG iterations. CPU/CUDA differences were `0.000244 K` in
maximum temperature, `1.69e-8 m/s` in maximum velocity, and zero in reported
melt volume and keyhole depth. Post-projection relative L2 divergence was
`6.227e-5` CPU and `6.221e-5` CUDA against the `1e-3` target. This proves
device execution and close parity only for that tiny smoke; the API did not
report an energy metric, and this is not full-solver workload parity or
performance qualification.

The preregistered 10 mm, 480 µm corridor case was attempted directly on the
local CPU reference solver. After 133 source-step evaluations (7.23 s wall
time), it stopped at the declared boiling-enthalpy limit with
`Thermal model validity exceeded (boiling or nonphysical enthalpy);
evaporation/free-surface CFD required`. The last attempted step began at
10.691 µs of a 10.437 ms scan and captured 99.999999998% of the source; domain
truncation did not cause the stop. The fixed-material solver has no evaporation
mass/energy sink or moving free surface, so no full-track section, energy
balance, or comparison residual was produced. Exact attempt evidence is in
`docs/p5_case0_10mm_480um_validity_stop.json`. P5 remains `unavailable`.

## 2026-09-24 — IN625 P7 source gate

A targeted primary-source audit found separate IN625 evidence for solid Cp and
thermal diffusivity with 95% uncertainties (Georgia Tech Gen3 CSP; conductivity
is derived using a constant density), liquid density/viscosity/surface tension
for BÖHLER L625, powder DRS absorptivity at 1070 nm, and an identified NIST
AM-Bench powder lot. The BÖHLER composition is not the NIST lot; powder DRS is
not a hot molten-surface law; none of the combined evidence gives the required
same-lot, uncertainty-bounded full table through boiling. IN625 therefore stays
limited to its current unvalidated fusion-enthalpy screening; full transient
and GPU admission remain closed. Source details and direct citations are in
`docs/IN625_P7_SOURCE_GATE_2026-09-24.md`.

## 2026-09-24 — Phase 22 CPU/CUDA multistep smoke

The frozen five-step production `TransientEnthalpy3DGPU.solve_toolpath` case
ran on CPU and explicit RTX 4060 `cuda:0`; the focused test passed 1/1. Both
pressure projections converged, with equal peak temperature, melt volume, and
surface recession. Maximum velocity differed by `4.77e-7 m/s`; post-projection
relative L2 divergence was `7.34e-8` / `1.03e-7`. Maximum absolute divergence
remains reported as `0.078125` / `0.15625 s^-1`. Full-field comparison, energy
closure, performance, mesh/time convergence, and experimental validation are
not available from this smoke. See
`docs/PHASE22_CPU_CUDA_MULTISTEP_SMOKE_2026-09-24.md`.

## 2026-09-24 — Phase 22 full-field CPU/CUDA parity

With an explicit opt-in diagnostic capped at 100,000 cells, the frozen
five-step production case exposed final temperature, enthalpy, velocity,
pressure, and surface-height arrays. CPU versus RTX 4060 `cuda:0` passed all
pre-set field tolerances (focused suite 3/3 PASS). Maximum temperature
difference was `2.4414e-4 K`; enthalpy relative L2 `1.96e-8`; pressure relative
L2 `6.92e-7`; surface-height difference zero. The default response stays
unchanged. No auditable total-energy ledger exists in this solver, so energy
closure remains unavailable. This is small-case numerical parity, not
analytical, convergence, performance, or experimental validation. See
`docs/PHASE22_FULL_FIELD_CPU_CUDA_PARITY_2026-09-24.md`.

## 2026-09-24 — CUDA manufactured pressure oracle

The device-side Phase 22 PCG recovered a mean-centered discrete manufactured
pressure on a 9³ liquid grid against an independently assembled host
finite-volume `A=-D(G)` operator. On explicit RTX 4060 `cuda:0`, the linear
residual was `7.4851e-4`, gauge-adjusted pressure relative L2 error
`2.9145e-4`, and independently recomputed operator residual `7.4854e-4`; all
were within the frozen `1e-3` limit (1/1 PASS). This is a pressure-operator
oracle only; it does not validate surface-force constitutive laws, total-energy
closure, convergence, performance, or experimental behavior. Details:
`docs/PHASE22_CUDA_PRESSURE_MANUFACTURED_2026-09-24.md`.

## 2026-09-24 — Sloped-surface energy ledger and worker timeout

Phase 22 previously applied the graph-area metric to evaporation cooling but
not to convection/radiation. Commit `a344821` now applies the actual graph area
once to all three environmental losses, while laser input remains projected
area. An opt-in independent per-cell ledger records laser, conduction,
advection, convection, radiation, evaporation, and surface-mask reset terms.
The focused suite passed 28/28. On RTX 4060 `cuda:0`, 64³ cells and 43 steps,
whole-field relative energy closure was `9.724e-5`, below `1e-3`; both pressure
residual gates were also below `1e-3`. This is one bounded CUDA case, not mesh
or time convergence or experimental validation. Report:
`docs/PHASE22_CUDA_ENERGY_AUDIT_2026-09-24.md`.

The CPU `enthalpy-fv-6` audit found no new high-confidence hidden physics defect;
existing energy, conservative internal-face, and source-capture tests cover the
inspected operators. The distinct legacy 2D FDM endpoint remains explicitly
screening-only and is not evidence about the shared CPU core.

`python/lpbf_worker.py` now supplies the 300 s default when a build-job omits
`timeout_s`; `python/test_lpbf_worker_timeout.py` passed 1/1. The current
checkout's live HTTP API then completed two IN718 build jobs, each with the
resolved material snapshot SHA-256. Archive/restore for this build-job result
remains unverified.

## 2026-09-24 — P5 Case 0 physics feasibility

The official NIST AMB2022-03 Case 0 is 285 W, 960 mm/s, nominal 67 µm
rotational Gaussian, one +X 10 mm bare-plate track, and 23.5 ± 1 °C starting
temperature. NIST's cross-section paper reports six values per case from three
tracks and two sections per track; sections are described as approximately at
mid-track, so the application's exact 4.9/6.0 mm choices are not source-bound.
NIST reports a Case 0 width/depth aspect ratio of 2.1. Sources:
[AMB2022-03 methods](https://www.nist.gov/document/amb2022-03-measurement-and-challenge-descriptions-version-101),
[cross-section study](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957295).

The current `enthalpy-fv-6` run stopped at its boiling validity guard after 133
source steps and 7.23 s, covering only 0.1024% of the scan. It produced no
complete run, energy closure, optical section, or comparison residual; repeating
it or changing corridor width cannot satisfy P5. Keep the result unavailable.
The next defensible path is a new model revision that handles the above-boiling
response, energy/mass-consistent evaporation and evolving free surface; assess
whether recoil/keyhole physics is required, then preregister a new 3-mesh ×
3-timestep comparison. This is a proposed prerequisite, not a validated model.
NIST 2025 beam metrology may support a nominal 67 µm Gaussian with uncertainty,
but not the strict byte-bound two-dimensional profile requirement:
[NIST AMS 100-67](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958616).

The CPU `enthalpy-fv-6` path is fixed-surface conduction/phase change and does
not solve evaporation, surface mass loss, recoil, or melt flow. Phase 22 adds
some of these as height-graph heuristics; the available OpenFOAM VOF route uses
Ti-6Al-4V evaporation defaults and has no established IN718 mass/energy coupling.
None is currently qualified for Case 0. Preserve the CPU boiling guard; do not
retry the same solve or describe an exploratory run as a NIST comparison.

## 2026-09-24 — Durable run-kind identity

Worker results now carry a trusted top-level `runKind`; the queue capture binds
it to its own result bytes and requires `settings.jobType=build-job` for
`build-screening`. `transient-thermal` is kept distinct, while historical v1
records without a kind remain byte-identical and read as `legacy-unspecified`.
The archive API/UI and bundle path preserve the kind. Build-job NIST optical
comparisons return unavailable for both new and legacy captures; no
`coreContract` is fabricated. Verification: Python capture and real queue
execution 7/7, focused archive/NIST/client/bundle TypeScript 31/31, lint PASS.
The complete selected-browser build-job → comparison → export → isolated restore
chain is still open.

## 2026-09-24 — Phase 22 analytic thermal oracle and browser archive flow

`python/test_lpbf_phase22_manufactured_thermal.py` exercises the production
`enthalpy_3d_nonlinear_step_kernel` on a source-free, fixed-property 3D
Dirichlet Fourier mode. The exact field is
`T=300+10 product_i sin(pi*x_i/L) exp(-3 alpha pi² t/L²)`; expected energy
change is independently integrated from that field, without the solver ledger.
CPU 9³/17³/33³ relative field errors are `1.5814e-3`, `5.5712e-4`,
`1.4679e-4`; relative exact-energy errors are `6.0033e-3`, `2.1197e-3`,
`5.5784e-4`. Explicit RTX 4060 `cuda:0` at 33³ gives `1.4677e-4` field and
`5.5771e-4` energy error. Focused test **2/2 PASS**. This closes only the
manufactured heat-operator subcheck; Phase 22 full model and P6 remain partial.
Full conditions and limits: `docs/PHASE22_MANUFACTURED_THERMAL_2026-09-24.md`.

An isolated browser session on a dedicated local server imported and verified
NIST AMB2022-03 official workbook revision 1 (`73293ca6…`) and local Table 4
transcription revision 1 (`b312cc28…`). Two IN718 Quick Screening jobs were
captured with those source links. The Table 4 comparison correctly returned
unavailable: the record was not a standard CPU transient solve, did not execute
the 10 mm bare-plate path or ambient condition, lacked a measured-profile
mapping and six-section observation operator, and had no 3–6-level mesh/time
studies. The flow exported bundle `43642650e30942489be6867d6f0e11da` (2 runs,
3 run artifacts, 2 source links), verified it, and restored copy
`30d6a902b25c44e2a65c357bb35c26d2`. During this trial the app mislabelled an
analytical screening result (`settings.mode=screening`,
`resolvedPhysics.transient=false`) as `transient-thermal`; this contract defect
is under repair. These scratch-root records are diagnostic, not durable product
archive evidence; repeat the acceptance flow after the run-kind fix.

## 2026-09-24 — Run-kind fix and repeat browser acceptance

Worker/capture/archive now use `analytical-screening` when a captured result has
`settings.mode=screening` and explicitly reports `resolvedPhysics.transient=false`.
The queue, Python capture, TypeScript repository, UI, NIST eligibility, and
bundle path preserve that identity. Fresh isolated UI run `a102b5269a3744b49b0cc0309e698752`
used IN718 and the NIST Table 4 Case 0 vector (285 W, 960 mm/s, 67 µm beam,
23 °C), completed as Rosenthal/Goldak analytical geometry, then previewed and
archived as `analytical-screening` with exact Table 4 transcription revision 1
(`b312cc28…`). The NIST comparison correctly returned unavailable because
analytical screening has no transient thermal evolution. Bundle
`3b6b4a0d570a4429b7b5b6b2380e5fce` contained 1 run, 2 artifacts, and 1 source
link; verification succeeded and restored copy `9ee6029283504c74a925e53e2a53c4f2`
was separate from the unchanged live archive. This is an archive/workflow
acceptance result, not thermal model validation. Focused checks: Python 10/10,
TypeScript 35/35, `npm run lint` and `git diff --check` PASS.

Independent audits of the active CPU enthalpy-FV, CUDA/Warp thermal path, and
phase/heat-flux closures found no additional high-confidence implementation
defect. Their scope does not qualify experimental accuracy. OpenFOAM evaporation
currently uses an evaporative energy sink/recoil term without a demonstrated
metal mass/VOF closure; its back-condensation assumption and IN718 applicability
remain unverified, so that branch is not treated as a qualified free-surface
model. P6 remains partial; do not remove the CPU boiling guard or claim P5.

## 2026-09-24 — Build-job identity and physics gate evidence

Successful build-job results now carry a composite SHA-256 over canonical
`alloyId`, `modelId`, `solverRevision`, property-snapshot schema/revision, and
the unchanged property-only SHA-256. Alias, model/revision/schema, property
change, cache-key, and stale-cache checks are in `python/test_lpbf_build_job.py`;
the TypeScript build session also rejects missing/inconsistent identity fields.
The dedicated Python script completed successfully in the identity worker;
focused TypeScript session tests passed 12/12.

The IN625 bounded fusion-enthalpy screen now has an independent 12-point
Gauss-Legendre Cp-integration oracle. It checks H(T), continuity, monotonicity,
latent contribution (290 kJ/kg), and dH/dT. Together with the material and
capability checks, 7/7 focused Python tests passed. This is numerical formula
verification only; source-validity range and experimental model validity stay
unknown, and build-job/full transient remain unavailable.

OpenFOAM code inspection confirmed that its evaporation flux contributed to
latent energy and recoil/plume sources without a matching VOF/continuity mass
transfer. The production case generator and C++ default now disable this
unclosed source group; the recoil formula fixture remains explicitly enabled
for equation/force-direction checks only. Three focused tests passed. Solver
diagnostics record absent mass-transfer closure and unqualified status. No
OpenFOAM build/runtime verification was available, and full evaporating-VOF
mass/energy/momentum closure remains unfinished.

TypeScript session tests: 12/12 PASS; `npm run lint`: PASS; Python syntax checks:
PASS; `git diff --check`: PASS. One root repeat of the expensive build-job
script was interrupted after it ran over 85 seconds; the assigned agent had
already completed that same script successfully. P6/P7 are updated to require a
GPU thermal qualification route for at least one newly admitted alloy.

## IN625 bounded bare-plate CPU/CUDA field screening — 2026-09-24

Evidence artifact: `docs/IN625_BAREPLATE_GPU_SCREENING_2026-09-24.md`.

The model uses the exact bounded IN625 enthalpy revision
`f47b07e4c8288b8c7177001f069a254be3410bace43ad5ea2f73168ac4466f07` in NumPy
and explicit RTX 4060 `cuda:0` paths. A 12×12×4 (576-cell), 4-step synthetic
absorbed-W moving-source case produced bitwise-identical temperature and
specific-enthalpy arrays in this environment; max CPU/CUDA energy residual was
`1.11e-16 J`. The continuous domain source capture fraction was `0.9999987339`,
above the shared `1/1.01` minimum. CUDA measurement: 1.325 s and 100,864 B peak
allocated device memory, for this small smoke only.

Focused verification: field + constitutive + shared source suites **36 PASS,
1 SKIP**; material capability suite **4/4 PASS**; `py_compile` and
`git diff --check` PASS. CUDA field tests were exercised without skips. The
single skip is the existing platform-dependent heat-source/OpenFOAM integration
case. The independent 64-point Cp integral checks constitutive H(T); CPU and
CUDA reject a liquidus-crossing step, and the shared source-capture gate rejects
truncated Gaussian input rather than renormalizing it.

The density is a fixed 8,440 kg/m³ supplier-bulletin assumption and is not tied
to the NIST AMB lot. The NIST benchmark is bare plate, but no NIST dataset was
run or compared here. This proves numerical implementation/parity only. The
source model is JMatPro-derived with assumed liquid/mushy values and has no
independent source validity span or quantified uncertainty; scientific
qualification, powder-bed support, build-job admission, P5 experiment comparison,
and full-transient capability remain open.

## Core physics + IN625 UI/archive integration — 2026-09-24

User-authorized core-engine physics fixes were added to Phase 22: the surface
temperature gradient for Marangoni forcing is projected with the height-graph
metric into tangential components, eliminating the spurious normal component
on a sloped interface. Recoil impulse now follows the inward local graph
normal, with the flat-surface limit preserving the prior vertical direction.
Focused Phase 22 Python suite: **29/29 PASS**; CPU/CUDA full-field,
multistep, and manufactured pressure groups: **5/5 PASS**, including RTX 4060
`cuda:0` test groups. Warp's Windows PCH temp cleanup reported `WinError 5`
after successful test process exit; this does not count as solver validation.

The IN625 client reads final temperature artifacts as little-endian binary
float64, checks content type, byte count, and manifest SHA-256, and compares
decoded arrays. Same-configuration live UI runs used 16×12×6 cells, 11 steps,
20 W absorbed power, and explicit CPU / `cuda:0`. Both had field SHA-256
`90670c1176da50ec2014a62076f057ebac6e39635e29beb390227a1598f58354`; displayed
comparison was 1,152 cells, maximum absolute difference **0 K**, RMS **0 K**.
Peak temperature was 300.432 K on each backend, final enthalpy 1.56 J, energy
residual 0 J, source capture 0.993615, and input/stored energy 0.0022 J; scalar
differences were zero. This is bounded numerical parity only.

The UI previewed, imported, and byte-verified local derived IN625 screening
source revision 2 (two artifacts, 1,938 bytes; document SHA-256
`be3286b30b3ec3a6970b577cd9050b19de716cbf8754c7ac2355cf20d5cea655`). The
CUDA run `587632c4976349e0b0d2a11718f62d3e` was archived with three artifacts
and the exact source revision. One-run/one-source server-local bundle
`ccfc76e23c544788ac8d11038c1754c3` passed verify and restored as isolated copy
`8622c0e102304cc980d0e04b5f22e701`. Archive preview initially failed because
the capture record has no `requestSummary`; the parser now reconstructs the
temporary validation envelope from authenticated `result.settings` without
loosening artifact/material/settings checks. Run HTTP preview round-trip
regression: **2/2 PASS**. The archived bounded screening run intentionally
has an unbound core contract; NIST comparison remains unavailable.

Source/client suites: **10/10 PASS**; adjacent archive/import/API suites:
**16/16 PASS**; IN625 client/UI tests: **6/6 PASS**; TypeScript, lint and
`git diff --check`: **PASS**. Root's sandboxed Python worker test attempt was
blocked by Windows ACL errors opening SQLite/temp paths; the agent's actual
small CPU worker→capture exercise passed. No OpenFOAM build/run was performed.
The source inputs remain locally derived/model-based, density is not lot-
matched, and nothing here establishes scientific validation or qualification.
Implementation and evidence checkpoint committed locally as `a5d60b6`.

## Follow-up checkpoint — Marangoni normal spacing + alloy matrix (2026-09-24)

A second core-physics audit found that the Phase 22 Marangoni boundary wrote
`mu * du_t/dn = tau` but scaled the velocity increment with vertical `dz`.
For a height graph, the adjacent vertical sample's first-order normal spacing
is `dz/sqrt(1 + h_x^2 + h_y^2)`, so the previous law over-applied tangential
shear on sloped surfaces. The kernel now uses that spacing. The sloped-graph
regression checks both tangential direction and recovered traction magnitude.

After this change, `python -m unittest test_lpbf_transient_3d_gpu -v` ran
**29/29 PASS** in 44.476 s; Warp compiled and exercised the relevant kernels on
CPU and the actual NVIDIA RTX 4060 Laptop GPU (`cuda:0`). This is numerical
kernel evidence only, not model/experiment qualification.

The five-alloy summary based on the machine-readable capability authority is
drafted in `docs/LPBF_ALLOY_CAPABILITY_MATRIX_2026-09-24.md`. It preserves the
four legacy alloys as estimated/unvalidated and IN625 as bounded bare-plate
CPU/CUDA screening only. After resumption, the focused suite was rerun:
**29/29 PASS** in 7.177 s; Warp loaded the Marangoni kernel on CPU and RTX 4060
`cuda:0`. The kernel fix, test, matrix, and evidence checkpoint form a separate
package. Frozen P4 remains `failed`, P5 remains `unavailable`, and the broad
goal is not complete.

## IN625 mushy-range CPU/CUDA witness (2026-09-24)

To check that the bounded IN625 field adapter traverses its latent-enthalpy
range, a synthetic 8×8×2 cell test starts at 1500 K and adds 30 W absorbed
power for 33 steps at 1e-4 s. This high initial state is deliberate numerical
coverage, not an LPBF preheat or process claim. Source capture is 0.9982844950;
the material revision remains `f47b07e4c8288b8c7177001f069a254be3410bace43ad5ea2f73168ac4466f07`.

`python -m pytest -q test_in625_bareplate_field.py`: **11 passed** on an RTX
4060 host (pytest cache ACL warning only). The 128-cell vector reached
1565.4608746 K and 4 mushy cells; the refined 1,024-cell vector reached
1577.3396719 K and 32 mushy cells. At each resolution CPU and `cuda:0` agreed
within 9.10e-13 K and 3.50e-10 J/kg; both ledger residual maxima were
5.33e-15 J. Independent 64-point Cp integration and global enthalpy balance
passed at both resolutions. One-run CPU/CUDA timings were 0.289/9.196 s
(128 cells) and 1.316/23.254 s (1,024 cells); incremental CUDA allocations
were 24,576/176,128 B. CUDA was 31.8× and 17.7× slower respectively; no speedup
claim. Full context and limitations: `docs/IN625_MUSHY_CPU_CUDA_SCREENING_2026-09-24.md`.

This closes field-level coverage of the implemented IN625 screening law's
mushy interval for one synthetic vector; it does not admit the source data or
model as physically qualified. P6 and P7 remain partial.

## Phase 22 molten-surface evaporation consistency fix (2026-09-24)

The surface recession kernel already limited its Hertz–Knudsen-like mass loss
to cells at or above the material solidus, but the enthalpy sink and energy
ledger did not. A CPU regression at 1850 K against the default 1878 K solidus
reproduced the mismatch: enthalpy fell while the surface height stayed fixed.
The solver now routes energy loss, ledger accounting, and height recession
through one liquid-surface mass-flux helper. Below solidus all three terms are
zero; above solidus the existing flux and surface-area treatment is preserved.

The focused regression first failed against the old behavior, then passed after
the fix. `python -m pytest -q test_lpbf_transient_3d_gpu.py`: **30 passed** on
CPU Warp. Pytest cache writes and Warp's process-exit temporary-directory
cleanup emitted Windows ACL warnings; the Warp kernel tests themselves passed.
This is an internal physics-contract consistency fix, not experimental
qualification; P4/P5/P6/P7 retain their existing statuses.

## Phase 22 explicit momentum time-step stability (2026-09-24)

The solver selected `dt` from thermal diffusion alone, while the momentum
predictor advances upwind advection and the viscosity Laplacian explicitly.
The selected step now takes the minimum of the existing thermal limit and a
conservative combined momentum bound using the documented 5 m/s per-component
velocity clamp and kinematic viscosity `mu/rho`:
`dt * sum(|u_a|/h_a + 2 nu/h_a^2) <= 0.5`.

A low-thermal-diffusivity test with each velocity component at the clamp
verifies the momentum bound controls the selected step and the end-time
scheduler preserves the requested duration. Full Phase 22 suite:
**31/31 passed** on CPU Warp. Local pytest/Warp temporary-directory ACL
warnings occurred after the passing checks. This stabilizes the explicit
numerical update for the configured velocity cap; it does not validate the
heuristic momentum or free-surface physics experimentally.

## P8 fresh UI archive acceptance and IN625 CPU/CUDA parity (2026-09-25)

The current checkout was built with `npm run build`; Vite emitted its existing
large Three.js chunk warning. The built local server and Python worker started,
and `/api/health` returned `status: ok`. In the live LPBF UI, a bounded IN625
bare-plate case used a 16×12×6 (1,152-cell) grid, 10 × 10 µs steps, 20 W
absorbed power, 0.4 mm Gaussian sigma, and zero scan velocity. CPU job
`0433a86abc094529a185de09fb47766c` and CUDA `cuda:0` job
`c724230219f7489b83d1f80ca6552a11` used model
`in625-bareplate-enthalpy-conduction-v1` rev 1 and material snapshot SHA-256
`f47b07e4c8288b8c7177001f069a254be3410bace43ad5ea2f73168ac4466f07`.
Both completed with peak temperature 300.226 K; final enthalpy difference was
`2.22045e-16 J`, energy residuals were `2.22045e-16 J` and zero, minimum
source capture was 0.993615, and the final temperature-field maximum absolute
difference was `1.13687e-13 K` (RMS `5.44234e-14 K`). These are descriptive
same-configuration CPU/CUDA parity results; the UI supplies no tolerance
pass/fail and they are not experimental validation. The model is explicitly
unvalidated literature-model screening, has no powder/absorption evolution,
vaporization, flow, or free surface, and its density is an assumed 8440 kg/m³
not matched to a material lot. Its bounded property interval is 273.15–1623.15
K; this result does not admit IN625 to full transient or build-job use.

The associated local-derived input source was previewed/imported and its
archived bytes verified at that time: revision 1 SHA-256
`be3286b30b3ec3a6970b577cd9050b19de716cbf8754c7ac2355cf20d5cea655` (2 files,
1,938 bytes). This is not raw publisher data or an experimental dataset; it
derives from Sabau et al. 2020 plus a fixed density assumption. The CUDA job
was archived against this exact source revision; its run remains legacy core
contract-unbound. A fresh IN718 30 W / 1,200 mm/s transient job
`aad3bc4b6ceb4abbbc56942554f202cb` also completed (29,988 cells, 9.484 s),
but its 40/20/60 µm melt geometry was flagged under-resolved, and the model is
unvalidated with no free-surface flow. Comparing the IN625 run with NIST
AMB2022-03 Table 4 correctly returned unavailable because the material and
process contracts do not match; the local Table 4 transcription revision SHA
was `b312cc286ccf7cd41c2ff8bc2bea3c0cf183af432125f402dfbebdf71b235ee0`.

The archive UI keyboard selector was exercised with ArrowUp/ArrowDown and
returned to the original IN625 run. Server-local bundle
`5c86ac62fed64f9b93c9a53b8d6817a9` contained 3 runs, 132 run artifacts, and 3
source links; bundle verification passed. Isolated restore
`58d94b80d0904a53bb11f5bab73eac51` completed and the UI confirmed the live
archive was unchanged. This verifies software archive integrity and workflow,
not the physical model. No changes were made to the frozen P4/P5/P7 gates.

### Moving-source power contract check (2026-09-25)

An audit questioned the per-node `0.5 * power` factor in
`python/lpbf_core_physics.py::integrated_source`. This is the GL2 time
quadrature weight, not a half-power loss: `GAUSS_NODES` contains two nodes,
each contributes 0.5 of the absorbed power after per-node spatial
normalization, so their sum integrates to the requested power per step.
`python -m unittest test_lpbf_heat_source.HeatSourceVerification.test_symmetry_power_and_future_powder -v` passed and asserts a 70 W integrated source for a 70 W input. This checks the axial source integration contract only; it does not validate the thermal evolution experimentally or establish mesh/time convergence. The standard 3D moving-source CPU transient already exists in `python/lpbf_simulation.py`; the separate Phase 21 2D stationary solver remains screening-only.

### NIST Table 4 source revision update (2026-09-25)

The source archive initially contained Table 4 local transcription revision 1
(source version 1.0.0, one 3,374-byte file, document SHA-256
`b312cc286ccf7cd41c2ff8bc2bea3c0cf183af432125f402dfbebdf71b235ee0`). The
current catalog previewed version 1.1.0 (one 4,321-byte file) and imported it
as revision 2; the UI confirmed bytes matched at import. Revision 2 document
SHA-256 is `6c9d9f80f8c4eb2b7a6c18bbaab9ed7a993e43f155190dfff49808a4f854aaf0`.
The update adds source-located heat-treatment evidence. It remains an
unreviewed local aggregate transcription, not raw NIST measurements.

The earlier archived IN718 run `aad3bc4b6ceb4abbbc56942554f202cb` is
immutable and linked to revision 1. Its comparison against the current fixed
transcription correctly returned unavailable because the archived artifact
does not match the reviewed version 1.1.0 bytes; the run was not silently
rebound. The selected Table 4 case 0 is also not that job's process vector.
The comparator's model gate additionally requires a verified measured beam
profile artifact, which was not available in the AMB2022-03 source hunt. Thus
importing revision 2 improves provenance but does not make this or any run a
validatable/validated NIST comparison by itself.

## Three-mesh study failure handling (2026-09-25)

A fresh IN718 UI study using the built-in "Three meshes" option halted when
the 28 µm middle level captured 54.851% of the Gaussian source, below the existing
99% minimum. The source-capture guard correctly refused to renormalize this
truncated source. No threshold or frozen acceptance criterion changed.

Commit `4684213` updates `python/lpbf_simulation.py` so a failed coarse or medium level is
retained as an explicit unavailable level, the requested fine result and other
completed levels survive, and all partial-sequence convergence checks are
marked failed with the original error reason. The result UI renders missing
levels safely and displays the failed study status. A partial sequence cannot
be called converged.

Verification: the existing three-mesh study regression and a new synthetic
low-capture regression both passed. The broader `test_lpbf_engineering` plus
`test_lpbf_heat_source` run executed 49 tests but ended with 7 access-denied
temporary-directory errors on Windows; two OpenFOAM-dependent tests were
skipped. Isolated heat-source tests passed (15 tests, one OpenFOAM skip), and
`npm run lint` passed. The focused TSX UI test could not start because Node's
esbuild child process returned `spawn EPERM`. Therefore the broader package and
UI rendering test are not yet passing verification. This change improves
failure reporting and result preservation; it does not improve the source-
capture fraction, solver accuracy, or experimental validation.

## Layer-aligned three-mesh study repair (2026-09-25)

The failed 30 W / 1200 mm/s / 80 µm IN718 case requested 20 µm spacing. The
previous `sqrt(2)` level rounded to 28 µm. Its z centers at 14 and 42 µm made
the whole-cell active mask exclude the second cell, although that cell spans
28–56 µm and the layer surface is at 40 µm. The clipped interval 28–40 µm
therefore lost source integral; independent reproduction gives 54.8506%
capture. The unchanged 99% source-capture guard correctly rejected it.

For standard powder-layer mesh studies with requested backend `auto` or
`reference`, `python/lpbf_simulation.py` now runs a three-level CPU-reference
sequence with the explicit `layer-conforming` grid. The reproduced vector used
1/2/3 cells per 40 µm layer (40/20/13.333 µm). `requestedBackend` and actual
execution settings are recorded separately, with both requested and execution
input hashes. The same exact vector completed all three levels; energy relative
error was `3.0433745192575536e-16`. Width, depth and volume trends remained
`inconclusive`; result `validationStatus` remains `unvalidated`. This establishes
numerical execution and energy closure only, not mesh convergence or physical
validation.

Verification: three focused regressions passed (standard three-grid result,
failed fine-level preservation/backend provenance, and layer-aligned source
capture). The exact end-to-end vector completed. Broader package and UI checks
were not rerun after this change.

## Mesh-study backend disclosure (2026-09-25)

The layer-aligned protocol result now records `executionBackend=reference` in
addition to the requested backend, cell count per layer, and the separate
execution-input hash. The convergence panel displays this distinction (for
example: requested backend `automatic`, execution backend `reference`) so an
automatic request cannot be mistaken for GPU/OpenFOAM execution. The
`SimulationResult` type preserves the top-level requested backend and
`provenance.executionInputHash`.

Verification: the targeted Python failed-level/provenance regression passed and
`npm run lint` passed. `npm exec -- tsx tests/lpbf-presentation.test.tsx` could
not start: esbuild child process failed with `spawn EPERM`; this UI test is
unverified. No browser check was run.

## P4 fingerprint-locked temporal diagnostic (2026-09-25)

Scope: supplementary IN718 CPU reference study at fixed 5 µm mesh for the
frozen 40 W scenario, requested max dt 100/50/25 ns. Source inputs are the
frozen protocol `docs/LPBF_P4_CURRENT_40W_FINGERPRINT_PROTOCOL_2026-09-25.json`
(SHA-256 `db0a85e22a75709fcabb3f3bee9e7c0d44213a081881f6a076ee5de6820274df`)
and scenario (SHA-256
`2abec47f9d35c02158ea2e06876e3ca06c3ba5ba9243f1ddccaa94ef64752ea6`).
The final JSON report SHA-256 is
`726cad9aa1d4f2b7dc3009b8b10ed1a7db08b49ba1f9bc9e4b872f662054b558`.
The report pins the execution HEAD, start-time dirty source paths, runner and
assessment hashes, and equal implementation hashes before and after each row.

Results: 3,923/7,000/14,000 accepted steps; actual mean dt 89.217/50/25 ns.
Maximum relative energy-balance error `1.629e-13` passes the frozen 1% bound.
The accepted mean dt ratios are unequal, so the existing fixed-ratio estimator
returns **inconclusive** for time convergence. Cell-extent width/depth are
80/35 µm at all three levels; the reported zero finest-pair relative change
refers only to these quantized extents. The interpolated liquidus contour widths
are 77.7079/77.7053/77.7036 µm and depths 34.6956/34.6955/34.6963 µm.
These contours are numerical thermal proxies, not optical observations.
The frozen P4 `failed` verdict remains unchanged. No experimental validation
is claimed.

## NIST optical-observation boundary (2026-09-25)

The [NIST cross-sectional methods paper](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957295)
defines single-track measurements on three repeated tracks, with two sections
per track near its center. The sections are perpendicular to the scan (within
2 degrees); their location has estimated standard uncertainty ±0.2 mm. The
samples were mounted, aqua-regia etched, optically imaged, and measured in
ImageJ. Width is the widest horizontal span of the revealed boundary; depth is
the greatest vertical distance from the original plate surface, excluding any
height above that surface. Table 4 aggregates six measurements per case.

The current model's one nearest-midpoint ever-liquidus YZ section is a thermal
proxy. It does not reproduce six separately positioned etched/resolidified
boundaries or measured-beam-profile behavior. Therefore the existing NIST
comparison correctly remains `unavailable` with no optical residuals. The
[NIST beam-metrology report](https://www.nist.gov/publications/laser-beam-metrology-am-bench-2022-approaches-results-and-lessons-learned)
also documents variability and uncertainty in the AM Bench 2022 power-density
distribution. A nominal D4σ diameter alone cannot prove a profile-matched
model source. This is a source-method audit, not solver validation.

The [official NIST catalog](https://catalog.data.gov/dataset/am-bench-2022-measurement-results-data-optical-microscopy-of-laser-scanned-single-track-03)
lists raw TIFF, separate `_m.tif`, and per-file `.sha256` sidecars for each
Case 0 track/section. Workbook rows 2–7 map in order to
`L0-1/P3`, `L0-1/P4`, `L0-2/P3`, `L0-2/P4`, `L0-3/P3`, `L0-3/P4`;
P3 is 4.9 mm and P4 is 6.0 mm. Exact candidate filenames use
`AMB2022-718-SH1-BP1-{P3|P4}-L0-{1|2|3}.tif`. The workbook row mapping is
verified locally; catalog names are publisher metadata. TIFF bytes, sidecar
hash contents, and the `_m` image meaning could not be verified because the
official file endpoint was unavailable through the local proxy. No image
segmentation or optical-boundary claim follows from this mapping.
