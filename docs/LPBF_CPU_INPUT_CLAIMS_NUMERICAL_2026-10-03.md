# Exact-candidate CPU numerical verification — 2026-10-03

Candidate `ec3a5fcbeb1c5aa1b250ed31a4e812796c5d17ce` was extracted with `git archive` into `.runtime/v1-input-claims-20261003`. All **1,579 tracked source files** matched before the CPU suite, after that suite, and after the separate diagnostic rerun. No source was restored to conceal a mismatch. The [structured record](LPBF_CPU_INPUT_CLAIMS_NUMERICAL_2026-10-03.json) and [byte-exact support inventory](LPBF_CPU_INPUT_CLAIMS_NUMERICAL_2026-10-03_SUPPORT/SHA256.json) retain commands, logs, manifests and the observational harness.

## Results

- Bounded CPU suite: **27 PASS / 0 FAIL / 0 SKIP**, unittest time **22.988 s**. It covers existing manufactured transient operators, worker failure summaries/progress/automatic dispatch, the two legacy 280 W cases, and one nested measurement-evidence fixture. This is not the full Python suite.
- A separate instrumented rerun of the four manufactured/diffusion tests: **4 PASS**, unittest time **13.038 s**. Those four tests are already included in the 27; this is **27 distinct tests**, not 31.
- Explicit reused locked CPU interpreter: Python **3.12.10**. This does not establish a fresh Python environment install. Bytecode writes were disabled and a separate `cpu-temp` root kept the Node clean-install work independent.
- Canonical implementation identity remained `4cf24334a711ecf6fd41597cb087726580c0ed85b52ece72e0f15b89f6802e35` before and after diagnostics. Existing source and numerical thresholds were unchanged.

| Existing numerical case | Actual accepted steps |
|---|---|
| Uniform enthalpy ramp | 23 / 38 / 75 |
| Nonuniform enthalpy solution | 23 / 38 / 75 |
| Piecewise enthalpy phase-change ramp | 34 / 42 / 75 |
| Mixed-boundary diffusion, z levels 8 / 16 / 32 | 47 / 187 / 747 |

Diffusion RMS errors were **0.000565596212 → 0.000142081157 → 3.55629767e-05 K**; observed orders were **1.99305723 / 1.99826724**. The existing tests require monotonically decreasing RMS and order greater than 1 while refining space and time together (`dt ∝ dx²`). This does not separate spatial from temporal error.

The **1e-7 K** absolute bound applies only to uniform/nonuniform manufactured **final temperatures**. The **1e-10** relative energy bound applies across the cases. Piecewise sampled errors and diffusion RMS use their own assertions; the temperature bound is not reassigned to them.

## Evidence limits

The harness observes only the four existing unittest method frames and retains actual diagnostic values without changing production operators or tests. Only the fresh candidate's software/operator checks are supported here. Real moving-source LPBF mesh/time convergence remains **inconclusive**, NIST comparison **unavailable**, and experimental validity **unvalidated**. No new physics or large 5 µm solve was launched.

Node dependency installation, full unit/type/build reproduction, real UI keyboard/render behavior, the archived 60 W workflow and critical live recovery paths require their own records against this candidate. The earlier `33efb32` browser evidence is historical. Previous browser opening was explicitly denied; it has not been bypassed. **V1 release acceptance remains open.**
