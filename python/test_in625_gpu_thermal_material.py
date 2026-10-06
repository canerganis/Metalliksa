import math

import numpy as np
import pytest

from in625_gpu_thermal_material import (
    in625_cpu_thermal_at_kelvin,
    in625_cuda_thermal_at_kelvin,
)
from in625_thermal_material import (
    LIQUIDUS_K,
    REFERENCE_TEMPERATURE_K,
    SOLIDUS_K,
    in625_lpbf_thermal_at_kelvin,
    in625_lpbf_thermal_snapshot,
)


def _independent_oracle(temperature_k):
    """Gauss-Legendre integration of the published piecewise Cp model."""
    a, b, c, d = (362.0, 0.125, 0.0001741, -7.527126e-8)
    k_a, k_b = (4.93, 0.01575)
    liquid_cp, liquid_k, latent = 700.0, 30.0, 290_000.0
    width = 60.0
    nodes, weights = np.polynomial.legendre.leggauss(64)

    def cp_solid(t):
        return a + b*t + c*t*t + d*t*t*t

    def integral(lo, hi):
        midpoint = (lo + hi) / 2.0
        half = (hi - lo) / 2.0
        return half * math.fsum(
            float(weight) * cp_solid(midpoint + half*float(node))
            for node, weight in zip(nodes, weights)
        )

    t = float(temperature_k)
    cp_at_solidus = cp_solid(SOLIDUS_K)
    k_at_solidus = k_a + k_b*SOLIDUS_K
    if t <= SOLIDUS_K:
        return {
            "cp": cp_solid(t),
            "k": k_a + k_b*t,
            "h": integral(REFERENCE_TEMPERATURE_K, t),
            "fraction": 0.0,
        }
    fraction = (t - SOLIDUS_K) / width
    melt_delta = t - SOLIDUS_K
    return {
        "cp": cp_at_solidus + (liquid_cp - cp_at_solidus)*fraction,
        "k": k_at_solidus + (liquid_k - k_at_solidus)*fraction,
        "h": (
            integral(REFERENCE_TEMPERATURE_K, SOLIDUS_K)
            + cp_at_solidus*melt_delta
            + (liquid_cp - cp_at_solidus)*melt_delta*melt_delta/(2.0*width)
            + latent*fraction
        ),
        "fraction": fraction,
    }


@pytest.mark.parametrize(
    "temperature_k",
    [REFERENCE_TEMPERATURE_K, 900.0, SOLIDUS_K - 1e-7,
     SOLIDUS_K, SOLIDUS_K + 1e-7, (SOLIDUS_K + LIQUIDUS_K)/2.0, LIQUIDUS_K],
)
def test_cpu_adapter_matches_production_and_independent_integral(temperature_k):
    actual = in625_cpu_thermal_at_kelvin(temperature_k)
    production = in625_lpbf_thermal_at_kelvin(temperature_k)
    oracle = _independent_oracle(temperature_k)

    assert actual["materialRevisionSha256"] == in625_lpbf_thermal_snapshot()["materialRevisionSha256"]
    assert actual["validationStatus"] == "unvalidated-literature-model-screening"
    assert actual["specificHeat_J_kgK"] == pytest.approx(production["specificHeat_J_kgK"], rel=1e-13)
    assert actual["thermalConductivity_W_mK"] == pytest.approx(production["thermalConductivity_W_mK"], rel=1e-13)
    assert actual["specificEnthalpy_J_kg"] == pytest.approx(production["specificEnthalpy_J_kg"], abs=2e-9)
    assert actual["specificHeat_J_kgK"] == pytest.approx(oracle["cp"], rel=1e-13)
    assert actual["thermalConductivity_W_mK"] == pytest.approx(oracle["k"], rel=1e-13)
    assert actual["specificEnthalpy_J_kg"] == pytest.approx(oracle["h"], abs=2e-8)
    assert actual["liquidFraction"] == pytest.approx(oracle["fraction"], abs=1e-15)


def test_cpu_adapter_supports_arrays_and_has_no_cuda_dependency():
    result = in625_cpu_thermal_at_kelvin(np.array([REFERENCE_TEMPERATURE_K, SOLIDUS_K, LIQUIDUS_K]))
    assert result["specificHeat_J_kgK"].shape == (3,)
    assert result["thermalConductivity_W_mK"].shape == (3,)
    assert result["specificEnthalpy_J_kg"].shape == (3,)
    assert result["specificEnthalpy_J_kg"][0] == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), REFERENCE_TEMPERATURE_K - 1e-6, LIQUIDUS_K + 1e-6])
def test_cpu_adapter_rejects_non_numeric_nonfinite_or_out_of_bounds(bad):
    with pytest.raises(ValueError):
        in625_cpu_thermal_at_kelvin(bad)


@pytest.mark.parametrize("temperature_k", [REFERENCE_TEMPERATURE_K, SOLIDUS_K - 1e-7,
                                               SOLIDUS_K, SOLIDUS_K + 1e-7,
                                               (SOLIDUS_K + LIQUIDUS_K)/2.0, LIQUIDUS_K])
def test_cuda0_adapter_matches_cpu_and_independent_oracle(temperature_k):
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
        pytest.skip("explicit cuda:0 parity requires an available CUDA device")

    actual = in625_cuda_thermal_at_kelvin([temperature_k], device="cuda:0")
    cpu = in625_cpu_thermal_at_kelvin([temperature_k])
    oracle = _independent_oracle(temperature_k)
    assert actual["temperature_K"].device == torch.device("cuda:0")
    assert actual["materialRevisionSha256"] == cpu["materialRevisionSha256"]
    assert actual["validationStatus"] == cpu["validationStatus"] == "unvalidated-literature-model-screening"
    assert actual["materialId"] == cpu["materialId"] == "in625"
    for key in ("specificHeat_J_kgK", "effectiveHeatCapacity_J_kgK",
                "thermalConductivity_W_mK", "specificEnthalpy_J_kg", "liquidFraction"):
        gpu_value = actual[key].item()
        cpu_key = key
        assert gpu_value == pytest.approx(float(cpu[cpu_key][0]), rel=2e-13, abs=3e-8)
    assert actual["specificHeat_J_kgK"].item() == pytest.approx(oracle["cp"], rel=1e-13)
    assert actual["thermalConductivity_W_mK"].item() == pytest.approx(oracle["k"], rel=1e-13)
    assert actual["specificEnthalpy_J_kg"].item() == pytest.approx(oracle["h"], abs=3e-8)


def test_cuda_adapter_requires_explicit_ordinal_and_refuses_extrapolation():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA validation requires an available CUDA device")
    with pytest.raises(ValueError, match="explicit device"):
        in625_cuda_thermal_at_kelvin(REFERENCE_TEMPERATURE_K, device="cuda")
    with pytest.raises(ValueError, match="outside"):
        in625_cuda_thermal_at_kelvin([LIQUIDUS_K + 1e-5], device="cuda:0")
    for invalid in ("1000", 1000.0 + 1.0j, [1000.0 + 1.0j]):
        with pytest.raises(ValueError, match="finite numeric Kelvin"):
            in625_cuda_thermal_at_kelvin(invalid, device="cuda:0")
