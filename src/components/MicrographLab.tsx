import React, { useState, useRef, useEffect } from "react";
import {
  Microscope,
  Upload,
  Sparkles,
  Search,
  CheckCircle2,
  AlertTriangle,
  ZoomIn,
  ZoomOut,
  Grid,
  FileText,
  Sliders,
  Maximize2,
  RefreshCw,
  Activity,
  Layers,
  Columns,
  Split,
  Eye,
  Check,
  ArrowRight,
  ShieldCheck,
  X,
  FileUp,
  Image as ImageIcon,
  Copy,
  Table,
  Cpu,
  Zap,
} from "lucide-react";
import { MICROGRAPH_SAMPLES } from "../data/micrographSamples";
import { MicrographSample } from "../types";
import { SEMAutoAnalyzerStudio } from "./SEMAutoAnalyzerStudio";
import { EDSSpectrumLab } from "./EDSSpectrumLab";
import {
  MicrographFindingsTable,
  MetallurgicalSummaryData,
} from "./MicrographFindingsTable";

export const MicrographLab: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<
    "sem_studio" | "eds_studio" | "ai_diagnostic"
  >("sem_studio");
  const [selectedSample, setSelectedSample] = useState<MicrographSample>(
    MICROGRAPH_SAMPLES[0]
  );

  // Upload state
  const [customImage, setCustomImage] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploadedFileSize, setUploadedFileSize] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Metadata inputs
  const [alloyType, setAlloyType] = useState<string>(selectedSample.material);
  const [etchant, setEtchant] = useState<string>(selectedSample.etchant);
  const [magnification, setMagnification] = useState<string>(
    selectedSample.magnification
  );
  const [sampleHistory, setSampleHistory] = useState<string>(
    selectedSample.condition
  );

  // Split-Screen Side-by-Side Reference Comparison
  const [isSplitScreen, setIsSplitScreen] = useState<boolean>(false);
  const [splitReferenceSample, setSplitReferenceSample] =
    useState<MicrographSample>(MICROGRAPH_SAMPLES[0]);

  // High-Contrast Preview Area controls
  const [viewMode, setViewMode] = useState<
    "standard" | "high_contrast" | "darkfield" | "threshold" | "false_color"
  >("standard");
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);
  const [brightness, setBrightness] = useState<number>(100);
  const [contrast, setContrast] = useState<number>(115);
  const [showGrid, setShowGrid] = useState<boolean>(false);
  const [showScaleBar, setShowScaleBar] = useState<boolean>(true);

  // AI Diagnosis & Loading States
  const [isDiagnosing, setIsDiagnosing] = useState<boolean>(false);
  const [diagnosisResult, setDiagnosisResult] = useState<string | null>(null);
  const [summaryTableData, setSummaryTableData] =
    useState<MetallurgicalSummaryData | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeReportTab, setActiveReportTab] = useState<"table" | "narrative">(
    "table"
  );
  const [copied, setCopied] = useState<boolean>(false);

  // Switch sample handler
  const handleSelectSample = (sample: MicrographSample) => {
    setSelectedSample(sample);
    setCustomImage(null);
    setUploadedFileName(null);
    setUploadedFileSize(null);
    setAlloyType(sample.material);
    setEtchant(sample.etchant);
    setMagnification(sample.magnification);
    setSampleHistory(sample.condition);
    setDiagnosisResult(null);
    setSummaryTableData(null);
    setErrorMessage(null);
    setZoomLevel(1.0);
  };

  // Process File
  const processSelectedFile = (file: File) => {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.type)) {
      setErrorMessage("Upload a JPEG, PNG, WebP, or GIF micrograph.");
      return;
    }
    const reader = new FileReader();
    reader.onload = (event) => {
      const base64 = event.target?.result as string;
      setCustomImage(base64);
      setUploadedFileName(file.name);
      setUploadedFileSize(
        file.size > 1024 * 1024
          ? `${(file.size / (1024 * 1024)).toFixed(2)} MB`
          : `${(file.size / 1024).toFixed(1)} KB`
      );
      setDiagnosisResult(null);
      setSummaryTableData(null);
      setErrorMessage(null);
      setSampleHistory("User Uploaded Test Specimen (Batch QA Verification)");
    };
    reader.readAsDataURL(file);
  };

  // Drag & drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processSelectedFile(e.target.files[0]);
    }
  };

  const handleClearUpload = () => {
    setCustomImage(null);
    setUploadedFileName(null);
    setUploadedFileSize(null);
    setDiagnosisResult(null);
    setSummaryTableData(null);
    setAlloyType(selectedSample.material);
    setEtchant(selectedSample.etchant);
    setMagnification(selectedSample.magnification);
    setSampleHistory(selectedSample.condition);
  };

  // Trigger AI diagnosis (indeterminate progress)
  const handleRunDiagnosis = async () => {
    setIsDiagnosing(true);
    setErrorMessage(null);
    setDiagnosisResult(null);
    setSummaryTableData(null);

    const imageToSend = customImage || selectedSample.imageUrl;

    try {
      const res = await fetch("/api/metallurgy/diagnose-micrograph", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          imageBase64: imageToSend,
          mimeType: customImage?.match(/^data:([^;]+);base64,/)?.[1] || "image/svg+xml",
          alloyType,
          etchantUsed: etchant,
          magnification,
          sampleHistory,
          referenceGrade: isSplitScreen
            ? `${splitReferenceSample.material} (${splitReferenceSample.title})`
            : undefined,
        }),
      });

      const rawText = await res.text();
      let data: any = {};
      try {
        data = JSON.parse(rawText);
      } catch {
        throw new Error(
          res.ok
            ? "Invalid diagnosis response from server."
            : `Server error (${res.status}): ${rawText.substring(0, 100)}`
        );
      }

      if (!res.ok) {
        throw new Error(data.error || "Diagnosis failed");
      }

      setDiagnosisResult(data.diagnosis || data.text);

      setSummaryTableData(data.summaryTable || null);
      setActiveReportTab(data.summaryTable ? "table" : "narrative");
    } catch (err: any) {
      console.error(err);
      setErrorMessage(err.message || "Failed to analyze micrograph.");
    } finally {
      setIsDiagnosing(false);
    }
  };

  const handleCopyReport = () => {
    const textToCopy = summaryTableData
      ? `METALLURGICAL DIAGNOSTIC SUMMARY
Alloy Grade: ${summaryTableData.materialGrade}
Compliance: ${summaryTableData.complianceStatus}
Primary Matrix: ${summaryTableData.primaryMatrix}
Secondary Phases: ${summaryTableData.secondaryPhases}
ASTM Grain Size: ${summaryTableData.astmGrainSize}
Defect Rating: ${summaryTableData.defectPorosityRating}
Hardness: ${summaryTableData.estimatedHardness}
Yield Strength: ${summaryTableData.estimatedYieldMpa}

Key Findings:
${summaryTableData.keyFindings.map((f) => `- ${f}`).join("\n")}

Detailed Report:
${diagnosisResult || ""}`
      : diagnosisResult || "";

    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const currentDisplayImage = customImage || selectedSample.imageUrl;

  // View Filter Style Calculation
  const getFilterStyle = () => {
    let base = `brightness(${brightness}%) contrast(${contrast}%)`;
    if (viewMode === "high_contrast") {
      base += " grayscale(100%) contrast(160%) brightness(105%)";
    } else if (viewMode === "darkfield") {
      base += " invert(100%) hue-rotate(180deg) contrast(140%)";
    } else if (viewMode === "threshold") {
      base += " grayscale(100%) contrast(280%) brightness(90%)";
    } else if (viewMode === "false_color") {
      base += " contrast(150%) saturate(220%) hue-rotate(90deg)";
    }
    return base;
  };

  return (
    <div id="micrograph-lab-container" className="space-y-5">
      {/* Top Header & Sub-Tab Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl bg-[#090e18] border border-[#162032]">
        <div>
          <div className="flex items-center gap-2 text-sky-400 font-mono text-[10px] font-semibold uppercase tracking-widest">
            <Microscope className="w-3.5 h-3.5 text-sky-400" />
            AI Quantitative Metallography & Fractography Lab
          </div>
          <h2 className="text-lg font-bold text-white tracking-tight mt-0.5">
            Microstructure & Defect AI Diagnostic Suite
          </h2>
          <p className="text-xs text-slate-400 max-w-2xl mt-0.5">
            Identify constituent phases, grain morphology (ASTM E112), carbide
            networks, micro-inclusions, and failure mechanisms.
          </p>
        </div>

        {/* Sub-tab Switcher */}
        <div className="flex items-center gap-2">
          <div className="flex p-1 bg-[#050810] rounded-xl border border-[#162032] flex-wrap gap-1">
            <button
              type="button"
              onClick={() => setActiveSubTab("sem_studio")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition cursor-pointer ${
                activeSubTab === "sem_studio"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-[0_0_12px_rgba(56,189,248,0.25)]"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-sky-400" />
              <span>Automated SEM Studio</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveSubTab("eds_studio")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition cursor-pointer ${
                activeSubTab === "eds_studio"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_12px_rgba(6,182,212,0.3)]"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Zap className="w-3.5 h-3.5 text-cyan-400" />
              <span>EDS & Chemical Microanalysis</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveSubTab("ai_diagnostic")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition cursor-pointer ${
                activeSubTab === "ai_diagnostic"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-[0_0_12px_rgba(56,189,248,0.25)]"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Columns className="w-3.5 h-3.5" />
              <span>Side-by-Side Comparator</span>
            </button>
          </div>
        </div>
      </div>

      {/* RENDER ACTIVE SUBTAB VIEW */}
      {activeSubTab === "sem_studio" ? (
        <SEMAutoAnalyzerStudio />
      ) : activeSubTab === "eds_studio" ? (
        <EDSSpectrumLab />
      ) : (
        <>
          {/* DRAG-AND-DROP FILE UPLOAD ZONE & PRESETS */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Left: Drag & Drop Zone */}
            <div className="lg:col-span-6">
              <div
                id="micrograph-dropzone"
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`relative p-4 rounded-xl border-2 border-dashed transition cursor-pointer flex flex-col justify-center items-center text-center group ${
                  isDragging
                    ? "border-sky-400 bg-sky-500/10 shadow-[0_0_20px_rgba(56,189,248,0.35)] scale-[1.01]"
                    : customImage
                    ? "border-emerald-500/50 bg-[#060e18]"
                    : "border-[#1e2d46] hover:border-sky-500/50 bg-[#090e18] hover:bg-[#0c1424]"
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  onChange={handleFileInputChange}
                  className="hidden"
                />

                {customImage ? (
                  <div className="w-full flex items-center justify-between gap-3 text-left">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0 overflow-hidden">
                        <img
                          src={customImage}
                          alt="Uploaded Micrograph Thumbnail"
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-emerald-300">
                            Custom Specimen Uploaded
                          </span>
                          <span className="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-mono border border-emerald-500/40">
                            Ready
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5 truncate max-w-[240px]">
                          {uploadedFileName || "micrograph_upload.png"} (
                          {uploadedFileSize || "Calibrated"})
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          fileInputRef.current?.click();
                        }}
                        className="px-2.5 py-1 rounded bg-[#0c1322] hover:bg-white/10 border border-[#1e2d46] text-[11px] font-mono text-sky-400 transition"
                      >
                        Change File
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleClearUpload();
                        }}
                        className="p-1 rounded bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 transition"
                        title="Remove uploaded image and revert to benchmark"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2 py-2">
                    <div className="w-10 h-10 rounded-full bg-sky-500/10 border border-sky-500/30 flex items-center justify-center mx-auto text-sky-400 group-hover:scale-110 transition">
                      <FileUp className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white group-hover:text-sky-300 transition">
                        Drag & drop test micrograph image here, or{" "}
                        <span className="text-sky-400 underline underline-offset-2">
                          browse files
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                        Supports SEM, TEM & optical micrographs (PNG, JPEG, WebP,
                        GIF)
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right: Quick Benchmark Reference Selector */}
            <div className="lg:col-span-6 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest font-semibold">
                  Or Select Standard Benchmark Specimen:
                </span>
                {customImage && (
                  <button
                    onClick={handleClearUpload}
                    className="text-[10px] font-mono text-sky-400 hover:text-sky-300 flex items-center gap-1"
                  >
                    <RefreshCw className="w-3 h-3" /> Revert to Presets
                  </button>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {MICROGRAPH_SAMPLES.slice(0, 6).map((sample) => (
                  <button
                    key={sample.id}
                    onClick={() => handleSelectSample(sample)}
                    className={`p-2 rounded-lg border text-left transition flex flex-col justify-between ${
                      !customImage && selectedSample.id === sample.id
                        ? "bg-sky-500/20 border-sky-400/60 text-sky-300 shadow-[0_0_8px_rgba(56,189,248,0.25)]"
                        : "bg-[#090e18] border-[#162032] text-slate-400 hover:text-white hover:bg-white/[0.03]"
                    }`}
                  >
                    <div className="font-semibold text-xs text-white line-clamp-1">
                      {sample.title.split("(")[0]}
                    </div>
                    <div className="text-[10px] font-mono text-slate-400 mt-0.5 truncate">
                      {sample.magnification} • {sample.material}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* MAIN LAB WORKSPACE */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Left: HIGH-CONTRAST PREVIEW AREA */}
            <div className="lg:col-span-7 bg-[#090e18] rounded-xl border border-[#162032] p-3.5 space-y-3 flex flex-col justify-between">
              {/* Preview Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400 pb-2.5 border-b border-[#162032]">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-white text-xs">
                    {customImage
                      ? `Specimen: ${uploadedFileName || "Uploaded Sample"}`
                      : selectedSample.title}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#0c1322] text-[10px] font-mono text-sky-400 border border-sky-500/30">
                    {magnification}
                  </span>
                  {customImage && (
                    <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-[10px] font-mono text-emerald-300 border border-emerald-500/30">
                      QA Test Batch
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  {/* High Contrast Filter Select */}
                  <select
                    value={viewMode}
                    onChange={(e) => setViewMode(e.target.value as any)}
                    className="px-2 py-1 bg-[#0c1322] border border-[#1e2d46] text-sky-300 rounded font-mono text-[11px] focus:outline-none focus:border-sky-400"
                    title="Select High-Contrast Optical Enhancement Filter"
                  >
                    <option value="standard">Natural View</option>
                    <option value="high_contrast">High-Contrast Mono</option>
                    <option value="darkfield">Darkfield / Polarity Invert</option>
                    <option value="threshold">Phase Boundary Threshold</option>
                    <option value="false_color">False-Color Heatmap</option>
                  </select>

                  {/* Split Screen Toggle */}
                  <button
                    type="button"
                    onClick={() => setIsSplitScreen(!isSplitScreen)}
                    className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono font-bold border transition ${
                      isSplitScreen
                        ? "bg-sky-500/20 border-sky-400/50 text-sky-300 shadow-[0_0_10px_rgba(56,189,248,0.25)]"
                        : "bg-[#0c1322] border-[#162032] text-slate-400 hover:text-white"
                    }`}
                    title="Toggle Split-Screen Side-by-Side Reference Comparison"
                  >
                    <Columns className="w-3.5 h-3.5" />
                    <span>{isSplitScreen ? "Side-by-Side" : "Split"}</span>
                  </button>

                  <button
                    onClick={() => setShowGrid(!showGrid)}
                    className={`p-1.5 rounded border transition ${
                      showGrid
                        ? "bg-sky-500/20 border-sky-400/50 text-sky-300 shadow-[0_0_8px_rgba(56,189,248,0.3)]"
                        : "bg-[#0c1322] border-[#162032] text-slate-400 hover:text-white"
                    }`}
                    title="Toggle ASTM Reticle Intercept Grid"
                  >
                    <Grid className="w-3.5 h-3.5" />
                  </button>

                  <button
                    onClick={() => {
                      setZoomLevel(1.0);
                      setBrightness(100);
                      setContrast(115);
                      setViewMode("standard");
                    }}
                    className="p-1.5 rounded bg-[#0c1322] border border-[#162032] text-slate-400 hover:text-white hover:bg-white/5 transition"
                    title="Reset Image Adjustments"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Reference Grade Selector Bar (When Split Screen Active) */}
              {isSplitScreen && (
                <div className="p-2 rounded-lg bg-[#050810] border border-sky-900/40 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span className="text-slate-300 font-bold text-[11px]">
                      Standard Reference Benchmark:
                    </span>
                  </div>
                  <select
                    value={splitReferenceSample.id}
                    onChange={(e) => {
                      const s = MICROGRAPH_SAMPLES.find(
                        (item) => item.id === e.target.value
                      );
                      if (s) setSplitReferenceSample(s);
                    }}
                    className="px-2 py-0.5 bg-[#0c1322] border border-[#1e2d46] text-sky-300 rounded font-mono text-[11px] focus:outline-none focus:border-sky-400"
                  >
                    {MICROGRAPH_SAMPLES.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.title} ({s.material})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* High-Contrast Preview Viewport (Single or Split) */}
              {isSplitScreen ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {/* Left Column: Test Specimen */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] font-mono px-1">
                      <span className="text-sky-300 font-bold flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-sky-400"></span>
                        <span>Test Specimen</span>
                      </span>
                      <span className="text-slate-400 text-[10px]">
                        {customImage ? "Uploaded Image" : selectedSample.material}
                      </span>
                    </div>
                    <div className="w-full aspect-[4/3] rounded-lg bg-[#020408] border border-[#162032] relative overflow-hidden flex items-center justify-center shadow-inner">
                      <div
                        className="w-full h-full flex items-center justify-center transition-all duration-150"
                        style={{
                          transform: `scale(${zoomLevel})`,
                          filter: getFilterStyle(),
                        }}
                      >
                        <img
                          src={currentDisplayImage}
                          alt="Test Micrograph"
                          referrerPolicy="no-referrer"
                          className="max-w-full max-h-full object-contain select-none"
                        />
                      </div>

                      {/* AI Scanning Line Animation when diagnosing */}
                      {isDiagnosing && (
                        <div className="absolute inset-0 pointer-events-none overflow-hidden">
                          <div className="w-full h-1 bg-gradient-to-r from-transparent via-sky-400 to-transparent shadow-[0_0_12px_#38bdf8] animate-laserScan"></div>
                          <div className="absolute inset-0 bg-sky-500/10 backdrop-blur-[0.5px]"></div>
                        </div>
                      )}

                      {showGrid && (
                        <div className="absolute inset-0 pointer-events-none grid grid-cols-4 grid-rows-4 border border-sky-400/30">
                          {Array.from({ length: 16 }).map((_, i) => (
                            <div
                              key={i}
                              className="border border-sky-400/20 relative"
                            />
                          ))}
                        </div>
                      )}

                      {/* High Contrast Mode Pill */}
                      {viewMode !== "standard" && (
                        <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/80 border border-sky-500/40 text-[9px] font-mono text-sky-300 uppercase">
                          {viewMode.replace("_", " ")}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right Column: Database Reference Microstructure */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] font-mono px-1">
                      <span className="text-emerald-400 font-bold flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                        <span>Standard Reference</span>
                      </span>
                      <span className="text-slate-400 text-[10px] truncate max-w-[140px]">
                        {splitReferenceSample.material}
                      </span>
                    </div>
                    <div className="w-full aspect-[4/3] rounded-lg bg-[#020408] border border-emerald-900/40 relative overflow-hidden flex items-center justify-center shadow-inner">
                      <div
                        className="w-full h-full flex items-center justify-center transition-all duration-150"
                        style={{
                          transform: `scale(${zoomLevel})`,
                          filter: getFilterStyle(),
                        }}
                      >
                        <img
                          src={splitReferenceSample.imageUrl}
                          alt="Reference Micrograph"
                          referrerPolicy="no-referrer"
                          className="max-w-full max-h-full object-contain select-none"
                        />
                      </div>

                      {showGrid && (
                        <div className="absolute inset-0 pointer-events-none grid grid-cols-4 grid-rows-4 border border-emerald-400/30">
                          {Array.from({ length: 16 }).map((_, i) => (
                            <div
                              key={i}
                              className="border border-emerald-400/20 relative"
                            />
                          ))}
                        </div>
                      )}

                      <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-black/80 border border-emerald-500/40 text-[9px] font-mono text-emerald-300">
                        Grade: {splitReferenceSample.material}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="w-full aspect-[4/3] rounded-lg bg-[#020408] border border-[#162032] relative overflow-hidden flex items-center justify-center shadow-inner">
                  {/* The Image Canvas with Filter Enhancement */}
                  <div
                    className="w-full h-full flex items-center justify-center transition-all duration-150"
                    style={{
                      transform: `scale(${zoomLevel})`,
                      filter: getFilterStyle(),
                    }}
                  >
                    <img
                      src={currentDisplayImage}
                      alt="Metallurgical Micrograph"
                      className="max-w-full max-h-full object-contain select-none"
                    />
                  </div>

                  {/* AI Scanning Laser Effect */}
                  {isDiagnosing && (
                    <div className="absolute inset-0 pointer-events-none overflow-hidden">
                      <div className="w-full h-1 bg-gradient-to-r from-transparent via-sky-400 to-transparent shadow-[0_0_16px_#38bdf8] animate-laserScan"></div>
                      <div className="absolute inset-0 bg-sky-500/10 backdrop-blur-[0.5px]"></div>
                      <div className="absolute bottom-3 left-3 px-3 py-1.5 rounded-lg bg-black/90 border border-sky-500/40 text-xs font-mono text-sky-300 flex items-center gap-2">
                        <Cpu className="w-3.5 h-3.5 text-sky-400 animate-spin" />
                        <span>AI Scanning Grain Boundaries & Phase Fractions...</span>
                      </div>
                    </div>
                  )}

                  {/* ASTM Grain Sizing Reticle Overlay */}
                  {showGrid && (
                    <div className="absolute inset-0 pointer-events-none grid grid-cols-6 grid-rows-6 border border-sky-400/30">
                      {Array.from({ length: 36 }).map((_, i) => (
                        <div
                          key={i}
                          className="border border-sky-400/20 relative"
                        >
                          <span className="absolute top-0.5 left-0.5 text-[8px] font-mono text-sky-400/60">
                            {i + 1}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Calibrated Scale Bar Overlay */}
                  {showScaleBar && (
                    <div className="absolute bottom-3 right-3 bg-black/85 border border-white/20 px-2.5 py-1 rounded backdrop-blur-sm pointer-events-none flex flex-col items-end">
                      <div className="w-16 h-1 bg-white shadow-[0_0_4px_rgba(255,255,255,0.8)] mb-0.5"></div>
                      <span className="text-[9px] font-mono text-slate-200">
                        {magnification.includes("1000") ||
                        magnification.includes("2000")
                          ? "10 µm"
                          : magnification.includes("500")
                          ? "20 µm"
                          : "50 µm"}
                      </span>
                    </div>
                  )}

                  {/* Active Filter Badge */}
                  {viewMode !== "standard" && (
                    <div className="absolute top-3 left-3 px-2.5 py-1 rounded bg-black/85 border border-sky-500/50 text-[10px] font-mono text-sky-300 uppercase shadow-md flex items-center gap-1.5">
                      <Eye className="w-3 h-3 text-sky-400" />
                      <span>{viewMode.replace("_", " ")}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Adjustments Sliders Bar */}
              <div className="grid grid-cols-3 gap-3 pt-1 text-xs text-slate-400">
                <div>
                  <div className="flex justify-between text-[11px] mb-1 font-mono">
                    <span>Magnification Zoom</span>
                    <span className="text-sky-400 font-bold">
                      {zoomLevel.toFixed(1)}x
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1.0"
                    max="2.5"
                    step="0.1"
                    value={zoomLevel}
                    onChange={(e) => setZoomLevel(parseFloat(e.target.value))}
                    className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1 font-mono">
                    <span>Brightness</span>
                    <span className="text-sky-400 font-bold">{brightness}%</span>
                  </div>
                  <input
                    type="range"
                    min="60"
                    max="150"
                    step="5"
                    value={brightness}
                    onChange={(e) => setBrightness(parseInt(e.target.value))}
                    className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1 font-mono">
                    <span>Contrast / Reticle</span>
                    <span className="text-sky-400 font-bold">{contrast}%</span>
                  </div>
                  <input
                    type="range"
                    min="60"
                    max="180"
                    step="5"
                    value={contrast}
                    onChange={(e) => setContrast(parseInt(e.target.value))}
                    className="w-full accent-sky-400 bg-[#0c1322] cursor-pointer"
                  />
                </div>
              </div>
            </div>

            {/* Right: Metadata Inputs & AI Diagnostic Report / Summary Table */}
            <div className="lg:col-span-5 space-y-3.5 flex flex-col justify-between">
              {/* Metadata Context Inputs */}
              <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-2.5">
                <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold block">
                  Sample Context & Metallographic Metadata
                </span>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <label className="text-slate-400 mb-1 block">
                      Alloy Category / Name
                    </label>
                    <input
                      type="text"
                      value={alloyType}
                      onChange={(e) => setAlloyType(e.target.value)}
                      className="w-full px-2.5 py-1 bg-[#0c1322] border border-[#162032] rounded text-white font-mono text-xs focus:outline-none focus:border-sky-400"
                    />
                  </div>

                  <div>
                    <label className="text-slate-400 mb-1 block">
                      Etchant Reagent
                    </label>
                    <input
                      type="text"
                      value={etchant}
                      onChange={(e) => setEtchant(e.target.value)}
                      className="w-full px-2.5 py-1 bg-[#0c1322] border border-[#162032] rounded text-white font-mono text-xs focus:outline-none focus:border-sky-400"
                    />
                  </div>

                  <div>
                    <label className="text-slate-400 mb-1 block">
                      Magnification / SEM
                    </label>
                    <input
                      type="text"
                      value={magnification}
                      onChange={(e) => setMagnification(e.target.value)}
                      className="w-full px-2.5 py-1 bg-[#0c1322] border border-[#162032] rounded text-white font-mono text-xs focus:outline-none focus:border-sky-400"
                    />
                  </div>

                  <div>
                    <label className="text-slate-400 mb-1 block">
                      Heat Treatment State
                    </label>
                    <input
                      type="text"
                      value={sampleHistory}
                      onChange={(e) => setSampleHistory(e.target.value)}
                      className="w-full px-2.5 py-1 bg-[#0c1322] border border-[#162032] rounded text-white font-mono text-xs focus:outline-none focus:border-sky-400"
                    />
                  </div>
                </div>

                {/* Run Diagnosis Button */}
                <button
                  id="run-ai-micrograph-diagnosis-btn"
                  onClick={handleRunDiagnosis}
                  disabled={isDiagnosing || !customImage}
                  className="w-full py-2.5 px-3 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold rounded text-xs flex items-center justify-center gap-2 shadow-[0_0_12px_rgba(56,189,248,0.3)] transition disabled:opacity-50"
                >
                  {isDiagnosing ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></div>
                      <span>Analyzing Microstructure with AI...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Describe Uploaded Micrograph</span>
                    </>
                  )}
                </button>
                {!customImage && <p className="mt-2 text-xs text-slate-400">Upload a real micrograph to analyze it. The built-in SVG specimens are illustrations.</p>}
              </div>

              {/* Diagnosis Output Card / Loading State / Findings Table */}
              <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] flex-1 flex flex-col justify-between overflow-hidden">
                {/* Card Header with View Switcher */}
                <div className="flex items-center justify-between pb-2 border-b border-[#162032]">
                  <div className="flex items-center gap-2">
                    <FileText className="w-3.5 h-3.5 text-sky-400" />
                    <span className="text-xs font-mono font-bold text-slate-200">
                      Metallurgical Diagnostic Report
                    </span>
                  </div>

                  {/* Switch between Summary Table and Narrative Report */}
                  {summaryTableData && (
                    <div className="flex p-0.5 bg-[#050810] rounded-lg border border-[#162032] text-[10px] font-mono">
                      <button
                        onClick={() => setActiveReportTab("table")}
                        className={`px-2 py-0.5 rounded transition flex items-center gap-1 ${
                          activeReportTab === "table"
                            ? "bg-sky-500/20 text-sky-300 font-bold"
                            : "text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        <Table className="w-3 h-3" />
                        <span>Summary Table</span>
                      </button>
                      <button
                        onClick={() => setActiveReportTab("narrative")}
                        className={`px-2 py-0.5 rounded transition flex items-center gap-1 ${
                          activeReportTab === "narrative"
                            ? "bg-sky-500/20 text-sky-300 font-bold"
                            : "text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        <FileText className="w-3 h-3" />
                        <span>Full Report</span>
                      </button>
                    </div>
                  )}
                </div>

                {/* Content Area */}
                <div className="mt-2.5 text-xs text-slate-300 leading-relaxed overflow-y-auto max-h-[380px] pr-1 space-y-2.5">
                  {errorMessage && (
                    <div className="p-2.5 bg-rose-950/40 border border-rose-800/80 rounded text-rose-200 text-xs flex items-start gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
                      <span>{errorMessage}</span>
                    </div>
                  )}

                  {/* MULTI-STAGE LOADING STATE */}
                  {isDiagnosing ? (
                    <div className="py-6 px-3 space-y-4">
                      {/* Indeterminate state: the server reports no progress, so none is shown. */}
                      <div role="status" className="p-2.5 rounded-lg border bg-sky-500/10 border-sky-400/50">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="w-3.5 h-3.5 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
                            <span className="text-xs font-mono font-bold text-sky-300">Running micrograph diagnosis</span>
                          </div>
                          <span className="text-[10px] font-mono text-sky-400 font-bold">Running</span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-1 pl-5 font-sans">
                          Waiting for the server response. Progress is not reported.
                        </p>
                      </div>

                      {/* Shimmer Skeleton preview */}
                      <div className="space-y-2 pt-2 animate-pulse">
                        <div className="h-3 bg-white/5 rounded w-3/4"></div>
                        <div className="h-3 bg-white/5 rounded w-full"></div>
                        <div className="h-3 bg-white/5 rounded w-5/6"></div>
                      </div>
                    </div>
                  ) : diagnosisResult ? (
                    /* RESULTS DISPLAY (Summary Table OR Full Narrative) */
                    activeReportTab === "table" ? (
                      <MicrographFindingsTable
                        summary={summaryTableData}
                        detailedReport={diagnosisResult}
                        onCopyReport={handleCopyReport}
                        copied={copied}
                      />
                    ) : (
                      <div className="space-y-3">
                        <div className="flex justify-end">
                          <button
                            onClick={handleCopyReport}
                            className="px-2 py-1 rounded bg-[#0c1322] hover:bg-white/10 border border-[#1e2d46] text-[11px] font-mono text-slate-300 hover:text-white transition flex items-center gap-1.5"
                          >
                            {copied ? (
                              <>
                                <Check className="w-3 h-3 text-emerald-400" />
                                <span className="text-emerald-300">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-3 h-3 text-slate-400" />
                                <span>Copy Text</span>
                              </>
                            )}
                          </button>
                        </div>
                        <div className="prose prose-invert prose-xs max-w-none text-slate-200 space-y-2 whitespace-pre-line font-sans">
                          {diagnosisResult}
                        </div>
                      </div>
                    )
                  ) : (
                    /* Initial default state */
                    <div className="space-y-2.5 text-slate-400 py-1">
                      <div className="font-semibold text-slate-300 font-mono text-[11px]">
                        Default Specimen Metallography:
                      </div>
                      <ul className="space-y-1 pl-4 list-disc text-slate-300">
                        {selectedSample.keyFeatures.map((feat, idx) => (
                          <li key={idx}>{feat}</li>
                        ))}
                      </ul>
                      <p className="text-[11px] text-slate-500 pt-2 border-t border-[#162032]">
                        Upload a real micrograph for a visual description. The built-in specimens are illustrations; this analysis does not establish phase fractions, ASTM grain size, or conformance.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
