// One lazy view per listed registry module (Phase 7 slice 1). The Record type makes a missing or
// extra view a compile error; tests/module-views.test.ts checks every entry against the
// contract's view.component/export and against the App.tsx renderModule switch, which still
// renders the modules (props such as onNavigate/mode stay there until Phase 9 edits App.tsx).
import { lazy, type ComponentType, type LazyExoticComponent } from 'react';
import type { ListedModuleId } from './registry';

// Views take module-specific props (onNavigate, mode, ...); the switch in App.tsx supplies them.
export type ModuleView = LazyExoticComponent<ComponentType<any>>;

export const MODULE_VIEWS: Record<ListedModuleId, ModuleView> = {
  '3d-distortion-lab': lazy(() => import('../components/LpbfEngineeringWorkspace').then(m => ({ default: m.LpbfEngineeringWorkspace }))),
  'lpbf-optimizer': lazy(() => import('../components/LpbfBayesianOptimizerLab').then(m => ({ default: m.LpbfBayesianOptimizerLab }))),
  'solidification-microstructure': lazy(() => import('../components/SolidificationMicrostructureLab').then(m => ({ default: m.SolidificationMicrostructureLab }))),
  'experimental-validation': lazy(() => import('../components/ExperimentalValidationLab').then(m => ({ default: m.ExperimentalValidationLab }))),
  'toolpath-studio': lazy(() => import('../components/LpbfToolpathStudioLab').then(m => ({ default: m.LpbfToolpathStudioLab }))),
  'murakami-fatigue': lazy(() => import('../components/MurakamiFatigueLab').then(m => ({ default: m.MurakamiFatigueLab }))),
  'keyhole-raytracing': lazy(() => import('../components/KeyholeRaytracingLab').then(m => ({ default: m.KeyholeRaytracingLab }))),
  'lpbf-dataset-comparison': lazy(() => import('../components/LpbfDatasetComparisonLab').then(m => ({ default: m.LpbfDatasetComparisonLab }))),
  'lpbf-calibration-scorecard': lazy(() => import('../components/LpbfCalibrationScorecardLab').then(m => ({ default: m.LpbfCalibrationScorecardLab }))),
  'database': lazy(() => import('../components/MaterialsDatabaseView').then(m => ({ default: m.MaterialsDatabaseView }))),
  'alloy-builder': lazy(() => import('../components/AlloyBuilder').then(m => ({ default: m.AlloyBuilder }))),
  'phase-diagram': lazy(() => import('../components/PhaseDiagramViewer').then(m => ({ default: m.PhaseDiagramViewer }))),
  'ttt-cct-kinetics': lazy(() => import('../components/PhaseKineticsTTTCCTStudio').then(m => ({ default: m.PhaseKineticsTTTCCTStudio }))),
  'micrograph': lazy(() => import('../components/MicrographLab').then(m => ({ default: m.MicrographLab }))),
  'eds-lab': lazy(() => import('../components/EDSSpectrumLab').then(m => ({ default: m.EDSSpectrumLab }))),
  'electrochem-suite': lazy(() => import('../components/CorrosionEngineeringLab').then(m => ({ default: m.CorrosionEngineeringLab }))),
  'icme-motor': lazy(() => import('../components/ICMEMultiScalePipelineStudio').then(m => ({ default: m.ICMEMultiScalePipelineStudio }))),
  'materials-project': lazy(() => import('../components/MaterialsProjectExplorer').then(m => ({ default: m.MaterialsProjectExplorer }))),
  'calculators': lazy(() => import('../components/PocketCalculators').then(m => ({ default: m.PocketCalculators }))),
  'research-hub': lazy(() => import('../components/AdvancedResearchHub').then(m => ({ default: m.AdvancedResearchHub }))),
  'experimental-data': lazy(() => import('../components/EvidenceWorkspace').then(m => ({ default: m.EvidenceWorkspace }))),
  'digital-twin': lazy(() => import('../components/DigitalTwinHub').then(m => ({ default: m.DigitalTwinHub }))),
  'uq-lab': lazy(() => import('../components/UQLab').then(m => ({ default: m.UQLab }))),
  'traceability': lazy(() => import('../components/EvidenceWorkspace').then(m => ({ default: m.EvidenceWorkspace }))),
  'copilot': lazy(() => import('../components/MetallurgyCopilot').then(m => ({ default: m.MetallurgyCopilot }))),
};
