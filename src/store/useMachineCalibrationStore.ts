/**
 * Session-only selection of a machine calibration artefact (user data). Not persisted: a reload starts with no artefact
 * selected, so the default screening path is the only one issued until the user opts in. Screening only, not validation.
 */
import { create } from "zustand";
import type { MachineCalibrationReportInput } from "../data/lpbfMachineCalibration";

interface MachineCalibrationSelection {
  selectedId: string | null;
  /** Latest result for the selected artefact, kept for the run report. */
  report: MachineCalibrationReportInput | null;
  select: (id: string | null) => void;
  setReport: (report: MachineCalibrationReportInput | null) => void;
}

export const useMachineCalibrationStore = create<MachineCalibrationSelection>((set) => ({
  selectedId: null,
  report: null,
  select: (id) => set({ selectedId: id, report: null }),
  setReport: (report) => set({ report }),
}));
