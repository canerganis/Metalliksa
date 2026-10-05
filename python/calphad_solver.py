#!/usr/bin/env python3
"""
MetalliX CALPHAD multi-component Gibbs free energy minimisation (pycalphad)

pycalphad is REQUIRED. The solver never substitutes a non-thermodynamic model: when
pycalphad is not installed, when a requested element is absent from the selected
database, when the selected database is a pycalphad test fixture, or when the
equilibrium calculation fails, it returns success false with status "unavailable",
an unavailableKind and a reason (exit code 0; the request itself was well formed).
The former empirical "sub-regular" fallback (wt%-linear liquidus correlations,
sqrt/power-law phase fractions, ln gamma = -0.45 (1 - x), reported with
isEmpirical false) was removed: it was not a Gibbs minimisation and failed the
Gibbs-Duhem relation.

What a successful pycalphad run computes:
 1. Gibbs free energy minimisation (pycalphad equilibrium, compound-energy formalism)
    on a temperature grid at fixed composition and 1 atm.
 2. Chemical potentials (MU) and activities a_i = exp(mu_i / RT).
 3. Phase constitution (phase names, fractions, phase compositions) per temperature.
 4. New-PHACOMP Nv / Md screening (Ni-base only, tabulated values; unavailable otherwise).
 5. Liquidus / solidus refined between grid points by multi-section equilibria.
 6. A stepwise Scheil-Gulliver solidification path (pycalphad equilibria of the remaining
    liquid; scheil_gulliver) and, from it, partition coefficients k of the primary solid
    phase at its first appearance. Labelled unvalidated, with its validity range.

Every field that cannot be computed is null with a status and a reason (see
criticalTemperatureStatus, scheilSolidification, solutePartitioning[].reason):
 - gamma-prime solvus: unavailable, the L1_2 model phase also describes the
   disordered gamma and no site-fraction ordering check exists;
 - beta transus / sigma: flagged phase-name heuristics on the grid.

Speed: parsed databases and compiled pycalphad models (Workspace) are cached per process by
calphad_model_cache (key: database SHA-256, components, phases, condition keys). In the IPC
service calphad requests run in one dedicated worker (persistent_ipc_service
AFFINITY_SCRIPT_NAMES), so repeated requests for a system are warm. Each result reports
modelCache.status ("cold" / "warm") and timingsMs.

Databases: python/databases holds pycalphad test files next to a few real
assessments. Test fixtures (file header or catalogue flag) are refused; the catalogue
marks each entry as "assessment" or "test-fixture".
"""

import sys
import os
import glob
import json
import math
import re
import time
import warnings
from typing import Callable, Dict, Any, List, Optional, Set, Tuple

# Suppress benign pycalphad TDB syntax warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Test pycalphad availability
PYCALPHAD_AVAILABLE = False
PYCALPHAD_VERSION = "Not installed"
PYCALPHAD_IMPORT_ERROR: Optional[str] = None
try:
    import pycalphad
    from pycalphad import Database, equilibrium, variables as v
    import numpy as np
    PYCALPHAD_AVAILABLE = True
    PYCALPHAD_VERSION = pycalphad.__version__
except Exception as e:
    PYCALPHAD_AVAILABLE = False
    PYCALPHAD_IMPORT_ERROR = str(e)

import physical_constants
from alloy_data_calphad_battery_icme import provenance as _domain_data_provenance
from calphad_model_cache import process_cache, read_tdb_text
from input_validation import UNKNOWN_ELEMENT, ValidationError, validation_envelope

# Phase 6a value step (b): R is the exact SI 2019 product N_A*k from
# physical_constants (it replaced the CODATA printed truncation 8.314462618;
# relative change 1.8e-11).
GAS_CONSTANT_R = physical_constants.GAS_CONSTANT_R.value  # J / (mol*K), exact
ZERO_CELSIUS_K = physical_constants.ZERO_CELSIUS_K.value  # 273.15 K

# Directory containing open-source TDB databases
DATABASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "databases")

def _atomic_weight(el: str) -> float:
    """CIAAW 2021 abridged standard atomic weight (physical_constants), in g/mol.

    Phase 6a value step (b): every real element in physical_constants gets its own
    weight (P, S, Sn, Pb, Be, Sc ... no longer get the former 50.0 g/mol stand-in).
    A symbol with no standard atomic weight there is refused with UNKNOWN_ELEMENT
    (exit 2, HTTP 422); there is no fallback value.
    """
    try:
        return physical_constants.atomic_weight(el)
    except physical_constants.UnknownElementError:
        raise ValidationError(
            UNKNOWN_ELEMENT, f"elements.{el}",
            f"Element {el!r} has no standard atomic weight in physical_constants "
            f"(CIAAW 2021); it cannot be converted between wt% and at%.",
            {"element": repr(el), "reason": "no-standard-atomic-weight",
             "source": physical_constants.CIAAW_SOURCE},
        ) from None

# New-PHACOMP Electron Hole Numbers (N_v) and d-orbital energy levels (Md in eV)
PHACOMP_DATA = {
    "Cr": {"Nv": 4.66, "Md": 1.488},
    "Mo": {"Nv": 4.66, "Md": 1.550},
    "W":  {"Nv": 4.66, "Md": 1.655},
    "Mn": {"Nv": 3.66, "Md": 1.183},
    "Fe": {"Nv": 2.66, "Md": 0.985},
    "Co": {"Nv": 1.71, "Md": 0.777},
    "Ni": {"Nv": 0.66, "Md": 0.717},
    "V":  {"Nv": 5.66, "Md": 1.872},
    "Nb": {"Nv": 5.66, "Md": 2.117},
    "Ta": {"Nv": 5.66, "Md": 2.224},
    "Ti": {"Nv": 6.66, "Md": 2.271},
    "Zr": {"Nv": 6.66, "Md": 2.944},
    "Hf": {"Nv": 6.66, "Md": 3.020},
    "Al": {"Nv": 7.66, "Md": 1.900},
    "Si": {"Nv": 8.66, "Md": 1.900},
    "C":  {"Nv": 0.00, "Md": 0.000},
    "B":  {"Nv": 0.00, "Md": 0.000},
}

# Database status values of OPEN_TDB_CATALOG entries.
DB_STATUS_ASSESSMENT = "assessment"
DB_STATUS_TEST_FIXTURE = "test-fixture"

# Curated metadata registry of the TDB files in python/databases that this solver may use.
# "elements" is the ELEMENT list of the file itself (checked by test_calphad_honesty).
# Only entries with status "assessment" are usable; a "test-fixture" entry is refused
# (unavailableKind "database-test-fixture"): those files are pycalphad test inputs, not
# thermodynamic assessments, and a result computed from them must not be shown as one.
OPEN_TDB_CATALOG = [
    {
        "id": "alcocrni",
        "fileName": "alcocrni.tdb",
        "name": "Al-Co-Cr-Ni test database (pycalphad test fixture, refused)",
        "description": "File header: 'FOR TESTING PURPOSES ONLY -- NOT FOR RESEARCH' (CRALDAD version 1, combined from four ternaries). Its L12_FCC phase is the ordered/disordered FCC model phase, not a verified gamma-prime. Not an assessment.",
        "elements": ["AL", "CO", "CR", "NI"],
        "primaryPhases": ["FCC_A1", "L12_FCC", "LIQUID", "BCC_A2", "BCC_B2", "SIGMA_SGTE"],
        "source": "File header: FOR TESTING PURPOSES ONLY -- NOT FOR RESEARCH",
        "suitability": "None: test fixture, not an assessment",
        "assessedBaseElements": [],
        "status": DB_STATUS_TEST_FIXTURE,
        "usable": False,
        "statusReason": "file header: 'FOR TESTING PURPOSES ONLY -- NOT FOR RESEARCH'",
    },
    {
        "id": "cost507",
        "fileName": "COST507.tdb",
        "name": "COST 507 Comprehensive Light Alloys Database",
        "description": "The European COST Action 507 thermodynamic database (round II, 1999) for light-metal alloys: 27 elements (29 species with VA and the electron gas) and 243 phases.",
        "elements": ["AL", "MG", "SI", "CU", "ZN", "TI", "FE", "NI", "CR", "MN", "ZR", "V", "C", "B", "LI", "O", "N", "MO", "NB", "TA", "W", "HF", "Y", "CE", "ND", "SN", "AR"],
        "primaryPhases": ["FCC_A1", "HCP_A3", "LIQUID", "DIAMOND_A4", "MG2SI", "AL12MG17", "ALMG_BETA", "ALCU_THETA", "ALTI"],
        "source": "COST Action 507 Thermochemical Database for Light Alloys (file obtained from opencalphad.com)",
        "suitability": "Light-metal alloys with an Al, Mg or Ti base. Ni-, Fe- and Co-base alloys are outside its assessed scope and are refused.",
        "assessedBaseElements": ["AL", "MG", "TI"],
        "status": DB_STATUS_ASSESSMENT,
        "usable": True,
        "statusReason": None,
    },
    {
        "id": "mc_fecocrnbti",
        "fileName": "mc_fecocrnbti.tdb",
        "name": "Reduced Matcalc-derived Fe-Co-Cr-Nb-Ti database (pycalphad test fixture, refused)",
        "description": "File header: derived from the Matcalc steel database 2.060 (ODbL); 'Only Fe-Co-Cr-Nb-Ti parameters retained (for performance in test)'. A reduced file kept for tests, not an assessment of the alloys it names.",
        "elements": ["AL", "B", "C", "CO", "CR", "CU", "FE", "H", "HF", "LA", "MN", "MO", "N", "NB", "NI", "O", "P", "PD", "S", "SI", "TI", "V", "W", "Y"],
        "primaryPhases": ["FCC_A1", "BCC_A2", "LIQUID", "LAVES_C14", "LAVES_C15", "M23C6", "MC_SHP"],
        "source": "File header: Matcalc steel database 2.060 (ODbL), reduced for pycalphad test performance",
        "suitability": "None: test fixture, not an assessment",
        "assessedBaseElements": [],
        "status": DB_STATUS_TEST_FIXTURE,
        "usable": False,
        "statusReason": "file header: 'Only Fe-Co-Cr-Nb-Ti parameters retained (for performance in test)'",
    },
    {
        "id": "alni_dupin_2001",
        "fileName": "alni_dupin_2001.tdb",
        "name": "Al-Ni Dupin 2001 Benchmark (NIST/SGTE)",
        "description": "The Al-Ni assessment of Dupin, Ansara and Sundman with ordered FCC_L12, FCC_A1, BCC_B2 and intermetallics.",
        "elements": ["AL", "NI"],
        "primaryPhases": ["FCC_A1", "FCC_L12", "LIQUID", "BCC_A2", "BCC_B2", "AL3NI1", "AL3NI2", "AL3NI5"],
        "source": "Dupin, Ansara, Sundman, Calphad 25 (2001) 279-298",
        "suitability": "Binary Al-Ni only",
        "assessedBaseElements": ["AL", "NI"],
        "status": DB_STATUS_ASSESSMENT,
        "usable": True,
        "statusReason": None,
    },
    {
        "id": "cr_fe_ni",
        "fileName": "Cr-Fe-Ni_shallow_bcc.tdb",
        "name": "Cr-Fe-Ni minimal file (pycalphad test fixture, refused)",
        "description": "One phase only (BCC_A2 over Cr, Fe, Ni): no FCC and no LIQUID, so it cannot represent a stainless steel. No assessment reference in the file; its name and size identify it as a minimal pycalphad test input.",
        "elements": ["CR", "FE", "NI"],
        "primaryPhases": ["BCC_A2"],
        "source": "No assessment reference in the file; minimal test input (one phase)",
        "suitability": "None: test fixture, not an assessment",
        "assessedBaseElements": [],
        "status": DB_STATUS_TEST_FIXTURE,
        "usable": False,
        "statusReason": "catalogue flag: single-phase minimal test input (BCC_A2 only, no FCC, no LIQUID)",
    },
    {
        "id": "crtiv_ghosh",
        "fileName": "crtiv_ghosh.tdb",
        "name": "Cr-Ti-V Assessment (Ghosh)",
        "description": "Thermodynamic assessment of the ternary Cr-Ti-V system (TDB written by T. Abe and T. Bolotova, NIMS, 2014). Contains no Al.",
        "elements": ["TI", "CR", "V"],
        "primaryPhases": ["HCP_A3", "BCC_A2", "LIQUID"],
        "source": "Cr-Ti-V assessment (G. Ghosh), TDB file by T. Abe and T. Bolotova (NIMS)",
        "suitability": "Cr-Ti-V only; commercial Ti alloys such as Ti-6Al-4V contain Al and are not covered",
        "assessedBaseElements": ["TI", "CR", "V"],
        "status": DB_STATUS_ASSESSMENT,
        "usable": True,
        "statusReason": None,
    },
]


# Alloy systems the application works with, as (id, label, base element, major alloying elements).
# Element sets only (no composition numbers): coverage depends on which elements a database
# contains and which base elements it is assessed for. Minor/impurity elements (C, Co, B, ...) are
# left out, so "covered" is the most favourable reading; a request that adds them can still be
# refused for missing elements.
COVERAGE_REFERENCE_SYSTEMS = (
    ("in718", "Inconel 718 (UNS N07718)", "Ni", ("Ni", "Cr", "Fe", "Nb", "Mo", "Ti", "Al")),
    ("in625", "Inconel 625 (UNS N06625)", "Ni", ("Ni", "Cr", "Mo", "Nb", "Fe")),
    ("ti6al4v", "Ti-6Al-4V (UNS R56400)", "Ti", ("Ti", "Al", "V")),
    ("ss316l", "316L stainless steel (UNS S31603)", "Fe", ("Fe", "Cr", "Ni", "Mo", "Mn", "Si")),
    ("alsi10mg", "AlSi10Mg (EN AC-43000 family)", "Al", ("Al", "Si", "Mg")),
    ("alsi10mg_fe", "AlSi10Mg with Fe impurity", "Al", ("Al", "Si", "Mg", "Fe")),
    ("ni_al", "Ni-Al binary (model alloy)", "Ni", ("Ni", "Al")),
)


# Deviations observed with the covering database (stated, not corrected).
COVERAGE_KNOWN_DEVIATIONS = {
    "ti6al4v": ("COST 507 gives the HCP_A3 (alpha) phase up to about 925 degC for Ti-6Al-4V on a 25 degC grid "
                "(phase-name heuristic), against a beta transus of about 995 degC usually reported for this "
                "alloy; treat alpha/beta results from this database as indicative only."),
}


def system_coverage() -> List[Dict[str, Any]]:
    """Which reference alloy systems an installed, assessed database can answer, and why not otherwise.

    Uses the same resolve_database rules as a calculation (no database is substituted, test
    fixtures never count). "covered" says a database contains every major element and is
    assessed for the base element; it does not say that results were validated for that alloy.
    """
    out = []
    for sys_id, label, base, elements in COVERAGE_REFERENCE_SYSTEMS:
        res = resolve_database(list(elements), None, None, base)
        row: Dict[str, Any] = {"id": sys_id, "label": label, "baseElement": base, "elements": list(elements)}
        if res["ok"]:
            row.update({"status": "covered", "databaseId": res["id"], "databaseUsed": res["name"],
                        "databaseSuitability": res["suitability"],
                        "note": "a database contains every major element and is assessed for the base element; "
                                "agreement with experiment is not established by this check"})
            if sys_id in COVERAGE_KNOWN_DEVIATIONS:
                row["knownDeviation"] = COVERAGE_KNOWN_DEVIATIONS[sys_id]
        else:
            row.update({"status": "unavailable", "unavailableKind": res["kind"],
                        "reason": "no thermodynamic database for this system: " + res["reason"],
                        "missingElements": res["extra"].get("missingElements", [])})
        out.append(row)
    return out


def list_available_databases() -> Dict[str, Any]:
    """Returns the list of available Open TDB databases and engine capabilities."""
    installed_files = []
    if os.path.exists(DATABASES_DIR):
        installed_files = [os.path.basename(p) for p in glob.glob(os.path.join(DATABASES_DIR, "*.tdb"))]

    return {
        "systemCoverage": system_coverage(),
        "modelCache": process_cache().stats(),
        "success": True,
        "engine": "pycalphad-open-tdb",
        "pycalphadAvailable": PYCALPHAD_AVAILABLE,
        "pycalphadVersion": PYCALPHAD_VERSION,
        "unavailableReason": None if PYCALPHAD_AVAILABLE else UNAVAILABLE_REASON_PYCALPHAD,
        "databasesCount": len(OPEN_TDB_CATALOG),
        "usableDatabasesCount": sum(1 for e in OPEN_TDB_CATALOG if e["usable"]),
        "databases": OPEN_TDB_CATALOG,
        "installedFiles": installed_files
    }


def normalize_composition(elements: dict, unit: str = "wt_pct") -> Tuple[dict, dict]:
    """Converts element input dictionary into both normalized wt% and atomic mole fractions."""
    clean = {}
    for el, val in elements.items():
        if val is None or float(val) <= 0:
            continue
        if isinstance(el, str) and el.strip() == "RE":
            # "RE" is the usual label for a rare-earth (mischmetal) addition, e.g. WE43;
            # read as an element symbol it would silently become rhenium. Refuse it.
            raise ValidationError(
                UNKNOWN_ELEMENT, "elements.RE",
                "'RE' is ambiguous: it usually means rare earths (a mixture), not rhenium. "
                "Send 'Re' for rhenium, or the individual rare-earth elements with their amounts.",
                {"element": "'RE'", "reason": "ambiguous-rare-earth-label"},
            )
        # Title case element symbols: 'ni' -> 'Ni'
        el_symbol = el.strip().capitalize()
        if len(el.strip()) > 1 and el.strip()[1].islower():
            el_symbol = el.strip()[0].upper() + el.strip()[1:].lower()
        else:
            el_symbol = el.strip().upper()
            if len(el_symbol) == 2:
                el_symbol = el_symbol[0] + el_symbol[1].lower()
        clean[el_symbol] = float(val)

    if not clean:
        clean = {"Ni": 80.0, "Al": 10.0, "Cr": 10.0}

    total = sum(clean.values())
    if total <= 0:
        total = 1.0

    if unit == "at_pct":
        at_frac = {el: val / total for el, val in clean.items()}
        # Compute wt%
        mw_mix = sum(at_frac[el] * _atomic_weight(el) for el in at_frac)
        wt_pct = {el: (at_frac[el] * _atomic_weight(el) / mw_mix) * 100.0 for el in at_frac}
    else:
        wt_pct = {el: (val / total) * 100.0 for el, val in clean.items()}
        # Convert wt% to moles
        moles = {el: (pct / 100.0) / _atomic_weight(el) for el, pct in wt_pct.items()}
        tot_moles = sum(moles.values())
        at_frac = {el: m / tot_moles for el, m in moles.items()}

    return wt_pct, at_frac


# --------------------------------------------------------------------------- unavailable results
UNAVAILABLE_REASON_PYCALPHAD = "pycalphad not installed"
KIND_PYCALPHAD_MISSING = "pycalphad-not-installed"
KIND_TEST_FIXTURE = "database-test-fixture"
KIND_ELEMENTS_MISSING = "elements-missing-from-database"
KIND_NO_DATABASE_COVERS = "no-database-covers-elements"
KIND_UNKNOWN_DATABASE = "unknown-database-id"
KIND_DATABASE_FILE_MISSING = "database-file-missing"
KIND_DATABASE_LOAD_FAILED = "database-load-failed"
KIND_SINGLE_COMPONENT = "fewer-than-two-components"
KIND_EQUILIBRIUM_FAILED = "pycalphad-equilibrium-failed"
KIND_NOT_ASSESSED = "database-not-assessed-for-base"
KIND_NON_FINITE_OUTPUT = "non-finite-result"


def base_element(at_frac: dict) -> str:
    """The alloy's base element: the largest atomic fraction (first one on a tie)."""
    return max(at_frac, key=lambda el: at_frac[el])


class CalphadUnavailable(Exception):
    """Raised inside the pycalphad path for a condition that makes the request unanswerable."""

    def __init__(self, kind: str, reason: str, **extra: Any):
        super().__init__(reason)
        self.kind = kind
        self.reason = reason
        self.extra = extra


def unavailable_result(
    kind: str,
    reason: str,
    *,
    name: str,
    wt_pct: dict,
    at_frac: dict,
    t_min_c: float,
    t_max_c: float,
    t_step_c: float,
    reasons: Optional[List[str]] = None,
    **extra: Any
) -> Dict[str, Any]:
    """The explicit "no CALPHAD result" envelope: success false, status "unavailable".

    It carries no equilibriumProfile, no critical temperatures and no isEmpirical flag
    (there is no number to label). ``reason`` is the first reason; ``reasons`` lists all.
    """
    out: Dict[str, Any] = {
        "success": False,
        "status": "unavailable",
        "unavailableKind": kind,
        "reason": reason,
        "reasons": list(reasons) if reasons else [reason],
        "engine": "pycalphad-open-tdb",
        "pycalphadAvailable": PYCALPHAD_AVAILABLE,
        "pycalphadVersion": PYCALPHAD_VERSION if PYCALPHAD_AVAILABLE else None,
        "alloyName": name,
        "nominalComposition": wt_pct,
        "atomicFractions": at_frac,
        "requestedElements": list(at_frac.keys()),
        "baseElement": base_element(at_frac),
        "temperatureRangeC": [t_min_c, t_max_c],
        "temperatureStepC": t_step_c,
    }
    out.update(extra)
    return out


# --------------------------------------------------------------------------- database resolution
_TDB_ELEMENT_CACHE: Dict[str, Set[str]] = {}

# Header lines (comments, first lines of a file) that mark a pycalphad test input.
_FIXTURE_HEADER_MARKERS = (
    "FOR TESTING PURPOSES ONLY",
    "NOT FOR RESEARCH",
    "FOR PERFORMANCE IN TEST",
)
_HEADER_LINES_SCANNED = 40


def tdb_elements_from_text(text: str) -> Set[str]:
    """Element symbols of a TDB text, from its ELEMENT commands (no pycalphad needed).

    '$' starts a comment; a command ends at '!'. VA and the electron gas '/-' are not
    elements of the alloy and are dropped. test_calphad_honesty checks this parser
    against pycalphad's Database.elements for every catalogue file.
    """
    out: Set[str] = set()
    for line in text.splitlines():
        code = line.split("$", 1)[0]
        for command in code.split("!"):
            m = re.match(r"\s*EL(?:EM(?:ENT)?)?\s+(\S+)", command, re.IGNORECASE)
            if m:
                sym = m.group(1).upper()
                if sym not in ("VA", "/-"):
                    out.add(sym)
    return out


def tdb_file_elements(path: str) -> Set[str]:
    if path not in _TDB_ELEMENT_CACHE:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            _TDB_ELEMENT_CACHE[path] = tdb_elements_from_text(fh.read())
    return set(_TDB_ELEMENT_CACHE[path])


def database_fixture_reason(entry: Optional[dict], path: Optional[str]) -> Optional[str]:
    """Why a database file is a pycalphad test fixture, or None.

    Two independent checks: the catalogue status, and the comment header of the file
    itself (so a test file is still refused if the catalogue entry is ever edited).
    """
    if entry is not None and entry.get("status") == DB_STATUS_TEST_FIXTURE:
        return entry.get("statusReason") or "catalogue marks it as a test fixture"
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                head = [next(fh, "") for _ in range(_HEADER_LINES_SCANNED)]
        except OSError:
            return None
        for line in head:
            stripped = line.strip()
            if not stripped.startswith("$"):
                continue
            upper = stripped.upper()
            for marker in _FIXTURE_HEADER_MARKERS:
                if marker in upper:
                    return f"file header: {stripped.lstrip('$ ').strip()!r}"
    return None


def _entry_by_id(preferred_id: str) -> Optional[dict]:
    for entry in OPEN_TDB_CATALOG:
        if entry["id"] == preferred_id or entry["fileName"] == preferred_id:
            return entry
    return None


def _missing(requested: List[str], db_elements: Set[str]) -> List[str]:
    return [el for el in requested if el.upper() not in db_elements]


def resolve_database(
    requested: List[str],
    preferred_id: Optional[str] = None,
    custom_tdb_text: Optional[str] = None,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Choose the thermodynamic database for ``requested`` element symbols, or refuse.

    Rules (no heuristics on element order, no silent substitution, no dropped element):
      * custom TDB text: used as given (status "user-supplied", no scope check); refused
        when it lacks a requested element;
      * a databaseId: that catalogue entry only; refused when it is unknown, a test
        fixture, missing on disk, not assessed for the alloy's base element
        (``assessedBaseElements``), or lacking a requested element;
      * otherwise: the usable (status "assessment") catalogue database with the fewest
        elements that is assessed for the base element and contains every requested
        element. A database whose file header marks a test file is skipped (recorded in
        databasesConsidered), never aborting the selection. Refused when none qualifies.

    ``base`` is the base element symbol (largest atomic fraction); None skips the scope check.
    Returns {"ok": True, "path", "name", "id", "status", "suitability", "elements"} or
    {"ok": False, "kind", "reason", "extra"}. Needs no pycalphad.
    """
    if custom_tdb_text:
        elems = tdb_elements_from_text(custom_tdb_text)
        missing = _missing(requested, elems)
        if missing:
            return {"ok": False, "kind": KIND_ELEMENTS_MISSING,
                    "reason": f"element(s) {', '.join(missing)} not in the supplied TDB text; "
                              f"refusing to drop them and renormalise",
                    "extra": {"missingElements": missing, "databaseId": "custom",
                              "databaseUsed": "User-supplied TDB text", "databaseStatus": "user-supplied"}}
        return {"ok": True, "path": "", "name": "User-supplied TDB text", "id": "custom",
                "status": "user-supplied", "suitability": "Not verified (user-supplied)",
                "elements": elems}

    if preferred_id:
        entry = _entry_by_id(preferred_id)
        if entry is None:
            return {"ok": False, "kind": KIND_UNKNOWN_DATABASE,
                    "reason": f"unknown databaseId {preferred_id!r}; known ids: "
                              f"{', '.join(e['id'] for e in OPEN_TDB_CATALOG)}",
                    "extra": {"databaseId": preferred_id}}
        candidates = [entry]
    else:
        candidates = sorted((e for e in OPEN_TDB_CATALOG if e["usable"]), key=lambda e: len(e["elements"]))

    base_up = base.upper() if base else None
    considered: List[Dict[str, Any]] = []
    best = None  # in-scope usable candidate with the fewest missing elements (ties: the narrower file)
    for entry in candidates:
        path = os.path.join(DATABASES_DIR, entry["fileName"])
        if not os.path.exists(path):
            if preferred_id:
                return {"ok": False, "kind": KIND_DATABASE_FILE_MISSING,
                        "reason": f"database file {entry['fileName']} is not installed",
                        "extra": {"databaseId": entry["id"], "databaseUsed": entry["name"]}}
            considered.append({"databaseId": entry["id"], "status": "file-missing"})
            continue
        fixture = database_fixture_reason(entry, path)
        if fixture:
            if preferred_id:
                return {"ok": False, "kind": KIND_TEST_FIXTURE,
                        "reason": f"database {entry['id']!r} is a pycalphad test fixture, not a thermodynamic "
                                  f"assessment ({fixture}); refused",
                        "extra": {"databaseId": entry["id"], "databaseUsed": entry["name"],
                                  "databaseStatus": DB_STATUS_TEST_FIXTURE}}
            considered.append({"databaseId": entry["id"], "status": "test-fixture-skipped", "reason": fixture})
            continue
        assessed = entry.get("assessedBaseElements", [])
        if base_up is not None and base_up not in assessed:
            if preferred_id:
                return {"ok": False, "kind": KIND_NOT_ASSESSED,
                        "reason": f"database {entry['id']!r} is not assessed for {base}-base alloys "
                                  f"(assessed base elements: {', '.join(assessed)})",
                        "extra": {"databaseId": entry["id"], "databaseUsed": entry["name"],
                                  "databaseStatus": entry["status"], "assessedBaseElements": list(assessed),
                                  "databaseSuitability": entry["suitability"]}}
            considered.append({"databaseId": entry["id"], "status": entry["status"], "notAssessedForBase": base})
            continue
        elems = tdb_file_elements(path)
        missing = _missing(requested, elems)
        if not missing:
            return {"ok": True, "path": path, "name": entry["name"], "id": entry["id"],
                    "status": entry["status"], "suitability": entry["suitability"], "elements": elems}
        considered.append({"databaseId": entry["id"], "status": entry["status"], "missingElements": missing})
        if preferred_id:
            return {"ok": False, "kind": KIND_ELEMENTS_MISSING,
                    "reason": f"element(s) {', '.join(missing)} not in database {entry['name']!r}; "
                              f"refusing to drop them and renormalise",
                    "extra": {"missingElements": missing, "databaseId": entry["id"],
                              "databaseUsed": entry["name"], "databaseStatus": entry["status"]}}
        if best is None or len(missing) < len(best[1]):
            best = (entry, missing)

    if best is not None:
        entry, missing = best
        return {"ok": False, "kind": KIND_NO_DATABASE_COVERS,
                "reason": f"no usable thermodynamic database contains all requested elements "
                          f"({', '.join(requested)}); the closest, {entry['name']!r}, lacks "
                          f"{', '.join(missing)}. Test-fixture databases are never used",
                "extra": {"missingElements": missing, "databaseId": entry["id"], "databaseUsed": entry["name"],
                          "databaseStatus": entry["status"], "databasesConsidered": considered}}
    if any(c.get("notAssessedForBase") for c in considered):
        scopes = "; ".join(f"{e['id']}: {', '.join(e['assessedBaseElements'])}"
                           for e in OPEN_TDB_CATALOG if e["usable"])
        return {"ok": False, "kind": KIND_NOT_ASSESSED,
                "reason": f"no usable thermodynamic database is assessed for {base}-base alloys "
                          f"(assessed base elements by database: {scopes}); databases are never substituted",
                "extra": {"databasesConsidered": considered}}
    return {"ok": False, "kind": KIND_NO_DATABASE_COVERS,
            "reason": "no usable thermodynamic database is installed",
            "extra": {"databasesConsidered": considered}}


def load_database_with_info(tdb_path_or_text: str, is_raw_text: bool = False) -> Tuple[Any, Dict[str, Any]]:
    """Parsed pycalphad Database plus cache information, or (None, info) when it cannot be loaded.

    The TDB text is read and hashed on every call; the parse is reused from the process cache
    (calphad_model_cache) only for identical text, so an edited file is never served stale.
    """
    if not PYCALPHAD_AVAILABLE:
        return None, {"status": "unavailable"}
    try:
        text = tdb_path_or_text if is_raw_text else read_tdb_text(tdb_path_or_text)
        return process_cache().database(
            text, lambda t: Database.from_string(t, fmt="tdb"),
            path=None if is_raw_text else tdb_path_or_text)
    except Exception as e:
        sys.stderr.write(f"[CALPHAD] Error loading TDB: {e}\n")
        return None, {"status": "error"}


def load_pycalphad_database(tdb_path_or_text: str, is_raw_text: bool = False) -> Any:
    """Parsed pycalphad Database (cached per process by content hash), or None."""
    return load_database_with_info(tdb_path_or_text, is_raw_text)[0]


PHACOMP_UNAVAILABLE_KEYS = {
    "n_v_bar": None,
    "m_d_bar": None,
    "tcpEmbrittlementRisk": None,
    "tcpSigmaRiskTemperatureC": None,
    "thermodynamicStabilityIndex": None,
}


def calculate_phacomp(at_frac: dict) -> dict:
    """New-PHACOMP N_v and M_d for TCP embrittlement screening.

    Applies to Ni-base superalloys only; for any other base element it is unavailable
    (the audit showed AlSi10Mg and Ti-6Al-4V reported "High" TCP risk and an 850 C sigma
    temperature). An element without a tabulated N_v/M_d makes it unavailable too: the
    former default of 1.0 for unlisted elements was an invented value.
    """
    base = base_element(at_frac)
    if base != "Ni":
        return {"status": "unavailable",
                "reason": f"New-PHACOMP (Nv/Md TCP screening) applies to Ni-base superalloys only; "
                          f"this alloy is {base}-base",
                **PHACOMP_UNAVAILABLE_KEYS}
    unlisted = [el for el in at_frac if el not in PHACOMP_DATA]
    if unlisted:
        return {"status": "unavailable",
                "reason": f"no tabulated Nv/Md value for element(s) {', '.join(unlisted)}",
                **PHACOMP_UNAVAILABLE_KEYS}
    n_v_bar = sum(at_frac[elem] * PHACOMP_DATA[elem]["Nv"] for elem in at_frac)
    m_d_bar = sum(at_frac[elem] * PHACOMP_DATA[elem]["Md"] for elem in at_frac)

    if n_v_bar > 2.49 or m_d_bar > 0.985:
        risk = "High"
        sigma_temp_c = 850.0
    elif n_v_bar > 2.30 or m_d_bar > 0.920:
        risk = "Moderate"
        sigma_temp_c = 820.0
    else:
        risk = "Low"
        sigma_temp_c = None

    stability_index = max(0.0, min(100.0, 100.0 - (n_v_bar - 2.0) * 80.0))

    return {
        "status": "screening-tabulated-values",
        "n_v_bar": round(n_v_bar, 4),
        "m_d_bar": round(m_d_bar, 4),
        "tcpEmbrittlementRisk": risk,
        "tcpSigmaRiskTemperatureC": sigma_temp_c,
        "thermodynamicStabilityIndex": round(stability_index, 1)
    }


LIQUID_FULL_FRACTION = 0.999   # liquidus: no solid phase above the 0.001 reporting cut-off
LIQUID_TRACE_FRACTION = 0.001  # solidus: the liquid phase is absent (phases <= 0.001 are not reported)
REFINE_POINTS_PER_ROUND = 9    # interior points per refinement round (multi-section)
REFINE_MAX_ROUNDS = 6

# refine(temperatures_c) -> liquid fraction at each temperature, None where that point did not converge
RefineFn = Callable[[List[float]], List[Optional[float]]]


def _liquid_fraction_of_point(point: Dict[str, Any]) -> float:
    return sum(ph["fraction"] for ph in point["phases"] if "LIQUID" in ph["phaseId"])


def _refine_boundary(
    lo_c: float,
    hi_c: float,
    on_hi_side: Callable[[float], bool],
    refine: Optional[RefineFn],
    tolerance_c: float,
) -> Tuple[float, float, int, int, bool]:
    """Narrow the bracket [lo_c, hi_c] around a boundary by repeated multi-section.

    Each round evaluates REFINE_POINTS_PER_ROUND equally spaced interior temperatures in one
    equilibrium call, then keeps the sub-interval where the liquid fraction crosses the
    threshold (on_hi_side false at its lower end, true at its upper end). Assumes the liquid
    fraction crosses the threshold once in the bracket. Returns
    (lo, hi, rounds, points evaluated, complete); complete is False without ``refine``, when
    a point fails to converge, or when the tolerance was not reached.
    """
    rounds = 0
    points = 0
    if refine is None:
        return lo_c, hi_c, 0, 0, False
    while hi_c - lo_c > tolerance_c:
        if rounds >= REFINE_MAX_ROUNDS:
            return lo_c, hi_c, rounds, points, False
        temps = [round(lo_c + (hi_c - lo_c) * k / (REFINE_POINTS_PER_ROUND + 1), 2)
                 for k in range(1, REFINE_POINTS_PER_ROUND + 1)]
        liquid = refine(temps)
        rounds += 1
        points += len(temps)
        if len(liquid) != len(temps) or any(x is None for x in liquid):
            return lo_c, hi_c, rounds, points, False
        flags = [on_hi_side(x) for x in liquid]
        if any(flags):
            first = flags.index(True)
            hi_c = temps[first]
            if first > 0:
                lo_c = temps[first - 1]
        else:
            lo_c = temps[-1]
    return lo_c, hi_c, rounds, points, True


def derive_critical_temperatures(
    equilibrium_profile: List[Dict[str, Any]],
    l12_by_name_max_c: Optional[float],
    beta_transus_c: Optional[float],
    sigma_phase_solvus_c: Optional[float],
    phacomp_sigma_c: Optional[float],
    refine: Optional[RefineFn] = None,
    tolerance_c: float = 0.5,
) -> Tuple[Dict[str, Optional[float]], Dict[str, Dict[str, Any]]]:
    """Critical temperatures from a computed grid, with a status per field.

    Returns (criticalTemperatures, criticalTemperatureStatus). Only what the grid (and the
    optional refinement) supports is a number; everything else is None with a reason:
      * liquidus: the lowest temperature with liquid >= 99.9 % (no solid phase above the
        0.001 reporting cut-off). The grid points that bracket it are refined with ``refine``
        down to ``tolerance_c``; the value is the middle of the final bracket, which is
        reported in the status as bracketC. Without ``refine`` (or when a point fails) the
        bracket is the grid interval and the status says "bracketed-by-grid".
      * solidus: the lowest temperature with liquid > 0.1 %, bracketed and refined the same
        way. Unavailable when the liquid is already present at the lowest grid temperature,
        or never appears, instead of the former value (the lowest grid temperature).
      * gamma-prime solvus: always None, phase name L1_2 is not proof of ordering;
      * beta transus / sigma: flagged phase-name heuristics.
    Grid points marked status "not-converged" are ignored. The critical temperatures assume
    the liquid fraction rises monotonically with temperature. Pure function of the profile
    and ``refine``: testable without pycalphad.
    """
    status: Dict[str, Dict[str, Any]] = {}

    def _unavailable(reason: str, **more: Any) -> Dict[str, Any]:
        return {"status": "unavailable", "reason": reason, **more}

    converged = sorted((p for p in equilibrium_profile if p.get("status", "converged") != "not-converged"),
                       key=lambda p: p["temperatureC"])
    failed_temps = sorted(p["temperatureC"] for p in equilibrium_profile if p.get("status") == "not-converged")

    def locate(on_hi_side: Callable[[float], bool], absent: str, at_grid_minimum: str, definition: str):
        if not converged:
            return None, _unavailable("no grid point converged")
        flags = [on_hi_side(_liquid_fraction_of_point(p)) for p in converged]
        if not any(flags):
            return None, _unavailable(absent)
        j = flags.index(True)
        if j == 0:
            return None, _unavailable(at_grid_minimum)
        lo0, hi0 = converged[j - 1]["temperatureC"], converged[j]["temperatureC"]
        lo, hi, rounds, points, complete = _refine_boundary(lo0, hi0, on_hi_side, refine, tolerance_c)
        value = (lo + hi) / 2.0
        note = ("refined by multi-section equilibrium calculations between the bracketing grid points"
                if complete else "bracket of two grid points, not refined")
        entry = {"status": "bisected" if complete else "bracketed-by-grid",
                 "bracketC": [lo, hi], "gridBracketC": [lo0, hi0], "toleranceC": round(hi - lo, 2),
                 "refinementRounds": rounds, "refinementPoints": points, "definition": definition, "note": note}
        if any(lo0 < t < hi0 for t in failed_temps):
            entry["warning"] = "a grid point inside this bracket did not converge"
        return value, entry

    liquidus_c, status["liquidusC"] = locate(
        lambda liq: liq >= LIQUID_FULL_FRACTION,
        "liquid never reaches 99.9 % inside the temperature grid, so the liquidus is above the grid",
        "liquid is already >= 99.9 % at the lowest grid temperature, so the liquidus is at or below the grid",
        "lowest temperature with liquid >= 99.9 % (up to 0.1 % solid may remain: phases below 0.1 % are not reported)")
    solidus_c, status["solidusC"] = locate(
        lambda liq: liq > LIQUID_TRACE_FRACTION,
        "no liquid appears inside the temperature grid, so the solidus is above the grid",
        "liquid is already present at the lowest grid temperature, so the solidus is at or below the grid",
        "lowest temperature with liquid > 0.1 % (liquid below 0.1 % is not reported)")
    if liquidus_c is not None and solidus_c is not None and solidus_c > liquidus_c:
        solidus_c = None
        status["solidusC"] = _unavailable("the liquid fraction is not monotonic in temperature on this grid "
                                          "(solidus above liquidus); the boundaries are not identified")

    if l12_by_name_max_c is None:
        status["gammaPrimeSolvusC"] = _unavailable("no phase named L1_2 appeared on the grid")
    else:
        status["gammaPrimeSolvusC"] = _unavailable(
            "gamma-prime was identified by phase name only: the L1_2 model phase also describes the disordered "
            "gamma matrix, and no site-fraction ordering check is implemented, so a gamma-prime solvus is not stated",
            observedByNameOnly={"phaseNameContains": "L12", "highestGridTemperatureC": round(l12_by_name_max_c, 1)})

    status["betaTransusC"] = (
        {"status": "heuristic-phase-name",
         "note": "highest grid temperature with HCP_A3 > 1 %; grid resolution; meaningful for Ti alloys only"}
        if beta_transus_c else _unavailable("no HCP_A3 phase above 1 % on the grid"))
    if sigma_phase_solvus_c:
        status["tcpSigmaRiskTemperatureC"] = {"status": "heuristic-phase-name",
                                              "note": "highest grid temperature with a phase named SIGMA > 0.5 %"}
    elif phacomp_sigma_c is not None:
        status["tcpSigmaRiskTemperatureC"] = {"status": "screening-constant",
                                              "note": "New-PHACOMP risk-class constant, not a calculated solvus"}
    else:
        status["tcpSigmaRiskTemperatureC"] = _unavailable(
            "no sigma phase on the grid, and New-PHACOMP gives no sigma temperature (not a Ni-base alloy, or risk Low)")
    for key in ("gammaDoublePrimeSolvusC", "deltaSolvusC", "carbidePrecipitationC"):
        status[key] = _unavailable("not computed by this engine")

    status["freezingRangeC"] = (
        {"status": "computed", "note": "liquidus - solidus, both with the tolerances reported above"}
        if liquidus_c is not None and solidus_c is not None
        else _unavailable("needs both the liquidus and the solidus"))

    values: Dict[str, Optional[float]] = {
        "liquidusC": round(liquidus_c, 1) if liquidus_c is not None else None,
        "solidusC": round(solidus_c, 1) if solidus_c is not None else None,
        "freezingRangeC": round(liquidus_c - solidus_c, 1) if liquidus_c is not None and solidus_c is not None else None,
        "gammaPrimeSolvusC": None,
        "gammaDoublePrimeSolvusC": None,
        "deltaSolvusC": None,
        "betaTransusC": round(beta_transus_c, 1) if beta_transus_c else None,
        "carbidePrecipitationC": None,
        "tcpSigmaRiskTemperatureC": round(sigma_phase_solvus_c, 1) if sigma_phase_solvus_c else phacomp_sigma_c,
    }
    return values, status


PHASE_COLORS = {
    "LIQUID": "#0284c7",
    "FCC_A1": "#38bdf8",
    "FCC_L12": "#a855f7",
    "L12_FCC": "#a855f7",
    "BCC_A2": "#10b981",
    "BCC_B2": "#f59e0b",
    "HCP_A3": "#6366f1",
    "SIGMA_SGTE": "#ef4444",
    "LAVES_C14": "#f97316",
    "LAVES_C15": "#ea580c",
    "MG2SI": "#14b8a6",
    "DIAMOND_A4": "#eab308",
    "CEMENTITE": "#b45309",
    "M23C6": "#dc2626",
}


def _friendly_phase_name(phase_str: str) -> str:
    if phase_str in ["FCC_A1", "GAMMA"]:
        return "γ-Matrix (FCC_A1 solid solution)"
    if phase_str in ["FCC_L12", "L12_FCC"]:
        return "L1_2 phase (γ' only if ordered; ordering not verified)"
    if phase_str in ["BCC_A2"]:
        return "α-Ferrite / β-Titanium (BCC_A2)"
    if phase_str in ["BCC_B2"]:
        return "B2 Superlattice Intermetallic (BCC_B2)"
    if phase_str in ["HCP_A3"]:
        return "α-Phase / HCP Matrix (HCP_A3)"
    if "SIGMA" in phase_str:
        return "TCP σ (Sigma) Embrittling Phase"
    if phase_str == "LIQUID":
        return "Liquid Phase"
    if phase_str == "MG2SI":
        return "Mg2Si Hardening Precipitate"
    return phase_str


class _EquilibriumRunner:
    """Runs pycalphad equilibria for one (database, components, phases, condition keys) system.

    With pycalphad's Workspace the compiled models come from the process cache
    (calphad_model_cache); without it (older pycalphad) each call is a plain equilibrium().
    Every call goes through ``run`` with the same condition keys, so a cached Workspace keeps
    its PhaseRecordFactory (pycalphad rebuilds it only when the condition keys change).
    """

    def __init__(self, dbf: Any, db_sha: str, comps: List[str], phases: List[str], conditions: Dict[Any, Any]):
        self.dbf = dbf
        self.comps = comps
        self.phases = phases
        self.workspace: Any = None
        self.lock: Any = None
        self.calls = 0
        self.cache_info: Dict[str, Any] = {"status": "not-used", "buildMs": 0.0}
        try:
            from pycalphad import Workspace
        except ImportError:  # older pycalphad: plain equilibrium(), every call builds its models
            self.cache_info = {"status": "unavailable-no-workspace-api", "buildMs": 0.0}
            return
        key = (PYCALPHAD_VERSION, db_sha, tuple(sorted(comps)), tuple(sorted(phases)),
               tuple(str(k) for k in conditions))
        self.workspace, self.lock, self.cache_info = process_cache().workspace(
            key, lambda: Workspace(dbf, comps, phases, conditions))

    def run(self, conditions: Dict[Any, Any], as_dataset: bool = False) -> Any:
        self.calls += 1
        if self.workspace is None:
            return equilibrium(self.dbf, self.comps, self.phases, conditions)
        self.workspace.conditions = conditions
        result = self.workspace.eq
        return result.get_dataset() if as_dataset else result


def _flat_point_arrays(eq_r: Any, n: int) -> Tuple[Any, Any, Any, Any, Any]:
    """(GM[n], MU[n, c], Phase[n, v], NP[n, v], X[n, v, c] or None) for n temperatures at one composition."""
    def arr(x: Any) -> Any:
        return np.asarray(getattr(x, "values", x))
    gm = arr(eq_r.GM).reshape(n, -1)[:, 0]
    mu = arr(eq_r.MU).reshape(n, -1)
    ph = arr(eq_r.Phase).reshape(n, -1)
    nps = arr(eq_r.NP).reshape(n, -1)
    x = None
    if hasattr(eq_r, "X"):
        try:
            x = arr(eq_r.X).reshape(n, ph.shape[1], -1)
        except Exception:
            x = None
    return gm, mu, ph, nps, x


SCHEIL_DEFAULT_STEP_C = 2.0
SCHEIL_MAX_STEPS = 400
SCHEIL_TIME_BUDGET_S = 20.0
SCHEIL_LIQUID_STOP = 1e-3       # stop when < 0.1 % liquid remains (same cut-off as the solidus definition)
SCHEIL_MIN_MOLE_FRACTION = 1e-6  # lower bound for a liquid-composition condition (clamps are counted)


def scheil_gulliver(
    run_point: Callable[[float, Dict[str, float]], Optional[Dict[str, Any]]],
    start_c: float,
    x0: Dict[str, float],
    step_c: float = SCHEIL_DEFAULT_STEP_C,
    max_steps: int = SCHEIL_MAX_STEPS,
    time_budget_s: float = SCHEIL_TIME_BUDGET_S,
    min_temperature_c: float = -273.0,
) -> Dict[str, Any]:
    """Scheil-Gulliver solidification path (no diffusion in the solid, complete mixing in the liquid).

    Classic stepwise algorithm: at each temperature step the current liquid (composition x_L) is
    equilibrated; the solid that forms is removed from the system, the liquid fraction is
    multiplied by the local liquid fraction and x_L becomes the composition of the equilibrium
    liquid. ``run_point(T_C, x_liquid)`` returns {"liquid": f, "liquidX": {...},
    "phases": {name: amount}} for one equilibrium, or None when it did not converge.

    Fractions are on the pycalphad basis (moles of atoms). The path stops when the liquid
    fraction falls below SCHEIL_LIQUID_STOP, when the liquid disappears inside one step (an
    invariant reaction or the step skipped the end of solidification: the terminal temperature
    is then known to within that step), when a point does not converge, at the step or time
    limit, or at the lowest temperature. Every stop is reported with its reason; nothing is
    extrapolated. Pure function of ``run_point``: testable without pycalphad.
    """
    t0 = time.perf_counter()
    comps = sorted(x0)
    x_liq = {c: float(x0[c]) for c in comps}
    f_liq = 1.0
    solid_integral = {c: 0.0 for c in comps}
    phase_amounts: Dict[str, float] = {}
    points: List[Dict[str, Any]] = [{"temperatureC": round(start_c, 2), "fractionSolid": 0.0,
                                     "liquidX": dict(x_liq), "solidX": None, "solidPhases": []}]
    t_c = start_c
    clamped_steps = 0
    first_solid: Optional[Dict[str, Any]] = None
    first_appearance: Dict[str, Dict[str, Any]] = {}
    reason = "step-limit"
    terminal_bracket: Optional[List[float]] = None
    steps = 0
    while steps < max_steps:
        if time.perf_counter() - t0 > time_budget_s:
            reason = "time-budget"
            break
        t_prev = t_c
        t_c = t_prev - step_c
        if t_c < min_temperature_c:
            reason = "temperature-floor"
            break
        cond_x = {}
        clamped = False
        for c in comps:
            val = max(SCHEIL_MIN_MOLE_FRACTION, x_liq[c])
            clamped = clamped or val != x_liq[c]
            cond_x[c] = val
        total = sum(cond_x.values())
        cond_x = {c: val / total for c, val in cond_x.items()}
        clamped_steps += int(clamped)
        res = run_point(t_c, cond_x)
        steps += 1
        if res is None:
            reason = "equilibrium-not-converged"
            terminal_bracket = [round(t_c, 2), round(t_prev, 2)]
            break
        local_liq = float(res["liquid"])
        solids = {k: float(v) for k, v in res["phases"].items() if v > 0.0}
        local_solid = max(0.0, 1.0 - local_liq)
        if local_liq <= 1e-9:
            # The remaining liquid solidified completely inside this step.
            for name, amount in solids.items():
                phase_amounts[name] = phase_amounts.get(name, 0.0) + f_liq * amount
            for c in comps:
                solid_integral[c] += f_liq * cond_x[c]
            points.append({"temperatureC": round(t_c, 2), "fractionSolid": 1.0, "liquidX": None,
                           "solidX": dict(cond_x), "solidPhases": sorted(solids)})
            f_liq = 0.0
            reason = "liquid-exhausted-within-step"
            terminal_bracket = [round(t_c, 2), round(t_prev, 2)]
            break
        new_x_liq = {c: float(res["liquidX"].get(c, 0.0)) for c in comps}
        solid_x = None
        if local_solid > 1e-12:
            solid_x = {c: (cond_x[c] - local_liq * new_x_liq[c]) / local_solid for c in comps}
            for c in comps:
                solid_integral[c] += f_liq * local_solid * solid_x[c]
            for name, amount in solids.items():
                phase_amounts[name] = phase_amounts.get(name, 0.0) + f_liq * amount
            if first_solid is None:
                first_solid = {"temperatureC": round(t_c, 2), "liquidX": dict(cond_x), "solidX": dict(solid_x),
                               "phases": sorted(solids)}
            # first appearance of each solid phase: its composition next to the coexisting liquid
            for name, phase_x in (res.get("phasesX") or {}).items():
                if name not in first_appearance and phase_x:
                    first_appearance[name] = {"temperatureC": round(t_c, 2), "phaseX": dict(phase_x),
                                              "liquidX": dict(new_x_liq)}
        f_liq *= local_liq
        x_liq = new_x_liq
        points.append({"temperatureC": round(t_c, 2), "fractionSolid": round(1.0 - f_liq, 6),
                       "liquidX": dict(x_liq), "solidX": solid_x, "solidPhases": sorted(solids)})
        if f_liq < SCHEIL_LIQUID_STOP:
            reason = "liquid-below-0.1-percent"
            break
    # Mass balance of the path: solid formed + liquid left must give back the alloy composition.
    balance = max(abs(solid_integral[c] + f_liq * (x_liq[c] if f_liq > 0 else 0.0) - x0[c]) for c in comps)
    complete = reason in ("liquid-below-0.1-percent", "liquid-exhausted-within-step")
    return {
        "status": "complete" if complete else "incomplete",
        "terminationReason": reason,
        "terminalTemperatureC": points[-1]["temperatureC"],
        "terminalBracketC": terminal_bracket,
        "remainingLiquidFraction": round(f_liq, 6),
        "steps": steps,
        "stepC": step_c,
        "points": points,
        "phaseAmounts": {k: round(v, 6) for k, v in sorted(phase_amounts.items())},
        "firstSolid": first_solid,
        "firstAppearance": first_appearance,
        "clampedSteps": clamped_steps,
        "massBalanceMaxAbsError": balance,
        "elapsedMs": round((time.perf_counter() - t0) * 1000.0, 2),
    }


def solve_pycalphad_equilibrium(
    alloy_name: str,
    wt_pct: dict,
    at_frac: dict,
    t_min_c: float,
    t_max_c: float,
    t_step_c: float,
    tdb_path: str,
    db_name: str,
    custom_tdb_text: Optional[str] = None,
    adaptive_grid: bool = True,
    boundary_refinement: bool = True,
    min_refine_step_c: float = 0.5,
    db_id: str = "",
    db_status: str = "",
    db_suitability: str = "",
    scheil: bool = True,
    scheil_step_c: float = SCHEIL_DEFAULT_STEP_C,
) -> Dict[str, Any]:
    """
    Gibbs free energy minimisation with pycalphad on a database already chosen by
    resolve_database. Raises CalphadUnavailable when the request cannot be answered
    (database not loadable, element absent from the database, fewer than two components);
    elements are never dropped or renormalised.
    """
    start_time = time.perf_counter()
    timings: Dict[str, float] = {}

    def _lap(name: str, since: float) -> float:
        now = time.perf_counter()
        timings[name] = round((now - since) * 1000.0, 2)
        return now

    dbf, db_cache = load_database_with_info(custom_tdb_text if custom_tdb_text else tdb_path,
                                            is_raw_text=bool(custom_tdb_text))
    if dbf is None:
        raise CalphadUnavailable(KIND_DATABASE_LOAD_FAILED, "pycalphad could not load the thermodynamic database")
    t_mark = _lap("databaseLoad", start_time)

    db_elements = [e.upper() for e in dbf.elements if e.upper() not in ["VA", "/-"]]

    # Every requested element must be in the database. Nothing is dropped and the
    # composition is not renormalised (the former code silently removed e.g. Al from
    # Ti-6Al-4V and renormalised the rest).
    missing = [el for el in at_frac if el.upper() not in db_elements]
    if missing:
        raise CalphadUnavailable(
            KIND_ELEMENTS_MISSING,
            f"element(s) {', '.join(missing)} not in database {db_name!r}; refusing to drop them and renormalise",
            missingElements=missing,
        )
    available_comps = [el.upper() for el in at_frac]
    unsupported_elems: List[str] = []
    if len(available_comps) < 2:
        raise CalphadUnavailable(
            KIND_SINGLE_COMPONENT,
            f"pycalphad equilibrium needs at least two components; got {list(at_frac.keys())}",
        )
    active_at_frac = {el.upper(): float(val) for el, val in at_frac.items()}

    # Dependent component: the base element (largest fraction). The independent components are
    # in alphabetical order so that the condition keys (and with them the cached model key) do
    # not depend on the order of the minor fractions.
    dep_comp = sorted(available_comps, key=lambda c: active_at_frac[c], reverse=True)[0]
    indep_comps = sorted(c for c in available_comps if c != dep_comp)

    # All components for pycalphad (including VA for vacancy sublattice if present in DB)
    all_comps = list(available_comps)
    if "VA" in dbf.elements:
        all_comps.append("VA")

    phases = list(dbf.phases.keys())

    # Build temperature grid
    t_start_k = max(298.15, t_min_c + ZERO_CELSIUS_K)
    t_end_k = min(3000.0, t_max_c + ZERO_CELSIUS_K)
    num_steps = max(5, min(80, int(round((t_end_k - t_start_k) / t_step_c)) + 1))
    temp_grid_k = [round(float(t_start_k + i * (t_end_k - t_start_k) / (num_steps - 1)), 2) for i in range(num_steps)]

    conditions = {
        v.P: 101325.0,
        v.T: temp_grid_k,
    }
    composition_adjustments: Dict[str, Dict[str, float]] = {}
    for comp in indep_comps:
        # Bound fraction to avoid extreme boundary degeneracies (reported, not silent)
        val = max(1e-5, min(0.999, active_at_frac[comp]))
        if val != active_at_frac[comp]:
            composition_adjustments[comp] = {"requestedMoleFraction": active_at_frac[comp], "usedMoleFraction": val}
        conditions[v.X(comp)] = val

    runner = _EquilibriumRunner(dbf, db_cache.get("sha256", ""), all_comps, phases, conditions)
    t_mark = _lap("workspaceBuild", t_mark)
    if runner.lock is not None:
        runner.lock.acquire()
    try:
        result = _solve_with_runner(
            runner, conditions, dep_comp, indep_comps, alloy_name, wt_pct, at_frac, t_min_c, t_max_c, t_step_c,
            tdb_path, db_name, db_id, db_status, db_suitability, boundary_refinement, min_refine_step_c,
            scheil, scheil_step_c, num_steps, available_comps, unsupported_elems, composition_adjustments,
            timings, t_mark)
    finally:
        if runner.lock is not None:
            runner.lock.release()

    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    timings["total"] = elapsed_ms
    result["computeTimeMs"] = elapsed_ms
    result["timingsMs"] = timings
    cache_stats = process_cache().stats()
    workspace_status = runner.cache_info.get("status")
    result["modelCache"] = {
        "status": "warm" if workspace_status == "hit" else ("cold" if workspace_status in ("miss", "disabled") else
                                                            "not-cached"),
        "workspace": workspace_status,
        "database": db_cache.get("status"),
        "databaseSha256": db_cache.get("sha256"),
        "workspaceBuildMs": runner.cache_info.get("buildMs"),
        "originalWorkspaceBuildMs": runner.cache_info.get("originalBuildMs"),
        "note": ("Compiled pycalphad models are cached per worker process and keyed by database content "
                 "(SHA-256), components and phases. 'cold' means this process built them for this request "
                 "(model construction and code generation included in the time); 'warm' means they were reused."),
        **cache_stats,
    }
    return result


def _solve_with_runner(runner, conditions, dep_comp, indep_comps, alloy_name, wt_pct, at_frac, t_min_c, t_max_c,
                       t_step_c, tdb_path, db_name, db_id, db_status, db_suitability, boundary_refinement,
                       min_refine_step_c, scheil, scheil_step_c, num_steps, available_comps, unsupported_elems,
                       composition_adjustments, timings, t_mark) -> Dict[str, Any]:
    eq = runner.run(conditions, as_dataset=runner.workspace is not None)
    t_mark_now = time.perf_counter()
    timings["gridEquilibrium"] = round((t_mark_now - t_mark) * 1000.0, 2)
    t_mark = t_mark_now

    # Extract coordinates and arrays
    t_coords = list(eq.T.values)
    eq_comps = [str(c) for c in eq.component.values]

    equilibrium_profile = []
    not_converged_temps: List[float] = []
    all_phases_observed = set()
    beta_transus_c = None
    sigma_phase_solvus_c = None
    l12_by_name_max_c = None  # highest grid T with a phase NAMED L1_2 (not a verified gamma-prime)

    for i, t_k in enumerate(t_coords):
        t_c = round(t_k - ZERO_CELSIUS_K, 1)

        # Molar Gibbs Free Energy (J/mol)
        gm_j_mol = float(eq.GM.values[0, 0, i, 0, 0]) if len(eq.GM.shape) == 5 else float(eq.GM.values.flat[i])
        gm_kj_mol = round(gm_j_mol / 1000.0, 3)

        # Active phases and fractions
        phs = eq.Phase.values[0, 0, i, 0, 0, :] if len(eq.Phase.shape) == 6 else eq.Phase.values.reshape(len(t_coords), -1)[i]
        nps = eq.NP.values[0, 0, i, 0, 0, :] if len(eq.NP.shape) == 6 else eq.NP.values.reshape(len(t_coords), -1)[i]

        # A point whose equilibrium did not converge (pycalphad returns NaN) is never reported
        # as a state: null values and status "not-converged" (no NaN reaches the JSON).
        rt = GAS_CONSTANT_R * t_k
        try:
            mu_values: Optional[List[float]] = [float(m) for m in eq.MU.values.reshape(len(t_coords), -1)[i]]
        except Exception:
            mu_values = None
        converged = (
            math.isfinite(gm_j_mol)
            and mu_values is not None
            and len(mu_values) == len(eq_comps)
            and all(math.isfinite(m) and abs(m / rt) < 700.0 for m in mu_values)
            and any(bool(np.isfinite(n)) and float(n) > 0.001 for n in nps)
        )
        if not converged:
            not_converged_temps.append(t_c)
            equilibrium_profile.append({
                "temperatureC": t_c,
                "temperatureK": t_k,
                "status": "not-converged",
                "phases": [],
                "totalGibbsEnergy_kJ_mol": None,
                "chemicalPotentials_J_mol": None,
                "thermodynamicActivities": None,
            })
            continue

        step_phases = []
        gamma_prime_frac = 0.0
        hcp_frac = 0.0
        sigma_frac = 0.0

        for vertex_idx, (p_name, np_val) in enumerate(zip(phs, nps)):
            if not p_name or np.isnan(np_val) or float(np_val) <= 0.001:
                continue

            phase_str = str(p_name).strip()
            all_phases_observed.add(phase_str)
            fraction = round(float(np_val), 4)

            if phase_str in ["FCC_L12", "L12_FCC", "GAMMA_PRIME"]:
                gamma_prime_frac += fraction
            if phase_str in ["HCP_A3", "ALPHA_HCP"]:
                hcp_frac += fraction
            if "SIGMA" in phase_str:
                sigma_frac += fraction

            comp_map: Dict[str, float] = {}
            try:
                if hasattr(eq, 'X'):
                    # Access 7D array: (N, P, T, X1, X2, vertex, component)
                    if len(eq.X.shape) == 7:
                        x_arr = eq.X.values[0, 0, i, 0, 0, vertex_idx, :]
                    elif len(eq.X.shape) == 6:
                        x_arr = eq.X.values[0, 0, i, 0, vertex_idx, :]
                    else:
                        x_arr = eq.X.values.reshape(len(t_coords), len(phs), -1)[i, vertex_idx, :]
                    comp_map = {eq_comps[ci]: round(float(x_arr[ci]), 4) for ci in range(len(eq_comps)) if not np.isnan(x_arr[ci])}
            except Exception:
                comp_map = {}

            step_phases.append({
                "phaseId": phase_str,
                "phaseName": _friendly_phase_name(phase_str),
                "fraction": fraction,
                "color": PHASE_COLORS.get(phase_str, "#94a3b8"),
                "isPrimary": phase_str in ["FCC_A1", "BCC_A2", "HCP_A3", "LIQUID"],
                "isPrecipitate": phase_str in ["FCC_L12", "L12_FCC", "MG2SI", "BCC_B2"],
                "isTCP": "SIGMA" in phase_str or "LAVES" in phase_str,
                "compositions": comp_map,
            })

        # Chemical Potentials and Thermodynamic Activities
        activities = {}
        chem_potentials_j_mol = {}
        for c_idx, c_name in enumerate(eq_comps):
            mu_val = mu_values[c_idx]
            chem_potentials_j_mol[c_name] = round(mu_val, 1)
            # a_i = exp(mu_i / RT)
            activities[c_name] = float(math.exp(mu_val / rt))

        # Phase-name based observations; the critical temperatures are assembled
        # after the loop (liquidus / solidus / gamma-prime are checked there).
        if gamma_prime_frac > 0.01:
            l12_by_name_max_c = max(l12_by_name_max_c or 0.0, t_c)
        if hcp_frac > 0.01:
            beta_transus_c = max(beta_transus_c or 0.0, t_c)
        if sigma_frac > 0.005:
            sigma_phase_solvus_c = max(sigma_phase_solvus_c or 0.0, t_c)

        equilibrium_profile.append({
            "temperatureC": t_c,
            "temperatureK": t_k,
            "status": "converged",
            "phases": step_phases,
            "totalGibbsEnergy_kJ_mol": gm_kj_mol,
            "chemicalPotentials_J_mol": chem_potentials_j_mol,
            "thermodynamicActivities": activities
        })

    if not equilibrium_profile or 2 * len(not_converged_temps) > len(equilibrium_profile) \
            or len(not_converged_temps) == len(equilibrium_profile):
        raise CalphadUnavailable(
            KIND_EQUILIBRIUM_FAILED,
            "pycalphad equilibrium failed (non-finite results)",
            nonConvergedPoints=len(not_converged_temps),
            gridPoints=len(equilibrium_profile),
            nonConvergedTemperaturesC=not_converged_temps,
        )

    phacomp = calculate_phacomp(at_frac)
    phacomp_sigma_c = phacomp["tcpSigmaRiskTemperatureC"]

    def point_equilibria(temps_c: List[float], x_indep: Optional[Dict[str, float]] = None
                         ) -> List[Optional[Dict[str, Any]]]:
        """Phase amounts and the liquid composition at each temperature (one pycalphad call).

        ``x_indep`` replaces the independent mole fractions (Scheil steps); the condition keys stay
        those of the grid, so a cached Workspace keeps its compiled functions. None marks a point
        that did not converge (or a failed call): such a point never becomes a value.
        """
        try:
            cond = dict(conditions)
            cond[v.T] = [float(t) + ZERO_CELSIUS_K for t in temps_c]
            if x_indep is not None:
                for comp in indep_comps:
                    cond[v.X(comp)] = float(x_indep[comp])
            eq_r = runner.run(cond)
            n = len(temps_c)
            gm_r, mu_r, ph_r, np_r, x_r = _flat_point_arrays(eq_r, n)
        except Exception as err:  # a failed call leaves the bracket / stops the path, it never invents a value
            sys.stderr.write(f"[pycalphad] point equilibrium failed: {err}\n")
            return [None] * len(temps_c)
        out: List[Optional[Dict[str, Any]]] = []
        for k in range(len(temps_c)):
            if not (math.isfinite(float(gm_r[k])) and bool(np.all(np.isfinite(mu_r[k])))):
                out.append(None)
                continue
            liquid = 0.0
            liquid_vertices = 0
            liquid_x: Dict[str, float] = {}
            solids: Dict[str, float] = {}
            solids_x: Dict[str, Dict[str, float]] = {}
            for j, (name, amount) in enumerate(zip(ph_r[k], np_r[k])):
                if not name or not bool(np.isfinite(amount)) or float(amount) <= 0.0:
                    continue
                name_s = str(name).strip()
                if "LIQUID" in name_s:
                    if float(amount) > 0.001:
                        liquid += float(amount)
                        liquid_vertices += 1
                        if x_r is not None:
                            liquid_x = {eq_comps[ci]: float(x_r[k, j, ci]) for ci in range(len(eq_comps))
                                        if eq_comps[ci] != "VA" and np.isfinite(x_r[k, j, ci])}
                else:
                    solids[name_s] = solids.get(name_s, 0.0) + float(amount)
                    if x_r is not None and name_s not in solids_x:
                        solids_x[name_s] = {eq_comps[ci]: float(x_r[k, j, ci]) for ci in range(len(eq_comps))
                                            if eq_comps[ci] != "VA" and np.isfinite(x_r[k, j, ci])}
            out.append({"liquid": liquid, "liquidVertices": liquid_vertices, "liquidX": liquid_x,
                        "phases": solids, "phasesX": solids_x})
        return out

    def liquid_fraction_at(temps_c: List[float]) -> List[Optional[float]]:
        return [None if p is None else p["liquid"] for p in point_equilibria(temps_c)]

    refinement_tolerance_c = max(0.05, float(min_refine_step_c))
    calls_before = runner.calls
    critical_temperatures, status = derive_critical_temperatures(
        equilibrium_profile, l12_by_name_max_c, beta_transus_c, sigma_phase_solvus_c, phacomp_sigma_c,
        refine=liquid_fraction_at if boundary_refinement else None,
        tolerance_c=refinement_tolerance_c)
    refinement_calls = runner.calls - calls_before
    t_mark_now = time.perf_counter()
    timings["boundaryRefinement"] = round((t_mark_now - t_mark) * 1000.0, 2)
    t_mark = t_mark_now
    liquidus_c = critical_temperatures["liquidusC"]

    # ---------------------------------------------------------------- Scheil-Gulliver path
    scheil_result: Optional[Dict[str, Any]] = None
    scheil_unavailable: Optional[str] = None
    liquidus_status = status.get("liquidusC", {})
    if not scheil:
        scheil_unavailable = "not requested"
    elif liquidus_c is None:
        scheil_unavailable = "the liquidus is not available on this grid, so there is no start temperature"
    elif liquidus_status.get("status") != "bisected":
        scheil_unavailable = "the liquidus was not refined (grid bracket only); the path needs a refined start temperature"
    else:
        # the composition of the grid conditions (including any reported clamp)
        x0 = {c: float(conditions[v.X(c)]) for c in indep_comps}
        x0[dep_comp] = 1.0 - sum(x0.values())

        def run_point(t_c: float, x_liq: Dict[str, float]) -> Optional[Dict[str, Any]]:
            res = point_equilibria([t_c], {c: x_liq[c] for c in indep_comps})[0]
            if res is None or res["liquidVertices"] > 1:
                return None  # non-convergence or a liquid miscibility gap: the path stops here
            if res["liquid"] > 0.0 and not res["liquidX"]:
                return None
            return res

        start_c = float(liquidus_status["bracketC"][1])  # upper end of the bracket: fully liquid
        scheil_result = scheil_gulliver(run_point, start_c, x0, step_c=max(0.25, min(10.0, float(scheil_step_c))),
                                        min_temperature_c=t_start_floor_c(conditions))
    timings["scheil"] = round((time.perf_counter() - t_mark) * 1000.0, 2)
    t_mark = time.perf_counter()

    scheil_points, scheil_block, partitioning_table = _scheil_outputs(
        scheil_result, scheil_unavailable, wt_pct, db_name, available_comps)

    timings["postProcessing"] = round((time.perf_counter() - t_mark) * 1000.0, 2)

    return {
        "success": True,
        "engine": "pycalphad-open-tdb",
        "pycalphadVersion": PYCALPHAD_VERSION,
        "databaseUsed": db_name,
        "databaseId": db_id,
        "databaseStatus": db_status,
        "databaseSuitability": db_suitability,
        "databasePath": tdb_path,
        "thermodynamicModel": "Compound Energy Formalism (CEF) Gibbs minimisation (pycalphad equilibrium)",
        "isEmpirical": False,
        "equilibriumCalls": runner.calls,
        "alloyName": alloy_name,
        "nominalComposition": wt_pct,
        "atomicFractions": at_frac,
        "activeComponents": available_comps,
        "dependentComponent": dep_comp,
        "unsupportedElements": unsupported_elems,
        "compositionAdjustments": composition_adjustments,
        "temperatureRangeC": [t_min_c, t_max_c],
        "temperatureStepC": t_step_c,
        "gridPoints": num_steps,
        "equilibriumProfile": equilibrium_profile,
        "criticalTemperatures": critical_temperatures,
        "criticalTemperatureStatus": status,
        "phacompAnalysis": phacomp,
        "solutePartitioning": partitioning_table,
        "multiElementScheil": scheil_points,
        "multiElementScheilStatus": scheil_block["status"],
        "multiElementScheilNote": scheil_block["note"],
        "scheilSolidification": scheil_block,
        "thermodynamicStabilityIndex": phacomp["thermodynamicStabilityIndex"],
        "tcpEmbrittlementRisk": phacomp["tcpEmbrittlementRisk"],
        "nonConvergedPoints": not_converged_temps,
        "boundaryRefinement": {
            "enabled": bool(boundary_refinement),
            "toleranceC": refinement_tolerance_c,
            "equilibriumCalls": refinement_calls,
            "note": ("Liquidus and solidus are refined between the bracketing grid points by repeated "
                     "multi-section equilibrium calculations; there is no adaptive grid."),
        },
    }


def t_start_floor_c(conditions: Dict[Any, Any]) -> float:
    """Lowest temperature (degC) a Scheil path may reach: the bottom of the requested grid."""
    temps = conditions[v.T]
    return min(float(t) for t in temps) - ZERO_CELSIUS_K


def _mole_to_wt_pct(x: Dict[str, float]) -> Dict[str, float]:
    masses = {c: x[c] * _atomic_weight(c.capitalize()) for c in x if c != "VA"}
    total = sum(masses.values())
    if total <= 0:
        return {}
    return {c.capitalize(): round(100.0 * m / total, 3) for c, m in masses.items()}


SCHEIL_STATUS_COMPUTED = "pycalphad-scheil-gulliver"
SCHEIL_STATUS_UNAVAILABLE = "unavailable"


def _scheil_outputs(scheil_result: Optional[Dict[str, Any]], unavailable_reason: Optional[str],
                    wt_pct: Dict[str, float], db_name: str, comps: List[str]
                    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    """Chart points, the scheilSolidification block and the liquidus partition table."""
    validity = ("Scheil-Gulliver limit: no diffusion in the solid, complete mixing in the liquid, local "
                "equilibrium at the interface, no undercooling. Real solidification lies between this path and "
                "equilibrium (lever rule); back-diffusion of fast interstitials (C, N) is ignored. "
                f"Thermodynamics from {db_name}; not validated against experiment in this application.")
    if scheil_result is None:
        block = {
            "status": SCHEIL_STATUS_UNAVAILABLE,
            "reason": unavailable_reason,
            "note": f"Scheil-Gulliver path unavailable: {unavailable_reason}.",
            "validity": validity,
            "evidence": "unvalidated",
        }
        rows = [{"element": c, "partitionCoefficient_k": None, "partitionCoefficientSource": "unavailable",
                 "reason": "needs the Scheil-Gulliver path", "temperatureC": None,
                 "primarySolidPhase": None, "role": None}
                for c in comps]
        return [], block, rows

    points = []
    for p in scheil_result["points"]:
        points.append({
            "fractionSolid": round(p["fractionSolid"], 4),
            "temperatureC": p["temperatureC"],
            "liquidCompositions": _mole_to_wt_pct(p["liquidX"]) if p["liquidX"] else None,
            "solidCompositions": _mole_to_wt_pct(p["solidX"]) if p["solidX"] else None,
            "solidPhases": p["solidPhases"],
        })
    # Partition coefficient k = x(phase) / x(liquid) of the majority solid phase of the path, at its
    # first appearance (equilibrium tie-line between that phase and the liquid it forms from).
    amounts = scheil_result["phaseAmounts"]
    primary = max(amounts, key=lambda name: amounts[name]) if amounts else None
    tie = scheil_result.get("firstAppearance", {}).get(primary) if primary else None
    rows = []
    for c in comps:
        k = None
        if tie is not None and tie["liquidX"].get(c, 0.0) > 1e-9 and c in tie["phaseX"]:
            k = tie["phaseX"][c] / tie["liquidX"][c]
        if k is None:
            role = None
        elif k < 0.95:
            role = "Rejected into the liquid (k < 1): enriches the last liquid / interdendritic regions"
        elif k > 1.05:
            role = "Enriched in the primary solid (k > 1): depleted in the last liquid"
        else:
            role = "Little partitioning (k close to 1)"
        rows.append({
            "element": c,
            "partitionCoefficient_k": round(k, 4) if k is not None else None,
            "partitionCoefficientSource": "scheil-primary-phase-tie-line" if k is not None else "unavailable",
            "reason": None if k is not None else "no tie-line between the primary solid and the liquid on the path",
            "temperatureC": tie["temperatureC"] if tie else None,
            "primarySolidPhase": primary,
            "role": role,
        })
    complete = scheil_result["status"] == "complete"
    reason_text = {
        "liquid-below-0.1-percent": "the remaining liquid fell below 0.1 %",
        "liquid-exhausted-within-step": "the remaining liquid solidified within the last temperature step "
                                        "(invariant reaction; temperature known to within one step)",
        "equilibrium-not-converged": "an equilibrium on the path did not converge or showed a liquid miscibility gap",
        "time-budget": "the time budget was reached",
        "step-limit": "the step limit was reached",
        "temperature-floor": "the bottom of the requested temperature range was reached",
    }
    termination = scheil_result["terminationReason"]
    reason_text = reason_text.get(termination, termination)
    block = {
        "status": SCHEIL_STATUS_COMPUTED if complete else "incomplete",
        "reason": None if complete else f"the path stopped early: {reason_text}",
        "note": ("Scheil-Gulliver solidification path computed step by step with pycalphad equilibria of the "
                 "remaining liquid; fractions are mole fractions of atoms. Stopped because " + reason_text + "."),
        "method": "stepwise Scheil-Gulliver with pycalphad equilibrium (removed solid, mixed liquid)",
        "fractionBasis": "mole fraction of atoms",
        "terminationReason": scheil_result["terminationReason"],
        "startTemperatureC": scheil_result["points"][0]["temperatureC"],
        "terminalTemperatureC": scheil_result["terminalTemperatureC"],
        "terminalBracketC": scheil_result["terminalBracketC"],
        "remainingLiquidFraction": scheil_result["remainingLiquidFraction"],
        "stepC": scheil_result["stepC"],
        "steps": scheil_result["steps"],
        "phaseAmounts": scheil_result["phaseAmounts"],
        "clampedSteps": scheil_result["clampedSteps"],
        "massBalanceMaxAbsError": scheil_result["massBalanceMaxAbsError"],
        "validity": validity,
        "evidence": "unvalidated",
        "elapsedMs": scheil_result["elapsedMs"],
    }
    return points, block, rows


def compute_multi_component_equilibrium(
    name: str,
    elements: dict,
    unit: str = "wt_pct",
    t_min_c: float = 500.0,
    t_max_c: float = 1450.0,
    t_step_c: float = 20.0,
    database_id: Optional[str] = None,
    custom_tdb_text: Optional[str] = None,
    adaptive_grid: bool = True,
    boundary_refinement: bool = True,
    min_refine_step_c: float = 0.5,
    scheil: bool = True,
    scheil_step_c: float = SCHEIL_DEFAULT_STEP_C,
) -> Dict[str, Any]:
    """
    Main entry point. Resolves the database, then runs the pycalphad Gibbs minimisation.

    There is no fallback model: every condition that stops a real CALPHAD result
    (database refused or incomplete, pycalphad missing or failing) returns the
    unavailable envelope (see unavailable_result) with a reason.
    """
    wt_pct, at_frac = normalize_composition(elements, unit)
    requested = list(at_frac.keys())
    base = dict(name=name, wt_pct=wt_pct, at_frac=at_frac,
                t_min_c=t_min_c, t_max_c=t_max_c, t_step_c=t_step_c)

    resolved = resolve_database(requested, database_id, custom_tdb_text, base_element(at_frac))
    if not resolved["ok"]:
        reasons = [resolved["reason"]]
        if not PYCALPHAD_AVAILABLE:
            reasons.append(UNAVAILABLE_REASON_PYCALPHAD)
        return unavailable_result(resolved["kind"], resolved["reason"], reasons=reasons,
                                  **base, **resolved["extra"])

    db_extra = {"databaseId": resolved["id"], "databaseUsed": resolved["name"],
                "databaseStatus": resolved["status"], "databaseSuitability": resolved["suitability"]}
    if not PYCALPHAD_AVAILABLE:
        return unavailable_result(KIND_PYCALPHAD_MISSING, UNAVAILABLE_REASON_PYCALPHAD, **base, **db_extra)

    try:
        return solve_pycalphad_equilibrium(
            alloy_name=name,
            wt_pct=wt_pct,
            at_frac=at_frac,
            t_min_c=t_min_c,
            t_max_c=t_max_c,
            t_step_c=t_step_c,
            tdb_path=resolved["path"],
            db_name=resolved["name"],
            custom_tdb_text=custom_tdb_text,
            adaptive_grid=adaptive_grid,
            boundary_refinement=boundary_refinement,
            min_refine_step_c=min_refine_step_c,
            db_id=resolved["id"],
            db_status=resolved["status"],
            db_suitability=resolved["suitability"],
            scheil=scheil,
            scheil_step_c=scheil_step_c,
        )
    except CalphadUnavailable as exc:
        return unavailable_result(exc.kind, exc.reason, **base, **db_extra, **exc.extra)
    except Exception as err:
        sys.stderr.write(f"[pycalphad] equilibrium failed: {err}\n")
        return unavailable_result(KIND_EQUILIBRIUM_FAILED, f"pycalphad equilibrium failed: {err}",
                                  **base, **db_extra)


def serialize_result(result: Dict[str, Any]) -> str:
    """JSON text of a result; NaN/Infinity are never emitted (they are not JSON and the
    server's JSON.parse would fail). A result that still holds a non-finite number is
    replaced by an explicit unavailable envelope."""
    try:
        return json.dumps(result, allow_nan=False)
    except ValueError as err:
        sys.stderr.write(f"[calphad] result held a non-finite number: {err}\n")
        return json.dumps({
            "success": False,
            "status": "unavailable",
            "unavailableKind": KIND_NON_FINITE_OUTPUT,
            "reason": "pycalphad equilibrium failed (non-finite results)",
            "reasons": ["pycalphad equilibrium failed (non-finite results)"],
            "engine": "pycalphad-open-tdb",
            "alloyName": result.get("alloyName"),
            "provenance": result.get("provenance"),
        }, allow_nan=False)


def main():
    """CLI and JSON pipe entrypoint for Python process / IPC daemon."""
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--status":
            print(json.dumps(list_available_databases()))
            return

        if len(sys.argv) > 1 and sys.argv[1] != "-":
            raw_input = sys.argv[1]
        else:
            raw_input = sys.stdin.read()

        if not raw_input.strip():
            # Standard verification run: Ni-base superalloy
            payload = {
                "name": "Inconel 718 Benchmark",
                "elements": {"Ni": 53.0, "Cr": 19.0, "Fe": 18.0, "Nb": 5.0, "Mo": 3.0, "Ti": 1.0, "Al": 1.0},
                "unit": "wt_pct",
                "tMin": 500.0,
                "tMax": 1450.0,
                "tStep": 25.0,
                "adaptiveGrid": True,
                "boundaryRefinement": True,
                "minRefineStep": 0.5
            }
        else:
            payload = json.loads(raw_input)

        action = payload.get("action")
        if action == "list_databases":
            print(json.dumps(list_available_databases()))
            return

        name = payload.get("name", "Multi-Component Alloy")
        elements = payload.get("elements", {"Ni": 75, "Al": 10, "Cr": 15})
        unit = payload.get("unit", "wt_pct")
        t_min = float(payload.get("tMin", 500.0))
        t_max = float(payload.get("tMax", 1450.0))
        t_step = float(payload.get("tStep", 25.0))
        db_id = payload.get("databaseId") or payload.get("database") or payload.get("databaseName")
        custom_tdb = payload.get("customTdbText")
        adaptive_grid = bool(payload.get("adaptiveGrid", True))
        boundary_refinement = bool(payload.get("boundaryRefinement", True))
        min_refine_step = float(payload.get("minRefineStep", 0.5))
        scheil = bool(payload.get("scheil", True))
        scheil_step = float(payload.get("scheilStepC", SCHEIL_DEFAULT_STEP_C))

        result = compute_multi_component_equilibrium(
            name=name,
            elements=elements,
            unit=unit,
            t_min_c=t_min,
            t_max_c=t_max,
            t_step_c=t_step,
            database_id=db_id,
            custom_tdb_text=custom_tdb,
            adaptive_grid=adaptive_grid,
            boundary_refinement=boundary_refinement,
            min_refine_step_c=min_refine_step,
            scheil=scheil,
            scheil_step_c=scheil_step,
        )
        # Phase 6a provenance (constants version, the R actually used, domain data)
        result["provenance"] = {
            "constantsVersion": physical_constants.CONSTANTS_VERSION,
            "gasConstantR_J_molK": GAS_CONSTANT_R,
            "atomicWeightsSource": physical_constants.CIAAW_SOURCE,
            **_domain_data_provenance(),
            "constantsNote": "Exact SI 2019 R = N_A*k (Phase 6a value step); it replaced the "
                             "CODATA printed truncation 8.314462618. Atomic weights: CIAAW 2021 "
                             "abridged for every element; unknown symbols are refused.",
        }
        print(serialize_result(result))

    except ValidationError as e:
        # Phase 6a envelope: invalid input, not a solver failure (HTTP 422 in the bridge).
        print(json.dumps(validation_envelope(e)))
        sys.exit(2)
    except Exception as e:
        sys.stderr.write(f"CALPHAD Python Error: {str(e)}\n")
        print(json.dumps({
            "success": False,
            "error": str(e),
            "engine": "pycalphad-open-tdb",
            "errorKind": "internal",
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()

