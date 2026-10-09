"""Second gate family for machine calibration (declared after seeing the oracle: a single eta can only absorb a
UNIFORM machine-level offset). Depth-only eta (etaD rung). Gates:
 G5 uniform default bias on the user's m tracks: >= 80 % of ln residuals at default share a sign AND |mean| >= 0.15;
 G6 G5 AND LOO skill > 0 AND eta not within one fine step of a bound;
 G7 G6 AND m >= 5.
Reports pass rate, false pass (held-out depth MAPE worse than default), median held-out MAPE default -> cal, band coverage."""
import json, math, random, collections
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
KERNELS = ("eagar-tsai", "goldak", "rosenthal")
SOURCES = ("hofmann-316l-2026", "ku-leuven-316l-2021", "totis-ti64-2021", "ku-leuven-ti64-2021", "lane-in625-2020")
DEFAULT = {"316L Stainless Steel": 0.42, "Ti-6Al-4V": 0.35, "Inconel 625": 0.38}
NODES = [round(0.20 + 0.05 * i, 2) for i in range(15)]
FINE = np.array([round(0.25 + 0.005 * i, 6) for i in range(111)])
LAM = 0.05
MS = (12, 16, 24)
DRAWS = 200
T80 = {2: 1.886, 3: 1.638, 4: 1.533, 5: 1.476, 6: 1.440, 7: 1.415, 8: 1.397}
rows = {r["rowId"]: r for r in json.load(open(HERE / "calib-proto/rows.json"))}
tab = collections.defaultdict(dict)
for rid, k, a, W, D, status, dH in json.load(open(HERE / "calib-proto/grid.json")):
    tab[(rid, k)][a] = (W, D, status)


def interp(vals, eta):
    i = min(max(j for j, n in enumerate(NODES) if n <= eta + 1e-9), len(NODES) - 2)
    lo, hi = NODES[i], NODES[i + 1]
    a, b = vals.get(lo), vals.get(hi)
    if a is None or b is None or a[2] != "computed" or b[2] != "computed" or not a[1] or not b[1]:
        return None
    w = (math.log(eta) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return math.exp((1 - w) * math.log(a[1]) + w * math.log(b[1]))


def build(source, kernel):
    sets = collections.defaultdict(list)
    for rid, r in rows.items():
        if r["source"] == source:
            sets[(r["power_W"], r["speed_mm_s"], r["beamDiameter_um"])].append(rid)
    rng = random.Random(12345)
    lnD, mD, defD = [], [], []
    prior = None
    for key in sorted(sets):
        rid = rng.choice(sorted(sets[key]))
        prior = DEFAULT[rows[rid]["material"]]
        fine = [interp(tab[(rid, kernel)], e) for e in FINE]
        d = interp(tab[(rid, kernel)], prior)
        if any(f is None for f in fine) or d is None:
            continue
        lnD.append([math.log(f) for f in fine]); mD.append(math.log(rows[rid]["D"])); defD.append(math.log(d))
    return np.array(lnD), np.array(mD), np.array(defD), prior


def fit(lnD, mD, prior):
    return int(np.argmin(np.mean(np.abs(mD[:, None] - lnD), axis=0) + LAM * np.log(FINE / prior) ** 2))


mape = lambda p, m: float(np.mean(np.abs(np.exp(p - m) - 1)) * 100)
res = []
for source in SOURCES:
    for kernel in KERNELS:
        lnD, mD, defD, prior = build(source, kernel)
        n = len(mD)
        for m in MS:
            if n < m + 3:
                continue
            rec = collections.defaultdict(list)
            for draw in range(DRAWS):
                rng = random.Random(draw)
                idx = np.array(sorted(rng.sample(range(n), m)))
                rest = np.array([i for i in range(n) if i not in set(idx.tolist())])
                r0 = mD[idx] - defD[idx]
                frac_sign = max(np.mean(r0 > 0), np.mean(r0 < 0))
                uniform = frac_sign >= 0.8 and abs(float(np.mean(r0))) >= 0.15
                j = fit(lnD[idx], mD[idx], prior)
                loo = np.array([mD[idx[l]] - lnD[idx[l], fit(lnD[np.delete(idx, l)], mD[np.delete(idx, l)], prior)] for l in range(m)])
                skill = 1 - np.mean(np.abs(loo)) / np.mean(np.abs(r0))
                at_bound = j <= 1 or j >= len(FINE) - 2
                hd, hc = mape(defD[rest], mD[rest]), mape(lnD[rest, j], mD[rest])
                mu, sd = float(np.mean(loo)), float(np.std(loo, ddof=1))
                half = T80.get(m - 1, 1.2816) * sd * math.sqrt(1 + 1 / m)
                rr = mD[rest] - lnD[rest, j]
                cov = float(np.mean((rr >= mu - half) & (rr <= mu + half)))
                rec["hd"].append(hd); rec["hc"].append(hc); rec["cov"].append(cov); rec["half"].append(100 * (math.exp(half) - 1))
                rec["eta"].append(float(FINE[j]))
                rec["G5"].append(uniform); rec["G6"].append(uniform and skill > 0 and not at_bound)
                rec["G7"].append(uniform and skill > 0 and not at_bound and m >= 12)
            row = {"source": source, "kernel": kernel, "m": m, "nSets": n, "hdDefault": float(np.median(rec["hd"])),
                   "hdCalAll": float(np.median(rec["hc"])), "worseAll": float(np.mean(np.array(rec["hc"]) > np.array(rec["hd"]))), "gates": {}}
            for g in ("G5", "G6", "G7"):
                ok = np.array(rec[g])
                if ok.sum() == 0:
                    row["gates"][g] = {"passRate": 0.0}; continue
                hc, hd = np.array(rec["hc"])[ok], np.array(rec["hd"])[ok]
                row["gates"][g] = {"passRate": float(ok.mean()), "falsePass": float(np.mean(hc > hd)), "falsePassBy5": float(np.mean(hc > hd + 5)),
                                   "hdCal": float(np.median(hc)), "hdDef": float(np.median(hd)), "gainMedian": float(np.median(hd - hc)),
                                   "cov80": float(np.mean(np.array(rec["cov"])[ok])), "halfPct": float(np.median(np.array(rec["half"])[ok])),
                                   "etaMedian": float(np.median(np.array(rec["eta"])[ok]))}
            res.append(row)
json.dump(res, open(HERE / "machcal_gate2_big.json", "w"), indent=1)
print("| source | kernel | m | sets | HO D MAPE def -> cal (all) | worse% | G5 pass/false | G6 pass / false / false>5pt / def->cal / cov80 / band± / eta | G7 pass / false / def->cal / cov80 |")
print("|---|---|---|---|---|---|---|---|---|")
for r in res:
    g5, g6, g7 = r["gates"]["G5"], r["gates"]["G6"], r["gates"]["G7"]
    f = lambda g, full: ("0.00" if g.get("passRate", 0) == 0 else (f"{g['passRate']:.2f} / {g['falsePass']:.2f} / {g['falsePassBy5']:.2f} / {g['hdDef']:.1f}->{g['hdCal']:.1f} / {g['cov80']:.2f} / {g['halfPct']:.0f} / {g['etaMedian']:.3f}" if full else f"{g['passRate']:.2f} / {g['falsePass']:.2f} / {g['hdDef']:.1f}->{g['hdCal']:.1f} / {g['cov80']:.2f}"))
    g5s = "0.00" if g5.get("passRate", 0) == 0 else f"{g5['passRate']:.2f}/{g5['falsePass']:.2f}"
    print(f"| {r['source']} | {r['kernel']} | {r['m']} | {r['nSets']} | {r['hdDefault']:.1f} -> {r['hdCalAll']:.1f} | {100*r['worseAll']:.0f} | {g5s} | {f(g6, True)} | {f(g7, False)} |")
