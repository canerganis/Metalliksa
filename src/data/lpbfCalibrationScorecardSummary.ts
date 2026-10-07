/**
 * Pure plain-language summary of a calibration scorecard view record. It only selects, orders and formats numbers
 * that already exist in the record (no physics, no statistics beyond min/max over shown fields). Every number is
 * returned with the record field it was read from. Screening only, not validation.
 */
import { statusCounts, type LpbfCalibrationScorecardDocument, type ScorecardHeadlineRow } from "./lpbfCalibrationScorecard";

export const SUMMARY_METRIC_DEFINITION = "MAPE on held-out sources, leave-one-source-out, equal source weight.";
export const SUMMARY_LEGEND = "< 20 % lower error / 20-35 % moderate / > 35 % high - display bands chosen by this page, not a validation criterion";

export interface SummaryNumber { readonly display: string; readonly source: string }
export interface SummaryPart { readonly t: string; readonly number?: SummaryNumber }
export interface SummaryItem {
  readonly id: string;
  readonly text: string;
  readonly parts: readonly SummaryPart[];
  readonly numbers: readonly SummaryNumber[];
}
export interface ScorecardSummary { readonly items: readonly SummaryItem[]; readonly notes: readonly string[] }

const KERNELS: Readonly<Record<string, string>> = { rosenthal: "Rosenthal", "eagar-tsai": "Eagar-Tsai", goldak: "Goldak" };
const kernelName = (k: string): string => KERNELS[k] ?? k;
const dp1 = (v: number): string => { const t = v.toFixed(1); return t === "-0.0" ? "0.0" : t; };
const dp2 = (v: number): string => v.toFixed(2);

/** Display bands chosen by this page (see SUMMARY_LEGEND); they are not a validation criterion. */
export function errorWord(mapePercent: number): "lower error" | "moderate" | "high" {
  const r = Number(dp1(mapePercent));
  return r < 20 ? "lower error" : r <= 35 ? "moderate" : "high";
}

type PartInput = string | SummaryNumber;
function item(id: string, inputs: readonly PartInput[]): SummaryItem {
  const parts = inputs.map<SummaryPart>((p) => (typeof p === "string" ? { t: p } : { t: p.display, number: p }));
  return { id, parts, text: parts.map((p) => p.t).join(""), numbers: parts.flatMap((p) => (p.number ? [p.number] : [])) };
}

type Scored = { row: ScorecardHeadlineRow; v: number };

const rowIndex = (doc: LpbfCalibrationScorecardDocument, r: ScorecardHeadlineRow): number => doc.headline.indexOf(r);
const mapeNum = (doc: LpbfCalibrationScorecardDocument, r: ScorecardHeadlineRow, v: number): SummaryNumber =>
  ({ display: `${dp1(v)} %`, source: `headline[${rowIndex(doc, r)}].headline.equalSourceWeight.mapeDefault` });
const withWord = (n: SummaryNumber, v: number): PartInput[] => [n, ` (${errorWord(v)})`];

function scored(rows: readonly ScorecardHeadlineRow[]): Scored[] {
  const out: Scored[] = [];
  for (const row of rows) {
    const v = row.headline?.equalSourceWeight.mapeDefault;
    if (v !== null && v !== undefined) out.push({ row, v });
  }
  return out;
}

function rangeParts(doc: LpbfCalibrationScorecardDocument, label: string, rows: readonly ScorecardHeadlineRow[]): PartInput[] | null {
  const s = scored(rows);
  if (s.length === 0) return null;
  const lo = s.reduce((a, b) => (b.v < a.v ? b : a));
  const hi = s.reduce((a, b) => (b.v > a.v ? b : a));
  return [`${label}: `, ...withWord(mapeNum(doc, lo.row, lo.v), lo.v), " to ", ...withWord(mapeNum(doc, hi.row, hi.v), hi.v)];
}

interface ConfusionCell { readonly label: string; readonly n: number; readonly accuracy: number; readonly source: string }

function confusionCells(doc: LpbfCalibrationScorecardDocument): ConfusionCell[] {
  const out: ConfusionCell[] = [];
  for (const [alloy, blk] of Object.entries(doc.regimeConfusion.byAlloy)) {
    for (const [key, value] of Object.entries(blk)) {
      if (!key.startsWith("beam")) continue;
      const at = (value as { atDefaultEta?: { n?: unknown; accuracy?: unknown } }).atDefaultEta;
      if (at && typeof at.n === "number" && typeof at.accuracy === "number" && Number.isFinite(at.accuracy)) {
        out.push({ label: `${alloy}, KU beam reading ${key.slice(4)} µm`, n: at.n, accuracy: at.accuracy, source: `regimeConfusion.byAlloy["${alloy}"]["${key}"].atDefaultEta.accuracy` });
      }
    }
  }
  return out;
}

export function summarizeScorecard(doc: LpbfCalibrationScorecardDocument): ScorecardSummary {
  const items: SummaryItem[] = [];
  const counts = statusCounts(doc);
  const enabledNum: SummaryNumber = { display: String(counts.enabled), source: "gateSummary.enabled (count of headline[].status = enabled)" };
  const totalNum: SummaryNumber = { display: String(doc.headline.length), source: "headline.length" };

  // (a) calibration outcome
  items.push(counts.enabled === 0
    ? item("calibration", [enabledNum, " of ", totalNum, " cells passed the gate, so calibrated mode is not offered; all results are unchanged screening output"])
    : item("calibration", [enabledNum, " of ", totalNum, " cells passed the gate; calibrated mode is offered only for those cells, every other result is unchanged screening output"]));

  // (b) best held-out accuracy per quantity
  for (const q of ["width", "depth"] as const) {
    const rows = doc.headline.filter((r) => r.quantity === q);
    const s = scored(rows);
    if (s.length === 0) {
      items.push(item(`best-${q}`, [`Best held-out ${q} accuracy: no held-out errors available`]));
      continue;
    }
    const best = s.reduce((a, b) => (b.v < a.v ? b : a));
    const parts: PartInput[] = [`Best held-out ${q} accuracy: ${kernelName(best.row.kernel)}, ${best.row.material}, `, ...withWord(mapeNum(doc, best.row, best.v), best.v), " (default rung)"];
    for (const r of rows.filter((x) => x.status === "enabled")) {
      const served = r.headline?.equalSourceWeight.mapeServed;
      if (served === null || served === undefined) continue;
      parts.push(`; served by enabled cell ${kernelName(r.kernel)}, ${r.material}: `,
        { display: `${dp1(served)} %`, source: `headline[${rowIndex(doc, r)}].headline.equalSourceWeight.mapeServed` });
    }
    items.push(item(`best-${q}`, parts));
  }

  // (c) where it fails
  const depthRange = rangeParts(doc, "Depth held-out error across kernels", doc.headline.filter((r) => r.quantity === "depth"));
  if (depthRange) items.push(item("fail-depth", depthRange));
  for (const q of ["width", "depth"] as const) {
    const p = rangeParts(doc, `Rosenthal ${q} held-out error`, doc.headline.filter((r) => r.kernel === "rosenthal" && r.quantity === q));
    if (p) items.push(item(`fail-rosenthal-${q}`, p));
  }
  doc.n01.forEach((n, i) => {
    const d = n.rungs.default;
    if (!d || d.widthFactor === null || d.depthFactor === null) return;
    items.push(item(`fail-n01-${n.kernel}`, [`Guo N01 (known failure, not fitted), ${kernelName(n.kernel)}, default rung, predicted / measured: width x`,
      { display: dp2(d.widthFactor), source: `n01[${i}].rungs.default.widthFactor` }, ", depth x",
      { display: dp2(d.depthFactor), source: `n01[${i}].rungs.default.depthFactor` }]));
  });
  const conf = confusionCells(doc);
  if (conf.length > 0) {
    const lo = conf.reduce((a, b) => (b.accuracy < a.accuracy ? b : a));
    const hi = conf.reduce((a, b) => (b.accuracy > a.accuracy ? b : a));
    const acc = (c: ConfusionCell): PartInput[] => [{ display: `${dp1(c.accuracy * 100)} %`, source: c.source }, ` (${c.label}, n = `, { display: String(c.n), source: c.source.replace(/accuracy$/, "n") }, ")"];
    items.push(item("fail-regime", ["Regime label accuracy at the default absorptivity, against published labels: ", ...acc(lo), " to ", ...acc(hi)]));
  }

  // (d) not covered
  const alloys = [...new Set(doc.headline.map((r) => r.material))];
  const noData = alloys.filter((a) => doc.headline.filter((r) => r.material === a).every((r) => r.status === "no-data"));
  if (noData.length > 0) items.push(item("not-covered", [`Not covered: no trainable source, so no result at all, for ${noData.join(" and ")}`]));

  return { items, notes: doc.notes };
}
