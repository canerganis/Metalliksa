"""
Phase 6b (vectorisation lane) golden cases: xrd_peak_deconvolution.
(The cnls_fitting_solver cases were removed with the electrochemistry modules.)

Merged into capture_phase6a_golden by one delimited block there. These goldens are
bound to BASE_REVISION below (faa6684, the code before the NumPy/SciPy rewrite), not
to the Phase 6a label d33b6f5, and live in python/golden/phase6b/ so the Phase 6a
bit-exact tests never iterate them. test_phase6b_vector_parity.py compares the
rewritten solvers against them with the tolerances stated there.

All observations are synthetic (generated below from closed-form models plus a
deterministic modulation / LCG pseudo-noise, no RNG); they are numerical fixtures,
not experimental data. Generated values are rounded to 9-10 significant digits so
the payload text does not depend on the last ulp of the platform libm.
"""

import cmath
import math
from typing import Any, Dict, List

BASE_REVISION = "faa6684"
GOLDEN_SUBDIR = "phase6b"
SOLVERS = ("xrd_peak_deconvolution",)


def _sig(value: float, digits: int = 10) -> float:
    return float(f"{value:.{digits}g}")


def _log_frequencies(f_max: float, f_min: float, per_decade: int) -> List[float]:
    decades = math.log10(f_max) - math.log10(f_min)
    count = int(round(decades * per_decade))
    return [_sig(10.0 ** (math.log10(f_max) - k / per_decade)) for k in range(count + 1)]


def _eis_points(z_of_omega, f_max: float, f_min: float, per_decade: int, modulation: float) -> List[Dict[str, float]]:
    points = []
    for i, f in enumerate(_log_frequencies(f_max, f_min, per_decade)):
        z = z_of_omega(2.0 * math.pi * f) * (1.0 + modulation * math.sin(1.7 * i))
        points.append({"frequency": f, "zReal": _sig(z.real), "zImag": _sig(z.imag),
                       "minusZImag": _sig(-z.imag)})
    return points


def _cpe(q: float, n: float, w: float) -> complex:
    return 1.0 / (q * w ** n * cmath.exp(1j * n * math.pi / 2.0))


def _par(a: complex, b: complex) -> complex:
    return a * b / (a + b)


def _randles(w: float) -> complex:  # Rs=10, Rct=100, Cdl=1e-5
    return 10.0 + _par(100.0, 1.0 / (1j * w * 1e-5))


def _randles_cpe(w: float) -> complex:  # Rs=8, Rct=250, Q=2e-5, n=0.85
    return 8.0 + _par(250.0, _cpe(2e-5, 0.85, w))


def _tlm_open(w: float) -> complex:  # Rs=2, Rion=65, Rct=250, Qdl=1.5e-4, alpha=0.9 (Bisquert open)
    zeta = _par(250.0, _cpe(1.5e-4, 0.9, w))
    gamma = cmath.sqrt(65.0 / zeta)
    return 2.0 + cmath.sqrt(65.0 * zeta) / cmath.tanh(gamma)


def _two_rc(w: float) -> complex:  # Rs=12, R1=80 || Q1(3e-6, 0.88), R2=400 || C2(2e-4)
    return 12.0 + _par(80.0, _cpe(3e-6, 0.88, w)) + _par(400.0, 1.0 / (1j * w * 2e-4))


def _param(name, element, value, lo, hi, field="value", unit="Ohm", ptype="Resistor"):
    return {"paramName": name, "elementId": element, "field": field, "value": value,
            "min": lo, "max": hi, "unit": unit, "paramType": ptype}


_RANDLES_POINTS = _eis_points(_randles, 1e5, 0.1, 8, 0.002)

_CUSTOM_TWO_RC = {"branches": [
    {"connection": "series", "elements": [{"id": "rs", "name": "Rs", "type": "R", "value": 15.0}]},
    {"connection": "parallel", "elements": [
        {"id": "r1", "name": "R1", "type": "R", "value": 60.0},
        {"id": "q1", "name": "Q1", "type": "CPE", "value": 5e-6, "exponent": 0.8}]},
    {"connection": "parallel", "elements": [
        {"id": "r2", "name": "R2", "type": "R", "value": 300.0},
        {"id": "c2", "name": "C2", "type": "C", "value": 1e-4}]},
]}

def _ka2(two_theta: float) -> float:
    d = 1.540598 / (2.0 * math.sin(math.radians(two_theta / 2.0)))
    return 2.0 * math.degrees(math.asin(min(1.0, 1.544426 / (2.0 * d))))


def _pv(x: float, c: float, i: float, w: float, eta: float) -> float:
    u = ((x - c) / (w / 2.0)) ** 2
    return i * (eta / (1.0 + u) + (1.0 - eta) * math.exp(-math.log(2.0) * u))


def _p7(x: float, c: float, i: float, w: float, m: float) -> float:
    return i / (1.0 + 4.0 * (2.0 ** (1.0 / m) - 1.0) * ((x - c) / w) ** 2) ** m


def _xrd_points(start: float, profile, center: float, intensity: float, fwhm: float, shape: float,
                bg0: float, bg1: float, ka2: bool = True, n: int = 131, seed: int = 12345) -> List[Dict[str, float]]:
    state = seed
    c2 = _ka2(center)
    points = []
    for k in range(n):
        tt = round(start + 0.02 * k, 2)
        y = bg0 + bg1 * (tt - start) + profile(tt, center, intensity, fwhm, shape)
        if ka2:
            y += profile(tt, c2, 0.5 * intensity, 1.03 * fwhm, shape)
        state = (1103515245 * state + 12345) % 2 ** 31
        y += (state / 2 ** 31 - 0.5) * 20.0  # +-10 counts deterministic pseudo-noise
        points.append({"twoTheta": tt, "sampleIntensity": round(y, 2)})
    return points


_XRD = {
    "pv_ka2_cu111": {
        "mode": "deconvolve", "profileType": "pseudo-voigt", "center": 43.3, "intensity": 3500, "fwhm": 0.25,
        "eta": 0.5, "enableKa2": True, "ka2Ratio": 0.5,
        "points": _xrd_points(42.0, _pv, 43.30, 4000.0, 0.20, 0.4, 210.0, 5.0),
    },
    "pv_ka2_cu200_offset_guess": {
        "mode": "deconvolve", "profileType": "pseudo-voigt", "center": 50.40, "intensity": 1500, "fwhm": 0.3,
        "eta": 0.3, "enableKa2": True, "ka2Ratio": 0.5,
        "points": _xrd_points(49.2, _pv, 50.43, 1900.0, 0.24, 0.55, 180.0, -3.0, seed=777),
    },
    "pearson7_ka2": {
        "mode": "deconvolve", "profileType": "pearson-vii", "center": 43.3, "intensity": 3500, "fwhm": 0.25,
        "pearsonM": 2.0, "enableKa2": True, "ka2Ratio": 0.5,
        "points": _xrd_points(42.0, _p7, 43.30, 4000.0, 0.20, 1.6, 200.0, 4.0, seed=4242),
    },
    "pv_single_no_ka2": {
        "mode": "deconvolve", "profileType": "pseudo-voigt", "center": 74.10, "intensity": 900, "fwhm": 0.35,
        "eta": 0.5, "enableKa2": False,
        "points": _xrd_points(73.0, _pv, 74.13, 1200.0, 0.30, 0.7, 150.0, 1.5, ka2=False, n=111, seed=99),
    },
    # Silent default today: no points -> the initial guesses are returned as the "fit".
    "edge_missing_points": {"mode": "deconvolve"},
}

CASES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "xrd_peak_deconvolution": _XRD,
}
