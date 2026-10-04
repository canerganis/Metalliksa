import React from "react";
import { Layers } from "lucide-react";

// Build-job solidification microstructure (python/lpbf_solidification_microstructure.py
// project_build_job_microstructure). Python projects thermal.solidificationKinetics and decides the status:
// "available" (liquidus field-map G/R), "screening-fallback" (tail-length heuristic; carries a reason) or
// "unavailable" (carries a reason, no numbers). This panel only displays those decisions.

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

export const BuildJobMicrostructurePanel: React.FC<{ microstructure: BuildJobMicrostructureLike | null | undefined }> = ({ microstructure }) => {
  if (!microstructure) return null;
  const m = microstructure;
  const provenance = [m.modelId, m.gradientSource].filter(Boolean).join(" · ") || (m.source ?? "");
  const cellular = typeof m.morphology === "string" && m.morphology.startsWith("Cellular");
  const gOverR = Number.isFinite(m.g_over_r_ratio)
    ? (m.g_over_r_ratio as number)
    : (m.G_K_m ?? NaN) / Math.max(1e-9, m.R_m_s ?? NaN);
  return (
    <div className="space-y-2" data-micro-status={m.status ?? "unknown"}>
      <div className="flex items-center gap-2">
        <Layers className="w-4 h-4 text-teal-400" />
        <h3 className="text-xs font-bold text-white">Solidification Microstructure</h3>
      </div>
      {m.status === "unavailable" ? (
        <p className="text-[11px] text-slate-400" data-micro-note="unavailable">Unavailable — {m.reason}</p>
      ) : (
        <>
          {m.status === "screening-fallback" && (
            <p className="text-[10px] text-amber-300" data-micro-note="screening-fallback">Screening only — {m.reason}</p>
          )}
          {m.regimeNote && <p className="text-[10px] text-amber-300" data-micro-note="regime">{m.regimeNote}</p>}
          <div className="grid grid-cols-2 gap-2">
            <MicroMetric label="PDAS (µm)" value={m.PDAS_um?.toFixed(2) ?? "—"} hint={`Hunt–Lu 1996 · ${provenance}`} />
            <MicroMetric
              label="SDAS (µm)"
              value={m.SDAS_um?.toFixed(2) ?? "—"}
              hint={cellular ? `cells have no secondary arms · Kirkwood 1985 · ${provenance}` : `Kirkwood 1985 · ${provenance}`}
            />
            <MicroMetric label="Morphology" value={m.morphology ?? "—"} hint={`G/R = ${gOverR.toExponential(1)}`} />
            <MicroMetric label="Cooling Rate" value={m.coolingRate_K_s?.toExponential(1) ?? "—"} hint="K/s" />
          </div>
          <p className="text-[9px] text-slate-500 mt-1">{m.disclaimer}</p>
        </>
      )}
    </div>
  );
};
