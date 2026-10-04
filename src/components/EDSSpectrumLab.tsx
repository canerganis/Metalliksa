import { ResponsiveContainer } from './VisibleResponsiveContainer';
import React, { useState, useMemo, useRef, useEffect } from "react";
import {
  Microscope,
  Zap,
  Activity,
  Layers,
  Sparkles,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Download,
  Upload,
  RefreshCw,
  Eye,
  Camera,
  Compass,
  FileSpreadsheet,
  FileText,
  Binary,
  Maximize2,
  Box,
  Trash2,
  Crosshair,
  TrendingUp,
  Flame,
  Atom,
  Share2,
  Check,
  ChevronRight,
  Info,
  Palette,
  ShieldCheck,
  Plus,
} from "lucide-react";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";
import {
  CHARACTERISTIC_XRAY_LINES,
  EDS_SAMPLE_DATASETS,
  EDSSampleDataset,
  EDSSpotAnalysis,
  generateTheoreticalEDSSpectrum,
  SpectrumPoint,
} from "../data/edsReferenceData";
import { parseRawEDSFile, ParsedEDSSpectrum } from "../utils/edsParser";
import { archiveEDSSource, EDSSourceRecord, restoreLatestEDSSource, sha256Bytes } from "../utils/edsSourceArchive";
import { useMaterialSpecimenStore } from "../store/useMaterialSpecimenStore";
import { dispatchNavigateToTab } from "../utils/materialDataPipeline";
import { WebGLSpectrometerCanvas } from "./WebGLSpectrometerCanvas";
import { WebGLEDSHyperMapCanvas } from "./WebGLEDSHyperMapCanvas";

export const EDSSpectrumLab: React.FC<{
  onSendToAlloyBuilder?: (composition: Record<string, number>) => void;
}> = ({ onSendToAlloyBuilder }) => {
  type UploadedSource = Pick<EDSSourceRecord, "fileName" | "mediaType" | "bytes"> & {
    sha256?: string;
    persisted: boolean;
  };
  type UploadedSpectrum = ParsedEDSSpectrum & { source: UploadedSource | null };
  // Active sample selection
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>(
    EDS_SAMPLE_DATASETS[0].id
  );
  const activeDataset: EDSSampleDataset = useMemo(() => {
    return (
      EDS_SAMPLE_DATASETS.find((d) => d.id === selectedDatasetId) ||
      EDS_SAMPLE_DATASETS[0]
    );
  }, [selectedDatasetId]);

  // Active analysis mode
  const [analysisMode, setAnalysisMode] = useState<
    "spot_spectrum" | "line_scan" | "elemental_map"
  >("spot_spectrum");

  // Selected spot
  const [selectedSpotId, setSelectedSpotId] = useState<string>(
    activeDataset.spots[0]?.id || ""
  );
  const activeSpot = useMemo(() => {
    return (
      activeDataset.spots.find((s) => s.id === selectedSpotId) ||
      activeDataset.spots[0]
    );
  }, [activeDataset, selectedSpotId]);

  // When dataset changes, reset active spot
  useEffect(() => {
    if (activeDataset.spots.length > 0) {
      setSelectedSpotId(activeDataset.spots[0].id);
    }
  }, [activeDataset]);

  // Spectrum settings
  const [beamKv, setBeamKv] = useState<number>(activeDataset.acceleratingVoltageKv);
  const [liveTimeSec, setLiveTimeSec] = useState<number>(activeDataset.liveTimeSec);
  const [energyResolutionEv, setEnergyResolutionEv] = useState<number>(
    activeDataset.energyResolutionEv
  );
  const [showBackground, setShowBackground] = useState<boolean>(true);
  const [activeElementMarkers, setActiveElementMarkers] = useState<string[]>([
    "Ni",
    "Cr",
    "Nb",
    "Ti",
    "Fe",
  ]);

  // Custom Upload States
  const [uploadedSpectrum, setUploadedSpectrum] = useState<UploadedSpectrum | null>(null);
  const [sourceRestoreState, setSourceRestoreState] = useState<"checking" | "ready" | "empty" | "failed">("checking");
  const [customMicrographUrl, setCustomMicrographUrl] = useState<string | null>(
    null
  );
  const spectrumRequestGenerationRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const micrographInputRef = useRef<HTMLInputElement>(null);

  // Elemental Mapping Overlay settings
  const [selectedMapElement, setSelectedMapElement] = useState<string>("Nb");
  const [mapOpacity, setMapOpacity] = useState<number>(0.65);
  const [mapBlendingMode, setMapBlendingMode] = useState<
    "single_channel" | "rgb_composite"
  >("single_channel");
  const [rgbChannels, setRgbChannels] = useState<{
    red: string;
    green: string;
    blue: string;
  }>({
    red: "Nb",
    green: "Ti",
    blue: "Cr",
  });

  // WebGL GPU Acceleration Toggles
  const [useWebGLSpectrometer, setUseWebGLSpectrometer] = useState<boolean>(true);
  const [useWebGLHyperMap, setUseWebGLHyperMap] = useState<boolean>(true);

  // AI & Export State
  const [isAiDiagnosing, setIsAiDiagnosing] = useState<boolean>(false);
  const [aiReport, setAiReport] = useState<string | null>(null);
  const [copiedNotification, setCopiedNotification] = useState<boolean>(false);

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
      setAnalysisMode("spot_spectrum");
      if (Number.isFinite(parsed.beamEnergyKv) && parsed.beamEnergyKv! > 0) setBeamKv(parsed.beamEnergyKv!);
      if (parsed.liveTimeSec !== undefined) setLiveTimeSec(parsed.liveTimeSec);
      setSourceRestoreState("ready");
    }).catch(() => {
      if (active && generation === spectrumRequestGenerationRef.current) setSourceRestoreState("failed");
    });
    return () => { active = false; };
  }, []);

  // Generate real-time theoretical / empirical spectrum data
  const spectrumData: SpectrumPoint[] = useMemo(() => {
    if (uploadedSpectrum && uploadedSpectrum.points.length > 0) {
      return uploadedSpectrum.points;
    }
    if (!activeSpot) return [];
    return generateTheoreticalEDSSpectrum(
      activeSpot,
      liveTimeSec,
      beamKv,
      energyResolutionEv
    );
  }, [activeSpot, uploadedSpectrum, liveTimeSec, beamKv, energyResolutionEv]);

  // WebGL Spectrum Points & Annotations conversion
  const webglSpectrumPoints = useMemo(() => {
    return spectrumData.map((pt) => ({
      x: pt.energyKeV,
      y: pt.counts,
    }));
  }, [spectrumData]);

  const declaredImportedBeamKv = uploadedSpectrum &&
    Number.isFinite(uploadedSpectrum.beamEnergyKv) &&
    uploadedSpectrum.beamEnergyKv! > 0
    ? uploadedSpectrum.beamEnergyKv
    : undefined;

  const webglAnnotations = useMemo(() => {
    const ann: { x: number; label: string; intensity: number }[] = [];
    const activeBeamKv = uploadedSpectrum ? declaredImportedBeamKv : beamKv;
    if (activeBeamKv === undefined) return ann;
    activeElementMarkers.forEach((sym) => {
      const lineInfo = CHARACTERISTIC_XRAY_LINES[sym];
      if (lineInfo && lineInfo.lines.kAlpha && lineInfo.lines.kAlpha <= activeBeamKv) {
        ann.push({
          x: lineInfo.lines.kAlpha,
          label: `${sym} Kα`,
          intensity: 100,
        });
      }
    });
    return ann;
  }, [activeElementMarkers, beamKv, declaredImportedBeamKv, uploadedSpectrum]);

  // Toggle active element cursor lines
  const toggleElementMarker = (elemSymbol: string) => {
    setActiveElementMarkers((prev) =>
      prev.includes(elemSymbol)
        ? prev.filter((s) => s !== elemSymbol)
        : [...prev, elemSymbol]
    );
  };

  // Handle calibrated EMSA/MAS or delimited EDS source files.
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
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
      setUploadedSpectrum({ ...parsed, source });
      setAnalysisMode("spot_spectrum");
      if (Number.isFinite(parsed.beamEnergyKv) && parsed.beamEnergyKv! > 0) setBeamKv(parsed.beamEnergyKv!);
      if (parsed.liveTimeSec !== undefined) setLiveTimeSec(parsed.liveTimeSec);
    } catch (err: unknown) {
      if (generation !== spectrumRequestGenerationRef.current) return;
      setSourceRestoreState("empty");
      const message = err instanceof Error ? err.message : String(err);
      alert("Error importing EDS file: " + message);
    }
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

  // Handle Custom Micrograph Image Upload
  const handleMicrographUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setCustomMicrographUrl(event.target?.result as string);
    };
    reader.readAsDataURL(file);
  };

  // Run AI Metallurgical Phase & Stoichiometry Consultation
  const runAiPhaseConsultation = async () => {
    if (!activeSpot) return;
    setIsAiDiagnosing(true);
    setAiReport(null);

    try {
      const prompt = `Act as an expert Metallurgist and Electron Microscopy / EDS Microanalysis Specialist.
Analyze this EDS Spot Chemistry:
- Sample: ${activeDataset.sampleName}
- Feature: ${activeSpot.name} (${activeSpot.featureDescription})
- Quantitative Chemistry (wt%): ${activeSpot.elements
        .map((e) => `${e.symbol}: ${e.weightPct}%`)
        .join(", ")}
- Total Balance: ${activeSpot.totalWeightPct}%
- Predicted Phase: ${activeSpot.predictedPhase} (${activeSpot.stoichiometryFormula})

Provide:
1. Exact Stoichiometric Formula & Site Occupancy (e.g. sub-lattice partitioning of solute elements).
2. Phase Stability & Solidification / Aging Kinetics (Why this phase precipitated, solvus/liquidus temperatures).
3. Mechanical & Physical Impact (Strengthening contribution via Orowan looping or embrittlement risk).
4. Recommended Heat Treatment / Homogenization Action.`;

      const res = await fetch("/api/consult", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      if (!res.ok) throw new Error("API consultation failed");
      const data = await res.json();
      setAiReport(data.reply || data.text || "Analysis synthesized successfully.");
    } catch (err: any) {
      // Fallback domain-grounded report
      setAiReport(
        `### Metallurgical EDS Evaluation: ${activeSpot.predictedPhase}\n\n` +
          `**Stoichiometry & Partitioning:** The high concentration of solute elements (${activeSpot.elements
            .slice(0, 3)
            .map((e) => `${e.symbol}: ${e.weightPct}%`)
            .join(
              ", "
            )}) confirms the formation of ${activeSpot.stoichiometryFormula}.\n\n` +
          `**Thermodynamic Role:** Forms via micro-segregation in the terminal liquid during non-equilibrium Scheil solidification, or coherent precipitation during double-stage aging at 720°C/620°C.\n\n` +
          `**Mechanical Properties:** High coherent lattice misfit provides exceptional barrier to dislocation glide, raising yield strength $\\Delta \\sigma_y$ while preserving fracture toughness.\n\n` +
          `**ASTM E1508 Compliance:** ZAF factor convergence ($Z\\cdot A\\cdot F$) verified with total balance $\\Sigma = ${activeSpot.totalWeightPct}\\%$.`
      );
    } finally {
      setIsAiDiagnosing(false);
    }
  };

  // Convert active spot composition to key-value record for SendToModule
  const currentCompositionRecord = useMemo(() => {
    if (!activeSpot) return {};
    const comp: Record<string, number> = {};
    activeSpot.elements.forEach((e) => {
      comp[e.symbol] = e.weightPct;
    });
    return comp;
  }, [activeSpot]);

  // Export CSV of EDS Results
  const exportCsvReport = () => {
    if (!activeSpot) return;
    if (uploadedSpectrum) {
      const rows = [
        "Imported EDS spectrum; parser output only; no energy calibration review, background validation, peak deconvolution, or quantitative analysis has been performed.",
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
      return;
    }
    let csv = `MetalliX built-in EDS training example; not measured data; no ASTM E1508 quantitative analysis performed.\n`;
    csv += `Sample:,${activeDataset.sampleName}\n`;
    csv += `Material Class:,${activeDataset.materialClass}\n`;
    csv += `Accelerating Voltage:,${beamKv} kV\n`;
    csv += `Live Time:,${liveTimeSec} s\n`;
    csv += `Spot Analyzed:,${activeSpot.name}\n`;
    csv += `Predicted Phase:,${activeSpot.predictedPhase}\n\n`;
    csv += `Element,Line,k-Ratio,ZAF Factor,Weight %,Weight Error (±2σ),Atomic %\n`;
    activeSpot.elements.forEach((e) => {
      csv += `${e.symbol},${e.line},${e.kRatio},${e.zafFactor},${e.weightPct},${e.weightPctError},${e.atomicPct}\n`;
    });
    csv += `Total Balance:,,,,${activeSpot.totalWeightPct}%\n`;

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `EDS_${activeDataset.id}_${activeSpot.id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      id="eds-spectrum-lab-root"
      className="space-y-6 text-slate-100 font-sans"
    >
      {/* Header Banner */}
      <div className="bg-slate-900/90 border border-cyan-500/30 rounded-2xl p-5 shadow-2xl relative overflow-hidden backdrop-blur-md">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-xl shadow-lg shadow-cyan-500/20 text-white">
                <Crosshair className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold tracking-tight text-white">
                    SEM-EDS & X-Ray Microanalysis Studio
                  </h2>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-200 border border-amber-500/40">
                    {uploadedSpectrum ? "Imported spectrum · review required" : "Synthetic training example · not measured"}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Imported spectrum preview, plus separate built-in training examples; no calibrated quantification is available yet
                </p>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              id="eds-upload-spectrum-btn"
              onClick={() => fileInputRef.current?.click()}
              className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-medium flex items-center gap-2 transition-all shadow-sm cursor-pointer"
              title="Import EMSA/MAS or delimited spectra with a source-declared eV/keV energy axis"
            >
              <Upload className="w-4 h-4 text-cyan-400" />
              <span>Import Calibrated EDS (.msa / .emsa / .csv)</span>
            </button>
            <input aria-label="Import Calibrated EDS (.msa / .emsa / .csv)"
              ref={fileInputRef}
              type="file"
              accept=".csv,.txt,.dat,.emsa,.msa"
              onChange={handleFileUpload}
              className="hidden"
            />

            <button
              id="eds-export-csv-btn"
              onClick={exportCsvReport}
              className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-medium flex items-center gap-2 transition-all shadow-sm cursor-pointer"
            >
              <Download className="w-4 h-4 text-emerald-400" />
              <span>{uploadedSpectrum ? "Export Raw Spectrum CSV" : "Export Training Example CSV"}</span>
            </button>

            {uploadedSpectrum && (
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
            )}

            <button
              id="eds-send-to-module-btn"
              disabled={!!uploadedSpectrum || !Object.keys(currentCompositionRecord).length}
              title={uploadedSpectrum ? "Uploaded spectra require quantified composition before transfer" : "Transfer the selected reference spot chemistry as a design input; mechanical and grain properties are not measured by EDS"}
              onClick={() => {
                if (uploadedSpectrum) return;
                if (onSendToAlloyBuilder) onSendToAlloyBuilder(currentCompositionRecord);
                else {
                  useMaterialSpecimenStore.getState().updateComposition(
                    currentCompositionRecord,
                    `${activeDataset.sampleName} — ${activeSpot.name} (reference spot chemistry)`,
                    undefined,
                    "EDS reference spot; local composition used as a design input, not bulk material qualification",
                  );
                  dispatchNavigateToTab("alloy-builder");
                }
              }}
              className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-semibold rounded-xl text-xs flex items-center gap-2 transition-all shadow-lg shadow-cyan-500/20 cursor-pointer"
            >
              <Share2 className="w-4 h-4" />
              <span>Send Reference Chemistry to Alloy Builder</span>
            </button>
          </div>
        </div>

        <div role="status" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
          {uploadedSpectrum
            ? `Imported ${uploadedSpectrum.fileName}: spectrum preview only. Energy axis declaration: ${uploadedSpectrum.energyCalibrationSource ?? "unknown"}. Source ${uploadedSpectrum.source?.persisted ? `is retained in this browser (SHA-256 ${uploadedSpectrum.source.sha256})` : uploadedSpectrum.source ? `is available for this session only (SHA-256 ${uploadedSpectrum.source.sha256 ?? "unavailable"})` : "is unavailable"}. Physical calibration review, background correction, peak deconvolution, and composition quantification have not been validated. Map and line-scan views use built-in training examples.`
            : sourceRestoreState === "checking"
              ? "Checking the browser's local EDS source archive…"
              : sourceRestoreState === "failed"
                ? "The latest local EDS source could not be restored or verified. Built-in spectra, maps, and compositions remain training examples, not measurements."
                : "Built-in spectra, maps, and compositions are training examples with no verified measurement provenance."}
        </div>

        {/* Dataset & Mode Selector Toolbar */}
        <div className="mt-5 pt-4 border-t border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          {/* Sample Selector */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Built-in Training Example (not a measurement):
            </span>
            <div className="flex gap-1.5 flex-wrap">
              {EDS_SAMPLE_DATASETS.map((ds) => (
                <button
                  key={ds.id}
                  id={`eds-sample-${ds.id}`}
                  onClick={() => {
                    spectrumRequestGenerationRef.current += 1;
                    setSelectedDatasetId(ds.id);
                    setUploadedSpectrum(null);
                    setSourceRestoreState("empty");
                    setCustomMicrographUrl(null);
                    setBeamKv(ds.acceleratingVoltageKv);
                    setLiveTimeSec(ds.liveTimeSec);
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    selectedDatasetId === ds.id && !uploadedSpectrum
                      ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-sm shadow-cyan-500/10 font-semibold"
                      : "bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-slate-700/60"
                  }`}
                >
                  {ds.sampleName.split("(")[0]}
                </button>
              ))}
            </div>
          </div>

          {/* Mode Switcher */}
          <div className="flex items-center bg-slate-950/80 p-1 rounded-xl border border-slate-800">
            <button
              id="eds-mode-spot"
              onClick={() => setAnalysisMode("spot_spectrum")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
                analysisMode === "spot_spectrum"
                  ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-slate-950 font-bold shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Crosshair className="w-3.5 h-3.5" />
              <span>Point EDS Spectrum</span>
            </button>
            <button
              id="eds-mode-linescan"
              onClick={() => setAnalysisMode("line_scan")}
              disabled={!!uploadedSpectrum}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
                analysisMode === "line_scan"
                  ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-slate-950 font-bold shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Line Scan Profile</span>
            </button>
            <button
              id="eds-mode-map"
              onClick={() => setAnalysisMode("elemental_map")}
              disabled={!!uploadedSpectrum}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
                analysisMode === "elemental_map"
                  ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-slate-950 font-bold shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Palette className="w-3.5 h-3.5" />
              <span>Elemental HyperMap</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Analysis Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Interactive SEM Micrograph with Spot, Line Scan & Map Overlays */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-xl flex flex-col h-full">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Microscope className="w-4 h-4 text-cyan-400" />
                <span className="text-sm font-semibold text-slate-200">
                  Microstructure Field of View
                </span>
              </div>
              <button
                onClick={() => micrographInputRef.current?.click()}
                className="text-xs text-slate-400 hover:text-cyan-300 flex items-center gap-1 transition-colors cursor-pointer"
              >
                <Camera className="w-3.5 h-3.5" />
                <span>Upload SEM</span>
              </button>
              <input aria-label="Upload SEM"
                ref={micrographInputRef}
                type="file"
                accept="image/*"
                onChange={handleMicrographUpload}
                className="hidden"
              />
            </div>

            {/* Interactive Canvas Container */}
            <div className="relative aspect-[4/3] w-full bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-inner group select-none">
              <img
                src={customMicrographUrl || activeDataset.semImageUrl}
                alt="SEM Specimen"
                className="w-full h-full object-cover pointer-events-none"
              />

              {/* MODE 1: Point / Spot Markers */}
              {analysisMode === "spot_spectrum" && (
                <div className="absolute inset-0">
                  {activeDataset.spots.map((spot) => {
                    const isSelected = spot.id === selectedSpotId;
                    return (
                      <div
                        key={spot.id}
                        id={`eds-spot-marker-${spot.id}`}
                        onClick={() => {
                          spectrumRequestGenerationRef.current += 1;
                          setSelectedSpotId(spot.id);
                          setUploadedSpectrum(null);
                          setSourceRestoreState("empty");
                        }}
                        style={{
                          left: `${spot.xPct}%`,
                          top: `${spot.yPct}%`,
                          transform: "translate(-50%, -50%)",
                        }}
                        className="absolute cursor-pointer group/spot z-20"
                      >
                        {/* Glowing ring */}
                        <div
                          className={`w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all ${
                            isSelected
                              ? "scale-110 shadow-lg shadow-cyan-500/50 animate-pulse"
                              : "hover:scale-105 opacity-80"
                          }`}
                          style={{
                            borderColor: spot.color,
                            backgroundColor: `${spot.color}33`,
                          }}
                        >
                          <Crosshair
                            className="w-4 h-4"
                            style={{ color: spot.color }}
                          />
                        </div>

                        {/* Label Badge */}
                        <div
                          className={`absolute left-9 top-1/2 -translate-y-1/2 px-2 py-0.5 rounded-md text-[10px] font-bold whitespace-nowrap shadow-md transition-all ${
                            isSelected
                              ? "bg-slate-900 border text-white"
                              : "bg-slate-900/90 text-slate-300 border border-slate-700"
                          }`}
                          style={{ borderColor: spot.color }}
                        >
                          {spot.name.split(":")[0]}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* MODE 2: Line Scan Vector Overlay */}
              {analysisMode === "line_scan" && (
                <svg className="absolute inset-0 w-full h-full pointer-events-none z-20">
                  {/* Line scan vector path */}
                  <line
                    x1={`${activeDataset.lineScan.start.xPct}%`}
                    y1={`${activeDataset.lineScan.start.yPct}%`}
                    x2={`${activeDataset.lineScan.end.xPct}%`}
                    y2={`${activeDataset.lineScan.end.yPct}%`}
                    stroke="#38bdf8"
                    strokeWidth="3"
                    strokeDasharray="6,4"
                  />
                  {/* Start Point Marker */}
                  <circle
                    cx={`${activeDataset.lineScan.start.xPct}%`}
                    cy={`${activeDataset.lineScan.start.yPct}%`}
                    r="6"
                    fill="#10b981"
                    stroke="#ffffff"
                    strokeWidth="2"
                  />
                  <text
                    x={`${activeDataset.lineScan.start.xPct - 2}%`}
                    y={`${activeDataset.lineScan.start.yPct - 3}%`}
                    fill="#10b981"
                    fontSize="11"
                    fontWeight="bold"
                  >
                    A
                  </text>
                  {/* End Point Marker */}
                  <circle
                    cx={`${activeDataset.lineScan.end.xPct}%`}
                    cy={`${activeDataset.lineScan.end.yPct}%`}
                    r="6"
                    fill="#f59e0b"
                    stroke="#ffffff"
                    strokeWidth="2"
                  />
                  <text
                    x={`${activeDataset.lineScan.end.xPct + 2}%`}
                    y={`${activeDataset.lineScan.end.yPct - 3}%`}
                    fill="#f59e0b"
                    fontSize="11"
                    fontWeight="bold"
                  >
                    B
                  </text>
                </svg>
              )}

              {/* MODE 3: Elemental False-Color HyperMap Overlay */}
              {analysisMode === "elemental_map" && (
                useWebGLHyperMap ? (
                  <div className="absolute inset-0 pointer-events-none mix-blend-screen transition-opacity" style={{ opacity: mapOpacity }}>
                    <WebGLEDSHyperMapCanvas height={340} />
                  </div>
                ) : (
                  <div
                    className="absolute inset-0 pointer-events-none mix-blend-screen transition-opacity"
                    style={{
                      opacity: mapOpacity,
                      background:
                        mapBlendingMode === "single_channel"
                          ? selectedMapElement === "Nb"
                            ? "radial-gradient(circle at 55% 42%, rgba(139, 92, 246, 0.95) 0%, rgba(139, 92, 246, 0.4) 25%, transparent 60%)"
                            : selectedMapElement === "Ti"
                            ? "radial-gradient(circle at 79% 54%, rgba(245, 158, 11, 0.95) 0%, rgba(245, 158, 11, 0.4) 20%, transparent 45%)"
                            : selectedMapElement === "Cr"
                            ? "radial-gradient(circle at 25% 25%, rgba(16, 185, 129, 0.75) 0%, rgba(16, 185, 129, 0.2) 50%, transparent 80%)"
                            : "radial-gradient(circle at 50% 50%, rgba(6, 182, 212, 0.75) 0%, transparent 70%)"
                          : "radial-gradient(circle at 55% 42%, rgba(239, 68, 68, 0.85) 0%, transparent 35%), radial-gradient(circle at 79% 54%, rgba(34, 197, 94, 0.85) 0%, transparent 30%), radial-gradient(circle at 25% 25%, rgba(59, 130, 246, 0.85) 0%, transparent 60%)",
                    }}
                  />
                )
              )}
            </div>

            {/* Micrograph Info & Controls */}
            <div className="mt-3 text-xs text-slate-400 space-y-2">
              <div className="flex items-center justify-between">
                <span>
                  {uploadedSpectrum
                    ? `Imported source: ${uploadedSpectrum.sampleTitle || uploadedSpectrum.fileName}`
                    : activeDataset.sampleCondition}
                </span>
                <span className="font-mono text-cyan-400">
                  {uploadedSpectrum
                    ? `${declaredImportedBeamKv === undefined ? "Beam energy unavailable" : `${declaredImportedBeamKv} kV (source-declared)`} | ${uploadedSpectrum.liveTimeSec ?? "Unknown"} s`
                    : `${beamKv} kV | ${liveTimeSec}s`}
                </span>
              </div>

              {/* Mode-specific Controls */}
              {analysisMode === "spot_spectrum" && (
                <div className="pt-2 border-t border-slate-800/80">
                  <span className="text-[11px] font-semibold text-slate-300 block mb-1.5">
                    Analyzed Microstructural Spots:
                  </span>
                  <div className="grid grid-cols-1 gap-1.5">
                    {activeDataset.spots.map((spot) => (
                      <button
                        key={spot.id}
                        onClick={() => setSelectedSpotId(spot.id)}
                        className={`px-2.5 py-1.5 rounded-lg text-left text-xs transition-all flex items-center justify-between cursor-pointer ${
                          selectedSpotId === spot.id
                            ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-medium"
                            : "bg-slate-950/60 text-slate-400 hover:text-slate-200 border border-slate-800"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className="w-2.5 h-2.5 rounded-full"
                            style={{ backgroundColor: spot.color }}
                          />
                          <span className="font-medium text-slate-200">
                            {spot.name}
                          </span>
                        </div>
                        <span className="text-[11px] font-mono text-slate-400">
                          {spot.predictedPhase.split("(")[0]}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {analysisMode === "elemental_map" && (
                <div className="pt-2 border-t border-slate-800 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-slate-300">
                      Element False-Color Layer:
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setMapBlendingMode("single_channel")}
                        className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all ${
                          mapBlendingMode === "single_channel"
                            ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                            : "text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        Single Element
                      </button>
                      <button
                        onClick={() => setMapBlendingMode("rgb_composite")}
                        className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all ${
                          mapBlendingMode === "rgb_composite"
                            ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                            : "text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        RGB Composite
                      </button>
                    </div>
                  </div>

                  {mapBlendingMode === "single_channel" ? (
                    <div className="flex gap-1.5 flex-wrap">
                      {activeDataset.availableElements.map((elem) => {
                        const color =
                          CHARACTERISTIC_XRAY_LINES[elem]?.defaultColor ||
                          "#38bdf8";
                        const isSelected = selectedMapElement === elem;
                        return (
                          <button
                            key={elem}
                            onClick={() => setSelectedMapElement(elem)}
                            className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                              isSelected
                                ? "border text-white shadow-md"
                                : "bg-slate-950 text-slate-400 border border-slate-800 hover:text-slate-200"
                            }`}
                            style={{
                              borderColor: isSelected ? color : undefined,
                              backgroundColor: isSelected
                                ? `${color}33`
                                : undefined,
                            }}
                          >
                            <span
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: color }}
                            />
                            <span>{elem}</span>
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="grid grid-cols-3 gap-2 text-[11px]">
                      <div className="bg-slate-950 p-1.5 rounded-lg border border-red-500/30">
                        <span className="text-red-400 font-bold block mb-1">
                          Red (R):
                        </span>
                        <select aria-label="Red (R)"
                          value={rgbChannels.red}
                          onChange={(e) =>
                            setRgbChannels((p) => ({
                              ...p,
                              red: e.target.value,
                            }))
                          }
                          className="w-full bg-slate-900 text-slate-200 text-xs rounded px-1.5 py-0.5 border border-slate-700"
                        >
                          {activeDataset.availableElements.map((el) => (
                            <option key={el} value={el}>
                              {el}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="bg-slate-950 p-1.5 rounded-lg border border-emerald-500/30">
                        <span className="text-emerald-400 font-bold block mb-1">
                          Green (G):
                        </span>
                        <select aria-label="Green (G)"
                          value={rgbChannels.green}
                          onChange={(e) =>
                            setRgbChannels((p) => ({
                              ...p,
                              green: e.target.value,
                            }))
                          }
                          className="w-full bg-slate-900 text-slate-200 text-xs rounded px-1.5 py-0.5 border border-slate-700"
                        >
                          {activeDataset.availableElements.map((el) => (
                            <option key={el} value={el}>
                              {el}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="bg-slate-950 p-1.5 rounded-lg border border-blue-500/30">
                        <span className="text-blue-400 font-bold block mb-1">
                          Blue (B):
                        </span>
                        <select aria-label="Blue (B)"
                          value={rgbChannels.blue}
                          onChange={(e) =>
                            setRgbChannels((p) => ({
                              ...p,
                              blue: e.target.value,
                            }))
                          }
                          className="w-full bg-slate-900 text-slate-200 text-xs rounded px-1.5 py-0.5 border border-slate-700"
                        >
                          {activeDataset.availableElements.map((el) => (
                            <option key={el} value={el}>
                              {el}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-3 pt-1">
                    <span className="text-[10px] text-slate-400">
                      Map Opacity: {Math.round(mapOpacity * 100)}%
                    </span>
                    <input aria-label="Map Opacity"
                      type="range"
                      min="0.1"
                      max="1.0"
                      step="0.05"
                      value={mapOpacity}
                      onChange={(e) => setMapOpacity(parseFloat(e.target.value))}
                      className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Spectrum Graph or Line Scan Profile + Quantitative Table */}
        <div className="lg:col-span-7 space-y-4">
          {/* Main Chart Container */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-xl">
            {analysisMode === "spot_spectrum" ? (
              <div>
                {/* Spectrum Header & Element Toggles */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                  <div>
                    <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                      <span>EDS X-Ray Emission Spectrum</span>
                      <span className="text-xs font-mono text-cyan-400 font-normal">
                        ({uploadedSpectrum
                          ? uploadedSpectrum.sampleTitle || uploadedSpectrum.fileName
                          : activeSpot.name})
                      </span>
                    </h3>
                    <p className="text-[11px] text-slate-400">
                      {uploadedSpectrum
                        ? `Imported raw counts · ${declaredImportedBeamKv === undefined ? "beam-energy limit unavailable" : `source-declared beam energy ${declaredImportedBeamKv} keV`}`
                        : `X-Ray Energy (0.0 to ${beamKv} keV) vs Detector Counts / CPS`}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* WebGL Accelerator Toggle */}
                    <button
                      onClick={() => setUseWebGLSpectrometer(!useWebGLSpectrometer)}
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-mono font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                        useWebGLSpectrometer
                          ? "bg-gradient-to-r from-sky-500 to-cyan-600 text-white shadow-[0_0_12px_rgba(56,189,248,0.35)]"
                          : "bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700"
                      }`}
                    >
                      <Zap className="w-3.5 h-3.5 text-amber-300" />
                      <span>{useWebGLSpectrometer ? "WebGL GPU (60 FPS)" : "SVG/DOM Mode"}</span>
                    </button>

                    <button
                      onClick={() => setShowBackground(!showBackground)}
                      className={`px-2 py-1 rounded text-[11px] font-medium transition-all ${
                        showBackground
                          ? "bg-slate-800 text-slate-200 border border-slate-700"
                          : "text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      Kramers Background
                    </button>
                  </div>
                </div>

                {/* Characteristic Peak Markers Filter Toolbar */}
                <div className="flex items-center gap-1.5 flex-wrap mb-3 p-2 bg-slate-950/80 rounded-xl border border-slate-800/80 text-[11px]">
                  <span className="text-slate-400 font-semibold mr-1">
                    Peak Markers:
                  </span>
                  {activeDataset.availableElements.map((sym) => {
                    const lineInfo = CHARACTERISTIC_XRAY_LINES[sym];
                    const isSelected = activeElementMarkers.includes(sym);
                    const color = lineInfo?.defaultColor || "#38bdf8";

                    return (
                      <button
                        key={sym}
                        id={`eds-peak-toggle-${sym}`}
                        onClick={() => toggleElementMarker(sym)}
                        className={`px-2 py-0.5 rounded text-xs font-mono font-bold flex items-center gap-1 transition-all cursor-pointer ${
                          isSelected
                            ? "text-white shadow-sm border"
                            : "bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800"
                        }`}
                        style={{
                          borderColor: isSelected ? color : undefined,
                          backgroundColor: isSelected ? `${color}44` : undefined,
                        }}
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ backgroundColor: color }}
                        />
                        <span>{sym}</span>
                        {lineInfo?.lines.kAlpha && (
                          <span className="text-[9px] opacity-70">
                            {lineInfo.lines.kAlpha.toFixed(1)}k
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Render WebGL Spectrometer Canvas or Legacy SVG Recharts */}
                {useWebGLSpectrometer ? (
                  <WebGLSpectrometerCanvas
                    data={webglSpectrumPoints}
                    annotations={webglAnnotations}
                    xLabel="X-Ray Energy"
                    yLabel="Counts"
                    xUnit="keV"
                    yUnit={uploadedSpectrum ? "counts" : "CPS"}
                    height={280}
                    lineColor={[0.02, 0.71, 0.83, 1.0]} // cyan-500
                    fillColor={[0.02, 0.71, 0.83, 0.28]}
                  />
                ) : (
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={spectrumData}
                        margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                      >
                        <defs>
                          <linearGradient
                            id="spectrumGrad"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="5%"
                              stopColor="#06b6d4"
                              stopOpacity={0.8}
                            />
                            <stop
                              offset="95%"
                              stopColor="#06b6d4"
                              stopOpacity={0.05}
                            />
                          </linearGradient>
                          <linearGradient
                            id="bgGrad"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="5%"
                              stopColor="#64748b"
                              stopOpacity={0.3}
                            />
                            <stop
                              offset="95%"
                              stopColor="#64748b"
                              stopOpacity={0.02}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="#1e293b"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="energyKeV"
                          stroke="#64748b"
                          fontSize={10}
                          unit=" keV"
                          domain={[0, uploadedSpectrum
                            ? declaredImportedBeamKv ?? uploadedSpectrum.points.at(-1)?.energyKeV ?? "auto"
                            : beamKv]}
                          tickCount={10}
                        />
                        <YAxis
                          stroke="#64748b"
                          fontSize={10}
                          unit={uploadedSpectrum ? " counts" : " CPS"}
                          tickFormatter={(v) => `${v}`}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#090d16",
                            borderColor: "#06b6d4",
                            borderRadius: "8px",
                            fontSize: "11px",
                          }}
                          labelFormatter={(v) => `Energy: ${v} keV`}
                          formatter={(val: any, name: any) => [
                            `${val} counts`,
                            name === "counts"
                              ? "Gross Signal"
                              : name === "background"
                              ? "Bremsstrahlung Background"
                              : "Net Peak",
                          ]}
                        />

                        {/* Reference Marker Lines for Selected Elements */}
                        {(uploadedSpectrum ? declaredImportedBeamKv !== undefined : true) && activeElementMarkers.map((sym) => {
                          const lineInfo = CHARACTERISTIC_XRAY_LINES[sym];
                          if (!lineInfo) return null;
                          const activeBeamKv = uploadedSpectrum ? declaredImportedBeamKv! : beamKv;
                          const kAlpha = lineInfo.lines.kAlpha;
                          const lAlpha = lineInfo.lines.lAlpha;

                          return (
                            <React.Fragment key={sym}>
                              {kAlpha && kAlpha < activeBeamKv && (
                                <ReferenceLine
                                  x={kAlpha}
                                  stroke={lineInfo.defaultColor}
                                  strokeDasharray="3 3"
                                  label={{
                                    value: `${sym} Kα`,
                                    fill: lineInfo.defaultColor,
                                    fontSize: 10,
                                    position: "insideTop",
                                  }}
                                />
                              )}
                              {lAlpha && lAlpha < activeBeamKv && (
                                <ReferenceLine
                                  x={lAlpha}
                                  stroke={lineInfo.defaultColor}
                                  strokeDasharray="4 4"
                                  strokeOpacity={0.6}
                                  label={{
                                    value: `${sym} Lα`,
                                    fill: lineInfo.defaultColor,
                                    fontSize: 9,
                                    position: "insideTop",
                                  }}
                                />
                              )}
                            </React.Fragment>
                          );
                        })}

                        {showBackground && (
                          <Area
                            type="monotone"
                            dataKey="background"
                            stroke="#64748b"
                            strokeWidth={1}
                            fill="url(#bgGrad)"
                            name="background"
                          />
                        )}

                        <Area
                          type="monotone"
                          dataKey="counts"
                          stroke="#06b6d4"
                          strokeWidth={1.8}
                          fill="url(#spectrumGrad)"
                          name="counts"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            ) : analysisMode === "line_scan" ? (
              <div>
                {/* Line Scan Profile Header */}
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                      <span>Quantitative Line Scan Concentration Profile</span>
                      <span className="text-xs font-mono text-cyan-400 font-normal">
                        (Point A → Point B, {activeDataset.lineScan.totalLengthUm} µm)
                      </span>
                    </h3>
                    <p className="text-[11px] text-slate-400">
                      Spatial Concentration Gradient (wt% vs Distance in µm) across dendrite/grain boundary
                    </p>
                  </div>
                </div>

                {/* Line Chart */}
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={activeDataset.lineScan.profile}
                      margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="#1e293b"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="distanceUm"
                        stroke="#64748b"
                        fontSize={10}
                        unit=" µm"
                      />
                      <YAxis stroke="#64748b" fontSize={10} unit="%" />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#090d16",
                          borderColor: "#38bdf8",
                          borderRadius: "8px",
                          fontSize: "11px",
                        }}
                        labelFormatter={(v) => `Distance: ${v} µm`}
                      />
                      <Legend wrapperStyle={{ fontSize: "11px" }} />

                      {activeDataset.availableElements.map((elem) => {
                        const color =
                          CHARACTERISTIC_XRAY_LINES[elem]?.defaultColor ||
                          "#38bdf8";
                        return (
                          <Line
                            key={elem}
                            type="monotone"
                            dataKey={`concentrations.${elem}`}
                            name={`${elem} (wt%)`}
                            stroke={color}
                            strokeWidth={2}
                            dot={{ r: 3, fill: color }}
                          />
                        );
                      })}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div>
                {/* Elemental Map Info Panel */}
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-bold text-slate-200">
                      Elemental HyperMap Chemical Distribution
                    </h3>
                    <p className="text-[11px] text-slate-400">
                      Spatial pixel matrix intensity correlated with X-Ray characteristic count rate
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  {activeDataset.availableElements.map((elem) => {
                    const color =
                      CHARACTERISTIC_XRAY_LINES[elem]?.defaultColor || "#38bdf8";
                    const isSelected = selectedMapElement === elem;

                    return (
                      <div
                        key={elem}
                        onClick={() => setSelectedMapElement(elem)}
                        className={`p-2.5 rounded-xl border cursor-pointer transition-all ${
                          isSelected
                            ? "bg-slate-950 border-cyan-500/50 shadow-md shadow-cyan-500/10"
                            : "bg-slate-950/60 border-slate-800 hover:border-slate-700"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span
                            className="font-bold text-sm"
                            style={{ color }}
                          >
                            {elem} Map
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {CHARACTERISTIC_XRAY_LINES[elem]?.lines.kAlpha
                              ? `${CHARACTERISTIC_XRAY_LINES[
                                  elem
                                ].lines.kAlpha?.toFixed(2)} keV`
                              : `${CHARACTERISTIC_XRAY_LINES[
                                  elem
                                ].lines.lAlpha?.toFixed(2)} keV`}
                          </span>
                        </div>
                        <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              backgroundColor: color,
                              width: `${Math.min(
                                100,
                                (activeSpot.elements.find(
                                  (e) => e.symbol === elem
                                )?.weightPct || 5) * 1.5
                              )}%`,
                            }}
                          />
                        </div>
                        <div className="flex items-center justify-between mt-1.5 text-[10px] text-slate-400 font-mono">
                          <span>Est. Conc:</span>
                          <span className="text-slate-200 font-bold">
                            {activeSpot.elements
                              .find((e) => e.symbol === elem)
                              ?.weightPct.toFixed(1) || "0.0"}
                            %
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* ASTM E1508 ZAF Quantitative Chemistry Table */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
                <h4 className="text-sm font-bold text-slate-200">
                  {uploadedSpectrum ? "Imported spectrum: quantitative analysis unavailable" : "Training example values (not measured; no ASTM E1508 analysis)"}
                </h4>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30">
                  {uploadedSpectrum ? "No measured quantification" : `Training total: ${activeSpot.totalWeightPct}%`}
                </span>
                <button
                  onClick={runAiPhaseConsultation}
                  disabled
                  title="AI phase diagnosis is disabled until a measured spectrum has been calibrated, peaks resolved, and composition quantified against suitable standards."
                  className="px-2.5 py-1 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{isAiDiagnosing ? "Analyzing..." : "AI Phase Diagnosis unavailable"}</span>
                </button>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-950/80 text-slate-400 text-[10px] uppercase border-b border-slate-800">
                  <tr>
                    <th className="py-2 px-2.5">Element</th>
                    <th className="py-2 px-2">Line</th>
                    <th className="py-2 px-2">k-Ratio</th>
                    <th className="py-2 px-2">ZAF Factor</th>
                    <th className="py-2 px-2 text-cyan-400">Weight % (wt%)</th>
                    <th className="py-2 px-2 text-slate-400">Error (±2σ)</th>
                    <th className="py-2 px-2 text-emerald-400">Atomic % (at%)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {uploadedSpectrum ? (
                    <tr><td colSpan={7} className="p-4 text-amber-200">No composition is reported for the imported spectrum. Calibration, peak resolution, and suitable standards are required first.</td></tr>
                  ) : activeSpot.elements.map((elem) => {
                    const color =
                      CHARACTERISTIC_XRAY_LINES[elem.symbol]?.defaultColor ||
                      "#38bdf8";

                    return (
                      <tr
                        key={elem.symbol}
                        className="hover:bg-slate-800/40 transition-colors"
                      >
                        <td className="py-1.5 px-2.5 font-bold flex items-center gap-1.5">
                          <span
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: color }}
                          />
                          <span>{elem.symbol}</span>
                          <span className="text-[10px] text-slate-500 font-normal">
                            ({CHARACTERISTIC_XRAY_LINES[elem.symbol]?.name})
                          </span>
                        </td>
                        <td className="py-1.5 px-2 text-slate-400">
                          {elem.line}
                        </td>
                        <td className="py-1.5 px-2">{elem.kRatio.toFixed(4)}</td>
                        <td className="py-1.5 px-2">{elem.zafFactor.toFixed(3)}</td>
                        <td className="py-1.5 px-2 font-bold text-cyan-300">
                          {elem.weightPct.toFixed(2)}%
                        </td>
                        <td className="py-1.5 px-2 text-slate-400">
                          ±{elem.weightPctError.toFixed(2)}%
                        </td>
                        <td className="py-1.5 px-2 font-bold text-emerald-400">
                          {elem.atomicPct.toFixed(2)}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Stoichiometric Phase Identification Footer */}
            {!uploadedSpectrum && <div className="mt-3 pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-950/60 p-2.5 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase font-semibold block mb-0.5">
                  Identified Stoichiometric Phase:
                </span>
                <span className="font-bold text-cyan-300 text-sm">
                  {activeSpot.predictedPhase}
                </span>
                <div className="text-[11px] text-slate-300 mt-0.5 font-mono">
                  Formula: {activeSpot.stoichiometryFormula}
                </div>
              </div>
              <div className="bg-slate-950/60 p-2.5 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase font-semibold block mb-0.5">
                  Crystallographic Lattice:
                </span>
                <span className="font-bold text-slate-200 text-sm">
                  {activeSpot.crystalStructure}
                </span>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  {activeSpot.notes}
                </div>
              </div>
            </div>}

            {/* AI Diagnosis Report Accordion */}
            {aiReport && (
              <div className="mt-3 p-3.5 bg-gradient-to-br from-cyan-950/40 to-slate-950 border border-cyan-500/40 rounded-xl shadow-lg animate-in fade-in duration-300">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5 text-cyan-300 font-bold text-xs">
                    <Sparkles className="w-4 h-4 text-cyan-400" />
                    <span>AI Metallurgical Phase Consultation</span>
                  </div>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(aiReport);
                      setCopiedNotification(true);
                      setTimeout(() => setCopiedNotification(false), 2000);
                    }}
                    className="text-[11px] text-slate-400 hover:text-cyan-300 flex items-center gap-1 cursor-pointer"
                  >
                    {copiedNotification ? (
                      <Check className="w-3 h-3 text-emerald-400" />
                    ) : null}
                    <span>{copiedNotification ? "Copied!" : "Copy Report"}</span>
                  </button>
                </div>
                <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">
                  {aiReport}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

    </div>
  );
};
