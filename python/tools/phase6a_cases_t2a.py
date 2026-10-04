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
captured path is the sub-regular fallback minimiser (engine
"subregular-adaptive-minimizer"); the pycalphad path is not covered here.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional

# battery_corrosion_eis_solver adds a wall-clock duration under this name.
EXTRA_VOLATILE_KEYS = frozenset({"pythonDurationMs"})

# Synthetic Randles + Warburg spectrum (Rs 0.015 ohm, Rct 0.032 ohm, Cdl 1.6 F,
# sigma 0.004 ohm s^-1/2), 31 log-spaced points from 10 kHz to 10 mHz, rounded to
# 8 decimals. Synthetic, not measured data.
_EIS_F = [10000.0, 6309.573445, 3981.071706, 2511.886432, 1584.893192, 1000.0, 630.957344,
          398.107171, 251.188643, 158.489319, 100.0, 63.095734, 39.810717, 25.118864, 15.848932,
          10.0, 6.309573, 3.981072, 2.511886, 1.584893, 1.0, 0.630957, 0.398107, 0.251189,
          0.158489, 0.1, 0.063096, 0.039811, 0.025119, 0.015849, 0.01]
_EIS_ZR = [0.01501596, 0.0150201, 0.01502531, 0.01503189, 0.01504021, 0.01505077, 0.01506431,
           0.01508193, 0.01510559, 0.01513906, 0.01519047, 0.01527838, 0.01544683, 0.01580107,
           0.01658622, 0.01832425, 0.02188526, 0.02792002, 0.03536584, 0.04166528, 0.04559466,
           0.04774272, 0.04901273, 0.04997638, 0.05092542, 0.05201318, 0.05333968, 0.05499251,
           0.05706651, 0.05967479, 0.06295736]
_EIS_ZI = [-2.59e-05, -3.585e-05, -5.028e-05, -7.144e-05, -0.00010285, -0.00014993, -0.00022118,
           -0.00032982, -0.00049663, -0.00075414, -0.00115334, -0.0017736, -0.00273639,
           -0.00421871, -0.0064446, -0.00957533, -0.01332138, -0.01632226, -0.0166503,
           -0.01421681, -0.01092469, -0.00824724, -0.00656125, -0.00575303, -0.00563571,
           -0.00607464, -0.00700212, -0.00840752, -0.01032716, -0.01283877, -0.01606063]

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
        # Unknown "Xx" uses the LEGACY 50.0 g/mol fallback, kept in step (a)
        # (fix round p6a-fix2, B1); bit-identical to the pre-migration output.
        "edge_unknown_element_xx": {
            "name": "Unknown element", "unit": "wt_pct",
            "elements": {"Ni": 70.0, "Cr": 20.0, "Xx": 10.0},
            "tMin": 800.0, "tMax": 1500.0, "tStep": 50.0,
        },
    },
    "battery_corrosion_eis_solver": {
        # R 8.314, F 96485.332 (p2d site).
        "p2d_continuum_nmc811": {"action": "p2d_continuum", "chemistryId": "nmc811", "cRate": 2.5,
                                 "tempC": 15.0, "soc": 0.6},
        # R 8.314 (degradation site).
        "battery_degradation_lfp": {"action": "battery_degradation", "chemistryId": "lfp",
                                    "cycles": 800, "tempC": 35.0, "chargeCRate": 1.5},
        # R 8.314462618, F 96485.33212 (Nernst-Planck-Poisson site).
        "nernst_planck_poisson": {"action": "nernst_planck_poisson", "formulationId": "lipf6_ec_emc",
                                  "currentDensity_mA_cm2": 6.0, "gap_um": 40.0, "tempC": 10.0},
        # R 8.31446, F 96485.33 (uploaded-EIS exchange-current site).
        "uploaded_eis_synthetic_randles": {"action": "analyze_uploaded_eis", "frequencies": _EIS_F,
                                           "zReal": _EIS_ZR, "zImag": _EIS_ZI,
                                           "applicationDomain": "battery", "cellTemperatureC": 30.0,
                                           "nominalCapacityAh": 4.8},
        # Pre-existing masking (kept unchanged): an unknown action still returns
        # {"error": ..., "success": true} with exit code 0.
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
