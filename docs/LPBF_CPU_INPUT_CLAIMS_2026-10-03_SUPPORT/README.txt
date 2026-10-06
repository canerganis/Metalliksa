# Supporting evidence inventory

Selected small raw logs, reports, and helper records for `../LPBF_CPU_INPUT_CLAIMS_2026-10-03.md`. Every file except this SHA list is covered by `SHA256SUMS.txt`. The inventory does not include environment secrets, full thermal outputs, browser captures, or a new clean build.

- `integration-node-final.log`, `integration-python-final.log`, `integration-typecheck-final.log`: root final bounded integration outputs; Node log includes storage-unavailable warnings.
- `sol-measurement-fix.txt`, `sol-ui-claim-map.txt`, `luna-backend-measurement-review.txt`: measurement-contract and displayed-claim review evidence.
- `luna-backend-unit.log`, `luna-backend-validator.log`: bounded backend fixture and validator checks.
- `luna-source-label.txt`, `luna-legacy-test.txt`: label and corrected 280 W test notes.
- `reproduction-check.json`, `frozen-source-check.json`: corrected doc/hash helper and immutable frozen-source result.
- `validate_reproduction.ps1.txt`, `verify_frozen_source.py.txt`: text-only helper copies. They are provided as review evidence, not launched from this directory.
- `helper-attempts.txt`: disclosure of the first gitlink-count failure and the fact that transient before/after fixture bytes were not retained; no raw log for that failed attempt was retained.
- `plan.txt`: bounded scope, ownership, and acceptance limits.

Root-reported environment probe: reused locked CPU venv Python 3.12.10, NumPy 2.2.6, pydantic 2.13.5, `pip check` PASS. This is not a fresh environment-install record. No broad Python/GPU suite, clean Node build, browser replay, experimental validation, or production qualification is established by this package.
