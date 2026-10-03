# LPBF CPU Input and Display Claims — 2026-10-03

## Scope and decision

This evidence note covers bounded frontend/backend contract corrections and the clean-reproduction instructions integrated over base `bd979c715cd774aa2f4585b641177f5dc55e4e4e`. The historical frozen source remains `33efb32b7d9734587a78d1cb9de8224d7ef2a4ec`; new edits are not retroactively accepted by that release record. The new working candidate still requires root-owned commit and exact-candidate clean install/unit/build verification. Full V1 acceptance remains open.

## Claims supported by the changes

- **Measurement evidence stays unverified until process inputs are present.** The frontend no longer invents current controls for manual/conditionless measurements and preserves an explicitly complete 22-field `processVector`. Partial/malformed vectors, Boolean/string-number measurement values and unknown measurement/uncertainty fields are rejected with local errors. The backend still decides equality against normalized worker inputs; missing vectors remain `unverified` and withhold the calibration factor. The original defect was rejected or truncated submissions, not a demonstrated successful false calibration.
- **Numerical-method text follows the recorded method.** The UI labels adaptive `cell-integrated-gaussian-adaptive-gl-v2` and legacy `cell-integrated-gaussian-gl2-v1` separately. Unknown/missing identifiers have defensive component fallbacks, and unknown text is React-escaped. The service parser remains strict and rejects missing/unknown method identifiers in an API result with numerical diagnostics, so those fallbacks are not evidence that unknown API records are accepted.
- **One short track is not a six-section NIST optical result.** The legacy 280 W test still checks completion, energy audit and bounded peak, and its no-evaporation test still checks the boiling fail-closed path. Its invalid expectation that a 500 µm single-track fixture emits six independent optical sections was replaced with assertions that the observation is absent and the comparator returns unavailable/unvalidated with no numeric residual. No solver or evaporation physics changed.
- **Reproduction selects the existing locked CPU interpreter explicitly.** The application instructions set absolute `METALLIX_PYTHON` and `PYTHONDONTWRITEBYTECODE` before worker tests, run imports and `pip check`, and compare source hashes before/after. The runtime is prepared separately; the clean Git archive does not silently create or contain a fresh Python environment.

## Verification evidence

- Root-reported final combined Node integration: **41 PASS / 0 SKIP / 0 FAIL** in 1.813 s. The log contains test-environment Zustand persistence warnings; this result does not establish browser persistence or keyboard acceptance.
- Root-reported final bounded Python integration: **3 PASS / 0 SKIP / 0 FAIL** in 11.910 s: the two 280 W legacy contract tests and one existing measurement-evidence CPU fixture. Sol's focused frontend measurement submission suite finished **12/12 PASS**. Independent Luna backend review passed its existing unittest and rejected **8/8** malformed numeric/vector fixtures; the final combined root log includes the later unknown-field fixes.
- Root-reported `tsc --noEmit`: **PASS**. The source-label focused test reported **7/7 PASS** before final integration.
- The supported locked runtime was an existing CPU venv: Python 3.12.10, NumPy 2.2.6 and `pydantic` 2.13.5; root reported imports and `pip check` PASS. This is not a newly created clean venv or a clean Node install/build.
- Reproduction helper verification: document PowerShell syntax PASS; the documented hash function detected both unchanged and modified fixtures. Frozen source stable-read check covered 1,520 tracked blobs with one Git submodule pointer excluded. An initial helper attempt counted the 1,521 `ls-tree` entries including that gitlink and failed its 1,520-file expectation; the documented helper was corrected to enumerate blobs, then the check passed.
- Independent frozen-source verification found **1,520 matched files / 0 mismatches** for candidate `33efb32...`. That confirms preserved historical bytes only; it does not accept the new UI candidate.

The raw selected logs and reviewer notes are indexed in [`LPBF_CPU_INPUT_CLAIMS_2026-10-03_SUPPORT`](LPBF_CPU_INPUT_CLAIMS_2026-10-03_SUPPORT/README.txt), with a SHA-256 inventory.

## Limits and next gate

No full Python/GPU suite, clean install, final build, new solver study, NIST download, browser, keyboard, stale-input, or cancellation acceptance is claimed here. The earlier browser security denial remains in force; UI replay was not retried. NIST comparison is **unavailable** and **unvalidated**; physical moving-source convergence remains **inconclusive**; experimental validation is **unvalidated** and production readiness remains **false**. No new evaporation physics was tested or validated.

Next: commit only owned changes after integration review, then verify one exact clean candidate with the explicit locked Python environment, source-hash guard, supported unit/type/build gates, and browser acceptance only if access is restored. Keep this record as pre-commit integration evidence; later candidate results require a new dated record.
