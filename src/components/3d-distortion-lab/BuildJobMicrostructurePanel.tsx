import React from "react";
import { Layers } from "lucide-react";
import { BuildJobSegregationPanel } from "./BuildJobSegregationPanel";

// Build-job solidification microstructure (python/lpbf_solidification_microstructure.py
// project_build_job_microstructure). Python projects thermal.solidificationKinetics and decides the status:
// "available" (liquidus field-map G/R), "screening-fallback" (tail-length heuristic; carries a reason),
// "degenerate-floor" (field map used but R/cooling are solver clamp floors; carries a reason, copied numbers
// are not a result) or "unavailable" (carries a reason, no numbers). This panel only displays those decisions;
// degenerate-floor is rendered like unavailable (reason only, no PDAS/SDAS/morphology).
// The optional `segregation` block (python/lpbf_solidification_segregation.py) is rendered at the bottom by
// BuildJobSegregationPanel; it carries its own status and is independent of the microstructure status.

export interface BuildJobMicrostructureLike {
  status?: string;
  reason?: string | null;
  source?: string | null;
  modelId?: string | null;
  gradientSource?: string | null;
  usedFieldMap?: boolean | null;
  regime?: string | null;
  regimeNote?: string | null;
  G_K_m?: number | null;
  R_m_s?: number | null;
  g_over_r_ratio?: number | null;
  coolingRate_K_s?: number | null;
  PDAS_um?: number | null;
  SDAS_um?: number | null;
  morphology?: string | null;
  disclaimer?: string | null;
}

const MicroMetric: React.FC<{ label: string; value: string; hint?: string }> = ({ label, value, hint }) => (
  <div className="rounded-lg border px-2 py-1.5 border-[#162032] bg-[#060a12]" data-micro-metric={label}>
    <div className="text-[9px] text-slate-500 uppercase">{label}</div>
    <div className="text-[12px] text-white font-bold truncate">{value}</div>
    {hint && <div className="text-[9px] text-slate-500">{hint}</div>}
  </div>
);

const KNOWN_STATUS = ["available", "screening-fallback", "degenerate-floor", "unavailable"];

export const BuildJobMicrostructurePanel: React.FC<{
  micro: BuildJobMicrostructureLike | null | undefined;
  segregation?: unknown;
}> = ({ micro, segregation }) => {
  if (!micro) return null;
  // A block without a known status (an old worker's Rosenthal block) is never shown as available.
  const known = typeof micro.status === "string" && KNOWN_STATUS.includes(micro.status);
  const m: BuildJobMicrostructureLike = known ? micro : { status: "unavailable", reason: "legacy block without status" };
  // modelId and gradientSource are the same string on the field-map path: show each distinct value once.
  const provenance = Array.from(new Set([m.modelId, m.gradientSource].filter(Boolean))).join(" · ") || (m.source ?? "");
  const cellular = typeof m.morphology === "string" && m.morphology.startsWith("Cellular");
  // Python's own G/R (not recomputed in TS from rounded G and R).
  const gOverR = typeof m.g_over_r_ratio === "number" && Number.isFinite(m.g_over_r_ratio) ? m.g_over_r_ratio.toExponential(1) : "—";
  return (
    <div className="space-y-2" data-micro-status={m.status ?? "unknown"}>
      <div className="flex items-center gap-2">
        <Layers className="w-4 h-4 text-teal-400" />
        <h3 className="text-xs font-bold text-white">Solidification Microstructure</h3>
      </div>
      {m.status === "unavailable" ? (
        <p className="text-[11px] text-slate-400" data-micro-note="unavailable">Unavailable — {m.reason}</p>
      ) : m.status === "degenerate-floor" ? (
        <p className="text-[11px] text-slate-400" data-micro-note="degenerate-floor">Not a computed value — {m.reason}</p>
      ) : (
        <>
          {m.status === "screening-fallback" && (
            <p className="text-[10px] text-amber-300" data-micro-note="screening-fallback">Screening only — {m.reason}</p>
          )}
          {m.regimeNote && <p className="text-[10px] text-amber-300" data-micro-note="regime">{m.regimeNote}</p>}
          <div className="grid grid-cols-2 gap-2">
            <MicroMetric label="PDAS (µm)" value={m.PDAS_um?.toFixed(2) ?? "—"} hint="Hunt–Lu 1996" />
            <MicroMetric
              label="SDAS (µm)"
              value={m.SDAS_um?.toFixed(2) ?? "—"}
              hint={cellular ? "cells have no secondary arms · Kirkwood 1985" : "Kirkwood 1985"}
            />
            <MicroMetric label="Morphology" value={m.morphology ?? "—"} hint={`G/R = ${gOverR}`} />
            <MicroMetric label="Cooling Rate" value={m.coolingRate_K_s?.toExponential(1) ?? "—"} hint="K/s · median of G·R over front samples" />
          </div>
          {provenance && <p className="text-[9px] text-slate-500" data-micro-provenance>Source: {provenance}</p>}
          <p className="text-[9px] text-slate-500 mt-1">{m.disclaimer}</p>
        </>
      )}
      {segregation !== undefined && <BuildJobSegregationPanel segregation={segregation} />}
    </div>
  );
};
