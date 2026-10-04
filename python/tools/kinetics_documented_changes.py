"""
Documented value changes of kinetics_ttt_cct_solver made by the engine-fix lane fx-kinetics.

Used by capture_phase6a_golden.documented_change_violation (via
phase6a_t2b_golden_cases.EXPECTED_DOCUMENTED_VALUE_CHANGES) and by
test_phase6a_t2b_migration. Every drift row of the listed patterns is verified EXACTLY against
the re-blessed document; nothing is accepted by a numeric tolerance except the display rounding
of a value that is recomputed here by an independent formula (LSW).

Changes (the d33b6f5 / 7f3f803 base golden -> now):

1. Non-steel alloys (registry class without "Steel": Inconel 718, Ti-6Al-4V, Al 7075): the steel
   template outputs are unavailable. TTT curves are null; the CCT rows keep the cooling-rate grid
   but start temperature/time, primary microstructure, phase fractions and HRC are null;
   the CALPHAD-vs-kinetics equilibrium text and martensite fields, the critical cooling rate
   are null. Every one carries an explicit status and the reason "kinetics model is steel-only".
2. Registry placeholders (alloy_registry.KINETICS_PLACEHOLDERS: in718 and al7075 Ms/Mf) are null
   in alloyMetadata and criticalTransformationTemperatures, with a status.
3. Steels: TTT points get floorHit (True only where tStart_s is the 1 ms floor); a CCT diffusional
   start that is on the floor or reached by one integration step alone is null with the status
   unavailable-ttt-incubation-floor-or-step-limited and a reason. New status/summary keys.
4. LSW: K_LSW used the mole fraction where mol/m^3 is needed (K too small by 1/Vm = 9.1e4) and
   had a 1e-3 nm^3/h floor. The radius, strengthening value and regime of every row are
   recomputed here with an independent SI formula for both the old and the new definition.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PYTHON_DIR = Path(__file__).resolve().parent.parent
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import alloy_registry  # noqa: E402 (python/ module)
import input_validation  # noqa: E402 (python/ module)
import physical_constants  # noqa: E402 (python/ module)

STEEL_ONLY_REASON = "kinetics model is steel-only"
ST_STEEL_ONLY = "unavailable-kinetics-model-steel-only"
ST_PLACEHOLDER = "unavailable-registry-placeholder"
ST_REGISTRY = "registry-screening-value"
ST_START_FLOOR = "unavailable-ttt-incubation-floor-or-step-limited"
ST_START_SCHEIL = "diffusional-start-scheil-additivity"
ST_START_ATHERMAL = "athermal-martensite-no-diffusional-start-above-ms"
ST_LOOKUP = "steel-lookup-by-ccr-band-not-computed"
ST_STATIC_TEXT = "static-text-not-a-calphad-calculation"
ST_ILLUSTRATIVE = "steel-illustrative-correlation"
TTT_FLOOR_S = 0.001
LEGACY_R_GAS = 8.314  # the d33b6f5 / 7f3f803 base goldens were captured with this R

# ----------------------------------------------------------------------------------------------
# LSW oracle: r^3 - r0^3 = K t, K = 8 gamma D C_e Vm^2 / (9 R T) with C_e in mol/m^3.
# Lifshitz & Slyozov, J. Phys. Chem. Solids 19 (1961) 35; Wagner, Z. Elektrochem. 65 (1961) 581.
# Dimensional check: (J/m^2)(m^2/s)(mol/m^3)(m^3/mol)^2 / (J/mol) = m^3/s.
_GAMMA_J_M2 = 0.045
_X_E = 0.02
_VM_M3_MOL = 1.1e-5
_D0_M2_S = 1.2e-4
_R0_NM = 1.5
_R_CRIT_NM = 9.0
_OROWAN_PEAK_MPA = 280.0
_OLD_K_FLOOR_NM3_H = 1e-3


def _k_si_m3_s(q_j_mol: float, t_k: float, r_gas: float, concentration_mol_m3: float) -> float:
    d = _D0_M2_S * math.exp(-q_j_mol / (r_gas * t_k))
    return 8.0 * _GAMMA_J_M2 * d * concentration_mol_m3 * _VM_M3_MOL ** 2 / (9.0 * r_gas * t_k)


def lsw_radius_nm(q_kj_mol: float, aging_c: float, time_h: float, r_gas: float, *, corrected: bool) -> float:
    """Unrounded mean radius (nm). corrected=False reproduces the old unit error and floor."""
    t_k = aging_c + 273.15
    conc = _X_E / _VM_M3_MOL if corrected else _X_E
    k_nm3_h = _k_si_m3_s(q_kj_mol * 1e3, t_k, r_gas, conc) * 1e27 * 3600.0
    if not corrected:
        k_nm3_h = max(_OLD_K_FLOOR_NM3_H, k_nm3_h)
    return (_R0_NM ** 3 + k_nm3_h * time_h) ** (1.0 / 3.0)


def lsw_boost_mpa(r_nm: float) -> float:
    if r_nm <= _R_CRIT_NM:
        return _OROWAN_PEAK_MPA * math.sqrt(r_nm / _R_CRIT_NM)
    return _OROWAN_PEAK_MPA * (_R_CRIT_NM / r_nm)


def lsw_regime(r_nm: float) -> str:
    return ("Weak-Pair / Strong-Pair Cutting" if r_nm <= _R_CRIT_NM
            else "Orowan Dislocation Looping (Over-aged)")


# ----------------------------------------------------------------------------------------------
class _Ctx:
    def __init__(self, new_stdout: Dict[str, Any], new_r_gas: float):
        self.n = new_stdout
        self.alloy_type = new_stdout["alloyMetadata"]["type"]
        self.steel = "Steel" in self.alloy_type
        self.new_r = new_r_gas
        model = new_stdout.get("kineticsModel") or {}
        self.model = model
        self.reg_id = model.get("registryAlloyId")

    def cct_row(self, i: int) -> Dict[str, Any]:
        return self.n["cctContinuousCoolingMap"][i]


def _idx(key: str) -> int:
    return int(re.search(r"\[(\d+)\]", key).group(1))


def _is_null_change(row) -> Optional[str]:
    if row["kind"] != "changed" or row["new"] is not None or row["old"] is None:
        return f"{row['key']}: expected a value changed to null, got {row['kind']} {row['old']!r} -> {row['new']!r}"
    return None


def _is_added(row, expected) -> Optional[str]:
    if row["kind"] != "added" or row["new"] != expected or type(row["new"]) is not type(expected):
        return f"{row['key']}: expected an added {expected!r}, got {row['kind']} {row['new']!r}"
    return None


def _need_non_steel(ctx: _Ctx, row) -> Optional[str]:
    if ctx.steel:
        return f"{row['key']}: a steel alloy ({ctx.alloy_type}) keeps this value"
    if ctx.model.get("status") != "unavailable" or ctx.model.get("reason") != STEEL_ONLY_REASON:
        return f"{row['key']}: kineticsModel is not unavailable with the reason {STEEL_ONLY_REASON!r}"
    return None


# --- non-steel: curves, CCT row values, equilibrium/martensite fields -------------------------
def _h_ttt_removed(row, ctx):
    problem = _need_non_steel(ctx, row)
    if problem:
        return problem
    if row["kind"] != "removed" or ctx.n.get("tttIsothermalCurves") is not None:
        return f"{row['key']}: expected a removed TTT point and tttIsothermalCurves null"
    return None


def _h_ttt_null(row, ctx):
    problem = _need_non_steel(ctx, row)
    if problem:
        return problem
    if row["kind"] != "added" or row["new"] is not None or ctx.n.get("tttIsothermalCurves", 0) is not None:
        return f"{row['key']}: expected tttIsothermalCurves added as null"
    return None


def _h_cct_nonsteel_null(row, ctx):
    return _need_non_steel(ctx, row) or _is_null_change(row)


def _h_cct_start_null(row, ctx):
    """transformedStartTemp_C / Time_s / primaryMicrostructure -> null: non-steel, or a steel floor row."""
    problem = _is_null_change(row)
    if problem:
        return problem
    entry = ctx.cct_row(_idx(row["key"]))
    if ctx.steel:
        if entry.get("transformedStart_status") != ST_START_FLOOR:
            return f"{row['key']}: null start of a steel row whose status is {entry.get('transformedStart_status')!r}"
        if any(entry.get(k) is not None for k in ("transformedStartTemp_C", "transformedStartTime_s",
                                                 "primaryMicrostructure")):
            return f"{row['key']}: a floor row must have all three start fields null"
        return None
    return _need_non_steel(ctx, row)


def _h_cct_status_added(row, ctx):
    """Added per-row status keys; the expected value follows from the (verified) row content."""
    entry = ctx.cct_row(_idx(row["key"]))
    leaf = row["key"].rsplit(".", 1)[-1]
    if not ctx.steel:
        problem = _need_non_steel(ctx, row)
        if problem:
            return problem
        expected = STEEL_ONLY_REASON if leaf == "unavailableReason" else ST_STEEL_ONLY
        return _is_added(row, expected)
    if leaf in ("phaseFractions_status", "predictedHardness_HRC_status"):
        return _is_added(row, ST_LOOKUP)
    if leaf == "transformedStart_status":
        if entry.get("primaryMicrostructure") is None:
            expected = ST_START_FLOOR
        elif entry.get("primaryMicrostructure") == "Martensite (Athermal)":
            expected = ST_START_ATHERMAL
        else:
            expected = ST_START_SCHEIL
        return _is_added(row, expected)
    if leaf == "unavailableReason":
        if entry.get("transformedStart_status") == ST_START_FLOOR:
            if row["kind"] != "added" or not str(row["new"]).startswith("the Scheil-additivity start is not a model result"):
                return f"{row['key']}: a floor row needs the floor reason, got {row['new']!r}"
            return None
        return _is_added(row, None)
    return f"{row['key']}: unknown status key"


def _h_gap_null(row, ctx):
    return _need_non_steel(ctx, row) or _is_null_change(row)


def _h_gap_status_added(row, ctx):
    leaf = row["key"].rsplit(".", 1)[-1]
    block = "equilibriumPrediction" if ".equilibriumPrediction." in row["key"] else "kineticRealityAtSelectedCooling"
    if not ctx.steel:
        problem = _need_non_steel(ctx, row)
        if problem:
            return problem
        return _is_added(row, ST_STEEL_ONLY if leaf == "status" else STEEL_ONLY_REASON)
    if leaf == "status":
        return _is_added(row, ST_STATIC_TEXT if block == "equilibriumPrediction" else ST_ILLUSTRATIVE)
    if row["kind"] != "added" or not isinstance(row["new"], str) or not row["new"]:
        return f"{row['key']}: expected an added reason text"
    return None


def _h_ccr_null(row, ctx):
    return _need_non_steel(ctx, row) or _is_null_change(row)


# --- placeholders -----------------------------------------------------------------------------
def _h_placeholder_null(row, ctx):
    key = row["key"].rsplit(".", 1)[-1]  # Ms_C / Mf_C
    if (ctx.reg_id, key) not in alloy_registry.KINETICS_PLACEHOLDERS:
        return f"{row['key']}: ({ctx.reg_id}, {key}) is not flagged in alloy_registry.KINETICS_PLACEHOLDERS"
    return _is_null_change(row)


def _h_critical_status_added(row, ctx):
    leaf = row["key"].rsplit(".", 1)[-1]
    if leaf == "CriticalCoolingRate_CCR_status":
        return _is_added(row, ST_REGISTRY if ctx.steel else ST_STEEL_ONLY)
    base = leaf[:-len("_status")]
    flagged = (ctx.reg_id, base) in alloy_registry.KINETICS_PLACEHOLDERS
    return _is_added(row, ST_PLACEHOLDER if flagged else ST_REGISTRY)


# --- steel floor flags and summary blocks -----------------------------------------------------
def _h_floor_hit_added(row, ctx):
    if not ctx.steel:
        return f"{row['key']}: floorHit exists only for the steel TTT points"
    if row["kind"] != "added" or not isinstance(row["new"], bool):
        return f"{row['key']}: expected an added bool"
    point = ctx.n["tttIsothermalCurves"][_idx(row["key"])]
    if row["new"] and point["tStart_s"] != TTT_FLOOR_S:
        return f"{row['key']}: floorHit true but tStart_s {point['tStart_s']!r} is not the floor"
    if not row["new"] and point["tStart_s"] < TTT_FLOOR_S:
        return f"{row['key']}: floorHit false but tStart_s is below the floor"
    return None


def _h_model_added(row, ctx):
    if row["kind"] != "added":
        return f"{row['key']}: expected an added key"
    leaf = row["key"]
    if leaf == "kineticsModel.status":
        return _is_added(row, "available" if ctx.steel else "unavailable")
    if leaf == "kineticsModel.reason":
        return _is_added(row, None if ctx.steel else STEEL_ONLY_REASON)
    if leaf == "kineticsModel.registryAlloyId":
        # independent of the solver: the registry id the request alloy name resolves to
        record = input_validation.require_known_alloy(ctx.n["alloy"], alloy_registry.DOMAIN_KINETICS, field="alloy")
        return _is_added(row, record.id)
    return None


def _h_floor_block_added(row, ctx):
    if row["kind"] != "added":
        return f"{row['key']}: expected an added key"
    block = ctx.n["tttIncubationFloor"]
    curves = ctx.n.get("tttIsothermalCurves")
    leaf = row["key"].rsplit(".", 1)[-1]
    if leaf == "pointCount":
        return _is_added(row, len(curves) if ctx.steel else None)
    if leaf == "floorHitCount":
        return _is_added(row, sum(1 for p in curves if p["floorHit"]) if ctx.steel else None)
    if leaf == "floorValue_s":
        return _is_added(row, TTT_FLOOR_S)
    if leaf == "status":
        if not ctx.steel:
            return _is_added(row, ST_STEEL_ONLY)
        return _is_added(row, "floor-hit-points-flagged" if block["floorHitCount"] else "no-floor-hit-points")
    return None


# --- LSW --------------------------------------------------------------------------------------
def _h_lsw(row, ctx):
    i = _idx(row["key"])
    leaf = row["key"].rsplit(".", 1)[-1]
    q = ctx.n["alloyMetadata"]["Q_diff_kJ_mol"]
    aging_c = ctx.n["inputParameters"]["agingTemp_C"]
    t_h = ctx.n["lswPrecipitateCoarsening"][i]["agingTime_h"]
    r_new = lsw_radius_nm(q, aging_c, t_h, ctx.new_r, corrected=True)
    r_old = lsw_radius_nm(q, aging_c, t_h, LEGACY_R_GAS, corrected=False)
    if leaf == "meanRadius_nm":
        exp_old, exp_new, tol = r_old, r_new, 0.005
    elif leaf == "precipitationHardening_MPa":
        exp_old, exp_new, tol = lsw_boost_mpa(r_old), lsw_boost_mpa(r_new), 0.05
    else:
        old_text, new_text = lsw_regime(r_old), lsw_regime(r_new)
        if row["kind"] != "changed" or row["old"] != old_text or row["new"] != new_text:
            return f"{row['key']}: regime {row['old']!r} -> {row['new']!r}, expected {old_text!r} -> {new_text!r}"
        return None
    if row["kind"] != "numeric" or type(row["old"]) is not float or type(row["new"]) is not float:
        return f"{row['key']}: expected a float change, got {row['kind']}"
    if abs(row["old"] - exp_old) > tol + 1e-9:
        return f"{row['key']}: old {row['old']!r} is not the old formula value {exp_old!r}"
    if abs(row["new"] - exp_new) > tol + 1e-9:
        return f"{row['key']}: new {row['new']!r} is not the SI oracle value {exp_new!r}"
    return None


# (pattern, handler); the patterns are the keys of EXPECTED_DOCUMENTED_VALUE_CHANGES.
_CCT = r"cctContinuousCoolingMap\[\d+\]"
_GAP = r"calphadVsKineticsGap"
HANDLERS: Dict[str, Callable] = {
    r"tttIsothermalCurves\[\d+\]\.(?!floorHit).+": _h_ttt_removed,
    r"tttIsothermalCurves": _h_ttt_null,
    r"tttIsothermalCurves\[\d+\]\.floorHit": _h_floor_hit_added,
    _CCT + r"\.(predictedHardness_HRC|phaseFractions\.(Martensite_pct|Bainite_pct|Pearlite_Ferrite_pct|RetainedAustenite_pct))":
        _h_cct_nonsteel_null,
    _CCT + r"\.(transformedStartTemp_C|transformedStartTime_s|primaryMicrostructure)": _h_cct_start_null,
    _CCT + r"\.(transformedStart_status|phaseFractions_status|predictedHardness_HRC_status|unavailableReason)":
        _h_cct_status_added,
    _GAP + r"\.equilibriumPrediction\.(stablePhasesAtRT|martensiteFraction|soluteSupersaturation)": _h_gap_null,
    _GAP + r"\.kineticRealityAtSelectedCooling\.(criticalCoolingRate_C_s|isSuppressedEquilibrium|"
           r"predictedMartensite_pct|diffusionSuppressionIndex|verdict)": _h_gap_null,
    _GAP + r"\.(equilibriumPrediction|kineticRealityAtSelectedCooling)\.(status|reason)": _h_gap_status_added,
    r"criticalTransformationTemperatures\.CriticalCoolingRate_CCR_C_s": _h_ccr_null,
    r"(alloyMetadata|criticalTransformationTemperatures)\.(Ms_C|Mf_C)": _h_placeholder_null,
    r"criticalTransformationTemperatures\.(Ms_C_status|Mf_C_status|CriticalCoolingRate_CCR_status)":
        _h_critical_status_added,
    r"kineticsModel\.(status|reason|registryAlloyId)": _h_model_added,
    r"kineticsModel\.(scope|illustrativeOnly|note|placeholderParameters(\[\d+\])?|"
    r"lswPrecipitateCoarsening\.(status|note))": lambda row, ctx: (
        None if row["kind"] == "added" else f"{row['key']}: expected an added key"),
    r"tttIncubationFloor\.(status|floorValue_s|pointCount|floorHitCount)": _h_floor_block_added,
    r"tttIncubationFloor\.note": lambda row, ctx: (
        None if row["kind"] == "added" else f"{row['key']}: expected an added key"),
    r"lswPrecipitateCoarsening\[\d+\]\.(meanRadius_nm|precipitationHardening_MPa|strengtheningMechanism)": _h_lsw,
}

# Row kinds each pattern may be documented for. A row of another kind (for example the bounded
# numeric R drift of a steel TTT time) is NOT a documented change: it goes through the default guard.
_A, _C, _R, _N = {"added"}, {"changed"}, {"removed"}, {"numeric", "changed"}
HANDLER_KINDS: Dict[str, set] = {
    r"tttIsothermalCurves\[\d+\]\.(?!floorHit).+": _R,
    r"tttIsothermalCurves": _A,
    r"tttIsothermalCurves\[\d+\]\.floorHit": _A,
    _CCT + r"\.(predictedHardness_HRC|phaseFractions\.(Martensite_pct|Bainite_pct|Pearlite_Ferrite_pct|RetainedAustenite_pct))": _C,
    _CCT + r"\.(transformedStartTemp_C|transformedStartTime_s|primaryMicrostructure)": _C,
    _CCT + r"\.(transformedStart_status|phaseFractions_status|predictedHardness_HRC_status|unavailableReason)": _A,
    _GAP + r"\.equilibriumPrediction\.(stablePhasesAtRT|martensiteFraction|soluteSupersaturation)": _C,
    _GAP + r"\.kineticRealityAtSelectedCooling\.(criticalCoolingRate_C_s|isSuppressedEquilibrium|"
           r"predictedMartensite_pct|diffusionSuppressionIndex|verdict)": _C,
    _GAP + r"\.(equilibriumPrediction|kineticRealityAtSelectedCooling)\.(status|reason)": _A,
    r"criticalTransformationTemperatures\.CriticalCoolingRate_CCR_C_s": _C,
    r"(alloyMetadata|criticalTransformationTemperatures)\.(Ms_C|Mf_C)": _C,
    r"criticalTransformationTemperatures\.(Ms_C_status|Mf_C_status|CriticalCoolingRate_CCR_status)": _A,
    r"kineticsModel\.(status|reason|registryAlloyId)": _A,
    r"kineticsModel\.(scope|illustrativeOnly|note|placeholderParameters(\[\d+\])?|"
    r"lswPrecipitateCoarsening\.(status|note))": _A,
    r"tttIncubationFloor\.(status|floorValue_s|pointCount|floorHitCount)": _A,
    r"tttIncubationFloor\.note": _A,
    r"lswPrecipitateCoarsening\[\d+\]\.(meanRadius_nm|precipitationHardening_MPa|strengtheningMechanism)": _N,
}
assert set(HANDLER_KINDS) == set(HANDLERS)

DESCRIPTIONS: Dict[str, str] = {
    r"tttIsothermalCurves\[\d+\]\.(?!floorHit).+":
        "non-steel alloys: the TTT curves (unsourced alloy-class constants, steel phase labels) are removed",
    r"tttIsothermalCurves": "non-steel alloys: tttIsothermalCurves is null (kinetics model is steel-only)",
    r"tttIsothermalCurves\[\d+\]\.floorHit":
        "steel TTT points: new floorHit flag (true only where tStart_s is the 1 ms floor)",
    _CCT + r"\.(predictedHardness_HRC|phaseFractions\.(Martensite_pct|Bainite_pct|Pearlite_Ferrite_pct|RetainedAustenite_pct))":
        "non-steel alloys: phase fractions and HRC are null (steel lookup table)",
    _CCT + r"\.(transformedStartTemp_C|transformedStartTime_s|primaryMicrostructure)":
        "CCT start null: non-steel (steel-only), or a steel start on the TTT floor / one integration step",
    _CCT + r"\.(transformedStart_status|phaseFractions_status|predictedHardness_HRC_status|unavailableReason)":
        "new per-row status keys",
    _GAP + r"\.equilibriumPrediction\.(stablePhasesAtRT|martensiteFraction|soluteSupersaturation)":
        "non-steel alloys: steel equilibrium text is null",
    _GAP + r"\.kineticRealityAtSelectedCooling\.(criticalCoolingRate_C_s|isSuppressedEquilibrium|"
           r"predictedMartensite_pct|diffusionSuppressionIndex|verdict)":
        "non-steel alloys: steel martensite/verdict fields are null",
    _GAP + r"\.(equilibriumPrediction|kineticRealityAtSelectedCooling)\.(status|reason)": "new status/reason keys",
    r"criticalTransformationTemperatures\.CriticalCoolingRate_CCR_C_s":
        "non-steel alloys: the steel critical cooling rate is null",
    r"(alloyMetadata|criticalTransformationTemperatures)\.(Ms_C|Mf_C)":
        "registry placeholders (alloy_registry.KINETICS_PLACEHOLDERS) are null",
    r"criticalTransformationTemperatures\.(Ms_C_status|Mf_C_status|CriticalCoolingRate_CCR_status)":
        "new status keys for Ms/Mf/CCR",
    r"kineticsModel\.(status|reason|registryAlloyId)": "new kineticsModel block",
    r"kineticsModel\.(scope|illustrativeOnly|note|placeholderParameters(\[\d+\])?|"
    r"lswPrecipitateCoarsening\.(status|note))": "new kineticsModel block",
    r"tttIncubationFloor\.(status|floorValue_s|pointCount|floorHitCount)": "new tttIncubationFloor block",
    r"tttIncubationFloor\.note": "new tttIncubationFloor block",
    r"lswPrecipitateCoarsening\[\d+\]\.(meanRadius_nm|precipitationHardening_MPa|strengtheningMechanism)":
        "LSW unit fix: C_e in mol/m^3 (x_e/Vm), no 1e-3 nm^3/h floor; checked against an independent SI formula",
}
assert set(HANDLERS) == set(DESCRIPTIONS)


def row_violation(row: Dict[str, Any], new_stdout: Dict[str, Any],
                  new_r_gas: Optional[float] = None) -> Optional[str]:
    """None when ``row`` is exactly one of the documented changes above, else the problem."""
    if new_r_gas is None:
        new_r_gas = physical_constants.GAS_CONSTANT_R.value
    try:
        ctx = _Ctx(new_stdout, new_r_gas)
    except (KeyError, TypeError):
        return f"{row['key']}: re-blessed document lacks alloyMetadata.type"
    for pattern, handler in HANDLERS.items():
        if re.fullmatch(pattern, row["key"]) and row["kind"] in HANDLER_KINDS[pattern]:
            try:
                return handler(row, ctx)
            except (KeyError, IndexError, TypeError) as exc:
                return f"{row['key']}: cannot verify against the re-blessed document ({exc!r})"
    return f"{row['key']}: no documented-change handler"


def is_documented_row(key: str, kind: Optional[str]) -> bool:
    """Whether a drift row of this key and kind belongs to a documented change above."""
    return any(re.fullmatch(p, key) and (kind is None or kind in HANDLER_KINDS[p]) for p in HANDLERS)


def document_violations(new_stdout: Dict[str, Any], new_r_gas: Optional[float] = None) -> List[str]:
    """Whole-document checks of a kinetics result (also for rows that did not drift)."""
    if new_r_gas is None:
        new_r_gas = physical_constants.GAS_CONSTANT_R.value
    out: List[str] = []
    ctx = _Ctx(new_stdout, new_r_gas)
    q = new_stdout["alloyMetadata"]["Q_diff_kJ_mol"]
    aging_c = new_stdout["inputParameters"]["agingTemp_C"]
    for i, entry in enumerate(new_stdout["lswPrecipitateCoarsening"]):
        r = lsw_radius_nm(q, aging_c, entry["agingTime_h"], new_r_gas, corrected=True)
        if abs(entry["meanRadius_nm"] - r) > 0.005 + 1e-9:
            out.append(f"lswPrecipitateCoarsening[{i}].meanRadius_nm {entry['meanRadius_nm']} != SI oracle {r}")
        if abs(entry["precipitationHardening_MPa"] - lsw_boost_mpa(r)) > 0.05 + 1e-9:
            out.append(f"lswPrecipitateCoarsening[{i}].precipitationHardening_MPa mismatch")
        if entry["strengtheningMechanism"] != lsw_regime(r):
            out.append(f"lswPrecipitateCoarsening[{i}].strengtheningMechanism mismatch")
    if not ctx.steel:
        if ctx.model.get("status") != "unavailable" or new_stdout.get("tttIsothermalCurves") is not None:
            out.append("non-steel alloy must have kineticsModel unavailable and tttIsothermalCurves null")
        for i, row in enumerate(new_stdout["cctContinuousCoolingMap"]):
            fractions = list(row["phaseFractions"].values())
            if (any(v is not None for v in fractions) or row["predictedHardness_HRC"] is not None
                    or row["transformedStartTemp_C"] is not None or row["primaryMicrostructure"] is not None):
                out.append(f"cctContinuousCoolingMap[{i}]: a non-steel row carries steel-template values")
    else:
        curves = new_stdout["tttIsothermalCurves"]
        block = new_stdout["tttIncubationFloor"]
        if curves is None:
            return out + ["a steel alloy must have TTT curves"]
        if (block["pointCount"], block["floorHitCount"]) != (len(curves), sum(1 for p in curves if p["floorHit"])):
            out.append("tttIncubationFloor counts do not match the TTT points")
        for i, point in enumerate(curves):
            if point["floorHit"] != (point["tStart_s"] == TTT_FLOOR_S) and point["floorHit"]:
                out.append(f"tttIsothermalCurves[{i}]: floorHit true but tStart_s is not the floor")
            if not point["floorHit"] and point["tStart_s"] < TTT_FLOOR_S:
                out.append(f"tttIsothermalCurves[{i}]: tStart_s below the floor")
        for i, row in enumerate(new_stdout["cctContinuousCoolingMap"]):
            if row["transformedStart_status"] == ST_START_FLOOR and row["primaryMicrostructure"] is not None:
                out.append(f"cctContinuousCoolingMap[{i}]: floor-driven start still reports a microstructure")
    return out
