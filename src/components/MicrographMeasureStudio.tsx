import React, { useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, Download, Play, Ruler, Upload } from "lucide-react";
import { measureMicrograph, type MicrographMeasureRequest, type MicrographMeasureResult } from "../services/micrographMeasureService";
import {
  DECODABLE_TYPES,
  DEFAULT_SETTINGS,
  MAX_SIDE_PX,
  buildExportRecord,
  buildMeasureRequest,
  calibrationRequestKeys,
  exportCsv,
  greyFromRgba,
  greyHistogram,
  manualCounts,
  testLineGeometry,
  requestSignature,
  runBlocker,
  sha256Hex,
  unpackMask,
  unsupportedImageReason,
  type CalibrationInput,
  type GreyImage,
  type ManualCounting,
  type MeasureSettings,
  type SourceProvenance,
} from "../utils/micrographInput";
import { segmentLengthPx, type CaliperUnit } from "../utils/semAnalysis";
import { MicrographMeasureResults } from "./MicrographMeasureResults";

type LoadedImage = GreyImage & { key: string; source: SourceProvenance; dataUrl: string };
type Tool = "caliper" | "pipette" | "manual";
const CALIPER_UNITS: { value: CaliperUnit; label: string }[] = [
  { value: "nm", label: "nm" }, { value: "µm", label: "µm" }, { value: "mm", label: "mm" },
];
const input = "w-full px-2 py-1 bg-[#0c1322] border border-[#162032] rounded text-white font-mono text-xs focus:outline-none focus:border-sky-400";
const panel = "p-3 rounded-xl bg-[#090e18] border border-[#162032] space-y-2";

function intIn(value: string, lo: number, hi: number, fallback: number) {
  const n = Math.round(Number(value));
  return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : fallback;
}

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function decodeFile(file: File): Promise<{ data: Uint8ClampedArray; width: number; height: number; dataUrl: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`${file.name}: the file could not be read.`));
    reader.onload = () => {
      const dataUrl = String(reader.result);
      const img = new Image();
      const timer = setTimeout(() => reject(new Error(`${file.name}: the browser did not decode the image within 15 s.`)), 15000);
      img.onerror = () => { clearTimeout(timer); reject(new Error(`${file.name}: the browser could not decode this image.`)); };
      img.onload = () => {
        clearTimeout(timer);
        if (img.naturalWidth > MAX_SIDE_PX || img.naturalHeight > MAX_SIDE_PX) {
          reject(new Error(`${file.name}: ${img.naturalWidth} x ${img.naturalHeight} px exceeds ${MAX_SIDE_PX} px per side.`));
          return;
        }
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx) { reject(new Error("Canvas 2D is unavailable.")); return; }
        ctx.drawImage(img, 0, 0);
        resolve({ data: ctx.getImageData(0, 0, canvas.width, canvas.height).data, width: canvas.width, height: canvas.height, dataUrl });
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
  });
}

/**
 * Calibrated micrograph measurement view. The browser decodes the image, takes the user's calibration, crop and
 * thresholds, and shows what python/micrograph_measure.py returns (via POST /api/python/micrograph-measure).
 */
export const MicrographMeasureStudio: React.FC<{ onImageChange?: (image: { dataUrl: string; key: string } | null) => void }> = ({ onImageChange }) => {
  const [image, setImage] = useState<LoadedImage | null>(null);
  const [loadMessage, setLoadMessage] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool>("caliper");
  const [calibration, setCalibration] = useState<CalibrationInput>({ mode: "scale-bar", segment: null, barValue: NaN, barUnit: "µm" });
  const [pendingPoint, setPendingPoint] = useState<{ x: number; y: number } | null>(null);
  const [settings, setSettings] = useState<MeasureSettings>(DEFAULT_SETTINGS);
  const [manual, setManual] = useState<ManualCounting | null>(null);
  const [pipette, setPipette] = useState<{ x: number; y: number; grey: number } | null>(null);
  const [result, setResult] = useState<{ data: MicrographMeasureResult; signature: string; request: MicrographMeasureRequest; geometry: string } | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [showMasks, setShowMasks] = useState(true);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const signature = requestSignature(image?.key ?? null, calibration, settings, manual);
  const geometry = JSON.stringify([image?.key ?? null, settings.crop, settings.linesPerDirection]);
  const stale = result !== null && result.signature !== signature;
  const blocker = runBlocker(image, calibration, settings, manual);
  const histogram = useMemo(() => (image ? greyHistogram(image.grey) : null), [image]);
  const lines = result && result.geometry === geometry ? result.data.testLines : null;

  useEffect(() => () => abortRef.current?.abort(), []);

  const adopt = (next: LoadedImage) => {
    abortRef.current?.abort();
    setImage(next);
    setResult(null);
    setRunError(null);
    setManual(null);
    setPipette(null);
    setPendingPoint(null);
    onImageChange?.({ dataUrl: next.dataUrl, key: next.key });
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    const refusal = unsupportedImageReason(file.name, file.type);
    if (refusal) { setLoadMessage(refusal); return; }
    setLoadMessage(`Decoding ${file.name}...`);
    try {
      const [decoded, bytes] = await Promise.all([decodeFile(file), file.arrayBuffer()]);
      const fileSha256 = await sha256Hex(new Uint8Array(bytes));
      const grey = greyFromRgba(decoded.data, decoded.width, decoded.height);
      adopt({ ...grey, key: `${fileSha256}:${file.name}`, dataUrl: decoded.dataUrl,
        source: { fileName: file.name, fileSha256, kind: "uploaded-file", convertedFromColour: grey.wasColour } });
      setCalibration({ mode: "scale-bar", segment: null, barValue: NaN, barUnit: "µm" });
      setSettings(DEFAULT_SETTINGS);
      setLoadMessage(grey.wasColour ? "Colour image: converted to grey with BT.601 luma." : null);
    } catch (err) {
      const reason = err instanceof Error ? err.message : "The image could not be loaded.";
      setLoadMessage(image ? `${reason} The previous image stays loaded.` : reason);
    }
  };

  const run = async () => {
    if (!image || blocker) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const request = buildMeasureRequest(image, calibration, settings, manual);
    const runSignature = signature;
    const runGeometry = geometry;
    setRunning(true);
    setRunError(null);
    try {
      const data = await measureMicrograph(request, controller.signal);
      if (!controller.signal.aborted) setResult({ data, signature: runSignature, request, geometry: runGeometry });
    } catch (err) {
      if (!controller.signal.aborted) setRunError(err instanceof Error ? err.message : "Measurement failed.");
    } finally {
      if (abortRef.current === controller) setRunning(false);
    }
  };

  // Draw the image with the overlays returned by the authority (masks, test lines, intersections).
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !image) return;
    canvas.width = image.width;
    canvas.height = image.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const rgba = ctx.createImageData(image.width, image.height);
    for (let i = 0, p = 0; i < image.grey.length; i++, p += 4) {
      rgba.data[p] = rgba.data[p + 1] = rgba.data[p + 2] = image.grey[i];
      rgba.data[p + 3] = 255;
    }
    const data = result && !stale ? result.data : null;
    if (data && showMasks) {
      const { x0, y0, x1, y1 } = data.record.roi;
      const w = x1 - x0, h = y1 - y0;
      for (const [cls, colour] of [[data.classes.dark, [239, 68, 68]], [data.classes.bright, [34, 211, 238]]] as const) {
        if (!cls?.maskPackedBase64) continue;
        const mask = unpackMask(cls.maskPackedBase64, w, h);
        for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
          if (!mask[y * w + x]) continue;
          const p = ((y + y0) * image.width + (x + x0)) * 4;
          rgba.data[p] = (rgba.data[p] + colour[0]) >> 1;
          rgba.data[p + 1] = (rgba.data[p + 1] + colour[1]) >> 1;
          rgba.data[p + 2] = (rgba.data[p + 2] + colour[2]) >> 1;
        }
      }
    }
    ctx.putImageData(rgba, 0, 0);
    const { top, bottom, left, right } = settings.crop;
    ctx.fillStyle = "rgba(15, 23, 42, 0.55)";
    ctx.fillRect(0, 0, image.width, top);
    ctx.fillRect(0, image.height - bottom, image.width, bottom);
    ctx.fillRect(0, 0, left, image.height);
    ctx.fillRect(image.width - right, 0, right, image.height);
    const lw = Math.max(1, image.width / 500);
    if (lines) {
      ctx.strokeStyle = "rgba(250, 204, 21, 0.8)";
      ctx.lineWidth = lw;
      for (const ln of lines) {
        const [ox, oy] = ln.roiOffset;
        ctx.beginPath();
        if (ln.orientation === "h") { ctx.moveTo(ox, oy + ln.position + 0.5); ctx.lineTo(ox + ln.lengthPx, oy + ln.position + 0.5); }
        else { ctx.moveTo(ox + ln.position + 0.5, oy); ctx.lineTo(ox + ln.position + 0.5, oy + ln.lengthPx); }
        ctx.stroke();
      }
    }
    const dot = (x: number, y: number, colour: string) => {
      ctx.fillStyle = colour;
      ctx.beginPath();
      ctx.arc(x + 0.5, y + 0.5, 2.5 * lw, 0, Math.PI * 2);
      ctx.fill();
    };
    if (data?.grainSize?.intersections) {
      const [ox, oy] = data.testLines[0]?.roiOffset ?? [0, 0];
      for (const pt of data.grainSize.intersections) dot(ox + pt.x, oy + pt.y, pt.weight < 1 ? "#f0abfc" : "#d946ef");
    }
    if (manual) for (const c of manual.clicks) dot(c.x, c.y, c.weight < 1 ? "#86efac" : "#22c55e");
    const seg = calibration.mode === "scale-bar" ? calibration.segment : null;
    if (seg || pendingPoint) {
      ctx.strokeStyle = "#fb923c";
      ctx.lineWidth = 2 * lw;
      if (seg) { ctx.beginPath(); ctx.moveTo(seg.x1, seg.y1); ctx.lineTo(seg.x2, seg.y2); ctx.stroke(); }
      if (pendingPoint) dot(pendingPoint.x, pendingPoint.y, "#fb923c");
    }
  }, [image, result, stale, showMasks, settings.crop, lines, manual, calibration, pendingPoint]);

  const onCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!image) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.min(image.width - 1, Math.max(0, Math.floor(((e.clientX - rect.left) / rect.width) * image.width)));
    const y = Math.min(image.height - 1, Math.max(0, Math.floor(((e.clientY - rect.top) / rect.height) * image.height)));
    if (tool === "pipette") { setPipette({ x, y, grey: image.grey[y * image.width + x] }); return; }
    if (tool === "caliper") {
      if (calibration.mode !== "scale-bar") return;
      if (!pendingPoint) { setPendingPoint({ x, y }); return; }
      setCalibration({ ...calibration, segment: { x1: pendingPoint.x, y1: pendingPoint.y, x2: x, y2: y } });
      setPendingPoint(null);
      return;
    }
    if (!lines || !manual) return;
    let best: { line: number; x: number; y: number; d: number } | null = null;
    for (const ln of lines) {
      const [ox, oy] = ln.roiOffset;
      const along = ln.orientation === "h" ? x - ox : y - oy;
      if (along < 0 || along >= ln.lengthPx) continue;
      const d = ln.orientation === "h" ? Math.abs(y - (oy + ln.position)) : Math.abs(x - (ox + ln.position));
      if (!best || d < best.d) best = ln.orientation === "h" ? { line: ln.index, x, y: oy + ln.position, d } : { line: ln.index, x: ox + ln.position, y, d };
    }
    if (best && best.d <= Math.max(4, image.width / 150)) {
      setManual({ geometry: manual.geometry, clicks: [...manual.clicks, { line: best.line, x: best.x, y: best.y, weight: e.shiftKey ? 0.5 : 1 }] });
    }
  };

  const exportRecord = (kind: "json" | "csv") => {
    if (!result || !image || stale) return;
    const stamp = new Date().toISOString();
    if (kind === "json") {
      download("micrograph-measurement.json", JSON.stringify(buildExportRecord(result.data, result.request, image.source, stamp), null, 2), "application/json");
    } else {
      download("micrograph-measurement.csv", exportCsv(result.data, image.source), "text/csv");
    }
  };

  // Any change of the test-line geometry discards manual clicks: they were counted on the old lines (review S1).
  const setCrop = (key: keyof MeasureSettings["crop"], value: string) => {
    const next = { ...settings, crop: { ...settings.crop, [key]: intIn(value, 0, MAX_SIDE_PX - 1, 0) } };
    setSettings(next);
    if (manual) setManual({ clicks: [], geometry: testLineGeometry(next) });
  };
  const calKeys = calibrationRequestKeys(calibration);
  const maxBin = histogram ? Math.max(...histogram) : 1;
  const counts = manual ? manualCounts(manual.clicks, 2 * settings.linesPerDirection) : null;

  return (
    <div className="space-y-4">
      <div className={`${panel} flex flex-wrap items-center gap-2`}>
        <input ref={fileRef} type="file" aria-label="Load micrograph image" className="hidden"
          accept={[...DECODABLE_TYPES, "image/tiff", ".tif", ".tiff"].join(",")}
          onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = ""; }} />
        <button type="button" onClick={() => fileRef.current?.click()}
          className="px-3 py-1.5 rounded border border-[#1e2d46] bg-[#0c1322] text-xs font-mono text-slate-200 flex items-center gap-2">
          <Upload className="w-3.5 h-3.5" /> Load image (PNG, JPEG, BMP, GIF, WebP)
        </button>
        {image && <span className="text-[11px] font-mono text-slate-400">{image.source.fileName} · {image.width} x {image.height} px</span>}
        {loadMessage && <p role="alert" className="w-full text-[11px] text-amber-200">{loadMessage}</p>}
        {!image && (
          <p className="w-full text-[11px] text-slate-400">
            Steps: load a micrograph, calibrate the scale (caliper over the scale bar, or a stated pixel size), exclude the
            data bar, choose and name grey-level classes or grain counting, then measure. No built-in images are provided.
          </p>
        )}
      </div>

      {image && (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
          <div className="xl:col-span-7 space-y-2">
            <div className="flex flex-wrap gap-1 text-xs font-mono" role="group" aria-label="Image tool">
              {([["caliper", "Scale-bar caliper", Ruler], ["pipette", "Pipette", Crosshair], ["manual", "Manual intersections", Crosshair]] as const).map(([id, label, Icon]) => (
                <button key={id} type="button" aria-pressed={tool === id} onClick={() => { setTool(id); setPendingPoint(null); }}
                  className={`px-2 py-1 rounded border flex items-center gap-1 ${tool === id ? "border-sky-400 text-sky-300" : "border-[#1e2d46] text-slate-400"}`}>
                  <Icon className="w-3 h-3" />{label}
                </button>
              ))}
              <label className="flex items-center gap-1 text-slate-400 ml-2">
                <input type="checkbox" checked={showMasks} onChange={(e) => setShowMasks(e.target.checked)} /> Show result masks
              </label>
            </div>
            <canvas ref={canvasRef} onClick={onCanvasClick} className="w-full max-w-[720px] h-auto border border-[#162032] rounded cursor-crosshair"
              style={{ imageRendering: "pixelated" }} aria-label="Micrograph with measurement overlays" />
            <div className="text-[11px] font-mono text-slate-400">
              {tool === "caliper" && (pendingPoint ? "Click the other end of the scale bar." : "Click both ends of the image scale bar.")}
              {tool === "pipette" && (pipette ? `Pixel (${pipette.x}, ${pipette.y}): grey ${pipette.grey}` : "Click to read a grey level.")}
              {tool === "manual" && (manual
                ? lines ? "Click each boundary crossing on a yellow test line; shift-click scores 1/2 (line end touching a boundary)."
                  : "Run once to get the test lines for the current crop and line count."
                : "Enable manual counting in the grain panel.")}
            </div>
            {histogram && (
              <figure aria-label="Grey-level histogram of the loaded image">
                <svg viewBox="0 0 256 60" className="w-full h-16 bg-[#050810] rounded" preserveAspectRatio="none">
                  {histogram.map((n, g) => n > 0 && <rect key={g} x={g} y={60 - (58 * n) / maxBin} width={1} height={(58 * n) / maxBin} fill="#64748b" />)}
                  {settings.dark.enabled && <line x1={settings.dark.maxGrey + 0.5} x2={settings.dark.maxGrey + 0.5} y1={0} y2={60} stroke="#ef4444" />}
                  {settings.bright.enabled && <line x1={settings.bright.minGrey + 0.5} x2={settings.bright.minGrey + 0.5} y1={0} y2={60} stroke="#22d3ee" />}
                  {settings.grains.enabled && <line x1={settings.grains.boundaryMaxGrey + 0.5} x2={settings.grains.boundaryMaxGrey + 0.5} y1={0} y2={60} stroke="#d946ef" />}
                </svg>
                <figcaption className="text-[10px] text-slate-500">Grey-level histogram of the whole image (input display, 0 left to 255 right) with the chosen thresholds.</figcaption>
              </figure>
            )}
          </div>

          <div className="xl:col-span-5 space-y-3">
            <section className={panel} aria-labelledby="mm-cal">
              <h3 id="mm-cal" className="text-xs font-mono font-bold text-slate-200">1. Calibration (required)</h3>
              <label className="block text-[11px] text-slate-400">Calibration source
                <select className={input} value={calibration.mode} onChange={(e) => setCalibration(e.target.value === "pixel-size"
                  ? { mode: "pixel-size", umPerPx: NaN, note: "" } : { mode: "scale-bar", segment: null, barValue: NaN, barUnit: "µm" })}>
                  <option value="scale-bar">Scale bar on the image (caliper)</option>
                  <option value="pixel-size">Stated pixel size (instrument record)</option>
                </select>
              </label>
              {calibration.mode === "scale-bar" ? (
                <div className="grid grid-cols-2 gap-2">
                  <label className="text-[11px] text-slate-400">Printed bar length
                    <input className={input} type="number" min={0} step="any" value={Number.isFinite(calibration.barValue) ? calibration.barValue : ""}
                      onChange={(e) => setCalibration({ ...calibration, barValue: e.target.value === "" ? NaN : Number(e.target.value) })} />
                  </label>
                  <label className="text-[11px] text-slate-400">Bar length unit
                    <select className={input} value={calibration.barUnit} onChange={(e) => setCalibration({ ...calibration, barUnit: e.target.value as CaliperUnit })}>
                      {CALIPER_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                    </select>
                  </label>
                  <div className="col-span-2 text-[11px] font-mono text-slate-400">
                    Caliper: {calibration.segment ? `${segmentLengthPx(calibration.segment).toFixed(1)} px` : "not drawn"}
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <label className="text-[11px] text-slate-400">Pixel size (µm/px)
                    <input className={input} type="number" min={0} step="any" value={Number.isFinite(calibration.umPerPx) ? calibration.umPerPx : ""}
                      onChange={(e) => setCalibration({ ...calibration, umPerPx: e.target.value === "" ? NaN : Number(e.target.value) })} />
                  </label>
                  <label className="text-[11px] text-slate-400">Source of the pixel size
                    <input className={input} type="text" maxLength={200} value={calibration.note}
                      onChange={(e) => setCalibration({ ...calibration, note: e.target.value })} />
                  </label>
                </div>
              )}
              <p className="text-[11px] text-slate-500">{"reason" in calKeys ? calKeys.reason : "Calibration set; the authority computes µm/px and records the source."}</p>
            </section>

            <section className={panel} aria-labelledby="mm-roi">
              <h3 id="mm-roi" className="text-xs font-mono font-bold text-slate-200">2. Region of interest (exclude the data bar)</h3>
              <div className="grid grid-cols-4 gap-2">
                {(["top", "bottom", "left", "right"] as const).map((k) => (
                  <label key={k} className="text-[11px] text-slate-400">Exclude {k} (px)
                    <input className={input} type="number" min={0} step={1} value={settings.crop[k]} onChange={(e) => setCrop(k, e.target.value)} />
                  </label>
                ))}
              </div>
            </section>

            <section className={panel} aria-labelledby="mm-classes">
              <h3 id="mm-classes" className="text-xs font-mono font-bold text-slate-200">3. Grey-level classes (you name them)</h3>
              {(["dark", "bright"] as const).map((k) => {
                const cls = settings[k];
                const value = k === "dark" ? settings.dark.maxGrey : settings.bright.minGrey;
                return (
                  <div key={k} className="grid grid-cols-6 gap-2 items-end">
                    <label className="col-span-2 text-[11px] text-slate-400 flex items-center gap-1">
                      <input type="checkbox" checked={cls.enabled} onChange={(e) => setSettings({ ...settings, [k]: { ...cls, enabled: e.target.checked } })} />
                      Measure {k} class
                    </label>
                    <label className="col-span-2 text-[11px] text-slate-400">{k === "dark" ? "Dark" : "Bright"} class name
                      <input className={input} type="text" maxLength={60} value={cls.label} onChange={(e) => setSettings({ ...settings, [k]: { ...cls, label: e.target.value } })} />
                    </label>
                    <label className="col-span-2 text-[11px] text-slate-400">{k === "dark" ? "grey ≤" : "grey ≥"} threshold
                      <input className={input} type="number" min={k === "dark" ? 0 : 1} max={k === "dark" ? 254 : 255} step={1} value={value}
                        onChange={(e) => setSettings(k === "dark"
                          ? { ...settings, dark: { ...settings.dark, maxGrey: intIn(e.target.value, 0, 254, settings.dark.maxGrey) } }
                          : { ...settings, bright: { ...settings.bright, minGrey: intIn(e.target.value, 1, 255, settings.bright.minGrey) } })} />
                    </label>
                  </div>
                );
              })}
              <div className="grid grid-cols-3 gap-2">
                <label className="text-[11px] text-slate-400">CI tiles per side
                  <input className={input} type="number" min={2} max={10} step={1} value={settings.tiles} onChange={(e) => setSettings({ ...settings, tiles: intIn(e.target.value, 2, 10, 4) })} />
                </label>
                <label className="text-[11px] text-slate-400">Sensitivity ± grey
                  <input className={input} type="number" min={1} max={64} step={1} value={settings.sensitivityDeltaGrey} onChange={(e) => setSettings({ ...settings, sensitivityDeltaGrey: intIn(e.target.value, 1, 64, 10) })} />
                </label>
                <label className="text-[11px] text-slate-400">Smallest particle (px)
                  <input className={input} type="number" min={1} step={1} value={settings.minAreaPx} onChange={(e) => setSettings({ ...settings, minAreaPx: intIn(e.target.value, 1, 100000, 4) })} />
                </label>
              </div>
            </section>

            <section className={panel} aria-labelledby="mm-grains">
              <h3 id="mm-grains" className="text-xs font-mono font-bold text-slate-200">4. Grain size, ASTM E112 intercept</h3>
              <div className="grid grid-cols-2 gap-2 items-end">
                <label className="text-[11px] text-slate-400 flex items-center gap-1">
                  <input type="checkbox" checked={settings.grains.enabled} onChange={(e) => setSettings({ ...settings, grains: { ...settings.grains, enabled: e.target.checked } })} />
                  Automatic count (boundaries darker than grains)
                </label>
                <label className="text-[11px] text-slate-400">Boundary grey ≤
                  <input className={input} type="number" min={0} max={254} step={1} value={settings.grains.boundaryMaxGrey}
                    onChange={(e) => setSettings({ ...settings, grains: { ...settings.grains, boundaryMaxGrey: intIn(e.target.value, 0, 254, 90) } })} />
                </label>
                <label className="text-[11px] text-slate-400">Test lines per direction
                  <input className={input} type="number" min={1} max={50} step={1} value={settings.linesPerDirection}
                    onChange={(e) => {
                      const next = { ...settings, linesPerDirection: intIn(e.target.value, 1, 50, 8) };
                      setSettings(next);
                      if (manual) setManual({ clicks: [], geometry: testLineGeometry(next) });
                    }} />
                </label>
                <label className="text-[11px] text-slate-400 flex items-center gap-1">
                  <input type="checkbox" checked={manual !== null} onChange={(e) => { setManual(e.target.checked ? { clicks: [], geometry: testLineGeometry(settings) } : null); if (e.target.checked) setTool("manual"); }} />
                  Manual counting (any image type)
                </label>
              </div>
              {manual && (
                <div className="text-[11px] text-slate-400 space-y-1">
                  <div>Clicks: {manual.clicks.length}; per line: {counts?.join(" / ")}</div>
                  <div className="flex gap-2">
                    <button type="button" className="px-2 py-0.5 rounded border border-[#1e2d46]" onClick={() => setManual({ ...manual, clicks: manual.clicks.slice(0, -1) })}>Undo last click</button>
                    <button type="button" className="px-2 py-0.5 rounded border border-[#1e2d46]" onClick={() => setManual({ clicks: [], geometry: testLineGeometry(settings) })}>Clear clicks</button>
                  </div>
                </div>
              )}
            </section>

            <div className="space-y-1">
              <button type="button" onClick={() => void run()} disabled={blocker !== null || running}
                className="w-full py-2 rounded bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 disabled:opacity-50">
                <Play className="w-3.5 h-3.5" /> {running ? "Measuring..." : "Measure (Python authority)"}
              </button>
              {blocker && <p className="text-[11px] text-slate-400">{blocker}</p>}
              {runError && <p role="alert" className="text-[11px] text-rose-300">{runError}</p>}
            </div>
          </div>
        </div>
      )}

      {result && (
        <section className={panel} aria-labelledby="mm-results">
          <div className="flex items-center justify-between">
            <h3 id="mm-results" className="text-xs font-mono font-bold text-slate-200">Measurement result</h3>
            <div className="flex gap-2">
              {(["json", "csv"] as const).map((k) => (
                <button key={k} type="button" disabled={stale} onClick={() => exportRecord(k)}
                  className="px-2 py-1 rounded border border-[#1e2d46] text-[11px] font-mono text-slate-300 flex items-center gap-1 disabled:opacity-40">
                  <Download className="w-3 h-3" /> Export {k.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <MicrographMeasureResults result={result.data} stale={stale} />
        </section>
      )}
    </div>
  );
};
