---
paths:
  - "python/**"
  - "tests/**/*python*"
  - "tests/**/*lpbf*"
---

# Python solver rules

- Material data goes through `python/lpbf_material_registry.py` and `python/alloy_registry.py`; golden files live in `python/golden/`. Update a golden file only when the physics change is intended, and say so in the commit.
- Solver code is pinned by `python/lpbf_implementation_fingerprint.expected` (checked by `python/lpbf_fingerprint_pin.py`). After editing a pinned solver file, regenerate the pin deliberately; never edit the `.expected` file by hand to silence a failure.
- Several `src/` TypeScript modules mirror Python physics, and `tests/` has cross-language checks. Change both sides in the same commit and run `npm run test:unit` plus the matching `python/test_*.py`.
- Use only the CPU baseline in `python/requirements-lpbf.in` for tests. `python/requirements.txt` pulls torch/CUDA; do not install it for CI-style runs.
- Tests that call `git show <old sha>` need full git history (CI uses `fetch-depth: 0`); with `CI` set they fail instead of skipping when a revision is missing.
- Physics change checklist: run `npm run test:meltpool`, `npm run test:lpbf` and the frozen benchmarks relevant to the module; record verified scientific claims in `PROOF.md`.
- `python/golden/phase6b/cnls_fitting_solver/*.json` (bound to blob faa6684) still hold the pre-EUQ-2 `cpeCapacitances` rows (initial-guess Rs/Rct). They are superseded: `python/test_phase6b_vector_parity.py` excludes that subtree and checks it against an independent Brug/Hsu-Mansfeld oracle. Re-pin those rows the next time the phase6b goldens are regenerated.
