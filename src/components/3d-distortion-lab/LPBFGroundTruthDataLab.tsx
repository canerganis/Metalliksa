import { ResponsiveContainer } from '../VisibleResponsiveContainer';
import React, { useState, useMemo, useEffect } from "react";
import {
  Database,
  Layers,
  Zap,
  Activity,
  ShieldCheck,
  AlertTriangle,
  Info,
  Download,
  Plus,
  Filter,
  CheckCircle2,
  ExternalLink,
  BookOpen,
  Sliders,
  Scale,
  Sparkles,
  RefreshCw,
  Trash2,
  ArrowRight,
  GitFork,
  FileSpreadsheet,
  Share2,
} from "lucide-react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip as RechartsTooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";
import {
  TraceableLPBFRecord,
  LPBFAlloyId,
  ProcessRegime,
  calculateLinearEnergyDensity,
  calculateArealEnergyDensity,
  calculateVolumetricEnergyDensity,
  calculatePeakLaserIntensity,
  calculateNormalizedEnthalpy,
  classifyProcessRegime,
  ALLOY_THERMAL_PROPERTIES,
} from "../../types/lpbfDataFoundation";
import {
  MASTER_LPBF_REFERENCE_DATASETS,
  loadUserLPBFRecords,
  saveUserLPBFRecords,
} from "../../data/lpbfReferenceDatasets";
import { useMaterialSpecimenStore } from "../../store/useMaterialSpecimenStore";
import {
  evaluateLiteraturePvWindow,
  heatTreatmentCohorts,
  orientationCohorts,
} from "../../utils/lpbfFourAlloySchema";

export interface LPBFGroundTruthDataLabProps {
  onApplyParametersToSimulation?: (params: {
    power_W: number;
    speed_mms: number;
    hatch_um: number;
    layer_um: number;
    beam_um?: number;
    doi?: string;
    material: string;
  }) => void;
}

type ActiveViewTab = "datasets" | "derived-quantities" | "schema-builder" | "ved-limitations";

export const LPBFGroundTruthDataLab: React.FC<LPBFGroundTruthDataLabProps> = ({
  onApplyParametersToSimulation,
}) => {
  const [activeTab, setActiveTab] = useState<ActiveViewTab>("datasets");
  const [selectedAlloy, setSelectedAlloy] = useState<LPBFAlloyId>("ti6al4v");
  const [regimeFilter, setRegimeFilter] = useState<string>("all");
  const [userRecords, setUserRecords] = useState<TraceableLPBFRecord[]>([]);
  const [selectedRecord, setSelectedRecord] = useState<TraceableLPBFRecord | null>(null);
  const [syncNotice, setSyncNotice] = useState<string | null>(null);

  // Load user records on mount and seed calculator/form from Build Job store
  useEffect(() => {
    const saved = loadUserLPBFRecords();
    setUserRecords(saved);
    const lpbf = useMaterialSpecimenStore.getState().activeSpecimen.lpbf;
    setCalcPower_W(lpbf.laserPower_W);
    setCalcSpeed_mm_s(lpbf.scanSpeed_mms);
    setCalcHatch_um(lpbf.hatch_um);
    setCalcLayer_um(lpbf.layer_um);
    setCalcSpot_um(lpbf.beamDiameter_um);
    setCalcAbsorptivity(lpbf.laserAbsorptivity);
    setFormPower(lpbf.laserPower_W);
    setFormSpeed(lpbf.scanSpeed_mms);
    setFormHatch(lpbf.hatch_um);
    setFormLayer(lpbf.layer_um);
    setFormSpot(lpbf.beamDiameter_um);
    if (lpbf.specimenDoi) setFormDoi(lpbf.specimenDoi);
  }, []);

  // Derived Quantities Interactive Sandbox State
  const [calcPower_W, setCalcPower_W] = useState<number>(200);
  const [calcSpeed_mm_s, setCalcSpeed_mm_s] = useState<number>(900);
  const [calcHatch_um, setCalcHatch_um] = useState<number>(100);
  const [calcLayer_um, setCalcLayer_um] = useState<number>(30);
  const [calcSpot_um, setCalcSpot_um] = useState<number>(80);
  const [calcAbsorptivity, setCalcAbsorptivity] = useState<number>(0.42);

  // Iso-VED Comparison State (Set A vs Set B for VED Fallacy demonstration)
  const [isoVedA_Power, setIsoVedA_Power] = useState<number>(300);
  const [isoVedA_Speed, setIsoVedA_Speed] = useState<number>(1500);
  const [isoVedA_Spot, setIsoVedA_Spot] = useState<number>(50);

  const [isoVedB_Power, setIsoVedB_Power] = useState<number>(100);
  const [isoVedB_Speed, setIsoVedB_Speed] = useState<number>(500);
  const [isoVedB_Spot, setIsoVedB_Spot] = useState<number>(120);

  const isoHatch_um = 100;
  const isoLayer_um = 30;

  // Form State for Adding a New Traceable Record
  const [formBuildJob, setFormBuildJob] = useState<string>("QUAL-RUN-2026-01");
  const [formMachine, setFormMachine] = useState<string>("EOS M290");
  const [formPower, setFormPower] = useState<number>(220);
  const [formSpeed, setFormSpeed] = useState<number>(950);
  const [formHatch, setFormHatch] = useState<number>(100);
  const [formLayer, setFormLayer] = useState<number>(30);
  const [formSpot, setFormSpot] = useState<number>(80);
  const [formStrategy, setFormStrategy] = useState<any>("Meander (67° alternating rotation)");
  const [formSampleCode, setFormSampleCode] = useState<string>("SPEC-EXP-001");
  const [formOrientation, setFormOrientation] = useState<0 | 45 | 90>(0);
  const [formHeatTreatment, setFormHeatTreatment] = useState<any>("As-Built");
  const [formDensityPct, setFormDensityPct] = useState<number>(99.82);
  const [formUTS, setFormUTS] = useState<number>(1210);
  const [formYield, setFormYield] = useState<number>(1080);
  const [formElongation, setFormElongation] = useState<number>(8.5);
  const [formHardness, setFormHardness] = useState<number>(375);
  const [formCitation, setFormCitation] = useState<string>("In-house ASTM E8 qualification test");
  const [formDoi, setFormDoi] = useState<string>("10.1016/j.actamat.2026.internal");
  const [formStandard, setFormStandard] = useState<string>("ASTM B962 / ASTM E8");
  const [formPowderLot, setFormPowderLot] = useState<string>("");
  const [formPowderD10, setFormPowderD10] = useState<string>("");
  const [formPowderD50, setFormPowderD50] = useState<string>("");
  const [formPowderD90, setFormPowderD90] = useState<string>("");

  // Filtered dataset combining literature + user records for selected alloy
  const activeDataset = useMemo(() => {
    const litRecords = MASTER_LPBF_REFERENCE_DATASETS[selectedAlloy] || [];
    const customRecords = userRecords.filter((r) => r.build.alloyId === selectedAlloy);
    const combined = [...litRecords, ...customRecords];

    if (regimeFilter === "all") return combined;
    return combined.filter((r) => r.params.derived.predictedRegime === regimeFilter);
  }, [selectedAlloy, userRecords, regimeFilter]);

  const schemaPanels = useMemo(() => {
    const lpbf = useMaterialSpecimenStore.getState().activeSpecimen.lpbf;
    return {
      window: evaluateLiteraturePvWindow(selectedAlloy, lpbf.laserPower_W, lpbf.scanSpeed_mms),
      ht: heatTreatmentCohorts(selectedAlloy),
      ori: orientationCohorts(selectedAlloy),
    };
  }, [selectedAlloy, userRecords]);

  // Scatter chart data formatted for Recharts
  const scatterData = useMemo(() => {
    return activeDataset.map((r) => ({
      name: r.sample.sampleCode,
      ved: r.params.derived.volumetricEnergyDensity_J_mm3,
      density: r.properties.relativeDensity_pct,
      porosity: r.properties.porosity_pct,
      uts: r.properties.ultimateTensileStrength_MPa || 0,
      elongation: r.properties.elongationAtBreak_pct || 0,
      hardness: r.properties.hardness_value || 0,
      led: r.params.derived.linearEnergyDensity_J_mm,
      aed: r.params.derived.arealEnergyDensity_J_mm2,
      power: r.params.laserPower_W,
      speed: r.params.scanSpeed_mm_s,
      ht: r.sample.heatTreatment,
      ori: r.sample.buildOrientationDeg,
      regime: r.params.derived.predictedRegime,
      record: r,
    }));
  }, [activeDataset]);

  // Real-time calculations for Sandbox
  const sandboxCalculations = useMemo(() => {
    const led = calculateLinearEnergyDensity(calcPower_W, calcSpeed_mm_s);
    const aed = calculateArealEnergyDensity(calcPower_W, calcSpeed_mm_s, calcHatch_um);
    const ved = calculateVolumetricEnergyDensity(calcPower_W, calcSpeed_mm_s, calcHatch_um, calcLayer_um);
    const intensity = calculatePeakLaserIntensity(calcPower_W, calcSpot_um);
    const normalizedEnthalpy = calculateNormalizedEnthalpy(
      calcPower_W,
      calcSpeed_mm_s,
      calcSpot_um,
      selectedAlloy,
      calcAbsorptivity
    );
    const regime = classifyProcessRegime(ved, calcPower_W, calcSpeed_mm_s, selectedAlloy);

    return { led, aed, ved, intensity, normalizedEnthalpy, regime };
  }, [calcPower_W, calcSpeed_mm_s, calcHatch_um, calcLayer_um, calcSpot_um, selectedAlloy, calcAbsorptivity]);

  // Iso-VED calculations
  const isoComparison = useMemo(() => {
    const vedA = calculateVolumetricEnergyDensity(isoVedA_Power, isoVedA_Speed, isoHatch_um, isoLayer_um);
    const vedB = calculateVolumetricEnergyDensity(isoVedB_Power, isoVedB_Speed, isoHatch_um, isoLayer_um);

    const ledA = calculateLinearEnergyDensity(isoVedA_Power, isoVedA_Speed);
    const ledB = calculateLinearEnergyDensity(isoVedB_Power, isoVedB_Speed);

    const aedA = calculateArealEnergyDensity(isoVedA_Power, isoVedA_Speed, isoHatch_um);
    const aedB = calculateArealEnergyDensity(isoVedB_Power, isoVedB_Speed, isoHatch_um);

    const intA = calculatePeakLaserIntensity(isoVedA_Power, isoVedA_Spot);
    const intB = calculatePeakLaserIntensity(isoVedB_Power, isoVedB_Spot);

    const nthA = calculateNormalizedEnthalpy(isoVedA_Power, isoVedA_Speed, isoVedA_Spot, selectedAlloy);
    const nthB = calculateNormalizedEnthalpy(isoVedB_Power, isoVedB_Speed, isoVedB_Spot, selectedAlloy);

    // Interaction time t_dwell = d_spot / v (microseconds)
    const dwellA_us = (isoVedA_Spot / Math.max(1, isoVedA_Speed)) * 1000;
    const dwellB_us = (isoVedB_Spot / Math.max(1, isoVedB_Speed)) * 1000;

    return {
      vedA,
      vedB,
      ledA,
      ledB,
      aedA,
      aedB,
      intA,
      intB,
      nthA,
      nthB,
      dwellA_us: Number(dwellA_us.toFixed(1)),
      dwellB_us: Number(dwellB_us.toFixed(1)),
    };
  }, [isoVedA_Power, isoVedA_Speed, isoVedA_Spot, isoVedB_Power, isoVedB_Speed, isoVedB_Spot, selectedAlloy]);

  // Add custom record handler
  const handleAddRecord = (e: React.FormEvent) => {
    e.preventDefault();
    const newId = `usr-${Date.now()}`;
    const led = calculateLinearEnergyDensity(formPower, formSpeed);
    const aed = calculateArealEnergyDensity(formPower, formSpeed, formHatch);
    const ved = calculateVolumetricEnergyDensity(formPower, formSpeed, formHatch, formLayer);
    const intensity = calculatePeakLaserIntensity(formPower, formSpot);
    const normalizedEnthalpy = calculateNormalizedEnthalpy(formPower, formSpeed, formSpot, selectedAlloy);
    const regime = classifyProcessRegime(ved, formPower, formSpeed, selectedAlloy);

    const newRec: TraceableLPBFRecord = {
      id: newId,
      build: {
        id: `bld-${newId}`,
        buildJobName: formBuildJob,
        alloyId: selectedAlloy,
        alloyName:
          selectedAlloy === "ti6al4v"
            ? "Ti-6Al-4V Grade 5"
            : selectedAlloy === "ss316l"
            ? "316L Stainless Steel"
            : "AlSi10Mg Aluminum",
        machineModel: formMachine,
        powderLotNumber: formPowderLot.trim() || "Not recorded",
        powderAtomization: "Gas Atomized (GA)",
        powderD10_um: formPowderD10.trim() ? Number(formPowderD10) : 0,
        powderD50_um: formPowderD50.trim() ? Number(formPowderD50) : 0,
        powderD90_um: formPowderD90.trim() ? Number(formPowderD90) : 0,
        buildDate: new Date().toISOString().split("T")[0],
        facility: "User Additive Laboratory",
      },
      params: {
        id: `par-${newId}`,
        laserPower_W: formPower,
        scanSpeed_mm_s: formSpeed,
        hatchSpacing_um: formHatch,
        layerThickness_um: formLayer,
        beamSpotDiameter_um: formSpot,
        scanStrategy: formStrategy,
        baseplatePreheat_C: selectedAlloy === "alsi10mg" ? 150 : 35,
        chamberAtmosphere: "Argon 99.999% (<100 ppm O2)",
        opticalAbsorptivity: ALLOY_THERMAL_PROPERTIES[selectedAlloy].defaultAbsorptivity,
        derived: {
          linearEnergyDensity_J_mm: led,
          arealEnergyDensity_J_mm2: aed,
          volumetricEnergyDensity_J_mm3: ved,
          peakLaserIntensity_MW_cm2: intensity,
          normalizedEnthalpy_dH_hs: normalizedEnthalpy,
          predictedRegime: regime,
        },
      },
      sample: {
        id: `smp-${newId}`,
        sampleCode: formSampleCode,
        locationOnPlate: { x_mm: 50, y_mm: 50, z_mm: 0 },
        buildOrientationDeg: formOrientation,
        heatTreatment: formHeatTreatment,
        specimenGeometry: "Cylindrical Tensile (ASTM E8)",
      },
      properties: {
        id: `prp-${newId}`,
        relativeDensity_pct: formDensityPct,
        porosity_pct: Number((100 - formDensityPct).toFixed(2)),
        densityMeasurementMethod: "Archimedes (ASTM B962)",
        yieldStrength_MPa: formYield,
        ultimateTensileStrength_MPa: formUTS,
        elongationAtBreak_pct: formElongation,
        hardness_value: formHardness,
        hardness_scale: "HV0.5",
        defectMorphology: formDensityPct > 99.7 ? "Dense (<0.1% pores)" : "Lack of Fusion (irregular, un-melted powder)",
      },
      source: {
        id: `src-${newId}`,
        sourceType: "experimental",
        citation: formCitation,
        title: `Validation build ${formSampleCode}`,
        authors: "Internal User Metallurgist",
        journal: "Internal Test Report",
        year: 2026,
        doi: formDoi,
        url: formDoi.startsWith("10.") ? `https://doi.org/${formDoi}` : undefined,
        testingStandards: formStandard.split("/").map((s) => s.trim()),
        labOrganization: "MetalliX User Lab",
      },
    };

    const updated = [newRec, ...userRecords];
    setUserRecords(updated);
    saveUserLPBFRecords(updated);
    setSelectedRecord(newRec);
    useMaterialSpecimenStore.getState().updateLpbfProcess({
      laserPower_W: formPower,
      scanSpeed_mms: formSpeed,
      hatch_um: formHatch,
      layer_um: formLayer,
      beamDiameter_um: formSpot,
      specimenDoi: formDoi,
    });
    setSyncNotice(`✅ Record ${formSampleCode} saved with 5-tier traceability!`);
    setTimeout(() => setSyncNotice(null), 4000);
  };

  // Sync chosen record to digital twin or active specimen
  const handleSyncToSpecimenStore = (rec: TraceableLPBFRecord) => {
    const activeSpecimen = useMaterialSpecimenStore.getState().activeSpecimen;
    if (activeSpecimen) {
      useMaterialSpecimenStore.getState().setSpecimen({
        uts_25C_MPa: rec.properties.ultimateTensileStrength_MPa || activeSpecimen.uts_25C_MPa,
        yieldStrength_25C_MPa: rec.properties.yieldStrength_MPa || activeSpecimen.yieldStrength_25C_MPa,
        elongation_pct: rec.properties.elongationAtBreak_pct || activeSpecimen.elongation_pct,
        lpbf: {
          ...activeSpecimen.lpbf,
          recommendedLaserPower_W: rec.params.laserPower_W,
          recommendedScanSpeed_mms: rec.params.scanSpeed_mm_s,
          recommendedHatch_um: rec.params.hatchSpacing_um,
          recommendedLayer_um: rec.params.layerThickness_um,
          laserPower_W: rec.params.laserPower_W,
          scanSpeed_mms: rec.params.scanSpeed_mm_s,
          hatch_um: rec.params.hatchSpacing_um,
          layer_um: rec.params.layerThickness_um,
          beamDiameter_um: rec.params.beamSpotDiameter_um,
          preheatTemp_C: rec.params.baseplatePreheat_C,
          specimenDoi: rec.source.doi,
        },
      });
      setSyncNotice(`Pushed ${rec.sample.sampleCode} to Active Specimen & Digital Twin!`);
      setTimeout(() => setSyncNotice(null), 4000);
    }
  };

  // Export dataset as JSON
  const handleExportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(activeDataset, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `LPBF_GroundTruth_${selectedAlloy}_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  // Export dataset as CSV
  const handleExportCSV = () => {
    const headers = [
      "Record ID",
      "Alloy",
      "Sample Code",
      "Laser Power (W)",
      "Scan Speed (mm/s)",
      "Hatch Spacing (um)",
      "Layer Thickness (um)",
      "Linear Energy Density (J/mm)",
      "Areal Energy Density (J/mm2)",
      "Volumetric Energy Density (J/mm3)",
      "Predicted Regime",
      "Relative Density (%)",
      "Porosity (%)",
      "UTS (MPa)",
      "Yield Strength (MPa)",
      "Elongation (%)",
      "Hardness (HV)",
      "Source Citation",
      "DOI",
    ];

    const rows = activeDataset.map((r) => [
      r.id,
      r.build.alloyName,
      r.sample.sampleCode,
      r.params.laserPower_W,
      r.params.scanSpeed_mm_s,
      r.params.hatchSpacing_um,
      r.params.layerThickness_um,
      r.params.derived.linearEnergyDensity_J_mm,
      r.params.derived.arealEnergyDensity_J_mm2,
      r.params.derived.volumetricEnergyDensity_J_mm3,
      r.params.derived.predictedRegime,
      r.properties.relativeDensity_pct,
      r.properties.porosity_pct,
      r.properties.ultimateTensileStrength_MPa || "",
      r.properties.yieldStrength_MPa || "",
      r.properties.elongationAtBreak_pct || "",
      r.properties.hardness_value || "",
      `"${r.source.citation.replace(/"/g, '""')}"`,
      r.source.doi,
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `LPBF_GroundTruth_${selectedAlloy}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div className="space-y-6 text-slate-200">
      {/* Top Banner & Context */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-[#0b1322] via-[#0e172a] to-[#0a101d] border border-sky-500/20 shadow-[0_0_24px_rgba(56,189,248,0.06)] relative overflow-hidden">
        <div className="absolute right-0 top-0 w-80 h-full bg-[radial-gradient(ellipse_at_top_right,rgba(56,189,248,0.12),transparent_70%)] pointer-events-none"></div>
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className="px-2.5 py-0.5 rounded-md bg-sky-500/20 text-sky-300 border border-sky-400/30 text-[11px] font-mono font-semibold">
                DAY 1–2 GROUND TRUTH FOUNDATION
              </span>
              <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono">
                ASTM F3055 / ASTM B962 / ASTM E8
              </span>
              <span className="px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/30 text-[10px] font-mono">
                Literature + 5-tier
              </span>
            </div>
            <h2 className="text-xl lg:text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
              <Database className="w-6 h-6 text-sky-400" />
              <span>LPBF Ground Truth &amp; Process Parameter Foundation</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1 max-w-3xl leading-relaxed">
              Curated peer-reviewed datasets from published literature (Ti-6Al-4V, 316L, AlSi10Mg) linking process parameters (Power, Scan Speed, Hatch Spacing, Layer Thickness, Scan Strategy) to verified physical properties (Density, Porosity %, UTS, Elongation, Hardness) with strict source traceability.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={handleExportCSV}
              className="px-3 py-2 rounded-xl bg-[#090e18] hover:bg-slate-800 border border-slate-700 text-xs font-mono text-slate-200 flex items-center gap-1.5 transition cursor-pointer"
              title="Export active alloy dataset as CSV"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
              <span>Export CSV</span>
            </button>
            <button
              type="button"
              onClick={handleExportJSON}
              className="px-3 py-2 rounded-xl bg-[#090e18] hover:bg-slate-800 border border-slate-700 text-xs font-mono text-slate-200 flex items-center gap-1.5 transition cursor-pointer"
              title="Export active alloy dataset as JSON"
            >
              <Download className="w-3.5 h-3.5 text-sky-400" />
              <span>Export JSON</span>
            </button>
          </div>
        </div>

        {/* Sync notification */}
        {syncNotice && (
          <div className="mt-3 p-2.5 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-xs font-mono flex items-center gap-2 animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{syncNotice}</span>
          </div>
        )}
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 p-1.5 bg-[#090e18] border border-[#1a2538] rounded-2xl overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab("datasets")}
          className={`flex-1 min-w-[170px] py-2 px-3 rounded-xl text-xs font-mono font-bold flex items-center justify-center gap-2 transition cursor-pointer ${
            activeTab === "datasets"
              ? "bg-sky-500/20 text-sky-300 border border-sky-400/40 shadow-[0_0_12px_rgba(56,189,248,0.25)]"
              : "text-slate-400 hover:text-slate-200 hover:bg-[#0c1424] border border-transparent"
          }`}
        >
          <BookOpen className="w-3.5 h-3.5 text-sky-400" />
          <span>1. Literature Reference Data</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded bg-sky-400/10 text-sky-300">
            {activeDataset.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("derived-quantities")}
          className={`flex-1 min-w-[190px] py-2 px-3 rounded-xl text-xs font-mono font-bold flex items-center justify-center gap-2 transition cursor-pointer ${
            activeTab === "derived-quantities"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-400/40 shadow-[0_0_12px_rgba(6,182,212,0.25)]"
              : "text-slate-400 hover:text-slate-200 hover:bg-[#0c1424] border border-transparent"
          }`}
        >
          <Zap className="w-3.5 h-3.5 text-cyan-400" />
          <span>2. Energy Density (VED/LED/AED)</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyan-400/10 text-cyan-300">Calculators</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("ved-limitations")}
          className={`flex-1 min-w-[190px] py-2 px-3 rounded-xl text-xs font-mono font-bold flex items-center justify-center gap-2 transition cursor-pointer ${
            activeTab === "ved-limitations"
              ? "bg-amber-500/20 text-amber-300 border border-amber-400/40 shadow-[0_0_12px_rgba(245,158,11,0.25)]"
              : "text-slate-400 hover:text-slate-200 hover:bg-[#0c1424] border border-transparent"
          }`}
        >
          <Scale className="w-3.5 h-3.5 text-amber-400" />
          <span>3. VED Limitation Analysis</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-400/10 text-amber-300">Fallacy Sandbox</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("schema-builder")}
          className={`flex-1 min-w-[170px] py-2 px-3 rounded-xl text-xs font-mono font-bold flex items-center justify-center gap-2 transition cursor-pointer ${
            activeTab === "schema-builder"
              ? "bg-purple-500/20 text-purple-300 border border-purple-400/40 shadow-[0_0_12px_rgba(168,85,247,0.25)]"
              : "text-slate-400 hover:text-slate-200 hover:bg-[#0c1424] border border-transparent"
          }`}
        >
          <Plus className="w-3.5 h-3.5 text-purple-400" />
          <span>4. Schema Data Entry</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-400/10 text-purple-300">5-Tier Backbone</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: LITERATURE REFERENCE DATASETS & PROCESS MAP CHARTS */}
      {/* ========================================================================= */}
      {activeTab === "datasets" && (
        <div className="space-y-6">
          {/* Alloy Selector & Filters Bar */}
          <div className="p-4 rounded-2xl bg-[#090e18] border border-[#162032] flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-mono text-slate-400 mr-1">Select Alloy:</span>
              <button
                type="button"
                onClick={() => setSelectedAlloy("ti6al4v")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-mono font-bold transition cursor-pointer ${
                  selectedAlloy === "ti6al4v"
                    ? "bg-sky-500 text-white shadow-[0_0_10px_rgba(56,189,248,0.4)]"
                    : "bg-[#0d1524] text-slate-300 hover:bg-slate-800 border border-slate-700"
                }`}
              >
                Ti-6Al-4V (Grade 5 / ELI)
              </button>
              <button
                type="button"
                onClick={() => setSelectedAlloy("ss316l")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-mono font-bold transition cursor-pointer ${
                  selectedAlloy === "ss316l"
                    ? "bg-sky-500 text-white shadow-[0_0_10px_rgba(56,189,248,0.4)]"
                    : "bg-[#0d1524] text-slate-300 hover:bg-slate-800 border border-slate-700"
                }`}
              >
                316L Stainless Steel
              </button>
              <button
                type="button"
                onClick={() => setSelectedAlloy("alsi10mg")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-mono font-bold transition cursor-pointer ${
                  selectedAlloy === "alsi10mg"
                    ? "bg-sky-500 text-white shadow-[0_0_10px_rgba(56,189,248,0.4)]"
                    : "bg-[#0d1524] text-slate-300 hover:bg-slate-800 border border-slate-700"
                }`}
              >
                AlSi10Mg Aluminum
              </button>
              <button
                type="button"
                onClick={() => setSelectedAlloy("in718")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-mono font-bold transition cursor-pointer ${
                  selectedAlloy === "in718"
                    ? "bg-sky-500 text-white shadow-[0_0_10px_rgba(56,189,248,0.4)]"
                    : "bg-[#0d1524] text-slate-300 hover:bg-slate-800 border border-slate-700"
                }`}
              >
                IN718 Nickel
              </button>
            </div>

            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-xs font-mono text-slate-400">Regime:</span>
              <select aria-label="Regime"
                value={regimeFilter}
                onChange={(e) => setRegimeFilter(e.target.value)}
                className="bg-[#0c121e] border border-[#1e293b] rounded-lg px-2.5 py-1 text-xs font-mono text-slate-200 focus:border-sky-400 focus:outline-none"
              >
                <option value="all">All Regimes ({MASTER_LPBF_REFERENCE_DATASETS[selectedAlloy].length})</option>
                <option value="Stable Conduction">Stable Conduction</option>
                <option value="Lack of Fusion (LoF)">Lack of Fusion (LoF)</option>
                <option value="Keyhole Vaporization">Keyhole Vaporization</option>
                <option value="Balling / Plateau-Rayleigh Instability">Balling / Instability</option>
              </select>
            </div>
          </div>

          {/* Peer-Reviewed Source Citations Card */}
          <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] text-xs font-mono space-y-2">
            <div className="flex items-center justify-between text-slate-300 font-bold">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-sky-400" />
                <span>Primary Peer-Reviewed Reference Studies ({selectedAlloy.toUpperCase()})</span>
              </div>
              <span className="text-[10px] text-slate-500">Cross-checked against original laboratory tables</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 pt-1">
              {Array.from(new Set(activeDataset.map((r) => r.source.citation))).map((citation, idx) => {
                const rec = activeDataset.find((r) => r.source.citation === citation);
                if (!rec) return null;
                return (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg bg-[#0c1322] border border-slate-800 text-[11px] space-y-1.5 flex flex-col justify-between"
                  >
                    <div>
                      <div className="font-semibold text-slate-200 line-clamp-2">{rec.source.title}</div>
                      <div className="text-slate-400 text-[10px] mt-0.5">{rec.source.authors}</div>
                      <div className="text-sky-400/90 text-[10px]">{rec.source.journal} ({rec.source.year})</div>
                    </div>
                    <div className="flex items-center justify-between pt-1 border-t border-slate-800/80">
                      <a
                        href={rec.source.url || `https://doi.org/${rec.source.doi}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[10px] text-sky-400 hover:text-sky-300 flex items-center gap-1 font-mono"
                      >
                        <span>DOI: {rec.source.doi}</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                        {rec.source.labOrganization}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032] text-[11px] font-mono space-y-1">
              <div className="text-slate-300 font-bold">Literature P–v box</div>
              <div className="text-slate-400">
                {schemaPanels.window.box.powerMin_W}–{schemaPanels.window.box.powerMax_W} W · {schemaPanels.window.box.speedMin_mm_s}–
                {schemaPanels.window.box.speedMax_mm_s} mm/s
              </div>
              <div className={schemaPanels.window.inside ? "text-emerald-300" : "text-amber-300"}>
                Build Job is {schemaPanels.window.inside ? "inside" : "outside"} this box
              </div>
              {schemaPanels.window.hull && (
                <div className="text-slate-500">
                  Dense conduction hull (n={schemaPanels.window.hull.n}): {schemaPanels.window.hull.powerMin_W}–{schemaPanels.window.hull.powerMax_W} W ·{" "}
                  {schemaPanels.window.hull.speedMin_mm_s}–{schemaPanels.window.hull.speedMax_mm_s} mm/s
                </div>
              )}
              <p className="text-slate-500">{schemaPanels.window.box.notes}</p>
            </div>
            <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032] text-[11px] font-mono space-y-1">
              <div className="text-slate-300 font-bold">As-built / SR / HIP</div>
              {schemaPanels.ht.map((c) => (
                <div key={c.label} className="text-slate-400">
                  {c.label}: n={c.n}
                  {c.meanYS != null ? ` · YS ${c.meanYS}` : ""}
                  {c.meanUTS != null ? ` · UTS ${c.meanUTS}` : ""}
                  {c.meanElong != null ? ` · A ${c.meanElong}%` : ""}
                </div>
              ))}
            </div>
            <div className="p-3 rounded-xl bg-[#090e18] border border-[#162032] text-[11px] font-mono space-y-1">
              <div className="text-slate-300 font-bold">0° / 45° / 90° coupons</div>
              {schemaPanels.ori.map((c) => (
                <div key={c.label} className="text-slate-400">
                  {c.label}: n={c.n}
                  {c.meanYS != null ? ` · YS ${c.meanYS}` : ""}
                  {c.meanFatigue != null ? ` · σ_w ${c.meanFatigue}` : ""}
                </div>
              ))}
              <p className="text-slate-500">Fatigue lab reads these DOI rows when YS at 0° and 90° exist.</p>
            </div>
          </div>

          {/* Interactive Recharts: Process Window & Density vs VED */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Chart 1: VED vs Relative Density */}
            <div className="p-4 rounded-2xl bg-[#090e18] border border-[#162032] space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold font-mono text-white flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-sky-400" />
                    <span>Volumetric Energy Density vs. Relative Density (%)</span>
                  </h4>
                  <p className="text-[10px] font-mono text-slate-400">
                    Archimedes (ASTM B962) &amp; Micro-CT Densities across process regimes
                  </p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-mono">
                  Conduction Optimum: &gt;99.7%
                </span>
              </div>

              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a2538" />
                    <XAxis
                      type="number"
                      dataKey="ved"
                      name="VED"
                      unit=" J/mm³"
                      stroke="#64748b"
                      fontSize={11}
                      domain={["auto", "auto"]}
                    />
                    <YAxis
                      type="number"
                      dataKey="density"
                      name="Relative Density"
                      unit="%"
                      domain={[93, 100.2]}
                      stroke="#64748b"
                      fontSize={11}
                    />
                    <ZAxis range={[60, 60]} />
                    <RechartsTooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="p-2.5 rounded-lg bg-[#0c1322] border border-sky-400/40 text-xs font-mono shadow-xl space-y-1">
                              <div className="font-bold text-sky-300">{data.name}</div>
                              <div className="text-slate-300">VED: {data.ved} J/mm³</div>
                              <div className="text-emerald-300 font-semibold">Density: {data.density}%</div>
                              <div className="text-amber-300">Porosity: {data.porosity}%</div>
                              <div className="text-slate-400 text-[10px]">Regime: {data.regime}</div>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <ReferenceLine
                      y={99.7}
                      stroke="#10b981"
                      strokeDasharray="4 4"
                      label={{ value: "Aerospace Spec 99.7%", fill: "#10b981", fontSize: 10, position: "insideTopRight" }}
                    />
                    <Scatter
                      name="Samples"
                      data={scatterData}
                      fill="#38bdf8"
                      onClick={(e) => {
                        const selected = scatterData.find(point => point === e.payload);
                        if (selected) setSelectedRecord(selected.record);
                      }}
                      className="cursor-pointer"
                    />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Chart 2: VED vs UTS / Porosity */}
            <div className="p-4 rounded-2xl bg-[#090e18] border border-[#162032] space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold font-mono text-white flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Volumetric Energy Density vs. UTS (MPa)</span>
                  </h4>
                  <p className="text-[10px] font-mono text-slate-400">
                    Tensile test specimens (ASTM E8) showing drop at LoF and over-melting
                  </p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20 font-mono">
                  Peak at Conduction Window
                </span>
              </div>

              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a2538" />
                    <XAxis
                      type="number"
                      dataKey="ved"
                      name="VED"
                      unit=" J/mm³"
                      stroke="#64748b"
                      fontSize={11}
                      domain={["auto", "auto"]}
                    />
                    <YAxis
                      type="number"
                      dataKey="uts"
                      name="UTS"
                      unit=" MPa"
                      stroke="#64748b"
                      fontSize={11}
                    />
                    <ZAxis range={[60, 60]} />
                    <RechartsTooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="p-2.5 rounded-lg bg-[#0c1322] border border-emerald-400/40 text-xs font-mono shadow-xl space-y-1">
                              <div className="font-bold text-emerald-300">{data.name}</div>
                              <div className="text-slate-300">VED: {data.ved} J/mm³</div>
                              <div className="text-white font-semibold">UTS: {data.uts} MPa</div>
                              <div className="text-cyan-300">Elongation: {data.elongation}%</div>
                              {data.hardness > 0 && <div className="text-amber-300">Hardness: {data.hardness} HV</div>}
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Scatter
                      name="Tensile Properties"
                      data={scatterData.filter((d) => d.uts > 0)}
                      fill="#10b981"
                      onClick={(e) => {
                        const selected = scatterData.find(point => point === e.payload);
                        if (selected) setSelectedRecord(selected.record);
                      }}
                      className="cursor-pointer"
                    />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#090e18] border border-[#162032] space-y-3">
            <h4 className="text-xs font-bold font-mono text-white">P–v map (literature coupons)</h4>
            <p className="text-[10px] font-mono text-slate-400">
              Geometric LoF is still W vs h and D vs t on the decision engine. This plot is the DOI coupon cloud, not VED alone.
            </p>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a2538" />
                  <XAxis type="number" dataKey="speed" name="v" unit=" mm/s" stroke="#64748b" fontSize={11} />
                  <YAxis type="number" dataKey="power" name="P" unit=" W" stroke="#64748b" fontSize={11} />
                  <ZAxis range={[60, 60]} />
                  <RechartsTooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="p-2.5 rounded-lg bg-[#0c1322] border border-sky-400/40 text-xs font-mono shadow-xl space-y-1">
                            <div className="font-bold text-sky-300">{data.name}</div>
                            <div>P {data.power} W · v {data.speed} mm/s</div>
                            <div>{data.ht} · {data.ori}°</div>
                            <div className="text-slate-400">{data.regime}</div>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Scatter
                    name="Coupons"
                    data={scatterData}
                    fill="#38bdf8"
                    onClick={(e) => {
                      const selected = scatterData.find(point => point === e.payload);
                      if (selected) setSelectedRecord(selected.record);
                    }}
                    className="cursor-pointer"
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Detailed 5-Tier Backbone Traceability Table */}
          <div className="p-4 rounded-2xl bg-[#090e18] border border-[#162032] space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-bold font-mono text-white flex items-center gap-2">
                  <Database className="w-4 h-4 text-sky-400" />
                  <span>5-Tier Traceability Matrix: Build ➔ ProcessParams ➔ Sample ➔ Properties ➔ Source</span>
                </h3>
                <p className="text-xs text-slate-400 font-mono">
                  Complete pedigree linking laser scan parameters, derived energy densities, measured mechanical properties, and published DOIs.
                </p>
              </div>
              <span className="text-xs font-mono text-slate-400">
                Showing <strong className="text-sky-400">{activeDataset.length}</strong> records
              </span>
            </div>

            <div className="overflow-x-auto rounded-xl border border-slate-800">
              <table className="w-full text-left font-mono text-xs text-slate-300">
                <thead className="bg-[#0c1322] text-[11px] text-slate-400 uppercase border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Sample Code</th>
                    <th className="py-2.5 px-3">Machine &amp; Job</th>
                    <th className="py-2.5 px-3 text-right">P (W)</th>
                    <th className="py-2.5 px-3 text-right">v (mm/s)</th>
                    <th className="py-2.5 px-3 text-right">h (µm)</th>
                    <th className="py-2.5 px-3 text-right">t (µm)</th>
                    <th className="py-2.5 px-3 text-right text-sky-300">VED (J/mm³)</th>
                    <th className="py-2.5 px-3 text-right text-cyan-300">LED (J/mm)</th>
                    <th className="py-2.5 px-3">Regime</th>
                    <th className="py-2.5 px-3 text-right text-emerald-300">Density %</th>
                    <th className="py-2.5 px-3 text-right">UTS (MPa)</th>
                    <th className="py-2.5 px-3 text-right">Elong %</th>
                    <th className="py-2.5 px-3">Source / DOI</th>
                    <th className="py-2.5 px-3 text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {activeDataset.map((rec) => {
                    const isSelected = selectedRecord?.id === rec.id;
                    const regimeColor =
                      rec.params.derived.predictedRegime === "Stable Conduction"
                        ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                        : rec.params.derived.predictedRegime === "Lack of Fusion (LoF)"
                        ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
                        : "text-rose-400 bg-rose-500/10 border-rose-500/20";

                    return (
                      <tr
                        key={rec.id}
                        className={`hover:bg-slate-800/50 transition cursor-pointer ${
                          isSelected ? "bg-sky-500/10" : ""
                        }`}
                        onClick={() => setSelectedRecord(rec)}
                      >
                        <td className="py-2.5 px-3 font-semibold text-white">
                          <div className="flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-sky-400"></span>
                            <span>{rec.sample.sampleCode}</span>
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">
                          <div>{rec.build.machineModel}</div>
                          <div className="text-[10px] text-slate-500">{rec.sample.heatTreatment}</div>
                        </td>
                        <td className="py-2.5 px-3 text-right font-medium text-slate-200">{rec.params.laserPower_W}</td>
                        <td className="py-2.5 px-3 text-right font-medium text-slate-200">{rec.params.scanSpeed_mm_s}</td>
                        <td className="py-2.5 px-3 text-right text-slate-400">{rec.params.hatchSpacing_um}</td>
                        <td className="py-2.5 px-3 text-right text-slate-400">{rec.params.layerThickness_um}</td>
                        <td className="py-2.5 px-3 text-right font-bold text-sky-400">
                          {rec.params.derived.volumetricEnergyDensity_J_mm3}
                        </td>
                        <td className="py-2.5 px-3 text-right text-cyan-400">
                          {rec.params.derived.linearEnergyDensity_J_mm}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className={`text-[10px] px-2 py-0.5 rounded-md border ${regimeColor} whitespace-nowrap`}>
                            {rec.params.derived.predictedRegime.replace("Balling / Plateau-Rayleigh Instability", "Balling")}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-bold text-emerald-400">
                          {rec.properties.relativeDensity_pct.toFixed(2)}%
                        </td>
                        <td className="py-2.5 px-3 text-right font-medium text-slate-200">
                          {rec.properties.ultimateTensileStrength_MPa || "-"}
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-300">
                          {rec.properties.elongationAtBreak_pct ? `${rec.properties.elongationAtBreak_pct}%` : "-"}
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="text-[11px] text-slate-300 truncate max-w-[140px]" title={rec.source.citation}>
                            {rec.source.journal} ({rec.source.year})
                          </div>
                          <a
                            href={rec.source.url || `https://doi.org/${rec.source.doi}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[10px] text-sky-400 hover:underline flex items-center gap-0.5"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <span>DOI</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSyncToSpecimenStore(rec);
                              if (onApplyParametersToSimulation) {
                                onApplyParametersToSimulation({
                                  power_W: rec.params.laserPower_W,
                                  speed_mms: rec.params.scanSpeed_mm_s,
                                  hatch_um: rec.params.hatchSpacing_um,
                                  layer_um: rec.params.layerThickness_um,
                                  beam_um: rec.params.beamSpotDiameter_um,
                                  doi: rec.source.doi,
                                  material: rec.build.alloyName,
                                });
                              }
                            }}
                            className="p-1.5 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-400/20 text-[10px] transition cursor-pointer"
                            title="Push parameters to Active Digital Twin & 3D Simulation"
                          >
                            <Share2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Selected Record Detail Inspector Modal / Drawer */}
          {selectedRecord && (
            <div className="p-4 rounded-2xl bg-[#0a101d] border border-sky-500/30 space-y-3 animate-fadeIn">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-sky-400"></span>
                  <h4 className="text-sm font-bold font-mono text-white">
                    Traceability Record Detail: {selectedRecord.sample.sampleCode} ({selectedRecord.build.alloyName})
                  </h4>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-400/30">
                    {selectedRecord.params.derived.predictedRegime}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedRecord(null)}
                  className="text-slate-400 hover:text-white text-xs font-mono px-2 py-1 rounded bg-slate-800"
                >
                  Close
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs font-mono">
                {/* 1. Build Info */}
                <div className="p-3 rounded-xl bg-[#070b13] border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-sky-400 uppercase tracking-wider">1. Build Level</span>
                  <div className="text-slate-200 font-semibold">{selectedRecord.build.buildJobName}</div>
                  <div className="text-slate-400 text-[11px]">Machine: {selectedRecord.build.machineModel}</div>
                  <div className="text-slate-400 text-[11px]">Powder Lot: {selectedRecord.build.powderLotNumber}</div>
                  <div className="text-slate-400 text-[11px]">Atomization: {selectedRecord.build.powderAtomization}</div>
                  <div className="text-slate-400 text-[11px]">D50: {selectedRecord.build.powderD50_um} µm</div>
                </div>

                {/* 2. Process Params */}
                <div className="p-3 rounded-xl bg-[#070b13] border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">2. Process Params</span>
                  <div className="text-slate-200">P = {selectedRecord.params.laserPower_W} W | v = {selectedRecord.params.scanSpeed_mm_s} mm/s</div>
                  <div className="text-slate-400 text-[11px]">Hatch: {selectedRecord.params.hatchSpacing_um} µm | Layer: {selectedRecord.params.layerThickness_um} µm</div>
                  <div className="text-slate-400 text-[11px]">Spot Size: {selectedRecord.params.beamSpotDiameter_um} µm</div>
                  <div className="text-slate-400 text-[11px] truncate" title={selectedRecord.params.scanStrategy}>
                    Strategy: {selectedRecord.params.scanStrategy}
                  </div>
                  <div className="text-sky-300 font-semibold text-[11px]">
                    VED: {selectedRecord.params.derived.volumetricEnergyDensity_J_mm3} J/mm³
                  </div>
                </div>

                {/* 3. Sample & Properties */}
                <div className="p-3 rounded-xl bg-[#070b13] border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">3. Sample &amp; Properties</span>
                  <div className="text-emerald-400 font-bold">Relative Density: {selectedRecord.properties.relativeDensity_pct}%</div>
                  <div className="text-slate-300">Porosity: {selectedRecord.properties.porosity_pct}%</div>
                  <div className="text-slate-400 text-[11px]">
                    UTS: {selectedRecord.properties.ultimateTensileStrength_MPa || "N/A"} MPa
                  </div>
                  <div className="text-slate-400 text-[11px]">
                    Elongation: {selectedRecord.properties.elongationAtBreak_pct || "N/A"}%
                  </div>
                  <div className="text-slate-400 text-[11px]">
                    Hardness: {selectedRecord.properties.hardness_value || "N/A"} {selectedRecord.properties.hardness_scale}
                  </div>
                </div>

                {/* 4. Source & Standards */}
                <div className="p-3 rounded-xl bg-[#070b13] border border-slate-800 space-y-1 flex flex-col justify-between">
                  <div>
                    <span className="text-[10px] font-bold text-purple-400 uppercase tracking-wider">4. Source Traceability</span>
                    <div className="text-slate-300 text-[11px] font-medium line-clamp-2" title={selectedRecord.source.title}>
                      {selectedRecord.source.title}
                    </div>
                    <div className="text-slate-400 text-[10px]">
                      {selectedRecord.source.journal} ({selectedRecord.source.year})
                    </div>
                  </div>
                  <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
                    <a
                      href={selectedRecord.source.url || `https://doi.org/${selectedRecord.source.doi}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[10px] text-sky-400 hover:underline flex items-center gap-1"
                    >
                      <span>DOI Resolver</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                    <button
                      type="button"
                      onClick={() => handleSyncToSpecimenStore(selectedRecord)}
                      className="px-2 py-1 rounded bg-sky-500/20 text-sky-300 hover:bg-sky-500/30 text-[10px]"
                    >
                      Sync to Twin
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: DERIVED ENERGY QUANTITIES CALCULATOR (VED, LED, AED, INTENSITY) */}
      {/* ========================================================================= */}
      {activeTab === "derived-quantities" && (
        <div className="space-y-6">
          <div className="p-5 rounded-2xl bg-[#090e18] border border-[#162032] space-y-4">
            <div>
              <h3 className="text-base font-bold font-mono text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-cyan-400" />
                <span>Standard Derived Quantities Calculator (ASTM F3055 / LPBF Physics)</span>
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-1">
                Calculate volumetric, areal, and linear energy densities alongside peak laser intensity and dimensionless normalized enthalpy.
              </p>
            </div>

            {/* Input Sliders & Controls */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
              {/* Laser Power P */}
              <div className="p-3.5 rounded-xl bg-[#0c121e] border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300 font-semibold">Laser Power (P)</span>
                  <span className="text-sky-400 font-bold">{calcPower_W} W</span>
                </div>
                <input aria-label="Laser Power (P)"
                  type="range"
                  min={50}
                  max={500}
                  step={5}
                  value={calcPower_W}
                  onChange={(e) => setCalcPower_W(Number(e.target.value))}
                  className="w-full accent-sky-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>50 W</span>
                  <span>275 W</span>
                  <span>500 W</span>
                </div>
              </div>

              {/* Scan Speed v */}
              <div className="p-3.5 rounded-xl bg-[#0c121e] border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300 font-semibold">Scan Speed (v)</span>
                  <span className="text-cyan-400 font-bold">{calcSpeed_mm_s} mm/s</span>
                </div>
                <input aria-label="Scan Speed (v)"
                  type="range"
                  min={200}
                  max={2500}
                  step={25}
                  value={calcSpeed_mm_s}
                  onChange={(e) => setCalcSpeed_mm_s(Number(e.target.value))}
                  className="w-full accent-cyan-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>200 mm/s</span>
                  <span>1350 mm/s</span>
                  <span>2500 mm/s</span>
                </div>
              </div>

              {/* Hatch Spacing h */}
              <div className="p-3.5 rounded-xl bg-[#0c121e] border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300 font-semibold">Hatch Spacing (h)</span>
                  <span className="text-amber-400 font-bold">{calcHatch_um} µm</span>
                </div>
                <input aria-label="Hatch Spacing (h)"
                  type="range"
                  min={40}
                  max={200}
                  step={5}
                  value={calcHatch_um}
                  onChange={(e) => setCalcHatch_um(Number(e.target.value))}
                  className="w-full accent-amber-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>40 µm</span>
                  <span>120 µm</span>
                  <span>200 µm</span>
                </div>
              </div>

              {/* Layer Thickness t */}
              <div className="p-3.5 rounded-xl bg-[#0c121e] border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300 font-semibold">Layer Thickness (t)</span>
                  <span className="text-purple-400 font-bold">{calcLayer_um} µm</span>
                </div>
                <input aria-label="Layer Thickness (t)"
                  type="range"
                  min={20}
                  max={80}
                  step={5}
                  value={calcLayer_um}
                  onChange={(e) => setCalcLayer_um(Number(e.target.value))}
                  className="w-full accent-purple-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>20 µm</span>
                  <span>50 µm</span>
                  <span>80 µm</span>
                </div>
              </div>

              {/* Beam Spot Diameter d_spot */}
              <div className="p-3.5 rounded-xl bg-[#0c121e] border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300 font-semibold">Beam Spot Diameter (d)</span>
                  <span className="text-emerald-400 font-bold">{calcSpot_um} µm</span>
                </div>
                <input aria-label="Beam Spot Diameter (d)"
                  type="range"
                  min={40}
                  max={150}
                  step={5}
                  value={calcSpot_um}
                  onChange={(e) => setCalcSpot_um(Number(e.target.value))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>40 µm</span>
                  <span>95 µm</span>
                  <span>150 µm</span>
                </div>
              </div>

              {/* Alloy & Absorptivity Preset */}
              <div className="p-3.5 rounded-xl bg-[#0c121e] border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300 font-semibold">Alloy Preset</span>
                  <span className="text-rose-400 font-bold">η = {calcAbsorptivity}</span>
                </div>
                <select aria-label="Alloy Preset"
                  value={selectedAlloy}
                  onChange={(e) => {
                    const newAlloy = e.target.value as LPBFAlloyId;
                    setSelectedAlloy(newAlloy);
                    setCalcAbsorptivity(ALLOY_THERMAL_PROPERTIES[newAlloy].defaultAbsorptivity);
                  }}
                  className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-1.5 text-xs font-mono text-white"
                >
                  <option value="ti6al4v">Ti-6Al-4V (η = 0.42)</option>
                  <option value="ss316l">316L Stainless Steel (η = 0.53)</option>
                  <option value="alsi10mg">AlSi10Mg Aluminum (η = 0.22)</option>
                  <option value="in718">Inconel 718 (η = 0.55)</option>
                </select>
                <div className="text-[10px] text-slate-400 font-mono">
                  Melting: {ALLOY_THERMAL_PROPERTIES[selectedAlloy].meltingPoint_C}°C
                </div>
              </div>
            </div>

            {/* Derived Energy Densities Output Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-3">
              {/* 1. Volumetric Energy Density VED */}
              <div className="p-4 rounded-xl bg-gradient-to-b from-[#0e172a] to-[#080e1a] border border-sky-500/30 space-y-1 relative overflow-hidden">
                <span className="text-[10px] font-mono text-sky-400 font-bold uppercase tracking-wider">
                  Volumetric Energy Density (VED)
                </span>
                <div className="text-2xl font-bold font-mono text-white">
                  {sandboxCalculations.ved} <span className="text-xs text-slate-400 font-normal">J/mm³</span>
                </div>
                <div className="text-[11px] font-mono text-slate-400">
                  <code className="text-sky-300">VED = P / (v · h · t)</code>
                </div>
                <div className="text-[10px] text-slate-500 pt-1">
                  Standard bulk powder volume input metric.
                </div>
              </div>

              {/* 2. Linear Energy Density LED */}
              <div className="p-4 rounded-xl bg-gradient-to-b from-[#0e172a] to-[#080e1a] border border-cyan-500/30 space-y-1">
                <span className="text-[10px] font-mono text-cyan-400 font-bold uppercase tracking-wider">
                  Linear Energy Density (LED)
                </span>
                <div className="text-2xl font-bold font-mono text-white">
                  {sandboxCalculations.led} <span className="text-xs text-slate-400 font-normal">J/mm</span>
                </div>
                <div className="text-[11px] font-mono text-slate-400">
                  <code className="text-cyan-300">LED = P / v</code>
                </div>
                <div className="text-[10px] text-slate-500 pt-1">
                  Single laser track energy input rate.
                </div>
              </div>

              {/* 3. Areal Energy Density AED */}
              <div className="p-4 rounded-xl bg-gradient-to-b from-[#0e172a] to-[#080e1a] border border-amber-500/30 space-y-1">
                <span className="text-[10px] font-mono text-amber-400 font-bold uppercase tracking-wider">
                  Areal / Surface Density (AED)
                </span>
                <div className="text-2xl font-bold font-mono text-white">
                  {sandboxCalculations.aed} <span className="text-xs text-slate-400 font-normal">J/mm²</span>
                </div>
                <div className="text-[11px] font-mono text-slate-400">
                  <code className="text-amber-300">AED = P / (v · h)</code>
                </div>
                <div className="text-[10px] text-slate-500 pt-1">
                  Energy per layer scan area.
                </div>
              </div>

              {/* 4. Peak Laser Intensity */}
              <div className="p-4 rounded-xl bg-gradient-to-b from-[#0e172a] to-[#080e1a] border border-purple-500/30 space-y-1">
                <span className="text-[10px] font-mono text-purple-400 font-bold uppercase tracking-wider">
                  Peak Intensity (I₀)
                </span>
                <div className="text-2xl font-bold font-mono text-white">
                  {sandboxCalculations.intensity} <span className="text-xs text-slate-400 font-normal">MW/cm²</span>
                </div>
                <div className="text-[11px] font-mono text-slate-400">
                  <code className="text-purple-300">I₀ = 4P / (π · d²)</code>
                </div>
                <div className="text-[10px] text-slate-500 pt-1">
                  Governs metal vaporization &amp; keyhole depth.
                </div>
              </div>
            </div>

            {/* Regime Assessment Card */}
            <div className="p-4 rounded-xl bg-[#0c1322] border border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-lg ${
                    sandboxCalculations.regime === "Stable Conduction"
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                      : sandboxCalculations.regime === "Lack of Fusion (LoF)"
                      ? "bg-amber-500/20 text-amber-400 border border-amber-500/40"
                      : "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                  }`}
                >
                  {sandboxCalculations.regime === "Stable Conduction" ? "✓" : "!"}
                </div>
                <div>
                  <div className="text-xs font-mono text-slate-400">Predicted Metallurgical Regime:</div>
                  <div className="text-sm font-bold font-mono text-white">
                    {sandboxCalculations.regime}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 text-xs font-mono">
                <div className="text-right">
                  <span className="text-slate-400">Normalized Enthalpy (ΔH/hₛ):</span>
                  <div className="font-bold text-sky-400">{sandboxCalculations.normalizedEnthalpy}</div>
                </div>
                <div className="text-right pl-3 border-l border-slate-800">
                  <span className="text-slate-400">Expected Relative Density:</span>
                  <div className="font-bold text-emerald-400">
                    {sandboxCalculations.regime === "Stable Conduction"
                      ? "> 99.8%"
                      : sandboxCalculations.regime === "Lack of Fusion (LoF)"
                      ? "94.0% - 97.0%"
                      : "97.5% - 98.8%"}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: THE VED LIMITATION & FALLACY SANDBOX */}
      {/* ========================================================================= */}
      {activeTab === "ved-limitations" && (
        <div className="space-y-6">
          {/* Main Theoretical Explanation Banner */}
          <div className="p-5 rounded-2xl bg-[#090e18] border border-amber-500/30 space-y-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
              <h3 className="text-base font-bold font-mono text-white">
                Why Volumetric Energy Density (VED) Alone is an Oversimplification
              </h3>
            </div>
            <p className="text-xs font-mono text-slate-300 leading-relaxed">
              In academic literature and industrial practice, <strong>Volumetric Energy Density</strong> (<code className="text-amber-300">VED = P / (v·h·t)</code>) is commonly cited as a universal index. However, multiple seminal papers (e.g. <em>King et al., 2014; Scime &amp; Beuth, 2018; Sola &amp; Nouri, 2019</em>) prove that <strong>VED is non-unique and inherently ambiguous</strong>. Two parameter sets with the exact same VED can trigger polar-opposite physical outcomes.
            </p>

            {/* 4 Core Reasons Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
              <div className="p-3 rounded-xl bg-[#0c1322] border border-slate-800 space-y-1">
                <span className="text-[11px] font-bold text-amber-400 font-mono">
                  1. Blindness to Beam Spot Size (d_spot) &amp; Peak Intensity
                </span>
                <p className="text-[11px] text-slate-400 leading-relaxed font-mono">
                  VED does not include beam diameter <code className="text-slate-300">d</code>. Because peak intensity scales with <code className="text-slate-300">I ∝ P / d²</code>, shrinking the laser spot from 100 µm to 50 µm increases peak intensity by 400% without altering VED, turning a benign conduction pool into violent keyhole metal boiling.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-[#0c1322] border border-slate-800 space-y-1">
                <span className="text-[11px] font-bold text-amber-400 font-mono">
                  2. Non-Linear Optical Absorptivity (η) in Keyhole vs Conduction
                </span>
                <p className="text-[11px] text-slate-400 leading-relaxed font-mono">
                  VED assumes constant 100% absorption. In reality, conduction absorption for Ti-6Al-4V is ~40%, but when deep keyhole cavities open, multiple internal optical reflections trap laser photons, jumping effective absorptivity to &gt;80% and drastically amplifying actual energy absorbed.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-[#0c1322] border border-slate-800 space-y-1">
                <span className="text-[11px] font-bold text-amber-400 font-mono">
                  3. Degeneracy of (P, v) Pairs &amp; Cooling Rate Divergence
                </span>
                <p className="text-[11px] text-slate-400 leading-relaxed font-mono">
                  Equal VED does not imply equal thermal history. Cooling rate depends on both the local thermal gradient and solidification rate; grain structure, phase transformation and stress require material-specific models and experimental evidence.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-[#0c1322] border border-slate-800 space-y-1">
                <span className="text-[11px] font-bold text-amber-400 font-mono">
                  4. Thermal Diffusion Length vs Laser Interaction Dwell Time
                </span>
                <p className="text-[11px] text-slate-400 leading-relaxed font-mono">
                  Heat conduction into previous solid layers depends on interaction time <code className="text-slate-300">t_dwell = d / v</code> and thermal diffusion length <code className="text-slate-300">l_th = √(α · t_dwell)</code>. High-speed scanning conducts less heat into the substrate, inducing lack-of-fusion despite high nominal VED.
                </p>
              </div>
            </div>
          </div>

          {/* Interactive Iso-VED Equivalence Sandbox */}
          <div className="p-5 rounded-2xl bg-[#090e18] border border-[#162032] space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold font-mono text-white flex items-center gap-2">
                  <Scale className="w-4 h-4 text-sky-400" />
                  <span>The "Iso-VED Equivalence" Proof Sandbox</span>
                </h4>
                <p className="text-xs text-slate-400 font-mono">
                  Adjust Condition A and Condition B below to achieve identical VED, and observe the divergence in peak intensity, dwell time, and physical outcome.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  // Preload classic published Iso-VED discrepancy pair
                  setIsoVedA_Power(300);
                  setIsoVedA_Speed(1500);
                  setIsoVedA_Spot(50);

                  setIsoVedB_Power(100);
                  setIsoVedB_Speed(500);
                  setIsoVedB_Spot(120);
                }}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono cursor-pointer transition"
              >
                Reset to Published Case (66.7 J/mm³)
              </button>
            </div>

            {/* Side-by-Side Parameter & Metric Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* CONDITION A */}
              <div className="p-4 rounded-xl bg-[#0c121e] border border-sky-500/40 space-y-3">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <span className="text-xs font-bold font-mono text-sky-300">Condition A: High Speed, Narrow Beam</span>
                  <span className="text-xs font-bold font-mono text-sky-400">VED = {isoComparison.vedA} J/mm³</span>
                </div>

                <div className="space-y-2 text-xs font-mono">
                  <div>
                    <div className="flex justify-between text-slate-300">
                      <span>Laser Power (P):</span>
                      <span className="font-bold">{isoVedA_Power} W</span>
                    </div>
                    <input aria-label="Condition A laser power (P)"
                      type="range"
                      min={100}
                      max={450}
                      step={10}
                      value={isoVedA_Power}
                      onChange={(e) => setIsoVedA_Power(Number(e.target.value))}
                      className="w-full accent-sky-500"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-slate-300">
                      <span>Scan Speed (v):</span>
                      <span className="font-bold">{isoVedA_Speed} mm/s</span>
                    </div>
                    <input aria-label="Condition A scan speed (v)"
                      type="range"
                      min={300}
                      max={2000}
                      step={50}
                      value={isoVedA_Speed}
                      onChange={(e) => setIsoVedA_Speed(Number(e.target.value))}
                      className="w-full accent-sky-500"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-slate-300">
                      <span>Beam Diameter (d):</span>
                      <span className="font-bold">{isoVedA_Spot} µm</span>
                    </div>
                    <input aria-label="Condition A beam diameter (d)"
                      type="range"
                      min={40}
                      max={150}
                      step={5}
                      value={isoVedA_Spot}
                      onChange={(e) => setIsoVedA_Spot(Number(e.target.value))}
                      className="w-full accent-sky-500"
                    />
                  </div>
                </div>

                {/* Physics Outputs for Condition A */}
                <div className="p-3 rounded-lg bg-[#080d17] border border-slate-800 space-y-1.5 text-xs font-mono">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Linear Energy (P/v):</span>
                    <span className="text-white font-semibold">{isoComparison.ledA} J/mm</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Peak Laser Intensity:</span>
                    <span className="text-amber-400 font-bold">{isoComparison.intA} MW/cm²</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Laser Dwell Time:</span>
                    <span className="text-cyan-400 font-semibold">{isoComparison.dwellA_us} µs</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Normalized Enthalpy (ΔH/hₛ):</span>
                    <span className="text-purple-400 font-semibold">{isoComparison.nthA}</span>
                  </div>
                </div>
              </div>

              {/* CONDITION B */}
              <div className="p-4 rounded-xl bg-[#0c121e] border border-amber-500/40 space-y-3">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <span className="text-xs font-bold font-mono text-amber-300">Condition B: Low Speed, Wide Beam</span>
                  <span className="text-xs font-bold font-mono text-amber-400">VED = {isoComparison.vedB} J/mm³</span>
                </div>

                <div className="space-y-2 text-xs font-mono">
                  <div>
                    <div className="flex justify-between text-slate-300">
                      <span>Laser Power (P):</span>
                      <span className="font-bold">{isoVedB_Power} W</span>
                    </div>
                    <input aria-label="Condition B laser power (P)"
                      type="range"
                      min={50}
                      max={350}
                      step={10}
                      value={isoVedB_Power}
                      onChange={(e) => setIsoVedB_Power(Number(e.target.value))}
                      className="w-full accent-amber-500"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-slate-300">
                      <span>Scan Speed (v):</span>
                      <span className="font-bold">{isoVedB_Speed} mm/s</span>
                    </div>
                    <input aria-label="Condition B scan speed (v)"
                      type="range"
                      min={200}
                      max={1200}
                      step={25}
                      value={isoVedB_Speed}
                      onChange={(e) => setIsoVedB_Speed(Number(e.target.value))}
                      className="w-full accent-amber-500"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-slate-300">
                      <span>Beam Diameter (d):</span>
                      <span className="font-bold">{isoVedB_Spot} µm</span>
                    </div>
                    <input aria-label="Condition B beam diameter (d)"
                      type="range"
                      min={40}
                      max={160}
                      step={5}
                      value={isoVedB_Spot}
                      onChange={(e) => setIsoVedB_Spot(Number(e.target.value))}
                      className="w-full accent-amber-500"
                    />
                  </div>
                </div>

                {/* Physics Outputs for Condition B */}
                <div className="p-3 rounded-lg bg-[#080d17] border border-slate-800 space-y-1.5 text-xs font-mono">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Linear Energy (P/v):</span>
                    <span className="text-white font-semibold">{isoComparison.ledB} J/mm</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Peak Laser Intensity:</span>
                    <span className="text-amber-400 font-bold">{isoComparison.intB} MW/cm²</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Laser Dwell Time:</span>
                    <span className="text-cyan-400 font-semibold">{isoComparison.dwellB_us} µs</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Normalized Enthalpy (ΔH/hₛ):</span>
                    <span className="text-purple-400 font-semibold">{isoComparison.nthB}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Synthesis comparison verdict */}
            <div className="p-4 rounded-xl bg-[#080e1a] border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-3 text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                <span className="text-slate-300">
                  VED Delta: <strong className="text-white">{Math.abs(isoComparison.vedA - isoComparison.vedB).toFixed(2)} J/mm³</strong>
                  {" "}({Math.abs(isoComparison.vedA - isoComparison.vedB) < 1 ? "Identical VED!" : "Non-identical"})
                </span>
              </div>
              <div className="text-slate-400">
                Peak Intensity Ratio: <strong className="text-amber-300">{(isoComparison.intA / Math.max(0.01, isoComparison.intB)).toFixed(2)}x</strong>
                {" • "}
                Dwell Time Ratio: <strong className="text-cyan-300">{(isoComparison.dwellB_us / Math.max(0.01, isoComparison.dwellA_us)).toFixed(2)}x</strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: SCHEMA DATA ENTRY FORM (TRACEABILITY BACKBONE) */}
      {/* ========================================================================= */}
      {activeTab === "schema-builder" && (
        <div className="space-y-6">
          <div className="p-5 rounded-2xl bg-[#090e18] border border-[#162032] space-y-4">
            <div>
              <h3 className="text-base font-bold font-mono text-white flex items-center gap-2">
                <Plus className="w-5 h-5 text-purple-400" />
                <span>Add Traceable Record to Ground Truth Foundation</span>
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-1">
                Add an experimental run or verified literature data point maintaining strict relational traceability:
                <span className="text-sky-300 ml-1">Build ➔ ProcessParams ➔ Sample ➔ Properties ➔ Source</span>.
              </p>
            </div>

            <form onSubmit={handleAddRecord} className="space-y-5">
              {/* 1. Build Level */}
              <div className="p-4 rounded-xl bg-[#0c121e] border border-slate-800 space-y-3">
                <div className="flex items-center gap-2 text-xs font-mono font-bold text-sky-400">
                  <span>1. BUILD LEVEL INFORMATION</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
                  <div>
                    <label className="block text-slate-400 mb-1">Build Job Name / Run ID</label>
                    <input aria-label="Build Job Name / Run ID"
                      type="text"
                      value={formBuildJob}
                      onChange={(e) => setFormBuildJob(e.target.value)}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Machine Model</label>
                    <input aria-label="Machine Model"
                      type="text"
                      value={formMachine}
                      onChange={(e) => setFormMachine(e.target.value)}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Target Alloy</label>
                    <select aria-label="Target Alloy"
                      value={selectedAlloy}
                      onChange={(e) => setSelectedAlloy(e.target.value as LPBFAlloyId)}
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    >
                      <option value="ti6al4v">Ti-6Al-4V Grade 5 (ELI)</option>
                      <option value="ss316l">316L Stainless Steel</option>
                      <option value="alsi10mg">AlSi10Mg Aluminum</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Powder lot (optional)</label>
                    <input aria-label="Powder lot (optional)"
                      type="text"
                      value={formPowderLot}
                      onChange={(e) => setFormPowderLot(e.target.value)}
                      placeholder="Not recorded"
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">D10 (µm, optional)</label>
                    <input aria-label="D10 (µm, optional)"
                      type="number"
                      value={formPowderD10}
                      onChange={(e) => setFormPowderD10(e.target.value)}
                      placeholder="empty"
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">D50 (µm, optional)</label>
                    <input aria-label="D50 (µm, optional)"
                      type="number"
                      value={formPowderD50}
                      onChange={(e) => setFormPowderD50(e.target.value)}
                      placeholder="empty"
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">D90 (µm, optional)</label>
                    <input aria-label="D90 (µm, optional)"
                      type="number"
                      value={formPowderD90}
                      onChange={(e) => setFormPowderD90(e.target.value)}
                      placeholder="empty"
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                </div>
              </div>

              {/* 2. Process Parameters Level */}
              <div className="p-4 rounded-xl bg-[#0c121e] border border-slate-800 space-y-3">
                <div className="flex items-center justify-between text-xs font-mono font-bold text-cyan-400">
                  <span>2. PROCESS PARAMETERS &amp; AUTOMATIC DERIVED ENERGY DENSITIES</span>
                  <span className="text-sky-300 font-normal">
                    VED = {calculateVolumetricEnergyDensity(formPower, formSpeed, formHatch, formLayer)} J/mm³ | LED = {calculateLinearEnergyDensity(formPower, formSpeed)} J/mm
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs font-mono">
                  <div>
                    <label className="block text-slate-400 mb-1">Power (W)</label>
                    <input aria-label="Power (W)"
                      type="number"
                      value={formPower}
                      onChange={(e) => setFormPower(Number(e.target.value))}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white font-bold text-sky-300"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Speed (mm/s)</label>
                    <input aria-label="Speed (mm/s)"
                      type="number"
                      value={formSpeed}
                      onChange={(e) => setFormSpeed(Number(e.target.value))}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white font-bold text-cyan-300"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Hatch (µm)</label>
                    <input aria-label="Hatch (µm)"
                      type="number"
                      value={formHatch}
                      onChange={(e) => setFormHatch(Number(e.target.value))}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Layer (µm)</label>
                    <input aria-label="Layer (µm)"
                      type="number"
                      value={formLayer}
                      onChange={(e) => setFormLayer(Number(e.target.value))}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Spot Size (µm)</label>
                    <input aria-label="Spot Size (µm)"
                      type="number"
                      value={formSpot}
                      onChange={(e) => setFormSpot(Number(e.target.value))}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Scan Strategy</label>
                    <select aria-label="Scan Strategy"
                      value={formStrategy}
                      onChange={(e) => setFormStrategy(e.target.value)}
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    >
                      <option value="Meander (67° alternating rotation)">Meander (67°)</option>
                      <option value="Stripe (5mm width, 90° rotation)">Stripe (5mm)</option>
                      <option value="Island / Checkerboard (5x5mm)">Island (5x5mm)</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* 3. Sample & Measured Properties Level */}
              <div className="p-4 rounded-xl bg-[#0c121e] border border-slate-800 space-y-3">
                <div className="flex items-center gap-2 text-xs font-mono font-bold text-emerald-400">
                  <span>3. SAMPLE &amp; MEASURED MECHANICAL PROPERTIES</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs font-mono">
                  <div>
                    <label className="block text-slate-400 mb-1">Sample Code</label>
                    <input aria-label="Sample Code"
                      type="text"
                      value={formSampleCode}
                      onChange={(e) => setFormSampleCode(e.target.value)}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white font-bold"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Orientation</label>
                    <select aria-label="Orientation"
                      value={formOrientation}
                      onChange={(e) => setFormOrientation(Number(e.target.value) as any)}
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    >
                      <option value={0}>0° (Horizontal)</option>
                      <option value={45}>45° (Inclined)</option>
                      <option value={90}>90° (Vertical)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Heat Treatment</label>
                    <select aria-label="Heat Treatment"
                      value={formHeatTreatment}
                      onChange={(e) => setFormHeatTreatment(e.target.value)}
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    >
                      <option value="As-Built">As-Built</option>
                      <option value="Stress Relieved (SR)">Stress Relieved (SR)</option>
                      <option value="Hot Isostatic Pressed (HIP)">HIP Treated</option>
                      <option value="Solution Treated & Aged (STA)">STA Aged</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Relative Density (%)</label>
                    <input aria-label="Relative Density (%)"
                      type="number"
                      step={0.01}
                      value={formDensityPct}
                      onChange={(e) => setFormDensityPct(Number(e.target.value))}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-emerald-400 font-bold"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">UTS (MPa)</label>
                    <input aria-label="UTS (MPa)"
                      type="number"
                      value={formUTS}
                      onChange={(e) => setFormUTS(Number(e.target.value))}
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Elongation (%)</label>
                    <input aria-label="Elongation (%)"
                      type="number"
                      step={0.1}
                      value={formElongation}
                      onChange={(e) => setFormElongation(Number(e.target.value))}
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                </div>
              </div>

              {/* 4. Source Level */}
              <div className="p-4 rounded-xl bg-[#0c121e] border border-slate-800 space-y-3">
                <div className="flex items-center gap-2 text-xs font-mono font-bold text-purple-400">
                  <span>4. SOURCE PROVENANCE &amp; STANDARDS TRACEABILITY</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
                  <div>
                    <label className="block text-slate-400 mb-1">Citation / Lab Report</label>
                    <input aria-label="Citation / Lab Report"
                      type="text"
                      value={formCitation}
                      onChange={(e) => setFormCitation(e.target.value)}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">DOI or Internal Hash</label>
                    <input aria-label="DOI or Internal Hash"
                      type="text"
                      value={formDoi}
                      onChange={(e) => setFormDoi(e.target.value)}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Testing Standards Used</label>
                    <input aria-label="Testing Standards Used"
                      type="text"
                      value={formStandard}
                      onChange={(e) => setFormStandard(e.target.value)}
                      required
                      className="w-full bg-[#080d17] border border-slate-700 rounded-lg p-2 text-white"
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="submit"
                  className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-mono font-bold text-xs shadow-[0_0_15px_rgba(56,189,248,0.3)] transition cursor-pointer flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  <span>Commit Record to Ground Truth Foundation</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
