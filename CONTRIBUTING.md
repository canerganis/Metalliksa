# Contributing to Metalliksa

Metalliksa is under active development (pre-1.0): interfaces, data formats and results can change. See [STATUS.md](STATUS.md) for the current state and [docs/GOOD_FIRST_ISSUES.md](docs/GOOD_FIRST_ISSUES.md) for starter tasks.

## Setup and checks

Node >= 22.13 and Python 3.11 or 3.12.

```bash
npm ci
pip install -r python/requirements-lpbf.in
npm run lint            # tsc --noEmit
npm run test:unit       # TypeScript/TSX tests
npm run test:meltpool   # melt-pool solver accuracy (Python)
npm run build
```

Run one file with `npx tsx --test tests/<file>.test.ts` and one Python test with `python python/test_<name>.py`. The long LPBF worker tests can time out under load; rerun them alone before reporting a failure. Say plainly which checks you did not run.

## Evidence rules (short version; full text in [RULES.md](RULES.md))

- Never present synthetic, estimated or unverified data as measured.
- Cite a source for every value: DOI or URL, locator (table or figure), units, and a digitization flag where a value was read from a figure.
- Pre-declare an evaluation (data split, metric, gate) before looking at results; do not adjust thresholds afterwards.
- Record failed, skipped and unavailable checks next to the passing ones.
- Do not fill a missing property from another alloy; mark it unresolved.
- Published papers and publisher PDFs are not redistributed; respect each dataset's licence.

## Pull requests

- Keep changes small and scoped; describe the input/output contract for scientific changes.
- Stage explicit paths (`git add <file>`); avoid `git add .` and `git add -A`.
- Do not edit the frozen LPBF physics, goldens or the implementation fingerprint except through a planned, reviewed bump (see [PROOF.md](PROOF.md)). Files listed in `.github/CODEOWNERS`, including `.github/workflows/ci.yml`, need maintainer review.
- UI and documentation text is English.
