import React, { useState, useMemo } from "react";
import {
  ShieldCheck,
  Award,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileText,
  Activity,
  Layers,
  Sparkles,
  Download,
  Printer,
  ChevronRight,
  Info,
  Compass,
  Gauge,
  Flame,
  Droplet,
  Zap,
  RefreshCw,
  Cpu,
  Check,
  Crosshair,
  TrendingUp,
  FileSpreadsheet,
  FileCode,
  X,
} from "lucide-react";
import { MmpdsBasisResult, QualificationTestEvaluation } from "../types";
import { generateAerospaceCoCPDF, CoCData } from "../utils/exportAerospaceCoC";
import { ENGINEERING_ESTIMATE_DISCLAIMER, EngineeringEstimateBanner } from "../utils/engineeringDisclaimer";

// Standard Aerospace & Defense Alloy Presets with Authentic Base Metallurgical Data
interface AlloyPreset {
  id: string;
  name: string;
  category: string;
  standardSpec: string;
  defaultRoute: string;
  meanYieldMpa: number;
  meanTensileMpa: number;
  elongationPct: number;
  fractureToughnessMpaM: number;
  youngsModulusGpa: number;
  densityGcm3: number;
  defaultTempMin: number;
  defaultTempMax: number;
  defaultCoating: string;
  prenScore?: number;
  notes: string;
}

const ALLOY_PRESETS: AlloyPreset[] = [
  {
    id: "ti-6al-4v-ams4928",
    name: "Ti-6Al-4V Grade 5",
    category: "Titanium Alpha-Beta Alloy",
    standardSpec: "AMS 4928 / AMS 4911 / MIL-T-9047",
    defaultRoute: "Wrought / Die Forged",
    meanYieldMpa: 930,
    meanTensileMpa: 1010,
    elongationPct: 14,
    fractureToughnessMpaM: 68,
    youngsModulusGpa: 114,
    densityGcm3: 4.43,
    defaultTempMin: -65,
    defaultTempMax: 380,
    defaultCoating: "Titanium Anodize (AMS 2488 Type II)",
    prenScore: 32,
    notes: "High strength-to-weight airframe structural forging, excellent marine corrosion passivity.",
  },
  {
    id: "ti-10-2-3-ams4984",
    name: "Ti-10V-2Fe-3Al (Near-Beta)",
    category: "Near-Beta Titanium Alloy",
    standardSpec: "AMS 4983 / AMS 4984 / MMPDS Ch. 5",
    defaultRoute: "Die Forged & Aged (STA)",
    meanYieldMpa: 1190,
    meanTensileMpa: 1260,
    elongationPct: 10,
    fractureToughnessMpaM: 52,
    youngsModulusGpa: 110,
    densityGcm3: 4.65,
    defaultTempMin: -54,
    defaultTempMax: 315,
    defaultCoating: "Titanium Anodize (AMS 2488)",
    prenScore: 30,
    notes: "High hardenability near-beta alloy for large section heavy landing gear forgings and rotor hubs.",
  },
  {
    id: "inconel-718-ams5662",
    name: "Inconel 718 Superalloy",
    category: "Nickel-Base Superalloy",
    standardSpec: "AMS 5662 / AMS 5663 / N07718",
    defaultRoute: "Wrought / Double Aged",
    meanYieldMpa: 1220,
    meanTensileMpa: 1440,
    elongationPct: 18,
    fractureToughnessMpaM: 95,
    youngsModulusGpa: 205,
    densityGcm3: 8.19,
    defaultTempMin: -196,
    defaultTempMax: 650,
    defaultCoating: "Passivated / Bare Passive Cr2O3 Film",
    prenScore: 48,
    notes: "Gamma-double-prime precipitation hardened for turbine disks, cryogenic to 650°C creep resistance.",
  },
  {
    id: "inconel-625-ams5666",
    name: "Inconel 625 (UNS N06625)",
    category: "Nickel-Chromium-Molybdenum Superalloy",
    standardSpec: "AMS 5666 / ASTM B443 / MIL-N-24410",
    defaultRoute: "Wrought Annealed Grade 1",
    meanYieldMpa: 520,
    meanTensileMpa: 930,
    elongationPct: 45,
    fractureToughnessMpaM: 120,
    youngsModulusGpa: 207,
    densityGcm3: 8.44,
    defaultTempMin: -196,
    defaultTempMax: 980,
    defaultCoating: "Bare Passive Cr2O3 Film (Immune to Pitting)",
    prenScore: 51,
    notes: "Outstanding chloride pitting immunity (PREN 51), naval submarine exhaust and rocket engine combustion liners.",
  },
  {
    id: "al-7075-t651",
    name: "Al 7075-T651",
    category: "High-Strength Aluminum (Al-Zn-Mg-Cu)",
    standardSpec: "AMS 4045 / ASTM B209 / QQ-A-250/12",
    defaultRoute: "Rolled Plate (T651)",
    meanYieldMpa: 515,
    meanTensileMpa: 580,
    elongationPct: 11,
    fractureToughnessMpaM: 29,
    youngsModulusGpa: 71,
    densityGcm3: 2.81,
    defaultTempMin: -54,
    defaultTempMax: 120,
    defaultCoating: "Chromic Anodize (MIL-A-8625 Type I) + Epoxy Primer",
    prenScore: 12,
    notes: "Primary airframe upper wing skins. High strength, requires strict corrosion barrier in ST direction.",
  },
  {
    id: "al-7050-t7451",
    name: "Al 7050-T7451 Overaged",
    category: "Thick Section Aircraft Aluminum",
    standardSpec: "AMS 4050 / MIL-A-22771 / MMPDS Ch. 3",
    defaultRoute: "Heavy Forged / Thick Plate",
    meanYieldMpa: 470,
    meanTensileMpa: 535,
    elongationPct: 12,
    fractureToughnessMpaM: 36,
    youngsModulusGpa: 71.5,
    densityGcm3: 2.83,
    defaultTempMin: -54,
    defaultTempMax: 125,
    defaultCoating: "Tartaric-Sulfuric Acid Anodize (TSA) + Primer",
    prenScore: 13,
    notes: "Thick plate airframe bulkheads with superior exfoliation and stress corrosion cracking (SCC) resistance.",
  },
  {
    id: "al-2024-t351",
    name: "Al 2024-T351 (Al-Cu-Mg)",
    category: "Damage-Tolerant Aluminum Alloy",
    standardSpec: "AMS 4037 / QQ-A-250/4 / ASTM B209",
    defaultRoute: "Rolled Sheet / Extrusion (T351)",
    meanYieldMpa: 330,
    meanTensileMpa: 475,
    elongationPct: 18,
    fractureToughnessMpaM: 41,
    youngsModulusGpa: 73.1,
    densityGcm3: 2.78,
    defaultTempMin: -54,
    defaultTempMax: 120,
    defaultCoating: "Alclad Pure Al Cladding + Chromic Anodize",
    prenScore: 11,
    notes: "Lower wing skin tension panels and pressurized fuselage skin due to high fracture toughness and fatigue growth resistance.",
  },
  {
    id: "al-li-2099-t83",
    name: "Al-Li 2099-T83 (Al-Li-Cu)",
    category: "3rd Gen Aluminum-Lithium",
    standardSpec: "AMS 4296 / MMPDS Item 3.7.12",
    defaultRoute: "Extruded / Plate (T83)",
    meanYieldMpa: 490,
    meanTensileMpa: 540,
    elongationPct: 9,
    fractureToughnessMpaM: 34,
    youngsModulusGpa: 79,
    densityGcm3: 2.63,
    defaultTempMin: -54,
    defaultTempMax: 100,
    defaultCoating: "Tartaric-Sulfuric Acid Anodizing (TSA) + Primer",
    prenScore: 14,
    notes: "Low density (8% weight saving) with high Young's modulus for fuselage stringers and floor beams.",
  },
  {
    id: "steel-300m-ams6417",
    name: "300M Ultra-High Strength Steel",
    category: "Modified 4340 Alloy Steel",
    standardSpec: "AMS 6417 / MIL-S-8844",
    defaultRoute: "VAR Forged & Q&T (54 HRC)",
    meanYieldMpa: 1720,
    meanTensileMpa: 2080,
    elongationPct: 10,
    fractureToughnessMpaM: 58,
    youngsModulusGpa: 200,
    densityGcm3: 7.85,
    defaultTempMin: -54,
    defaultTempMax: 260,
    defaultCoating: "Low Hydrogen Cadmium Plate (AMS-QQ-P-416) + Baked",
    prenScore: 8,
    notes: "Heavy military aircraft landing gear forgings and arrestor hooks. Susceptible to hydrogen embrittlement.",
  },
  {
    id: "aeromet-100-ams6532",
    name: "Aermet 100 Cobalt-Nickel Steel",
    category: "Ultra-Tough Secondary Hardening Steel",
    standardSpec: "AMS 6532 / MIL-S-8984 / UNS K92580",
    defaultRoute: "VIM/VAR Forged & Hardened",
    meanYieldMpa: 1760,
    meanTensileMpa: 1965,
    elongationPct: 14,
    fractureToughnessMpaM: 115,
    youngsModulusGpa: 194,
    densityGcm3: 7.89,
    defaultTempMin: -54,
    defaultTempMax: 425,
    defaultCoating: "Zinc-Nickel Plating (AMS 2417) / Cadmium",
    prenScore: 10,
    notes: "Exceptional fracture toughness (115 MPa√m) at ultra-high strength for military rotor masts and armor-piercing shafts.",
  },
  {
    id: "maraging-300-mil-s-46850",
    name: "Maraging 300 (Vascomax 300)",
    category: "Carbon-Free Maraging Nickel Steel",
    standardSpec: "MIL-S-46850 / AMS 6514 / ASTM A538",
    defaultRoute: "VIM/VAR Bar & Aged (480°C)",
    meanYieldMpa: 2010,
    meanTensileMpa: 2060,
    elongationPct: 11,
    fractureToughnessMpaM: 45,
    youngsModulusGpa: 190,
    densityGcm3: 8.0,
    defaultTempMin: -54,
    defaultTempMax: 400,
    defaultCoating: "Chemical Nickel / Passivation",
    prenScore: 7,
    notes: "Near-zero distortion during aging, high hardness for rocket motor cases, centrifuges, and missile fins.",
  },
  {
    id: "stainless-17-4ph-h900",
    name: "17-4PH (AISI 630) H900",
    category: "Martensitic Precipitation Hardened",
    standardSpec: "AMS 5604 / ASTM A564 / UNS S17400",
    defaultRoute: "Bar / Forged (H900 Peak Age)",
    meanYieldMpa: 1180,
    meanTensileMpa: 1320,
    elongationPct: 14,
    fractureToughnessMpaM: 78,
    youngsModulusGpa: 196,
    densityGcm3: 7.78,
    defaultTempMin: -54,
    defaultTempMax: 315,
    defaultCoating: "Nitric Acid Passivation (AMS 2700 Method 1)",
    prenScore: 23,
    notes: "High strength aerospace fasteners and structural brackets with good general corrosion resistance.",
  },
  {
    id: "stainless-custom-465",
    name: "Custom 465 Stainless",
    category: "Premium PH Martensitic Stainless",
    standardSpec: "AMS 5936 / ASTM A564 / MMPDS Ch. 2",
    defaultRoute: "VAR Forged & H950 Aged",
    meanYieldMpa: 1655,
    meanTensileMpa: 1790,
    elongationPct: 13,
    fractureToughnessMpaM: 88,
    youngsModulusGpa: 200,
    densityGcm3: 7.82,
    defaultTempMin: -54,
    defaultTempMax: 370,
    defaultCoating: "Passivation (AMS 2700 Type 2)",
    prenScore: 26,
    notes: "High strength combined with high stress corrosion cracking threshold (K_ISCC) for naval aircraft landing gear.",
  },
  {
    id: "rene-41-ams5545",
    name: "René 41 Superalloy",
    category: "High-Temperature Gamma-Prime Nickel",
    standardSpec: "AMS 5545 / AMS 5712 / UNS N07041",
    defaultRoute: "Sheet / Forged (Fully Aged)",
    meanYieldMpa: 1040,
    meanTensileMpa: 1420,
    elongationPct: 16,
    fractureToughnessMpaM: 82,
    youngsModulusGpa: 218,
    densityGcm3: 8.25,
    defaultTempMin: -54,
    defaultTempMax: 870,
    defaultCoating: "Aluminide Diffusion Coating / TBC",
    prenScore: 42,
    notes: "Turbine afterburner casings, ramjet missile bodies, retaining rings subject to 870°C high stress.",
  },
  {
    id: "haynes-230-ams5878",
    name: "Haynes 230 (UNS N06230)",
    category: "Nickel-Chromium-Tungsten Superalloy",
    standardSpec: "AMS 5878 / ASTM B435 / MIL-N-24707",
    defaultRoute: "Wrought Solution Annealed",
    meanYieldMpa: 390,
    meanTensileMpa: 870,
    elongationPct: 47,
    fractureToughnessMpaM: 135,
    youngsModulusGpa: 211,
    densityGcm3: 8.97,
    defaultTempMin: -54,
    defaultTempMax: 1150,
    defaultCoating: "Bare Protective Film / Thermal Barrier",
    prenScore: 45,
    notes: "Exceptional resistance to high-temperature nitridation and grain coarsening up to 1150°C in combustors.",
  },
  {
    id: "lpbf-ti64-hip",
    name: "LPBF Ti-6Al-4V (Additive + HIP)",
    category: "Additive Manufacturing (DMLS/LPBF)",
    standardSpec: "AMS 7000 / ASTM F2924 / MMPDS AM",
    defaultRoute: "Laser PBF + HIP (920°C/100MPa) + Anneal",
    meanYieldMpa: 945,
    meanTensileMpa: 1030,
    elongationPct: 13,
    fractureToughnessMpaM: 62,
    youngsModulusGpa: 112,
    densityGcm3: 4.42,
    defaultTempMin: -65,
    defaultTempMax: 380,
    defaultCoating: "Anodize Type II (AMS 2488)",
    prenScore: 32,
    notes: "Hot Isostatic Pressed additive structural component with healed micro-porosity for aerospace brackets.",
  },
  {
    id: "lpbf-inconel718-hip",
    name: "LPBF Inconel 718 (Additive + HIP)",
    category: "Additive Superalloy (LPBF)",
    standardSpec: "AMS 7005 / ASTM F3055 / MMPDS AM",
    defaultRoute: "LPBF + HIP (1120°C) + Direct Double Age",
    meanYieldMpa: 1180,
    meanTensileMpa: 1390,
    elongationPct: 15,
    fractureToughnessMpaM: 84,
    youngsModulusGpa: 202,
    densityGcm3: 8.19,
    defaultTempMin: -196,
    defaultTempMax: 650,
    defaultCoating: "Passivated / TBC",
    prenScore: 48,
    notes: "Rocket injector heads and complex cooled turbine vanes produced with zero weld seams.",
  },
  {
    id: "lpbf-al-f357-hip",
    name: "LPBF Al-F357 (Al-Si7-Mg0.6 AM)",
    category: "High-Strength Additive Aluminum",
    standardSpec: "AMS 4478 / ASTM F3318 / MMPDS AM",
    defaultRoute: "LPBF + T6 Heat Treated (Sol + Age)",
    meanYieldMpa: 340,
    meanTensileMpa: 395,
    elongationPct: 9,
    fractureToughnessMpaM: 26,
    youngsModulusGpa: 72,
    densityGcm3: 2.68,
    defaultTempMin: -54,
    defaultTempMax: 130,
    defaultCoating: "Sulfuric Anodize (MIL-A-8625 Type II) + Primer",
    prenScore: 10,
    notes: "Beryllium-free aerospace heat exchangers and lightweight satellite avionics chassis.",
  },
];

// Manufacturing Process Knockdown / Scatter Profiles
interface MfgRouteConfig {
  id: string;
  name: string;
  scatterCvPct: number; // Coefficient of variation %
  typicalDefectDensity: string;
  castingFactorRequired: boolean;
  ndcClass: string;
  description: string;
}

const MFG_ROUTES: MfgRouteConfig[] = [
  {
    id: "wrought_forged",
    name: "Wrought / Closed-Die Forged (AMS Spec)",
    scatterCvPct: 2.8,
    typicalDefectDensity: "< 0.01% (Clean VAR/VIM melt)",
    castingFactorRequired: false,
    ndcClass: "Ultrasonic Class AAA (MIL-STD-2154)",
    description: "Highest structural integrity, uniform grain refinement, minimum statistical scatter.",
  },
  {
    id: "rolled_plate",
    name: "Rolled Sheet & Plate (L / LT Oriented)",
    scatterCvPct: 3.4,
    typicalDefectDensity: "< 0.03% (Inclusions ASTM E45 A/B)",
    castingFactorRequired: false,
    ndcClass: "Ultrasonic Class A",
    description: "Moderate directional anisotropy between Longitudinal (L) and Short-Transverse (ST) directions.",
  },
  {
    id: "extruded",
    name: "Extruded Structural Profiles",
    scatterCvPct: 3.8,
    typicalDefectDensity: "< 0.04% (Grain boundary segregation)",
    castingFactorRequired: false,
    ndcClass: "Ultrasonic Class B",
    description: "Elongated fibrous grain structure in extrusion direction, slightly higher LT scatter.",
  },
  {
    id: "investment_cast",
    name: "Investment Casting (A356 / Ti / Inconel)",
    scatterCvPct: 6.2,
    typicalDefectDensity: "0.1 - 0.4% (Micro-shrinkage & gas pores)",
    castingFactorRequired: true,
    ndcClass: "Radiographic Grade A/B (ASTM E192)",
    description: "Requires 1.25x or 1.50x casting factor knockdown if not 100% hot-isostatic-pressed.",
  },
  {
    id: "lpbf_as_built",
    name: "Additive LPBF / DMLS (As-Built / Stress Relieved)",
    scatterCvPct: 8.5,
    typicalDefectDensity: "0.2 - 0.8% (Keyhole & lack-of-fusion voids)",
    castingFactorRequired: false,
    ndcClass: "High CT Scan / NDT critical",
    description: "High residual thermal stress, un-healed sub-surface pores, high statistical property scatter.",
  },
  {
    id: "lpbf_hip_treated",
    name: "Additive LPBF + HIP (Hot Isostatic Pressed) + Heat Treated",
    scatterCvPct: 3.6,
    typicalDefectDensity: "< 0.02% (Densified >99.95%)",
    castingFactorRequired: false,
    ndcClass: "Ultrasonic / Micro-CT Class A",
    description: "HIP at 100-150 MPa closes internal gas porosity and yields wrought-like fatigue endurance.",
  },
];

// Protective Surface Treatments
const COATING_OPTIONS = [
  { id: "anodize_chromic", name: "Chromic Acid Anodize (MIL-A-8625 Type I) + Epoxy Primer", saltFogBonusHrs: 500, galvanicBonus: 0.9 },
  { id: "anodize_sulfuric", name: "Sulfuric Anodize (MIL-A-8625 Type II / Hardcoat Type III)", saltFogBonusHrs: 1000, galvanicBonus: 0.95 },
  { id: "cadmium_plate", name: "Low-Hydrogen Cadmium Plating (AMS-QQ-P-416) + Baked", saltFogBonusHrs: 1500, galvanicBonus: 0.98 },
  { id: "zinc_nickel", name: "Zinc-Nickel Plating (AMS 2417) + Trivalent Passivation", saltFogBonusHrs: 1200, galvanicBonus: 0.95 },
  { id: "passivation_ams", name: "Chemical Passivation (AMS 2700 Method 1 / ASTM A967)", saltFogBonusHrs: 336, galvanicBonus: 0.85 },
  { id: "thermal_barrier", name: "Thermal Barrier Coating (TBC YSZ + MCrAlY Bond Coat)", saltFogBonusHrs: 2000, galvanicBonus: 0.99 },
  { id: "bare_metal", name: "Bare As-Machined (No Protective Barrier)", saltFogBonusHrs: 24, galvanicBonus: 0.2 },
];

export const StandardQualificationEngine: React.FC = () => {
  // Active Preset or Custom
  const [selectedPresetId, setSelectedPresetId] = useState<string>("ti-6al-4v-ams4928");
  const [selectedMfgRouteId, setSelectedMfgRouteId] = useState<string>("wrought_forged");
  const [selectedCoatingId, setSelectedCoatingId] = useState<string>("anodize_chromic");

  // Core Inputs
  const [alloyName, setAlloyName] = useState<string>("Ti-6Al-4V Grade 5");
  const [meanYieldMpa, setMeanYieldMpa] = useState<number>(930);
  const [meanTensileMpa, setMeanTensileMpa] = useState<number>(1010);
  const [fractureToughnessMpaM, setFractureToughnessMpaM] = useState<number>(68);
  const [sampleSizeN, setSampleSizeN] = useState<number>(60); // 10 to 500
  const [customScatterCv, setCustomScatterCv] = useState<number>(2.8);
  const [serviceTempMin, setServiceTempMin] = useState<number>(-54);
  const [serviceTempMax, setServiceTempMax] = useState<number>(350);
  const [operatingStressMpa, setOperatingStressMpa] = useState<number>(550);
  const [targetApplication, setTargetApplication] = useState<string>("Structural coupon screening (unlabeled)");

  // AI Audit State
  const [isAiAuditing, setIsAiAuditing] = useState<boolean>(false);
  const [aiAuditReport, setAiAuditReport] = useState<string | null>(null);
  const [auditErrorMessage, setAuditErrorMessage] = useState<string | null>(null);

  // Certificate of Conformance (CoC) Export Modal State
  const [showCocModal, setShowCocModal] = useState<boolean>(false);
  const [cocEngineerName, setCocEngineerName] = useState<string>("Materials engineer (placeholder)");
  const [cocFacility, setCocFacility] = useState<string>("Engineering screening workbench");
  const [cocProgramName, setCocProgramName] = useState<string>("Generic structural coupon screening");
  const [cocRevision, setCocRevision] = useState<string>("REV-D2");
  const [isExportingPdf, setIsExportingPdf] = useState<boolean>(false);
  const [exportSuccessMsg, setExportSuccessMsg] = useState<string | null>(null);

  // Active Preset Handler
  const handlePresetSelect = (preset: AlloyPreset) => {
    setSelectedPresetId(preset.id);
    setAlloyName(preset.name);
    setMeanYieldMpa(preset.meanYieldMpa);
    setMeanTensileMpa(preset.meanTensileMpa);
    setFractureToughnessMpaM(preset.fractureToughnessMpaM);
    setServiceTempMin(preset.defaultTempMin);
    setServiceTempMax(preset.defaultTempMax);
    setOperatingStressMpa(Math.round(preset.meanYieldMpa * 0.6));

    // Matching Route
    if (preset.id === "lpbf-ti64-hip") {
      setSelectedMfgRouteId("lpbf_hip_treated");
      setCustomScatterCv(3.6);
    } else {
      setSelectedMfgRouteId("wrought_forged");
      setCustomScatterCv(2.8);
    }
  };

  // Active Route Handler
  const handleRouteSelect = (routeId: string) => {
    setSelectedMfgRouteId(routeId);
    const found = MFG_ROUTES.find((r) => r.id === routeId);
    if (found) {
      setCustomScatterCv(found.scatterCvPct);
    }
  };

  // ==========================================
  // MMPDS-14 / MIL-HDBK-5 STATISTICAL ENGINE
  // ==========================================
  const mmpdsStats: MmpdsBasisResult = useMemo(() => {
    const N = Math.max(10, sampleSizeN);
    const cov = Math.max(1.0, customScatterCv) / 100;
    const stdDev = meanYieldMpa * cov;

    // MMPDS One-Sided Tolerance Limit Factors:
    // A-Basis: 99% probability with 95% confidence
    // B-Basis: 90% probability with 95% confidence
    const z99 = 2.326348;
    const z90 = 1.281552;
    const z95_conf = 1.644854;

    // Classical Natrella / Lieberman-Resnikoff approximation for one-sided tolerance factor k:
    const kA = Number(
      (z99 + Math.sqrt(z99 * z99 - (1 - (z95_conf * z95_conf) / (2 * (N - 1))) * (z99 * z99 - (z95_conf * z95_conf) / N)) /
        (1 - (z95_conf * z95_conf) / (2 * (N - 1)))).toFixed(3)
    ) || (z99 * (1 + z95_conf / Math.sqrt(2 * N)));

    const kB = Number(
      (z90 + Math.sqrt(z90 * z90 - (1 - (z95_conf * z95_conf) / (2 * (N - 1))) * (z90 * z90 - (z95_conf * z95_conf) / N)) /
        (1 - (z95_conf * z95_conf) / (2 * (N - 1)))).toFixed(3)
    ) || (z90 * (1 + z95_conf / Math.sqrt(2 * N)));

    // A-Basis & B-Basis Yield Strength
    const aBasisYield = Math.max(0, Math.round(meanYieldMpa - kA * stdDev));
    const bBasisYield = Math.max(0, Math.round(meanYieldMpa - kB * stdDev));
    const sBasisYield = Math.max(0, Math.round(meanYieldMpa - 3.0 * stdDev));

    // Tensile Allowables
    const stdDevTensile = meanTensileMpa * cov;
    const aBasisTensile = Math.max(0, Math.round(meanTensileMpa - kA * stdDevTensile));
    const bBasisTensile = Math.max(0, Math.round(meanTensileMpa - kB * stdDevTensile));

    // Secondary MMPDS Derived Allowables
    const shearUltimate = Math.round(aBasisTensile * 0.60);
    const bearingYield = Math.round(aBasisYield * 1.50); // e/D = 1.5
    const bearingUltimate = Math.round(aBasisTensile * 2.00); // e/D = 2.0
    const compressiveYield = Math.round(aBasisYield * 1.04);

    // Process Capability Cpk (assuming specification lower limit is nominal - 15%)
    const specLowerLimit = meanYieldMpa * 0.85;
    const cpk = Number(((meanYieldMpa - specLowerLimit) / (3 * stdDev)).toFixed(2));

    let status: "A-Basis Qualified" | "B-Basis Qualified" | "S-Basis Provisional" | "Insufficient Sampling" = "A-Basis Qualified";
    if (N < 30) {
      status = "S-Basis Provisional";
    } else if (cpk < 1.33 || cov > 0.06) {
      status = "B-Basis Qualified";
    }

    return {
      meanYield: meanYieldMpa,
      meanTensile: meanTensileMpa,
      stdDev: Math.round(stdDev),
      covPct: Number((cov * 100).toFixed(2)),
      sampleSize: N,
      kA,
      kB,
      aBasisYield,
      bBasisYield,
      sBasisYield,
      aBasisTensile,
      bBasisTensile,
      shearUltimate,
      bearingYield,
      bearingUltimate,
      compressiveYield,
      fractureToughnessKic: fractureToughnessMpaM,
      cpk,
      status,
    };
  }, [meanYieldMpa, meanTensileMpa, fractureToughnessMpaM, sampleSizeN, customScatterCv]);

  // =========================================================================
  // QUALIFICATION PROTOCOL CHECKLIST (template only — not auto-PASS)
  // =========================================================================
  const qualificationTests: QualificationTestEvaluation[] = useMemo(() => {
    return [
      {
        id: "mil-salt-fog",
        standard: "MIL-STD-810H",
        methodName: "Method 509.7: Salt Fog Marine Corrosion (5% NaCl)",
        testCategory: "Salt Fog / Marine",
        passProbabilityPct: 0,
        riskLevel: "Low",
        primaryThreat: "Not evaluated — laboratory salt fog is required",
        criticalThreshold: "168 - 336 hrs Continuous Salt Spray (user-attested)",
        mitigationRecommendation: "Checklist item only. This software does not confirm Method 509.7 execution.",
        executionStatus: "Not executed",
      },
      {
        id: "mil-shock",
        standard: "MIL-STD-810H",
        methodName: "Method 516.8: Mechanical Shock and Pyrotechnic Drop (100g/6ms)",
        testCategory: "Mechanical Shock",
        passProbabilityPct: 0,
        riskLevel: "Low",
        primaryThreat: "Not evaluated — shock table data is required",
        criticalThreshold: `User-entered K_IC: ${fractureToughnessMpaM} MPa√m (not a test result)`,
        mitigationRecommendation: "Checklist item only. Fracture toughness sliders do not constitute Method 516.8 PASS.",
        executionStatus: "Not executed",
      },
      {
        id: "mil-thermal-shock",
        standard: "MIL-STD-810H",
        methodName: "Method 503.7: Thermal Shock and Temperature Cycling",
        testCategory: "Thermal Shock",
        passProbabilityPct: 0,
        riskLevel: "Low",
        primaryThreat: "Not evaluated — thermal-cycle testing is required",
        criticalThreshold: `Entered ΔT: ${serviceTempMax - serviceTempMin}°C (user input)`,
        mitigationRecommendation: "Checklist item only. Temperature sliders do not confirm Method 503.7.",
        executionStatus: "Not executed",
      },
      {
        id: "mil-vibration",
        standard: "MIL-STD-810H",
        methodName: "Method 514.8: High-G Random Vibration and Acoustic Fatigue",
        testCategory: "Vibration / High-G",
        passProbabilityPct: 0,
        riskLevel: "Low",
        primaryThreat: "Not evaluated — shaker / acoustic data is required",
        criticalThreshold: `Entered operating stress: ${operatingStressMpa} MPa (user input)`,
        mitigationRecommendation: "Checklist item only. This software does not confirm Method 514.8 execution.",
        executionStatus: "Not executed",
      },
      {
        id: "as9100-cpk",
        standard: "AS9100 Rev D",
        methodName: "Clause 8.5.1: Process Capability Index (Cpk) — template only",
        testCategory: "Process Capability",
        passProbabilityPct: 0,
        riskLevel: "Low",
        primaryThreat: "Not evaluated — production lot evidence is required",
        criticalThreshold: `Slider Cpk: ${mmpdsStats.cpk} (not AS9100 evidence)`,
        mitigationRecommendation: "Checklist item only. Slider Cpk is not an AS9100 lot release.",
        executionStatus: "Not executed",
      },
      {
        id: "nato-scc",
        standard: "NATO STANAG",
        methodName: "STANAG 4370 / MIL-STD-1568: Environmental Stress Corrosion Cracking (SCC)",
        testCategory: "SCC Threshold",
        passProbabilityPct: 0,
        riskLevel: "Low",
        primaryThreat: "Not evaluated — SCC specimens are required",
        criticalThreshold: "User-attested K_ISCC test only",
        mitigationRecommendation: "Checklist item only. PREN / alloy presets do not confirm STANAG SCC.",
        executionStatus: "Not executed",
      },
    ];
  }, [fractureToughnessMpaM, serviceTempMin, serviceTempMax, operatingStressMpa, mmpdsStats]);

  const overallReadinessIndex = 0;

  // AI Deep Qualification Audit Handler
  const handleRunAiAudit = async () => {
    setIsAiAuditing(true);
    setAuditErrorMessage(null);
    try {
      const activeCoating = COATING_OPTIONS.find((c) => c.id === selectedCoatingId)?.name || "Standard Aerospace Anodize";
      const activeRoute = MFG_ROUTES.find((r) => r.id === selectedMfgRouteId)?.name || "Wrought / Die Forged";

      const res = await fetch("/api/metallurgy/qualify-aerospace", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          alloyName,
          baseSystem: ALLOY_PRESETS.find((p) => p.id === selectedPresetId)?.category || "Aerospace Structural Alloy",
          manufacturingRoute: activeRoute,
          meanYield: meanYieldMpa,
          meanTensile: meanTensileMpa,
          aBasisYield: mmpdsStats.aBasisYield,
          bBasisYield: mmpdsStats.bBasisYield,
          fractureToughness: fractureToughnessMpaM,
          serviceTempMin,
          serviceTempMax,
          protectiveCoating: activeCoating,
          targetStandards: "Screening checklist only: MIL-STD-810H / AS9100 / STANAG templates (not executed)",
        }),
      });

      if (!res.ok) {
        throw new Error(`Audit request failed with status: ${res.status}`);
      }

      const data = await res.json();
      setAiAuditReport(data.auditReport || "Audit complete.");
    } catch (err: any) {
      console.error("AI Audit error:", err);
      setAuditErrorMessage(err.message || "Failed to contact qualification audit engine.");
    } finally {
      setIsAiAuditing(false);
    }
  };

  // CoC Data Generator
  const generateCoCPayload = (): CoCData => {
    const activePreset = ALLOY_PRESETS.find((p) => p.id === selectedPresetId);
    const activeRoute = MFG_ROUTES.find((r) => r.id === selectedMfgRouteId)?.name || "Wrought / Die Forged";
    const activeCoating = COATING_OPTIONS.find((c) => c.id === selectedCoatingId)?.name || "Standard Aerospace Anodize";

    return {
      certificateId: `SCREEN-${selectedPresetId.toUpperCase().slice(0, 8)}-${Date.now().toString().slice(-6)}`,
      revision: cocRevision,
      issueDate: new Date().toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }),
      engineerName: cocEngineerName,
      qaDirectorName: "QA reviewer (placeholder)",
      facility: cocFacility,
      programName: cocProgramName,
      alloyName,
      category: activePreset?.category || "Aerospace Structural Alloy",
      standardSpec: activePreset?.standardSpec || "MMPDS-14 Chapter 9 / AMS Specification",
      manufacturingRoute: activeRoute,
      protectiveCoating: activeCoating,
      serviceTempMin,
      serviceTempMax,
      operatingStressMpa,
      meanYieldMpa,
      meanTensileMpa,
      fractureToughnessMpaM,
      sampleSizeN,
      scatterCvPct: customScatterCv,
      mmpdsStats,
      qualificationTests,
      overallReadinessIndex,
      aiAuditNotes: aiAuditReport,
    };
  };

  // Export PDF Handler
  const handleExportPDF = async () => {
    setIsExportingPdf(true);
    setExportSuccessMsg(null);
    try {
      const payload = generateCoCPayload();
      const doc = await generateAerospaceCoCPDF(payload);
      doc.save(`${alloyName.replace(/[^a-zA-Z0-9]/g, "_")}_screening_audit.pdf`);
      setExportSuccessMsg("Screening PDF exported (not a certificate).");
      setTimeout(() => setExportSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error("PDF generation failed:", err);
      setAuditErrorMessage("Failed to render PDF: " + err.message);
    } finally {
      setIsExportingPdf(false);
    }
  };

  // Export CSV Handler
  const handleExportCSV = () => {
    const payload = generateCoCPayload();
    const rows = [
      ["METALLIX SCREENING AUDIT DATA PACKAGE"],
      ["Certificate ID", payload.certificateId],
      ["Revision", payload.revision],
      ["Issue Date", payload.issueDate],
      ["QA Lead Sign-off", payload.engineerName],
      ["Facility", payload.facility],
      ["Target Program", payload.programName],
      ["Alloy Name", payload.alloyName],
      ["Standard Specification", payload.standardSpec],
      ["Manufacturing Route", payload.manufacturingRoute],
      ["Surface Treatment", payload.protectiveCoating],
      ["Sample Size (N)", payload.sampleSizeN],
      ["Scatter CV (%)", payload.scatterCvPct],
      ["Overall Qualification Index (%)", payload.overallReadinessIndex],
      [],
      ["MMPDS DESIGN ALLOWABLES (MPa)"],
      ["Parameter Code", "Description", "Mean", "A-Basis (99%)", "B-Basis (90%)", "Unit"],
      ["F_ty", "Tensile Yield Strength (0.2% Offset)", payload.meanYieldMpa, payload.mmpdsStats.aBasisYield, payload.mmpdsStats.bBasisYield, "MPa"],
      ["F_tu", "Ultimate Tensile Strength", payload.meanTensileMpa, payload.mmpdsStats.aBasisTensile, payload.mmpdsStats.bBasisTensile, "MPa"],
      ["F_cy", "Compressive Yield Strength", Math.round(payload.meanYieldMpa * 1.04), payload.mmpdsStats.compressiveYield, Math.round(payload.mmpdsStats.bBasisYield * 1.04), "MPa"],
      ["F_su", "Shear Ultimate Strength", Math.round(payload.meanTensileMpa * 0.60), payload.mmpdsStats.shearUltimate, Math.round(payload.mmpdsStats.bBasisTensile * 0.60), "MPa"],
      ["F_bry", "Bearing Yield (e/D=1.5)", Math.round(payload.meanYieldMpa * 1.50), payload.mmpdsStats.bearingYield, Math.round(payload.mmpdsStats.bBasisYield * 1.50), "MPa"],
      ["F_bru", "Bearing Ultimate (e/D=2.0)", Math.round(payload.meanTensileMpa * 2.00), payload.mmpdsStats.bearingUltimate, Math.round(payload.mmpdsStats.bBasisTensile * 2.00), "MPa"],
      ["K_IC", "Fracture Toughness", payload.fractureToughnessMpaM, payload.fractureToughnessMpaM, payload.fractureToughnessMpaM, "MPa√m"],
      ["C_pk", "Process Capability Index", payload.mmpdsStats.cpk, payload.mmpdsStats.cpk, payload.mmpdsStats.cpk, "-"],
      [],
      ["MIL-STD-810H / AS9100 / STANAG PROTOCOL CHECKLIST"],
      ["Standard", "Test Category", "Execution status", "Attestation", "Threat", "Mitigation"],
      ...payload.qualificationTests.map((t) => [
        t.standard,
        t.testCategory,
        t.executionStatus || "Not executed",
        "User-attested only",
        `"${t.primaryThreat.replace(/"/g, '""')}"`,
        `"${t.mitigationRecommendation.replace(/"/g, '""')}"`,
      ]),
    ];

    const csvContent = "data:text/csv;charset=utf-8," + rows.map((e) => e.join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `${alloyName.replace(/[^a-zA-Z0-9]/g, "_")}_MMPDS_CoC_DataPackage.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Export JSON Handler
  const handleExportJSON = () => {
    const payload = generateCoCPayload();
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(payload, null, 2));
    const link = document.createElement("a");
    link.setAttribute("href", dataStr);
    link.setAttribute("download", `${alloyName.replace(/[^a-zA-Z0-9]/g, "_")}_CoC_Compliance_Payload.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner */}
      <div className="bg-[#090e18] p-5 sm:p-6 rounded-2xl border border-[#162032] shadow-[0_0_25px_rgba(56,189,248,0.06)] relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-sky-500/5 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20"></div>

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 relative z-10">
          <div className="flex items-start gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-sky-500/20 to-emerald-500/20 border border-sky-400/40 flex items-center justify-center text-sky-300 shadow-[0_0_15px_rgba(56,189,248,0.2)]">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <h2 className="text-lg sm:text-xl font-bold text-white font-mono tracking-wide">
                  Standards & Qualification Compliance Engine
                </h2>
                <span className="px-2 py-0.5 rounded-full bg-sky-500/10 border border-sky-400/30 text-sky-300 text-[10px] font-mono font-bold tracking-wider">
                  MIL-HDBK-5 // MMPDS-14
                </span>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-400/30 text-emerald-300 text-[10px] font-mono font-bold tracking-wider">
                  MIL-STD-810H & AS9100
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-1">
                Instant statistical screening of A/B-style coupon stats and a MIL-STD-810H / AS9100 / STANAG protocol checklist (not executed by this software).
              </p>
              <EngineeringEstimateBanner className="mt-3 max-w-3xl" />
            </div>
          </div>

          {/* Action Buttons & Qualification Readiness Gauge Score */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Export CoC Button */}
            <button
              type="button"
              onClick={() => setShowCocModal(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500/20 to-sky-500/20 hover:from-emerald-500/30 hover:to-sky-500/30 border border-emerald-400/50 text-emerald-300 hover:text-emerald-200 text-xs font-mono font-bold transition shadow-[0_0_15px_rgba(16,185,129,0.2)]"
            >
              <FileText className="w-4 h-4 text-emerald-400" />
              <span>Export screening report</span>
            </button>

            {/* Gauge */}
            <div className="flex items-center gap-4 bg-[#050810] p-3 rounded-xl border border-[#162032]">
              <div className="text-right font-mono">
                <span className="text-[10px] text-slate-400 block uppercase tracking-wider">Protocol checklist</span>
                <span className="text-xl font-extrabold text-amber-300">
                  Not executed
                </span>
                <span className="text-[9px] text-slate-500 block">
                  User-attested only
                </span>
              </div>
              <div className="w-10 h-10 rounded-xl bg-[#0c1322] border border-[#1e2d46] flex items-center justify-center">
                <Award className="w-5 h-5 text-amber-400" />
              </div>
            </div>
          </div>
        </div>

        {/* Export Success Banner */}
        {exportSuccessMsg && (
          <div className="mt-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-center gap-2.5 text-xs text-emerald-300 font-mono">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{exportSuccessMsg}</span>
          </div>
        )}

        {/* Quick Aerospace Standard Presets Selector */}
        <div className="mt-5 pt-4 border-t border-[#162032] space-y-2">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-widest font-semibold block">
            Standard Aerospace & Military Reference Alloy Library:
          </span>
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {ALLOY_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => handlePresetSelect(preset)}
                className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition flex items-center gap-2 whitespace-nowrap ${
                  selectedPresetId === preset.id
                    ? "bg-sky-500/20 text-sky-300 border border-sky-400/50 shadow-[0_0_12px_rgba(56,189,248,0.25)]"
                    : "bg-[#0c1322] hover:bg-[#111a2d] text-slate-300 border border-[#162032]"
                }`}
              >
                <span>{preset.name}</span>
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-black/40 text-slate-400">
                  {preset.category.split(" ")[0]}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Grid: Parameters & Manufacturing (Left) + MMPDS Statistical Basis & Gaussian PDF (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Mechanical, Manufacturing & Operational Inputs */}
        <div className="lg:col-span-5 space-y-4">
          {/* Section 1: Material & Mechanical Parameters */}
          <div className="bg-[#090e18] p-4.5 rounded-2xl border border-[#162032] space-y-3.5 font-mono">
            <div className="flex items-center justify-between pb-2 border-b border-[#162032]">
              <div className="flex items-center gap-2 text-sky-300 text-xs font-bold uppercase tracking-wider">
                <Sliders className="w-4 h-4" />
                <span>1. Mechanical & Statistical Sampling</span>
              </div>
              <span className="text-[10px] text-slate-400">ASTM E8 / MMPDS-14</span>
            </div>

            {/* Alloy Name */}
            <div className="space-y-1">
              <label className="text-[11px] text-slate-400 block">Alloy Designation & Spec:</label>
              <input
                type="text"
                value={alloyName}
                onChange={(e) => setAlloyName(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-[#050810] border border-[#162032] text-xs text-white focus:outline-none focus:border-sky-400"
              />
            </div>

            {/* Mean Yield & Tensile */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-400">Mean Fty (Yield):</span>
                  <span className="text-sky-300 font-bold">{meanYieldMpa} MPa</span>
                </div>
                <input
                  type="range"
                  min={200}
                  max={2200}
                  step={10}
                  value={meanYieldMpa}
                  onChange={(e) => setMeanYieldMpa(parseInt(e.target.value))}
                  className="w-full accent-sky-400 h-1 bg-[#162032] rounded"
                />
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-400">Mean Ftu (Tensile):</span>
                  <span className="text-emerald-300 font-bold">{meanTensileMpa} MPa</span>
                </div>
                <input
                  type="range"
                  min={250}
                  max={2500}
                  step={10}
                  value={meanTensileMpa}
                  onChange={(e) => setMeanTensileMpa(parseInt(e.target.value))}
                  className="w-full accent-emerald-400 h-1 bg-[#162032] rounded"
                />
              </div>
            </div>

            {/* Fracture Toughness & Sample Count */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-400">Fracture K_IC:</span>
                  <span className="text-amber-300 font-bold">{fractureToughnessMpaM} MPa√m</span>
                </div>
                <input
                  type="range"
                  min={15}
                  max={140}
                  step={2}
                  value={fractureToughnessMpaM}
                  onChange={(e) => setFractureToughnessMpaM(parseInt(e.target.value))}
                  className="w-full accent-amber-400 h-1 bg-[#162032] rounded"
                />
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-400">Sample Count (N):</span>
                  <span className="text-white font-bold">{sampleSizeN} coupons</span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={300}
                  step={5}
                  value={sampleSizeN}
                  onChange={(e) => setSampleSizeN(parseInt(e.target.value))}
                  className="w-full accent-sky-400 h-1 bg-[#162032] rounded"
                />
              </div>
            </div>

            {/* Scatter Coefficient of Variation (Cv) */}
            <div className="space-y-1 pt-1">
              <div className="flex justify-between text-[11px]">
                <span className="text-slate-400">Statistical Scatter (Cv = σ/μ):</span>
                <span className="text-cyan-300 font-bold">{customScatterCv}%</span>
              </div>
              <input
                type="range"
                min={1.0}
                max={12.0}
                step={0.2}
                value={customScatterCv}
                onChange={(e) => setCustomScatterCv(parseFloat(e.target.value))}
                className="w-full accent-cyan-400 h-1 bg-[#162032] rounded"
              />
              <span className="text-[10px] text-slate-500 block">
                {customScatterCv <= 3.0 ? "Wrought / VAR Forged High Uniformity" : customScatterCv <= 5.0 ? "Standard Rolled/Extruded" : "High Scatter (As-Built AM or Sand Cast)"}
              </span>
            </div>
          </div>

          {/* Section 2: Manufacturing Route & Protective Surface Treatments */}
          <div className="bg-[#090e18] p-4.5 rounded-2xl border border-[#162032] space-y-3.5 font-mono">
            <div className="flex items-center justify-between pb-2 border-b border-[#162032]">
              <div className="flex items-center gap-2 text-emerald-300 text-xs font-bold uppercase tracking-wider">
                <Layers className="w-4 h-4" />
                <span>2. Manufacturing Route & Environment</span>
              </div>
              <span className="text-[10px] text-slate-400">AS9100 / NDT</span>
            </div>

            {/* Route Selector */}
            <div className="space-y-1.5">
              <label className="text-[11px] text-slate-400 block">Manufacturing & Processing Route:</label>
              <select
                value={selectedMfgRouteId}
                onChange={(e) => handleRouteSelect(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-[#050810] border border-[#162032] text-xs text-sky-300 focus:outline-none focus:border-sky-400"
              >
                {MFG_ROUTES.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Protective Barrier Coating */}
            <div className="space-y-1.5">
              <label className="text-[11px] text-slate-400 block">Surface Barrier & Corrosion Protection:</label>
              <select
                value={selectedCoatingId}
                onChange={(e) => setSelectedCoatingId(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-[#050810] border border-[#162032] text-xs text-emerald-300 focus:outline-none focus:border-emerald-400"
              >
                {COATING_OPTIONS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Operating Environmental Envelope */}
            <div className="grid grid-cols-3 gap-2.5 pt-1">
              <div className="space-y-1">
                <span className="text-[10px] text-slate-400 block">Min Temp (°C):</span>
                <input
                  type="number"
                  value={serviceTempMin}
                  onChange={(e) => setServiceTempMin(parseInt(e.target.value))}
                  className="w-full px-2.5 py-1 bg-[#050810] border border-[#162032] rounded text-xs text-white"
                />
              </div>

              <div className="space-y-1">
                <span className="text-[10px] text-slate-400 block">Max Temp (°C):</span>
                <input
                  type="number"
                  value={serviceTempMax}
                  onChange={(e) => setServiceTempMax(parseInt(e.target.value))}
                  className="w-full px-2.5 py-1 bg-[#050810] border border-[#162032] rounded text-xs text-white"
                />
              </div>

              <div className="space-y-1">
                <span className="text-[10px] text-slate-400 block">Design Stress (MPa):</span>
                <input
                  type="number"
                  value={operatingStressMpa}
                  onChange={(e) => setOperatingStressMpa(parseInt(e.target.value))}
                  className="w-full px-2.5 py-1 bg-[#050810] border border-[#162032] rounded text-xs text-amber-300"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: MMPDS Statistical Basis Dashboard & Bell Curve */}
        <div className="lg:col-span-7 space-y-4 font-mono">
          {/* MMPDS Allowables Summary Card */}
          <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] shadow-[0_0_20px_rgba(56,189,248,0.08)] space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#162032] pb-3">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Award className="w-4 h-4 text-sky-400" />
                  <span>MMPDS-14 / MIL-HDBK-5 Design Allowables</span>
                </h3>
                <span className="text-[11px] text-slate-400">
                  Calculated using 1-Sided Tolerance Limits (Sample Size N={mmpdsStats.sampleSize}, kA={mmpdsStats.kA}, kB={mmpdsStats.kB})
                </span>
              </div>

              <div className="flex items-center gap-2">
                <span
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold border ${
                    mmpdsStats.status === "A-Basis Qualified"
                      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                      : mmpdsStats.status === "B-Basis Qualified"
                      ? "bg-sky-500/20 text-sky-300 border-sky-500/40"
                      : "bg-amber-500/20 text-amber-300 border-amber-500/40"
                  }`}
                >
                  {mmpdsStats.status}
                </span>
              </div>
            </div>

            {/* Key Allowables 3-Box Comparison */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* A-Basis */}
              <div className="p-3.5 bg-[#050810] rounded-xl border border-sky-500/30 relative overflow-hidden">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-sky-300 uppercase">A-Basis (Fty)</span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300">99% / 95% Conf</span>
                </div>
                <div className="mt-2">
                  <span className="text-2xl font-extrabold text-white">{mmpdsStats.aBasisYield}</span>
                  <span className="text-xs text-slate-400 ml-1">MPa</span>
                </div>
                <span className="text-[10px] text-slate-400 block mt-1">
                  Single load path flight critical structures (FAA/DoD)
                </span>
              </div>

              {/* B-Basis */}
              <div className="p-3.5 bg-[#050810] rounded-xl border border-emerald-500/30 relative overflow-hidden">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-emerald-300 uppercase">B-Basis (Fty)</span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">90% / 95% Conf</span>
                </div>
                <div className="mt-2">
                  <span className="text-2xl font-extrabold text-emerald-300">{mmpdsStats.bBasisYield}</span>
                  <span className="text-xs text-slate-400 ml-1">MPa</span>
                </div>
                <span className="text-[10px] text-slate-400 block mt-1">
                  Redundant, fail-safe multi-path airframe structures
                </span>
              </div>

              {/* Mean & S-Basis */}
              <div className="p-3.5 bg-[#050810] rounded-xl border border-[#162032] relative overflow-hidden">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-slate-300 uppercase">Mean / S-Basis</span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#162032] text-slate-400">Spec Min</span>
                </div>
                <div className="mt-2">
                  <span className="text-xl font-bold text-slate-200">{mmpdsStats.meanYield}</span>
                  <span className="text-xs text-slate-400 ml-1">/ {mmpdsStats.sBasisYield} MPa</span>
                </div>
                <span className="text-[10px] text-slate-400 block mt-1">
                  Process Cpk: <strong className="text-sky-300">{mmpdsStats.cpk}</strong> (StdDev: ±{mmpdsStats.stdDev} MPa)
                </span>
              </div>
            </div>

            {/* Full Derived Mechanical Allowables Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-[#162032] text-slate-400 text-[10px] uppercase">
                    <th className="py-1.5 px-2">Design Parameter</th>
                    <th className="py-1.5 px-2">Symbol</th>
                    <th className="py-1.5 px-2">A-Basis (99%)</th>
                    <th className="py-1.5 px-2">B-Basis (90%)</th>
                    <th className="py-1.5 px-2">Typical Mean</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#162032] text-slate-300">
                  <tr>
                    <td className="py-2 px-2 font-medium">Tensile Yield Strength</td>
                    <td className="py-2 px-2 text-sky-400">Fty</td>
                    <td className="py-2 px-2 text-white font-bold">{mmpdsStats.aBasisYield} MPa</td>
                    <td className="py-2 px-2 text-emerald-300 font-bold">{mmpdsStats.bBasisYield} MPa</td>
                    <td className="py-2 px-2 text-slate-400">{mmpdsStats.meanYield} MPa</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-2 font-medium">Ultimate Tensile Strength</td>
                    <td className="py-2 px-2 text-sky-400">Ftu</td>
                    <td className="py-2 px-2 text-white font-bold">{mmpdsStats.aBasisTensile} MPa</td>
                    <td className="py-2 px-2 text-emerald-300 font-bold">{mmpdsStats.bBasisTensile} MPa</td>
                    <td className="py-2 px-2 text-slate-400">{mmpdsStats.meanTensile} MPa</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-2 font-medium">Compressive Yield Strength</td>
                    <td className="py-2 px-2 text-sky-400">Fcy</td>
                    <td className="py-2 px-2">{mmpdsStats.compressiveYield} MPa</td>
                    <td className="py-2 px-2">{Math.round(mmpdsStats.bBasisYield * 1.04)} MPa</td>
                    <td className="py-2 px-2 text-slate-400">{Math.round(mmpdsStats.meanYield * 1.04)} MPa</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-2 font-medium">Shear Ultimate Strength</td>
                    <td className="py-2 px-2 text-sky-400">Fsu (0.6 Ftu)</td>
                    <td className="py-2 px-2">{mmpdsStats.shearUltimate} MPa</td>
                    <td className="py-2 px-2">{Math.round(mmpdsStats.bBasisTensile * 0.60)} MPa</td>
                    <td className="py-2 px-2 text-slate-400">{Math.round(mmpdsStats.meanTensile * 0.60)} MPa</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-2 font-medium">Bearing Ultimate (e/D = 2.0)</td>
                    <td className="py-2 px-2 text-sky-400">Fbru</td>
                    <td className="py-2 px-2">{mmpdsStats.bearingUltimate} MPa</td>
                    <td className="py-2 px-2">{Math.round(mmpdsStats.bBasisTensile * 2.0)} MPa</td>
                    <td className="py-2 px-2 text-slate-400">{Math.round(mmpdsStats.meanTensile * 2.0)} MPa</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Interactive Gaussian Distribution (Probability Density Function) */}
            <div className="pt-2 border-t border-[#162032]">
              <div className="flex items-center justify-between text-[11px] text-slate-400 pb-1">
                <span>Gaussian Statistical Tolerance Distribution Curve:</span>
                <span className="text-sky-300">σ = ±{mmpdsStats.stdDev} MPa</span>
              </div>
              <div className="w-full h-28 bg-[#050810] rounded-xl border border-[#162032] relative overflow-hidden flex items-end px-2 pt-2">
                <svg viewBox="0 0 400 90" className="w-full h-full">
                  <defs>
                    <linearGradient id="bellGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.4" />
                      <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.02" />
                    </linearGradient>
                  </defs>
                  {/* Gaussian Curve */}
                  <path
                    d="M 10,85 Q 120,85 170,40 Q 200,8 230,40 Q 280,85 390,85"
                    fill="url(#bellGrad)"
                    stroke="#38bdf8"
                    strokeWidth="2"
                  />
                  {/* A-Basis Marker (99%) */}
                  <line x1="120" y1="10" x2="120" y2="85" stroke="#f43f5e" strokeWidth="2" strokeDasharray="3,2" />
                  <text x="122" y="24" fill="#f43f5e" fontSize="9" fontWeight="bold" fontFamily="monospace">
                    A-Basis ({mmpdsStats.aBasisYield})
                  </text>

                  {/* B-Basis Marker (90%) */}
                  <line x1="160" y1="20" x2="160" y2="85" stroke="#10b981" strokeWidth="2" strokeDasharray="3,2" />
                  <text x="162" y="38" fill="#10b981" fontSize="9" fontWeight="bold" fontFamily="monospace">
                    B-Basis ({mmpdsStats.bBasisYield})
                  </text>

                  {/* Mean Marker */}
                  <line x1="200" y1="5" x2="200" y2="85" stroke="#94a3b8" strokeWidth="1.5" />
                  <text x="204" y="16" fill="#cbd5e1" fontSize="9" fontWeight="bold" fontFamily="monospace">
                    Mean μ ({mmpdsStats.meanYield})
                  </text>
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Military & Aerospace Qualification Protocols Matrix (MIL-STD-810H, AS9100, NATO STANAG) */}
      <div className="bg-[#090e18] p-5 sm:p-6 rounded-2xl border border-[#162032] space-y-4 font-mono">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#162032] pb-3.5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span>MIL-STD-810H, AS9100 & NATO STANAG Protocol Checklist</span>
              </h3>
              <p className="text-[11px] text-slate-400">
                Template rows only. Status is Not executed / user-attested. This software does not confirm environmental testing.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={handleRunAiAudit}
            disabled={isAiAuditing}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-sky-500/20 hover:bg-sky-500/30 border border-sky-400/40 text-sky-300 text-xs font-bold transition shadow-[0_0_12px_rgba(56,189,248,0.2)] disabled:opacity-50"
          >
            {isAiAuditing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                <span>AI Screening Notes</span>
          </button>
        </div>

        {/* 6 Qualification Test Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {qualificationTests.map((t) => (
            <div
              key={t.id}
              className="p-4 rounded-xl border transition relative overflow-hidden flex flex-col justify-between bg-[#050810] border-amber-500/30"
            >
              <div>
                <div className="flex items-center justify-between gap-1 pb-2 border-b border-[#162032]">
                  <span className="text-[10px] px-2 py-0.5 rounded bg-[#0c1322] border border-[#162032] text-sky-300 font-bold">
                    {t.standard}
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-200 border border-amber-500/40">
                    {t.executionStatus || "Not executed"}
                  </span>
                </div>

                <h4 className="text-xs font-bold text-white mt-2.5 leading-snug">{t.methodName}</h4>

                <div className="mt-3 space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-400">Execution:</span>
                    <span className="font-bold text-amber-300">Not executed</span>
                  </div>
                  <p className="text-[10px] text-slate-500">User-attested only — no software PASS/FAIL.</p>
                </div>

                {/* Threat & Threshold */}
                <div className="mt-3 space-y-1 text-[11px]">
                  <div className="text-slate-400">
                    <span className="text-slate-500 block text-[10px]">Failure Mechanism:</span>
                    <span className="text-slate-200">{t.primaryThreat}</span>
                  </div>
                  <div className="text-slate-400 pt-1">
                    <span className="text-slate-500 block text-[10px]">Test Spectrum Threshold:</span>
                    <span className="text-sky-300">{t.criticalThreshold}</span>
                  </div>
                </div>
              </div>

              {/* Mitigation Action */}
              <div className="mt-3.5 pt-2.5 border-t border-[#162032] text-[10px] text-slate-300">
                <strong className="text-amber-400 block mb-0.5">Engineering Action:</strong>
                <p className="text-slate-400 leading-relaxed">{t.mitigationRecommendation}</p>
              </div>
            </div>
          ))}
        </div>

        {/* AI Audit Report Drawer */}
        {aiAuditReport && (
          <div className="mt-5 p-5 bg-[#050810] rounded-xl border border-sky-500/40 space-y-3">
            <div className="flex items-center justify-between border-b border-[#162032] pb-2">
              <div className="flex items-center gap-2 text-sky-300 text-xs font-bold uppercase tracking-wider">
                <Sparkles className="w-4 h-4" />
                <span>AI Aerospace Qualification & Regulatory Compliance Audit Report</span>
              </div>
              <button
                type="button"
                onClick={() => setAiAuditReport(null)}
                className="text-xs text-slate-400 hover:text-white"
              >
                Close
              </button>
            </div>
            <div className="prose prose-invert prose-xs max-w-none text-slate-300 leading-relaxed whitespace-pre-wrap font-sans">
              {aiAuditReport}
            </div>
          </div>
        )}

        {auditErrorMessage && (
          <div className="mt-3 p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300">
            {auditErrorMessage}
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* AS9100 / MIL-HDBK-5 OFFICIAL CERTIFICATE OF CONFORMANCE (CoC) MODAL       */}
      {/* ========================================================================= */}
      {showCocModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md overflow-y-auto font-mono">
          <div className="bg-[#090e18] border border-[#1e2d46] rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-[0_0_50px_rgba(0,0,0,0.8)] overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 sm:p-5 border-b border-[#162032] bg-[#0c1322]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center text-emerald-300">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm sm:text-base font-bold text-white uppercase tracking-wider flex items-center gap-2">
                    <span>Screening report template</span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                      Screening template
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400">
                    Screening worksheet export. Not a Certificate of Conformance.
                  </p>
                  <EngineeringEstimateBanner className="mt-2" />
                </div>
              </div>

              <button
                type="button"
                onClick={() => setShowCocModal(false)}
                className="w-8 h-8 rounded-lg bg-[#162032] hover:bg-[#1e2d46] text-slate-400 hover:text-white flex items-center justify-center transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 sm:p-6 overflow-y-auto space-y-6">
              {/* CoC Metadata Customization Form */}
              <div className="bg-[#050810] p-4 rounded-xl border border-[#162032] space-y-3">
                <span className="text-xs font-bold text-sky-300 uppercase tracking-wider block">
                  1. Document Signatory & Program Credentials
                </span>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="space-y-1">
                    <label className="text-slate-400 text-[11px] block">Lead Metallurgical Engineer / Signatory:</label>
                    <input
                      type="text"
                      value={cocEngineerName}
                      onChange={(e) => setCocEngineerName(e.target.value)}
                      className="w-full px-3 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg text-white text-xs focus:border-sky-400 focus:outline-none"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-slate-400 text-[11px] block">Accredited Testing Facility / Org:</label>
                    <input
                      type="text"
                      value={cocFacility}
                      onChange={(e) => setCocFacility(e.target.value)}
                      className="w-full px-3 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg text-white text-xs focus:border-sky-400 focus:outline-none"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-slate-400 text-[11px] block">Target program / screening example:</label>
                    <input
                      type="text"
                      value={cocProgramName}
                      onChange={(e) => setCocProgramName(e.target.value)}
                      className="w-full px-3 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg text-white text-xs focus:border-sky-400 focus:outline-none"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-slate-400 text-[11px] block">Document Revision ID:</label>
                    <input
                      type="text"
                      value={cocRevision}
                      onChange={(e) => setCocRevision(e.target.value)}
                      className="w-full px-3 py-1.5 bg-[#090e18] border border-[#1e2d46] rounded-lg text-white text-xs focus:border-sky-400 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* Certificate Live Document Preview */}
              <div className="bg-[#f8fafc] text-[#0f172a] p-5 sm:p-7 rounded-xl border border-slate-300 shadow-inner space-y-4 font-sans text-xs">
                {/* Cert Header */}
                <div className="flex justify-between items-start border-b-2 border-[#0f172a] pb-3">
                  <div>
                    <h2 className="text-base font-extrabold text-[#0f172a] tracking-tight">
                      METALLIX ENGINEERING SCREENING WORKSHEET
                    </h2>
                    <span className="text-[10px] text-slate-600 block mt-0.5">
                    Screening worksheet / protocol checklist template
                    </span>
                  </div>
                  <div className="text-right text-[10px] font-mono">
                    <span className="font-bold text-sky-800 block">
                      REF: COC-{selectedPresetId.toUpperCase().slice(0, 8)}-{Date.now().toString().slice(-6)}
                    </span>
                    <span className="text-slate-600">Rev: {cocRevision} | Date: {new Date().toLocaleDateString()}</span>
                  </div>
                </div>

                {/* Section 1: Spec */}
                <div>
                  <h4 className="font-bold text-[11px] text-[#0f172a] border-b border-slate-300 pb-1 mb-2 uppercase">
                    1. Material Specification & Provenance
                  </h4>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
                    <div>
                      <span className="text-slate-500">Designated Alloy:</span>{" "}
                      <strong className="text-slate-900">{alloyName}</strong>
                    </div>
                    <div>
                      <span className="text-slate-500">Standard Spec:</span>{" "}
                      <strong className="text-slate-900">
                        {ALLOY_PRESETS.find((p) => p.id === selectedPresetId)?.standardSpec || "MMPDS Chapter 9 / AMS"}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500">Manufacturing Route:</span>{" "}
                      <span className="text-slate-800 font-medium">
                        {MFG_ROUTES.find((r) => r.id === selectedMfgRouteId)?.name || "Wrought / Forged"}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Surface Barrier:</span>{" "}
                      <span className="text-slate-800 font-medium">
                        {COATING_OPTIONS.find((c) => c.id === selectedCoatingId)?.name || "Standard Anodize"}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Sample Size (N):</span>{" "}
                      <span className="text-slate-800 font-medium">
                        {sampleSizeN} Coupons (Scatter CV: {customScatterCv}%)
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Operating Envelope:</span>{" "}
                      <span className="text-slate-800 font-medium">
                        {serviceTempMin}°C to +{serviceTempMax}°C (σ_op: {operatingStressMpa} MPa)
                      </span>
                    </div>
                  </div>
                </div>

                {/* Section 2: MMPDS Allowables Table */}
                <div>
                  <h4 className="font-bold text-[11px] text-[#0f172a] border-b border-slate-300 pb-1 mb-2 uppercase">
                    2. Statistical Design Allowables (MMPDS-14 1-Sided Tolerance Limits)
                  </h4>
                  <table className="w-full text-left text-[10px] border border-slate-300">
                    <thead className="bg-slate-200 text-slate-800 font-bold">
                      <tr>
                        <th className="p-1 border border-slate-300">Code</th>
                        <th className="p-1 border border-slate-300">Description</th>
                        <th className="p-1 border border-slate-300">Mean</th>
                        <th className="p-1 border border-slate-300 text-sky-800">A-Basis (99%)</th>
                        <th className="p-1 border border-slate-300 text-emerald-800">B-Basis (90%)</th>
                        <th className="p-1 border border-slate-300">Unit</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      <tr>
                        <td className="p-1 font-bold border border-slate-300">F_ty</td>
                        <td className="p-1 border border-slate-300">Tensile Yield Strength</td>
                        <td className="p-1 border border-slate-300">{meanYieldMpa}</td>
                        <td className="p-1 font-bold text-sky-800 border border-slate-300">{mmpdsStats.aBasisYield}</td>
                        <td className="p-1 font-bold text-emerald-800 border border-slate-300">{mmpdsStats.bBasisYield}</td>
                        <td className="p-1 border border-slate-300">MPa</td>
                      </tr>
                      <tr>
                        <td className="p-1 font-bold border border-slate-300">F_tu</td>
                        <td className="p-1 border border-slate-300">Tensile Ultimate Strength</td>
                        <td className="p-1 border border-slate-300">{meanTensileMpa}</td>
                        <td className="p-1 font-bold text-sky-800 border border-slate-300">{mmpdsStats.aBasisTensile}</td>
                        <td className="p-1 font-bold text-emerald-800 border border-slate-300">{mmpdsStats.bBasisTensile}</td>
                        <td className="p-1 border border-slate-300">MPa</td>
                      </tr>
                      <tr>
                        <td className="p-1 font-bold border border-slate-300">F_cy</td>
                        <td className="p-1 border border-slate-300">Compressive Yield Strength</td>
                        <td className="p-1 border border-slate-300">{Math.round(meanYieldMpa * 1.04)}</td>
                        <td className="p-1 border border-slate-300">{mmpdsStats.compressiveYield}</td>
                        <td className="p-1 border border-slate-300">{Math.round(mmpdsStats.bBasisYield * 1.04)}</td>
                        <td className="p-1 border border-slate-300">MPa</td>
                      </tr>
                      <tr>
                        <td className="p-1 font-bold border border-slate-300">K_IC</td>
                        <td className="p-1 border border-slate-300">Fracture Toughness</td>
                        <td className="p-1 border border-slate-300">{fractureToughnessMpaM}</td>
                        <td className="p-1 border border-slate-300">{fractureToughnessMpaM}</td>
                        <td className="p-1 border border-slate-300">{fractureToughnessMpaM}</td>
                        <td className="p-1 border border-slate-300">MPa√m</td>
                      </tr>
                    </tbody>
                  </table>
                  <p className="text-[9px] text-slate-500 mt-1">
                    Process Capability C_pk: {mmpdsStats.cpk} | Tolerance Factors: k_A={mmpdsStats.kA}, k_B={mmpdsStats.kB}
                  </p>
                </div>

                {/* Section 3: MIL-STD-810H Compliance */}
                <div>
                  <h4 className="font-bold text-[11px] text-[#0f172a] border-b border-slate-300 pb-1 mb-2 uppercase">
                    3. Environmental & Military Test Compliance Summary
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {qualificationTests.slice(0, 6).map((t) => (
                      <div key={t.id} className="p-1.5 border border-slate-300 rounded bg-white text-[9.5px]">
                        <span className="font-bold text-slate-800 block truncate">{t.standard}: {t.testCategory}</span>
                        <div className="flex justify-between items-center mt-1">
                          <span className="text-slate-600">Status:</span>
                          <span className="font-bold text-amber-800">
                            {t.executionStatus || "Not executed"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Sign-off Box */}
                <div className="border-t-2 border-[#0f172a] pt-3 flex justify-between items-end">
                  <div>
                    <span className="text-[10px] font-bold text-slate-900 block">Lead QA Engineer Sign-off:</span>
                    <span className="text-xs font-serif italic text-slate-800">{cocEngineerName}</span>
                    <span className="text-[9px] text-slate-500 block">{ENGINEERING_ESTIMATE_DISCLAIMER}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] text-slate-600 block">Document status:</span>
                    <span className="text-xs font-bold text-amber-900 px-2 py-0.5 bg-amber-100 border border-amber-400 rounded">
                      SCREENING TEMPLATE
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer with Export Action Buttons */}
            <div className="p-4 sm:p-5 border-t border-[#162032] bg-[#0c1322] flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="text-xs text-slate-400 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Ready for export in PDF, CSV Data Table, and JSON compliance format.</span>
              </div>

              <div className="flex items-center gap-2.5 w-full sm:w-auto">
                <button
                  type="button"
                  onClick={handleExportCSV}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#162032] hover:bg-[#1e2d46] text-slate-300 hover:text-white text-xs font-bold transition border border-[#223350]"
                >
                  <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
                  <span>CSV Table</span>
                </button>

                <button
                  type="button"
                  onClick={handleExportJSON}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#162032] hover:bg-[#1e2d46] text-slate-300 hover:text-white text-xs font-bold transition border border-[#223350]"
                >
                  <FileCode className="w-3.5 h-3.5 text-sky-400" />
                  <span>JSON Payload</span>
                </button>

                <button
                  type="button"
                  onClick={handleExportPDF}
                  disabled={isExportingPdf}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-sky-500 hover:from-emerald-400 hover:to-sky-400 text-slate-950 text-xs font-extrabold transition shadow-[0_0_20px_rgba(16,185,129,0.3)] disabled:opacity-50"
                >
                  {isExportingPdf ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                  <span>{isExportingPdf ? "Generating PDF..." : "Download screening PDF"}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
