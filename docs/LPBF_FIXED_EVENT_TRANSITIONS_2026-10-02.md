# LPBF Fixed-Event Liquidus Transition Analysis

Event time: `0.00024999999999999995 s`. This is a diagnostic comparison of accepted-step observations.

| Cell (i, j, k) | 50 ns endpoint / interval | 25 ns endpoint / interval | 12.5 ns endpoint / interval | Δ 50→25 (fine−coarse) | Δ 25→12.5 (fine−coarse) |
|---|---|---|---|---|---|
| `(29, 43, 60)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(30, 42, 60)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(30, 43, 59)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(30, 43, 60)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(30, 43, 61)` | 0.0001156 s; (0.00011555 s, 0.0001156 s] | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | one_sided_crossing | both_absent |
| `(30, 44, 60)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(31, 43, 60)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(58, 43, 61)` | 0.0002438 s; (0.00024375 s, 0.0002438 s] | 0.00024375 s; (0.000243725 s, 0.00024375 s] | 0.00024375 s; (0.0002437375 s, 0.00024375 s] | -5.00000001e-08 s | +9.89605533e-17 s (roundoff-equivalent) |
| `(58, 44, 61)` | 0.0002438 s; (0.00024375 s, 0.0002438 s] | 0.00024375 s; (0.000243725 s, 0.00024375 s] | 0.00024375 s; (0.0002437375 s, 0.00024375 s] | -5.00000001e-08 s | +9.89605533e-17 s (roundoff-equivalent) |
| `(59, 42, 61)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(59, 43, 60)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(59, 43, 61)` | censored; right-censored at 0.00025 s | 0.00025 s; (0.000249975 s, 0.00025 s]; terminal/boundary-sensitive | 0.00025 s; (0.0002499875 s, 0.00025 s]; terminal/boundary-sensitive | one_sided_crossing | +5.70832444e-17 s (roundoff-equivalent) |
| `(59, 43, 62)` | 0.0002301 s; (0.00023005 s, 0.0002301 s] | 0.00023005 s; (0.000230025 s, 0.00023005 s] | 0.00023005 s; (0.0002300375 s, 0.00023005 s] | -5.00000001e-08 s | +8.41069835e-17 s (roundoff-equivalent) |
| `(59, 44, 60)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(59, 44, 61)` | censored; right-censored at 0.00025 s | 0.00025 s; (0.000249975 s, 0.00025 s]; terminal/boundary-sensitive | 0.00025 s; (0.0002499875 s, 0.00025 s]; terminal/boundary-sensitive | one_sided_crossing | +5.70832444e-17 s (roundoff-equivalent) |
| `(59, 44, 62)` | 0.0002301 s; (0.00023005 s, 0.0002301 s] | 0.00023005 s; (0.000230025 s, 0.00023005 s] | 0.00023005 s; (0.0002300375 s, 0.00023005 s] | -5.00000001e-08 s | +8.41069835e-17 s (roundoff-equivalent) |
| `(59, 45, 61)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(60, 43, 61)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |
| `(60, 44, 61)` | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | censored; right-censored at 0.00025 s | both_absent | both_absent |

## Interpretation limits

- Each discrete detection is bracketed by the stored previous accepted clock and crossing endpoint; no continuous within-step crossing is established.
- Crossings on the event's final accepted step are boundary-sensitive at the fixed observation endpoint.
- Right-censored cells have no observed crossing by the event time; absence is not evidence of no later crossing.
- Roundoff-equivalent deltas retain their raw signed value and are only labeled using the stated tolerance.

Roundoff-equivalence threshold: `1.0e-14 s`; raw signed deltas are retained.
