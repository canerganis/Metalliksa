#!/usr/bin/env python3
"""Loaders for melt-pool / absorptivity / thermal values transcribed from maintainer-supplied papers (wave 5).

Numbers only: the articles and their figures are not committed. Every committed CSV row carries a ``locator``
(table or figure panel of the source article) and a ``digitized`` flag; every CSV is SHA-256 pinned below and
refused when its bytes change. The SHA-256 of the maintainer-supplied PDF each table was read from is recorded
(the PDF itself is not redistributed).

Sources and what was taken (comparison inputs only; nothing here calibrates, validates or promotes a label):

* Ghosh et al. 2018, JOM 70, 1011 (doi:10.1007/s11837-018-2771-x): seven IN625 bare-plate single tracks.
  Width / depth are numbers PRINTED in Fig. 1 (not read off an axis; ``digitized=false``,
  ``value_origin`` says so). Melt-pool lengths are DIGITIZED from the Fig. 2 bar chart and live in a separate
  file (``digitized=true``).
* Trapp et al. 2017, Appl. Mater. Today 9, 341 (doi:10.1016/j.apmt.2017.08.006, CC BY 4.0): calorimetric
  effective absorptivity vs power (316L disc and powder, W and Al 1100 discs), all DIGITIZED from Figs. 4, 6, 7;
  316L bare-disc track width / depth at 500 mm/s DIGITIZED from Fig. 3(a) (separate file).
* Rubenchik et al. 2015, Appl. Opt. 54, 7230 (doi:10.1364/AO.54.007230): powder absorptivity vs temperature at
  970 nm (316 SS, Ti-6Al-4V, Al), DIGITIZED from Fig. 4 at 100 C steps.
* Ye et al. 2019, Adv. Eng. Mater. 21, 1900185 (doi:10.1002/adem.201900185): Table 1 minimal calorimetric
  absorptivity Am of bare Ti-6Al-4V, IN625 and 316L foils (table transcription).
* Heigel, Lane, Levine 2020, IMMI 9, 31 (doi:10.1007/s40192-020-00170-8): Table 2 cooling-rate summary of the
  AMB2018-01 IN625 3D builds (table transcription; thermal reference target, not melt-pool geometry).

Melt-pool rows use the same row shape as ``lpbf_public_datasets.load_lane_in625`` (power W, speed mm/s, beam
1/e^2 diameter um, layer um, preheat C, width/depth um) plus ``locator`` and ``digitized``. None of these sources
is in ``lpbf_calibration_config.TRAINABLE_SOURCES``: adding one changes the frozen config hash and needs a new
calibration version (see data/benchmark/README.md).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lpbf_public_datasets import (  # noqa: E402
    ASSUMED_PREHEAT_C, REPO_ROOT, _load_pinned_csv, sha256_file)

BENCHMARK_DIR = REPO_ROOT / "data" / "benchmark"
TRANSCRIBED = "2026-10-07"
SOURCE_NOTE = ("maintainer-supplied PDF copy, read locally on 2026-10-07; not committed (article not redistributed); "
               "the hash identifies the copy that was read, not a publisher original")

# ---- Ghosh et al. 2018 (IN625 single tracks) ------------------------------------------------------------------
GHOSH_DIR = BENCHMARK_DIR / "ghosh-in625-2018"
GHOSH_TRACKS_TABLE = GHOSH_DIR / "fig1_tracks.csv"
GHOSH_LENGTH_TABLE = GHOSH_DIR / "fig2_length_digitized.csv"
GHOSH_TRACKS_SHA256 = "79ee2d58b26c56dc88eadd5b1b0f73fb8f33e1b50a8f5eb73ac37d20e8487ce2"
GHOSH_LENGTH_SHA256 = "c4441be3525eb1dbc34dd51ce3862043a05636b29d62619709ca04372c2f0a29"
GHOSH_TRACK_COLUMNS = ["case", "power_W", "speed_mm_s", "width_um", "depth_um", "measurement_sd_um", "locator",
                       "digitized", "value_origin"]
GHOSH_LENGTH_COLUMNS = ["case", "power_W", "speed_mm_s", "length_um", "length_sd_um", "read_uncertainty_um", "locator",
                        "digitized"]
# The paper gives no experimental spot size; its FE model uses a Gaussian 1/e^2 RADIUS of 70 um (ref. 20).
GHOSH_MODEL_BEAM_DIAMETER_UM = 140.0
GHOSH_PROVENANCE = {
    "id": "ghosh-in625-2018", "doi": "10.1007/s11837-018-2771-x",
    "citation": ("S. Ghosh, L. Ma, L. E. Levine, R. E. Ricker, M. R. Stoudt, J. C. Heigel, J. E. Guyer, 'Single-Track "
                 "Melt-Pool Measurements and Microstructures in Inconel 625', JOM 70 (2018) 1011-1016, "
                 "doi:10.1007/s11837-018-2771-x, Fig. 1 (w, h labels) and Fig. 2 (measured lengths)."),
    "license": ("(c) 2018 The Minerals, Metals & Materials Society; values transcribed from the published article; "
                "article not redistributed"),
    "material": "Inconel 625",
    "evidenceKind": "published measurement (numbers printed in a figure; lengths digitized from a bar chart)",
    "source": {"file": "ghosh2018.pdf", "bytes": 853758,
               "sha256": "b89cd530b173102b00e090b09880b1b5b4ab3b5c558570fe302de329cd29bf0a", "note": SOURCE_NOTE},
    "caveats": [
        "Bare IN625 plate (25.4 x 25.4 x 3.2 mm, 400 grit, annealed 870 C / 1 h), no powder; seven 4 mm tracks; widths "
        "and depths from CLSM cross-sections at the track centre; stated SD about 1 um (p. 2).",
        "Power per case comes from the Fig. 2 power groups (case 1 = 49 W, cases 2-4 = 122 W, cases 5-7 = 195 W) and "
        "speed from the Fig. 1 scan-speed axis (200 / 500 / 800 mm/s); the text confirms case 5 = 195 W / 200 mm/s "
        "and case 7 = 195 W / 800 mm/s.",
        "The experimental spot size is not stated. beamDiameter_um = 140 is the paper's FE model input (1/e^2 radius "
        "70 um, its ref. 20), an ASSUMPTION for the experiment; Lane et al. 2020 give D4sigma 100 um for the NIST "
        "EOS M270 (CBM) used for AMB2018-02.",
        "Case 5 (195 W, 200 mm/s) is described as the onset of keyholing.",
        "Case 7 (195 W, 800 mm/s) has the nominal AM-Bench parameters: width 133 um and length ~0.82 mm agree with "
        "Lane 2020 CBM case B (133 um, 780 um) but the depth (38 um) is far below Lane's 91 um. The paper does not "
        "explain the difference; it is recorded, not resolved.",
        "Fig. 2 lengths are the thermography lengths of Heigel & Lane (MSEC 2017, the paper's ref. 4) for the same "
        "tracks, DIGITIZED from the bar chart (value = error-bar midpoint, SD = half error-bar span; read "
        "uncertainty about 5 um).",
        "Preheat not stated (20 C assumed; the FE model starts at 293 K).",
    ],
    "overlap": ("Not double-counted with lane-in625-2020: different tracks, plate and campaign (pre-AM-Bench 2017 "
                "tracks, cases 1-7) on the same laboratory's commercial machine; only case 7 shares nominal P/v with "
                "Lane CBM case B. Same laboratory, so not independent of Lane in machine/operator terms."),
}


def load_ghosh_in625(verify: bool = True, beam_diameter_um: float = GHOSH_MODEL_BEAM_DIAMETER_UM) -> Dict[str, Any]:
    """Seven melt-pool rows (Fig. 1 labels). Lengths: see ``load_ghosh_in625_lengths``."""
    records = _load_pinned_csv(GHOSH_TRACKS_TABLE, GHOSH_TRACKS_SHA256 if verify else sha256_file(GHOSH_TRACKS_TABLE),
                               GHOSH_TRACK_COLUMNS, "Ghosh Fig. 1")
    rows = []
    for r in records:
        rows.append({"dataset": GHOSH_PROVENANCE["id"], "rowId": f"ghosh-in625-case{int(r['case'])}",
                     "material": GHOSH_PROVENANCE["material"], "power_W": float(r["power_W"]),
                     "speed_mm_s": float(r["speed_mm_s"]), "beamDiameter_um": float(beam_diameter_um),
                     "layer_um": 0.0, "preheat_C": ASSUMED_PREHEAT_C,
                     "width_um": float(r["width_um"]), "depth_um": float(r["depth_um"]),
                     "widthSigma_um": float(r["measurement_sd_um"]), "depthSigma_um": float(r["measurement_sd_um"]),
                     "area_um2": None, "balling": None, "height_um": None, "hatch_um": None,
                     "case": int(r["case"]), "locator": r["locator"], "digitized": r["digitized"] == "true",
                     "valueOrigin": r["value_origin"], "source": "Ghosh 2018 Fig. 1"})
    prov = dict(GHOSH_PROVENANCE)
    prov.update(file=GHOSH_TRACKS_TABLE.name, fileSha256=sha256_file(GHOSH_TRACKS_TABLE), rows=len(rows),
                beamDiameterInput_um=float(beam_diameter_um), transcribed=TRANSCRIBED)
    return {"rows": rows, "provenance": prov}


def load_ghosh_in625_lengths(verify: bool = True) -> Dict[str, Any]:
    """Seven DIGITIZED melt-pool lengths (Fig. 2 bars)."""
    records = _load_pinned_csv(GHOSH_LENGTH_TABLE, GHOSH_LENGTH_SHA256 if verify else sha256_file(GHOSH_LENGTH_TABLE),
                               GHOSH_LENGTH_COLUMNS, "Ghosh Fig. 2")
    rows = [{"dataset": GHOSH_PROVENANCE["id"], "rowId": f"ghosh-in625-case{int(r['case'])}-length",
             "case": int(r["case"]), "power_W": float(r["power_W"]), "speed_mm_s": float(r["speed_mm_s"]),
             "length_um": float(r["length_um"]), "lengthSd_um": float(r["length_sd_um"]),
             "readUncertainty_um": float(r["read_uncertainty_um"]), "locator": r["locator"],
             "digitized": r["digitized"] == "true"} for r in records]
    prov = dict(GHOSH_PROVENANCE)
    prov.update(file=GHOSH_LENGTH_TABLE.name, fileSha256=sha256_file(GHOSH_LENGTH_TABLE), rows=len(rows),
                transcribed=TRANSCRIBED)
    return {"rows": rows, "provenance": prov}


# ---- Trapp et al. 2017 (calorimetric absorptivity; 316L track size) -----------------------------------------------
TRAPP_DIR = BENCHMARK_DIR / "trapp-316l-2017"
TRAPP_TRACKS_TABLE = TRAPP_DIR / "fig3a_tracks_digitized.csv"
TRAPP_ABS_TABLE = TRAPP_DIR / "absorptivity_digitized.csv"
TRAPP_TRACKS_SHA256 = "3a7bc34d75bb09bf41771331d116ce5d7e5ca0b7251aeb4d1e45c1e066a4ce7f"
TRAPP_ABS_SHA256 = "20473b090b33b816ddcdc6881ed1e70a8cb78feb2ebf188ae97c8c3ca174ddf9"
TRAPP_TRACK_COLUMNS = ["power_W", "power_label_W", "speed_mm_s", "spot_1e2_diameter_um", "width_um", "depth_um",
                       "read_uncertainty_power_W", "read_uncertainty_um", "locator", "digitized"]
TRAPP_ABS_COLUMNS = ["series", "material", "surface", "speed_mm_s", "power_W", "absorptivity",
                     "read_uncertainty_power_W", "read_uncertainty_absorptivity", "flag", "locator", "digitized"]
TRAPP_PROVENANCE = {
    "id": "trapp-316l-2017", "doi": "10.1016/j.apmt.2017.08.006",
    "citation": ("J. Trapp, A. M. Rubenchik, G. Guss, M. J. Matthews, 'In situ absorptivity measurements of metallic "
                 "powders during laser powder-bed fusion additive manufacturing', Applied Materials Today 9 (2017) "
                 "341-349, doi:10.1016/j.apmt.2017.08.006, Figs. 3(a), 4, 6, 7."),
    "license": ("CC BY 4.0 (open access, stated on the article); values transcribed from the published article; "
                "article not redistributed"),
    "material": "316L Stainless Steel",
    "evidenceKind": "published measurement (digitized from figures)",
    "source": {"file": "trapp2017.pdf", "bytes": 2797820,
               "sha256": "f305411d5746e27a1049b3c894ea1f82884b282d97d69110012894617baa3c06", "note": SOURCE_NOTE},
    "caveats": [
        "Every value is DIGITIZED from the article's raster figures (300 ppi JPEG): axes calibrated on the tick marks, "
        "symbol centroids found by colour masks. Cross-figure agreement of the same 316L series (Fig. 3(a) vs Fig. 4 "
        "at 500 mm/s; Figs. 4, 6(b), 7 at 1500 mm/s) is within 0.002 absorptivity; the stated read uncertainty is "
        "0.005 (0.008 for overlapping symbols), 0.5-1.5 W in power and 3 um in track size.",
        "Specimens: 10 mm discs laser-cut from 0.5 mm rolled 316L / W sheet and 0.6 mm Al 1100 sheet on a porous "
        "alumina holder; powder results are a 100 um layer of 316L powder in a machined cup. Not a semi-infinite "
        "plate: at 1500 mm/s some 316L discs were penetrated (rows flagged).",
        "Laser: 1070 nm cw Yb fibre, Gaussian 60 +- 5 um 1/e^2 diameter; argon flow; absorptivity = calorimetric "
        "energy / (P l / v), mean of two repeats (error bars are the two values, not digitized).",
        "Fig. 3(a) track width/depth at 500 mm/s: depth includes the keyhole regime above about 70 W (the paper's "
        "regimes I-III); there is no depth symbol at 117 W. Fig. 3(b) power labels are carried as power_label_W.",
        "Literature reference points drawn at P = 0 in Figs. 4 and 7 are not measurements of this work and are "
        "excluded.",
    ],
}


def load_trapp_316l_tracks(verify: bool = True) -> Dict[str, Any]:
    """Eleven DIGITIZED 316L bare-disc track rows (Fig. 3(a)); depth is None where no symbol is plotted."""
    records = _load_pinned_csv(TRAPP_TRACKS_TABLE, TRAPP_TRACKS_SHA256 if verify else sha256_file(TRAPP_TRACKS_TABLE),
                               TRAPP_TRACK_COLUMNS, "Trapp Fig. 3(a)")
    rows = []
    for r in records:
        rows.append({"dataset": TRAPP_PROVENANCE["id"], "rowId": f"trapp-316l-v500-p{int(r['power_W']):03d}",
                     "material": TRAPP_PROVENANCE["material"], "power_W": float(r["power_W"]),
                     "speed_mm_s": float(r["speed_mm_s"]), "beamDiameter_um": float(r["spot_1e2_diameter_um"]),
                     "layer_um": 0.0, "preheat_C": ASSUMED_PREHEAT_C,
                     "width_um": float(r["width_um"]), "depth_um": float(r["depth_um"]) if r["depth_um"] else None,
                     "widthSigma_um": None, "depthSigma_um": None, "area_um2": None, "balling": None,
                     "height_um": None, "hatch_um": None,
                     "powerLabel_W": float(r["power_label_W"]) if r["power_label_W"] else None,
                     "readUncertainty_um": float(r["read_uncertainty_um"]),
                     "readUncertaintyPower_W": float(r["read_uncertainty_power_W"]),
                     "locator": r["locator"], "digitized": r["digitized"] == "true", "source": "Trapp 2017 Fig. 3(a)"})
    prov = dict(TRAPP_PROVENANCE)
    prov.update(file=TRAPP_TRACKS_TABLE.name, fileSha256=sha256_file(TRAPP_TRACKS_TABLE), rows=len(rows),
                transcribed=TRANSCRIBED)
    return {"rows": rows, "provenance": prov}


def load_trapp_absorptivity(verify: bool = True) -> Dict[str, Any]:
    """107 DIGITIZED effective-absorptivity points in seven series (reference data, not melt-pool rows)."""
    records = _load_pinned_csv(TRAPP_ABS_TABLE, TRAPP_ABS_SHA256 if verify else sha256_file(TRAPP_ABS_TABLE),
                               TRAPP_ABS_COLUMNS, "Trapp absorptivity")
    rows = [{"dataset": TRAPP_PROVENANCE["id"], "series": r["series"], "material": r["material"],
             "surface": r["surface"], "speed_mm_s": float(r["speed_mm_s"]), "power_W": float(r["power_W"]),
             "absorptivity": float(r["absorptivity"]), "wavelength_nm": 1070.0, "spot_1e2_diameter_um": 60.0,
             "readUncertaintyPower_W": float(r["read_uncertainty_power_W"]),
             "readUncertaintyAbsorptivity": float(r["read_uncertainty_absorptivity"]), "flag": r["flag"] or None,
             "locator": r["locator"], "digitized": r["digitized"] == "true"} for r in records]
    prov = dict(TRAPP_PROVENANCE)
    prov.update(file=TRAPP_ABS_TABLE.name, fileSha256=sha256_file(TRAPP_ABS_TABLE), rows=len(rows),
                transcribed=TRANSCRIBED, kind="absorptivity reference (effective, calorimetric, scanning)")
    return {"rows": rows, "provenance": prov}


# ---- Rubenchik et al. 2015 (powder absorptivity vs temperature) ---------------------------------------------------
RUBENCHIK_DIR = BENCHMARK_DIR / "rubenchik-powder-2015"
RUBENCHIK_TABLE = RUBENCHIK_DIR / "fig4_powder_absorptivity_digitized.csv"
RUBENCHIK_SHA256 = "ad114f77c5c2da8649e18c81eff056f3e0a74ff54bad66800b7da7d92cb290c9"
RUBENCHIK_COLUMNS = ["series", "material", "sample", "irradiance_W_cm2", "run", "temperature_C", "absorptivity_median",
                     "absorptivity_p05", "absorptivity_p95", "read_uncertainty_absorptivity", "locator", "digitized"]
RUBENCHIK_PROVENANCE = {
    "id": "rubenchik-powder-2015", "doi": "10.1364/AO.54.007230",
    "citation": ("A. Rubenchik, S. Wu, S. Mitchell, I. Golosker, M. LeBlanc, N. Peterson, 'Direct measurements of "
                 "temperature-dependent laser absorptivity of metal powders', Applied Optics 54 (2015) 7230-7233, "
                 "doi:10.1364/AO.54.007230, Fig. 4(a)-(c)."),
    "license": ("(c) 2015 Optical Society of America; values transcribed from the published article; article not "
                "redistributed"),
    "material": "316 Stainless Steel / Ti-6Al-4V / Al powders",
    "evidenceKind": "published measurement (digitized from figure traces)",
    "source": {"file": "rubenchik2015.pdf", "bytes": 504722,
               "sha256": "ea25f3eeab52397640f8c7217d37a6a0af2ffad5bf8c8685723f3ad9db19027f", "note": SOURCE_NOTE},
    "caveats": [
        "Powder layers on a Ta disc heated uniformly by 970 nm VCSEL light (flat top, 1 cm aperture) at 8.7-13.8 "
        "W/cm^2, in air, up to about 500 C; no melting, no scanning. This is powder-bed absorptivity of a cold, "
        "unmelted layer, not melt-pool coupling.",
        "DIGITIZED from the vector traces of Fig. 4 rendered at 300 dpi: per trace, the median (and 5th / 95th "
        "percentile) absorptivity of the trace pixels within +-15 C of 100, 200, 300, 400 (and 500) C; read "
        "uncertainty 0.02 (trace noise and overplotting).",
        "Fig. 4(b) Ti-6Al-4V powder A, 8.9 W/cm^2 1st run is mostly hidden under the other traces and was not "
        "digitized. Run labels follow the legend: 1st / 2nd = repeat on the same sample.",
        "Text states the Ti-6Al-4V value is about 70 % and the 316 SS values agree with ray-tracing 58-60 %.",
    ],
}


def load_rubenchik_powder_absorptivity(verify: bool = True) -> Dict[str, Any]:
    records = _load_pinned_csv(RUBENCHIK_TABLE, RUBENCHIK_SHA256 if verify else sha256_file(RUBENCHIK_TABLE),
                               RUBENCHIK_COLUMNS, "Rubenchik Fig. 4")
    rows = [{"dataset": RUBENCHIK_PROVENANCE["id"], "series": r["series"], "material": r["material"],
             "sample": r["sample"], "irradiance_W_cm2": float(r["irradiance_W_cm2"]), "run": r["run"],
             "temperature_C": float(r["temperature_C"]), "absorptivity": float(r["absorptivity_median"]),
             "absorptivityP05": float(r["absorptivity_p05"]), "absorptivityP95": float(r["absorptivity_p95"]),
             "wavelength_nm": 970.0, "readUncertaintyAbsorptivity": float(r["read_uncertainty_absorptivity"]),
             "locator": r["locator"], "digitized": r["digitized"] == "true"} for r in records]
    prov = dict(RUBENCHIK_PROVENANCE)
    prov.update(file=RUBENCHIK_TABLE.name, fileSha256=sha256_file(RUBENCHIK_TABLE), rows=len(rows),
                transcribed=TRANSCRIBED, kind="absorptivity reference (powder layer, static, below melting)")
    return {"rows": rows, "provenance": prov}


# ---- Heigel, Lane, Levine 2020 (AMB2018-01 IN625 3D-build cooling rates) -----------------------------------------
HEIGEL_DIR = BENCHMARK_DIR / "heigel-in625-amb2018-01"
HEIGEL_TABLE = HEIGEL_DIR / "table2_cooling_rates.csv"
HEIGEL_SHA256 = "aeeb2ebe0f85fc47a6232719e44f0dbc76a06fe424aa63d6a1b9d0f00b0e6700"
HEIGEL_COLUMNS = ["feature", "feature_size_mm", "layers", "odd_n", "odd_mean_C_s", "odd_median_C_s", "odd_sd_C_s",
                  "even_n", "even_mean_C_s", "even_median_C_s", "even_sd_C_s", "locator", "digitized"]
HEIGEL_PROVENANCE = {
    "id": "heigel-in625-amb2018-01", "doi": "10.1007/s40192-020-00170-8",
    "citation": ("J. C. Heigel, B. M. Lane, L. E. Levine, 'In Situ Measurements of Melt-Pool Length and Cooling Rate "
                 "During 3D Builds of the Metal AM-Bench Artifacts', Integr. Mater. Manuf. Innov. 9 (2020) 31-53, "
                 "doi:10.1007/s40192-020-00170-8, Table 2."),
    "license": ("US Government work (stated on the article: text not subject to copyright protection in the United "
                "States); values transcribed from the published article; article not redistributed"),
    "material": "Inconel 625",
    "evidenceKind": "published measurement (thermography-derived, table transcription)",
    "source": {"file": "heigel2020.pdf", "bytes": 13025592,
               "sha256": "6b34fd0cf31a23d40520059b4c17aafc65ea0245d57477190c944b9a9428a34e", "note": SOURCE_NOTE},
    "caveats": [
        "3D build (AMB2018-01 bridge artifact, EOS M270, 195 W / 800 mm/s infill, D4sigma 100 um, 20 um layers, "
        "0.1 mm hatch), not single tracks; cooling rate = (1290 C - 1000 C) / time between the two true-temperature "
        "crossings per pixel, using the bare-plate solidus emissivity 0.221 from Lane et al.",
        "n = number of pixels; SD is the root sum square of the average measurement uncertainty and the pixel-to-pixel "
        "spread (Table 2 footnote). Odd layers scan along X, even layers along Y with 0.48-13 ms reheat gaps; the "
        "paper warns the two are not comparable to single-track values.",
        "The Table 2 caption does not say which of the two thermography builds (Build 1 / Build 2) the histograms "
        "come from.",
        "Melt-pool lengths in this paper are figure-only (Figs. 11-12, time-based per-pixel lengths) and were not "
        "digitized.",
    ],
}


def load_heigel_in625_cooling(verify: bool = True) -> Dict[str, Any]:
    records = _load_pinned_csv(HEIGEL_TABLE, HEIGEL_SHA256 if verify else sha256_file(HEIGEL_TABLE), HEIGEL_COLUMNS,
                               "Heigel Table 2")
    rows = []
    for r in records:
        for parity in ("odd", "even"):
            rows.append({"dataset": HEIGEL_PROVENANCE["id"], "feature": r["feature"],
                         "featureSize_mm": r["feature_size_mm"] or None, "layers": r["layers"], "layerParity": parity,
                         "n": int(r[f"{parity}_n"]), "mean_C_s": float(r[f"{parity}_mean_C_s"]),
                         "median_C_s": float(r[f"{parity}_median_C_s"]), "sd_C_s": float(r[f"{parity}_sd_C_s"]),
                         "locator": r["locator"], "digitized": r["digitized"] == "true"})
    prov = dict(HEIGEL_PROVENANCE)
    prov.update(file=HEIGEL_TABLE.name, fileSha256=sha256_file(HEIGEL_TABLE), rows=len(rows), tableRows=len(records),
                transcribed=TRANSCRIBED, kind="thermal reference target (3D-build cooling rate)")
    return {"rows": rows, "provenance": prov}


# ---- Ye et al. 2019 (minimal calorimetric absorptivity, Table 1) --------------------------------------------------
YE_DIR = BENCHMARK_DIR / "ye-2019-absorptivity"
YE_TABLE = YE_DIR / "table1_min_absorptivity.csv"
YE_SHA256 = "a6432fe813e02bd5ddb8615739944864dd678e5b63d9525a594bf759cc0a7367"
YE_COLUMNS = ["material", "substrate", "minimal_absorptivity_Am", "locator", "digitized"]
YE_PROVENANCE = {
    "id": "ye-2019-absorptivity", "doi": "10.1002/adem.201900185",
    "citation": ("J. Ye, S. A. Khairallah, A. M. Rubenchik, M. F. Crumb, G. Guss, J. Belak, M. J. Matthews, 'Energy "
                 "Coupling Mechanisms and Scaling Behavior Associated with Laser Powder Bed Fusion Additive "
                 "Manufacturing', Adv. Eng. Mater. 21 (2019) 1900185, doi:10.1002/adem.201900185, Table 1."),
    "license": ("(c) 2019 WILEY-VCH Verlag GmbH & Co. KGaA; values transcribed from the published article; article "
                "not redistributed"),
    "material": "Ti-6Al-4V / Inconel 625 / 316L Stainless Steel",
    "evidenceKind": "published measurement (table transcription)",
    "source": {"file": "ye2019.pdf", "bytes": 1270086,
               "sha256": "79dfa894705e72d44fde88937ab9387c7793b9586530bd7132723a73638c7a27", "note": SOURCE_NOTE},
    "caveats": [
        "Am is the minimum of the calorimetric effective absorptivity vs laser power on bare as-machined 0.5 mm foil "
        "discs (1 cm, Goodfellow), found in the conduction-to-keyhole transition; the paper reads it as an estimate of "
        "flat-melt absorptivity. Scanning 1/e^2 57 um beam, ~1 um wavelength (Table 1 caption).",
        "Only the 'in this work' row is transcribed; the A0 row of Table 1 is cited literature (its ref. 8), not a "
        "measurement of this work. Surface roughness Ra: Ti64 0.52, In625 0.13, SS316L 0.17 um (text).",
        "The absorptivity-vs-power curves (Fig. 1, Ti64) and melt-pool cross-sections (Fig. 2, Ti64 / In625) are "
        "figure-only and were not digitized in this lane.",
    ],
}


def load_ye_min_absorptivity(verify: bool = True) -> Dict[str, Any]:
    records = _load_pinned_csv(YE_TABLE, YE_SHA256 if verify else sha256_file(YE_TABLE), YE_COLUMNS, "Ye Table 1")
    rows = [{"dataset": YE_PROVENANCE["id"], "material": r["material"], "substrate": r["substrate"],
             "absorptivity": float(r["minimal_absorptivity_Am"]), "quantity": "minimal effective absorptivity Am",
             "locator": r["locator"], "digitized": r["digitized"] == "true"} for r in records]
    prov = dict(YE_PROVENANCE)
    prov.update(file=YE_TABLE.name, fileSha256=sha256_file(YE_TABLE), rows=len(rows), transcribed=TRANSCRIBED,
                kind="absorptivity reference (minimum effective absorptivity, scanning, bare foil)")
    return {"rows": rows, "provenance": prov}


# ---- registries -----------------------------------------------------------------------------------------------------
MELTPOOL_LOADERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "ghosh-in625-2018": load_ghosh_in625,
    "trapp-316l-2017": load_trapp_316l_tracks,
}
MELTPOOL_DIGITIZED = {"ghosh-in625-2018": False, "trapp-316l-2017": True}
REFERENCE_LOADERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "ghosh-in625-2018-lengths": load_ghosh_in625_lengths,
    "trapp-316l-2017-absorptivity": load_trapp_absorptivity,
    "rubenchik-powder-2015": load_rubenchik_powder_absorptivity,
    "heigel-in625-amb2018-01": load_heigel_in625_cooling,
    "ye-2019-absorptivity": load_ye_min_absorptivity,
}
PINNED_TABLES = {
    GHOSH_TRACKS_TABLE: GHOSH_TRACKS_SHA256, GHOSH_LENGTH_TABLE: GHOSH_LENGTH_SHA256,
    TRAPP_TRACKS_TABLE: TRAPP_TRACKS_SHA256, TRAPP_ABS_TABLE: TRAPP_ABS_SHA256,
    RUBENCHIK_TABLE: RUBENCHIK_SHA256, HEIGEL_TABLE: HEIGEL_SHA256, YE_TABLE: YE_SHA256,
}
# Papers that were read and deliberately not ingested (reason recorded; see data/benchmark/README.md).
NOT_INGESTED = {
    "levine2020": ("Levine et al. 2020 (doi:10.1007/s40192-019-00164-1) is the AM-Bench 2018 overview: its AMB2018-02 "
                   "melt-pool numbers are the Lane 2020 measurements already in lane-in625-amb2018-02 (Fig. 8 shows "
                   "percentage model errors only). Ingesting them would double-count."),
    "yadroitsev2010": ("Yadroitsev et al. 2010 (doi:10.1016/j.jmatprotec.2010.05.010) gives width/depth only as text "
                       "ranges for 304L fusion lines and as figures for 904L powder tracks (not an app alloy); the 316L "
                       "result is a categorical stability map (Fig. 11). No P/v-resolved melt-pool row for an app "
                       "alloy."),
    "lass2017": "IN625 microsegregation / delta-phase paper: segregation-model validation material only (not ingested).",
    "keller2017": "IN625 FE / phase-field / DICTRA paper: segregation-model validation material only (not ingested).",
    "simonds2021": ("Simonds et al. 2021 (doi:10.1016/j.apmt.2021.101049): time-resolved Ti-6Al-4V absorptance and "
                    "x-ray melt-pool geometry are figure-only; deferred to a follow-up digitization lane."),
}


def all_meltpool_rows(verify: bool = True) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for loader in MELTPOOL_LOADERS.values():
        out.extend(loader(verify=verify)["rows"])
    return out


if __name__ == "__main__":
    for name, fn in {**MELTPOOL_LOADERS, **REFERENCE_LOADERS}.items():
        d = fn()
        print(f"{name}: {d['provenance']['rows']} rows, {d['provenance']['file']} sha256 {d['provenance']['fileSha256']}")
