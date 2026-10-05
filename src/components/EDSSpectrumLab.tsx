import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Crosshair,
  Download,
  FileSpreadsheet,
  Share2,
  Upload,
} from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { parseRawEDSFile, type ParsedEDSSpectrum } from "../utils/edsParser";
import {
  archiveEDSSource,
  restoreLatestEDSSource,
  sha256Bytes,
  type EDSSourceRecord,
} from "../utils/edsSourceArchive";
import { FWHM_LIMITS_EV, NET_AREA_LABEL, findEdsPeaks, type EdsPeakIdResult } from "../utils/edsPeakId";
import {
  importVendorQuant,
  type VendorAnalysisType,
  type VendorQuantProvenance,
  type VendorQuantResult,
} from "../utils/edsVendorQuant";
import { XRAY_EMISSION_LINES_SOURCE } from "../data/xrayEmissionLines";
import { useMaterialSpecimenStore } from "../store/useMaterialSpecimenStore";
import { dispatchNavigateToTab } from "../utils/materialDataPipeline";
import { WebGLSpectrometerCanvas } from "./WebGLSpectrometerCanvas";

/** What accompanies a composition sent to the Alloy Builder. Only vendor-reported tables are ever sent. */
export interface EDSCompositionTransfer {
  label: string;
  provenance: VendorQuantProvenance;
}

type UploadedSource = Pick<EDSSourceRecord, "fileName" | "mediaType" | "bytes"> & {
  sha256?: string;
  persisted: boolean;
};
type UploadedSpectrum = ParsedEDSSpectrum & { source: UploadedSource | null };

const DEFAULT_FWHM_EV = 130;

/** Marker text: an overlap peak names its first two candidates, so the chart never shows one of them as the answer. */
function markerLabel(peak: { candidates: { label: string }[]; overlap: boolean; energyKeV: number }): string {
  if (peak.candidates.length === 0) return peak.energyKeV.toFixed(2);
  return peak.overlap && peak.candidates.length > 1
    ? `${peak.candidates[0].label} / ${peak.candidates[1].label}`
    : peak.candidates[0].label;
}

/** Identity of the vendor import input (file and metadata); a parsed result is valid only for the same signature. */
export function vendorSignature(
  file: { fileName: string; bytes: ArrayBuffer; loadedAt: Date } | null,
  instrument: string, software: string, analysisType: string,
): string {
  return JSON.stringify([file ? [file.fileName, file.bytes.byteLength, file.loadedAt.getTime()] : null,
    instrument, software, analysisType]);
}

function fmt(value: number, digits: number): string {
  return Number.isFinite(value) ? value.toFixed(digits) : "-";
}

export const EDSSpectrumLab: React.FC<{
  onSendToAlloyBuilder?: (composition: Record<string, number>, transfer?: EDSCompositionTransfer) => void;
}> = ({ onSendToAlloyBuilder }) => {
  const [uploadedSpectrum, setUploadedSpectrum] = useState<UploadedSpectrum | null>(null);
  const [sourceRestoreState, setSourceRestoreState] = useState<"checking" | "ready" | "empty" | "failed">("checking");
  const [importError, setImportError] = useState<string | null>(null);
  const [fwhmEv, setFwhmEv] = useState<number>(DEFAULT_FWHM_EV);
  const [showBackground, setShowBackground] = useState<boolean>(true);
  const [showMarkers, setShowMarkers] = useState<boolean>(true);
  const [useGpuView, setUseGpuView] = useState<boolean>(false);
  const [showNetAreas, setShowNetAreas] = useState<boolean>(false);
  const spectrumRequestGenerationRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const vendorInputRef = useRef<HTMLInputElement>(null);

  // Vendor quantification import
  const [vendorFile, setVendorFile] = useState<{ fileName: string; bytes: ArrayBuffer; loadedAt: Date } | null>(null);
  const [vendorInstrument, setVendorInstrument] = useState<string>("");
  const [vendorSoftware, setVendorSoftware] = useState<string>("");
  const [vendorAnalysisType, setVendorAnalysisType] = useState<VendorAnalysisType | "">("");
  const [vendorResult, setVendorResult] = useState<VendorQuantResult | null>(null);

  useEffect(() => {
    let active = true;
    const generation = spectrumRequestGenerationRef.current;
    void restoreLatestEDSSource().then(record => {
      if (!active || generation !== spectrumRequestGenerationRef.current) return;
      if (!record) {
        setSourceRestoreState("empty");
        return;
      }
      const binary = record.fileName.toLowerCase().endsWith(".spc");
      const content = binary ? record.bytes : new TextDecoder().decode(record.bytes);
      const parsed = parseRawEDSFile(content, record.fileName);
      setUploadedSpectrum({ ...parsed, source: { ...record, persisted: true } });
      setSourceRestoreState("ready");
    }).catch(() => {
      if (active && generation === spectrumRequestGenerationRef.current) setSourceRestoreState("failed");
    });
    return () => { active = false; };
  }, []);

  // The parsed vendor table belongs to exactly one (file, metadata) input. Any change clears it at once, so a
  // stale accepted result can neither be shown beside a new file name nor sent while the new input is parsed.
  const vendorInputSignature = vendorSignature(vendorFile, vendorInstrument, vendorSoftware, vendorAnalysisType);
  const [vendorResultSignature, setVendorResultSignature] = useState<string | null>(null);
  useEffect(() => {
    setVendorResult(null);
    setVendorResultSignature(null);
    if (!vendorFile) return;
    let active = true;
    void importVendorQuant(
      vendorFile.bytes,
      vendorFile.fileName,
      { instrument: vendorInstrument, software: vendorSoftware, analysisType: vendorAnalysisType },
      vendorFile.loadedAt,
    ).then(result => {
      if (!active) return;
      setVendorResult(result);
      setVendorResultSignature(vendorSignature(vendorFile, vendorInstrument, vendorSoftware, vendorAnalysisType));
    }).catch(() => { if (active) setVendorResult(null); });
    return () => { active = false; };
  }, [vendorFile, vendorInstrument, vendorSoftware, vendorAnalysisType]);
  const vendorCurrent = vendorResult !== null && vendorResultSignature === vendorInputSignature;

  const fwhmValid = Number.isFinite(fwhmEv) && fwhmEv >= FWHM_LIMITS_EV.min && fwhmEv <= FWHM_LIMITS_EV.max;
  const peakAnalysis = useMemo<{ result: EdsPeakIdResult | null; error: string | null }>(() => {
    if (!uploadedSpectrum) return { result: null, error: null };
    try {
      const channels = uploadedSpectrum.points.map(point => ({ energyKeV: point.energyKeV, counts: point.counts }));
      return { result: findEdsPeaks(channels, { fwhmEv: fwhmValid ? fwhmEv : DEFAULT_FWHM_EV }), error: null };
    } catch (err: unknown) {
      return { result: null, error: err instanceof Error ? err.message : String(err) };
    }
  }, [uploadedSpectrum, fwhmEv, fwhmValid]);
  const peakResult = peakAnalysis.result;

  const chartData = useMemo(() => {
    if (!uploadedSpectrum) return [];
    return uploadedSpectrum.points.map((point, index) => ({
      energyKeV: point.energyKeV,
      counts: point.counts,
      background: peakResult ? Math.round(peakResult.background[index] * 100) / 100 : undefined,
    }));
  }, [uploadedSpectrum, peakResult]);

  const gpuData = useMemo(
    () => chartData.map(point => ({ x: point.energyKeV, y: point.counts })),
    [chartData],
  );
  const gpuBackground = useMemo(
    () => (peakResult
      ? [{ name: "SNIP background", color: "#64748b", points: chartData.map(point => ({ x: point.energyKeV, y: point.background ?? 0 })) }]
      : []),
    [chartData, peakResult],
  );
  const gpuAnnotations = useMemo(
    () => (peakResult?.peaks ?? []).map(peak => ({
      x: peak.energyKeV,
      label: markerLabel(peak),
      intensity: peak.netCounts,
    })),
    [peakResult],
  );

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const generation = ++spectrumRequestGenerationRef.current;
    try {
      const bytes = await file.arrayBuffer();
      if (generation !== spectrumRequestGenerationRef.current) return;
      const content = file.name.toLowerCase().endsWith(".spc")
        ? bytes
        : new TextDecoder().decode(bytes);
      const parsed = parseRawEDSFile(content, file.name);
      let source: UploadedSource = {
        fileName: file.name,
        mediaType: file.type || "application/octet-stream",
        bytes: bytes.slice(0),
        persisted: false,
      };
      try {
        const archived = await archiveEDSSource(
          file.name,
          file.type,
          bytes,
          undefined,
          () => generation === spectrumRequestGenerationRef.current,
        );
        if (generation !== spectrumRequestGenerationRef.current) return;
        source = { ...archived, persisted: true };
        setSourceRestoreState("ready");
      } catch {
        if (generation !== spectrumRequestGenerationRef.current) return;
        source.sha256 = await sha256Bytes(bytes).catch(() => undefined);
        if (generation !== spectrumRequestGenerationRef.current) return;
        setSourceRestoreState("failed");
      }
      setImportError(null);
      setUploadedSpectrum({ ...parsed, source });
    } catch (err: unknown) {
      if (generation !== spectrumRequestGenerationRef.current) return;
      setImportError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleVendorUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const bytes = await file.arrayBuffer();
    setVendorFile({ fileName: file.name, bytes, loadedAt: new Date() });
  };

  const downloadOriginalSource = () => {
    const source = uploadedSpectrum?.source;
    if (!source) return;
    const url = URL.createObjectURL(new Blob([source.bytes], { type: source.mediaType }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = source.fileName;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const exportCsvReport = () => {
    if (!uploadedSpectrum) return;
    const rows = [
      "Imported EDS spectrum; parser output only; no quantitative analysis has been performed.",
      `Source filename:,${uploadedSpectrum.fileName}`,
      `Source SHA-256:,${uploadedSpectrum.source?.sha256 ?? "not computed"}`,
      `Source retained in browser:,${uploadedSpectrum.source?.persisted ? "yes" : "session only"}`,
      `Energy calibration declaration:,${uploadedSpectrum.energyCalibrationSource ?? "unavailable"}`,
      "Energy (keV),Parsed counts",
      ...uploadedSpectrum.points.map((point) => `${point.energyKeV},${point.counts}`),
    ];
    const blob = new Blob([rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `EDS_parsed_${uploadedSpectrum.fileName.replace(/[^a-zA-Z0-9._-]/g, "_")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const sendVendorComposition = () => {
    if (!vendorCurrent || !vendorResult?.accepted || !vendorResult.provenance || !vendorResult.transferLabel) return;
    const transfer: EDSCompositionTransfer = { label: vendorResult.transferLabel, provenance: vendorResult.provenance };
    if (onSendToAlloyBuilder) {
      onSendToAlloyBuilder(vendorResult.composition, transfer);
      return;
    }
    useMaterialSpecimenStore.getState().updateComposition(
      vendorResult.composition,
      `${vendorResult.provenance.fileName} (vendor EDS, ${vendorResult.provenance.analysisType})`,
      undefined,
      transfer.label,
    );
    dispatchNavigateToTab("alloy-builder");
  };

  const peaks = peakResult?.peaks ?? [];
  const statusText = uploadedSpectrum
    ? `Imported ${uploadedSpectrum.fileName}. Energy axis declaration: ${uploadedSpectrum.energyCalibrationSource ?? "unknown"}. Source ${uploadedSpectrum.source?.persisted ? "retained in this browser" : "kept for this session only"}${uploadedSpectrum.source?.sha256 ? `; SHA-256 ${uploadedSpectrum.source.sha256}` : ""}.`
    : sourceRestoreState === "checking"
      ? "Checking the browser's local EDS source archive..."
      : sourceRestoreState === "failed"
        ? "The latest local EDS source could not be restored or verified."
        : "No spectrum imported.";

  return (
    <div id="eds-spectrum-lab-root" className="space-y-6 text-slate-100 font-sans">
      {/* Header */}
      <div className="bg-slate-900/90 border border-cyan-500/30 rounded-2xl p-5 shadow-2xl backdrop-blur-md">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-xl text-white">
              <Crosshair className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight text-white">EDS Spectrum Viewer</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Imported spectra only. Peak candidates are listed from a cited line table; nothing here is quantified.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              id="eds-upload-spectrum-btn"
              onClick={() => fileInputRef.current?.click()}
              className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-medium flex items-center gap-2 transition-all cursor-pointer"
              title="Import EMSA/MAS or delimited spectra with a source-declared eV/keV energy axis"
            >
              <Upload className="w-4 h-4 text-cyan-400" />
              <span>Import Calibrated EDS (.msa / .emsa / .csv)</span>
            </button>
            <input
              aria-label="Import calibrated EDS spectrum file"
              ref={fileInputRef}
              type="file"
              accept=".csv,.txt,.dat,.emsa,.msa"
              onChange={handleFileUpload}
              className="hidden"
            />
            {uploadedSpectrum && (
              <>
                <button
                  id="eds-export-csv-btn"
                  onClick={exportCsvReport}
                  className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-medium flex items-center gap-2 transition-all cursor-pointer"
                >
                  <Download className="w-4 h-4 text-emerald-400" />
                  <span>Export Raw Spectrum CSV</span>
                </button>
                <button
                  id="eds-download-original-btn"
                  onClick={downloadOriginalSource}
                  disabled={!uploadedSpectrum.source}
                  title={uploadedSpectrum.source ? "Download the byte-identical imported source file" : "The source bytes are unavailable"}
                  className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 border border-slate-700 rounded-xl text-xs font-medium flex items-center gap-2 transition-all"
                >
                  <Download className="w-4 h-4 text-cyan-400" />
                  <span>Download Original</span>
                </button>
              </>
            )}
          </div>
        </div>
        <div role="status" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100 break-words">
          {statusText}
        </div>
        {importError && (
          <div role="alert" className="mt-3 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-100 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>Error importing EDS file: {importError}</span>
          </div>
        )}
      </div>

      {!uploadedSpectrum && (
        <div id="eds-empty-state" className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 text-sm text-slate-300 space-y-2">
          <h3 className="text-base font-semibold text-white">No spectrum imported</h3>
          <p>
            Import a spectrum exported from your EDS software: a calibrated EMSA/MAS file (.emsa, .msa) or a
            two-column delimited file (.csv, .txt, .dat) whose header declares the energy unit (eV or keV).
            Files without a declared energy calibration are rejected rather than guessed.
          </p>
          <p>
            Once imported, the spectrum is plotted with a SNIP background, maxima that stand out from that
            background are marked, and every tabulated X-ray line near each maximum is listed, with overlaps flagged.
            No built-in or simulated spectra are provided.
          </p>
        </div>
      )}

      {uploadedSpectrum && (
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-slate-300">
            <span><span className="text-slate-500">File:</span> {uploadedSpectrum.fileName}</span>
            <span><span className="text-slate-500">Channels:</span> {uploadedSpectrum.points.length}</span>
            {uploadedSpectrum.beamEnergyKv !== undefined && <span><span className="text-slate-500">Beam:</span> {uploadedSpectrum.beamEnergyKv} kV</span>}
            {uploadedSpectrum.liveTimeSec !== undefined && <span><span className="text-slate-500">Live time:</span> {uploadedSpectrum.liveTimeSec} s</span>}
            {uploadedSpectrum.deadTimePct !== undefined && <span><span className="text-slate-500">Dead time:</span> {fmt(uploadedSpectrum.deadTimePct, 1)} %</span>}
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-300">
            <label className="flex items-center gap-2">
              <span>Detector FWHM (eV)</span>
              <input
                type="number"
                min={FWHM_LIMITS_EV.min}
                max={FWHM_LIMITS_EV.max}
                step={1}
                value={Number.isFinite(fwhmEv) ? fwhmEv : ""}
                onChange={(e) => setFwhmEv(e.target.value === "" ? Number.NaN : Number(e.target.value))}
                className="w-20 bg-slate-950 border border-slate-700 rounded-lg px-2 py-1 text-slate-100"
              />
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={showBackground} onChange={(e) => setShowBackground(e.target.checked)} />
              <span>SNIP background</span>
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={showMarkers} onChange={(e) => setShowMarkers(e.target.checked)} />
              <span>Peak markers</span>
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={useGpuView} onChange={(e) => setUseGpuView(e.target.checked)} />
              <span>GPU view (pan / zoom)</span>
            </label>
          </div>
          {!fwhmValid && (
            <p role="alert" className="text-xs text-amber-200">
              Enter an FWHM between {FWHM_LIMITS_EV.min} and {FWHM_LIMITS_EV.max} eV; {DEFAULT_FWHM_EV} eV is used until then.
            </p>
          )}
          {peakResult && (
            <p className="text-xs text-slate-400">
              Detector FWHM is one constant over the whole spectrum (default {DEFAULT_FWHM_EV} eV is a typical Mn K-alpha figure, not a measurement of this detector).
              SNIP half-window {peakResult.parameters.snipIterations} channels ({fmt(peakResult.parameters.snipIterations * peakResult.parameters.channelWidthEv, 0)} eV);
              a maximum must exceed {peakResult.parameters.minSignificance} x sqrt(background) above the background and above its surroundings.
            </p>
          )}
          {peakAnalysis.error && (
            <p role="alert" className="text-xs text-rose-200">Peak search unavailable: {peakAnalysis.error}</p>
          )}

          {useGpuView ? (
            <WebGLSpectrometerCanvas
              data={gpuData}
              deconvolutionPeaks={showBackground ? gpuBackground : []}
              annotations={showMarkers ? gpuAnnotations : []}
              xLabel="X-Ray Energy"
              yLabel="Counts"
              xUnit="keV"
              yUnit="counts"
              height={320}
              lineColor={[0.02, 0.71, 0.83, 1.0]}
              fillColor={[0.02, 0.71, 0.83, 0.28]}
            />
          ) : (
            <div className="h-72 w-full" role="img" aria-label="Imported EDS spectrum: counts against energy in keV, with SNIP background and detected maxima marked">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 18, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis
                    dataKey="energyKeV"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    stroke="#64748b"
                    fontSize={10}
                    unit=" keV"
                    tickCount={10}
                    tickFormatter={(v: number) => v.toFixed(1)}
                  />
                  <YAxis stroke="#64748b" fontSize={10} unit=" counts" width={72} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#090d16", borderColor: "#06b6d4", borderRadius: "8px", fontSize: "11px" }}
                    labelFormatter={(v) => `Energy: ${Number(v).toFixed(3)} keV`}
                    formatter={(val: number, name: string) => [`${val} counts`, name === "background" ? "SNIP background" : "Imported counts"]}
                  />
                  <Legend wrapperStyle={{ fontSize: "11px" }} />
                  {showMarkers && peaks.map((peak) => (
                    <ReferenceLine
                      key={peak.channel}
                      x={peak.energyKeV}
                      stroke={peak.overlap ? "#f59e0b" : "#34d399"}
                      strokeDasharray="3 3"
                      label={{ value: markerLabel(peak), fill: peak.overlap ? "#fbbf24" : "#6ee7b7", fontSize: 10, position: "top" }}
                    />
                  ))}
                  {showBackground && peakResult && (
                    <Line type="monotone" dataKey="background" name="background" stroke="#94a3b8" strokeWidth={1.2} dot={false} isAnimationActive={false} />
                  )}
                  <Line type="monotone" dataKey="counts" name="counts" stroke="#06b6d4" strokeWidth={1.4} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {uploadedSpectrum && peakResult && (
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-3">
          <h3 className="text-base font-semibold text-white">Peak candidates ({peaks.length})</h3>
          <p className="text-xs text-slate-400">
            Candidates are every tabulated line within +/-{fmt(peakResult.parameters.matchWindowEv, 0)} eV of the maximum. A candidate is not an identification:
            check a second line of each element, and note that sum peaks, escape peaks and lines outside the table are not considered.
            Line energies: {XRAY_EMISSION_LINES_SOURCE.publisher}, {XRAY_EMISSION_LINES_SOURCE.title.split(":")[0]} ({XRAY_EMISSION_LINES_SOURCE.originalReference}).
          </p>
          {peaks.length === 0 ? (
            <p className="text-sm text-slate-300">No maximum passes the background-significance test. This does not show that an element is absent.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <caption className="sr-only">Detected maxima and the tabulated X-ray lines near each</caption>
                <thead className="text-slate-400 border-b border-slate-700">
                  <tr>
                    <th scope="col" className="py-1.5 pr-3">Energy (keV)</th>
                    <th scope="col" className="py-1.5 pr-3">Channel</th>
                    <th scope="col" className="py-1.5 pr-3">Net counts</th>
                    <th scope="col" className="py-1.5 pr-3">Background</th>
                    <th scope="col" className="py-1.5 pr-3">Net / sqrt(bg)</th>
                    <th scope="col" className="py-1.5 pr-3">Candidate lines (delta eV)</th>
                    <th scope="col" className="py-1.5">Overlap</th>
                  </tr>
                </thead>
                <tbody>
                  {peaks.map((peak) => (
                    <tr key={peak.channel} className="border-b border-slate-800 align-top">
                      <td className="py-1.5 pr-3 font-mono">{fmt(peak.energyKeV, 3)}</td>
                      <td className="py-1.5 pr-3 font-mono">{peak.channel}</td>
                      <td className="py-1.5 pr-3 font-mono">{fmt(peak.netCounts, 1)}</td>
                      <td className="py-1.5 pr-3 font-mono">{fmt(peak.backgroundCounts, 1)}</td>
                      <td className="py-1.5 pr-3 font-mono">{fmt(peak.significance, 1)}</td>
                      <td className="py-1.5 pr-3">
                        {peak.candidates.length === 0
                          ? <span className="text-slate-400">no tabulated line within the window</span>
                          : peak.candidates.map(c => `${c.label} (${c.deltaEv >= 0 ? "+" : ""}${fmt(c.deltaEv, 0)})`).join(", ")}
                      </td>
                      <td className="py-1.5 text-amber-200 max-w-md">
                        {peak.overlap ? peak.overlapNote : <span className="text-slate-500">-</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {peaks.length > 0 && (
            <div className="pt-2">
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input type="checkbox" checked={showNetAreas} onChange={(e) => setShowNetAreas(e.target.checked)} />
                <span>Show net peak areas</span>
              </label>
              {showNetAreas && (
                <div className="mt-2 overflow-x-auto">
                  <p className="text-xs text-amber-200 mb-1">{NET_AREA_LABEL}</p>
                  <table className="w-full text-xs text-left">
                    <caption className="sr-only">Net peak areas, relative intensities only</caption>
                    <thead className="text-slate-400 border-b border-slate-700">
                      <tr>
                        <th scope="col" className="py-1.5 pr-3">Energy (keV)</th>
                        <th scope="col" className="py-1.5 pr-3">Window (keV)</th>
                        <th scope="col" className="py-1.5 pr-3">Net area (counts)</th>
                        <th scope="col" className="py-1.5">Counting sigma</th>
                      </tr>
                    </thead>
                    <tbody>
                      {peaks.map((peak) => (
                        <tr key={peak.channel} className="border-b border-slate-800">
                          <td className="py-1.5 pr-3 font-mono">{fmt(peak.energyKeV, 3)}</td>
                          <td className="py-1.5 pr-3 font-mono">{fmt(peak.netArea.fromKeV, 3)} - {fmt(peak.netArea.toKeV, 3)}</td>
                          <td className="py-1.5 pr-3 font-mono">{fmt(peak.netArea.netCounts, 0)}</td>
                          <td className="py-1.5 font-mono">{fmt(peak.netArea.countingSigma, 0)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Sum of imported counts minus SNIP background over +/-1 FWHM of each maximum; overlapping peaks share counts. The sigma is the
                    square root of the gross counts in the window and ignores the background-model error.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Vendor quantification import */}
      <div id="eds-vendor-quant-panel" className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-3">
        <h3 className="text-base font-semibold text-white flex items-center gap-2">
          <FileSpreadsheet className="w-4 h-4 text-cyan-400" />
          Vendor quantification import
        </h3>
        <p className="text-xs text-slate-400">
          Quantification is not computed here. To use a composition, import the element / wt% table that your EDS software already
          produced. Columns: element symbol, wt%, optional 1-sigma (wt%). Optional header rows:
          {" "}<code># instrument: ...</code>, <code># software: ...</code>, <code># analysis_type: spot|area</code>.
          Negative, non-numeric or unknown-element rows reject the whole file; a total outside 95-105 wt% only warns.
        </p>
        <div className="flex flex-wrap items-end gap-4 text-xs text-slate-300">
          <label className="flex flex-col gap-1">
            <span>Instrument</span>
            <input
              type="text"
              value={vendorInstrument}
              onChange={(e) => setVendorInstrument(e.target.value)}
              className="w-56 bg-slate-950 border border-slate-700 rounded-lg px-2 py-1 text-slate-100"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span>Quantification software</span>
            <input
              type="text"
              value={vendorSoftware}
              onChange={(e) => setVendorSoftware(e.target.value)}
              className="w-56 bg-slate-950 border border-slate-700 rounded-lg px-2 py-1 text-slate-100"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span>Analysis type</span>
            <select
              value={vendorAnalysisType}
              onChange={(e) => setVendorAnalysisType(e.target.value as VendorAnalysisType | "")}
              className="bg-slate-950 border border-slate-700 rounded-lg px-2 py-1 text-slate-100"
            >
              <option value="">Select...</option>
              <option value="spot">Spot</option>
              <option value="area">Area</option>
            </select>
          </label>
          <button
            id="eds-vendor-import-btn"
            onClick={() => vendorInputRef.current?.click()}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-medium flex items-center gap-2 cursor-pointer"
          >
            <Upload className="w-4 h-4 text-cyan-400" />
            <span>Import vendor wt% table (.csv / .txt)</span>
          </button>
          <input
            aria-label="Import vendor quantification table"
            ref={vendorInputRef}
            type="file"
            accept=".csv,.txt,.tsv"
            onChange={handleVendorUpload}
            className="hidden"
          />
        </div>

        {vendorFile && !vendorCurrent && (
          <p role="status" className="text-xs text-slate-400">Checking {vendorFile.fileName} with the current metadata...</p>
        )}
        {vendorResult && vendorFile && vendorCurrent && (
          <div className="space-y-2 text-xs">
            <p className="text-slate-400 break-words">Imported {vendorFile.fileName}</p>
            {vendorResult.errors.length > 0 && (
              <div role="alert" className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-rose-100 space-y-1">
                <p className="font-semibold">Rejected: nothing was imported.</p>
                <ul className="list-disc pl-5">
                  {vendorResult.errors.map((error, index) => (
                    <li key={index}>{error.row > 0 ? `Row ${error.row}: ` : ""}{error.message}</li>
                  ))}
                </ul>
              </div>
            )}
            {vendorResult.warnings.map((warning, index) => (
              <div key={index} role="status" className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-amber-100">{warning}</div>
            ))}
            {vendorResult.rows.length > 0 && !vendorResult.accepted && (
              <p className="text-slate-400">Rows that parsed (shown for reference only; nothing was imported):</p>
            )}
            {vendorResult.rows.length > 0 && (
              <table className="text-left">
                <caption className="sr-only">Vendor-reported composition</caption>
                <thead className="text-slate-400 border-b border-slate-700">
                  <tr>
                    <th scope="col" className="py-1 pr-4">Element</th>
                    <th scope="col" className="py-1 pr-4">wt%</th>
                    <th scope="col" className="py-1">1-sigma (wt%)</th>
                  </tr>
                </thead>
                <tbody>
                  {vendorResult.rows.map((row) => (
                    <tr key={row.element} className="border-b border-slate-800">
                      <td className="py-1 pr-4">{row.element}</td>
                      <td className="py-1 pr-4 font-mono">{row.weightPct}</td>
                      <td className="py-1 font-mono">{row.sigmaWeightPct ?? "-"}</td>
                    </tr>
                  ))}
                  <tr>
                    <td className="py-1 pr-4 text-slate-400">Total</td>
                    <td className="py-1 pr-4 font-mono">{fmt(vendorResult.totalWeightPct, 2)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            )}
            {vendorResult.accepted && vendorResult.provenance && (
              <div className="space-y-2">
                <p className="text-slate-300 break-words">
                  {vendorResult.transferLabel}. File SHA-256 {vendorResult.provenance.sha256}.
                </p>
                <button
                  id="eds-send-to-module-btn"
                  onClick={sendVendorComposition}
                  className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-semibold rounded-xl text-xs flex items-center gap-2 cursor-pointer"
                  title="Send the vendor-reported local composition to the Alloy Builder as a design input; it is not a bulk composition"
                >
                  <Share2 className="w-4 h-4" />
                  <span>Send vendor composition to Alloy Builder</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
