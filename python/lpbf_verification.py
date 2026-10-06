"""Independent numerical checks. Calibration never changes validation status."""
import math


def compare(predicted, measured):
    if len(predicted) != len(measured) or not predicted:
        raise ValueError("Paired nonempty measurements required")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in predicted) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in measured):
        raise ValueError("Predictions must be nonnegative; measured dimensions must be positive and finite")
    e = [p-m for p, m in zip(predicted, measured)]
    denom = sum(p*p for p in predicted)
    factor = sum(p*m for p, m in zip(predicted, measured))/denom if denom else None
    return {"count": len(e), "errors_pct": [100*d/m for d, m in zip(e, measured)],
            "rmse_um": math.sqrt(sum(d*d for d in e)/len(e)), "bias_um": sum(e)/len(e),
            "calibrationFactor": factor, "status": "calibration-only",
            "note": "Least-squares dimension multiplier, not fitted absorptivity. Requires independent holdout validation."}


# Celik, Ghia, Roache & Freitas 2008, J. Fluids Eng. 130(7):078001, Step 2: a refinement factor
# r = h_coarse/h_fine greater than 1.3 is "desirable" ("based on experience, and not on formal
# derivation"). It is applied here as a gate: a smaller ratio gives an inconclusive check.
CELIK_MIN_REFINEMENT_RATIO = 1.3


def _celik_apparent_order(e32, e21, r21, r32, iterations=200, tol=1e-12):
    """Apparent order p, Celik et al. 2008 Eq. (3a-3c), by fixed-point iteration from the first term.

    Monotone case only (s = sign(e32/e21) = +1; the caller rejects oscillatory sets). Returns None when
    the iteration does not settle. q(p) = 0 when r21 == r32, which reproduces ln|e32/e21| / ln r.
    """
    s = 1.0
    ratio = abs(e32 / e21)
    p = abs(math.log(ratio)) / math.log(r21)
    for _ in range(iterations):
        num, den = r21 ** p - s, r32 ** p - s
        if num <= 0 or den <= 0:
            return None
        p_next = abs(math.log(ratio) + math.log(num / den)) / math.log(r21)
        if abs(p_next - p) <= tol * max(1.0, p):
            return p_next
        p = p_next
    return None


def convergence(values, spacings):
    """Three-grid check, coarse to fine: values/spacings ordered [coarse, medium, fine]."""
    if len(values) != 3 or len(spacings) != 3 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0
                                                                for x in list(values)+list(spacings)):
        return {"status": "inconclusive", "reason": "Three positive results required"}
    # Celik notation: grid 1 = fine, 3 = coarse; e32 = phi3 - phi2, e21 = phi2 - phi1.
    e32, e21 = values[0]-values[1], values[1]-values[2]
    # Cell extents can differ by a few ULPs after grid-coordinate arithmetic.
    # Such differences cannot support an observed order or a GCI estimate.
    roundoff = 32*math.ulp(max(values))
    if abs(e32) <= roundoff or abs(e21) <= roundoff:
        return {"status": "inconclusive", "reason": "Unresolved or identical discrete geometry"}
    if e32*e21 < 0:
        return {"status": "inconclusive", "oscillatory": True,
                "reason": "Non-monotonic (oscillatory) results: e32/e21 < 0 (Celik et al. 2008 Step 3)"}
    r21, r32 = spacings[1]/spacings[2], spacings[0]/spacings[1]
    if r21 <= 1 or r32 <= 1:
        return {"status": "inconclusive", "reason": "Spacings must strictly refine (coarse > medium > fine)"}
    if min(r21, r32) < CELIK_MIN_REFINEMENT_RATIO:
        return {"status": "inconclusive", "refinementRatios": [r32, r21],
                "reason": f"Refinement ratio below {CELIK_MIN_REFINEMENT_RATIO} (Celik et al. 2008 Step 2)"}
    # Monotone convergence toward h = 0 needs an apparent order p > 0. For phi = phi0 + C h^p,
    # e32/e21 = r21^p (r32^p - 1)/(r21^p - 1), which tends to ln r32 / ln r21 as p -> 0, so p > 0 iff
    # |e32/e21| exceeds that limit (for r21 == r32: |e32| > |e21|, the previous rule).
    if abs(e32/e21) <= math.log(r32)/math.log(r21) * (1 + 1e-12):
        return {"status": "inconclusive", "reason": "Non-converging trend (apparent order p <= 0)"}
    order = _celik_apparent_order(e32, e21, r21, r32)
    if order is None or not math.isfinite(order) or order <= 0:
        return {"status": "inconclusive", "reason": "Apparent-order iteration (Celik et al. 2008 Eq. 3) did not settle"}
    gci = 1.25*abs(e21/values[2])/(r21**order-1)
    return {"status": "numerically-converging", "observedOrder": order, "fineGCI_pct": 100*gci,
            "fineChange_pct": 100*abs(e21/values[2]), "refinementRatios": [r32, r21],
            "method": "Celik et al. 2008 Eq. 3-7 (unequal refinement ratios)",
            "note": "Numerical convergence is not experimental validation"}
