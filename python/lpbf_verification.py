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


def convergence(values, spacings):
    if len(values) != 3 or len(spacings) != 3 or not all(math.isfinite(x) and x > 0 for x in values+spacings):
        return {"status": "inconclusive", "reason": "Three positive results required"}
    r = spacings[0]/spacings[1]
    if r <= 1 or abs(spacings[1]/spacings[2]-r) > 0.02*r:
        return {"status": "inconclusive", "reason": "A constant refinement ratio > 1 is required"}
    a, b = values[0]-values[1], values[1]-values[2]
    # Cell extents can differ by a few ULPs after grid-coordinate arithmetic.
    # Such differences cannot support an observed order or a GCI estimate.
    roundoff = 32*math.ulp(max(values))
    if abs(a) <= roundoff or abs(b) <= roundoff or a*b <= 0 or abs(a) <= abs(b):
        return {"status": "inconclusive", "reason": "Non-monotonic, unresolved or identical discrete geometry"}
    order = math.log(abs(a/b))/math.log(r)
    gci = 1.25*abs(b/values[2])/(r**order-1)
    return {"status": "numerically-converging", "observedOrder": order, "fineGCI_pct": 100*gci,
            "fineChange_pct": 100*abs(b/values[2]), "note": "Numerical convergence is not experimental validation"}
