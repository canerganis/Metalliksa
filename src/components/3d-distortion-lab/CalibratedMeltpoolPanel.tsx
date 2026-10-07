import React, { useEffect, useState } from "react";
import { pythonComputationService, type LPBFCalibratedMeltpoolResult } from "../../services/pythonComputationService";
import {
  COMMITTED_CALIBRATION_ARTEFACT,
  enabledCellsFor,
  type CalibrationArtefactSummary,
} from "../../data/lpbfCalibrationArtefact";

// Opt-in calibrated mode for the Melt Pool lab. SCREENING ONLY, NOT VALIDATION: effective absorptivity fitted to
// published tracks outside the frozen kernels, served only for cells that passed the held-out gate.
//
// - The control is NOT rendered (not greyed out) while no cell is enabled for the chosen kernel and alloy: a permanently
//   disabled control would itself be a claim. The scorecard link stays.
// - Default OFF, never persisted. OFF issues no request at all; the lab's own screening request path is untouched.
// - When only one quantity is served, nothing is derived from a mix of calibrated and screening values
//   (no depth/width, length/width, aspect ratio): those cells show a dash with the reason.

export const SCORECARD_HASH = "#/lpbf-calibration-scorecard";

export type CalibratedRequest = Parameters<typeof pythonComputationService.solveLPBFCalibratedMeltpool>[0];

/** The only rule that triggers a calibrated request: the user opted in AND an enabled cell exists. */
export function shouldRequestCalibrated(optedIn: boolean, enabledCellCount: number): boolean {
  return optedIn && enabledCellCount > 0;
}

function fmt(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

function Dash({ reason }: { reason: string }) {
  return <span title={reason}>— <span className="text-[10px] text-slate-400">({reason})</span></span>;
}

export function CalibratedResultView({ result }: { result: LPBFCalibratedMeltpoolResult }) {
  const c = result.calibrated;
  const cal = result.calibration;
  const dim = result.outsideTrainingEnvelope ? "opacity-50" : "";
  const bothServed = c.width_um !== null && c.depth_um !== null;
  return (
    <div data-testid="calibrated-result" className="space-y-2 text-xs">
      <p className="rounded-lg border border-sky-500/40 bg-sky-500/10 p-2 text-[11px] text-sky-100">
        <span data-testid="calibrated-badge" className="mr-1.5 rounded border border-sky-400/60 px-1.5 py-0.5 font-bold text-sky-200">Screening only</span>
        Calibrated mode · Screening only (not validation).
        {cal ? <> Effective absorptivity fitted on: <span data-testid="fitted-on">{cal.fittedOn.join("; ")}</span>.</> : null}
        {cal && Object.keys(cal.heldOutScore).length ? <> Held-out score: {Object.entries(cal.heldOutScore).map(([q, text]) => `${q}: ${text}`).join(" | ")}.</> : null}
        {" "}<a className="underline" href={SCORECARD_HASH}>Open scorecard</a>
      </p>
      {!c.available ? <p data-testid="calibrated-unavailable" className="text-amber-300">Calibrated values are not available: {c.reason ?? "no enabled cell"}.</p> : (
        <div className={`grid grid-cols-2 gap-2 rounded-xl border border-slate-800 bg-[#050810] p-2 ${dim}`}>
          <div>
            <span className="block text-[10px] text-slate-400">Calibrated width (W)</span>
            <strong data-testid="cal-width" className="text-sm text-emerald-300">{c.width_um !== null ? `${fmt(c.width_um)} µm` : <Dash reason={c.widthReason ?? "not served"} />}</strong>
            {c.width_pi90_um ? <span data-testid="cal-width-pi90" className="block text-[10px] text-slate-400">PI 90 %: [{fmt(c.width_pi90_um[0], 0)}, {fmt(c.width_pi90_um[1], 0)}] µm</span> : null}
          </div>
          <div>
            <span className="block text-[10px] text-slate-400">Calibrated depth (D)</span>
            <strong data-testid="cal-depth" className="text-sm text-amber-300">{c.depth_um !== null ? `${fmt(c.depth_um)} µm` : <Dash reason={c.depthReason ?? "not served"} />}</strong>
            {c.depth_pi90_um ? <span data-testid="cal-depth-pi90" className="block text-[10px] text-slate-400">PI 90 %: [{fmt(c.depth_pi90_um[0], 0)}, {fmt(c.depth_pi90_um[1], 0)}] µm</span> : null}
          </div>
          <div data-testid="cal-ratio">
            <span className="block text-[10px] text-slate-400">Depth-to-width (D/W)</span>
            {bothServed && c.depthOverWidth !== null && c.depthOverWidth !== undefined
              ? <strong className="text-sm text-white">{fmt(c.depthOverWidth, 2)}</strong>
              : <Dash reason={c.depthOverWidthReason ?? "needs both quantities served"} />}
          </div>
          <div data-testid="cal-aspect">
            <span className="block text-[10px] text-slate-400">Length-to-width (L/W)</span>
            <Dash reason="no calibrated length; never mixed with calibrated W" />
          </div>
        </div>
      )}
      {c.available ? <p data-testid="cal-regime" className="text-[11px] text-slate-400">Regime label (screening, at the default absorptivity, unchanged): <strong className="text-slate-200">{c.regimeLabel ?? "—"}</strong></p> : null}
      {result.outsideTrainingEnvelope ? <p data-testid="envelope-warning" className="text-amber-300">Outside the training envelope, calibrated numbers greyed: {result.envelopeNotes.join("; ")}.</p> : null}
    </div>
  );
}

export interface CalibratedMeltpoolPanelProps {
  readonly heatSource: "goldak" | "eagar-tsai" | "rosenthal";
  readonly material: string;
  readonly request: Omit<CalibratedRequest, "heatSource" | "material">;
  readonly summary?: CalibrationArtefactSummary | null;
  /** injected in tests; defaults to the shared service */
  readonly solve?: (payload: CalibratedRequest, signal?: AbortSignal) => Promise<LPBFCalibratedMeltpoolResult>;
}

export function CalibratedMeltpoolPanel({
  heatSource, material, request, summary = COMMITTED_CALIBRATION_ARTEFACT,
  solve = (p, s) => pythonComputationService.solveLPBFCalibratedMeltpool(p, s),
}: CalibratedMeltpoolPanelProps) {
  const cells = enabledCellsFor(summary, heatSource, material);
  const [optedIn, setOptedIn] = useState(false); // default OFF; never persisted beyond this component's lifetime
  const [result, setResult] = useState<LPBFCalibratedMeltpoolResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestKey = JSON.stringify([heatSource, material, request]);
  const active = shouldRequestCalibrated(optedIn, cells.length);

  useEffect(() => {
    if (!active) { setResult(null); setError(null); return; }
    const controller = new AbortController();
    setError(null);
    solve({ ...request, heatSource, material }, controller.signal)
      .then((r) => { if (!controller.signal.aborted) setResult(r); })
      .catch((e: unknown) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Calibrated request failed."); });
    return () => controller.abort();
  }, [active, requestKey]);

  if (cells.length === 0) {
    return (
      <p data-testid="calibration-link-only" className="text-[11px] text-slate-400">
        No calibrated mode is offered for this kernel and alloy: no cell passes the held-out gate. <a className="underline" href={SCORECARD_HASH}>Calibration scorecard</a>
      </p>
    );
  }
  return (
    <section data-testid="calibrated-panel" aria-label="Calibrated mode" className="space-y-2 rounded-xl border border-[#162032] bg-[#090e18] p-3">
      <label className="flex items-center gap-2 text-xs font-semibold text-white">
        <input data-testid="calibrated-toggle" type="checkbox" checked={optedIn} onChange={(e) => setOptedIn(e.target.checked)} />
        Calibrated mode (opt-in)
      </label>
      {optedIn && error ? <p role="alert" className="text-xs text-rose-300">{error}</p> : null}
      {optedIn && result ? <CalibratedResultView result={result} /> : null}
      {!optedIn ? <p className="text-[11px] text-slate-400">Off: only the unchanged screening result is shown. <a className="underline" href={SCORECARD_HASH}>Calibration scorecard</a></p> : null}
    </section>
  );
}
