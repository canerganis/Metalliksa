"""Ceiling check for machine calibration: best single eta / single ln-offset / both, fitted on the WHOLE source
(oracle, in-sample) -- what no 3-8 track fit can beat. Plus the regime breakdown of the default depth error."""
import json, math, collections
from pathlib import Path
import numpy as np
import importlib.util
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ms", HERE / "machcal_sim.py")
# re-use the table builder without re-running the simulation: copy the minimal pieces
KERNELS = ("eagar-tsai", "goldak", "rosenthal")
SOURCES = ("hofmann-316l-2026", "ku-leuven-316l-2021", "totis-ti64-2021", "ku-leuven-ti64-2021", "lane-in625-2020")
DEFAULT = {"316L Stainless Steel": 0.42, "Ti-6Al-4V": 0.35, "Inconel 625": 0.38}
NODES = [round(0.20 + 0.05 * i, 2) for i in range(15)]
FINE = np.array([round(0.25 + 0.005 * i, 6) for i in range(111)])
rows = {r["rowId"]: r for r in json.load(open(HERE / "calib-proto/rows.json"))}
tab = collections.defaultdict(dict)
dh_at = {}
for rid, k, a, W, D, status, dH in json.load(open(HERE / "calib-proto/grid.json")):
    tab[(rid, k)][a] = (W, D, status)
    if a == 0.5 and dH:
        dh_at[rid] = dH / 0.5


def interp(vals, eta):
    i = max(j for j, n in enumerate(NODES) if n <= eta + 1e-9)
    i = min(i, len(NODES) - 2)
    lo, hi = NODES[i], NODES[i + 1]
    a, b = vals.get(lo), vals.get(hi)
    if a is None or b is None or a[2] != "computed" or b[2] != "computed" or not a[0] or not b[0] or not a[1] or not b[1]:
        return None
    w = (math.log(eta) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return (math.exp((1 - w) * math.log(a[0]) + w * math.log(b[0])), math.exp((1 - w) * math.log(a[1]) + w * math.log(b[1])))


def regime(h):
    return "conduction" if h < 15 else ("transition" if h < 30 else "keyhole")


out = []
for source in SOURCES:
    for kernel in KERNELS:
        lnD, mD, defD, cls, lnW, mW, defW = [], [], [], [], [], [], []
        for rid, r in rows.items():
            if r["source"] != source:
                continue
            vals = tab[(rid, kernel)]
            fine = [interp(vals, e) for e in FINE]
            d = interp(vals, DEFAULT[r["material"]])
            if any(f is None for f in fine) or d is None or rid not in dh_at:
                continue
            lnD.append([math.log(f[1]) for f in fine]); lnW.append([math.log(f[0]) for f in fine])
            mD.append(math.log(r["D"])); mW.append(math.log(r["W"]))
            defD.append(math.log(d[1])); defW.append(math.log(d[0]))
            cls.append(regime(dh_at[rid] * DEFAULT[r["material"]]))
        if not lnD:
            continue
        lnD, mD, defD, lnW, mW, defW = map(np.array, (lnD, mD, defD, lnW, mW, defW))
        cls = np.array(cls)
        mape = lambda p, m: float(np.mean(np.abs(np.exp(p - m) - 1)) * 100)
        bias = lambda p, m: float(np.mean(np.exp(p - m) - 1) * 100)
        # (a) eta only
        curve = np.array([mape(lnD[:, j], mD) for j in range(len(FINE))])
        ja = int(np.argmin(curve))
        # (b) offset only at default
        c = float(np.median(mD - defD))
        # (c) eta + offset (eta minimising the MAD after median-centring)
        curve_c = np.array([mape(lnD[:, j] + np.median(mD - lnD[:, j]), mD) for j in range(len(FINE))])
        jc = int(np.argmin(curve_c))
        by = {}
        for g in ("conduction", "transition", "keyhole"):
            sel = cls == g
            if sel.sum():
                by[g] = {"n": int(sel.sum()), "biasDefault": bias(defD[sel], mD[sel]), "mapeDefault": mape(defD[sel], mD[sel]),
                         "biasAtOracleEta": bias(lnD[sel, ja], mD[sel])}
        rec = {"source": source, "kernel": kernel, "n": int(len(mD)),
               "depth": {"mapeDefault": mape(defD, mD), "biasDefault": bias(defD, mD),
                         "etaOnly": {"eta": float(FINE[ja]), "mape": float(curve[ja])},
                         "offsetOnly": {"c": c, "factor": math.exp(c), "mape": mape(defD + c, mD)},
                         "etaPlusOffset": {"eta": float(FINE[jc]), "factor": math.exp(float(np.median(mD - lnD[:, jc]))), "mape": float(curve_c[jc])},
                         "byRegime": by},
               "width": {"mapeDefault": mape(defW, mW), "mapeAtDepthOracleEta": mape(lnW[:, ja], mW),
                         "mapeAtEtaPlusOffsetEta": mape(lnW[:, jc], mW)}}
        out.append(rec)
json.dump(out, open(HERE / "machcal_oracle.json", "w"), indent=1)
print("| source | kernel | n | D MAPE default (bias) | eta-only oracle: eta / MAPE | offset-only: factor / MAPE | eta+offset: eta / factor / MAPE | W MAPE default -> at depth-oracle eta | regime bias default (n) |")
print("|---|---|---|---|---|---|---|---|---|")
for r in out:
    d, w = r["depth"], r["width"]
    rb = ", ".join(f"{g[:4]} {v['biasDefault']:+.0f}% ({v['n']})" for g, v in d["byRegime"].items())
    print(f"| {r['source']} | {r['kernel']} | {r['n']} | {d['mapeDefault']:.1f} ({d['biasDefault']:+.0f}) | {d['etaOnly']['eta']:.3f} / {d['etaOnly']['mape']:.1f} | {d['offsetOnly']['factor']:.2f} / {d['offsetOnly']['mape']:.1f} | {d['etaPlusOffset']['eta']:.3f} / {d['etaPlusOffset']['factor']:.2f} / {d['etaPlusOffset']['mape']:.1f} | {w['mapeDefault']:.1f} -> {w['mapeAtDepthOracleEta']:.1f} | {rb} |")
