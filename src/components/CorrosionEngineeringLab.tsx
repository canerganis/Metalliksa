import React, { useState, useMemo } from "react";
import {
  ShieldAlert,
  Droplets,
  Activity,
  Flame,
  AlertTriangle,
  CheckCircle2,
  Sliders,
  Layers,
  FileSpreadsheet,
  Zap,
  Info,
  TrendingDown,
  RefreshCw,
  Compass,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { DynamicPourbaixStudio } from "./DynamicPourbaixStudio";
import { CorrosionEISKineticsStudio } from "./CorrosionEISKineticsStudio";
import { TafelPolarizationLab } from "./TafelPolarizationLab";

// Standard Reduction Potentials & Corrosion Parameters
interface GalvanicMetal {
  id: string;
  name: string;
  symbol: string;
  e0: number; // Volts vs SHE
  valency: number;
  density: number; // g/cm³
  atomicMass: number; // g/mol
  category: "Active (Anodic)" | "Moderate" | "Noble (Cathodic)";
  pittingIndex?: number;
  description: string;
  recommendedCoatings: string[];
}

const GALVANIC_METALS: GalvanicMetal[] = [
  { id: "mg", name: "Magnesium Alloy (AZ31B)", symbol: "Mg", e0: -2.37, valency: 2, density: 1.74, atomicMass: 24.31, category: "Active (Anodic)", description: "High galvanic activity. Prime candidate for sacrificial anodes in cathodic protection.", recommendedCoatings: ["Micro-arc oxidation (MAO)", "Fluoride conversion", "Sacrificial isolation"] },
  { id: "al-7075", name: "Aerospace Aluminum (7075-T6)", symbol: "Al-Zn-Mg", e0: -1.66, valency: 3, density: 2.81, atomicMass: 26.98, category: "Active (Anodic)", description: "Susceptible to stress corrosion cracking (SCC) and exfoliation along grain boundaries.", recommendedCoatings: ["Chromate-free anodizing (Tartaric-Sulfuric)", "Epoxy primer with corrosion inhibitors"] },
  { id: "al-6061", name: "Structural Aluminum (6061-T6)", symbol: "Al-Mg-Si", e0: -1.45, valency: 3, density: 2.70, atomicMass: 26.98, category: "Active (Anodic)", description: "General structural aluminum with moderate marine passivity.", recommendedCoatings: ["Hard anodizing Type III", "Polyurethane topcoat"] },
  { id: "zn", name: "Zinc (Hot-Dip Galvanizing)", symbol: "Zn", e0: -0.76, valency: 2, density: 7.14, atomicMass: 65.38, category: "Active (Anodic)", description: "Traditional sacrificial galvanic barrier for steel reinforcement and marine piles.", recommendedCoatings: ["Passivation chromating/silane", "Duplex paint over HDG"] },
  { id: "steel-1018", name: "Carbon Steel (AISI 1018)", symbol: "Fe-C", e0: -0.44, valency: 2, density: 7.87, atomicMass: 55.85, category: "Moderate", description: "Standard structural steel; corrodes uniformly unless protected by cathodic system.", recommendedCoatings: ["Zinc-rich epoxy primer", "Thermal spray aluminum (TSA)"] },
  { id: "cast-iron", name: "Ductile Cast Iron (ASTM A536)", symbol: "Fe-Si-C", e0: -0.50, valency: 2, density: 7.10, atomicMass: 55.85, category: "Moderate", description: "Prone to graphitic corrosion where iron leaches leaving porous graphite network.", recommendedCoatings: ["Coal tar epoxy", "Polyethylene encasement"] },
  { id: "cd", name: "Cadmium Plate", symbol: "Cd", e0: -0.40, valency: 2, density: 8.65, atomicMass: 112.41, category: "Moderate", description: "Aerospace fastener electroplating preventing galvanic lock with aluminum.", recommendedCoatings: ["Zinc-Nickel replacement (RoHS compliant)", "Silicate passivate"] },
  { id: "ni-200", name: "Commercial Nickel (Nickel 200)", symbol: "Ni", e0: -0.25, valency: 2, density: 8.90, atomicMass: 58.69, category: "Moderate", description: "Excellent caustic alkali and dry halogen immunity via stable NiO passive film.", recommendedCoatings: ["Electroless Ni-P plating"] },
  { id: "pb-sn", name: "Lead-Tin Solder (60/40)", symbol: "Pb-Sn", e0: -0.13, valency: 2, density: 8.50, atomicMass: 150.0, category: "Moderate", description: "Electronic interconnections; prone to galvanic whiskers in humid environments.", recommendedCoatings: ["Conformal coating (Parylene / Silicone)"] },
  { id: "cu-c110", name: "Electrolytic Copper (C11000 ETP)", symbol: "Cu", e0: +0.34, valency: 2, density: 8.96, atomicMass: 63.55, category: "Noble (Cathodic)", description: "Highly noble cathode metal; accelerates rapid galvanic corrosion on Al and Fe.", recommendedCoatings: ["Tinned coating", "Dielectric dielectric isolating gaskets"] },
  { id: "ss-304", name: "Stainless Steel 304 (Passive)", symbol: "SS 304", e0: +0.02, valency: 2.2, density: 7.90, atomicMass: 55.5, category: "Noble (Cathodic)", pittingIndex: 18, description: "Standard 18/8 stainless; prone to crevice corrosion and pitting in marine chloride.", recommendedCoatings: ["Nitric acid passivation (ASTM A967)", "Electropolishing"] },
  { id: "ss-316l", name: "Stainless Steel 316L (Passive)", symbol: "SS 316L", e0: +0.08, valency: 2.4, density: 8.00, atomicMass: 55.5, category: "Noble (Cathodic)", pittingIndex: 25, description: "2.5% Molybdenum addition stabilizes Cr2O3 passive barrier against chloride pitting.", recommendedCoatings: ["Citric acid passivation", "Pickling & passivation"] },
  { id: "duplex-2205", name: "Duplex Stainless Steel 2205", symbol: "22Cr Duplex", e0: +0.12, valency: 2.5, density: 7.80, atomicMass: 55.0, category: "Noble (Cathodic)", pittingIndex: 35, description: "Austenitic-ferritic microstructure with high resistance to chloride SCC and pitting.", recommendedCoatings: ["Pickling paste", "Clean oxide thermal annealing"] },
  { id: "ti-64", name: "Titanium Grade 5 (Ti-6Al-4V)", symbol: "Ti-6Al-4V", e0: +0.20, valency: 4, density: 4.43, atomicMass: 47.87, category: "Noble (Cathodic)", description: "Exceptional self-healing TiO2 barrier. Virtually immune to seawater pitting.", recommendedCoatings: ["Thermal oxidation", "Dielectric isolation from CFRP"] },
  { id: "inconel-718", name: "Inconel 718 Superalloy", symbol: "Ni-Cr-Fe", e0: +0.18, valency: 3, density: 8.19, atomicMass: 58.0, category: "Noble (Cathodic)", pittingIndex: 48, description: "Aerospace superalloy with extreme immunity to chloride pitting and high-temp hot corrosion.", recommendedCoatings: ["Thermal barrier coatings (TBC)", "Aluminide diffusion"] },
  { id: "cfrp-carbon", name: "Carbon Fiber Composite (CFRP)", symbol: "C (Graphite)", e0: +1.20, valency: 2, density: 1.80, atomicMass: 12.01, category: "Noble (Cathodic)", description: "Electrically conductive carbon matrix acting as aggressive cathode against Al airframes.", recommendedCoatings: ["Fiberglass isolation ply", "Polysulfide sealants"] },
];

export function CorrosionEngineeringLab() {
  const [activeTab, setActiveTab] = useState<"galvanic" | "pren" | "polarization" | "ocp-g59" | "pourbaix" | "corrosion-eis">("corrosion-eis");

  // Galvanic Simulator State
  const [anodeIdx, setAnodeIdx] = useState<number>(1); // 7075 Al
  const [cathodeIdx, setCathodeIdx] = useState<number>(9); // Copper
  const [currentDensity, setCurrentDensity] = useState<number>(3.0); // mA/cm²
  const [anodeArea, setAnodeArea] = useState<number>(25); // cm²
  const [cathodeArea, setCathodeArea] = useState<number>(250); // cm²
  const [electrolyte, setElectrolyte] = useState<"marine" | "acidic" | "industrial" | "soil" | "tapwater">("marine");

  // PREN & Critical Pitting State
  const [cr, setCr] = useState<number>(22.0);
  const [mo, setMo] = useState<number>(3.2);
  const [w, setW] = useState<number>(0.0);
  const [n, setN] = useState<number>(0.18);
  const [cptChloridePpm, setCptChloridePpm] = useState<number>(20000); // 20k ppm (seawater)

  // Tafel Polarization Calculator State
  const [eCorr, setECorr] = useState<number>(-0.45); // Volts
  const [iCorrLog, setICorrLog] = useState<number>(-5.5); // log(A/cm²)
  const [betaA, setBetaA] = useState<number>(0.12); // V/decade
  const [betaC, setBetaC] = useState<number>(0.10); // V/decade
  const [appliedOverpotential, setAppliedOverpotential] = useState<number>(0.15); // V

  // Calculations
  const anodeMetal = GALVANIC_METALS[anodeIdx] || GALVANIC_METALS[0];
  const cathodeMetal = GALVANIC_METALS[cathodeIdx] || GALVANIC_METALS[9];

  const potentialDiff = Math.abs(cathodeMetal.e0 - anodeMetal.e0);
  const areaRatio = cathodeArea / Math.max(0.1, anodeArea);

  const envFactor = useMemo(() => {
    switch (electrolyte) {
      case "acidic": return 4.0;
      case "marine": return 2.2;
      case "industrial": return 1.5;
      case "soil": return 1.1;
      case "tapwater": return 0.5;
    }
  }, [electrolyte]);

  // Faraday penetration calculation:
  // i_eff = i_base * (A_cath / A_anode)^0.7 * envFactor * (ΔE / 1.0)
  const effectiveIcorr_uA = currentDensity * 1000 * Math.pow(areaRatio, 0.72) * envFactor * Math.max(0.2, potentialDiff);
  
  const penetrationRateMmYear = useMemo(() => {
    const M = anodeMetal.atomicMass;
    const nVal = anodeMetal.valency;
    const rho = anodeMetal.density;
    // CR (mm/yr) = (0.00327 * i_corr (µA/cm²) * M) / (n * rho)
    return (0.00327 * effectiveIcorr_uA * M) / (nVal * rho);
  }, [anodeMetal, effectiveIcorr_uA]);

  const penetrationMpy = penetrationRateMmYear * 39.37; // mils per year
  const massLossGramsPerDay = useMemo(() => {
    // Mass loss (g/day) = (i_corr (A) * M * 86400) / (n * F) where F = 96485 C/mol
    const totalCurrentA = (effectiveIcorr_uA * 1e-6) * anodeArea;
    const gramsPerSec = (totalCurrentA * anodeMetal.atomicMass) / (anodeMetal.valency * 96485);
    return gramsPerSec * 86400;
  }, [effectiveIcorr_uA, anodeArea, anodeMetal]);

  // PREN Score
  const prenScore = useMemo(() => {
    return cr + 3.3 * (mo + 0.5 * w) + 16 * n;
  }, [cr, mo, w, n]);

  // Critical Pitting Temperature (CPT) Estimate in 6% FeCl3 (ASTM G48A approx)
  // CPT (°C) ≈ 2.5 * PREN - 37.1
  const estimatedCPT_Celsius = useMemo(() => {
    const cpt = 2.5 * prenScore - 37.1;
    return Math.max(0, Math.min(95, cpt));
  }, [prenScore]);

  // Stern-Geary Polarization Resistance (Rp)
  // Rp = (Beta_a * Beta_c) / (2.303 * i_corr * (Beta_a + Beta_c))
  const sternGearyRp = useMemo(() => {
    const icorrActual = Math.pow(10, iCorrLog); // A/cm²
    const bProduct = betaA * betaC;
    const bSum = betaA + betaC;
    const bConstant = bProduct / (2.303 * bSum);
    return bConstant / icorrActual; // Ohm * cm²
  }, [betaA, betaC, iCorrLog]);

  return (
    <div className="space-y-6">
      {/* Top Banner Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-[#090e18] p-5 rounded-2xl border border-[#162032] shadow-sm">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-[0_0_16px_rgba(245,158,11,0.25)]">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-extrabold text-white font-mono tracking-wide uppercase">
                Corrosion & Degradation Engineering
              </h2>
              <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-mono border border-amber-500/40">
                ASTM / NACE / ISO
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Faraday Mass Loss, Galvanic Couple Kinetics, PREN Pitting Index & Tafel Polarization
            </p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1.5 p-1 bg-[#050810] rounded-xl border border-[#162032] overflow-x-auto">
          <button
            type="button"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(8);
              setActiveTab("galvanic");
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === "galvanic"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Droplets className="w-3.5 h-3.5" />
            <span>Galvanic Couple (ASTM G82)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(8);
              setActiveTab("pren");
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === "pren"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Pitting Resistance (PREN/CPT)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(8);
              setActiveTab("polarization");
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === "polarization"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Tafel / Stern-Geary</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(8);
              setActiveTab("ocp-g59");
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === "ocp-g59"
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Real-Time OCP &amp; ASTM G59</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(8);
              setActiveTab("pourbaix");
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === "pourbaix"
                ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-[0_0_10px_rgba(56,189,248,0.3)]"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Compass className="w-3.5 h-3.5 text-sky-400" />
            <span>Pourbaix E–pH (25 °C)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(8);
              setActiveTab("corrosion-eis");
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === "corrosion-eis"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.3)]"
                : "text-amber-400 hover:text-amber-200 bg-amber-950/20 border border-amber-900/30"
            }`}
          >
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Corrosion EIS &amp; Coating Delamination</span>
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 1. GALVANIC COUPLE & FARADAY MASS LOSS                   */}
      {/* ======================================================== */}
      {activeTab === "galvanic" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Controls */}
          <div className="lg:col-span-7 space-y-6">
            <div className="bg-[#090e18] p-5 rounded-xl border border-[#162032] space-y-5">
              <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                  <Droplets className="w-4 h-4 text-amber-400" />
                  <span>Galvanic Pair Configuration</span>
                </h3>
                <span className="text-[11px] text-slate-400 font-mono">ASTM G102 Standard</span>
              </div>

              {/* Anode / Cathode Selectors */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Anodic Metal */}
                <div className="p-4 bg-[#050810] rounded-xl border border-red-500/40 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-red-400 font-mono flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                      ANODE (Corroding Metal)
                    </span>
                    <span className="text-[11px] font-mono text-red-300 font-bold">
                      {anodeMetal.e0 > 0 ? `+${anodeMetal.e0}` : anodeMetal.e0} V vs SHE
                    </span>
                  </div>
                  <select aria-label="ANODE (Corroding Metal)"
                    value={anodeIdx}
                    onChange={(e) => setAnodeIdx(parseInt(e.target.value))}
                    className="w-full bg-[#0c1322] border border-[#1e2d46] rounded-lg p-2 text-xs text-white font-mono focus:outline-none focus:border-red-400"
                  >
                    {GALVANIC_METALS.map((m, idx) => (
                      <option key={m.id} value={idx}>
                        {m.name} [{m.e0 > 0 ? `+${m.e0}` : m.e0}V]
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-slate-400 leading-relaxed">{anodeMetal.description}</p>

                  <div className="pt-2 border-t border-[#162032] flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">Exposed Anode Area:</span>
                    <div className="flex items-center gap-1">
                      <input aria-label="Exposed Anode Area (cm²)"
                        type="number"
                        inputMode="decimal"
                        value={anodeArea}
                        onChange={(e) => setAnodeArea(Math.max(0.1, parseFloat(e.target.value) || 0.1))}
                        className="w-20 px-2 py-0.5 bg-[#0c1322] border border-[#1e2d46] rounded text-right text-white font-bold"
                      />
                      <span className="text-[10px] text-slate-400">cm²</span>
                    </div>
                  </div>
                </div>

                {/* Cathodic Metal */}
                <div className="p-4 bg-[#050810] rounded-xl border border-sky-500/40 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-sky-400 font-mono flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-sky-500"></span>
                      CATHODE (Protected Metal)
                    </span>
                    <span className="text-[11px] font-mono text-sky-300 font-bold">
                      {cathodeMetal.e0 > 0 ? `+${cathodeMetal.e0}` : cathodeMetal.e0} V vs SHE
                    </span>
                  </div>
                  <select aria-label="CATHODE (Protected Metal)"
                    value={cathodeIdx}
                    onChange={(e) => setCathodeIdx(parseInt(e.target.value))}
                    className="w-full bg-[#0c1322] border border-[#1e2d46] rounded-lg p-2 text-xs text-white font-mono focus:outline-none focus:border-sky-400"
                  >
                    {GALVANIC_METALS.map((m, idx) => (
                      <option key={m.id} value={idx}>
                        {m.name} [{m.e0 > 0 ? `+${m.e0}` : m.e0}V]
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-slate-400 leading-relaxed">{cathodeMetal.description}</p>

                  <div className="pt-2 border-t border-[#162032] flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">Exposed Cathode Area:</span>
                    <div className="flex items-center gap-1">
                      <input aria-label="Exposed Cathode Area (cm²)"
                        type="number"
                        inputMode="decimal"
                        value={cathodeArea}
                        onChange={(e) => setCathodeArea(Math.max(0.1, parseFloat(e.target.value) || 0.1))}
                        className="w-20 px-2 py-0.5 bg-[#0c1322] border border-[#1e2d46] rounded text-right text-white font-bold"
                      />
                      <span className="text-[10px] text-slate-400">cm²</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Environmental Parameters */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div className="space-y-1.5">
                  <label className="text-xs font-mono text-slate-300">Electrolyte Environment:</label>
                  <select aria-label="Electrolyte Environment"
                    value={electrolyte}
                    onChange={(e) => setElectrolyte(e.target.value as any)}
                    className="w-full bg-[#0c1322] border border-[#1e2d46] rounded-lg p-2 text-xs text-white font-mono focus:outline-none focus:border-amber-400"
                  >
                    <option value="marine">Seawater (3.5% NaCl Chloride, High Conductance)</option>
                    <option value="acidic">Acid Rain / Salt Spray Fog (pH 3.2 Extreme)</option>
                    <option value="industrial">Industrial Chemical Atmosphere (SO₂ / NOx)</option>
                    <option value="soil">Underground Marine Soil (Moist Aerated)</option>
                    <option value="tapwater">Treated Fresh Tap Water (Low Ionic)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300">Uncoupled Base Current Density:</span>
                    <span className="text-amber-400 font-bold">{currentDensity} mA/cm²</span>
                  </div>
                  <input aria-label="Uncoupled Base Current Density (mA/cm²)"
                    type="range"
                    min="0.1"
                    max="10.0"
                    step="0.1"
                    value={currentDensity}
                    onChange={(e) => setCurrentDensity(parseFloat(e.target.value))}
                    className="w-full accent-amber-400 cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                    <span>0.1 mA (Passivated)</span>
                    <span>10.0 mA (Uninhibited)</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Results & Faraday Quantitative Output */}
          <div className="lg:col-span-5 space-y-6">
            <div className="bg-[#090e18] p-5 rounded-xl border border-[#162032] space-y-5">
              <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                  <Activity className="w-4 h-4 text-amber-400" />
                  <span>Faraday Penetration & Risk Assessment</span>
                </h3>
              </div>

              {/* Driving EMF */}
              <div className="p-4 bg-[#050810] rounded-xl border border-[#162032] space-y-3">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400">Driving Cell Potential (ΔE°):</span>
                  <span className="text-amber-400 font-bold text-sm font-mono">{potentialDiff.toFixed(2)} V</span>
                </div>
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400">Area Ratio (Cathode : Anode):</span>
                  <span className={`font-bold ${areaRatio > 5 ? "text-red-400" : "text-sky-300"}`}>
                    {areaRatio.toFixed(1)} : 1
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400">Accelerated Galvanic Current:</span>
                  <span className="text-white font-bold font-mono">{(effectiveIcorr_uA / 1000).toFixed(2)} mA/cm²</span>
                </div>
              </div>

              {/* Penetration Gauge */}
              <div className="p-4 bg-[#050810] rounded-xl border border-[#162032] text-center space-y-2">
                <span className="text-[11px] text-slate-400 font-mono uppercase tracking-wider block">
                  Annual Penetration Depth (Faraday's Law)
                </span>
                <div className="text-3xl font-extrabold font-mono text-red-400 tracking-tight">
                  {penetrationRateMmYear.toFixed(3)} <span className="text-base font-normal text-slate-400">mm / yr</span>
                </div>
                <div className="text-xs font-mono text-orange-300">
                  ≈ {penetrationMpy.toFixed(1)} mils/year (mpy) | Mass loss: {massLossGramsPerDay.toFixed(2)} g / day
                </div>

                <div className="pt-2">
                  {penetrationRateMmYear > 2.0 ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-500/20 text-red-300 border border-red-500/40 text-xs font-mono font-bold">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      EXTREME CATASTROPHIC PENETRATION RISK
                    </span>
                  ) : penetrationRateMmYear > 0.5 ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-mono font-bold">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      MODERATE GALVANIC ACCELERATION
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-mono font-bold">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      ACCEPTABLE / PASSIVATED JOINT
                    </span>
                  )}
                </div>
              </div>

              {/* Recommended Mitigation Strategies */}
              <div className="p-3.5 bg-[#050810] rounded-xl border border-[#162032] space-y-2">
                <span className="text-[11px] font-mono text-slate-300 uppercase tracking-wider block font-bold">
                  Recommended Engineering Mitigations for {anodeMetal.name}:
                </span>
                <ul className="space-y-1 text-xs text-slate-400 font-mono">
                  {anodeMetal.recommendedCoatings.map((c, idx) => (
                    <li key={idx} className="flex items-center gap-2 text-slate-300">
                      <span className="text-amber-400">•</span>
                      <span>{c}</span>
                    </li>
                  ))}
                  <li className="flex items-center gap-2 text-sky-300">
                    <span>•</span>
                    <span>Use non-conductive dielectric sleeves/washers to break electrical contact.</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 2. PITTING RESISTANCE (PREN & CPT)                        */}
      {/* ======================================================== */}
      {activeTab === "pren" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 space-y-6">
            <div className="bg-[#090e18] p-5 rounded-xl border border-[#162032] space-y-5">
              <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-sky-400" />
                  <span>Pitting Resistance Equivalent Number (PREN)</span>
                </h3>
                <span className="text-[11px] text-slate-400 font-mono">ISO 15156 / NACE MR0175</span>
              </div>

              <p className="text-xs text-slate-400 leading-relaxed font-mono">
                Formula: <span className="text-sky-300 font-bold">PREN = %Cr + 3.3(%Mo + 0.5%W) + 16(%N)</span>. Predicts the alloy's ability to resist localized breakdown of its protective Cr₂O₃ passive oxide in chloride environments.
              </p>

              {/* Elemental Composition Sliders & Inputs */}
              <div className="space-y-4">
                {/* Cr */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300">Chromium (%Cr):</span>
                    <span className="text-sky-300 font-bold">{cr.toFixed(1)} wt%</span>
                  </div>
                  <input aria-label="Chromium (%Cr)"
                    type="range"
                    min="10.0"
                    max="32.0"
                    step="0.1"
                    value={cr}
                    onChange={(e) => setCr(parseFloat(e.target.value))}
                    className="w-full accent-sky-400 cursor-pointer"
                  />
                </div>

                {/* Mo */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300">Molybdenum (%Mo):</span>
                    <span className="text-sky-300 font-bold">{mo.toFixed(1)} wt%</span>
                  </div>
                  <input aria-label="Molybdenum (%Mo)"
                    type="range"
                    min="0.0"
                    max="10.0"
                    step="0.1"
                    value={mo}
                    onChange={(e) => setMo(parseFloat(e.target.value))}
                    className="w-full accent-sky-400 cursor-pointer"
                  />
                </div>

                {/* W */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300">Tungsten (%W):</span>
                    <span className="text-sky-300 font-bold">{w.toFixed(1)} wt%</span>
                  </div>
                  <input aria-label="Tungsten (%W)"
                    type="range"
                    min="0.0"
                    max="6.0"
                    step="0.1"
                    value={w}
                    onChange={(e) => setW(parseFloat(e.target.value))}
                    className="w-full accent-sky-400 cursor-pointer"
                  />
                </div>

                {/* N */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300">Nitrogen (%N):</span>
                    <span className="text-sky-300 font-bold">{n.toFixed(2)} wt%</span>
                  </div>
                  <input aria-label="Nitrogen (%N)"
                    type="range"
                    min="0.0"
                    max="0.60"
                    step="0.01"
                    value={n}
                    onChange={(e) => setN(parseFloat(e.target.value))}
                    className="w-full accent-sky-400 cursor-pointer"
                  />
                </div>
              </div>

              {/* Standard Presets */}
              <div className="pt-2">
                <span className="text-[11px] text-slate-400 font-mono block mb-1.5">Industry Standard Alloy Presets:</span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
                  <button
                    type="button"
                    onClick={() => { setCr(18.0); setMo(0.2); setW(0); setN(0.04); }}
                    className="p-2 rounded bg-[#050810] hover:bg-sky-500/20 text-slate-300 border border-[#162032]"
                  >
                    AISI 304 (18/8)
                  </button>
                  <button
                    type="button"
                    onClick={() => { setCr(17.5); setMo(2.5); setW(0); setN(0.06); }}
                    className="p-2 rounded bg-[#050810] hover:bg-sky-500/20 text-slate-300 border border-[#162032]"
                  >
                    AISI 316L
                  </button>
                  <button
                    type="button"
                    onClick={() => { setCr(22.0); setMo(3.1); setW(0); setN(0.18); }}
                    className="p-2 rounded bg-[#050810] hover:bg-sky-500/20 text-slate-300 border border-[#162032]"
                  >
                    Duplex 2205
                  </button>
                  <button
                    type="button"
                    onClick={() => { setCr(25.0); setMo(3.8); setW(0.6); setN(0.28); }}
                    className="p-2 rounded bg-[#050810] hover:bg-sky-500/20 text-slate-300 border border-[#162032]"
                  >
                    Super Duplex 2507
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Diagnostic Prediction Cards */}
          <div className="lg:col-span-5 space-y-6">
            <div className="bg-[#090e18] p-5 rounded-xl border border-[#162032] space-y-5">
              <div className="flex items-center justify-between border-b border-[#162032] pb-3">
                <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <span>Pitting Immunity & Critical Pitting Temp</span>
                </h3>
              </div>

              {/* Big Score Card */}
              <div className="p-5 bg-[#050810] rounded-xl border border-[#162032] text-center space-y-2">
                <span className="text-xs text-slate-400 font-mono uppercase tracking-wider block">
                  Calculated PREN Index
                </span>
                <div className="text-4xl font-black font-mono text-sky-400 tracking-tight">
                  {prenScore.toFixed(1)}
                </div>

                <div className="pt-2">
                  {prenScore >= 40 ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-mono font-bold">
                      <CheckCircle2 className="w-4 h-4" />
                      Super Duplex (PREN ≥ 40) - Offshore Seawater Immune
                    </span>
                  ) : prenScore >= 32 ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-500/20 text-sky-300 border border-sky-500/40 text-xs font-mono font-bold">
                      <CheckCircle2 className="w-4 h-4" />
                      Standard Duplex - High Marine Chloride Resistance
                    </span>
                  ) : prenScore >= 24 ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-mono font-bold">
                      <AlertTriangle className="w-4 h-4" />
                      Marine Crevice Pitting Risk (Warm Seawater &gt;25°C)
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-500/20 text-red-400 border border-red-500/40 text-xs font-mono font-bold">
                      <AlertTriangle className="w-4 h-4" />
                      High Risk of Severe Pitting & Chloride SCC
                    </span>
                  )}
                </div>
              </div>

              {/* Critical Pitting Temp (CPT) Estimate */}
              <div className="p-4 bg-[#050810] rounded-xl border border-[#162032] space-y-2.5">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300 flex items-center gap-1.5">
                    <Flame className="w-3.5 h-3.5 text-amber-400" />
                    <span>Est. Critical Pitting Temp (CPT):</span>
                  </span>
                  <span className="text-emerald-400 font-bold text-sm">~{estimatedCPT_Celsius.toFixed(1)} °C</span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed font-mono">
                  Above {estimatedCPT_Celsius.toFixed(1)}°C in aerated 6% FeCl₃, passive oxide undergoes spontaneous breakdown and autocatalytic pit nucleation.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 3. TAFEL POLARIZATION & STERN-GEARY KINETICS             */}
      {/* ======================================================== */}
      {activeTab === "polarization" && (
        <div className="pt-2">
          <TafelPolarizationLab />
        </div>
      )}

      {/* ======================================================== */}
      {/* 4. REAL-TIME OCP & ASTM G59 LPR TRANSIENT STUDIO        */}
      {/* ======================================================== */}
      {activeTab === "ocp-g59" && (
        <div className="pt-2">
          
        </div>
      )}

      {/* ======================================================== */}
      {/* 5. DYNAMIC POURBAIX (E-pH-T-SALINITY) PHASE GENERATOR   */}
      {/* ======================================================== */}
      {activeTab === "pourbaix" && (
        <div className="pt-2">
          <DynamicPourbaixStudio />
        </div>
      )}

      {/* ======================================================== */}
      {/* 6. CORROSION EIS KINETICS & COATING DEGRADATION STUDIO   */}
      {/* ======================================================== */}
      {activeTab === "corrosion-eis" && (
        <div className="pt-2">
          <CorrosionEISKineticsStudio />
        </div>
      )}
    </div>
  );
}



