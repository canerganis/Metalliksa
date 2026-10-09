"""Regime-consistency gate (declared after the oracle showed regime-dependent depth error): the user's tracks are
drawn stratified from the two most populated regime classes of the source (m/2 each). Depth-only eta.
 G8: m >= 8, >= 3 tracks per class, LOO skill > 0, eta not at bound, AND the per-class median LOO residual
     (ln meas/pred at the fitted eta) differs between the two classes by <= 0.15 (no regime-dependent remainder).
 G9: G8 with the class difference <= 0.10.
Reports pass rate, false pass, held-out MAPE default -> cal, 80 % band coverage on the held-out tracks."""
import json, math, random, collections
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
KERNELS = ("eagar-tsai", "goldak", "rosenthal")
SOURCES = ("hofmann-316l-2026", "ku-leuven-316l-2021", "totis-ti64-2021", "ku-leuven-ti64-2021")
DEFAULT = {"316L Stainless Steel": 0.42, "Ti-6Al-4V": 0.35, "Inconel 625": 0.38}
NODES = [round(0.20 + 0.05 * i, 2) for i in range(15)]
FINE = np.array([round(0.25 + 0.005 * i, 6) for i in range(111)])
LAM = 0.05
MS = (8, 10, 12, 16)
DRAWS = 200
T80 = {5: 1.476, 6: 1.440, 7: 1.415, 8: 1.397, 9: 1.383, 10: 1.372, 11: 1.363, 12: 1.356, 15: 1.341}
rows = {r["rowId"]: r for r in json.load(open(HERE / "calib-proto/rows.json"))}
tab = collections.defaultdict(dict)
dh_at = {}
for rid, k, a, W, D, status, dH in json.load(open(HERE / "calib-proto/grid.json")):
    tab[(rid, k)][a] = (W, D, status)
    if a == 0.5 and dH:
        dh_at[rid] = dH / 0.5


def interp(vals, eta):
    i = min(max(j for j, n in enumerate(NODES) if n <= eta + 1e-9), len(NODES) - 2)
    lo, hi = NODES[i], NODES[i + 1]
    a, b = vals.get(lo), vals.get(hi)
    if a is None or b is None or a[2] != "computed" or b[2] != "computed" or not a[1] or not b[1]:
        return None
    w = (math.log(eta) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return math.exp((1 - w) * math.log(a[1]) + w * math.log(b[1]))


def regime(h):
    return "conduction" if h < 15 else ("transition" if h < 30 else "keyhole")


def build(source, kernel):
    sets = collections.defaultdict(list)
    for rid, r in rows.items():
        if r["source"] == source:
            sets[(r["power_W"], r["speed_mm_s"], r["beamDiameter_um"])].append(rid)
    rng = random.Random(12345)
    lnD, mD, defD, cls = [], [], [], []
    prior = None
    for key in sorted(sets):
        rid = rng.choice(sorted(sets[key]))
        prior = DEFAULT[rows[rid]["material"]]
        fine = [interp(tab[(rid, kernel)], e) for e in FINE]
        d = interp(tab[(rid, kernel)], prior)
        if any(f is None for f in fine) or d is None or rid not in dh_at:
            continue
        lnD.append([math.log(f) for f in fine]); mD.append(math.log(rows[rid]["D"])); defD.append(math.log(d))
        cls.append(regime(dh_at[rid] * prior))
    return np.array(lnD), np.array(mD), np.array(defD), np.array(cls), prior


def fit(lnD, mD, prior):
    return int(np.argmin(np.mean(np.abs(mD[:, None] - lnD), axis=0) + LAM * np.log(FINE / prior) ** 2))


mape = lambda p, m: float(np.mean(np.abs(np.exp(p - m) - 1)) * 100)
res = []
for source in SOURCES:
    for kernel in KERNELS:
        lnD, mD, defD, cls, prior = build(source, kernel)
        n = len(mD)
        counts = collections.Counter(cls.tolist())
        top2 = [c for c, _ in counts.most_common(2)]
        if len(top2) < 2:
            continue
        for m in MS:
            h = m // 2
            if any(counts[c] < h + 2 for c in top2):
                res.append({"source": source, "kernel": kernel, "m": m, "skipped": f"classes {dict(counts)}"})
                continue
            rec = collections.defaultdict(list)
            for draw in range(DRAWS):
                rng = random.Random(draw)
                idx = np.array(sorted(sum((rng.sample(np.flatnonzero(cls == c).tolist(), h) for c in top2), [])))
                rest = np.array([i for i in range(n) if i not in set(idx.tolist())])
                r0 = mD[idx] - defD[idx]
                j = fit(lnD[idx], mD[idx], prior)
                loo = np.array([mD[idx[l]] - lnD[idx[l], fit(lnD[np.delete(idx, l)], mD[np.delete(idx, l)], prior)] for l in range(m)])
                skill = 1 - np.mean(np.abs(loo)) / np.mean(np.abs(r0))
                at_bound = j <= 1 or j >= len(FINE) - 2
                cmed = [float(np.median(loo[cls[idx] == c])) for c in top2]
                dclass = abs(cmed[0] - cmed[1])
                hd, hc = mape(defD[rest], mD[rest]), mape(lnD[rest, j], mD[rest])
                mu, sd = float(np.mean(loo)), float(np.std(loo, ddof=1))
                half = T80.get(m - 1, 1.2816) * sd * math.sqrt(1 + 1 / m)
                rr = mD[rest] - lnD[rest, j]
                cov = float(np.mean((rr >= mu - half) & (rr <= mu + half)))
                rec["hd"].append(hd); rec["hc"].append(hc); rec["cov"].append(cov); rec["half"].append(100 * (math.exp(half) - 1))
                rec["eta"].append(float(FINE[j])); rec["dclass"].append(dclass)
                base = skill > 0 and not at_bound
                rec["G8"].append(base and dclass <= 0.15); rec["G9"].append(base and dclass <= 0.10)
                rec["G1"].append(skill > 0 and not at_bound)
            row = {"source": source, "kernel": kernel, "m": m, "nSets": n, "classes": top2, "hdDefault": float(np.median(rec["hd"])),
                   "hdCalAll": float(np.median(rec["hc"])), "worseAll": float(np.mean(np.array(rec["hc"]) > np.array(rec["hd"]))),
                   "dclassMedian": float(np.median(rec["dclass"])), "gates": {}}
            for g in ("G1", "G8", "G9"):
                ok = np.array(rec[g])
                if ok.sum() == 0:
                    row["gates"][g] = {"passRate": 0.0}; continue
                hc, hd = np.array(rec["hc"])[ok], np.array(rec["hd"])[ok]
                row["gates"][g] = {"passRate": float(ok.mean()), "falsePass": float(np.mean(hc > hd)), "falsePassBy5": float(np.mean(hc > hd + 5)),
                                   "hdCal": float(np.median(hc)), "hdDef": float(np.median(hd)), "cov80": float(np.mean(np.array(rec["cov"])[ok])),
                                   "halfPct": float(np.median(np.array(rec["half"])[ok])), "etaMedian": float(np.median(np.array(rec["eta"])[ok]))}
            res.append(row)
json.dump(res, open(HERE / "machcal_gate3.json", "w"), indent=1)
print("| source | kernel | m | sets | classes | HO D MAPE def -> cal (all) | worse% | class diff med | G1 pass/false | G8 pass / false / false>5 / def->cal / cov80 / band± / eta | G9 pass / false / def->cal / cov80 |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for r in res:
    if "skipped" in r:
        print(f"| {r['source']} | {r['kernel']} | {r['m']} | skipped: {r['skipped']} | | | | | | | |"); continue
    g1, g8, g9 = r["gates"]["G1"], r["gates"]["G8"], r["gates"]["G9"]
    f = lambda g, full: ("0.00" if g.get("passRate", 0) == 0 else (f"{g['passRate']:.2f} / {g['falsePass']:.2f} / {g['falsePassBy5']:.2f} / {g['hdDef']:.1f}->{g['hdCal']:.1f} / {g['cov80']:.2f} / {g['halfPct']:.0f} / {g['etaMedian']:.3f}" if full else f"{g['passRate']:.2f} / {g['falsePass']:.2f} / {g['hdDef']:.1f}->{g['hdCal']:.1f} / {g['cov80']:.2f}"))
    g1s = "0.00" if g1.get("passRate", 0) == 0 else f"{g1['passRate']:.2f}/{g1['falsePass']:.2f}"
    print(f"| {r['source']} | {r['kernel']} | {r['m']} | {r['nSets']} | {'+'.join(c[:4] for c in r['classes'])} | {r['hdDefault']:.1f} -> {r['hdCalAll']:.1f} | {100*r['worseAll']:.0f} | {r['dclassMedian']:.2f} | {g1s} | {f(g8, True)} | {f(g9, False)} |")
