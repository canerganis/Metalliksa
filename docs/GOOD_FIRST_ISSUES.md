# Good first issues

Scoped starter tasks drawn from the open items in [STATUS.md](../STATUS.md) and the backlog. Read [CONTRIBUTING.md](../CONTRIBUTING.md) first: evidence rules apply to every item, and the frozen LPBF physics, goldens and fingerprint are out of scope for starters.

1. **Document the `lpbf-optimizer` module contract.** STATUS.md lists the optimizer contract document as open (the contracted-modules test depends on it). Write the input/output contract, scope and limits.
   Files: `docs/modules/` (new `lpbf-optimizer.md`, see `lpbf-calibration-scorecard.md` as a model), `python/module_contracts_lpbf_secondary.py`, `python/test_module_contract_lpbf_secondary.py`.

2. **Confirm the KU Leuven beam diameter and datum.** The scorecard carries two beam readings (37.5 vs 75 um) and the decision changes between them. Check the published dataset description, record the answer with a locator, or mark it unresolved.
   Files: `docs/LPBF_KEYHOLE_BEAM_CONVENTION_2026-10-07.md`, `docs/LITERATURE_SOURCES.md`, `data/calibration/`.

3. **Investigate the Ghosh vs Lane IN625 depth discrepancy.** Ghosh 2018 (digitized) and Lane 2020 disagree on depth for IN625; document whether datum, cross-section or absorptivity explains it. No threshold or physics changes.
   Files: `docs/LITERATURE_SOURCES.md`, `docs/LPBF_CALIBRATION_HELDOUT_2026-10-06.md`, `data/benchmark/README.md`.

4. **Add IN625 to the build job documentation and checks.** The error-band and build-job text notes IN718 relies on a single sentinel source and IN625 coverage is partial; document what is supported for IN625 and where it is shown in the UI.
   Files: `docs/LPBF_ENGINEERING.md`, `python/lpbf_build_job_solver.py` (read-only reference), `tests/`.

5. **Translate the README.** Add `README.tr.md` (or another language) that preserves every limit and evidence statement without adding claims, and link it from the README header.
   Files: `README.md`, new `README.<lang>.md`.

6. **Add a source-locator audit script.** Check that every literature table row lists DOI, locator and a digitization flag, and report gaps without changing data.
   Files: `scripts/` (new script), `data/`, `docs/LITERATURE_SOURCES.md`, a test in `tests/`.

7. **Missing sources noted in STATUS.md.** Locate the open-access Zhao supplementary information or Huang supplementary table 3 (or document that they are unavailable), and record licence and locators.
   Files: `docs/LITERATURE_SOURCES.md`, `docs/LPBF_KEYHOLE_LITERATURE_NOTES_2026-10-07.md`.

8. **Improve README and docs link checking.** Add a small test that every relative link and image path in `README.md` and `CONTRIBUTING.md` exists.
   Files: `tests/` (new test file), `README.md`.
