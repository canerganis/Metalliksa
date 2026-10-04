#!/usr/bin/env python3
"""
MetalliX Python HPC Subsystem Dispatcher
Coordinates CPU-intensive calculations: CALPHAD Gibbs Minimization, DFT Elastic Tensors, etc.
"""

import sys
import json
import os
import platform

def get_system_status():
    return {
        "status": "online",
        "pythonVersion": platform.python_version(),
        "platform": platform.platform(),
        "subsystems": {
            "calphad_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "calphad_solver.py")),
                "description": "Multi-component CALPHAD Gibbs free energy minimizer, Scheil-Gulliver & New-PHACOMP solver"
            },
            "dft_property_calculator": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "dft_property_calculator.py")),
                "description": "Continuum elasticity of supplied single-crystal C_ij (not DFT): Voigt-Reuss-Hill, Born stability, per-atom Anderson Debye temperature & anisotropy"
            },
            "cnls_fitting_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "cnls_fitting_solver.py")),
                "description": "Complex Non-Linear Least Squares (CNLS) Levenberg-Marquardt impedance optimizer & Kramers-Kronig Lin-KK test"
            },
            "xrd_peak_deconvolution": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "xrd_peak_deconvolution.py")),
                "description": "Pseudo-Voigt & Pearson-VII peak deconvolution, Ka1/Ka2 Rachinger stripping, Williamson-Hall microstrain & dislocation density"
            },
            "lpbf_thermal_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "lpbf_thermal_solver.py")),
                "description": "3D Goldak moving laser melt pool, thermal gradient G, solidification rate R, cooling rate G*R & Hunt microstructure"
            },
            "lpbf_build_job_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "lpbf_build_job_solver.py")),
                "description": "Single LPBF Build Job: Rosenthal screening, STL slicer, literature P-v box, print verdict"
            },
            "inverse_alloy_optimizer": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "inverse_alloy_optimizer.py")),
                "description": "Multi-Objective Pareto Genetic Algorithm (NSGA-II) for superalloy & HEA chemistry inverse optimization"
            },
            "pourbaix_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "pourbaix_solver.py")),
                "description": "Multi-Element Nernst E-pH electrochemical equilibrium, corrosion/passivation/immunity stability map"
            },
            "kinetics_ttt_cct_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "kinetics_ttt_cct_solver.py")),
                "description": "Johnson-Mehl-Avrami-Kolmogorov (JMAK) TTT C-curves, Scheil CCT continuous cooling, LSW coarsening & CALPHAD vs Kinetics gap"
            },
            "icme_multiscale_pipeline_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "icme_multiscale_pipeline_solver.py")),
                "description": "End-to-end ICME Digital Thread: DFT Atomistic (C_ij) -> CALPHAD Solute Misfit -> Kinetics/Solidification -> Dislocation/Orowan Microstructure -> Macro FEA & CAE Material Cards"
            },
            "stochastic_uq_mmpds_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "stochastic_uq_mmpds_solver.py")),
                "description": "High-dimensional Monte Carlo Uncertainty Quantification, Sobol sensitivity decomposition, and MMPDS-01 A/B-Basis design allowable qualification"
            },
            "marangoni_pore_instability_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "marangoni_pore_instability_solver.py")),
                "description": "3D Marangoni flow thermocapillary instability, surfactant dγ/dT inversion, and 3D gas entrapment pore probability heatmap"
            },
            "part_scale_inherent_strain_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "part_scale_inherent_strain_solver.py")),
                "description": "3D CAD/STL multi-layer slicer & part-scale progressive Inherent Strain (ISM) FEA residual stress, springback warpage & recoater crash predictor"
            },
            "tafel_corrosion_rate_solver": {
                "available": os.path.exists(os.path.join(os.path.dirname(__file__), "tafel_corrosion_rate_solver.py")),
                "description": "ASTM G102 & G59 Automated Annual Corrosion Rate (mm/year), Stern-Geary kinetics & Faraday penetration solver"
            }
        }
    }

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps(get_system_status()))
    else:
        print(json.dumps(get_system_status()))
