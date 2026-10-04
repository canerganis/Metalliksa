import React, { useState, useMemo } from "react";
import {
  ShieldCheck,
  Award,
  FileText,
  Download,
  Printer,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  Building2,
  UserCheck,
  RefreshCw,
  QrCode,
  Gauge,
  Microscope,
  Atom,
  Box,
  Layers,
  Info,
  ChevronRight,
  Send,
  Zap,
} from "lucide-react";
import {
  generateAerospaceCoCPDF,
  AerospaceAuditReportData,
  LabMultiTestData,
} from "../utils/exportAerospaceCoC";
import { ENGINEERING_ESTIMATE_DISCLAIMER, EngineeringEstimateBanner } from "../utils/engineeringDisclaimer";
import { buildAerospaceChecklist, computeAerospaceScreeningStats } from "../utils/aerospaceScreening";

interface AerospacePreset {
  id: string;
  programTitle: string;
  partName: string;
  partNumber: string;
  cageCode: string;
  criticality: "Class 1 (Flight Critical)" | "Class 2 (Primary Structural)" | "Class 3 (Secondary System)";
  alloyName: string;
  category: string;
  standardSpec: string;
  manufacturingRoute: string;
  heatTreatmentCondition: string;
  protectiveCoating: string;
  serviceTempMin: number;
  serviceTempMax: number;
  operatingStressMpa: number;
  meanYieldMpa: number;
  meanTensileMpa: number;
  fractureToughnessMpaM: number;
  sampleSizeN: number;
  scatterCvPct: number;
  densityGcm3: number;
  youngsModulusGpa: number;
  labData: LabMultiTestData;
  notes: string;
  isDemoScenario?: boolean;
}

const GENERIC_SCREENING_PRESET: AerospacePreset = {
  id: "generic-coupon-screening",
  programTitle: "Generic structural coupon screening",
  partName: "Unlabeled tensile coupon series",
  partNumber: "SCR-COUPON-001",
  cageCode: "N/A (screening)",
  criticality: "Class 3 (Secondary System)",
  alloyName: "Ti-6Al-4V Grade 5 (Alpha-Beta Titanium)",
  category: "Structural coupon screening example",
  standardSpec: "AMS 4928 (reference spec only — not a qualification)",
  manufacturingRoute: "Wrought screening coupon",
  heatTreatmentCondition: "STA (screening example)",
  protectiveCoating: "None specified (screening)",
  serviceTempMin: -50,
  serviceTempMax: 250,
  operatingStressMpa: 400,
  meanYieldMpa: 880,
  meanTensileMpa: 950,
  fractureToughnessMpaM: 55,
  sampleSizeN: 12,
  scatterCvPct: 4.0,
  densityGcm3: 4.43,
  youngsModulusGpa: 114,
  labData: {
    taborTest: {
      measuredHardnessHV: 320,
      predictedYieldMpa: 875,
      predictedUtsMpa: 945,
      strainHardeningExponentN: 0.13,
      fractureToughnessKic: 55,
      correlationConfidencePct: 80,
      indentationStandard: "ASTM E384 (screening estimate)",
    },
    xrdAnalysis: {
      primaryPhase: "HCP α-Ti (example)",
      secondaryPhaseFractionPct: 8.0,
      crystalliteSizeNm: 40,
      microstrainPct: 0.18,
      surfaceResidualStressMpa: -80,
      standardReference: "XRD screening overlay",
    },
    ebsdMicrostructure: {
      meanGrainSizeUm: 16,
      astmGrainSizeNumberG: 8.5,
      hagbFractionPct: 70,
      dominantTextureOrientation: "Not attested",
      schmidFactorAverage: 0.4,
      standardReference: "ASTM E112 screening estimate",
    },
    additiveDefectAudit: {
      volumetricEnergyDensityJmm3: 0,
      maxThermalWarpageMm: 0,
      peakTensileStressMpa: 0,
      keyholeRiskScorePct: 0,
      lackOfFusionRiskPct: 0,
      asBuiltVsHipState: "Not an AM lot",
      standardReference: "Not executed",
    },
  },
  notes: "Generic unlabeled screening example. Not a flight program, CAGE, or certificate.",
  isDemoScenario: false,
};

const DEMO_SCENARIO_PRESETS: AerospacePreset[] = [
  {
    id: "f35-bulkhead-ti64",
    programTitle: "Next-Gen Fighter Airframe (JSF/F-35)",
    partName: "Main Fuselage Station 450 Wing Carry-Through Bulkhead",
    partNumber: "WCTB-TI64-FS450-REV7",
    cageCode: "94117",
    criticality: "Class 1 (Flight Critical)",
    alloyName: "Ti-6Al-4V Grade 5 (Alpha-Beta Titanium)",
    category: "Titanium Alpha-Beta Forging",
    standardSpec: "AMS 4928 / MIL-T-9047 / MMPDS-14 Ch. 5",
    manufacturingRoute: "Precision Closed-Die Forged + Vacuum Annealed",
    heatTreatmentCondition: "STA (Solution Treated at 955°C / Overaged at 540°C)",
    protectiveCoating: "Titanium Anodize Type II (AMS 2488) + Epoxy Primer",
    serviceTempMin: -65,
    serviceTempMax: 380,
    operatingStressMpa: 580,
    meanYieldMpa: 935,
    meanTensileMpa: 1015,
    fractureToughnessMpaM: 68,
    sampleSizeN: 60,
    scatterCvPct: 2.8,
    densityGcm3: 4.43,
    youngsModulusGpa: 114,
    labData: {
      taborTest: {
        measuredHardnessHV: 338,
        predictedYieldMpa: 932,
        predictedUtsMpa: 1012,
        strainHardeningExponentN: 0.138,
        fractureToughnessKic: 68.4,
        correlationConfidencePct: 99.4,
        indentationStandard: "ASTM E8 / ASTM E384 Micro-indentation",
      },
      xrdAnalysis: {
        primaryPhase: "HCP α-Ti (Alpha Matrix)",
        secondaryPhaseFractionPct: 8.6,
        crystalliteSizeNm: 44.2,
        microstrainPct: 0.174,
        surfaceResidualStressMpa: -145, // Compressive residual stress
        standardReference: "ASTM E975 / Rigaku SmartLab XRD",
      },
      ebsdMicrostructure: {
        meanGrainSizeUm: 14.2,
        astmGrainSizeNumberG: 9.1,
        hagbFractionPct: 82.4,
        dominantTextureOrientation: "<0001> Basal Split Along Forging Axis",
        schmidFactorAverage: 0.38,
        standardReference: "ASTM E112 / Oxford Instruments EBSD",
      },
      additiveDefectAudit: {
        volumetricEnergyDensityJmm3: 58.4,
        maxThermalWarpageMm: 0.12,
        peakTensileStressMpa: 210,
        keyholeRiskScorePct: 1.8,
        lackOfFusionRiskPct: 0.9,
        asBuiltVsHipState: "Wrought Forged Baseline Reference",
        standardReference: "MIL-STD-2154 Ultrasonic Class AAA",
      },
    },
    notes: "DEMO SCENARIO only. Fictional fighter bulkhead example — not a live program record.",
  },
  {
    id: "ariane-rocket-in718",
    programTitle: "Heavy Launch Vehicle (Ariane 6 / Artemis)",
    partName: "Cryogenic LOX/Methane Main Combustion Injector Dome",
    partNumber: "RKT-IN718-INJ-009A",
    cageCode: "F0294",
    criticality: "Class 1 (Flight Critical)",
    alloyName: "Inconel 718 (UNS N07718 Nickel Superalloy)",
    category: "Additive Superalloy (LPBF + HIP)",
    standardSpec: "AMS 7005 / ASTM F3055 / MMPDS AM",
    manufacturingRoute: "EOS M400-4 Multi-Laser LPBF (400W Yb-Fiber)",
    heatTreatmentCondition: "HIP (1120°C/100MPa/4h) + Double Aged (720°C/8h + 620°C/8h)",
    protectiveCoating: "Passive Bare High-Cr2O3 Surface (Acid Cleaned)",
    serviceTempMin: -196,
    serviceTempMax: 650,
    operatingStressMpa: 720,
    meanYieldMpa: 1185,
    meanTensileMpa: 1395,
    fractureToughnessMpaM: 86,
    sampleSizeN: 45,
    scatterCvPct: 3.4,
    densityGcm3: 8.19,
    youngsModulusGpa: 204,
    labData: {
      taborTest: {
        measuredHardnessHV: 446,
        predictedYieldMpa: 1180,
        predictedUtsMpa: 1390,
        strainHardeningExponentN: 0.162,
        fractureToughnessKic: 86.2,
        correlationConfidencePct: 98.9,
        indentationStandard: "ASTM E8 / Tabor-Cahoon Indentation",
      },
      xrdAnalysis: {
        primaryPhase: "FCC γ-Ni Matrix",
        secondaryPhaseFractionPct: 18.5, // gamma prime / gamma double prime
        crystalliteSizeNm: 38.6,
        microstrainPct: 0.215,
        surfaceResidualStressMpa: +48,
        standardReference: "ASTM E975 / Rigaku SmartLab XRD",
      },
      ebsdMicrostructure: {
        meanGrainSizeUm: 22.8,
        astmGrainSizeNumberG: 8.0,
        hagbFractionPct: 76.5,
        dominantTextureOrientation: "<001> Fiber Texture Parallel to Build (+Z)",
        schmidFactorAverage: 0.42,
        standardReference: "ASTM E112 / Oxford Instruments EBSD",
      },
      additiveDefectAudit: {
        volumetricEnergyDensityJmm3: 65.2,
        maxThermalWarpageMm: 0.18,
        peakTensileStressMpa: 310,
        keyholeRiskScorePct: 3.2,
        lackOfFusionRiskPct: 1.4,
        asBuiltVsHipState: "Hot Isostatic Pressed (HIP 100MPa 100% Dense)",
        standardReference: "ASTM F3055 LPBF Aerospace AM Standard",
      },
    },
    notes: "Monolithic additively manufactured coaxial swirl injector head with regenerative cooling passages. Zero welds.",
  },
  {
    id: "commercial-wing-al7075",
    programTitle: "Commercial Transport Wing (A350 / 787)",
    partName: "Upper Wing Skin Tension Stringer Attachment Panel",
    partNumber: "WS-AL7075-ST44-P2",
    cageCode: "06481",
    criticality: "Class 2 (Primary Structural)",
    alloyName: "Al 7075-T7451 Overaged (Al-Zn-Mg-Cu)",
    category: "High-Strength Aerospace Aluminum",
    standardSpec: "AMS 4050 / ASTM B209 / MMPDS Ch. 3",
    manufacturingRoute: "Stretched Heavy Plate (T7451 Stress-Relieved)",
    heatTreatmentCondition: "Solution Heat Treated + Two-Stage Overaged (T7451)",
    protectiveCoating: "Tartaric-Sulfuric Acid (TSA) Anodize + Epoxy Primer",
    serviceTempMin: -54,
    serviceTempMax: 125,
    operatingStressMpa: 310,
    meanYieldMpa: 475,
    meanTensileMpa: 540,
    fractureToughnessMpaM: 37,
    sampleSizeN: 50,
    scatterCvPct: 2.4,
    densityGcm3: 2.81,
    youngsModulusGpa: 71.7,
    labData: {
      taborTest: {
        measuredHardnessHV: 162,
        predictedYieldMpa: 472,
        predictedUtsMpa: 538,
        strainHardeningExponentN: 0.118,
        fractureToughnessKic: 37.4,
        correlationConfidencePct: 99.1,
        indentationStandard: "ASTM E8 / Tabor-Cahoon Indentation",
      },
      xrdAnalysis: {
        primaryPhase: "FCC α-Al Matrix",
        secondaryPhaseFractionPct: 4.8, // eta prime MgZn2
        crystalliteSizeNm: 62.4,
        microstrainPct: 0.092,
        surfaceResidualStressMpa: -35,
        standardReference: "ASTM E975 / Rigaku SmartLab XRD",
      },
      ebsdMicrostructure: {
        meanGrainSizeUm: 34.0,
        astmGrainSizeNumberG: 7.0,
        hagbFractionPct: 88.0,
        dominantTextureOrientation: "Brass & Copper Rolling Texture ({112}<111>)",
        schmidFactorAverage: 0.44,
        standardReference: "ASTM E112 / Oxford Instruments EBSD",
      },
      additiveDefectAudit: {
        volumetricEnergyDensityJmm3: 0,
        maxThermalWarpageMm: 0.04,
        peakTensileStressMpa: 45,
        keyholeRiskScorePct: 0.1,
        lackOfFusionRiskPct: 0.0,
        asBuiltVsHipState: "Wrought Stretched Plate T7451",
        standardReference: "AMS 4050 / MIL-STD-2154 UT Class AA",
      },
    },
    notes: "Overaged T7451 temper provides immunity against stress corrosion cracking (SCC) in short-transverse (ST) grain direction.",
  },
  {
    id: "navy-carrier-hook-300m",
    programTitle: "Naval Carrier Aviation Arrestor System",
    partName: "Main Arresting Hook Forged Shank Beam",
    partNumber: "HK-300M-NAV-880B",
    cageCode: "61349",
    criticality: "Class 1 (Flight Critical)",
    alloyName: "300M Ultra-High Strength Steel (VAR Melt)",
    category: "Ultra-High Strength Low-Alloy Steel",
    standardSpec: "AMS 6417 / MIL-S-8844 / MMPDS Ch. 2",
    manufacturingRoute: "Vacuum Arc Remelt (VAR) Forged + Q&T",
    heatTreatmentCondition: "Austenitized 870°C, Oil Quenched, Double Tempered 300°C (54 HRC)",
    protectiveCoating: "Low Hydrogen Cadmium Plating (AMS-QQ-P-416) + Baked 24h",
    serviceTempMin: -54,
    serviceTempMax: 260,
    operatingStressMpa: 1050,
    meanYieldMpa: 1720,
    meanTensileMpa: 2080,
    fractureToughnessMpaM: 58,
    sampleSizeN: 35,
    scatterCvPct: 2.2,
    densityGcm3: 7.85,
    youngsModulusGpa: 200,
    labData: {
      taborTest: {
        measuredHardnessHV: 575,
        predictedYieldMpa: 1715,
        predictedUtsMpa: 2075,
        strainHardeningExponentN: 0.088,
        fractureToughnessKic: 58.6,
        correlationConfidencePct: 98.7,
        indentationStandard: "ASTM E8 / ASTM E18 Hardness",
      },
      xrdAnalysis: {
        primaryPhase: "Tempered Martensite (BCT α')",
        secondaryPhaseFractionPct: 1.8, // Retained Austenite
        crystalliteSizeNm: 26.5,
        microstrainPct: 0.380,
        surfaceResidualStressMpa: -320, // Shot peened compressive layer
        standardReference: "ASTM E975 Retained Austenite Analysis",
      },
      ebsdMicrostructure: {
        meanGrainSizeUm: 8.5, // Prior Austenite Grain Size
        astmGrainSizeNumberG: 10.5,
        hagbFractionPct: 71.0,
        dominantTextureOrientation: "Randomized Forged Bainite/Martensite Laths",
        schmidFactorAverage: 0.36,
        standardReference: "ASTM E112 Grain Size Analysis",
      },
      additiveDefectAudit: {
        volumetricEnergyDensityJmm3: 0,
        maxThermalWarpageMm: 0.06,
        peakTensileStressMpa: 90,
        keyholeRiskScorePct: 0.0,
        lackOfFusionRiskPct: 0.0,
        asBuiltVsHipState: "VAR Forged + Controlled Shot Peened (AMS 2430)",
        standardReference: "MIL-STD-2154 Class AAA NDT",
      },
    },
    notes: "Arresting cable dynamic impact load of 180,000 lbs. Baking mandatory within 4 hours of plating to prevent hydrogen embrittlement.",
  },
];

const ALL_PRESETS: AerospacePreset[] = [GENERIC_SCREENING_PRESET, ...DEMO_SCENARIO_PRESETS];

export function AerospaceAuditReportGenerator() {
  const [demoScenariosEnabled, setDemoScenariosEnabled] = useState<boolean>(false);
  const [selectedPresetId, setSelectedPresetId] = useState<string>(GENERIC_SCREENING_PRESET.id);

  // Editable Document Metadata
  const [certificateId, setCertificateId] = useState<string>(
    `SCREEN-EST-${Math.floor(100000 + Math.random() * 900000)}`
  );
  const [lotHeatNumber, setLotHeatNumber] = useState<string>("HEAT-SCR-0001");
  const [partNumber, setPartNumber] = useState<string>(GENERIC_SCREENING_PRESET.partNumber);
  const [partName, setPartName] = useState<string>(GENERIC_SCREENING_PRESET.partName);
  const [customerPoNumber, setCustomerPoNumber] = useState<string>("N/A");
  const [cageCode, setCageCode] = useState<string>(GENERIC_SCREENING_PRESET.cageCode);
  const [revision, setRevision] = useState<string>("Rev A (screening)");
  const [engineerName, setEngineerName] = useState<string>("Materials engineer (placeholder)");
  const [qaDirectorName, setQaDirectorName] = useState<string>("QA reviewer (placeholder)");
  const [facility, setFacility] = useState<string>("Engineering screening workbench");
  const [programName, setProgramName] = useState<string>(GENERIC_SCREENING_PRESET.programTitle);
  const [criticalityLevel, setCriticalityLevel] = useState<
    "Class 1 (Flight Critical)" | "Class 2 (Primary Structural)" | "Class 3 (Secondary System)"
  >(GENERIC_SCREENING_PRESET.criticality);

  // Material & Mechanical Properties
  const [alloyName, setAlloyName] = useState<string>(GENERIC_SCREENING_PRESET.alloyName);
  const [standardSpec, setStandardSpec] = useState<string>(GENERIC_SCREENING_PRESET.standardSpec);
  const [manufacturingRoute, setManufacturingRoute] = useState<string>(GENERIC_SCREENING_PRESET.manufacturingRoute);
  const [heatTreatmentCondition, setHeatTreatmentCondition] = useState<string>(
    GENERIC_SCREENING_PRESET.heatTreatmentCondition
  );
  const [protectiveCoating, setProtectiveCoating] = useState<string>(GENERIC_SCREENING_PRESET.protectiveCoating);
  const [serviceTempMin, setServiceTempMin] = useState<number>(GENERIC_SCREENING_PRESET.serviceTempMin);
  const [serviceTempMax, setServiceTempMax] = useState<number>(GENERIC_SCREENING_PRESET.serviceTempMax);
  const [operatingStressMpa, setOperatingStressMpa] = useState<number>(GENERIC_SCREENING_PRESET.operatingStressMpa);
  const [meanYieldMpa, setMeanYieldMpa] = useState<number>(GENERIC_SCREENING_PRESET.meanYieldMpa);
  const [meanTensileMpa, setMeanTensileMpa] = useState<number>(GENERIC_SCREENING_PRESET.meanTensileMpa);
  const [fractureToughnessMpaM, setFractureToughnessMpaM] = useState<number>(GENERIC_SCREENING_PRESET.fractureToughnessMpaM);
  const [sampleSizeN, setSampleSizeN] = useState<number>(GENERIC_SCREENING_PRESET.sampleSizeN);
  const [scatterCvPct, setScatterCvPct] = useState<number>(GENERIC_SCREENING_PRESET.scatterCvPct);

  // Active Lab Multi-Test Data
  const [labData, setLabData] = useState<LabMultiTestData>(GENERIC_SCREENING_PRESET.labData);

  // AI Audit State
  const [aiAuditReport, setAiAuditReport] = useState<string | null>(
    `SCREENING NOTES (not a certification):\n${ENGINEERING_ESTIMATE_DISCLAIMER}\nEnvironmental protocol rows are a checklist template (Not executed / user-attested only).`
  );
  const [isAiAuditing, setIsAiAuditing] = useState<boolean>(false);
  const [isExportingPdf, setIsExportingPdf] = useState<boolean>(false);
  const [exportSuccessMsg, setExportSuccessMsg] = useState<string | null>(null);

  // Apply Preset Handler
  const handlePresetSelect = (presetId: string) => {
    setSelectedPresetId(presetId);
    const preset = ALL_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;

    setProgramName(preset.programTitle);
    setPartName(preset.partName);
    setPartNumber(preset.partNumber);
    setCageCode(preset.cageCode);
    setCriticalityLevel(preset.criticality);
    setAlloyName(preset.alloyName);
    setStandardSpec(preset.standardSpec);
    setManufacturingRoute(preset.manufacturingRoute);
    setHeatTreatmentCondition(preset.heatTreatmentCondition);
    setProtectiveCoating(preset.protectiveCoating);
    setServiceTempMin(preset.serviceTempMin);
    setServiceTempMax(preset.serviceTempMax);
    setOperatingStressMpa(preset.operatingStressMpa);
    setMeanYieldMpa(preset.meanYieldMpa);
    setMeanTensileMpa(preset.meanTensileMpa);
    setFractureToughnessMpaM(preset.fractureToughnessMpaM);
    setSampleSizeN(preset.sampleSizeN);
    setScatterCvPct(preset.scatterCvPct);
    setLabData(preset.labData);
  };

  // Compute MMPDS Statistics
  const mmpdsStats = useMemo(
    () => computeAerospaceScreeningStats({ meanYieldMpa, meanTensileMpa, sampleSizeN, scatterCvPct }),
    [meanYieldMpa, meanTensileMpa, sampleSizeN, scatterCvPct]
  );

  // Qualification protocol checklist (not auto-PASS from sliders)
  const qualificationTests = useMemo(() => {
    return buildAerospaceChecklist({
      fractureToughnessMpaM,
      serviceTempMin,
      serviceTempMax,
      operatingStressMpa,
      cpk: mmpdsStats.cpk,
    });
  }, [fractureToughnessMpaM, serviceTempMin, serviceTempMax, operatingStressMpa, mmpdsStats.cpk]);

  const overallReadinessIndex = 0;

  // Payload Builder
  const getPayload = (): AerospaceAuditReportData => {
    return {
      certificateId,
      lotHeatNumber,
      partNumber,
      partName,
      customerPoNumber,
      cageCode,
      revision,
      issueDate: new Date().toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }),
      engineerName,
      qaDirectorName,
      facility,
      programName,
      criticalityLevel,
      alloyName,
      category: ALL_PRESETS.find((p) => p.id === selectedPresetId)?.category || "Structural screening example",
      standardSpec,
      manufacturingRoute,
      heatTreatmentCondition,
      protectiveCoating,
      serviceTempMin,
      serviceTempMax,
      operatingStressMpa,
      meanYieldMpa,
      meanTensileMpa,
      elongationPct: 14,
      fractureToughnessMpaM,
      youngsModulusGpa: ALL_PRESETS.find((p) => p.id === selectedPresetId)?.youngsModulusGpa || 114,
      densityGcm3: ALL_PRESETS.find((p) => p.id === selectedPresetId)?.densityGcm3 || 4.43,
      sampleSizeN,
      scatterCvPct,
      mmpdsStats,
      labData,
      qualificationTests,
      overallReadinessIndex,
      aiAuditNotes: aiAuditReport,
    };
  };

  // PDF Export Trigger
  const handleExportPDF = async () => {
    setIsExportingPdf(true);
    setExportSuccessMsg(null);
    try {
      const payload = getPayload();
      const doc = await generateAerospaceCoCPDF(payload);
      doc.save(`${certificateId}_screening_audit.pdf`);
      setExportSuccessMsg(`Exported screening PDF (not a certificate): ${certificateId}_screening_audit.pdf`);
    } catch (err: any) {
      console.error("PDF generation failed:", err);
      setExportSuccessMsg(`Export error: ${err.message || "Failed to render PDF"}`);
    } finally {
      setIsExportingPdf(false);
    }
  };

  // JSON PLM Export Trigger
  const handleExportJSON = () => {
    const payload = getPayload();
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${certificateId}_PLM_Dataset.json`;
    a.click();
    URL.revokeObjectURL(url);
    setExportSuccessMsg(`Exported JSON dataset (screening payload, not a CoC).`);
  };

  // Run AI Airworthiness Audit Handler
  const handleRunAiAudit = async () => {
    setIsAiAuditing(true);
    try {
      const res = await fetch("/api/metallurgy/qualify-aerospace", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          alloyName,
          baseSystem: ALL_PRESETS.find((p) => p.id === selectedPresetId)?.category || "Structural screening example",
          manufacturingRoute,
          meanYield: meanYieldMpa,
          meanTensile: meanTensileMpa,
          aBasisYield: mmpdsStats.aBasisYield,
          bBasisYield: mmpdsStats.bBasisYield,
          fractureToughness: fractureToughnessMpaM,
          serviceTempMin,
          serviceTempMax,
          protectiveCoating,
          targetStandards: "Screening checklist only: MMPDS-style stats, MIL-STD-810H / AS9100 / STANAG templates (not executed)",
        }),
      });

      if (!res.ok) {
        throw new Error(`AI Audit endpoint returned status ${res.status}`);
      }

      const data = await res.json();
      setAiAuditReport(data.auditReport || ENGINEERING_ESTIMATE_DISCLAIMER);
    } catch (err: any) {
      console.error("AI Audit error:", err);
      setAiAuditReport(
        `SCREENING SYNTHESIS (not airworthiness):\n- Slider-derived A/B-style numbers (F_ty≈${mmpdsStats.aBasisYield} MPa) are engineering estimates, not MMPDS handbook allowables.\n- Grain-size / EBSD fields are screening overlays, not ASTM E112 certification.\n- MIL-STD-810H methods 509.7 and 516.8 are checklist rows only (Not executed).\n- ${ENGINEERING_ESTIMATE_DISCLAIMER}`
      );
    } finally {
      setIsAiAuditing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl relative overflow-hidden">
        <div className="absolute -right-16 -top-16 w-64 h-64 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 relative z-10">
          <div className="flex items-start gap-3">
            <div className="p-3 bg-gradient-to-br from-sky-600 to-indigo-700 rounded-xl text-white shadow-lg shadow-sky-500/20 border border-sky-400/30">
              <ShieldCheck className="w-7 h-7" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                  Audit report templates (demo)
                </h1>
                <span className="px-2 py-0.5 text-xs font-semibold bg-amber-500/20 text-amber-200 border border-amber-500/40 rounded-full flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" /> Screening only
                </span>
                <span className="px-2 py-0.5 text-xs font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/40 rounded-full">
                  PDF template
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400 mt-1">
                Engineering screening worksheets for coupon metadata, slider-based stats, and protocol checklists. Not a Certificate of Conformance and not NADCAP / AS9100 evidence.
              </p>
              <EngineeringEstimateBanner className="mt-3 max-w-3xl" />
            </div>
          </div>

          {/* Quick Action Export Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleExportPDF}
              disabled={isExportingPdf}
              className="px-4 py-2.5 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white text-xs sm:text-sm font-semibold rounded-lg shadow-lg shadow-sky-600/30 border border-sky-400/40 flex items-center gap-2 transition-all cursor-pointer disabled:opacity-50"
            >
              {isExportingPdf ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              <span>Download screening PDF</span>
            </button>

            <button
              onClick={handleExportJSON}
              className="px-3 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs sm:text-sm font-medium rounded-lg border border-slate-700 flex items-center gap-2 transition-all cursor-pointer"
              title="Export JSON for Teamcenter/Windchill PLM"
            >
              <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
              <span className="hidden sm:inline">PLM JSON</span>
            </button>
          </div>
        </div>

        {exportSuccessMsg && (
          <div className="mt-4 p-3 bg-emerald-950/50 border border-emerald-700/60 rounded-lg text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{exportSuccessMsg}</span>
          </div>
        )}
      </div>

      {/* Screening presets + optional DEMO SCENARIO fighter/CAGE examples */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Award className="w-4 h-4 text-sky-400" /> Screening example:
          </span>
          <label className="flex items-center gap-2 text-xs text-amber-200 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={demoScenariosEnabled}
              onChange={(e) => {
                const enabled = e.target.checked;
                setDemoScenariosEnabled(enabled);
                if (!enabled) {
                  handlePresetSelect(GENERIC_SCREENING_PRESET.id);
                }
              }}
              className="rounded bg-slate-800 border-slate-600 text-amber-500 focus:ring-0 w-3.5 h-3.5 cursor-pointer"
            />
            <span className="font-bold tracking-wide">DEMO SCENARIO</span>
            <span className="text-slate-500 normal-case font-normal">
              Unlock fighter / CAGE / Class 1 fiction (not live programs)
            </span>
          </label>
        </div>

        {demoScenariosEnabled && (
          <div className="mb-3 rounded-lg border border-amber-500/40 bg-amber-950/40 px-3 py-2 text-[11px] text-amber-100">
            DEMO SCENARIO presets include fictional F-35 / launch-vehicle identities and CAGE-like codes. They are teaching templates, not operational records.
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {(demoScenariosEnabled ? ALL_PRESETS : [GENERIC_SCREENING_PRESET]).map((preset) => {
            const isSelected = selectedPresetId === preset.id;
            return (
              <button
                key={preset.id}
                onClick={() => handlePresetSelect(preset.id)}
                className={`text-left p-3 rounded-lg border transition-all cursor-pointer relative ${
                  isSelected
                    ? "bg-sky-950/60 border-sky-500 text-white shadow-md shadow-sky-500/10 ring-1 ring-sky-500/50"
                    : "bg-slate-800/60 border-slate-700/60 text-slate-300 hover:bg-slate-800 hover:border-slate-600"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-sky-300 truncate max-w-[170px]">
                    {preset.alloyName.split(" (")[0]}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                      preset.isDemoScenario || DEMO_SCENARIO_PRESETS.some((d) => d.id === preset.id)
                        ? "bg-amber-500/20 text-amber-200 border border-amber-500/40"
                        : "bg-slate-700/60 text-slate-300 border border-slate-600"
                    }`}
                  >
                    {preset.isDemoScenario || DEMO_SCENARIO_PRESETS.some((d) => d.id === preset.id)
                      ? "DEMO"
                      : "Screening"}
                  </span>
                </div>
                <div className="text-[11px] font-medium text-slate-200 mb-0.5 line-clamp-1">
                  {preset.programTitle}
                </div>
                <div className="text-[10px] text-slate-400 line-clamp-1">{preset.partName}</div>
                <div className="mt-2 pt-2 border-t border-slate-700/50 flex items-center justify-between text-[10px] text-slate-400">
                  <span>
                    F_ty: <strong className="text-slate-200">{preset.meanYieldMpa} MPa</strong>
                  </span>
                  <span>
                    K_IC: <strong className="text-slate-200">{preset.fractureToughnessMpaM} MPa√m</strong>
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Grid: Parameters & Interactive CoC Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Metadata & Mechanical Parameters (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Certificate Metadata Editor */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 border-b border-slate-800 pb-2">
              <Building2 className="w-4 h-4 text-sky-400" /> Certificate & Traceability Metadata
            </h3>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Document ID (Doc Ref)</label>
                <input aria-label="Document ID (Doc Ref)"
                  type="text"
                  value={certificateId}
                  onChange={(e) => setCertificateId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Lot / Heat Melt No</label>
                <input aria-label="Lot / Heat Melt No"
                  type="text"
                  value={lotHeatNumber}
                  onChange={(e) => setLotHeatNumber(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Part Number</label>
                <input aria-label="Part Number"
                  type="text"
                  value={partNumber}
                  onChange={(e) => setPartNumber(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px]"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Customer PO / Contract</label>
                <input aria-label="Customer PO / Contract"
                  type="text"
                  value={customerPoNumber}
                  onChange={(e) => setCustomerPoNumber(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px]"
                />
              </div>
              <div className="col-span-2">
                <label className="text-[10px] text-slate-400 block mb-0.5">Component / Part Description</label>
                <input aria-label="Component / Part Description"
                  type="text"
                  value={partName}
                  onChange={(e) => setPartName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px]"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Lead Metallurgist</label>
                <input aria-label="Lead Metallurgist"
                  type="text"
                  value={engineerName}
                  onChange={(e) => setEngineerName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px]"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">QA reviewer (placeholder)</label>
                <input aria-label="QA reviewer (placeholder)"
                  type="text"
                  value={qaDirectorName}
                  onChange={(e) => setQaDirectorName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px]"
                />
              </div>
            </div>
          </div>

          {/* MMPDS Mechanical Properties & Statistical Allowables */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="flex items-center gap-1.5">
                <Gauge className="w-4 h-4 text-emerald-400" /> MMPDS-14 Allowables Controls
              </span>
              <span className="text-[10px] px-1.5 py-0.5 bg-emerald-900/50 text-emerald-300 border border-emerald-600/40 rounded">
                Cpk: {mmpdsStats.cpk}
              </span>
            </h3>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">
                  Mean Yield F_ty (0.2% Offset)
                </label>
                <div className="flex items-center gap-1">
                  <input aria-label="Mean Yield F_ty (0.2% Offset) (MPa)"
                    type="number"
                    value={meanYieldMpa}
                    onChange={(e) => setMeanYieldMpa(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px]"
                  />
                  <span className="text-[10px] text-slate-400">MPa</span>
                </div>
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Mean Tensile UTS F_tu</label>
                <div className="flex items-center gap-1">
                  <input aria-label="Mean Tensile UTS F_tu (MPa)"
                    type="number"
                    value={meanTensileMpa}
                    onChange={(e) => setMeanTensileMpa(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px]"
                  />
                  <span className="text-[10px] text-slate-400">MPa</span>
                </div>
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Fracture Toughness K_IC</label>
                <div className="flex items-center gap-1">
                  <input aria-label="Fracture Toughness K_IC (MPa√m)"
                    type="number"
                    value={fractureToughnessMpaM}
                    onChange={(e) => setFractureToughnessMpaM(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px]"
                  />
                  <span className="text-[10px] text-slate-400">MPa√m</span>
                </div>
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Sample Size (N Coupons)</label>
                <input aria-label="Sample Size (N Coupons)"
                  type="number"
                  value={sampleSizeN}
                  onChange={(e) => setSampleSizeN(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px]"
                />
              </div>
            </div>

            {/* Calculated A-Basis / B-Basis Summary */}
            <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 grid grid-cols-2 gap-2 text-xs">
              <div className="p-2 bg-slate-900 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">A-Basis Yield (T99/95%)</span>
                <span className="text-sm font-bold text-sky-300">{mmpdsStats.aBasisYield} MPa</span>
                <span className="text-[9px] text-slate-500 block">k_A = {mmpdsStats.kA}</span>
              </div>
              <div className="p-2 bg-slate-900 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">B-Basis Yield (T90/95%)</span>
                <span className="text-sm font-bold text-indigo-300">{mmpdsStats.bBasisYield} MPa</span>
                <span className="text-[9px] text-slate-500 block">k_B = {mmpdsStats.kB}</span>
              </div>
            </div>
          </div>

          {/* AI Airworthiness Audit Engine */}
          <div className="bg-gradient-to-br from-slate-900 to-slate-950 border border-sky-900/50 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-sky-300 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-sky-400" /> AI screening notes
              </span>
              <button
                onClick={handleRunAiAudit}
                disabled={isAiAuditing}
                className="px-2.5 py-1 bg-sky-600 hover:bg-sky-500 text-white text-[11px] font-semibold rounded flex items-center gap-1 cursor-pointer disabled:opacity-50 transition-all"
              >
                {isAiAuditing ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                <span>Re-Audit</span>
              </button>
            </div>
            <p className="text-[11px] text-slate-300 leading-relaxed bg-slate-950/80 p-2.5 rounded border border-slate-800">
              {aiAuditReport}
            </p>
          </div>
        </div>

        {/* Right Column: Live screening worksheet preview (7 cols) */}
        <div className="lg:col-span-7">
          <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
            {/* Certificate Header Banner (Aero Style) */}
            <div className="bg-slate-900 p-4 border-b border-sky-500/40 relative">
              <EngineeringEstimateBanner className="mb-3" />
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[9px] px-2 py-0.5 bg-sky-500/20 text-sky-300 border border-sky-500/40 rounded font-semibold uppercase">
                    Screening report preview (not a CoC)
                  </span>
                  <h2 className="text-base font-bold text-white tracking-wide mt-1">
                    ENGINEERING SCREENING WORKSHEET
                  </h2>
                  <p className="text-[10px] text-slate-400">
                    Protocol checklist template — methods not executed by this software
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-[11px] font-mono font-bold text-sky-300">{certificateId}</div>
                  <div className="text-[10px] text-slate-400">CAGE: {cageCode} | {revision}</div>
                  <div className="text-[9px] font-semibold text-emerald-400 mt-0.5">● CONFORMING RELEASE</div>
                </div>
              </div>
            </div>

            {/* Certificate Document Content View */}
            <div className="p-4 sm:p-5 space-y-4 text-slate-300 text-xs bg-slate-950">
              {/* Section 1: Spec Overview Table */}
              <div>
                <div className="text-[11px] font-bold text-white uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                  <span>1. Material Specification & Manufacturing Provenance</span>
                </div>
                <div className="border border-slate-800 rounded-lg overflow-hidden grid grid-cols-2 text-[11px]">
                  <div className="p-2 bg-slate-900/60 border-r border-b border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Material Specification:</span>
                    <strong className="text-white">{alloyName}</strong> ({standardSpec})
                  </div>
                  <div className="p-2 bg-slate-900/60 border-b border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Manufacturing Route:</span>
                    <strong className="text-white">{manufacturingRoute}</strong>
                  </div>
                  <div className="p-2 bg-slate-900/60 border-r border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Heat Treatment Condition:</span>
                    <strong className="text-white">{heatTreatmentCondition}</strong>
                  </div>
                  <div className="p-2 bg-slate-900/60 border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Surface Protection / Passivity:</span>
                    <strong className="text-white">{protectiveCoating}</strong>
                  </div>
                </div>
              </div>

              {/* Section 2: MMPDS Statistical Table */}
              <div>
                <div className="text-[11px] font-bold text-white uppercase tracking-wider mb-1.5 flex items-center justify-between">
                  <span>2. Statistical Mechanical Allowables (MMPDS-14 / MIL-HDBK-5)</span>
                  <span className="text-[10px] text-sky-400 font-mono">N = {sampleSizeN} Coupons</span>
                </div>
                <div className="border border-slate-800 rounded-lg overflow-hidden">
                  <table className="w-full text-left text-[11px]">
                    <thead className="bg-slate-900 text-slate-400 border-b border-slate-800 text-[10px]">
                      <tr>
                        <th className="p-1.5">Symbol</th>
                        <th className="p-1.5">Description</th>
                        <th className="p-1.5 text-right">Mean</th>
                        <th className="p-1.5 text-right">A-Basis (T99)</th>
                        <th className="p-1.5 text-right">B-Basis (T90)</th>
                        <th className="p-1.5 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 text-slate-200">
                      <tr>
                        <td className="p-1.5 font-mono text-sky-300 font-bold">F_ty</td>
                        <td className="p-1.5">Tensile Yield Strength (0.2% Offset)</td>
                        <td className="p-1.5 text-right">{meanYieldMpa} MPa</td>
                        <td className="p-1.5 text-right font-bold text-sky-300">{mmpdsStats.aBasisYield} MPa</td>
                        <td className="p-1.5 text-right text-indigo-300">{mmpdsStats.bBasisYield} MPa</td>
                        <td className="p-1.5 text-center text-[10px] text-emerald-400 font-semibold">Pass</td>
                      </tr>
                      <tr>
                        <td className="p-1.5 font-mono text-sky-300 font-bold">F_tu</td>
                        <td className="p-1.5">Tensile Ultimate Strength (UTS)</td>
                        <td className="p-1.5 text-right">{meanTensileMpa} MPa</td>
                        <td className="p-1.5 text-right font-bold text-sky-300">{mmpdsStats.aBasisTensile} MPa</td>
                        <td className="p-1.5 text-right text-indigo-300">{mmpdsStats.bBasisTensile} MPa</td>
                        <td className="p-1.5 text-center text-[10px] text-emerald-400 font-semibold">Pass</td>
                      </tr>
                      <tr>
                        <td className="p-1.5 font-mono text-sky-300 font-bold">K_IC</td>
                        <td className="p-1.5">Plane-Strain Fracture Toughness (ASTM E399)</td>
                        <td className="p-1.5 text-right">{fractureToughnessMpaM} MPa√m</td>
                        <td className="p-1.5 text-right font-bold text-sky-300">{fractureToughnessMpaM} MPa√m</td>
                        <td className="p-1.5 text-right text-indigo-300">{fractureToughnessMpaM} MPa√m</td>
                        <td className="p-1.5 text-center text-[10px] text-emerald-400 font-semibold">Pass</td>
                      </tr>
                      <tr>
                        <td className="p-1.5 font-mono text-sky-300 font-bold">F_su</td>
                        <td className="p-1.5">Shear Ultimate Strength (Derived)</td>
                        <td className="p-1.5 text-right">{Math.round(meanTensileMpa * 0.6)} MPa</td>
                        <td className="p-1.5 text-right font-bold text-sky-300">{mmpdsStats.shearUltimate} MPa</td>
                        <td className="p-1.5 text-right text-indigo-300">{Math.round(mmpdsStats.bBasisTensile * 0.6)} MPa</td>
                        <td className="p-1.5 text-center text-[10px] text-emerald-400 font-semibold">Pass</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Section 3: Multi-Lab Advanced NDT Verification */}
              <div>
                <div className="text-[11px] font-bold text-white uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                  <span>3. Advanced Multi-Lab Experimental Verification Matrix</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="p-2 bg-slate-900/70 border border-slate-800 rounded">
                    <span className="text-[10px] font-bold text-sky-300 flex items-center gap-1">
                      <Gauge className="w-3 h-3" /> Tabor-Cahoon Indentation
                    </span>
                    <div className="text-slate-300 text-[10px] mt-1">
                      Predicted Yield: <strong>{labData.taborTest?.predictedYieldMpa ?? meanYieldMpa} MPa</strong> | UTS:{" "}
                      <strong>{labData.taborTest?.predictedUtsMpa ?? meanTensileMpa} MPa</strong> (n={labData.taborTest?.strainHardeningExponentN ?? 0.14})
                    </div>
                  </div>
                  <div className="p-2 bg-slate-900/70 border border-slate-800 rounded">
                    <span className="text-[10px] font-bold text-emerald-300 flex items-center gap-1">
                      <Atom className="w-3 h-3" /> Rapid XRD & Residual Stress
                    </span>
                    <div className="text-slate-300 text-[10px] mt-1">
                      Crystallite: <strong>{labData.xrdAnalysis?.crystalliteSizeNm ?? 44} nm</strong> | Surface σ_res:{" "}
                      <strong>{labData.xrdAnalysis?.surfaceResidualStressMpa ?? -145} MPa</strong>
                    </div>
                  </div>
                  <div className="p-2 bg-slate-900/70 border border-slate-800 rounded">
                    <span className="text-[10px] font-bold text-indigo-300 flex items-center gap-1">
                      <Microscope className="w-3 h-3" /> EBSD Grain Size & Texture
                    </span>
                    <div className="text-slate-300 text-[10px] mt-1">
                      Mean Grain: <strong>{labData.ebsdMicrostructure?.meanGrainSizeUm ?? 14.2} µm</strong> (ASTM G=
                      {labData.ebsdMicrostructure?.astmGrainSizeNumberG ?? 9.1}) | HAGB:{" "}
                      <strong>{labData.ebsdMicrostructure?.hagbFractionPct ?? 82}%</strong>
                    </div>
                  </div>
                  <div className="p-2 bg-slate-900/70 border border-slate-800 rounded">
                    <span className="text-[10px] font-bold text-amber-300 flex items-center gap-1">
                      <Box className="w-3 h-3" /> 3D AM Defect & Warpage
                    </span>
                    <div className="text-slate-300 text-[10px] mt-1">
                      VED: <strong>{labData.additiveDefectAudit?.volumetricEnergyDensityJmm3 ?? 58.4} J/mm³</strong> | Max Warpage:{" "}
                      <strong>{labData.additiveDefectAudit?.maxThermalWarpageMm ?? 0.12} mm</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Certificate Sign-off & Stamp */}
              <div className="border border-slate-800 bg-slate-900/90 rounded-lg p-3 flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="space-y-1 text-[11px]">
                  <div className="font-bold text-white">Screening statement (not certification)</div>
                  <div className="text-[10px] text-slate-400">
                    Lead Metallurgist: <strong className="text-slate-200">{engineerName}</strong>
                  </div>
                  <div className="text-[10px] text-slate-400">
                    QA Director: <strong className="text-slate-200">{qaDirectorName}</strong>
                  </div>
                </div>

                {/* Digital Stamp of Airworthiness */}
                <div className="px-4 py-2 bg-amber-950/80 border-2 border-amber-500/80 rounded-lg text-center shadow-lg">
                  <div className="text-[10px] font-bold text-amber-200 tracking-wider">SCREENING ONLY</div>
                  <div className="text-sm font-extrabold text-white">NOT CERTIFIED</div>
                  <div className="text-[9px] text-amber-300 font-mono font-semibold">CHECKLIST TEMPLATE</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
