import React, { useState, useEffect, useMemo, lazy, Suspense } from 'react';
import { ArrowRight, Search } from 'lucide-react';
import { MODULES, WORKSPACES, ModuleId, isModuleId, moduleFromHash, moduleHash } from './data/workspaces';
import { WorkspaceVisibility } from './components/WorkspaceVisibility';
import { ModuleBoundary } from './components/ModuleBoundary';
import { useMaterialSpecimenStore } from './store/useMaterialSpecimenStore';
import { AirgapBanner } from './components/AirgapBanner';
import { pythonComputationService, PythonEngineStatus } from './services/pythonComputationService';
import { startMaterialContextBridge, useMaterialContextBridgeStore } from './services/materialContextBridge';
import { startEngineeringJobPersistence } from './store/useLpbfEngineeringStore';
import { EvidenceBadge } from './components/sdk/EvidenceBadge';
import { SilentBoundary } from './components/SilentBoundary';
import { ModuleNav } from './components/ModuleNav';
import { formatExactNumber } from './utils/numberFormat';
import { canOpenPalette, isApplePlatform, paletteShortcutKeys, paletteShortcutLabel, useCommandPaletteShortcut, visibleModalOpen, type PaletteGate } from './hooks/useCommandPaletteShortcut';
import { isBootOverlayOpen, setBootOverlayOpen } from './utils/bootOverlay';
// Boot screen in its own chunk (keeps the index chunk in budget). The request starts as soon as this
// module evaluates, in parallel with React start-up; until it arrives an opaque cover hides the shell.
const bootChunk = import('./components/BootSequence');
// A failed chunk is handled by SilentBoundary at render (shell shows, with no boot screen to keep the palette closed).
bootChunk.catch(() => setBootOverlayOpen(false));
const BootSequence = lazy(() => bootChunk.then(m => ({ default: m.BootSequence })));
// Scientific context panel (mostly explanatory text) in its own chunk, requested at module evaluation like the
// boot chunk; it arrives while the boot overlay still covers the shell. Keeps the index chunk within budget.
const contextChunk = import('./components/ScientificContextPanel');
contextChunk.catch(() => undefined); // A failed chunk is handled by SilentBoundary at render.
const ScientificContextPanel = lazy(() => contextChunk.then(m => ({ default: m.ScientificContextPanel })));
// Own chunk: the strip sits at the end of the page, so it does not need to be in the index chunk.
const TelemetryStrip = lazy(() => import('./components/TelemetryStrip').then(m => ({ default: m.TelemetryStrip })));
// Own chunk: the engine availability dialog is opened on demand from the header status button. A factory,
// because React.lazy caches a rejected import: a retry after a failed chunk needs a new lazy component.
const loadEngineStatusDialog = () => lazy(() => import('./components/EngineStatusDialog').then(m => ({ default: m.EngineStatusDialog })));
// Own chunk: the command palette (Ctrl/Cmd+K or the header button) and its stylesheet load on first open. A factory
// for the same reason as the engine dialog: Retry after a failed chunk needs a fresh lazy component.
const loadCommandPalette = () => lazy(() => import('./components/CommandPaletteChunk').then(m => ({ default: m.CommandPalette })));
const APPLE = isApplePlatform(typeof navigator === 'undefined' ? '' : navigator.platform);
const SHORTCUT_LABEL = paletteShortcutLabel(APPLE);
const SHORTCUT_KEYS = paletteShortcutKeys(APPLE);
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
  const [dialogLoad, setDialogLoad] = useState(0);
  const EngineStatusDialog = useMemo(loadEngineStatusDialog, [dialogLoad]);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteLoad, setPaletteLoad] = useState(0);
  const CommandPalette = useMemo(loadCommandPalette, [paletteLoad]);
  const retryPalette = () => setPaletteLoad(n => n + 1);
  // The palette opens only when no other modal is up or requested: the engine dialog (also while its chunk loads),
  // the boot overlay, or a module's own dialog on screen.
  const paletteGate = (): PaletteGate => ({ paletteOpen, engineDialogOpen: showStatus, bootOverlayOpen: isBootOverlayOpen(), moduleModalOpen: visibleModalOpen() });
  const openPalette = () => { if (canOpenPalette(paletteGate())) setPaletteOpen(true); };
  useCommandPaletteShortcut(APPLE, paletteGate, () => setPaletteOpen(true));
  // Chunk failure: Retry remounts the boundary with a fresh lazy import; Close also resets it so the next open retries.
  // Chrome keeps a failed module fetch for the page's lifetime (browser-checked: Retry did not refetch), so the
  // alert also offers a reload, as ModuleBoundary does.
  const retryDialog = () => setDialogLoad(n => n + 1);
  const closeDialog = () => { setShowStatus(false); retryDialog(); };
  const specimen = useMaterialSpecimenStore(s => s.activeSpecimen);
  const materialTransfer = useMaterialContextBridgeStore();
  const activeModule = MODULES.find(m => m.id === activeTab)!;
  const activeWorkspace = WORKSPACES.find(w => w.id === activeModule.workspace)!;
  const filtered = MODULES.filter(m => `${m.label} ${m.description} ${m.workspace}`.toLowerCase().includes(moduleSearch.toLowerCase()));
  // Hash routing owns location.hash, so the skip link moves focus itself instead of following "#main-content".
  function skipToMain(event: React.MouseEvent) {
    event.preventDefault();
    document.getElementById('main-content')?.focus();
  }

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

  // The skip link follows the boot overlay in the DOM: when the overlay closes, the browser's Tab starting point is
  // where the overlay was, so the next Tab lands on the skip link (it is the first focusable element left on the page).
  return <><SilentBoundary><Suspense fallback={<div className="mk-boot-cover" aria-hidden="true" />}><BootSequence /></Suspense></SilentBoundary><a href="#main-content" className="mk-skip-link" onClick={skipToMain}>Skip to main content</a><div className="mk-shell min-h-screen text-slate-100 selection:bg-sky-500/25">
    <div className="mk-grid-overlay" aria-hidden="true" />
    <div className="mk-scanline" aria-hidden="true" />
    <AirgapBanner />
    <header className="mk-header sticky top-0 z-40 border-b px-4 lg:px-6 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3"><button aria-label="Toggle workspace navigation" aria-expanded={navigationOpen} onClick={() => setNavigationOpen(v => !v)} className="lg:hidden rounded-lg border border-cyan-400/30 bg-cyan-950/20 px-3 py-2 text-xs text-cyan-100">Modules</button><div className="hidden sm:contents"><div className="mk-brand-mark" aria-label="Metalliksa logo"><span className="mk-brand-crown" aria-hidden="true" /><span className="mk-brand-wing left" aria-hidden="true" /><span className="mk-brand-wing right" aria-hidden="true" /><span className="mk-brand-laser" aria-hidden="true" /><span className="mk-brand-face" aria-hidden="true"><span className="mk-brand-visor" /><span className="mk-brand-core" /></span><span className="mk-brand-orbit orbit-one" aria-hidden="true" /><span className="mk-brand-orbit orbit-two" aria-hidden="true" /></div></div><div><h1 className="mk-brand-title text-lg font-semibold text-white">METALLIKSA</h1><p className="text-[11px] uppercase tracking-[0.18em] text-cyan-100/80">Future materials command system</p></div></div>
        <div className="flex items-center gap-2 sm:gap-3"><button type="button" aria-haspopup="dialog" aria-keyshortcuts={SHORTCUT_KEYS} onClick={openPalette} className="mk-status inline-flex items-center gap-2 px-3 py-2 text-xs text-cyan-100"><Search className="h-3.5 w-3.5" aria-hidden="true"/><span className="sr-only sm:not-sr-only">Search modules</span><kbd aria-hidden="true" className="hidden sm:inline font-mono text-[10px] text-cyan-100/80">{SHORTCUT_LABEL}</kbd></button><span className="mk-hud-chip hidden sm:inline">Local control plane</span><button onClick={() => { setPaletteOpen(false); setShowStatus(true); }} className="mk-status px-3 py-2 text-xs text-cyan-100"><span className={`mr-2 inline-block h-1.5 w-1.5 rounded-full ${checking ? 'bg-amber-300 animate-pulse' : status?.online ? 'bg-emerald-300' : 'bg-amber-300'}`}/>{checking ? 'Checking…' : status?.online ? 'Engine connected' : 'Engine unavailable'}</button></div>
      </div>
    </header>
    <div className="flex flex-col lg:flex-row">
      <aside className={`${navigationOpen ? 'block' : 'hidden'} mk-sidebar lg:block lg:w-60 xl:w-64 shrink-0 border-b lg:border-b-0 lg:border-r p-4 lg:sticky lg:top-[var(--mk-header-h)] lg:h-[calc(100vh_-_var(--mk-header-h))] overflow-y-auto`}>
        <div className="mb-5 flex items-center justify-between"><div><p className="text-[10px] uppercase tracking-[0.18em] text-cyan-100/75">Navigation</p><p className="mt-1 text-xs text-slate-200">Engineering surfaces</p></div><span className="mk-count-badge font-mono text-[10px]">{String(MODULES.length).padStart(2, '0')}</span></div><label htmlFor="module-search" className="mb-2 block text-xs text-cyan-50/85">Find a module</label><div className="relative mb-5"><Search className="absolute left-3 top-3 w-4 h-4 text-cyan-200/80"/><input id="module-search" type="search" value={moduleSearch} onChange={e => setModuleSearch(e.target.value)} placeholder="Materials, evidence…" className="aero-input w-full rounded-xl border pl-9 pr-2 py-2.5 text-sm focus:ring-2 focus:ring-cyan-400/40"/></div>
        <ModuleNav modules={filtered} activeTab={activeTab} activeWorkspace={activeWorkspace.id} onNavigate={navigate} />
      </aside>
      <main id="main-content" tabIndex={-1} className="flex-1 min-w-0 p-4 sm:p-6 xl:p-8">
        <div className="mk-content-header mb-5 border-b pb-5 pl-4"><p className="mb-2 text-[10px] uppercase tracking-[0.2em] text-cyan-200">{activeWorkspace.label} / Active surface</p><div className="flex flex-wrap items-center gap-3"><h2 className="text-2xl font-semibold text-white">{activeModule.label}</h2><span title="Module maturity; this is not a validation claim for any result." className={`mk-scope-badge ${activeModule.scope === 'Preview' ? 'is-preview' : ''}`}>{activeModule.scope}</span><EvidenceBadge moduleId={activeModule.id} /></div><p className="mt-2 max-w-4xl text-sm leading-6 text-slate-200">{activeModule.description}</p></div>
        <details className="mb-5 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3 text-xs">
          <summary className="cursor-pointer text-slate-300">Shared material · <span className="text-sky-200">{specimen.name}</span> · {formatExactNumber(specimen.lpbf.laserPower_W)} W / {formatExactNumber(specimen.lpbf.scanSpeed_mms)} mm/s <span className="ml-2 text-slate-500">Context & trust</span></summary>
          <div className="mt-3 grid gap-3 md:grid-cols-2 text-slate-400"><p>Hatch {specimen.lpbf.hatch_um} µm · Layer {specimen.lpbf.layer_um} µm · Beam {specimen.lpbf.beamDiameter_um} µm · Preheat {specimen.lpbf.preheatTemp_C} °C. Material and process are shared across LPBF stages.</p><p>Module scope: Production / Research / Preview / Unresolved. Result evidence: Measured / Validated simulation / Calibrated simulation / Literature estimate / Screening only / Unresolved. Conservation, convergence and experimental validation are separate checks.</p><p>Visited modules retain their local view during navigation. Specimen and registry persist in this browser. Meshes and most specialist views remain session-only.</p></div>
        </details>
        {materialTransfer.message && <p role={materialTransfer.error ? 'alert' : 'status'} className={`mb-4 rounded-lg border px-4 py-3 text-xs ${materialTransfer.error ? 'border-amber-500/30 text-amber-200' : 'border-cyan-500/20 text-cyan-200'}`}>{materialTransfer.message}</p>}
        {activeTab !== 'ai-orchestrator' && <SilentBoundary><Suspense fallback={null}><ScientificContextPanel moduleId={activeTab} specimen={specimen} /></Suspense></SilentBoundary>}
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
    {showStatus && <SilentBoundary key={dialogLoad} fallback={<div role="alert" className="fixed bottom-4 left-4 right-4 z-50 mx-auto max-w-md rounded-lg border border-amber-500/30 bg-slate-950 p-4 text-sm text-amber-200">Engine availability details could not be loaded. <button onClick={retryDialog} className="ml-2 underline">Retry</button> <button onClick={() => window.location.reload()} className="ml-2 underline">Reload application</button> <button onClick={closeDialog} className="ml-2 underline">Close</button></div>}><Suspense fallback={null}><EngineStatusDialog status={status} statusError={statusError} checking={checking} onClose={() => setShowStatus(false)} onRefresh={() => void refreshStatus()} /></Suspense></SilentBoundary>}
    {paletteOpen && <SilentBoundary key={paletteLoad} fallback={<div role="alert" className="fixed bottom-4 left-4 right-4 z-50 mx-auto max-w-md rounded-lg border border-amber-500/30 bg-slate-950 p-4 text-sm text-amber-200">Module search could not be loaded. <button onClick={retryPalette} className="ml-2 underline">Retry</button> <button onClick={() => window.location.reload()} className="ml-2 underline">Reload application</button> <button onClick={() => { setPaletteOpen(false); retryPalette(); }} className="ml-2 underline">Close</button></div>}><Suspense fallback={null}><CommandPalette activeTab={activeTab} onNavigate={navigate} onClose={() => setPaletteOpen(false)} /></Suspense></SilentBoundary>}
  </div></>;
}


