# IN625 CUDA repeated timing after inversion synchronization reduction — 2026-09-24

## Method

After commit 150e604, each resolution had one CPU and one explicit
cuda:0 warm-up excluded from timing, followed by five alternating CPU/CUDA
repeats. CUDA was synchronized immediately before and after each timed call.
The same source profile, domain, initial temperature, boundary conditions, and
duration were used for each CPU/CUDA pair. The measured interval covers the
direct run_cpu or run_cuda call, including solver work and result/diagnostic
construction; it excludes UI/API transport. This is a small local timing
campaign, not a general device benchmark.

## Results

| Grid | CPU median (range) | CUDA median (range) | CUDA / CPU median | Max temperature difference |
| --- | ---: | ---: | ---: | ---: |
| 128 cells, 33 steps | 0.197975 s (0.194243–0.219378) | 4.876871 s (4.855451–5.157074) | 24.634× slower | 4.547e-13 K |
| 1,024 cells, 132 steps | 1.358964 s (1.311236–1.636411) | 19.098597 s (18.307919–20.404802) | 14.054× slower | 9.095e-13 K |

The focused field suite passed 12/12 after the synchronization reduction,
including independent enthalpy and energy checks. CUDA remains substantially
slower at both tested sizes. The earlier one-shot timing rows are not a paired
before/after campaign, so this measurement cannot establish how much of the
difference came from the code change, warm-up, or run conditions. No speedup or
crossover is claimed.

## Scope

This is a numerical screening law only. It does not qualify IN625, validate
LPBF process behavior, establish a general transient path, or close P6/P7.

## Larger same-domain anisotropic refinement

A follow-on synthetic case doubled the cell count from 1,024 to 2,048 by
refining z only while preserving the 2 mm × 2 mm × 0.5 mm domain, 3.3 ms
duration, 30 W absorbed source, 0.099 J input, source profile, and 1500 K
initial state. The grid was 16 × 16 × 8 with cell sizes
125 × 125 × 62.5 µm, dt = 12.5 µs, and 264 steps. One warm-up per backend
was excluded, then three CPU/CUDA timings alternated:

| Grid | CPU median (range) | CUDA median (range) | CUDA / CPU median |
| --- | ---: | ---: | ---: |
| 2,048 cells, z-refined | 4.012762 s (3.992162–4.127304) | 43.616675 s (37.312368–43.836660) | 10.869× slower |

The CPU and CUDA runs both reached 1593.516258 K and 44 mushy cells. The
independent 64-point enthalpy and total-energy oracles passed for both outputs;
maximum CPU/CUDA differences were 9.095e-13 K and 4.657e-10 J/kg. This
higher-resolution synthetic case still does not qualify the material or
process. CUDA remained slower; no crossover is demonstrated.

## Fused CUDA enthalpy inversion — 2026-09-25

The 60-step pointwise Torch bisection was replaced on the explicit CUDA path by
one float64 Warp kernel per enthalpy inversion. The kernel retains the same
bounded interval, enthalpy law, comparison direction and all 60 bisection
updates. The Torch-loop implementation remains the fallback when Warp cannot
be imported. Focused IN625 field tests passed **13/13**, including a direct Warp
inverse check at the reference, solidus and liquidus boundaries, field parity,
independent enthalpy and energy checks.

The timing workload was unchanged from the 2,048-cell z-refined case above:
16 × 16 × 8 cells, 125 × 125 × 62.5 µm cells, 1500 K initial state,
12.5 µs step, 264 steps, 30 W absorbed power, 0.3 mm Gaussian sigma and a
stationary source at (1, 1) mm. All runs used explicit `cuda:0`, identical
material revision `f47b07e4…6f07`, CUDA synchronization immediately before
and after each timed call, one untimed backend warm-up, and a 180 s per-call
cap. No sample timed out.

| Alternating pair | Torch-loop CUDA | Fused Warp CUDA | Peak temperature (both) | Mushy cells (both) |
| --- | ---: | ---: | ---: | ---: |
| 1 | 52.972063 s | 2.097026 s | 1593.516257613138 K | 44 |
| 2 | 33.083509 s | 1.355652 s | 1593.516257613138 K | 44 |
| 3 | 34.246542 s | 1.529947 s | 1593.516257613138 K | 44 |

Median time was 34.246542 s for Torch and 1.529947 s for Warp on this one
workload. Pair ratios were 25.261×, 24.404× and 22.384×. Timings varied by
about 1.6× within each backend, so the evidence supports a repeatable direction
of improvement for this case but not a stable or application-wide speedup
factor. Torch and Warp summed specific enthalpy differed by 5×10⁻⁷ J/kg
(relative 3.4×10⁻¹⁶); both reported final total enthalpy 11.570662616926892 J
and maximum energy residual 5.329070518200751×10⁻¹⁵ J. This is numerical
parity for the bounded screening workload, not material or LPBF process
validation, and does not establish GPU parity for other thermal contracts.
