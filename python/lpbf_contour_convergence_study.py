"""Independent CPU 3+3 gate for the continuous peak-liquidus thermal contour.

The original cell-extent assessment remains in the same report. This metric is
a numerical thermal proxy, not an etched-optical measurement operator.
"""

import argparse
import copy
import json
import math
from pathlib import Path

from lpbf_convergence_study import ACCEPTANCE, _axis, study
from lpbf_peak import PEAK_EXTRACTION


PROTOCOL_ID = "p4-peak-liquidus-contour-v1"
CONTOUR_OPERATOR = "peak-liquidus-cell-edge-linear-contour-v1"


def _contour_axis(axis, resolution_key):
    rows = copy.deepcopy(axis["levels"])
    invalid_levels = []
    for row in rows:
        if row["status"] != "completed":
            continue
        contour = row.get("interpolatedPeakMeltPool")
        if (not isinstance(contour, dict) or contour.get("status") != "thermal-proxy"
                or contour.get("operator") != CONTOUR_OPERATOR
                or contour.get("temporalSelection") != PEAK_EXTRACTION
                or contour.get("surfaceTreatment") != "No temperature extrapolation to the model surface"
                or any(type(contour.get(key)) not in (int, float)
                       or not math.isfinite(contour[key]) or contour[key] <= 0
                       for key in ("width_um", "depth_um"))):
            row.update(status="failed", reason="Bound continuous liquidus contour is unavailable or invalid")
            invalid_levels.append({"requested": row["requested"], "reason": row["reason"]})
            continue
        row["width_um"] = contour["width_um"]
        row["depth_um"] = contour["depth_um"]
    assessment = _axis(rows, resolution_key)
    if invalid_levels:
        assessment["invalidLevels"] = invalid_levels
    return assessment


def contour_study(scenario, mesh_levels_um, timestep_levels_s):
    """Execute both frozen discrete and predeclared continuous assessments."""
    report = study(scenario, mesh_levels_um, timestep_levels_s)
    report["protocolId"] = PROTOCOL_ID
    report["contourOperator"] = CONTOUR_OPERATOR
    report["contourTemporalSelection"] = PEAK_EXTRACTION
    report["contourAcceptance"] = copy.deepcopy(ACCEPTANCE)
    report["discreteStatus"] = report["status"]
    for name, key in (("meshStudy", "actualMesh_m"), ("timestepStudy", "actualMeanDt_s")):
        report[name]["contourAssessment"] = _contour_axis(report[name], key)
    states = [report[name]["contourAssessment"]["status"] for name in ("meshStudy", "timestepStudy")]
    report["contourStatus"] = "failed" if "failed" in states else "inconclusive" if "inconclusive" in states else "pass"
    report["contourEvidenceScope"] = "Numerical thermal proxy only; not an etched-optical section or experimental validation"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mesh-levels-um", nargs="+", type=float, required=True)
    parser.add_argument("--timestep-levels-s", nargs="+", type=float, required=True)
    args = parser.parse_args()
    report = contour_study(json.loads(args.scenario.read_text(encoding="utf-8")),
                           args.mesh_levels_um, args.timestep_levels_s)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Discrete: {report['discreteStatus']}; contour: {report['contourStatus']} ({args.output})")


if __name__ == "__main__":
    main()
