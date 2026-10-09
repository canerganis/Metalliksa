import React from "react";
import { MACHINE_VERDICT_SENTENCE, machineEvidenceBadge, machineTileLine, type MachineCalibrationStatus } from "../../data/lpbfMachineCalibration";
import { useMachineDepth, type MachineRequest, type MachineSolve } from "./useMachineDepth";

/**
 * Second line of the Build Job W x D tile: the machine-calibrated depth (user data) next to, never instead of, the
 * screening value. Renders nothing until the user selects a machine calibration artefact in the Melt Pool lab. The Build
 * Job verdict never reads it. Screening only unless the backend returned the calibrated kind for a complete artefact.
 */
export function MachineTileLine({ material, request, screeningDepth, status, solve, selectedId }: {
  material: string;
  request: MachineRequest;
  screeningDepth: number | null;
  status?: MachineCalibrationStatus | null;
  solve?: MachineSolve;
  selectedId?: string | null;
}) {
  const { artefact, wantsSolve, cell, result, error } = useMachineDepth({ heatSource: "rosenthal", material, request, status, solve, selectedId, publishReport: true });
  if (!artefact) return null;
  const block = result?.machineCalibrated;
  const line = wantsSolve ? machineTileLine(block, screeningDepth) : null;
  const text = line
    ?? (error ? `Machine depth unavailable: ${error}` : wantsSolve ? "Machine depth: computing" : `Machine depth not served: ${cell?.reasonText?.[0] ?? "no cell for this alloy"}`);
  return (
    <div data-testid="machine-tile-line" className="mt-0.5 whitespace-normal text-[10px] text-slate-400" title={`${block ? machineEvidenceBadge(block) : "Screening only"}. ${MACHINE_VERDICT_SENTENCE}`}>
      {text}
    </div>
  );
}
