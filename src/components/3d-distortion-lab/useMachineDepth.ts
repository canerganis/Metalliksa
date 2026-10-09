import { useEffect, useState } from "react";
import { pythonComputationService } from "../../services/pythonComputationService";
import {
  artefactsForMaterial, depthCellFor,
  type MachineArtefactSummary, type MachineCalibratedBlock, type MachineCalibratedResult, type MachineCalibrationStatus, type MachineCellSummary,
} from "../../data/lpbfMachineCalibration";
import { useMachineCalibrationStore } from "../../store/useMachineCalibrationStore";

// Shared logic for the machine calibration (user data) views: the Melt Pool lab section and the Build Job W x D tile
// line. Nothing is requested until the user selects an artefact (session-only selection). A cell that is not served
// needs no solver call: its reasons come from the artefact summary. Screening only, not validation.

export type MachineRequest = Omit<Parameters<typeof pythonComputationService.solveLPBFMachineCalibratedMeltpool>[0], "machineCalibration" | "material" | "heatSource">;
export type MachineSolve = (payload: Parameters<typeof pythonComputationService.solveLPBFMachineCalibratedMeltpool>[0], signal?: AbortSignal) => Promise<MachineCalibratedResult>;

let statusPromise: Promise<MachineCalibrationStatus> | null = null;
/** One status request per page session; a failure resolves to "no artefacts" so the views stay hidden. */
export function loadMachineStatusOnce(): Promise<MachineCalibrationStatus> {
  if (!statusPromise) {
    statusPromise = pythonComputationService.getLpbfMachineCalibrationStatus().catch(() => ({ artefacts: [], skipped: 0 }));
  }
  return statusPromise;
}

export function refusedBlockFor(cell: MachineCellSummary | undefined): MachineCalibratedBlock {
  return {
    available: false, status: cell?.status, depth_um: null, depthBand_um: null, evidenceKind: "screening-only", evidenceScope: null,
    missingMethodFields: [], reasonText: cell?.reasonText?.length ? cell.reasonText : ["the artefact has no cell for this kernel and material"],
    experimentalValidation: false,
  };
}

export interface MachineDepthState {
  readonly artefacts: readonly MachineArtefactSummary[];
  readonly artefact: MachineArtefactSummary | undefined;
  readonly cell: MachineCellSummary | undefined;
  readonly wantsSolve: boolean;
  readonly result: MachineCalibratedResult | null;
  readonly error: string | null;
}

export function useMachineDepth(opts: {
  heatSource: "goldak" | "eagar-tsai" | "rosenthal";
  material: string;
  request: MachineRequest;
  status?: MachineCalibrationStatus | null;
  solve?: MachineSolve;
  /** the Build Job tile publishes its result for the run report; the Melt Pool lab section does not */
  publishReport?: boolean;
  /** test seam: overrides the session selection (server rendering always sees the initial store state) */
  selectedId?: string | null;
}): MachineDepthState {
  const { heatSource, material, request, status: injected, publishReport = false } = opts;
  const solve: MachineSolve = opts.solve ?? ((p, s) => pythonComputationService.solveLPBFMachineCalibratedMeltpool(p, s));
  const [fetched, setFetched] = useState<MachineCalibrationStatus | null>(null);
  const storeSelected = useMachineCalibrationStore((s) => s.selectedId);
  const selectedId = opts.selectedId !== undefined ? opts.selectedId : storeSelected;
  const setReport = useMachineCalibrationStore((s) => s.setReport);
  const [result, setResult] = useState<MachineCalibratedResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const status = injected !== undefined ? injected : fetched;

  useEffect(() => {
    if (injected !== undefined) return;
    let alive = true;
    loadMachineStatusOnce().then((s) => { if (alive) setFetched(s); });
    return () => { alive = false; };
  }, [injected]);

  const artefacts = artefactsForMaterial(status, material);
  const artefact = artefacts.find((a) => a.machineCalibrationId === selectedId);
  const cell = depthCellFor(artefact, heatSource);
  const wantsSolve = Boolean(artefact && cell && cell.status === "served");
  const requestKey = JSON.stringify([selectedId, heatSource, material, request]);

  useEffect(() => {
    if (!artefact) { setResult(null); setError(null); if (publishReport) setReport(null); return; }
    if (!wantsSolve) {
      setResult(null); setError(null);
      if (publishReport) setReport({ artefact, kernel: heatSource, block: refusedBlockFor(cell), screeningDepth_um: null });
      return;
    }
    const controller = new AbortController();
    setError(null);
    solve({ ...request, heatSource, material, machineCalibration: artefact.machineCalibrationId }, controller.signal)
      .then((r) => {
        if (controller.signal.aborted) return;
        setResult(r);
        if (publishReport) setReport({ artefact, kernel: heatSource, block: r.machineCalibrated, screeningDepth_um: r.screening?.meltPoolGeometry?.depth_um ?? null });
      })
      .catch((e: unknown) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Machine calibration request failed."); });
    return () => controller.abort();
  }, [requestKey, wantsSolve, artefact?.machineCalibrationId, status]);

  return { artefacts, artefact, cell, wantsSolve, result, error };
}
