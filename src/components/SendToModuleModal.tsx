import { contractById } from '../modules/registry';
import React, { useState } from "react";
import { AccessibleModal } from "./AccessibleModal";
import {
  Zap,
  Flame,
  Gauge,
  FlaskConical,
  Cpu,
  Compass,
  ArrowRight,
  CheckCircle2,
  X,
  Sparkles,
  Layers,
  Activity,
  Atom,
  Clock,
  ShieldCheck,
  Box,
} from "lucide-react";
import {
  PipelineMaterialPayload,
  ModuleTargetId,
  setActivePipelineMaterial,
  dispatchNavigateToTab,
  pipelineHardnessText,
} from "../utils/materialDataPipeline";

interface SendToModuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  payload: PipelineMaterialPayload | null;
  onNavigate?: (tabId: string) => void;
}

// Specimen-store payloads carry null for properties they cannot compute; show that instead of "null MPa".
export const mpaOrUnavailable = (value: number | null | undefined) => (value == null ? "unavailable" : `${value} MPa`);
export const celsiusOrUnavailable = (value: number | null | undefined) => (value == null ? "unavailable" : `${value}°C`);

export const SendToModuleModal: React.FC<SendToModuleModalProps> = ({
  isOpen,
  onClose,
  payload,
  onNavigate,
}) => {
  const [dispatchedTarget, setDispatchedTarget] = useState<ModuleTargetId | null>(null);

  if (!isOpen || !payload) return null;

  const handleDispatch = (targetId: ModuleTargetId) => {
    setActivePipelineMaterial(payload);
    setDispatchedTarget(targetId);

    setTimeout(() => {
      if (onNavigate) {
        onNavigate(targetId);
      } else {
        dispatchNavigateToTab(targetId);
      }
      onClose();
      setDispatchedTarget(null);
    }, 350);
  };

  const hardnessText = pipelineHardnessText(payload.hardnessHV, payload.hardnessHVSource, payload.hardness);

  const targets = [
    {
      id: "alloy-builder" as ModuleTargetId,
      name: contractById("alloy-builder").label,
      category: "Composition & Specimen",
      icon: FlaskConical,
      color: "text-purple-400",
      borderColor: "border-purple-500/30 hover:border-purple-400/70",
      bgColor: "bg-purple-500/10",
      badge: "Active specimen",
      description: `Loads this composition into the Alloy Builder as the shared active specimen for editing.`,
      highlights: [
        `Base: ${payload.baseMetal}-Matrix`,
        `σy: ${mpaOrUnavailable(payload.yieldStrength)}`,
        `${Object.keys(payload.composition).length} Elements`,
      ],
    },
    {
      id: "icme-motor" as ModuleTargetId,
      name: contractById("icme-motor").label,
      category: "Solidification & CALPHAD Microsegregation",
      icon: Cpu,
      color: "text-cyan-400",
      borderColor: "border-cyan-500/30 hover:border-cyan-400/70",
      bgColor: "bg-cyan-500/10",
      badge: "Scheil / SDAS",
      description: `Transfers composition to simulate non-equilibrium Scheil-Gulliver solidification, secondary dendrite arm spacing (SDAS), and microsegregation indices.`,
      highlights: [
        `T_liq: ${celsiusOrUnavailable(payload.icmeProfile.liquidusTemp_C)}`,
        `T_sol: ${celsiusOrUnavailable(payload.icmeProfile.solidusTemp_C)}`,
        `CE: ${payload.icmeProfile.carbonEquivalent || "N/A"}%`,
      ],
    },
    {
      id: "3d-distortion-lab" as ModuleTargetId,
      name: contractById("3d-distortion-lab").label,
      category: "Laser Powder Bed Fusion",
      icon: Box,
      color: "text-cyan-300",
      borderColor: "border-cyan-500/30 hover:border-cyan-400/70",
      bgColor: "bg-cyan-500/10",
      badge: "Python verdict / 5-tier",
      description: `Opens the Additive 3D LPBF wizard (alloy + process vector → optional STL → Python printability → literature DOI). Industrial verdict lives there — this transfer does not stamp printable.`,
      highlights: [
        `Alloy: ${payload.name}`,
        `σy: ${mpaOrUnavailable(payload.yieldStrength)}`,
        "Shared LPBF process vector",
      ],
    },
    {
      id: "phase-diagram" as ModuleTargetId,
      name: contractById("phase-diagram").label,
      category: "Equilibrium Thermodynamics",
      icon: Compass,
      color: "text-indigo-400",
      borderColor: "border-indigo-500/30 hover:border-indigo-400/70",
      bgColor: "bg-indigo-500/10",
      badge: "Equilibrium / Ac3",
      description: `Maps equivalent carbon content onto the Iron-Carbon binary phase space to inspect austenite, ferrite, pearlite, and martensite start (Ms) boundaries.`,
      highlights: [
        `Ac3: ${celsiusOrUnavailable(payload.icmeProfile.criticalAc3_C ?? null)}`,
        `C-wt: ${(payload.composition.C || 0).toFixed(2)}%`,
        `Solvus: ${celsiusOrUnavailable(payload.icmeProfile.solvusTemp_C)}`,
      ],
    },
  ];

  return (
    <AccessibleModal
      open
      onClose={onClose}
      label="Cross-module data pipeline"
      overlayClassName="bg-black/80 backdrop-blur-md p-4"
      panelClassName="bg-[#090e18] border border-[#162032] rounded-2xl max-w-4xl w-full max-h-[92vh] flex flex-col shadow-[0_12px_45px_rgba(0,0,0,0.85)] overflow-hidden animate-in zoom-in-95 duration-200"
    >
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-[#162032] bg-[#0c1322]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400 shadow-[0_0_15px_rgba(56,189,248,0.25)]">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm sm:text-base font-bold text-white font-mono uppercase tracking-wide">
                  Cross-Module Data Pipeline
                </h3>
                <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 text-[10px] font-mono border border-sky-500/40">
                  1-Click Transfer
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Automatically injects chemistry, kinetic constants, and constitutive parameters into specialized metallurgy labs.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Selected Material Summary Card */}
        <div className="p-4 bg-[#050810] border-b border-[#162032]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-white font-mono">{payload.name}</span>
                <span className="text-[11px] text-slate-400 font-mono">({payload.standard})</span>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-mono border border-slate-700">
                  {payload.category}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                {Object.entries(payload.composition)
                  .filter(([_, v]) => Number(v) > 0.05)
                  .map(([elem, wt]) => (
                    <span
                      key={elem}
                      className="px-1.5 py-0.5 rounded bg-[#0c1322] border border-[#1e2d46] text-sky-300 font-mono text-[10px]"
                    >
                      <strong className="text-white">{elem}:</strong> {String(wt)}%
                    </span>
                  ))}
              </div>
            </div>

            <div className="flex items-center gap-3 text-xs font-mono">
              <div className="text-right">
                <span className="text-[10px] text-slate-500 block uppercase">Yield / UTS</span>
                <span className="text-emerald-400 font-bold">{mpaOrUnavailable(payload.yieldStrength)} / {mpaOrUnavailable(payload.tensileStrength)}</span>
              </div>
              <div className="text-right">
                <span className="text-[10px] text-slate-500 block uppercase">Hardness</span>
                <span className="text-amber-400 font-bold">{hardnessText}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Module Target Grid */}
        <div className="p-4 sm:p-5 overflow-y-auto flex-1 space-y-3">
          <div className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold">
            Select Destination Metallurgy Engine:
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {targets.map((target) => {
              const Icon = target.icon;
              const isDispatched = dispatchedTarget === target.id;

              return (
                <div
                  key={target.id}
                  className={`p-3.5 rounded-xl bg-[#0c1322] border ${target.borderColor} transition-all duration-200 flex flex-col justify-between group hover:shadow-[0_4px_20px_rgba(0,0,0,0.5)]`}
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className={`p-2 rounded-lg ${target.bgColor} ${target.color} border border-white/5`}>
                          <Icon className="w-4 h-4" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-white font-mono group-hover:text-sky-300 transition">
                            {target.name}
                          </h4>
                          <span className="text-[10px] text-slate-400 block font-mono">
                            {target.category}
                          </span>
                        </div>
                      </div>
                      <span className="px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 text-[9px] font-mono border border-slate-700 whitespace-nowrap">
                        {target.badge}
                      </span>
                    </div>

                    <p className="text-[11px] text-slate-300 font-mono leading-relaxed line-clamp-2">
                      {target.description}
                    </p>

                    <div className="flex items-center gap-1.5 flex-wrap pt-1">
                      {target.highlights.map((hl, i) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 rounded bg-[#070b12] text-slate-400 text-[9.5px] font-mono border border-[#162032]"
                        >
                          {hl}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="pt-3 mt-2 border-t border-[#162032] flex items-center justify-between">
                    <span className="text-[10px] text-slate-500 font-mono">
                      Loads full chemistry & constants
                    </span>
                    <button
                      type="button"
                      onClick={() => handleDispatch(target.id)}
                      disabled={isDispatched}
                      className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition flex items-center gap-1.5 ${
                        isDispatched
                          ? "bg-emerald-500 text-slate-950 shadow-[0_0_12px_rgba(16,185,129,0.5)]"
                          : "bg-sky-500 hover:bg-sky-400 text-slate-950 shadow-[0_0_10px_rgba(56,189,248,0.3)]"
                      }`}
                    >
                      {isDispatched ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Piping Data...</span>
                        </>
                      ) : (
                        <>
                          <span>Send to Module</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-[#162032] bg-[#0c1322] flex items-center justify-between font-mono text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>Pipeline Active & Ready for Instant Ingestion</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition font-mono text-xs"
          >
            Close
          </button>
        </div>
    </AccessibleModal>
  );
};
