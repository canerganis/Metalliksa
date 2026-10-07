import React from "react";
import {
  COMMITTED_LPBF_KEYHOLE_BENCHMARK,
  type LpbfKeyholeBenchmark,
  type LpbfKeyholeSpread,
} from "../data/lpbfKeyholeBenchmark";

const LABELS = ["conduction", "transition", "keyhole"] as const;
const NOT_REPORTED = "not reported";
const SOURCE_LABELS: Readonly<Record<string, string>> = {
  "cunningham-ti64-2019": "Cunningham et al. (2019)",
  "zhao-ti64-2020-boundary": "Zhao et al. (2020), boundary data",
  "zhao-ti64-2020-pores": "Zhao et al. (2020), pore data",
  "gan-keyhole-2021": "Gan et al. (2021)",
  "hann-ss304-2011": "Hann et al. (2011)",
  "huang-al7a77-2022": "Huang et al. (2022)",
};
const DEPTH_SETS: readonly (readonly [string, string])[] = [
  ["cunningham95", "Cunningham 95 um"],
  ["cunningham140", "Cunningham 140 um"],
  ["zhaoBoundaryBare", "Zhao boundary, bare"],
  ["zhaoBoundaryPowder", "Zhao boundary, powder"],
];

function isNum(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function valueText(value: unknown, digits = 3): string {
  return isNum(value) ? value.toFixed(digits) : NOT_REPORTED;
}

function spreadText(spread: LpbfKeyholeSpread | undefined): string {
  if (!spread || typeof spread !== "object") return NOT_REPORTED;
  return `min ${valueText(spread.min)} / median ${valueText(spread.median)} / max ${valueText(spread.max)} (n = ${valueText(spread.n, 0)})`;
}

function doiHref(doi: string): string {
  return `https://doi.org/${doi.replace(/^https?:\/\/(dx\.)?doi\.org\//, "")}`;
}

export function LpbfKeyholeBenchmarkPanel({
  document = COMMITTED_LPBF_KEYHOLE_BENCHMARK,
}: { document?: LpbfKeyholeBenchmark | null } = {}) {
  const sources = Array.isArray(document?.sources) ? document.sources : [];
  const matrix = document?.regimeConfusion?.matrix;
  const keyholeReported = matrix?.keyhole;
  const keyholeRowTotal = keyholeReported
    ? Object.values(keyholeReported).reduce((sum, count) => sum + (isNum(count) ? count : 0), 0)
    : 0;
  const keyholeRecall = document?.regimeConfusion?.keyholeRecall ??
    (keyholeRowTotal > 0 && isNum(keyholeReported?.keyhole) ? keyholeReported.keyhole / keyholeRowTotal : undefined);
  const rowsIngested = sources.reduce((sum, source) => sum + (isNum(source?.rows) ? source.rows : 0), 0);
  const depth = document?.depth;
  const keyholeThreshold = document?.keyholeThreshold;
  const porosity = document?.porosity;
  const flagged = porosity?.zhaoPoreCasesFlaggedHigh;
  return (
    <section data-testid="lpbf-keyhole-benchmark" aria-labelledby="keyhole-benchmark-title" className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <header className="border-b border-slate-100 bg-slate-50 p-4">
        <h2 id="keyhole-benchmark-title" className="font-semibold text-slate-800">Keyhole regime benchmark (literature)</h2>
        {document?.label ? <p className="mt-1 text-xs text-slate-600">{document.label}</p> : null}
      </header>
      <div className="space-y-4 p-4 text-sm text-slate-800">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" aria-label="Benchmark metrics">
          <p>Accuracy: <strong>{valueText(document?.regimeConfusion?.accuracy)}</strong></p>
          <p>Keyhole recall: <strong>{valueText(keyholeRecall)}</strong></p>
          <p>Rows ingested (all sources): <strong>{sources.length ? rowsIngested : NOT_REPORTED}</strong></p>
          <p>App keyhole threshold (index): <strong>{valueText(keyholeThreshold?.app, 1)}</strong></p>
          <p>Zhao pore cases flagged high: <strong>{typeof flagged === "string" ? flagged : NOT_REPORTED}</strong></p>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-slate-700">Keyhole depth error, app Fabbro prediction vs measured vapor depression</h3>
          <ul className="mt-1 grid gap-1 text-xs sm:grid-cols-2">
            {DEPTH_SETS.map(([key, label]) => (
              <li key={key}>{label}: depth MAPE (%) <strong>{valueText(depth?.[key], 1)}</strong></li>
            ))}
          </ul>
        </div>

        <div className="space-y-1 text-xs">
          <p>App index at published keyhole line: <strong>{spreadText(keyholeThreshold?.appIndexAtPublishedKeyholeLine)}</strong></p>
          <p>App index along published porosity boundary: <strong>{spreadText(porosity?.appIndexAlongPublishedPorosityBoundary)}</strong></p>
        </div>

        <div className="overflow-x-auto">
          <table data-testid="keyhole-confusion-matrix" className="w-full text-left text-xs">
            <caption className="mb-2 text-left text-slate-600">Regime confusion matrix, reported labels by app screening labels; n = {valueText(document?.regimeConfusion?.n, 0)}. {document?.regimeConfusion?.rule ?? NOT_REPORTED}</caption>
            <thead><tr className="border-b border-slate-200 text-slate-600">
              <th scope="col" className="p-2">Reported \ predicted</th>
              {LABELS.map((label) => <th key={label} scope="col" className="p-2">{label}</th>)}
            </tr></thead>
            <tbody>
              {LABELS.map((reported) => (
                <tr key={reported} className="border-b border-slate-100">
                  <th scope="row" className="p-2 font-medium">{reported}</th>
                  {LABELS.map((predicted) => {
                    const count = matrix?.[reported]?.[predicted];
                    return <td key={predicted} className="p-2 tabular-nums">{isNum(count) ? count : NOT_REPORTED}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <caption className="mb-2 text-left text-slate-600">Literature sources included in the view record; row counts are rows ingested per source (digitized or printed values).</caption>
            <thead><tr className="border-b border-slate-200 text-slate-600">
              <th scope="col" className="p-2">Source</th><th scope="col" className="p-2">Rows</th><th scope="col" className="p-2">DOI</th>
            </tr></thead>
            <tbody>
              {sources.length ? sources.map((source, index) => (
                <tr key={source.id ?? source.doi ?? index} className="border-b border-slate-100">
                  <th scope="row" className="p-2 font-medium">{(source.id && SOURCE_LABELS[source.id]) || source.id || NOT_REPORTED}</th>
                  <td className="p-2">{isNum(source.rows) ? source.rows : NOT_REPORTED}</td>
                  <td className="p-2">{source.doi ? <a className="underline" href={doiHref(source.doi)}>{source.doi}</a> : NOT_REPORTED}</td>
                </tr>
              )) : <tr><td className="p-2" colSpan={3}>{NOT_REPORTED}</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="space-y-1 border-t border-slate-100 pt-3 text-xs text-slate-700">
          <p>{typeof document?.honesty === "string" ? document.honesty : NOT_REPORTED}</p>
          {document?.physicsBumpProposed === true ? (
            <p>A planned physics update is proposed; see the evidence note{typeof document.evidenceNote === "string" ? <>: <code>{document.evidenceNote}</code></> : null}.</p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
