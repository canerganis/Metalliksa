#!/usr/bin/env python3
"""
Phase 6a tranche 2a golden cases: calphad_solver, battery_corrosion_eis_solver and
icme_multiscale_pipeline_solver.

Kept out of capture_phase6a_golden.py so that the other tranche-2 branch can add
its own case module next to this one; the harness merges both through one small
delimited block each.

The three solvers are byte-identical at d33b6f5 and at 7f3f803 (the tranche-2
base), so the harness's d33b6f5 blob binding applies unchanged; test_phase6a_t2a
asserts that identity. None of the three uses an RNG.

calphad_solver: pycalphad is not installed in the locked test environment, so the
captured (d33b6f5) path is the sub-regular fallback minimiser (engine
"subregular-adaptive-minimizer", isEmpirical false); the pycalphad path is not
covered here. The fallback was removed (fx-calphad lane): the four success cases are
now the explicit "unavailable" envelope (EXPECTED_UNAVAILABLE_CHANGES below); the old
goldens stay on disk as the record of the removed non-thermodynamic output.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional

# battery_corrosion_eis_solver adds a wall-clock duration under this name.
EXTRA_VOLATILE_KEYS = frozenset({"pythonDurationMs"})

def _key_sorted(value: Any) -> Any:
    """Return ``value`` with every dict in key order.

    calphad_solver and icme_multiscale_pipeline_solver depend on the order of the
    composition keys (calphad: matrix/partitioning order and majorElements; icme:
    floating-point summation order). Golden files store the input with sorted keys
    and the regression re-runs that stored input, so each payload is defined in
    sorted order here: the captured run and the re-run send identical JSON.
    """
    if isinstance(value, dict):
        return {k: _key_sorted(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_key_sorted(v) for v in value]
    return value


_RAW_CASES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "calphad_solver": {
        "in718_wt_pct": {
            "name": "Inconel 718", "unit": "wt_pct",
            "elements": {"Ni": 53.0, "Cr": 19.0, "Fe": 18.0, "Nb": 5.0, "Mo": 3.0, "Ti": 1.0, "Al": 1.0},
            "tMin": 500.0, "tMax": 1450.0, "tStep": 25.0,
        },
        # at_pct path: wt% is derived from the atomic weights (the old 50.0 fallback site).
        "ti64_at_pct": {
            "name": "Ti-6Al-4V (at%)", "unit": "at_pct",
            "elements": {"Ti": 86.0, "Al": 10.2, "V": 3.8},
            "tMin": 600.0, "tMax": 1750.0, "tStep": 30.0,
        },
        "ss316l_fixed_grid": {
            "name": "316L", "unit": "wt_pct",
            "elements": {"Fe": 65.5, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Mn": 2.0, "Si": 0.75, "C": 0.03},
            "tMin": 700.0, "tMax": 1550.0, "tStep": 50.0, "adaptiveGrid": False, "boundaryRefinement": False,
        },
        # Lower/upper-case symbols are normalised; a zero-valued unknown entry is
        # skipped before any atomic-weight lookup, so it stays accepted.
        "alsi10mg_case_variants_zero_unknown": {
            "name": "AlSi10Mg", "unit": "wt_pct",
            "elements": {"al": 88.5, "SI": 10.0, "mg": 0.5, "Fe": 1.0, "Xx": 0},
            "tMin": 400.0, "tMax": 750.0, "tStep": 20.0,
        },
        # Unknown "Xx": the pre-migration code (golden) weighted it with 50.0 g/mol;
        # design step (b) refuses it (UNKNOWN_ELEMENT), see EXPECTED_BEHAVIOUR_CHANGES.
        "edge_unknown_element_xx": {
            "name": "Unknown element", "unit": "wt_pct",
            "elements": {"Ni": 70.0, "Cr": 20.0, "Xx": 10.0},
            "tMin": 800.0, "tMax": 1500.0, "tStep": 50.0,
        },
    },
    "battery_corrosion_eis_solver": {
        # The p2d_continuum_nmc811, battery_degradation_lfp, nernst_planck_poisson and
        # uploaded_eis_synthetic_randles cases (and their step_b goldens) were deleted on
        # 2026-10-04 with their solver actions (no UI consumer; only corrosion_kinetics stays).
        # Recorded as the pre-migration success:true masking; since the V1 follow-up the
        # solver reports success:false for it (see EXPECTED_SUCCESS_FLAG_CHANGES).
        "edge_unknown_action_success_masking": {"action": "no_such_action"},
    },
    "icme_multiscale_pipeline_solver": {
        # Empty payload: every documented default (Inconel 718, Ni base, LPBF cooling).
        "default_payload_in718": {},
        "ti64_preset": {"alloyName": "Ti-6Al-4V Grade 5 (Aero AM)", "baseMetal": "Ti",
                        "composition_wt": {"Al": 6.0, "V": 4.0, "Fe": 0.25, "C": 0.05, "Si": 0.05},
                        "coolingRate_C_s": 250000, "agingTemp_C": 550, "agingTime_h": 4,
                        "componentType": "lpbf_bracket"},
        "aisi4340_preset": {"alloyName": "AISI 4340 Ultra-High Strength Steel", "baseMetal": "Fe",
                            "composition_wt": {"C": 0.40, "Cr": 0.80, "Ni": 1.80, "Mo": 0.25, "Mn": 0.70, "Si": 0.25},
                            "coolingRate_C_s": 250, "agingTemp_C": 480, "agingTime_h": 2,
                            "componentType": "pressure_bulkhead"},
        "alsi10mg_preset": {"alloyName": "AlSi10Mg Additive Alloy", "baseMetal": "Al",
                            "composition_wt": {"Si": 10.0, "Mg": 0.45, "Fe": 0.15, "Ti": 0.05, "Mn": 0.05},
                            "coolingRate_C_s": 600000, "agingTemp_C": 160, "agingTime_h": 6,
                            "componentType": "lpbf_bracket"},
        # Silent default before the migration: unknown solute "Zr" used atomic weight 55.0.
        "edge_unknown_solute_zr": {"alloyName": "Ni + Zr", "baseMetal": "Ni",
                                   "composition_wt": {"Cr": 19.0, "Zr": 0.5}},
    },
}
CASES: Dict[str, Dict[str, Dict[str, Any]]] = _key_sorted(_RAW_CASES)

# (solver, case) -> expected validation code after the structural migration.
EXPECTED_BEHAVIOUR_CHANGES = {
    ("icme_multiscale_pipeline_solver", "edge_unknown_solute_zr"): "UNKNOWN_ELEMENT",
    # Design step (b): "Xx" has no standard atomic weight (was the 50.0 g/mol stand-in).
    ("calphad_solver", "edge_unknown_element_xx"): "UNKNOWN_ELEMENT",
}


# (solver, case) -> the old golden stays on disk as the record of the old behaviour
# (exit code 0, stdout carried "success": true next to "error"). The solver now returns
# the same stdout with "success": false; exit code and error message are unchanged.
EXPECTED_SUCCESS_FLAG_CHANGES = {
    ("battery_corrosion_eis_solver", "edge_unknown_action_success_masking"),
}


# (solver, case) -> exact fields of the "unavailable" envelope that replaces the removed
# calphad fallback on an interpreter WITHOUT pycalphad (the locked one). The old golden
# stays on disk (exit 0, success true, engine "subregular-adaptive-minimizer",
# isEmpirical false). Four exact matches, nothing is accepted by tolerance; a case is
# never re-blessed into step_b (step_b_excluded_cases). Not checked when pycalphad is
# importable: that run takes the real path, which these goldens do not cover.
# Resolution after the fix round (database scope): IN718 (Ni base) has no database that is
# assessed for Ni base and contains all its elements (COST 507 is a light-alloy database and is
# refused for Ni/Fe/Co base); 316L (Fe base) has no assessed database at all; Ti-6Al-4V and
# AlSi10Mg go to COST 507 (Ti / Al base) and are only unavailable for the missing pycalphad.
_COST507_SUITABILITY = ("Light-metal alloys with an Al, Mg or Ti base. Ni-, Fe- and Co-base alloys are "
                        "outside its assessed scope and are refused.")
_UNAVAILABLE_COMMON = {
    "success": False,
    "status": "unavailable",
    "engine": "pycalphad-open-tdb",
    "pycalphadAvailable": False,
    "pycalphadVersion": None,
}
_UNAVAILABLE_PYCALPHAD_MISSING = {
    **_UNAVAILABLE_COMMON,
    "unavailableKind": "pycalphad-not-installed",
    "reason": "pycalphad not installed",
    "reasons": ["pycalphad not installed"],
    "databaseId": "cost507",
    "databaseUsed": "COST 507 Comprehensive Light Alloys Database",
    "databaseStatus": "assessment",
    "databaseSuitability": _COST507_SUITABILITY,
}
_IN718_REASON = ("no usable thermodynamic database contains all requested elements (Al, Cr, Fe, Mo, Nb, Ni, Ti); "
                 "the closest, 'Al-Ni Dupin 2001 Benchmark (NIST/SGTE)', lacks Cr, Fe, Mo, Nb, Ti. "
                 "Test-fixture databases are never used")
_316L_REASON = ("no usable thermodynamic database is assessed for Fe-base alloys (assessed base elements by "
                "database: cost507: AL, MG, TI; alni_dupin_2001: AL, NI; crtiv_ghosh: TI, CR, V); "
                "databases are never substituted")
EXPECTED_UNAVAILABLE_CHANGES = {
    ("calphad_solver", "in718_wt_pct"): {
        **_UNAVAILABLE_COMMON,
        "unavailableKind": "no-database-covers-elements",
        "reason": _IN718_REASON,
        "reasons": [_IN718_REASON, "pycalphad not installed"],
        "baseElement": "Ni",
        "missingElements": ["Cr", "Fe", "Mo", "Nb", "Ti"],
        "databaseId": "alni_dupin_2001",
        "databaseUsed": "Al-Ni Dupin 2001 Benchmark (NIST/SGTE)",
        "databaseStatus": "assessment",
        "databasesConsidered": [
            {"databaseId": "alni_dupin_2001", "status": "assessment", "missingElements": ["Cr", "Fe", "Mo", "Nb", "Ti"]},
            {"databaseId": "crtiv_ghosh", "status": "assessment", "notAssessedForBase": "Ni"},
            {"databaseId": "cost507", "status": "assessment", "notAssessedForBase": "Ni"},
        ],
    },
    ("calphad_solver", "ti64_at_pct"): {**_UNAVAILABLE_PYCALPHAD_MISSING, "baseElement": "Ti"},
    ("calphad_solver", "ss316l_fixed_grid"): {
        **_UNAVAILABLE_COMMON,
        "unavailableKind": "database-not-assessed-for-base",
        "reason": _316L_REASON,
        "reasons": [_316L_REASON, "pycalphad not installed"],
        "baseElement": "Fe",
        "databasesConsidered": [
            {"databaseId": "alni_dupin_2001", "status": "assessment", "notAssessedForBase": "Fe"},
            {"databaseId": "crtiv_ghosh", "status": "assessment", "notAssessedForBase": "Fe"},
            {"databaseId": "cost507", "status": "assessment", "notAssessedForBase": "Fe"},
        ],
    },
    ("calphad_solver", "alsi10mg_case_variants_zero_unknown"): {**_UNAVAILABLE_PYCALPHAD_MISSING, "baseElement": "Al"},
}


# --------------------------------------------------------------------------- source tables
# Solver-local tables of the bound base blob, snapshotted before the migration so
# the tests can keep proving that the migrated values are the old ones.

def _literal_assignment(source: bytes, function: Optional[str], name: str) -> Any:
    """ast.literal_eval of ``name = {...}`` (inside ``function`` when given)."""
    tree = ast.parse(source.decode("utf-8"))
    scope: ast.AST = tree
    if function is not None:
        scope = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function)
    for node in ast.walk(scope):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name):
            return ast.literal_eval(node.value)
    raise KeyError(f"{name} not found")


# solver -> list of (function or None, variable name)
SOURCE_TABLES = {
    "calphad_solver": [(None, "ATOMIC_WEIGHTS")],
    "icme_multiscale_pipeline_solver": [("solve_multiscale_pipeline", "atomic_weights")],
}


def capture_source_tables(golden, force: bool, label: str, from_revision: Optional[str]) -> List[str]:
    out: List[str] = []
    for solver, targets in SOURCE_TABLES.items():
        path = golden.GOLDEN_DIR / solver / golden.SOURCE_TABLES_FILE
        if path.exists() and not force:
            out.append(f"skip {solver}/{golden.SOURCE_TABLES_FILE} (exists)")
            continue
        meta, source = golden._binding(solver, label, from_revision)
        values = {name: _literal_assignment(source, fn, name) for fn, name in targets}
        doc = dict(meta)
        doc.update({"schema": golden.GOLDEN_SCHEMA, "solver": solver,
                    "table": ",".join(name for _, name in targets), "values": values})
        golden._write(path, doc)
        out.append(f"wrote {solver}/{golden.SOURCE_TABLES_FILE}")
    return out
