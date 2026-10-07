import React, { useState } from "react";
import { FileSearch } from "lucide-react";
import {
  COMMITTED_LEADERBOARD,
  DEFAULT_SORT,
  KIND_LABEL,
  fmtFixed,
  groupRows,
  nextSort,
  sortRows,
  type LeaderboardGroup,
  type LeaderboardRow,
  type LpbfLeaderboardDocument,
  type SortKey,
  type SortState,
} from "../data/lpbfLeaderboard";

// Read-only view of the Python-generated record docs/LPBF_LEADERBOARD_<date>.json. Every number below is read from
// that JSON: no physics and no statistics are computed here. Screening benchmark of published single tracks, not
// validation. Scores are per (material, quantity) and held-out source; there is deliberately no cross-material rank.

const COLUMNS: ReadonlyArray<{ key: SortKey; label: string }> = [
  { key: "entry", label: "Entry" },
  { key: "kind", label: "Kind" },
  { key: "heldOutSource", label: "Held-out source" },
  { key: "nRows", label: "Rows / sets" },
  { key: "mapePct", label: "MAPE, %" },
  { key: "skill", label: "Skill vs baseline, CI95" },
  { key: "coverage", label: "Coverage 90 %" },
  { key: "unresolved", label: "Unresolved" },
];

function ariaSort(state: SortState, key: SortKey): "ascending" | "descending" | "none" {
  return state.key !== key ? "none" : state.dir === "asc" ? "ascending" : "descending";
}

function skillText(row: LeaderboardRow): string {
  const c = row.cell;
  if (c.skill === null || c.skill === undefined) return "n/a";
  const ci = c.skillCi95 ? ` [${fmtFixed(c.skillCi95[0], 2)}, ${fmtFixed(c.skillCi95[1], 2)}]` : "";
  return `${fmtFixed(c.skill, 2)}${ci}${row.isBaseline ? " (this entry is the baseline)" : ""}`;
}

function coverageText(row: LeaderboardRow): string {
  const cov = row.cell.coverage90;
  if (!cov || cov.coverage === null) return "n/a (no intervals given)";
  const w = cov.wilson95 ? ` [${fmtFixed(cov.wilson95[0], 2)}, ${fmtFixed(cov.wilson95[1], 2)}]` : "";
  return `${fmtFixed(cov.coverage, 2)} (${cov.k}/${cov.n})${w}`;
}

function EntryCell({ row }: { row: LeaderboardRow }) {
  return (
    <td className="p-2 align-top">
      <div className="font-medium text-slate-900">{row.entryName}</div>
      <div className="text-slate-600">{row.entryVersion} · {row.author}</div>
      {row.url ? <div className="text-slate-600">URL (text only): <span>{row.url}</span></div> : null}
    </td>
  );
}

function GroupTable({ group, sort, onSort, testId }: { group: LeaderboardGroup; sort: SortState; onSort: (key: SortKey) => void; testId: string }) {
  const rows = sortRows(group.rows, sort);
  return (
    <div className="overflow-x-auto" data-testid={testId}>
      <table className="w-full text-left text-xs">
        <caption className="mb-2 text-left font-medium text-slate-800">{group.material}, melt-pool {group.quantity} (held-out sources only; screening benchmark, not validation)</caption>
        <thead>
          <tr className="border-b border-slate-200 text-slate-600">
            {COLUMNS.map((c) => (
              <th key={c.key} scope="col" aria-sort={ariaSort(sort, c.key)} className="p-2">
                <button type="button" data-sort-key={c.key} onClick={() => onSort(c.key)} className="inline-flex items-center gap-1 rounded font-semibold text-slate-700 underline decoration-dotted underline-offset-2 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-600">
                  {c.label}
                  <span aria-hidden="true">{sort.key === c.key ? (sort.dir === "asc" ? "▲" : "▼") : ""}</span>
                </button>
              </th>
            ))}
            <th scope="col" className="p-2">Provenance sha256</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const c = row.cell;
            if (c.status !== "scored") {
              return (
                <tr key={row.key} data-testid="leaderboard-excluded" className="border-b border-slate-100 text-slate-600">
                  <EntryCell row={row} />
                  <td className="p-2 align-top">{KIND_LABEL[row.kind]}</td>
                  <td className="p-2 align-top">{c.heldOutSource}</td>
                  <td className="p-2 align-top tabular-nums">{c.nRows} / {c.nSets}</td>
                  <td className="p-2 align-top" colSpan={4}>Excluded: the submission declares it trained on this source, so it is not held out.</td>
                  <td className="p-2 align-top"><code title={row.sha}>{row.sha.slice(0, 12)}</code></td>
                </tr>
              );
            }
            return (
              <tr key={row.key} data-testid="leaderboard-row" className="border-b border-slate-100 text-slate-800">
                <EntryCell row={row} />
                <td className="p-2 align-top">{KIND_LABEL[row.kind]}</td>
                <td className="p-2 align-top">{c.heldOutSource}</td>
                <td className="p-2 align-top tabular-nums">{c.nRows} / {c.nSets}</td>
                <td className="p-2 align-top tabular-nums">{fmtFixed(c.mapePct, 1)}</td>
                <td className="p-2 align-top tabular-nums">{skillText(row)}</td>
                <td className="p-2 align-top tabular-nums">{coverageText(row)}</td>
                <td className="p-2 align-top tabular-nums">{c.unresolved ?? "n/a"}</td>
                <td className="p-2 align-top"><code title={row.sha}>{row.sha.slice(0, 12)}</code></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function NoLeaderboardRecord() {
  return (
    <div role="status" data-testid="no-leaderboard-record" className="rounded-xl border border-slate-300 bg-white p-4 text-sm text-slate-700">
      <div className="mb-2 flex items-center gap-2 font-semibold text-slate-800"><FileSearch className="h-4 w-4" aria-hidden="true" />No leaderboard record committed yet</div>
      <p>Run <code>python -B python/tools/lpbf_benchmark_score.py builtin --table-cache &lt;cache&gt;</code> to generate <code>docs/LPBF_LEADERBOARD_&lt;date&gt;.json</code>. Until then there is nothing to show here: no entry is invented and no ranking is implied.</p>
    </div>
  );
}

export function LpbfLeaderboardPanel({ document: doc = COMMITTED_LEADERBOARD, initialSort = DEFAULT_SORT }: { document?: LpbfLeaderboardDocument | null; initialSort?: SortState } = {}) {
  const [sort, setSort] = useState<SortState>(initialSort);
  const onSort = (key: SortKey) => setSort((s) => nextSort(s, key));
  return (
    <section aria-labelledby="lpbf-leaderboard-title" data-testid="leaderboard" className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <header className="border-b border-slate-100 bg-slate-50 p-4">
        <h2 id="lpbf-leaderboard-title" className="font-semibold text-slate-800">Open screening benchmark leaderboard (LPBF melt pool)</h2>
        <p className="mt-1 text-xs text-slate-700">
          <span data-testid="leaderboard-badge" className="mr-2 inline-block rounded border border-sky-300 bg-sky-100 px-2 py-0.5 font-semibold text-sky-900">Screening benchmark</span>
          Predictions of published single tracks, scored per material and held-out source with the calibration scorecard protocol. Screening benchmark, not validation.
        </p>
      </header>
      <div className="space-y-4 p-4">
        {!doc ? <NoLeaderboardRecord /> : doc.entries.length === 0 ? (
          <p role="status" data-testid="empty-leaderboard" className="text-sm text-slate-700">The committed record holds no entries.</p>
        ) : (
          <>
            <p className="text-xs text-slate-700" data-testid="leaderboard-meta">
              Generated {doc.generatedAt}; implementation fingerprint <code>{doc.implementationHash}</code>; manifest sha256 <code>{doc.manifestSha256}</code>. {doc.calibratedRung.note}
            </p>
            <p className="text-xs text-slate-700">{doc.honesty}</p>
            <p className="text-xs text-slate-600">Use the column header buttons to sort every table; rows are never combined into one cross-material rank. Excluded and unresolved values stay at the bottom.</p>
            {groupRows(doc).map((g) => (
              <GroupTable key={`${g.material}|${g.quantity}`} group={g} sort={sort} onSort={onSort} testId="leaderboard-group" />
            ))}
            <details className="text-xs text-slate-700">
              <summary className="cursor-pointer font-medium">Catalog sentinels (used during physics development, not blind)</summary>
              <div className="mt-2 space-y-4">
                {groupRows(doc, "sentinels").map((g) => (
                  <GroupTable key={`s|${g.material}|${g.quantity}`} group={g} sort={sort} onSort={onSort} testId="leaderboard-sentinel-group" />
                ))}
              </div>
            </details>
          </>
        )}
      </div>
    </section>
  );
}
