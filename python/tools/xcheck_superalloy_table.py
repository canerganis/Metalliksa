#!/usr/bin/env python3
"""Cross-check liquidus / solidus of our CALPHAD stack against the Zenodo 22901717 table.

Analysis script only. It does NOT change any solver, golden or evidence label.

Reference: Zenodo 22901717 ``Superalloys.xlsx`` (CC BY 4.0), 555 Ni/Co/Fe superalloys, values
computed with Thermo-Calc TCNI12 (a calculation, not a measurement).
Ours: pycalphad on the repaired MatCalc mc_ni database (a different assessment; the repair
loses the BCC_B2 order-disorder contribution, so BCC_B2 is excluded from the phase list).

Method per alloy (all temperatures in degrees Celsius, table basis verified: columns are mass
fractions that sum to 1; the table headers give degrees Celsius):
  * composition = the table's element columns (mass fraction) -> mole fractions via the solver's
    own ``normalize_composition`` (so atomic weights are the project's);
  * equilibrium liquidus = lowest T with liquid >= 99.9 % ; solidus = lowest T with liquid > 0.1 %
    (the same definitions as ``derive_critical_temperatures``), coarse grid then multi-section
    refinement to the stated tolerance;
  * Scheil solidus = terminal temperature of ``calphad_solver.scheil_gulliver`` (liquid < 0.1 %).

Usage (from python/):
  python -B tools/xcheck_superalloy_table.py --xlsx <Superalloys.xlsx> --tdb <mc_ni_repaired.tdb> \
      --out <result.json> [--alloys "Inconel 718,Inconel 625"] [--no-scheil]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import warnings
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import numpy as np  # noqa: E402

warnings.filterwarnings("ignore")

import calphad_solver as cs  # noqa: E402  (read-only use: normalize_composition, scheil_gulliver)
from pycalphad import Database, equilibrium, variables as v  # noqa: E402

K0 = 273.15
ELEMENT_COLUMNS = ["Al", "B", "C", "Co", "Cr", "Fe", "Hf", "Mo", "Nb", "Ni", "Re", "Ru", "Si",
                   "Ta", "Ti", "V", "W", "Zr", "Cu", "Mn"]
# Phases kept: no BCC_B2 (ordering contribution lost in the repair). NIAL is a separate B2-type
# phase of the same database and is excluded for the same reason. Oxides, sulfides, nitrides,
# borides and gas are irrelevant for these alloys (no O, S, N in the table compositions).
PHASES = ["LIQUID", "FCC_A1", "BCC_A2", "HCP_A3", "GAMMA_PRIME", "DELTA", "SIGMA", "MU_PHASE",
          "LAVES", "P_PHASE", "R_PHASE", "M23C6", "M6C", "M7C3", "M3C2", "ETA",
          "CRB", "CR2B", "CR5B3", "M2B", "MOB", "MOB2", "NBB", "NB3B2", "NB5B6", "TIB", "TIB2", "TI3B4",
          "NI5HF", "NI7HF2", "NITI2", "NI2CR", "G_PHASE", "CHI_A12", "DIAMOND_A4", "GRAPHITE"]
LIQUID_HI = 0.999
LIQUID_LO = 0.001


def log(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def read_table(xlsx: str):
    import pandas as pd
    df = pd.read_excel(xlsx)
    return df


def row_composition(row) -> Dict[str, float]:
    return {e: float(row[e]) * 100.0 for e in ELEMENT_COLUMNS if float(row[e]) > 0.0}


class Calc:
    """One compiled pycalphad Workspace per alloy; every call re-uses it (same condition keys)."""

    def __init__(self, dbf, comps: List[str], phases: List[str], x: Dict[str, float]):
        from pycalphad import Workspace
        self.dbf, self.comps, self.phases = dbf, comps, phases
        self.x = x  # mole fractions by upper-case symbol
        self.dep = max(x, key=lambda k: x[k])  # dependent component (the base element)
        self.keys = [el for el in x if el != self.dep]
        conds = self._conds([1800.0 + K0], {el: x[el] for el in self.keys})
        self.ws = Workspace(dbf, comps, phases, conds)

    def _conds(self, temps_k, xs: Dict[str, float]):
        conds = {v.T: list(temps_k), v.P: 101325, v.N: 1}
        for el in self.keys:
            conds[v.X(el)] = float(xs[el])
        return conds

    def point(self, temps_k: List[float], xs: Optional[Dict[str, float]] = None):
        self.ws.conditions = self._conds(temps_k, xs or self.x)
        return self.ws.eq.get_dataset()

    def liquid_fractions(self, temps_k: List[float]) -> List[Optional[float]]:
        eq = self.point(temps_k)
        n = len(temps_k)
        ph = np.asarray(eq.Phase.values).reshape(n, -1)
        npv = np.asarray(eq.NP.values).reshape(n, -1)
        gm = np.asarray(eq.GM.values).reshape(n)
        out: List[Optional[float]] = []
        for i in range(n):
            if not math.isfinite(float(gm[i])) or not np.any(np.isfinite(npv[i])):
                out.append(None)
                continue
            liq = 0.0
            for p, a in zip(ph[i], npv[i]):
                if str(p) == "LIQUID" and np.isfinite(a):
                    liq += float(a)
            out.append(liq)
        return out


def find_boundary(calc: Calc, t_lo_k: float, t_hi_k: float, step_k: float, pred, tol_k: float = 0.5):
    """Lowest T on [t_lo, t_hi] for which pred(liquid) is true (pred monotone in T assumed).
    Returns (value_k_mid, bracket, status)."""
    temps = list(np.arange(t_lo_k, t_hi_k + 1e-9, step_k))
    if t_hi_k - temps[-1] > 1e-6:
        temps.append(t_hi_k)  # the upper end must be probed: a freezing range narrower than step_k fits between grid points
    liq = calc.liquid_fractions(temps)
    if any(x is None for x in liq):
        bad = [round(t - K0) for t, x in zip(temps, liq) if x is None]
        nonconv = len(bad)
    else:
        nonconv = 0
    flags = [(x is not None and pred(x)) for x in liq]
    if not any(flags):
        return None, None, "predicate never true in range"
    first = flags.index(True)
    if first == 0:
        return None, None, "predicate already true at the lower end of the range"
    lo, hi = temps[first - 1], temps[first]
    if liq[first - 1] is None:
        return None, None, "non-converged point next to the boundary"
    while hi - lo > tol_k:
        sub = [lo + (hi - lo) * k / 9.0 for k in range(1, 9)]
        sl = calc.liquid_fractions(sub)
        if any(x is None for x in sl):
            return None, [lo, hi], "non-converged point during refinement"
        f = [pred(x) for x in sl]
        if any(f):
            j = f.index(True)
            hi = sub[j]
            lo = sub[j - 1] if j > 0 else lo
        else:
            lo = sub[-1]
    status = "ok" if nonconv == 0 else f"ok ({nonconv} non-converged grid points elsewhere)"
    return 0.5 * (lo + hi), [lo, hi], status


def scheil_solidus(calc: Calc, start_c: float, step_c: float, time_budget_s: float):
    def run_point(t_c: float, x_liq: Dict[str, float]):
        eq = calc.point([t_c + K0], {el.upper(): val for el, val in x_liq.items()})
        ph = np.asarray(eq.Phase.values).reshape(-1)
        npv = np.asarray(eq.NP.values).reshape(-1)
        xv = np.asarray(eq.X.values).reshape(len(ph), -1)
        gm = float(np.asarray(eq.GM.values).reshape(-1)[0])
        if not math.isfinite(gm):
            return None
        cnames = [str(c) for c in eq.component.values]
        liquid = 0.0
        liquid_x: Dict[str, float] = {}
        amounts: Dict[str, float] = {}
        for i, (p, a) in enumerate(zip(ph, npv)):
            p = str(p)
            if p == "" or not np.isfinite(a):
                continue
            if p == "LIQUID":
                liquid += float(a)
                liquid_x = {c: float(xv[i][k]) for k, c in enumerate(cnames) if c != "VA"}
            else:
                amounts[p] = amounts.get(p, 0.0) + float(a)
        if liquid > 0 and not liquid_x:
            return None
        return {"liquid": liquid, "liquidX": liquid_x, "phases": amounts}

    comps_nova = [c for c in calc.comps if c != "VA"]
    x0 = {c: calc.x[c] for c in comps_nova}
    return cs.scheil_gulliver(run_point, start_c, x0, step_c=step_c, max_steps=800,
                              time_budget_s=time_budget_s)


def run_alloy(dbf, row, do_scheil: bool, scheil_step_c: float) -> Dict[str, Any]:
    name = str(row["Alloy"])
    comp_wt = row_composition(row)
    rec: Dict[str, Any] = {
        "alloy": name, "family": str(row["Family"]), "compositionWtPct": {k: round(val, 4) for k, val in comp_wt.items()},
        "tableSolidusC": float(row["Solidus Temp (∘C)"]), "tableLiquidusC": float(row["Liquidus Temp (∘C)"]),
        "tableFreezingRangeK": float(row["Freezing Range"]),
    }
    wt, at = cs.normalize_composition(comp_wt, "wt_pct")
    comps = sorted(e.upper() for e in at) + ["VA"]
    x = {e.upper(): val for e, val in at.items()}
    calc = Calc(dbf, comps, [p for p in PHASES if p in dbf.phases], x)
    t0 = time.perf_counter()
    try:
        t_liq, br_l, st_l = find_boundary(calc, 1200 + K0, 2000 + K0, 25.0, lambda f: f >= LIQUID_HI)
        # solidus search range must lie below the liquidus
        s_hi = (t_liq if t_liq else 2000 + K0)
        t_sol, br_s, st_s = find_boundary(calc, 1000 + K0, s_hi, 25.0, lambda f: f > LIQUID_LO)
    except Exception as exc:  # recorded, never hidden
        rec.update(status="failed", reason=f"{type(exc).__name__}: {exc}")
        return rec
    rec["ourLiquidusC"] = None if t_liq is None else round(t_liq - K0, 2)
    rec["ourSolidusC"] = None if t_sol is None else round(t_sol - K0, 2)
    rec["liquidusStatus"], rec["solidusStatus"] = st_l, st_s
    rec["liquidusBracketC"] = None if br_l is None else [round(b - K0, 2) for b in br_l]
    rec["solidusBracketC"] = None if br_s is None else [round(b - K0, 2) for b in br_s]
    rec["equilibriumSeconds"] = round(time.perf_counter() - t0, 1)
    if do_scheil and t_liq is not None:
        t1 = time.perf_counter()
        try:
            sch = scheil_solidus(calc, (t_liq - K0) + 2.0, scheil_step_c, 120.0)
            rec["scheilStatus"] = sch["status"]
            rec["scheilTerminationReason"] = sch["terminationReason"]
            rec["scheilTerminalC"] = sch["terminalTemperatureC"]
            rec["scheilTerminalBracketC"] = sch["terminalBracketC"]
            rec["scheilRemainingLiquid"] = sch["remainingLiquidFraction"]
            rec["scheilStepC"] = scheil_step_c
            rec["scheilMassBalanceMaxAbsError"] = sch["massBalanceMaxAbsError"]
            rec["scheilFirstSolidPhases"] = (sch.get("firstSolid") or {}).get("phases")
        except Exception as exc:
            rec["scheilStatus"] = "failed"
            rec["scheilReason"] = f"{type(exc).__name__}: {exc}"
        rec["scheilSeconds"] = round(time.perf_counter() - t1, 1)
    rec["status"] = "computed" if t_liq is not None and t_sol is not None else "incomplete"
    return rec


def dump(args, results, skipped) -> None:
    import pycalphad
    out = {
        "pycalphad": pycalphad.__version__, "tdb": os.path.basename(args.tdb), "xlsx": os.path.basename(args.xlsx),
        "phases": PHASES, "liquidDefinition": {"liquidusFraction>=": LIQUID_HI, "solidusFraction>": LIQUID_LO},
        "results": results, "skipped": skipped,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)


def summarize(paths: List[str]) -> str:
    """Markdown table + statistics from one or more result JSON files (no pycalphad needed)."""
    rows: List[Dict[str, Any]] = []
    for pth in paths:
        with open(pth, encoding="utf-8") as fh:
            rows += json.load(fh)["results"]
    lines = ["| Alloy | table liq | table sol | our liq (eq) | our sol (eq) | our Scheil end | d_liq | d_sol | d_Scheil |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    stats: Dict[str, List[float]] = {"liq": [], "sol": [], "sch": []}
    for r in rows:
        if r.get("status") != "computed":
            lines.append(f"| {r['alloy']} | {r['tableLiquidusC'] - K0:.0f} | {r['tableSolidusC'] - K0:.0f} | not computed: {r.get('reason') or r.get('liquidusStatus') or r.get('status')} | | | | | |")
            continue
        tl, ts = r["tableLiquidusC"] - K0, r["tableSolidusC"] - K0  # table numbers read as kelvin
        dl, ds = r["ourLiquidusC"] - tl, r["ourSolidusC"] - ts
        stats["liq"].append(dl)
        stats["sol"].append(ds)
        sch = "n/a"
        dsch = "n/a"
        if r.get("scheilStatus") == "complete":
            sch = f"{r['scheilTerminalC']:.0f}"
            dsc = r["scheilTerminalC"] - ts
            stats["sch"].append(dsc)
            dsch = f"{dsc:+.0f}"
        elif r.get("scheilStatus"):
            sch = f"incomplete ({r.get('scheilTerminationReason')}, {r.get('scheilRemainingLiquid')} liquid left at {r.get('scheilTerminalC')})"
        lines.append(f"| {r['alloy']} | {tl:.0f} | {ts:.0f} | {r['ourLiquidusC']:.0f} | {r['ourSolidusC']:.0f} | {sch} | {dl:+.0f} | {ds:+.0f} | {dsch} |")
    lines.append("")
    lines.append("Differences are ours minus table, table read as kelvin and converted to deg C (see the unit finding).")
    for key, label in (("liq", "liquidus"), ("sol", "solidus"), ("sch", "Scheil end vs table solidus")):
        d = stats[key]
        if d:
            lines.append(f"- {label}: n={len(d)}, mean bias {sum(d) / len(d):+.1f} K, MAE {sum(abs(x) for x in d) / len(d):.1f} K, "
                         f"max |error| {max(abs(x) for x in d):.1f} K")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summarize", nargs="+", metavar="RESULT_JSON", help="print markdown summary of result files and exit")
    ap.add_argument("--xlsx")
    ap.add_argument("--tdb")
    ap.add_argument("--out")
    ap.add_argument("--alloys", default="", help="comma list of table 'Alloy' names; default: all computable")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--no-scheil", action="store_true")
    ap.add_argument("--scheil-step", type=float, default=4.0)
    args = ap.parse_args()
    if args.summarize:
        print(summarize(args.summarize))
        return 0
    if not (args.xlsx and args.tdb and args.out):
        ap.error("--xlsx, --tdb and --out are required unless --summarize is used")

    df = read_table(args.xlsx)
    dbf = Database(args.tdb)
    db_elements = {e.upper() for e in dbf.elements if e.upper() not in ("VA", "/-")}
    wanted = [a.strip() for a in args.alloys.split(",") if a.strip()]
    results: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    seen = set()
    for _, row in df.iterrows():
        name = str(row["Alloy"])
        if wanted and name not in wanted:
            continue
        if name in seen:
            skipped.append({"alloy": name, "reason": "duplicate name in table (first row used)"})
            continue
        seen.add(name)
        comp = row_composition(row)
        missing = sorted(e for e in comp if e.upper() not in db_elements)
        if missing:
            skipped.append({"alloy": name, "family": str(row["Family"]), "reason": "element(s) not in database: " + ",".join(missing)})
            continue
        if args.max and len(results) >= args.max:
            break
        log(f"[xcheck] {name}")
        results.append(run_alloy(dbf, row, not args.no_scheil, args.scheil_step))
        log(f"   -> liq {results[-1].get('ourLiquidusC')} sol {results[-1].get('ourSolidusC')} "
            f"scheil {results[-1].get('scheilTerminalC')} (table {results[-1]['tableLiquidusC']}/{results[-1]['tableSolidusC']})")
        dump(args, results, skipped)  # incremental, so a long run never loses finished alloys

    dump(args, results, skipped)
    log(f"[xcheck] wrote {args.out}: {len(results)} computed rows, {len(skipped)} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
