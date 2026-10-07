import React from "react";
import { FlaskConical } from "lucide-react";

// Build-job Nb segregation / terminal gamma-Laves screening (python/lpbf_solidification_segregation.py
// build_job_segregation). Python decides everything: status "available" (IN718: DuPont, Robino & Marder 1997
// pseudo-ternary model, Literature estimate (screening)), "unavailable" (reason only, e.g. constants not verified
// against a primary source) or "not-applicable" (no Nb-bearing gamma/Laves model for the alloy). This panel only
// displays those decisions; it never computes a fraction and shows no number unless the status is "available".

interface SegBandEntry {
  C_wt?: number | null;
  fGammaLavesConstituent?: number | null;
  fGammaNbCConstituent?: number | null;
  fEutecticTotal?: number | null;
  riskClass?: string | null;
  status?: string | null;
  reason?: string | null;
}

interface SegBandPoint {
  label?: string;
  Nb_wt?: number | null;
  binaryUpperBound?: SegBandEntry | null;
  pseudoTernaryAtCmax?: SegBandEntry | null;
}

export interface BuildJobSegregationLike {
  status?: string;
  reason?: string | null;
  alloyId?: string | null;
  evidenceLabel?: string | null;
  k_Nb?: { value?: number | null; citation?: string | null; locator?: string | null } | null;
  band?: SegBandPoint[] | null;
  bandNote?: string | null;
  feBaseSensitivity?: { point?: SegBandPoint | null; note?: string | null; constants?: Record<string, { value?: number | null }> } | null;
  segregation?: {
    Nb_wt?: number | null;
    basis?: string | null;
    coreRatioToNominal?: number | null;
    interdendritic?: { fs?: number; liquidNb_wt?: number | null; ratioToNominal?: number | null; atEutecticComposition?: boolean }[] | null;
  } | null;
  riskClass?: string | null;
  riskClassRule?: string | null;
  processCoupling?: {
    status?: string | null;
    reason?: string | null;
    G_K_m?: number | null;
    R_m_s?: number | null;
    morphology?: string | null;
    PDAS_um?: number | null;
    note?: string | null;
  } | null;
  upperBoundNote?: string | null;
  sourceAgreementNote?: string | null;
  quantity?: string | null;
  binaryBoundNote?: string | null;
  validity?: {
    outsideSourceRegime?: boolean;
    outsideSourceRegimeReason?: string | null;
    sourceRegime?: string | null;
    outsideSourceComposition?: boolean;
    outsideSourceCompositionReasons?: string[] | null;
    kTransferNote?: string | null;
  } | null;
}

const KNOWN_STATUS = ["available", "unavailable", "not-applicable"];

const fin = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const pct = (v: unknown) => (fin(v) ? `${(v * 100).toFixed(1)} %` : "—");
const num = (v: unknown, digits = 2) => (fin(v) ? v.toFixed(digits) : "—");

function asBlock(value: unknown): BuildJobSegregationLike | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as BuildJobSegregationLike;
}

export const BuildJobSegregationPanel: React.FC<{ segregation: unknown }> = ({ segregation }) => {
  const headingId = React.useId();
  const raw = asBlock(segregation);
  if (!raw) return null;
  // A block without a known status is never shown as available.
  const known = typeof raw.status === "string" && KNOWN_STATUS.includes(raw.status);
  const s: BuildJobSegregationLike = known ? raw : { status: "unavailable", reason: "segregation block without a known status" };
  return (
    <section className="space-y-2 border-t border-[#162032] pt-3 mt-2" aria-labelledby={headingId} data-seg-status={s.status}>
      <div className="flex items-center gap-2">
        <FlaskConical className="w-4 h-4 text-teal-400" aria-hidden="true" />
        <h4 id={headingId} className="text-xs font-bold text-white">Nb Segregation &amp; Laves (Scheil screening)</h4>
      </div>
      {s.status === "not-applicable" ? (
        <p className="text-[11px] text-slate-400" data-seg-note="not-applicable">Not applicable — {s.reason}</p>
      ) : s.status !== "available" ? (
        <p className="text-[11px] text-slate-400" data-seg-note="unavailable">Unavailable — {s.reason}</p>
      ) : (
        <AvailableBody s={s} />
      )}
    </section>
  );
};

const AvailableBody: React.FC<{ s: BuildJobSegregationLike }> = ({ s }) => {
  const band = Array.isArray(s.band) ? s.band : [];
  const pc = s.processCoupling ?? null;
  const pcShown = pc && (pc.status === "available" || pc.status === "screening-fallback");
  const fe = s.feBaseSensitivity?.point ?? null;
  const v = s.validity ?? null;
  return (
    <>
      {s.evidenceLabel && (
        <p className="inline-block rounded border border-amber-400/60 px-2 py-0.5 text-[10px] text-amber-200" data-seg-label>
          {s.evidenceLabel}
        </p>
      )}
      <p className="text-[11px] text-slate-300" data-seg-k>
        k<sub>Nb</sub> = {num(s.k_Nb?.value, 2)} — {s.k_Nb?.citation}
        {s.k_Nb?.locator ? `, ${s.k_Nb.locator}` : ""}
      </p>
      <table className="w-full text-[10px] text-slate-300 border-collapse" data-seg-band>
        <caption className="text-left text-[10px] text-slate-500 pb-1">
          Terminal eutectic-type fractions over the specification Nb band (fraction of the liquid, %)
        </caption>
        <thead>
          <tr className="text-slate-500">
            <th scope="col" className="text-left font-normal">Nb (wt%)</th>
            <th scope="col" className="text-left font-normal">γ/Laves, C = 0 (binary; model upper bound over C only)</th>
            <th scope="col" className="text-left font-normal">γ/Laves at C max</th>
            <th scope="col" className="text-left font-normal">γ/NbC at C max</th>
          </tr>
        </thead>
        <tbody>
          {band.map((p, i) => {
            const t = p.pseudoTernaryAtCmax ?? null;
            const ternaryOk = t && !t.status;
            return (
              <tr key={p.label ?? i} data-seg-band-row={p.label}>
                <th scope="row" className="text-left font-normal">
                  {num(p.Nb_wt, 3)} <span className="text-slate-500">({p.label})</span>
                </th>
                <td>{pct(p.binaryUpperBound?.fGammaLavesConstituent)}</td>
                <td>{ternaryOk ? pct(t.fGammaLavesConstituent) : `— ${t?.reason ?? ""}`}</td>
                <td>{ternaryOk ? pct(t.fGammaNbCConstituent) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {s.bandNote && <p className="text-[9px] text-slate-500">{s.bandNote}</p>}
      {s.quantity && <p className="text-[9px] text-slate-500" data-seg-quantity>{s.quantity}</p>}
      <p className="text-[11px] text-slate-300" data-seg-risk>
        Laves risk class: <strong className="text-white">{s.riskClass}</strong>
        {s.riskClassRule ? <span className="text-slate-500"> ({s.riskClassRule})</span> : null}
      </p>
      {s.segregation && (
        <p className="text-[11px] text-slate-300" data-seg-ratio>
          Segregation ratio C<sub>L</sub>/C<sub>0</sub> (Nb {num(s.segregation.Nb_wt, 3)} wt%): core k·C<sub>0</sub> ={" "}
          {num(s.segregation.coreRatioToNominal, 2)}
          {(s.segregation.interdendritic ?? []).map((r) => (
            <span key={String(r.fs)}>
              {" "}· f<sub>s</sub> = {num(r.fs, 2)}: {num(r.ratioToNominal, 2)}
              {r.atEutecticComposition ? " (capped at the γ/Laves composition)" : ""}
            </span>
          ))}
          {s.segregation.basis ? <span className="text-slate-500"> — {s.segregation.basis}</span> : null}
        </p>
      )}
      {fe && (
        <p className="text-[10px] text-slate-400" data-seg-sensitivity>
          Fe-base constant set (k<sub>Nb</sub> = {num(s.feBaseSensitivity?.constants?.k_gamma_Nb?.value, 2)}), nominal Nb: γ/Laves{" "}
          {pct(fe.binaryUpperBound?.fGammaLavesConstituent)} at C = 0, {pct(fe.pseudoTernaryAtCmax?.fGammaLavesConstituent)} at C max — {s.feBaseSensitivity?.note}
        </p>
      )}
      <div className="text-[10px] text-slate-400" data-seg-coupling={pc?.status ?? "unavailable"}>
        {pcShown ? (
          <>
            Process coupling (copied from the microstructure block): G = {fin(pc.G_K_m) ? pc.G_K_m.toExponential(2) : "—"} K/m, R ={" "}
            {num(pc.R_m_s, 4)} m/s, {pc.morphology ?? "—"}, PDAS {num(pc.PDAS_um, 2)} µm.
            {pc.status === "screening-fallback" && pc.reason ? ` Screening only — ${pc.reason}` : ""} {pc.note}
          </>
        ) : (
          <>Process coupling unavailable — {pc?.reason ?? "no microstructure block"}</>
        )}
      </div>
      {v && (
        <div className="rounded border border-amber-500/40 p-2 text-[10px] text-amber-200 space-y-1" role="note" data-seg-validity>
          {v.outsideSourceRegime && <p>Outside the source regime — {v.outsideSourceRegimeReason}</p>}
          {v.outsideSourceComposition && (v.outsideSourceCompositionReasons ?? []).length > 0 && (
            <ul className="list-disc pl-4">
              {(v.outsideSourceCompositionReasons ?? []).map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
          {v.kTransferNote && <p>{v.kTransferNote}</p>}
        </div>
      )}
      {s.upperBoundNote && <p className="text-[10px] text-slate-400" data-seg-upper-bound>{s.upperBoundNote}</p>}
      {s.sourceAgreementNote && (
        <p className="text-[10px] text-amber-200" data-seg-source-agreement>
          Agreement with the source measurements: {s.sourceAgreementNote}
        </p>
      )}
      {s.binaryBoundNote && <p className="text-[9px] text-slate-500">{s.binaryBoundNote}</p>}
    </>
  );
};
