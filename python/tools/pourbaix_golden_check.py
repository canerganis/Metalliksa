#!/usr/bin/env python3
"""Exact check of a re-blessed ``pourbaix_solver`` document against the independent oracle.

Used by ``capture_phase6a_golden.documented_change_violation`` for the rows listed in
``EXPECTED_DOCUMENTED_VALUE_CHANGES["pourbaix_solver"]`` (WP-E replaced the hand-written rule
tree by a minimum-Gibbs-energy equilibrium, so the d33b6f5 golden differs structurally).

``document_problems(old_stdout, new_stdout)`` recomputes every documented section of the new
document from ``tools/pourbaix_oracle.py`` (its own species numbers, constants and brute-force
argmin/polygon code) and returns ``{section: [problem, ...]}``; a documented drift row is accepted
only when the section it lives in has no problem. What is compared:

- categories, dominant species ids and formulas, ids, phases, roles, stoichiometry: EQUAL;
- boundary and polygon coordinates, line intercept/slope: <= COORD_TOL (1e-4 V, pH units for the
  vertical lines and the pH coordinate); this is the only tolerance, and it is the spec's;
- texts: EQUAL to the engine's fixed category text table (``pourbaix_solver.CATEGORY_TEXTS``,
  ``CATEGORY_MITIGATION``, the water labels) or to the literal strings pinned below;
- derived numbers that are rounded in the document (``deltaE_Immunity_V``, ``potential_V_SHE``,
  water lines, ``standardE0_V``): EQUAL after the same rounding (the oracle's CODATA-printed R and F
  differ from the exact SI constants by 3e-11 relative, far below the rounding step);
- the species table: stoichiometry exact, ``dfG_kJ_mol`` equal to the oracle within float
  representation (1e-6 kJ/mol = 1 mJ/mol: the oracle writes the atlas values as cal/mol * 4.184 and uses CODATA-printed F in the derived FeO4 2- row);
- the old value of every row: equal to the d33b6f5 golden (checked by the caller);
- dataValidity (engine v5): candidate-set ids and members equal the oracle's own CANDIDATES (rebuilt from the
  primary numbers), each withheld region's vertices within COORD_TOL of the oracle's polygon, the free pH
  windows recomputed here from those oracle polygons and the oracle's water lines, every grid cell's and
  point's withheld flag equal to the oracle's brute-force ``withheld_hits``.

Nothing here widens the generic step-(b) bound for any other row.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

TOOLS_DIR = Path(__file__).resolve().parent
PYTHON_DIR = TOOLS_DIR.parent
for _p in (str(PYTHON_DIR), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pourbaix_oracle as oracle  # noqa: E402  (independent oracle, python/tools)

COORD_TOL = 1e-4  # V (pH units for the pH coordinate): boundary / polygon coordinates
DFG_TOL_KJ = 1e-6  # kJ/mol: float representation of cal -> kJ and the 3e-11 R/F difference of the Latimer-derived FeO4 2- row
NUDGE_V = 3 * COORD_TOL  # V (or pH): side probes of a boundary midpoint (beyond the coordinate bound)

SECTIONS = ("analyticalBoundaries", "chloridePittingBoundary", "dataValidity", "domains", "engine",
            "experimentalOverlay", "model", "parameters", "speciesInventory", "speciesTable", "stabilityFieldGrid",
            "temperatureStatus", "waterStabilityLines")
ENGINE_ID = "pourbaix-gibbs-25c-v6"
# Withheld rows recorded as excluded by scope (V2) although they belong to a candidate set (the others are V3).
SCOPE_EXCLUDED_CANDIDATES = {"TiH2"}

# Reference-electrode offsets (V vs SHE) of the d33b6f5 solver; unchanged by WP-E.
_OFFSETS = {"SHE": 0.000, "SCE": 0.241, "Ag/AgCl (3M KCl)": 0.207, "Ag/AgCl (Sat KCl)": 0.197,
            "CSE": 0.316, "MMS": 0.640}
_CHLORIDE_MOLAR_MASS = 35.453
_PITTING_NOTE = ("No sourced generic pitting potential exists for a pure element (Epit depends on alloy, "
                 "surface and test method); the equilibrium contains no chloro-complexes.")
_PITTING_RISK = "Not assessed (no sourced pitting potential)"
_TEMPERATURE_NOTE = "No temperature extrapolation: the table has no consistent entropies or heat capacities."
_IMMUNITY_MITIGATION_BELOW = ("E is below water line a: hydrogen evolution is thermodynamically possible; "
                              "hydrogen uptake can matter for susceptible alloys.")
_IMMUNITY_MITIGATION_INSIDE = ("The metal is the equilibrium phase at this point; the map makes no "
                               "statement about rates or protection.")
_RISK_KEYS = ("Immune", "Stable Passivity", "Caution", "Pitting Hazard", "Severe Corrosion", "High Risk")
_KEY_BY_ROLE = {"metal": "immunity", "cation": "corrosion_acid", "oxide": "passivation",
                "anion_low": "corrosion_alkaline", "anion_high": "transpassive"}


def _engine():
    import pourbaix_solver as eng
    import pourbaix_species_25c as table
    import physical_constants as pc
    return eng, table, pc


def _close(a: float, b: float, tol: float) -> bool:
    return isinstance(a, (int, float)) and not isinstance(a, bool) and abs(a - b) <= tol


def _exact(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b


def _dedupe(poly):
    out = []
    for p in poly:
        if not out or abs(p[0] - out[-1][0]) > 1e-9 or abs(p[1] - out[-1][1]) > 1e-9:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) <= 1e-9 and abs(out[0][1] - out[-1][1]) <= 1e-9:
        out.pop()
    return out


def _match_vertices(engine_pts, oracle_pts) -> Optional[str]:
    """Every engine vertex has an oracle vertex within COORD_TOL and vice versa (same counts)."""
    if len(engine_pts) != len(oracle_pts):
        return f"{len(engine_pts)} vertices, oracle {len(oracle_pts)}"
    for a in engine_pts:
        if not any(abs(a[0] - b[0]) <= COORD_TOL and abs(a[1] - b[1]) <= COORD_TOL for b in oracle_pts):
            return f"vertex ({a[0]:.6f}, {a[1]:.6f}) has no oracle vertex within {COORD_TOL}"
    for b in oracle_pts:
        if not any(abs(a[0] - b[0]) <= COORD_TOL and abs(a[1] - b[1]) <= COORD_TOL for a in engine_pts):
            return f"oracle vertex ({b[0]:.6f}, {b[1]:.6f}) missing in the document"
    return None


def _convex_simple(poly) -> bool:
    """Vertices in order form a simple convex polygon: all turns the same way and one full revolution."""
    n = len(poly)
    if n < 3:
        return False
    signs = []
    total = 0.0
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        cx, cy = poly[(i + 2) % n]
        cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if abs(cross) > 1e-12:
            signs.append(cross > 0)
        total += math.atan2(cross, (bx - ax) * (cx - bx) + (by - ay) * (cy - by))
    return len(set(signs)) == 1 and abs(abs(total) - 2 * math.pi) < 1e-6


def _terms(side: str):
    out = []
    for term in side.split(" + "):
        m = re.fullmatch(r"(\d*)(.+)", term)
        out.append((int(m.group(1) or 1), m.group(2)))
    return out


def _equation_problem(eq: Any, row_a: Dict[str, Any], row_b: Dict[str, Any]) -> Optional[str]:
    """Independent balance check of ``A + .. <=> B + ..`` (metal, O, H and charge), A left, B right."""
    if not isinstance(eq, str) or eq.count(" ⇌ ") != 1:
        return f"equation {eq!r} is not 'left ⇌ right'"
    left, right = (_terms(s) for s in eq.split(" ⇌ "))
    bookkeeping = {"H₂O": (0, 1, 2, 0), "H⁺": (0, 0, 1, 1), "e⁻": (0, 0, 0, -1)}  # metal, O, H, charge
    species = {row_a["formula"]: (row_a["x"], row_a["o"], row_a["h"], row_a["z"]),
               row_b["formula"]: (row_b["x"], row_b["o"], row_b["h"], row_b["z"])}
    totals = []
    for side, expected in ((left, row_a["formula"]), (right, row_b["formula"])):
        if sum(1 for _, label in side if label == expected) != 1:
            return f"equation {eq!r} lacks {expected!r} on the expected side"
        t = [0, 0, 0, 0]
        for n, label in side:
            vec = species.get(label) or bookkeeping.get(label)
            if vec is None:
                return f"equation {eq!r}: unknown term {label!r}"
            for i in range(4):
                t[i] += n * vec[i]
        totals.append(t)
    if totals[0] != totals[1]:
        return f"equation {eq!r} is not balanced (metal, O, H, charge): {totals[0]} vs {totals[1]}"
    return None


def _oracle_boundaries(element: str, log_a: float):
    """(a, b) -> (end1, end2) shared polygon edges of the oracle (names in table order)."""
    c = oracle.coeffs(element, log_a)
    polys = oracle.polygons(element, log_a)
    names = list(c)
    out = {}
    for ia in range(len(names)):
        for ib in range(ia + 1, len(names)):
            a, b = names[ia], names[ib]
            if a not in polys:
                continue
            on = []
            for v in polys[a][0]:
                ga = c[a][0] + c[a][1] * v[0] + c[a][2] * v[1]
                gb = c[b][0] + c[b][1] * v[0] + c[b][2] * v[1]
                if abs(ga - gb) < 1e-3:  # J/mol, float noise of the clipping only
                    on.append(v)
            best = None
            for i in range(len(on)):
                for j in range(i + 1, len(on)):
                    d = math.hypot(on[i][0] - on[j][0], on[i][1] - on[j][1])
                    if d > 1e-9 and (best is None or d > best[0]):
                        best = (d, on[i], on[j])
            if best:
                out[(a, b)] = (best[1], best[2])
    return out


def _metal_boundary_E(element: str, log_a: float, pH: float) -> Optional[float]:
    c = oracle.coeffs(element, log_a)
    bound = None
    for k, (c0, cp, ce) in c.items():
        if ce < 0:  # n > 0: g_k >= 0 (metal) <=> E <= (c0 + cp pH) / (-ce)
            e = (c0 + cp * pH) / (-ce)
            bound = e if bound is None else min(bound, e)
    return bound


def _oracle_free_windows(element: str, log_a: float) -> List[List[float]]:
    """pH intervals free of withheld regions inside the water window, from the oracle's polygons."""
    k = oracle.LN10 * oracle.R * oracle.T / oracle.F
    e0 = oracle.water_lines(0.0)[1]
    blocked = []
    for _, _, poly in oracle.withheld_polygons(element, log_a):
        for a, b, c in ((-k, -1.0, 0.0), (k, 1.0, -e0)):
            new = []
            for i in range(len(poly)):
                p_, q_ = poly[i], poly[(i + 1) % len(poly)]
                fp, fq = c + a * p_[0] + b * p_[1], c + a * q_[0] + b * q_[1]
                if fp <= 0:
                    new.append(p_)
                if (fp < 0 < fq) or (fq < 0 < fp):
                    t = fp / (fp - fq)
                    new.append((p_[0] + t * (q_[0] - p_[0]), p_[1] + t * (q_[1] - p_[1])))
            poly = new
            if not poly:
                break
        if poly and 0.5 * abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                                  for i in range(len(poly)))) > 1e-9:
            blocked.append((min(q[0] for q in poly), max(q[0] for q in poly)))
    blocked.sort()
    free, start = [], oracle.BOX[0]
    for lo, hi in blocked:
        if lo > start:
            free.append([start, lo])
        start = max(start, hi)
    if start < oracle.BOX[1]:
        free.append([start, oracle.BOX[1]])
    return free


def document_problems(old_stdout: Dict[str, Any], new_stdout: Dict[str, Any]) -> Dict[str, List[str]]:
    """Recompute the documented sections of ``new_stdout`` from the oracle; {section: [problems]}."""
    eng, table, pc = _engine()
    problems: Dict[str, List[str]] = {s: [] for s in SECTIONS}
    try:
        element = old_stdout["element"]
        log_a = old_stdout["parameters"]["ionActivity_log10"]
        chloride_ppm = old_stdout["parameters"]["chlorideConcentration_ppm"]
        requested_t = old_stdout["parameters"]["temperature_C"]
        old_points = old_stdout["experimentalOverlay"]["points"]
    except (KeyError, TypeError):
        for s in SECTIONS:
            problems[s].append("the d33b6f5 golden lacks the element/parameters/points the check needs")
        return problems
    if element not in oracle.DATA:
        for s in SECTIONS:
            problems[s].append(f"the oracle has no data for element {element!r}")
        return problems
    data = oracle.dataset(element)
    names = list(data["sp"])
    texts = eng.CATEGORY_TEXTS

    # ---- speciesTable -------------------------------------------------------------------
    p = problems["speciesTable"]
    st = new_stdout.get("speciesTable")
    engine_rows = table.species_rows(element)
    rows: List[Dict[str, Any]] = []
    if not isinstance(st, dict) or not isinstance(st.get("species"), list):
        p.append("speciesTable.species missing")
    else:
        rows = st["species"]
        if len(rows) != len(names):
            p.append(f"{len(rows)} species rows, oracle {len(names)}")
        for row, name in zip(rows, names):
            x, o, h, z, g, phase, role = data["sp"][name]
            for key, want in (("id", name), ("x", x), ("o", o), ("h", h), ("z", z), ("phase", phase),
                              ("role", role), ("category", oracle.CATEGORY[role])):
                if not _exact(row.get(key), want):
                    p.append(f"{name}.{key}: {row.get(key)!r} != {want!r}")
            if not _close(row.get("dfG_kJ_mol"), g, DFG_TOL_KJ):
                p.append(f"{name}.dfG_kJ_mol: {row.get('dfG_kJ_mol')!r} != oracle {g!r}")
            if row.get("verification") not in ("V1", "V2"):
                p.append(f"{name}.verification {row.get('verification')!r} is not a verified level")
            # formula, source, verification level and evidence are provenance text: they must equal the engine's
            # species table exactly (a forged level, rename or evidence text is not a documented value change)
            engine_row = engine_rows[names.index(name)] if len(engine_rows) == len(names) else {}
            for key in ("formula", "source", "verification", "evidence", "category"):
                if not isinstance(row.get(key), str) or not row[key]:
                    p.append(f"{name}.{key} is empty")
                elif not _exact(row.get(key), engine_row.get(key)):
                    p.append(f"{name}.{key} differs from the engine's species table: {row.get(key)!r}")
            if set(row) != set(engine_row):
                p.append(f"{name}: keys {sorted(row)} != the engine's {sorted(engine_row)}")
        if not _close(st.get("waterDfG_kJ_mol"), data["H2O"], DFG_TOL_KJ):
            p.append(f"waterDfG_kJ_mol {st.get('waterDfG_kJ_mol')!r} != oracle {data['H2O']!r}")
        set_id, _, set_note = table.ELEMENT_SET[element]
        if st.get("sourceSet") != set_id or st.get("sourceSetNote") != set_note:
            p.append("sourceSet / sourceSetNote differ from the engine's table")
        if st.get("schema") != table.SCHEMA:
            p.append(f"schema {st.get('schema')!r} != {table.SCHEMA!r}")
        withheld = oracle.WITHHELD.get(element, {})
        # Elements with a plain withheld dict (Ni): the keys are the ids (V3). Al (WP-Al): the rejected
        # atlas rows that are not in the served set keep an "(atlas)" id (V3), followed by the excluded
        # metastable phases of the same set (V2, tools/pourbaix_oracle.AL_EXCLUDED). Cr, Mo, Ti (v5): the
        # members of the oracle's candidate sets in set order (V3; TiH2 V2, excluded by scope), then the
        # oracle's EXCLUDED rows (V2).
        want_level = {}
        if element in oracle.CANDIDATES:
            want_ids = [k for members in oracle.CANDIDATES[element].values() for k in members]
            want_level = {k: ("V2" if k in SCOPE_EXCLUDED_CANDIDATES else "V3") for k in want_ids}
            want_ids += list(oracle.EXCLUDED.get(element, {}))
            want_level.update({k: "V2" for k in oracle.EXCLUDED.get(element, {})})
        elif "sp" not in withheld:
            want_ids = [k for k in withheld]
            want_level = {k: "V3" for k in want_ids}
        else:
            want_ids = [f"{k}(atlas)" for k in withheld["sp"] if k not in data["sp"]]
            want_level = {i: "V3" for i in want_ids}
            if element == "Al":
                want_ids += list(oracle.AL_EXCLUDED)
                want_level.update({k: "V2" for k in oracle.AL_EXCLUDED})
        got = st.get("withheldSpecies")
        if not isinstance(got, list) or [w.get("id") for w in got] != want_ids:
            p.append(f"withheldSpecies {got!r} != oracle withheld {want_ids!r}")
        elif any(w.get("verification") != want_level[w["id"]] or not w.get("reason") for w in got):
            p.append("a withheld species is not recorded with its verification level (V3 rejected/unverified, V2 excluded) and a reason")
        else:
            engine_withheld = [{"id": r[0], "verification": r[10], "reason": r[11]}
                               for r in table.WITHHELD_SPECIES.get(element, ())]
            if got != engine_withheld:
                p.append("withheldSpecies rows (id, level, reason text) differ from the engine's table")
    id_of = {name: rows[i].get("id") for i, name in enumerate(names) if i < len(rows)}
    formula_of = {name: rows[i].get("formula") for i, name in enumerate(names) if i < len(rows)}
    name_of_id = {v: k for k, v in id_of.items()}
    if p:
        # The remaining sections are identified through this table; stop here for this document.
        for s in SECTIONS:
            if s != "speciesTable":
                problems[s].append("speciesTable does not match the oracle; section not verified")
        return problems

    # ---- stabilityFieldGrid ------------------------------------------------------------
    p = problems["stabilityFieldGrid"]
    grid = new_stdout.get("stabilityFieldGrid")
    if not isinstance(grid, list) or len(grid) != 15 * 21:
        p.append(f"grid has {len(grid) if isinstance(grid, list) else grid!r} cells, expected 315")
    else:
        k = 0
        for p_idx in range(15):
            for e_idx in range(21):
                ph, e = float(p_idx), -2.0 + e_idx * 0.2
                cell = grid[k]
                k += 1
                sp = oracle.dominant(element, ph, e, log_a)
                role = data["sp"][sp][6]
                cat = oracle.CATEGORY[role]
                her, oer = oracle.water_lines(ph)
                inside = her <= e <= oer
                want = {"pH": ph, "E_V_SHE": round(e, 2), "dominantSpeciesId": id_of[sp],
                        "dominantSpecies": formula_of[sp], "category": cat,
                        "regime": cat if inside else f"{cat} — {eng.OUTSIDE_WATER_LABEL}",
                        "mechanismTitle": texts[cat]["mechanismTitle"], "color": texts[cat]["color"],
                        "isInsideWaterStability": inside,
                        "insideWithheldDataRegion": bool(oracle.withheld_hits(element, ph, e, log_a))}
                if set(cell) != set(want):
                    p.append(f"cell {k - 1}: keys {sorted(cell)} != {sorted(want)}")
                    continue
                for key, val in want.items():
                    if not _exact(cell[key], val):
                        p.append(f"cell {k - 1} (pH {ph:g}, E {e:.2f}).{key}: {cell[key]!r} != {val!r}")
    # ---- domains --------------------------------------------------------------------------
    p = problems["domains"]
    polys = oracle.polygons(element, log_a)
    doms = new_stdout.get("domains")
    if not isinstance(doms, list):
        p.append("domains missing")
    else:
        if [d.get("speciesId") for d in doms] != [id_of[n] for n in polys]:
            p.append(f"domain species {[d.get('speciesId') for d in doms]} != oracle {[id_of[n] for n in polys]}")
        else:
            for d, (name, (poly, _)) in zip(doms, polys.items()):
                if d.get("category") != oracle.CATEGORY[data["sp"][name][6]]:
                    p.append(f"{d['speciesId']}: category {d.get('category')!r}")
                if set(d) != {"speciesId", "category", "polygon"}:
                    p.append(f"{d['speciesId']}: keys {sorted(d)}")
                got = _dedupe([(v["pH"], v["E_V_SHE"]) for v in d.get("polygon", [])])
                bad = _match_vertices(got, _dedupe(poly))
                if bad:
                    p.append(f"{d['speciesId']}: {bad}")
                elif not _convex_simple(got):
                    p.append(f"{d['speciesId']}: polygon is not a simple convex polygon (vertex order)")

    # ---- analyticalBoundaries -----------------------------------------------------------
    p = problems["analyticalBoundaries"]
    bounds = new_stdout.get("analyticalBoundaries")
    if not isinstance(bounds, list):
        p.append("analyticalBoundaries missing")
    else:
        want_b = _oracle_boundaries(element, log_a)
        got_keys = []
        for b in bounds:
            a_name, b_name = name_of_id.get(b.get("speciesAId")), name_of_id.get(b.get("speciesBId"))
            tag = b.get("id", "?")
            if a_name is None or b_name is None:
                p.append(f"{tag}: unknown species ids {b.get('speciesAId')!r}, {b.get('speciesBId')!r}")
                continue
            got_keys.append((a_name, b_name))
            want_keys = {"id", "name", "equation", "boundaryType", "speciesA", "speciesB", "speciesAId",
                         "speciesBId", "points", "line"}
            if set(b) != want_keys:
                p.append(f"{tag}: keys {sorted(b)}")
            ra, rb = rows[names.index(a_name)], rows[names.index(b_name)]
            ca, cb = ra["category"], rb["category"]
            for key, val in (("id", f"{id_of[a_name]}__{id_of[b_name]}"),
                             ("name", f"{formula_of[a_name]} / {formula_of[b_name]}"),
                             ("speciesA", formula_of[a_name]), ("speciesB", formula_of[b_name]),
                             ("boundaryType", f"{ca} / {cb}" if ca != cb
                              else f"{ca}: {formula_of[a_name]} / {formula_of[b_name]}")):
                if not _exact(b.get(key), val):
                    p.append(f"{tag}.{key}: {b.get(key)!r} != {val!r}")
            bad = _equation_problem(b.get("equation"), ra, rb)
            if bad:
                p.append(f"{tag}: {bad}")
            engine_by_id = {s.id: s for s in eng._coefficients(element, log_a)}
            want_equation = eng._equation(engine_by_id[id_of[a_name]], engine_by_id[id_of[b_name]])
            if b.get("equation") != want_equation:
                p.append(f"{tag}.equation {b.get('equation')!r} != the engine's reaction text {want_equation!r}")
            line = b.get("line")
            ol = oracle.boundary(element, a_name, b_name, log_a)
            if ol[0] == "pH":
                if not (isinstance(line, dict) and set(line) == {"type", "pH"} and line["type"] == "vertical"
                        and _close(line["pH"], ol[1], COORD_TOL)):
                    p.append(f"{tag}.line {line!r} != vertical pH {ol[1]:.6f}")
            else:
                if not (isinstance(line, dict) and set(line) == {"type", "E_V_SHE_at_pH0", "slope_V_per_pH"}
                        and line["type"] == "sloped" and _close(line["E_V_SHE_at_pH0"], ol[1], COORD_TOL)
                        and _close(line["slope_V_per_pH"], ol[2], COORD_TOL)):
                    p.append(f"{tag}.line {line!r} != E0 {ol[1]:.6f}, slope {ol[2]:.6f}")
            pts = b.get("points")
            ends = want_b.get((a_name, b_name))
            if not (isinstance(pts, list) and len(pts) == 2) or ends is None:
                p.append(f"{tag}: points {pts!r} / oracle edge {ends!r}")
                continue
            got_pts = [(q["pH"], q["E_V_SHE"]) for q in pts]
            straight = all(abs(got_pts[0][i] - ends[0][i]) <= COORD_TOL and abs(got_pts[1][i] - ends[1][i])
                           <= COORD_TOL for i in (0, 1))
            swapped = all(abs(got_pts[0][i] - ends[1][i]) <= COORD_TOL and abs(got_pts[1][i] - ends[0][i])
                          <= COORD_TOL for i in (0, 1))
            if not (straight or swapped):
                p.append(f"{tag}: ends {got_pts} != oracle {list(ends)} (> {COORD_TOL})")
            # brute force: both sides of the midpoint are won by exactly {A, B}
            mid = ((got_pts[0][0] + got_pts[1][0]) / 2.0, (got_pts[0][1] + got_pts[1][1]) / 2.0)
            probes = ((mid[0], mid[1] + NUDGE_V), (mid[0], mid[1] - NUDGE_V)) if ol[0] != "pH" \
                else ((mid[0] + NUDGE_V, mid[1]), (mid[0] - NUDGE_V, mid[1]))
            if {oracle.dominant(element, x, y, log_a) for x, y in probes} != {a_name, b_name}:
                p.append(f"{tag}: the oracle's dominant species beside the midpoint are not {{A, B}}")
        if sorted(got_keys) != sorted(want_b):
            p.append(f"boundary pairs {sorted(got_keys)} != oracle {sorted(want_b)}")

    # ---- speciesInventory ---------------------------------------------------------------
    p = problems["speciesInventory"]
    want_inv = {v: [] for v in _KEY_BY_ROLE.values()}
    for name in names:
        want_inv[_KEY_BY_ROLE[data["sp"][name][6]]].append(
            formula_of[name] + ("(s)" if data["sp"][name][5] == "s" else "(aq)"))
    if new_stdout.get("speciesInventory") != want_inv:
        p.append(f"speciesInventory {new_stdout.get('speciesInventory')!r} != {want_inv!r}")

    # ---- waterStabilityLines ------------------------------------------------------------
    p = problems["waterStabilityLines"]
    k_slope = oracle.LN10 * oracle.R * oracle.T / oracle.F
    e0_oer = round(oracle.water_lines(0.0)[1], 4)
    w = new_stdout.get("waterStabilityLines", {})
    if not _exact(w.get("e0_OER"), e0_oer):
        p.append(f"e0_OER {w.get('e0_OER')!r} != {e0_oer!r}")
    want_eq = f"E = {e0_oer:.4f} - {k_slope:.4f}·pH (Line b: O₂ + 4H⁺ + 4e⁻ ⇌ 2H₂O)"
    if w.get("equation_OER") != want_eq:
        p.append(f"equation_OER {w.get('equation_OER')!r} != {want_eq!r}")
    line_b = w.get("line_b_oxygen_OER")
    want_lb = [{"pH": float(i), "E_V_SHE": round(oracle.water_lines(float(i))[1], 4)} for i in range(16)]
    if line_b != want_lb:
        p.append("line_b_oxygen_OER differs from the oracle's water line b")
    line_a = w.get("line_a_hydrogen_HER")
    want_la = [{"pH": float(i), "E_V_SHE": round(oracle.water_lines(float(i))[0], 4)} for i in range(16)]
    if line_a != want_la:
        p.append("line_a_hydrogen_HER differs from the oracle's water line a")
    want_her = f"E = 0.000 - {k_slope:.4f}·pH (Line a: 2H⁺ + 2e⁻ ⇌ H₂)"
    if w.get("equation_HER") != want_her:
        p.append(f"equation_HER {w.get('equation_HER')!r} != {want_her!r}")
    if not _exact(w.get("nernstSlope"), round(k_slope, 5)):
        p.append(f"nernstSlope {w.get('nernstSlope')!r} != {round(k_slope, 5)!r}")
    if set(w) != {"nernstSlope", "e0_OER", "line_a_hydrogen_HER", "line_b_oxygen_OER", "equation_HER", "equation_OER"}:
        p.append(f"waterStabilityLines keys {sorted(w)}")

    # ---- experimentalOverlay ----------------------------------------------------------
    p = problems["experimentalOverlay"]
    ov = new_stdout.get("experimentalOverlay")
    pts = ov.get("points") if isinstance(ov, dict) else None
    if not isinstance(pts, list) or len(pts) != len(old_points):
        p.append("experimentalOverlay.points missing or of another length than the golden's")
    else:
        breakdown = {k: 0 for k in _RISK_KEYS}
        counts: Dict[str, int] = {}
        outside = 0
        withheld_pts = 0
        for i, (pt, old) in enumerate(zip(pts, old_points)):
            ph, pot, ref = old["pH"], old["potential_Input_V"], old["refElectrode"]
            e = pot + _OFFSETS[ref]
            sp = oracle.dominant(element, ph, e, log_a)
            cat = oracle.CATEGORY[data["sp"][sp][6]]
            her, oer = oracle.water_lines(ph)
            inside = her <= e <= oer
            e_imm = _metal_boundary_E(element, log_a, ph)
            hits = oracle.withheld_hits(element, ph, e, log_a)
            tx = texts[cat]
            if e < her:
                dep = "H⁺ reduction possible (E below water line a)"
            elif e < oer:
                dep = "O₂ reduction possible (E between water lines a and b)"
            else:
                dep = "Above water line b (water oxidation region)"
            mit = []
            if cat == eng.CATEGORY_IMMUNITY:
                mit.append(_IMMUNITY_MITIGATION_BELOW if e < her else _IMMUNITY_MITIGATION_INSIDE)
            else:
                if cat == eng.CATEGORY_ACID and e_imm is not None:
                    mit.append(f"Cathodic protection: polarise below the computed metal-domain boundary "
                               f"(E < {round(e_imm, 2)} V vs SHE at pH {ph:g}).")
                elif e_imm is not None:
                    mit.append(f"The metal-domain boundary at pH {ph:g} lies at {round(e_imm, 2)} V vs SHE.")
                mit.extend(eng.CATEGORY_MITIGATION[cat])
            want = {"potential_V_SHE": round(e, 4), "regime": cat if inside else f"{cat} — {eng.OUTSIDE_WATER_LABEL}",
                    "category": cat, "dominantSpecies": formula_of[sp], "dominantSpeciesId": id_of[sp],
                    "mechanismId": tx["mechanismId"], "mechanismTitle": tx["mechanismTitle"],
                    "mechanismDetails": tx["mechanismDetails"], "riskLevel": tx["riskLevel"],
                    "color": tx["color"], "depolarizer": dep,
                    "deltaE_Immunity_V": None if e_imm is None else round(e - e_imm, 3),
                    "deltaE_Pitting_V": None, "isInsideWaterStability": inside,
                    "waterStabilityLabel": eng.INSIDE_WATER_LABEL if inside else eng.OUTSIDE_WATER_LABEL,
                    "insideWithheldDataRegion": bool(hits), "withheldDataSpeciesIds": [h[1] for h in hits],
                    "engineeringMitigations": mit}
            for key, val in want.items():
                if key not in pt or not _exact(pt[key], val):
                    p.append(f"point {i} ({pt.get('id')}).{key}: {pt.get(key)!r} != {val!r}")
            # the user's own input fields are the golden's, bit for bit (no drift of a measured potential)
            for key in ("id", "name", "pH", "potential_Input_V", "refElectrode", "currentDensity_uA_cm2",
                        "timeHours", "stageName", "notes"):
                if key not in pt or not _exact(pt[key], old.get(key)):
                    p.append(f"point {i} ({pt.get('id')}).{key}: {pt.get(key)!r} != the golden's {old.get(key)!r}")
            if set(pt) != set(want) | {"id", "name", "pH", "potential_Input_V", "refElectrode",
                                       "currentDensity_uA_cm2", "timeHours", "stageName", "notes"}:
                p.append(f"point {i}: keys {sorted(pt)}")
            breakdown[tx["riskLevel"]] += 1
            counts[cat] = counts.get(cat, 0) + 1
            outside += 0 if inside else 1
            withheld_pts += 1 if hits else 0
        if pts:
            parts = ", ".join(f"{n} in {c}" for c, n in sorted(counts.items()))
            diag = (f"Equilibrium classification of {len(pts)} test point(s) in the {element}–H₂O map at "
                    f"25 °C (dissolved activity 10^{log_a:g}): {parts}.")
            if outside:
                diag += f" {outside} point(s) lie outside the water stability window (metastable)."
            if withheld_pts:
                diag += (f" {withheld_pts} point(s) lie in a withheld-data region, where the map is not valid "
                         "(dataValidity).")
            diag += (" This is a thermodynamic statement; it makes no claim about rates, film protectiveness "
                     "or pitting.")
        else:
            diag = "No experimental data provided."
        if ov.get("overallTrajectoryDiagnosis") != diag:
            p.append(f"overallTrajectoryDiagnosis {ov.get('overallTrajectoryDiagnosis')!r} != {diag!r}")
        if ov.get("riskBreakdown") != breakdown:
            p.append(f"riskBreakdown {ov.get('riskBreakdown')!r} != {breakdown!r}")
        if ov.get("totalPointsCount") != len(pts) or set(ov) != {"totalPointsCount", "riskBreakdown",
                                                                "overallTrajectoryDiagnosis", "points"}:
            p.append("experimentalOverlay keys / totalPointsCount differ")

    # ---- chloridePittingBoundary ---------------------------------------------------------
    p = problems["chloridePittingBoundary"]
    want_pb = {"pittingActive": False, "status": "unavailable-no-sourced-epit", "chloride_ppm": chloride_ppm,
               "chloride_Molar": round(max(chloride_ppm, 0.0) * 1e-3 / _CHLORIDE_MOLAR_MASS, 5),
               "nominal_Epit_V_SHE": None, "points": [], "note": _PITTING_NOTE}
    if new_stdout.get("chloridePittingBoundary") != want_pb:
        p.append(f"chloridePittingBoundary {new_stdout.get('chloridePittingBoundary')!r} != {want_pb!r}")

    # ---- parameters / temperatureStatus / engine / model --------------------------------------
    p = problems["parameters"]
    prm = new_stdout.get("parameters", {})
    ref_cat = name_of_id.get(table.REFERENCE_CATION[element])
    e0 = oracle.boundary(element, names[0], ref_cat, 0.0) if ref_cat else None
    k_nernst = oracle.LN10 * oracle.R * oracle.T / oracle.F
    want_p = {"temperature_C": 25.0, "requestedTemperature_C": float(requested_t), "pittingPotential_V_SHE": None,
              "pittingRisk": _PITTING_RISK, "standardE0_V": round(e0[1], 4) if e0 and e0[0] == "E" else None,
              "nernstSlope_V_pH": round(k_nernst, 5), "ionActivity_log10": float(log_a),
              "chlorideConcentration_ppm": float(chloride_ppm),
              "chloride_Molar": round(max(chloride_ppm, 0.0) * 1e-3 / _CHLORIDE_MOLAR_MASS, 5)}
    for key, val in want_p.items():
        if key not in prm or not _exact(prm[key], val):
            p.append(f"parameters.{key}: {prm.get(key)!r} != {val!r}")
    if set(prm) != set(want_p):
        p.append(f"parameters keys {sorted(prm)} != {sorted(want_p)}")
    p = problems["temperatureStatus"]
    want_t = {"status": "supported-25C-only", "temperature_C": 25.0, "supported_C": [25.0], "toleranceC": 0.5,
              "note": _TEMPERATURE_NOTE}
    if new_stdout.get("temperatureStatus") != want_t:
        p.append(f"temperatureStatus {new_stdout.get('temperatureStatus')!r} != {want_t!r}")
    p = problems["engine"]
    if new_stdout.get("engine") != eng.ENGINE_ID or eng.ENGINE_ID != ENGINE_ID:
        p.append(f"engine {new_stdout.get('engine')!r} != {ENGINE_ID!r}")
    p = problems["model"]
    model = new_stdout.get("model")
    want_m = eng._model_block(log_a, element)
    want_m.update({"temperature_C": 25.0, "temperature_K": 298.15,
                   "box": {"pH_min": oracle.BOX[0], "pH_max": oracle.BOX[1],
                           "E_min_V_SHE": oracle.BOX[2], "E_max_V_SHE": oracle.BOX[3]},
                   "gasConstantR_J_molK": pc.GAS_CONSTANT_R.value, "faraday_C_mol": pc.FARADAY.value,
                   "engine": ENGINE_ID,
                   "dissolvedActivityRange_log10": list(oracle.ACTIVITY_RANGE.get(element, (-6.0, 0.0)))})
    if model != want_m:
        p.append(f"model block differs from the engine text/constants: {sorted(set(model or {}) ^ set(want_m))}")
    if isinstance(model, dict):
        if abs(model.get("gasConstantR_J_molK", 0) / oracle.R - 1) > 1e-9 \
                or abs(model.get("faraday_C_mol", 0) / oracle.F - 1) > 1e-9:
            p.append("model R / F differ from the oracle's CODATA values by more than 1e-9 relative")

    # ---- dataValidity (v5) -----------------------------------------------------------------
    p = problems["dataValidity"]
    dv = new_stdout.get("dataValidity")
    want_keys = {"status", "activityRange_log10", "rule", "candidateSets", "regions",
                 "pHWindowsFreeOfRegionsInsideWater", "unsourcedSpecies"}
    if not isinstance(dv, dict) or set(dv) != want_keys:
        p.append(f"dataValidity keys {sorted(dv) if isinstance(dv, dict) else dv!r} != {sorted(want_keys)}")
        return problems
    cand = oracle.CANDIDATES.get(element, {})
    want_regions = oracle.withheld_polygons(element, log_a)
    want_status = ("withheld-species-regions" if want_regions else
                   ("withheld-candidates-without-region" if cand else "no-withheld-candidates"))
    if dv["status"] != want_status:
        p.append(f"status {dv['status']!r} != {want_status!r}")
    if dv["activityRange_log10"] != list(oracle.ACTIVITY_RANGE.get(element, (-6.0, 0.0))):
        p.append(f"activityRange_log10 {dv['activityRange_log10']!r}")
    if dv["rule"] != eng._data_validity_block("Fe", -6.0)["rule"]:
        p.append("rule text differs from the engine's")
    got_sets = dv["candidateSets"]
    if [(c.get("id"), c.get("speciesIds")) for c in got_sets] != [(k, list(v)) for k, v in cand.items()]:
        p.append("candidateSets (ids / members) differ from the oracle's candidate sets")
    elif got_sets != table.candidate_sets(element):
        p.append("candidateSets labels differ from the engine's table")
    if dv["unsourcedSpecies"] != table.unsourced_species(element):
        p.append("unsourcedSpecies differ from the engine's table")
    regions = dv["regions"]
    if [(r.get("candidateSet"), r.get("speciesId")) for r in regions] != [(a, b) for a, b, _ in want_regions]:
        p.append(f"regions {[(r.get('candidateSet'), r.get('speciesId')) for r in regions]} != oracle "
                 f"{[(a, b) for a, b, _ in want_regions]}")
    else:
        rows_w = {r["id"]: r for r in table.withheld_rows(element)}
        for r, (set_id, sid, poly) in zip(regions, want_regions):
            if set(r) != {"candidateSet", "speciesId", "formula", "category", "polygon"}:
                p.append(f"region {sid}: keys {sorted(r)}")
                continue
            role = cand[set_id][sid][6]
            if r["category"] != oracle.CATEGORY[role] or r["formula"] != rows_w[sid]["formula"]:
                p.append(f"region {sid}: category / formula")
            got = _dedupe([(v["pH"], v["E_V_SHE"]) for v in r["polygon"]])
            bad = _match_vertices(got, _dedupe(poly))
            if bad:
                p.append(f"region {sid}: {bad}")
            elif not _convex_simple(got):
                p.append(f"region {sid}: polygon is not a simple convex polygon")
    windows = dv["pHWindowsFreeOfRegionsInsideWater"]
    want_w = _oracle_free_windows(element, log_a)
    if not (isinstance(windows, list) and len(windows) == len(want_w)
            and all(isinstance(w, list) and len(w) == 2 and _close(w[0], v[0], COORD_TOL) and _close(w[1], v[1], COORD_TOL)
                    for w, v in zip(windows, want_w))):
        p.append(f"pHWindowsFreeOfRegionsInsideWater {windows!r} != oracle {want_w!r}")
    return problems


# ---------------------------------------------------------------------------------------------
# The documented change: which drift rows against the d33b6f5 golden this check may accept.
# One entry per leaf-key path (list indices written [] and matched as [<n>]); nothing else
# is a pourbaix documented change. Rows listed here are accepted only through row_problem().
# ---------------------------------------------------------------------------------------------
DOCUMENTED_KEYS = (
    'analyticalBoundaries[].boundaryType',
    'analyticalBoundaries[].equation',
    'analyticalBoundaries[].id',
    'analyticalBoundaries[].line.E_V_SHE_at_pH0',
    'analyticalBoundaries[].line.pH',
    'analyticalBoundaries[].line.slope_V_per_pH',
    'analyticalBoundaries[].line.type',
    'analyticalBoundaries[].name',
    'analyticalBoundaries[].points[].E_V_SHE',
    'analyticalBoundaries[].points[].pH',
    'analyticalBoundaries[].speciesA',
    'analyticalBoundaries[].speciesAId',
    'analyticalBoundaries[].speciesB',
    'analyticalBoundaries[].speciesBId',
    'chloridePittingBoundary.chloride_Molar',
    'chloridePittingBoundary.chloride_ppm',
    'chloridePittingBoundary.nominal_Epit_V_SHE',
    'chloridePittingBoundary.note',
    'chloridePittingBoundary.pittingActive',
    'chloridePittingBoundary.pittingPotential_V_SHE',
    'chloridePittingBoundary.pittingThresholdLine[].E_V_SHE',
    'chloridePittingBoundary.pittingThresholdLine[].pH',
    'chloridePittingBoundary.points',
    'chloridePittingBoundary.status',
    'dataValidity.activityRange_log10[]',
    'dataValidity.candidateSets',
    'dataValidity.candidateSets[].id',
    'dataValidity.candidateSets[].label',
    'dataValidity.candidateSets[].speciesIds[]',
    'dataValidity.pHWindowsFreeOfRegionsInsideWater[][]',
    'dataValidity.regions',
    'dataValidity.regions[].candidateSet',
    'dataValidity.regions[].category',
    'dataValidity.regions[].formula',
    'dataValidity.regions[].polygon[].E_V_SHE',
    'dataValidity.regions[].polygon[].pH',
    'dataValidity.regions[].speciesId',
    'dataValidity.rule',
    'dataValidity.status',
    'dataValidity.unsourcedSpecies',
    'dataValidity.unsourcedSpecies[].formula',
    'dataValidity.unsourcedSpecies[].reason',
    'domains[].category',
    'domains[].polygon[].E_V_SHE',
    'domains[].polygon[].pH',
    'domains[].speciesId',
    'engine',
    'experimentalOverlay.overallTrajectoryDiagnosis',
    'experimentalOverlay.points[].category',
    'experimentalOverlay.points[].color',
    'experimentalOverlay.points[].deltaE_Immunity_V',
    'experimentalOverlay.points[].deltaE_Pitting_V',
    'experimentalOverlay.points[].depolarizer',
    'experimentalOverlay.points[].dominantSpecies',
    'experimentalOverlay.points[].dominantSpeciesId',
    'experimentalOverlay.points[].engineeringMitigations[]',
    'experimentalOverlay.points[].insideWithheldDataRegion',
    'experimentalOverlay.points[].mechanismDetails',
    'experimentalOverlay.points[].mechanismId',
    'experimentalOverlay.points[].mechanismTitle',
    'experimentalOverlay.points[].regime',
    'experimentalOverlay.points[].riskLevel',
    'experimentalOverlay.points[].waterStabilityLabel',
    'experimentalOverlay.points[].withheldDataSpeciesIds',
    'experimentalOverlay.points[].withheldDataSpeciesIds[]',
    'experimentalOverlay.riskBreakdown.Caution',
    'experimentalOverlay.riskBreakdown.High Risk',
    'experimentalOverlay.riskBreakdown.Immune',
    'experimentalOverlay.riskBreakdown.Pitting Hazard',
    'experimentalOverlay.riskBreakdown.Severe Corrosion',
    'experimentalOverlay.riskBreakdown.Stable Passivity',
    'model.activityCoefficients',
    'model.activityConvention',
    'model.box.E_max_V_SHE',
    'model.box.E_min_V_SHE',
    'model.box.pH_max',
    'model.box.pH_min',
    'model.chloride',
    'model.dissolvedActivityRange_log10[]',
    'model.engine',
    'model.excludedSpecies[]',
    'model.faraday_C_mol',
    'model.gasConstantR_J_molK',
    'model.method',
    'model.reference',
    'model.riskLevelNote',
    'model.temperatureScope',
    'model.temperature_C',
    'model.temperature_K',
    'model.tieBreak',
    'model.waterLines',
    'parameters.pittingPotential_V_SHE',
    'parameters.pittingRisk',
    'parameters.requestedTemperature_C',
    'parameters.standardE0_V',
    'speciesInventory.corrosion_acid[]',
    'speciesInventory.corrosion_alkaline[]',
    'speciesInventory.immunity[]',
    'speciesInventory.passivation[]',
    'speciesInventory.transpassive',
    'speciesInventory.transpassive[]',
    'speciesTable.schema',
    'speciesTable.sourceSet',
    'speciesTable.sourceSetNote',
    'speciesTable.species[].category',
    'speciesTable.species[].dfG_kJ_mol',
    'speciesTable.species[].evidence',
    'speciesTable.species[].formula',
    'speciesTable.species[].h',
    'speciesTable.species[].id',
    'speciesTable.species[].o',
    'speciesTable.species[].phase',
    'speciesTable.species[].role',
    'speciesTable.species[].source',
    'speciesTable.species[].verification',
    'speciesTable.species[].x',
    'speciesTable.species[].z',
    'speciesTable.waterDfG_kJ_mol',
    'speciesTable.withheldSpecies',
    'speciesTable.withheldSpecies[].id',
    'speciesTable.withheldSpecies[].reason',
    'speciesTable.withheldSpecies[].verification',
    'stabilityFieldGrid[].category',
    'stabilityFieldGrid[].color',
    'stabilityFieldGrid[].dominantSpecies',
    'stabilityFieldGrid[].dominantSpeciesId',
    'stabilityFieldGrid[].insideWithheldDataRegion',
    'stabilityFieldGrid[].isInsideWaterStability',
    'stabilityFieldGrid[].mechanismTitle',
    'stabilityFieldGrid[].regime',
    'temperatureStatus.note',
    'temperatureStatus.status',
    'temperatureStatus.supported_C[]',
    'temperatureStatus.temperature_C',
    'temperatureStatus.toleranceC',
    'waterStabilityLines.e0_OER',
    'waterStabilityLines.equation_OER',
    'waterStabilityLines.line_b_oxygen_OER[].E_V_SHE',
)


def _pattern(normalized: str) -> str:
    return r"\[\d+\]".join(re.escape(part) for part in normalized.split("[]"))


DOCUMENTED_VALUE_CHANGES = {
    _pattern(k): "WP-E: rule tree -> minimum-Gibbs-energy equilibrium; verified exactly against pourbaix_oracle"
    for k in DOCUMENTED_KEYS
}


def flatten(value: Any, prefix: str = "") -> Dict[str, Any]:
    """Leaf map with the same key spelling as drift_report.flatten (empty containers are leaves)."""
    out: Dict[str, Any] = {}
    if isinstance(value, dict):
        if not value:
            out[prefix] = value
        for k in value:
            out.update(flatten(value[k], f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(value, list):
        if not value:
            out[prefix] = value
        for i, v in enumerate(value):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = value
    return out


_MISSING = object()


class Context:
    """The oracle check of one (golden, re-blessed) document pair, computed once per bless/test."""

    def __init__(self, old_stdout: Dict[str, Any], new_stdout: Dict[str, Any]):
        self.problems = document_problems(old_stdout, new_stdout)
        self.old_flat = flatten(old_stdout)
        self.new_flat = flatten(new_stdout)


def row_problem(row: Dict[str, Any], context: Context) -> Optional[str]:
    """None when the drift row is exactly the documented change: the row's old value is the
    d33b6f5 golden's leaf, its new value is the re-blessed document's leaf, and the oracle check
    of the section it lives in has no problem."""
    key, kind = row["key"], row["kind"]
    problems, old_flat, new_flat = context.problems, context.old_flat, context.new_flat
    section = re.split(r"[.\[]", key, maxsplit=1)[0]
    if section not in problems:
        return f"{key}: not in a section the oracle check covers"
    if problems[section]:
        return f"{key}: {section} differs from the oracle: {problems[section][0]}"
    old, new = old_flat.get(key, _MISSING), new_flat.get(key, _MISSING)
    if kind == "added":
        ok = old is _MISSING and new is not _MISSING and _exact(new, row["new"])
    elif kind == "removed":
        ok = new is _MISSING and old is not _MISSING and _exact(old, row["old"])
    elif kind in ("numeric", "changed"):
        ok = (old is not _MISSING and new is not _MISSING and _exact(old, row["old"]) and _exact(new, row["new"])
              and not _exact(old, new))
    else:
        ok = False
    if not ok:
        return (f"{key}: {kind} row old {row.get('old')!r} / new {row.get('new')!r} is not the d33b6f5 golden "
                f"leaf {None if old is _MISSING else old!r} -> the re-blessed leaf "
                f"{None if new is _MISSING else new!r}")
    return None


def main(argv=None) -> int:
    """Check every re-blessed pourbaix_solver step_b document against the oracle (exit 1 on any problem)."""
    import capture_phase6a_golden as golden
    failed = 0
    for case in golden.CASES["pourbaix_solver"]:
        path = golden.step_b_path("pourbaix_solver", case)
        if not path.is_file():
            continue
        old = golden.load_golden("pourbaix_solver", case)["stdout"]
        new = golden.load_expected("pourbaix_solver", case)["stdout"]
        problems = {k: v for k, v in document_problems(old, new).items() if v}
        print(f"pourbaix_solver/{case}: {'OK' if not problems else problems}")
        failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
