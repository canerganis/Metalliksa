/**
 * SAMPLE DIGITAL TWIN DATA SCHEMA & STORE
 * 
 * Centralized, multi-scale, physical-to-digital twin schema that connects and feeds all MetalliX modules:
 * 1. Chemistry & Raw Alloy Data (AlloyBuilder, PocketCalculators, Schaeffler, CE)
 * 2. Thermodynamics & Phase Constitution (CALPHAD Gibbs Solver, Fe-C, SGTE)
 * 3. Manufacturing & Thermal History (ThermalCycleScheduler, Additive3DDistortion, Heat Treatment)
 * 4. Microstructure & Characterization (XRD, EBSD, EDS)
 * 5. Mechanical & Performance Properties (HardnessToTensile, MMPDS, Tensile/Yield/Toughness)
 * 6. Electrochemical, Battery & Corrosion (EIS, Tafel, Pitting, OCV)
 * 7. Environmental, Extreme Service & Hypersonic (Ablation, High-T Oxidation)
 * 8. Standards, Aerospace Certification & Audit (AerospaceAudit, MIL-STD/AMS/AS9100)
 */

export interface DigitalTwinChemistry {
  baseElement: string;
  nominalComposition: Record<string, number>; // e.g. { Fe: 68.5, Cr: 18.0, Ni: 10.0, Mo: 2.5, C: 0.03 }
  measuredComposition?: Record<string, number>; // EDS / OES verified
  carbonEquivalent?: {
    ceIIW?: number | null;
    pcm?: number | null;
    cen?: number | null;
  };
  schaefflerCoordinates?: {
    crEq: number | null;
    niEq: number | null;
    estimatedFerriteNumber: number | null;
    matrixPrediction: string;
  };
}

export interface DigitalTwinThermodynamics {
  calphadSystemId: string; // e.g. "fe-c", "ni-al", "ti-al", "cu-ni"
  liquidusTemperatureC: number | null;
  solidusTemperatureC: number | null;
  freezingRangeC: number | null;
  stablePhasesAtRoomTemp: {
    phaseId: string;
    phaseName: string;
    fractionPct: number | null;
    crystalStructure: string;
  }[];
  scheilSolidification: {
    eutecticFractionPct: number | null;
    hotTearingIndexKou: number | null;
    microsegregationSeverity: "Low" | "Moderate" | "High" | "Critical" | "Unresolved";
  };
  transformationTemps?: {
    ac1?: number | null;
    ac3?: number | null;
    ms?: number | null;
    mf?: number | null;
    bs?: number | null;
  };
}

export interface DigitalTwinProcessHistory {
  manufacturingRoute: "LPBF (Laser Powder Bed)" | "Forged & Rolled" | "Investment Cast" | "DED (Direct Energy)" | "Extruded" | "HIP (Hot Isostatic Pressed)" | "Unresolved";
  currentCondition: "As-Built / As-Cast" | "Solution Treated" | "Peak Aged (T6)" | "Stress Relieved" | "Annealed" | "Quenched & Tempered" | "Unresolved";
  thermalCycles: {
    stageName: string;
    targetTempC: number | null;
    holdTimeMinutes: number | null;
    coolingMethod: "Furnace Cool" | "Air Cool" | "Oil Quench" | "Water Quench" | "Gas Fan";
    notes?: string;
  }[];
  additiveParameters?: {
    laserPowerW: number | null;
    scanSpeedMmS: number | null;
    hatchDistanceUm: number | null;
    layerThicknessUm: number | null;
    volumetricEnergyDensityJ_mm3: number | null;
    predictedResidualStressMpa: number | null;
    maxDeflectionMm: number | null;
  };
}

export interface DigitalTwinMicrostructure {
  primaryCrystalStructure: "FCC" | "BCC" | "HCP" | "BCT" | "L12" | "B2" | "Amorphous" | "Unresolved";
  astmGrainSizeNumber: number | null; // e.g. 8.5
  meanGrainDiameterUm: number | null; // e.g. 18.5 um
  porosityPct: number | null; // e.g. 0.08%
  phasesDetected: {
    name: string;
    fractionPct: number | null;
    morphology: string; // e.g. "Cellular Dendritic", "Equiaxed", "Acicular Martensite", "Lamellar Pearlite"
  }[];
  ebsdTexture: {
    preferredOrientation: string; // e.g. "<001> Build Direction Fiber"
    misorientationAngleMeanDeg: number | null;
    lowAngleBoundaryPct: number | null;
    highAngleBoundaryPct: number | null;
    kosselSchmidFactorMean: number | null;
  };
  xrdVerification: {
    primaryPeaks: { hkl: string; twoTheta: number | null; intensityPct: number }[];
    residualStressSin2PsiMpa: number | null; // e.g. +145 MPa (tensile)
    crystalliteSizeNm: number | null;
  };
  edsPurityPurityPct: number | null;
}

export interface DigitalTwinMechanicalProperties {
  yieldStrengthMpa: number | null;
  ultimateTensileStrengthMpa: number | null;
  elongationPct: number | null;
  reductionOfAreaPct: number | null;
  hardness: {
    value: number | null;
    scale: "HV" | "HRC" | "HRB" | "HBW" | "Unresolved";
    convertedHRC?: number | null;
    convertedHV?: number | null;
  };
  fractureToughnessK1cMpaSqrtM?: number | null;
  fatigueLimitMpa?: number | null; // 10^7 cycles
  mmpdsStatisticalBasis: {
    basisLevel: "A-Basis Qualified" | "B-Basis Qualified" | "S-Basis Provisional" | "Tentative R&D" | "Not assessed";
    sampleCountN: number | null;
    cpkReliability: number | null;
  };
}

export interface DigitalTwinElectrochemistry {
  corrosionRateMpy: number | null; // Mils per year
  openCircuitPotentialEcorrV: number | null; // V vs SCE
  pittingPotentialEpitV?: number | null;
  polarizationResistanceRpOhmCm2: number | null;
  eisImpedanceModuleOhm: number | null;
  passivationQuality: "Immune" | "Passive Stable" | "Susceptible to Pitting" | "Active Dissolution" | "Unresolved";
  batteryCompatibility?: {
    lithiumIntercalationVoltageV: number | null;
    capacityMah_g: number | null;
    cycleRetentionPct1000: number | null;
  };
}

export interface DigitalTwinExtremeService {
  operatingMaxTempC: number | null;
  hypersonicAblationRecessionRateMm_s?: number | null;
  thermalConductivityW_mK: number | null;
  thermalDiffusivityMm2_s: number | null;
  oxidationResistanceCategory: "Excellent (Protective Cr2O3/Al2O3)" | "Moderate" | "Severe Scaling" | "Unresolved";
  creepRuptureLifeHours?: {
    temperatureC: number | null;
    stressMpa: number | null;
    hoursToRupture: number | null;
  };
}

export interface DigitalTwinQualityAndCert {
  applicableStandards: string[]; // e.g. ["AMS 5662", "ASTM B348", "MIL-STD-810H", "AS9100D"]
  aerospaceFlightReadinessScorePct: number | null; // 0 - 100
  qualificationAuditStatus: string;
  complianceRiskLevel: "Negligible" | "Low" | "Moderate" | "High" | "Unresolved";
  nonDestructiveTestResults: {
    ultrasonicInspection: "Accept (Level A)" | "Reject" | "Pending";
    xrayRadiography: "ASTM E1742 Class I" | "Class II" | "Flaw Detected" | "Pending";
    surfaceDyePenetrant: "No Indications" | "Micro-cracks present" | "Pending";
  };
  blockchainHashCertificate?: string;
}

export interface DigitalTwinAttachment {
  id: string;
  name: string;
  type: "stl_geometry" | "ebsd_map" | "raw_eis" | "xrd_profile" | "sem_micrograph" | "custom_binary";
  sizeBytes: number;
  data?: string | ArrayBuffer;
  metadata?: Record<string, any>;
  uploadedAt: string;
}

/** Original declared claims retained for traceability, never effective qualification. */
export interface DigitalTwinReportedClaims {
  verification: "unverified";
  currentStatus?: SampleDigitalTwin["currentStatus"];
  certification?: DigitalTwinQualityAndCert;
  mmpdsStatisticalBasis?: DigitalTwinMechanicalProperties["mmpdsStatisticalBasis"];
}

export interface SampleDigitalTwin {
  /** Record provenance does not establish measurement validity or qualification. */
  evidence?: { kind: "demo" | "unresolved" | "user-supplied"; note: string; qualification: "not-assessed"; reportedClaims?: DigitalTwinReportedClaims };
  id: string; // Unique Twin UUID / Serial
  serialNumber: string; // e.g. "TWIN-IN718-LPBF-2026-088"
  sampleName: string; // e.g. "Inconel 718 LPBF High-Pressure Turbine Blade"
  materialCategory: "Nickel Superalloy" | "Titanium Alloy" | "Stainless Steel" | "Alloy Steel" | "Aluminum Aerospace" | "Refractory / CMC" | "Unresolved";
  standardDesignation: string; // e.g. "UNS N07718 / AMS 5662"
  creationDate: string;
  lastUpdated: string;
  leadMetallurgist: string;
  organization: string;
  currentStatus: string;
  
  // Optional large binary attachments (e.g. 50k+ facet binary STL, 1M point EBSD Euler angle maps)
  // Persisted seamlessly in IndexedDB without 5 MB localStorage ceiling
  attachments?: DigitalTwinAttachment[];

  // 8 Integrated Sub-Domains
  chemistry: DigitalTwinChemistry;
  thermodynamics: DigitalTwinThermodynamics;
  processHistory: DigitalTwinProcessHistory;
  microstructure: DigitalTwinMicrostructure;
  mechanical: DigitalTwinMechanicalProperties;
  electrochemistry: DigitalTwinElectrochemistry;
  extremeService: DigitalTwinExtremeService;
  certification: DigitalTwinQualityAndCert;
}




