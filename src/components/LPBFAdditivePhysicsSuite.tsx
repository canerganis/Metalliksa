import React, { useState, useMemo } from "react";
import {
  Zap,
  Flame,
  Activity,
  Layers,
  Thermometer,
  ShieldAlert,
  AlertTriangle,
  Info,
  TrendingDown,
  Wind,
  Settings2,
  Compass,
  Grid,
  RotateCw,
  Box,
  Droplets,
  Sparkles,
} from "lucide-react";
import { CandidateAlloySolution, InverseDesignTargets } from "../utils/inverseAlloyOptimizer";
import { LaserMeltPoolThermalMap } from "./LaserMeltPoolThermalMap";
import { useMaterialSpecimenStore, LpbfScanStrategy } from "../store/useMaterialSpecimenStore";

interface Props {
  candidate: CandidateAlloySolution;
  targets: InverseDesignTargets;
}

export interface LPBFProcessParameters {
  laserPower_W: number; // 100 - 600 W
  scanSpeed_mms: number; // 300 - 2500 mm/s
  hatchSpacing_um: number; // 50 - 180 um
  layerThickness_um: number; // 20 - 80 um
  beamDiameter_um: number; // 40 - 120 um
  preheatTemp_C: number; // 25 - 500 °C
  scanStrategy: "island_67" | "meander_90" | "stripe_unidirectional";
  atomizationGas: "Argon" | "Nitrogen" | "VIGA_Vacuum";
}

function scanStrategyToSuite(s: LpbfScanStrategy): LPBFProcessParameters["scanStrategy"] {
  if (s === "island") return "island_67";
  if (s === "stripe") return "stripe_unidirectional";
  return "meander_90";
}

function scanStrategyFromSuite(s: LPBFProcessParameters["scanStrategy"]): LpbfScanStrategy {
  if (s === "island_67") return "island";
  if (s === "stripe_unidirectional") return "stripe";
  return "meander-67";
}

export const LPBFAdditivePhysicsSuite: React.FC<Props> = ({ candidate, targets }) => {
  const [activeSubTab, setActiveSubTab] = useState<"thermal-map" | "process-window" | "scan-rheology">("thermal-map");
  const specimen = useMaterialSpecimenStore((s) => s.activeSpecimen);
  const lpbf = specimen.lpbf;
  const updateLpbfProcess = useMaterialSpecimenStore((s) => s.updateLpbfProcess);
  const [atomizationGas, setAtomizationGas] = useState<LPBFProcessParameters["atomizationGas"]>("Argon");

  const params: LPBFProcessParameters = {
    laserPower_W: lpbf.laserPower_W,
    scanSpeed_mms: lpbf.scanSpeed_mms,
    hatchSpacing_um: lpbf.hatch_um,
    layerThickness_um: lpbf.layer_um,
    beamDiameter_um: lpbf.beamDiameter_um,
    preheatTemp_C: lpbf.preheatTemp_C,
    scanStrategy: scanStrategyToSuite(lpbf.scanStrategy),
    atomizationGas,
  };

  const setParams = (
    updater: LPBFProcessParameters | ((prev: LPBFProcessParameters) => LPBFProcessParameters)
  ) => {
    const next = typeof updater === "function" ? updater(params) : updater;
    setAtomizationGas(next.atomizationGas);
    updateLpbfProcess({
      laserPower_W: next.laserPower_W,
      scanSpeed_mms: next.scanSpeed_mms,
      hatch_um: next.hatchSpacing_um,
      layer_um: next.layerThickness_um,
      beamDiameter_um: next.beamDiameter_um,
      preheatTemp_C: next.preheatTemp_C,
      scanStrategy: scanStrategyFromSuite(next.scanStrategy),
    });
  };

  // Element Vaporization Loss state
  const comp = candidate.compositionWt;

  // Material thermal constants based on alloy base matrix
  const thermalProps = useMemo(() => {
    const matrix = targets.baseMatrix;
    switch (matrix) {
      case "Aluminum":
        return {
          thermalConductivity: 150, // W/(m*K)
          specificHeat: 900, // J/(kg*K)
          absorptivity: 0.28,
          latentHeatFusion: 397000, // J/kg
          meltingPoint_C: candidate.liquidus_C || 660,
          boilingPoint_C: 2470,
        };
      case "Titanium":
        return {
          thermalConductivity: 18,
          specificHeat: 540,
          absorptivity: 0.42,
          latentHeatFusion: 290000,
          meltingPoint_C: candidate.liquidus_C || 1668,
          boilingPoint_C: 3287,
        };
      case "Nickel":
        return {
          thermalConductivity: 22,
          specificHeat: 450,
          absorptivity: 0.45,
          latentHeatFusion: 298000,
          meltingPoint_C: candidate.liquidus_C || 1455,
          boilingPoint_C: 2730,
        };
      case "Steel":
        return {
          thermalConductivity: 28,
          specificHeat: 490,
          absorptivity: 0.40,
          latentHeatFusion: 270000,
          meltingPoint_C: candidate.liquidus_C || 1500,
          boilingPoint_C: 2862,
        };
      case "Refractory":
        return {
          thermalConductivity: 65,
          specificHeat: 250,
          absorptivity: 0.52,
          latentHeatFusion: 340000,
          meltingPoint_C: candidate.liquidus_C || 2500,
          boilingPoint_C: 4800,
        };
      default:
        return {
          thermalConductivity: 24,
          specificHeat: 460,
          absorptivity: 0.44,
          latentHeatFusion: 290000,
          meltingPoint_C: candidate.liquidus_C || 1400,
          boilingPoint_C: 2800,
        };
    }
  }, [targets.baseMatrix, candidate.liquidus_C]);

  // Comprehensive Rosenthal & Eagar-Tsai Process Physics Calculations
  const lpbfPhysics = useMemo(() => {
    const {
      laserPower_W,
      scanSpeed_mms,
      hatchSpacing_um,
      layerThickness_um,
      beamDiameter_um,
      preheatTemp_C,
      scanStrategy,
      atomizationGas,
    } = params;

    const rho = candidate.density_gcm3 * 1000; // kg/m^3
    const k = thermalProps.thermalConductivity; // W/(m*K)
    const cp = thermalProps.specificHeat; // J/(kg*K)
    const eta = thermalProps.absorptivity; // optical absorptivity
    const Tm = thermalProps.meltingPoint_C;
    const T0 = preheatTemp_C;

    // Volumetric Energy Density (VED) in J/mm^3
    // VED = P / (v * h * t)
    const v_mm_s = scanSpeed_mms;
    const h_mm = hatchSpacing_um / 1000;
    const t_mm = layerThickness_um / 1000;
    const ved_J_mm3 = parseFloat((laserPower_W / (v_mm_s * h_mm * t_mm)).toFixed(1));

    // Linear Energy Density (LED) in J/mm
    const led_J_mm = parseFloat((laserPower_W / v_mm_s).toFixed(2));

    // Rosenthal Analytical Melt Pool Dimensions
    // Thermal diffusivity alpha = k / (rho * cp) in m^2/s
    const alpha = k / (rho * cp);
    const v_m_s = scanSpeed_mms / 1000;
    const effectivePower_W = laserPower_W * eta;

    // Rosenthal dimensionless peak temperature scale
    const deltaT_m = Tm - T0;
    
    // Normalized Enthalpy (King Criterion: h* = eta * P / (rho * cp * sqrt(pi * alpha * v * d_beam^3)))
    const d_beam_m = beamDiameter_um * 1e-6;
    const enthalpyNormalized =
      effectivePower_W /
      (rho * cp * deltaT_m * Math.sqrt(Math.PI * alpha * v_m_s * Math.pow(d_beam_m, 3)));

    // Melt pool width (w_um) and depth (d_um) via Eagar-Tsai / Rosenthal scaling
    const w_um = Math.round(
      beamDiameter_um * 1.25 * Math.pow(Math.max(0.5, enthalpyNormalized * 0.45), 0.45)
    );
    const d_um = Math.round(
      layerThickness_um * 1.6 * Math.pow(Math.max(0.4, enthalpyNormalized * 0.38), 0.6)
    );
    const length_um = Math.round(w_um * (1.8 + (v_m_s / 0.8) * 0.8));

    // Aspect ratio depth/width (Keyhole threshold is typically d/w > 0.75 - 0.85)
    const depthToWidthRatio = parseFloat((d_um / Math.max(1, w_um)).toFixed(2));

    // Process Window & Defect Regimes
    let processRegime: "Conduction Mode (Optimal)" | "Keyhole Porosity (Overheating)" | "Lack of Fusion (Pores)" | "Balling (Instability)";
    let processStatus: "Optimal" | "Warning" | "Critical";
    let processExplanation = "";

    // Lack of Fusion threshold: depth must sufficiently penetrate previous layer (d > 1.4 * t) & width > hatch
    const penetrationFactor = d_um / layerThickness_um;
    const overlapFactor = w_um / hatchSpacing_um;

    if (penetrationFactor < 1.3 || overlapFactor < 1.05) {
      processRegime = "Lack of Fusion (Pores)";
      processStatus = "Critical";
      processExplanation =
        "Insufficient laser energy; melt pool depth does not adequately penetrate the previous layer (d < 1.3t). High risk of un-melted powder voids between layers.";
    } else if (depthToWidthRatio > 0.82 || enthalpyNormalized > 3.8) {
      processRegime = "Keyhole Porosity (Overheating)";
      processStatus = "Critical";
      processExplanation =
        "Excessive energy density induces metallic vaporization and deep keyhole vapor cavity collapse. High risk of entrapped gas and spherical keyhole pores.";
    } else if (led_J_mm < 0.15 || v_mm_s > 2000) {
      processRegime = "Balling (Instability)";
      processStatus = "Warning";
      processExplanation =
        "High scan velocity promotes Plateau-Rayleigh capillary hydrodynamic instability, leading to discontinuous track balling.";
    } else {
      processRegime = "Conduction Mode (Optimal)";
      processStatus = "Optimal";
      processExplanation =
        "Optimal conduction melting regime (d/w = " +
        depthToWidthRatio +
        "). Layer penetration of " +
        Math.round(penetrationFactor * 100) +
        "% and hatch overlap of " +
        Math.round(overlapFactor * 100) +
        "% provide >99.8% relative density.";
    }

    // Solidification Microstructure Parameters (G & R)
    // Temperature gradient G (K/m) at the trailing edge of melt pool: G ~ 2 * deltaT_m / (w_um * 1e-6)
    const G_Km = Math.round((2.4 * deltaT_m) / (w_um * 1e-6)); // ~ 10^6 - 10^7 K/m
    // Solidification growth rate R (m/s) = v * cos(theta) ~ 0.4 * v
    const R_ms = parseFloat((v_m_s * 0.55).toFixed(3)); // ~ 0.2 - 1.2 m/s
    // Cooling Rate T_dot = G * R (K/s)
    const coolingRate_Ks = Math.round(G_Km * R_ms);
    // Secondary / Primary Dendrite Arm Spacing (PDAS lambda_1 in um ~ A * (coolingRate)^-1/3)
    const pdas_um = parseFloat((45 * Math.pow(coolingRate_Ks, -0.28)).toFixed(2));

    // Columnar to Equiaxed Transition (CET - Hunt Criterion)
    // G^3.5 / R ratio: Higher = Columnar anisotropic grains; Lower = Fine Equiaxed grains
    const cetIndex = parseFloat((Math.log10(Math.pow(G_Km / 1e6, 3.5) / Math.max(0.01, R_ms))).toFixed(2));
    const grainMorphology =
      cetIndex < 2.5
        ? "Fine Equiaxed (Isotropic Toughness)"
        : cetIndex < 4.8
        ? "Mixed Columnar + Equiaxed Microstructure"
        : "Directional Columnar Cellular (Epitaxial Anisotropy)";

    // Residual Thermal Stress & Distortion Estimation (Mercelis / Kruth Model)
    // Residual stress scales with thermal expansion alpha_th * E * deltaT, reduced by preheat and rotation
    const baseStress_MPa = Math.round(
      candidate.yieldStrength_25C_MPa * 0.85 * (1 - (T0 - 25) / (Tm * 0.6))
    );
    const strategyReduction =
      scanStrategy === "island_67" ? 0.65 : scanStrategy === "meander_90" ? 0.82 : 1.0;
    const estimatedResidualStress_MPa = Math.max(
      40,
      Math.round(baseStress_MPa * strategyReduction)
    );

    // Powder Rheology & Flowability (Gas Atomization physics)
    const gasFactor = atomizationGas === "Argon" ? 1.0 : atomizationGas === "Nitrogen" ? 1.08 : 0.92;
    const d50_um = Math.round(32 * gasFactor);
    const d10_um = Math.round(18 * gasFactor);
    const d90_um = Math.round(53 * gasFactor);
    const hausnerRatio = parseFloat((1.14 * (atomizationGas === "VIGA_Vacuum" ? 0.97 : 1.0)).toFixed(2));
    const carrIndex_pct = Math.round((1 - 1 / hausnerRatio) * 100);
    const hallFlow_s50g = parseFloat((22.4 * gasFactor).toFixed(1));

    // Volatile Element Vaporization Susceptibility (High Vapor Pressure Volatilization)
    const volatileElements: { elem: string; originalWt: number; vaporLossPct: number; afterWt: number }[] = [];
    
    // High vapor pressure elements: Zn, Mg, Mn, Al, Cr, Li
    const vaporCoeffs: Record<string, number> = {
      Zn: 0.45,
      Mg: 0.35,
      Mn: 0.18,
      Al: 0.08,
      Cr: 0.03,
      Ti: 0.01,
    };

    let totalVolLoss = 0;
    for (const [el, rawWt] of Object.entries(comp)) {
      const wt = Number(rawWt) || 0;
      if (wt > 0 && vaporCoeffs[el]) {
        // Vaporization scales with normalized enthalpy (excess superheat)
        const lossFactor = Math.min(0.5, vaporCoeffs[el] * Math.max(0.3, enthalpyNormalized * 0.35));
        const lostWt = parseFloat((wt * lossFactor).toFixed(2));
        const after = parseFloat((wt - lostWt).toFixed(2));
        totalVolLoss += lostWt;
        volatileElements.push({
          elem: el,
          originalWt: wt,
          vaporLossPct: parseFloat((lossFactor * 100).toFixed(1)),
          afterWt: after,
        });
      }
    }

    return {
      ved_J_mm3,
      led_J_mm,
      enthalpyNormalized: parseFloat(enthalpyNormalized.toFixed(2)),
      w_um,
      d_um,
      length_um,
      depthToWidthRatio,
      penetrationFactor: parseFloat(penetrationFactor.toFixed(2)),
      overlapFactor: parseFloat(overlapFactor.toFixed(2)),
      processRegime,
      processStatus,
      processExplanation,
      G_Km,
      R_ms,
      coolingRate_Ks,
      pdas_um,
      cetIndex,
      grainMorphology,
      estimatedResidualStress_MPa,
      d10_um,
      d50_um,
      d90_um,
      hausnerRatio,
      carrIndex_pct,
      hallFlow_s50g,
      volatileElements,
      totalVolLoss: parseFloat(totalVolLoss.toFixed(2)),
    };
  }, [params, candidate, targets.baseMatrix, thermalProps]);

  return (
    <div className="space-y-4">
      {/* HEADER: LPBF ADVANCED PROCESS SUITE */}
      <div className="p-4 rounded-xl bg-[#0b1322] border border-[#1d2a44] space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <Flame className="w-5 h-5 text-rose-400" />
              <h3 className="text-sm font-bold text-white font-mono">
                LPBF Additive Manufacturing Thermal Melt Pool &amp; Microstructure Physics Suite
              </h3>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Rosenthal 3D heat conduction, Eagar-Tsai melt pool geometry ($d/w$), solidification kinetics ($G \times R$), and element vaporization loss model.
            </p>
            <p className="text-[10px] text-sky-300/80 mt-1.5 font-mono">
              Build Job vector shared with Additive Lab — {specimen.name} · P {lpbf.laserPower_W} W · v {lpbf.scanSpeed_mms} mm/s · h {lpbf.hatch_um} µm · t {lpbf.layer_um} µm · d {lpbf.beamDiameter_um} µm · T₀ {lpbf.preheatTemp_C}°C. Industrial printability is the Python verdict in Additive Lab, not this screening suite.
            </p>
          </div>

          <div
            className="px-3 py-1.5 rounded-lg border font-mono text-xs font-bold flex items-center gap-1.5 self-start sm:self-auto bg-slate-500/15 text-slate-200 border-slate-500/40"
          >
            <AlertTriangle className="w-4 h-4 text-slate-400" />
            <span>Screening: {lpbfPhysics.processRegime}</span>
          </div>
        </div>

        {/* TOP KPI CARDS */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono">
          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <span className="text-[10px] text-slate-400 block">Volumetric Energy Density (VED):</span>
            <div className="text-base font-bold text-sky-400 mt-0.5">
              {lpbfPhysics.ved_J_mm3} <span className="text-xs font-normal text-slate-400">J/mm³</span>
            </div>
            <span className="text-[9px] text-slate-500">Linear: {lpbfPhysics.led_J_mm} J/mm</span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <span className="text-[10px] text-slate-400 block">Melt Pool Ratio (d/w):</span>
            <div className="text-base font-bold text-amber-400 mt-0.5">
              {lpbfPhysics.depthToWidthRatio}{" "}
              <span className="text-xs font-normal text-slate-400">
                ({lpbfPhysics.d_um}μm / {lpbfPhysics.w_um}μm)
              </span>
            </div>
            <span className="text-[9px] text-slate-500">Keyhole Threshold: &lt; 0.80</span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <span className="text-[10px] text-slate-400 block">Cooling Rate (T_dot = G·R):</span>
            <div className="text-base font-bold text-emerald-400 mt-0.5">
              {(lpbfPhysics.coolingRate_Ks / 1e6).toFixed(2)}×10⁶{" "}
              <span className="text-xs font-normal text-slate-400">K/s</span>
            </div>
            <span className="text-[9px] text-slate-500">Dendrite Spacing (λ₁): {lpbfPhysics.pdas_um} μm</span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032]">
            <span className="text-[10px] text-slate-400 block">Layer Penetration:</span>
            <div className="text-base font-bold text-purple-400 mt-0.5">
              {Math.round(lpbfPhysics.penetrationFactor * 100)}%{" "}
              <span className="text-xs font-normal text-slate-400">({lpbfPhysics.d_um}/{params.layerThickness_um}μm)</span>
            </div>
            <span className="text-[9px] text-slate-500">Hatch Overlap: {Math.round(lpbfPhysics.overlapFactor * 100)}%</span>
          </div>
        </div>

        {/* Process Regime Explanation */}
        <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032] text-xs font-mono text-slate-300 flex items-start gap-2">
          <Info className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
          <span>{lpbfPhysics.processExplanation}</span>
        </div>
      </div>

      {/* SUB-TAB NAVIGATOR WITHIN LPBF MODULE */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-xl bg-[#090e18] border border-[#162032] font-mono text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setActiveSubTab("thermal-map")}
            className={`px-3 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition ${
              activeSubTab === "thermal-map"
                ? "bg-rose-500/20 text-rose-300 border border-rose-500/50 shadow-sm shadow-rose-500/20"
                : "bg-[#0c1322] text-slate-400 border border-[#162032] hover:text-white"
            }`}
          >
            <Thermometer className="w-3.5 h-3.5" />
            Laser Melt Pool Thermal Map &amp; Solidification Front
          </button>

          <button
            onClick={() => setActiveSubTab("process-window")}
            className={`px-3 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition ${
              activeSubTab === "process-window"
                ? "bg-sky-500/20 text-sky-300 border border-sky-500/50 shadow-sm shadow-sky-500/20"
                : "bg-[#0c1322] text-slate-400 border border-[#162032] hover:text-white"
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            2D Process Window (P-v) &amp; Geometric Cross-Section
          </button>

          <button
            onClick={() => setActiveSubTab("scan-rheology")}
            className={`px-3 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition ${
              activeSubTab === "scan-rheology"
                ? "bg-purple-500/20 text-purple-300 border border-purple-500/50 shadow-sm shadow-purple-500/20"
                : "bg-[#0c1322] text-slate-400 border border-[#162032] hover:text-white"
            }`}
          >
            <Grid className="w-3.5 h-3.5" />
            Scan Strategy &amp; Powder Rheology
          </button>
        </div>

        <span className="text-[11px] text-slate-400 hidden sm:inline-block">
          Matrix: <strong className="text-white">{targets.baseMatrix}</strong> (k = {thermalProps.thermalConductivity} W/m·K)
        </span>
      </div>

      {/* SUB-TAB 1: LASER MELT POOL THERMAL MAP (COOLING RATES & SOLIDIFICATION FRONTS) */}
      {activeSubTab === "thermal-map" && (
        <LaserMeltPoolThermalMap
          candidate={candidate}
          targets={targets}
          laserPower_W={params.laserPower_W}
          scanSpeed_mms={params.scanSpeed_mms}
          beamDiameter_um={params.beamDiameter_um}
          preheatTemp_C={params.preheatTemp_C}
          layerThickness_um={params.layerThickness_um}
          hatchSpacing_um={params.hatchSpacing_um}
          onParametersChange={(newParams) => {
            setParams((prev) => ({
              ...prev,
              ...newParams,
            }));
          }}
        />
      )}

      {/* 2-COLUMN LAYOUT: PROCESS SLIDERS & ROSENTHAL MELT POOL VISUALIZER */}
      {activeSubTab === "process-window" && (
      <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* LEFT 5 COLS: INTERACTIVE PROCESS PARAMETERS */}
        <div className="lg:col-span-5 p-4 rounded-xl bg-[#0c1322] border border-[#1a263c] space-y-3.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white font-mono flex items-center gap-1.5">
              <Settings2 className="w-4 h-4 text-amber-400" />
              LPBF Machine Parameters
            </span>
            <span className="text-[10px] font-mono text-slate-400">
              Laser &amp; Scan Controls
            </span>
          </div>

          {/* Slider 1: Laser Power */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Laser Power (P)</span>
              <strong className="text-amber-400">{params.laserPower_W} W</strong>
            </div>
            <input aria-label="Laser Power (P)"
              type="range"
              min="100"
              max="500"
              step="10"
              value={params.laserPower_W}
              onChange={(e) =>
                setParams((p) => ({ ...p, laserPower_W: parseInt(e.target.value) }))
              }
              className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-amber-400"
            />
            <div className="flex justify-between text-[9px] text-slate-500 font-mono">
              <span>100 W</span>
              <span>500 W</span>
            </div>
          </div>

          {/* Slider 2: Scan Speed */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Scan Speed (v)</span>
              <strong className="text-sky-400">{params.scanSpeed_mms} mm/s</strong>
            </div>
            <input aria-label="Scan Speed (v)"
              type="range"
              min="400"
              max="2200"
              step="25"
              value={params.scanSpeed_mms}
              onChange={(e) =>
                setParams((p) => ({ ...p, scanSpeed_mms: parseInt(e.target.value) }))
              }
              className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-sky-400"
            />
            <div className="flex justify-between text-[9px] text-slate-500 font-mono">
              <span>400 mm/s</span>
              <span>2200 mm/s</span>
            </div>
          </div>

          {/* Slider 3: Hatch Spacing */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Hatch Spacing (h)</span>
              <strong className="text-emerald-400">{params.hatchSpacing_um} μm</strong>
            </div>
            <input aria-label="Hatch Spacing (h)"
              type="range"
              min="50"
              max="160"
              step="5"
              value={params.hatchSpacing_um}
              onChange={(e) =>
                setParams((p) => ({ ...p, hatchSpacing_um: parseInt(e.target.value) }))
              }
              className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-emerald-400"
            />
            <div className="flex justify-between text-[9px] text-slate-500 font-mono">
              <span>50 μm</span>
              <span>160 μm</span>
            </div>
          </div>

          {/* Slider 4: Layer Thickness */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Layer Thickness (t)</span>
              <strong className="text-purple-400">{params.layerThickness_um} μm</strong>
            </div>
            <input aria-label="Layer Thickness (t)"
              type="range"
              min="20"
              max="80"
              step="5"
              value={params.layerThickness_um}
              onChange={(e) =>
                setParams((p) => ({ ...p, layerThickness_um: parseInt(e.target.value) }))
              }
              className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-purple-400"
            />
            <div className="flex justify-between text-[9px] text-slate-500 font-mono">
              <span>20 μm</span>
              <span>80 μm</span>
            </div>
          </div>

          {/* Slider 4b: Beam Diameter */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Beam Diameter (d)</span>
              <strong className="text-cyan-400">{params.beamDiameter_um} μm</strong>
            </div>
            <input aria-label="Beam Diameter (d)"
              type="range"
              min="40"
              max="140"
              step="5"
              value={params.beamDiameter_um}
              onChange={(e) =>
                setParams((p) => ({ ...p, beamDiameter_um: parseInt(e.target.value) }))
              }
              className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-cyan-400"
            />
            <div className="flex justify-between text-[9px] text-slate-500 font-mono">
              <span>40 μm</span>
              <span>140 μm</span>
            </div>
          </div>

          {/* Slider 5: Preheat Temperature */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Build Plate Preheat (T₀)</span>
              <strong className="text-rose-400">{params.preheatTemp_C} °C</strong>
            </div>
            <input aria-label="Build Plate Preheat (T₀)"
              type="range"
              min="25"
              max="400"
              step="25"
              value={params.preheatTemp_C}
              onChange={(e) =>
                setParams((p) => ({ ...p, preheatTemp_C: parseInt(e.target.value) }))
              }
              className="w-full h-1.5 bg-[#162032] rounded-lg appearance-none cursor-pointer accent-rose-400"
            />
            <div className="flex justify-between text-[9px] text-slate-500 font-mono">
              <span>25 °C (Ambient)</span>
              <span>400 °C (Elevated)</span>
            </div>
          </div>
        </div>

        {/* RIGHT 7 COLS: ROSENTHAL 3D MELT POOL & THERMAL GRADIENT PROFILES */}
        <div className="lg:col-span-7 p-4 rounded-xl bg-[#0c1322] border border-[#1a263c] flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white font-mono flex items-center gap-1.5">
              <Compass className="w-4 h-4 text-sky-400" />
              Rosenthal Melt Pool Transverse Cross-Section Profile
            </span>
            <div className="text-[11px] font-mono text-slate-400">
              Width: <strong className="text-sky-300">{lpbfPhysics.w_um}μm</strong> | Depth:{" "}
              <strong className="text-amber-300">{lpbfPhysics.d_um}μm</strong>
            </div>
          </div>

          {/* 2D Cross Section SVG */}
          <div className="w-full bg-[#070c16] rounded-xl border border-[#162032] p-3 flex flex-col items-center justify-center relative overflow-hidden">
            <svg viewBox="0 0 420 180" className="w-full h-auto max-h-[190px]">
              {/* Powder Bed Baseline & Substrate */}
              <rect x="20" y="80" width="380" height="90" fill="#0f172a" stroke="#1e293b" />
              <text x="30" y="160" fill="#64748b" fontSize="9" fontFamily="monospace">
                Previous Layer / Substrate
              </text>

              {/* Powder Layer */}
              <rect
                x="20"
                y={80 - params.layerThickness_um * 0.7}
                width="380"
                height={params.layerThickness_um * 0.7}
                fill="#1e293b"
                fillOpacity="0.6"
                stroke="#334155"
                strokeDasharray="2 2"
              />
              <text
                x="30"
                y={75 - params.layerThickness_um * 0.7}
                fill="#94a3b8"
                fontSize="9"
                fontFamily="monospace"
              >
                Powder Layer (t = {params.layerThickness_um} μm)
              </text>

              {/* Laser Beam Spot */}
              <polygon points="200,10 220,10 214,70 206,70" fill="url(#laserGradient)" opacity="0.85" />
              <defs>
                <linearGradient id="laserGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#fbbf24" stopOpacity="0.4" />
                </linearGradient>
                <radialGradient id="meltGradient" cx="50%" cy="30%" r="60%">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.95" />
                  <stop offset="45%" stopColor="#ea580c" stopOpacity="0.75" />
                  <stop offset="85%" stopColor="#0284c7" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#0f172a" stopOpacity="0.0" />
                </radialGradient>
              </defs>

              {/* Melt Pool Ellipse / Paraboloid */}
              {(() => {
                const cx = 210;
                const cy = 80;
                const rx = Math.min(160, Math.max(30, (lpbfPhysics.w_um / 2) * 0.9));
                const ry = Math.min(80, Math.max(20, lpbfPhysics.d_um * 0.85));

                // Path for semi-ellipse dipping into substrate
                return (
                  <g>
                    {/* Heat Affected Zone (HAZ) */}
                    <ellipse
                      cx={cx}
                      cy={cy + ry * 0.2}
                      rx={rx * 1.3}
                      ry={ry * 1.25}
                      fill="none"
                      stroke="#0284c7"
                      strokeWidth="1.5"
                      strokeDasharray="4 2"
                      opacity="0.6"
                    />

                    {/* Liquid Melt Pool Boundary */}
                    <ellipse
                      cx={cx}
                      cy={cy + ry * 0.15}
                      rx={rx}
                      ry={ry}
                      fill="url(#meltGradient)"
                      stroke="#f59e0b"
                      strokeWidth="2"
                    />

                    {/* Width dimension line */}
                    <line
                      x1={cx - rx}
                      y1={cy - 12}
                      x2={cx + rx}
                      y2={cy - 12}
                      stroke="#38bdf8"
                      strokeWidth="1"
                    />
                    <text
                      x={cx}
                      y={cy - 16}
                      fill="#38bdf8"
                      fontSize="9"
                      fontFamily="monospace"
                      textAnchor="middle"
                    >
                      w = {lpbfPhysics.w_um} μm
                    </text>

                    {/* Depth dimension line */}
                    <line
                      x1={cx + rx + 15}
                      y1={cy}
                      x2={cx + rx + 15}
                      y2={cy + ry}
                      stroke="#fbbf24"
                      strokeWidth="1"
                    />
                    <text
                      x={cx + rx + 22}
                      y={cy + ry / 2 + 3}
                      fill="#fbbf24"
                      fontSize="9"
                      fontFamily="monospace"
                    >
                      d = {lpbfPhysics.d_um} μm
                    </text>
                  </g>
                );
              })()}
            </svg>
          </div>

          {/* Microstructure & Solidification Physics Callout */}
          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="p-2 rounded-lg bg-[#070c16] border border-[#162032]">
              <span className="text-[10px] text-slate-400 block">Thermal Gradient (G):</span>
              <strong className="text-sky-300 text-sm block mt-0.5">
                {(lpbfPhysics.G_Km / 1e6).toFixed(2)} × 10⁶ K/m
              </strong>
              <span className="text-[9px] text-slate-500">Melt boundary thermal slope</span>
            </div>

            <div className="p-2 rounded-lg bg-[#070c16] border border-[#162032]">
              <span className="text-[10px] text-slate-400 block">Solidification Velocity (R):</span>
              <strong className="text-emerald-300 text-sm block mt-0.5">
                {lpbfPhysics.R_ms} m/s
              </strong>
              <span className="text-[9px] text-slate-500">Dendrite growth rate</span>
            </div>
          </div>
        </div>
      </div>
      </div>
      )}

      {/* SUB-TAB 3: SCAN STRATEGY & THERMAL STRESS / POWDER RHEOLOGY */}
      {activeSubTab === "scan-rheology" && (
        <div className="space-y-4">
      {/* SECTION 3: 2D P-v PROCESS WINDOW CONTOUR MAP & SCAN STRATEGY SIMULATOR */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* LEFT 7 COLS: 2D LASER POWER VS SCAN SPEED (P-v) PROCESS WINDOW MAP */}
        <div className="lg:col-span-7 p-4 rounded-xl bg-[#0c1322] border border-[#1a263c] space-y-3 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-amber-400" />
              2D Laser Process Window Map (P vs. v Map)
            </span>
            <span className="text-[10px] text-slate-400">
              Click map to dynamically adjust operating point
            </span>
          </div>

          {/* Interactive SVG P-v Contour Map */}
          <div className="w-full bg-[#070c16] rounded-xl border border-[#162032] p-2 relative overflow-hidden flex flex-col items-center">
            <svg
              viewBox="0 0 440 220"
              className="w-full h-auto cursor-crosshair select-none"
              onClick={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                const clickX = e.clientX - rect.left;
                const clickY = e.clientY - rect.top;
                const svgX = (clickX / rect.width) * 440;
                const svgY = (clickY / rect.height) * 220;

                // Map svg coordinates back to scanSpeed (400 - 2200) and power (100 - 500)
                // X: 50 -> 400px maps to 400 -> 2200 mm/s
                // Y: 180 -> 20px maps to 100 -> 500 W
                const newV = Math.round(
                  400 + Math.max(0, Math.min(1, (svgX - 50) / 350)) * 1800
                );
                const newP = Math.round(
                  100 + Math.max(0, Math.min(1, (180 - svgY) / 160)) * 400
                );
                setParams((prev) => ({
                  ...prev,
                  scanSpeed_mms: newV,
                  laserPower_W: newP,
                }));
              }}
            >
              {/* Grid Lines */}
              <line x1="50" y1="20" x2="400" y2="20" stroke="#1e293b" strokeDasharray="2 2" />
              <line x1="50" y1="60" x2="400" y2="60" stroke="#1e293b" strokeDasharray="2 2" />
              <line x1="50" y1="100" x2="400" y2="100" stroke="#1e293b" strokeDasharray="2 2" />
              <line x1="50" y1="140" x2="400" y2="140" stroke="#1e293b" strokeDasharray="2 2" />
              <line x1="50" y1="180" x2="400" y2="180" stroke="#334155" strokeWidth="1.5" />
              <line x1="50" y1="20" x2="50" y2="180" stroke="#334155" strokeWidth="1.5" />

              {/* Axis Labels */}
              <text x="220" y="205" fill="#94a3b8" fontSize="10" textAnchor="middle">
                Scan Speed v (mm/s)
              </text>
              <text
                x="15"
                y="100"
                fill="#94a3b8"
                fontSize="10"
                transform="rotate(-90 15,100)"
                textAnchor="middle"
              >
                Laser Power P (W)
              </text>

              {/* X Tick Labels */}
              <text x="50" y="195" fill="#64748b" fontSize="8" textAnchor="middle">400</text>
              <text x="137" y="195" fill="#64748b" fontSize="8" textAnchor="middle">850</text>
              <text x="225" y="195" fill="#64748b" fontSize="8" textAnchor="middle">1300</text>
              <text x="312" y="195" fill="#64748b" fontSize="8" textAnchor="middle">1750</text>
              <text x="400" y="195" fill="#64748b" fontSize="8" textAnchor="middle">2200</text>

              {/* Y Tick Labels */}
              <text x="42" y="183" fill="#64748b" fontSize="8" textAnchor="end">100</text>
              <text x="42" y="143" fill="#64748b" fontSize="8" textAnchor="end">200</text>
              <text x="42" y="103" fill="#64748b" fontSize="8" textAnchor="end">300</text>
              <text x="42" y="63" fill="#64748b" fontSize="8" textAnchor="end">400</text>
              <text x="42" y="23" fill="#64748b" fontSize="8" textAnchor="end">500</text>

              {/* Zone 1: Keyhole Porosity Region (Top-Left high energy) */}
              <polygon
                points="50,20 220,20 50,110"
                fill="#e11d48"
                fillOpacity="0.25"
                stroke="#f43f5e"
                strokeWidth="1"
                strokeDasharray="3 2"
              />
              <text x="95" y="55" fill="#fb7185" fontSize="9" fontWeight="bold">
                Keyhole Regime (Overheating / Cavity Collapse)
              </text>

              {/* Zone 2: Lack of Fusion Region (Bottom-Right low energy) */}
              <polygon
                points="170,180 400,180 400,80 270,130"
                fill="#6366f1"
                fillOpacity="0.22"
                stroke="#818cf8"
                strokeWidth="1"
                strokeDasharray="3 2"
              />
              <text x="320" y="155" fill="#a5b4fc" fontSize="9" fontWeight="bold" textAnchor="middle">
                Lack of Fusion (Insufficient Melting)
              </text>

              {/* Zone 3: Balling Region (Far Right High Speed) */}
              <polygon
                points="360,20 400,20 400,80 360,70"
                fill="#f59e0b"
                fillOpacity="0.2"
                stroke="#fbbf24"
                strokeWidth="1"
              />
              <text x="380" y="45" fill="#fcd34d" fontSize="8" textAnchor="middle">
                Balling
              </text>

              {/* Zone 4: Optimal Conduction Mode (Center) */}
              <path
                d="M 50,110 Q 180,95 270,130 L 400,80 L 360,20 L 220,20 Z"
                fill="#10b981"
                fillOpacity="0.18"
                stroke="#34d399"
                strokeWidth="1.5"
              />
              <text x="180" y="105" fill="#6ee7b7" fontSize="10" fontWeight="bold">
                ✓ Stable Conduction Mode (Defect-Free Window)
              </text>

              {/* Dynamic Current Operating Point */}
              {(() => {
                const ptX = 50 + ((params.scanSpeed_mms - 400) / 1800) * 350;
                const ptY = 180 - ((params.laserPower_W - 100) / 400) * 160;
                const color =
                  lpbfPhysics.processStatus === "Optimal"
                    ? "#34d399"
                    : lpbfPhysics.processStatus === "Warning"
                    ? "#fbbf24"
                    : "#f43f5e";

                return (
                  <g>
                    {/* Ripple ring */}
                    <circle cx={ptX} cy={ptY} r="10" fill={color} fillOpacity="0.25" className="animate-ping" />
                    {/* Center point */}
                    <circle cx={ptX} cy={ptY} r="5" fill={color} stroke="#ffffff" strokeWidth="1.5" />
                    {/* Tooltip callout */}
                    <rect
                      x={Math.min(320, Math.max(60, ptX - 50))}
                      y={ptY - 24}
                      width="100"
                      height="16"
                      rx="4"
                      fill="#0f172a"
                      stroke={color}
                      strokeWidth="1"
                    />
                    <text
                      x={Math.min(320, Math.max(60, ptX - 50)) + 50}
                      y={ptY - 13}
                      fill="#ffffff"
                      fontSize="8"
                      fontFamily="monospace"
                      textAnchor="middle"
                      fontWeight="bold"
                    >
                      P={params.laserPower_W}W, v={params.scanSpeed_mms}mm/s
                    </text>
                  </g>
                );
              })()}
            </svg>
          </div>
        </div>

        {/* RIGHT 5 COLS: SCAN STRATEGY & THERMAL STRESS RELIEVER */}
        <div className="lg:col-span-5 p-4 rounded-xl bg-[#0c1322] border border-[#1a263c] space-y-3 font-mono flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white flex items-center gap-1.5">
                <Grid className="w-4 h-4 text-purple-400" />
                Scan Strategy &amp; Residual Stress
              </span>
              <span className="text-[10px] text-slate-400">Thermal Stress Mitigation</span>
            </div>

            {/* Scan Strategy Selector Tabs */}
            <div className="grid grid-cols-3 gap-1.5 mt-2.5">
              {[
                { id: "island_67", label: "Island / Chessboard 67°", desc: "Lowest Stress" },
                { id: "meander_90", label: "Meander 90°", desc: "Balanced Speed" },
                { id: "stripe_unidirectional", label: "Stripe 0°", desc: "High Anisotropy" },
              ].map((st) => (
                <button
                  key={st.id}
                  onClick={() =>
                    setParams((p) => ({
                      ...p,
                      scanStrategy: st.id as any,
                    }))
                  }
                  className={`p-2 rounded-lg text-left transition border ${
                    params.scanStrategy === st.id
                      ? "bg-purple-500/20 text-purple-200 border-purple-500/50 shadow-sm"
                      : "bg-[#070c16] text-slate-400 border-[#162032] hover:text-white"
                  }`}
                >
                  <div className="text-[11px] font-bold">{st.label}</div>
                  <div className="text-[9px] text-slate-500">{st.desc}</div>
                </button>
              ))}
            </div>

            {/* Scan Track Animated Vector Preview */}
            <div className="mt-3 p-3 rounded-lg bg-[#070c16] border border-[#162032] flex items-center justify-around">
              <div className="w-20 h-20 bg-[#0f172a] rounded border border-purple-500/30 relative overflow-hidden flex items-center justify-center">
                {params.scanStrategy === "island_67" && (
                  <div className="grid grid-cols-2 grid-rows-2 w-full h-full gap-0.5 p-1">
                    <div className="bg-purple-500/30 rounded-sm flex flex-col justify-around p-0.5">
                      <div className="h-0.5 bg-amber-400 rounded w-full" />
                      <div className="h-0.5 bg-amber-400 rounded w-full" />
                    </div>
                    <div className="bg-purple-500/30 rounded-sm flex justify-around p-0.5">
                      <div className="w-0.5 bg-sky-400 rounded h-full" />
                      <div className="w-0.5 bg-sky-400 rounded h-full" />
                    </div>
                    <div className="bg-purple-500/30 rounded-sm flex justify-around p-0.5">
                      <div className="w-0.5 bg-sky-400 rounded h-full" />
                      <div className="w-0.5 bg-sky-400 rounded h-full" />
                    </div>
                    <div className="bg-purple-500/30 rounded-sm flex flex-col justify-around p-0.5">
                      <div className="h-0.5 bg-amber-400 rounded w-full" />
                      <div className="h-0.5 bg-amber-400 rounded w-full" />
                    </div>
                  </div>
                )}
                {params.scanStrategy === "meander_90" && (
                  <div className="flex flex-col justify-around w-full h-full p-2">
                    <div className="h-1 bg-amber-400 rounded w-full" />
                    <div className="h-1 bg-amber-400 rounded w-full" />
                    <div className="h-1 bg-amber-400 rounded w-full" />
                    <div className="h-1 bg-amber-400 rounded w-full" />
                  </div>
                )}
                {params.scanStrategy === "stripe_unidirectional" && (
                  <div className="flex flex-col justify-around w-full h-full p-2">
                    <div className="h-1 bg-rose-400 rounded w-full" />
                    <div className="h-1 bg-rose-400 rounded w-full" />
                    <div className="h-1 bg-rose-400 rounded w-full" />
                  </div>
                )}
              </div>

              <div className="space-y-1.5 text-xs">
                <span className="text-[10px] text-slate-400 block">Estimated Residual Stress:</span>
                <div className="text-base font-bold text-rose-300">
                  {lpbfPhysics.estimatedResidualStress_MPa}{" "}
                  <span className="text-xs text-slate-400 font-normal">MPa</span>
                </div>
                <div className="text-[10px] text-slate-400">
                  {params.scanStrategy === "island_67"
                    ? "✓ 67° rotation symmetrically distributes thermal gradient; reduces distortion by ~35%."
                    : params.scanStrategy === "meander_90"
                    ? "Standard scan; directional residual stress is moderate."
                    : "⚠️ High anisotropy and pronounced directional tensile stress risk."}
                </div>
              </div>
            </div>
          </div>

          <div className="p-2 rounded-lg bg-[#070c16] border border-[#162032] text-[10px] text-slate-400 flex items-center justify-between">
            <span>Build Plate Preheat Benefit:</span>
            <strong className="text-emerald-400 font-mono">
              -{Math.round(((params.preheatTemp_C - 25) / 400) * 45)}% Stress Reduction
            </strong>
          </div>
        </div>
      </div>

      {/* SECTION 4: GRAIN MORPHOLOGY (CET), ELEMENT VAPORIZATION & POWDER RHEOLOGY */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Grain Morphology / Columnar-to-Equiaxed Transition (CET) */}
        <div className="p-4 rounded-xl bg-[#0c1322] border border-[#1a263c] space-y-3 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-purple-400" />
              Grain Morphology (Hunt CET Criterion)
            </span>
            <span className="text-[10px] text-purple-300 px-2 py-0.5 rounded bg-purple-500/20 border border-purple-500/30 font-bold">
              G^3.5 / R = {lpbfPhysics.cetIndex}
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032] space-y-1.5">
            <div className="text-xs text-white font-bold">{lpbfPhysics.grainMorphology}</div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              At ultra-high cooling rates (10⁶ K/s), secondary dendrite arm spacing refines to{" "}
              <strong className="text-emerald-400">{lpbfPhysics.pdas_um} μm</strong>,
              providing superior strength and toughness via Hall-Petch grain boundary strengthening.
            </p>
          </div>
        </div>

        {/* Volatile Element Vaporization Loss (Langmuir Flux) */}
        <div className="p-4 rounded-xl bg-[#0c1322] border border-[#1a263c] space-y-3 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center gap-1.5">
              <Wind className="w-4 h-4 text-amber-400" />
              Laser Vaporization Loss (Langmuir Flux)
            </span>
            <span className="text-[10px] text-slate-400">
              Total: <strong className="text-amber-300">{lpbfPhysics.totalVolLoss}%</strong>
            </span>
          </div>

          {lpbfPhysics.volatileElements.length > 0 ? (
            <div className="space-y-1.5">
              {lpbfPhysics.volatileElements.map((v) => (
                <div
                  key={v.elem}
                  className="p-2 rounded-lg bg-[#070c16] border border-[#162032] flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded bg-sky-500/20 text-sky-300 flex items-center justify-center font-bold text-[10px]">
                      {v.elem}
                    </span>
                    <span className="text-slate-300">
                      {v.originalWt}% → <strong className="text-white">{v.afterWt}%</strong>
                    </span>
                  </div>
                  <span className="text-[11px] text-rose-400 font-bold">
                    -{v.vaporLossPct}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-2.5 rounded-lg bg-[#070c16] border border-[#162032] text-xs text-slate-400">
              No high vapor pressure volatile elements detected in this alloy. Compositional stability is preserved.
            </div>
          )}
        </div>

        {/* Powder Atomization Rheology & Hall Flowability */}
        <div className="p-4 rounded-xl bg-[#0c1322] border border-[#1a263c] space-y-3 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center gap-1.5">
              <Droplets className="w-4 h-4 text-sky-400" />
              Powder Rheology &amp; Flowability
            </span>
            {/* Gas Atomization selector */}
            <select aria-label="Gas atomization selector"
              value={params.atomizationGas}
              onChange={(e) =>
                setParams((p) => ({
                  ...p,
                  atomizationGas: e.target.value as any,
                }))
              }
              className="px-2 py-0.5 text-[10px] rounded bg-[#070c16] border border-[#162032] text-sky-300"
            >
              <option value="Argon">Gas Atomization (Ar)</option>
              <option value="Nitrogen">Gas Atomization (N₂)</option>
              <option value="VIGA_Vacuum">VIGA Vacuum Induction</option>
            </select>
          </div>

          <div className="space-y-1.5 text-xs">
            <div className="p-2 rounded-lg bg-[#070c16] border border-[#162032] flex justify-between items-center">
              <span className="text-slate-400">Particle Size Distribution (PSD):</span>
              <span className="text-sky-300 font-bold">
                D10: {lpbfPhysics.d10_um} | D50: {lpbfPhysics.d50_um} | D90: {lpbfPhysics.d90_um} μm
              </span>
            </div>
            <div className="p-2 rounded-lg bg-[#070c16] border border-[#162032] flex justify-between items-center">
              <span className="text-slate-400">Hausner Ratio / Carr Index:</span>
              <span className="text-emerald-300 font-bold">
                {lpbfPhysics.hausnerRatio} (Excellent Flow) / {lpbfPhysics.carrIndex_pct}%
              </span>
            </div>
            <div className="p-2 rounded-lg bg-[#070c16] border border-[#162032] flex justify-between items-center">
              <span className="text-slate-400">Hall Flowmeter Rate:</span>
              <span className="text-amber-300 font-bold">{lpbfPhysics.hallFlow_s50g} s/50g</span>
            </div>
          </div>
        </div>
      </div>
        </div>
      )}
    </div>
  );
};

