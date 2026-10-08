# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- Maintainer note: keep this file under 200 lines. Area-specific rules belong in .claude/rules/ (python-solvers.md, frontend.md), which load only when matching files are touched. -->

## Repository

`Metalliksa-1/` (package `metallix-pocket-model`) is the product repo. The parent folder `metalliksaa/` is a separate git repo with workspace notes only; sibling `Metalliksa-1-*` folders and `tmp*` dirs there are old worktrees, ignore them. Check which repo a `git` command targets.

It is a local research workstation for metal additive manufacturing (LPBF thermal solvers, CALPHAD, kinetics, evidence registry). It is not a qualification tool.

## Commands

Node >= 22.13 (`.nvmrc` is 24), Python 3.11 or 3.12. The default Python runtime (`python/requirements-lpbf.in`) includes pycalphad, so CALPHAD runs without a second setup; the GPU/ML stack is the separate `python/requirements.txt`.

```bash
npm run dev                  # tsx server.ts, Express + Vite middleware, PORT default 3000
npm run build                # vite build + esbuild server.ts -> dist/server.cjs
npm start                    # node dist/server.cjs, with NODE_ENV=production
npm run lint                 # tsc --noEmit (the type check)
npm run lint:eslint          # eslint src server.ts routes server tests
npm run test:unit            # tsx --test tests/*.test.ts tests/*.test.tsx
npx tsx --test tests/<file>.test.ts                                # one test file
npx tsx --test --test-name-pattern="<name>" tests/<file>.test.ts   # one test case
npm run check:bundle         # build + gzip budgets in scripts/bundle-budgets.json
npm run test:meltpool        # melt-pool solver accuracy (python only)
npm run test:lpbf            # python/test_lpbf_build_job.py (:slow adds --slow)
npm run test:lpbf:engineering
npm run test:lpbf:api        # needs the dev server running
python python/test_<name>.py # one python test
```

- CI (`.github/workflows/ci.yml`, draft, never run on GitHub) runs the unit tests minus `scripts/ci-unit-tests.txt`. Keep that file LF; with CRLF the exclusion silently matches nothing.
- No AI route is served any more; `OPENAI_API_KEY` is only reported by the runtime config.

## Architecture

Three tiers: React 18 + Zustand (`src/`) -> Express (`server.ts`, `routes/`, `server/`) -> Python solvers (`python/`).

- The server spawns Python via `server/pythonRuntime.ts`, `pythonRoot.ts` and `processOrchestrator.ts`. Long LPBF jobs run in a persistent worker (`python/lpbf_worker.py`, bridged by `server/lpbfWorkerBridge.ts`).
- Runtime data, not source: `.lpbf-jobs`, `.lpbf-runs`, `.lpbf-run-bundles`, `.lpbf-sources`, `.runtime`.
- Routers mounted in `server.ts`: `researchRegistry`, `lpbfSources`, `lpbfRuns` (before the 50 MB `express.json`), then `physics`, `lpbfSimulation`, `characterization`, `research`.
- `routes/AUTHORITY_ALLOWLIST.json` is a ratchet baseline (with `.ceiling.json`); do not grow it to make a check pass.
- `server/airgap.ts` blocks outbound calls (Crossref search, OpenAI) in air-gap mode.
- Frontend state of record: `useMaterialSpecimenStore` (live LPBF vector), `useLpbfWorkflowStore` (stage and build context), `useLpbfEngineeringStore` (advanced inputs, job polling), `useLpbfBuildJobStore` (Python screening results), and the research registry (`src/types/research.ts`, persisted as `metalliksa-research-registry-v1`). Details: `docs/RESEARCH_WORKSTATION.md`.

## Evidence rules (from RULES.md)

- Never present mock, synthetic, estimated or unverified data as measured. Evidence kinds (Measured, Validated simulation, Calibrated simulation, Literature estimate, Screening only, Unresolved) are separate from module maturity (Production, Research, Preview, Unresolved).
- Qualification outputs cannot grant a release or certificate. Keep the Build -> ProcessParams -> Sample -> Properties -> Source chain (`docs/archive/SCHEMA.md`). A standards-compliance claim must name the ASTM/ISO standard and its scope.
- Report skipped and failed checks explicitly; an earlier pass is not current evidence.
- UI text is English; code identifiers and comments are English. Reply to the maintainer in Turkish.

## Git

- Stage explicit paths (other agents or the user may have uncommitted work here); never `git add .` or `-A`. Do not reset, clean or stash user work.
- Commit verified work locally. Push only when asked. Never commit `.env`, generated output or `.tmp-*` dirs.
- Product state lives in `STATUS.md`; update it at milestones only. Multi-agent runs: see `.orchestra/RESUME.md`.

## Working style

Use your judgement on tools, subagents and how much to verify for the size of the change; ask only when a decision is genuinely the maintainer's. Verify at the narrowest meaningful level and say plainly what was not run.

## Further reading

`docs/LPBF_ENGINEERING.md` (model scope and limits), `ROADMAP.md`, `docs/archive/SCHEMA.md`, `PROOF.md`, `RULES.md`.
