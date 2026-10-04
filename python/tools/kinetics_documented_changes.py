"""
Documented value changes of kinetics_ttt_cct_solver against the d33b6f5 / 7f3f803 base goldens.

Used by capture_phase6a_golden.documented_change_violation (via
phase6a_t2b_golden_cases.EXPECTED_DOCUMENTED_VALUE_CHANGES) and by test_phase6a_t2b_migration.

Two levels of checking:

* row_violation: each drift row of a documented pattern must be of an allowed kind and must be exactly the value
  the re-blessed document holds at that key (a removed row: the key is absent / the curve list is null). The LSW
  rows additionally check the OLD value against the old formula (unit error, 1e-3 floor, legacy R).
* document_violations: the WHOLE re-blessed document is compared with an independent expectation: every status,
  text and availability field exactly; for a steel inside the Li (1998) model range every TTT point, critical
  temperature, CCT start and the critical cooling rate against tools/kinetics_li_oracle.py (scipy quad / brentq,
  separate code from the solver) within the display rounding; LSW rows against an independent SI formula.

Changes (base golden -> now):

1. Lane kin-li: the steel template (unsourced nose temperatures, Avrami constants, 1 ms floor, CCT phase
   fractions/HRC looked up by cooling-rate band) is replaced by the Li et al. (1998) model: TTT C-curves for
   ferrite/pearlite/bainite from composition and ASTM grain size, CCT starts by the additivity rule, Grange
   Ae3/Ae1, Li Bs, Kung-Rayment Ms, model critical cooling rate. Phase fractions and HRC are null (not computed).
   Reported only for a steel inside the composition range stated by M. Li (1996 thesis p. 86); a steel outside
   it (AISI D2) and every non-steel alloy are unavailable with an explicit status and reason.
2. fx-kinetics (kept): non-steel alloys unavailable ("kinetics model is steel-only"); registry placeholders
   (alloy_registry.KINETICS_PLACEHOLDERS) null in alloyMetadata; non-steel alloyMetadata Ae1/critical cooling
   rate null.
3. fx-kinetics (kept): LSW K used the mole fraction where mol/m^3 is needed (K too small by 1/Vm = 9.1e4) and had
   a 1e-3 nm^3/h floor; null at or above the registry Ae3 (steels: Ae1).
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

PYTHON_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent
for _p in (PYTHON_DIR, TOOLS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import alloy_registry  # noqa: E402 (python/ module)
import hardness_conversion_e140 as e140  # noqa: E402 (python/ module)
import input_validation  # noqa: E402 (python/ module)
import physical_constants  # noqa: E402 (python/ module)
import kinetics_li_oracle as oracle  # noqa: E402 (tools/ module)

STEEL_ONLY_REASON = "kinetics model is steel-only"
ST_STEEL_ONLY = "unavailable-kinetics-model-steel-only"
ST_OUTSIDE = "unavailable-composition-outside-li-model-range"
ST_PLACEHOLDER = "unavailable-registry-placeholder"
ST_REGISTRY = "registry-screening-value"
ST_START_LI = "li1998-additivity-first-diffusional-start"
ST_START_ATHERMAL = "athermal-martensite-no-diffusional-start-above-ms"
ST_NOT_AUSTENITIC = "unavailable-austenitizing-at-or-below-ae3"
ST_FRACTIONS = "unavailable-fractions-not-computed"
ST_HV_NO_HRC = "unavailable-no-predicted-hrc"
ST_STATIC_TEXT = "static-text-not-a-calphad-calculation"
ST_LI = "li1998-additivity-screening"
ST_GRANGE = "computed-grange-1961-screening"
ST_BS = "computed-li-1998-screening"
ST_MS = "computed-andrews-kung-rayment-1982-screening"
ST_MF = "unavailable-not-modelled"
ST_TTT_NO_FLOOR = "no-floor-li-1998-law"
ST_LSW_ILLUSTRATIVE = "generic-constants-illustrative"
ST_LSW_ABOVE = "unavailable-aging-temperature-at-or-above-solvus"
LEGACY_R_GAS = 8.314  # the d33b6f5 / 7f3f803 base goldens were captured with this R
CCT_RATES = (0.05, 0.2, 1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 500.0, 2000.0)
ATHERMAL_LABEL = "Martensite (Athermal)"
MODEL_VERSION = "li1998-additivity-v1"
ENGINE = "MetalliX-Python-Li1998-Additivity-Kinetics-v4.0"
TTT_POINT_KEYS = ["temperature_C", "phase", "tStart_s", "t50_s", "tFinish_s", "avramiExponent_n",
                  "drivingForce_DeltaT_C", "floorHit"]
KM_ALPHA = 0.011

# Independent copies of the solver texts (a typo or a rewording in the solver must be seen here).
SCOPE = "low-alloy steels inside the composition range stated for the Li (1998) model"
SOURCE_LABEL = (
    "Li, Niebuhr, Meekisho & Atteridge, Metall. Mater. Trans. B 29 (1998) 661-672: equations as printed in "
    "M. Li, PhD thesis, Oregon Graduate Institute (1996), Eqs. 3.67 and 3.70-3.77, and in Collins et al., "
    "Metals 13 (2023) 1168, Eqs. 1-14; Ae3/Ae1: Grange (1961) as printed in Collins et al. Eqs. 8 and 11; "
    "Ms: Andrews linear equation modified by Kung & Rayment (1982), Li (1996) Eq. 3.77; CCT: additivity rule "
    "(Scheil 1935)."
)
VALIDITY_SOURCE = (
    "M. Li (1996) thesis p. 86: the author 'has not thoroughly tested the application range' and believes the "
    "model valid 'at least within the same range of Creusot-Loire model': 0.1<C<0.5, Si<1.0, Mn<2, Ni<4, Cr<3, "
    "Mo<1, V<0.2, Cu<0.5, Mo+Ni+Cr+Mo<5 (as printed), 0.01<Al<0.05 (wt%)."
)
NON_STEEL_NOTE = (
    "The Li (1998) TTT/CCT model covers low-alloy steels only; no sourced transformation-kinetics model of this "
    "alloy class is implemented, so no TTT/CCT curves, start temperatures, phase fractions or hardness are reported."
)
OUTSIDE_NOTE = (
    "The composition is outside the range stated for the Li (1998) model (M. Li 1996 thesis p. 86), so no TTT/CCT "
    "curves, start temperatures, phase fractions or hardness are reported."
)
LI_NOTE = (
    "Li et al. (1998) isothermal start/finish law with Grange Ae3/Ae1, Li Bs and Kung-Rayment Ms; CCT starts from "
    "the additivity rule applied to each phase's 1 % start curve independently (no phase interaction, no carbon "
    "partitioning). Unvalidated screening model: phase fractions and hardness are not computed."
)
FRACTIONS_REASON = (
    "phase fractions and hardness are not computed: the Li (1998) model needs the equilibrium ferrite and pearlite "
    "amounts from a thermodynamic Fe-C-M model that is not implemented"
)
TTT_NO_FLOOR_NOTE = (
    "The Li (1998) start-time law diverges at its start temperature (Ae3, Ae1, Bs); no time floor is applied. "
    "Points with a start time of 1e6 s or more are not listed."
)
TTT_UNAVAILABLE_NOTE = "No TTT points: the kinetics model is unavailable for this alloy."
LSW_NOTE = (
    "K_LSW uses generic gamma, equilibrium concentration, molar volume and D0 shared by every alloy (only the "
    "activation energy is per alloy; one molar volume serves both the matrix concentration and the "
    "precipitate); the strengthening column is an unsourced screening curve."
)
STEEL_PHASES = "Ferrite + Cementite / Equilibrium intermetallics"
GAP_STEEL_EQ = {"stablePhasesAtRT": STEEL_PHASES,
                "martensiteFraction": "0.0% (Thermodynamically Forbidden in Equilibrium)",
                "soluteSupersaturation": "Near Zero (<0.01 wt% C in ferrite)",
                "status": ST_STATIC_TEXT,
                "reason": "fixed steel text; no equilibrium (CALPHAD) calculation is performed here"}
GAP_LI_REASON = (
    "Li (1998) start-time model with the additivity rule; phase fractions are not computed. The martensite "
    "% is given only when no diffusional start is reached above Ms (Koistinen-Marburger, alpha = 0.011/K "
    "as in Li 1996 Eq. 3.76, at 25 C)")
GRAIN_DEFINITION = ("priorGrainSize_um is taken as the mean planar grain diameter d; "
                    "G = -3.2877 - 6.6439 log10(sqrt(pi/4) d / mm) (ASTM E112, Collins et al. Eqs. 3-4)")
START_CRITERION = ("1 % reaction (X = 0.01) per phase; each phase's start curve is integrated "
                   "independently from the austenitizing temperature (no phase interaction)")
CCR_DEFINITION = ("slowest linear cooling rate from the austenitizing temperature at which "
                  "no ferrite, pearlite or bainite 1 % start is reached above Ms")
SUPPRESSED_VERDICT = "No diffusional start above Ms (Li 1998 additivity): martensite from Ms"
_VERDICT_RE = re.compile(r"(Ferrite|Pearlite|Bainite) start at (-?\d+\.\d) C \(Li 1998 additivity\); "
                         r"phase fractions not computed")
# Tolerances: display rounding of the solver plus its 0.05 K midpoint integration (oracle: adaptive quad).
TOL_TEMP_C = 0.1          # temperatures rounded to 0.1 C (0.05) + integration
TOL_REL_TIME = 2e-5       # 6 significant digits (5e-6) + quadrature
TOL_REL_CCT_TIME = 1e-3   # 4 significant digits (5e-4) + start-temperature error / rate
TOL_REL_CCR = 1e-3        # 4 significant digits (5e-4) + midpoint rule
OLD_KINETICS_HRC_BANDS = (18.0, 28.0, 42.0, 54.0, 58.0, 64.0)

# ----------------------------------------------------------------------------------------------
# LSW oracle: r^3 - r0^3 = K t, K = 8 gamma D C_e Vm^2 / (9 R T) with C_e in mol/m^3.
# Lifshitz & Slyozov, J. Phys. Chem. Solids 19 (1961) 35; Wagner, Z. Elektrochem. 65 (1961) 581.
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
_PATH_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _leaf(doc: Any, key: str) -> Tuple[bool, Any]:
    """(present, value) at a drift-report key such as 'a.b[3].c'."""
    cur = doc
    for name, index in _PATH_RE.findall(key):
        if name:
            if not isinstance(cur, dict) or name not in cur:
                return False, None
            cur = cur[name]
        else:
            i = int(index)
            if not isinstance(cur, list) or i >= len(cur):
                return False, None
            cur = cur[i]
    return True, cur


def _same(a: Any, b: Any) -> bool:
    return a == b and type(a) is type(b)


def _record(doc: Dict[str, Any]):
    return input_validation.require_known_alloy(doc["alloy"], alloy_registry.DOMAIN_KINETICS, field="alloy")


def _alloy_is_steel(reg_id: str) -> bool:
    """Steel class from the registry descriptor type (alloy_data_kinetics_uq_fatigue), not from the solver output."""
    import alloy_data_kinetics_uq_fatigue as kinetics_data  # noqa: E402 (python/ module)
    return "Steel" in kinetics_data.KINETICS_DESCRIPTORS[reg_id]["type"]


def classify(doc: Dict[str, Any]) -> Tuple[str, bool, bool]:
    """(registry id, steel, inside the Li range), independent of the solver's own flags."""
    record = _record(doc)
    steel = _alloy_is_steel(record.id)
    comp = dict(record.value("composition_wt", alloy_registry.DOMAIN_KINETICS))
    bad, _unchecked = oracle.range_violations(comp)
    return record.id, steel, steel and not bad


def _is_null_change(row) -> Optional[str]:
    if row["kind"] != "changed" or row["new"] is not None or row["old"] is None:
        return f"{row['key']}: expected a value changed to null, got {row['kind']} {row['old']!r} -> {row['new']!r}"
    return None


def _h_doc_leaf(row, doc, r_gas):
    """The row's new value is the document's value at that key (whole-document checks verify the value)."""
    present, value = _leaf(doc, row["key"])
    if row["kind"] == "removed":
        if present:
            return f"{row['key']}: removed row but the key is present in the re-blessed document"
        return None
    if not present:
        return f"{row['key']}: key absent from the re-blessed document"
    if not _same(value, row["new"]):
        return f"{row['key']}: row new {row['new']!r} != document {value!r}"
    return None


def _h_alloy_meta_nonsteel(row, doc, r_gas):
    _rid, steel, _inside = classify(doc)
    if steel:
        return f"{row['key']}: a steel keeps its registry echo"
    return _is_null_change(row)


def _h_placeholder_null(row, doc, r_gas):
    reg_id = _record(doc).id
    key = row["key"].rsplit(".", 1)[-1]
    if (reg_id, key) not in alloy_registry.KINETICS_PLACEHOLDERS:
        return f"{row['key']}: ({reg_id}, {key}) is not flagged in alloy_registry.KINETICS_PLACEHOLDERS"
    return _is_null_change(row)


def _h_lsw(row, doc, r_gas):
    i = int(re.search(r"\[(\d+)\]", row["key"]).group(1))
    leaf = row["key"].rsplit(".", 1)[-1]
    q = doc["alloyMetadata"]["Q_diff_kJ_mol"]
    aging_c = doc["inputParameters"]["agingTemp_C"]
    t_h = doc["lswPrecipitateCoarsening"][i]["agingTime_h"]
    _rid, steel, _inside = classify(doc)
    meta = {"Ae3_C": _record(doc).value("Ae3_C", alloy_registry.DOMAIN_KINETICS),
            "Ae1_C": _record(doc).value("Ae1_C", alloy_registry.DOMAIN_KINETICS)}
    unavailable = lsw_limit(meta, aging_c, steel) is not None
    r_new = lsw_radius_nm(q, aging_c, t_h, r_gas, corrected=True)
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


def hv_violation(row, doc) -> Optional[str]:
    """predictedHardness_HV / _status rows of a row whose HRC is null (Li model: not computed; non-steel).

    The old HV must be round(10.5 * HRC + 40) of one of the old lookup-band HRC values; the new HV null, the
    status the one that belongs to the alloy class (steel: unavailable-no-predicted-hrc; other: no verified table).
    """
    match = re.fullmatch(r"cctContinuousCoolingMap\[(\d+)\]\.predictedHardness_HV(_status)?", row["key"])
    if not match:
        return f"{row['key']}: not an HV row"
    entry = doc["cctContinuousCoolingMap"][int(match.group(1))]
    if entry.get("predictedHardness_HRC") is not None:
        return f"{row['key']}: HRC is not null"
    reg_id = _record(doc).id
    expected_status = ST_HV_NO_HRC if reg_id in {"aisi4140", "aisi4340", "aisid2"} else \
        e140.STATUS_UNAVAILABLE_ALLOY_CLASS
    if entry.get("predictedHardness_HV_status") != expected_status or entry.get("predictedHardness_HV") is not None:
        return f"{row['key']}: HV/status {entry.get('predictedHardness_HV')!r}/{entry.get('predictedHardness_HV_status')!r}"
    if match.group(2):
        if row["kind"] != "added" or row["new"] != expected_status:
            return f"{row['key']}: expected an added status {expected_status!r}"
        return None
    allowed = {round(h * 10.5 + 40.0, 0) for h in OLD_KINETICS_HRC_BANDS}
    if row["kind"] != "changed" or row["new"] is not None or type(row["old"]) is not float or row["old"] not in allowed:
        return f"{row['key']}: expected old round(10.5 * HRC + 40) of an old HRC band -> null, got {row!r}"
    return None


_ANY = {"added", "changed", "numeric", "removed"}
_A, _C = {"added"}, {"changed"}
_LSW = r"lswPrecipitateCoarsening\[\d+\]"
_RULES: List[Tuple[str, set, Callable, str]] = [
    (r"engine", _C, _h_doc_leaf, "engine name: Li (1998) additivity kinetics v4.0"),
    (r"tttIsothermalCurves", _A, _h_doc_leaf, "TTT curves null when the model is unavailable"),
    (r"tttIsothermalCurves\[\d+\](\..+)?", _ANY, _h_doc_leaf,
     "TTT curves: Li (1998) C-curves of a steel inside the model range (verified against the independent oracle); "
     "removed when the model is unavailable"),
    (r"cctContinuousCoolingMap\[\d+\]\.(?!predictedHardness_HV(_status)?$).+", _ANY, _h_doc_leaf,
     "CCT rows: additivity-rule starts of the Li model (oracle-verified), fractions/HRC null (not computed), statuses; "
     "all null with the reason when the model is unavailable"),
    (r"criticalTransformationTemperatures\..+", _ANY, _h_doc_leaf,
     "critical temperatures: Grange Ae3/Ae1, Li Bs, Kung-Rayment Ms, model critical cooling rate (oracle-verified); "
     "registry echoes with statuses when the model is unavailable"),
    (r"calphadVsKineticsGap\..+", _ANY, _h_doc_leaf,
     "kinetic reality at the selected rate from the Li model; null with the reason when unavailable"),
    (r"kineticsModel(\..+)?", _ANY, _h_doc_leaf, "kineticsModel block (verified exactly as a whole)"),
    (r"tttIncubationFloor\..+", _ANY, _h_doc_leaf, "tttIncubationFloor block (no floor in the Li law)"),
    (r"provenance\.kineticsModelVersion", _A, _h_doc_leaf, "provenance names the kinetics model version"),
    (r"alloyMetadata\.(Ae1_C|critical_cooling_rate_C_s)", _C, _h_alloy_meta_nonsteel,
     "non-steel alloys: the steel registry echoes Ae1 and critical cooling rate are null"),
    (r"alloyMetadata\.(Ms_C|Mf_C)", _C, _h_placeholder_null,
     "registry placeholders (alloy_registry.KINETICS_PLACEHOLDERS) are null"),
    (_LSW + r"\.(meanRadius_nm|precipitationHardening_MPa|strengtheningMechanism)", {"numeric", "changed"}, _h_lsw,
     "LSW unit fix: C_e in mol/m^3 (x_e/Vm), no 1e-3 nm^3/h floor; null at or above the registry solvus "
     "(steels: Ae1); checked against an independent SI formula"),
    (_LSW + r"\.status", _A, _h_doc_leaf, "new LSW row status"),
]
HANDLERS: Dict[str, Callable] = {p: h for p, _k, h, _d in _RULES}
HANDLER_KINDS: Dict[str, set] = {p: k for p, k, _h, _d in _RULES}
DESCRIPTIONS: Dict[str, str] = {p: d for p, _k, _h, d in _RULES}
assert len(HANDLERS) == len(_RULES)


def row_violation(row: Dict[str, Any], new_stdout: Dict[str, Any],
                  new_r_gas: Optional[float] = None) -> Optional[str]:
    """None when ``row`` is one of the documented changes above (value equal to the document), else the problem."""
    if new_r_gas is None:
        new_r_gas = physical_constants.GAS_CONSTANT_R.value
    if not isinstance(new_stdout, dict):
        return f"{row['key']}: no re-blessed document"
    for pattern, handler in HANDLERS.items():
        if re.fullmatch(pattern, row["key"]) and row["kind"] in HANDLER_KINDS[pattern]:
            try:
                return handler(row, new_stdout, new_r_gas)
            except (KeyError, IndexError, TypeError, ValueError, AttributeError,
                    input_validation.ValidationError) as exc:
                return f"{row['key']}: cannot verify against the re-blessed document ({exc!r})"
    return f"{row['key']}: no documented-change handler"


def is_documented_row(key: str, kind: Optional[str]) -> bool:
    """Whether a drift row of this key and kind belongs to a documented change above."""
    return any(re.fullmatch(p, key) and (kind is None or kind in HANDLER_KINDS[p]) for p in HANDLERS)


# ----------------------------------------------------------------------------------------------
def document_violations(new_stdout: Dict[str, Any], new_r_gas: Optional[float] = None) -> List[str]:
    """Whole-document checks of a kinetics result, also for fields that did not drift."""
    if new_r_gas is None:
        new_r_gas = physical_constants.GAS_CONSTANT_R.value
    out: List[str] = []
    try:
        return _document_violations(new_stdout, new_r_gas, out)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        return out + [f"document is malformed ({exc!r})"]


def _close(a: Any, b: float, tol: float) -> bool:
    return isinstance(a, float) and abs(a - b) <= tol + 1e-12


def _rel_close(a: Any, b: float, rel: float) -> bool:
    return isinstance(a, float) and abs(a - b) <= rel * abs(b) + 1e-12


def _document_violations(n: Dict[str, Any], r_gas: float, out: List[str]) -> List[str]:
    record = _record(n)
    reg_id = record.id
    meta = n["alloyMetadata"]
    steel = _alloy_is_steel(reg_id)
    if steel != ("Steel" in meta["type"]):
        out.append(f"alloyMetadata.type {meta['type']!r} disagrees with the registry descriptor")
    comp = dict(record.value("composition_wt", alloy_registry.DOMAIN_KINETICS))
    violations, unchecked = oracle.range_violations(comp)
    modelled = steel and not violations
    placeholders = sorted(k for a, k in alloy_registry.KINETICS_PLACEHOLDERS if a == reg_id)
    params = n["inputParameters"]
    aging_c = params["agingTemp_C"]
    registry = {key: record.value(key, alloy_registry.DOMAIN_KINETICS)
                for key in ("Ae3_C", "Ae1_C", "Ms_C", "Mf_C", "Q_diff_kJ_mol", "critical_cooling_rate_C_s")}
    if n.get("engine") != ENGINE:
        out.append(f"engine {n.get('engine')!r}")
    # ---- alloyMetadata echoes
    for key, value in registry.items():
        expected = None if (key in placeholders or (not steel and key in ("Ae1_C", "critical_cooling_rate_C_s"))) \
            else value
        if meta[key] != expected:
            out.append(f"alloyMetadata.{key} is {meta[key]!r}, expected {expected!r}")
    if meta["composition_wt"] != comp:
        out.append("alloyMetadata.composition_wt is not the registry composition")
    # ---- availability
    if not steel:
        st, reason, note = ST_STEEL_ONLY, STEEL_ONLY_REASON, NON_STEEL_NOTE
    elif violations:
        st, reason, note = ST_OUTSIDE, "composition outside the Li (1998) model range: " + "; ".join(violations), \
            OUTSIDE_NOTE
    else:
        st, reason, note = None, None, LI_NOTE
    orc = None
    aust = params["austSolutionTemp_C"]
    user_cr = params["selectedCoolingRate_C_s"]
    if modelled:
        orc = oracle.Oracle(comp, float(params["priorGrainSize_um"]), r_gas)
    # ---- kineticsModel
    limit = lsw_limit({"Ae3_C": registry["Ae3_C"], "Ae1_C": registry["Ae1_C"]}, aging_c, steel)
    model = n["kineticsModel"]
    expected_model = {
        "status": "available" if modelled else "unavailable",
        "reason": reason,
        "scope": SCOPE,
        "registryAlloyId": reg_id,
        "illustrativeOnly": True,
        "note": note,
        "placeholderParameters": placeholders,
        "lswPrecipitateCoarsening": {"status": ST_LSW_ABOVE if limit else ST_LSW_ILLUSTRATIVE, "note": LSW_NOTE,
                                     "reason": lsw_reason(aging_c, limit) if limit else None},
        "modelVersion": MODEL_VERSION,
        "sourceLabel": SOURCE_LABEL,
        "validationStatus": "unvalidated",
        "evidenceLevel": "screening",
        "validityDomain": {"status": "not-applicable-alloy-class" if not steel else
                           ("outside" if violations else "inside"),
                           "source": VALIDITY_SOURCE,
                           "violations": violations if steel else [],
                           "unchecked": unchecked if steel else []},
    }
    li_block = model.get("li1998")
    if {k: v for k, v in model.items() if k != "li1998"} != expected_model:
        out.append(f"kineticsModel differs from the expected block: {model!r}")
    if not modelled:
        if li_block is not None:
            out.append("kineticsModel.li1998 must be null when the model is unavailable")
    else:
        exp_texts = {"grainSizeDefinition": GRAIN_DEFINITION, "activationEnergy_J_mol": 115060.0,
                     "startCriterion": START_CRITERION, "criticalCoolingRateDefinition": CCR_DEFINITION,
                     "fractionsComputed": False, "fractionsReason": FRACTIONS_REASON}
        for key, value in exp_texts.items():
            if not _same(li_block.get(key), value):
                out.append(f"kineticsModel.li1998.{key} is {li_block.get(key)!r}")
        if not _close(li_block.get("astmGrainSize_G"), orc.g, 0.0005):
            out.append(f"kineticsModel.li1998.astmGrainSize_G {li_block.get('astmGrainSize_G')!r} != {orc.g!r}")
        for ph in oracle.PHASES:
            if not _rel_close(li_block["compositionFactors"].get(ph), orc.F[ph], 1e-5):
                out.append(f"kineticsModel.li1998.compositionFactors.{ph}")
        for name, x in (("X_0p01", 0.01), ("X_0p5", 0.5), ("X_0p99", 0.99)):
            if not _rel_close(li_block["reactionIntegral_S"].get(name), oracle.s_integral(x), 1e-5):
                out.append(f"kineticsModel.li1998.reactionIntegral_S.{name}")
        if sorted(li_block["reactionIntegral_S"]) != ["X_0p01", "X_0p5", "X_0p99"]:
            out.append("kineticsModel.li1998.reactionIntegral_S keys")
        if sorted(li_block) != sorted(list(exp_texts) + ["astmGrainSize_G", "compositionFactors", "reactionIntegral_S"]):
            out.append(f"kineticsModel.li1998 keys {sorted(li_block)!r}")
    # ---- TTT curves and the floor block
    curves = n["tttIsothermalCurves"]
    floor = n["tttIncubationFloor"]
    if modelled:
        exp_points = orc.ttt()
        if not isinstance(curves, list) or len(curves) != len(exp_points):
            out.append(f"tttIsothermalCurves: {None if curves is None else len(curves)} points, oracle {len(exp_points)}")
        else:
            for i, (p, e) in enumerate(zip(curves, exp_points)):
                tag = f"tttIsothermalCurves[{i}]"
                if sorted(p) != sorted(TTT_POINT_KEYS):
                    out.append(f"{tag} keys {list(p)!r}")
                    continue
                if p["phase"] != e["phase"] or p["avramiExponent_n"] is not None or p["floorHit"] is not False:
                    out.append(f"{tag}: phase/avrami/floorHit {p['phase']!r} {p['avramiExponent_n']!r} {p['floorHit']!r}")
                if not _close(p["temperature_C"], e["temperature_C"], 0.005) or \
                        not _close(p["drivingForce_DeltaT_C"], e["drivingForce_DeltaT_C"], 0.005):
                    out.append(f"{tag}: temperature {p['temperature_C']!r} vs oracle {e['temperature_C']!r}")
                for key in ("tStart_s", "t50_s", "tFinish_s"):
                    if not _rel_close(p[key], e[key], TOL_REL_TIME):
                        out.append(f"{tag}.{key} {p[key]!r} vs oracle {e[key]!r}")
        expected_floor = {"status": ST_TTT_NO_FLOOR, "floorValue_s": None,
                          "pointCount": len(curves) if isinstance(curves, list) else None,
                          "floorHitCount": 0, "note": TTT_NO_FLOOR_NOTE}
    else:
        if curves is not None:
            out.append("tttIsothermalCurves must be null when the model is unavailable")
        expected_floor = {"status": st, "floorValue_s": None, "pointCount": None, "floorHitCount": None,
                          "note": TTT_UNAVAILABLE_NOTE}
    if floor != expected_floor:
        out.append(f"tttIncubationFloor differs from the expected block: {floor!r}")
    # ---- critical temperatures, CCT rows, gap
    crit = n["criticalTransformationTemperatures"]
    rows = n["cctContinuousCoolingMap"]
    gap = n["calphadVsKineticsGap"]
    if [r["coolingRate_C_s"] for r in rows] != list(CCT_RATES):
        out.append("cctContinuousCoolingMap cooling-rate grid changed")
    hv_status = ST_HV_NO_HRC if reg_id in {"aisi4140", "aisi4340", "aisid2"} else e140.STATUS_UNAVAILABLE_ALLOY_CLASS
    null_fractions = {"Martensite_pct": None, "Bainite_pct": None, "Pearlite_Ferrite_pct": None,
                      "RetainedAustenite_pct": None}
    if not modelled:
        expected_crit = {
            "Ae3_BetaTransus_GammaSolvus_C": registry["Ae3_C"],
            "Ae1_C": registry["Ae1_C"] if steel else None,
            "Ms_C": None if "Ms_C" in placeholders else registry["Ms_C"],
            "Mf_C": None if "Mf_C" in placeholders else registry["Mf_C"],
            "CriticalCoolingRate_CCR_C_s": None,
            "Ae1_C_status": ST_REGISTRY if steel else ST_STEEL_ONLY,
            "Ms_C_status": ST_PLACEHOLDER if "Ms_C" in placeholders else ST_REGISTRY,
            "Mf_C_status": ST_PLACEHOLDER if "Mf_C" in placeholders else ST_REGISTRY,
            "CriticalCoolingRate_CCR_status": st,
            "Ae3_C_status": ST_REGISTRY,
            "Bs_C": None,
            "Bs_C_status": st,
        }
        if crit != expected_crit:
            out.append(f"criticalTransformationTemperatures differs: {crit!r}")
        for i, row in enumerate(rows):
            expected_row = {
                "coolingRate_C_s": row["coolingRate_C_s"], "transformedStartTemp_C": None,
                "transformedStartTime_s": None, "primaryMicrostructure": None, "phaseFractions": null_fractions,
                "predictedHardness_HRC": None, "predictedHardness_HV": None, "predictedHardness_HV_status": hv_status,
                "transformedStart_status": st, "phaseFractions_status": st, "predictedHardness_HRC_status": st,
                "unavailableReason": reason, "phaseStartTemps_C": None,
            }
            if row != expected_row:
                out.append(f"cctContinuousCoolingMap[{i}]: unavailable row differs: {row!r}")
        expected_eq = {"stablePhasesAtRT": None, "martensiteFraction": None, "soluteSupersaturation": None,
                       "status": st, "reason": reason}
        expected_reality = {"coolingRate_C_s": user_cr, "criticalCoolingRate_C_s": None,
                            "isSuppressedEquilibrium": None, "predictedMartensite_pct": None,
                            "diffusionSuppressionIndex": None, "verdict": None, "status": st, "reason": reason}
        if gap["equilibriumPrediction"] != expected_eq:
            out.append(f"calphadVsKineticsGap.equilibriumPrediction differs: {gap['equilibriumPrediction']!r}")
        if gap["kineticRealityAtSelectedCooling"] != expected_reality:
            out.append(f"calphadVsKineticsGap.kineticRealityAtSelectedCooling differs: "
                       f"{gap['kineticRealityAtSelectedCooling']!r}")
    else:
        _check_modelled(n, orc, crit, rows, gap, aust, user_cr, hv_status, null_fractions, out)
    # ---- LSW rows
    q = registry["Q_diff_kJ_mol"]
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
        r = lsw_radius_nm(q, aging_c, entry["agingTime_h"], r_gas, corrected=True)
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


def _check_modelled(n, orc, crit, rows, gap, aust, user_cr, hv_status, null_fractions, out):
    fully_austenitic = aust > orc.ae3
    exp_temps = {"Ae3_BetaTransus_GammaSolvus_C": orc.ae3, "Ae1_C": orc.ae1, "Ms_C": orc.ms, "Bs_C": orc.bs}
    for key, value in exp_temps.items():
        if not _close(crit.get(key), value, 0.05):
            out.append(f"criticalTransformationTemperatures.{key} {crit.get(key)!r} vs oracle {value!r}")
    exp_status = {"Mf_C": None, "Ae1_C_status": ST_GRANGE, "Ms_C_status": ST_MS, "Mf_C_status": ST_MF,
                  "Ae3_C_status": ST_GRANGE, "Bs_C_status": ST_BS,
                  "CriticalCoolingRate_CCR_status": ST_LI if fully_austenitic else ST_NOT_AUSTENITIC}
    for key, value in exp_status.items():
        if crit.get(key) != value:
            out.append(f"criticalTransformationTemperatures.{key} is {crit.get(key)!r}, expected {value!r}")
    if sorted(crit) != sorted(list(exp_temps) + list(exp_status) + ["CriticalCoolingRate_CCR_C_s"]):
        out.append(f"criticalTransformationTemperatures keys {sorted(crit)!r}")
    ccr = orc.critical_rate(aust) if fully_austenitic else None
    if ccr is None:
        if crit.get("CriticalCoolingRate_CCR_C_s") is not None:
            out.append("CriticalCoolingRate_CCR_C_s must be null below Ae3")
    elif not _rel_close(crit.get("CriticalCoolingRate_CCR_C_s"), ccr, TOL_REL_CCR):
        out.append(f"CriticalCoolingRate_CCR_C_s {crit.get('CriticalCoolingRate_CCR_C_s')!r} vs oracle {ccr!r}")
    not_aust_reason = (f"austenitizing temperature {aust:g} C is at or below the Grange Ae3 of {orc.ae3:.1f} C: "
                       "the Li model assumes a fully austenitic start")
    for i, row in enumerate(rows):
        tag = f"cctContinuousCoolingMap[{i}]"
        cr = row["coolingRate_C_s"]
        if not fully_austenitic:
            expected_row = {
                "coolingRate_C_s": cr, "transformedStartTemp_C": None, "transformedStartTime_s": None,
                "primaryMicrostructure": None, "phaseFractions": null_fractions, "predictedHardness_HRC": None,
                "predictedHardness_HV": None, "predictedHardness_HV_status": hv_status,
                "transformedStart_status": ST_NOT_AUSTENITIC, "phaseFractions_status": ST_NOT_AUSTENITIC,
                "predictedHardness_HRC_status": ST_NOT_AUSTENITIC, "unavailableReason": not_aust_reason,
                "phaseStartTemps_C": None}
            if row != expected_row:
                out.append(f"{tag}: not-austenitic row differs: {row!r}")
            continue
        starts = {ph: orc.phase_start(ph, aust, cr) for ph in oracle.PHASES}
        got = row.get("phaseStartTemps_C") or {}
        if sorted(got) != sorted(oracle.PHASES):
            out.append(f"{tag}.phaseStartTemps_C keys {sorted(got)!r}")
            continue
        for ph, value in starts.items():
            if (value is None) != (got[ph] is None) or (value is not None and not _close(got[ph], value, TOL_TEMP_C)):
                out.append(f"{tag}.phaseStartTemps_C.{ph} {got[ph]!r} vs oracle {value!r}")
        found = {ph: t for ph, t in starts.items() if t is not None}
        if not found:
            ok = (row["primaryMicrostructure"] == ATHERMAL_LABEL and _close(row["transformedStartTemp_C"], orc.ms, 0.05)
                  and row["transformedStart_status"] == ST_START_ATHERMAL)
            first_t = orc.ms
        else:
            first_t = max(found.values())
            near = {ph for ph, t in found.items() if first_t - t <= 2 * TOL_TEMP_C}  # tie within the rounding
            ok = (row["primaryMicrostructure"] in near and _close(row["transformedStartTemp_C"], first_t, TOL_TEMP_C)
                  and row["transformedStart_status"] == ST_START_LI)
        if not ok:
            out.append(f"{tag}: first start {row['primaryMicrostructure']!r} {row['transformedStartTemp_C']!r} "
                       f"{row['transformedStart_status']!r} vs oracle {first_t!r} {sorted(found)!r}")
        if not _rel_close(row["transformedStartTime_s"], (aust - first_t) / cr, TOL_REL_CCT_TIME):
            out.append(f"{tag}.transformedStartTime_s {row['transformedStartTime_s']!r}")
        fixed = {"phaseFractions": null_fractions, "predictedHardness_HRC": None, "predictedHardness_HV": None,
                 "predictedHardness_HV_status": hv_status, "phaseFractions_status": ST_FRACTIONS,
                 "predictedHardness_HRC_status": ST_FRACTIONS, "unavailableReason": None}
        for key, value in fixed.items():
            if row.get(key) != value:
                out.append(f"{tag}.{key} is {row.get(key)!r}, expected {value!r}")
        if len(row) != 13:
            out.append(f"{tag}: keys {sorted(row)!r}")
    if gap["equilibriumPrediction"] != GAP_STEEL_EQ:
        out.append(f"calphadVsKineticsGap.equilibriumPrediction differs: {gap['equilibriumPrediction']!r}")
    reality = gap["kineticRealityAtSelectedCooling"]
    if not fully_austenitic:
        expected = {"coolingRate_C_s": user_cr, "criticalCoolingRate_C_s": None, "isSuppressedEquilibrium": None,
                    "predictedMartensite_pct": None, "diffusionSuppressionIndex": None, "verdict": None,
                    "status": ST_NOT_AUSTENITIC, "reason": not_aust_reason}
        if reality != expected:
            out.append(f"calphadVsKineticsGap.kineticRealityAtSelectedCooling differs: {reality!r}")
        return
    user_starts = {ph: orc.phase_start(ph, aust, user_cr) for ph in oracle.PHASES}
    found = {ph: t for ph, t in user_starts.items() if t is not None}
    suppressed = not found
    km = round((1.0 - math.exp(-KM_ALPHA * max(0.0, orc.ms - 25.0))) * 100.0, 1)
    fixed = {"coolingRate_C_s": user_cr, "isSuppressedEquilibrium": suppressed,
             "predictedMartensite_pct": km if suppressed else None, "diffusionSuppressionIndex": None,
             "status": ST_LI, "reason": GAP_LI_REASON}
    for key, value in fixed.items():
        if not (reality.get(key) == value or (isinstance(value, float) and _close(reality.get(key), value, 0.1))):
            out.append(f"calphadVsKineticsGap.kineticRealityAtSelectedCooling.{key} is {reality.get(key)!r}, "
                       f"expected {value!r}")
    if not _rel_close(reality.get("criticalCoolingRate_C_s"), ccr, TOL_REL_CCR):
        out.append("calphadVsKineticsGap.kineticRealityAtSelectedCooling.criticalCoolingRate_C_s")
    verdict = reality.get("verdict")
    if suppressed:
        if verdict != SUPPRESSED_VERDICT:
            out.append(f"verdict {verdict!r}")
    else:
        m = _VERDICT_RE.fullmatch(verdict or "")
        first_t = max(found.values())
        near = {ph for ph, t in found.items() if first_t - t <= 2 * TOL_TEMP_C}
        if not m or m.group(1) not in near or abs(float(m.group(2)) - first_t) > TOL_TEMP_C:
            out.append(f"verdict {verdict!r} vs oracle {sorted(found.items())!r}")
    if len(reality) != 8:
        out.append(f"kineticRealityAtSelectedCooling keys {sorted(reality)!r}")
