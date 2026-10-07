import React from "react";
import {
  COMMITTED_ERROR_BANDS,
  bandDisplays,
  bandSubjectFromThermal,
  type BandDisplay,
  type BandSubject,
  type ErrorBandsSummary,
} from "../data/lpbfErrorBands";

/**
 * Published-track error of the frozen screening kernels next to a melt-pool width / depth (REPORTING ONLY).
 *
 * One line per quantity: a short form (e.g. "D err. -43/+41 % (cov 68 %)") that opens the full sentence, which is plain
 * text in the page (never only a title attribute) and reachable by keyboard (native disclosure). The sentence always
 * carries n, the sources, the per-source median errors and the measured held-out coverage; the evidence label stays
 * "Screening only". Nothing is rendered when the committed summary is absent, when the melt-pool extent was not
 * computed, or when the subject is not a thermal-solver result. No label, verdict or gate reads this component.
 */
export function PublishedTrackBandLines({ displays, testIdPrefix = "band" }: { displays: readonly BandDisplay[]; testIdPrefix?: string }) {
  if (displays.length === 0) return null;
  return (
    <div data-testid={`${testIdPrefix}-block`} className="space-y-1 text-[11px] text-slate-300" aria-label="Published-track error of this screening result">
      {displays.map((d) => (
        <details key={d.quantity} data-testid={`${testIdPrefix}-${d.quantity}`} data-band-state={d.state} className="rounded-lg border border-slate-800 bg-[#050810] px-2.5 py-1.5">
          <summary
            className="cursor-pointer font-mono text-[11px] text-amber-200 focus-visible:outline-2 focus-visible:outline-sky-300"
            title={d.sentence}
            data-testid={`${testIdPrefix}-${d.quantity}-short`}
          >
            {d.short}
          </summary>
          <p className="mt-1 leading-5 text-slate-300" data-testid={`${testIdPrefix}-${d.quantity}-sentence`}>{d.sentence}</p>
        </details>
      ))}
    </div>
  );
}

export function PublishedTrackBands({ subject, thermal, summary = COMMITTED_ERROR_BANDS, testIdPrefix }: {
  subject?: BandSubject | null;
  thermal?: Parameters<typeof bandSubjectFromThermal>[0];
  summary?: ErrorBandsSummary | null;
  testIdPrefix?: string;
}) {
  const s = subject ?? bandSubjectFromThermal(thermal);
  const displays = bandDisplays(summary, s);
  if (displays.length === 0) return null;
  return <PublishedTrackBandLines displays={displays} testIdPrefix={testIdPrefix} />;
}
