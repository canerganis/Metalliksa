import React, { useEffect, useRef, useState } from "react";
import { AlertTriangle, Grid3x3, Info, RefreshCw } from "lucide-react";
import {
  GrSolidificationRequestError,
  runGrSolidification,
  type GrAlloyId,
  type GrCell,
  type GrCellBody,
  type GrSolidificationResponse,
} from "../services/lpbfGrSolidificationService";
import { LITERATURE_PV_WINDOWS } from "../utils/lpbfFourAlloySchema";
import {
  BAND_COLORS,
  BAND_LETTERS,
  GR_HATCH_PATTERN_ID,
  GR_MAX_CELLS,
  METRICS,
  SEQUENTIAL_STOPS,
  STATUS_LABELS,
  cellAriaLabel,
  cellAt,
  cellGlyph,
  cellStyle,
  checkedGrSolidification,
  formatSci,
  isOutsideRegime,
  metricRange,
  moveCell,
  type GrMetric,
} from "../data/lpbfGrSolidification";
import {
  defaultAxisRange,
  parseAxis,
  type CellPosition,
} from "../data/lpbfProcessWindow";

const GRID_KEYS = new Set(["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"]);
const MAX_POWER_W = 1500;
const MAX_SPEED_MM_S = 10000;
const panelClass = "rounded-2xl border border-white/10 bg-[#111b25] shadow-[0_18px_50px_rgba(0,0,0,.18)]";
const inputClass = "w-full rounded-lg border border-white/10 bg-[#0b141d] px-2.5 py-2 font-mono text-sm text-slate-100 outline-none transition focus:border-cyan-300/60 focus:ring-2 focus:ring-cyan-300/10";

export const GR_BANNER_TEXT =
  "Screening only. Conduction-field G/R from the frozen Rosenthal model; Hunt bands are uncalibrated; CET constants unavailable for this alloy; not a grain-structure prediction.";

interface FormState {
  alloyId: GrAlloyId;
  beam: string;
  layer: string;
  hatch: string;
  preheat: string;
  pMin: string; pMax: string; pN: string;
  vMin: string; vMax: string; vN: string;
}

function defaultForm(alloyId: GrAlloyId): FormState {
  const base = { beam: "80", layer: "40", hatch: "110", preheat: "80" };
  if (alloyId === "in718") {
    const box = LITERATURE_PV_WINDOWS.in718;
    const p = defaultAxisRange({ min: box.powerMin_W, max: box.powerMax_W });
    const v = defaultAxisRange({ min: box.speedMin_mm_s, max: box.speedMax_mm_s });
    return { alloyId, ...base, pMin: String(p.min), pMax: String(p.max), pN: "7", vMin: String(v.min), vMax: String(v.max), vN: "7" };
  }
  return { alloyId, ...base, pMin: "", pMax: "", pN: "7", vMin: "", vMax: "", vN: "7" };
}

const fmtNum = (v: number | null | undefined, digits = 3): string => formatSci(v, digits);

// ---------------------------------------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------------------------------------
export const GrLegend: React.FC<{ result: GrSolidificationResponse; metric: GrMetric }> = ({ result, metric }) => {
  const spec = METRICS.find(m => m.id === metric)!;
  const cells = result.cells ?? [];
  if (metric === "band") {
    return (
      <div data-testid="gr-legend" className="space-y-1 text-xs text-slate-300">
        <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
          {Object.entries(BAND_COLORS).map(([band, color]) => (
            <li key={band} className="flex items-center gap-2">
              <span className="inline-flex h-4 w-5 items-center justify-center rounded-sm text-[10px] font-bold text-slate-900" style={{ background: color }} aria-hidden="true">{BAND_LETTERS[band]}</span>
              {band}
            </li>
          ))}
        </ul>
        <p className="text-slate-400">Uncalibrated Hunt G/R thresholds, not a CET prediction.</p>
      </div>
    );
  }
  const range = metricRange(cells, metric);
  const gradient = `linear-gradient(to right, ${SEQUENTIAL_STOPS.join(", ")})`;
  return (
    <div data-testid="gr-legend" className="space-y-1 text-xs text-slate-300">
      <div className="h-3 w-full max-w-sm rounded-sm" style={{ background: gradient }} aria-hidden="true" />
      <div className="flex max-w-sm justify-between font-mono">
        <span data-testid="gr-legend-min">{range ? (metric === "laves" ? range.min.toFixed(4) : range.min.toFixed(2)) : "no value"}</span>
        <span className="text-slate-400">{spec.unit}</span>
        <span data-testid="gr-legend-max">{range ? (metric === "laves" ? range.max.toFixed(4) : range.max.toFixed(2)) : "no value"}</span>
      </div>
      <p className="text-slate-400">Outlined empty cells have no value (error, unavailable or solver floor). Hatched cells are keyhole regime, outside the conduction model.</p>
    </div>
  );
};

// ---------------------------------------------------------------------------------------------------------
// Heat map (SVG, role=grid, one tab stop)
// ---------------------------------------------------------------------------------------------------------
const M = { left: 64, right: 12, top: 12, bottom: 54 };
const PLOT_W = 600;
const PLOT_H = 360;

export const GrHeatmap: React.FC<{
  result: GrSolidificationResponse;
  metric: GrMetric;
  selected: CellPosition | null;
  onSelect?: (position: CellPosition) => void;
  stale?: boolean;
}> = ({ result, metric, selected, onSelect, stale }) => {
  const grid = result.grid!;
  const { nP, nV, powers_W, speeds_mm_s } = grid;
  const cw = PLOT_W / nV;
  const ch = PLOT_H / nP;
  const gridRef = useRef<SVGGElement | null>(null);
  const [focused, setFocused] = useState(false);
  const range = metricRange(result.cells ?? [], metric);
  const fontSize = Math.max(9, Math.min(cw, ch) * 0.4);
  const activeId = selected ? `gr-cell-${selected.iP}-${selected.iV}` : undefined;
  const x = (iV: number) => M.left + iV * cw;
  const y = (iP: number) => M.top + PLOT_H - (iP + 1) * ch;

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (!GRID_KEYS.has(event.key) || !onSelect) return;
    event.preventDefault();
    onSelect(moveCell(selected ?? { iP: 0, iV: 0 }, event.key, nP, nV));
  };

  return (
    <div data-testid="gr-heatmap" data-stale={stale ? "true" : "false"} className={stale ? "opacity-60" : undefined}>
      <svg viewBox={`0 0 ${M.left + PLOT_W + M.right} ${M.top + PLOT_H + M.bottom}`} className="h-auto w-full" role="group" aria-label={`G/R solidification map for ${result.materialName}: speed on the horizontal axis, power on the vertical axis`}>
        <defs>
          <pattern id={GR_HATCH_PATTERN_ID} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#f8fafc" strokeWidth="1.6" strokeOpacity="0.75" />
          </pattern>
        </defs>
        <g
          ref={gridRef}
          role="grid"
          tabIndex={0}
          aria-label="G/R solidification cells. Use the arrow keys to move between cells, Home and End for the first and last speed, Page Up and Page Down for the highest and lowest power."
          aria-rowcount={nP}
          aria-colcount={nV}
          aria-activedescendant={activeId}
          data-testid="gr-grid"
          onKeyDown={onKeyDown}
          onFocus={() => { setFocused(true); if (!selected && onSelect) onSelect({ iP: 0, iV: 0 }); }}
          onBlur={() => setFocused(false)}
          style={{ outline: "none" }}
        >
          {Array.from({ length: nP }, (_, rowFromBottom) => {
            const iP = nP - 1 - rowFromBottom;
            return (
              <g key={iP} role="row" aria-rowindex={rowFromBottom + 1}>
                {Array.from({ length: nV }, (_, iV) => {
                  const cell = cellAt(result, iP, iV);
                  const style = cellStyle(cell, metric, range);
                  const outside = isOutsideRegime(cell);
                  const glyph = cellGlyph(cell, metric);
                  return (
                    <g
                      key={iV}
                      id={`gr-cell-${iP}-${iV}`}
                      role="gridcell"
                      aria-colindex={iV + 1}
                      aria-selected={selected?.iP === iP && selected?.iV === iV}
                      aria-label={cellAriaLabel(cell, metric)}
                      data-testid={`gr-cell-${iP}-${iV}`}
                      data-status={cell.status}
                      data-outside-regime={outside ? "true" : "false"}
                      data-no-value={style.noValue ? "true" : "false"}
                      onClick={() => { onSelect?.({ iP, iV }); gridRef.current?.focus(); }}
                      style={{ cursor: onSelect ? "pointer" : undefined }}
                    >
                      <rect
                        x={x(iV)} y={y(iP)} width={cw} height={ch}
                        fill={style.fill}
                        stroke={style.outlined ? style.stroke : "#0f172a"}
                        strokeWidth={style.outlined ? 2 : 1}
                        strokeDasharray={style.outlined ? "4 3" : undefined}
                      />
                      {outside && <rect data-testid="gr-keyhole-marker" x={x(iV)} y={y(iP)} width={cw} height={ch} fill={`url(#${GR_HATCH_PATTERN_ID})`} pointerEvents="none" />}
                      {glyph && <text x={x(iV) + cw / 2} y={y(iP) + ch / 2 + fontSize * 0.35} textAnchor="middle" fontSize={fontSize} fontWeight={700} fill={style.textColor} aria-hidden="true">{glyph}</text>}
                    </g>
                  );
                })}
              </g>
            );
          })}
          {selected && (
            <rect data-testid="gr-active-ring" x={x(selected.iV)} y={y(selected.iP)} width={cw} height={ch}
              fill="none" stroke={focused ? "#38bdf8" : "#e2e8f0"} strokeWidth={focused ? 4 : 2.5} pointerEvents="none" />
          )}
        </g>
        <g fontSize="11" fill="#cbd5e1" aria-hidden="true">
          {speeds_mm_s.map((v, iV) => (iV % (nV > 10 ? 2 : 1) === 0) && <text key={`v${iV}`} x={x(iV) + cw / 2} y={M.top + PLOT_H + 16} textAnchor="middle">{v}</text>)}
          {powers_W.map((p, iP) => (iP % (nP > 10 ? 2 : 1) === 0) && <text key={`p${iP}`} x={M.left - 8} y={y(iP) + ch / 2 + 4} textAnchor="end">{p}</text>)}
          <text x={M.left + PLOT_W / 2} y={M.top + PLOT_H + 40} textAnchor="middle" fontSize="12" fill="#e2e8f0">Scan speed v (mm/s)</text>
          <text transform={`translate(14 ${M.top + PLOT_H / 2}) rotate(-90)`} textAnchor="middle" fontSize="12" fill="#e2e8f0">Laser power P (W)</text>
        </g>
      </svg>
    </div>
  );
};

// ---------------------------------------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------------------------------------
const LocationRow: React.FC<{ name: string; loc: GrCellBody["front"]["median"]; band: string | null }> = ({ name, loc, band }) => (
  <tr className="border-t border-white/[.06]">
    <th scope="row" className="py-1 pr-2 text-left font-medium text-slate-300">{name}</th>
    <td className="py-1 pr-2 font-mono">{loc ? fmtNum(loc.G_K_m) : "n/a"}</td>
    <td className="py-1 pr-2 font-mono">{loc ? fmtNum(loc.R_m_s) : "n/a"}</td>
    <td className="py-1 pr-2 font-mono">{loc ? fmtNum(loc.GoverR_K_s_m2) : "n/a"}</td>
    <td className="py-1 pr-2 font-mono">{loc ? fmtNum(loc.GtimesR_K_s) : "n/a"}</td>
    <td className="py-1">{band ?? "n/a"}</td>
  </tr>
);

export const GrCellDetail: React.FC<{ body: (GrCellBody & { power_W: number; speed_mm_s: number }) | null; result: GrSolidificationResponse }> = ({ body, result }) => {
  if (!body) {
    return <p data-testid="gr-detail-empty" className="text-sm text-slate-400">Select a cell (click it, or Tab to the grid and use the arrow keys) to see G, R, the bands and the Laves bound.</p>;
  }
  const cl = body.rosenthalCenterline;
  const laves = body.laves;
  const ub = laves.sampledArcUpperBound;
  return (
    <div data-testid="gr-detail" aria-live="polite" className="space-y-3 text-sm text-slate-300">
      <h3 className="font-semibold text-slate-100">{STATUS_LABELS[body.status]}: {body.power_W} W, {body.speed_mm_s} mm/s</h3>
      {body.reason && <p role={body.status === "error" ? "alert" : "note"} data-testid="gr-detail-reason" className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-100">{body.reason}</p>}
      {body.regimeNote && <p data-testid="gr-detail-regime" className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-100">{body.regime}. {body.regimeNote}</p>}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-xs" data-testid="gr-detail-table">
          <caption className="pb-1 text-left text-slate-400">Rear liquidus arc, copied from the frozen solver (G in K/m, R in m/s, G/R in K s/m^2, G*R in K/s)</caption>
          <thead><tr className="text-left text-slate-500"><th scope="col" className="pr-2">Point</th><th scope="col" className="pr-2">G</th><th scope="col" className="pr-2">R</th><th scope="col" className="pr-2">G/R</th><th scope="col" className="pr-2">G*R</th><th scope="col">Hunt G/R screening band</th></tr></thead>
          <tbody>
            <LocationRow name="Bottom" loc={body.front.bottom} band={body.morphology.bands.bottom} />
            <LocationRow name="Median" loc={body.front.median} band={body.morphology.bands.median} />
            <LocationRow name="Tail" loc={body.front.tail} band={body.morphology.bands.tail} />
          </tbody>
        </table>
        <p className="mt-1 text-xs text-slate-500">{body.front.coolingBasis}. {body.morphology.label}.</p>
      </div>
      <div data-testid="gr-detail-rosenthal" className="text-xs">
        <p className="font-semibold text-slate-400">Rosenthal trailing-centreline reference</p>
        {cl.status === "available" ? (
          <>
            <p className="font-mono">x_tail {cl.xTail_um?.toFixed(1)} um, G {fmtNum(cl.G_K_m)} K/m, R {fmtNum(cl.R_m_s)} m/s, G/R {fmtNum(cl.GoverR_K_s_m2)}, G*R {fmtNum(cl.GtimesR_K_s)}</p>
            <p className="text-slate-500">{cl.label}</p>
          </>
        ) : <p>Unavailable: {cl.reason}</p>}
      </div>
      <div data-testid="gr-detail-cet" className="text-xs">
        <p className="font-semibold text-slate-400">CET: {body.cet.status}</p>
        {body.cet.status === "unavailable" ? <p>{body.cet.reason}</p> : (
          <ul className="list-disc pl-5">{(["bottom", "median", "tail"] as const).map(k => <li key={k}>{k}: {body.cet.locations[k]?.band ?? "n/a"}</li>)}</ul>
        )}
      </div>
      <div data-testid="gr-detail-laves" className="text-xs">
        <p className="font-semibold text-slate-400">Laves (binary C = 0 upper bound, fraction of the liquid)</p>
        <p className="font-mono">Equilibrium-k bound (whole boundary): {result.laves.equilibriumKBound.toFixed(4)}</p>
        {laves.status === "available" && ub ? (
          <>
            <p className="font-mono">Trapping-adjusted, sampled arc only: {ub.f.toFixed(4)} (at {ub.location}, R {fmtNum(ub.R_m_s)} m/s, V_D {ub.V_D_m_s} m/s, k {ub.kEff.toFixed(4)})</p>
            {laves.note && <p className="mt-1 text-slate-500">{laves.note}</p>}
          </>
        ) : <p>Trapping-adjusted bound unavailable: {laves.reason}</p>}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------------------------------------
type Props = { initialResult?: GrSolidificationResponse | null };

const formKey = (f: FormState): string => JSON.stringify(f);

export const GrSolidificationMapCard: React.FC<Props> = ({ initialResult = null }) => {
  const [form, setForm] = useState<FormState>(() => defaultForm("in718"));
  const [result, setResult] = useState<GrSolidificationResponse | null>(initialResult);
  const [resultKey, setResultKey] = useState<string | null>(initialResult ? formKey(defaultForm(initialResult.alloyId)) : null);
  const [metric, setMetric] = useState<GrMetric>("goverr");
  const [selected, setSelected] = useState<CellPosition | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ kind: "validation" | "engine-unavailable" | "response"; message: string } | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => () => abortRef.current?.abort(), []);

  const set = (patch: Partial<FormState>) => setForm(prev => ({ ...prev, ...patch }));
  const stale = result !== null && resultKey !== formKey(form);
  const hasBox = form.alloyId === "in718";
  const powerAxis = parseAxis(form.pMin, form.pMax, form.pN, "Power", "W", MAX_POWER_W);
  const speedAxis = parseAxis(form.vMin, form.vMax, form.vN, "Speed", "mm/s", MAX_SPEED_MM_S);
  const nums = ["beam", "layer", "hatch"].map(k => Number(form[k as "beam" | "layer" | "hatch"]));
  const preheat = Number(form.preheat);
  const processOk = nums.every(n => Number.isFinite(n) && n > 0) && form.preheat.trim() !== "" && Number.isFinite(preheat) && preheat >= 0;
  const cellCount = powerAxis.values.length * speedAxis.values.length;
  const blocker = !processOk
    ? "Beam, layer and hatch must be greater than 0 and preheat must be 0 or more."
    : !powerAxis.ok ? powerAxis.reason
      : !speedAxis.ok ? speedAxis.reason
        : cellCount > GR_MAX_CELLS ? `At most ${GR_MAX_CELLS} cells are allowed (got ${cellCount}).` : null;

  const compute = async () => {
    if (blocker) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const key = formKey(form);
    setLoading(true);
    setError(null);
    try {
      const raw = await runGrSolidification({
        mode: "map", alloyId: form.alloyId, beamDiameter_um: nums[0], layer_um: nums[1], hatch_um: nums[2],
        preheatTemp_C: preheat, powers: powerAxis.values, speeds: speedAxis.values,
      }, controller.signal);
      if (controller.signal.aborted) return;
      setResult(checkedGrSolidification(raw));
      setResultKey(key);
      setSelected(null);
    } catch (e) {
      if (controller.signal.aborted) return;
      if (e instanceof GrSolidificationRequestError) setError({ kind: e.kind, message: e.message });
      else setError({ kind: "response", message: e instanceof Error ? e.message : "Unexpected response." });
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  };

  const selectedCell: GrCell | null = result?.grid && selected ? cellAt(result, selected.iP, selected.iV) ?? null : null;
  const field = (label: string, key: keyof FormState, unit?: string, type = "number") => (
    <label className="block text-xs text-slate-400">
      <span className="mb-1 block">{label}{unit ? ` (${unit})` : ""}</span>
      <input className={inputClass} type={type} inputMode="decimal" value={form[key]} onChange={e => set({ [key]: e.target.value } as Partial<FormState>)} />
    </label>
  );

  return (
    <section className={`${panelClass} space-y-4 p-4 sm:p-5`} aria-labelledby="gr-heading" data-testid="gr-card">
      <header className="flex flex-wrap items-center gap-2">
        <Grid3x3 className="h-4 w-4 text-cyan-200" aria-hidden="true" />
        <h2 id="gr-heading" className="text-base font-semibold text-slate-100">G/R solidification map (screening)</h2>
      </header>
      <p data-testid="gr-banner" role="note" className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-100">{GR_BANNER_TEXT}</p>
      {result && (
        <p data-testid="gr-evidence" className="text-xs text-slate-400">{result.evidence.statement}</p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <label className="block text-xs text-slate-400">
          <span className="mb-1 block">Alloy</span>
          <select className={inputClass} value={form.alloyId} onChange={e => setForm(defaultForm(e.target.value as GrAlloyId))}>
            <option value="in718">IN718</option>
            <option value="in625">IN625</option>
          </select>
        </label>
        {field("Beam diameter", "beam", "um")}
        {field("Layer", "layer", "um")}
        {field("Hatch", "hatch", "um")}
        {field("Preheat", "preheat", "C")}
      </div>
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
        {field("Power min", "pMin", "W")}
        {field("Power max", "pMax", "W")}
        {field("Power n", "pN")}
        {field("Speed min", "vMin", "mm/s")}
        {field("Speed max", "vMax", "mm/s")}
        {field("Speed n", "vN")}
      </div>
      {!hasBox && <p data-testid="gr-no-box" className="flex items-start gap-1.5 text-xs text-slate-400"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />No literature P-v box for IN625 in the repository; enter a range.</p>}
      {hasBox && <p className="text-xs text-slate-500">Default range: 0.5 x to 1.5 x the IN718 literature P-v box.</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button" onClick={compute} disabled={loading || blocker !== null} data-testid="gr-compute"
          className="inline-flex items-center gap-2 rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
          {loading ? "Computing" : "Compute map"}
        </button>
        <span className="text-xs text-slate-500">{blocker ? blocker : `${cellCount} cells, about ${(cellCount * 0.02).toFixed(1)} s. Nothing runs until you click Compute.`}</span>
      </div>
      {error && (
        <p role="alert" data-testid="gr-error" className="flex items-start gap-2 rounded border border-rose-500/40 bg-rose-500/10 p-2 text-sm text-rose-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {error.kind === "validation" ? `The engine refused the request: ${error.message}` : error.kind === "engine-unavailable" ? `The engine is unavailable: ${error.message}` : `The response was rejected: ${error.message}`}
        </p>
      )}

      {result && result.mode === "map" && result.grid && (
        <div className="space-y-3" data-testid="gr-result">
          {stale && <p role="status" data-testid="gr-stale" className="text-xs text-amber-200">Inputs changed since this result was computed. Compute again to refresh.</p>}
          <div className="flex flex-wrap items-end gap-3">
            <label className="block text-xs text-slate-400">
              <span className="mb-1 block">Colour by</span>
              <select className={inputClass} value={metric} onChange={e => setMetric(e.target.value as GrMetric)} data-testid="gr-metric">
                {METRICS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </label>
            <p className="text-xs text-slate-400" data-testid="gr-counts">
              {result.materialName}: {(Object.keys(result.counts) as Array<keyof typeof result.counts>).map(k => `${STATUS_LABELS[k]} ${result.counts[k]}`).join(", ")}
            </p>
          </div>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
            <div className="space-y-2">
              <GrHeatmap result={result} metric={metric} selected={selected} onSelect={setSelected} stale={stale} />
              <GrLegend result={result} metric={metric} />
            </div>
            <GrCellDetail body={selectedCell} result={result} />
          </div>
          <div className="border-t border-white/[.07] pt-3 text-xs text-slate-400" data-testid="gr-cet-status">
            <p className="font-semibold">Columnar-to-equiaxed transition</p>
            <p>{result.cet.constantsStatus.status === "unavailable" ? `CET: unavailable. ${result.cet.constantsStatus.reason ?? ""}` : "CET constants are available."}</p>
            <p className="mt-1">Morphology labels on this map are the Hunt G/R screening band (uncalibrated), not a CET prediction.</p>
            <p className="mt-1">Equation {result.cet.equation}. Verified against the source PDF: {result.cet.equationVerified ? "yes" : "no"}.</p>
          </div>
          <details className="text-xs text-slate-400">
            <summary className="cursor-pointer font-semibold text-slate-300">Limits</summary>
            <ul className="mt-1 list-disc space-y-0.5 pl-5" data-testid="gr-limits">{result.limits.map((l, i) => <li key={i}>{l}</li>)}</ul>
          </details>
        </div>
      )}
    </section>
  );
};

export default GrSolidificationMapCard;
