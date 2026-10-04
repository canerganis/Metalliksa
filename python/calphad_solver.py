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
 4. New-PHACOMP Nv / Md screening (tabulated values; unlisted elements use 1.0).

Post-processing that is NOT a calculated CALPHAD result is flagged, not hidden
(see criticalTemperatureStatus, solutePartitioning[].partitionCoefficientSource and
multiElementScheilStatus in the output):
 - liquidus: first grid temperature with liquid >= 98 % (grid resolution only);
 - solidus: only when the grid hit a trace-liquid point; unavailable when the
   solver reached the grid bound (the former value was the lowest grid temperature);
 - gamma-prime solvus: unavailable, the L1_2 model phase also describes the
   disordered gamma and no site-fraction ordering check exists;
 - the Scheil-style curve and the default partition coefficients are screening
   numbers, not thermodynamic results.

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
from input_validation import UNKNOWN_ELEMENT, ValidationError, validation_envelope

# Phase 6a value step (b): R is the exact SI 2019 product N_A*k from
# physical_constants (it replaced the CODATA printed truncation 8.314462618;
# relative change 1.8e-11).
GAS_CONSTANT_R = physical_constants.GAS_CONSTANT_R.value  # J / (mol*K), exact
ZERO_CELSIUS_K = physical_constants.ZERO_CELSIUS_K.value  # 273.15 K

# Directory containing open-source TDB databases
DATABASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "databases")

# Global in-memory cache for loaded pycalphad Database objects
_TDB_CACHE: Dict[str, Any] = {}

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


def list_available_databases() -> Dict[str, Any]:
    """Returns the list of available Open TDB databases and engine capabilities."""
    installed_files = []
    if os.path.exists(DATABASES_DIR):
        installed_files = [os.path.basename(p) for p in glob.glob(os.path.join(DATABASES_DIR, "*.tdb"))]

    return {
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


def load_pycalphad_database(tdb_path_or_text: str, is_raw_text: bool = False) -> Any:
    """Loads and caches a pycalphad Database instance in memory."""
    if not PYCALPHAD_AVAILABLE:
        return None

    cache_key = "custom_tdb" if is_raw_text else tdb_path_or_text
    if cache_key in _TDB_CACHE and not is_raw_text:
        return _TDB_CACHE[cache_key]

    try:
        if is_raw_text:
            dbf = Database(tdb_path_or_text)
        else:
            dbf = Database(tdb_path_or_text)
        if not is_raw_text:
            _TDB_CACHE[cache_key] = dbf
        return dbf
    except Exception as e:
        sys.stderr.write(f"[CALPHAD] Error loading TDB: {e}\n")
        return None


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
    db_suitability: str = ""
) -> Dict[str, Any]:
    """
    Gibbs free energy minimisation with pycalphad on a database already chosen by
    resolve_database. Raises CalphadUnavailable when the request cannot be answered
    (database not loadable, element absent from the database, fewer than two components);
    elements are never dropped or renormalised.
    """
    start_time = time.perf_counter()

    dbf = load_pycalphad_database(custom_tdb_text if custom_tdb_text else tdb_path, is_raw_text=bool(custom_tdb_text))
    if dbf is None:
        raise CalphadUnavailable(KIND_DATABASE_LOAD_FAILED, "pycalphad could not load the thermodynamic database")

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

    # Reference dependent component (usually base element with highest fraction)
    sorted_comps = sorted(available_comps, key=lambda c: active_at_frac[c], reverse=True)
    dep_comp = sorted_comps[0]
    indep_comps = sorted_comps[1:]

    # All components for pycalphad (including VA for vacancy sublattice if present in DB)
    all_comps = list(available_comps)
    if "VA" in dbf.elements:
        all_comps.append("VA")

    # Filter all phases in the database
    phases = list(dbf.phases.keys())

    # Build temperature grid
    t_start_k = max(298.15, t_min_c + ZERO_CELSIUS_K)
    t_end_k = min(3000.0, t_max_c + ZERO_CELSIUS_K)
    num_steps = max(5, min(80, int(round((t_end_k - t_start_k) / t_step_c)) + 1))
    temp_grid_k = [round(float(t_start_k + i * (t_end_k - t_start_k) / (num_steps - 1)), 2) for i in range(num_steps)]

    # Setup conditions
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

    # Execute pycalphad equilibrium. A Workspace is what equilibrium() builds internally; keeping it
    # lets the boundary refinement re-evaluate single temperatures without rebuilding the
    # models (about 7 s for COST 507 against 0.3 s per call).
    try:
        from pycalphad import Workspace
        workspace: Any = Workspace(dbf, all_comps, phases, conditions)
        eq = workspace.eq.get_dataset()
    except ImportError:  # older pycalphad: plain equilibrium(), refinement then rebuilds per call
        workspace = None
        eq = equilibrium(dbf, all_comps, phases, conditions)

    # Extract coordinates and arrays
    t_coords = list(eq.T.values)
    eq_comps = [str(c) for c in eq.component.values]
    
    equilibrium_profile = []
    not_converged_temps: List[float] = []
    all_phases_observed = set()
    beta_transus_c = None
    sigma_phase_solvus_c = None
    l12_by_name_max_c = None  # highest grid T with a phase NAMED L1_2 (not a verified gamma-prime)

    # Track tie-line partition coefficients from two-phase regions
    tie_line_partitioning = {c: [] for c in eq_comps}

    # Color mapping for phases
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

    for i, t_k in enumerate(t_coords):
        t_c = round(t_k - ZERO_CELSIUS_K, 1)

        # Molar Gibbs Free Energy (J/mol)
        gm_j_mol = float(eq.GM.values[0, 0, i, 0, 0]) if len(eq.GM.shape) == 5 else float(eq.GM.values.flat[i])
        gm_kj_mol = round(gm_j_mol / 1000.0, 3)

        # Active phases and fractions
        phs = eq.Phase.values[0, 0, i, 0, 0, :] if len(eq.Phase.shape) == 6 else eq.Phase.values.squeeze()[i]
        nps = eq.NP.values[0, 0, i, 0, 0, :] if len(eq.NP.shape) == 6 else eq.NP.values.squeeze()[i]

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
        liq_fraction = 0.0
        gamma_prime_frac = 0.0
        hcp_frac = 0.0
        sigma_frac = 0.0

        # Phase compositions for tie-line partitioning
        phase_compositions: Dict[str, Dict[str, float]] = {}

        for vertex_idx, (p_name, np_val) in enumerate(zip(phs, nps)):
            if not p_name or np.isnan(np_val) or float(np_val) <= 0.001:
                continue

            phase_str = str(p_name).strip()
            all_phases_observed.add(phase_str)
            fraction = round(float(np_val), 4)

            if "LIQUID" in phase_str:
                liq_fraction += fraction
            if phase_str in ["FCC_L12", "L12_FCC", "GAMMA_PRIME"]:
                gamma_prime_frac += fraction
            if phase_str in ["HCP_A3", "ALPHA_HCP"]:
                hcp_frac += fraction
            if "SIGMA" in phase_str:
                sigma_frac += fraction

            # Extract composition of this phase if available
            try:
                if hasattr(eq, 'X'):
                    # Access 7D array: (N, P, T, X1, X2, vertex, component)
                    if len(eq.X.shape) == 7:
                        x_arr = eq.X.values[0, 0, i, 0, 0, vertex_idx, :]
                    elif len(eq.X.shape) == 6:
                        x_arr = eq.X.values[0, 0, i, 0, vertex_idx, :]
                    else:
                        x_arr = eq.X.values.squeeze()[i, vertex_idx, :]
                    comp_map = {eq_comps[ci]: round(float(x_arr[ci]), 4) for ci in range(len(eq_comps)) if not np.isnan(x_arr[ci])}
                    phase_compositions[phase_str] = comp_map
            except Exception:
                pass

            # Friendly human readable phase name
            friendly_name = phase_str
            if phase_str in ["FCC_A1", "GAMMA"]:
                friendly_name = "γ-Matrix (FCC_A1 solid solution)"
            elif phase_str in ["FCC_L12", "L12_FCC"]:
                friendly_name = "L1_2 phase (γ' only if ordered; ordering not verified)"
            elif phase_str in ["BCC_A2"]:
                friendly_name = "α-Ferrite / β-Titanium (BCC_A2)"
            elif phase_str in ["BCC_B2"]:
                friendly_name = "B2 Superlattice Intermetallic (BCC_B2)"
            elif phase_str in ["HCP_A3"]:
                friendly_name = "α-Phase / HCP Matrix (HCP_A3)"
            elif "SIGMA" in phase_str:
                friendly_name = "TCP σ (Sigma) Embrittling Phase"
            elif phase_str == "LIQUID":
                friendly_name = "Liquid Phase"
            elif phase_str == "MG2SI":
                friendly_name = "Mg2Si Hardening Precipitate"

            color = PHASE_COLORS.get(phase_str, "#94a3b8")

            step_phases.append({
                "phaseId": phase_str,
                "phaseName": friendly_name,
                "fraction": fraction,
                "color": color,
                "isPrimary": phase_str in ["FCC_A1", "BCC_A2", "HCP_A3", "LIQUID"],
                "isPrecipitate": phase_str in ["FCC_L12", "L12_FCC", "MG2SI", "BCC_B2"],
                "isTCP": "SIGMA" in phase_str or "LAVES" in phase_str,
                "compositions": phase_compositions.get(phase_str, {})
            })

        # Calculate tie-line partitioning coefficients if two key phases coexist
        # (e.g., L12 vs FCC_A1, or Solid vs Liquid in mushy zone)
        ppt_phase = "L12_FCC" if "L12_FCC" in phase_compositions else ("FCC_L12" if "FCC_L12" in phase_compositions else None)
        mat_phase = "FCC_A1" if "FCC_A1" in phase_compositions else ("BCC_A2" if "BCC_A2" in phase_compositions else None)
        liq_phase = "LIQUID" if "LIQUID" in phase_compositions else None

        if ppt_phase and mat_phase:
            for c in eq_comps:
                x_ppt = phase_compositions[ppt_phase].get(c, 0.0)
                x_mat = phase_compositions[mat_phase].get(c, 0.0)
                if x_mat > 0.001 and x_ppt > 0.0001:
                    tie_line_partitioning[c].append(x_ppt / x_mat)
        elif mat_phase and liq_phase:
            # Solid-liquid partitioning
            for c in eq_comps:
                x_sol = phase_compositions[mat_phase].get(c, 0.0)
                x_liq = phase_compositions[liq_phase].get(c, 0.0)
                if x_liq > 0.001 and x_sol > 0.0001:
                    tie_line_partitioning[c].append(x_sol / x_liq)

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

    def liquid_fraction_at(temps_c: List[float]) -> List[Optional[float]]:
        """Liquid fraction at each temperature (one pycalphad call); None where it did not converge."""
        try:
            cond = dict(conditions)
            cond[v.T] = [float(t) + ZERO_CELSIUS_K for t in temps_c]
            if workspace is not None:
                workspace.conditions = cond
                eq_r = workspace.eq
            else:
                eq_r = equilibrium(dbf, all_comps, phases, cond)
            n = len(temps_c)

            def _flat(x: Any) -> Any:
                return np.asarray(getattr(x, "values", x)).reshape(n, -1)

            gm_r = _flat(eq_r.GM)[:, 0]
            mu_r = _flat(eq_r.MU)
            ph_r = _flat(eq_r.Phase)
            np_r = _flat(eq_r.NP)
        except Exception as err:  # a failed refinement leaves the grid bracket, it never invents a value
            sys.stderr.write(f"[pycalphad] boundary refinement failed: {err}\n")
            return [None] * len(temps_c)
        out: List[Optional[float]] = []
        for k in range(len(temps_c)):
            if not (math.isfinite(float(gm_r[k])) and bool(np.all(np.isfinite(mu_r[k])))):
                out.append(None)
                continue
            out.append(sum(float(x) for name, x in zip(ph_r[k], np_r[k])
                           if name and "LIQUID" in str(name) and bool(np.isfinite(x)) and float(x) > 0.001))
        return out

    refinement_tolerance_c = max(0.05, float(min_refine_step_c))
    critical_temperatures, status = derive_critical_temperatures(
        equilibrium_profile, l12_by_name_max_c, beta_transus_c, sigma_phase_solvus_c, phacomp_sigma_c,
        refine=liquid_fraction_at if boundary_refinement else None,
        tolerance_c=refinement_tolerance_c)
    liquidus_c = critical_temperatures["liquidusC"]
    solidus_c = critical_temperatures["solidusC"]

    # Calculate average partition coefficients from tie-lines
    partitioning_table = []
    for c in eq_comps:
        k_vals = tie_line_partitioning.get(c, [])
        # Find nominal wt% case-insensitively
        elem_wt = next((wt_pct[k] for k in wt_pct if k.upper() == c.upper()), 0.0)

        if k_vals:
            k_avg = float(np.mean(k_vals))
            k_source = "tie-line"
        else:
            # Screening default (not thermodynamic): used when no two-phase tie-line exists
            k_source = "default-table-not-thermodynamic"
            if c in ["AL", "TI", "TA"]:
                k_avg = 3.2
            elif c in ["NB", "V"]:
                k_avg = 2.8
            elif c in ["CR", "CO", "FE"]:
                k_avg = 0.55
            elif c in ["MO", "W"]:
                k_avg = 0.72
            else:
                k_avg = 1.0

        # Determine metallurgical role based on thermodynamics
        if k_avg > 1.3:
            role = "Precipitate / Gamma'-Forming Partitioning Element"
        elif k_avg < 0.8:
            role = "Matrix / Gamma-Partitioning Element"
        else:
            role = "Neutral / Solid-Solution Element"

        # Material balance: X_tot = f_mat * X_mat + f_ppt * X_ppt, with an ASSUMED f_ppt
        f_ppt_est = 0.30
        c_mat = elem_wt / ((1.0 - f_ppt_est) + f_ppt_est * k_avg) if (1.0 - f_ppt_est + f_ppt_est * k_avg) > 0 else elem_wt
        c_ppt = k_avg * c_mat

        partitioning_table.append({
            "element": c,
            "partitionCoefficient_k": round(k_avg, 3),
            "partitionCoefficientSource": k_source,
            "assumedPrecipitateFraction": f_ppt_est,
            "matrixFraction_pct": round(c_mat, 2),
            "precipitateFraction_pct": round(c_ppt, 2),
            "role": role,
            "source": (f"Mean of tie-line composition ratios from pycalphad equilibria in {db_name}; "
                       f"matrix/precipitate wt% use an assumed precipitate fraction of {f_ppt_est}"
                       if k_source == "tie-line" else
                       "Default screening value (no tie-line in this calculation); NOT a CALPHAD result; "
                       f"matrix/precipitate wt% use an assumed precipitate fraction of {f_ppt_est}")
        })

    # Scheil-style segregation curve from the k values. NOT a Scheil-Gulliver calculation:
    # the temperature axis is an ad hoc power law between liquidus and solidus, and it is
    # left null when either critical temperature is unavailable.
    scheil_points = []
    k_dict = {row["element"]: row["partitionCoefficient_k"] for row in partitioning_table}
    curve_available = liquidus_c is not None and solidus_c is not None

    for step in range(21):
        fs = step * 0.048  # 0.0 to ~0.96
        t_scheil: Optional[float] = None
        if curve_available:
            delta_t = max(15.0, liquidus_c - solidus_c)
            t_scheil = liquidus_c - delta_t * (math.pow(max(0.005, 1.0 - fs), -0.28) - 1.0)
            t_scheil = max(solidus_c - 140.0, min(liquidus_c, t_scheil))

        liq_comp = {}
        sol_comp = {}
        for elem, c0 in wt_pct.items():
            k_part = k_dict.get(elem.upper(), 0.85 if elem in ["Nb", "Mo", "Ti", "C"] else 0.98)
            cl = c0 * math.pow(max(0.02, 1.0 - fs), k_part - 1.0)
            cs = k_part * cl
            liq_comp[elem] = round(cl, 2)
            sol_comp[elem] = round(cs, 2)

        scheil_points.append({
            "fractionSolid": round(fs, 3),
            "temperatureC": round(t_scheil, 1) if t_scheil is not None else None,
            "liquidCompositions": liq_comp,
            "solidCompositions": sol_comp
        })

    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

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
        "computeTimeMs": elapsed_ms,
        "iterations": num_steps * len(phases),
        "alloyName": alloy_name,
        "nominalComposition": wt_pct,
        "atomicFractions": at_frac,
        "activeComponents": available_comps,
        "unsupportedElements": unsupported_elems,
        "compositionAdjustments": composition_adjustments,
        "temperatureRangeC": [t_min_c, t_max_c],
        "temperatureStepC": t_step_c,
        "equilibriumProfile": equilibrium_profile,
        "criticalTemperatures": critical_temperatures,
        "criticalTemperatureStatus": status,
        "phacompAnalysis": phacomp,
        "solutePartitioning": partitioning_table,
        "multiElementScheil": scheil_points,
        "multiElementScheilStatus": "screening-curve-not-thermodynamic",
        "multiElementScheilNote": ("Compositions follow the Scheil equation C_L = C0 (1 - fs)^(k - 1) with the k values "
                                   "above; the temperature axis is an ad hoc curve between liquidus and solidus, "
                                   "not a Scheil-Gulliver calculation, and is null when either is unavailable."),
        "thermodynamicStabilityIndex": phacomp["thermodynamicStabilityIndex"],
        "tcpEmbrittlementRisk": phacomp["tcpEmbrittlementRisk"],
        "nonConvergedPoints": not_converged_temps,
        "boundaryRefinement": {
            "enabled": bool(boundary_refinement),
            "toleranceC": refinement_tolerance_c,
            "equilibriumCalls": sum(status[k].get("refinementRounds", 0) for k in ("liquidusC", "solidusC")),
            "note": ("Liquidus and solidus are refined between the bracketing grid points by repeated "
                     "multi-section equilibrium calculations; there is no adaptive grid."),
        },
    }


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
    min_refine_step_c: float = 0.5
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
            min_refine_step_c=min_refine_step
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

