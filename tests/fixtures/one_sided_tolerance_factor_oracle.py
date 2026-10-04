"""Exact one-sided normal tolerance factors k(N, p, gamma) from first principles.

Generates tests/fixtures/one-sided-tolerance-factor-oracle.json, the independent oracle used by
tests/utils-tolerance-factor.test.ts.

Definition (one-sided lower tolerance bound  xbar - k*s  that is below the p-quantile of a normal
population with confidence gamma):

    P( xbar - k s <= mu - z_p sigma ) = gamma

With Z = sqrt(N)(xbar - mu)/sigma ~ N(0,1) and V = (N-1) s^2/sigma^2 ~ chi2(N-1) independent, this is

    P( (Z + z_p sqrt(N)) / sqrt(V/(N-1)) <= k sqrt(N) ) = gamma

i.e. k sqrt(N) is the gamma-quantile of a non-central t with df = N-1 and non-centrality z_p sqrt(N):

    k = nct.ppf(gamma, N-1, z_p sqrt(N)) / sqrt(N)

The value is computed twice, independently:
  * "exact": scipy.stats.nct.ppf (Boost non-central t implementation),
  * "quad":  the same probability written as a 1-D integral over the chi2(N-1) density,
             P = int_0^inf Phi(k sqrt(N) sqrt(v/(N-1)) - z_p sqrt(N)) f_chi2(v; N-1) dv,
             solved for k with brentq.  The two must agree to 1e-6 or the script aborts.

Run with the locked interpreter (scipy 1.15.3, numpy 2.2.6):
    .runtime/lpbf-win-py312/Scripts/python.exe -B tests/fixtures/one_sided_tolerance_factor_oracle.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import scipy
from scipy import integrate, optimize, stats

CONFIDENCE = 0.95
BASES = {"A": 0.99, "B": 0.90}
N_VALUES = list(range(5, 301))


def k_exact(n: int, p: float, gamma: float) -> float:
    zp = stats.norm.ppf(p)
    return float(stats.nct.ppf(gamma, n - 1, zp * math.sqrt(n)) / math.sqrt(n))


def k_quad(n: int, p: float, gamma: float) -> float:
    zp = stats.norm.ppf(p)
    df = n - 1
    delta = zp * math.sqrt(n)
    chi2 = stats.chi2(df)
    lo, hi = chi2.ppf(1e-14), chi2.ppf(1 - 1e-14)

    def coverage(k: float) -> float:
        t = k * math.sqrt(n)
        f = lambda v: stats.norm.cdf(t * math.sqrt(v / df) - delta) * chi2.pdf(v)
        val, _ = integrate.quad(f, lo, hi, epsabs=1e-13, epsrel=1e-12, limit=400)
        return val

    return float(optimize.brentq(lambda k: coverage(k) - gamma, zp, zp + 20.0, xtol=1e-12))


def main() -> None:
    rows = []
    for n in N_VALUES:
        row = {"N": n}
        for basis, p in BASES.items():
            e = k_exact(n, p, CONFIDENCE)
            q = k_quad(n, p, CONFIDENCE)
            if abs(e - q) > 1e-6:
                raise SystemExit(f"nct vs quadrature disagree at N={n} basis {basis}: {e} vs {q}")
            row[f"k{basis}"] = round(e, 6)
        rows.append(row)
    out = {
        "description": "Exact one-sided normal tolerance factors k = nct.ppf(0.95, N-1, z_p*sqrt(N))/sqrt(N); "
        "A-basis p=0.99, B-basis p=0.90, confidence 0.95. Cross-checked against chi2 quadrature (|diff| <= 1e-6).",
        "generator": "tests/fixtures/one_sided_tolerance_factor_oracle.py",
        "scipy": scipy.__version__,
        "numpy": np.__version__,
        "confidence": CONFIDENCE,
        "p": BASES,
        "rows": rows,
    }
    target = Path(__file__).with_name("one-sided-tolerance-factor-oracle.json")
    target.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {target} ({len(rows)} rows)")
    for n in (5, 10, 30, 60, 100, 200, 300):
        r = rows[n - 5]
        print(n, r["kA"], r["kB"])


if __name__ == "__main__":
    main()
