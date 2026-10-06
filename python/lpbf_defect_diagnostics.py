"""Geometric LPBF screening; these outputs are not defect probabilities.

The overlap criterion assumes identical, aligned semi-elliptical melt pools.
W is full width and D is penetration depth. At the midpoint between tracks,
the ellipse ordinate is D sqrt(1 - (H/W)^2); requiring it to reach the previous
layer gives (H/W)^2 + (T/D)^2 <= 1. Solving for H gives maximumHatch_um.
No material-specific empirical correction is applied.
"""

import math
from numbers import Real


MODEL_ID = "elliptic-overlap-screening-v1"


def _dimension(name, value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        qualifier = "positive" if positive else "nonnegative"
        raise ValueError(f"{name} must be finite and {qualifier}")
    return value


def _finite_ratio(numerator, denominator):
    if denominator == 0:
        return None
    value = numerator / denominator
    return value if math.isfinite(value) else None


def defect_diagnostics(width_um, depth_um, length_um, hatch_um, layer_um, *, aggregate=False):
    """Return finite JSON-compatible geometry screens or explicit unresolved values.

    Dimensions are micrometres. Invalid inputs raise ValueError. ``aggregate``
    denotes bounding dimensions of multiple tracks, which cannot be screened as
    a single melt-pool cross-section. Null risks mean physically unresolved.
    """
    width = _dimension("width_um", width_um)
    depth = _dimension("depth_um", depth_um)
    length = _dimension("length_um", length_um)
    hatch = _dimension("hatch_um", hatch_um, positive=True)
    layer = _dimension("layer_um", layer_um, positive=True)
    if not isinstance(aggregate, bool):
        raise ValueError("aggregate must be a boolean")

    limitations = [
        "Geometric screening only; no pore probability, porosity estimate, or certification.",
        "Requires local single-track width and penetration depth for an aligned semi-elliptical cross-section.",
        "Ignores local pool fluctuations, track registration, powder packing, and remelting history.",
        "Accuracy depends on supplied geometry; Rosenthal-derived dimensions can fail this screen.",
        "No Ti-6Al-4V-specific correction or universal keyhole/balling threshold is applied.",
    ]
    lof = {
        "status": "unresolved", "ellipseIndex": None, "signedMargin": None,
        "overlapDepth_um": None, "maximumHatch_um": None, "riskScreened": None,
        "reason": None,
    }
    result = {
        "modelId": MODEL_ID,
        "scope": "aggregate-multi-track" if aggregate else "single-track-cross-section",
        "status": "unresolved", "limitations": limitations,
        "lackOfFusion": lof,
        "keyhole": {
            "depthToWidth": None, "risk": None, "kingModeIndicator": None,
            "reason": "Aspect ratio alone cannot resolve vapor depression stability or keyhole pore formation.",
        },
        "balling": {
            "lengthToWidth": None, "risk": None,
            "reason": "Elongation alone cannot resolve capillary breakup, wetting, or track continuity.",
        },
        "gasPore": {"risk": None, "reason": "Gas inventory, transport, and pore nucleation are not resolved."},
        "porosity": {"value": None, "reason": "Geometry screening does not predict volumetric porosity."},
        "provenance": [{
            "title": "Harkin et al. (2023), Equation 5",
            "url": "https://link.springer.com/article/10.1007/s00170-023-11163-0",
            "use": "Semi-elliptical overlap criterion; empirical material-specific correction excluded.",
        }],
    }
    if aggregate:
        lof["reason"] = "Aggregate bounding dimensions do not identify local inter-track or inter-layer overlap."
        return result

    result["keyhole"]["depthToWidth"] = _finite_ratio(depth, width)
    result["balling"]["lengthToWidth"] = _finite_ratio(length, width)
    # Balling Instability (Rayleigh-Plateau Criterion)
    # Cylindrical capillary breakup when length/width > \pi (Yadroitsev continuity threshold)
    lw_ratio = result["balling"]["lengthToWidth"]
    if lw_ratio is not None:
        if lw_ratio > math.pi * 1.2:
            result["balling"]["risk"] = "high"
            result["balling"]["reason"] = f"L/W ratio {lw_ratio:.2f} significantly exceeds Rayleigh-Plateau limit (\u03c0). High risk of severe balling and track discontinuity."
        elif lw_ratio > math.pi:
            result["balling"]["risk"] = "moderate"
            result["balling"]["reason"] = f"L/W ratio {lw_ratio:.2f} exceeds \u03c0 limit. Marginal capillary instability expected."
        else:
            result["balling"]["risk"] = "low"
            result["balling"]["reason"] = f"L/W ratio {lw_ratio:.2f} < \u03c0 indicates stable continuous track without capillary breakup."
        result["provenance"].append({
            "title": "Yadroitsev et al. (2010)",
            "url": "https://doi.org/10.1016/j.jmatprotec.2010.01.011",
            "use": "Rayleigh-Plateau capillary instability for single-track balling (L/W > \u03c0).",
        })

    # Keyhole: no stability/porosity verdict from D/W alone (see limitations; risk stays None). The
    # King et al. 2014 sec. 5.2 classification (keyhole mode when depth > half-width, D/W > 0.5) is
    # reported as a mode indicator only. The old 1.5 / 1.0 thresholds are in neither King 2014 nor
    # Cunningham 2019.
    aspect_ratio = _finite_ratio(depth, width)
    if aspect_ratio is not None:
        mode = "keyhole-mode" if aspect_ratio > 0.5 else "conduction-mode"
        result["keyhole"]["kingModeIndicator"] = mode
        result["keyhole"]["reason"] = (
            f"D/W {aspect_ratio:.2f} {'>' if aspect_ratio > 0.5 else '<='} 0.5: {mode} by the King et al. 2014 "
            "depth > half-width classification. Aspect ratio alone cannot resolve vapor depression stability "
            "or keyhole pore formation, so no risk is assigned.")
        result["provenance"].append({
            "title": "King et al. (2014), J. Mater. Process. Technol. 214, 2915, sec. 5.2",
            "url": "https://doi.org/10.1016/j.jmatprotec.2014.06.005",
            "use": "Keyhole-mode classification when melt-pool depth exceeds the half-width (D/W > 0.5); label only.",
        })

    if width == 0 or depth == 0:
        lof.update({
            "status": "no-melt" if width == 0 else "inadequate-penetration",
            "overlapDepth_um": 0.0, "maximumHatch_um": 0.0, "riskScreened": True,
            "reason": "Zero width or penetration cannot cover a positive hatch and layer thickness.",
        })
        result["status"] = "geometry-screened"
        return result

    h_ratio = _finite_ratio(hatch, width)
    t_ratio = _finite_ratio(layer, depth)
    # The piecewise form avoids overflow in squares outside the ellipse.
    lof["overlapDepth_um"] = (
        depth * math.sqrt(max(0.0, (1 - h_ratio) * (1 + h_ratio)))
        if h_ratio is not None and h_ratio < 1 else 0.0
    )
    lof["maximumHatch_um"] = (
        width * math.sqrt(max(0.0, (1 - t_ratio) * (1 + t_ratio)))
        if t_ratio is not None and t_ratio < 1 else 0.0
    )
    index = None if h_ratio is None or t_ratio is None else h_ratio * h_ratio + t_ratio * t_ratio
    if index is None or not math.isfinite(index):
        lof["reason"] = "Dimension ratios exceed finite floating-point range; overlap index is unresolved."
        return result
    margin = 1.0 - index
    # Classification uses the reported index, without an empirical safety band.
    marginal = index == 1.0
    lof.update({
        "ellipseIndex": index, "signedMargin": margin,
        "status": "marginal" if marginal else ("lack-of-fusion-screened" if index > 1 else "covered-geometrically"),
        "riskScreened": None if marginal else index > 1,
        "reason": "Only the idealized elliptical overlap condition is evaluated.",
    })
    result["status"] = "geometry-screened"
    return result
