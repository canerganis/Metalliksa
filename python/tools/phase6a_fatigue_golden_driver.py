#!/usr/bin/env python3
"""
Phase 6a golden driver for lpbf_fatigue_fracture (a library module, no __main__).

It reproduces lpbf_worker_rpc._rpc_fatigue_fracture (the only production caller,
served at /api/python/lpbf-fatigue-fracture) with the same payload defaults, reads
the JSON payload on stdin and prints the result JSON on stdout, so the golden
harness can run the module like a solver script.

Exit codes: 0 success; 2 with the input_validation envelope on stdout for a
ValidationError; 1 with {"error", "errorKind": "internal"} for anything else.

The harness puts the module under test first on PYTHONPATH (a git blob extracted
to a temp dir for --from-revision captures), then python/.
"""

import json
import sys

import lpbf_fatigue_fracture
from input_validation import ValidationError, validation_envelope


def run(payload):
    alloy = payload.get("alloyName", "Ti-6Al-4V")
    engine = lpbf_fatigue_fracture.MurakamiFatigueEngine(alloy)
    sqrt_area = float(payload.get("sqrtArea_um", 45.0))
    location = payload.get("location", "internal")
    r_ratio = float(payload.get("stressRatio_R", -1.0))
    return {
        "fatigue_limit": engine.calculate_fatigue_limit(sqrt_area, location, r_ratio),
        "kitagawa_takahashi_curve": engine.generate_kitagawa_takahashi_curve(location, r_ratio, n_points=30),
        "paris_crack_growth": engine.simulate_paris_crack_growth(
            initial_defect_sqrt_area_um=sqrt_area,
            cyclic_stress_amplitude_MPa=float(payload.get("stressAmplitude_MPa", 220.0)),
            stress_ratio_R=r_ratio,
        ),
    }


def main():
    try:
        print(json.dumps(run(json.loads(sys.stdin.read()))))
    except ValidationError as err:
        print(json.dumps(validation_envelope(err)))
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001 - reported as an internal error
        print(json.dumps({"error": str(exc), "errorKind": "internal"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
