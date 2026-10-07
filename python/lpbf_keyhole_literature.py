#!/usr/bin/env python3
"""Keyhole benchmark data transcribed from maintainer-supplied papers (wave 5d), plus the papers' published relations.

Numbers only: the articles and their figures are not committed. Every committed CSV row carries a ``locator`` (table,
equation, text page or figure panel) and a ``digitized`` flag; figure reads live only in files named ``*digitized*``
with a read-uncertainty column. Every CSV is SHA-256 pinned below and refused when its bytes change. The SHA-256 of
the PDF copy each value was read from is recorded (the PDF is not redistributed).

What was taken (comparison inputs only; nothing here calibrates, validates or changes a solver threshold):

* Cunningham et al. 2019, Science 363, 849 (doi:10.1126/science.aav4687): Ti-6Al-4V bare plate, APS x-ray imaging.
  Vapor-depression depth vs power per scan speed for 95 um (Fig. 3B, 46 points) and 140 um (Fig. 3C, 23 points)
  spots, DIGITIZED; the Fig. 3A blue (vapor-depression transition) and red (melt-pool transition) dashed lines in P-V
  space for the 95 um spot, DIGITIZED as straight-line fits. The regime label of a Fig. 3B case is derived from
  those two lines exactly as the paper defines the domains (below blue = conduction, above red = keyhole).
* Zhao et al. 2020, Science 370, 1080 (doi:10.1126/science.abd1587): Ti-6Al-4V keyhole-porosity boundary (bare
  plate and ~105 um powder layer, ~100 um spot) from Fig. 1A with the boundary keyhole depths of Fig. 2A/2B, and the
  Fig. 1A maximum-pore-size markers (pores observed), all DIGITIZED.
* Gan et al. 2021, Nat. Commun. 12, 2379 (doi:10.1038/s41467-021-22704-0, CC BY 4.0): keyhole-number relations
  (Eqs. 1, 2, 5-9) and the five Al6061 cases whose P, V and Ke are PRINTED in Figs. 1-2. The per-case Fig. 1a data are
  in Supplementary Data 1; its 71 Ti-6Al-4V rows are ingested as a cross-check (load_gan_data1_ti64) and flagged
  independentOfCunningham2019 = False: they are Cunningham 2019 (Gan ref. 2), never counted as a second dataset.
* Huang et al. 2022, Nat. Commun. 13, 1170 (doi:10.1038/s41467-022-28694-x, CC BY 4.0): Al7A77 / Al regime labels
  printed in Figs. 1, 4 and the text; the front-wall-angle relation and the normalised-enthalpy-product thresholds.
  Huang's Ti-6Al-4V points are Cunningham 2019 and Zhao 2020 data (its refs. 25, 16) and are NOT taken again.
* Hann et al. 2011, J. Phys. D 44, 445401 (doi:10.1088/0022-3727/44/44/445401): the 14 AISI 304 laser welds printed
  in Tables 3-4 (P, U, fibre diameter, dH/hs, delta*), the normalised enthalpy definition (Eq. 4), the depth relation
  as printed, and the Table 2 vaporization-enthalpy ratios (Ti-6Al-4V Hv/hs = 12.34).

Only Ti-6Al-4V is an app material among these; Al6061, Al7A77, pure Al and AISI 304 are not in the app's material
authority, so those rows are ingested with their labels but not run through the app (``appEvaluable=False``).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lpbf_public_datasets import REPO_ROOT, _load_pinned_csv, sha256_file  # noqa: E402

BENCHMARK_DIR = REPO_ROOT / "data" / "benchmark"
TRANSCRIBED = "2026-10-07"
SOURCE_NOTE = ("maintainer-supplied PDF copy, read locally on 2026-10-07; not committed (article not redistributed); "
               "the hash identifies the copy that was read, not a publisher original")
ASSUMED_PREHEAT_C = 20.0
APP_MATERIAL_TI64 = "Ti-6Al-4V"

# ---- Cunningham 2019 --------------------------------------------------------------------------------------------
CUN_DIR = BENCHMARK_DIR / "cunningham-ti64-2019"
CUN_DEPTH_TABLE = CUN_DIR / "fig3bc_vapor_depth_digitized.csv"
CUN_LINES_TABLE = CUN_DIR / "fig3a_transition_lines_digitized.csv"
CUN_DEPTH_SHA256 = "223583bb6eead835ebbc0071fae0619408617bacf616790f9226267dacf34a03"
CUN_LINES_SHA256 = "49c956b7dc4b77adf0672809aa6369a451a3f9ebf3d65ff104396a72b505b0d5"
CUN_DEPTH_COLUMNS = ["case", "spot_um", "power_W", "speed_mm_s", "vapor_depression_depth_um", "depth_sd_um",
                     "read_uncertainty_um", "power_read_uncertainty_W", "locator", "digitized"]
CUN_LINES_COLUMNS = ["line", "meaning", "spot_um", "slope_W_per_mm_s", "intercept_W", "speed_min_mm_s",
                     "speed_max_mm_s", "fit_residual_sd_W", "read_uncertainty_W", "locator", "digitized"]
CUN_PROVENANCE = {
    "id": "cunningham-ti64-2019", "doi": "10.1126/science.aav4687",
    "citation": ("R. Cunningham, C. Zhao, N. Parab, C. Kantzos, J. Pauza, K. Fezzaa, T. Sun, A. D. Rollett, 'Keyhole "
                 "threshold and morphology in laser melting revealed by ultrahigh-speed x-ray imaging', Science 363 "
                 "(2019) 849-852, doi:10.1126/science.aav4687, Fig. 3A-C."),
    "license": ("(c) 2019 The Authors, some rights reserved; exclusive licensee AAAS; numbers digitized from the "
                "published figures; article not redistributed"),
    "material": "Ti-6Al-4V", "substrate": "bare plate (no powder)",
    "evidenceKind": "published measurement (operando x-ray vapor-depression depth), digitized from figures",
    "source": {"file": "cunningham2019.pdf", "bytes": 658815,
               "sha256": "995151c40f0ca70a525b0fde2fc0fd067ae6cb52aa4943c5d89e67cd683f3fe4", "note": SOURCE_NOTE},
    "supplementaryNeeded": ("Supplementary Materials read 2026-10-07 (aav4687_cunningham_sm.pdf, pp. 2-4): single-mode "
                            "fibre laser with a Gaussian profile, focal spot ~56 um (1/e^2) and larger spots by "
                            "defocusing, so the 95/140 um spot sizes are 1/e^2 diameters (Eq. S1 uses the 1/e^2 "
                            "diameter); confirmed independently by Gan 2021 Supplementary Data 1 (r0 = d/2). Fig. 3A "
                            "red line = melt-pool transition (d/w ~ 0.5, stationary beam, SM Figs. S2/S3)."),
    "caveats": [
        "Depth is the VAPOR-DEPRESSION (keyhole) depth from operando x-ray radiographs, mean of > 30 frames, error bar "
        "= SD (Fig. 3 caption, p. 2). It is not the post-mortem melt-pool depth.",
        "Values digitized from the embedded 300 ppi raster of Fig. 3: axes calibrated on the tick marks; value = marker "
        "centre; SD = half the error-bar span only where the bar extends beyond the marker (else blank). Read "
        "uncertainty 4 um, 6 um in crowded clusters; power read uncertainty 3 W. Powers fall on a ~13/26 W setpoint "
        "grid (cf. the Fig. 2A/B legends) but the read value is recorded, not snapped.",
        "Regime labels for the 95 um spot come from the Fig. 3A dashed lines (blue: vapor-depression transition, red: "
        "melt-pool transition; text p. 2: below blue = conduction domain, above red = keyhole domain). The lines were "
        "measured in the stationary-beam experiment and placed in P-V space by the authors; Fig. 3A applies to the "
        "95 um spot only, so 140 um rows carry no regime label.",
        "Some 400-900 mm/s high-power points have a 'J'-shaped depression (text p. 2); the plotted depth is used as is.",
        "Substrate temperature not stated: 20 C assumed. Plate thickness and laser profile are in the SI (not read).",
    ],
    "overlap": ("Gan et al. 2021 Fig. 1a Ti-6Al-4V points (spot 95 and 140 um) and Huang et al. 2022 Fig. 1b "
                "Ti-6Al-4V bare-plate points are this dataset (Gan ref. 2, Huang ref. 25); they are not ingested "
                "again."),
}

# ---- Zhao 2020 --------------------------------------------------------------------------------------------------
ZHAO_DIR = BENCHMARK_DIR / "zhao-ti64-2020"
ZHAO_BOUNDARY_TABLE = ZHAO_DIR / "fig1a_porosity_boundary_digitized.csv"
ZHAO_PORE_TABLE = ZHAO_DIR / "fig1a_pore_markers_digitized.csv"
ZHAO_BOUNDARY_SHA256 = "979e63b17f1b43adea03b9e69a4a73bd4595c70721e67a850a5e5a436f08c271"
ZHAO_PORE_SHA256 = "60497f386b27769726f6dcd5dff98d5ccdead5bb9609623e29e61efba4d16568"
ZHAO_BOUNDARY_COLUMNS = ["case", "setting", "spot_um", "power_W", "speed_mm_s", "keyhole_depth_um",
                         "depth_read_uncertainty_um", "power_read_uncertainty_W", "speed_read_uncertainty_mm_s",
                         "locator", "digitized"]
ZHAO_PORE_COLUMNS = ["case", "spot_um", "power_W", "speed_mm_s", "bare_plate_pores", "powder_bed_pores",
                     "power_read_uncertainty_W", "speed_read_uncertainty_mm_s", "locator", "digitized"]
ZHAO_PROVENANCE = {
    "id": "zhao-ti64-2020", "doi": "10.1126/science.abd1587",
    "citation": ("C. Zhao, N. D. Parab, X. Li, K. Fezzaa, W. Tan, A. D. Rollett, T. Sun, 'Critical instability at "
                 "moving keyhole tip generates porosity in laser melting', Science 370 (2020) 1080-1086, "
                 "doi:10.1126/science.abd1587, Figs. 1A, 2A, 2B."),
    "license": ("(c) 2020 The Authors, some rights reserved; exclusive licensee AAAS; numbers digitized from the "
                "published figures; article not redistributed"),
    "material": "Ti-6Al-4V", "substrate": "thin bare plate (~400 um) and the same plate with a ~105 um powder layer",
    "evidenceKind": "published measurement (operando x-ray keyhole-porosity boundary and pore observation), digitized",
    "source": {"file": "zhao2020.pdf", "bytes": 1039762,
               "sha256": "7aa2a6f96f83cfb4546c6cfbf7d0792a51aadaa2909c811bf54b3382694bb384", "note": SOURCE_NOTE},
    "supplementaryNeeded": ("The energy-density definition (E, MJ/m2), the beam profile and the per-condition tables "
                            "are in the Supplementary Materials (not available)."),
    "caveats": [
        "Boundary markers (Fig. 1A open circles = bare plate, open squares = powder bed) are the P-V conditions on the "
        "keyhole porosity boundary; pores appear across it toward higher energy density. Several boundary markers "
        "contain a tiny pore marker (borderline conditions).",
        "Boundary keyhole depth d1 is read from Fig. 2A (vs V) and Fig. 2B (vs P) and matched by value; the bare-plate "
        "point at ~375 mm/s / 128 W exists in Fig. 2A/2B but has no open circle in Fig. 1A, and the Fig. 1A bare "
        "circle at ~222 mm/s / 82 W has no Fig. 2 depth. Both are recorded as found, not resolved.",
        "Pore markers: blue left half = pores in the bare plate, red half = pores in the powder bed; 'not-shown' means "
        "no marker half for that setting at that P-V (the figure does not say whether the condition was run).",
        "The stable side of the boundary carries no markers, so the pore data are one-sided (pores observed only).",
        "Spot size '~100 um' (Fig. 1 caption), taken as the 1/e^2 diameter (assumption). Read uncertainty: 4 W, "
        "4 mm/s, 6 um depth. Substrate temperature not stated: 20 C assumed. The ~400 um plate is not semi-infinite.",
    ],
    "overlap": ("Same APS beamline/group as Cunningham 2019 but a different campaign and quantity (porosity boundary, "
                "~100 um spot). Huang 2022 Fig. 1b/2 re-plot these data (Huang ref. 16) and are not ingested again."),
}

# ---- Gan 2021 ---------------------------------------------------------------------------------------------------
GAN_DIR = BENCHMARK_DIR / "gan-keyhole-2021"
GAN_TABLE = GAN_DIR / "printed_cases.csv"
GAN_SHA256 = "0da9f9b9f604e439040923d1d0f1d498024c4b78f04edaeef9838b5991fd04ff"
GAN_DATA1_TABLE = GAN_DIR / "supplementary_data1_ti64.csv"
GAN_DATA1_SHA256 = "1fad0e2f1d3fed3a95c4126e68ebbacc130185bed8fd56f0a56a8b2dce387ca1"
GAN_DATA1_XLSX_SHA256 = "b52d9173eb3a63983dd87c56b2720abd419a200e9594b863218de13da6a7597a"
GAN_DATA1_COLUMNS = ["case", "spot_label", "P_W", "eta", "V_m_s", "d_m", "r0_m", "k_W_mK", "rho_kg_m3", "cp_J_kgK",
                     "alpha_m2_s", "Tv_minus_T0_K", "Lv_J_m3", "Tl_minus_T0_K", "Lm_J_m3", "e_m", "length_um",
                     "tan_theta", "locator", "digitized"]
GAN_COLUMNS = ["case", "material", "substrate", "power_W", "speed_mm_s", "spot_um", "keyhole_number_printed",
               "regime_reported", "stability_reported", "locator", "digitized"]
GAN_PROVENANCE = {
    "id": "gan-keyhole-2021", "doi": "10.1038/s41467-021-22704-0",
    "citation": ("Z. Gan, O. L. Kafka, N. Parab, C. Zhao, L. Fang, O. Heinonen, T. Sun, W. K. Liu, 'Universal scaling "
                 "laws of keyhole stability and porosity in 3D printing of metals', Nat. Commun. 12 (2021) 2379, "
                 "doi:10.1038/s41467-021-22704-0."),
    "license": "CC BY 4.0 (article); values transcribed with locators; article not redistributed",
    "material": "Al6061 (printed cases); relations are material-general",
    "evidenceKind": "published measurement (printed case labels) and published scaling relations",
    "source": {"file": "gan2021.pdf", "bytes": 1642516,
               "sha256": "85dc767c0a91020f97119cc53139b9718e2f3523a5e30ddb4ce6ccb36ad0b074", "note": SOURCE_NOTE},
    "supplementaryNeeded": ("Supplementary Data 1 (Ti-6Al-4V keyhole depths behind Fig. 1a, Gan Table 1 properties) was "
                            "read 2026-10-07 and its 71 Ti-6Al-4V rows are ingested as a cross-check "
                            "(supplementary_data1_ti64.csv, load_gan_data1_ti64); Fig. 1a was not digitized and the "
                            "Al6061 block is not ingested."),
    "caveats": [
        "Ke uses the keyhole absorptivity eta (Eq. 6, a function of Ke_m*Ld* with the flat minimum absorptivity eta_m "
        "of Ye et al. 2019), not a flat absorptivity.",
        "Al6061 is not an app material: the five printed cases are ingested with Gan's own labels but not run through "
        "the app.",
        "Bare plates, Ar-filled chamber, 1070 nm single-mode Gaussian beam, spot set by defocus (Methods p. 7).",
    ],
    "overlap": "Gan Fig. 1a Ti-6Al-4V = Cunningham 2019 (ref. 2): not ingested twice.",
}

# ---- Huang 2022 -------------------------------------------------------------------------------------------------
HUANG_DIR = BENCHMARK_DIR / "huang-al7a77-2022"
HUANG_TABLE = HUANG_DIR / "printed_cases.csv"
HUANG_SHA256 = "09561449e3851aea31d98a8e2a2c05745b1a53a6ef0116c0313dbac95e2e75a9"
HUANG_COLUMNS = ["case", "material", "substrate", "power_W", "speed_mm_s", "spot_um", "regime_reported",
                 "pores_reported", "aed_printed_MJ_m2", "locator", "digitized"]
HUANG_PROVENANCE = {
    "id": "huang-al7a77-2022", "doi": "10.1038/s41467-022-28694-x",
    "citation": ("Y. Huang, T. G. Fleming, S. J. Clark, S. Marussi, K. Fezzaa, J. Thiyagalingam, C. L. A. Leung, "
                 "P. D. Lee, 'Keyhole fluctuation and pore formation mechanisms during laser powder bed fusion "
                 "additive manufacturing', Nat. Commun. 13 (2022) 1170, doi:10.1038/s41467-022-28694-x."),
    "license": "CC BY 4.0 (article); values transcribed with locators; article not redistributed",
    "material": "Al7A77 powder on an Al plate; bare Al plate",
    "evidenceKind": "published measurement (printed regime labels) and published relations",
    "source": {"file": "huang2022.pdf", "bytes": 3063398,
               "sha256": "e94de7e606e1faa87ef74af52ef52dbaa75638e198ac97eab6b23e333d3ef9f5", "note": SOURCE_NOTE},
    "supplementaryNeeded": ("Supplementary Table 3 (thermophysical properties, absorptivity beta) is needed to "
                            "recompute dH/hm*Lth* exactly; not available."),
    "caveats": [
        "Regimes I (quasi-stable), II (transition), III (unstable) are Huang's keyhole-morphology classes, all within "
        "keyhole-mode melting; they are not conduction/transition/keyhole melting modes.",
        "Al7A77 and pure Al are not app materials: ingested with Huang's labels, not run through the app.",
        "500 W, 50 um spot, 30 um layer (Table 1); APS 32-ID-B, 20 us frame interval.",
    ],
    "overlap": ("Huang Fig. 1b/2 Ti-6Al-4V, IN718 and SS304 data are re-plotted from Cunningham 2019, Zhao 2020, "
                "Kouraytem, Parab and Hojjatzadeh; none of them is ingested from Huang."),
}

# ---- Hann 2011 --------------------------------------------------------------------------------------------------
HANN_DIR = BENCHMARK_DIR / "hann-ss304-2011"
HANN_TABLE = HANN_DIR / "tables3_4_welds.csv"
HANN_SHA256 = "376aa91b41ca2b479b016ced3eea54e15f1443ce1d1d3dc9065906218dd47973"
HANN_COLUMNS = ["case", "material", "power_W", "speed_m_min", "fibre_diameter_um", "focus_diameter_um",
                "dH_hs_printed", "delta_star_printed", "side_reported", "locator", "digitized"]
HANN_PROVENANCE = {
    "id": "hann-ss304-2011", "doi": "10.1088/0022-3727/44/44/445401",
    "citation": ("D. B. Hann, J. Iammi, J. Folkes, 'A simple methodology for predicting laser-weld properties from "
                 "material and laser parameters', J. Phys. D: Appl. Phys. 44 (2011) 445401, "
                 "doi:10.1088/0022-3727/44/44/445401, Tables 2-4, Eq. (4)."),
    "license": "(c) 2011 IOP Publishing Ltd; values transcribed from printed tables; article not redistributed",
    "material": "AISI 304 (6 mm plate), 2 kW fibre laser bead-on-plate welds",
    "evidenceKind": "published measurement (printed table values) and published relations",
    "source": {"file": "hann2011.pdf", "bytes": 1211406,
               "sha256": "c00854f896f1e21ff81e750d77df0c191621782ff4c6846a471b933665fc84cc", "note": SOURCE_NOTE},
    "supplementaryNeeded": "None (no SI); the absorptivity eta and property values behind dH/hs are not stated.",
    "caveats": [
        "Welding, not LPBF: mm-scale spots (focus 320-960 um), 1-3 m/min. AISI 304 is not an app material, so the "
        "rows are not run through the app; they are used to check Hann's own printed depth relation.",
        "D in Tables 3-4 is the process-fibre diameter; the focus diameters 320/640/960 um are from the p. 2 text.",
        "delta* = depth/sigma with sigma the beam half-width at the surface (Table 1); depth itself is not printed.",
    ],
    "overlap": "Independent of the x-ray datasets (different process and material).",
}

# ---- published relations -----------------------------------------------------------------------------------------
REL_DIR = BENCHMARK_DIR / "keyhole-reference-relations-2026"
REL_TABLE = REL_DIR / "published_relations.csv"
REL_SHA256 = "85564cf60e576946ebcb6dd05c29d5fac8a66fc3bf353f6abb7de4c8c02e4452"
REL_COLUMNS = ["relation", "source_dataset", "relation_text", "constants", "uncertainty", "locator", "digitized"]

# Constants of the relations implemented below; the test checks them against published_relations.csv.
GAN_KE_CONDUCTION_MAX = 1.4
GAN_KE_KEYHOLE_MIN = 6.0
GAN_ASPECT_SLOPE = 0.4
GAN_ASPECT_OFFSET = 1.4
GAN_KE_STABLE_MAX = 16.0
GAN_KE_CHAOTIC_MIN = 30.0
GAN_ETA_MAX = 0.7
GAN_ETA_RATE = 0.6
HUANG_HM_TI64_J_MM3 = 6.26
HUANG_TI64_THRESHOLD = 8.0
HUANG_TI64_THRESHOLD_HALFWIDTH = 3.0
HANN_HV_HS_TI64 = 12.34


def _f(x: str) -> Optional[float]:
    return float(x) if x not in ("", None) else None


def _prov(base: Dict[str, Any], path: Path, rows: int, **extra: Any) -> Dict[str, Any]:
    prov = dict(base)
    prov.update(file=path.name, fileSha256=sha256_file(path), rows=rows, transcribed=TRANSCRIBED, **extra)
    return prov


def cunningham_lines(verify: bool = True) -> Dict[str, Dict[str, float]]:
    recs = _load_pinned_csv(CUN_LINES_TABLE, CUN_LINES_SHA256 if verify else sha256_file(CUN_LINES_TABLE),
                            CUN_LINES_COLUMNS, "Cunningham Fig. 3A")
    return {r["line"]: {"slope": float(r["slope_W_per_mm_s"]), "intercept": float(r["intercept_W"]),
                        "vmin": float(r["speed_min_mm_s"]), "vmax": float(r["speed_max_mm_s"]),
                        "readUncertainty_W": float(r["read_uncertainty_W"]), "spot_um": float(r["spot_um"]),
                        "meaning": r["meaning"], "locator": r["locator"], "digitized": r["digitized"] == "true"}
            for r in recs}


def cunningham_regime(power_W: float, speed_mm_s: float, lines: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    """Regime per Cunningham Fig. 3A (95 um spot): below blue = conduction, above red = keyhole, else transition.
    ``nearBoundary`` is True when P is within the read uncertainty of either line."""
    pb = lines["blue-dashed"]["slope"] * speed_mm_s + lines["blue-dashed"]["intercept"]
    pr = lines["red-dashed"]["slope"] * speed_mm_s + lines["red-dashed"]["intercept"]
    label = "conduction" if power_W < pb else "keyhole" if power_W > pr else "transition"
    tol = max(lines["blue-dashed"]["readUncertainty_W"], lines["red-dashed"]["readUncertainty_W"])
    return {"label": label, "blueLine_W": pb, "redLine_W": pr,
            "nearBoundary": abs(power_W - pb) <= tol or abs(power_W - pr) <= tol}


def load_cunningham_depths(verify: bool = True) -> Dict[str, Any]:
    recs = _load_pinned_csv(CUN_DEPTH_TABLE, CUN_DEPTH_SHA256 if verify else sha256_file(CUN_DEPTH_TABLE),
                            CUN_DEPTH_COLUMNS, "Cunningham Fig. 3B/3C")
    lines = cunningham_lines(verify)
    rows = []
    for r in recs:
        spot, P, v = float(r["spot_um"]), float(r["power_W"]), float(r["speed_mm_s"])
        reg = cunningham_regime(P, v, lines) if spot == lines["red-dashed"]["spot_um"] else None
        rows.append({"dataset": CUN_PROVENANCE["id"], "rowId": r["case"], "material": APP_MATERIAL_TI64,
                     "appEvaluable": True, "substrate": "bare plate", "power_W": P, "speed_mm_s": v,
                     "beamDiameter_um": spot, "preheat_C": ASSUMED_PREHEAT_C,
                     "vaporDepressionDepth_um": float(r["vapor_depression_depth_um"]),
                     "depthSd_um": _f(r["depth_sd_um"]), "readUncertainty_um": float(r["read_uncertainty_um"]),
                     "powerReadUncertainty_W": float(r["power_read_uncertainty_W"]),
                     "regimeReported": reg["label"] if reg else None,
                     "regimeNearBoundary": reg["nearBoundary"] if reg else None,
                     "regimeBasis": ("Fig. 3A blue/red transition lines (95 um spot)" if reg else
                                     "not reported (Fig. 3A lines are for the 95 um spot)"),
                     "locator": r["locator"], "digitized": r["digitized"] == "true"})
    return {"rows": rows, "provenance": _prov(CUN_PROVENANCE, CUN_DEPTH_TABLE, len(rows),
                                              linesFile=CUN_LINES_TABLE.name,
                                              linesFileSha256=sha256_file(CUN_LINES_TABLE))}


def load_zhao_boundary(verify: bool = True) -> Dict[str, Any]:
    recs = _load_pinned_csv(ZHAO_BOUNDARY_TABLE, ZHAO_BOUNDARY_SHA256 if verify else sha256_file(ZHAO_BOUNDARY_TABLE),
                            ZHAO_BOUNDARY_COLUMNS, "Zhao Fig. 1A boundary")
    rows = [{"dataset": ZHAO_PROVENANCE["id"], "rowId": r["case"], "material": APP_MATERIAL_TI64, "appEvaluable": True,
             "substrate": "bare plate" if r["setting"] == "bare" else "powder bed (~105 um layer)",
             "setting": r["setting"], "power_W": float(r["power_W"]), "speed_mm_s": float(r["speed_mm_s"]),
             "beamDiameter_um": float(r["spot_um"]), "preheat_C": ASSUMED_PREHEAT_C,
             "keyholeDepth_um": _f(r["keyhole_depth_um"]), "depthReadUncertainty_um": _f(r["depth_read_uncertainty_um"]),
             "regimeReported": "keyhole-porosity boundary", "locator": r["locator"],
             "digitized": r["digitized"] == "true"} for r in recs]
    return {"rows": rows, "provenance": _prov(ZHAO_PROVENANCE, ZHAO_BOUNDARY_TABLE, len(rows))}


def load_zhao_pores(verify: bool = True) -> Dict[str, Any]:
    recs = _load_pinned_csv(ZHAO_PORE_TABLE, ZHAO_PORE_SHA256 if verify else sha256_file(ZHAO_PORE_TABLE),
                            ZHAO_PORE_COLUMNS, "Zhao Fig. 1A pores")
    rows = [{"dataset": ZHAO_PROVENANCE["id"], "rowId": r["case"], "material": APP_MATERIAL_TI64, "appEvaluable": True,
             "power_W": float(r["power_W"]), "speed_mm_s": float(r["speed_mm_s"]),
             "beamDiameter_um": float(r["spot_um"]), "preheat_C": ASSUMED_PREHEAT_C,
             "barePlatePores": r["bare_plate_pores"] == "true", "powderBedPores": r["powder_bed_pores"] == "true",
             "regimeReported": "keyhole porosity (pores observed)", "locator": r["locator"],
             "digitized": r["digitized"] == "true"} for r in recs]
    return {"rows": rows, "provenance": _prov(ZHAO_PROVENANCE, ZHAO_PORE_TABLE, len(rows))}


def load_gan_cases(verify: bool = True) -> Dict[str, Any]:
    recs = _load_pinned_csv(GAN_TABLE, GAN_SHA256 if verify else sha256_file(GAN_TABLE), GAN_COLUMNS,
                            "Gan printed cases")
    rows = [{"dataset": GAN_PROVENANCE["id"], "rowId": r["case"], "material": r["material"], "appEvaluable": False,
             "substrate": r["substrate"], "power_W": float(r["power_W"]), "speed_mm_s": float(r["speed_mm_s"]),
             "beamDiameter_um": float(r["spot_um"]), "keyholeNumberPrinted": _f(r["keyhole_number_printed"]),
             "regimeReported": r["regime_reported"], "stabilityReported": r["stability_reported"] or None,
             "locator": r["locator"], "digitized": r["digitized"] == "true"} for r in recs]
    return {"rows": rows, "provenance": _prov(GAN_PROVENANCE, GAN_TABLE, len(rows))}


def load_gan_data1_ti64(verify: bool = True) -> Dict[str, Any]:
    """Gan 2021 Supplementary Data 1, Ti-6Al-4V rows as published (the Cunningham 2019 cases, Gan ref. 2).

    Used only as a cross-check of the digitized Cunningham depths and of Gan Eq. (2) with Gan's own Table 1 property
    set; these are the same measurements as ``load_cunningham_depths`` and are never counted as a second dataset.
    SI units as published (m, m/s, W); the loader adds um / mm/s convenience fields."""
    recs = _load_pinned_csv(GAN_DATA1_TABLE, GAN_DATA1_SHA256 if verify else sha256_file(GAN_DATA1_TABLE),
                            GAN_DATA1_COLUMNS, "Gan Supplementary Data 1 Ti-6Al-4V")
    rows = [{"dataset": "gan-keyhole-2021-supplementary-data1", "rowId": r["case"], "material": APP_MATERIAL_TI64,
             "power_W": float(r["P_W"]), "eta": float(r["eta"]), "speed_mm_s": float(r["V_m_s"]) * 1e3,
             "beamDiameter_um": round(float(r["d_m"]) * 1e6, 6), "r0_um": round(float(r["r0_m"]) * 1e6, 6),
             "keyholeDepth_um": round(float(r["e_m"]) * 1e6, 6), "lengthPublished_um": _f(r["length_um"]),
             "ganTable1": {"k_W_mK": float(r["k_W_mK"]), "rho_kg_m3": float(r["rho_kg_m3"]),
                           "cp_J_kgK": float(r["cp_J_kgK"]), "alpha_m2_s": float(r["alpha_m2_s"]),
                           "TlMinusT0_K": float(r["Tl_minus_T0_K"]), "TvMinusT0_K": float(r["Tv_minus_T0_K"])},
             "independentOfCunningham2019": False, "sameExperimentsAs": CUN_PROVENANCE["id"],
             "locator": r["locator"], "digitized": r["digitized"] == "true"} for r in recs]
    prov = {"id": "gan-keyhole-2021-supplementary-data1", "doi": "10.1038/s41467-021-22704-0",
            "license": "CC BY 4.0 (Nat. Commun. supplementary data); Ti-6Al-4V rows copied as published",
            "source": {"file": "gan2021_data1.xlsx", "sha256": GAN_DATA1_XLSX_SHA256, "note": SOURCE_NOTE},
            "overlap": "Cunningham 2019 Ti-6Al-4V cases (Gan ref. 2); cross-check only, never a second dataset.",
            "independentOfCunningham2019": False, "sameExperimentsAs": CUN_PROVENANCE["id"],
            "file": GAN_DATA1_TABLE.name, "fileSha256": sha256_file(GAN_DATA1_TABLE), "rows": len(rows),
            "transcribed": TRANSCRIBED}
    return {"rows": rows, "provenance": prov}


def load_huang_cases(verify: bool = True) -> Dict[str, Any]:
    recs = _load_pinned_csv(HUANG_TABLE, HUANG_SHA256 if verify else sha256_file(HUANG_TABLE), HUANG_COLUMNS,
                            "Huang printed cases")
    rows = [{"dataset": HUANG_PROVENANCE["id"], "rowId": r["case"], "material": r["material"], "appEvaluable": False,
             "substrate": r["substrate"], "power_W": float(r["power_W"]), "speed_mm_s": float(r["speed_mm_s"]),
             "beamDiameter_um": float(r["spot_um"]), "regimeReported": r["regime_reported"],
             "poresReported": r["pores_reported"] or None, "aedPrinted_MJ_m2": _f(r["aed_printed_MJ_m2"]),
             "locator": r["locator"], "digitized": r["digitized"] == "true"} for r in recs]
    return {"rows": rows, "provenance": _prov(HUANG_PROVENANCE, HUANG_TABLE, len(rows))}


def load_hann_welds(verify: bool = True) -> Dict[str, Any]:
    recs = _load_pinned_csv(HANN_TABLE, HANN_SHA256 if verify else sha256_file(HANN_TABLE), HANN_COLUMNS,
                            "Hann Tables 3-4")
    rows = [{"dataset": HANN_PROVENANCE["id"], "rowId": r["case"], "material": r["material"], "appEvaluable": False,
             "power_W": float(r["power_W"]), "speed_m_min": float(r["speed_m_min"]),
             "fibreDiameter_um": float(r["fibre_diameter_um"]), "focusDiameter_um": float(r["focus_diameter_um"]),
             "dHhsPrinted": float(r["dH_hs_printed"]), "deltaStarPrinted": float(r["delta_star_printed"]),
             "regimeReported": r["side_reported"], "locator": r["locator"], "digitized": r["digitized"] == "true"}
            for r in recs]
    return {"rows": rows, "provenance": _prov(HANN_PROVENANCE, HANN_TABLE, len(rows))}


def load_relations(verify: bool = True) -> Dict[str, Any]:
    recs = _load_pinned_csv(REL_TABLE, REL_SHA256 if verify else sha256_file(REL_TABLE), REL_COLUMNS,
                            "published keyhole relations")
    rows = []
    for r in recs:
        consts = {}
        for item in filter(None, r["constants"].split(";")):
            k, v = item.split("=")
            consts[k] = float(v)
        rows.append({"relation": r["relation"], "sourceDataset": r["source_dataset"], "text": r["relation_text"],
                     "constants": consts, "uncertainty": r["uncertainty"] or None, "locator": r["locator"],
                     "digitized": r["digitized"] == "true"})
    return {"rows": rows, "provenance": {"id": "keyhole-reference-relations-2026", "file": REL_TABLE.name,
                                         "fileSha256": sha256_file(REL_TABLE), "rows": len(rows),
                                         "transcribed": TRANSCRIBED,
                                         "evidenceKind": "published relations with fitted constants (transcribed)"}}


# ---- published relations, implemented (pure functions; properties are supplied by the caller) --------------------
def gan_keyhole_number(power_W: float, speed_mm_s: float, spot_um: float, rho: float, cp: float, k: float,
                       T_liq_C: float, T0_C: float, eta_min: float) -> Dict[str, float]:
    """Gan 2021 Eqs. (1), (6), (7). r0 = spot/2; eta from the flat minimum absorptivity eta_m (Eq. 6)."""
    v = speed_mm_s * 1e-3
    r0 = spot_um * 1e-6 / 2.0
    alpha = k / (rho * cp)
    dT = T_liq_C - T0_C
    ke_m_ld = eta_min * power_W / (dT * math.pi * rho * cp * v * r0 ** 2)
    eta = GAN_ETA_MAX * (1.0 - math.exp(-GAN_ETA_RATE * ke_m_ld))
    ke = eta * power_W / (dT * math.pi * rho * cp * math.sqrt(alpha * v * r0 ** 3))
    return {"Ke": ke, "eta": eta, "KemLd": ke_m_ld, "r0_um": r0 * 1e6}


def gan_regime(ke: float) -> str:
    return ("conduction" if ke < GAN_KE_CONDUCTION_MAX else "keyhole" if ke > GAN_KE_KEYHOLE_MIN else "transition")


def gan_keyhole_depth_um(ke: float, spot_um: float) -> float:
    """Gan Eq. (2): e = r0 * 0.4 (Ke - 1.4), floored at 0."""
    return max(0.0, GAN_ASPECT_SLOPE * (ke - GAN_ASPECT_OFFSET)) * spot_um / 2.0


def huang_enthalpy_product(power_W: float, speed_mm_s: float, spot_um: float, beta: float,
                           hm_J_mm3: float = HUANG_HM_TI64_J_MM3) -> float:
    """Huang 2022 dH/hm * Lth* = beta*P / (sqrt(pi) * hm * v * r^2), r = spot/2 (the diffusivity cancels)."""
    v = speed_mm_s * 1e-3
    r = spot_um * 1e-6 / 2.0
    return beta * power_W / (math.sqrt(math.pi) * hm_J_mm3 * 1e9 * v * r ** 2)


def hann_depth_relation_as_printed(dH_hs: float, hv_hs: float = 10.0) -> float:
    """Hann 2011 p. 4 piecewise delta*(dH/hs) exactly as printed (see the report: it does not reproduce Tables 3-4)."""
    if dH_hs <= 1.0:
        return 0.0
    if dH_hs <= hv_hs:
        return math.sqrt(dH_hs - 1.0)
    return math.sqrt(dH_hs - 10.0)


def hann_regime(app_index: float, hv_hs: float = HANN_HV_HS_TI64) -> str:
    """Hann's keyhole transition at dH/hs = Hv/hs, applied to an index of the same form (sigma = 1/e^2 radius)."""
    return "keyhole" if app_index > hv_hs else "not-keyhole"


# ---- registries -------------------------------------------------------------------------------------------------
LOADERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "cunningham-ti64-2019": load_cunningham_depths,
    "zhao-ti64-2020-boundary": load_zhao_boundary,
    "zhao-ti64-2020-pores": load_zhao_pores,
    "gan-keyhole-2021": load_gan_cases,
    "huang-al7a77-2022": load_huang_cases,
    "hann-ss304-2011": load_hann_welds,
}
PINNED_TABLES = {
    CUN_DEPTH_TABLE: CUN_DEPTH_SHA256, CUN_LINES_TABLE: CUN_LINES_SHA256,
    ZHAO_BOUNDARY_TABLE: ZHAO_BOUNDARY_SHA256, ZHAO_PORE_TABLE: ZHAO_PORE_SHA256,
    GAN_TABLE: GAN_SHA256, GAN_DATA1_TABLE: GAN_DATA1_SHA256, HUANG_TABLE: HUANG_SHA256, HANN_TABLE: HANN_SHA256,
    REL_TABLE: REL_SHA256,
}
EXPECTED_ROWS = {
    CUN_DEPTH_TABLE: 69, CUN_LINES_TABLE: 2, ZHAO_BOUNDARY_TABLE: 20, ZHAO_PORE_TABLE: 35, GAN_TABLE: 5,
    GAN_DATA1_TABLE: 71, HUANG_TABLE: 6, HANN_TABLE: 14, REL_TABLE: 19,
}
DATASET_DIRS = (CUN_DIR, ZHAO_DIR, GAN_DIR, HUANG_DIR, HANN_DIR, REL_DIR)


if __name__ == "__main__":
    for name, fn in LOADERS.items():
        d = fn()
        print(f"{name}: {d['provenance']['rows']} rows, {d['provenance']['file']} sha256 {d['provenance']['fileSha256']}")
    print("relations:", load_relations()["provenance"]["rows"])
