#!/usr/bin/env python3
"""Report over docs/research/fv_evap_results.json by the pre-declared rule (PREDECLARED_fv_evap.md §3).

usage: python -B lpbf_depth_research/report.py docs/research/fv_evap_results.json > tables.md
Prints: completion per source x band per arm, per-source W/D bias/MAPE of every arm (operator env-mid
primary, peak and env-full beside it) against the three analytic kernels on the identical rows, the
equal-source-weight pooled numbers, the gate verdict with numbers, the NIST bound, Cunningham cavity vs vapour
depth, mesh convergence (20/10/5 um), energy balance and runtime."""
from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

PHI = 0.6  # kernel powder datum assumption of the earlier reports (D_kernel - PHI * t)
BANDS = ("cond<15", "15-20", "20-30", ">=30")
KERNELS = ("eagar-tsai", "goldak", "rosenthal")
SOURCES = [("hofmann bare", lambda r: r["dataset"].startswith("hofmann") and r["t_um"] == 0.0),
           ("hofmann 30um", lambda r: r["dataset"].startswith("hofmann") and r["t_um"] == 30.0),
           ("hofmann 60um", lambda r: r["dataset"].startswith("hofmann") and r["t_um"] == 60.0),
           ("totis 25um", lambda r: r["dataset"].startswith("totis")),
           ("ku 316L", lambda r: r["dataset"] == "ku-leuven-316l-2021"),
           ("ku Ti64", lambda r: r["dataset"] == "ku-leuven-ti64-2021"),
           ("lane IN625", lambda r: r["dataset"] == "lane-in625-2020"),
           ("ghosh IN625", lambda r: r["dataset"] == "ghosh-in625-2018"),
           ("trapp 316L", lambda r: r["dataset"] == "trapp-316l-2017"),
           ("nist IN718", lambda r: r["dataset"] == "nist-amb2022-03")]


def load(path):
    d = json.loads(Path(path).read_text("utf-8"))
    rows = d["rows"]
    res = {}
    for x in d["results"]:
        res[(x["rowId"], x["arm"], x["mesh_um"], x["track_um"])] = x
    return d, rows, res


def fv_wd(x, op):
    """(W, D_plate) of a completed result for an operator; None when not usable."""
    if not x or x["status"] != "completed":
        return None, None
    o = x["operators"]
    if op == "env-mid":
        e = o["envMid"]
        return (e["width_um"] or None), (e["depthPlate_um"] if e["reachesPlate"] else None)
    if op == "env-full":
        e = o["envFull"]
        return (e["width_um"] or None), (e["depthPlate_um"] if e["reachesPlate"] else None)
    e = o["peak"]
    return (e["width_um"] or None), (e["depthPlate_um"] if e["reachesPlate"] else None)


def kernel_wd(r, k):
    p = (r.get("kernels") or {}).get(k)
    if not p or p.get("status") != "computed":
        return None, None
    return p["W"], p["D"] - PHI * r["t_um"]


def stats(pairs):
    pairs = [(p, m) for p, m in pairs if p is not None and m]
    if not pairs:
        return None
    rel = [(p - m) / m for p, m in pairs]
    return dict(n=len(pairs), bias=100 * st.mean(rel), mape=100 * st.mean(abs(v) for v in rel))


def fmt(s):
    return "-" if s is None else f"{s['bias']:+.0f}/{s['mape']:.0f}"


def main():
    d, rows, res = load(sys.argv[1])
    arms = list(d["arms"])
    main_rows = [r for r in rows if r["depth_um"] is not None]
    out = []
    P = out.append
    P(f"results file: {sys.argv[1]}; started {d.get('startedAt')} finished {d.get('finishedAt', 'UNFINISHED')}; "
      f"{len(d['results'])} finished tasks")
    P("\n### Completion per source x band (20 um, track 600): completed / boiling-stop / other per arm")
    P("| source | band | n | " + " | ".join(arms) + " |")
    P("|---" * (len(arms) + 3) + "|")
    for name, sel in SOURCES:
        for b in BANDS:
            rs = [r for r in main_rows if sel(r) and r["band"] == b]
            if not rs:
                continue
            cells = []
            for a in arms:
                xs = [res.get((r["rowId"], a, 20.0, 600.0)) for r in rs]
                ok = sum(1 for x in xs if x and x["status"] == "completed")
                boil = sum(1 for x in xs if x and x["status"] == "boiling-stop")
                oth = sum(1 for x in xs if x and x["status"] not in ("completed", "boiling-stop"))
                miss = sum(1 for x in xs if x is None)
                cells.append(f"{ok} ok / {boil} boil" + (f" / {oth} other" if oth else "") + (f" / {miss} not run" if miss else ""))
            P(f"| {name} | {b} | {len(rs)} | " + " | ".join(cells) + " |")

    def per_source_table(arm, op):
        P(f"\n### Arm `{arm}`, operator `{op}`: depth bias/MAPE % [width bias/MAPE %] on the rows the arm completed, kernels on the SAME rows")
        P("| source | n | FV | ET C0 | Goldak C0 | Rosenthal C0 | best kernel (D MAPE) |")
        P("|---|---|---|---|---|---|---|")
        per_source = {}
        for name, sel in SOURCES:
            rs = [r for r in main_rows if sel(r)]
            ok = []
            for r in rs:
                x = res.get((r["rowId"], arm, 20.0, 600.0))
                w, dd = fv_wd(x, op)
                if dd is None:
                    continue
                if any(kernel_wd(r, k)[1] is None for k in KERNELS):
                    continue
                ok.append((r, w, dd))
            if len(ok) < 3:
                P(f"| {name} | {len(ok)} | too few completed rows | | | | |")
                continue
            dfv = stats([(dd, r["depth_um"]) for r, w, dd in ok]); wfv = stats([(w, r["width_um"]) for r, w, dd in ok])
            ks = {k: (stats([(kernel_wd(r, k)[1], r["depth_um"]) for r, _, _ in ok]), stats([(kernel_wd(r, k)[0], r["width_um"]) for r, _, _ in ok])) for k in KERNELS}
            best = min(KERNELS, key=lambda k: ks[k][0]["mape"])
            per_source[name] = dict(n=len(ok), fvD=dfv, fvW=wfv, kernels=ks, best=best)
            P(f"| {name} | {len(ok)} | {fmt(dfv)} [{fmt(wfv)}] | " + " | ".join(f"{fmt(ks[k][0])} [{fmt(ks[k][1])}]" for k in KERNELS) + f" | {best} {ks[best][0]['mape']:.0f} |")
        return per_source

    def pooled(per_source):
        if not per_source:
            return None
        fvD = st.mean(v["fvD"]["mape"] for v in per_source.values())
        fvW = st.mean(v["fvW"]["mape"] for v in per_source.values())
        kD = {k: st.mean(v["kernels"][k][0]["mape"] for v in per_source.values()) for k in KERNELS}
        kW = {k: st.mean(v["kernels"][k][1]["mape"] for v in per_source.values()) for k in KERNELS}
        best = min(KERNELS, key=lambda k: kD[k])
        return dict(fvD=fvD, fvW=fvW, kD=kD, kW=kW, best=best, sources=len(per_source))

    summary = {}
    for arm in arms:
        for op in ("env-mid", "peak", "env-full"):
            ps = per_source_table(arm, op)
            pl = pooled(ps)
            summary[(arm, op)] = (ps, pl)
            if pl:
                P(f"\nEqual-source-weight ({pl['sources']} sources): FV D MAPE {pl['fvD']:.1f} / W MAPE {pl['fvW']:.1f}; kernels D "
                  + ", ".join(f"{k} {pl['kD'][k]:.1f}" for k in KERNELS) + f"; best kernel {pl['best']} ({pl['kD'][pl['best']]:.1f}); "
                  + "kernels W " + ", ".join(f"{k} {pl['kW'][k]:.1f}" for k in KERNELS))

    P("\n### Per band (20 um), arm evap-sf vs evap-v40, operator env-mid: D bias/MAPE on rows both completed; ET C0 beside")
    P("| source | band | n | evap-sf | evap-v40 | ET C0 |")
    P("|---|---|---|---|---|---|")
    for name, sel in SOURCES:
        for b in BANDS:
            rs = [r for r in main_rows if sel(r) and r["band"] == b]
            ok = [(r, fv_wd(res.get((r["rowId"], "evap-sf", 20.0, 600.0)), "env-mid")[1], fv_wd(res.get((r["rowId"], "evap-v40", 20.0, 600.0)), "env-mid")[1])
                  for r in rs]
            ok = [t for t in ok if t[1] is not None and t[2] is not None and kernel_wd(t[0], "eagar-tsai")[1] is not None]
            if not ok:
                continue
            P(f"| {name} | {b} | {len(ok)} | {fmt(stats([(a, r['depth_um']) for r, a, _ in ok]))} | {fmt(stats([(c, r['depth_um']) for r, _, c in ok]))} | {fmt(stats([(kernel_wd(r, 'eagar-tsai')[1], r['depth_um']) for r, _, _ in ok]))} |")

    P("\n### Surface temperature and evaporated energy fraction, arm evap-sf (20 um), per source x band: median T_surf/T_b, median evaporated fraction, max")
    for name, sel in SOURCES:
        for b in BANDS:
            xs = [res.get((r["rowId"], "evap-sf", 20.0, 600.0)) for r in main_rows if sel(r) and r["band"] == b]
            xs = [x for x in xs if x and x["status"] == "completed"]
            if not xs:
                continue
            ratio = [x["maxSurfaceTemperature_K"] / x["boiling_K"] for x in xs]
            ef = [x["energy"]["evaporatedFraction"] for x in xs]
            P(f"  {name} {b}: n{len(xs)} T_surf/T_b median {st.median(ratio):.2f} max {max(ratio):.2f}; evaporated fraction median {st.median(ef):.2f} max {max(ef):.2f}")

    P("\n### NIST vapour/melt bound (gate 4): cavity-mid depth <= measured melt depth, arm evap-sf")
    nist_ok = True
    for r in main_rows:
        if r["dataset"] != "nist-amb2022-03":
            continue
        x = res.get((r["rowId"], "evap-sf", 20.0, 600.0))
        if not x or x["status"] != "completed":
            P(f"  {r['rowId']}: not completed"); nist_ok = False; continue
        c = x["operators"]["cavityMid"]["depthPlate_um"]; e = x["operators"]["envMid"]["depthPlate_um"]
        okb = c <= r["depth_um"]
        nist_ok &= okb
        P(f"  {r['rowId']}: cavity {c:.0f} um, melt FV {e:.0f} um, measured melt {r['depth_um']:.0f} um -> {'ok' if okb else 'VIOLATION'}")

    P("\n### Cunningham vapour depth vs cavity proxy (arm evap-sf, 20 um)")
    for r in rows:
        if r["depth_um"] is not None:
            continue
        x = res.get((r["rowId"], "evap-sf", 20.0, 600.0))
        if not x or x["status"] != "completed":
            P(f"  {r['rowId']}: {x['status'] if x else 'not run'}"); continue
        c = x["operators"]["cavityMid"]; e = x["operators"]["envMid"]
        P(f"  {r['rowId']} ({r['band']}): measured vapour {r['vapor_um']:.0f} um; cavity-mid {c['depthPlate_um']:.0f} um; melt env-mid {e['depthPlate_um']:.0f} um; Fabbro F0 {(r.get('fabbro') or {}).get('F0', float('nan')):.0f} um; T_surf/T_b {x['maxSurfaceTemperature_K'] / x['boiling_K']:.2f}")

    P("\n### Mesh convergence, arm evap-sf, operator env-mid (W / D um; cells; wall s)")
    mesh_ok = True
    fine_cases = 0
    for r in rows:
        runs = {(x["mesh_um"], x["track_um"]): x for (rid, a, mm, tr), x in res.items() if rid == r["rowId"] and a == "evap-sf"}
        if len(runs) <= 1:
            continue
        line = [f"  {r['rowId']} ({r['dataset']} {r['band']}, meas W {r['width_um']} D {r['depth_um']}):"]
        for key in sorted(runs, key=lambda t: (-t[1], -t[0])):
            x = runs[key]
            if x["status"] == "completed":
                e = x["operators"]["envMid"]
                line.append(f"{key[0]:g}um@{key[1]:g}: W {e['width_um']:.0f} D {e['depthPlate_um']:.0f} ({x['discretization']['cells']} cells, {x['wall_s']:.0f} s)")
            else:
                line.append(f"{key[0]:g}um@{key[1]:g}: {x['status']} {x.get('message', '')[:60]}")
        P(" ".join(line))
        tracks = {t for _, t in runs}
        for tr in tracks:
            a, b = runs.get((10.0, tr)), runs.get((5.0, tr))
            if a and b and a["status"] == "completed" and b["status"] == "completed":
                ea, eb = a["operators"]["envMid"], b["operators"]["envMid"]
                dw = abs(eb["width_um"] - ea["width_um"]) / max(eb["width_um"], 1e-9)
                dd = abs(eb["depthPlate_um"] - ea["depthPlate_um"]) / max(eb["depthPlate_um"], 1e-9)
                fine_cases += 1
                okc = dw <= .05 and dd <= .05
                mesh_ok &= okc
                P(f"    10 -> 5 um at track {tr:g}: dW {100 * dw:.0f} % dD {100 * dd:.0f} % -> {'ok' if okc else 'NOT converged'}")
            a, b = runs.get((20.0, tr)), runs.get((10.0, tr))
            if a and b and a["status"] == "completed" and b["status"] == "completed":
                ea, eb = a["operators"]["envMid"], b["operators"]["envMid"]
                P(f"    20 -> 10 um at track {tr:g}: dW {100 * abs(eb['width_um'] - ea['width_um']) / max(eb['width_um'], 1e-9):.0f} % dD {100 * abs(eb['depthPlate_um'] - ea['depthPlate_um']) / max(eb['depthPlate_um'], 1e-9):.0f} %")

    P("\n### Energy balance (gate 6) and runtime")
    worst = 0.0
    for a in arms:
        xs = [x for x in d["results"] if x["arm"] == a and x["status"] == "completed"]
        if xs:
            resid = max(x["energy"]["relativeResidual"] for x in xs)
            worst = max(worst, resid)
            w = sorted(x["wall_s"] for x in xs)
            P(f"  {a}: n{len(xs)} completed; max |residual| {resid:.1e}; wall median {st.median(w):.0f} s, p90 {w[int(.9 * (len(w) - 1))]:.0f} s, max {max(w):.0f} s"
              + (f"; evaporated fraction median {st.median(x['energy']['evaporatedFraction'] for x in xs):.2f} max {max(x['energy']['evaporatedFraction'] for x in xs):.2f}" if a.startswith("evap") else ""))
        stops = [x for x in d["results"] if x["arm"] == a and x["status"] != "completed"]
        if stops:
            w = sorted(x.get("wall_s", 0) for x in stops)
            P(f"  {a}: n{len(stops)} not completed ({', '.join(sorted(set(x['status'] for x in stops)))}); wall median {st.median(w):.0f} s")
    errs = [(x["rowId"], x["arm"], x["mesh_um"], x.get("message", "")[:120]) for x in d["results"] if x["status"] == "error"]
    if errs:
        P("  errors: " + "; ".join(f"{a} {b} {c}um: {m}" for a, b, c, m in errs))

    P("\n### Gate (PREDECLARED §3), arm evap-sf, operator env-mid")
    ps, pl = summary[("evap-sf", "env-mid")]
    if not pl:
        P("  not evaluable: no source with >= 3 completed rows")
    else:
        best = pl["best"]
        g1 = pl["fvD"] <= pl["kD"][best] - 5
        bad2 = [n for n, v in ps.items() if v["fvD"]["mape"] > v["kernels"][best][0]["mape"] + 5]
        bad3 = [n for n, v in ps.items() if v["fvW"]["mape"] > v["kernels"][best][1]["mape"] + 2]
        P(f"  1. equal-source D MAPE: FV {pl['fvD']:.1f} vs best kernel {best} {pl['kD'][best]:.1f} (need <= {pl['kD'][best] - 5:.1f}) -> {'PASS' if g1 else 'FAIL'}")
        P(f"  2. sources with D MAPE worse than {best} by > 5 points: {bad2 or 'none'} -> {'PASS' if not bad2 else 'FAIL'}")
        P(f"  3. sources with W MAPE worse than {best} by > 2 points: {bad3 or 'none'} -> {'PASS' if not bad3 else 'FAIL'}")
        P(f"  4. NIST vapour/melt bound -> {'PASS' if nist_ok else 'FAIL'}")
        P(f"  5. mesh 10 -> 5 um <= 5 % on {fine_cases} finished 5 um cases -> {'PASS' if (mesh_ok and fine_cases) else 'FAIL' if fine_cases else 'NOT EVALUABLE (no finished 5 um pair)'}")
        P(f"  6. energy residual max {worst:.1e} <= 1 % -> {'PASS' if worst <= .01 else 'FAIL'}")
        allok = g1 and not bad2 and not bad3 and nist_ok and mesh_ok and fine_cases and worst <= .01
        P(f"  VERDICT: {'PASS' if allok else 'FAIL'}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
