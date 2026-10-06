"""Reproducible numerical benchmark; fixtures are not experimental measurements."""
import argparse
import json
import time
from pathlib import Path
from lpbf_simulation import validate, transient, implementation_fingerprint
from lpbf_openfoam import thermal
from lpbf_worker import capabilities


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    caps = capabilities()
    if not caps["openfoamThermal"]:
        raise SystemExit("Benchmark requires a compiled OpenFOAM 14 backend")
    base = dict(mode="standard", backend="reference", power_W=40, mesh_um=40,
                trackLength_um=200, cooling_s=.0001, dwell_s=0)
    results = []
    for name,patch in (("single-track",{}), ("rotated-multilayer",dict(power_W=10,tracks=2,layers=2,layer_um=45,scanAngle_deg=35,dwell_s=.00002)),
                       ("island",dict(power_W=10,tracks=2,strategy="island",islandSize_um=100))):
        p,m = validate({**base,**patch})
        started=time.perf_counter(); reference=transient(p,m); reference_time=time.perf_counter()-started
        started=time.perf_counter(); foam=thermal(p,m); foam_time=time.perf_counter()-started
        results.append(dict(name=name,input=p,implementationHash=implementation_fingerprint(),
            reference=dict(metrics=reference["metrics"],energy=reference["energyBalance"],wallTime_s=reference_time),
            openfoam=dict(metrics=foam["metrics"],energy=foam["energyBalance"],mass=foam["massBalance"],phase=foam["phaseAudit"],mesh=foam["discretization"],wallTime_s=foam_time),
            peakDifference_pct=100*(foam["metrics"]["peakTemperature_K"]-reference["metrics"]["peakTemperature_K"])/reference["metrics"]["peakTemperature_K"]))
    out=dict(status="Numerical verification only; experimental validation pending",openfoam=caps["openfoamVersion"],
             binaryHash=caps["binaryHash"],fixtures=results,
             limitations="Fixed reference mass, assumed absorption depth, estimated properties, no momentum or free surface. Timings include OpenFOAM case I/O on WSL-mounted workspace.")
    Path(args.output).write_text(json.dumps(out,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps([dict(name=r["name"],peakDifference_pct=r["peakDifference_pct"],energyError=r["openfoam"]["energy"]["relativeError"],dimensions={k:r["openfoam"]["metrics"][k] for k in ("length_um","width_um","depth_um")}) for r in results],indent=2))


if __name__ == "__main__": main()
