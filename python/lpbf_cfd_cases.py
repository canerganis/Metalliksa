"""Test-only OpenFOAM CFD verification helpers and case writers.

Moved unchanged from lpbf_cfd.py (design 5c, B1): the WSL capability probe and
runner, the droplet / Stefan / Darcy / thermal-parity / Marangoni / recoil /
laser verification case writers, their field readers and analytical oracles.
Only test_lpbf_cfd.py and the parity harness (G10) use them. This module is NOT
part of lpbf_simulation.IMPLEMENTATION_SOURCE_FILES, and no manifest file may
import it (test_lpbf_implementation_fingerprint FORBIDDEN_MANIFEST_IMPORTS).
It imports from lpbf_cfd, never the other way round.
"""

import json
import math
import os
import subprocess
from pathlib import Path

from lpbf_cfd import (
    CFD_MODEL_ID,
    CFD_SOLVER_ID,
    WSL_BASHRC,
    WSL_DISTRO,
    foam_header,
    is_linux,
    to_wsl_path,
)

WSL_SOLVER_BIN = "/mnt/c/Users/can02/OneDrive/Desktop/Uşağım/metalliksaa/Metalliksa-1/python/openfoam/bin/metalliksaMeltPoolFoam"


def verify_cfd_capability():
    """Verify if WSL, OpenFOAM 14, and metalliksaMeltPoolFoam binary are operational."""
    cmd = (
        f"source {WSL_BASHRC} 2>/dev/null && "
        f"[ -x {WSL_SOLVER_BIN} ] && "
        f"{WSL_SOLVER_BIN} -help 2>&1 | grep -i OpenFOAM"
    )
    try:
        runner = ["bash", "-c", cmd] if is_linux() else ["wsl", "-d", WSL_DISTRO, "--", "bash", "-c", cmd]
        res = subprocess.run(
            runner,
            capture_output=True,
            text=True,
            timeout=15,
        )
        has_bin = res.returncode == 0 and "OpenFOAM" in res.stdout
        return {
            "available": has_bin,
            "solverId": CFD_SOLVER_ID,
            "modelId": CFD_MODEL_ID,
            "binary": WSL_SOLVER_BIN,
            "details": res.stdout.strip(),
        }
    except Exception as err:
        return {
            "available": False,
            "solverId": CFD_SOLVER_ID,
            "modelId": CFD_MODEL_ID,
            "error": str(err),
        }


def run_wsl_command(cmd, timeout_s=120):
    """Run a shell command inside WSL with OpenFOAM environment loaded."""
    full_cmd = f"source {WSL_BASHRC} && {cmd}"
    runner = ["bash", "-c", full_cmd] if is_linux() else ["wsl", "-d", WSL_DISTRO, "--", "bash", "-c", full_cmd]
    res = subprocess.run(
        runner,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    return res


def setup_droplet_case(
    case_dir,
    radius_m=25e-6,
    sigma=1.7,
    domain_m=100e-6,
    n_cells=20,
    end_time=4e-7,
    dt=2e-7,
):
    """Generate a 2D static liquid metal droplet case in gas to verify Laplace pressure jump and volume conservation."""
    c_dir = Path(case_dir)
    os.makedirs(c_dir / "0", exist_ok=True)
    os.makedirs(c_dir / "constant", exist_ok=True)
    os.makedirs(c_dir / "system", exist_ok=True)

    half = domain_m / 2.0
    dz = domain_m / n_cells

    # 1. system/blockMeshDict
    bm = foam_header("dictionary", "blockMeshDict", "system")
    bm += f"""convertToMeters 1;

vertices
(
    ({-half} {-half} 0)
    ({half} {-half} 0)
    ({half} {half} 0)
    ({-half} {half} 0)
    ({-half} {-half} {dz})
    ({half} {-half} {dz})
    ({half} {half} {dz})
    ({-half} {half} {dz})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({n_cells} {n_cells} 1) simpleGrading (1 1 1)
);

edges ();

boundary
(
    walls
    {{
        type wall;
        faces
        (
            (0 4 7 3)
            (1 2 6 5)
            (0 1 5 4)
            (3 7 6 2)
        );
    }}
    frontAndBack
    {{
        type empty;
        faces
        (
            (0 3 2 1)
            (4 5 6 7)
        );
    }}
);
"""
    (c_dir / "system" / "blockMeshDict").write_text(bm, encoding="utf-8")

    # 2. system/controlDict
    cd = foam_header("dictionary", "controlDict", "system")
    cd += f"""application     metalliksaMeltPoolFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          {dt};
writeControl    timeStep;
writeInterval   1;
purgeWrite      0;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
"""
    (c_dir / "system" / "controlDict").write_text(cd, encoding="utf-8")

    # 3. system/fvSchemes
    fs = foam_header("dictionary", "fvSchemes", "system")
    fs += """ddtSchemes
{
    default         Euler;
}
gradSchemes
{
    default         Gauss linear;
}
divSchemes
{
    div(phi,alpha)  Gauss interfaceCompression vanLeer 1;
    div(rhoPhi,U)   Gauss linearUpwind grad(U);
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
    div(rhoCpPhi,T) Gauss upwind;
    div(rhoLfPhi,liquidFraction) Gauss upwind;
}
laplacianSchemes
{
    default         Gauss linear uncorrected;
}
interpolationSchemes
{
    default         linear;
}
snGradSchemes
{
    default         uncorrected;
}
"""
    (c_dir / "system" / "fvSchemes").write_text(fs, encoding="utf-8")

    # 4. system/fvSolution
    fsol = foam_header("dictionary", "fvSolution", "system")
    fsol += """solvers
{
    "alpha.metal.*"
    {
        nCorrectors     2;
        nSubCycles      1;
        MULESCorr       yes;
        MULES
        {
            nIter           10;
            tolerance       1e-3;
        }
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0;
    }
    pcorr
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-5;
        relTol          0;
    }
    pcorrFinal
    {
        $pcorr;
    }
    p_rgh
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-7;
        relTol          0.01;
    }
    p_rghFinal
    {
        $p_rgh;
        relTol          0;
    }
    "(U|T).*"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0;
    }
}
PIMPLE
{
    momentumPredictor no;
    nOuterCorrectors 1;
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
    pRefCell        0;
    pRefValue       0;
    p_rghRefCell    0;
    p_rghRefValue   0;
}
"""
    (c_dir / "system" / "fvSolution").write_text(fsol, encoding="utf-8")

    # 5. constant/phaseProperties
    pp = foam_header("dictionary", "phaseProperties", "constant")
    pp += f"""phases          (metal gas);
sigma           {sigma};
"""
    (c_dir / "constant" / "phaseProperties").write_text(pp, encoding="utf-8")

    # 6. constant/physicalProperties.metal & gas
    pm = foam_header("dictionary", "physicalProperties.metal", "constant")
    pm += """viscosityModel  constant;
nu              7.5e-07;
rho             7900;
"""
    (c_dir / "constant" / "physicalProperties.metal").write_text(pm, encoding="utf-8")

    pg = foam_header("dictionary", "physicalProperties.gas", "constant")
    pg += """viscosityModel  constant;
nu              1.5e-05;
rho             1.2;
"""
    (c_dir / "constant" / "physicalProperties.gas").write_text(pg, encoding="utf-8")

    # 7. constant/momentumTransport
    mt = foam_header("dictionary", "momentumTransport", "constant")
    mt += """simulationType  laminar;
"""
    (c_dir / "constant" / "momentumTransport").write_text(mt, encoding="utf-8")

    # 8. constant/g
    g_str = foam_header("dictionary", "g", "constant")
    g_str += """dimensions      [acceleration];
value           (0 0 0);
"""
    (c_dir / "constant" / "g").write_text(g_str, encoding="utf-8")

    # 9. constant/thermalProperties
    tp = foam_header("dictionary", "thermalProperties", "constant")
    tp += """kMetal          30.0;
kGas            0.026;
cpMetal         500.0;
cpGas           1000.0;
solidus_T       1650.0;
liquidus_T      1700.0;
latentHeat      2.7e5;
Cmush           1e6;
"""
    (c_dir / "constant" / "thermalProperties").write_text(tp, encoding="utf-8")

    # 10. 0/ fields: alpha.metal, U, p_rgh, T
    alpha_cells = []
    dx = domain_m / n_cells
    for j in range(n_cells):
        y = -half + (j + 0.5) * dx
        for i in range(n_cells):
            x = -half + (i + 0.5) * dx
            dist = math.sqrt(x * x + y * y)
            if dist < radius_m - 0.5 * dx:
                alpha_cells.append(1.0)
            elif dist > radius_m + 0.5 * dx:
                alpha_cells.append(0.0)
            else:
                frac = (radius_m + 0.5 * dx - dist) / dx
                alpha_cells.append(max(0.0, min(1.0, frac)))

    total_cells = len(alpha_cells)
    cell_values_str = "\n".join(str(v) for v in alpha_cells)

    am = foam_header("volScalarField", "alpha.metal", "0")
    am += f"""dimensions      [];
internalField   nonuniform List<scalar>
{total_cells}
(
{cell_values_str}
);
boundaryField
{{
    walls
    {{
        type            zeroGradient;
    }}
    frontAndBack
    {{
        type            empty;
    }}
}}
"""
    (c_dir / "0" / "alpha.metal").write_text(am, encoding="utf-8")

    prgh = foam_header("volScalarField", "p_rgh", "0")
    prgh += """dimensions      [pressure];
internalField   uniform 0;
boundaryField
{
    walls
    {
        type            fixedFluxPressure;
        value           uniform 0;
    }
    frontAndBack
    {
        type            empty;
    }
}
"""
    (c_dir / "0" / "p_rgh").write_text(prgh, encoding="utf-8")

    uf = foam_header("volVectorField", "U", "0")
    uf += """dimensions      [velocity];
internalField   uniform (0 0 0);
boundaryField
{
    walls
    {
        type            noSlip;
    }
    frontAndBack
    {
        type            empty;
    }
}
"""
    (c_dir / "0" / "U").write_text(uf, encoding="utf-8")

    tf = foam_header("volScalarField", "T", "0")
    tf += """dimensions      [temperature];
internalField   uniform 1800;
boundaryField
{
    walls
    {
        type            zeroGradient;
    }
    frontAndBack
    {
        type            empty;
    }
}
"""
    (c_dir / "0" / "T").write_text(tf, encoding="utf-8")

    lf_cells = [1.0 if a > 0.5 else 0.0 for a in alpha_cells]
    lf_str = "\n".join(str(v) for v in lf_cells)
    lff = foam_header("volScalarField", "liquidFraction", "0")
    lff += f"""dimensions      [];
internalField   nonuniform List<scalar>
{total_cells}
(
{lf_str}
);
boundaryField
{{
    walls
    {{
        type            zeroGradient;
    }}
    frontAndBack
    {{
        type            empty;
    }}
}}
"""
    (c_dir / "0" / "liquidFraction").write_text(lff, encoding="utf-8")


def setup_stefan_case(
    case_dir,
    length_m=100e-6,
    t_hot=1800.0,
    t_init=1600.0,
    tm=1650.0,
    n_cells=20,
    end_time=1e-5,
    dt=2e-6,
):
    """Generate a 1D melting Stefan benchmark case in a pure metal domain."""
    c_dir = Path(case_dir)
    os.makedirs(c_dir / "0", exist_ok=True)
    os.makedirs(c_dir / "constant", exist_ok=True)
    os.makedirs(c_dir / "system", exist_ok=True)

    dx = length_m / n_cells
    dz = dx

    # 1. blockMeshDict
    bm = foam_header("dictionary", "blockMeshDict", "system")
    bm += f"""convertToMeters 1;

vertices
(
    (0 0 0)
    ({length_m} 0 0)
    ({length_m} {dx} 0)
    (0 {dx} 0)
    (0 0 {dz})
    ({length_m} 0 {dz})
    ({length_m} {dx} {dz})
    (0 {dx} {dz})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({n_cells} 1 1) simpleGrading (1 1 1)
);

edges ();

boundary
(
    hotWall
    {{
        type wall;
        faces ((0 4 7 3));
    }}
    coldWall
    {{
        type wall;
        faces ((1 2 6 5));
    }}
    sides
    {{
        type wall;
        faces
        (
            (0 1 5 4)
            (3 7 6 2)
        );
    }}
    frontAndBack
    {{
        type empty;
        faces
        (
            (0 3 2 1)
            (4 5 6 7)
        );
    }}
);
"""
    (c_dir / "system" / "blockMeshDict").write_text(bm, encoding="utf-8")

    # 2. controlDict
    cd = foam_header("dictionary", "controlDict", "system")
    cd += f"""application     metalliksaMeltPoolFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          {dt};
writeControl    timeStep;
writeInterval   1;
purgeWrite      0;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
"""
    (c_dir / "system" / "controlDict").write_text(cd, encoding="utf-8")

    # 3. fvSchemes
    fs = foam_header("dictionary", "fvSchemes", "system")
    fs += """ddtSchemes
{
    default         Euler;
}
gradSchemes
{
    default         Gauss linear;
}
divSchemes
{
    div(phi,alpha)  Gauss interfaceCompression vanLeer 1;
    div(rhoPhi,U)   Gauss linearUpwind grad(U);
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
    div(rhoCpPhi,T) Gauss upwind;
    div(rhoLfPhi,liquidFraction) Gauss upwind;
}
laplacianSchemes
{
    default         Gauss linear uncorrected;
}
interpolationSchemes
{
    default         linear;
}
snGradSchemes
{
    default         uncorrected;
}
"""
    (c_dir / "system" / "fvSchemes").write_text(fs, encoding="utf-8")

    # 4. fvSolution
    fsol = foam_header("dictionary", "fvSolution", "system")
    fsol += """solvers
{
    "alpha.metal.*"
    {
        nCorrectors     2;
        nSubCycles      1;
        MULESCorr       yes;
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0;
    }
    pcorr
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-5;
        relTol          0;
    }
    pcorrFinal
    {
        $pcorr;
    }
    p_rgh
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-7;
        relTol          0.01;
    }
    p_rghFinal
    {
        $p_rgh;
        relTol          0;
    }
    "(U|T).*"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0;
    }
}
PIMPLE
{
    momentumPredictor no;
    nOuterCorrectors 1;
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
    pRefCell        0;
    pRefValue       0;
    p_rghRefCell    0;
    p_rghRefValue   0;
}
"""
    (c_dir / "system" / "fvSolution").write_text(fsol, encoding="utf-8")

    # 5. constant/phaseProperties
    pp = foam_header("dictionary", "phaseProperties", "constant")
    pp += """phases          (metal gas);
sigma           1.7;
"""
    (c_dir / "constant" / "phaseProperties").write_text(pp, encoding="utf-8")

    # 6. physicalProperties
    pm = foam_header("dictionary", "physicalProperties.metal", "constant")
    pm += """viscosityModel  constant;
nu              7.5e-07;
rho             7900;
"""
    (c_dir / "constant" / "physicalProperties.metal").write_text(pm, encoding="utf-8")

    pg = foam_header("dictionary", "physicalProperties.gas", "constant")
    pg += """viscosityModel  constant;
nu              1.5e-05;
rho             1.2;
"""
    (c_dir / "constant" / "physicalProperties.gas").write_text(pg, encoding="utf-8")

    # 7. momentumTransport
    mt = foam_header("dictionary", "momentumTransport", "constant")
    mt += """simulationType  laminar;
"""
    (c_dir / "constant" / "momentumTransport").write_text(mt, encoding="utf-8")

    # 8. g
    g_str = foam_header("dictionary", "g", "constant")
    g_str += """dimensions      [acceleration];
value           (0 0 0);
"""
    (c_dir / "constant" / "g").write_text(g_str, encoding="utf-8")

    # 9. thermalProperties
    tp = foam_header("dictionary", "thermalProperties", "constant")
    tp += f"""kMetal          30.0;
kGas            0.026;
cpMetal         500.0;
cpGas           1000.0;
solidus_T       {tm - 5.0};
liquidus_T      {tm + 5.0};
latentHeat      2.7e5;
Cmush           1e7;
"""
    (c_dir / "constant" / "thermalProperties").write_text(tp, encoding="utf-8")

    # 10. 0/ fields: pure metal domain
    am = foam_header("volScalarField", "alpha.metal", "0")
    am += """dimensions      [];
internalField   uniform 1;
boundaryField
{
    hotWall     { type zeroGradient; }
    coldWall    { type zeroGradient; }
    sides       { type zeroGradient; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "alpha.metal").write_text(am, encoding="utf-8")

    prgh = foam_header("volScalarField", "p_rgh", "0")
    prgh += """dimensions      [pressure];
internalField   uniform 0;
boundaryField
{
    hotWall     { type fixedFluxPressure; value uniform 0; }
    coldWall    { type fixedFluxPressure; value uniform 0; }
    sides       { type fixedFluxPressure; value uniform 0; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "p_rgh").write_text(prgh, encoding="utf-8")

    uf = foam_header("volVectorField", "U", "0")
    uf += """dimensions      [velocity];
internalField   uniform (0 0 0);
boundaryField
{
    hotWall     { type noSlip; }
    coldWall    { type noSlip; }
    sides       { type noSlip; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "U").write_text(uf, encoding="utf-8")

    tf = foam_header("volScalarField", "T", "0")
    tf += f"""dimensions      [temperature];
internalField   uniform {t_init};
boundaryField
{{
    hotWall     {{ type fixedValue; value uniform {t_hot}; }}
    coldWall    {{ type zeroGradient; }}
    sides       {{ type zeroGradient; }}
    frontAndBack {{ type empty; }}
}}
"""
    (c_dir / "0" / "T").write_text(tf, encoding="utf-8")

    lff = foam_header("volScalarField", "liquidFraction", "0")
    lff += """dimensions      [];
internalField   uniform 0;
boundaryField
{
    hotWall     { type zeroGradient; }
    coldWall    { type zeroGradient; }
    sides       { type zeroGradient; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "liquidFraction").write_text(lff, encoding="utf-8")


def run_cfd_simulation(case_dir, timeout_s=120):
    """Run blockMesh and metalliksaMeltPoolFoam in WSL under case_dir."""
    wsl_case = to_wsl_path(case_dir)

    # 1. blockMesh
    mesh_res = run_wsl_command(f"cd {wsl_case} && blockMesh", timeout_s=60)
    if mesh_res.returncode != 0:
        raise RuntimeError(f"blockMesh failed in {case_dir}:\n{mesh_res.stderr}\n{mesh_res.stdout}")

    # 2. metalliksaMeltPoolFoam
    solver_res = run_wsl_command(
        f"cd {wsl_case} && {WSL_SOLVER_BIN} -case {wsl_case}",
        timeout_s=timeout_s,
    )
    if solver_res.returncode != 0:
        raise RuntimeError(f"metalliksaMeltPoolFoam failed:\n{solver_res.stderr}\n{solver_res.stdout}")

    # 3. Read diagnostics
    diag_file = Path(case_dir) / "cfd-diagnostics.json"
    diag = {}
    if diag_file.exists():
        try:
            diag = json.loads(diag_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "stdout": solver_res.stdout,
        "stderr": solver_res.stderr,
        "diagnostics": diag,
        "caseDir": str(case_dir),
    }


def read_foam_scalar_field(case_dir, field_name, time_str=None):
    """Read a scalar field from an OpenFOAM ascii time directory."""
    import re
    c_dir = Path(case_dir)
    if time_str is None:
        times = []
        for p in c_dir.iterdir():
            if p.is_dir():
                try:
                    times.append((float(p.name), p.name))
                except ValueError:
                    pass
        if not times:
            raise FileNotFoundError(f"No time directories found in {case_dir}")
        times.sort()
        time_str = times[-1][1]

    field_file = c_dir / time_str / field_name
    if not field_file.exists():
        raise FileNotFoundError(f"Field file not found: {field_file}")

    content = field_file.read_text(encoding="utf-8")
    m_uni = re.search(r"internalField\s+uniform\s+([-\d.eE+]+)\s*;", content)
    if m_uni:
        return [float(m_uni.group(1))]

    m_nonuni = re.search(r"internalField\s+nonuniform\s+List<scalar>\s*\d+\s*\((.*?)\)\s*;", content, re.DOTALL)
    if m_nonuni:
        return [float(v) for v in m_nonuni.group(1).split()]

    raise ValueError(f"Could not parse internalField in {field_file}")


def read_foam_vector_field(case_dir, field_name, time_str=None):
    """Read a vector field from an OpenFOAM ascii time directory."""
    import re
    c_dir = Path(case_dir)
    if time_str is None:
        times = []
        for p in c_dir.iterdir():
            if p.is_dir():
                try:
                    times.append((float(p.name), p.name))
                except ValueError:
                    pass
        if not times:
            raise FileNotFoundError(f"No time directories found in {case_dir}")
        times.sort()
        time_str = times[-1][1]

    field_file = c_dir / time_str / field_name
    if not field_file.exists():
        raise FileNotFoundError(f"Field file not found: {field_file}")

    content = field_file.read_text(encoding="utf-8")
    m_uni = re.search(r"internalField\s+uniform\s*\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)\s*;", content)
    if m_uni:
        return [(float(m_uni.group(1)), float(m_uni.group(2)), float(m_uni.group(3)))]

    m_nonuni = re.search(r"internalField\s+nonuniform\s+List<vector>\s*\d+\s*\((.*?)\)\s*;", content, re.DOTALL)
    if m_nonuni:
        tuples = re.findall(r"\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)", m_nonuni.group(1))
        return [(float(x), float(y), float(z)) for x, y, z in tuples]

    raise ValueError(f"Could not parse internalField in {field_file}")


def stefan_analytical_solution(t_s, t_hot=1800.0, tm=1650.0, t_init=1600.0, k=30.0, rho=7900.0, cp=500.0, lf=2.7e5):
    """Compute exact 1D 2-phase Stefan melting front position s(t) = 2 * lambda * sqrt(alpha_L * t)."""
    import scipy.optimize
    alpha_l = k / (rho * cp)
    ste_l = cp * (t_hot - tm) / lf
    ste_s = cp * (tm - t_init) / lf

    def transcendental(lam):
        term_l = ste_l / (math.exp(lam**2) * math.erf(lam))
        term_s = ste_s / (math.exp(lam**2) * math.erfc(lam))
        return term_l - term_s - lam * math.sqrt(math.pi)

    sol = scipy.optimize.root_scalar(transcendental, bracket=[1e-5, 5.0], method="brentq")
    lam = sol.root
    s_t = 2.0 * lam * math.sqrt(alpha_l * t_s)
    return {
        "lambda": lam,
        "front_m": s_t,
        "front_um": s_t * 1e6,
        "alpha_l": alpha_l,
        "ste_l": ste_l,
        "ste_s": ste_s,
    }


def setup_darcy_damping_case(
    case_dir,
    length_m=100e-6,
    height_m=100e-6,
    nx=10,
    ny=20,
    inlet_velocity=0.05,
    end_time=5e-6,
    dt=1e-6,
):
    """Generate a 2D channel flow case with Darcy velocity suppression in the solid half."""
    c_dir = Path(case_dir)
    os.makedirs(c_dir / "0", exist_ok=True)
    os.makedirs(c_dir / "constant", exist_ok=True)
    os.makedirs(c_dir / "system", exist_ok=True)

    dx = length_m / nx
    dy = height_m / ny
    dz = dx
    half_y = height_m / 2.0

    bm = foam_header("dictionary", "blockMeshDict", "system")
    bm += f"""convertToMeters 1;
vertices
(
    (0 {-half_y} 0)
    ({length_m} {-half_y} 0)
    ({length_m} {half_y} 0)
    (0 {half_y} 0)
    (0 {-half_y} {dz})
    ({length_m} {-half_y} {dz})
    ({length_m} {half_y} {dz})
    (0 {half_y} {dz})
);
blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} 1) simpleGrading (1 1 1)
);
edges ();
boundary
(
    inlet
    {{
        type patch;
        faces ((0 4 7 3));
    }}
    outlet
    {{
        type patch;
        faces ((1 2 6 5));
    }}
    walls
    {{
        type wall;
        faces
        (
            (0 1 5 4)
            (3 7 6 2)
        );
    }}
    frontAndBack
    {{
        type empty;
        faces
        (
            (0 3 2 1)
            (4 5 6 7)
        );
    }}
);
"""
    (c_dir / "system" / "blockMeshDict").write_text(bm, encoding="utf-8")

    cd = foam_header("dictionary", "controlDict", "system")
    cd += f"""application     metalliksaMeltPoolFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          {dt};
writeControl    timeStep;
writeInterval   1;
purgeWrite      0;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
"""
    (c_dir / "system" / "controlDict").write_text(cd, encoding="utf-8")

    fs = foam_header("dictionary", "fvSchemes", "system")
    fs += """ddtSchemes
{
    default         Euler;
}
gradSchemes
{
    default         Gauss linear;
}
divSchemes
{
    div(phi,alpha)  Gauss interfaceCompression vanLeer 1;
    div(rhoPhi,U)   Gauss linearUpwind grad(U);
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
    div(rhoCpPhi,T) Gauss upwind;
}
laplacianSchemes
{
    default         Gauss linear uncorrected;
}
interpolationSchemes
{
    default         linear;
}
snGradSchemes
{
    default         uncorrected;
}
"""
    (c_dir / "system" / "fvSchemes").write_text(fs, encoding="utf-8")

    fsol = foam_header("dictionary", "fvSolution", "system")
    fsol += """solvers
{
    "alpha.metal.*"
    {
        nCorrectors     2;
        nSubCycles      1;
        MULESCorr       yes;
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0;
    }
    pcorr
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-5;
        relTol          0;
    }
    pcorrFinal { $pcorr; }
    p_rgh
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-7;
        relTol          0.01;
    }
    p_rghFinal { $p_rgh; relTol 0; }
    "(U|T).*"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0;
    }
}
PIMPLE
{
    momentumPredictor yes;
    nOuterCorrectors 1;
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
}
"""
    (c_dir / "system" / "fvSolution").write_text(fsol, encoding="utf-8")

    pp = foam_header("dictionary", "phaseProperties", "constant")
    pp += """phases          (metal gas);
sigma           1.7;
"""
    (c_dir / "constant" / "phaseProperties").write_text(pp, encoding="utf-8")

    pm = foam_header("dictionary", "physicalProperties.metal", "constant")
    pm += """viscosityModel  constant;
nu              7.5e-07;
rho             7900;
"""
    (c_dir / "constant" / "physicalProperties.metal").write_text(pm, encoding="utf-8")

    pg = foam_header("dictionary", "physicalProperties.gas", "constant")
    pg += """viscosityModel  constant;
nu              1.5e-05;
rho             1.2;
"""
    (c_dir / "constant" / "physicalProperties.gas").write_text(pg, encoding="utf-8")

    mt = foam_header("dictionary", "momentumTransport", "constant")
    mt += "simulationType  laminar;\n"
    (c_dir / "constant" / "momentumTransport").write_text(mt, encoding="utf-8")

    g_str = foam_header("dictionary", "g", "constant")
    g_str += """dimensions      [acceleration];
value           (0 0 0);
"""
    (c_dir / "constant" / "g").write_text(g_str, encoding="utf-8")

    tp = foam_header("dictionary", "thermalProperties", "constant")
    tp += """kMetal          30.0;
kGas            0.026;
cpMetal         500.0;
cpGas           1000.0;
solidus_T       1645.0;
liquidus_T      1655.0;
latentHeat      2.7e5;
Cmush           1e7;
"""
    (c_dir / "constant" / "thermalProperties").write_text(tp, encoding="utf-8")

    am = foam_header("volScalarField", "alpha.metal", "0")
    am += """dimensions      [];
internalField   uniform 1;
boundaryField
{
    inlet       { type fixedValue; value uniform 1; }
    outlet      { type zeroGradient; }
    walls       { type zeroGradient; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "alpha.metal").write_text(am, encoding="utf-8")

    prgh = foam_header("volScalarField", "p_rgh", "0")
    prgh += """dimensions      [pressure];
internalField   uniform 0;
boundaryField
{
    inlet       { type fixedValue; value uniform 100; }
    outlet      { type fixedValue; value uniform 0; }
    walls       { type fixedFluxPressure; value uniform 0; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "p_rgh").write_text(prgh, encoding="utf-8")

    uf = foam_header("volVectorField", "U", "0")
    uf += """dimensions      [velocity];
internalField   uniform (0 0 0);
boundaryField
{
    inlet       { type pressureInletOutletVelocity; value uniform (0 0 0); }
    outlet      { type zeroGradient; }
    walls       { type slip; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "U").write_text(uf, encoding="utf-8")

    total_cells = nx * ny
    t_vals = []
    fl_vals = []
    for j in range(ny):
        y = -half_y + (j + 0.5) * dy
        is_liquid = (y >= 0)
        temp = 1800.0 if is_liquid else 300.0
        fl = 1.0 if is_liquid else 0.0
        for _ in range(nx):
            t_vals.append(temp)
            fl_vals.append(fl)

    t_str = "\n".join(str(v) for v in t_vals)
    fl_str = "\n".join(str(v) for v in fl_vals)

    tf = foam_header("volScalarField", "T", "0")
    tf += f"""dimensions      [temperature];
internalField   nonuniform List<scalar>
{total_cells}
(
{t_str}
);
boundaryField
{{
    inlet       {{ type zeroGradient; }}
    outlet      {{ type zeroGradient; }}
    walls       {{ type zeroGradient; }}
    frontAndBack {{ type empty; }}
}}
"""
    (c_dir / "0" / "T").write_text(tf, encoding="utf-8")

    lff = foam_header("volScalarField", "liquidFraction", "0")
    lff += f"""dimensions      [];
internalField   nonuniform List<scalar>
{total_cells}
(
{fl_str}
);
boundaryField
{{
    inlet       {{ type zeroGradient; }}
    outlet      {{ type zeroGradient; }}
    walls       {{ type zeroGradient; }}
    frontAndBack {{ type empty; }}
}}
"""
    (c_dir / "0" / "liquidFraction").write_text(lff, encoding="utf-8")


def setup_thermal_parity_case(
    case_dir,
    length_m=200e-6,
    t_hot=800.0,
    t_init=300.0,
    n_cells=40,
    end_time=2e-5,
    dt=2e-6,
):
    """Generate 1D pure metal conduction benchmark with flow disabled for thermal parity."""
    c_dir = Path(case_dir)
    os.makedirs(c_dir / "0", exist_ok=True)
    os.makedirs(c_dir / "constant", exist_ok=True)
    os.makedirs(c_dir / "system", exist_ok=True)

    dx = length_m / n_cells
    dz = dx

    bm = foam_header("dictionary", "blockMeshDict", "system")
    bm += f"""convertToMeters 1;
vertices
(
    (0 0 0)
    ({length_m} 0 0)
    ({length_m} {dx} 0)
    (0 {dx} 0)
    (0 0 {dz})
    ({length_m} 0 {dz})
    ({length_m} {dx} {dz})
    (0 {dx} {dz})
);
blocks
(
    hex (0 1 2 3 4 5 6 7) ({n_cells} 1 1) simpleGrading (1 1 1)
);
edges ();
boundary
(
    hotWall
    {{
        type wall;
        faces ((0 4 7 3));
    }}
    coldWall
    {{
        type wall;
        faces ((1 2 6 5));
    }}
    sides
    {{
        type wall;
        faces
        (
            (0 1 5 4)
            (3 7 6 2)
        );
    }}
    frontAndBack
    {{
        type empty;
        faces
        (
            (0 3 2 1)
            (4 5 6 7)
        );
    }}
);
"""
    (c_dir / "system" / "blockMeshDict").write_text(bm, encoding="utf-8")

    cd = foam_header("dictionary", "controlDict", "system")
    cd += f"""application     metalliksaMeltPoolFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          {dt};
writeControl    timeStep;
writeInterval   1;
purgeWrite      0;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
"""
    (c_dir / "system" / "controlDict").write_text(cd, encoding="utf-8")

    fs = foam_header("dictionary", "fvSchemes", "system")
    fs += """ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes
{
    div(phi,alpha) Gauss interfaceCompression vanLeer 1;
    div(rhoPhi,U) Gauss linearUpwind grad(U);
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
    div(rhoCpPhi,T) Gauss upwind;
}
laplacianSchemes { default Gauss linear uncorrected; }
interpolationSchemes { default linear; }
snGradSchemes { default uncorrected; }
"""
    (c_dir / "system" / "fvSchemes").write_text(fs, encoding="utf-8")

    fsol = foam_header("dictionary", "fvSolution", "system")
    fsol += """solvers
{
    "alpha.metal.*"
    {
        nCorrectors     2;
        nSubCycles      1;
        MULESCorr       yes;
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0;
    }
    pcorr
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-5;
        relTol          0;
    }
    pcorrFinal
    {
        $pcorr;
    }
    p_rgh
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-7;
        relTol          0.01;
    }
    p_rghFinal
    {
        $p_rgh;
        relTol          0;
    }
    "(U|T).*"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0;
    }
}
PIMPLE
{
    momentumPredictor no;
    nOuterCorrectors 1;
    nCorrectors 2;
    nNonOrthogonalCorrectors 0;
    pRefCell 0;
    pRefValue 0;
    p_rghRefCell 0;
    p_rghRefValue 0;
}
"""
    (c_dir / "system" / "fvSolution").write_text(fsol, encoding="utf-8")

    pp = foam_header("dictionary", "phaseProperties", "constant")
    pp += "phases (metal gas);\nsigma 1.7;\n"
    (c_dir / "constant" / "phaseProperties").write_text(pp, encoding="utf-8")

    pm = foam_header("dictionary", "physicalProperties.metal", "constant")
    pm += "viscosityModel constant;\nnu 7.5e-07;\nrho 7900;\n"
    (c_dir / "constant" / "physicalProperties.metal").write_text(pm, encoding="utf-8")

    pg = foam_header("dictionary", "physicalProperties.gas", "constant")
    pg += "viscosityModel constant;\nnu 1.5e-05;\nrho 1.2;\n"
    (c_dir / "constant" / "physicalProperties.gas").write_text(pg, encoding="utf-8")

    mt = foam_header("dictionary", "momentumTransport", "constant")
    mt += "simulationType laminar;\n"
    (c_dir / "constant" / "momentumTransport").write_text(mt, encoding="utf-8")

    g_str = foam_header("dictionary", "g", "constant")
    g_str += "dimensions [acceleration];\nvalue (0 0 0);\n"
    (c_dir / "constant" / "g").write_text(g_str, encoding="utf-8")

    tp = foam_header("dictionary", "thermalProperties", "constant")
    tp += "kMetal 30.0;\nkGas 0.026;\ncpMetal 500.0;\ncpGas 1000.0;\nsolidus_T 1645.0;\nliquidus_T 1655.0;\nlatentHeat 2.7e5;\nCmush 1e7;\n"
    (c_dir / "constant" / "thermalProperties").write_text(tp, encoding="utf-8")

    am = foam_header("volScalarField", "alpha.metal", "0")
    am += """dimensions [];
internalField uniform 1;
boundaryField
{
    hotWall { type zeroGradient; }
    coldWall { type zeroGradient; }
    sides { type zeroGradient; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "alpha.metal").write_text(am, encoding="utf-8")

    prgh = foam_header("volScalarField", "p_rgh", "0")
    prgh += """dimensions [pressure];
internalField uniform 0;
boundaryField
{
    hotWall { type fixedFluxPressure; value uniform 0; }
    coldWall { type fixedFluxPressure; value uniform 0; }
    sides { type fixedFluxPressure; value uniform 0; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "p_rgh").write_text(prgh, encoding="utf-8")

    uf = foam_header("volVectorField", "U", "0")
    uf += """dimensions [velocity];
internalField uniform (0 0 0);
boundaryField
{
    hotWall { type fixedValue; value uniform (0 0 0); }
    coldWall { type fixedValue; value uniform (0 0 0); }
    sides { type fixedValue; value uniform (0 0 0); }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "U").write_text(uf, encoding="utf-8")

    tf = foam_header("volScalarField", "T", "0")
    tf += f"""dimensions [temperature];
internalField uniform {t_init};
boundaryField
{{
    hotWall {{ type fixedValue; value uniform {t_hot}; }}
    coldWall {{ type zeroGradient; }}
    sides {{ type zeroGradient; }}
    frontAndBack {{ type empty; }}
}}
"""
    (c_dir / "0" / "T").write_text(tf, encoding="utf-8")

    lff = foam_header("volScalarField", "liquidFraction", "0")
    lff += """dimensions [];
internalField uniform 0;
boundaryField
{
    hotWall { type zeroGradient; }
    coldWall { type zeroGradient; }
    sides { type zeroGradient; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "liquidFraction").write_text(lff, encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 2: Marangoni case setup
# ---------------------------------------------------------------------------

def setup_marangoni_case(
    case_dir,
    lx: float = 100e-6,
    ly: float = 100e-6,
    nx: int = 20,
    ny: int = 20,
    t_cold: float = 300.0,
    t_hot: float = 2100.0,
    dsigma_dt: float = -2.6e-4,
    sigma0: float = 1.52,
    end_time: float = 2e-7,
    dt: float = 5e-8,
):
    """Set up a 2D Marangoni verification case.

    Geometry:
      - x in [0, lx], y in [0, ly], 1 cell deep in z.
      - Lower half (y < ly/2): metal (alpha.metal = 1).
      - Upper half (y >= ly/2): gas (alpha.metal = 0).
      - Metal-gas interface at y = ly/2.

    Temperature:
      - Linear gradient: T(x) = t_cold + (t_hot - t_cold) * x / lx.
      - Applied as initial + boundary condition (hotWall at x=lx, coldWall at x=0).

    Physics:
      - dSigma/dT < 0 (metals): Marangoni force pulls surface toward cold end (−x).
      - Oracle: net x-velocity at interface cells must be negative.

    thermalProperties (written to constant/):
      - sigma0, dSigmaDT, Tref_sigma, interfaceThreshold written so the solver
        reads them via IOdictionary (READ_IF_PRESENT).
    """
    c_dir = Path(case_dir)

    # ------------------------------------------------------------------
    # blockMeshDict — 2D bilayer mesh
    # ------------------------------------------------------------------
    bm = foam_header("dictionary", "blockMeshDict")
    bm += f"""convertToMeters 1;

vertices
(
    (0    0    0)         // 0
    ({lx} 0    0)         // 1
    ({lx} {ly} 0)         // 2
    (0    {ly} 0)         // 3
    (0    0    {lx/nx})   // 4
    ({lx} 0    {lx/nx})   // 5
    ({lx} {ly} {lx/nx})   // 6
    (0    {ly} {lx/nx})   // 7
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} 1) simpleGrading (1 1 1)
);

boundary
(
    coldWall   {{ type wall; faces ((0 4 7 3)); }}
    hotWall    {{ type wall; faces ((1 5 6 2)); }}
    bottom     {{ type wall; faces ((0 1 5 4)); }}
    top        {{ type wall; faces ((3 2 6 7)); }}
    frontAndBack {{ type empty; faces ((0 3 2 1)(4 5 6 7)); }}
);
"""
    (c_dir / "system").mkdir(parents=True, exist_ok=True)
    (c_dir / "constant").mkdir(parents=True, exist_ok=True)
    (c_dir / "0").mkdir(parents=True, exist_ok=True)
    (c_dir / "system" / "blockMeshDict").write_text(bm, encoding="utf-8")

    # ------------------------------------------------------------------
    # controlDict
    # ------------------------------------------------------------------
    cd = foam_header("dictionary", "controlDict")
    cd += f"""application     metalliksaMeltPoolFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          {dt};
writeControl    timeStep;
writeInterval   1;
purgeWrite      1;
writeFormat     ascii;
writePrecision  10;
runTimeModifiable yes;
"""
    (c_dir / "system" / "controlDict").write_text(cd, encoding="utf-8")

    # fvSchemes / fvSolution — reuse reasonable defaults
    fvsc = foam_header("dictionary", "fvSchemes", "system")
    fvsc += """ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes
{
    div(phi,alpha)  Gauss interfaceCompression vanLeer 1;
    div(rhoPhi,U)   Gauss linearUpwind grad(U);
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
    div(rhoCpPhi,T) Gauss upwind;
    div(rhoLfPhi,liquidFraction) Gauss upwind;
}
laplacianSchemes { default Gauss linear uncorrected; }
interpolationSchemes { default linear; }
snGradSchemes { default uncorrected; }
"""
    (c_dir / "system" / "fvSchemes").write_text(fvsc, encoding="utf-8")

    fvsol = foam_header("dictionary", "fvSolution", "system")
    fvsol += """solvers
{
    "alpha.metal.*"
    {
        nCorrectors     2;
        nSubCycles      1;
        MULESCorr       yes;
        MULES { nIter 10; tolerance 1e-3; }
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0;
    }
    pcorr  { solver PCG; preconditioner DIC; tolerance 1e-5; relTol 0; }
    pcorrFinal { $pcorr; }
    p_rgh  { solver PCG; preconditioner DIC; tolerance 1e-7; relTol 0.01; }
    p_rghFinal { $p_rgh; relTol 0; }
    "(U|T).*"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0;
    }
}
PIMPLE
{
    momentumPredictor yes;
    nOuterCorrectors  1;
    nCorrectors       2;
    nNonOrthogonalCorrectors 0;
    pRefCell    0;
    pRefValue   0;
    p_rghRefCell  0;
    p_rghRefValue 0;
}
relaxationFactors { equations { ".*" 1; } }
"""
    (c_dir / "system" / "fvSolution").write_text(fvsol, encoding="utf-8")

    # ------------------------------------------------------------------
    # Physical constants (constant/)
    # ------------------------------------------------------------------

    # g — gravity disabled (horizontal Marangoni test; buoyancy would complicate)
    gf = foam_header("uniformDimensionedVectorField", "g", "constant")
    gf += "dimensions      [acceleration];\nvalue           (0 0 0);\n"
    (c_dir / "constant" / "g").write_text(gf, encoding="utf-8")

    # phaseProperties — OF14 format (replaces old transportProperties)
    pp = foam_header("dictionary", "phaseProperties", "constant")
    pp += f"""phases          (metal gas);
sigma           {sigma0};
"""
    (c_dir / "constant" / "phaseProperties").write_text(pp, encoding="utf-8")

    # physicalProperties.metal — viscosityModel constant (OF14 naming)
    # Ti-6Al-4V liquid: rho~4000 kg/m³, nu~1e-6 m²/s
    pm = foam_header("dictionary", "physicalProperties.metal", "constant")
    pm += """viscosityModel  constant;
nu              1e-6;
rho             4000;
"""
    (c_dir / "constant" / "physicalProperties.metal").write_text(pm, encoding="utf-8")

    # physicalProperties.gas — Ar: rho~1.6 kg/m³, nu~1.5e-5 m²/s
    pg = foam_header("dictionary", "physicalProperties.gas", "constant")
    pg += """viscosityModel  constant;
nu              1.5e-5;
rho             1.6;
"""
    (c_dir / "constant" / "physicalProperties.gas").write_text(pg, encoding="utf-8")

    # momentumTransport
    mt = foam_header("dictionary", "momentumTransport", "constant")
    mt += "simulationType  laminar;\n"
    (c_dir / "constant" / "momentumTransport").write_text(mt, encoding="utf-8")

    # thermalProperties — Marangoni parameters written here
    # interfaceThreshold: low value to accept any cell where |grad(alpha)| > 1e3 1/m.
    # (bulk cells have |grad(alpha)| ~ 0; true interface cells have ~1/cell_size ~ 2e5).
    # Using 1e3 ensures diagnostics work even after VOF interface broadening.
    interface_threshold = 1e3
    tp2 = foam_header("dictionary", "thermalProperties", "constant")
    tp2 += f"""// Ti-6Al-4V thermal properties
kMetal          30.0;
kGas            0.026;
cpMetal         500.0;
cpGas           1000.0;
solidus_T       1877.0;
liquidus_T      1928.0;
latentHeat      2.86e5;
Cmush           1e6;

// Phase 2: Marangoni surface tension parameters
sigma0          {sigma0};
dSigmaDT        {dsigma_dt};
Tref_sigma      1928.0;
interfaceThreshold {interface_threshold:.6g};
"""
    (c_dir / "constant" / "thermalProperties").write_text(tp2, encoding="utf-8")

    # ------------------------------------------------------------------
    # Initial fields (0/)
    # ------------------------------------------------------------------

    # alpha.metal — lower half metal, upper half gas
    # Use cellwise initialisation via setFields-style or write analytically.
    # We write a uniform zero then rely on the cells being split by ny//2.
    # For this simple case: write per-row field using foamFile nonuniform list.
    n_cells = nx * ny
    half_ny = ny // 2
    alpha_vals = []
    for j in range(ny):
        for i in range(nx):
            alpha_vals.append("1" if j < half_ny else "0")

    af = foam_header("volScalarField", "alpha.metal", "0")
    af += f"""dimensions [0 0 0 0 0 0 0];
internalField nonuniform List<scalar>
{n_cells}
(
{chr(10).join(alpha_vals)}
)
;
boundaryField
{{
    coldWall   {{ type zeroGradient; }}
    hotWall    {{ type zeroGradient; }}
    bottom     {{ type zeroGradient; }}
    top        {{ type zeroGradient; }}
    frontAndBack {{ type empty; }}
}}
"""
    (c_dir / "0" / "alpha.metal").write_text(af, encoding="utf-8")

    # T — linear gradient in x: t_cold at x=0, t_hot at x=lx
    dx = lx / nx
    t_vals = []
    for j in range(ny):
        for i in range(nx):
            x_c = (i + 0.5) * dx
            t_c = t_cold + (t_hot - t_cold) * x_c / lx
            t_vals.append(f"{t_c:.4f}")

    tf = foam_header("volScalarField", "T", "0")
    tf += f"""dimensions [0 0 0 1 0 0 0];
internalField nonuniform List<scalar>
{n_cells}
(
{chr(10).join(t_vals)}
)
;
boundaryField
{{
    coldWall   {{ type fixedValue; value uniform {t_cold}; }}
    hotWall    {{ type fixedValue; value uniform {t_hot}; }}
    bottom     {{ type zeroGradient; }}
    top        {{ type zeroGradient; }}
    frontAndBack {{ type empty; }}
}}
"""
    (c_dir / "0" / "T").write_text(tf, encoding="utf-8")

    # U — zero everywhere initially
    uf = foam_header("volVectorField", "U", "0")
    uf += """dimensions [0 1 -1 0 0 0 0];
internalField uniform (0 0 0);
boundaryField
{
    coldWall   { type noSlip; }
    hotWall    { type noSlip; }
    bottom     { type slip; }
    top        { type slip; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "U").write_text(uf, encoding="utf-8")

    # p_rgh — zero reference
    pf = foam_header("volScalarField", "p_rgh", "0")
    pf += """dimensions [1 -1 -2 0 0 0 0];
internalField uniform 0;
boundaryField
{
    coldWall   { type fixedFluxPressure; value uniform 0; }
    hotWall    { type fixedFluxPressure; value uniform 0; }
    bottom     { type fixedFluxPressure; value uniform 0; }
    top        { type fixedFluxPressure; value uniform 0; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "p_rgh").write_text(pf, encoding="utf-8")

    # liquidFraction — zero everywhere (T above liquidus will be set by solver)
    lff = foam_header("volScalarField", "liquidFraction", "0")
    lff += """dimensions [];
internalField uniform 1;
boundaryField
{
    coldWall   { type zeroGradient; }
    hotWall    { type zeroGradient; }
    bottom     { type zeroGradient; }
    top        { type zeroGradient; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "liquidFraction").write_text(lff, encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 3: Recoil Pressure and Evaporation case setup
# ---------------------------------------------------------------------------

def knight_analytical_recoil_pressure(
    T: float,
    boiling_T: float = 3560.0,
    latent_heat_vap: float = 8.9e6,
    molar_mass: float = 0.0459,
    P0: float = 101325.0,
) -> float:
    """Compute analytical Knight (1979) recoil pressure at temperature T."""
    if T < 1000.0:
        return 0.0
    R_univ = 8.314462618
    Rs = R_univ / molar_mass
    exp_arg = (latent_heat_vap / Rs) * (1.0 / boiling_T - 1.0 / T)
    exp_arg = max(-80.0, min(80.0, exp_arg))
    p_sat = P0 * math.exp(exp_arg)
    return 0.54 * p_sat


def setup_recoil_case(
    case_dir,
    lx: float = 100e-6,
    ly: float = 100e-6,
    nx: int = 20,
    ny: int = 20,
    t_peak: float = 3560.0,
    t_base: float = 2000.0,
    boiling_T: float = 3560.0,
    latent_heat_vap: float = 8.9e6,
    molar_mass: float = 0.0459,
    end_time: float = 2e-7,
    dt: float = 5e-8,
):
    """Set up a 2D recoil-formula verification case.

    This fixture explicitly enables the recoil/evaporation source to verify
    the pressure formula and force direction only. It does not verify an
    evaporating free surface or mass-transfer closure.

    Geometry:
      - x in [0, lx], y in [0, ly], 1 cell deep in z.
      - Lower half (y < ly/2): liquid metal (alpha.metal = 1).
      - Upper half (y >= ly/2): gas (alpha.metal = 0).
      - Free surface at y = ly/2.

    Temperature:
      - Surface hot spot centered at x = lx/2 with peak temperature t_peak (>= boiling_T).
      - T(x) = t_base + (t_peak - t_base) * exp( -((x - lx/2)/(0.25*lx))^2 ).

    Physics:
      - Knight (1979) recoil pressure: P_recoil = 0.54 * P_sat(T).
      - Body force: f_recoil = P_recoil * grad(alpha1).
      - Since metal is below (y < ly/2) and gas is above (y >= ly/2),
        grad(alpha1) has a negative y-component (points into metal).
      - Therefore, recoil force f_recoil_y < 0, depressing the surface downward.
    """
    c_dir = Path(case_dir)
    (c_dir / "system").mkdir(parents=True, exist_ok=True)
    (c_dir / "constant").mkdir(parents=True, exist_ok=True)
    (c_dir / "0").mkdir(parents=True, exist_ok=True)

    # 1. blockMeshDict
    bm = foam_header("dictionary", "blockMeshDict")
    bm += f"""convertToMeters 1;

vertices
(
    (0    0    0)         // 0
    ({lx} 0    0)         // 1
    ({lx} {ly} 0)         // 2
    (0    {ly} 0)         // 3
    (0    0    {lx/nx})   // 4
    ({lx} 0    {lx/nx})   // 5
    ({lx} {ly} {lx/nx})   // 6
    (0    {ly} {lx/nx})   // 7
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} 1) simpleGrading (1 1 1)
);

boundary
(
    leftWall   {{ type wall; faces ((0 4 7 3)); }}
    rightWall  {{ type wall; faces ((1 5 6 2)); }}
    bottom     {{ type wall; faces ((0 1 5 4)); }}
    top        {{ type wall; faces ((3 2 6 7)); }}
    frontAndBack {{ type empty; faces ((0 3 2 1)(4 5 6 7)); }}
);
"""
    (c_dir / "system" / "blockMeshDict").write_text(bm, encoding="utf-8")

    # 2. controlDict
    cd = foam_header("dictionary", "controlDict")
    cd += f"""application     metalliksaMeltPoolFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          {dt};
writeControl    timeStep;
writeInterval   1;
purgeWrite      1;
writeFormat     ascii;
writePrecision  10;
runTimeModifiable yes;
"""
    (c_dir / "system" / "controlDict").write_text(cd, encoding="utf-8")

    # 3. fvSchemes
    fvsc = foam_header("dictionary", "fvSchemes", "system")
    fvsc += """ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes
{
    div(phi,alpha)  Gauss interfaceCompression vanLeer 1;
    div(rhoPhi,U)   Gauss linearUpwind grad(U);
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
    div(rhoCpPhi,T) Gauss upwind;
    div(rhoLfPhi,liquidFraction) Gauss upwind;
}
laplacianSchemes { default Gauss linear uncorrected; }
interpolationSchemes { default linear; }
snGradSchemes { default uncorrected; }
"""
    (c_dir / "system" / "fvSchemes").write_text(fvsc, encoding="utf-8")

    # 4. fvSolution
    fvsol = foam_header("dictionary", "fvSolution", "system")
    fvsol += """solvers
{
    "alpha.metal.*"
    {
        nCorrectors     2;
        nSubCycles      1;
        MULESCorr       yes;
        MULES { nIter 10; tolerance 1e-3; }
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0;
    }
    pcorr  { solver PCG; preconditioner DIC; tolerance 1e-5; relTol 0; }
    pcorrFinal { $pcorr; }
    p_rgh  { solver PCG; preconditioner DIC; tolerance 1e-7; relTol 0.01; }
    p_rghFinal { $p_rgh; relTol 0; }
    "(U|T).*"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0;
    }
}
PIMPLE
{
    momentumPredictor yes;
    nOuterCorrectors  1;
    nCorrectors       2;
    nNonOrthogonalCorrectors 0;
    pRefCell    0;
    pRefValue   0;
    p_rghRefCell  0;
    p_rghRefValue 0;
}
relaxationFactors { equations { ".*" 1; } }
"""
    (c_dir / "system" / "fvSolution").write_text(fvsol, encoding="utf-8")

    # 5. constant/g
    gf = foam_header("uniformDimensionedVectorField", "g", "constant")
    gf += "dimensions      [acceleration];\nvalue           (0 0 0);\n"
    (c_dir / "constant" / "g").write_text(gf, encoding="utf-8")

    # 6. constant/phaseProperties
    pp = foam_header("dictionary", "phaseProperties", "constant")
    pp += """phases          (metal gas);
sigma           1.52;
"""
    (c_dir / "constant" / "phaseProperties").write_text(pp, encoding="utf-8")

    # 7. constant/physicalProperties.metal
    pm = foam_header("dictionary", "physicalProperties.metal", "constant")
    pm += """viscosityModel  constant;
nu              1e-6;
rho             4000;
"""
    (c_dir / "constant" / "physicalProperties.metal").write_text(pm, encoding="utf-8")

    # 8. constant/physicalProperties.gas
    pg = foam_header("dictionary", "physicalProperties.gas", "constant")
    pg += """viscosityModel  constant;
nu              1.5e-5;
rho             1.6;
"""
    (c_dir / "constant" / "physicalProperties.gas").write_text(pg, encoding="utf-8")

    # 9. constant/momentumTransport
    mt = foam_header("dictionary", "momentumTransport", "constant")
    mt += "simulationType  laminar;\n"
    (c_dir / "constant" / "momentumTransport").write_text(mt, encoding="utf-8")

    # 10. constant/thermalProperties
    tp3 = foam_header("dictionary", "thermalProperties", "constant")
    tp3 += f"""// Ti-6Al-4V thermal properties with Phase 3 recoil & evaporation
kMetal          30.0;
kGas            0.026;
cpMetal         500.0;
cpGas           1000.0;
solidus_T       1877.0;
liquidus_T      1928.0;
latentHeat      2.86e5;
Cmush           1e6;

// Phase 2: Marangoni parameters
sigma0          1.52;
dSigmaDT        -2.6e-4;
Tref_sigma      1928.0;
interfaceThreshold 1e3;

// Phase 3: Formula-verification fixture only; not an evaporating VOF model.
active          true;
latentHeatVap   {latent_heat_vap:.6e};
boiling_T       {boiling_T:.6g};
molarMass       {molar_mass:.6g};
evapCoeff       0.82;
P0              101325.0;
"""
    (c_dir / "constant" / "thermalProperties").write_text(tp3, encoding="utf-8")

    # 11. 0/alpha.metal — lower half metal, upper half gas
    n_cells = nx * ny
    half_ny = ny // 2
    alpha_vals = []
    for j in range(ny):
        for i in range(nx):
            alpha_vals.append("1" if j < half_ny else "0")

    af = foam_header("volScalarField", "alpha.metal", "0")
    af += f"""dimensions [0 0 0 0 0 0 0];
internalField nonuniform List<scalar>
{n_cells}
(
{chr(10).join(alpha_vals)}
)
;
boundaryField
{{
    leftWall   {{ type zeroGradient; }}
    rightWall  {{ type zeroGradient; }}
    bottom     {{ type zeroGradient; }}
    top        {{ type zeroGradient; }}
    frontAndBack {{ type empty; }}
}}
"""
    (c_dir / "0" / "alpha.metal").write_text(af, encoding="utf-8")

    # 12. 0/T — hot spot at surface center x = lx/2
    t_vals = []
    sigma_spot = 0.25 * lx
    for j in range(ny):
        for i in range(nx):
            x_center = (i + 0.5) * (lx / nx)
            dist_sq = (x_center - 0.5 * lx) ** 2
            t_cell = t_base + (t_peak - t_base) * math.exp(-dist_sq / (sigma_spot ** 2))
            t_vals.append(f"{t_cell:.6g}")

    tf = foam_header("volScalarField", "T", "0")
    tf += f"""dimensions [0 0 0 1 0 0 0];
internalField nonuniform List<scalar>
{n_cells}
(
{chr(10).join(t_vals)}
)
;
boundaryField
{{
    leftWall   {{ type zeroGradient; }}
    rightWall  {{ type zeroGradient; }}
    bottom     {{ type zeroGradient; }}
    top        {{ type zeroGradient; }}
    frontAndBack {{ type empty; }}
}}
"""
    (c_dir / "0" / "T").write_text(tf, encoding="utf-8")

    # 13. 0/U
    uf = foam_header("volVectorField", "U", "0")
    uf += """dimensions [0 1 -1 0 0 0 0];
internalField uniform (0 0 0);
boundaryField
{
    leftWall   { type slip; }
    rightWall  { type slip; }
    bottom     { type noSlip; }
    top        { type slip; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "U").write_text(uf, encoding="utf-8")

    # 14. 0/p
    pf = foam_header("volScalarField", "p", "0")
    pf += """dimensions [1 -1 -2 0 0 0 0];
internalField uniform 0;
boundaryField
{
    leftWall   { type zeroGradient; }
    rightWall  { type zeroGradient; }
    bottom     { type zeroGradient; }
    top        { type fixedValue; value uniform 0; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "p").write_text(pf, encoding="utf-8")

    # 15. 0/p_rgh
    prgh = foam_header("volScalarField", "p_rgh", "0")
    prgh += """dimensions [1 -1 -2 0 0 0 0];
internalField uniform 0;
boundaryField
{
    leftWall   { type fixedFluxPressure; value uniform 0; }
    rightWall  { type fixedFluxPressure; value uniform 0; }
    bottom     { type fixedFluxPressure; value uniform 0; }
    top        { type fixedFluxPressure; value uniform 0; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "p_rgh").write_text(prgh, encoding="utf-8")

    # 16. 0/liquidFraction
    lff = foam_header("volScalarField", "liquidFraction", "0")
    lff += """dimensions [];
internalField uniform 1;
boundaryField
{
    leftWall   { type zeroGradient; }
    rightWall  { type zeroGradient; }
    bottom     { type zeroGradient; }
    top        { type zeroGradient; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "liquidFraction").write_text(lff, encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 4: Laser model case setup
# ---------------------------------------------------------------------------

def setup_laser_case(
    case_dir,
    lx: float = 100e-6,
    ly: float = 100e-6,
    nx: int = 20,
    ny: int = 20,
    end_time: float = 2e-7,
    dt: float = 5e-8,
    laser_power: float = 100.0,
    laser_radius: float = 20e-6,
    t_start: float = 0.0,
    t_end: float = 2e-7,
    p_start: tuple = (20e-6, 50e-6, 0.0),
    p_end: tuple = (80e-6, 50e-6, 0.0),
):
    """Set up a 2D laser verification case."""
    c_dir = Path(case_dir)

    os.makedirs(c_dir / "0", exist_ok=True)
    os.makedirs(c_dir / "constant", exist_ok=True)
    os.makedirs(c_dir / "system", exist_ok=True)

    dz = lx / nx

    bm = foam_header("dictionary", "blockMeshDict", "system")
    bm += f"""convertToMeters 1;
vertices
(
    (0    0    0)
    ({lx} 0    0)
    ({lx} {ly} 0)
    (0    {ly} 0)
    (0    0    {dz})
    ({lx} 0    {dz})
    ({lx} {ly} {dz})
    (0    {ly} {dz})
);
blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} 1) simpleGrading (1 1 1)
);
edges ();
boundary
(
    walls
    {{
        type wall;
        faces ((0 1 5 4) (1 2 6 5) (2 3 7 6) (3 0 4 7));
    }}
    frontAndBack
    {{
        type empty;
        faces ((0 3 2 1) (4 5 6 7));
    }}
);
"""
    (c_dir / "system" / "blockMeshDict").write_text(bm, encoding="utf-8")

    cd = foam_header("dictionary", "controlDict", "system")
    cd += f"""application     metalliksaMeltPoolFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          {dt};
writeControl    timeStep;
writeInterval   1;
purgeWrite      0;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
"""
    (c_dir / "system" / "controlDict").write_text(cd, encoding="utf-8")

    fs = foam_header("dictionary", "fvSchemes", "system")
    fs += """ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes
{
    div(phi,alpha) Gauss interfaceCompression vanLeer 1;
    div(rhoPhi,U) Gauss linearUpwind grad(U);
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
    div(rhoCpPhi,T) Gauss upwind;
}
laplacianSchemes { default Gauss linear uncorrected; }
interpolationSchemes { default linear; }
snGradSchemes { default uncorrected; }
"""
    (c_dir / "system" / "fvSchemes").write_text(fs, encoding="utf-8")

    fsol = foam_header("dictionary", "fvSolution", "system")
    fsol += """solvers
{
    "alpha.metal.*"
    {
        nCorrectors     2;
        nSubCycles      1;
        MULESCorr       yes;
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0;
    }
    pcorr
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-5;
        relTol          0;
    }
    pcorrFinal
    {
        $pcorr;
    }
    p_rgh
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-7;
        relTol          0.01;
    }
    p_rghFinal
    {
        $p_rgh;
        relTol          0;
    }
    "(U|T).*"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0;
    }
}
PIMPLE
{
    momentumPredictor no;
    nOuterCorrectors 1;
    nCorrectors 2;
    nNonOrthogonalCorrectors 0;
    pRefCell 0;
    pRefValue 0;
    p_rghRefCell 0;
    p_rghRefValue 0;
}
"""
    (c_dir / "system" / "fvSolution").write_text(fsol, encoding="utf-8")

    pp = foam_header("dictionary", "phaseProperties", "constant")
    pp += "phases (metal gas);\nsigma 1.7;\n"
    (c_dir / "constant" / "phaseProperties").write_text(pp, encoding="utf-8")

    pm = foam_header("dictionary", "physicalProperties.metal", "constant")
    pm += "viscosityModel constant;\nnu 7.5e-07;\nrho 7900;\n"
    (c_dir / "constant" / "physicalProperties.metal").write_text(pm, encoding="utf-8")

    pg = foam_header("dictionary", "physicalProperties.gas", "constant")
    pg += "viscosityModel constant;\nnu 1.5e-05;\nrho 1.2;\n"
    (c_dir / "constant" / "physicalProperties.gas").write_text(pg, encoding="utf-8")

    mt = foam_header("dictionary", "momentumTransport", "constant")
    mt += "simulationType laminar;\n"
    (c_dir / "constant" / "momentumTransport").write_text(mt, encoding="utf-8")

    g_str = foam_header("dictionary", "g", "constant")
    g_str += "dimensions [acceleration];\nvalue (0 0 0);\n"
    (c_dir / "constant" / "g").write_text(g_str, encoding="utf-8")

    tp = foam_header("dictionary", "thermalProperties", "constant")
    tp += f"""kMetal          30.0;
kGas            0.026;
cpMetal         500.0;
cpGas           1000.0;
solidus_T       1650.0;
liquidus_T      1700.0;
latentHeat      2.7e5;
Cmush           1e6;

laserActive     true;
laserPower      {laser_power};
laserRadius     {laser_radius};
laserAbsorptivity 1.0;
laserDirection  (0 -1 0);
laserTStart     1 ({t_start});
laserTEnd       1 ({t_end});
laserPStart     1 ( ({p_start[0]} {p_start[1]} {p_start[2]}) );
laserPEnd       1 ( ({p_end[0]} {p_end[1]} {p_end[2]}) );
"""
    (c_dir / "constant" / "thermalProperties").write_text(tp, encoding="utf-8")

    n_cells = nx * ny
    half_ny = ny // 2
    alpha_vals = ["1" if j < half_ny else "0" for j in range(ny) for i in range(nx)]
    
    am = foam_header("volScalarField", "alpha.metal", "0")
    alpha_str = "\n".join(alpha_vals)
    am += f"""dimensions [];
internalField nonuniform List<scalar>
{n_cells}
(
{alpha_str}
);
boundaryField
{{
    walls {{ type zeroGradient; }}
    frontAndBack {{ type empty; }}
}}
"""
    (c_dir / "0" / "alpha.metal").write_text(am, encoding="utf-8")

    prgh = foam_header("volScalarField", "p_rgh", "0")
    prgh += """dimensions [pressure];
internalField uniform 0;
boundaryField
{
    walls { type fixedFluxPressure; value uniform 0; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "p_rgh").write_text(prgh, encoding="utf-8")

    uf = foam_header("volVectorField", "U", "0")
    uf += """dimensions [velocity];
internalField uniform (0 0 0);
boundaryField
{
    walls { type noSlip; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "U").write_text(uf, encoding="utf-8")

    tf = foam_header("volScalarField", "T", "0")
    tf += """dimensions [temperature];
internalField uniform 300;
boundaryField
{
    walls { type zeroGradient; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "T").write_text(tf, encoding="utf-8")

    lff = foam_header("volScalarField", "liquidFraction", "0")
    lff += """dimensions [];
internalField uniform 0;
boundaryField
{
    walls { type zeroGradient; }
    frontAndBack { type empty; }
}
"""
    (c_dir / "0" / "liquidFraction").write_text(lff, encoding="utf-8")
