# Engineering startup execution

The versioned progress ledger in `src/data/engineeringRoadmap.ts` tracks the 20 work packages agreed on 2026-09-15. It measures evidenced work, not industrial qualification or elapsed time. The LPBF workspace displays this ledger.

Each package has equal weight (5/100). Ordered milestones earn 10% definition, 35% implementation, 30% testing, 15% independent review, and 10% acceptance. Every credited milestone requires evidence, date and reviewer. Acceptance requires accepted dependencies and no blocker. Reopening a milestone removes it and all subsequent credit; preserve the reason in the work log.

Customer interviews and pilot acceptance remain founder/customer work. Technical foundations may be developed before those dependencies close, but final package acceptance cannot bypass them. No customer evidence or scientific approval is inferred from automated tests.

Industrial gates are cumulative: each gate needs its own accepted tasks and every earlier gate. In particular, H01/H02 task progress cannot bypass unaccepted E02/E03/E04/F01 modules at K2. The 20-task scope is unchanged.

The latest 2026-09-15 continuation closes A01 and A02 after independent review. Each is 100% complete within its stated technical acceptance scope. Total evidenced work is **10%**, remaining **90%**, with **2/20 packages** and zero industrial gates accepted. This measures the startup work scope, not physical-model accuracy or the fraction of existing application code completed. The earlier 4.25% and 5.5% snapshots are superseded by recorded evidence, not an arbitrary progress target. A02's versioned evidence is in `docs/evidence/a02-environment-2026-09-15.json`.

Customer track decision: founder interviews and customer-specific pilot criteria (B01/B02) are deferred. We may continue C01/C02 using explicitly labelled generic engineering assumptions and sourced public data, but B01/B02 remain uncredited and all pilot, holdout and commercial gates remain blocked until a customer scope is supplied. No customer evidence or scientific approval is inferred from automated tests.

Next: C01/C02 technical material-data foundations under the deferred-customer scope. Record every assumption, source, unit and limitation so the work can be re-scoped when pilot inputs arrive.

## Execution order

1. A01: map active modules, solver paths, test evidence and unresolved model limitations.
2. A02: diagnose and reproduce the actual application interpreter, dependencies and tools.
3. C01/C02 foundations: module data requirements, provenance, units, source acquisition, checksums and quarantine before transfer. Offline work must remain possible; raw detector signals are not temperatures.
4. D01/D02: numerical verification followed by independent experimental validation within a declared scope.
5. E01 and UI: connect reviewed data to modules; then apply selected shadcn/Radix/TanStack patterns to engineering screens.

UI reference repositories were cloned in the installation workspace on 2026-09-15. Integration is pending the interface audit. Do not treat cloning as implementation credit.

## Per-job handoff

Record changed behavior, tests and failures, milestone evidence, overall earned/remaining percentage, accepted package count, blockers and the immediate next action in `sonkayıtlar/LOG.md`. Commit and push each coherent tested change; stage only task-owned edits.
