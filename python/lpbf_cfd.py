"""LPBF Multiphysics CFD orchestration, case generation, and verification layer.

Integrates the OpenFOAM 14 multiphysics CFD solver (metalliksaMeltPoolFoam)
for two-phase metal-gas Volume of Fluid (VOF), Continuum Surface Force (CSF)
Laplace capillarity, enthalpy-based phase change, Carman-Kozeny mushy-zone
Darcy velocity damping, Marangoni tangential stress (Phase 2), and
Knight recoil pressure & Hertz-Knudsen evaporation (Phase 3).

Model ID:      multiphase-vof-csf-v1
Solver ID:     metalliksaMeltPoolFoam-OpenFOAM14-4
Marangoni ID:  tangential-dsigmadT-interface-v1
Recoil ID:     recoil-knight-clausius-v1

The test-only WSL probe, runner and verification case writers (droplet, Stefan,
Darcy, thermal parity, Marangoni, recoil, laser) live in lpbf_cfd_cases.py
(design 5c, B1); that module imports from this one, never the other way round.
"""

from pathlib import Path

CFD_SOLVER_ID = "metalliksaMeltPoolFoam-OpenFOAM14-4"
CFD_MODEL_ID = "multiphase-vof-csf-v1"
MARANGONI_MODEL_ID = "tangential-dsigmadT-interface-v1"
RECOIL_MODEL_ID = "recoil-knight-clausius-v1"

import platform

WSL_DISTRO = "Ubuntu-22.04"
WSL_BASHRC = "/opt/openfoam14/etc/bashrc"


def is_linux():
    """Return True if executing directly in Linux / WSL environment."""
    return platform.system() == "Linux"


def to_wsl_path(path):
    """Convert a Windows path or Path object to a WSL /mnt/... path."""
    p = Path(path).resolve()
    if is_linux():
        return str(p)
    drive = p.drive.replace(":", "").lower()
    parts = list(p.parts[1:])
    return f"/mnt/{drive}/" + "/".join(parts)


def foam_header(class_name, object_name, location="system"):
    """Generate standard OpenFOAM header."""
    return (
        "/*--------------------------------*- C++ -*----------------------------------*\\\n"
        "  =========                 |\n"
        "  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox\n"
        "   \\\\    /   O peration     | Website:  https://openfoam.org\n"
        "    \\\\  /    A nd           | Version:  14\n"
        "     \\\\/     M anipulation  |\n"
        "\\*---------------------------------------------------------------------------*/\n"
        "FoamFile\n"
        "{\n"
        "    format      ascii;\n"
        f"    class       {class_name};\n"
        f"    location    \"{location}\";\n"
        f"    object      {object_name};\n"
        "}\n"
        "// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //\n\n"
    )


def setup_cfd_multiphysics_case(p, m, folder):
    import math
    import numpy as np
    from lpbf_simulation import scan_segments
    folder = Path(folder)
    (folder/"system").mkdir(parents=True, exist_ok=True)
    (folder/"constant").mkdir(parents=True, exist_ok=True)
    (folder/"0").mkdir(parents=True, exist_ok=True)
    segments, end = scan_segments(p)
    radius = p["beamDiameter_um"]*.5e-6
    span = p["trackLength_um"]*1e-6+(p["tracks"]-1)*p["hatch_um"]*1e-6+6*radius
    nxy = math.ceil(span/(p["mesh_um"]*1e-6)); dx = span/nxy
    bottom = -math.ceil(max(300e-6, 4*radius)/dx)*dx
    nz = math.ceil((-bottom+p["layers"]*p["layer_um"]*1e-6)/dx)
    if nxy*nxy*nz > 200000: raise ValueError("OpenFOAM CFD cell budget exceeded (>200k cells)")
    z = bottom+(np.arange(nz)+.5)*dx
    counts = [int(np.sum(z < layer*p["layer_um"]*1e-6)) for layer in range(int(p["layers"])+1)]
    if any(b <= a for a,b in zip(counts,counts[1:])):
        raise ValueError("Mesh cannot resolve each powder layer; reduce mesh spacing below layer thickness")
    top = bottom+nz*dx
    corners = [(x, y, zz) for zz in (bottom, top) for x, y in ((-span/2, -span/2), (span/2, -span/2), (span/2, span/2), (-span/2, span/2))]
    vertices = "\n".join("(%s %s %s)" % point for point in corners)
    mesh = foam_header("dictionary", "blockMeshDict", "system")+f'''convertToMeters 1;
vertices ({vertices});
blocks (hex (0 1 2 3 4 5 6 7) ({nxy} {nxy} {nz}) simpleGrading (1 1 1));
edges ();
boundary (
    xMin {{ type patch; faces ((3 0 4 7)); }}
    xMax {{ type patch; faces ((1 2 6 5)); }}
    yMin {{ type wall; faces ((0 1 5 4)); }}
    yMax {{ type wall; faces ((2 3 7 6)); }}
    zMin {{ type wall; faces ((0 3 2 1)); }}
    zMax {{ type patch; faces ((4 5 6 7)); }}
);
mergePatchPairs ();
'''
    (folder/"system/blockMeshDict").write_text(mesh)
    
    cd = foam_header("dictionary", "controlDict", "system")
    cd += f'''application     metalliksaMeltPoolFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end};
deltaT          1e-8;
writeControl    adjustableRunTime;
writeInterval   {end/60};
purgeWrite      0;
writeFormat     ascii;
writePrecision  12;
writeCompression off;
timeFormat      general;
timePrecision   12;
runTimeModifiable false;
adjustTimeStep  yes;
maxCo           0.2;
maxAlphaCo      0.2;
maxDeltaT       {p["maxDt_s"]};
'''
    (folder/"system/controlDict").write_text(cd)

    (folder/"system/fvSchemes").write_text(foam_header("dictionary", "fvSchemes", "system") + '''
ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes { default none; 
    div(rhoPhi,U) Gauss linearUpwind grad(U);
    div(phi,alpha) Gauss interfaceCompression vanLeer 1;
    div(phirb,alpha) Gauss linear;
    div(rhoCpPhi,T) Gauss upwind;
    div(rhoLfPhi,liquidFraction) Gauss upwind;
}
laplacianSchemes { default Gauss linear orthogonal; }
interpolationSchemes { default linear; }
snGradSchemes { default orthogonal; }
''')
    (folder/"system/fvSolution").write_text(foam_header("dictionary", "fvSolution", "system") + '''
solvers {
    "alpha.metal.*" { 
        nCorrectors 2; 
        nSubCycles 1; 
        MULESCorr yes; 
        MULES { nIter 10; tolerance 1e-3; }
        solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0; 
    }
    pcorr { solver PCG; preconditioner DIC; tolerance 1e-5; relTol 0; }
    pcorrFinal { $pcorr; }
    "p_rgh.*" { solver PCG; preconditioner DIC; tolerance 1e-8; relTol 0; }
    "U.*" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-6; relTol 0; }
    "T.*" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-6; relTol 0; }
}
PIMPLE { nOuterCorrectors 1; nCorrectors 2; nNonOrthogonalCorrectors 0; }
''')

    (folder/"constant/g").write_text(foam_header("dictionary", "g", "constant") + "dimensions [0 1 -2 0 0 0 0];\nvalue (0 0 -9.81);\n")
    (folder/"constant/momentumTransport").write_text(foam_header("dictionary", "momentumTransport", "constant") + "simulationType laminar;\n")
    (folder/"constant/phaseProperties").write_text(foam_header("dictionary", "phaseProperties", "constant") + "phases (metal gas);\nsigma 1.52;\n")
    (folder/"constant/physicalProperties.metal").write_text(foam_header("dictionary", "physicalProperties.metal", "constant") + "viscosityModel constant;\nnu 7.5e-07;\nrho 4000;\n")
    (folder/"constant/physicalProperties.gas").write_text(foam_header("dictionary", "physicalProperties.gas", "constant") + "viscosityModel constant;\nnu 1.5e-05;\nrho 1.6;\n")
    
    tp = foam_header("dictionary", "thermalProperties", "constant")
    tp += f'''
kMetal          30.0;
kGas            0.026;
cpMetal         500.0;
cpGas           1000.0;
solidus_T       {m["solidus_K"]};
liquidus_T      {m["liquidus_K"]};
latentHeat      2.86e5;
Cmush           1e6;

sigma0          1.52;
dSigmaDT        -2.6e-4;
Tref_sigma      {m["liquidus_K"]};
interfaceThreshold 1e3;

// Evaporation/recoil/plume remain disabled until VOF mass transfer is closed.
active          false;
latentHeatVap   7.4e6;
boiling_T       {m["boiling_K"]};
molarMass       0.046;
evapCoeff       0.82;
P0              101325.0;
plumeMomentumScale {p.get("plumeMomentumScale", 1.0)};

laserActive     true;
laserPower      {p.get("power_W", 200.0)};
laserRadius     {radius};
laserAbsorptivity {m.get("absorptivity", 0.4)};
laserDirection  (0 0 -1);
useRayTracing   {"true" if p.get("useRayTracing", True) else "false"};
raysPerDim      {p.get("raysPerDim", 20)};

laserTStart     {len(segments)} ( {" ".join(str(s["start_s"]) for s in segments)} );
laserTEnd       {len(segments)} ( {" ".join(str(s["end_s"]) for s in segments)} );
laserPStart     {len(segments)} ( {" ".join(f'({s["start"][0]} {s["start"][1]} {(s["layer"]+1)*p["layer_um"]*1e-6})' for s in segments)} );
laserPEnd       {len(segments)} ( {" ".join(f'({s["end"][0]} {s["end"][1]} {(s["layer"]+1)*p["layer_um"]*1e-6})' for s in segments)} );
'''
    (folder/"constant/thermalProperties").write_text(tp)

    import sys
    import json
    sys.path.append(str(Path(__file__).parent))
    from powder_packer import generate_powder_bed, compute_powder_bed_statistics

    d10 = float(p.get("d10_um", 15)) * 1e-6
    d50 = float(p.get("d50_um", 30)) * 1e-6
    d90 = float(p.get("d90_um", 45)) * 1e-6
    target_packing = float(p.get("packingFraction", 0.55))
    seed = p.get("powderSeed", 42)
    powder_layer_z = p["layers"] * p["layer_um"] * 1e-6

    spheres = generate_powder_bed(span, span, powder_layer_z, d10=d10, d50=d50, d90=d90, target_packing=target_packing, seed=seed)
    powder_stats = compute_powder_bed_statistics(spheres, span, span, powder_layer_z)
    (folder/"powder_bed_info.json").write_text(json.dumps(powder_stats, indent=2))
    
    n_cells = nxy * nxy * nz
    x_c = -span/2 + (np.arange(nxy) + 0.5) * dx
    y_c = -span/2 + (np.arange(nxy) + 0.5) * dx
    ZZ, YY, XX = np.meshgrid(z, y_c, x_c, indexing='ij')
    
    alpha_np = np.zeros_like(ZZ)
    alpha_np[ZZ < 0] = 1.0
    
    for (sx, sy, sz, sr) in spheres:
        # powder_packer returns sx, sy in [ -span/2 + r, span/2 - r ]
        dist2 = (XX - sx)**2 + (YY - sy)**2 + (ZZ - sz)**2
        alpha_np[dist2 <= sr**2] = 1.0
        
    alpha_vals = [("1" if v > 0.5 else "0") for v in alpha_np.flatten()]
    joined_alpha = "\n".join(alpha_vals)
    am = foam_header("volScalarField", "alpha.metal", "0") + f'''
dimensions [0 0 0 0 0 0 0];
internalField nonuniform List<scalar>
{n_cells}
(
{joined_alpha}
);
boundaryField
{{
    xMin {{ type zeroGradient; }}
    xMax {{ type zeroGradient; }}
    yMin {{ type zeroGradient; }}
    yMax {{ type zeroGradient; }}
    zMin {{ type zeroGradient; }}
    zMax {{ type zeroGradient; }}
}}
'''
    (folder/"0/alpha.metal").write_text(am)
    
    (folder/"0/p_rgh").write_text(foam_header("volScalarField", "p_rgh", "0") + '''
dimensions [1 -1 -2 0 0 0 0];
internalField uniform 0;
boundaryField {
    xMin { type fixedFluxPressure; value uniform 0; }
    xMax { type fixedValue; value uniform 0; }
    yMin { type fixedFluxPressure; value uniform 0; }
    yMax { type fixedFluxPressure; value uniform 0; }
    zMin { type fixedFluxPressure; value uniform 0; }
    zMax { type fixedValue; value uniform 0; }
}
''')

    u_gas = float(p.get("shielding_gas_velocity_mps", 0.0))
    u_bcs = f'''
    xMin {{ type fixedValue; value uniform ({u_gas} 0 0); }}
    xMax {{ type inletOutlet; inletValue uniform (0 0 0); value uniform ({u_gas} 0 0); }}
    yMin {{ type noSlip; }}
    yMax {{ type noSlip; }}
    zMin {{ type noSlip; }}
    zMax {{ type inletOutlet; inletValue uniform ({u_gas} 0 0); value uniform ({u_gas} 0 0); }}
    ''' if u_gas > 0.0 else '''
    xMin { type noSlip; }
    xMax { type noSlip; }
    yMin { type noSlip; }
    yMax { type noSlip; }
    zMin { type noSlip; }
    zMax { type noSlip; }
    '''

    (folder/"0/U").write_text(foam_header("volVectorField", "U", "0") + f'''
dimensions [0 1 -1 0 0 0 0];
internalField uniform ({u_gas} 0 0);
boundaryField {{ {u_bcs} }}
''')

    (folder/"0/T").write_text(foam_header("volScalarField", "T", "0") + f'''
dimensions [0 0 0 1 0 0 0];
internalField uniform {p.get("preheat_C", 20.0) + 273.15};
boundaryField {{
    xMin {{ type fixedValue; value uniform {p.get("preheat_C", 20.0) + 273.15}; }}
    xMax {{ type zeroGradient; }}
    yMin {{ type zeroGradient; }}
    yMax {{ type zeroGradient; }}
    zMin {{ type zeroGradient; }}
    zMax {{ type inletOutlet; inletValue uniform {p.get("preheat_C", 20.0) + 273.15}; value uniform {p.get("preheat_C", 20.0) + 273.15}; }}
}}
''')

    (folder/"0/liquidFraction").write_text(foam_header("volScalarField", "liquidFraction", "0") + '''
dimensions [0 0 0 0 0 0 0];
internalField uniform 0;
boundaryField {
    xMin { type zeroGradient; }
    xMax { type zeroGradient; }
    yMin { type zeroGradient; }
    yMax { type zeroGradient; }
    zMin { type zeroGradient; }
    zMax { type zeroGradient; }
}
''')

    return dx, segments

def cfd_multiphysics(p, m, report=lambda *args: None, artifact_dir=None):
    if artifact_dir is None:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="metalliksa-cfd-") as tmp:
            return cfd_multiphysics(p, m, report, tmp)
    folder = Path(artifact_dir)/"openfoam-cfd-case"
    dx, segments = setup_cfd_multiphysics_case(p, m, folder)
    
    script = 'source /opt/openfoam14/etc/bashrc; blockMesh -case "$1" && checkMesh -case "$1" && "$2" -case "$1"'
    import subprocess
    BINARY_CFD = Path(__file__).parent/'openfoam/bin/metalliksaMeltPoolFoam'
    wsl_folder = to_wsl_path(folder)
    wsl_bin = to_wsl_path(BINARY_CFD)
    
    cmd_str = f'source /opt/openfoam14/etc/bashrc; blockMesh -case "{wsl_folder}" && checkMesh -case "{wsl_folder}" && "{wsl_bin}" -case "{wsl_folder}"'
    runner = ["bash", "-c", cmd_str] if is_linux() else ["wsl", "-d", WSL_DISTRO, "--", "bash", "-c", cmd_str]
    
    child = subprocess.Popen(runner, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    with (folder/"solver.log").open("w") as log:
        for line in child.stdout:
            log.write(line)
            if "Time = " in line:
                try:
                    t_str = line.split("Time = ")[1].strip()
                    t = float(t_str)
                    report(t/segments[-1]["end_s"], "CFD t="+t_str)
                except:
                    pass
        code = child.wait()
    if code:
        raise ValueError("OpenFOAM CFD failed: "+(folder/"solver.log").read_text()[-2500:])
    
    import json
    try:
        diag = json.loads((folder/"cfd-diagnostics.json").read_text())
    except:
        diag = {}

    try:
        powder_info = json.loads((folder/"powder_bed_info.json").read_text())
        diag["powderBed"] = powder_info
    except:
        pass

    # Phase 8: read solidification microstructure JSON
    solidification_data = {}
    try:
        solidification_data = json.loads((folder/"solidification-microstructure.json").read_text())
    except:
        pass
        
    return dict(metrics=dict(), thermalHistory=[], fieldSeries=[],
                fieldOverlapDiagnostics=dict(),
                numericalDiagnostics=diag,
                solidificationMicrostructure=solidification_data,
                energyBalance=dict(), discretization=dict(mesh_m=dx), scanPath=segments)
