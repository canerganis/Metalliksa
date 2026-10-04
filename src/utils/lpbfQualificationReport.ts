import { canonicalLpbfMaterialName } from "./lpbfMaterialIdentity";
import type { ActiveSpecimenState } from "../store/useMaterialSpecimenStore";
import { engineeringSignature, type LpbfEngineeringState } from "../store/useLpbfEngineeringStore";
import type { LpbfBuildContext } from "../store/useLpbfWorkflowStore";
import type { PythonLpbfBuildJobResult } from "../services/pythonComputationService";
import { isResultStale } from "./lpbfResultStaleness";

export function sharedSimulationInput(specimen: ActiveSpecimenState) {
  const process = specimen.lpbf;
  return {material: canonicalLpbfMaterialName(specimen.name), power_W:process.laserPower_W,speed_mm_s:process.scanSpeed_mms,beamDiameter_um:process.beamDiameter_um,preheat_C:process.preheatTemp_C,layer_um:process.layer_um,hatch_um:process.hatch_um};
}

export function createLpbfQualificationReport(specimen: ActiveSpecimenState, context: LpbfBuildContext, engineering: LpbfEngineeringState, buildJob: PythonLpbfBuildJobResult | null, researchEvidence: unknown[] = []) {
  const result = engineering.job?.status === "completed" ? engineering.job.result : undefined;
  const currentSignature = engineeringSignature(sharedSimulationInput(specimen), engineering, specimen.lpbf.scanStrategy);
  const stale = isResultStale(engineering.resultSignature, currentSignature, !!result);
  const gaps = [
    ...(!context.buildId.trim() ? ["Build identity is missing."] : []),
    ...(!context.machine.trim() ? ["Machine identity is missing."] : []),
    ...(!context.powderLot.trim() ? ["Powder lot is missing."] : []),
    ...(!result ? ["No completed thermal simulation is attached."] : []),
    ...(stale ? ["Current inputs differ from the attached simulation. Re-run or review the executed input snapshot."] : []),
    ...(!result?.measurementEvidence?.length ? ["No worker-reported measurement evidence is attached."] : []),
    ...(!context.measurementMethod.trim() ? ["Measurement method is missing."] : []),
    "Independent experimental validation has not been established.",
    "Free surface, momentum, evaporation, recoil, pore trapping and residual stress are not resolved by the thermal workflow.",
  ];
  return {
    schemaVersion: 1,
    reportType: "LPBF research qualification dossier",
    createdAt: new Date().toISOString(),
    scope: "Research",
    qualificationStatus: "Unresolved",
    productionReady: false,
    resultType: result?.effectiveMode === "screening" ? "Screening only" : "Unresolved",
    resultDescription: result ? result.label : "No completed result",
    specimen: {id:specimen.id,name:specimen.name,composition:specimen.composition,compositionUnit:specimen.unit,materialTransfer:specimen.materialTransfer??null},
    buildContext: context,
    currentProcess: specimen.lpbf,
    executedInput: engineering.submittedInput ?? result?.settings ?? null,
    job: engineering.job ? {...engineering.job, result} : null,
    resultMatchesCurrentInputs: result ? !stale : null,
    buildScreening: buildJob ? {modelId:buildJob.modelId,verdict:buildJob.verdict,assumptions:buildJob.assumptions,qualification:buildJob.qualification ?? null,uq:buildJob.uq ?? null,ambench:buildJob.ambench ?? null} : null,
    researchEvidence,
    measurementDraft: {width_um:engineering.width,depth_um:engineering.depth,source:engineering.source,specimenOrDoi:engineering.specimen,uncertainty_um:engineering.uncertainty,holdout:engineering.holdout,replicates:engineering.measurements,status:"User-supplied; only worker-reported evidence is part of the executed comparison"},
    verification: {conservation:result?.energyBalance ?? null,numericalConvergence:result?.convergenceStudy ?? null,experimentalValidation:"Unresolved"},
    limitations: gaps,
  };
}
