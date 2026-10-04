import React, { useState, useEffect, lazy, Suspense } from 'react';
import { Cpu, X, ArrowRight, Search, Layers, BookOpen, Flame, Network } from 'lucide-react';
import { MODULES, WORKSPACES, ModuleId, isModuleId, moduleFromHash, moduleHash } from './data/workspaces';
import { WorkspaceVisibility } from './components/WorkspaceVisibility';
import { ModuleBoundary } from './components/ModuleBoundary';
import { AccessibleModal } from './components/AccessibleModal';
import { useMaterialSpecimenStore } from './store/useMaterialSpecimenStore';
import { AirgapBanner } from './components/AirgapBanner';
import { pythonComputationService, PythonEngineStatus } from './services/pythonComputationService';
import { startMaterialContextBridge, useMaterialContextBridgeStore } from './services/materialContextBridge';
import { startEngineeringJobPersistence } from './store/useLpbfEngineeringStore';
import { ScientificContextPanel } from './components/ScientificContextPanel';
import { BootSequence } from './components/BootSequence';
import { SilentBoundary } from './components/SilentBoundary';
// Own chunk: the strip sits at the end of the page, so it does not need to be in the index chunk.
const TelemetryStrip = lazy(() => import('./components/TelemetryStrip').then(m => ({ default: m.TelemetryStrip })));
const EvidenceWorkspace = lazy(() => import('./components/EvidenceWorkspace').then(m => ({ default: m.EvidenceWorkspace })));
const ResearchIntegrationPanel = lazy(() => import('./components/ResearchIntegrationPanel').then(m => ({ default: m.ResearchIntegrationPanel })));
const PocketCalculators = lazy(() => import("./components/PocketCalculators").then(m => ({ default: m.PocketCalculators })));
const MicrographLab = lazy(() => import("./components/MicrographLab").then(m => ({ default: m.MicrographLab })));
const AlloyBuilder = lazy(() => import("./components/AlloyBuilder").then(m => ({ default: m.AlloyBuilder })));
const MaterialsDatabaseView = lazy(() => import("./components/MaterialsDatabaseView").then(m => ({ default: m.MaterialsDatabaseView })));
const MetallurgyCopilot = lazy(() => import("./components/MetallurgyCopilot").then(m => ({ default: m.MetallurgyCopilot })));
const CorrosionEngineeringLab = lazy(() => import("./components/CorrosionEngineeringLab").then(m => ({ default: m.CorrosionEngineeringLab })));
const MaterialsProjectExplorer = lazy(() => import("./components/MaterialsProjectExplorer").then(m => ({ default: m.MaterialsProjectExplorer })));
const ICMEMultiScalePipelineStudio = lazy(() => import("./components/ICMEMultiScalePipelineStudio").then(m => ({ default: m.ICMEMultiScalePipelineStudio })));
const StandardQualificationEngine = lazy(() => import("./components/StandardQualificationEngine").then(m => ({ default: m.StandardQualificationEngine })));
const LpbfEngineeringWorkspace = lazy(() => import("./components/LpbfEngineeringWorkspace").then(m => ({ default: m.LpbfEngineeringWorkspace })));
const LpbfBayesianOptimizerLab = lazy(() => import("./components/LpbfBayesianOptimizerLab").then(m => ({ default: m.LpbfBayesianOptimizerLab })));
const SolidificationMicrostructureLab = lazy(() => import("./components/SolidificationMicrostructureLab").then(m => ({ default: m.SolidificationMicrostructureLab })));  // Phase 8
const ThermomechanicalDistortionLab = lazy(() => import("./components/ThermomechanicalDistortionLab").then(m => ({ default: m.ThermomechanicalDistortionLab })));  // Phase 9
const ExperimentalValidationLab = lazy(() => import("./components/ExperimentalValidationLab").then(m => ({ default: m.ExperimentalValidationLab }))); // Phase 10
const ModulusFNOLab = lazy(() => import("./components/ModulusFNOLab").then(m => ({ default: m.ModulusFNOLab }))); // Phase 11
const LpbfToolpathStudioLab = lazy(() => import("./components/LpbfToolpathStudioLab").then(m => ({ default: m.LpbfToolpathStudioLab }))); // Phase 12
const ToolpathThermalMapLab = lazy(() => import("./components/ToolpathThermalMapLab").then(m => ({ default: m.ToolpathThermalMapLab }))); // Phase 12+17
const IndustrialCertificationLab = lazy(() => import("./components/IndustrialCertificationLab").then(m => ({ default: m.IndustrialCertificationLab }))); // Phase 9 & 10
const MurakamiFatigueLab = lazy(() => import("./components/MurakamiFatigueLab").then(m => ({ default: m.MurakamiFatigueLab }))); // Phase 13
const LpbfDefectTwinLab = lazy(() => import("./components/LpbfDefectTwinLab").then(m => ({ default: m.LpbfDefectTwinLab }))); // Phase 14
const LpbfAdaptiveMitigationLab = lazy(() => import("./components/LpbfAdaptiveMitigationLab").then(m => ({ default: m.LpbfAdaptiveMitigationLab }))); // Phase 15
const MultiLaserPlumeLab = lazy(() => import("./components/MultiLaserPlumeLab").then(m => ({ default: m.MultiLaserPlumeLab }))); // Phase 16
const MultiTrackThermalLab = lazy(() => import("./components/MultiTrackThermalLab").then(m => ({ default: m.MultiTrackThermalLab }))); // Phase 17
const PowderDEMCompactionLab = lazy(() => import("./components/PowderDEMCompactionLab").then(m => ({ default: m.PowderDEMCompactionLab }))); // Phase 18
const OpticalTomographyLab = lazy(() => import("./components/OpticalTomographyLab").then(m => ({ default: m.OpticalTomographyLab }))); // Phase 19
const TransientEnthalpy3DGPULab = lazy(() => import("./components/TransientEnthalpy3DGPULab").then(m => ({ default: m.TransientEnthalpy3DGPULab }))); // Phase 22
const KeyholeRaytracingLab = lazy(() => import("./components/KeyholeRaytracingLab").then(m => ({ default: m.KeyholeRaytracingLab }))); // Phase 26

const AerospaceAuditReportGenerator = lazy(() => import("./components/AerospaceAuditReportGenerator").then(m => ({ default: m.AerospaceAuditReportGenerator })));
const AdvancedResearchHub = lazy(() => import("./components/AdvancedResearchHub").then(m => ({ default: m.AdvancedResearchHub })));
const PhaseDiagramViewer = lazy(() => import("./components/PhaseDiagramViewer").then(m => ({ default: m.PhaseDiagramViewer })));
const EDSSpectrumLab = lazy(() => import("./components/EDSSpectrumLab").then(m => ({ default: m.EDSSpectrumLab })));
const DigitalTwinHub = lazy(() => import("./components/DigitalTwinHub").then(m => ({ default: m.DigitalTwinHub })));
const PhaseKineticsTTTCCTStudio = lazy(() => import("./components/PhaseKineticsTTTCCTStudio").then(m => ({ default: m.PhaseKineticsTTTCCTStudio })));
const UQLab = lazy(() => import("./components/UQLab").then(m => ({ default: m.UQLab })));
const AIOrchestratorPanel = lazy(() => import("./components/AIOrchestratorPanel").then(m => ({ default: m.AIOrchestratorPanel })));

export type NavSubTab = ModuleId;
export type DisciplineHubId = typeof WORKSPACES[number]['id'];

function initialTab(): ModuleId {
  const linked = moduleFromHash(window.location.hash);
  if (linked) return linked;
  const parameters = new URLSearchParams(window.location.search);
  if (parameters.has('lpbfStage') || parameters.has('lpbfSubTab')) return '3d-distortion-lab';
  // Explicit unknown routes go to LPBF instead of silently restoring another workspace.
  if (window.location.hash) return '3d-distortion-lab';
  try { const saved = localStorage.getItem('metallixa.workspace.module'); if (isModuleId(saved)) return saved; } catch { /* Optional storage. */ }
  return '3d-distortion-lab';
}

export default function App() {
  const [activeTab, setActiveTab] = useState<ModuleId>(initialTab);
  const [visited, setVisited] = useState<ModuleId[]>(() => [initialTab()]);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [moduleSearch, setModuleSearch] = useState('');
  const [showStatus, setShowStatus] = useState(false);
  const [status, setStatus] = useState<PythonEngineStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const specimen = useMaterialSpecimenStore(s => s.activeSpecimen);
  const materialTransfer = useMaterialContextBridgeStore();
  const activeModule = MODULES.find(m => m.id === activeTab)!;
  const activeWorkspace = WORKSPACES.find(w => w.id === activeModule.workspace)!;
  const filtered = MODULES.filter(m => `${m.label} ${m.description} ${m.workspace}`.toLowerCase().includes(moduleSearch.toLowerCase()));

  function activate(id: ModuleId) {
    setActiveTab(id);
    setVisited(current => current.includes(id) ? current : [...current, id]);
    setNavigationOpen(false);
  }
  function navigate(id: string) {
    if (!isModuleId(id)) return;
    activate(id);
    if (window.location.hash !== moduleHash(id)) window.location.hash = moduleHash(id);
  }
  async function refreshStatus(force = true) {
    setChecking(true); setStatusError(null);
    try { setStatus(await pythonComputationService.checkEngineStatus(force)); }
    catch (error) { setStatus(null); setStatusError(error instanceof Error ? error.message : 'Engine status unavailable.'); }
    finally { setChecking(false); }
  }
  useEffect(() => {
    void refreshStatus(false);
    const onHash = () => activate(moduleFromHash(window.location.hash) ?? '3d-distortion-lab');
    const onNavigate = (event: Event) => {
      const id = (event as CustomEvent<{ tabId?: string }>).detail?.tabId;
      if (id) navigate(id);
    };
    window.addEventListener('hashchange', onHash);
    window.addEventListener('metallix-navigate-tab', onNavigate);
    return () => { window.removeEventListener('hashchange', onHash); window.removeEventListener('metallix-navigate-tab', onNavigate); };
  }, []);
  useEffect(() => startMaterialContextBridge(), []);
  useEffect(() => startEngineeringJobPersistence(), []);
  useEffect(() => {
    try { localStorage.setItem('metallixa.workspace.module', activeTab); } catch { /* Navigation still works. */ }
  }, [activeTab]);

  function renderModule(id: ModuleId) {
    switch (id) {
      case '3d-distortion-lab': return <LpbfEngineeringWorkspace />;
      case 'lpbf-optimizer': return <LpbfBayesianOptimizerLab />;
      case 'solidification-microstructure': return <SolidificationMicrostructureLab />;  // Phase 8
      case 'thermomechanical-distortion': return <ThermomechanicalDistortionLab />; // Phase 9
      case 'experimental-validation': return <ExperimentalValidationLab />; // Phase 10
      case 'modulus-fno-lab': return <ModulusFNOLab />; // Phase 11
      case 'toolpath-studio': return <LpbfToolpathStudioLab />; // Phase 12
      case 'toolpath-thermal-map': return <ToolpathThermalMapLab />; // Phase 12+17
      case 'industrial-certification': return <IndustrialCertificationLab />; // Phase 9 & 10
      case 'murakami-fatigue': return <MurakamiFatigueLab />; // Phase 13
      case 'defect-twin': return <LpbfDefectTwinLab />; // Phase 14
      case 'adaptive-mitigation': return <LpbfAdaptiveMitigationLab />; // Phase 15
      case 'multilaser-plume': return <MultiLaserPlumeLab />; // Phase 16
      case 'thermal-accumulation': return <MultiTrackThermalLab />; // Phase 17
      case 'powder-compaction': return <PowderDEMCompactionLab />; // Phase 18
      case 'optical-tomography': return <OpticalTomographyLab />; // Phase 19
      case 'transient-3d-gpu': return <TransientEnthalpy3DGPULab />; // Phase 22
      case 'keyhole-raytracing': return <KeyholeRaytracingLab />; // Phase 26
      case 'research-hub': return <AdvancedResearchHub />;
      case 'experimental-data': return <EvidenceWorkspace mode="experimental" />;
      case 'traceability': return <EvidenceWorkspace mode="traceability" />;
      case 'uq-lab': return <UQLab onNavigate={navigate} />;
      case 'digital-twin': return <DigitalTwinHub onNavigateToModule={navigate} />;
      case 'electrochem-suite': return <CorrosionEngineeringLab />;
      case 'aerospace-pdf-audit': return <AerospaceAuditReportGenerator />;
      case 'ttt-cct-kinetics': return <PhaseKineticsTTTCCTStudio onSendToModule={navigate} />;
      case 'icme-motor': return <ICMEMultiScalePipelineStudio />;
      case 'qualification': return <StandardQualificationEngine />;
      case 'materials-project': return <MaterialsProjectExplorer />;
      case 'calculators': return <PocketCalculators />;
      case 'eds-lab': return <EDSSpectrumLab />;
      case 'micrograph': return <MicrographLab />;
      case 'alloy-builder': return <AlloyBuilder onNavigate={navigate} />;
      case 'database': return <MaterialsDatabaseView onNavigate={navigate} />;
      case 'phase-diagram': return <PhaseDiagramViewer />;
      case 'copilot': return <MetallurgyCopilot />;
      case 'ai-orchestrator': return <AIOrchestratorPanel />;
    }
  }

  return <><BootSequence /><div className="mk-shell min-h-screen text-slate-100 selection:bg-sky-500/25">
    <div className="mk-grid-overlay" aria-hidden="true" />
    <div className="mk-scanline" aria-hidden="true" />
    <AirgapBanner />
    <header className="mk-header sticky top-0 z-40 border-b px-4 lg:px-6 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3"><button aria-label="Toggle workspace navigation" aria-expanded={navigationOpen} onClick={() => setNavigationOpen(v => !v)} className="lg:hidden rounded-lg border border-cyan-400/30 bg-cyan-950/20 px-3 py-2 text-xs text-cyan-100">Modules</button><div className="mk-brand-mark" aria-label="Metalliksa logo"><span className="mk-brand-crown" aria-hidden="true" /><span className="mk-brand-wing left" aria-hidden="true" /><span className="mk-brand-wing right" aria-hidden="true" /><span className="mk-brand-laser" aria-hidden="true" /><span className="mk-brand-face" aria-hidden="true"><span className="mk-brand-visor" /><span className="mk-brand-core" /></span><span className="mk-brand-orbit orbit-one" aria-hidden="true" /><span className="mk-brand-orbit orbit-two" aria-hidden="true" /></div><div><h1 className="mk-brand-title text-lg font-semibold text-white">METALLIKSA</h1><p className="text-[11px] uppercase tracking-[0.18em] text-cyan-100/80">Future materials command system</p></div></div>
        <div className="flex items-center gap-3"><span className="mk-hud-chip hidden sm:inline">Local control plane</span><button onClick={() => setShowStatus(true)} className="mk-status px-3 py-2 text-xs text-cyan-100"><span className={`mr-2 inline-block h-1.5 w-1.5 rounded-full ${checking ? 'bg-amber-300 animate-pulse' : status?.online ? 'bg-emerald-300' : 'bg-amber-300'}`}/>{checking ? 'Checking…' : status?.online ? 'Engine connected' : 'Engine unavailable'}</button></div>
      </div>
    </header>
    <div className="flex flex-col lg:flex-row">
      <aside className={`${navigationOpen ? 'block' : 'hidden'} mk-sidebar lg:block lg:w-60 xl:w-64 shrink-0 border-b lg:border-b-0 lg:border-r p-4 lg:sticky lg:top-[77px] lg:h-[calc(100vh-77px)] overflow-y-auto`}>
        <div className="mb-5 flex items-center justify-between"><div><p className="text-[10px] uppercase tracking-[0.18em] text-cyan-100/75">Navigation</p><p className="mt-1 text-xs text-slate-200">Engineering surfaces</p></div><span className="mk-count-badge font-mono text-[10px]">{String(MODULES.length).padStart(2, '0')}</span></div><label htmlFor="module-search" className="mb-2 block text-xs text-cyan-50/85">Find a module</label><div className="relative mb-5"><Search className="absolute left-3 top-3 w-4 h-4 text-cyan-200/80"/><input id="module-search" type="search" value={moduleSearch} onChange={e => setModuleSearch(e.target.value)} placeholder="Materials, evidence…" className="aero-input w-full rounded-xl border pl-9 pr-2 py-2.5 text-sm focus:ring-2 focus:ring-cyan-400/40"/></div>
        <nav aria-label="Engineering workspaces">
          {WORKSPACES.map(workspace => {
            const Icon = workspace.id === 'lpbf' ? Flame : workspace.id === 'materials' ? Layers : workspace.id === 'orchestration' ? Network : BookOpen;
            const modules = filtered.filter(m => m.workspace === workspace.id);
            if (!modules.length) return null;
            return <div key={workspace.id} className="mb-5"><button onClick={() => navigate(workspace.defaultModule)} className={`mb-2 flex items-center gap-2 text-xs font-semibold ${workspace.id === activeWorkspace.id ? 'text-cyan-100' : 'text-slate-200'}`}><Icon className="w-4 h-4"/>{workspace.label}</button><div className="space-y-0.5">{modules.map(module => <button key={module.id} aria-current={activeTab === module.id ? 'page' : undefined} title={module.description} onClick={() => navigate(module.id)} className={`mk-nav-item w-full text-left px-3 py-2 text-sm transition-colors ${activeTab === module.id ? 'is-active text-cyan-50 font-medium' : 'text-slate-300 hover:text-white'}`}>{module.label}</button>)}</div></div>;
          })}
          {!filtered.length && <p role="status" className="text-sm text-slate-400">No matching modules. Try a material, method or workflow name.</p>}
        </nav>
      </aside>
      <main className="flex-1 min-w-0 p-4 sm:p-6 xl:p-8">
        <div className="mk-content-header mb-5 border-b pb-5 pl-4"><p className="mb-2 text-[10px] uppercase tracking-[0.2em] text-cyan-200">{activeWorkspace.label} / Active surface</p><div className="flex flex-wrap items-center gap-3"><h2 className="text-2xl font-semibold text-white">{activeModule.label}</h2><span title="Module maturity; this is not a validation claim for any result." className={`mk-scope-badge ${activeModule.scope === 'Preview' ? 'is-preview' : ''}`}>{activeModule.scope}</span></div><p className="mt-2 max-w-4xl text-sm leading-6 text-slate-200">{activeModule.description}</p></div>
        <details className="mb-5 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3 text-xs">
          <summary className="cursor-pointer text-slate-300">Shared material · <span className="text-sky-200">{specimen.name}</span> · {specimen.lpbf.laserPower_W} W / {specimen.lpbf.scanSpeed_mms} mm/s <span className="ml-2 text-slate-500">Context & trust</span></summary>
          <div className="mt-3 grid gap-3 md:grid-cols-2 text-slate-400"><p>Hatch {specimen.lpbf.hatch_um} µm · Layer {specimen.lpbf.layer_um} µm · Beam {specimen.lpbf.beamDiameter_um} µm · Preheat {specimen.lpbf.preheatTemp_C} °C. Material and process are shared across LPBF stages.</p><p>Module scope: Production / Research / Preview / Unresolved. Result evidence: Measured / Validated simulation / Calibrated simulation / Literature estimate / Screening only / Unresolved. Conservation, convergence and experimental validation are separate checks.</p><p>Visited modules retain their local view during navigation. Specimen and registry persist in this browser. Meshes and most specialist views remain session-only.</p></div>
        </details>
        {materialTransfer.message && <p role={materialTransfer.error ? 'alert' : 'status'} className={`mb-4 rounded-lg border px-4 py-3 text-xs ${materialTransfer.error ? 'border-amber-500/30 text-amber-200' : 'border-cyan-500/20 text-cyan-200'}`}>{materialTransfer.message}</p>}
        {activeTab !== 'ai-orchestrator' && <ScientificContextPanel moduleId={activeTab} specimen={specimen} />}
        {visited.map(id => <div key={id} hidden={id !== activeTab} data-module={id}><WorkspaceVisibility visible={id === activeTab}>
          <ModuleBoundary label={MODULES.find(m => m.id === id)!.label}>
            <Suspense fallback={<div role="status" className="min-h-60 flex items-center justify-center text-slate-400">Loading engineering module…</div>}>
              {(id === 'database' || id === '3d-distortion-lab') && <ResearchIntegrationPanel targetModule={id === 'database' ? 'materials-db' : 'lpbf-solver'} />}
              {renderModule(id)}
            </Suspense>
          </ModuleBoundary>
        </WorkspaceVisibility></div>)}
        <div className="mt-8 border-t border-slate-800 pt-4 flex flex-wrap justify-between items-center gap-3"><p className="text-xs text-slate-500">Review inputs, source applicability and evidence before making an engineering decision.</p><button onClick={() => navigate(activeModule.next)} className="inline-flex gap-2 items-center text-sm text-sky-300 hover:text-sky-100">Next: {MODULES.find(m => m.id === activeModule.next)?.label}<ArrowRight className="h-4 w-4"/></button></div>
      </main>
    </div>
    <SilentBoundary><Suspense fallback={null}><TelemetryStrip engine={status} engineChecking={checking || (status === null && statusError === null)} moduleCount={MODULES.length} /></Suspense></SilentBoundary>
    {showStatus && <AccessibleModal open onClose={() => setShowStatus(false)} labelledBy="engine-title" closeOnBackdrop overlayClassName="bg-slate-950/80 p-4" panelClassName="w-full max-w-xl max-h-[85vh] overflow-y-auto rounded-xl border border-slate-700 bg-slate-950 p-6">
        <div className="flex justify-between items-center"><h2 id="engine-title" className="font-semibold flex gap-2 items-center"><Cpu className="w-5 h-5 text-sky-400"/>Engine availability</h2><button aria-label="Close engine status" onClick={() => setShowStatus(false)}><X className="w-5 h-5"/></button></div>
        <p className="my-4 text-sm text-slate-400">Availability is reported by the backend. An installed solver does not establish a validated physical model.</p>
        {statusError && <p role="alert" className="text-sm text-amber-300">{statusError}</p>}
        <p className="text-sm mb-3">{status?.online ? `Python ${status.pythonVersion ?? 'version unavailable'} · ${status.status}` : 'Python backend unavailable. Check the local server and Python runtime.'}</p>
        <dl className="divide-y divide-slate-800">{(Object.entries(status?.subsystems ?? {}) as [string, { available: boolean }][]).map(([name, subsystem]) => <div key={name} className="py-2 flex justify-between gap-3 text-xs"><dt>{name.replaceAll('_', ' ')}</dt><dd className={subsystem.available ? 'text-sky-300' : 'text-amber-300'}>{subsystem.available ? 'Available' : 'Unavailable'}</dd></div>)}</dl>
        {!status?.subsystems && <p className="text-xs text-slate-500">Subsystem status has not been reported.</p>}
        <button disabled={checking} onClick={() => void refreshStatus()} className="mt-4 rounded-lg bg-sky-600 px-4 py-2 text-sm disabled:opacity-50">{checking ? 'Checking…' : 'Refresh status'}</button>
    </AccessibleModal>}
  </div></>;
}


