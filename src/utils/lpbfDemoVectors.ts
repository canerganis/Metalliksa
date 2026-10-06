import type { LPBFAlloyId } from "../types/lpbfDataFoundation";
import type { LpbfProcessPatch } from "../store/useMaterialSpecimenStore";

/**
 * Demo P–v–h–t–d vectors. These only load process inputs;
 * printability is always decided by Python compose_verdict.
 */
export const LPBF_DEMO_VECTORS: Record<
  LPBFAlloyId,
  { printable: LpbfProcessPatch; lof: LpbfProcessPatch }
> = {
  ti6al4v: {
    printable: { laserPower_W: 200, scanSpeed_mms: 1000, hatch_um: 100, layer_um: 30, beamDiameter_um: 80 },
    lof: { laserPower_W: 120, scanSpeed_mms: 1600, hatch_um: 180, layer_um: 60, beamDiameter_um: 80 },
  },
  ss316l: {
    printable: { laserPower_W: 180, scanSpeed_mms: 900, hatch_um: 90, layer_um: 30, beamDiameter_um: 80 },
    lof: { laserPower_W: 110, scanSpeed_mms: 1500, hatch_um: 180, layer_um: 60, beamDiameter_um: 80 },
  },
  alsi10mg: {
    printable: { laserPower_W: 340, scanSpeed_mms: 1100, hatch_um: 110, layer_um: 30, beamDiameter_um: 100 },
    lof: { laserPower_W: 200, scanSpeed_mms: 1800, hatch_um: 200, layer_um: 60, beamDiameter_um: 100 },
  },
  in718: {
    printable: { laserPower_W: 190, scanSpeed_mms: 900, hatch_um: 90, layer_um: 30, beamDiameter_um: 80 },
    lof: { laserPower_W: 90, scanSpeed_mms: 1400, hatch_um: 140, layer_um: 50, beamDiameter_um: 80 },
  },
  in625: {
    printable: { laserPower_W: 220, scanSpeed_mms: 950, hatch_um: 100, layer_um: 30, beamDiameter_um: 80 },
    lof: { laserPower_W: 100, scanSpeed_mms: 1500, hatch_um: 150, layer_um: 50, beamDiameter_um: 80 },
  },
};
