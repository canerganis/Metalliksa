export type TabType = 
  | "copilot"
  | "calculators"
  | "micrograph"
  | "phase-diagrams"
  | "crystal-3d"
  | "alloy-builder"
  | "elements"
  | "database"
  | "qualification"
  | "notebook";

export interface MmpdsBasisResult {
  meanYield: number; // MPa
  meanTensile: number; // MPa
  stdDev: number; // MPa
  covPct: number; // %
  sampleSize: number;
  kA: number;
  kB: number;
  aBasisYield: number; // MPa
  bBasisYield: number; // MPa
  sBasisYield: number; // MPa
  aBasisTensile: number; // MPa
  bBasisTensile: number; // MPa
  shearUltimate: number; // MPa
  bearingYield: number; // MPa
  bearingUltimate: number; // MPa
  compressiveYield: number; // MPa
  fractureToughnessKic: number; // MPa*m^0.5
  cpk: number;
  status: "A-Basis Qualified" | "B-Basis Qualified" | "S-Basis Provisional" | "Insufficient Sampling";
}

export interface QualificationTestEvaluation {
  id: string;
  standard: "MIL-STD-810H" | "AS9100 Rev D" | "NATO STANAG" | "ASTM / AMS";
  methodName: string;
  testCategory: "Salt Fog / Marine" | "Mechanical Shock" | "Thermal Shock" | "Vibration / High-G" | "Extreme Climatics" | "Process Capability" | "SCC Threshold";
  /** Kept for payload compatibility; screening templates must not auto-score PASS. */
  passProbabilityPct: number;
  riskLevel: "Low" | "Moderate" | "High" | "Critical";
  primaryThreat: string;
  criticalThreshold: string;
  mitigationRecommendation: string;
  executionStatus?: "Not executed" | "User attested";
}

export interface ElementData {
  atomicNumber: number;
  symbol: string;
  name: string;
  atomicMass: number;
  atomicRadius: number; // in pm
  electronegativity: number; // Pauling
  crystalStructure: "BCC" | "FCC" | "HCP" | "Diamond" | "Tetragonal" | "Orthorhombic" | "Hexagonal" | "Rhombohedral" | "Other";
  density: number; // g/cm^3
  meltingPoint: number; // °C
  boilingPoint: number; // °C
  valence: number[];
  youngsModulus?: number; // GPa
  thermalExpansion?: number; // µm/(m·K)
  category: "transition" | "post-transition" | "alkali" | "alkaline-earth" | "metalloid" | "non-metal" | "lanthanide" | "actinide";
  metallurgicalRole: string;
  magnetic?: "Ferromagnetic" | "Paramagnetic" | "Diamagnetic" | "Antiferromagnetic";
}

export interface MaterialSpec {
  id: string;
  name: string;
  category: "Carbon Steel" | "Alloy Steel" | "Tool Steel" | "Stainless Steel" | "Aluminum Alloy" | "Titanium Alloy" | "Nickel Superalloy" | "Copper Alloy" | "Magnesium Alloy" | "Refractory & Specialty" | "Ceramic & Carbide";
  standard: string; // e.g. "AISI 4140", "UNS G41400", "EN 42CrMo4"
  composition: Record<string, number | { min: number; max: number }>;
  yieldStrength: number; // MPa
  tensileStrength: number; // MPa
  elongation: number; // %
  hardness: string; // e.g. "28-32 HRC (Normalized & Tempered)"
  density: number; // g/cm3
  meltingRange: string; // °C
  youngsModulus: number; // GPa
  thermalConductivity?: number; // W/(m·K)
  thermalExpansion?: number; // µm/(m·K)
  poissonRatio?: number;
  microstructure: string;
  heatTreatments: {
    name: string;
    temperature: string;
    cooling: string;
    resultingHardness: string;
  }[];
  applications: string[];
  failureRisks: string[];
}

export interface CarbonEquivalentResult {
  ceIIW: number;
  pcm: number;
  cen: number;
  weldabilityLevel: "Excellent" | "Good" | "Moderate (Preheat required)" | "Poor (High preheat & strict low hydrogen required)";
  recommendedPreheatTemp: number; // in °C
  riskNotes: string[];
}

export interface SchaefflerResult {
  crEq: number;
  niEq: number;
  primaryPhase: "Martensite" | "Austenite" | "Ferrite" | "Austenite + Ferrite" | "Martensite + Austenite" | "Martensite + Ferrite" | "Martensite + Austenite + Ferrite";
  ferriteNumberEstimated: number;
  hotCrackingRisk: "Low" | "Moderate" | "High";
  martensiticHardeningRisk: "Low" | "Moderate" | "High";
}

export interface TransformationTempsResult {
  ms: number; // Martensite start (°C)
  mf: number; // Martensite finish (°C)
  bs: number; // Bainite start (°C)
  ac1: number; // Austenite start (°C)
  ac3: number; // Austenite finish (°C)
}

export interface DiffusionResult {
  caseDepth: number; // mm at threshold
  effectiveCaseDepth: number; // mm at 0.4% C
  profileData: { depthMm: number; concentrationPct: number }[];
  diffusivity: number; // m^2/s
}

export interface XrdPeak {
  hkl: string;
  twoTheta: number; // degrees
  dSpacing: number; // Angstroms
  intensityPct: number;
}

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  imageUrl?: string;
  contextAttached?: any;
}

export interface ConsultMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export interface FieldNotebookEntry {
  id: string;
  title: string;
  date: string;
  author: string;
  category: "Alloy Development" | "Failure Investigation" | "Heat Treatment Run" | "Metallography" | "Quality Control";
  alloyName?: string;
  composition?: Record<string, number>;
  hardnessTest?: string;
  observations: string;
  aiInsights?: string;
  tags: string[];
}
