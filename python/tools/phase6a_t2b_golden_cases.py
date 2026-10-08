"""
Phase 6a tranche 2b golden cases: kinetics_ttt_cct_solver and lpbf_fatigue_fracture. Merged into capture_phase6a_golden.CASES by one delimited
block there, so the tranche-2a cases (calphad, battery-eis) merge trivially.

Base: the three solver files are byte-identical between d33b6f5 (the harness label,
capture_phase6a_golden.BASE_REVISION) and 7f3f803 (tranche 2 base), so the existing
blob binding holds unchanged (`git diff --stat d33b6f5 7f3f803 -- <files>` is empty).

Golden files store "input" with sorted keys, so the regression test runs the
CASES payload below (original order), never the stored "input".
lpbf_fatigue_fracture has no __main__; it runs through MODULE_DRIVERS.
"""

from typing import Any, Dict

import fatigue_documented_changes as _fatigue_fx  # tools/ module
import kinetics_documented_changes as _kinetics_fx  # tools/ module

CASES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "kinetics_ttt_cct_solver": {
        # PhaseKineticsTTTCCTStudio defaults (alloy "AISI 4140", 10 C/s, 25 um, 860 C, 720 C / 8 h).
        "aisi4140_ui_defaults": {
            "alloy": "AISI 4140", "coolingRate_C_s": 10.0, "grainSize_um": 25.0,
            "austTemp_C": 860.0, "agingTemp_C": 720.0, "agingTime_h": 8.0,
        },
        "aisi4340_slow_cool": {
            "alloy": "AISI 4340", "coolingRate_C_s": 0.5, "grainSize_um": 20.0,
            "austTemp_C": 845.0, "agingTemp_C": 600.0, "agingTime_h": 4.0,
        },
        "in718_lpbf_quench": {
            "alloy": "Inconel 718", "coolingRate_C_s": 1000.0, "grainSize_um": 35.0,
            "austTemp_C": 980.0, "agingTemp_C": 720.0, "agingTime_h": 8.0,
        },
        "ti64_beta_quench": {
            "alloy": "Ti-6Al-4V", "coolingRate_C_s": 500.0, "grainSize_um": 50.0,
            "austTemp_C": 1050.0, "agingTemp_C": 550.0, "agingTime_h": 4.0,
        },
        # Silent default today: an unknown alloy is solved with the AISI 4140 data.
        "edge_unknown_alloy": {"alloy": "Unobtainium XYZ", "coolingRate_C_s": 10.0},
    },
    "lpbf_fatigue_fracture": {
        # MurakamiFatigueLab defaults (Ti-6Al-4V, 45 um, internal, R=-1, 240 MPa).
        "ti64_ui_defaults": {"alloyName": "Ti-6Al-4V", "sqrtArea_um": 45, "location": "internal",
                             "stressRatio_R": -1.0, "stressAmplitude_MPa": 240},
        "ss316l_surface_r01": {"alloyName": "316L SS", "sqrtArea_um": 120, "location": "surface",
                               "stressRatio_R": 0.1, "stressAmplitude_MPa": 180},
        "in718_subsurface": {"alloyName": "Inconel 718", "sqrtArea_um": 30, "location": "sub-surface",
                             "stressRatio_R": -1.0, "stressAmplitude_MPa": 300},
        "alsi10mg_large_pore": {"alloyName": "AlSi10Mg", "sqrtArea_um": 400, "location": "internal",
                                "stressRatio_R": 0.1, "stressAmplitude_MPa": 90},
        # Silent default today: an unknown alloy uses the Ti-6Al-4V constants.
        "edge_unknown_alloy": {"alloyName": "Unobtanium-X", "sqrtArea_um": 45},
    },
}

# Solvers without a __main__ run through a driver script (path relative to python/).
MODULE_DRIVERS: Dict[str, str] = {
    "lpbf_fatigue_fracture": "tools/phase6a_fatigue_golden_driver.py",
}


def _fatigue_table(table):
    return {name: dict(vars(row)) for name, row in table.items()}


# Solver-local tables snapshotted from the bound base blob (_source_tables.json).
TABLE_TARGETS = {
    "kinetics_ttt_cct_solver": ("ALLOY_KINETICS_DB", lambda t: t),
    "lpbf_fatigue_fracture": ("ALLOY_FATIGUE_DATABASE", _fatigue_table),
}

# (solver, case) -> validation error code expected after the structural migration.
EXPECTED_BEHAVIOUR_CHANGES = {
    ("kinetics_ttt_cct_solver", "edge_unknown_alloy"): "UNKNOWN_ALLOY",
    ("lpbf_fatigue_fracture", "edge_unknown_alloy"): "UNKNOWN_ALLOY",
}

# Documented value changes that a step_b re-bless may record although they are not
# bounded numeric drift: solver -> {drift-row key pattern: description}. Each listed row
# is checked exactly by capture_phase6a_golden.documented_change_violation against the
# re-blessed document (never by a looser bound); any other row keeps the default guard.
EXPECTED_DOCUMENTED_VALUE_CHANGES = {
    "kinetics_ttt_cct_solver": {
        r"cctContinuousCoolingMap\[\d+\]\.predictedHardness_HV":
            "HV = round(10.5 * HRC + 40) (unsourced) -> ASTM E140 Table 1 interpolation for the "
            "non-austenitic steels (AISI 4140/4340/D2) in HRC 20-68; null for other alloy "
            "classes and outside HRC 20-68",
        r"cctContinuousCoolingMap\[\d+\]\.predictedHardness_HV_status":
            "new status key next to predictedHardness_HV (converted / unavailable reason)",
        # Engine-fix lane fx-kinetics: non-steel alloys unavailable (steel-only model), registry
        # placeholders null, TTT floor flags, floor/step-limited CCT starts null, LSW unit fix.
        # Each pattern is verified exactly by tools/kinetics_documented_changes.row_violation.
        **_kinetics_fx.DESCRIPTIONS,
    },
    # Physics audit KS-2 / KS-3 (El-Haddad a0 with Murakami Y; Paris growth of sqrt(area) from the defect
    # size, Y by location, dK = Kmax for R <= 0, closed-form life). Every row is accepted only if the whole
    # re-blessed document matches tools/fatigue_documented_changes.document_problems (independent
    # recomputation from the d33b6f5 table snapshot, numerical Paris quadrature), never by a bound.
    "lpbf_fatigue_fracture": dict(_fatigue_fx.DESCRIPTIONS),
}
