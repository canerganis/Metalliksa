import assert from "node:assert/strict";
import { parseSimulationJob } from "../src/services/lpbfSimulationService";

const base = { id: "a".repeat(32), status: "running", progress: .5, log: "test fixture", error: null };
assert.equal(parseSimulationJob(base).status, "running");
for (const bad of [{ ...base, progress: NaN }, { ...base, progress: 2 }, { ...base, id: "../case" }, { ...base, status: "completed" }]) {
  assert.throws(() => parseSimulationJob(bad));
}
const result = {
  requestedMode: "screening", effectiveMode: "screening", fallbackReason: null,
  schemaVersion: 1, validationStatus: "unvalidated", productionReady: false, confidence: "low",
  settings: {}, solver: { id: "synthetic-contract-test", version: "1" },
  material: { name: "fixture", quality: "synthetic", source: "Unit test; not experimental" },
  label: "Screening only", regime: "test", mainRisk: "test", recommendation: "test", riskScope: "test",
  metrics: { width_um: 100, depth_um: 50, length_um: 200 }, assumptions: ["Synthetic fixture"],
  analyticalComparison: { goldak: { width_um: 100, depth_um: 50, length_um: 200 } },
};
assert.equal(parseSimulationJob({ ...base, status: "completed", result }).result?.label, "Screening only");
const retained = { status: 'retained-unverified', fileCount: 2, totalBytes: 4096 };
for (const status of ['failed', 'cancelled', 'timed_out'] as const) {
  assert.deepEqual(parseSimulationJob({ ...base, status, partialArtifacts: retained }).partialArtifacts, retained);
  assert.equal(parseSimulationJob({ ...base, status, partialArtifacts: { status: 'inventory-unavailable' } }).partialArtifacts?.status, 'inventory-unavailable');
}
for (const partialArtifacts of [
  null, {}, { ...retained, fileCount: 0 }, { ...retained, fileCount: 1.5 },
  { ...retained, totalBytes: -1 }, { ...retained, totalBytes: Number.MAX_SAFE_INTEGER + 1 },
  { ...retained, unexpected: true }, { status: 'inventory-unavailable', fileCount: -1 },
  { status: 'inventory-unavailable', totalBytes: 'unknown' }, { status: 'verified', fileCount: 2, totalBytes: 4096 },
]) assert.throws(() => parseSimulationJob({ ...base, status: 'cancelled', partialArtifacts }), /partial artifact inventory/);
for (const status of ['queued', 'running', 'completed'] as const) {
  assert.throws(() => parseSimulationJob({ ...base, status, result: status === 'completed' ? result : undefined,
    partialArtifacts: retained }), /partial artifact inventory/);
}
assert.equal(parseSimulationJob({ ...base, status: 'completed', result }).partialArtifacts, undefined);
for (const patch of [
  { validationStatus: "validated" }, { productionReady: true },
  { metrics: { width_um: -1, depth_um: 50, length_um: 200 } },
  { thermalHistory: [{ time_s: 0, peak_K: Infinity }] },
  { measurementComparison: { width_um: { errors_pct: "bad" } } },
  { energyBalance: { input_J: "bad" } },
  { massBalance: { initial_kg: -1, deposited_kg: 0, final_kg: 1, relativeError: 0, scope: "fixture" } },
  { phaseAudit: { liquidVolume_m3: 1, solidVolume_m3: 0, activeVolume_m3: 1, minFraction: 0, maxFraction: 1.1, scope: "fixture" } },
  { artifacts: [{ path: "../secret", size_bytes: 0, sha256: "a".repeat(64) }] },
  { fieldPreviews: ["https://untrusted.example/field.svg"] },
]) assert.throws(() => parseSimulationJob({ ...base, status: "completed", result: { ...result, ...patch } }));
assert.throws(() => parseSimulationJob({ ...base, status: "cancelled", result }));
assert.throws(() => parseSimulationJob({ ...base, status: "completed", result: {...result,effectiveMode:"standard"} }));
const thermal={...result,requestedMode:"standard",effectiveMode:"standard",energyBalance:{input_J:1,losses_J:.2,stored_J:.8,relativeError:0},massBalance:{initial_kg:1,deposited_kg:1,final_kg:2,relativeError:0,scope:"stationary"},phaseAudit:{liquidVolume_m3:1,solidVolume_m3:1,activeVolume_m3:2,minFraction:0,maxFraction:1,scope:"enthalpy"}};
assert.doesNotThrow(()=>parseSimulationJob({...base,status:"completed",result:thermal}));
assert.throws(()=>parseSimulationJob({...base,status:"completed",result:{...thermal,massBalance:{...thermal.massBalance,final_kg:3}}}));
assert.throws(()=>parseSimulationJob({...base,status:"completed",result:{...thermal,phaseAudit:{...thermal.phaseAudit,activeVolume_m3:3}}}));
console.log("PASS: LPBF runtime contract rejects invalid, nonfinite and false-validation responses");

// Synthetic transport fixtures; no experimental or numerical validation claim.
const completed = (patch: Record<string, unknown>) => ({ ...base, status: "completed", result: { ...result, ...patch } });
// Hash binding is verified in Python; this client checks shape and model identity.
const coreContract = {
  schemaVersion: 1, modelId: 'analytical-conduction-screening-v1', actualBackend: 'analytical',
  requestedBackend: 'auto', effectiveMode: 'screening', solverId: 'rosenthal+goldak',
  inputSha256: 'a'.repeat(64), materialSha256: 'b'.repeat(64), evidenceClass: 'unvalidated-model',
  units: { power: 'W', speed: 'mm/s', length: 'um', preheat: 'degC', temperature: 'K', internalLength: 'm', time: 's', energy: 'J', beamDiameter: '1/e2-intensity' },
  resolvedPhysics: { conduction: true, transient: false, latentHeat: false, momentum: false, freeSurface: false, evaporation: false },
};
const bound = (c: unknown) => completed({settings: {backend: 'auto'}, solver: {id: 'rosenthal+goldak', version: 'enthalpy-fv-6'}, coreContract: c});
assert.doesNotThrow(() => parseSimulationJob(bound(coreContract)));
for (const bad of [null, {}, {...coreContract, schemaVersion: 2}, {...coreContract, actualBackend: 'cuda:0'},
  {...coreContract, materialSha256: 'missing'}, {...coreContract, modelId: 'unknown'},
  {...coreContract, requestedBackend: 'reference'}, {...coreContract, effectiveMode: 'standard'},
  {...coreContract, solverId: 'enthalpy-fv-6'}, {...coreContract, evidenceClass: 'validated'},
  {...coreContract, units: {...coreContract.units, temperature: 'degC'}},
  {...coreContract, resolvedPhysics: {...coreContract.resolvedPhysics, latentHeat: true}},
  {...coreContract, resolvedPhysics: {...coreContract.resolvedPhysics, momentum: true}},
  {...coreContract, extraField: true},
]) assert.throws(() => parseSimulationJob(bound(bad)), /core contract/);
for (const [actualBackend, solverId] of [['numpy-reference', 'enthalpy-fv-6'], ['openfoam-thermal', 'metalliksaThermal-OpenFOAM14-6']]) {
  const c = {...coreContract, actualBackend, solverId, modelId: 'stationary-enthalpy-conduction-v1', effectiveMode: 'standard',
    resolvedPhysics: {...coreContract.resolvedPhysics, transient: true, latentHeat: true}};
  const r = {...thermal, solver: {id: solverId, version: 'enthalpy-fv-6'}, settings: {backend: 'auto'}, coreContract: c};
  assert.doesNotThrow(() => parseSimulationJob({...base, status: 'completed', result: r}));
  const opposite = actualBackend === 'numpy-reference' ? 'openfoam-thermal' : 'reference';
  assert.throws(() => parseSimulationJob({...base, status: 'completed', result: {...r, settings: {backend: opposite}, coreContract: {...c, requestedBackend: opposite}}}), /core contract/);
}
const layerConformingContract = {
  ...coreContract,
  modelId: 'stationary-enthalpy-conduction-layer-conforming-v1',
  actualBackend: 'numpy-reference', requestedBackend: 'reference',
  effectiveMode: 'standard', solverId: 'enthalpy-fv-6',
  resolvedPhysics: {...coreContract.resolvedPhysics, transient: true, latentHeat: true},
};
const layerConformingResult = {
  ...thermal, solver: {id: 'enthalpy-fv-6', version: 'enthalpy-fv-6'},
  settings: {backend: 'reference', mode: 'standard', surfaceMode: 'powder-layer', powderGridPolicy: 'layer-conforming'},
  coreContract: layerConformingContract,
};
assert.doesNotThrow(() => parseSimulationJob({...base, status: 'completed', result: layerConformingResult}));
assert.throws(() => parseSimulationJob({...base, status: 'completed', result: {
  ...layerConformingResult, coreContract: {...layerConformingContract, modelId: 'stationary-enthalpy-conduction-v1'},
}}), /core contract/);
assert.throws(() => parseSimulationJob({...base, status: 'completed', result: {
  ...layerConformingResult, settings: {...layerConformingResult.settings, backend: 'auto'},
}}), /core contract/);
const layeredV2 = {
  ...thermal,
  solver: { id: 'layered-enthalpy-fv-1', version: 'layered-enthalpy-fv-1' },
  settings: { backend: 'reference', mode: 'standard', thermalModelId: 'layered-plate-enthalpy-v1',
    surfaceMode: 'bare-plate', barePlateGeometry: 'square', scanAngle_deg: 0, layers: 1, tracks: 1, study: 'none',
    plateThickness_um: 3170, supportThickness_um: 1000, contactResistance_m2K_W: 0,
    supportBottomBoundary: 'adiabatic', incidenceAngle_deg: 5, incidenceAzimuth_deg: 0,
    beamProfileModelId: 'assumed-oblique-gaussian-normal-plane-v1', sourcePenetration_um: 25 },
  coreContract: {
    schemaVersion: 2, modelId: 'layered-plate-enthalpy-v1', actualBackend: 'numpy-reference',
    requestedBackend: 'reference', effectiveMode: 'standard', solverId: 'layered-enthalpy-fv-1',
    inputSha256: 'a'.repeat(64), materialSha256: 'b'.repeat(64), evidenceClass: 'unvalidated-model',
    units: { power: 'W', speed: 'mm/s', length: 'um', preheat: 'degC', temperature: 'K', internalLength: 'm',
      time: 's', energy: 'J', beamDiameter: '1/e2-intensity', incidenceAngle: 'deg', incidenceAzimuth: 'deg',
      contactResistance: 'm2-K/W' },
    resolvedPhysics: { conduction: true, transient: true, latentHeat: true, momentum: false, freeSurface: false,
      evaporation: false, layeredMaterials: true, interfaceModelId: 'planar-series-resistance-v1',
      contactResistanceModelId: 'explicit-area-specific-resistance', supportMaterialRevisionSha256: 'c'.repeat(64),
      beamSourceModelId: 'assumed-oblique-gaussian-normal-plane-v1', supportBottomBoundaryId: 'adiabatic' },
  },
};
assert.doesNotThrow(() => parseSimulationJob({...base, status: 'completed', result: layeredV2}));
for (const patch of [
  { schemaVersion: 1 }, { modelId: 'stationary-enthalpy-conduction-v1' }, { actualBackend: 'cuda:0' },
  { resolvedPhysics: { ...layeredV2.coreContract.resolvedPhysics, supportBottomBoundaryId: 'isothermal-at-preheat' } },
  { resolvedPhysics: { ...layeredV2.coreContract.resolvedPhysics, supportMaterialRevisionSha256: 'bad-hash' } },
]) {
  assert.throws(() => parseSimulationJob({...base, status: 'completed', result: {
    ...layeredV2, coreContract: { ...layeredV2.coreContract, ...patch },
  }}), /core contract/);
}
for (const patch of [{ contactResistance_m2K_W: -1 }, { sourcePenetration_um: 151 },
  { beamProfileModelId: 'measured-profile' }, { scanAngle_deg: 1 }, { barePlateGeometry: 'rectangular-corridor' }]) {
  assert.throws(() => parseSimulationJob({...base, status: 'completed', result: {
    ...layeredV2, settings: { ...layeredV2.settings, ...patch },
  }}), /core contract/);
}
for (const effectiveMode of [undefined, null, "standrad", "high-fidelity", ["screening"]]) {
  assert.throws(() => parseSimulationJob(completed({ effectiveMode })), /execution mode/);
}
for (const requestedMode of [undefined, null, "unknown", ["screening"]]) {
  assert.throws(() => parseSimulationJob(completed({ requestedMode })), /execution mode/);
}
for (const fallbackReason of [undefined, null, "", "   "]) {
  assert.throws(() => parseSimulationJob(completed({ requestedMode: "high-fidelity", fallbackReason })), /fallback provenance/);
}
assert.doesNotThrow(() => parseSimulationJob(completed({ requestedMode: "high-fidelity", fallbackReason: "Free-surface solver unavailable" })));
assert.throws(() => parseSimulationJob(completed({ settings: { mode: "standard" } })), /execution mode/);
for (const mode of ["standard", "calibration"]) {
  assert.throws(() => parseSimulationJob(completed({ requestedMode: mode, effectiveMode: mode })), /conservation audit/);
  assert.doesNotThrow(() => parseSimulationJob({ ...base, status: "completed", result: { ...thermal, requestedMode: mode, effectiveMode: mode } }));
}
for (const times of [[1, 0], [0, 0]]) {
  assert.throws(() => parseSimulationJob(completed({ thermalHistory: times.map(time_s => ({ time_s, peak_K: 300 })) })), /thermal history/);
}
assert.doesNotThrow(() => parseSimulationJob(completed({ thermalHistory: [{ time_s: 0, peak_K: 300 }, { time_s: .01, peak_K: 1000 }] })));
const comparison = { count: 2, errors_pct: [-10, 10], rmse_um: 10, bias_um: -1, calibrationFactor: null, note: "Synthetic comparison" };
assert.doesNotThrow(() => parseSimulationJob(completed({ measurementComparison: { width_um: comparison } })));
assert.doesNotThrow(() => parseSimulationJob(completed({ measurementComparison: { width_um: { ...comparison, calibrationFactor: 1.1 } } })));
for (const patch of [{ count: 0 }, { count: -1 }, { count: 1.5 }, { count: 3 }, { rmse_um: -1 }, { calibrationFactor: 0 }, { calibrationFactor: -1 }]) {
  assert.throws(() => parseSimulationJob(completed({ measurementComparison: { width_um: { ...comparison, ...patch } } })), /measurement comparison/);
}
