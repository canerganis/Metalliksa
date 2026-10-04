"""
Documented value changes of kinetics_ttt_cct_solver made by the engine-fix lane fx-kinetics.

Used by capture_phase6a_golden.documented_change_violation (via
phase6a_t2b_golden_cases.EXPECTED_DOCUMENTED_VALUE_CHANGES) and by
test_phase6a_t2b_migration. Every drift row of the listed patterns is verified EXACTLY against
the re-blessed document; nothing is accepted by a numeric tolerance except the display rounding
of a value that is recomputed here by an independent formula (LSW).

Because a drift row exists only where a value differs from the d33b6f5 base, a value that stays at
(or returns to) the base value produces no row. document_violations therefore also checks the
WHOLE re-blessed document against an independent expectation of every status, text and
availability field of the kinetics result.

Changes (the d33b6f5 / 7f3f803 base golden -> now):

1. Non-steel alloys (registry class without "Steel": Inconel 718, Ti-6Al-4V, Al 7075): the steel
   template outputs are unavailable. TTT curves are null; the CCT rows keep the cooling-rate grid
   but start temperature/time, primary microstructure, phase fractions and HRC are null;
   the CALPHAD-vs-kinetics equilibrium text, martensite fields, the critical cooling rate (also in
   alloyMetadata) and the eutectoid Ae1 are null. Every one carries an explicit status and the
   reason "kinetics model is steel-only".
2. Registry placeholders (alloy_registry.KINETICS_PLACEHOLDERS: in718 and al7075 Ms/Mf) are null
   in alloyMetadata and criticalTransformationTemperatures, with a status.
3. Steels: TTT points get floorHit (== tStart_s is the 1 ms floor). The diffusional CCT start of
   every steel row is null (the incubation law has no Ae3 asymptote; start not computed).
   A steel row with no diffusional start above Ms stays the athermal Ms row.
4. LSW: K_LSW used the mole fraction where mol/m^3 is needed (K too small by 1/Vm = 9.1e4) and
   had a 1e-3 nm^3/h floor. The radius, strengthening value and regime of every row are
   recomputed here with an independent SI formula for both the old and the new definition. An aging
   temperature at or above the registry Ae3 (steels: also Ae1) makes every LSW row null with a status.
5. Steel D2: the fixed equilibrium text names alloy carbides instead of cementite.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

PYTHON_DIR = Path(__file__).resolve().parent.parent
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import alloy_registry  # noqa: E402 (python/ module)
import hardness_conversion_e140 as e140  # noqa: E402 (python/ module)
import input_validation  # noqa: E402 (python/ module)
import physical_constants  # noqa: E402 (python/ module)

STEEL_ONLY_REASON = "kinetics model is steel-only"
ST_STEEL_ONLY = "unavailable-kinetics-model-steel-only"
ST_PLACEHOLDER = "unavailable-registry-placeholder"
ST_REGISTRY = "registry-screening-value"
ST_START_NO_ASYMPTOTE = "unavailable-ttt-incubation-law-no-ae3-asymptote"
ST_START_ATHERMAL = "athermal-martensite-no-diffusional-start-above-ms"
ST_LOOKUP = "steel-lookup-by-ccr-band-not-computed"
ST_STATIC_TEXT = "static-text-not-a-calphad-calculation"
ST_ILLUSTRATIVE = "steel-illustrative-correlation"
ST_LSW_ILLUSTRATIVE = "generic-constants-illustrative"
ST_LSW_ABOVE = "unavailable-aging-temperature-at-or-above-solvus"
TTT_FLOOR_S = 0.001
LEGACY_R_GAS = 8.314  # the d33b6f5 / 7f3f803 base goldens were captured with this R
CCT_RATES = (0.05, 0.2, 1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 500.0, 2000.0)
NO_ASYMPTOTE_REASON = "incubation law has no Ae3 asymptote; start not computed"
STEEL_PHASES = "Ferrite + Cementite / Equilibrium intermetallics"
D2_PHASES = "Ferrite + alloy carbides (M7C3 / M23C6)"
OLD_STEEL_PHASES = "Ferrite + Cementite / Equilibrium intermetallics"  # the base text, every alloy
ATHERMAL_LABEL = "Martensite (Athermal)"

# Independent copies of the solver texts (a typo or a rewording in the solver must be seen here).
NON_STEEL_NOTE = (
    "The TTT/CCT numeric curves of non-steel alloys come from unsourced alloy-class constants "
    "(nose temperature, rate prefactor, Avrami exponent) and steel-template phase labels, not from a "
    "sourced model of this alloy, so they are not reported."
)
STEEL_NOTE = (
    "Steel template with unsourced class constants: the TTT nose/prefactor/Avrami constants are not fitted "
    "to published data, and the CCT phase fractions and HRC are a lookup by cooling-rate band, not computed."
)
LSW_NOTE = (
    "K_LSW uses generic gamma, equilibrium concentration, molar volume and D0 shared by every alloy (only the "
    "activation energy is per alloy; one molar volume serves both the matrix concentration and the "
    "precipitate); the strengthening column is an unsourced screening curve."
)
TTT_FLOOR_NOTE = (
    "tStart_s is clamped to a 1 ms floor where the unsourced incubation law (no Ae3 asymptote) gives "
    "less; a point with floorHit true is that floor, not a model value, and its t50_s and tFinish_s "
    "are derived from it."
)
GAP_STEEL_EQ_REASON = "fixed steel text; no equilibrium (CALPHAD) calculation is performed here"
GAP_STEEL_REALITY_REASON = "steel template with unsourced registry critical cooling rate; screening only"
GAP_STEEL_EQ = {"martensiteFraction": "0.0% (Thermodynamically Forbidden in Equilibrium)",
                "soluteSupersaturation": "Near Zero (<0.01 wt% C in ferrite)"}
TTT_POINT_KEYS = ["temperature_C", "phase", "tStart_s", "t50_s", "tFinish_s", "avramiExponent_n",
                  "drivingForce_DeltaT_C", "floorHit"]

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


def lsw_limit(alloy_meta: Dict[str, Any], aging_c: float, steel: bool) -> Optional[Tuple[str, float]]:
    """(label, temperature) when the aging temperature is at or above the registry Ae3 (steels: Ae1)."""
    if aging_c >= alloy_meta["Ae3_C"]:
        return "Ae3 (solvus/transus)", alloy_meta["Ae3_C"]
    if steel and aging_c >= alloy_meta["Ae1_C"]:
        return "Ae1", alloy_meta["Ae1_C"]
    return None


def lsw_reason(aging_c: float, limit: Tuple[str, float]) -> str:
    return (f"aging temperature {aging_c:g} C is at or above the registry {limit[0]} of {limit[1]:g} C: "
            "no precipitate population, so no coarsening or strengthening is reported")


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

    def aging_limit(self) -> Optional[Tuple[str, float]]:
        meta = dict(self.n["alloyMetadata"])
        # Ae3/Ae1 are registry values that are never nulled for steels; for non-steels Ae1 is null in the
        # output and not used (only Ae3 limits a non-steel).
        meta.setdefault("Ae1_C", None)
        return lsw_limit(meta, self.n["inputParameters"]["agingTemp_C"], self.steel)


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


def _h_nonsteel_null(row, ctx):
    return _need_non_steel(ctx, row) or _is_null_change(row)


def _h_cct_start_null(row, ctx):
    """transformedStartTemp_C / Time_s / primaryMicrostructure -> null: non-steel, or a steel start not computed."""
    problem = _is_null_change(row)
    if problem:
        return problem
    entry = ctx.cct_row(_idx(row["key"]))
    if ctx.steel:
        if entry.get("transformedStart_status") != ST_START_NO_ASYMPTOTE:
            return f"{row['key']}: null start of a steel row whose status is {entry.get('transformedStart_status')!r}"
        if any(entry.get(k) is not None for k in ("transformedStartTemp_C", "transformedStartTime_s",
                                                 "primaryMicrostructure")):
            return f"{row['key']}: a not-computed start must have all three start fields null"
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
        return _is_added(row, STEEL_ONLY_REASON if leaf == "unavailableReason" else ST_STEEL_ONLY)
    if leaf in ("phaseFractions_status", "predictedHardness_HRC_status"):
        return _is_added(row, ST_LOOKUP)
    if leaf == "transformedStart_status":
        if entry.get("primaryMicrostructure") is None:
            expected = ST_START_NO_ASYMPTOTE
        elif entry.get("primaryMicrostructure") == ATHERMAL_LABEL:
            expected = ST_START_ATHERMAL
        else:
            return f"{row['key']}: a steel row reports a diffusional start ({entry.get('primaryMicrostructure')!r})"
        return _is_added(row, expected)
    if leaf == "unavailableReason":
        if entry.get("transformedStart_status") == ST_START_NO_ASYMPTOTE:
            return _is_added(row, NO_ASYMPTOTE_REASON)
        return _is_added(row, None)
    return f"{row['key']}: unknown status key"


def _h_gap_stable_phases(row, ctx):
    """Non-steel: null. Steel D2 only: the fixed text names alloy carbides instead of cementite."""
    if not ctx.steel:
        return _need_non_steel(ctx, row) or _is_null_change(row)
    if ctx.reg_id != "aisid2":
        return f"{row['key']}: only AISI D2 changes its fixed equilibrium text"
    if row["kind"] != "changed" or row["old"] != OLD_STEEL_PHASES or row["new"] != D2_PHASES:
        return f"{row['key']}: expected {OLD_STEEL_PHASES!r} -> {D2_PHASES!r}, got {row['old']!r} -> {row['new']!r}"
    return None


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
    return _is_added(row, GAP_STEEL_EQ_REASON if block == "equilibriumPrediction" else GAP_STEEL_REALITY_REASON)


# --- placeholders and other withdrawn registry echoes -------------------------------------------
def _h_placeholder_null(row, ctx):
    key = row["key"].rsplit(".", 1)[-1]  # Ms_C / Mf_C
    if (ctx.reg_id, key) not in alloy_registry.KINETICS_PLACEHOLDERS:
        return f"{row['key']}: ({ctx.reg_id}, {key}) is not flagged in alloy_registry.KINETICS_PLACEHOLDERS"
    return _is_null_change(row)


def _h_critical_status_added(row, ctx):
    leaf = row["key"].rsplit(".", 1)[-1]
    if leaf in ("CriticalCoolingRate_CCR_status", "Ae1_C_status"):
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
    if row["new"] != (point["tStart_s"] == TTT_FLOOR_S):
        return f"{row['key']}: floorHit {row['new']!r} but tStart_s is {point['tStart_s']!r}"
    return None


def _h_model_added(row, ctx):
    if row["kind"] != "added":
        return f"{row['key']}: expected an added key"
    if row["key"] == "kineticsModel.status":
        return _is_added(row, "available" if ctx.steel else "unavailable")
    if row["key"] == "kineticsModel.reason":
        return _is_added(row, None if ctx.steel else STEEL_ONLY_REASON)
    if row["key"] == "kineticsModel.registryAlloyId":
        # independent of the solver: the registry id the request alloy name resolves to
        record = input_validation.require_known_alloy(ctx.n["alloy"], alloy_registry.DOMAIN_KINETICS, field="alloy")
        return _is_added(row, record.id)
    return None  # the other keys are compared exactly by document_violations


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


def _h_added_key(row, ctx):
    return None if row["kind"] == "added" else f"{row['key']}: expected an added key"


# --- LSW --------------------------------------------------------------------------------------
def _h_lsw(row, ctx):
    i = _idx(row["key"])
    leaf = row["key"].rsplit(".", 1)[-1]
    q = ctx.n["alloyMetadata"]["Q_diff_kJ_mol"]
    aging_c = ctx.n["inputParameters"]["agingTemp_C"]
    t_h = ctx.n["lswPrecipitateCoarsening"][i]["agingTime_h"]
    unavailable = ctx.aging_limit() is not None
    r_new = lsw_radius_nm(q, aging_c, t_h, ctx.new_r, corrected=True)
    r_old = lsw_radius_nm(q, aging_c, t_h, LEGACY_R_GAS, corrected=False)
    if leaf == "meanRadius_nm":
        exp_old, exp_new, tol = r_old, r_new, 0.005
    elif leaf == "precipitationHardening_MPa":
        exp_old, exp_new, tol = lsw_boost_mpa(r_old), lsw_boost_mpa(r_new), 0.05
    else:
        old_text = lsw_regime(r_old)
        new_text = None if unavailable else lsw_regime(r_new)
        if row["kind"] != "changed" or row["old"] != old_text or row["new"] != new_text:
            return f"{row['key']}: regime {row['old']!r} -> {row['new']!r}, expected {old_text!r} -> {new_text!r}"
        return None
    if unavailable:
        if row["kind"] != "changed" or row["new"] is not None or type(row["old"]) is not float:
            return f"{row['key']}: aging above the solvus must give null, got {row['kind']} {row['new']!r}"
        if abs(row["old"] - exp_old) > tol + 1e-9:
            return f"{row['key']}: old {row['old']!r} is not the old formula value {exp_old!r}"
        return None
    if row["kind"] != "numeric" or type(row["old"]) is not float or type(row["new"]) is not float:
        return f"{row['key']}: expected a float change, got {row['kind']}"
    if abs(row["old"] - exp_old) > tol + 1e-9:
        return f"{row['key']}: old {row['old']!r} is not the old formula value {exp_old!r}"
    if abs(row["new"] - exp_new) > tol + 1e-9:
        return f"{row['key']}: new {row['new']!r} is not the SI oracle value {exp_new!r}"
    return None


def _h_lsw_status_added(row, ctx):
    return _is_added(row, ST_LSW_ABOVE if ctx.aging_limit() is not None else ST_LSW_ILLUSTRATIVE)


# One rule per documented change: (pattern, row kinds it may be documented for, handler, description).
# A row of another kind (for example the bounded numeric R drift of a steel TTT time) is NOT a
# documented change: it goes through the default guard.
_A, _C, _R, _N = {"added"}, {"changed"}, {"removed"}, {"numeric", "changed"}
_CCT = r"cctContinuousCoolingMap\[\d+\]"
_GAP = r"calphadVsKineticsGap"
_LSW = r"lswPrecipitateCoarsening\[\d+\]"
_RULES: List[Tuple[str, set, Callable, str]] = [
    (r"tttIsothermalCurves\[\d+\]\.(?!floorHit).+", _R, _h_ttt_removed,
     "non-steel alloys: the TTT curves (unsourced alloy-class constants, steel phase labels) are removed"),
    (r"tttIsothermalCurves", _A, _h_ttt_null, "non-steel alloys: tttIsothermalCurves is null (kinetics model is steel-only)"),
    (r"tttIsothermalCurves\[\d+\]\.floorHit", _A, _h_floor_hit_added,
     "steel TTT points: new floorHit flag (== tStart_s is the 1 ms floor)"),
    (_CCT + r"\.(predictedHardness_HRC|phaseFractions\.(Martensite_pct|Bainite_pct|Pearlite_Ferrite_pct|RetainedAustenite_pct))",
     _C, _h_nonsteel_null, "non-steel alloys: phase fractions and HRC are null (steel lookup table)"),
    (_CCT + r"\.(transformedStartTemp_C|transformedStartTime_s|primaryMicrostructure)", _C, _h_cct_start_null,
     "CCT start null: non-steel (steel-only) or a steel diffusional start (incubation law has no Ae3 asymptote)"),
    (_CCT + r"\.(transformedStart_status|phaseFractions_status|predictedHardness_HRC_status|unavailableReason)", _A,
     _h_cct_status_added, "new per-row status keys"),
    (_GAP + r"\.equilibriumPrediction\.stablePhasesAtRT", _C, _h_gap_stable_phases,
     "non-steel alloys: steel equilibrium text is null; AISI D2 names alloy carbides"),
    (_GAP + r"\.equilibriumPrediction\.(martensiteFraction|soluteSupersaturation)", _C, _h_nonsteel_null,
     "non-steel alloys: steel equilibrium text is null"),
    (_GAP + r"\.kineticRealityAtSelectedCooling\.(criticalCoolingRate_C_s|isSuppressedEquilibrium|"
            r"predictedMartensite_pct|diffusionSuppressionIndex|verdict)", _C, _h_nonsteel_null,
     "non-steel alloys: steel martensite/verdict fields are null"),
    (_GAP + r"\.(equilibriumPrediction|kineticRealityAtSelectedCooling)\.(status|reason)", _A, _h_gap_status_added,
     "new status/reason keys"),
    (r"criticalTransformationTemperatures\.(CriticalCoolingRate_CCR_C_s|Ae1_C)", _C, _h_nonsteel_null,
     "non-steel alloys: the steel critical cooling rate and the eutectoid Ae1 are null"),
    (r"alloyMetadata\.(Ae1_C|critical_cooling_rate_C_s)", _C, _h_nonsteel_null,
     "non-steel alloys: the steel-template registry echoes Ae1 and critical cooling rate are null"),
    (r"(alloyMetadata|criticalTransformationTemperatures)\.(Ms_C|Mf_C)", _C, _h_placeholder_null,
     "registry placeholders (alloy_registry.KINETICS_PLACEHOLDERS) are null"),
    (r"criticalTransformationTemperatures\.(Ae1_C_status|Ms_C_status|Mf_C_status|CriticalCoolingRate_CCR_status)", _A,
     _h_critical_status_added, "new status keys for Ae1/Ms/Mf/CCR"),
    (r"kineticsModel\.(status|reason|registryAlloyId)", _A, _h_model_added, "new kineticsModel block"),
    (r"kineticsModel\.(scope|illustrativeOnly|note|placeholderParameters(\[\d+\])?|"
     r"lswPrecipitateCoarsening\.(status|note|reason))", _A, _h_added_key, "new kineticsModel block"),
    (r"tttIncubationFloor\.(status|floorValue_s|pointCount|floorHitCount)", _A, _h_floor_block_added,
     "new tttIncubationFloor block"),
    (r"tttIncubationFloor\.note", _A, _h_added_key, "new tttIncubationFloor block"),
    (_LSW + r"\.(meanRadius_nm|precipitationHardening_MPa|strengtheningMechanism)", _N, _h_lsw,
     "LSW unit fix: C_e in mol/m^3 (x_e/Vm), no 1e-3 nm^3/h floor; null at or above the registry solvus "
     "(steels: Ae1); checked against an independent SI formula"),
    (_LSW + r"\.status", _A, _h_lsw_status_added, "new LSW row status"),
]
HANDLERS: Dict[str, Callable] = {p: h for p, _k, h, _d in _RULES}
HANDLER_KINDS: Dict[str, set] = {p: k for p, k, _h, _d in _RULES}
DESCRIPTIONS: Dict[str, str] = {p: d for p, _k, _h, d in _RULES}
assert len(HANDLERS) == len(_RULES)


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


# ----------------------------------------------------------------------------------------------
def document_violations(new_stdout: Dict[str, Any], new_r_gas: Optional[float] = None) -> List[str]:
    """Whole-document checks of a kinetics result, also for fields that did not drift.

    Every status, text, availability and flag field of the kinetics result is compared with an
    independent expectation derived from the alloy class (the registry descriptor type), the registry
    placeholder flags, the request inputs and the solver's own numeric tables.
    """
    if new_r_gas is None:
        new_r_gas = physical_constants.GAS_CONSTANT_R.value
    out: List[str] = []
    try:
        return _document_violations(new_stdout, new_r_gas, out)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        return out + [f"document is malformed ({exc!r})"]


def _document_violations(n: Dict[str, Any], new_r_gas: float, out: List[str]) -> List[str]:
    meta = n["alloyMetadata"]
    steel = "Steel" in meta["type"]
    record = input_validation.require_known_alloy(n["alloy"], alloy_registry.DOMAIN_KINETICS, field="alloy")
    reg_id = record.id
    placeholders = sorted(k for a, k in alloy_registry.KINETICS_PLACEHOLDERS if a == reg_id)
    params = n["inputParameters"]
    aging_c = params["agingTemp_C"]
    user_cr = params["selectedCoolingRate_C_s"]
    registry_values = {key: record.value(key, alloy_registry.DOMAIN_KINETICS)
                       for key in ("Ae3_C", "Ae1_C", "Ms_C", "Mf_C", "Q_diff_kJ_mol", "critical_cooling_rate_C_s")}
    # ---- alloyMetadata echoes
    for key, value in registry_values.items():
        if key in placeholders or (not steel and key in ("Ae1_C", "critical_cooling_rate_C_s")):
            expected = None
        else:
            expected = value
        if meta[key] != expected:
            out.append(f"alloyMetadata.{key} is {meta[key]!r}, expected {expected!r}")
    # ---- kineticsModel block
    limit = lsw_limit({"Ae3_C": registry_values["Ae3_C"], "Ae1_C": registry_values["Ae1_C"]}, aging_c, steel)
    lsw_status = ST_LSW_ABOVE if limit else ST_LSW_ILLUSTRATIVE
    expected_model = {
        "status": "available" if steel else "unavailable",
        "reason": None if steel else STEEL_ONLY_REASON,
        "scope": "steel-only",
        "registryAlloyId": reg_id,
        "illustrativeOnly": True,
        "note": STEEL_NOTE if steel else NON_STEEL_NOTE,
        "placeholderParameters": placeholders,
        "lswPrecipitateCoarsening": {"status": lsw_status, "note": LSW_NOTE,
                                     "reason": lsw_reason(aging_c, limit) if limit else None},
    }
    if n.get("kineticsModel") != expected_model:
        out.append(f"kineticsModel differs from the expected block: {n.get('kineticsModel')!r}")
    # ---- TTT curves and the floor block
    curves = n["tttIsothermalCurves"]
    floor = n["tttIncubationFloor"]
    if steel:
        if not curves:
            out.append("a steel alloy must have TTT curves")
            curves = []
        for i, point in enumerate(curves):
            if sorted(point) != sorted(TTT_POINT_KEYS):  # goldens store sorted keys: compare as sets
                out.append(f"tttIsothermalCurves[{i}] keys {list(point)!r}")
            elif point["floorHit"] is not (point["tStart_s"] == TTT_FLOOR_S):
                out.append(f"tttIsothermalCurves[{i}]: floorHit {point['floorHit']!r} but tStart_s {point['tStart_s']!r}")
        hits = sum(1 for p in curves if p.get("floorHit") is True)
        expected_floor = {"status": "floor-hit-points-flagged" if hits else "no-floor-hit-points",
                          "floorValue_s": TTT_FLOOR_S, "pointCount": len(curves), "floorHitCount": hits,
                          "note": TTT_FLOOR_NOTE}
    else:
        if curves is not None:
            out.append("a non-steel alloy must have tttIsothermalCurves null")
        expected_floor = {"status": ST_STEEL_ONLY, "floorValue_s": TTT_FLOOR_S, "pointCount": None,
                          "floorHitCount": None, "note": NON_STEEL_NOTE}
    if floor != expected_floor:
        out.append(f"tttIncubationFloor differs from the expected block: {floor!r}")
    # ---- critical temperatures
    flagged = lambda key: key in placeholders  # noqa: E731
    expected_crit = {
        "Ae3_BetaTransus_GammaSolvus_C": registry_values["Ae3_C"],
        "Ae1_C": registry_values["Ae1_C"] if steel else None,
        "Ms_C": None if flagged("Ms_C") else registry_values["Ms_C"],
        "Mf_C": None if flagged("Mf_C") else registry_values["Mf_C"],
        "CriticalCoolingRate_CCR_C_s": registry_values["critical_cooling_rate_C_s"] if steel else None,
        "Ae1_C_status": ST_REGISTRY if steel else ST_STEEL_ONLY,
        "Ms_C_status": ST_PLACEHOLDER if flagged("Ms_C") else ST_REGISTRY,
        "Mf_C_status": ST_PLACEHOLDER if flagged("Mf_C") else ST_REGISTRY,
        "CriticalCoolingRate_CCR_status": ST_REGISTRY if steel else ST_STEEL_ONLY,
    }
    if n["criticalTransformationTemperatures"] != expected_crit:
        out.append(f"criticalTransformationTemperatures differs: {n['criticalTransformationTemperatures']!r}")
    # ---- CCT rows
    rows = n["cctContinuousCoolingMap"]
    if [r["coolingRate_C_s"] for r in rows] != list(CCT_RATES):
        out.append("cctContinuousCoolingMap cooling-rate grid changed")
    for i, row in enumerate(rows):
        tag = f"cctContinuousCoolingMap[{i}]"
        if not steel:
            expected_row = {
                "coolingRate_C_s": row["coolingRate_C_s"], "transformedStartTemp_C": None,
                "transformedStartTime_s": None, "primaryMicrostructure": None,
                "phaseFractions": {"Martensite_pct": None, "Bainite_pct": None, "Pearlite_Ferrite_pct": None,
                                   "RetainedAustenite_pct": None},
                "predictedHardness_HRC": None, "predictedHardness_HV": None,
                "predictedHardness_HV_status": e140.STATUS_UNAVAILABLE_ALLOY_CLASS,
                "transformedStart_status": ST_STEEL_ONLY, "phaseFractions_status": ST_STEEL_ONLY,
                "predictedHardness_HRC_status": ST_STEEL_ONLY, "unavailableReason": STEEL_ONLY_REASON,
            }
            if row != expected_row:
                out.append(f"{tag}: a non-steel row carries steel-template values or a wrong status: {row!r}")
            continue
        hv, hv_status = e140.hrc_to_hv_non_austenitic_steel(row["predictedHardness_HRC"])
        if (row["predictedHardness_HV"], row["predictedHardness_HV_status"]) != (hv, hv_status):
            out.append(f"{tag}: HV/status is not the E140 conversion of the row's HRC")
        if row["transformedStart_status"] == ST_START_NO_ASYMPTOTE:
            ok = (row["transformedStartTemp_C"] is None and row["transformedStartTime_s"] is None
                  and row["primaryMicrostructure"] is None and row["unavailableReason"] == NO_ASYMPTOTE_REASON)
        elif row["transformedStart_status"] == ST_START_ATHERMAL:
            ok = (row["primaryMicrostructure"] == ATHERMAL_LABEL
                  and row["transformedStartTemp_C"] == registry_values["Ms_C"]
                  and isinstance(row["transformedStartTime_s"], float) and row["unavailableReason"] is None)
        else:
            ok = False
        if not ok:
            out.append(f"{tag}: start fields do not match status {row['transformedStart_status']!r}")
        if (row["phaseFractions_status"], row["predictedHardness_HRC_status"]) != (ST_LOOKUP, ST_LOOKUP):
            out.append(f"{tag}: lookup statuses")
    # ---- CALPHAD-vs-kinetics gap
    gap = n["calphadVsKineticsGap"]
    eq, reality = gap["equilibriumPrediction"], gap["kineticRealityAtSelectedCooling"]
    if not steel:
        expected_eq = {"stablePhasesAtRT": None, "martensiteFraction": None, "soluteSupersaturation": None,
                       "status": ST_STEEL_ONLY, "reason": STEEL_ONLY_REASON}
        expected_reality = {"coolingRate_C_s": user_cr, "criticalCoolingRate_C_s": None,
                            "isSuppressedEquilibrium": None, "predictedMartensite_pct": None,
                            "diffusionSuppressionIndex": None, "verdict": None,
                            "status": ST_STEEL_ONLY, "reason": STEEL_ONLY_REASON}
    else:
        ccr = registry_values["critical_cooling_rate_C_s"]
        ms = registry_values["Ms_C"]
        fraction = (max(0.0, 1.0 - math.exp(-0.011 * max(0.0, ms - 25.0))) if user_cr >= ccr * 0.8
                    else (user_cr / ccr) * 0.95)
        fraction = min(0.99, max(0.0, fraction))
        verdict = ("Full Martensitic / Metastable Quench" if user_cr >= ccr else
                   "Mixed Microstructure (Martensite + Bainite)" if user_cr >= ccr * 0.2 else
                   "Diffusional Equilibrium Decomposition")
        expected_eq = dict(GAP_STEEL_EQ, stablePhasesAtRT=D2_PHASES if reg_id == "aisid2" else STEEL_PHASES,
                           status=ST_STATIC_TEXT, reason=GAP_STEEL_EQ_REASON)
        expected_reality = {"coolingRate_C_s": user_cr, "criticalCoolingRate_C_s": ccr,
                            "isSuppressedEquilibrium": user_cr >= 2.0,
                            "predictedMartensite_pct": round(fraction * 100.0, 1),
                            "diffusionSuppressionIndex": round(min(1.0, user_cr / max(1e-2, ccr)), 3),
                            "verdict": verdict, "status": ST_ILLUSTRATIVE, "reason": GAP_STEEL_REALITY_REASON}
    if eq != expected_eq:
        out.append(f"calphadVsKineticsGap.equilibriumPrediction differs: {eq!r}")
    if reality != expected_reality:
        out.append(f"calphadVsKineticsGap.kineticRealityAtSelectedCooling differs: {reality!r}")
    # ---- LSW rows
    q = registry_values["Q_diff_kJ_mol"]
    for i, entry in enumerate(n["lswPrecipitateCoarsening"]):
        tag = f"lswPrecipitateCoarsening[{i}]"
        if sorted(entry) != sorted(["agingTime_h", "meanRadius_nm", "precipitationHardening_MPa",
                                    "strengtheningMechanism", "status"]):
            out.append(f"{tag}: keys {list(entry)!r}")
            continue
        if limit:
            if (entry["meanRadius_nm"], entry["precipitationHardening_MPa"], entry["strengtheningMechanism"],
                    entry["status"]) != (None, None, None, ST_LSW_ABOVE):
                out.append(f"{tag}: aging above the solvus must be unavailable")
            continue
        r = lsw_radius_nm(q, aging_c, entry["agingTime_h"], new_r_gas, corrected=True)
        if entry["meanRadius_nm"] is None or abs(entry["meanRadius_nm"] - r) > 0.005 + 1e-9:
            out.append(f"{tag}.meanRadius_nm {entry['meanRadius_nm']} != SI oracle {r}")
        if (entry["precipitationHardening_MPa"] is None
                or abs(entry["precipitationHardening_MPa"] - lsw_boost_mpa(r)) > 0.05 + 1e-9):
            out.append(f"{tag}.precipitationHardening_MPa mismatch")
        if entry["strengtheningMechanism"] != lsw_regime(r):
            out.append(f"{tag}.strengtheningMechanism mismatch")
        if entry["status"] != ST_LSW_ILLUSTRATIVE:
            out.append(f"{tag}.status {entry['status']!r}")
    return out
