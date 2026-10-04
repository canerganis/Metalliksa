"""
test_phase8.py — Phase 8 Solidification Microstructure Coupling verification suite
====================================================================================
Tests the following components:
  1. Hunt-Lu PDAS and Kirkwood SDAS correlations (physical range).
  2. Hunt morphology criterion (G/R classification).
  3. Morphology fraction normalization (must sum to 1.0).
  4. compute_solidification_microstructure() without CFD data returns "unavailable"
     (moved to test_phase8_microstructure_contract.py, unittest).
  5. compute_solidification_microstructure() with mock CFD JSON (OpenFOAM path)
     (moved to test_phase8_microstructure_contract.py, unittest).
  6. lpbf_cfd.cfd_multiphysics() returns solidificationMicrostructure key.

Run with:
    pytest python/test_phase8.py -v
"""

import math
import pytest
import tempfile
from pathlib import Path

# ---- import Phase 8 module --------------------------------------------------
from lpbf_solidification_microstructure import (
    hunt_lu_pdas_um,
    kirkwood_sdas_um,
    hunt_morphology,
    morphology_fractions,
    compute_solidification_microstructure,
)


# ---------------------------------------------------------------------------
# Test 1 — Hunt-Lu PDAS physical range
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("G_Km,R_ms,expected_range", [
    (1e6,  0.05,  (0.1, 500.0)),   # Moderate gradient, moderate speed
    (1e7,  0.001, (0.1, 500.0)),   # High gradient, slow speed → coarse PDAS
    (5e5,  0.5,   (0.1, 500.0)),   # Low gradient, fast speed
    (1e9,  1.0,   (0.1, 500.0)),   # Near upper bound clamp
])
def test_pdas_physical_range(G_Km, R_ms, expected_range):
    pdas = hunt_lu_pdas_um(G_Km, R_ms)
    assert expected_range[0] <= pdas <= expected_range[1], \
        f"PDAS={pdas:.3f} µm outside [{expected_range[0]}, {expected_range[1]}] µm for G={G_Km:.1e}, R={R_ms}"


@pytest.mark.parametrize("G_Km,R_ms", [
    (1e5,  0.05),  # Low gradient: PDAS ~ 80/(316)*1.67 ≈ 0.42 µm, monotonically testable
    (1e6,  0.1),   # Moderate gradient, avoid clamp floor
])
def test_pdas_monotonic_in_G(G_Km, R_ms):
    """PDAS decreases as G increases (finer microstructure at higher gradient)."""
    pdas_lo = hunt_lu_pdas_um(G_Km * 0.5, R_ms)
    pdas_hi = hunt_lu_pdas_um(G_Km * 2.0, R_ms)
    assert pdas_hi < pdas_lo, "PDAS must decrease with increasing thermal gradient G"


# ---------------------------------------------------------------------------
# Test 2 — Kirkwood SDAS physical range
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cooling_K_s", [100.0, 1e4, 1e6, 1e8])
def test_sdas_physical_range(cooling_K_s):
    sdas = kirkwood_sdas_um(cooling_K_s)
    assert 0.05 <= sdas <= 200.0, \
        f"SDAS={sdas:.3f} µm outside [0.05, 200] µm for Ṫ={cooling_K_s:.1e} K/s"


def test_sdas_monotonic_in_cooling_rate():
    """SDAS decreases with increasing cooling rate (faster → finer)."""
    sdas_slow = kirkwood_sdas_um(1e4)
    sdas_fast = kirkwood_sdas_um(1e6)
    assert sdas_fast < sdas_slow, "SDAS must decrease with increasing cooling rate"


# ---------------------------------------------------------------------------
# Test 3 — Hunt morphology criterion
# ---------------------------------------------------------------------------

def test_morphology_columnar():
    """G/R > 1e8 → columnar."""
    G, R = 1.0e9, 0.05   # G/R = 2e10 >> 1e8
    morph = hunt_morphology(G, R)
    assert morph == "columnar", f"Expected columnar, got {morph}"


def test_morphology_equiaxed():
    """G/R < 1e6 → equiaxed."""
    G, R = 1.0e4, 0.5    # G/R = 2e4 << 1e6
    morph = hunt_morphology(G, R)
    assert morph == "equiaxed", f"Expected equiaxed, got {morph}"


def test_morphology_mixed():
    """G/R between 1e6 and 1e8 → mixed."""
    G, R = 1.0e6, 0.02   # G/R = 5e7 (in between)
    morph = hunt_morphology(G, R)
    assert morph == "mixed", f"Expected mixed, got {morph}"


# ---------------------------------------------------------------------------
# Test 4 — Morphology fractions sum to 1.0
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("G_Km,R_ms", [
    (1e9, 0.01),   # pure columnar
    (1e4, 1.0),    # pure equiaxed
    (5e6, 0.1),    # mixed zone
])
def test_morphology_fractions_sum_to_unity(G_Km, R_ms):
    fracs = morphology_fractions(G_Km, R_ms)
    total = fracs["columnar"] + fracs["equiaxed"] + fracs["mixed"]
    assert abs(total - 1.0) < 0.01, \
        f"Morphology fractions sum {total:.4f} ≠ 1.0 for G={G_Km:.1e}, R={R_ms}"


# Tests 5 and 6 (compute_solidification_microstructure without CFD data -> "unavailable"; OpenFOAM CFD path)
# live in test_phase8_microstructure_contract.py (unittest, runs without pytest).

# ---------------------------------------------------------------------------
# Test 7 — cfd_multiphysics returns solidificationMicrostructure key
# ---------------------------------------------------------------------------

def test_cfd_multiphysics_solidification_key():
    """cfd_multiphysics() must return a solidificationMicrostructure key (may be {})."""
    try:
        from lpbf_cfd import cfd_multiphysics
    except ImportError:
        pytest.skip("lpbf_cfd not importable in this environment")

    p = {
        "power_W": 300.0,
        "speed_mm_s": 800.0,
        "beamDiameter_um": 80,
        "tracks": 1,
        "trackLength_um": 50,
        "hatch_um": 50,
        "layers": 1,
        "layer_um": 30,
        "preheat_C": 20,
        "scanAngle_deg": 0.0,
        "layerRotation_deg": 67.0,
        "strategy": "unidirectional",
        "stripeWidth_um": 10000,
        "islandSize_um": 5000,
        "dwell_s": 0.0,
        "cooling_s": 0.0,
        "mesh_um": 20,
        "maxDt_s": 5e-8,
    }
    m = {
        "solidus_K": 1650,
        "liquidus_K": 1700,
        "boiling_K": 3560,
        "absorptivity": 0.4
    }

    with tempfile.TemporaryDirectory() as tmp:
        result = cfd_multiphysics(p, m, artifact_dir=tmp)

    # The key must exist (value may be {} if WSL/OpenFOAM unavailable)
    assert "solidificationMicrostructure" in result, \
        "cfd_multiphysics() must return 'solidificationMicrostructure' key"
    assert isinstance(result["solidificationMicrostructure"], dict)
