# Supporting evidence inventory

Evidence copied from `.tmp-lpbf-recovery-acceptance-20261003` on 2026-10-03. `SHA256SUMS.txt` hashes every support file except itself. Files are raw unless their name says derivative or helper. Large thermal field-state arrays and environment secrets are excluded.

- `clean-npm-elevated.*`, `clean-build-elevated.*`, `clean-lint.*`: clean runtime gates.
- `clean-unit-supported-final.*`, `clean-source-guard-supported-before/after.json`: authoritative supported Python suite and bracketing guards.
- `clean-unit-elevated.*`, `clean-unit.json/log`, `clean-unit-locked-python.*`: earlier failed/partial attempts; the elevated unit attempt had 357 PASS / 1 FAIL / 1 SKIP with `No module named pydantic`; the earlier sandbox run includes spawn EPERM. Preserve these as distinct attempts.
- `snapshot-source.json`: exact 1,520-file frozen source SHA map.
- `archive-comparison-and-recovery-derivative.json`: explicitly labeled compact derivative of before/after records; preserves exact official bare-plate source link and archived powder fixture conditions alongside comparator result and byte-equality assertions.
- `recovery-invariants-derivative.txt`: explains why large embedded before/after records were not copied.
- `cleanup-current.json`, `cleanup-helper.txt`: exact private-tree process-stop verification, released ports, and preserved data roots.
- `v1-claim-audit-sol.txt`: scoped review copied from scratch without rerunning tests.
- `boiling-error.jpg`, `restarted-error.jpg`, `boiling-job.json`, `crash-oracle.json`, `interrupted-job.json`: observed error UI and bounded job/recovery records.
- `numerical_diagnostics.json`, `numerical_diagnostics.py.txt`, `numerical.log`: four diagnostic-only checks and their observational helper.
- `bundle.log`, `cpu.log`: focused archive and worker suites.
- `job-api-evidence.json`, `roundtrip-evidence.json`: minimized completed-run API result and actual browser export/import/restore identity/inventory record.

The JSON/Markdown report is the concise summary. Software and workflow evidence does not establish experimental or production validation.
