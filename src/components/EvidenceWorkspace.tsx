import React, { useState } from 'react';
import { Download, ArrowRight } from 'lucide-react';
import { useResearchStore } from '../store/useResearchStore';
import { useMaterialSpecimenStore } from '../store/useMaterialSpecimenStore';
import { useLpbfEngineeringStore } from '../store/useLpbfEngineeringStore';
import { peekLpbfBuildJobKey, useLpbfBuildJobStore } from '../store/useLpbfBuildJobStore';
import { getResearchIntegrationRecords, researchReviewIssues, researchEvidenceLabel } from '../utils/researchRegistry';
import { ResearchIntegrationPanel } from './ResearchIntegrationPanel';

export function EvidenceWorkspace({ mode }: { mode: 'experimental' | 'traceability' }) {
  const research = useResearchStore();
  const specimen = useMaterialSpecimenStore(s => s.activeSpecimen);
  const engineering = useLpbfEngineeringStore();
  const build = useLpbfBuildJobStore();
  const [allMaterials, setAllMaterials] = useState(false);
  const [notice, setNotice] = useState('');
  const findings = research.findings.filter(f => (allMaterials || f.materialId === specimen.id) && (mode !== 'experimental' || f.evidenceType === 'measured'));
  const integrations = getResearchIntegrationRecords(research, undefined, specimen.id);
  const navigate = (tabId: string) => window.dispatchEvent(new CustomEvent('metallix-navigate-tab', { detail: { tabId } }));
  const download = () => {
    try {
      const packageData = {
        schemaVersion: 1, exportedAt: new Date().toISOString(), scope: 'Research evidence package; not a qualification certificate',
        activeSpecimen: specimen,
        research: research.exportSnapshot(),
        engineering: { job: engineering.job ?? null, submittedInput: engineering.submittedInput ?? null,
          scope: 'Job results describe submitted inputs. Compare these with the active specimen before reuse. No experimental validation is implied.' },
        buildScreening: { alignedWithCurrentInputs: build.lastKey === peekLpbfBuildJobKey(), job: build.job,
          scope: 'Analytical screening; the verdict is a screening indication (not validated against build outcomes) from the Python build-job solver.' },
        missingEvidence: ['Independent experimental validation and applicable acceptance criteria must be reviewed.', 'Source classifications and findings are user-reviewed records, not externally certified data.', 'Full worker case artifacts and uploaded meshes are stored separately and are not embedded in this JSON.'],
      };
      const url = URL.createObjectURL(new Blob([JSON.stringify(packageData, null, 2)], { type: 'application/json' }));
      const a = document.createElement('a'); a.href = url; a.download = `metalliksa-evidence-${new Date().toISOString().slice(0, 10)}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice('Evidence package exported. Retain worker artifacts separately for reproducibility.');
    } catch (error) { setNotice(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`); }
  };
  return <div className="space-y-5">
    <section className="rounded-xl border border-slate-700 bg-slate-900/40 p-5">
      <div className="flex flex-wrap justify-between items-start gap-4"><div><h3 className="text-lg font-semibold">{mode === 'experimental' ? 'Experimental evidence register' : 'Traceable review package'}</h3><p className="mt-2 text-sm text-slate-400 max-w-3xl">{mode === 'experimental' ? 'Measured findings remain attached to their source, process conditions, uncertainty and material. A reviewed source is not automatically a validation dataset.' : 'Capture the current material, submitted simulation inputs, job result and complete research registry for engineering review.'}</p></div><button onClick={download} className="inline-flex items-center gap-2 bg-sky-600 hover:bg-sky-500 rounded-lg px-4 py-2 text-sm"><Download className="w-4 h-4"/>Export evidence package</button></div>
      {notice && <p role="status" className="mt-3 text-xs text-cyan-200">{notice}</p>}
      <dl className="mt-5 grid gap-4 sm:grid-cols-3 text-sm"><div><dt className="text-slate-500 text-xs">Active material</dt><dd className="mt-1">{specimen.name}</dd></div><div><dt className="text-slate-500 text-xs">Engineering job</dt><dd className="mt-1 break-all">{engineering.job ? `${engineering.job.status} · ${engineering.job.id}` : 'No simulation job in this session'}</dd></div><div><dt className="text-slate-500 text-xs">Reviewed module references</dt><dd className="mt-1">{integrations.length} · {research.feedback.length} feedback records across registry</dd></div></dl>
    </section>
    {mode === 'experimental' && <ResearchIntegrationPanel targetModule="validation-dataset" />}
    <section className="rounded-xl border border-slate-800 p-5">
      <div className="flex flex-wrap justify-between gap-3 mb-4"><h3 className="font-semibold">{mode === 'experimental' ? 'Measured findings' : 'Finding provenance'}</h3><label className="text-xs text-slate-400 flex gap-2 items-center"><input type="checkbox" checked={allMaterials} onChange={e => setAllMaterials(e.target.checked)}/>Show all materials</label></div>
      {!findings.length && <div className="py-8 text-sm text-slate-400"><p>No {mode === 'experimental' ? 'measured ' : ''}findings registered for {allMaterials ? 'any material' : specimen.name}.</p><p className="mt-2 text-xs">Record the measurement value, unit, method, conditions and exact source location in Research Hub. Unknown information must remain explicit.</p></div>}
      <ul className="divide-y divide-slate-800">{findings.map(finding => {
        const source = research.sources.find(s => s.id === finding.sourceId);
        const gaps = researchReviewIssues(finding, source);
        return <li key={finding.id} className="py-4"><div className="flex flex-wrap justify-between gap-2"><h4 className="text-sm font-semibold">{finding.materialName} · {finding.property}: {finding.value} {finding.unit}</h4><span className="text-xs text-amber-200">{researchEvidenceLabel(finding)} · {finding.reviewStatus}</span></div><p className="mt-2 text-xs text-slate-400">{source?.title ?? 'Source unavailable'} · {source?.doi || source?.url} · {finding.locator}</p><p className="mt-1 text-xs text-slate-500">Method: {finding.conditions.measurementMethod || 'Unresolved'} · Machine: {finding.conditions.machine || 'Unresolved'} · Powder: {finding.conditions.powderCondition || 'Unresolved'} · Heat treatment: {finding.conditions.heatTreatment || 'Unresolved'}</p><p className="mt-1 text-xs text-slate-500">Uncertainty: {finding.uncertainty === undefined ? 'Not supplied' : `± ${finding.uncertainty} ${finding.unit}`} · {finding.uncertaintyDescription} · Confidence: {finding.confidence}</p>{gaps.length > 0 && <p className="mt-2 text-xs text-amber-300">Incomplete review: {gaps.join(' ')}</p>}{finding.conflictsWith.length > 0 && <p className="mt-2 text-xs text-fuchsia-300">Conflicting findings flagged. Integration requires resolution.</p>}</li>;
      })}</ul>
      <button onClick={() => { research.setActiveTab(mode === 'experimental' ? 'extract' : 'registry'); navigate('research-hub'); }} className="mt-3 text-sm text-sky-300 inline-flex gap-2 items-center">{mode === 'experimental' ? 'Record measurement in Research Hub' : 'Review sources and feedback'}<ArrowRight className="w-4 h-4"/></button>
    </section>
    <p className="text-xs text-amber-200/80">Qualification remains unresolved until applicable experimental evidence, specimen/build traceability and acceptance criteria are independently reviewed. Energy conservation and numerical convergence do not establish experimental validation.</p>
  </div>;
}
