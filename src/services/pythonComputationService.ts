/**
 * MetalliX Python HPC Subsystem & Proxy Client Service
 * Dispatches heavy, CPU-intensive calculations (CALPHAD Gibbs minimization, elastic-constant homogenisation, PHACOMP,
 * CNLS Levenberg-Marquardt EIS, XRD Peak Deconvolution, 3D Goldak LPBF Thermal, Inverse Alloy NSGA-II, Pourbaix E-pH)
 * to the backend Python 3.10 runtime with automatic fallback to client TypeScript engines.
 */

import {
  MultiComponentAlloyComposition,
  MultiComponentSolveResult,
  solveMultiComponentEquilibrium,
} from "../physics/calphadMultiComponentSolver";
import { parseTDBFile, PRELOADED_MULTI_COMPONENT_TDB } from "../physics/tdbParser";
import { PythonPourbaixResult, ExperimentalEpHEntry } from "../types/pourbaix";
import {
  TafelPythonCorrosionRateInput,
  TafelPythonCorrosionRateResult,
} from "../types/tafel";
import { createSeededRandom } from "../utils/seededRandom";
import { FARADAY_CONSTANT, GAS_CONSTANT_R } from "../utils/physicalConstants";
import { MILS_PER_MM } from "../utils/tafelDisplay";
import { PythonValidationError, validationErrorFromResponse } from "../utils/pythonValidationError";
import {
  CLIENT_DATABASE_LABEL,
  CLIENT_MODEL_LABEL,
  parseCalphadUnavailable,
  type CalphadFieldStatus,
  type CalphadUnavailable,
} from "../utils/calphadDisplay";

export interface PersistentIPCDiagnostics {
  success: boolean;
  status: "online" | "restarting" | "initializing" | "fallback_mode";
  isPersistent: boolean;
  channels?: {
    unixSocket: { path: string; active: boolean };
    httpMicroservice: { url: string; active: boolean };
  };
  requestsProcessed?: number;
  avgLatencyMs?: number;
  uptimeSeconds?: number;
  warmModulesCount?: number;
  lastError?: string | null;
}

export interface PythonEngineStatus {
  online: boolean;
  status: string;
  pythonVersion?: string;
  platform?: string;
  durationMs?: number;
  warm?: boolean;
  channel?: string;
  ipcDaemon?: PersistentIPCDiagnostics;
  /** Server-side qualifier sent instead of a per-subsystem map (currently "unverified"). */
  subsystemStatus?: string;
  subsystems?: {
    calphad_solver?: { available: boolean; description?: string };
    dft_property_calculator?: { available: boolean; description?: string };
    cnls_fitting_solver?: { available: boolean; description?: string };
    xrd_peak_deconvolution?: { available: boolean; description?: string };
    lpbf_thermal_solver?: { available: boolean; description?: string };
    inverse_alloy_optimizer?: { available: boolean; description?: string };
    pourbaix_solver?: { available: boolean; description?: string };
    kinetics_ttt_cct_solver?: { available: boolean; description?: string };
    icme_multiscale_pipeline_solver?: { available: boolean; description?: string };
    stochastic_uq_mmpds_solver?: { available: boolean; description?: string };
  };
}

export interface PythonCalphadDatabaseEntry {
  id: string;
  fileName: string;
  name: string;
  description: string;
  elements: string[];
  primaryPhases: string[];
  source: string;
  suitability: string;
  /** "assessment" or "test-fixture"; a test fixture is refused by the solver. */
  status?: "assessment" | "test-fixture";
  usable?: boolean;
  statusReason?: string | null;
  /** Machine-readable scope: the base elements this database is assessed for. */
  assessedBaseElements?: string[];
}

export interface PythonCalphadSolveResult extends MultiComponentSolveResult {
  engine: string;
  /** null when the engine did not report a time (never an invented one). */
  computeTimeMs: number | null;
  proxyRoundtripMs?: number;
  isPythonEngine: boolean;
  iterations?: number;
  pycalphadVersion?: string;
  databaseUsed?: string;
  databasePath?: string;
  thermodynamicModel?: string;
  isEmpirical?: boolean;
  databaseId?: string;
  databaseStatus?: string;
  /** Per critical-temperature field: computed, heuristic or unavailable with a reason. */
  criticalTemperatureStatus?: Record<string, CalphadFieldStatus>;
  multiElementScheilStatus?: string;
  multiElementScheilNote?: string;
  /** Set when the Python CALPHAD engine answered "unavailable"; the numbers are then the client screening model's. */
  pythonUnavailable?: CalphadUnavailable;
  activeComponents?: string[];
  unsupportedElements?: string[];
  databaseSuitability?: string;
  /** Grid temperatures (degC) whose equilibrium did not converge; their profile entries are null. */
  nonConvergedPoints?: number[];
  boundaryRefinement?: { enabled: boolean; toleranceC: number; equilibriumCalls: number; note: string };
  phacompAnalysis?: {
    status: "screening-tabulated-values" | "unavailable";
    reason?: string;
    n_v_bar: number | null;
    m_d_bar: number | null;
    tcpEmbrittlementRisk: "Low" | "Moderate" | "High" | null;
    tcpSigmaRiskTemperatureC: number | null;
    thermodynamicStabilityIndex: number | null;
  };
}

export interface DFTStructureInput {
  formula: string;
  material_id?: string;
  crystal_system?: string;
  space_group?: string;
  k_vrh?: number;
  g_vrh?: number;
  density?: number;
  formation_energy_per_atom?: number;
  energy_above_hull?: number;
  band_gap?: number;
  /** Cell site count. Not used by the engine (it is not atoms per formula unit); kept for old callers. */
  nsites?: number;
  /** Formula-unit molar mass (g/mol); used only with atoms_per_formula_unit when the formula is not a composition. */
  molar_mass?: number;
  atoms_per_formula_unit?: number;
  custom_c_ij?: {
    c11?: number;
    c22?: number;
    c33?: number;
    c12?: number;
    c13?: number;
    c23?: number;
    c44?: number;
    c55?: number;
    c66?: number;
  };
}

/**
 * Result of the continuum-elasticity engine (python/dft_property_calculator.py, v4.1). The name is
 * historical: nothing here is a DFT calculation (isDft is always false). The engine homogenises supplied
 * or built-in single-crystal elastic constants C_ij.
 */
export interface PythonDFTResult {
  success: true;
  status: "available";
  engine: string;
  scientificModel?: string;
  /** What the module is: "Continuum elasticity ... (not a DFT calculation)". Show it next to results. */
  label?: string;
  isDft?: false;
  /** custom-user-supplied | builtin-library-exact-match | isotropic-from-supplied-K-G */
  constantsOrigin?: string;
  /** unverified | cited-secondary-compilation | supplied-by-caller */
  referenceStatus?: string;
  sourceNotes?: string;
  /** Engine-measured milliseconds; null when none was reported (no invented 0). */
  computeTimeMs: number | null;
  proxyRoundtripMs?: number;
  isPythonEngine: boolean;
  materialInfo: {
    formula: string | null;
    material_id: string;
    crystal_system: string | null;
    space_group: string | null;
    density: number | null;
    formation_energy_per_atom: number | null;
    energy_above_hull: number | null;
    band_gap: number | null;
    is_stable: boolean | null;
    is_metal: boolean | null;
  };
  elasticStiffnessMatrix_Cij_GPa: number[][];
  elasticComplianceMatrix_Sij_1_over_GPa: number[][];
  bornStability?: {
    isMechanicallyStable: boolean;
    minimumEigenvalueGPa: number;
    allEigenvaluesGPa: number[];
    verdict: string;
    criteriaChecks: Array<{
      name: string;
      formula: string;
      value: number;
      passed: boolean;
      physicalMeaning: string;
    }>;
  };
  voigtReussHillModuli: {
    bulkModulus_K_Voigt_GPa: number;
    bulkModulus_K_Reuss_GPa: number;
    bulkModulus_K_VRH_GPa: number;
    shearModulus_G_Voigt_GPa: number;
    shearModulus_G_Reuss_GPa: number;
    shearModulus_G_VRH_GPa: number;
    youngsModulus_E_VRH_GPa: number;
    poissonsRatio_nu: number;
    pWaveModulus_GPa: number;
  };
  mechanicalIntegrityIndices: {
    pughRatio_B_over_G: number;
    cauchyPressure_C12_minus_C44_GPa: number;
    ductilityVerdict: string;
    universalAnisotropyIndex_AU: number;
    /** null for non-cubic crystals: the Zener ratio is defined for cubic crystals only. */
    zenerAnisotropyFactor_AZ: number | null;
    isIsotropic: boolean;
  };
  /** Every number is null (with `reason`) when it cannot be computed without a default or a guess. */
  acousticAndThermalProperties: {
    status?: "available" | "unavailable";
    reason?: string | null;
    longitudinalSoundVelocity_m_s: number | null;
    transverseSoundVelocity_m_s: number | null;
    meanSoundVelocity_m_s: number | null;
    debyeTemperature_K: number | null;
    gruneisenParameter_gamma: number | null;
    minimumThermalConductivity_W_mK: number | null;
    debyeBasis?: {
      atomsPerFormulaUnit: number;
      formulaUnitMolarMass_g_mol: number;
      meanAtomicMass_g_mol: number;
      atomNumberDensity_per_m3: number;
      source: string;
      reference: string;
    } | null;
  };
  /** null for a mechanically unstable tensor (see directionalYoungsModuliReason). */
  directionalYoungsModuli: {
    direction: string;
    hkl: number[];
    /** "lattice": a lattice [hkl]; "cartesian": a Cartesian direction (lattice parameters are not inputs). */
    frame?: "lattice" | "cartesian";
    label?: string;
    youngsModulusGPa: number | null;
    ratioToAverage: number | null;
  }[] | null;
  directionalYoungsModuliStatus?: "available" | "unavailable";
  directionalYoungsModuliReason?: string | null;
}

/** The engine has no result for this input (no default or nearest guess is substituted). */
export interface PythonDFTUnavailable {
  success: false;
  status: "unavailable";
  unavailableCode: string;
  reason: string;
  engine: string;
  label?: string;
  isDft?: false;
  computeTimeMs: number | null;
  isPythonEngine: boolean;
}

export type PythonDFTOutcome = PythonDFTResult | PythonDFTUnavailable;

export function isDftUnavailable(outcome: PythonDFTOutcome): outcome is PythonDFTUnavailable {
  return outcome.status === "unavailable";
}

export interface PythonXRDResult {
  success: boolean;
  engine: string;
  computeTimeMs: number;
  isPythonEngine: boolean;
  peaks: Array<{
    peak_id: number;
    two_theta_deg: number;
    hkl: string;
    fwhm_deg: number;
    eta_lorentz_fraction: number;
    d_spacing_angstrom: number;
    integral_breadth_deg: number;
    apparent_crystallite_size_nm: number;
    microstrain_pct: number;
  }>;
  williamsonHall: {
    linear_slope_4_epsilon: number;
    intercept_K_lambda_over_D: number;
    microstrain_epsilon: number | null;
    microstrain_percent: number | null;
    crystallite_size_nm: number | null;
    dislocation_density_m_minus_2: number | null;
    r_squared: number;
  };
}

// (PythonPourbaixResult imported from types/pourbaix)

export interface PythonKineticsResult {
  success: boolean;
  engine: string;
  computeTimeMs: number;
  proxyRoundtripMs?: number;
  alloy: string;
  alloyMetadata: {
    type: string;
    composition_wt: Record<string, number>;
    Ae3_C: number;
    /** null for non-steel alloys (a eutectoid Ae1 is a steel concept). */
    Ae1_C: number | null;
    /** null where the registry value is a non-physical placeholder (alloy_registry.KINETICS_PLACEHOLDERS). */
    Ms_C: number | null;
    Mf_C: number | null;
    Q_diff_kJ_mol: number;
    grain_size_d_um_default: number;
    aust_temp_C_default: number;
    phases: string[];
    /** null for non-steel alloys (the kinetics model is steel-only). */
    critical_cooling_rate_C_s: number | null;
    description: string;
  };
  inputParameters: {
    selectedCoolingRate_C_s: number;
    austSolutionTemp_C: number;
    priorGrainSize_um: number;
    agingTemp_C: number;
    agingTime_h: number;
  };
  criticalTransformationTemperatures: {
    Ae3_BetaTransus_GammaSolvus_C: number;
    /** null for non-steel alloys (Ae1_C_status "unavailable-kinetics-model-steel-only"). */
    Ae1_C: number | null;
    Ae1_C_status?: string;
    /** null for a registry placeholder (Ms_C_status "unavailable-registry-placeholder"). */
    Ms_C: number | null;
    Mf_C: number | null;
    /** null for non-steel alloys (the kinetics model is steel-only). */
    CriticalCoolingRate_CCR_C_s: number | null;
    Ms_C_status?: string;
    Mf_C_status?: string;
    CriticalCoolingRate_CCR_status?: string;
  };
  /**
   * Steel TTT points; null for non-steel alloys (kinetics model is steel-only). floorHit: tStart_s is the 1 ms
   * incubation floor, not a model value.
   */
  tttIsothermalCurves: Array<{
    temperature_C: number;
    phase: string;
    tStart_s: number;
    t50_s: number;
    tFinish_s: number;
    avramiExponent_n: number;
    drivingForce_DeltaT_C: number;
    floorHit?: boolean;
  }> | null;
  /**
   * The values below are null where unavailable: for every non-steel alloy (kinetics model is steel-only) and for a
   * steel start the 1 ms TTT floor drives (see transformedStart_status / unavailableReason).
   */
  cctContinuousCoolingMap: Array<{
    coolingRate_C_s: number;
    transformedStartTemp_C: number | null;
    transformedStartTime_s: number | null;
    primaryMicrostructure: string | null;
    phaseFractions: {
      Martensite_pct: number | null;
      Bainite_pct: number | null;
      Pearlite_Ferrite_pct: number | null;
      RetainedAustenite_pct: number | null;
    };
    predictedHardness_HRC: number | null;
    /** ASTM E140 Table 1 conversion of the predicted HRC (non-austenitic steels, HRC 20-68); null otherwise. */
    predictedHardness_HV: number | null;
    predictedHardness_HV_status?: string;
    transformedStart_status?: string;
    phaseFractions_status?: string;
    predictedHardness_HRC_status?: string;
    unavailableReason?: string | null;
  }>;
  /** Radius/strengthening/regime are null at or above the registry solvus (steels: Ae1): status says so. */
  lswPrecipitateCoarsening: Array<{
    agingTime_h: number;
    meanRadius_nm: number | null;
    precipitationHardening_MPa: number | null;
    strengtheningMechanism: string | null;
    status?: string;
  }>;
  calphadVsKineticsGap: {
    equilibriumPrediction: {
      /** null for non-steel alloys; for steels a fixed text (status "static-text-not-a-calphad-calculation"). */
      stablePhasesAtRT: string | null;
      martensiteFraction: string | null;
      soluteSupersaturation: string | null;
      status?: string;
      reason?: string;
    };
    kineticRealityAtSelectedCooling: {
      coolingRate_C_s: number;
      criticalCoolingRate_C_s: number | null;
      isSuppressedEquilibrium: boolean | null;
      predictedMartensite_pct: number | null;
      diffusionSuppressionIndex: number | null;
      verdict: string | null;
      status?: string;
      reason?: string;
    };
  };
  /** "unavailable" with reason "kinetics model is steel-only" for Inconel 718, Ti-6Al-4V and Al 7075. */
  kineticsModel?: {
    status: "available" | "unavailable";
    reason: string | null;
    scope: string;
    registryAlloyId: string;
    illustrativeOnly: boolean;
    note: string;
    placeholderParameters: string[];
    lswPrecipitateCoarsening?: { status: string; note: string; reason: string | null };
  };
  /** TTT incubation floor summary: points whose tStart_s is the 1 ms floor (floorHit). */
  tttIncubationFloor?: {
    status: string;
    floorValue_s: number;
    pointCount: number | null;
    floorHitCount: number | null;
    note: string;
  };
}

export interface PythonBayesianOptimizationResult {
  success: boolean;
  alloyId: string;
  bestParams?: {
    laserPower_W: number;
    scanSpeed_mms: number;
    hatch_um: number;
    layer_um: number;
  };
  bestScore: number;
  iterations: Array<{
    iteration: number;
    params: {
      laserPower_W: number;
      scanSpeed_mms: number;
      hatch_um: number;
      layer_um: number;
    };
    score: number;
    verdict: string;
  }>;
  converged: boolean;
  elapsedMs: number;
  nIterations: number;
}

// Phase 8: Solidification Microstructure Lab result type.
// Screening-field path (python/lpbf_solidification_microstructure.py compute_screening_field_microstructure):
// the numbers are thermal.solidificationKinetics from lpbf_thermal_solver (equal to the Build Job projection only
// for heatSource=rosenthal with the Build Job's inputs).
// status "available" = liquidus field-map G/R; "screening-fallback" = tail-length heuristic (reason says so);
// "degenerate-floor" = field map used but R/cooling are the solver's clamp floors (R <= 1e-4 m/s or cooling <=
// 1 K/s): the numbers are copied but are NOT a computed result and must not be shown as one;
// "unavailable" = no numbers (missing/unknown/impossible input), reason says why. Callers must check status first.
export interface SolidificationMicrostructureAvailable {
  status: 'available' | 'screening-fallback';
  reason?: string | null;
  source: string;
  modelId?: string | null;
  gradientSource?: string | null;
  usedFieldMap?: boolean | null;
  heatSourceModel?: string | null;
  materialName?: string | null;
  regime?: string | null;
  regimeNote?: string | null;
  normalizedEnthalpy?: number | null;
  absorptivity?: { effective: number | null; conduction: number | null };
  materialEvidence?: Record<string, unknown>;
  inputs?: Record<string, number>;
  morphologyBands_G_over_R?: { planar: number; cellular: number; columnar: number };
  scope?: string;
  G_K_m: number;
  R_m_s: number;
  coolingRate_K_s: number;
  g_over_r_ratio?: number | null;
  PDAS_um: number;
  SDAS_um: number;
  morphology: string;
  doi?: string | Record<string, string> | null;
  disclaimer: string;
  // Legacy CFD path only (a cfdResult was supplied); absent on the screening-field path.
  maxG_K_m?: number;
  maxR_m_s?: number;
  morphologyFractions?: { columnar: number; equiaxed: number; mixed: number };
  frontCellCount?: number;
}

export interface SolidificationMicrostructureUnavailable {
  status: 'unavailable';
  reason: string;
  source: string;
  heatSourceModel?: string | null;
  scope?: string;
  disclaimer?: string;
  doi?: string | Record<string, string> | null;
  G_K_m: null;
  R_m_s: null;
  coolingRate_K_s: null;
  PDAS_um: null;
  SDAS_um: null;
  morphology: null;
}

export type SolidificationMicrostructureDegenerate =
  Omit<SolidificationMicrostructureAvailable, 'status' | 'reason'> & {
    status: 'degenerate-floor';
    reason: string;
  };

export type SolidificationMicrostructureResult =
  | SolidificationMicrostructureAvailable
  | SolidificationMicrostructureDegenerate
  | SolidificationMicrostructureUnavailable;

// Phase 9: Thermomechanical Distortion Lab result type
export interface ThermomechanicalDistortionResult {
  modelId: string;
  status: string;
  strains: {
    exx: number;
    eyy: number;
    ezz: number;
  };
  residualStress: {
    vonMises_MPa: number;
    yieldLimit_MPa: number;
    riskLevel: "low" | "moderate" | "high";
  };
  distortion: {
    maxDeflection_mm: number;
    referenceLength_mm: number;
    referenceThickness_mm: number;
  };
}

class PythonComputationService {
  private statusCache: PythonEngineStatus | null = null;
  private lastCheckTime = 0;
  private statusInflight: Promise<PythonEngineStatus> | null = null;
  private statusSeq = 0;
  private statusAppliedSeq = 0;

  async runLpbfBayesianOptimization(data: any): Promise<PythonBayesianOptimizationResult> {
    const res = await fetch("/api/python/lpbf-bayesian-optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  // Phase 8: Solidification Microstructure Lab
  // params: materialName + power_W, speed_mm_s, beamDiameter_um, preheat_C, layerThickness_um, hatch_um, heatSource.
  // Python looks the alloy up by materialName; no k/liquidus/absorptivity is sent.
  async computeSolidificationMicrostructure(data: {
    params: Record<string, number | string>;
    material?: Record<string, number | string>;
    cfdResult?: Record<string, unknown>;
  }): Promise<SolidificationMicrostructureResult> {
    const res = await fetch("/api/python/lpbf-solidification-microstructure", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  // Phase 9: Thermomechanical Distortion Lab
  async computeThermomechanicalDistortion(data: {
    params: Record<string, number | string>;
    material: Record<string, number | string>;
    cfdResult?: Record<string, unknown>;
  }): Promise<ThermomechanicalDistortionResult> {
    const res = await fetch("/api/python/lpbf-thermomechanical-distortion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  // Phase 12: Toolpath & Scanner Kinematics
  async simulateToolpathKinematics(data: {
    content: string;
    format: "gcode" | "cli";
    defaultPower_W?: number;
    defaultSpeed_mms?: number;
    accelMax_mms2?: number;
    jumpSpeed_mms?: number;
    skywritingEnabled?: boolean;
  }): Promise<any> {
    const res = await fetch("/api/python/lpbf-toolpath-kinematics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  // Phase 13: Murakami Fatigue & Fracture Mechanics
  async computeMurakamiFatigue(data: {
    alloyName: string;
    sqrtArea_um: number;
    location: "surface" | "sub-surface" | "internal";
    stressRatio_R: number;
    stressAmplitude_MPa?: number;
  }): Promise<any> {
    const res = await fetch("/api/python/lpbf-fatigue-fracture", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  // Phase 15: Closed-Loop Feed-Forward Mitigation
  async processAdaptiveFeedforward(data: {
    content: string;
    format?: "gcode" | "cli";
    defaultPower_W?: number;
    defaultSpeed_mms?: number;
    apply67DegRotation?: boolean;
    layerIndex?: number;
    accelMax_mms2?: number;
    jumpSpeed_mms?: number;
  }): Promise<any> {
    const res = await fetch("/api/python/lpbf-adaptive-feedforward", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  // Phase 16: Multi-Laser Synchronization & Plume Attenuation
  async simulateMultiLaserPlume(data: {
    gasFlow?: { gasType?: string; velocity_m_s?: number; angle_deg?: number };
    plumeParams?: {
      sigma_plume_mm?: number;
      decay_length_mm?: number;
      base_extinction_coeff?: number;
      min_collision_dist_mm?: number;
      attenuation_hazard_threshold?: number;
    };
    laser1_vectors?: number[][];
    laser2_vectors?: number[][];
    mode?: "simulate" | "optimize";
  }): Promise<any> {
    const res = await fetch("/api/python/lpbf-multilaser-plume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  /**
   * Check whether the configured Python runtime is reachable
   */
  async checkEngineStatus(forceRefresh = false): Promise<PythonEngineStatus> {
    const now = Date.now();
    if (!forceRefresh && this.statusCache && now - this.lastCheckTime < 15000) {
      return this.statusCache;
    }
    // Non-forced callers share one in-flight request (app shell and boot check start together).
    if (!forceRefresh && this.statusInflight) return this.statusInflight;
    const request = this.requestEngineStatus(now).finally(() => {
      if (this.statusInflight === request) this.statusInflight = null;
    });
    this.statusInflight = request;
    return request;
  }

  private async requestEngineStatus(now: number): Promise<PythonEngineStatus> {
    const seq = ++this.statusSeq;
    let result: PythonEngineStatus;
    try {
      const res = await fetch("/api/python/status", {
        method: "GET",
        headers: { "Accept": "application/json" },
      });

      if (!res.ok) {
        throw new Error(`Status check HTTP ${res.status}`);
      }

      const data = await res.json();
      result = {
        online: data.success === true || data.status === "online" || data.status === "ready",
        status: data.status || "online",
        pythonVersion: data.pythonVersion ?? undefined,
        platform: data.platform,
        durationMs: data.durationMs,
        warm: data.warm === true,
        channel: data.channel ?? undefined,
        ipcDaemon: data.ipcDaemon,
        subsystems: data.subsystems,
        subsystemStatus: typeof data.subsystemStatus === "string" ? data.subsystemStatus : undefined,
      };
    } catch (err: any) {
      result = {
        online: false,
        status: "client_fallback",
        durationMs: 0,
      };
    }
    // An older request that finishes after a newer (e.g. forced) one must not overwrite its answer.
    if (seq < this.statusAppliedSeq && this.statusCache) return this.statusCache;
    this.statusAppliedSeq = seq;
    this.statusCache = result;
    this.lastCheckTime = now;
    return result;
  }

  /**
   * Fetches real-time status of the persistent Python IPC microservice daemon
   */
  async getIPCStatus(): Promise<PersistentIPCDiagnostics> {
    try {
      const res = await fetch("/api/python/ipc-status", {
        headers: { "Accept": "application/json" },
      });
      if (!res.ok) throw new Error(`IPC status check HTTP ${res.status}`);
      return await res.json();
    } catch (err: any) {
      return {
        success: false,
        status: "fallback_mode",
        isPersistent: false,
        channels: {
          // Unknown while the status endpoint is unreachable (the daemon picks its own addresses).
          unixSocket: { path: "", active: false },
          httpMicroservice: { url: "", active: false },
        },
        requestsProcessed: 0,
        avgLatencyMs: 0,
        uptimeSeconds: 0,
        warmModulesCount: 0,
        lastError: err.message,
      };
    }
  }

  /**
   * Forces re-warming of in-memory Python calculation modules
   */
  async triggerIPCWarmup(): Promise<{ success: boolean; durationMs?: number; message?: string }> {
    try {
      const res = await fetch("/api/python/ipc-warmup", {
        method: "POST",
        headers: { "Accept": "application/json" },
      });
      return await res.json();
    } catch (err: any) {
      return { success: false, message: err.message };
    }
  }

  /**
   * Fetches available Open-Source Thermodynamic Databases (TDB) supported by the backend pycalphad engine
   */
  async getCalphadDatabases(): Promise<{
    success: boolean;
    engine: string;
    pycalphadAvailable: boolean;
    pycalphadVersion: string;
    databases: PythonCalphadDatabaseEntry[];
  }> {
    try {
      const res = await fetch("/api/python/calphad-databases", {
        headers: { "Accept": "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err: any) {
      return {
        success: false,
        engine: "client-fallback",
        pycalphadAvailable: false,
        pycalphadVersion: "Unavailable",
        databases: [],
      };
    }
  }

  /**
   * Dispatch CALPHAD Gibbs free energy multi-component minimization to pycalphad backend
   */
  async solveCalphadEquilibrium(
    alloy: MultiComponentAlloyComposition,
    tMin = 400,
    tMax = 1450,
    tStep = 20,
    usePython = true,
    databaseId?: string,
    customTdbText?: string,
    adaptiveGrid = true,
    boundaryRefinement = true,
    minRefineStep = 0.5
  ): Promise<PythonCalphadSolveResult> {
    let pythonUnavailable: CalphadUnavailable | null = null;
    if (usePython) {
      let validation: PythonValidationError | null = null;
      try {
        const res = await fetch("/api/python/calphad-minimize", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: alloy.name,
            elements: alloy.elements,
            unit: alloy.unit || "wt_pct",
            tMin,
            tMax,
            tStep,
            databaseId,
            customTdbText,
            adaptiveGrid,
            boundaryRefinement,
            minRefineStep,
          }),
        });

        if (res.ok) {
          const data = await res.json();
          if (data.success && data.equilibriumProfile) {
            return {
              ...data,
              isPythonEngine: true,
              engine: data.engine || "pycalphad-open-tdb",
              computeTimeMs: typeof data.computeTimeMs === "number" ? data.computeTimeMs : null,
            };
          }
          // The Python engine has no fallback model: it says "unavailable" and why.
          pythonUnavailable = parseCalphadUnavailable(data);
        } else {
          validation = await validationErrorFromResponse(res, "CALPHAD");
        }
      } catch (err) {
        console.warn("Python CALPHAD proxy call failed, falling back to TypeScript engine:", err);
      }
      // Invalid input (e.g. an unknown element symbol): surface it; the caller decides
      // whether to show the client solver instead. Network errors and 5xx still fall back.
      if (validation) throw validation;
    }

    // Client-side TypeScript Fallback
    const startTime = performance.now();
    const fallbackTdb = parseTDBFile(
      PRELOADED_MULTI_COMPONENT_TDB[0].rawTdbText,
      PRELOADED_MULTI_COMPONENT_TDB[0].name
    );
    const clientResult = solveMultiComponentEquilibrium(alloy, fallbackTdb, tMin, tMax, tStep);
    const elapsed = Math.round(performance.now() - startTime);

    // Client screening numbers: labelled as such, never as a pycalphad/CALPHAD result.
    return {
      ...clientResult,
      engine: "MetalliX-Client-TS-Solver",
      computeTimeMs: elapsed,
      isPythonEngine: false,
      isEmpirical: true,
      thermodynamicModel: CLIENT_MODEL_LABEL,
      databaseUsed: CLIENT_DATABASE_LABEL,
      iterations: (tMax - tMin) / tStep,
      ...(pythonUnavailable ? { pythonUnavailable } : {}),
    };
  }

  /**
   * Dispatch the continuum-elasticity calculation (6x6 stiffness homogenisation, Born stability,
   * per-atom Debye temperature) to Python. The route name (dft-properties) is historical: this is not a
   * DFT calculation. When Python cannot answer there is no client-side substitute (the old fallback
   * filled in fixed velocities, a 450 K Debye temperature and a Grueneisen constant): the result is
   * "unavailable" with the reason.
   */
  async calculateDFTProperties(
    input: DFTStructureInput,
    usePython = true
  ): Promise<PythonDFTOutcome> {
    const unavailable = (code: string, reason: string): PythonDFTUnavailable => ({
      success: false,
      status: "unavailable",
      unavailableCode: code,
      reason,
      engine: "MetalliX-Continuum-Elasticity-Homogenizer",
      isDft: false,
      computeTimeMs: null,
      isPythonEngine: false,
    });
    if (!usePython) {
      return unavailable("PYTHON_NOT_REQUESTED", "The Python elasticity engine was not requested; there is no client-side substitute.");
    }
    try {
      const res = await fetch("/api/python/dft-properties", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.status === "unavailable") {
          return {
            ...data,
            success: false,
            isPythonEngine: true,
            computeTimeMs: typeof data.computeTimeMs === "number" ? data.computeTimeMs : null,
          };
        }
        if (data && data.success && data.elasticStiffnessMatrix_Cij_GPa) {
          return {
            ...data,
            status: "available",
            isPythonEngine: true,
            engine: data.engine || "MetalliX-Continuum-Elasticity-Homogenizer",
            computeTimeMs: typeof data.computeTimeMs === "number" ? data.computeTimeMs : null,
          };
        }
        const detail = data && typeof data.error === "string" ? `: ${data.error}` : "";
        return unavailable("PYTHON_BAD_RESPONSE", `The Python elasticity engine returned no tensor${detail}.`);
      }
      return unavailable("PYTHON_HTTP_ERROR", `The Python elasticity engine answered HTTP ${res.status}.`);
    } catch (err) {
      console.warn("Python elasticity proxy call failed:", err);
      return unavailable("PYTHON_UNREACHABLE", "The Python elasticity engine could not be reached; there is no client-side substitute.");
    }
  }

  /**
   * Dispatch XRD Peak Deconvolution & Williamson-Hall Microstrain Analysis to Python
   */
  async deconvolveXRD(payload: {
    twoTheta?: number[];
    intensity?: number[];
    radiationWavelength?: number;
    radiationKa1?: number;
    radiationKa2?: number;
    instrumentBroadeningDeg?: number;
    peaks?: Array<{ twoTheta: number; hkl: string; intensity?: number }>;
  }): Promise<PythonXRDResult> {
    // No client fallback: a failed or unsuccessful dispatch is an error, never a made-up fit.
    const res = await fetch("/api/python/xrd-deconvolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data?.success) {
      const detail = typeof data?.error === "string" ? `: ${data.error}` : "";
      throw new Error(`XRD deconvolution failed (HTTP ${res.status})${detail}`);
    }
    return { ...data, isPythonEngine: true };
  }

  /**
   * Dispatch Pourbaix E-pH Electrochemical Stability Solver to Python
   */
  async solvePourbaixDiagram(payload: {
    element?: string;
    temperature_C?: number;
    ionActivity_log10?: number;
    chloride_ppm?: number;
    experimentalPoints?: ExperimentalEpHEntry[];
  }, signal?: AbortSignal): Promise<PythonPourbaixResult> {
    const res = await fetch("/api/python/pourbaix-diagram", {
      signal,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const validation = await validationErrorFromResponse(res, "Pourbaix");
      if (validation) throw validation;
      throw new Error(`Pourbaix proxy error: HTTP ${res.status}`);
    }

    return await res.json();
  }

  /**
   * Dispatch Phase Transformation Kinetics (JMAK / TTT / CCT / LSW) Solver to Python
   */
  async calculatePhaseKineticsTTTCCT(payload: {
    alloy?: string;
    coolingRate_C_s?: number;
    grainSize_um?: number;
    austTemp_C?: number;
    agingTemp_C?: number;
    agingTime_h?: number;
  }): Promise<PythonKineticsResult> {
    const res = await fetch("/api/python/kinetics-ttt-cct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Phase Kinetics proxy error: HTTP ${res.status}`);
    }

    return await res.json();
  }

  /**
   * Dispatch the ICME multi-scale closed-form estimator (illustrative: tabulated constants, no DFT/CALPHAD/FEA run) to Python
   */
  async calculateICMEMultiScalePipeline(payload: {
    alloyName?: string;
    baseMetal?: "Ni" | "Fe" | "Ti" | "Al";
    crystalSystem?: "FCC" | "BCC" | "HCP";
    composition_wt?: { [key: string]: number };
    coolingRate_C_s?: number;
    grainSize_um?: number | null;
    agingTemp_C?: number;
    agingTime_h?: number;
    strainRate_s_inv?: number;
    serviceTemp_C?: number;
    componentType?: string;
  }): Promise<PythonICMEMultiScaleResult> {
    const res = await fetch("/api/python/icme-multiscale-pipeline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`ICME MultiScale Pipeline proxy error: HTTP ${res.status}`);
    }

    return await res.json();
  }

  /**
   * Dispatch Stochastic Uncertainty Quantification (UQ) & Aerospace MMPDS Allowables Solver to Python
   */
  async calculateStochasticUQMMPDS(payload: {
    alloyName?: string;
    baseMetal?: "Ni" | "Fe" | "Ti" | "Al";
    standardSpec?: string;
    composition_wt?: { [key: string]: number };
    composition_tolerances?: { [key: string]: number };
    coolingRate_nominal?: number;
    coolingRate_cov?: number;
    agingTemp_nominal?: number;
    agingTemp_stdDev?: number;
    agingTime_nominal?: number;
    agingTime_stdDev?: number;
    serviceStress_nominal?: number;
    serviceStress_cov?: number;
    initialFlawSize_um_mean?: number;
    initialFlawSize_um_std?: number;
    specMinYield_MPa?: number;
    specMinUTS_MPa?: number;
    specMinElongation_pct?: number;
    mcSamples?: number;
    samplingMethod?: "sobol_qmc";
    scramble?: boolean;
    seed?: number;
  }): Promise<PythonStochasticUQResult> {
    const res = await fetch("/api/python/stochastic-uq-mmpds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Stochastic UQ & MMPDS proxy error: HTTP ${res.status}`);
    }

    return await res.json();
  }

  /**
   * High-Fidelity 3D LPBF Laser Melt Pool, Geometry & Multi-Defect Physics Solver
   */
  async solveLPBFThermalPhysics(payload: {
    material: string;
    laserPower_W: number;
    scanSpeed_mm_s: number;
    beamDiameter_um: number;
    preheatTemp_C?: number;
    layerThickness_um?: number;
    hatchSpacing_um?: number;
    laserWavelength?: "IR_1064nm" | "Green_515nm" | "Blue_450nm";
    heatSource?: "rosenthal" | "eagar-tsai" | "goldak";
    sulfur_ppm?: number;
  }, signal?: AbortSignal): Promise<PythonLPBFResult> {
    const res = await fetch("/api/python/lpbf-thermal-solver", {
      signal,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`LPBF Thermal & Melt Pool proxy error: HTTP ${res.status}`);
    }

    return await res.json();
  }

  /**
   * CAD/STL hatch discretization and LPBF build-time estimate (galvo + recoater).
   */
  async solveSTLSlicerBuildTime(payload: {
    preset?: string;
    material: string;
    laserPower_W: number;
    scanSpeed_mms: number;
    layerThickness_um: number;
    hatchSpacing_um: number;
    recoatTimePerLayer_s?: number;
    hatchStrategy?: string;
    customTriangles?: number[][][] | null;
    cadAssetName?: string;
    triangleCountNative?: number;
  }): Promise<PythonSTLSlicerResult> {
    const res = await fetch("/api/python/stl-slicer-build-time", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recoatTimePerLayer_s: 9,
        hatchStrategy: "meander",
        preset: payload.preset ?? "nozzle",
        ...payload,
      }),
    });
    if (!res.ok) {
      throw new Error(`STL slicer / build-time proxy error: HTTP ${res.status}`);
    }
    return await res.json();
  }

  /**
   * Single Build Job: Rosenthal screening + slicer + print verdict (Python owns the decision).
   */
  async solveLpbfBuildJob(payload: {
    alloyId: string;
    thermalMaterial?: string;
    slicerMaterial?: string;
    laserPower_W: number;
    scanSpeed_mm_s: number;
    beamDiameter_um: number;
    preheatTemp_C?: number;
    layerThickness_um: number;
    hatchSpacing_um: number;
    laserWavelength?: "IR_1064nm" | "Green_515nm" | "Blue_450nm";
    preset?: string;
    customTriangles?: number[][][] | null;
    cadAssetName?: string;
    triangleCountNative?: number;
    processSeed?: number;
    scanStrategy?: string;
    stripeWidth_mm?: number;
    scanRotation_deg?: number;
    hatchDwell_ms?: number;
    inclineAngle_deg?: number;
    downskinOverhang_deg?: number;
    maxTriangles?: number;
    enableUq?: boolean;
    uqSamples?: number;
    includeAmbench?: boolean;
    defectSqrtAreas_um?: number[] | null;
    defectSqrtAreasPaste?: string;
    hardness_HV?: number;
    ctDetectionThreshold_um?: number;
    bypassCache?: boolean;
    gitSha?: string;
  }): Promise<PythonLpbfBuildJobResult> {
    const res = await fetch("/api/lpbf/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobType: "build-job", ...payload }),
    });
    if (!res.ok) {
      let detail = `LPBF build-job proxy error: HTTP ${res.status}`;
      try {
        const failed = await res.json();
        if (failed?.error) detail = String(failed.error);
      } catch { /* keep HTTP status text */ }
      throw new Error(detail);
    }
    const jobInfo = await res.json();
    const jobId = jobInfo.id;
    if (!jobId) throw new Error("No Job ID returned from /api/lpbf/jobs");

    while (true) {
      const poll = await fetch(`/api/lpbf/jobs/${jobId}`);
      if (!poll.ok) throw new Error(`Failed to poll job status: HTTP ${poll.status}`);
      const statusData = await poll.json();
      if (statusData.status === "completed") {
        return statusData.result;
      }
      if (["failed", "cancelled", "timed_out"].includes(statusData.status)) {
        throw new Error(statusData.error || `Python LPBF build-job ${statusData.status}`);
      }
      await new Promise(r => setTimeout(r, 500));
    }
  }

  /**
   * ASTM G102 & G59 Automated Annual Corrosion Rate (mm/year) via Python CPython 3.10 Engine
   */
  async calculateTafelCorrosionRate(
    payload: TafelPythonCorrosionRateInput
  ): Promise<TafelPythonCorrosionRateResult> {
    let validation: PythonValidationError | null = null;
    try {
      const res = await fetch("/api/python/tafel-corrosion-rate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          return {
            ...data,
            isPythonEngine: true,
          };
        }
      } else {
        validation = await validationErrorFromResponse(res, "Tafel");
      }
    } catch (err) {
      console.warn("Tafel Corrosion Rate Python proxy error, using client fallback:", err);
    }

    // Invalid input (e.g. unknown alloy): never substitute the client formula.
    if (validation) throw validation;

    // Client-side fallback with exact same ASTM G102 formulas
    return fallbackClientTafelCorrosionRate(payload);
  }
}

export interface PythonSTLSlicerResult {
  success?: boolean;
  pythonDurationMs?: number;
  geometrySource?: "uploaded-stl" | "demo-preset";
  preset?: string;
  cadAssetName?: string;
  meshMetrics?: {
    sizeX_mm: number;
    sizeY_mm: number;
    sizeZ_mm: number;
    estimatedSolidVolume_cm3: number;
    estimatedPartMass_g: number;
    triangleCount: number;
    triangleCountNative?: number;
  };
  buildTimeSummary?: {
    totalLayers: number;
    totalBuildTime_hr: number;
    totalBuildTime_min: number;
    totalLaserTime_hr: number;
    totalRecoatTime_hr: number;
    laserDutyRatio_pct: number;
    peakLayerArea_mm2: number;
    meanLayerArea_mm2: number;
  };
}

export type PythonLpbfGateStatus = "pass" | "warn" | "fail";

export interface PythonLpbfScreeningGate {
  id: string;
  status: PythonLpbfGateStatus;
  measured: number;
  required: number | null;
  unit: string;
  note: string;
}

export interface PythonLpbfSuggestedPatch {
  laserPower_W: number;
  scanSpeed_mms: number;
  hatch_um: number;
  layer_um: number;
  beamDiameter_um: number;
}

export interface PythonLpbfBuildJobVerdict {
  verdict: "printable" | "risky" | "do-not-print";
  headline: string;
  reasons: string[];
  lofGeometry: {
    widthOverHatch: number;
    depthOverLayer: number;
    tangIndex?: number;
    hOverW?: number;
    tOverD?: number;
  };
  literatureWindow: {
    inside: boolean;
    alloyId: string;
    box: { powerMin_W: number; powerMax_W: number; speedMin_mm_s: number; speedMax_mm_s: number };
  };
  gates?: PythonLpbfScreeningGate[];
  dominantGate?: string;
  suggestedPatch?: PythonLpbfSuggestedPatch | null;
  uq?: {
    P_printable: number;
    normalizedEnthalpy: { mean: number; std: number; unit: string };
    dominantUncertainty: string;
    nSamples: number;
  };
}

export interface PythonLpbfUqBlock {
  enabled: boolean;
  nSamples: number;
  seed: number;
  bands: Record<string, number>;
  calibration: string;
  P_printable: number;
  counts: { printable: number; risky: number; do_not_print: number };
  normalizedEnthalpy: { mean: number; std: number; unit: string };
  sobolProxy: Record<string, number>;
  screeningSensitivity?: Record<string, number>;
  sensitivityMethod?: string;
  dominantUncertainty: string;
  note: string;
}

export interface PythonLpbfAmbenchBlock {
  source: {
    challenge: string;
    doi: string;
    url: string;
    alloy: string;
    citation: string;
  };
  model: string;
  disclaimer: string;
  cases: Array<{
    caseId: string;
    nist: { length_um: number; width_um: number; depth_um: number };
    predicted: { length_um: number; width_um: number; depth_um: number };
    mape_pct: { length: number | null; width: number | null; depth: number | null; mean: number | null };
  }>;
  overallMeanMape_pct: number | null;
  alloyCoverage?: { status: string; note: string };
  fourAlloyCoverage?: Record<string, { status: string; note: string }>;
}

export interface PythonLpbfMurakamiBlock {
  status: string;
  fatigueLimit_MPa?: number | null;
  fatigueLimit_internal_MPa?: number;
  fatigueLimit_surface_MPa?: number;
  hardness_HV?: number;
  hardnessSource?: string;
  nDefects?: number;
  gumbel?: Record<string, number | string> | null;
  note: string;
  pasteHint?: string;
  alloyHvDefaults?: Record<string, number>;
  ctDetectionThreshold_um?: number | null;
}

export interface PythonLpbfQualificationBlock {
  status: string;
  screeningOnly: boolean;
  alloyId: string;
  standards: string[];
  couponPlan: string[];
  traceability: { inputHash: string; gitSha?: string | null; note: string };
  note: string;
}

export interface PythonLpbfCacheMeta {
  hit: boolean;
  key: string;
  ageMs: number;
  stats?: { entries: number; hits: number; misses: number; hitRate: number };
}

export interface PythonLpbfBuildJobResult {
  success: boolean;
  error?: string;
  engine: string;
  modelId: string;
  solverRevision?: string;
  materialPropertySchemaVersion?: number;
  materialPropertyRevision?: string;
  materialPropertySha256?: string;
  materialPropertySnapshot?: {
    schemaVersion: number;
    alloyId: string;
    thermal: Record<string, unknown>;
    slicer: Record<string, unknown>;
  };
  buildJobIdentity?: {
    schemaVersion: number;
    alloyId: string;
    modelId: string;
    solverRevision: string;
    materialPropertySchemaVersion: number;
    materialPropertyRevision: string;
    materialPropertySha256: string;
    sha256: string;
  };
  assumptions: string[];
  alloyId: string;
  processSeed?: number;
  scanStrategy?: {
    id: string;
    stripeWidth_mm: number;
    rotation_deg: number;
    hatchDwell_ms: number;
  };
  computeTimeMs: number;
  thermal: PythonLPBFResult;
  slicer: PythonSTLSlicerResult;
  verdict: PythonLpbfBuildJobVerdict;
  uq?: PythonLpbfUqBlock | null;
  ambench?: PythonLpbfAmbenchBlock | null;
  murakami?: PythonLpbfMurakamiBlock | null;
  qualification?: PythonLpbfQualificationBlock | null;
  cache?: PythonLpbfCacheMeta | null;
  porosity?: any;
  kinematics?: any;
  microstructure?: any;
  kinetics?: any;
}

export interface PythonLPBFResult {
  success: boolean;
  engine: string;
  modelId?: string;
  heatSourceModel?: string;
  keyholeModel?: {
    modelId?: string;
    fabbroDepth_um?: number;
    aspectRatio_e_over_d?: number;
    peclet?: number;
    absorptivity?: number;
    doi?: string;
  };
  marangoniModel?: {
    modelId?: string;
    flowDirection?: string;
    dGamma_dT_N_mK?: number;
    sulfur_ppm?: number;
    surfaceVelocity_m_s?: number;
    pecletMarangoni?: number;
    aspectNote?: string;
    doi?: string;
  };
  computeTimeMs: number;
  proxyRoundtripMs?: number;
  material: string;
  baseMetal: string;
  laserWavelength: string;
  processParameters: {
    laserPower_W: number;
    scanSpeed_mm_s: number;
    beamDiameter_um: number;
    preheatTemp_C: number;
    layerThickness_um: number;
    hatchSpacing_um: number;
    inclineAngle_deg?: number;
    processSeed?: number;
    effectiveAbsorptivity: number;
    effectiveConductivity_W_mK?: number;
    effectiveSpecificHeat_J_kgK?: number;
    solidConductivity_W_mK?: number;
    liquidConductivity_W_mK?: number;
    volumetricEnergyDensity_J_mm3: number;
    linearEnergyDensity_J_m: number;
    peakIntensity_MW_cm2?: number;
    normalizedEnthalpy: number;
    heatSource?: string;
    conductionAbsorptivity?: number;
    fabbroAbsorptivity?: number;
  };
  meltPoolGeometry: {
    length_um: number;
    width_um: number;
    depth_um: number;
    aspectRatio_L_over_W: number;
    depthToWidthRatio_D_over_W: number;
    keyholeVaporCavityDepth_um: number;
    regime: string;
    goldakParameters: {
      semiAxis_af_front_um: number;
      semiAxis_ar_rear_um: number;
      semiAxis_b_halfwidth_um: number;
      semiAxis_c_depth_um: number;
    };
  };
  hydrodynamicsAndRecoil: {
    peakTemperature_C: number;
    surfaceTemperature_C?: number;
    knudsenRecoilPressure_kPa: number;
    marangoniNumber: number;
    marangoniGeometrySource?: string;
    molarMass_kg_mol?: number;
    pecletThermalNumber: number;
    powderDenudationWidth_um: number;
  };
  defectDiagnostics: {
    lackOfFusionStatus: "Pass" | "Warning" | "Fail";
    lackOfFusionRisk: string;
    lackOfFusionOverlapIndex: number;
    tangIndex_hW_tD?: number;
    hOverW?: number;
    tOverD?: number;
    keyholePorosityRisk: string;
    ballingInstabilityRisk: string;
    recoaterCrashRisk: string;
    effectiveResidualStress_MPa: number;
    distortionIndex: number;
  };
  solidificationKinetics: {
    modelId?: string;
    gradientSource?: string;
    usedFieldMap?: boolean;
    thermalGradient_G_K_m: number;
    thermalGradient_G_K_um: number;
    thermalGradientTail_G_K_m?: number;
    solidificationRate_R_m_s: number;
    solidificationRate_R_mm_s: number;
    solidificationCosTheta?: number;
    coolingRate_K_s: number;
    coolingRate_log10: number;
    g_over_r_ratio: number;
    microstructureMorphology: string;
    primaryDendriteArmSpacing_PDAS_um: number;
    secondaryDendriteArmSpacing_SDAS_um: number;
    phaseTransformation?: {
      alloyClass?: string;
      expected?: string;
      criterion?: string;
      source?: string | null;
      doi?: string | null;
    };
    frontPointCount?: number;
    tail?: { x_um: number; z_um: number; G_K_m: number; R_m_s: number };
    bottom?: { x_um: number; z_um: number; G_K_m: number; R_m_s: number };
    doi?: string;
    disclaimer?: string;
  };
  geometricContours: {
    topDownXY: { x_um: number; y_um: number }[];
    longitudinalXZ: { x_um: number; z_depth_um: number; isKeyhole: boolean }[];
    transverseYZ: { y_um: number; z_depth_um: number }[];
    multiTrackHatchOverlap: {
      trackId: string;
      y_center_um: number;
      contour: { y_um: number; z_depth_um: number }[];
    }[];
  };
  thermalSlices?: {
    liquidus_C: number;
    solidus_C: number;
    haz_C: number;
    xz: {
      nx: number;
      nz: number;
      xMin_um: number;
      xMax_um: number;
      zMin_um: number;
      zMax_um: number;
      T_C: number[];
    };
    yz: {
      ny: number;
      nz: number;
      yMin_um: number;
      yMax_um: number;
      zMin_um: number;
      zMax_um: number;
      T_C: number[];
    };
  };
  processWindowMap: {
    currentOperatingPoint: {
      power_W: number;
      speed_mm_s: number;
      regime: string;
      lofStatus: string;
    };
    grid: {
      power_W: number;
      speed_mm_s: number;
      normalizedEnthalpy: number;
      regime: string;
      color: string;
      width_um: number;
      depth_um: number;
    }[];
  };
}

export interface StochasticPropertyStats {
  mean: number;
  stdDev: number;
  covPct: number;
  skewness: number;
  kurtosis: number;
  min: number;
  max: number;
  median_P50: number;
  P10: number;
  P90: number;
  ci95Lower_P2_5: number;
  ci95Upper_P97_5: number;
  P01: number;
  P99: number;
  mmpds_kA: number;
  mmpds_kB: number;
  aBasisAllowable: number;
  bBasisAllowable: number;
  aBasisConfidenceInterval95?: [number, number] | null;
  bBasisConfidenceInterval95?: [number, number] | null;
  allowableStandardError_A?: number | null;
  allowableStandardError_B?: number | null;
  allowableUncertaintyMethod?: string;
  cpk: number | null;
  conformancePct: number;
  histogram: {
    binCenter: number;
    binStart: number;
    binEnd: number;
    count: number;
    empiricalPdf: number;
    fittedNormalPdf: number;
    cumulativePct: number;
  }[];
}

export interface PythonStochasticUQResult {
  success: boolean;
  engine: string;
  computeTimeMs: number;
  proxyRoundtripMs?: number;
  sampleSizeN: number;
  samplingMetadata?: {
    samplingMethod: "sobol_qmc";
    scrambled: boolean;
    sobolDimensions: number;
    qmcAccelerationFactor: number | null;
    effectiveSampleSize: number | null;
    centeredL2Discrepancy: number;
    pseudoDiscrepancyBenchmark: number;
    discrepancyReductionPct: number | null;
    varianceReductionRatio: number | null;
    theoreticalConvergenceRate: string;
    samplingDescription: string;
    discrepancySampleSize?: number;
    diagnosticsLimitations?: string;
  };
  alloyMetadata: {
    alloyName: string;
    baseMetal: string;
    standardSpec: string;
    specMinYield_MPa: number;
    specMinUTS_MPa: number;
    specMinElongation_pct: number;
  };
  inputUncertainties: {
    compositionTolerances: { [key: string]: number };
    coolingRate_nominal: number;
    coolingRate_cov: number;
    agingTemp_nominal: number;
    agingTemp_stdDev: number;
    agingTime_nominal: number;
    agingTime_stdDev: number;
    serviceStress_nominal: number;
    serviceStress_cov: number;
  };
  stochasticProperties: {
    yieldStrength_Rp02: StochasticPropertyStats;
    ultimateTensileStrength_UTS: StochasticPropertyStats;
    elongationPct: StochasticPropertyStats;
    fractureToughness_K1c: StochasticPropertyStats;
    criticalFlawSize_ac: StochasticPropertyStats;
  };
  sensitivityMetadata?: {
    method: string;
    output: string;
    baseSampleSize: number;
    evaluationCount: number;
    independentInputs: boolean;
    indicesNormalized: boolean;
    status: string;
    limitations: string;
  };
  /** Added by the solver script (python/stochastic_uq_mmpds_solver.py provenance()); only modelStatus is read. */
  provenance?: { modelStatus?: string };
  sobolSensitivityAnalysis: {
    parameter: string;
    description: string;
    sobolFirstOrderIndex: number | null;
    sobolTotalOrderIndex?: number | null;
    interactionIndex?: number | null;
    varianceContributionPct: number | null;
  }[];
  aerospaceReliability: {
    qualificationStatus: string;
    yieldFailureProbability_Pf: number;
    hasoferLindBetaIndex: number;
    aBasisConforming: boolean;
    bBasisConforming: boolean;
    cpkConforming: boolean;
    criticalFlawMedian_mm: number;
    criticalFlaw_P10_mm: number;
  };
}

export interface PythonICMEMultiScaleResult {
  /** "illustrative": closed-form estimates on tabulated constants (no DFT, CALPHAD or FEA run). */
  modelStatus?: string;
  modelStatusNote?: string;
  modelParts?: string[];
  success: boolean;
  engine: string;
  computeTimeMs: number;
  proxyRoundtripMs?: number;
  inputParameters: {
    alloyName: string;
    baseMetal: string;
    crystalSystem: string;
    coolingRate_C_s: number;
    grainSize_um: number;
    agingTemp_C: number;
    agingTime_h: number;
    componentType: string;
  };
  scale0_dftAtomistic: {
    latticeParameter_a0_Angstrom: number;
    burgersVector_b_nm: number;
    slipPlane_dhkl_nm: number;
    elasticTensor_Cij_GPa: {
      C11: number;
      C12: number;
      C44: number;
    };
    homogenizedModuli: {
      youngsModulus_E_GPa: number;
      shearModulus_G_GPa: number;
      bulkModulus_B_GPa: number;
      poissonsRatio: number;
      pughRatio_B_over_G: number;
      cauchyPressure_GPa: number;
      ductilityVerdict: string;
    };
    peierlsNabarroLatticeFriction: {
      tau_PN_MPa: number;
      taylorFactor_M: number;
      sigma_0_friction_stress_MPa: number;
    };
  };
  scale1_calphadSoluteMisfit: {
    atomicFractions: { [key: string]: number };
    soluteBreakdown: {
      [key: string]: {
        wt_pct?: number;
        at_frac: number;
        sizeMisfit: number;
        modulusMisfit: number;
        strengthContribution_MPa: number;
      };
    };
    totalSolidSolutionStrengthening_MPa: number;
  };
  scale2_microstructureKinetics: {
    coolingRate_C_s: number;
    computedSDAS_um: number;
    grainSize_d_um: number;
    hallPetchStrengthening_MPa: number;
    dislocationDensity_rho_m2: string;
    taylorDislocationStrengthening_MPa: number;
    precipitationKinetics: {
      agingTemp_C: number;
      agingTime_h: number;
      meanPrecipitateRadius_nm: number;
      volumeFractionPct: number;
      interparticleSpacing_nm: number;
      shearingStrength_MPa: number;
      orowanStrength_MPa: number;
      activeMechanism: string;
      effectivePrecipitationStrengthening_MPa: number;
    };
  };
  scale3_continuumPlasticity: {
    strengtheningContributions_MPa: {
      sigma_0_LatticeFriction: number;
      deltaSigma_SS_SolidSolution: number;
      deltaSigma_HP_GrainBoundary: number;
      deltaSigma_Disloc_Forest: number;
      deltaSigma_Precip_OrowanCutting: number;
    };
    mechanicalProperties: {
      yieldStrength_Rp02_MPa: number;
      /** null = unavailable (see ultimateTensileStrength_UTS_status); never the yield strength. */
      ultimateTensileStrength_UTS_MPa: number | null;
      ultimateTensileStrength_UTS_status?: string;
      uniformElongationPct: number;
      totalElongationPct: number;
      /** null = unavailable (see fractureToughness_K1c_status). */
      fractureToughness_K1c_MPa_sqrt_m: number | null;
      fractureToughness_K1c_status?: string;
      hollomon_n: number;
      hollomon_K_MPa: number;
    };
    johnsonCookParameters: {
      A_MPa: number;
      B_MPa: number;
      n: number;
      C: number;
      m: number;
      T_melt_C: number;
    };
    stressStrainCurve: {
      engineeringStrainPct: number;
      engineeringStressMPa: number;
      trueStrain: number;
      trueStressMPa: number;
    }[];
  };
  scale4_macroComponentFEA: {
    componentName: string;
    criticalSectionArea_mm2: number;
    appliedStress_MPa: number;
    requiredSafetyFactor: number;
    actualSafetyFactor: number;
    structuralVerdict: string;
    structuralVerdictBasis?: string;
    lefmDamageTolerance: {
      /** null = unavailable: needs a fracture toughness K_Ic the model does not provide. */
      criticalFlawSize_ac_mm: number | null;
      plasticZoneRadius_rp_mm: number | null;
      inspectionNDICapability: string;
      status?: string;
    };
  };
  caeExportCards: {
    abaqus: string;
    lsDyna: string;
    ansys: string;
  };
}

export const pythonComputationService = new PythonComputationService();

function unavailableTafelCorrosionRate(
  payload: TafelPythonCorrosionRateInput,
  alloyId: string,
  alloyName: string,
  eCorr_V: number | null,
  specimenAreaCm2: number,
  temperatureC: number,
  initialThicknessMm: number,
  allowableLossMm: number,
  unavailable: Record<string, string>
): TafelPythonCorrosionRateResult {
  return {
    success: true,
    status: "unavailable",
    unavailable,
    unavailableReason: "Corrosion rate unavailable: " + Object.values(unavailable).join("; ") + ".",
    isPythonEngine: false,
    pythonVersion: "3.10 (Client Dual-Engine)",
    standards: ["ASTM G102-89(2015)", "ASTM G59-97(2020)", "NACE SP0169"],
    durationMs: 0.5,
    timestamp: new Date().toISOString(),
    corrosionRateMmYr: null,
    corrosionRateMpy: null,
    corrosionRateUmYr: null,
    corrosionRateNmHr: null,
    massLoss_g_m2_day: null,
    massLoss_mdd: null,
    massLoss_kg_m2_yr: null,
    sternGearyB_V: null,
    rp_ohm_cm2: null,
    rp_apparent_ohm: null,
    alloyId,
    alloyName,
    density_g_cm3: payload.density_g_cm3 ?? 0,
    equivalentWeight: payload.equivalentWeight ?? 0,
    iCorr_uA_cm2: null,
    eCorr_V,
    betaA: typeof payload.betaA === "number" ? payload.betaA : null,
    betaC: typeof payload.betaC === "number" ? payload.betaC : null,
    specimenAreaCm2,
    temperatureC,
    initialThicknessMm,
    allowableLossMm,
    rulUniformYears: null,
    rulPittingYears: null,
    severity: null,
    timelineProjections: [],
    temperatureSensitivity: [],
    pythonCode: null,
  };
}

/**
 * Pure TypeScript fallback for ASTM G102 / G59 Annual Corrosion Rate solver
 * providing parity with python/tafel_corrosion_rate_solver.py
 */
export function fallbackClientTafelCorrosionRate(
  payload: TafelPythonCorrosionRateInput
): TafelPythonCorrosionRateResult {
  // Same rules as the Python engine: the corrosion current density is a required measurement, the slopes are
  // required only for Stern-Geary B and Rp, and the substrate (density, equivalent weight) must be supplied because
  // this client formula cannot resolve alloy presets. Nothing is defaulted: no 1.25 uA/cm2, no 0.12 / 0.10 V/dec
  // slopes, no 316L substrate.
  const positive = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) && v > 0 ? v : null);
  const iCorrIn = positive(payload.iCorr_uA_cm2);
  const betaAIn = positive(payload.betaA);
  const betaCIn = positive(payload.betaC);
  const densityIn = positive(payload.density_g_cm3);
  const ewIn = positive(payload.equivalentWeight);
  const eCorr_V = typeof payload.eCorr_V === "number" && Number.isFinite(payload.eCorr_V) ? payload.eCorr_V : null;
  const specimenArea = Math.max(1e-4, payload.specimenAreaCm2 || 1.0);
  const initialThickness = Math.max(0.1, payload.initialThicknessMm || 5.0);
  const allowableLoss = Math.max(0.01, payload.allowableLossMm || 1.5);
  const tempC = payload.temperatureC ?? 25.0;
  const alloyName = payload.alloyName || payload.alloyId || "Unspecified substrate";
  const alloyId = payload.alloyId || "";

  const unavailable: Record<string, string> = {};
  if (iCorrIn === null) {
    unavailable.iCorr_uA_cm2 =
      payload.iCorr_uA_cm2 === undefined || payload.iCorr_uA_cm2 === null
        ? "iCorr_uA_cm2 was not supplied"
        : `iCorr_uA_cm2 must be a finite number > 0 (received ${String(payload.iCorr_uA_cm2)})`;
  }
  if (densityIn === null || ewIn === null) {
    unavailable.substrate =
      "density_g_cm3 and equivalentWeight must be supplied: the client formula cannot resolve an alloy preset";
  }
  if (iCorrIn === null || densityIn === null || ewIn === null) {
    return unavailableTafelCorrosionRate(payload, alloyId, alloyName, eCorr_V, specimenArea, tempC, initialThickness, allowableLoss, unavailable);
  }

  const iCorr_uA_cm2 = Math.max(1e-9, iCorrIn);
  const density = Math.max(0.1, densityIn);
  const ew = Math.max(1.0, ewIn);
  const betaA = betaAIn === null ? null : Math.max(0.005, betaAIn);
  const betaC = betaCIn === null ? null : Math.max(0.005, betaCIn);
  if (betaA === null) unavailable.betaA = "betaA was not supplied";
  if (betaC === null) unavailable.betaC = "betaC was not supplied";

  // Stern-Geary kinetics (need both slopes)
  let sternGearyB: number | null = null;
  let rp_ohm_cm2: number | null = null;
  let rp_apparent_ohm: number | null = null;
  if (betaA !== null && betaC !== null) {
    sternGearyB = (betaA * betaC) / (Math.LN10 * (betaA + betaC));
    rp_ohm_cm2 = sternGearyB / (iCorr_uA_cm2 * 1e-6);
    rp_apparent_ohm = rp_ohm_cm2 / specimenArea;
  }

  // Faraday penetration (ASTM G102)
  // Same K1/K2 as python/tafel_corrosion_rate_solver.py, from the exact F.
  const exactK1 = (1e-6 * 31557600.0 * 10.0) / FARADAY_CONSTANT;
  const cr_mm_yr = (exactK1 * iCorr_uA_cm2 * ew) / density;
  const cr_mpy = cr_mm_yr * MILS_PER_MM;
  const cr_um_yr = cr_mm_yr * 1000.0;
  const cr_nm_hr = (cr_mm_yr * 1e6) / (365.25 * 24.0);

  const exactK2 = (1e-6 * 86400.0 * 1e4) / FARADAY_CONSTANT;
  const mass_loss_g_m2_day = exactK2 * iCorr_uA_cm2 * ew;
  const mass_loss_mdd = mass_loss_g_m2_day * 10.0;
  const mass_loss_kg_m2_yr = mass_loss_g_m2_day * 0.36525;

  // Timeline projections
  const years = [1, 2, 3, 5, 7, 10, 15, 20, 25];
  const pittingFactor = 3.5;
  const timelineProjections = years.map((yr) => {
    const lossUniform = cr_mm_yr * yr;
    const lossPitting = cr_mm_yr * yr * pittingFactor;
    return {
      year: yr,
      lossUniformMm: +lossUniform.toFixed(4),
      lossPittingMm: +lossPitting.toFixed(4),
      remainingWallMm: +Math.max(0, initialThickness - lossUniform).toFixed(3),
      remainingPittingMm: +Math.max(0, initialThickness - lossPitting).toFixed(3),
      wallLossPct: +Math.min(100, (lossUniform / initialThickness) * 100).toFixed(2),
      exceedsAllowance: lossUniform >= allowableLoss,
    };
  });

  const rulUniformYears = +(allowableLoss / cr_mm_yr).toFixed(2);
  const rulPittingYears = +(allowableLoss / (cr_mm_yr * pittingFactor)).toFixed(2);

  // Temperature sensitivity (Arrhenius)
  // No registry in the browser: without a caller-supplied activation energy the 32 kJ/mol stand-in of the old
  // fallback would be an invented number, so the Arrhenius table is left empty instead.
  const ea = payload.activationEnergyJ_mol || null;
  const rGas = GAS_CONSTANT_R;
  const tRefK = tempC + 273.15;
  const temperatureSensitivity = (ea === null ? [] : [5, 15, 25, 35, 45, 55, 65, 75, 85]).map((t) => {
    const tK = t + 273.15;
    const exp = (-(ea as number) / rGas) * (1 / tK - 1 / tRefK);
    const factor = Math.exp(Math.max(-10, Math.min(10, exp)));
    const iT = iCorr_uA_cm2 * factor;
    const crT = (exactK1 * iT * ew) / density;
    return {
      tempC: t,
      tempK: tK,
      arrheniusFactor: +factor.toFixed(3),
      iCorr_uA_cm2: +iT.toFixed(4),
      corrosionRateMmYr: +crT.toFixed(4),
      corrosionRateMpy: +(crT * MILS_PER_MM).toFixed(2),
    };
  });

  // Severity rating
  let severity: TafelPythonCorrosionRateResult["severity"];
  if (cr_mm_yr < 0.02) {
    severity = {
      level: "Outstanding",
      code: "OUTSTANDING",
      color: "emerald",
      description: "Negligible corrosion degradation. Suitable for long-life aerospace, biomedical, and precision critical parts without corrosion allowance.",
      recommendation: "Standard surface passivating inspection; corrosion allowance can be 0.00 mm.",
    };
  } else if (cr_mm_yr < 0.10) {
    severity = {
      level: "Excellent",
      code: "EXCELLENT",
      color: "sky",
      description: "Very low corrosion rate. Highly reliable for marine subsea hulls, offshore piping, and structural load-bearing airframes.",
      recommendation: "Periodic 5-year ultrasonic wall gauge inspection; minimal sacrificial allowance.",
    };
  } else if (cr_mm_yr < 0.50) {
    severity = {
      level: "Good",
      code: "GOOD",
      color: "amber",
      description: "Moderate corrosion rate. Standard structural steel in non-aggressive industrial atmospheres or mild water.",
      recommendation: "Apply protective epoxy/polyurethane coating or zinc galvanizing. Corrosion allowance 1.5 - 3.0 mm recommended.",
    };
  } else if (cr_mm_yr < 1.00) {
    severity = {
      level: "Fair",
      code: "FAIR",
      color: "orange",
      description: "Noticeable corrosion penetration. Significant wall thinning occurs within 2 to 5 years if unprotected.",
      recommendation: "Active cathodic protection (ICCP/sacrificial zinc) and chemical corrosion inhibitor injection mandated.",
    };
  } else {
    severity = {
      level: "Unacceptable / Critical",
      code: "UNACCEPTABLE",
      color: "rose",
      description: "Severe catastrophic dissolution. Wall breach and structural failure imminent without immediate mitigation.",
      recommendation: "Material change required (upgrade to Inconel/316L/Titanium) or continuous heavy-duty barrier protection.",
    };
  }

  const pythonCode = `# ASTM G102 & G59 Python Calculation
i_corr_uA_cm2 = ${iCorr_uA_cm2}
ew = ${ew}
density = ${density}
K1 = 0.00327072
cr_mm_yr = (K1 * i_corr_uA_cm2 * ew) / density
print(f"Annual Corrosion Rate: {cr_mm_yr:.5f} mm/year")
`;

  return {
    success: true,
    isPythonEngine: false,
    pythonVersion: "3.10 (Client Dual-Engine)",
    standards: ["ASTM G102-89(2015)", "ASTM G59-97(2020)", "NACE SP0169"],
    durationMs: 0.5,
    timestamp: new Date().toISOString(),
    corrosionRateMmYr: +cr_mm_yr.toFixed(5),
    corrosionRateMpy: +cr_mpy.toFixed(3),
    corrosionRateUmYr: +cr_um_yr.toFixed(2),
    corrosionRateNmHr: +cr_nm_hr.toFixed(3),
    massLoss_g_m2_day: +mass_loss_g_m2_day.toFixed(4),
    massLoss_mdd: +mass_loss_mdd.toFixed(3),
    massLoss_kg_m2_yr: +mass_loss_kg_m2_yr.toFixed(4),
    sternGearyB_V: sternGearyB === null ? null : +sternGearyB.toFixed(5),
    rp_ohm_cm2: rp_ohm_cm2 === null ? null : +rp_ohm_cm2.toFixed(1),
    rp_apparent_ohm: rp_apparent_ohm === null ? null : +rp_apparent_ohm.toFixed(2),
    alloyId,
    alloyName,
    density_g_cm3: density,
    equivalentWeight: ew,
    iCorr_uA_cm2,
    eCorr_V,
    betaA,
    betaC,
    ...(Object.keys(unavailable).length > 0
      ? {
          status: "partial" as const,
          unavailable,
          unavailableReason:
            "Stern-Geary B and polarization resistance unavailable: " + Object.values(unavailable).join("; ") + ".",
        }
      : {}),
    specimenAreaCm2: specimenArea,
    temperatureC: tempC,
    initialThicknessMm: initialThickness,
    allowableLossMm: allowableLoss,
    rulUniformYears,
    rulPittingYears,
    severity,
    timelineProjections,
    temperatureSensitivity,
    pythonCode,
  };
}

/**
 * Top-level function to calculate annual corrosion rate (mm/year) via Python CPython 3.10 Engine
 */
export async function calculatePythonTafelCorrosionRate(
  payload: TafelPythonCorrosionRateInput
): Promise<TafelPythonCorrosionRateResult> {
  return pythonComputationService.calculateTafelCorrosionRate(payload);
}
