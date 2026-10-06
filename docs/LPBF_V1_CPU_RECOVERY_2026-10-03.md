# LPBF V1 CPU Recovery Acceptance — 2026-10-03

## Decision

This record documents bounded recovery and archive evidence for candidate `33efb32b7d9734587a78d1cb9de8224d7ef2a4ec`. It is **not full V1 acceptance**. The latest production-source archive contains 1,520 tracked files. Its manifest SHA-256 is `1570a5186cf02cd3f53d1c96883bce0cb6c2f0495c7da08c83bc8a31aeb180a7`; the frozen production runtime is `.runtime/v1-recovery-acceptance-20261003`.

## Candidate and clean-runtime evidence

- Offline `npm ci --offline --no-audit --no-fund`: **PASS**, 850 packages. Initial non-elevated attempts failed during cleanup with `ENOTEMPTY` and `EPERM`; the successful recorded install used the authorized elevated runner without changing install-script policy.
- TypeScript/lint and production build: **PASS** in the clean candidate runtime.
- Final unit suite: **358 PASS / 1 SKIP / 0 FAIL** (359 tests), with Python 3.12 and `pydantic 2.13.5`, explicit locked `.runtime/lpbf-win-py312`, and `PYTHONDONTWRITEBYTECODE=1`.
- The successful suite is bracketed by supported source guards: the same candidate and 1,520-file manifest, zero mismatches before and after. This is the authoritative integrity sequence.
- An earlier elevated unit attempt used the wrong/default Python, lacked `pydantic`, and produced **357 PASS / 1 FAIL / 1 SKIP**. A separate earlier sandbox run hit `spawn EPERM`. The wrong-Python attempt also rewrote tracked CPython 3.10 bytecode temporarily; those files were restored to HEAD. Therefore that attempt was **not** an uninterrupted integrity pass and is not merged into the final supported-run claim.
- The observational manufactured/numerical diagnostic ran four checks, all PASS. It is diagnostic only: experimental validation is false, solver validation is unvalidated, and physical LPBF convergence is inconclusive.

## CPU error and owner-crash behavior

- A real bounded boiling-limit job `72367015fbcc42ea9772eaa9b9e48b75` failed with the full thermal validity error. It retained the last valid state at 128 accepted steps, 258 source evaluations, 129 retries, and 7,736,904 source cell-evaluations. No completed result was published; its two partial artifacts remained explicitly `retained-unverified`.
- A separate real Reference job `3723637ab80a4b1394d2bb2827c9ea84` was interrupted by killing only its owner PID. Owner and child handles signaled within 0.343 seconds, the Node process stayed alive, and result files were absent. On lazy worker restart, the job became failed with exact error `Worker restarted during execution`; artifact access was rejected (HTTP 400), and 12 partial files (1,679,328 bytes) remained `retained-unverified`. Hard-kill last-valid CPU state is unavailable and is not inferred.
- This owner-only crash is distinct from a later production-node disappearance. The original Node processes (PIDs 28016/25984) were subsequently confirmed missing, with cause unknown. Two isolated Node server processes (PIDs 12312 and 7860) were later identity-checked against their private source/data roots, then both verified stopped; ports 3030, 3031, 5070, and 5071 were released and data roots were preserved. The narrow sandbox stop first received Access Denied; the exact approved elevated helper completed the verified cleanup. This event is not attributed to the deliberate owner crash.
- A fresh bounded Reference job `3e4d91d25763402bba3fbfa68d5ecbcd` completed in 19.25 seconds. The earlier completed job, archive, and source records remained byte-exact across recovery: prior job/run/source file counts were 71/72/5, and all 1,520 frozen source files matched.

## Browser archive round trip

An earlier actual in-app-browser sequence configured and ran Reference job `419c408729b44f36905c60085b9f1467`, then exported bundle `026751ab54be4b299d5a2dc72d690f1a`, imported `79c6072d26d54140902bdf142b16ff3d`, restored `ce5b7ac053cc49caa4878c600fb402dc`, and reloaded the result. The exported/imported 75 files and 71 restored objects matched byte-for-byte; the original/restored run record matched exactly. TAR size was 8,109,568 bytes with SHA-256 `efedf1570f43a33156c36b827f51f583d6c6fadf30589c4a89a802133118c661`. SQLite container byte identity is not claimed because restore creates fresh verified backups.

The provider download call took about 9.19 hours and the file chooser took 51.321 seconds. These are provider/UI automation delays; they are **not** product download latency measurements. A later session reset left no CUA tabs. Opening the local browser page was denied by browser security policy (`user declined permission`) and was not retried. Thus the earlier completed UI/API round trip remains evidence, but fresh screenshots and final same-candidate stale-input/cancellation browser checks remain pending.

## Evidence limits and next work

- The archived run is exactly bound to official workbook dataset `nist-amb2022-03-optical-xlsx-official-v1`, revision 1, SHA-256 `73293ca6c2a1929a2e244f806d6eb5900d4c739716f7f291e74c9bc12dc291b6`; its record says `exact-revision-bound`. The comparison service separately requires an eligible local Table 4 dataset binding (`nist-amb2022-03-optical-table4-local-v1`). These are distinct source contracts: the official workbook binding is valid, and the comparator's reason that no local Table 4 binding exists is also valid. The comparison remains **unavailable** and **unvalidated**. The bound workbook describes bare-plate optical measurements, while this archived fixture is a 600 µm powder-layer run (60 W, 1200 mm/s, 200 °C). It lacks a validated matching optical operator and comparable bare-plate conditions. No new NIST download was performed.
- A scoped claim audit found no active production path publishing an invalid NIST residual in its reviewed scope. It did find a historical PROOF entry asserting six-section observer output and official residuals, contradicted by the frozen comparator's unconditional disable and current unavailability. The audit also found the legacy 280 W Python test expects six sections from a single track; it was not run and must not support an all-Python-tests-pass claim. Root integration must mark the old claim superseded/unsupported and preserve the historical record.
- The six-section helper is test-only in the reviewed candidate and does not independently verify section/run provenance; it is insufficient evidence to enable or claim a validated optical comparison.
- Experimental validation remains **unvalidated**; production readiness is **false**. Numerical/software/UI checks do not establish experimental or production validity.
- Full V1 acceptance remains open. Remaining work includes fresh same-candidate stale-input and cancellation/malformed checks, current browser confirmation after access is available, and root integration of the scoped claim audit into STATUS/PROOF/index. Isolated data roots are retained; the private test server processes are stopped.
- Provider timing and unknown-cause process disappearance should remain explicitly separated from product latency and the deliberate owner-only crash test.

## Durable supporting records

Raw records, selected logs, helper notes, the scoped claim audit, and a file SHA-256 inventory are in [`LPBF_V1_CPU_RECOVERY_2026-10-03_SUPPORT`](LPBF_V1_CPU_RECOVERY_2026-10-03_SUPPORT/README.txt). Large field-state arrays, environment secrets, and unrelated scratch files were not copied. The source scratch remains `.tmp-lpbf-recovery-acceptance-20261003`.
