"""Pre-registered configuration of LPBF melt-pool calibration v2 (frozen BEFORE the first v2 run).

v2 is a NEW calibration version; v1 (``lpbf_calibration_config.CALIBRATION_CONFIG``, its artefact
``data/calibration/lpbf-meltpool-calibration-v1.json`` and the 2026-10-07 scorecard) is untouched and still verifies.

What v2 adds, decided before any v2 number was computed (see docs/LPBF_CALIBRATION_V2_PREREGISTRATION_2026-10-07.md):

* Two wave-5 literature melt-pool sources (``lpbf_literature_datasets``) join the leave-one-source-out protocol as
  TEST-ONLY held-out sources. They are never in any fit, rung selection, interval (``s_source``) or final fit:
  - ``ghosh-in625-2018`` (7 IN625 bare-plate tracks; width/depth printed in Fig. 1). The experimental spot size is
    NOT stated: 140 um (the paper's FE-model input) is an assumption, carried as a declared nuisance with the
    alternative reading 100 um (Lane 2020 D4sigma of the same laboratory's EOS M270). The gate decision must be
    identical under both readings, else the cell is ``rejected: unresolved input`` (same rule as the KU beam).
  - ``trapp-316l-2017`` (316L bare-disc tracks at 500 mm/s, DIGITIZED from Fig. 3(a); 0.5 mm discs, not a
    semi-infinite plate). The one row without a plotted depth is excluded (both quantities), reported.
* A test-only source is scored with exactly what the alloy's cell would serve: the FINAL fit and served rung on all
  trainable sources of the alloy, and the final cell's interval. It enters the gate as one more held-out source
  (it can only block ``enabled``, with the unchanged v1 thresholds). It may stand in for the missing second source
  of a single-source alloy only if it is NOT digitized, has NO assumed spot size, and has at least
  ``gate.minRowsForCoverage`` rows (below that the coverage criterion of the gate cannot be evaluated).
* Absorptivity references (Trapp 2017 calorimetric, Ye 2019 minimal absorptivity Am; Rubenchik 2015 powder as
  context) are an EXTERNAL SANITY ENVELOPE on fitted effective absorptivity per alloy: fits outside are flagged as a
  diagnostic. They are never a training target, never a prior centre, and never enter the gate.

Every grid, bound, prior, rung, bootstrap size, interval level and gate threshold is copied verbatim from v1
(test_lpbf_calibration_v2_config.py asserts it), so the meaning of the gate is unchanged. The runtime layer
(``lpbf_calibration_layer``) only accepts the v1 config hash, so no v2 artefact can reach calibrated mode.

Evidence label: everything stays ``screening-only``; nothing here derives or promotes a label.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from lpbf_calibration_config import CALIBRATION_CONFIG as CONFIG_V1
from lpbf_calibration_config import CATALOG_SOURCES, KERNELS, TRAINABLE_SOURCES, canonical_json, config_sha256

CONFIG_VERSION_V2 = "lpbf-meltpool-calibration-config-2"
CALIBRATION_SCHEMA_V2 = "lpbf-meltpool-calibration-2"
SCORECARD_SCHEMA_V2 = "lpbf-calibration-scorecard-2"
ARTEFACT_V2_REL_PATH = "data/calibration/lpbf-meltpool-calibration-v2.json"
SCORECARD_V2_STEM = "LPBF_CALIBRATION_SCORECARD_v2_"
PREREGISTRATION_DOC = "docs/LPBF_CALIBRATION_V2_PREREGISTRATION_2026-10-07.md"

TRAINABLE_SOURCES_V2 = tuple(TRAINABLE_SOURCES)  # unchanged: no new source trains in v2
TEST_ONLY_SOURCES = ("ghosh-in625-2018", "trapp-316l-2017")
GHOSH_SPOT_READINGS_UM = (140.0, 100.0)  # first = primary (loader default, the paper's FE-model input)

TEST_ONLY_ROLES: Dict[str, Dict[str, Any]] = {
    "ghosh-in625-2018": {
        "material": "Inconel 625", "role": "test-only (held out, never trained)",
        "digitized": False, "spotAssumed": True, "rowsExpected": 7,
        "loader": "lpbf_literature_datasets.load_ghosh_in625",
        "tableSha256": "79ee2d58b26c56dc88eadd5b1b0f73fb8f33e1b50a8f5eb73ac37d20e8487ce2",
        "nuisance": {"beamDiameter_um": list(GHOSH_SPOT_READINGS_UM),
                     "basis": "140 um = paper's FE model 1/e^2 radius 70 um (an assumption for the experiment); "
                              "100 um = Lane 2020 D4sigma of the NIST EOS M270 (same laboratory)",
                     "rule": "gate decision must be identical under both readings, else 'rejected: unresolved input'"},
        "rowRules": [],
        "notes": "case 7 depth (38 um) disagrees with Lane CBM case B (91 um) at the same nominal P/v: recorded, "
                 "not resolved, not excluded",
    },
    "trapp-316l-2017": {
        "material": "316L Stainless Steel", "role": "test-only (held out, never trained)",
        "digitized": True, "spotAssumed": False, "rowsExpected": 10,
        "loader": "lpbf_literature_datasets.load_trapp_316l_tracks",
        "tableSha256": "3a7bc34d75bb09bf41771331d116ce5d7e5ca0b7251aeb4d1e45c1e066a4ce7f",
        "nuisance": None,
        "rowRules": ["a row without a plotted depth (117 W) is excluded from both quantities and reported"],
        "notes": "0.5 mm bare discs, not semi-infinite; deep keyhole rows approach the disc thickness: kept and "
                 "declared, not cut on the measured response",
    },
}

# External absorptivity references: a sanity envelope on FITTED effective absorptivity, never a target.
ABSORPTIVITY_REFERENCES: Dict[str, Any] = {
    "role": "external sanity envelope on fitted effective absorptivity (diagnostic flag only): never a training "
            "target, never a prior centre, never in the gate",
    "tables": {
        "trapp-316l-2017-absorptivity": "20473b090b33b816ddcdc6881ed1e70a8cb78feb2ebf188ae97c8c3ca174ddf9",
        "ye-2019-absorptivity": "a6432fe813e02bd5ddb8615739944864dd678e5b63d9525a594bf759cc0a7367",
        "rubenchik-powder-2015": "ad114f77c5c2da8649e18c81eff056f3e0a74ff54bad66800b7da7d92cb290c9",
    },
    "rule": ("per alloy: envelope lower = min over the in-envelope reference values minus that value's read "
             "uncertainty; upper = max plus its read uncertainty, or none (one-sided) when no scanning-melt "
             "calorimetric series exists for the alloy. In-envelope: Trapp 316L 'disc' and 'powder' series (scanning, "
             "calorimetric, 1070 nm; points flagged 'penetrated' excluded) and Ye 2019 Am (bare foil minimum, table "
             "value, uncertainty 0.005 = half the last printed digit). Context only, NOT in the envelope: Rubenchik "
             "2015 powder (static, unmelted, 970 nm), W and Al 1100 discs (not app alloys)."),
    "checked": ("etaW, etaD and etaJoint of every final fit (all three kernels, every KU beam reading) and of every "
                "leave-one-source-out fold fit; flag 'outsideMeasuredAbsorptivityEnvelope' when below lower or above "
                "upper"),
    "envelopes": {
        "316L Stainless Steel": {"lower": 0.248, "upper": 0.797, "sides": "two-sided",
                                 "from": ["trapp disc (0.253-0.792)", "trapp powder (0.339-0.712)", "ye Am 0.28"]},
        "Ti-6Al-4V": {"lower": 0.255, "upper": None, "sides": "lower only",
                      "from": ["ye Am 0.26"], "context": ["rubenchik Ti-6Al-4V powder 0.648-0.715 (static, unmelted)"]},
        "Inconel 625": {"lower": 0.275, "upper": None, "sides": "lower only", "from": ["ye Am 0.28"]},
    },
    "weakness": ("the 316L envelope spans almost the whole fit bound [0.25, 0.80]; Ti-6Al-4V and Inconel 625 have a "
                 "lower bound only; the check can only catch gross compensation"),
}

NOT_USED_REFERENCES = {
    "ghosh-in625-2018-lengths": "melt-pool length is not a calibrated quantity (width/depth only)",
    "heigel-in625-amb2018-01": "3D-build cooling rate: a thermal target, not single-track geometry",
}


def _v2_config() -> Dict[str, Any]:
    cfg = copy.deepcopy(CONFIG_V1)
    cfg["version"] = CONFIG_VERSION_V2
    cfg["supersedes"] = {"configVersion": CONFIG_V1["version"], "configSha256": config_sha256(CONFIG_V1),
                         "artefact": "data/calibration/lpbf-meltpool-calibration-v1.json",
                         "rule": "v1 is never edited; v2 is a new pre-registered version"}
    roles = cfg["dataRoles"]
    roles["trainable"] = list(TRAINABLE_SOURCES_V2)
    roles["testOnly"] = list(TEST_ONLY_SOURCES)
    roles["testOnlyRoles"] = copy.deepcopy(TEST_ONLY_ROLES)
    roles["testOnlyNote"] = ("test-only literature sources: scored with the alloy's FINAL served fit, rung and interval "
                             "(trained on all trainable sources of the alloy); never in any fit, rung selection, "
                             "s_source or final fit")
    roles["testOnlyGate"] = {
        "entersGateAsHeldOutSource": True,
        "effect": "same per-held-out-source checks as a trainable fold (skill CI95 lower bound >= skillLbFloor, "
                  "coverage Wilson upper >= coverageWilsonUpperMin when n >= minRowsForCoverage, no extra "
                  "unresolved rows); it can only block 'enabled'",
        "secondSourceCredit": "only if not digitized AND no assumed spot size AND rows >= gate.minRowsForCoverage",
        "notInEtaConsistency": True,
        "notInSSource": True,
    }
    roles["digitizedNeverTrains"] = True
    cfg["absorptivityReferences"] = copy.deepcopy(ABSORPTIVITY_REFERENCES)
    cfg["notUsedReferences"] = dict(NOT_USED_REFERENCES)
    cfg["headline"] = {"heldOutAll": "equal source weight over every held-out source (trainable folds + test-only)",
                       "heldOutTrainableOnly": "the v1 definition (trainable leave-one-source-out folds only), kept "
                                               "for the before/after comparison"}
    return cfg


CALIBRATION_CONFIG_V2: Dict[str, Any] = _v2_config()

# Unchanged-by-design blocks (identical to v1 values; asserted by the tests).
V1_KEYS_CARRIED_VERBATIM = tuple(k for k in CONFIG_V1 if k not in ("version", "dataRoles"))


def config_v2_sha256() -> str:
    return config_sha256(CALIBRATION_CONFIG_V2)


def second_source_credit(source: str, n_rows: int, cfg: Dict[str, Any] = CALIBRATION_CONFIG_V2) -> bool:
    role = cfg["dataRoles"]["testOnlyRoles"][source]
    return (not role["digitized"]) and (not role["spotAssumed"]) and n_rows >= cfg["gate"]["minRowsForCoverage"]


# ---------------------------------------------------------------------------------------------
# absorptivity envelope (derived from the pinned tables by the pre-registered rule)
# ---------------------------------------------------------------------------------------------
def derive_absorptivity_envelopes() -> Dict[str, Dict[str, Any]]:
    """Re-derive the pinned envelopes from the pinned CSVs (the tests assert equality with the config)."""
    import lpbf_literature_datasets as L
    pts: Dict[str, List[tuple]] = {}
    for r in L.load_trapp_absorptivity()["rows"]:
        if r["material"] != "316L Stainless Steel":
            continue
        if not (r["series"].startswith("316L-disc") or r["series"].startswith("316L-powder")):
            continue
        if r["flag"] and "penetrated" in r["flag"]:
            continue
        pts.setdefault(r["material"], []).append((r["absorptivity"], r["readUncertaintyAbsorptivity"], "scan"))
    for r in L.load_ye_min_absorptivity()["rows"]:
        pts.setdefault(r["material"], []).append((r["absorptivity"], 0.005, "ye"))
    out: Dict[str, Dict[str, Any]] = {}
    for m, p in pts.items():
        lo = min(v - u for v, u, _ in p)
        two = any(kind == "scan" for _, _, kind in p)
        hi = max(v + u for v, u, _ in p) if two else None
        out[m] = {"lower": round(lo, 6), "upper": None if hi is None else round(hi, 6),
                  "sides": "two-sided" if two else "lower only"}
    return out


def envelope_check(material: str, etas: Dict[str, Optional[float]],
                   cfg: Dict[str, Any] = CALIBRATION_CONFIG_V2) -> Dict[str, Any]:
    env = cfg["absorptivityReferences"]["envelopes"].get(material)
    if env is None:
        return {"envelope": None, "outside": [], "flag": False}
    outside = []
    for name, eta in sorted(etas.items()):
        if eta is None:
            continue
        if eta < env["lower"] - 1e-12:
            outside.append({"param": name, "eta": eta, "side": "below"})
        elif env["upper"] is not None and eta > env["upper"] + 1e-12:
            outside.append({"param": name, "eta": eta, "side": "above"})
    return {"envelope": {"lower": env["lower"], "upper": env["upper"], "sides": env["sides"]},
            "outside": outside, "flag": bool(outside)}


__all__ = ["CALIBRATION_CONFIG_V2", "CONFIG_VERSION_V2", "CALIBRATION_SCHEMA_V2", "SCORECARD_SCHEMA_V2",
           "ARTEFACT_V2_REL_PATH", "SCORECARD_V2_STEM", "TEST_ONLY_SOURCES", "TRAINABLE_SOURCES_V2",
           "GHOSH_SPOT_READINGS_UM", "config_v2_sha256", "second_source_credit", "derive_absorptivity_envelopes",
           "envelope_check", "canonical_json", "KERNELS", "CATALOG_SOURCES"]
