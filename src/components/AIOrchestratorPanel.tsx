import React, { useState } from "react";
import { Bot, Check, Database, FileSearch, FlaskConical, ShieldCheck, Upload, X } from "lucide-react";

type PlanResponse = { success: boolean; plan: string; agents: Record<string, string>; evidence: { inventory: string; review: string }; uploadAllowed: boolean; sourceCollectionAllowed?: boolean; collectedSources?: Array<{ sourceId: string; bytes: number; filePath: string; sha256: string }> };
const agents = [
  { label: "GPT-6 Sol", detail: "Task routing", icon: Bot },
  { label: "GPT-6 Astra", detail: "Physics and decision gate", icon: FlaskConical },
  { label: "GPT-6 Luna", detail: "Data inventory", icon: FileSearch },
  { label: "GPT-6 Astra", detail: "Independent physics review", icon: ShieldCheck },
];

export function AIOrchestratorPanel() {
  const [objective, setObjective] = useState("Design a traceable dataset to predict melt pool behavior and defect risk from LPBF process parameters, sensor data, and simulation outputs.");
  const [constraints, setConstraints] = useState("No prepared or custom data is available. Data may be collected automatically from trusted, permitted open sources such as NIST AM-Bench, Materials Project, and NOMAD; do not use arbitrary websites; keep experimental and simulation data separate; prevent data leakage; include material, process, and source information in every record.");
  const [availableData, setAvailableData] = useState("No data is currently available. Agents should first propose a discovery and access plan for verifiable open sources such as NIST AM-Bench, Materials Project, and NOMAD. Do not download sources without human approval.");
  const [result, setResult] = useState<PlanResponse | null>(null);
  const [approved, setApproved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function createPlan() {
    setLoading(true); setError(null); setResult(null); setApproved(false);
    try {
      const response = await fetch("/api/orchestrator/dataset-plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ objective, constraints, availableData }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Dataset plan could not be created.");
      setResult(payload);
    } catch (err) { setError(err instanceof Error ? err.message : "Dataset planning failed."); }
    finally { setLoading(false); }
  }

  return <section className="space-y-5" aria-labelledby="orchestrator-title">
    <div className="rounded-2xl border border-cyan-400/25 bg-cyan-950/20 p-5 shadow-[0_0_32px_rgba(34,211,238,0.08)]">
      <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-[10px] uppercase tracking-[0.22em] text-cyan-300">Human-gated workflow</p><h2 id="orchestrator-title" className="mt-2 text-2xl font-semibold text-white">Dataset Planning</h2><p className="mt-2 max-w-3xl text-sm text-slate-300">Agents recommend the data needed. No data is uploaded and no files are changed without your approval.</p></div><span className={`rounded-full border px-3 py-1 text-xs ${approved ? "border-emerald-400/40 text-emerald-200" : "border-amber-400/40 text-amber-200"}`}>{approved ? "Plan approved" : "Human approval required"}</span></div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{agents.map(({ label, detail, icon: Icon }) => <div key={label} className="rounded-xl border border-slate-700/80 bg-slate-950/40 p-3"><div className="flex items-center gap-2 text-sm text-cyan-100"><Icon className="h-4 w-4" />{label}</div><p className="mt-1 text-xs text-slate-400">{detail}</p><p className="mt-2 text-[10px] uppercase tracking-wider text-slate-500">{result ? "Completed" : "Waiting"}</p></div>)}</div>
    </div>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="rounded-2xl border border-slate-700 bg-slate-950/45 p-5"><div className="mb-4 flex items-center gap-2"><Database className="h-5 w-5 text-cyan-300" /><h3 className="font-semibold text-white">Plan Input</h3></div><div className="mb-4 rounded-xl border border-emerald-400/25 bg-emerald-950/20 p-3 text-sm leading-6 text-emerald-100">Starting assumption: no prepared data is available. Data may be collected automatically from trusted, permitted sources (e.g., NIST AM-Bench, Materials Project, NOMAD); arbitrary internet sources are not used. Quality review and dataset inclusion are separate steps after download.</div><label className="mb-2 block text-xs uppercase tracking-wider text-cyan-200">Research Objective</label><textarea aria-label="Research Objective" value={objective} onChange={event => setObjective(event.target.value)} rows={5} className="aero-input mb-4 w-full rounded-xl border p-3 text-sm" /><label className="mb-2 block text-xs uppercase tracking-wider text-cyan-200">Constraints and Quality Rules</label><textarea aria-label="Constraints and Quality Rules" value={constraints} onChange={event => setConstraints(event.target.value)} rows={4} className="aero-input mb-4 w-full rounded-xl border p-3 text-sm" /><label className="mb-2 block text-xs uppercase tracking-wider text-cyan-200">Available Data</label><textarea aria-label="Available Data" value={availableData} onChange={event => setAvailableData(event.target.value)} rows={3} placeholder="If no prepared data is available, leave this unchanged; agents will suggest open sources." className="aero-input w-full rounded-xl border p-3 text-sm" /><button onClick={() => void createPlan()} disabled={loading || !objective.trim()} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50">{loading ? "Agents are working…" : "Create Dataset Plan"}<FileSearch className="h-4 w-4" /></button>{error && <p role="alert" className="mt-3 rounded-lg border border-rose-400/30 bg-rose-950/20 p-3 text-sm text-rose-200">{error}</p>}</div>
      <div className="rounded-2xl border border-slate-700 bg-slate-950/45 p-5"><div className="mb-4 flex items-center justify-between gap-3"><div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-amber-300" /><h3 className="font-semibold text-white">Agent Recommendations</h3></div>{result && <span className="text-xs text-slate-400">Source collection: automatic · Dataset: locked</span>}</div>{!result && <div className="flex min-h-72 items-center justify-center rounded-xl border border-dashed border-slate-700 p-6 text-center text-sm text-slate-400">After entering an objective and creating a plan, you will see the GPT-6 Luna data inventory, GPT-6 Astra physics review, and combined recommendation here.</div>}{result && <><article className="max-h-[34rem] overflow-y-auto whitespace-pre-wrap rounded-xl border border-cyan-400/20 bg-slate-950/70 p-4 text-sm leading-6 text-slate-200">{result.plan}</article><div className="mt-4 rounded-xl border border-emerald-400/20 bg-emerald-950/15 p-3 text-sm text-emerald-100">{result.collectedSources?.length ? `${result.collectedSources.length} permitted source file(s) were downloaded to the raw data area.` : "No directly downloadable permitted file links were found in the plan; nothing was downloaded."}</div><div className="mt-4 flex flex-wrap gap-2"><button onClick={() => setApproved(true)} className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-slate-950"><Check className="h-4 w-4" />Approve Plan</button><button onClick={() => { setResult(null); setApproved(false); }} className="inline-flex items-center gap-2 rounded-lg border border-amber-400/40 px-3 py-2 text-sm text-amber-200"><X className="h-4 w-4" />Request New Plan</button><button disabled={!approved} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 disabled:opacity-40"><Upload className="h-4 w-4" />Continue to Data Upload</button></div></>}</div>
    </div>
  </section>;
}
