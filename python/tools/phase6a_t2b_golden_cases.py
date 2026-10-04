"""
Phase 6a tranche 2b golden cases: kinetics_ttt_cct_solver, stochastic_uq_mmpds_solver
and lpbf_fatigue_fracture. Merged into capture_phase6a_golden.CASES by one delimited
block there, so the tranche-2a cases (calphad, battery-eis, icme) merge trivially.

Base: the three solver files are byte-identical between d33b6f5 (the harness label,
capture_phase6a_golden.BASE_REVISION) and 7f3f803 (tranche 2 base), so the existing
blob binding holds unchanged (`git diff --stat d33b6f5 7f3f803 -- <files>` is empty).

Stochastic cases use the solver's fixed seed (42) and N=500 (PROOF.md:1044 baseline).
Key order matters there: composition elements map to Sobol dimensions in insertion
order. Golden files store "input" with sorted keys, so the regression test runs the
CASES payload below (original order), never the stored "input".
lpbf_fatigue_fracture has no __main__; it runs through MODULE_DRIVERS.
"""

from typing import Any, Dict

_UQ_COMMON = {"mcSamples": 500, "seed": 42, "samplingMethod": "sobol_qmc", "scramble": True}

CASES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "kinetics_ttt_cct_solver": {
        # PhaseKineticsTTTCCTStudio defaults (alloy "AISI 4140", 10 C/s, 25 um, 860 C, 720 C / 8 h).
        "aisi4140_ui_defaults": {
            "alloy": "AISI 4140", "coolingRate_C_s": 10.0, "grainSize_um": 25.0,
            "austTemp_C": 860.0, "agingTemp_C": 720.0, "agingTime_h": 8.0,
        },
        "aisi4340_slow_cool": {
            "alloy": "AISI 4340", "coolingRate_C_s": 0.5, "grainSize_um": 20.0,
            "austTemp_C": 845.0, "agingTemp_C": 600.0, "agingTime_h": 4.0,
        },
        "in718_lpbf_quench": {
            "alloy": "Inconel 718", "coolingRate_C_s": 1000.0, "grainSize_um": 35.0,
            "austTemp_C": 980.0, "agingTemp_C": 720.0, "agingTime_h": 8.0,
        },
        "ti64_beta_quench": {
            "alloy": "Ti-6Al-4V", "coolingRate_C_s": 500.0, "grainSize_um": 50.0,
            "austTemp_C": 1050.0, "agingTemp_C": 550.0, "agingTime_h": 4.0,
        },
        # Silent default today: an unknown alloy is solved with the AISI 4140 data.
        "edge_unknown_alloy": {"alloy": "Unobtainium XYZ", "coolingRate_C_s": 10.0},
    },
    "stochastic_uq_mmpds_solver": {
        # Solver defaults (IN718-like chemistry, baseMetal Ni), Seed42/N500 (PROOF.md:1044).
        "seed42_n500_defaults_ni": dict(_UQ_COMMON),
        # StochasticUQMMPDSStudio presets ti64_ams4928, steel4340_ams6414, alsi10mg_ams4215.
        "preset_ti64_ams4928": dict(
            _UQ_COMMON, alloyName="Ti-6Al-4V Grade 5 (AMS 4928)", baseMetal="Ti",
            standardSpec="AMS 4928 / MIL-T-9047", coolingRate_nominal=250000, coolingRate_cov=0.30,
            agingTemp_nominal=550, agingTemp_stdDev=8.0, agingTime_nominal=4, serviceStress_nominal=620,
            specMinYield_MPa=830, specMinUTS_MPa=900, specMinElongation_pct=10,
            composition_wt={"Al": 6.0, "V": 4.0, "Fe": 0.25, "C": 0.04, "Si": 0.05},
            composition_tolerances={"Al": 0.35, "V": 0.30, "Fe": 0.08, "C": 0.015, "Si": 0.02}),
        "preset_steel4340_ams6414": dict(
            _UQ_COMMON, alloyName="AISI 4340 Ultra-High Strength (AMS 6414)", baseMetal="Fe",
            standardSpec="AMS 6414 / MMPDS Ch. 2", coolingRate_nominal=250, coolingRate_cov=0.15,
            agingTemp_nominal=480, agingTemp_stdDev=5.0, agingTime_nominal=2, serviceStress_nominal=950,
            specMinYield_MPa=1380, specMinUTS_MPa=1520, specMinElongation_pct=9,
            composition_wt={"C": 0.40, "Cr": 0.80, "Ni": 1.80, "Mo": 0.25, "Mn": 0.70, "Si": 0.25},
            composition_tolerances={"C": 0.03, "Cr": 0.10, "Ni": 0.15, "Mo": 0.05, "Mn": 0.08, "Si": 0.05}),
        "preset_alsi10mg_ams4215": dict(
            _UQ_COMMON, alloyName="AlSi10Mg Additive (AMS 4215)", baseMetal="Al",
            standardSpec="AMS 4215 / ASTM F3318", coolingRate_nominal=600000, coolingRate_cov=0.35,
            agingTemp_nominal=160, agingTemp_stdDev=4.0, agingTime_nominal=6, serviceStress_nominal=180,
            specMinYield_MPa=220, specMinUTS_MPa=330, specMinElongation_pct=6,
            composition_wt={"Si": 10.0, "Mg": 0.45, "Fe": 0.15, "Ti": 0.05},
            composition_tolerances={"Si": 0.5, "Mg": 0.08, "Fe": 0.04, "Ti": 0.02}),
        # Silent default kept in step (a): an unknown baseMetal uses the Al lattice branch,
        # and an unlisted solute ("Zr") uses the 5.0 default potency.
        "edge_unknown_base_metal_zz": dict(
            _UQ_COMMON, alloyName="Unobtainium", baseMetal="Zz",
            composition_wt={"Zr": 1.0, "Cu": 2.0}, composition_tolerances={"Zr": 0.1, "Cu": 0.2}),
    },
    "lpbf_fatigue_fracture": {
        # MurakamiFatigueLab defaults (Ti-6Al-4V, 45 um, internal, R=-1, 240 MPa).
        "ti64_ui_defaults": {"alloyName": "Ti-6Al-4V", "sqrtArea_um": 45, "location": "internal",
                             "stressRatio_R": -1.0, "stressAmplitude_MPa": 240},
        "ss316l_surface_r01": {"alloyName": "316L SS", "sqrtArea_um": 120, "location": "surface",
                               "stressRatio_R": 0.1, "stressAmplitude_MPa": 180},
        "in718_subsurface": {"alloyName": "Inconel 718", "sqrtArea_um": 30, "location": "sub-surface",
                             "stressRatio_R": -1.0, "stressAmplitude_MPa": 300},
        "alsi10mg_large_pore": {"alloyName": "AlSi10Mg", "sqrtArea_um": 400, "location": "internal",
                                "stressRatio_R": 0.1, "stressAmplitude_MPa": 90},
        # Silent default today: an unknown alloy uses the Ti-6Al-4V constants.
        "edge_unknown_alloy": {"alloyName": "Unobtanium-X", "sqrtArea_um": 45},
    },
}

# Solvers without a __main__ run through a driver script (path relative to python/).
MODULE_DRIVERS: Dict[str, str] = {
    "lpbf_fatigue_fracture": "tools/phase6a_fatigue_golden_driver.py",
}


def _fatigue_table(table):
    return {name: dict(vars(row)) for name, row in table.items()}


# Solver-local tables snapshotted from the bound base blob (_source_tables.json).
TABLE_TARGETS = {
    "kinetics_ttt_cct_solver": ("ALLOY_KINETICS_DB", lambda t: t),
    "lpbf_fatigue_fracture": ("ALLOY_FATIGUE_DATABASE", _fatigue_table),
}

# (solver, case) -> validation error code expected after the structural migration.
EXPECTED_BEHAVIOUR_CHANGES = {
    ("kinetics_ttt_cct_solver", "edge_unknown_alloy"): "UNKNOWN_ALLOY",
    ("lpbf_fatigue_fracture", "edge_unknown_alloy"): "UNKNOWN_ALLOY",
}

# Documented value changes that a step_b re-bless may record although they are not
# bounded numeric drift: solver -> {drift-row key pattern: description}. Each listed row
# is checked exactly by capture_phase6a_golden.documented_change_violation against the
# re-blessed document (never by a looser bound); any other row keeps the default guard.
EXPECTED_DOCUMENTED_VALUE_CHANGES = {
    "kinetics_ttt_cct_solver": {
        r"cctContinuousCoolingMap\[\d+\]\.predictedHardness_HV":
            "HV = round(10.5 * HRC + 40) (unsourced) -> ASTM E140 Table 1 interpolation for the "
            "non-austenitic steels (AISI 4140/4340/D2) in HRC 20-68; null for other alloy "
            "classes and outside HRC 20-68",
        r"cctContinuousCoolingMap\[\d+\]\.predictedHardness_HV_status":
            "new status key next to predictedHardness_HV (converted / unavailable reason)",
    },
    # norm_ppf sign fix (audit D1): every normal input of the UQ run was drawn with sigma 0.776
    # instead of 1, so the sampled statistics, the Sobol-Saltelli indices and the two
    # reliability numbers that depend on them move. The rows are not bounded numerically; the
    # whole re-blessed document must equal a fresh run of the PINNED pre-fix solver blob
    # (f41e316, bound by sha256) with scipy.special.ndtri as the inverse normal, so a later
    # solver edit cannot match its own oracle (capture_phase6a_golden.documented_change_violation).
    "stochastic_uq_mmpds_solver": {
        r"stochasticProperties\..+":
            "statistics of the sampled model outputs (normal inputs drawn with the corrected norm_ppf)",
        r"sobolSensitivityAnalysis\[\d+\]\..+":
            "Sobol-Saltelli rows (values, and the parameter order that follows from the sort)",
        r"aerospaceReliability\.(yieldFailureProbability_Pf|hasoferLindBetaIndex|aBasisConforming|"
        r"bBasisConforming|cpkConforming|criticalFlawMedian_mm|criticalFlaw_P10_mm)":
            "reliability numbers derived from the sampled outputs",
    },
}
