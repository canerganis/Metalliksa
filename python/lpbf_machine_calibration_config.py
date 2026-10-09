"""Configuration of the machine (single-source) melt-pool depth calibration. SCREENING ONLY, NOT VALIDATION.

Every number that shapes the gate, the fit, the band and the label rule lives here and is hashed into the machine
artefact (``config_sha256``). Not part of ``IMPLEMENTATION_SOURCE_FILES``; no frozen file imports it.

The fitted quantity is an empirical machine offset: a plain multiplicative depth factor ``f = exp(c)`` applied to the
frozen Rosenthal depth at the material default absorptivity. It is not an absorptivity and not a physical quantity.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict

MACHINE_SCHEMA = "lpbf-machine-calibration-1"
CELL_DESIGN_KERNEL = "rosenthal"

REASON_TEXT_EAGAR_GOLDAK = ("this kernel's depth error is regime-dependent on every published source; machine "
                            "calibration is not offered for Eagar-Tsai / Goldak depth (see scorecard v2)")

MACHINE_CALIBRATION_CONFIG: Dict[str, Any] = {
    "version": "lpbf-machine-calibration-config-1",
    "nuisance": {
        "name": "empirical machine offset",
        "form": "depth_calibrated = f * depth_default_absorptivity, f = exp(c)",
        "note": "not an absorptivity and not a physical quantity; it absorbs model error and measurement bias",
    },
    "fit": {
        "loss": "mean over the user's tracks of |ln(measured / (f * predicted_default))| + lambda * c^2",
        "lambda": 0.05,
        "cGrid": {"lo": -1.5, "hi": 1.5, "step": 0.002},
        "tieRule": "smaller |c|",
        "basis": {"laserWavelength": "IR_1064nm", "thermalSliceBackend": "cpu"},
        "bootstrapReplicates": 200,
        "bootstrapSeed": 0,
        "bootstrapLevel": 0.9,
        "trackUnit": "parameter set (power, speed, spot); replicate rows of one set are averaged in ln space",
    },
    "gate": {
        "minTracks": 4,
        "uniformSignFraction": 0.8,
        "minAbsMeanLnResidual": 0.15,
        "maxAbsC": math.log(3.0),
        "factorRange": [1.0 / 3.0, 3.0],
        "conditions": ["minTracks", "uniformSign", "offsetTooSmall", "looSkill", "factorOutOfRange", "eligible"],
        "regimeClassesRequired": False,
        "regimeClassesNote": "reported, not a condition (the stand-in simulation showed it has no power)",
    },
    "band": {"level": 0.8, "notInformativeRatio": 2.5,
             "statement": ("80 % of your own held-out tracks fell inside a band like this in the simulation on "
                           "published sources; it is not a tolerance")},
    # Maintainer decision 1: only Rosenthal depth for 316L Stainless Steel is eligible. A committed list, not computed
    # from the user's data.
    "eligibleCells": [{"kernel": "rosenthal", "material": "316L Stainless Steel", "quantity": "depth"}],
    "notEligibleReasons": {
        "width": "width is not part of machine calibration; only Rosenthal depth for 316L Stainless Steel is offered",
        "eagar-tsai|goldak": REASON_TEXT_EAGAR_GOLDAK,
        "Ti-6Al-4V": ("Ti-6Al-4V depth is not eligible: the published stand-ins disagree (one source is refused at "
                      "the bound, G6 false-pass rate up to 0.33) and no second Ti-6Al-4V stand-in with 20 or more "
                      "sets exists"),
        "Inconel 625": "insufficient stand-in: only 6 usable published sets, not simulated",
        "other-material": "no published stand-in simulation exists for this alloy",
    },
    # Maintainer decision 3: the calibrated-simulation label needs G6 and complete method fields on every track.
    "methodFields": {
        "required": ["depthDatum", "beamDiameterDefinition", "measuredPowerW", "crossSectionLocation", "replicates"],
        "examples": {"depthDatum": "plate surface / powder top", "beamDiameterDefinition": "1/e2, D4sigma, FWHM"},
        "rowKey": "method",
    },
    "evidence": {
        "calibrated": "calibrated-simulation",
        "screening": "screening-only",
        "scope": "this machine, user data",
        "labelCalibrated": ("Calibrated simulation, this machine, user data: empirical machine offset fitted to your "
                            "own tracks; not validation"),
        "labelScreening": "Screening only: machine calibration not served as calibrated simulation",
        "experimentalValidation": False,
        "labelPromotionProposed": "none",
    },
    "honesty": ("single-source fit of an empirical machine depth factor to the user's own single-track "
                "measurements; it absorbs model error; no per-row uncertainty; the global calibration and "
                "scorecard are unchanged"),
}


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def config_sha256(config: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> str:
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()


def is_eligible(kernel: str, material: str, quantity: str,
                config: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> bool:
    return any(e["kernel"] == kernel and e["material"] == material and e["quantity"] == quantity
               for e in config["eligibleCells"])


def not_eligible_reason(kernel: str, material: str, quantity: str,
                        config: Dict[str, Any] = MACHINE_CALIBRATION_CONFIG) -> str:
    r = config["notEligibleReasons"]
    if quantity != "depth":
        return r["width"]
    if kernel in ("eagar-tsai", "goldak"):
        return r["eagar-tsai|goldak"]
    return r.get(material, r["other-material"])
