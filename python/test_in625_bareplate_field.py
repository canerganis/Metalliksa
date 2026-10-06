import math
from pathlib import Path

import numpy as np
import pytest

import in625_bareplate_field as field
from in625_thermal_material import (
    LIQUIDUS_K,
    REFERENCE_TEMPERATURE_K,
    SOLIDUS_K,
    in625_lpbf_thermal_at_kelvin,
    in625_lpbf_thermal_snapshot,
)


def _independent_h_gauss(temperature_k):
    """Independent numerical integral of Cp plus the mushy latent term."""
    snap = in625_lpbf_thermal_snapshot()
    a, b, c, d = snap["solidCpPolynomial_J_kgK"]
    nodes, weights = np.polynomial.legendre.leggauss(64)

    def integrate_cp(low, high):
        if high <= low:
            return 0.0
        t = (high + low) / 2 + (high - low) / 2 * nodes
        cp = a + b*t + c*t**2 + d*t**3
        return float((high-low)/2 * np.dot(weights, cp))

    ts, tl = snap["solidus_K"], snap["liquidus_K"]
    if temperature_k <= ts:
        return integrate_cp(REFERENCE_TEMPERATURE_K, temperature_k)
    cp_s = a + b*ts + c*ts**2 + d*ts**3
    width = tl-ts
    fraction = (temperature_k-ts)/width
    mushy_cp = lambda q: cp_s + (snap["liquidCp_J_kgK"]-cp_s)*(q-ts)/width
    q = (temperature_k+ts)/2 + (temperature_k-ts)/2*nodes
    return (integrate_cp(REFERENCE_TEMPERATURE_K, ts)
            + float((temperature_k-ts)/2*np.dot(weights, mushy_cp(q)))
            + snap["latentHeat_J_kg"]*fraction)


def _config(**changes):
    values = dict(shape_xyz=(12, 12, 4), cell_size_m=(0.00025, 0.00025, 0.00025),
                  initial_temperature_K=298.15, dt_s=1.0e-5, steps=4,
                  absorbed_power_W=30.0, spot_sigma_m=0.0003,
                  scan_start_x_m=0.0015, scan_y_m=0.0015,
                  scan_velocity_x_m_s=1.25)
    values.update(changes)
    return field.BareplateConfig(**values)


def _mushy_config():
    """Bounded synthetic witness that exercises, but does not validate, mushy H(T)."""
    return _config(shape_xyz=(8, 8, 2), initial_temperature_K=1500.0,
                   dt_s=1e-4, steps=33, absorbed_power_W=30.0, scan_start_x_m=0.001,
                   scan_y_m=0.001, scan_velocity_x_m_s=0.0)


def _refined_mushy_config():
    """Same physical domain and input, with twofold spatial refinement."""
    return _config(shape_xyz=(16, 16, 4), cell_size_m=(1.25e-4,)*3,
                   initial_temperature_K=1500.0, dt_s=2.5e-5, steps=132,
                   absorbed_power_W=30.0, scan_start_x_m=0.001,
                   scan_y_m=0.001, scan_velocity_x_m_s=0.0)


def _as_numpy(value):
    return value.detach().cpu().numpy() if hasattr(value, "detach") else np.asarray(value)


def _assert_mushy_field_energy(result, config, expected_mushy_cells):
    temperature = _as_numpy(result.temperature_K)
    enthalpy = _as_numpy(result.specific_enthalpy_J_kg)
    snap = in625_lpbf_thermal_snapshot()
    assert np.any(temperature > snap["solidus_K"])
    assert np.all(temperature < LIQUIDUS_K)
    assert int(np.count_nonzero(temperature > snap["solidus_K"])) == expected_mushy_cells

    independent_h = np.array([_independent_h_gauss(float(t)) for t in temperature.flat])
    independent_h = independent_h.reshape(temperature.shape)
    np.testing.assert_allclose(enthalpy, independent_h, rtol=2e-12, atol=2e-7)

    cell_mass = field.DENSITY_KG_M3 * math.prod(config.cell_size_m)
    initial_total = (math.prod(config.shape_xyz) * cell_mass
                     * _independent_h_gauss(config.initial_temperature_K))
    input_energy = config.absorbed_power_W * config.dt_s * config.steps
    independent_final = float(independent_h.sum() * cell_mass)
    assert abs(independent_final - initial_total - input_energy) / input_energy < 1e-9
    assert result.metadata["sourceCaptureFractionMinimum"] >= field.MINIMUM_SOURCE_CAPTURE_FRACTION
    assert result.metadata["materialRevisionSha256"] == field.MATERIAL_REVISION_SHA256
    assert result.metadata["validationStatus"] == "unvalidated-literature-model-screening"


def test_enthalpy_matches_independent_integral_and_bounded_inverse():
    for temperature in (REFERENCE_TEMPERATURE_K, 700.0, SOLIDUS_K,
                        SOLIDUS_K+15.0, SOLIDUS_K+45.0, LIQUIDUS_K):
        state = in625_lpbf_thermal_at_kelvin(temperature)
        expected = _independent_h_gauss(temperature)
        assert math.isclose(state["specificEnthalpy_J_kg"], expected,
                            rel_tol=2e-12, abs_tol=2e-7)
        recovered = field._temperature_from_enthalpy_numpy(
            np.asarray(state["specificEnthalpy_J_kg"]))
        assert float(recovered) == pytest.approx(temperature, abs=2e-10)


def test_cuda_inverse_checks_bounds_and_uses_unchecked_60_step_bisection():
    torch = pytest.importorskip("torch")
    target = torch.tensor([700.123456789], dtype=torch.float64)
    calls = []

    def identity_law(temperature, *, validate=True):
        calls.append(validate)
        return None, None, None, temperature

    recovered = field._temperature_from_enthalpy_torch(
        target, identity_law, torch.tensor(REFERENCE_TEMPERATURE_K, dtype=torch.float64),
        torch.tensor(LIQUIDUS_K, dtype=torch.float64), torch,
    )
    assert recovered.item() == pytest.approx(target.item(), abs=2e-13)
    assert calls == [False] * 60

    with pytest.raises(ValueError, match="enthalpy crosses bounded IN625"):
        field._temperature_from_enthalpy_torch(
            torch.tensor([LIQUIDUS_K + 1.0]), identity_law,
            torch.tensor(REFERENCE_TEMPERATURE_K, dtype=torch.float64),
            torch.tensor(LIQUIDUS_K, dtype=torch.float64), torch,
        )


def test_warp_cuda_inverse_matches_phase_boundary_temperatures():
    torch = pytest.importorskip("torch")
    wp = pytest.importorskip("warp")
    if not torch.cuda.is_available():
        pytest.skip("CUDA device is not available")
    wp.config.use_precompiled_headers = False
    wp.config.kernel_cache_dir = str(Path(__file__).resolve().parent / ".tmp-in625-warp-tests")

    expected = [REFERENCE_TEMPERATURE_K, SOLIDUS_K-1e-6, SOLIDUS_K,
                SOLIDUS_K+15.0, LIQUIDUS_K-1e-6, LIQUIDUS_K]
    enthalpy = [in625_lpbf_thermal_at_kelvin(value)["specificEnthalpy_J_kg"]
                for value in expected]
    h0 = in625_lpbf_thermal_at_kelvin(REFERENCE_TEMPERATURE_K)["specificEnthalpy_J_kg"]
    h1 = in625_lpbf_thermal_at_kelvin(LIQUIDUS_K)["specificEnthalpy_J_kg"]
    gpu_enthalpy = torch.tensor(enthalpy, dtype=torch.float64, device="cuda:0")
    recovered = field._temperature_from_enthalpy_warp(gpu_enthalpy, h0, h1, torch)
    torch.testing.assert_close(
        recovered.cpu(), torch.tensor(expected, dtype=torch.float64), rtol=0.0, atol=2e-10,
    )


def test_cpu_moving_surface_source_conserves_absorbed_energy_and_metadata():
    cfg = _config()
    result = field.run_cpu(cfg)
    expected = cfg.absorbed_power_W * cfg.dt_s * cfg.steps
    assert result.temperature_K.shape == (4, 12, 12)
    assert result.temperature_K.max() > cfg.initial_temperature_K
    assert np.max(np.abs(result.energy_residual_J)) < 2e-10
    assert result.total_enthalpy_J[-1] - result.total_enthalpy_J[0] == pytest.approx(
        expected * (cfg.steps - 1) / cfg.steps, abs=2e-10)
    assert result.metadata["absorbedPower_W"] == cfg.absorbed_power_W
    assert result.metadata["validationStatus"] == "unvalidated-literature-model-screening"
    assert result.metadata["densityBasis"] == field.DENSITY_BASIS
    assert result.metadata["sourceCaptureFractionMinimum"] >= field.MINIMUM_SOURCE_CAPTURE_FRACTION
    assert result.metadata["powderOrMeltPoolClaim"] is False
    assert result.metadata["materialRevisionSha256"] == in625_lpbf_thermal_snapshot()["materialRevisionSha256"]


def test_cpu_field_enters_mushy_range_and_matches_independent_enthalpy_energy_oracle():
    cfg = _mushy_config()
    result = field.run_cpu(cfg)
    _assert_mushy_field_energy(result, cfg, expected_mushy_cells=4)


def test_liquidus_crossing_rejects_without_clipping_or_superheat():
    cfg = _config(shape_xyz=(4, 4, 2), cell_size_m=(0.0005, 0.0005, 0.0005),
                  initial_temperature_K=LIQUIDUS_K-0.1, dt_s=1e-5,
                  steps=1, absorbed_power_W=1000.0, spot_sigma_m=0.0002,
                  scan_start_x_m=0.001, scan_y_m=0.001,
                  scan_velocity_x_m_s=0.0)
    with pytest.raises(ValueError, match="crosses bounded IN625|liquidus bound"):
        field.run_cpu(cfg)


def test_source_requires_resolvable_positive_grid_weight():
    cfg = _config(spot_sigma_m=1e-200)
    with pytest.raises(ValueError, match="unresolved"):
        field.run_cpu(cfg)


def test_truncated_gaussian_source_is_rejected_instead_of_rescaled():
    cfg = _config(scan_start_x_m=0.0)
    with pytest.raises(ValueError, match="source capture .* below"):
        field.run_cpu(cfg)


def test_cuda_request_is_explicit_and_never_falls_back():
    with pytest.raises(ValueError, match="explicit CUDA device"):
        field.run_cuda(_config(), device="cpu")


try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    torch = None
    CUDA_AVAILABLE = False


@pytest.mark.skipif(not CUDA_AVAILABLE, reason="CUDA device is not available")
def test_cuda_full_field_matches_cpu_and_device_is_explicit():
    cfg = _config()
    cpu = field.run_cpu(cfg)
    gpu = field.run_cuda(cfg, "cuda:0")
    assert gpu.metadata["device"] == "cuda:0"
    assert gpu.metadata["backend"] == "cuda:0"
    assert np.allclose(gpu.temperature_K.cpu().numpy(), cpu.temperature_K, rtol=0, atol=2e-10)
    assert np.allclose(gpu.specific_enthalpy_J_kg.cpu().numpy(), cpu.specific_enthalpy_J_kg,
                       rtol=0, atol=2e-7)
    assert np.allclose(gpu.total_enthalpy_J.cpu().numpy(), cpu.total_enthalpy_J,
                       rtol=0, atol=2e-10)
    assert np.allclose(gpu.energy_residual_J.cpu().numpy(), cpu.energy_residual_J,
                       rtol=0, atol=2e-10)
    assert np.allclose(gpu.peak_temperature_K.cpu().numpy(), cpu.peak_temperature_K,
                       rtol=0, atol=2e-10)
    assert gpu.metadata["materialRevisionSha256"] == cpu.metadata["materialRevisionSha256"]


@pytest.mark.skipif(not CUDA_AVAILABLE, reason="CUDA device is not available")
def test_cuda_mushy_field_matches_cpu_and_independent_oracles():
    cfg = _mushy_config()
    cpu = field.run_cpu(cfg)
    gpu = field.run_cuda(cfg, "cuda:0")
    _assert_mushy_field_energy(cpu, cfg, expected_mushy_cells=4)
    _assert_mushy_field_energy(gpu, cfg, expected_mushy_cells=4)
    assert gpu.metadata["device"] == "cuda:0"
    np.testing.assert_allclose(_as_numpy(gpu.temperature_K), cpu.temperature_K,
                               rtol=0, atol=2e-10)
    np.testing.assert_allclose(_as_numpy(gpu.specific_enthalpy_J_kg),
                               cpu.specific_enthalpy_J_kg, rtol=0, atol=2e-7)
    np.testing.assert_allclose(_as_numpy(gpu.energy_residual_J),
                               cpu.energy_residual_J, rtol=0, atol=2e-10)
    np.testing.assert_allclose(_as_numpy(gpu.peak_temperature_K),
                               cpu.peak_temperature_K, rtol=0, atol=2e-10)


@pytest.mark.skipif(not CUDA_AVAILABLE, reason="CUDA device is not available")
def test_cuda_refined_mushy_field_matches_cpu_and_independent_oracles():
    cfg = _refined_mushy_config()
    cpu = field.run_cpu(cfg)
    gpu = field.run_cuda(cfg, "cuda:0")
    _assert_mushy_field_energy(cpu, cfg, expected_mushy_cells=32)
    _assert_mushy_field_energy(gpu, cfg, expected_mushy_cells=32)
    assert gpu.metadata["device"] == "cuda:0"
    np.testing.assert_allclose(_as_numpy(gpu.temperature_K), cpu.temperature_K,
                               rtol=0, atol=2e-10)
    np.testing.assert_allclose(_as_numpy(gpu.specific_enthalpy_J_kg),
                               cpu.specific_enthalpy_J_kg, rtol=0, atol=2e-7)
    np.testing.assert_allclose(_as_numpy(gpu.energy_residual_J),
                               cpu.energy_residual_J, rtol=0, atol=2e-10)
    np.testing.assert_allclose(_as_numpy(gpu.peak_temperature_K),
                               cpu.peak_temperature_K, rtol=0, atol=2e-10)


@pytest.mark.skipif(not CUDA_AVAILABLE, reason="CUDA device is not available")
def test_cuda_rejects_liquidus_crossing_and_unavailable_device():
    cfg = _config(shape_xyz=(4, 4, 2), cell_size_m=(0.0005, 0.0005, 0.0005),
                  initial_temperature_K=LIQUIDUS_K-0.1, dt_s=1e-5,
                  steps=1, absorbed_power_W=1000.0, spot_sigma_m=0.0002,
                  scan_start_x_m=0.001, scan_y_m=0.001,
                  scan_velocity_x_m_s=0.0)
    with pytest.raises(ValueError, match="crosses bounded IN625|liquidus bound"):
        field.run_cuda(cfg, "cuda:0")
    if torch.cuda.device_count() < 2:
        with pytest.raises(ValueError, match="unavailable CUDA device"):
            field.run_cuda(_config(), "cuda:1")
