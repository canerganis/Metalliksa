import React from 'react';
import { computeMMPDSEmpiricalStats, isSyntheticCouponDataset, type MaterialDataset, type MMPDSEmpiricalAllowableStats } from './uqLabData';

export const formatUqNumber = (value: number | null | undefined, digits = 1) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'Not assessed';
export const UQ_MODEL_STATUS_LABEL = 'Illustrative strength model, not calibrated (see modelStatus)';
/** Honesty label for the solver's toy strength model; `modelStatus` is the solver's provenance note when the response carries it. */
export function UqModelStatusNote({ modelStatus }: { modelStatus?: string }) {
  return (
    <div role="note" data-testid="uq-model-status" className="text-xs text-amber-200 rounded-lg border border-amber-700/50 bg-amber-950/30 px-3 py-2">
      <strong className="text-amber-300">{UQ_MODEL_STATUS_LABEL}</strong>
      {modelStatus ? <span className="block mt-0.5 text-slate-300">{modelStatus}</span> : null}
    </div>
  );
}
export function couponReportRows(dataset: MaterialDataset) {
  return [
    { key: 'yieldStrength', label: 'Yield strength', unit: 'MPa', minimum: dataset.specMinYieldMPa, values: dataset.coupons.map(c => c.yieldStrengthMPa) },
    { key: 'uts', label: 'Ultimate tensile strength', unit: 'MPa', minimum: dataset.specMinUTSMPa, values: dataset.coupons.map(c => c.utsMPa) },
    { key: 'elongation', label: 'Elongation', unit: '%', minimum: dataset.specMinElongationPct, values: dataset.coupons.map(c => c.elongationPct) },
  ].map(row => ({ ...row, stats: computeMMPDSEmpiricalStats(row.values, row.minimum, dataset.coupons.some(c => c.heatLotId.trim()) ? dataset.coupons.map(c => c.heatLotId) : []) }));
}
export const couponProvenance = (dataset: MaterialDataset) => isSyntheticCouponDataset(dataset)
  ? 'Synthetic teaching coupons; not experimental evidence.'
  : 'User-supplied coupon records; source, units, test method and material association require independent verification.';
export function couponWorksheetText(dataset: MaterialDataset): string {
  return [
    'Coupon statistics worksheet — screening only, not qualification',
    `Selected material context: ${dataset.name}`,
    couponProvenance(dataset),
    'Listed specification minima are selected reference context, not verified applicability to imported rows.',
    'Normality not tested. No Anderson–Darling p-value or certified MMPDS allowable is computed.',
    ...couponReportRows(dataset).map(row => `${row.label} (${row.unit}): n=${row.stats.sampleSize}; mean=${formatUqNumber(row.stats.mean)}; sample SD=${formatUqNumber(row.stats.stdDev)}; selected minimum=${row.minimum}; lower-spec index Cpl=${formatUqNumber(row.stats.cpl, 2)}; observed rows above selected minimum=${formatUqNumber(row.stats.conformancePct)}%.`),
    'Normal-model tolerance limits, when shown in the chart, assume independent normally distributed observations. They are approximate screening calculations, not reviewed handbook values.',
  ].join('\n');
}

export function CouponSummary({ stats, unit, synthetic }: { stats: MMPDSEmpiricalAllowableStats; unit: string; synthetic: boolean }) {
  const cards = [
    ['Sample mean', `${formatUqNumber(stats.mean)} ${unit}`, `Sample SD: ${formatUqNumber(stats.stdDev)} ${unit}; n=${stats.sampleSize}`],
    ['Observed conformance', `${formatUqNumber(stats.conformancePct)}%`, 'Fraction of supplied rows above the selected minimum; not a population failure probability.'],
    ['Lower-spec index Cpl', formatUqNumber(stats.cpl, 2), 'Descriptive (mean − lower minimum)/(3 × sample SD). Process stability and distribution suitability are unverified.'],
    ['Normality', 'Not tested', 'No p-value or normal-distribution acceptance is inferred from skewness or kurtosis.'],
  ];
  return <section aria-label="Coupon descriptive statistics" className="space-y-3"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{cards.map(([label, value, detail]) => <div key={label} className="rounded-xl border border-slate-700 bg-slate-900 p-4"><h3 className="text-xs text-slate-400">{label}</h3><p className="mt-2 text-lg font-semibold text-slate-100">{value}</p><p className="mt-2 text-xs text-slate-400">{detail}</p></div>)}</div><p className="text-xs text-amber-200">{synthetic ? 'Synthetic teaching data. ' : 'Uploaded records are unverified. '}No MMPDS handbook allowable or qualification is established.</p>{stats.issues.length > 0 && <p role="status" className="text-xs text-amber-300">{stats.issues.join(' ')}</p>}</section>;
}

export function CouponWorksheet({ dataset, onCopy, notification }: { dataset: MaterialDataset; onCopy: (value: string, label: string) => void; notification: string | null }) {
  const rows = couponReportRows(dataset);
  return <section aria-label="Coupon statistics worksheet" className="space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-5"><div className="flex flex-wrap justify-between gap-3"><h3 className="font-semibold text-slate-100">Coupon statistics worksheet</h3><button className="rounded border border-slate-600 px-3 py-2 text-xs text-slate-200" onClick={() => onCopy(couponWorksheetText(dataset), 'Worksheet copied')}>{notification || 'Copy Report'}</button></div><p className="text-xs text-amber-200">{couponProvenance(dataset)} No qualification or certified allowable is established.</p><p className="text-xs text-slate-400">Selected context: {dataset.name}. Reference minima are not verified specifications for imported specimens. Normality is not tested; source methods and lot independence require review.</p><div className="overflow-x-auto"><table className="w-full text-left text-xs text-slate-300"><thead><tr>{['Property','Unit','n','Mean','Sample SD','Selected minimum','Cpl','Observed conformance'].map(label => <th key={label} className="whitespace-nowrap border-b border-slate-700 p-2">{label}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.key}><td className="p-2">{row.label}</td><td className="p-2">{row.unit}</td><td className="p-2">{row.stats.sampleSize}</td><td className="p-2">{formatUqNumber(row.stats.mean)}</td><td className="p-2">{formatUqNumber(row.stats.stdDev)}</td><td className="p-2">{row.minimum}</td><td className="p-2">{formatUqNumber(row.stats.cpl,2)}</td><td className="p-2">{formatUqNumber(row.stats.conformancePct)}%</td></tr>)}</tbody></table></div><p className="text-xs text-slate-500">Each property is calculated from its own supplied column. Missing or insufficient statistics remain not assessed. Changing the chart property does not change worksheet column identity.</p></section>;
}
