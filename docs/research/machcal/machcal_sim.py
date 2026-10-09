"""Machine-specific (single-source) absorptivity calibration simulation on the prototype eta grid.
Reads calib-proto/grid.json + rows.json and depth_tdep_results.json (interpolation check). No solver call.
See PREDECLARED_depth_bands_machinecal.md section B."""
import json, math, random, collections, statistics
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PROTO = HERE / "calib-proto"
KERNELS = ("eagar-tsai", "goldak", "rosenthal")
SOURCES = ("hofmann-316l-2026", "ku-leuven-316l-2021", "totis-ti64-2021", "ku-leuven-ti64-2021", "lane-in625-2020")
DEFAULT = {"316L Stainless Steel": 0.42, "Ti-6Al-4V": 0.35, "Inconel 625": 0.38}
LAM = 0.05
NODES = [round(0.20 + 0.05 * i, 2) for i in range(15)]
FINE = np.array([round(0.25 + 0.005 * i, 6) for i in range(111)])
MS = (3, 4, 5, 6, 8)
DRAWS = 200
T80 = {2: 1.886, 3: 1.638, 4: 1.533, 5: 1.476, 6: 1.440, 7: 1.415, 8: 1.397}  # one-sided 90 % t (two-sided 80 %) by dof


def t80(dof):
    return T80.get(dof, 1.2816 if dof > 8 else 3.078)


rows = {r["rowId"]: r for r in json.load(open(PROTO / "rows.json"))}
grid = json.load(open(PROTO / "grid.json"))
tab = collections.defaultdict(dict)  # (rowId, kernel) -> eta -> (W, D, status)
for rid, k, a, W, D, status, dH in grid:
    tab[(rid, k)][a] = (W, D, status)


def interp(vals, eta):
    """ln-linear interpolation between nodes; None if a bracketing node is unresolved."""
    i = max(j for j, n in enumerate(NODES) if n <= eta + 1e-9)
    if i >= len(NODES) - 1:
        i = len(NODES) - 2
    lo, hi = NODES[i], NODES[i + 1]
    a, b = vals.get(lo), vals.get(hi)
    if a is None or b is None or a[2] != "computed" or b[2] != "computed" or not a[0] or not b[0] or not a[1] or not b[1]:
        return None
    w = (math.log(eta) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return (math.exp((1 - w) * math.log(a[0]) + w * math.log(b[0])), math.exp((1 - w) * math.log(a[1]) + w * math.log(b[1])))


# ---- interpolation check against the exact served default (depth_tdep C0)
# depth_tdep_results.json (2 MB, exact served default per row) is not committed; without it the check is skipped
# and only the interpolationCheck key / first report line differ from the committed outputs.
TDEP = HERE / "depth_tdep_results.json"
tdep = {r["rowId"]: r for r in json.load(open(TDEP, encoding="utf-8"))["rows"]} if TDEP.exists() else {}
chk = collections.defaultdict(list)
for (rid, k), vals in tab.items():
    r = rows[rid]
    if r["source"] not in SOURCES or rid not in tdep:
        continue
    p = tdep[rid]["pred"][f"{k}|C0"]
    it = interp(vals, DEFAULT[r["material"]])
    if it and p.get("status") == "computed" and p.get("D") and p.get("W"):
        chk[k].append((abs(math.log(it[0] / p["W"])), abs(math.log(it[1] / p["D"]))))
interp_check = {"skipped": "depth_tdep_results.json not present"} if not tdep else {k: {"n": len(v), "medAbsLnW": float(np.median([x[0] for x in v])), "medAbsLnD": float(np.median([x[1] for x in v])),
                    "p95AbsLnD": float(np.percentile([x[1] for x in v], 95))} for k, v in chk.items()}

# ---- per source x kernel: set table of fine-grid ln predictions
def build(source, kernel):
    sets = collections.defaultdict(list)
    for rid, r in rows.items():
        if r["source"] == source:
            sets[(r["power_W"], r["speed_mm_s"], r["beamDiameter_um"])].append(rid)
    keys, lnW, lnD, mW, mD, defW, defD = [], [], [], [], [], [], []
    rng = random.Random(12345)
    for key in sorted(sets):
        rid = rng.choice(sorted(sets[key]))  # one cross-section per track
        vals = tab[(rid, kernel)]
        fine = [interp(vals, e) for e in FINE]
        d = interp(vals, DEFAULT[rows[rid]["material"]])
        if any(f is None for f in fine) or d is None:
            continue
        keys.append(key)
        lnW.append([math.log(f[0]) for f in fine]); lnD.append([math.log(f[1]) for f in fine])
        mW.append(math.log(rows[rid]["W"])); mD.append(math.log(rows[rid]["D"]))
        defW.append(math.log(d[0])); defD.append(math.log(d[1]))
    return {"keys": keys, "lnW": np.array(lnW), "lnD": np.array(lnD), "mW": np.array(mW), "mD": np.array(mD),
            "defW": np.array(defW), "defD": np.array(defD), "nSetsAll": len(sets), "nSets": len(keys),
            "prior": DEFAULT[rows[next(iter(sets and [rid]))]["material"]] if keys else None}


def fit_eta(ln_pred, meas, prior):
    """argmin over FINE of mean |ln(meas/pred)| + LAM ln(eta/prior)^2; returns index."""
    loss = np.mean(np.abs(meas[:, None] - ln_pred), axis=0) + LAM * np.log(FINE / prior) ** 2
    return int(np.argmin(loss))


def mape(ln_pred, meas):
    return float(np.mean(np.abs(np.exp(ln_pred - meas) - 1.0)) * 100)


results = []
for source in SOURCES:
    for kernel in KERNELS:
        T = build(source, kernel)
        n = T["nSets"]
        prior = T["prior"]
        for m in MS:
            if n < m + 3:
                results.append({"source": source, "kernel": kernel, "m": m, "skipped": f"only {n} usable sets"})
                continue
            per_rung = {rung: collections.defaultdict(list) for rung in ("etaD", "etaJoint")}
            for draw in range(DRAWS):
                rng = random.Random(draw)
                idx = np.array(sorted(rng.sample(range(n), m)))
                rest = np.array([i for i in range(n) if i not in set(idx.tolist())])
                for rung in ("etaD", "etaJoint"):
                    def fitted(ii):
                        if rung == "etaD":
                            return fit_eta(T["lnD"][ii], T["mD"][ii], prior)
                        lossD = np.mean(np.abs(T["mD"][ii][:, None] - T["lnD"][ii]), axis=0)
                        lossW = np.mean(np.abs(T["mW"][ii][:, None] - T["lnW"][ii]), axis=0)
                        return int(np.argmin(0.5 * (lossD + lossW) + LAM * np.log(FINE / prior) ** 2))
                    j = fitted(idx)
                    eta = float(FINE[j])
                    # LOO inside the user's tracks
                    loo_res, loo_def = [], []
                    for leave in range(m):
                        ii = np.delete(idx, leave)
                        jj = fitted(ii)
                        o = idx[leave]
                        loo_res.append(T["mD"][o] - T["lnD"][o, jj])
                        loo_def.append(T["mD"][o] - T["defD"][o])
                    loo_res, loo_def = np.array(loo_res), np.array(loo_def)
                    mae_cal, mae_def = np.mean(np.abs(loo_res)), np.mean(np.abs(loo_def))
                    skill_loo = 1 - mae_cal / mae_def if mae_def > 0 else 0.0
                    loo_mape = float(np.mean(np.abs(np.exp(-loo_res) - 1)) * 100)
                    at_bound = j <= 1 or j >= len(FINE) - 2
                    gates = {"G1": skill_loo > 0, "G2": skill_loo > 0 and not at_bound,
                             "G3": skill_loo > 0 and not at_bound and m >= 4,
                             "G4": skill_loo > 0 and not at_bound and m >= 4 and loo_mape <= 25}
                    # held-out machine tracks
                    hd_def = mape(T["defD"][rest], T["mD"][rest])
                    hd_cal = mape(T["lnD"][rest, j], T["mD"][rest])
                    hw_def = mape(T["defW"][rest], T["mW"][rest])
                    hw_cal = mape(T["lnW"][rest, j], T["mW"][rest]) if rung == "etaJoint" else hw_def
                    # user band from LOO residuals (ln space): centre mu, spread sd, t factor, +1/m
                    mu = float(np.mean(loo_res)); sd = float(np.std(loo_res, ddof=1)) if m > 1 else 0.0
                    half = t80(m - 1) * sd * math.sqrt(1 + 1 / m)
                    resid_rest = T["mD"][rest] - T["lnD"][rest, j]
                    cov = float(np.mean((resid_rest >= mu - half) & (resid_rest <= mu + half)))
                    # band without the LOO centre shift (prediction not re-centred), same half width
                    cov0 = float(np.mean((resid_rest >= -half) & (resid_rest <= half)))
                    rec = per_rung[rung]
                    rec["eta"].append(eta); rec["skillLoo"].append(skill_loo); rec["looMape"].append(loo_mape)
                    rec["hdDef"].append(hd_def); rec["hdCal"].append(hd_cal); rec["hwDef"].append(hw_def); rec["hwCal"].append(hw_cal)
                    rec["cov"].append(cov); rec["cov0"].append(cov0); rec["halfPct"].append(100 * (math.exp(half) - 1))
                    rec["biasRest"].append(float(np.mean(resid_rest)))
                    for g, ok in gates.items():
                        rec[g].append(ok)
            for rung, rec in per_rung.items():
                summ = {"source": source, "kernel": kernel, "m": m, "rung": rung, "nSets": n, "draws": DRAWS,
                        "heldOutDepthMapeDefault": float(np.median(rec["hdDef"])),
                        "heldOutDepthMapeCal_all": float(np.median(rec["hdCal"])),
                        "heldOutDepthMapeCal_p10_p90": [float(np.percentile(rec["hdCal"], 10)), float(np.percentile(rec["hdCal"], 90))],
                        "heldOutWidthMapeDefault": float(np.median(rec["hwDef"])), "heldOutWidthMapeCal": float(np.median(rec["hwCal"])),
                        "etaMedian": float(np.median(rec["eta"])), "etaP10P90": [float(np.percentile(rec["eta"], 10)), float(np.percentile(rec["eta"], 90))],
                        "bandHalfPctMedian": float(np.median(rec["halfPct"])),
                        "coverage80_all": float(np.mean(rec["cov"])), "coverage80_noCentre_all": float(np.mean(rec["cov0"])),
                        "worseThanDefault_all": float(np.mean(np.array(rec["hdCal"]) > np.array(rec["hdDef"]))),
                        "gates": {}}
                for g in ("G1", "G2", "G3", "G4"):
                    ok = np.array(rec[g])
                    if ok.sum() == 0:
                        summ["gates"][g] = {"passRate": 0.0}
                        continue
                    hc, hdf = np.array(rec["hdCal"])[ok], np.array(rec["hdDef"])[ok]
                    summ["gates"][g] = {"passRate": float(ok.mean()), "heldOutDepthMapeCal": float(np.median(hc)),
                                        "heldOutDepthMapeDefault": float(np.median(hdf)),
                                        "falsePass": float(np.mean(hc > hdf)), "falsePassBy5": float(np.mean(hc > hdf + 5)),
                                        "coverage80": float(np.mean(np.array(rec["cov"])[ok])),
                                        "coverage80_noCentre": float(np.mean(np.array(rec["cov0"])[ok])),
                                        "bandHalfPct": float(np.median(np.array(rec["halfPct"])[ok]))}
                results.append(summ)

json.dump({"interpolationCheck": interp_check, "results": results}, open(HERE / "machcal_results.json", "w"), indent=1)

lines = [f"interpolation check vs exact served default (median |ln| per kernel): {json.dumps(interp_check)}", ""]
lines.append("| source | kernel | m | rung | sets | HO D MAPE def -> cal (all draws) | worse% all | G1 pass / falsePass / cal | G3 pass / falsePass / cal / cov80 | G4 pass / falsePass / cal / cov80 | band ± % | eta med [p10,p90] | HO W def -> cal |")
lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for s in results:
    if "skipped" in s:
        lines.append(f"| {s['source']} | {s['kernel']} | {s['m']} | - | - | skipped: {s['skipped']} | | | | | | | |")
        continue
    g = s["gates"]
    def gs(x, cov=False):
        if x.get("passRate", 0) == 0:
            return "0.00"
        base = f"{x['passRate']:.2f} / {x['falsePass']:.2f} / {x['heldOutDepthMapeCal']:.1f}"
        return base + (f" / {x['coverage80']:.2f}" if cov else "")
    lines.append(f"| {s['source'].split('-')[0]}{'-ti64' if 'ti64' in s['source'] else ''} | {s['kernel']} | {s['m']} | {s['rung']} | {s['nSets']} | {s['heldOutDepthMapeDefault']:.1f} -> {s['heldOutDepthMapeCal_all']:.1f} [{s['heldOutDepthMapeCal_p10_p90'][0]:.0f},{s['heldOutDepthMapeCal_p10_p90'][1]:.0f}] | {100*s['worseThanDefault_all']:.0f} | {gs(g['G1'])} | {gs(g['G3'], True)} | {gs(g['G4'], True)} | {s['bandHalfPctMedian']:.0f} | {s['etaMedian']:.3f} [{s['etaP10P90'][0]:.2f},{s['etaP10P90'][1]:.2f}] | {s['heldOutWidthMapeDefault']:.1f} -> {s['heldOutWidthMapeCal']:.1f} |")
(HERE / "machcal_report.md").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
