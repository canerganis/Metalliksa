"""Pre-registered configuration of the LPBF melt-pool calibration scorecard (frozen BEFORE the first real run).

Everything that could be tuned after seeing held-out numbers lives here and nowhere else: the absorptivity grids,
bounds, prior strength, source weighting, rung-selection margin, bootstrap sizes, interval levels and every gate /
physics-compensation threshold. ``config_sha256()`` is stored in the calibration artefact and in the scorecard
record; the runtime layer refuses an artefact whose config hash differs from the one compiled in here, so a
config change needs a NEW calibration version (a new artefact file name), never an in-place edit.

This module is deliberately NOT part of ``lpbf_simulation.IMPLEMENTATION_SOURCE_FILES``: it does not touch the
frozen physics, and no frozen file may import it (test_lpbf_calibration_frozen.py scans for that).

Evidence label: every output of the calibration stack stays ``screening-only``; nothing here derives a label.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

CONFIG_VERSION = "lpbf-meltpool-calibration-config-1"
CALIBRATION_SCHEMA = "lpbf-meltpool-calibration-1"
SCORECARD_SCHEMA = "lpbf-calibration-scorecard-1"
SCORECARD_VIEW_SCHEMA = "lpbf-calibration-scorecard-view-1"
ARTEFACT_REL_PATH = "data/calibration/lpbf-meltpool-calibration-v1.json"

KERNELS = ("eagar-tsai", "goldak", "rosenthal")

# Sources that fit / train / enter the gate (blind with respect to the physics development).
TRAINABLE_SOURCES = (
    "hofmann-316l-2026",
    "ku-leuven-316l-2021",
    "totis-ti64-2021",
    "ku-leuven-ti64-2021",
    "lane-in625-2020",
)
# Sources the frozen physics (PROOF 023, Goldak fix, test_goldak_fabbro bands) was developed against: test-only
# sentinels, never in any fit_*, final fit, s_source or gate (R1).
CATALOG_SOURCES = ("guo-316l-2024", "nist-amb2022-03-in718")

CALIBRATION_CONFIG: Dict[str, Any] = {
    "version": CONFIG_VERSION,
    "kernels": list(KERNELS),
    "dataRoles": {
        "trainable": list(TRAINABLE_SOURCES),
        "catalogSentinels": list(CATALOG_SOURCES),
        "catalogSentinelNote": ("catalog sentinels (used during physics development, not blind): reported "
                                "separately, never trained on, never in the gate"),
        "singleSourceAlloys": ["Inconel 625"],
        "noDataAlloys": ["Inconel 718", "AlSi10Mg"],
    },
    "kernelGrid": {"start": 0.20, "stop": 0.90, "step": 0.025, "plusMaterialDefaults": True,
                   "interpolation": "linear in ln(eta) on ln(width), ln(depth); a node pair with any "
                                    "non-'computed' status makes the row unresolved at that eta"},
    "fitGrid": {"start": 0.25, "stop": 0.80, "step": 0.005, "search": "deterministic grid scan, ties to the smaller eta"},
    "bounds": [0.25, 0.80],
    "materialDefaults": {"316L Stainless Steel": 0.42, "Ti-6Al-4V": 0.35, "Inconel 625": 0.38, "Inconel 718": 0.38},
    "prior": {"centre": "material default absorptivity_IR (one rule for every alloy)",
              "lambda": 0.05,
              "penalty": "lambda * ln(eta / eta_prior)^2 added to the set-averaged mean |ln| loss",
              "measuredAbsorptanceRole": "R5 bands and bounds only; never a target and never a 'match'"},
    "minCoverage": 0.95,
    "minSetsPerClass": 8,
    "cdClipLn": 0.693147,  # ln 2
    "sourceWeight": {"nSetsFull": 20, "rule": "w_s = min(1, nSets_s / 20), normalised over the training sources"},
    "ballingFlaggedRowsTrainWidth": False,
    "ballingFlaggedRowsTrainDepth": True,
    "rungs": ["default", "eta", "eta2", "eta2+dOffset"],
    "rungsReferenceOnly": ["powerlaw"],
    "rungMarginRel": 0.01,
    "rungSelection": {"where": "inside the training sources only", "innerLoso": "when >= 2 training sources",
                      "innerKFold": 5, "innerSeeds": [0, 1, 2], "tieBreak": "simpler rung",
                      "etaRungRule": "the joint eta rung may serve q only if the eta2 q-specific fit also "
                                     "improves q on the inner score"},
    "bootstrap": {"paramReplicates": 200, "skillReplicates": 1000, "seed": 0,
                  "paramUnit": "parameter set (cluster), stratified by source, theta refit per replicate",
                  "skillUnit": "test parameter set (cluster), theta fixed, no refit"},
    "p1": {"k": 5, "seeds": [0, 1, 2], "minSetsPerSource": 20},
    "interval": {"levels": [0.8, 0.9], "z": {"0.8": 1.2816, "0.9": 1.6449}, "minSourcesForSSource": 3,
                 "sSourceInflation": "chi-square upper bound, one-sided 90 % on the SD of per-source mean residuals",
                 "sSourceResiduals": "at a theta fitted WITHOUT the source itself and WITHOUT the held-out source "
                                     "(default eta when no training source is left)",
                 "notInformativeRatio": 2.5, "wilsonConfidence": 0.95},
    "gate": {"skillLbFloor": -0.02, "coverageLevel": 0.9, "coverageWilsonUpperMin": 0.90,
             "minRowsForCoverage": 10, "etaConsistencyDLn": 0.15, "etaSplitRatio": 1.3, "offsetDominantRatio": 1.25,
             "boundHitBootstrapFraction": 0.20, "boundHitSteps": 1,
             "unresolvedRule": "a rung that resolves fewer test rows than default fails the gate",
             "p1WithinSourceSkillLbMin": 0.0},
    "absorptanceBands": {
        "316L Stainless Steel": {"conduction": [0.31, 0.35], "keyhole": [0.50, 0.86],
                                 "basis": "Simonds 2018 Table III (stationary spot, polished)"},
        "Ti-6Al-4V": {"keyhole": [0.52, 0.72], "basis": "NIST mds2-2525 stationary pulse 62.0 % +- 0.10"},
        "widenFactor": 1.3,
    },
    "beamSensitivityUm": {"ku-leuven-316l-2021": [37.5, 75.0], "ku-leuven-ti64-2021": [37.5, 75.0],
                          "rule": "gate decision must be identical under both KU beam readings, else "
                                  "'rejected: unresolved input'"},
    "regimeClass": {"thresholds": [15.0, 30.0], "basis": "input-only normalised enthalpy at the material default"},
    "rounding": {"significantDigits": 6},
}


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def config_sha256(config: Dict[str, Any] = CALIBRATION_CONFIG) -> str:
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()
