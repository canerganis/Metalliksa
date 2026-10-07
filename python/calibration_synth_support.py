"""Synthetic fixtures shared by the offline calibration tests (no dataset, no solver, no GPU).

Synthetic kernel: W(eta) = 400 sqrt(eta P / v) (d / 50)^0.3, D(eta) = 0.6 W sqrt(eta / 0.5), with a per-kernel
scale. Measured values are the kernel at a TRUE eta times a per-source log offset and noise. Not a physics model.
"""

from __future__ import annotations

import math
import random
from typing import Any, Callable, Dict, List, Optional

import numpy as np

import lpbf_calibration_stats as st

KERNEL_SCALE = {"eagar-tsai": 1.0, "goldak": 1.05, "rosenthal": 0.9}


def synth_geometry(eta: float, power_W: float, speed_mm_s: float, beam_um: float, scale: float = 1.0):
    w = scale * 400.0 * math.sqrt(eta * power_W / speed_mm_s) * (beam_um / 50.0) ** 0.3
    d = 0.6 * w * math.sqrt(eta / 0.5)
    return w, d


def synth_solver(default_eta_by_material: Dict[str, float]) -> Callable:
    """Injected into lpbf_calibration_fit.build_table: (args, kernel, eta|None) -> (W, D, status)."""
    def solver(args, kernel, eta):
        material, P, v, d = args[0], args[1], args[2], args[3]
        e = default_eta_by_material[material] if eta is None else eta
        w, dd = synth_geometry(e, P, v, d, KERNEL_SCALE[kernel])
        return w, dd, "computed"
    return solver


def synth_rows(source: str, material: str, n_sets: int, true_eta_w: float, true_eta_d: float, default_eta: float,
               offset_w: float = 0.0, offset_d: float = 0.0, noise: float = 0.04, seed: int = 0,
               catalog: bool = False, published: bool = False, balling_every: int = 0) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    seen = set()
    i = 0
    while len(seen) < n_sets:
        P = rng.choice([100.0, 150.0, 200.0, 250.0, 300.0, 350.0])
        v = rng.choice([400.0, 600.0, 800.0, 1000.0, 1200.0])
        d = rng.choice([50.0, 70.0, 90.0, 110.0])
        if (P, v, d) in seen:
            continue
        seen.add((P, v, d))
        for _ in range(1 + (len(seen) % 7 == 0)):  # a few replicates
            i += 1
            w = synth_geometry(true_eta_w, P, v, d)[0] * math.exp(offset_w + rng.gauss(0, noise))
            dd = synth_geometry(true_eta_d, P, v, d)[1] * math.exp(offset_d + rng.gauss(0, noise))
            h = 30.0 * default_eta * P / v * 8.0 / 0.42 * (50.0 / d) ** 1.5 / 5.0
            row = {"rowId": f"{source}-{i:03d}", "source": source, "material": material, "power_W": P,
                   "speed_mm_s": v, "beamDiameter_um": d, "preheat_C": 20.0, "layer_um": 30.0, "hatch_um": None,
                   "width_um": w, "depth_um": dd,
                   "balling": 1 if (balling_every and i % balling_every == 0) else 0,
                   "publishedLabel": None, "catalog": catalog, "defaultAbsorptivity": default_eta,
                   "normalizedEnthalpyDefault": h, "regimeClass": st.regime_class_from_enthalpy(h)}
            if published:
                row["publishedLabel"] = {"conduction": "conduction", "transition": "transition",
                                         "keyhole": "keyhole"}[row["regimeClass"]]
            rows.append(row)
    return rows


def synth_loads(ku_beam: float = 37.5, scale_sets: int = 1) -> Dict[str, Any]:
    """A small stand-in for lpbf_calibration_fit.load_rows(): the real source ids, synthetic numbers."""
    m316, mti, m625, m718 = "316L Stainless Steel", "Ti-6Al-4V", "Inconel 625", "Inconel 718"
    tr: List[Dict[str, Any]] = []
    tr += synth_rows("hofmann-316l-2026", m316, 30 * scale_sets, 0.50, 0.46, 0.42, 0.0, 0.0, seed=1, balling_every=9)
    tr += synth_rows("ku-leuven-316l-2021", m316, 24, 0.52, 0.47, 0.42, 0.05, -0.04, seed=2, published=True)
    tr += synth_rows("totis-ti64-2021", mti, 28 * scale_sets, 0.40, 0.38, 0.35, 0.0, 0.0, seed=3)
    tr += synth_rows("ku-leuven-ti64-2021", mti, 14, 0.30, 0.45, 0.35, -0.08, 0.10, seed=4, published=True)
    tr += synth_rows("lane-in625-2020", m625, 23, 0.45, 0.42, 0.38, 0.0, 0.0, seed=5)
    cat = []
    cat += synth_rows("guo-316l-2024", m316, 3, 0.5, 0.46, 0.42, seed=6, catalog=True)
    n01 = dict(cat[0])
    n01.update(rowId="guo-316l-n01", power_W=260.0, speed_mm_s=520.0, beamDiameter_um=100.0, width_um=114.0, depth_um=180.0)
    cat.append(n01)
    cat += synth_rows("nist-amb2022-03-in718", m718, 4, 0.45, 0.42, 0.38, seed=7, catalog=True)
    prov = {s: {"doi": "10.0000/synthetic", "tableSha256": "0" * 64, "license": "synthetic", "citation": "synthetic fixture",
                "loaderRows": sum(1 for r in tr + cat if r["source"] == s), "loaderExcluded": []}
            for s in {r["source"] for r in tr + cat}}
    return {"trainable": tr, "catalog": cat, "provenance": prov}


DEFAULT_ETA = {"316L Stainless Steel": 0.42, "Ti-6Al-4V": 0.35, "Inconel 625": 0.38, "Inconel 718": 0.38}


def small_cfg(base: Dict[str, Any]) -> Dict[str, Any]:
    """The production config with small bootstrap sizes and a single seed, for speed only."""
    import copy
    cfg = copy.deepcopy(base)
    cfg["bootstrap"]["paramReplicates"] = 30
    cfg["bootstrap"]["skillReplicates"] = 100
    cfg["p1"]["seeds"] = [0]
    cfg["rungSelection"]["innerSeeds"] = [0]
    return cfg


def build_fk(rows: List[Dict[str, Any]], kernel: str = "eagar-tsai", nodes: Optional[List[float]] = None,
             eta_fine: Optional[Any] = None, default_override: Optional[Callable] = None) -> st.FineKernel:
    """FineKernel straight from the synthetic kernel (bypasses the table)."""
    nodes = nodes or [round(0.2 + 0.025 * i, 4) for i in range(29)]
    from lpbf_calibration_config import CALIBRATION_CONFIG
    eta_fine = st.eta_fine_grid(CALIBRATION_CONFIG) if eta_fine is None else eta_fine
    scale = KERNEL_SCALE[kernel]
    lnW = np.array([[math.log(synth_geometry(e, r["power_W"], r["speed_mm_s"], r["beamDiameter_um"], scale)[0]) for e in nodes] for r in rows])
    lnD = np.array([[math.log(synth_geometry(e, r["power_W"], r["speed_mm_s"], r["beamDiameter_um"], scale)[1]) for e in nodes] for r in rows])
    dW = np.array([synth_geometry(r["defaultAbsorptivity"], r["power_W"], r["speed_mm_s"], r["beamDiameter_um"], scale)[0] for r in rows])
    dD = np.array([synth_geometry(r["defaultAbsorptivity"], r["power_W"], r["speed_mm_s"], r["beamDiameter_um"], scale)[1] for r in rows])
    return st.FineKernel(rows, nodes, lnW, lnD, np.ones_like(lnW, dtype=bool), dW, dD, np.ones(len(rows), dtype=bool), eta_fine)
