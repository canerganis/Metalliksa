#!/usr/bin/env python3
"""Optional LOCAL cross-check: pycalphad Scheil LAVES fraction vs the literature gamma/Laves estimate.

Analysis script only. Not used by the app, not a test dependency, not run in CI. It changes no
solver, catalogue, golden or evidence label. Both columns are calculations:
  * "literature" = python/lpbf_solidification_segregation.py (DuPont, Robino & Marder 1997
    pseudo-ternary gamma-Nb-C model, Literature estimate (screening));
  * "pycalphad"  = calphad_solver.scheil_gulliver on a TDB the user supplies with --tdb (there is
    NO default path; the repaired MatCalc mc_ni database is held outside git, see
    docs/EXTERNAL_DATA_NOTES.md section 4, and is never committed or shipped).

Compositions (wt%): IN718 at the midpoint of the SMC-045 Table 1 limits for Ni, Cr, Nb, Mo, Ti,
Al, Fe balance, with C = 0 and C = 0.08 (the specification maximum). Minor max-only elements
(Co, Mn, Si, P, S, B, Cu) are left out and stated. IN625 has no literature value in this
repository (constants not verified), so only the pycalphad side is attempted, and a
non-converged or incomplete Scheil path is reported as such, never extrapolated.

Phase amounts from scheil_gulliver are on the pycalphad basis (moles of atoms); the literature
fractions are fractions of the liquid on a mass basis. The comparison is indicative only.

Usage (from python/):
  python -B tools/xcheck_scheil_laves.py --tdb <path/to/mc_ni_repaired.tdb> [--out result.json]
      [--md ../docs/LPBF_SCHEIL_LAVES_<date>.md] [--step 4] [--budget 300]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
from typing import Any, Dict, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import lpbf_solidification_segregation as seg  # noqa: E402

K0 = 273.15


def in718_midpoint(c_wt: float) -> Dict[str, float]:
    lim = seg.COMPOSITION_LIMITS["in718"]["limits"]
    comp = {el: 0.5 * (lo + hi) for el, (lo, hi) in lim.items() if lo is not None and el in
            ("Ni", "Cr", "Nb", "Mo", "Ti", "Al")}
    if c_wt > 0:
        comp["C"] = c_wt
    comp["Fe"] = 100.0 - sum(comp.values())
    return comp


# IN625: no composition authority with cited limits is held in the repository and the alloy 625
# literature constants were not verified, so its composition must be given on the command line
# (--in625 "Ni=..,Cr=..,Mo=..,Nb=..,Fe=..") with its source; nothing is assumed here.


def parse_comp(text: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for part in text.split(","):
        el, val = part.split("=")
        out[el.strip()] = float(val)
    return out


def run_pycalphad(tdb: str, comp_wt: Dict[str, float], step_c: float, budget_s: float) -> Dict[str, Any]:
    import calphad_solver as cs  # read-only use: normalize_composition, scheil_gulliver
    import xcheck_superalloy_table as xs  # Calc / find_boundary / scheil_solidus / PHASES (read-only)
    from pycalphad import Database

    dbf = Database(tdb)
    wt, at = cs.normalize_composition(comp_wt, "wt_pct")
    comps = sorted(e.upper() for e in at) + ["VA"]
    x = {e.upper(): val for e, val in at.items()}
    calc = xs.Calc(dbf, comps, [p for p in xs.PHASES if p in dbf.phases], x)
    rec: Dict[str, Any] = {"compositionWtPct": {k: round(v, 4) for k, v in comp_wt.items()}}
    t0 = time.perf_counter()
    try:
        t_liq, _br, st = xs.find_boundary(calc, 1200 + K0, 2000 + K0, 25.0, lambda f: f >= xs.LIQUID_HI)
    except Exception as exc:  # recorded, never hidden
        rec.update(status="failed", reason=f"liquidus: {type(exc).__name__}: {exc}")
        return rec
    rec["liquidusC"] = None if t_liq is None else round(t_liq - K0, 2)
    rec["liquidusStatus"] = st
    if t_liq is None:
        rec.update(status="failed", reason="no liquidus found")
        return rec
    try:
        sch = xs.scheil_solidus(calc, (t_liq - K0) + 2.0, step_c, budget_s)
    except Exception as exc:
        rec.update(status="failed", reason=f"scheil: {type(exc).__name__}: {exc}")
        return rec
    rec.update(
        status=sch["status"], terminationReason=sch["terminationReason"],
        terminalTemperatureC=sch["terminalTemperatureC"], remainingLiquidFraction=sch["remainingLiquidFraction"],
        phaseAmountsMolesOfAtoms=sch["phaseAmounts"], lavesMolesOfAtoms=sch["phaseAmounts"].get("LAVES"),
        lavesFirstAppearance=(sch.get("firstAppearance") or {}).get("LAVES"),
        massBalanceMaxAbsError=sch["massBalanceMaxAbsError"], stepC=step_c,
        seconds=round(time.perf_counter() - t0, 1),
    )
    return rec


def literature(c_wt: float) -> Dict[str, Any]:
    nb = 0.5 * sum(seg.COMPOSITION_LIMITS["in718"]["limits"]["Nb"])
    ni = seg.CONSTANTS["ni-base"]
    if c_wt <= 0:
        f = seg.scheil_eutectic_fraction(nb, ni["C_Nb_laves"]["value"], ni["k_gamma_Nb"]["value"])
        return {"model": "binary gamma-Nb Scheil (upper bound)", "Nb_wt": nb, "C_wt": 0.0, "fGammaLavesConstituent": round(f, 4)}
    r = seg.pseudo_ternary_path(nb, c_wt, ni)
    return {"model": "D97 pseudo-ternary", "Nb_wt": nb, "C_wt": c_wt, "fGammaLavesConstituent": round(r["fGammaLavesConstituent"], 4),
            "fGammaNbCConstituent": round(r["fGammaNbCConstituent"], 4)}


STEP0 = """## Step 0: database decision (recorded before modelling)

- `calphad_solver.OPEN_TDB_CATALOG` holds no usable Ni-Cr-Fe-Nb-Mo assessment and `system_coverage()` reports
  IN718 and IN625 as not covered. `mc_fecocrnbti.tdb` is a refused test fixture.
- The only open candidate is MatCalc `mc_ni` v2.036 (ODbL 1.0 / DbCL 1.0, has LAVES), held outside git under
  `.orchestra/external-data/` with a syntactic repair. `docs/EXTERNAL_DATA_NOTES.md` section 4: never commit the TDBs,
  review with legal counsel before shipping (the repaired copy is a derivative under ODbL share-alike).
- `docs/XCHECK_SUPERALLOY_TABLE.md`: its Scheil path completes for IN718 but is incomplete for IN625 (equilibrium not
  converged, 4.2 % liquid left at 1170 degC).
- Decision: the shipped path is the published closed-form model (`python/lpbf_solidification_segregation.py`,
  DuPont, Robino & Marder 1997, SAND97-1669C, Literature estimate (screening)). pycalphad Scheil on `mc_ni` is this
  optional local cross-check only: never a default path, never in CI, never in the app. `mc_ni` was not added to the
  catalogue and `calphad_solver.py` was not edited.
"""


def _is_mc_carbide(phase: str) -> bool:
    name = phase.upper()
    return name.startswith("MC") or "NBC" in name or name.startswith("FCC_A1#")


def render_md(result: Dict[str, Any]) -> str:
    lines = [
        f"# LPBF Scheil / Laves cross-check ({result['date']})",
        "",
        "Local analysis run of `python/tools/xcheck_scheil_laves.py`. Both columns are calculations; neither is a "
        "measurement and neither is validated for LPBF. The TDB is not part of the repository.",
        "",
        STEP0,
        "## Run",
        "",
        f"- TDB: `{result['tdbName']}` (sha256 `{result['tdbSha256'][:12]}...`), pycalphad {result['pycalphad']}",
        "- Literature side: `lpbf_solidification_segregation` (DuPont, Robino & Marder 1997, Literature estimate "
        "(screening)); fractions of the liquid, mass basis; C = 0 is the binary upper bound, C = 0.08 the pseudo-ternary "
        "model at the specification maximum.",
        "- pycalphad side: `calphad_solver.scheil_gulliver`; phase amounts in moles of atoms. Indicative comparison only.",
        "- The two columns are not directly comparable: the literature column is the gamma/Laves eutectic-type "
        "constituent (fraction of the liquid, eutectic gamma included), the LAVES column is the amount of the LAVES "
        "phase alone, so the constituent is necessarily larger than the phase amount for the same path.",
        "- IN718 composition: midpoints of SMC-045 Table 1 for Ni, Cr, Nb, Mo, Ti, Al, Fe balance; minor max-only "
        f"elements left out: {', '.join(result.get('omittedMinorElements', []))}.",
        "",
        "| Case | Literature gamma/Laves constituent (fraction of liquid) | pycalphad Scheil status | LAVES (mol atoms) | Other solids (mol atoms) | Terminal T (degC) | Remaining liquid |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in result["cases"]:
        lit = case.get("literature")
        py = case["pycalphad"]
        others = ", ".join(f"{k} {v}" for k, v in sorted((py.get("phaseAmountsMolesOfAtoms") or {}).items())
                           if k != "LAVES") or "-"
        status = py.get("status") or "-"
        if status != "complete":
            status += f" ({py.get('terminationReason') or py.get('reason')})"
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            case["name"], "n/a (constants not verified)" if lit is None else lit["fGammaLavesConstituent"], status,
            py.get("lavesMolesOfAtoms") if py.get("lavesMolesOfAtoms") is not None else "none formed",
            others, py.get("terminalTemperatureC"), py.get("remainingLiquidFraction")))
    no_mc = [c["name"] for c in result["cases"]
             if (c.get("literature") or {}).get("C_wt", 0) > 0
             and not any(_is_mc_carbide(k) for k in (c["pycalphad"].get("phaseAmountsMolesOfAtoms") or {}))]
    if no_mc:
        lines += ["", "No MC carbide formed in the pycalphad path for: " + "; ".join(no_mc) + ". The pseudo-ternary "
                      "model removes Nb into gamma/NbC at that carbon level, so the comparison in that row is doubtful."]
    if not any(c["name"].startswith("IN625") for c in result["cases"]):
        lines += ["", "IN625 was not run: the repository holds no cited IN625 composition limits and its literature "
                      "constants are not verified (the segregation block reports IN625 as unavailable)."]
    lines += ["", "Incomplete or non-converged paths are reported as they stopped; nothing is extrapolated.", ""]
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tdb", required=True, help="local TDB path (no default; never committed)")
    ap.add_argument("--in625", default=None, help='optional IN625 composition "Ni=..,Cr=..,..." (wt%%) with its source')
    ap.add_argument("--step", type=float, default=4.0)
    ap.add_argument("--budget", type=float, default=300.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--md", default=None)
    args = ap.parse_args(argv)
    import hashlib

    import pycalphad

    with open(args.tdb, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    cases = []
    for c_wt in (0.0, 0.08):
        comp = in718_midpoint(c_wt)
        cases.append({"name": f"IN718 midpoint, C={c_wt}", "literature": literature(c_wt),
                      "pycalphad": run_pycalphad(args.tdb, comp, args.step, args.budget)})
    if args.in625:
        cases.append({"name": "IN625 (user composition)", "literature": None,
                      "pycalphad": run_pycalphad(args.tdb, parse_comp(args.in625), args.step, args.budget)})
    result = {"date": _dt.date.today().isoformat(), "tdbName": os.path.basename(args.tdb), "tdbSha256": sha,
              "pycalphad": pycalphad.__version__, "cases": cases,
              "omittedMinorElements": ["Co", "Mn", "Si", "P", "S", "B", "Cu"]}
    text = json.dumps(result, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    else:
        print(text)
    if args.md:
        with open(args.md, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render_md(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
