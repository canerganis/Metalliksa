import React, { useMemo, useState } from "react";
import { Box, Layers, Sliders, AlertTriangle, Database, ChevronRight, Undo2, Copy, Check } from "lucide-react";
import { useMaterialSpecimenStore, type BaseMetalType, type LpbfScanStrategy } from "../store/useMaterialSpecimenStore";
import { useLpbfBuildJobPython } from "../store/useLpbfBuildJobStore";
import type { LPBFAlloyId } from "../types/lpbfDataFoundation";
import type { PrintVerdict } from "../utils/lpbfIndustrialDecision";
import { mapSpecimenToBuildJobMaterials } from "../utils/lpbfIndustrialDecision";
import { mapActionableReasons, modelHonestyLine, toActionableHeadline } from "../utils/lpbfActionableReasons";
import { LITERATURE_PV_WINDOWS } from "../utils/lpbfFourAlloySchema";
import { LPBF_DEMO_VECTORS } from "../utils/lpbfDemoVectors";

const LPBF_JOB_ALLOYS: { alloyId: LPBFAlloyId; presetId: string; label: string }[] = [
  { alloyId: "ti6al4v", presetId: "ti-6al-4v", label: "Ti-6Al-4V" },
  { alloyId: "ss316l", presetId: "ss-316l", label: "316L" },
  { alloyId: "alsi10mg", presetId: "alsi10mg", label: "AlSi10Mg" },
  { alloyId: "in718", presetId: "inconel-718", label: "IN718" },
];

export type LpbfBuildJobStage = "alloy" | "cad" | "process" | "record";

export const LPBF_WIZARD_SUB_TABS = [
  "industrial-decision",
  "basic-stl-slicer",
  "ground-truth-foundation",
] as const;

export const LPBF_BUILD_JOB_STAGES: {
  id: LpbfBuildJobStage;
  step: string;
  label: string;
  subTab: string;
}[] = [
  { id: "alloy", step: "1", label: "Alloy + P, v, h, t", subTab: "industrial-decision" },
  { id: "cad", step: "2", label: "STL (optional)", subTab: "basic-stl-slicer" },
  { id: "process", step: "3", label: "Python decision", subTab: "industrial-decision" },
  { id: "record", step: "4", label: "Literature + save", subTab: "ground-truth-foundation" },
];

export function isAdvancedLpbfSubTab(subTab: string): boolean {
  return !(LPBF_WIZARD_SUB_TABS as readonly string[]).includes(subTab);
}

export function subTabToBuildJobStage(
  subTab: string,
  focusedStage?: LpbfBuildJobStage | null
): LpbfBuildJobStage | null {
  if (isAdvancedLpbfSubTab(subTab)) return null;
  if (subTab === "basic-stl-slicer") return "cad";
  if (subTab === "ground-truth-foundation") return "record";
  if (subTab === "industrial-decision") {
    return focusedStage === "alloy" ? "alloy" : "process";
  }
  return "process";
}

function gateChipTone(status: string): string {
  if (status === "fail") return "text-rose-200 border-rose-500/40 bg-rose-500/10";
  if (status === "warn") return "text-amber-200 border-amber-500/40 bg-amber-500/10";
  return "text-slate-400 border-[#162032] bg-[#0c1322]";
}

function gateChipLabel(id: string): string {
  const map: Record<string, string> = {
    lof_tang: "Tang LoF",
    lof_wh: "W/h diag",
    lof_dt: "D/t diag",
    keyhole: "Keyhole ΔH",
    balling: "Balling L/W",
    literature_pv: "Lit P–v",
    recoater: "Recoater",
    distortion: "Distortion",
    downskin: "Downskin",
  };
  return map[id] || id;
}

function screeningAlloyWarning(name: string, baseMetal: BaseMetalType): string | null {
  if (mapSpecimenToBuildJobMaterials(name, baseMetal)) return null;
  return `Build screening does not support ${name || "an unspecified material"}; select one of the four listed alloys. No surrogate alloy was submitted.`;
}

function verdictTone(verdict: PrintVerdict): string {
  if (verdict === "printable") return "text-emerald-300 border-emerald-500/40 bg-emerald-500/10";
  if (verdict === "risky") return "text-amber-300 border-amber-500/40 bg-amber-500/10";
  return "text-rose-300 border-rose-500/40 bg-rose-500/10";
}

interface Props {
  activeSubTab: string;
  focusedWizardStage?: LpbfBuildJobStage | null;
  onNavigateStage: (subTab: string, stage: LpbfBuildJobStage) => void;
  onBackToDecision?: () => void;
}

export const LpbfBuildJobRail: React.FC<Props> = ({
  activeSubTab,
  focusedWizardStage,
  onNavigateStage,
  onBackToDecision,
}) => {
  const specimen = useMaterialSpecimenStore((s) => s.activeSpecimen);
  const updateLpbfProcess = useMaterialSpecimenStore((s) => s.updateLpbfProcess);
  const loadPreset = useMaterialSpecimenStore((s) => s.loadPreset);
  const { job, error, busy, cache, lastFlags } = useLpbfBuildJobPython();
  const [copied, setCopied] = useState(false);
  const lpbf = specimen.lpbf;
  const materialMap = mapSpecimenToBuildJobMaterials(specimen.name, specimen.baseMetal);
  const activeAlloyId = materialMap?.alloyId ?? null;
  const alloyWarn = screeningAlloyWarning(specimen.name, specimen.baseMetal);
  const pvBox = activeAlloyId ? LITERATURE_PV_WINDOWS[activeAlloyId] : null;
  const pPad = pvBox ? Math.round((pvBox.powerMax_W - pvBox.powerMin_W) * 0.25) || 40 : 0;
  const vPad = pvBox ? Math.round((pvBox.speedMax_mm_s - pvBox.speedMin_mm_s) * 0.25) || 80 : 0;
  const pMin = pvBox ? Math.min(lpbf.laserPower_W, Math.max(50, pvBox.powerMin_W - pPad)) : Math.max(1, Math.min(lpbf.laserPower_W, 50));
  const pMax = pvBox ? Math.max(lpbf.laserPower_W, pvBox.powerMax_W + pPad) : Math.max(lpbf.laserPower_W, 1000);
  const vMin = pvBox ? Math.min(lpbf.scanSpeed_mms, Math.max(100, pvBox.speedMin_mm_s - vPad)) : Math.max(1, Math.min(lpbf.scanSpeed_mms, 100));
  const vMax = pvBox ? Math.max(lpbf.scanSpeed_mms, pvBox.speedMax_mm_s + vPad) : Math.max(lpbf.scanSpeed_mms, 2000);
  const demo = activeAlloyId ? LPBF_DEMO_VECTORS[activeAlloyId] : null;
  const activeStage = subTabToBuildJobStage(activeSubTab, focusedWizardStage);
  const inAdvanced = isAdvancedLpbfSubTab(activeSubTab);
  const decision = job?.verdict ?? null;
  const thermal = job?.thermal ?? null;
  const slicer = job?.slicer ?? null;
  const pp = thermal?.processParameters;
  const geo = thermal?.meltPoolGeometry;
  const lof = decision?.lofGeometry;
  const pv = decision?.literatureWindow;
  const lofTight =
    decision != null &&
    (decision.lofGeometry.widthOverHatch < 1.05 || decision.lofGeometry.depthOverLayer < 1.15);
  const actionable = decision ? mapActionableReasons(decision.reasons).slice(0, 3) : [];
  const gates = decision?.gates ?? [];
  const suggested = decision?.suggestedPatch;
  const alloyLabel = LPBF_JOB_ALLOYS.find((a) => a.alloyId === activeAlloyId)?.label ?? `Unsupported: ${specimen.name || "unspecified material"}`;
  const jobLine = useMemo(
    () =>
      [
        alloyLabel,
        `${lpbf.laserPower_W} W`,
        `${lpbf.scanSpeed_mms} mm/s`,
        `h ${lpbf.hatch_um} µm`,
        `t ${lpbf.layer_um} µm`,
        `d ${lpbf.beamDiameter_um} µm`,
        `preheat ${lpbf.preheatTemp_C} °C`,
        decision ? `verdict ${decision.verdict}` : "verdict pending",
        job?.uq ? `P(printable) ${(job.uq.P_printable * 100).toFixed(0)}% n=${job.uq.nSamples}` : "UQ not run",
        job?.ambench?.overallMeanMape_pct != null
          ? `NIST MAPE ${job.ambench.overallMeanMape_pct}%`
          : "NIST not run",
        job?.murakami ? `Murakami ${job.murakami.status}` : "",
        decision?.dominantGate ? `gate ${decision.dominantGate}` : "",
        cache?.hit ? `cache HIT ${cache.ageMs}ms` : cache ? "cache MISS" : "",
        job?.modelId || "rosenthal-screening-v1",
      ]
        .filter(Boolean)
        .join(" · "),
    [
      alloyLabel,
      lpbf.laserPower_W,
      lpbf.scanSpeed_mms,
      lpbf.hatch_um,
      lpbf.layer_um,
      lpbf.beamDiameter_um,
      lpbf.preheatTemp_C,
      decision,
      job?.uq,
      job?.ambench,
      job?.murakami,
      job?.modelId,
      cache,
    ]
  );

  const copyJob = async () => {
    try {
      await navigator.clipboard.writeText(jobLine);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="rounded-2xl border border-[#1e2d46] bg-[#090e18] p-3.5 space-y-3">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Box className="w-4 h-4 text-sky-400" />
          <span className="text-xs font-bold text-white font-mono">LPBF process job</span>
          <span className="text-[10px] text-slate-400 font-mono truncate max-w-[280px]">
            {specimen.name}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 justify-end">
          {inAdvanced && onBackToDecision && (
            <button
              type="button"
              onClick={onBackToDecision}
              className="inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-1 rounded-lg border border-sky-500/40 text-sky-200 bg-sky-500/10"
            >
              <Undo2 className="w-3 h-3" />
              Back to decision
            </button>
          )}
          <button
            type="button"
            onClick={() => onNavigateStage("industrial-decision", "process")}
            className={`text-left text-[10px] font-mono font-bold px-2 py-1 rounded-lg border max-w-[420px] ${
              decision
                ? verdictTone(decision.verdict)
                : busy
                  ? "text-slate-300 border-[#162032] bg-[#0c1322]"
                  : error
                    ? "text-amber-300 border-amber-500/40 bg-amber-500/10"
                    : "text-slate-400 border-[#162032] bg-[#0c1322]"
            }`}
            title={modelHonestyLine(job?.modelId)}
          >
            {decision
              ? toActionableHeadline(decision.headline)
              : busy
                ? "Evaluating…"
                : error
                  ? "Python offline — no industrial verdict"
                  : "Python pending"}
          </button>
          {suggested && decision && decision.verdict !== "printable" && (
            <button
              type="button"
              onClick={() => updateLpbfProcess(suggested)}
              className="text-[10px] font-mono font-bold px-2 py-1 rounded-lg border border-sky-500/40 text-sky-200 bg-sky-500/10"
              title="Literature-box screening suggestion from Python — not a go-build stamp"
            >
              Apply suggested vector
            </button>
          )}
          <button
            type="button"
            onClick={() => void copyJob()}
            className="inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-1 rounded-lg border border-[#162032] text-slate-300 bg-[#0c1322]"
            title={jobLine}
          >
            {copied ? <Check className="w-3 h-3 text-emerald-300" /> : <Copy className="w-3 h-3" />}
            Copy job
          </button>
        </div>
      </div>

      {gates.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {gates.map((g) => (
            <span
              key={g.id}
              title={g.note}
              className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${gateChipTone(g.status)} ${
                decision?.dominantGate === g.id ? "ring-1 ring-sky-400/70" : ""
              }`}
            >
              {gateChipLabel(g.id)} {g.status}
              {g.id === "lof_wh" || g.id === "lof_dt" || g.id === "lof_tang" || g.id === "keyhole"
                ? ` ${g.measured}`
                : ""}
            </span>
          ))}
          {busy && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border text-sky-200 border-sky-500/40 bg-sky-500/10">
              busy
            </span>
          )}
          {cache && (
            <span
              title={cache.hit ? `Cached result age ${cache.ageMs} ms` : "Fresh solve"}
              className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                cache.hit
                  ? "text-emerald-200 border-emerald-500/40 bg-emerald-500/10"
                  : "text-slate-400 border-[#162032] bg-[#0c1322]"
              }`}
            >
              cache {cache.hit ? `HIT ${cache.ageMs}ms` : "MISS"}
              {cache.stats ? ` · ${(cache.stats.hitRate * 100).toFixed(0)}%` : ""}
            </span>
          )}
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border text-slate-500 border-[#162032] bg-[#0c1322]">
            UQ {lastFlags.enableUq ? "on" : "off"} · NIST {lastFlags.includeAmbench ? "on" : "off"}
          </span>
          {job?.uq && (
            <span
              title={job.uq.note}
              className="text-[9px] font-mono px-1.5 py-0.5 rounded border text-violet-200 border-violet-500/40 bg-violet-500/10"
            >
              P(printable) {(job.uq.P_printable * 100).toFixed(0)}% · ΔH{" "}
              {job.uq.normalizedEnthalpy.mean.toFixed(1)}±{job.uq.normalizedEnthalpy.std.toFixed(1)} · dom{" "}
              {job.uq.dominantUncertainty}
            </span>
          )}
          {job?.ambench?.overallMeanMape_pct != null && (
            <span
              title={job.ambench.disclaimer}
              className="text-[9px] font-mono px-1.5 py-0.5 rounded border text-sky-200 border-sky-500/40 bg-sky-500/10"
            >
              NIST AMB2018-02 MAPE {job.ambench.overallMeanMape_pct}% (IN625)
            </span>
          )}
          {job?.murakami && (
            <span
              title={job.murakami.note}
              className="text-[9px] font-mono px-1.5 py-0.5 rounded border text-slate-400 border-[#162032] bg-[#0c1322]"
            >
              Murakami {job.murakami.status}
            </span>
          )}
        </div>
      )}

      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        {LPBF_BUILD_JOB_STAGES.map((stage, idx) => (
          <React.Fragment key={stage.id}>
            <button
              type="button"
              onClick={() => onNavigateStage(stage.subTab, stage.id)}
              className={`shrink-0 px-2.5 py-1.5 rounded-lg text-[10px] font-mono font-bold border transition ${
                !inAdvanced && activeStage === stage.id
                  ? "bg-sky-500/20 text-sky-200 border-sky-400/50"
                  : "bg-[#0c1322] text-slate-400 border-[#162032] hover:text-white"
              }`}
            >
              <span className="text-slate-500 mr-1">{stage.step}</span>
              {stage.label}
            </button>
            {idx < LPBF_BUILD_JOB_STAGES.length - 1 && (
              <ChevronRight className="w-3 h-3 text-slate-600 shrink-0" />
            )}
          </React.Fragment>
        ))}
      </div>

      <p className="text-[10px] text-slate-500 font-mono">
        Workstation: four alloys · live P–v–h–t–d · STL optional
        {slicer?.geometrySource === "uploaded-stl" ? " (mesh loaded)" : " (cube screening if empty)"} ·
        printability is Python `job.verdict` only (rosenthal-screening-v1).
      </p>
      {alloyWarn && (
        <p className="text-[10px] text-amber-200 font-mono flex items-center gap-1">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          {alloyWarn}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wide mr-1">Alloy</span>
        {LPBF_JOB_ALLOYS.map((a) => (
          <button
            key={a.alloyId}
            type="button"
            onClick={() => loadPreset(a.presetId)}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold border transition ${
              activeAlloyId === a.alloyId
                ? "bg-sky-500/20 text-sky-200 border-sky-400/50"
                : "bg-[#0c1322] text-slate-400 border-[#162032] hover:text-white"
            }`}
          >
            {a.label}
          </button>
        ))}
        {demo && (
          <button
            type="button"
            onClick={() => updateLpbfProcess(demo.printable)}
            className="px-2 py-1 rounded-lg text-[10px] font-mono font-bold border border-emerald-500/30 text-emerald-200 bg-emerald-500/10"
            title="Loads the shared conduction demo vector; Python re-scores"
          >
            Load conduction vector
          </button>
        )}
        <span className="text-[10px] text-sky-200 font-mono">
          {alloyLabel} · {lpbf.laserPower_W} W · {lpbf.scanSpeed_mms} mm/s · h {lpbf.hatch_um} · t {lpbf.layer_um} · d{" "}
          {lpbf.beamDiameter_um}
        </span>
      </div>

      {inAdvanced ? (
        <details className="rounded-xl border border-[#162032] bg-[#0c1322] px-2.5 py-1.5">
          <summary className="cursor-pointer list-none text-[10px] font-mono font-bold text-slate-300 flex items-center justify-between gap-2">
            <span>
              Process sliders · {alloyLabel} · {lpbf.laserPower_W} W · {lpbf.scanSpeed_mms} mm/s
            </span>
            <span className="text-slate-500 font-normal">expand</span>
          </summary>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 pt-2">
            <JobSlider
              label="P (W)"
              value={lpbf.laserPower_W}
              min={pMin}
              max={pMax}
              step={10}
              onChange={(v) => updateLpbfProcess({ laserPower_W: v })}
            />
            <JobSlider
              label="v (mm/s)"
              value={lpbf.scanSpeed_mms}
              min={vMin}
              max={vMax}
              step={10}
              onChange={(v) => updateLpbfProcess({ scanSpeed_mms: v })}
            />
            <JobSlider
              label="h (µm)"
              value={lpbf.hatch_um}
              min={40}
              max={200}
              step={5}
              onChange={(v) => updateLpbfProcess({ hatch_um: v })}
            />
            <JobSlider
              label="t (µm)"
              value={lpbf.layer_um}
              min={20}
              max={80}
              step={5}
              onChange={(v) => updateLpbfProcess({ layer_um: v })}
            />
            <JobSlider
              label="d (µm)"
              value={lpbf.beamDiameter_um}
              min={40}
              max={140}
              step={5}
              onChange={(v) => updateLpbfProcess({ beamDiameter_um: v })}
            />
            <JobSlider
              label="Preheat (°C)"
              value={lpbf.preheatTemp_C}
              min={25}
              max={500}
              step={5}
              onChange={(v) => updateLpbfProcess({ preheatTemp_C: v })}
            />
          </div>
        </details>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
          <JobSlider
            label="P (W)"
            value={lpbf.laserPower_W}
            min={pMin}
            max={pMax}
            step={10}
            onChange={(v) => updateLpbfProcess({ laserPower_W: v })}
          />
          <JobSlider
            label="v (mm/s)"
            value={lpbf.scanSpeed_mms}
            min={vMin}
            max={vMax}
            step={10}
            onChange={(v) => updateLpbfProcess({ scanSpeed_mms: v })}
          />
          <JobSlider
            label="h (µm)"
            value={lpbf.hatch_um}
            min={40}
            max={200}
            step={5}
            onChange={(v) => updateLpbfProcess({ hatch_um: v })}
          />
          <JobSlider
            label="t (µm)"
            value={lpbf.layer_um}
            min={20}
            max={80}
            step={5}
            onChange={(v) => updateLpbfProcess({ layer_um: v })}
          />
          <JobSlider
            label="d (µm)"
            value={lpbf.beamDiameter_um}
            min={40}
            max={140}
            step={5}
            onChange={(v) => updateLpbfProcess({ beamDiameter_um: v })}
          />
          <JobSlider
            label="Preheat (°C)"
            value={lpbf.preheatTemp_C}
            min={25}
            max={500}
            step={5}
            onChange={(v) => updateLpbfProcess({ preheatTemp_C: v })}
          />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono text-slate-400">
        <span className="text-slate-500" title={(job?.assumptions || []).join(" ")}>
          {modelHonestyLine(job?.modelId)}
        </span>
        <span className="flex items-center gap-1">
          <Sliders className="w-3 h-3 text-cyan-400" />
          VED {pp?.volumetricEnergyDensity_J_mm3 ?? "—"} J/mm³
        </span>
        <span>LED {pp ? (pp.linearEnergyDensity_J_m / 1000).toFixed(3) : "—"} J/mm</span>
        <span>I₀ {pp?.peakIntensity_MW_cm2 ?? "—"} MW/cm²</span>
        <span>ΔH/hₛ {pp?.normalizedEnthalpy ?? "—"}</span>
        <span>W {geo?.width_um ?? "—"} µm · D {geo?.depth_um ?? "—"} µm</span>
        <span className={lof && lof.widthOverHatch < 1.05 ? "text-amber-300" : ""}>
          W/h {lof ? lof.widthOverHatch.toFixed(2) : "—"}
        </span>
        <span className={lof && lof.depthOverLayer < 1.15 ? "text-amber-300" : ""}>
          D/t {lof ? lof.depthOverLayer.toFixed(2) : "—"}
        </span>
        <span className={pv && !pv.inside ? "text-amber-300" : "text-slate-400"}>
          P–v {pv ? (pv.inside ? "inside box" : "outside box") : "—"}
        </span>
        <span>
          Ṫ{" "}
          {thermal?.solidificationKinetics.coolingRate_K_s != null
            ? `${(thermal.solidificationKinetics.coolingRate_K_s / 1e6).toFixed(2)}×10⁶ K/s`
            : "—"}
        </span>
        <span>
          {slicer?.buildTimeSummary ? `${slicer.buildTimeSummary.totalBuildTime_hr} h` : "N/A h"}
          {slicer?.meshMetrics ? ` · ${slicer.meshMetrics.estimatedPartMass_g} g` : ""}
        </span>
        <span className={slicer?.geometrySource === "uploaded-stl" ? "text-sky-300" : "text-slate-500"}>
          {slicer?.geometrySource === "uploaded-stl"
            ? `STL ${slicer.cadAssetName || "mesh"}`
            : slicer
              ? `Demo ${slicer.preset || "CAD"}`
              : "No part geometry"}
        </span>
        {lofTight && (
          <span className="text-amber-300 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            Hatch/layer overlap below Python LoF gates
          </span>
        )}
        <span className="flex items-center gap-1 ml-auto">
          <Layers className="w-3 h-3 text-sky-400" />
          {lpbf.scanStrategy}
          {job?.scanStrategy
            ? ` · ${job.scanStrategy.stripeWidth_mm} mm / ${job.scanStrategy.rotation_deg}° / dwell ${job.scanStrategy.hatchDwell_ms} ms`
            : " · 5 mm / 67° / dwell 0"}
        </span>
        <span className="text-slate-500" title="Deterministic process seed">
          seed {job?.processSeed ?? lpbf.processSeed ?? 42}
        </span>
        {lpbf.cadAssetName && (
          <span className="text-sky-300 truncate max-w-[160px]">{lpbf.cadAssetName}</span>
        )}
        {lpbf.specimenDoi && (
          <span className="flex items-center gap-1 text-emerald-300">
            <Database className="w-3 h-3" />
            {lpbf.specimenDoi}
          </span>
        )}
        <select aria-label="Scan strategy"
          value={lpbf.scanStrategy}
          onChange={(e) => updateLpbfProcess({ scanStrategy: e.target.value as LpbfScanStrategy })}
          className="bg-[#0c1322] border border-[#162032] rounded px-1.5 py-0.5 text-[10px] text-slate-200"
        >
          <option value="stripe">Stripe 5 mm / 67°</option>
          <option value="meander-67">Meander 67°</option>
          <option value="island">Island 5×5</option>
        </select>
        <label className="flex items-center gap-1 text-[10px] text-slate-400 font-mono">
          seed
          <input
            type="number"
            value={lpbf.processSeed ?? 42}
            onChange={(e) => updateLpbfProcess({ processSeed: Number(e.target.value) || 42 })}
            className="w-14 bg-[#0c1322] border border-[#162032] rounded px-1 py-0.5 text-[10px] text-slate-200"
          />
        </label>
      </div>

      {!inAdvanced && actionable.length > 0 && (
        <ul className="list-disc pl-5 space-y-0.5 text-[10px] text-slate-300 font-mono">
          {actionable.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
    </div>
  );
};

const JobSlider: React.FC<{
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}> = ({ label, value, min, max, step, onChange }) => (
  <label className="block space-y-0.5">
    <div className="flex justify-between text-[10px] font-mono">
      <span className="text-slate-400">{label}</span>
      <span className="text-sky-300 font-bold">{value}</span>
    </div>
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full h-1.5 accent-sky-400 cursor-pointer"
    />
  </label>
);
