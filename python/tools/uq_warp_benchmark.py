#!/usr/bin/env python3
"""
Stochastic UQ (python/stochastic_uq_mmpds_solver.py) phase profile and NVIDIA Warp
go/no-go measurement. Not run in CI; prints real numbers for the machine it runs on.

Decision rule (written before any Warp code was built, 2026-10-06):
  A Warp backend (GPU or CPU Warp) for the UQ engine is justified only if BOTH hold
    1. the per-realisation strength model (solve_realizations_vec) dominates the wall time of
       a full solve at the sample counts users can actually request (the solver clamps
       mcSamples to [500, 10000]; the UQ Lab offers 1,000 / 2,500 / 5,000 / 10,000 runs), and
    2. a Warp kernel of that model is at least 3x faster than the NumPy kernel end-to-end
       (host->device upload, launch, synchronise, device->host download; module compile
       excluded but reported) at one of those sample counts, with outputs equal to the NumPy
       path within 1e-12 relative (the same tolerance test_stochastic_uq_vectorized_parity
       uses between the scalar and vector kernels).
  Otherwise no Warp path is added to the product.

Measurements:
  A. full solve_stochastic_uq at the user-reachable sizes: wall time (median of --repeat) and a
     cProfile breakdown by phase (Sobol generation, centred L2 discrepancy, quantile
     transforms, model kernel, descriptive statistics, Saltelli sensitivity, JSON encoding of
     the result as the app's IPC path does).
  B. isolated kernel scaling at 1e3 .. 1e6 draws: Sobol generation, quantile transforms, the
     NumPy model kernel and, when Warp imports, the same model as a float64 Warp kernel on
     cuda:0 and on the Warp CPU device (end-to-end and launch-only), plus the max relative
     difference of all 12 outputs between Warp and NumPy. 1e5 and 1e6 are above the product
     cap and show only where a GPU would start to pay off.

The Warp kernel here is a measurement instrument, not a product backend; it is not imported by
the solver.

Usage (from python/):  python -B tools/uq_warp_benchmark.py [--repeat 5] [--sizes 1000,10000,100000,1000000]
                                                           [--warp auto|off] [--json out.json]
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import math
import os
import platform
import pstats
import statistics
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import alloy_data_kinetics_uq_fatigue as _uq_data  # noqa: E402
import stochastic_uq_mmpds_solver as solver  # noqa: E402

try:
    import warp as wp  # type: ignore
except Exception:  # ImportError or a broken install: the NumPy-only measurement still runs
    wp = None

USER_SIZES = (1000, 2500, 5000, 10000)
PROFILE_PHASES = (
    ("sobol", "generate_array"),
    ("discrepancy", "compute_centered_l2_discrepancy"),
    ("quantile", "norm_ppf_array"),
    ("model", "solve_realizations_vec"),
    ("stats", "calc_stats"),
    ("saltelli", "eval_factor_matrix"),
)


def _median_time(fn, repeat):
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


def _draws(n, seed=42):
    """Physical draws for n realisations, built the way solve_stochastic_uq builds them."""
    nominal = _uq_data.uq_default_composition_wt()
    tol = _uq_data.uq_default_composition_tolerances()
    elements = list(nominal)
    e_dim = len(elements)
    pts = solver.SobolSequenceGenerator(dimension=e_dim + 5, scramble=True, seed=seed).generate_array(n)
    comp = {}
    for idx, el in enumerate(elements):
        comp[el] = solver._pmax(0.0, nominal[el] + solver.norm_ppf_array(pts[:, idx]) * (tol.get(el, nominal[el] * .1) / 3.0))
    sigma_log = math.sqrt(math.log(1.0 + .25 ** 2))
    mu_log = math.log(150000.0) - .5 * sigma_log ** 2
    cr = np.exp(mu_log + sigma_log * solver.norm_ppf_array(pts[:, e_dim]))
    t_age = solver._pmax(200.0, 720.0 + solver.norm_ppf_array(pts[:, e_dim + 1]) * 7.5)
    time_age = solver._pmax(.2, 8.0 + solver.norm_ppf_array(pts[:, e_dim + 2]) * .25)
    stress = solver._pmax(50.0, 720.0 + solver.norm_ppf_array(pts[:, e_dim + 3]) * (720.0 * .08))
    flaw = solver._pmax(5.0, 45.0 + solver.norm_ppf_array(pts[:, e_dim + 4]) * 15.0)
    return pts, comp, cr, t_age, time_age, stress, flaw


def _quantile_transform(pts):
    for col in range(pts.shape[1]):
        solver.norm_ppf_array(pts[:, col])


# --------------------------------------------------------------------------------------
# Warp float64 kernel of solve_realizations_vec (measurement instrument only)
# --------------------------------------------------------------------------------------
OUTPUT_KEYS = ("yield_MPa", "uts_MPa", "elongation_pct", "k1c_MPa_m", "critical_flaw_ac_mm",
               "margin_yield_MPa", "margin_flaw_mm", "delta_sigma_ss", "delta_sigma_hp",
               "delta_sigma_ppt", "grain_size_um", "applied_stress")

if wp is not None:
    f64 = wp.float64

    @wp.func
    def _pmax64(a: wp.float64, b: wp.float64) -> wp.float64:
        # Python max(a, b): b only if b > a
        if b > a:
            return b
        return a

    @wp.func
    def _pmin64(a: wp.float64, b: wp.float64) -> wp.float64:
        if b < a:
            return b
        return a

    @wp.kernel
    def uq_model_kernel(comp: wp.array2d(dtype=wp.float64),
                        potency: wp.array(dtype=wp.float64),
                        key_idx: wp.array(dtype=wp.int32),
                        cr_in: wp.array(dtype=wp.float64),
                        temp_in: wp.array(dtype=wp.float64),
                        time_in: wp.array(dtype=wp.float64),
                        stress_in: wp.array(dtype=wp.float64),
                        flaw_in: wp.array(dtype=wp.float64),
                        consts: wp.array(dtype=wp.float64),
                        out: wp.array2d(dtype=wp.float64)):
        i = wp.tid()
        b_nm = consts[0]
        taylor_M = consts[1]
        sigma_0 = consts[2]
        k_hp = consts[3]
        nu = consts[4]
        G_c = consts[5]
        G_GPa = consts[6]
        E_GPa = consts[7]
        Q_diff = consts[8]
        R_gas = consts[9]
        zero_c = consts[10]
        pi = consts[11]

        n_el = comp.shape[1]
        ss = wp.float64(0.0)
        for e in range(n_el):
            w = _pmax64(wp.float64(0.0), comp[i, e])
            ss = ss + potency[e] * wp.pow(w, wp.float64(0.67))

        cr_eff = _pmax64(wp.float64(0.1), cr_in[i])
        d_grain = _pmax64(wp.float64(0.5), wp.float64(45.0) * wp.pow(cr_eff, wp.float64(-0.32)))
        hp = k_hp / wp.sqrt(d_grain)

        rho = _pmax64(wp.float64(1e12), wp.float64(1e13) * wp.pow(cr_eff, wp.float64(0.22)))
        disloc = taylor_M * wp.float64(0.35) * (G_GPa * wp.float64(1000.0)) * (b_nm * wp.float64(1e-3)) * wp.sqrt(rho) * wp.float64(1e-6)

        T_K = temp_in[i] + zero_c
        arrh = wp.exp(-_pmin64(wp.float64(45.0), Q_diff / (R_gas * _pmax64(wp.float64(300.0), T_K))))
        r_nm = _pmax64(wp.float64(0.8), wp.float64(18.0) * wp.pow(arrh * wp.float64(1e8) * _pmax64(wp.float64(0.1), time_in[i]), wp.float64(0.333)))

        f_pct = wp.float64(0.0)
        if key_idx[0] >= 0:
            f_pct = f_pct + comp[i, key_idx[0]] * wp.float64(2.2)
        if key_idx[1] >= 0:
            f_pct = f_pct + comp[i, key_idx[1]] * wp.float64(3.5)
        if key_idx[2] >= 0:
            f_pct = f_pct + comp[i, key_idx[2]] * wp.float64(4.0)
        if key_idx[3] >= 0:
            f_pct = f_pct + comp[i, key_idx[3]] * wp.float64(3.0)
        f_pct = _pmin64(wp.float64(28.0), f_pct)
        f_vol = _pmax64(wp.float64(0.005), f_pct / wp.float64(100.0))
        lam = _pmax64(wp.float64(2.0), (wp.sqrt(pi / _pmax64(wp.float64(0.001), f_vol)) - wp.float64(2.0)) * r_nm)

        shear = (taylor_M * (G_GPa * wp.float64(1000.0)) * (b_nm / wp.float64(1.0))) * wp.sqrt(_pmax64(wp.float64(0.001), f_vol * r_nm / wp.float64(1.5))) * wp.float64(0.12)
        orowan = (taylor_M * wp.float64(0.8) * (G_GPa * wp.float64(1000.0)) * b_nm) / _pmax64(wp.float64(5.0), lam) * wp.log(_pmax64(wp.float64(2.0), wp.float64(2.0) * r_nm / b_nm)) * wp.float64(0.18)
        ppt = _pmin64(shear, orowan)

        q = wp.float64(1.4)
        coupled = wp.pow(wp.pow(disloc, q) + wp.pow(ppt, q), wp.float64(1.0) / q)
        sy = sigma_0 + ss + hp + coupled

        n_wh = _pmax64(wp.float64(0.05), _pmin64(wp.float64(0.35), wp.float64(0.42) - wp.float64(0.00022) * sy))
        uts = sy * (wp.float64(1.0) + wp.float64(2.15) * n_wh)
        elong = _pmax64(wp.float64(3.0), _pmin64(wp.float64(50.0), wp.float64(3200.0) / wp.pow(sy, wp.float64(0.82)) * (wp.float64(1.0) + wp.float64(1.5) * n_wh)))

        k1c_base = wp.sqrt((E_GPa * G_c) / _pmax64(wp.float64(0.1), (wp.float64(1.0) - nu * nu)))
        k1c = _pmax64(wp.float64(18.0), _pmin64(wp.float64(160.0), k1c_base * (wp.float64(1.0) + wp.float64(0.025) * elong) * wp.pow(wp.float64(900.0) / _pmax64(wp.float64(300.0), sy), wp.float64(0.35))))

        applied = _pmax64(wp.float64(50.0), stress_in[i])
        ratio = k1c / (wp.float64(1.12) * applied)
        flaw_ac = (wp.float64(1.0) / pi) * (ratio * ratio) * wp.float64(1000.0)
        flaw_ac = _pmax64(wp.float64(0.05), _pmin64(wp.float64(250.0), flaw_ac))

        out[i, 0] = sy
        out[i, 1] = uts
        out[i, 2] = elong
        out[i, 3] = k1c
        out[i, 4] = flaw_ac
        out[i, 5] = sy - applied * wp.float64(1.5)
        out[i, 6] = flaw_ac - (flaw_in[i] / wp.float64(1000.0))
        out[i, 7] = ss
        out[i, 8] = hp
        out[i, 9] = ppt
        out[i, 10] = d_grain
        out[i, 11] = applied


def _warp_inputs(base_metal, comp, cr, temp, time_h, stress, flaw):
    lattice = _uq_data.uq_lattice_constants(base_metal)
    C11, C12, C44 = lattice["C11"], lattice["C12"], lattice["C44"]
    bulk_B = (C11 + 2.0 * C12) / 3.0
    G_Voigt = (C11 - C12 + 3.0 * C44) / 5.0
    G_Reuss = 5.0 * (C11 - C12) * C44 / max(1.0, (4.0 * C44 + 3.0 * (C11 - C12)))
    G_GPa = (G_Voigt + G_Reuss) / 2.0
    E_GPa = (9.0 * bulk_B * G_GPa) / max(1.0, (3.0 * bulk_B + G_GPa))
    elements = list(comp)
    n = len(cr)
    comp_mat = np.stack([np.broadcast_to(np.asarray(comp[e], dtype=np.float64), (n,)) for e in elements], axis=1) \
        if elements else np.zeros((n, 0))
    potency = np.array([_uq_data.UQ_SOLUTE_POTENCY.get(e, _uq_data.UQ_DEFAULT_SOLUTE_POTENCY) for e in elements], dtype=np.float64)
    key_idx = np.array([elements.index(k) if k in elements else -1 for k in ("Nb", "Ti", "Al", "Mg")], dtype=np.int32)
    consts = np.array([lattice["b_nm"], lattice["taylor_M"], lattice["sigma_0"], lattice["k_hp"], lattice["nu"],
                       lattice["G_c_kJ_m2"], G_GPa, E_GPa, _uq_data.UQ_PRECIPITATION_Q_J_MOL, solver.R_GAS,
                       solver.ZERO_C_K, math.pi], dtype=np.float64)
    return np.ascontiguousarray(comp_mat), potency, key_idx, consts


def _warp_run(device, host, n, repeat):
    """End-to-end (upload + launch + sync + download) and launch-only medians, plus outputs."""
    comp_mat, potency, key_idx, consts, cr, temp, time_h, stress, flaw = host

    def upload():
        return [wp.array(a, dtype=wp.float64 if a.dtype == np.float64 else wp.int32, device=device)
                for a in (comp_mat, potency, key_idx, cr, temp, time_h, stress, flaw, consts)]

    def run_e2e():
        arrs = upload()
        out = wp.zeros((n, 12), dtype=wp.float64, device=device)
        wp.launch(uq_model_kernel, dim=n, inputs=arrs + [out], device=device)
        wp.synchronize_device(device)
        return out.numpy()

    t0 = time.perf_counter()
    result = run_e2e()  # first call: module load / compile for this device
    first = time.perf_counter() - t0
    e2e = _median_time(run_e2e, repeat)

    arrs = upload()
    out = wp.zeros((n, 12), dtype=wp.float64, device=device)

    def launch_only():
        wp.launch(uq_model_kernel, dim=n, inputs=arrs + [out], device=device)
        wp.synchronize_device(device)

    launch = _median_time(launch_only, repeat)
    return {"firstCall_s": first, "endToEnd_s": e2e, "launchOnly_s": launch}, result


def _max_rel_diff(numpy_res, warp_out):
    worst = 0.0
    for k, key in enumerate(OUTPUT_KEYS):
        a = np.broadcast_to(np.asarray(numpy_res[key], dtype=np.float64), warp_out.shape[:1])
        b = warp_out[:, k]
        denom = np.maximum(np.abs(a), 1e-300)
        worst = max(worst, float(np.max(np.abs(a - b) / denom)))
    return worst


def profile_full_solve(sizes, repeat):
    rows = []
    for n in sizes:
        params = {"mcSamples": n}
        wall = _median_time(lambda: solver.solve_stochastic_uq(dict(params)), repeat)
        result = solver.solve_stochastic_uq(dict(params))
        json_s = _median_time(lambda: json.dumps(result), repeat)
        prof = cProfile.Profile()
        prof.enable()
        solver.solve_stochastic_uq(dict(params))
        prof.disable()
        stats = pstats.Stats(prof, stream=io.StringIO())
        phase = {}
        model_all = 0.0
        for label, fname in PROFILE_PHASES:
            # cumulative time of calls made directly from solve_stochastic_uq (so the quantile and
            # model calls made inside eval_factor_matrix are counted under 'saltelli', not twice)
            cum = 0.0
            for (_file, _line, name), (_cc, _nc, _tt, ct, callers) in stats.stats.items():
                if name != fname:
                    continue
                if fname == "solve_realizations_vec":
                    model_all += ct
                for (_cf, _cl, cname), cstats in callers.items():
                    if cname == "solve_stochastic_uq":
                        cum += cstats[3]
            phase[label] = cum
        total_prof = sum(ct for (_f, _l, name), (_cc, _nc, _tt, ct, _c) in stats.stats.items() if name == "solve_stochastic_uq")
        rows.append({"N": n, "wall_s": wall, "json_s": json_s, "profiledTotal_s": total_prof,
                     "modelAllCalls_s": model_all, "phases": phase})
    return rows


def kernel_scaling(sizes, repeat, use_warp):
    rows = []
    devices = []
    if use_warp and wp is not None:
        wp.init()
        devices = ["cpu"] + (["cuda:0"] if wp.is_cuda_available() else [])
    for n in sizes:
        row = {"N": n}
        e_dim = len(_uq_data.uq_default_composition_wt())
        gen = solver.SobolSequenceGenerator(dimension=e_dim + 5, scramble=True, seed=42)
        row["sobol_s"] = _median_time(lambda: solver.SobolSequenceGenerator(dimension=e_dim + 5, scramble=True, seed=42).generate_array(n), repeat)
        pts, comp, cr, t_age, time_age, stress, flaw = _draws(n)
        row["quantile_s"] = _median_time(lambda: _quantile_transform(pts), repeat)
        row["numpyModel_s"] = _median_time(lambda: solver.solve_realizations_vec("Ni", comp, cr, t_age, time_age, stress, flaw), repeat)
        numpy_res = solver.solve_realizations_vec("Ni", comp, cr, t_age, time_age, stress, flaw)
        row["warp"] = {}
        if devices:
            comp_mat, potency, key_idx, consts = _warp_inputs("Ni", comp, cr, t_age, time_age, stress, flaw)
            host = (comp_mat, potency, key_idx, consts, cr, t_age, time_age, stress, flaw)
            for dev in devices:
                timing, out = _warp_run(dev, host, n, repeat)
                timing["maxRelDiffVsNumpy"] = _max_rel_diff(numpy_res, out)
                timing["speedupEndToEnd"] = row["numpyModel_s"] / timing["endToEnd_s"]
                timing["speedupLaunchOnly"] = row["numpyModel_s"] / timing["launchOnly_s"]
                row["warp"][dev] = timing
        rows.append(row)
    return rows, devices


def _fmt(s):
    return f"{s * 1000.0:9.3f} ms"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--sizes", default="1000,10000,100000,1000000")
    ap.add_argument("--warp", choices=("auto", "off"), default="auto")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    sizes = [int(s) for s in args.sizes.split(",") if s]

    print(f"machine: {platform.node()} {platform.machine()} {platform.processor()}")
    print(f"python {platform.python_version()}  numpy {np.__version__}  warp {getattr(wp, '__version__', 'not importable')}")
    print(f"repeat (median of): {args.repeat}\n")

    print("A. full solve_stochastic_uq at user-reachable sample counts (solver clamps mcSamples to [500, 10000])")
    print("   phases = cProfile cumulative time of one profiled run for calls made directly by solve_stochastic_uq;")
    print("   'model' is the main-population solve_realizations_vec call, 'saltelli' = eval_factor_matrix incl. its")
    print("   own quantile/model calls, 'other' = remainder (bookkeeping, sums, sorting of the sensitivity rows).")
    print("   wall and json.dumps are unprofiled medians.")
    full = profile_full_solve(USER_SIZES, args.repeat)
    hdr = f"{'N':>6} {'wall':>12} {'json.dumps':>12} | " + " ".join(f"{p[0]:>12}" for p in PROFILE_PHASES) + f" {'other':>12}"
    print(hdr)
    for r in full:
        other = r["profiledTotal_s"] - sum(r["phases"].values())
        line = f"{r['N']:>6} {_fmt(r['wall_s'])} {_fmt(r['json_s'])} | " + " ".join(_fmt(r["phases"][p[0]]) for p in PROFILE_PHASES)
        print(line + f" {_fmt(max(0.0, other))}")
    for r in full:
        share_main = r["phases"]["model"] / r["profiledTotal_s"] * 100.0 if r["profiledTotal_s"] else float("nan")
        share_all = r["modelAllCalls_s"] / r["profiledTotal_s"] * 100.0 if r["profiledTotal_s"] else float("nan")
        print(f"   N={r['N']:>5}: model kernel share of the profiled solve = {share_main:5.1f} % (main population)"
              f" / {share_all:5.1f} % (all calls incl. Saltelli)")

    print("\nB. isolated kernel scaling (13-dim default IN718 case; model = solve_realizations_vec, 12 outputs)")
    rows, devices = kernel_scaling(sizes, args.repeat, args.warp == "auto")
    print(f"   warp devices measured: {devices if devices else 'none (warp not importable or --warp off)'}")
    print(f"{'N':>8} {'sobol':>12} {'quantile':>12} {'numpy model':>12} | per device: first call | end-to-end | launch-only | speedup e2e | speedup launch | max rel diff")
    for r in rows:
        line = f"{r['N']:>8} {_fmt(r['sobol_s'])} {_fmt(r['quantile_s'])} {_fmt(r['numpyModel_s'])} |"
        for dev, t in r["warp"].items():
            line += (f" {dev}: {_fmt(t['firstCall_s'])} | {_fmt(t['endToEnd_s'])} | {_fmt(t['launchOnly_s'])} |"
                     f" {t['speedupEndToEnd']:6.2f}x | {t['speedupLaunchOnly']:6.2f}x | {t['maxRelDiffVsNumpy']:.2e} ;")
        print(line)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"machine": platform.node(), "python": platform.python_version(), "numpy": np.__version__,
                       "warp": getattr(wp, "__version__", None), "repeat": args.repeat,
                       "fullSolve": full, "kernelScaling": rows, "warpDevices": devices}, fh, indent=2)
        print(f"\nwritten {args.json}")


if __name__ == "__main__":
    main()
