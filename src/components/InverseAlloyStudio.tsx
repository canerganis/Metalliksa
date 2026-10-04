import React, { useState, useMemo, useEffect } from "react";
import {
  Sparkles,
  FlaskConical,
  Atom,
  CheckCircle2,
  AlertCircle,
  Info,
  DollarSign,
  Layers,
  Thermometer,
  ShieldAlert,
  ShieldCheck,
  Zap,
  Cpu,
  Compass,
  FileCode2,
  Copy,
  Check,
  Download,
  Flame,
  Droplets,
  RotateCcw,
  Sliders,
  ChevronRight,
  TrendingUp,
  Award,
  Activity,
} from "lucide-react";
import {
  InverseDesignTargets,
  CandidateAlloySolution,
  solveInverseAlloyCandidates,
  generatePythonJupyterScript,
  calculateThermodynamicProfile,
} from "../utils/inverseAlloyOptimizer";
import { LME_PRICE_DATABASE } from "../data/lmePrices";
import { PERIODIC_ELEMENTS, evaluateHumeRothery } from "../data/elements";
import { AshbyPropertyMap } from "./AshbyPropertyMap";
import { PhysicalMetallurgyDossier } from "./PhysicalMetallurgyDossier";
import { MicroAlloySandbox } from "./MicroAlloySandbox";
import { LPBFAdditivePhysicsSuite } from "./LPBFAdditivePhysicsSuite";
import { HeatTreatmentAgingSimulator } from "./HeatTreatmentAgingSimulator";
import { SendToModuleButton } from "./SendToModuleButton";
import { createPipelinePayloadFromCandidate, setActivePipelineMaterial } from "../utils/materialDataPipeline";
import { useMaterialSpecimenStore, BaseMetalType } from "../store/useMaterialSpecimenStore";
import { Gauge } from "lucide-react";

interface InverseAlloyStudioProps {
  onNavigate?: (tabId: string) => void;
}

function inverseMatrixToBaseMetal(matrix: InverseDesignTargets["baseMatrix"]): BaseMetalType | undefined {
  if (matrix === "Nickel") return "Ni";
  if (matrix === "Titanium") return "Ti";
  if (matrix === "Steel") return "Fe";
  if (matrix === "Aluminum") return "Al";
  if (matrix === "Refractory") return "Refractory";
  return undefined;
}

function pushCandidateToBuildJob(cand: CandidateAlloySolution, targets: InverseDesignTargets) {
  useMaterialSpecimenStore.getState().updateComposition(
    cand.compositionWt,
    cand.name,
    inverseMatrixToBaseMetal(targets.baseMatrix),
    `Alloy Designer: ${cand.archetype}`
  );
}

export const InverseAlloyStudio: React.FC<InverseAlloyStudioProps> = ({ onNavigate }) => {
  // Navigation sub-tabs within the Studio
  const [activeTab, setActiveTab] = useState<
    "pareto-designer" | "micro-alloy-sandbox" | "lpbf-physics" | "heat-treatment" | "ashby-map" | "lme-economics" | "hume-rothery" | "jupyter-export"
  >("pareto-designer");

  // Multi-Objective Target Constraints
  const [targets, setTargets] = useState<InverseDesignTargets>({
    applicationName: "High-Pressure Turbine Rotor Operating at 850°C in Marine Atmosphere",
    baseMatrix: "Nickel",
    targetYieldStrength_25C: 1150,
    targetYieldStrength_Elevated: 780,
    serviceTemperature_C: 850,
    minElongation_pct: 15,
    minFractureToughness_K1c: 80,
    minPREN: 35,
    maxDensity_gcm3: 8.3,
    maxCostUSD_kg: 40.0,
    manufacturingRoute: "LPBF 3D Printing",
    elementExclusions: {
      noCobalt: false,
      noRhenium: true,
      noTantalum: false,
      lowCarbon: false,
    },
  });

  // Selected Candidate ID
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>("candidate-1-champion");
  const [copiedScript, setCopiedScript] = useState<boolean>(false);

  // Preset Engineering Scenarios
  const PRESET_SCENARIOS: { label: string; config: InverseDesignTargets }[] = [
    {
      label: "Turbine Rotor (850°C Marine)",
      config: {
        applicationName: "High-Pressure Turbine Rotor Operating at 850°C in Marine Atmosphere",
        baseMatrix: "Nickel",
        targetYieldStrength_25C: 1150,
        targetYieldStrength_Elevated: 780,
        serviceTemperature_C: 850,
        minElongation_pct: 15,
        minFractureToughness_K1c: 80,
        minPREN: 35,
        maxDensity_gcm3: 8.3,
        maxCostUSD_kg: 40.0,
        manufacturingRoute: "LPBF 3D Printing",
        elementExclusions: { noCobalt: false, noRhenium: true, noTantalum: false, lowCarbon: false },
      },
    },
    {
      label: "Deep-Sea Hull (300 bar Submersible)",
      config: {
        applicationName: "Deep-Sea 300-bar Submersible Pressure Hull & Ballast Valves",
        baseMatrix: "Steel",
        targetYieldStrength_25C: 1350,
        targetYieldStrength_Elevated: 400,
        serviceTemperature_C: 50,
        minElongation_pct: 20,
        minFractureToughness_K1c: 110,
        minPREN: 52,
        maxDensity_gcm3: 7.9,
        maxCostUSD_kg: 25.0,
        manufacturingRoute: "VIM/VAR Forging",
        elementExclusions: { noCobalt: true, noRhenium: true, noTantalum: true, lowCarbon: true },
      },
    },
    {
      label: "Hypersonic Mach 5+ Leading Edge",
      config: {
        applicationName: "Hypersonic Glide Vehicle Aerodynamic Stagnation Leading Edge",
        baseMatrix: "Refractory",
        targetYieldStrength_25C: 950,
        targetYieldStrength_Elevated: 620,
        serviceTemperature_C: 1450,
        minElongation_pct: 12,
        minFractureToughness_K1c: 65,
        minPREN: 20,
        maxDensity_gcm3: 14.5,
        maxCostUSD_kg: 180.0,
        manufacturingRoute: "Powder Metallurgy",
        elementExclusions: { noCobalt: false, noRhenium: false, noTantalum: false, lowCarbon: true },
      },
    },
    {
      label: "Bio-Medical Orthopedic Implant",
      config: {
        applicationName: "LPBF 3D Printed Low-Modulus Orthopedic Bone Scaffold",
        baseMatrix: "Titanium",
        targetYieldStrength_25C: 880,
        targetYieldStrength_Elevated: 200,
        serviceTemperature_C: 37,
        minElongation_pct: 18,
        minFractureToughness_K1c: 75,
        minPREN: 0,
        maxDensity_gcm3: 4.5,
        maxCostUSD_kg: 35.0,
        manufacturingRoute: "LPBF 3D Printing",
        elementExclusions: { noCobalt: true, noRhenium: true, noTantalum: false, lowCarbon: true },
      },
    },
    {
      label: "Lightweight EV Inverter Housing",
      config: {
        applicationName: "Lightweight High-Conductivity EV Power Inverter Enclosure",
        baseMatrix: "Aluminum",
        targetYieldStrength_25C: 480,
        targetYieldStrength_Elevated: 180,
        serviceTemperature_C: 150,
        minElongation_pct: 14,
        minFractureToughness_K1c: 40,
        minPREN: 0,
        maxDensity_gcm3: 2.75,
        maxCostUSD_kg: 15.0,
        manufacturingRoute: "LPBF 3D Printing",
        elementExclusions: { noCobalt: true, noRhenium: true, noTantalum: true, lowCarbon: true },
      },
    },
  ];

  // Run Solver & Synthesize Candidates
  const candidateSolutions = useMemo(() => {
    return solveInverseAlloyCandidates(targets);
  }, [targets]);

  const activeCandidate = useMemo(() => {
    return (
      candidateSolutions.find((c) => c.id === selectedCandidateId) ||
      candidateSolutions[0]
    );
  }, [candidateSolutions, selectedCandidateId]);

  useEffect(() => {
    if (activeTab !== "lpbf-physics") return;
    pushCandidateToBuildJob(activeCandidate, targets);
  }, [activeTab, activeCandidate, targets]);

  // Hume Rothery Explorer States
  const [solventSymbol, setSolventSymbol] = useState<string>("Ni");
  const [soluteSymbol, setSoluteSymbol] = useState<string>("Cr");
  const solvent = PERIODIC_ELEMENTS.find((e) => e.symbol === solventSymbol) || PERIODIC_ELEMENTS[0];
  const solute = PERIODIC_ELEMENTS.find((e) => e.symbol === soluteSymbol) || PERIODIC_ELEMENTS[1];
  const hrResult = evaluateHumeRothery(solvent, solute);

  // LME Price Shock Sensitivity Multiplier
  const [lmeMultiplier, setLmeMultiplier] = useState<number>(1.0);

  // Generated Python Script
  const pythonScript = useMemo(() => {
    return generatePythonJupyterScript(targets, activeCandidate);
  }, [targets, activeCandidate]);

  const handleCopyScript = () => {
    navigator.clipboard.writeText(pythonScript);
    setCopiedScript(true);
    setTimeout(() => setCopiedScript(false), 2500);
  };

  const handleDownloadScript = () => {
    const blob = new Blob([pythonScript], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${activeCandidate.name.replace(/[^a-zA-Z0-9]/g, "_")}_simulation.py`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div id="inverse-alloy-studio-container" className="space-y-5">
      {/* Top Banner & Navigation Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-5 rounded-2xl bg-[#090e18] border border-[#162032] shadow-xl">
        <div>
          <div className="flex items-center gap-2 text-sky-400 font-mono text-[11px] font-semibold uppercase tracking-widest">
            <FlaskConical className="w-4 h-4 text-sky-400" />
            Inverse Alloy Designer &amp; Pareto Synthesis Engine
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight mt-1 flex items-center gap-2">
            Target Envelope Alloy Synthesis &amp; Ashby Optimization Lab
          </h2>
          <p className="text-xs text-slate-400 max-w-3xl mt-1 leading-relaxed">
            Specify mechanical, thermal, corrosion (PREN), and density targets. The multi-objective engine synthesizes optimized chemical recipes, predicts phase stability (CALPHAD/VEC), calculates LME batch economics, and outputs runnable Python/Jupyter scripts.
          </p>
        </div>

        {/* Global Preset Selector */}
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <span className="text-[11px] font-mono text-slate-400 block lg:inline">Presets:</span>
          {PRESET_SCENARIOS.map((p, idx) => (
            <button
              key={idx}
              onClick={() => setTargets(p.config)}
              className="px-2.5 py-1 rounded-lg bg-[#0c1322] hover:bg-sky-500/10 border border-[#162032] hover:border-sky-500/40 text-slate-300 hover:text-sky-300 text-[11px] font-mono transition"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#162032] pb-3">
        {[
          { id: "pareto-designer", label: "Multi-Objective Inverse Designer", icon: Sparkles, badge: "4 Candidates" },
          { id: "micro-alloy-sandbox", label: "Micro-Alloy What-If Sandbox", icon: Sliders, badge: "Live Tuning" },
          { id: "lpbf-physics", label: "LPBF 3D Print Thermal Physics", icon: Flame, badge: "Melt Pool & VED" },
          { id: "heat-treatment", label: "Post-Processing, HIP & Aging", icon: Activity, badge: "Kinetics & T6" },
          { id: "ashby-map", label: "Interactive Ashby Selection Space", icon: Compass, badge: "2D Canvas" },
          { id: "lme-economics", label: "LME Raw Metal Cost & Supply Chain", icon: DollarSign, badge: "LME Index" },
          { id: "hume-rothery", label: "Hume-Rothery Solid Solution Physics", icon: Atom, badge: "Empirical Rules" },
          { id: "jupyter-export", label: "Python & Jupyter Script Generator", icon: FileCode2, badge: ".py / .ipynb" },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-3.5 py-2 rounded-xl text-xs font-mono font-medium flex items-center gap-2 transition ${
                isActive
                  ? "bg-sky-500/20 text-sky-300 border border-sky-400/50 shadow-[0_0_12px_rgba(56,189,248,0.25)]"
                  : "bg-[#090e18] text-slate-400 border border-[#162032] hover:text-white hover:bg-white/5"
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? "text-sky-400" : "text-slate-500"}`} />
              <span>{tab.label}</span>
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded ${
                  isActive ? "bg-sky-400/20 text-sky-200" : "bg-[#162032] text-slate-400"
                }`}
              >
                {tab.badge}
              </span>
            </button>
          );
        })}
      </div>

      {/* =========================================================================
          TAB 1: MULTI-OBJECTIVE INVERSE DESIGNER (PARETO SYNTHESIS)
         ========================================================================= */}
      {activeTab === "pareto-designer" && (
        <div className="space-y-5">
          {/* Target Specification & Constraint Inputs */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Input Controls Card */}
            <div className="lg:col-span-4 p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-4">
              <div className="flex items-center justify-between border-b border-[#162032] pb-2.5">
                <span className="text-xs font-bold text-white flex items-center gap-2 font-mono">
                  <Sliders className="w-4 h-4 text-sky-400" />
                  Target Specification Envelope
                </span>
                <span className="text-[10px] font-mono text-sky-400 uppercase font-semibold">
                  Constraint Matrix
                </span>
              </div>

              <div className="space-y-3 text-xs">
                {/* Application Name */}
                <div>
                  <label className="text-slate-400 block mb-1 font-medium text-[11px]">Application Target</label>
                  <input aria-label="Application Target"
                    type="text"
                    value={targets.applicationName}
                    onChange={(e) => setTargets({ ...targets, applicationName: e.target.value })}
                    className="w-full p-2 bg-[#0c1322] border border-[#162032] rounded text-white text-xs focus:outline-none focus:border-sky-400"
                  />
                </div>

                {/* Base Matrix System */}
                <div>
                  <label className="text-slate-400 block mb-1 font-medium text-[11px]">Preferred Base Matrix</label>
                  <select aria-label="Preferred Base Matrix"
                    value={targets.baseMatrix}
                    onChange={(e) => setTargets({ ...targets, baseMatrix: e.target.value as any })}
                    className="w-full p-2 bg-[#0c1322] border border-[#162032] rounded text-white text-xs font-mono focus:outline-none focus:border-sky-400"
                  >
                    <option value="Nickel">Nickel Superalloy (High-Temp γ' / Inconel class)</option>
                    <option value="Titanium">Titanium Alloy (Alpha-Beta / Near-Beta Ti-64)</option>
                    <option value="High-Entropy">High-Entropy Alloy (Cantor FCC/BCC CCAs)</option>
                    <option value="Steel">High-Strength Maraging / Super-Duplex Steel</option>
                    <option value="Aluminum">Aerospace 7000 / Al-Scandium Lightweight</option>
                    <option value="Refractory">Refractory W-Mo-Ta Ultra-High Temperature</option>
                  </select>
                </div>

                {/* Mechanical Properties: Yield at 25°C and Elevated */}
                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                      <span>σ_y (25°C):</span>
                      <strong className="text-emerald-400">{targets.targetYieldStrength_25C} MPa</strong>
                    </div>
                    <input aria-label="σ_y (25°C)"
                      type="range"
                      min={300}
                      max={2200}
                      step={25}
                      value={targets.targetYieldStrength_25C}
                      onChange={(e) =>
                        setTargets({ ...targets, targetYieldStrength_25C: parseInt(e.target.value) })
                      }
                      className="w-full accent-emerald-400"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                      <span>σ_y (High Temp):</span>
                      <strong className="text-amber-400">{targets.targetYieldStrength_Elevated} MPa</strong>
                    </div>
                    <input aria-label="σ_y (High Temp)"
                      type="range"
                      min={100}
                      max={1400}
                      step={20}
                      value={targets.targetYieldStrength_Elevated}
                      onChange={(e) =>
                        setTargets({ ...targets, targetYieldStrength_Elevated: parseInt(e.target.value) })
                      }
                      className="w-full accent-amber-400"
                    />
                  </div>
                </div>

                {/* Service Temperature & PREN */}
                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                      <span>Max Service T:</span>
                      <strong className="text-sky-300">{targets.serviceTemperature_C}°C</strong>
                    </div>
                    <input aria-label="Max Service T"
                      type="range"
                      min={50}
                      max={1600}
                      step={25}
                      value={targets.serviceTemperature_C}
                      onChange={(e) =>
                        setTargets({ ...targets, serviceTemperature_C: parseInt(e.target.value) })
                      }
                      className="w-full accent-sky-400"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                      <span>Min PREN:</span>
                      <strong className="text-cyan-400">{targets.minPREN}</strong>
                    </div>
                    <input aria-label="Min PREN"
                      type="range"
                      min={0}
                      max={65}
                      step={1}
                      value={targets.minPREN}
                      onChange={(e) => setTargets({ ...targets, minPREN: parseInt(e.target.value) })}
                      className="w-full accent-cyan-400"
                    />
                  </div>
                </div>

                {/* Density & Raw Material Budget Limit */}
                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                      <span>Max Density:</span>
                      <strong className="text-white">{targets.maxDensity_gcm3} g/cm³</strong>
                    </div>
                    <input aria-label="Max Density"
                      type="range"
                      min={2.7}
                      max={15.0}
                      step={0.1}
                      value={targets.maxDensity_gcm3}
                      onChange={(e) =>
                        setTargets({ ...targets, maxDensity_gcm3: parseFloat(e.target.value) })
                      }
                      className="w-full accent-sky-400"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                      <span>Max Cost ($/kg):</span>
                      <strong className="text-amber-300">${targets.maxCostUSD_kg}</strong>
                    </div>
                    <input aria-label="Max Cost ($/kg)"
                      type="range"
                      min={5}
                      max={200}
                      step={5}
                      value={targets.maxCostUSD_kg}
                      onChange={(e) =>
                        setTargets({ ...targets, maxCostUSD_kg: parseFloat(e.target.value) })
                      }
                      className="w-full accent-amber-400"
                    />
                  </div>
                </div>

                {/* Manufacturing Route */}
                <div>
                  <label className="text-slate-400 block mb-1 font-medium text-[11px]">Primary Manufacturing Route</label>
                  <select aria-label="Primary Manufacturing Route"
                    value={targets.manufacturingRoute}
                    onChange={(e) => setTargets({ ...targets, manufacturingRoute: e.target.value as any })}
                    className="w-full p-2 bg-[#0c1322] border border-[#162032] rounded text-white text-xs font-mono focus:outline-none focus:border-sky-400"
                  >
                    <option value="LPBF 3D Printing">Laser Powder Bed Fusion (LPBF / SLM 3D Printing)</option>
                    <option value="VIM/VAR Forging">Vacuum Induction Melting (VIM/VAR) + Forging</option>
                    <option value="Investment Casting">Directional Solidification (DS / Single Crystal)</option>
                    <option value="Powder Metallurgy">Hot Isostatic Pressing (HIP) / Spark Plasma Sintering</option>
                  </select>
                </div>

                {/* Element Exclusions Checkboxes */}
                <div className="p-2.5 rounded-lg bg-[#0c1322] border border-[#162032] space-y-1.5">
                  <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block font-semibold">
                    Supply Chain &amp; Elemental Exclusions:
                  </span>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={targets.elementExclusions.noCobalt}
                        onChange={(e) =>
                          setTargets({
                            ...targets,
                            elementExclusions: { ...targets.elementExclusions, noCobalt: e.target.checked },
                          })
                        }
                        className="accent-sky-400"
                      />
                      <span>Cobalt-Free (No Co)</span>
                    </label>
                    <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={targets.elementExclusions.noRhenium}
                        onChange={(e) =>
                          setTargets({
                            ...targets,
                            elementExclusions: { ...targets.elementExclusions, noRhenium: e.target.checked },
                          })
                        }
                        className="accent-sky-400"
                      />
                      <span>Rhenium-Free (No Re)</span>
                    </label>
                    <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={targets.elementExclusions.noTantalum}
                        onChange={(e) =>
                          setTargets({
                            ...targets,
                            elementExclusions: { ...targets.elementExclusions, noTantalum: e.target.checked },
                          })
                        }
                        className="accent-sky-400"
                      />
                      <span>Tantalum-Free (No Ta)</span>
                    </label>
                    <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={targets.elementExclusions.lowCarbon}
                        onChange={(e) =>
                          setTargets({
                            ...targets,
                            elementExclusions: { ...targets.elementExclusions, lowCarbon: e.target.checked },
                          })
                        }
                        className="accent-sky-400"
                      />
                      <span>Ultra-Low Carbon</span>
                    </label>
                  </div>
                </div>
              </div>
            </div>

            {/* 4 Pareto Candidate Cards Selector */}
            <div className="lg:col-span-8 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                  <Award className="w-4 h-4 text-amber-400" />
                  Synthesized Pareto Candidate Solutions ({candidateSolutions.length} Variants)
                </h3>
                <span className="text-[11px] font-mono text-slate-400">
                  Select candidate to inspect deep thermomechanical chemistry
                </span>
              </div>

              {/* Candidates Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {candidateSolutions.map((cand, idx) => {
                  const isSelected = cand.id === selectedCandidateId;
                  return (
                    <div
                      key={cand.id}
                      onClick={() => {
                        setSelectedCandidateId(cand.id);
                        pushCandidateToBuildJob(cand, targets);
                      }}
                      className={`p-4 rounded-xl border transition cursor-pointer flex flex-col justify-between space-y-3 ${
                        isSelected
                          ? "bg-[#0c1424] border-sky-400 shadow-[0_0_16px_rgba(56,189,248,0.25)]"
                          : "bg-[#090e18] border-[#162032] hover:border-slate-600 hover:bg-[#0c1322]"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 font-bold border border-sky-500/20">
                            #{idx + 1} {cand.archetype}
                          </span>
                          <span className="text-xs font-mono font-bold text-emerald-400">
                            {cand.conformanceScores.overallMatchPct}% Conformance
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-white mt-1.5 font-mono">{cand.name}</h4>
                        <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-1">{cand.tagline}</p>
                      </div>

                      {/* Quick Metric Bar */}
                      <div className="grid grid-cols-3 gap-2 p-2 rounded-lg bg-[#070c16] border border-[#162032] text-center font-mono text-xs">
                        <div>
                          <span className="text-[10px] text-slate-500 block">σ_y (25°C)</span>
                          <strong className="text-emerald-300">{cand.yieldStrength_25C_MPa} MPa</strong>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-500 block">Density</span>
                          <strong className="text-white">{cand.density_gcm3} g/cm³</strong>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-500 block">LME Cost</span>
                          <strong className="text-amber-300">${cand.rawCostUSD_kg}/kg</strong>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Active Candidate Deep Engineering Dossier */}
              <div className="p-4 rounded-xl bg-[#090e18] border border-sky-500/40 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#162032] pb-3">
                  <div>
                    <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                      Candidate Chemical &amp; Microstructural Blueprint
                    </span>
                    <h3 className="text-base font-bold text-white mt-0.5 font-mono flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-sky-400" />
                      {activeCandidate.name}
                    </h3>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
                    <SendToModuleButton
                      payload={createPipelinePayloadFromCandidate(activeCandidate, targets.applicationName)}
                      onNavigate={onNavigate}
                      label="Send to Module ⚡"
                      variant="primary"
                    />
                    <button
                      onClick={() => setActiveTab("lpbf-physics")}
                      className="px-2.5 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 font-bold flex items-center gap-1.5 transition"
                    >
                      <Flame className="w-3.5 h-3.5" />
                      LPBF Lazer
                    </button>
                    <button
                      onClick={() => setActiveTab("heat-treatment")}
                      className="px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 font-bold flex items-center gap-1.5 transition"
                    >
                      <Activity className="w-3.5 h-3.5" />
                      Heat Treatment &amp; HIP
                    </button>
                    <button
                      onClick={() => setActiveTab("micro-alloy-sandbox")}
                      className="px-2.5 py-1 rounded bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 border border-sky-500/40 font-bold flex items-center gap-1.5 transition"
                    >
                      <Sliders className="w-3.5 h-3.5" />
                      Micro-Alloying
                    </button>
                    <span className="px-2.5 py-1 rounded bg-sky-500/20 text-sky-300 border border-sky-400/40 font-bold">
                      Matrix: {activeCandidate.matrixPhase}
                    </span>
                    <span className="px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-400/40 font-bold">
                      PREN: {activeCandidate.pren}
                    </span>
                  </div>
                </div>

                {/* Direct Simulation Lab Transfer Strip */}
                <div className="p-3 bg-[#050810] rounded-xl border border-sky-500/25 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
                    <span className="text-[11px] font-mono text-slate-300 font-semibold">
                      Simulation Pipeline: Load synthesized alloy kinetics &amp; physics into:
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <button
                      type="button"
                      onClick={() => {
                        const p = createPipelinePayloadFromCandidate(activeCandidate, targets.applicationName);
                        setActivePipelineMaterial(p);
                        if (onNavigate) onNavigate("thermal-scheduler");
                      }}
                      className="px-2.5 py-1 rounded bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 font-mono text-[10.5px] flex items-center gap-1 transition"
                      title="Load synthetic alloy kinetic constants into Thermal Cycle Scheduler"
                    >
                      <Flame className="w-3 h-3 text-amber-400" />
                      <span>Heat Treatment Lab ➔</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const p = createPipelinePayloadFromCandidate(activeCandidate, targets.applicationName);
                        setActivePipelineMaterial(p);
                        if (onNavigate) onNavigate("xrd-lab");
                      }}
                      className="px-2.5 py-1 rounded bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/30 text-sky-300 font-mono text-[10.5px] flex items-center gap-1 transition"
                      title="Load Bragg reflections and crystal lattice into Rapid XRD Lab"
                    >
                      <Atom className="w-3 h-3 text-sky-400" />
                      <span>XRD Lab ➔</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const p = createPipelinePayloadFromCandidate(activeCandidate, targets.applicationName);
                        setActivePipelineMaterial(p);
                        if (onNavigate) onNavigate("hardness-tensile");
                      }}
                      className="px-2.5 py-1 rounded bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 font-mono text-[10.5px] flex items-center gap-1 transition"
                      title="Load estimated hardness, Tabor factor and work hardening into Hardness Lab"
                    >
                      <Gauge className="w-3 h-3 text-emerald-400" />
                      <span>Hardness Lab ➔</span>
                    </button>
                  </div>
                </div>

                {/* Nominal Composition Badges */}
                <div className="space-y-1.5">
                  <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block font-semibold">
                    Calculated Nominal Composition (% Weight &amp; Atomic Fraction):
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(activeCandidate.compositionWt).map(([elem, wt]) => (
                      <div
                        key={elem}
                        className="px-2.5 py-1.5 rounded-lg bg-[#0c1322] border border-[#1a263c] font-mono text-xs flex items-center gap-2"
                      >
                        <strong className="text-sky-400 text-sm">{elem}</strong>
                        <div className="text-[11px] text-slate-300">
                          <span>{wt}% wt</span>
                          <span className="text-slate-500 text-[10px] ml-1">
                            ({activeCandidate.compositionAt[elem] || 0}% at)
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Thermodynamic Heuristics Matrix */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <div className="p-2.5 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
                    <span className="text-[10px] text-slate-400 font-mono block">VEC (Valence Electrons):</span>
                    <div className="text-sm font-bold text-white font-mono">{activeCandidate.vec}</div>
                    <div className="text-[10px] text-slate-500">
                      {activeCandidate.vec >= 8.0
                        ? "Stable FCC solid solution"
                        : activeCandidate.vec < 6.87
                        ? "Stable BCC phase"
                        : "Mixed dual FCC+BCC phases"}
                    </div>
                  </div>

                  <div className="p-2.5 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
                    <span className="text-[10px] text-slate-400 font-mono block">Atomic Misfit (δ):</span>
                    <div className="text-sm font-bold text-emerald-400 font-mono">
                      {activeCandidate.atomicSizeMismatch_deltaPct}%
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {activeCandidate.atomicSizeMismatch_deltaPct < 6.6
                        ? "Favorable for single-phase solution"
                        : "High lattice strain → Precipitate driving force"}
                    </div>
                  </div>

                  <div className="p-2.5 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
                    <span className="text-[10px] text-slate-400 font-mono block">Freezing Range (ΔT_f):</span>
                    <div className="text-sm font-bold text-amber-400 font-mono">
                      {activeCandidate.freezingRange_C}°C
                    </div>
                    <div className="text-[10px] text-slate-500">
                      Solidus: {activeCandidate.solidus_C}°C | Liq: {activeCandidate.liquidus_C}°C
                    </div>
                  </div>

                  <div className="p-2.5 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
                    <span className="text-[10px] text-slate-400 font-mono block">Alloy cracking screen:</span>
                    <div className="text-sm font-bold text-cyan-400 font-mono">
                      {activeCandidate.lpbfPrintabilityScore} / 100
                    </div>
                    <div className="text-[10px] text-slate-500">
                      Chemistry / freezing-range screen only. Industrial printability is the Python verdict in Additive LPBF Lab.
                    </div>
                  </div>
                </div>

                {/* Strengthening Mechanism & Heat Treatment Recipe */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
                    <span className="font-bold text-white font-mono text-[11px] flex items-center gap-1.5">
                      <Atom className="w-3.5 h-3.5 text-sky-400" />
                      Strengthening Mechanism:
                    </span>
                    <p className="text-slate-300 leading-relaxed text-[11px]">
                      {activeCandidate.primaryStrengtheningMechanism}
                    </p>
                  </div>

                  <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
                    <span className="font-bold text-white font-mono text-[11px] flex items-center gap-1.5">
                      <Thermometer className="w-3.5 h-3.5 text-amber-400" />
                      Thermomechanical Heat Treatment Schedule:
                    </span>
                    <div className="text-[11px] text-slate-300 font-mono space-y-0.5">
                      <div>• Solutionize: {activeCandidate.heatTreatmentSchedule.solutionizing}</div>
                      <div>• Quench: {activeCandidate.heatTreatmentSchedule.quenchMedium}</div>
                      <div>• Aging: {activeCandidate.heatTreatmentSchedule.primaryAging}</div>
                    </div>
                  </div>
                </div>

                {/* Physics-Informed Analytical Dossier: Yield Breakdown & Scheil Curve */}
                <PhysicalMetallurgyDossier
                  candidate={activeCandidate}
                  serviceTemperature_C={targets.serviceTemperature_C}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 2: MICRO-ALLOY WHAT-IF SANDBOX (LIVE TUNING)
         ========================================================================= */}
      {activeTab === "micro-alloy-sandbox" && (
        <div className="space-y-4">
          {/* Candidate selector pills inside sandbox */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-[#090e18] border border-[#162032]">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-mono text-slate-300 font-bold">
                Select Base Candidate to Edit:
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {candidateSolutions.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelectedCandidateId(c.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono transition ${
                    selectedCandidateId === c.id
                      ? "bg-amber-500/20 text-amber-300 border border-amber-500/50 font-bold shadow-sm shadow-amber-500/20"
                      : "bg-[#0c1322] text-slate-400 border border-[#162032] hover:text-white"
                  }`}
                >
                  {c.archetype} ({c.name})
                </button>
              ))}
            </div>
          </div>

          {/* Sandbox Live Editor Component */}
          <MicroAlloySandbox
            key={activeCandidate.id}
            candidate={activeCandidate}
            targets={targets}
          />
        </div>
      )}

      {/* =========================================================================
          TAB 3: LPBF 3D PRINTING THERMAL PHYSICS & ROSENTHAL MELT POOL
         ========================================================================= */}
      {activeTab === "lpbf-physics" && (
        <div className="space-y-4">
          <div className="p-3 rounded-xl bg-sky-950/30 border border-sky-500/30 text-[11px] font-mono text-sky-200">
            Build Job process vector (P, v, h, t, d, preheat) is shared with 3D LPBF Simulation via{" "}
            <strong>useMaterialSpecimenStore.lpbf</strong>. Changing sliders here updates the digital twin job.
            Industrial printability is <strong>not</strong> decided here — use Send to Module → Additive LPBF Process Job.
          </div>
          {/* Candidate selector pills inside LPBF suite */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-[#090e18] border border-[#162032]">
            <div className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-rose-400" />
              <span className="text-xs font-mono text-slate-300 font-bold">
                Select Alloy Candidate to Analyze:
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {candidateSolutions.map((c) => (
                <button
                  key={c.id}
                  onClick={() => {
                    setSelectedCandidateId(c.id);
                    pushCandidateToBuildJob(c, targets);
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono transition ${
                    selectedCandidateId === c.id
                      ? "bg-rose-500/20 text-rose-300 border border-rose-500/50 font-bold shadow-sm shadow-rose-500/20"
                      : "bg-[#0c1322] text-slate-400 border border-[#162032] hover:text-white"
                  }`}
                >
                  {c.archetype} ({c.name})
                </button>
              ))}
            </div>
          </div>

          <LPBFAdditivePhysicsSuite
            key={activeCandidate.id}
            candidate={activeCandidate}
            targets={targets}
          />
        </div>
      )}

      {/* =========================================================================
          TAB 4: POST-PROCESSING, HIP & HEAT TREATMENT / AGING KINETICS
         ========================================================================= */}
      {activeTab === "heat-treatment" && (
        <div className="space-y-4">
          {/* Candidate selector pills inside Heat Treatment suite */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-[#090e18] border border-[#162032]">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-mono text-slate-300 font-bold">
                Select Alloy Candidate for Heat Treatment Analysis:
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {candidateSolutions.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelectedCandidateId(c.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono transition ${
                    selectedCandidateId === c.id
                      ? "bg-amber-500/20 text-amber-300 border border-amber-500/50 font-bold shadow-sm shadow-amber-500/20"
                      : "bg-[#0c1322] text-slate-400 border border-[#162032] hover:text-white"
                  }`}
                >
                  {c.archetype} ({c.name})
                </button>
              ))}
            </div>
          </div>

          <HeatTreatmentAgingSimulator
            key={activeCandidate.id}
            candidate={activeCandidate}
            targets={targets}
          />
        </div>
      )}

      {/* =========================================================================
          TAB 5: INTERACTIVE ASHBY PROPERTY SELECTION MAP
         ========================================================================= */}
      {activeTab === "ashby-map" && (
        <AshbyPropertyMap
          candidates={candidateSolutions}
          selectedCandidateId={selectedCandidateId}
          onSelectCandidate={setSelectedCandidateId}
          targets={targets}
        />
      )}

      {/* =========================================================================
          TAB 3: LME REAL-TIME METAL COST & SENSITIVITY LAB
         ========================================================================= */}
      {activeTab === "lme-economics" && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-amber-400 font-mono text-[10px] uppercase font-semibold">
                <DollarSign className="w-4 h-4 text-amber-400" />
                London Metal Exchange (LME) Commodity Index &amp; Raw Batch Cost
              </div>
              <h3 className="text-base font-bold text-white mt-0.5">
                Batch Raw Material Cost Breakdown for {activeCandidate.name}
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Calculates elemental cost contribution, scrap recyclability, and supply chain vulnerability.
              </p>
            </div>

            {/* Price Shock Simulation Slider */}
            <div className="p-3 bg-[#0c1322] rounded-xl border border-[#162032] space-y-1 font-mono text-xs shrink-0">
              <div className="flex justify-between text-slate-400">
                <span>Commodity Market Price Shock:</span>
                <strong className="text-amber-400">
                  {lmeMultiplier > 1 ? `+${Math.round((lmeMultiplier - 1) * 100)}%` : "Spot Benchmark"}
                </strong>
              </div>
              <input aria-label="Commodity Market Price Shock"
                type="range"
                min={0.8}
                max={2.5}
                step={0.1}
                value={lmeMultiplier}
                onChange={(e) => setLmeMultiplier(parseFloat(e.target.value))}
                className="w-full accent-amber-400"
              />
            </div>
          </div>

          {/* Cost Waterfall Breakdown Table */}
          <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-slate-300 font-bold">
                Elemental Cost Waterfall ({activeCandidate.costBreakdown.length} Constituents)
              </span>
              <span className="text-sm font-mono font-bold text-amber-400">
                Total Ingot Batch Cost: ${(activeCandidate.rawCostUSD_kg * lmeMultiplier).toFixed(2)} / kg
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-[#162032] text-slate-400 text-[11px]">
                    <th className="py-2">Element</th>
                    <th className="py-2">Weight Fraction (wt%)</th>
                    <th className="py-2">LME Spot ($/kg)</th>
                    <th className="py-2">Cost Contribution ($/kg)</th>
                    <th className="py-2">% of Total Batch Cost</th>
                    <th className="py-2">Supply Risk</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#162032] text-slate-200">
                  {activeCandidate.costBreakdown.map((item) => {
                    const lmeData = LME_PRICE_DATABASE[item.symbol];
                    const unitPrice = (lmeData ? lmeData.pricePerKgUSD : 10) * lmeMultiplier;
                    const adjustedCost = (item.wtPct / 100) * unitPrice;
                    return (
                      <tr key={item.symbol} className="hover:bg-white/5 transition">
                        <td className="py-2 font-bold text-sky-400 flex items-center gap-2">
                          {item.symbol} - {lmeData ? lmeData.name : item.symbol}
                        </td>
                        <td className="py-2">{item.wtPct}%</td>
                        <td className="py-2 text-slate-400">${unitPrice.toFixed(2)}/kg</td>
                        <td className="py-2 font-bold text-amber-300">${adjustedCost.toFixed(2)}</td>
                        <td className="py-2">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-[#162032] rounded-full overflow-hidden">
                              <div
                                className="h-full bg-amber-400 rounded-full"
                                style={{ width: `${item.pctOfTotalCost}%` }}
                              ></div>
                            </div>
                            <span>{item.pctOfTotalCost}%</span>
                          </div>
                        </td>
                        <td className="py-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              lmeData?.supplyRisk === "Critical / Strategic"
                                ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                                : lmeData?.supplyRisk === "Moderate"
                                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                                : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                            }`}
                          >
                            {lmeData?.supplyRisk || "Low"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 4: HUME-ROTHERY SOLID SOLUTION PHYSICS
         ========================================================================= */}
      {activeTab === "hume-rothery" && (
        <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                Empirical Physical Metallurgy
              </span>
              <h3 className="text-sm font-bold text-white flex items-center gap-2 mt-0.5 font-mono">
                <Atom className="w-4 h-4 text-sky-400" />
                Hume-Rothery Solid Solubility Evaluator
              </h3>
            </div>
            <span className="text-xs font-mono text-slate-400">
              Rules: Δr &lt; 15%, Iso-structure, Δχ &lt; 0.4, Valency
            </span>
          </div>

          {/* Solvent & Solute Selector */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {/* Solvent */}
            <div className="p-3.5 bg-[#0c1322] rounded-lg border border-[#162032] space-y-2">
              <label className="text-[10px] font-mono text-slate-400 uppercase tracking-widest block font-semibold">
                Base Matrix Solvent Metal (A):
              </label>
              <div className="flex flex-wrap gap-1.5">
                {["Ni", "Fe", "Ti", "Al", "Cu", "Co", "Mo", "W"].map((sym) => (
                  <button
                    key={sym}
                    onClick={() => setSolventSymbol(sym)}
                    className={`px-2.5 py-1 rounded font-mono text-xs font-bold transition ${
                      solventSymbol === sym
                        ? "bg-sky-500/20 border border-sky-400/60 text-sky-300 shadow-[0_0_8px_rgba(56,189,248,0.25)]"
                        : "bg-[#090e18] border border-[#162032] text-slate-300 hover:text-white hover:bg-white/5"
                    }`}
                  >
                    {sym}
                  </button>
                ))}
              </div>
              <div className="pt-1.5 text-xs font-mono text-slate-400 flex items-center gap-3">
                <span>Radius: <strong className="text-white">{solvent.atomicRadius} pm</strong></span>
                <span>Structure: <strong className="text-white">{solvent.crystalStructure}</strong></span>
                <span>χ: <strong className="text-white">{solvent.electronegativity}</strong></span>
              </div>
            </div>

            {/* Solute */}
            <div className="p-3.5 bg-[#0c1322] rounded-lg border border-[#162032] space-y-2">
              <label className="text-[10px] font-mono text-slate-400 uppercase tracking-widest block font-semibold">
                Alloying Solute Element (B):
              </label>
              <div className="flex flex-wrap gap-1.5">
                {["Cr", "Mo", "V", "Si", "Mn", "Nb", "Ta", "Al", "Ti", "W", "Sc"].map((sym) => (
                  <button
                    key={sym}
                    onClick={() => setSoluteSymbol(sym)}
                    className={`px-2.5 py-1 rounded font-mono text-xs font-bold transition ${
                      soluteSymbol === sym
                        ? "bg-sky-500/20 border border-sky-400/60 text-sky-300 shadow-[0_0_8px_rgba(56,189,248,0.25)]"
                        : "bg-[#090e18] border border-[#162032] text-slate-300 hover:text-white hover:bg-white/5"
                    }`}
                  >
                    {sym}
                  </button>
                ))}
              </div>
              <div className="pt-1.5 text-xs font-mono text-slate-400 flex items-center gap-3">
                <span>Radius: <strong className="text-white">{solute.atomicRadius} pm</strong></span>
                <span>Structure: <strong className="text-white">{solute.crystalStructure}</strong></span>
                <span>χ: <strong className="text-white">{solute.electronegativity}</strong></span>
              </div>
            </div>
          </div>

          {/* 4 Hume-Rothery Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
            <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
              <div className="flex justify-between items-center">
                <span className="text-[11px] font-mono text-slate-400">1. Size Factor (Δr)</span>
                {hrResult.sizeCriterion ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                )}
              </div>
              <div className="text-base font-mono font-bold text-white">{hrResult.sizeDifferencePct}%</div>
              <div className="text-[10px] text-slate-400">
                {hrResult.sizeDifferencePct < 15
                  ? "Favorable (< 15% misfit for substitutional solution)"
                  : "High misfit strain → Precipitate driving force"}
              </div>
            </div>

            <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
              <div className="flex justify-between items-center">
                <span className="text-[11px] font-mono text-slate-400">2. Crystal Isomorphism</span>
                {hrResult.crystalStructureMatch ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                )}
              </div>
              <div className="text-base font-mono font-bold text-white">
                {solvent.crystalStructure} vs {solute.crystalStructure}
              </div>
              <div className="text-[10px] text-slate-400">
                {hrResult.crystalStructureMatch
                  ? "Complete solid solution miscibility is possible"
                  : "Partial terminal solid solution with limited solubility"}
              </div>
            </div>

            <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
              <div className="flex justify-between items-center">
                <span className="text-[11px] font-mono text-slate-400">3. Electronegativity (Δχ)</span>
                {hrResult.electronegativityCriterion ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                )}
              </div>
              <div className="text-base font-mono font-bold text-white">
                Δχ = {hrResult.electronegativityDifference}
              </div>
              <div className="text-[10px] text-slate-400">
                {hrResult.electronegativityCriterion
                  ? "Metallic bond favored (Low compound affinity)"
                  : "High electronegativity gap → Intermetallic compound formation"}
              </div>
            </div>

            <div className="p-3 bg-[#0c1322] rounded-lg border border-[#162032] space-y-1">
              <div className="flex justify-between items-center">
                <span className="text-[11px] font-mono text-slate-400">4. Relative Valency</span>
                {hrResult.valencyMatch ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                )}
              </div>
              <div className="text-base font-mono font-bold text-white">
                Val: {solvent.valence[0]} vs {solute.valence[0]}
              </div>
              <div className="text-[10px] text-slate-400">
                Higher valency solute dissolves more readily in lower valency solvent.
              </div>
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-[#0c1322] border border-[#162032] flex items-start gap-3">
            <div className="p-1.5 rounded bg-sky-500/10 text-sky-400 shrink-0">
              <Info className="w-4 h-4" />
            </div>
            <div className="text-xs text-slate-300 space-y-0.5">
              <div className="font-bold text-white">
                Thermodynamic Phase Prediction for {solvent.name} - {solute.name} System:
                <span className="ml-2 font-mono text-sky-400">[{hrResult.overallSolubilityForecast}]</span>
              </div>
              <p className="leading-relaxed text-slate-400">{hrResult.explanation}</p>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 5: PYTHON & JUPYTER SCRIPT GENERATOR
         ========================================================================= */}
      {activeTab === "jupyter-export" && (
        <div className="p-4 rounded-xl bg-[#090e18] border border-[#162032] space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#162032] pb-3">
            <div>
              <span className="text-[10px] font-mono text-sky-400 uppercase tracking-widest font-semibold">
                Reproducible Scientific Computing
              </span>
              <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2 mt-0.5">
                <FileCode2 className="w-4 h-4 text-sky-400" />
                Python &amp; Jupyter Solver Script ({activeCandidate.name})
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Ready-to-execute Python code using NumPy, SciPy, and Matplotlib to verify all thermodynamic equations locally.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyScript}
                className="px-3 py-1.5 rounded-lg bg-[#0c1322] hover:bg-sky-500/10 border border-[#162032] hover:border-sky-500/40 text-slate-200 hover:text-sky-300 text-xs font-mono flex items-center gap-1.5 transition"
              >
                {copiedScript ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedScript ? "Copied Code!" : "Copy Python"}</span>
              </button>

              <button
                onClick={handleDownloadScript}
                className="px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs font-mono flex items-center gap-1.5 transition shadow-[0_0_12px_rgba(56,189,248,0.25)]"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download .py</span>
              </button>
            </div>
          </div>

          {/* Code Viewer */}
          <div className="relative rounded-xl bg-[#060a12] border border-[#162032] p-4 overflow-x-auto">
            <pre className="text-xs font-mono text-sky-300/90 leading-relaxed">
              <code>{pythonScript}</code>
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
