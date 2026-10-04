import React from "react";
import type {
  MeasuredQuantity,
  MicrographClassResult,
  MicrographGrainSize,
  MicrographMeasureResult,
} from "../services/micrographMeasureService";

/** Display formatting only (significant digits); every value comes from the Python result unchanged. */
export function fmt(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (value === 0) return "0";
  const abs = Math.abs(value);
  return abs >= 1e5 || abs < 1e-3 ? value.toExponential(digits - 1) : Number(value.toPrecision(digits)).toString();
}

export function fmtPct(fraction: number | null | undefined, digits = 4): string {
  return fraction === null || fraction === undefined ? "—" : `${fmt(fraction * 100, digits)} %`;
}

function Quantity({ q, pct = false }: { q: MeasuredQuantity; pct?: boolean }) {
  if (q.value === null) return <span className="text-slate-400">Unavailable: {q.reason}</span>;
  const show = (v: number | null) => (pct ? fmtPct(v) : fmt(v));
  const unit = pct || !q.unit || q.unit === "1" ? "" : ` ${q.unit}`;
  return (
    <span>
      <span className="text-white font-mono">{show(q.value)}{unit}</span>
      {q.ci95 && (
        <span className="text-slate-400 font-mono"> (95 % CI {show(q.ci95[0])} to {show(q.ci95[1])}{unit})</span>
      )}
    </span>
  );
}

function Row({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <tr className="border-b border-[#162032] align-top">
      <th scope="row" className="text-left font-normal text-slate-400 pr-3 py-1 w-56">{name}</th>
      <td className="py-1 text-slate-200">{children}</td>
    </tr>
  );
}

function ClassBlock({ cls }: { cls: MicrographClassResult }) {
  const af = cls.areaFraction;
  const p = cls.particles;
  const rule = cls.threshold.maxGrey !== undefined ? `grey ≤ ${cls.threshold.maxGrey}` : `grey ≥ ${cls.threshold.minGrey}`;
  return (
    <section className="space-y-1" aria-label={`Results for ${cls.label}`}>
      <h4 className="text-xs font-mono font-bold text-sky-300">{cls.label} ({rule})</h4>
      <table className="w-full text-xs"><tbody>
        <Row name="Area fraction (A_A)"><Quantity q={af.pixelFraction} pct /></Row>
        <Row name="Field-to-field spread">
          {af.fieldToField.tiles} tiles, SD {fmtPct(af.fieldToField.sd)}, half-width {fmtPct(af.fieldToField.halfWidth)}
        </Row>
        <Row name={`Threshold ∓${af.thresholdSensitivity.deltaGrey} grey levels`}>
          {fmtPct(af.thresholdSensitivity.fractionAtThresholdMinusDelta)} / {fmtPct(af.thresholdSensitivity.fractionAtThresholdPlusDelta)}
        </Row>
        <Row name="Class area"><Quantity q={af.classArea} /></Row>
        <Row name="Particles counted">
          {p.count} ({p.countTouchingRoiEdge} touch the ROI edge; {p.componentsBelowMinArea} below {p.minAreaPx} px not counted)
        </Row>
        <Row name="Detection limit (ECD)"><Quantity q={p.detectionLimitEcdUm} /></Row>
        <Row name="Number density"><Quantity q={p.numberDensity} /></Row>
        <Row name="Mean ECD"><Quantity q={p.meanEcd} /></Row>
        <Row name="Median / max ECD"><Quantity q={p.medianEcd} /> · <Quantity q={p.maxEcd} /></Row>
        <Row name="Mean free path"><Quantity q={p.meanFreePath} /></Row>
        <Row name="Shape classes">
          {Object.entries(p.shapeClasses).map(([k, v]) => `${k}: ${v}`).join(", ")}
        </Row>
      </tbody></table>
      <p className="text-[10px] text-slate-500">{p.shapeClassRule} Size statistics: {p.sizeStatisticsBasis}.</p>
    </section>
  );
}

function GrainBlock({ title, gs }: { title: string; gs: MicrographGrainSize }) {
  return (
    <section className="space-y-1" aria-label={title}>
      <h4 className="text-xs font-mono font-bold text-sky-300">{title}</h4>
      <table className="w-full text-xs"><tbody>
        <Row name="Intersections P">{fmt(gs.totalIntersections)} on {gs.lines} lines ({fmt(gs.totalLengthPx)} px)</Row>
        <Row name="Mean intercept length"><Quantity q={gs.meanIntercept} /></Row>
        <Row name="ASTM E112 grain size number G"><Quantity q={gs.astmG} /></Row>
        <Row name="Relative accuracy">{gs.relativeAccuracyPct === null ? "—" : `${fmt(gs.relativeAccuracyPct, 3)} %`}</Row>
      </tbody></table>
      {gs.warnings.length > 0 && (
        <ul role="alert" className="text-[11px] text-amber-300 list-disc pl-4">
          {gs.warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}
      <p className="text-[10px] text-slate-500">{gs.countingRule}. {gs.ciNote ?? ""}</p>
    </section>
  );
}

/** Presentational view of a Python measurement result. It shows the returned values; it computes none. */
export const MicrographMeasureResults: React.FC<{ result: MicrographMeasureResult; stale: boolean }> = ({ result, stale }) => {
  const cal = result.record.calibration;
  return (
    <div className={`space-y-4 ${stale ? "opacity-40" : ""}`} aria-live="polite">
      {stale && (
        <p role="status" className="text-xs text-amber-300">Inputs changed after this run: these results are out of date. Run again.</p>
      )}
      <div className="text-[11px] text-slate-400 space-y-0.5">
        <div>Calibration: {cal.calibrated ? `${fmt(cal.umPerPx, 6)} µm/px (${cal.method}; ${cal.derivation})` : cal.reason}</div>
        <div>ROI: x {result.record.roi.x0}-{result.record.roi.x1}, y {result.record.roi.y0}-{result.record.roi.y1} px · pixel SHA-256 {result.record.pixelSha256.slice(0, 16)}…</div>
        <div>Method {result.methodVersion} (python/micrograph_measure.py)</div>
      </div>
      {result.classes.dark && <ClassBlock cls={result.classes.dark} />}
      {result.classes.bright && <ClassBlock cls={result.classes.bright} />}
      {result.grainSize && <GrainBlock title="Grain size, automatic intersection count" gs={result.grainSize} />}
      {result.grainSizeManual && <GrainBlock title="Grain size, manual intersection count" gs={result.grainSizeManual} />}
      <details className="text-[11px] text-slate-400">
        <summary className="cursor-pointer">Limitations</summary>
        <ul className="list-disc pl-4 mt-1">{result.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      </details>
    </div>
  );
};
