import React, { useState, useMemo, useRef, useEffect } from "react";
import {
  Compass,
  Layers,
  Thermometer,
  Percent,
  Info,
  Sliders,
  Sparkles,
  RefreshCw,
  Eye,
  Activity,
  ArrowRight,
  BookOpen,
  Atom,
  Flame,
} from "lucide-react";
import { CALPHADThermodynamicsLab } from "./CALPHADThermodynamicsLab";

export interface PhaseRegion {
  id: string;
  name: string;
  shortName: string;
  phases: string[];
  crystalStructures: string;
  description: string;
  path: string; // SVG path d
  color: string;
  hoverColor: string;
  cMin: number;
  cMax: number;
  tMin: number;
  tMax: number;
}

export interface InvariantPoint {
  name: string;
  reaction: string;
  temp_C: number;
  comp_wt_pct: number;
  type: "Peritectic" | "Eutectic" | "Eutectoid";
  equation: string;
}

// Preset Alloy Compositions for Instant Probing
export interface FeCAlloyPreset {
  name: string;
  composition_wt_pct_C: number;
  class: "Hypoeutectoid Steel" | "Eutectoid Steel" | "Hypereutectoid Steel" | "Hypoeutectic Cast Iron" | "Eutectic Cast Iron" | "Hypereutectic Cast Iron";
  typicalApplications: string;
  expectedRoomTempMicrostructure: string;
}

export const FEC_ALLOY_PRESETS: FeCAlloyPreset[] = [
  {
    name: "AISI 1008 Low Carbon / IF Steel",
    composition_wt_pct_C: 0.08,
    class: "Hypoeutectoid Steel",
    typicalApplications: "Automotive deep-drawing body panels, appliance sheets",
    expectedRoomTempMicrostructure: "90% Primary Equiaxed Ferrite (α) + 10% Fine Pearlite colonies",
  },
  {
    name: "AISI 1018 Mild Structural Steel",
    composition_wt_pct_C: 0.18,
    class: "Hypoeutectoid Steel",
    typicalApplications: "Pins, shafts, structural bolts, weldments",
    expectedRoomTempMicrostructure: "76% Proeutectoid Ferrite (α) + 24% Pearlite (α + Fe3C)",
  },
  {
    name: "AISI 1045 Medium Carbon Machinery Steel",
    composition_wt_pct_C: 0.45,
    class: "Hypoeutectoid Steel",
    typicalApplications: "Automotive crankshafts, gears, axles, spindles",
    expectedRoomTempMicrostructure: "41% Proeutectoid Ferrite (α) + 59% Pearlite (α + Fe3C)",
  },
  {
    name: "AISI 1080 Eutectoid Rail & Wire Steel",
    composition_wt_pct_C: 0.76,
    class: "Eutectoid Steel",
    typicalApplications: "Railroad tracks, music wire, heavy springs",
    expectedRoomTempMicrostructure: "100% Fully Lamellar Pearlite (α + Fe3C alternating plates)",
  },
  {
    name: "AISI 1095 High Carbon Spring & Tool Steel",
    composition_wt_pct_C: 0.95,
    class: "Hypereutectoid Steel",
    typicalApplications: "Knives, saw blades, high-strength coil springs",
    expectedRoomTempMicrostructure: "97% Lamellar Pearlite + 3% Intergranular Proeutectoid Cementite Network",
  },
  {
    name: "AISI 52100 High-Carbon Bearing Steel",
    composition_wt_pct_C: 1.00,
    class: "Hypereutectoid Steel",
    typicalApplications: "Anti-friction ball & roller bearings, fuel injectors",
    expectedRoomTempMicrostructure: "Pearlite matrix with proeutectoid secondary cementite boundary networks",
  },
  {
    name: "Class 30 Gray Cast Iron (Hypoeutectic)",
    composition_wt_pct_C: 3.20,
    class: "Hypoeutectic Cast Iron",
    typicalApplications: "Engine blocks, brake discs, machine tool beds",
    expectedRoomTempMicrostructure: "Transformed Ledeburite + Pearlite + Graphite Flakes",
  },
  {
    name: "Eutectic White Cast Iron (Ledeburite)",
    composition_wt_pct_C: 4.30,
    class: "Eutectic Cast Iron",
    typicalApplications: "Extremely wear-resistant slurry pumps, mill liners",
    expectedRoomTempMicrostructure: "100% Transformed Ledeburite (Pearlite + Cementite eutectic structure)",
  },
  {
    name: "Hypereutectic White Cast Iron",
    composition_wt_pct_C: 5.10,
    class: "Hypereutectic Cast Iron",
    typicalApplications: "High-stress pulverizer rings, dredge pumps",
    expectedRoomTempMicrostructure: "Large Primary Cementite (Fe3C) needle plates in a Ledeburite matrix",
  },
];

export const INVARIANT_REACTIONS: InvariantPoint[] = [
  {
    name: "Peritectic Reaction",
    reaction: "Liquid (0.51% C) + δ-Ferrite (0.09% C) ➔ γ-Austenite (0.18% C)",
    temp_C: 1493,
    comp_wt_pct: 0.18,
    type: "Peritectic",
    equation: "L(0.51% C) + δ(0.09% C) ➔ γ(0.18% C) at 1493°C",
  },
  {
    name: "Eutectic Reaction (Ledeburite)",
    reaction: "Liquid (4.30% C) ➔ γ-Austenite (2.14% C) + Cementite (6.67% C)",
    temp_C: 1147,
    comp_wt_pct: 4.30,
    type: "Eutectic",
    equation: "L(4.30% C) ➔ γ(2.14% C) + Fe3C(6.67% C) [Ledeburite] at 1147°C",
  },
  {
    name: "Eutectoid Reaction (Pearlite)",
    reaction: "γ-Austenite (0.76% C) ➔ α-Ferrite (0.022% C) + Cementite (6.67% C)",
    temp_C: 727,
    comp_wt_pct: 0.76,
    type: "Eutectoid",
    equation: "γ(0.76% C) ➔ α(0.022% C) + Fe3C(6.67% C) [Pearlite] at 727°C",
  },
];

export const PhaseDiagramViewer: React.FC = () => {
  // Mode switcher: CALPHAD Gibbs Engine vs Fe-C Phase Diagram
  const [activeView, setActiveView] = useState<"calphad_solver" | "fe_c_diagram">("calphad_solver");

  // Active alloy composition & temperature probe
  const [compositionC, setCompositionC] = useState<number>(0.45); // wt% C
  const [temperatureC, setTemperatureC] = useState<number>(850); // °C
  const [hoveredRegion, setHoveredRegion] = useState<string | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<string>("AISI 1045 Medium Carbon Machinery Steel");
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [diagramMode, setDiagramMode] = useState<"Fe-C" | "Al-Cu" | "Ti-Al">("Fe-C");

  const svgRef = useRef<SVGSVGElement | null>(null);

  // Coordinate mapping for Fe-C (0 to 6.67 wt% C, 400 to 1600 °C)
  // SVG Canvas viewBox: 0 0 900 600 with margins
  const margin = { top: 40, right: 40, bottom: 60, left: 70 };
  const graphWidth = 900 - margin.left - margin.right; // 790
  const graphHeight = 600 - margin.top - margin.bottom; // 500

  const cToX = (c: number) => {
    const clampedC = Math.max(0, Math.min(6.67, c));
    return margin.left + (clampedC / 6.67) * graphWidth;
  };

  const tToY = (t: number) => {
    const minT = 400;
    const maxT = 1600;
    const clampedT = Math.max(minT, Math.min(maxT, t));
    return margin.top + graphHeight - ((clampedT - minT) / (maxT - minT)) * graphHeight;
  };

  const xToC = (x: number) => {
    const relX = x - margin.left;
    const c = (relX / graphWidth) * 6.67;
    return Math.max(0, Math.min(6.67, parseFloat(c.toFixed(2))));
  };

  const yToT = (y: number) => {
    const relY = y - margin.top;
    const frac = 1 - relY / graphHeight;
    const t = 400 + frac * (1600 - 400);
    return Math.max(400, Math.min(1600, Math.round(t)));
  };

  // SVG Mouse Handler for interactive click/drag probe
  const handleSvgPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    setIsDragging(true);
    updateProbeFromEvent(e);
  };

  const handleSvgPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (isDragging) {
      updateProbeFromEvent(e);
    }
  };

  const handleSvgPointerUp = () => {
    setIsDragging(false);
  };

  const updateProbeFromEvent = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    // Scale to SVG viewBox (900x600)
    const scaleX = 900 / rect.width;
    const scaleY = 600 / rect.height;

    const svgX = clientX * scaleX;
    const svgY = clientY * scaleY;

    if (svgX >= margin.left && svgX <= margin.left + graphWidth && svgY >= margin.top && svgY <= margin.top + graphHeight) {
      setCompositionC(xToC(svgX));
      setTemperatureC(yToT(svgY));
    }
  };

  // Detailed Phase determination & Lever Rule calculations at current (compositionC, temperatureC)
  const probeState = useMemo(() => {
    const C = compositionC;
    const T = temperatureC;

    // Helper functions for boundary lines
    // A3 line: from (0.022, 727) to (0, 912)
    const getA3 = (c: number) => {
      if (c <= 0.022) return 912 - ((912 - 727) / 0.022) * c;
      if (c <= 0.76) return 912 - ((912 - 727) / 0.76) * c;
      return 727;
    };

    // Acm line: from (0.76, 727) to (2.14, 1147)
    const getAcm = (c: number) => {
      if (c < 0.76 || c > 2.14) return 727;
      return 727 + ((1147 - 727) / (2.14 - 0.76)) * (c - 0.76);
    };

    // Solidus: 1493°C to 1147°C (0.18 to 2.14 wt% C)
    const getAusteniteSolidus = (c: number) => {
      if (c < 0.18) return 1493;
      if (c <= 2.14) return 1493 - ((1493 - 1147) / (2.14 - 0.18)) * (c - 0.18);
      return 1147;
    };

    // Liquidus: 1538°C to 1147°C (0 to 4.30 wt% C), and 1147°C to 1227°C (4.30 to 6.67 wt% C)
    const getLiquidus = (c: number) => {
      if (c <= 0.51) return 1538 - ((1538 - 1493) / 0.51) * c;
      if (c <= 4.30) return 1493 - ((1493 - 1147) / (4.30 - 0.51)) * (c - 0.51);
      return 1147 + ((1227 - 1147) / (6.67 - 4.30)) * (c - 4.30);
    };

    const T_liquidus = getLiquidus(C);
    const T_solidus = C <= 2.14 ? getAusteniteSolidus(C) : 1147;
    const T_A3 = getA3(C);
    const T_Acm = getAcm(C);

    let regionName = "";
    let phasesPresent: { name: string; formula: string; fractionPct: number; compositionC: number; crystal: string }[] = [];
    let stateCategory = "";
    let primaryPhase = "";
    let secondaryPhase = "";
    let equilibriumDescription = "";

    // 1. Above Liquidus: Pure Liquid
    if (T >= T_liquidus) {
      regionName = "Liquid (L)";
      stateCategory = "Homogeneous Liquid Melt";
      phasesPresent = [{ name: "Liquid Solution", formula: "L", fractionPct: 100, compositionC: C, crystal: "Amorphous Melt" }];
      equilibriumDescription = "Completely molten liquid alloy containing fully dissolved carbon solutes.";
    }
    // 2. Delta Ferrite region (High temp low carbon)
    else if (T > 1394 && C <= 0.51 && T <= 1538) {
      if (C <= 0.09) {
        regionName = "δ-Ferrite";
        stateCategory = "High-Temperature Solid Solution";
        phasesPresent = [{ name: "Delta Ferrite", formula: "δ", fractionPct: 100, compositionC: C, crystal: "BCC (High Temp)" }];
        equilibriumDescription = "High-temperature body-centered cubic delta-iron solid solution.";
      } else {
        regionName = "Liquid + δ-Ferrite";
        stateCategory = "Semi-Solid Mushy Zone";
        // Lever rule between delta (0.09%) and liquid (0.51%)
        const f_L = Math.max(0, Math.min(1, (C - 0.09) / (0.51 - 0.09)));
        const f_delta = 1 - f_L;
        phasesPresent = [
          { name: "Delta Ferrite", formula: "δ", fractionPct: parseFloat((f_delta * 100).toFixed(1)), compositionC: 0.09, crystal: "BCC" },
          { name: "Liquid Melt", formula: "L", fractionPct: parseFloat((f_L * 100).toFixed(1)), compositionC: 0.51, crystal: "Amorphous" },
        ];
        equilibriumDescription = "Peritectic mushy zone with coexisting delta ferrite dendrites in liquid melt.";
      }
    }
    // 3. Liquid + Austenite Mushy Zone (Between Solidus and Liquidus, C <= 4.30%)
    else if (T < T_liquidus && T >= 1147 && C <= 4.30) {
      regionName = "Liquid + γ-Austenite";
      stateCategory = "Two-Phase Solidification Zone";
      // Approximate tie-line endpoints
      const c_gamma = Math.max(0.18, Math.min(2.14, 0.18 + ((2.14 - 0.18) * (1493 - T)) / (1493 - 1147)));
      const c_liq = Math.max(0.51, Math.min(4.30, 0.51 + ((4.30 - 0.51) * (1493 - T)) / (1493 - 1147)));
      const f_L = Math.max(0, Math.min(1, (C - c_gamma) / (c_liq - c_gamma)));
      const f_gamma = 1 - f_L;
      phasesPresent = [
        { name: "Austenite", formula: "γ", fractionPct: parseFloat((f_gamma * 100).toFixed(1)), compositionC: parseFloat(c_gamma.toFixed(2)), crystal: "FCC" },
        { name: "Liquid Melt", formula: "L", fractionPct: parseFloat((f_L * 100).toFixed(1)), compositionC: parseFloat(c_liq.toFixed(2)), crystal: "Amorphous" },
      ];
      equilibriumDescription = "Solidifying austenite dendrites suspended within carbon-enriched liquid melt.";
    }
    // 4. Liquid + Cementite (C > 4.30%, T >= 1147)
    else if (T < T_liquidus && T >= 1147 && C > 4.30) {
      regionName = "Liquid + Primary Cementite (Fe3C)";
      stateCategory = "Hypereutectic Solidification";
      const c_liq = Math.max(4.30, Math.min(6.67, 4.30 + ((6.67 - 4.30) * (T - 1147)) / (1227 - 1147)));
      const f_cem = Math.max(0, Math.min(1, (C - c_liq) / (6.67 - c_liq)));
      const f_liq = 1 - f_cem;
      phasesPresent = [
        { name: "Primary Cementite", formula: "Fe3C", fractionPct: parseFloat((f_cem * 100).toFixed(1)), compositionC: 6.67, crystal: "Orthorhombic" },
        { name: "Liquid Melt", formula: "L", fractionPct: parseFloat((f_liq * 100).toFixed(1)), compositionC: parseFloat(c_liq.toFixed(2)), crystal: "Amorphous" },
      ];
      equilibriumDescription = "Hard primary cementite needles precipitating directly from cooling hypereutectic liquid.";
    }
    // 5. Single Phase Austenite (FCC gamma field)
    else if (T >= 727 && T < 1493 && C <= 2.14 && T >= (C <= 0.76 ? T_A3 : T_Acm)) {
      regionName = "γ-Austenite (FCC)";
      stateCategory = "Single-Phase Solid Solution";
      phasesPresent = [{ name: "Austenite", formula: "γ", fractionPct: 100, compositionC: C, crystal: "FCC (Face-Centered Cubic)" }];
      equilibriumDescription = "Ductile, non-magnetic face-centered cubic austenite solid solution. Ideal for hot forging and heat treatment austenitization.";
    }
    // 6. Ferrite + Austenite (Intercritical region, C <= 0.76%, 727°C <= T < A3)
    else if (T >= 727 && C <= 0.76 && T < T_A3) {
      regionName = "α-Ferrite + γ-Austenite";
      stateCategory = "Intercritical Dual-Phase Zone";
      // Alpha boundary at T: 0.022% at 727, 0% at 912
      const c_alpha = Math.max(0, 0.022 * ((912 - T) / (912 - 727)));
      // Gamma boundary A3 at T
      const c_gamma = Math.max(0.022, Math.min(0.76, 0.76 * ((912 - T) / (912 - 727))));
      const f_gamma = Math.max(0, Math.min(1, (C - c_alpha) / Math.max(0.001, c_gamma - c_alpha)));
      const f_alpha = 1 - f_gamma;
      phasesPresent = [
        { name: "Proeutectoid Ferrite", formula: "α", fractionPct: parseFloat((f_alpha * 100).toFixed(1)), compositionC: parseFloat(c_alpha.toFixed(3)), crystal: "BCC" },
        { name: "Austenite", formula: "γ", fractionPct: parseFloat((f_gamma * 100).toFixed(1)), compositionC: parseFloat(c_gamma.toFixed(2)), crystal: "FCC" },
      ];
      equilibriumDescription = "Intercritical two-phase mixture: proeutectoid ferrite grains nucleating along austenite grain boundaries.";
    }
    // 7. Austenite + Cementite (727°C <= T < 1147°C, 0.76% < C <= 6.67%)
    else if (T >= 727 && T <= 1147 && C > 0.76) {
      regionName = "γ-Austenite + Cementite (Fe3C)";
      stateCategory = "Two-Phase Solid Mixture";
      // Tie line between Acm (c_gamma) and Fe3C (6.67%)
      const c_gamma = Math.max(0.76, Math.min(2.14, 0.76 + ((2.14 - 0.76) * (T - 727)) / (1147 - 727)));
      const f_cem = Math.max(0, Math.min(1, (C - c_gamma) / (6.67 - c_gamma)));
      const f_gamma = 1 - f_cem;
      phasesPresent = [
        { name: "Austenite", formula: "γ", fractionPct: parseFloat((f_gamma * 100).toFixed(1)), compositionC: parseFloat(c_gamma.toFixed(2)), crystal: "FCC" },
        { name: "Cementite", formula: "Fe3C", fractionPct: parseFloat((f_cem * 100).toFixed(1)), compositionC: 6.67, crystal: "Orthorhombic" },
      ];
      equilibriumDescription = "Austenite matrix with grain-boundary proeutectoid cementite networks (in hypereutectoid steels) or transformed ledeburite (in cast irons).";
    }
    // 8. Below A1 (727°C): Ferrite (alpha) + Cementite (Fe3C)
    else {
      // Room temp / Sub-critical
      const c_alpha = 0.005; // negligible at room temp
      const c_cem = 6.67;
      const f_cem = Math.max(0, Math.min(1, (C - c_alpha) / (c_cem - c_alpha)));
      const f_alpha = 1 - f_cem;

      if (C <= 0.76) {
        regionName = "α-Ferrite + Pearlite (α + Fe3C)";
        stateCategory = "Hypoeutectoid Microstructure";
        // Proeutectoid ferrite fraction: (0.76 - C) / (0.76 - 0.022)
        const f_pro_alpha = Math.max(0, Math.min(1, (0.76 - C) / (0.76 - 0.022)));
        const f_pearlite = 1 - f_pro_alpha;
        phasesPresent = [
          { name: "Total Ferrite (α)", formula: "α (BCC)", fractionPct: parseFloat((f_alpha * 100).toFixed(1)), compositionC: 0.005, crystal: "BCC" },
          { name: "Total Cementite (Fe3C)", formula: "Fe3C", fractionPct: parseFloat((f_cem * 100).toFixed(1)), compositionC: 6.67, crystal: "Orthorhombic" },
        ];
        equilibriumDescription = `Hypoeutectoid equilibrium structure consisting of ~${(f_pro_alpha * 100).toFixed(0)}% Proeutectoid Ferrite and ~${(f_pearlite * 100).toFixed(0)}% Lamellar Pearlite.`;
      } else if (C <= 2.14) {
        regionName = "Pearlite + Secondary Cementite (Fe3C)";
        stateCategory = "Hypereutectoid Microstructure";
        const f_pro_cem = Math.max(0, Math.min(1, (C - 0.76) / (6.67 - 0.76)));
        const f_pearlite = 1 - f_pro_cem;
        phasesPresent = [
          { name: "Total Ferrite (α)", formula: "α (BCC)", fractionPct: parseFloat((f_alpha * 100).toFixed(1)), compositionC: 0.005, crystal: "BCC" },
          { name: "Total Cementite (Fe3C)", formula: "Fe3C", fractionPct: parseFloat((f_cem * 100).toFixed(1)), compositionC: 6.67, crystal: "Orthorhombic" },
        ];
        equilibriumDescription = `Hypereutectoid structure comprising ~${(f_pearlite * 100).toFixed(0)}% Pearlite matrix bounded by ~${(f_pro_cem * 100).toFixed(1)}% brittle grain boundary proeutectoid cementite.`;
      } else {
        regionName = "Transformed Ledeburite + Cementite / Cast Iron";
        stateCategory = "Cast Iron Microstructure";
        phasesPresent = [
          { name: "Total Ferrite (α)", formula: "α (BCC)", fractionPct: parseFloat((f_alpha * 100).toFixed(1)), compositionC: 0.005, crystal: "BCC" },
          { name: "Total Cementite (Fe3C)", formula: "Fe3C", fractionPct: parseFloat((f_cem * 100).toFixed(1)), compositionC: 6.67, crystal: "Orthorhombic" },
        ];
        equilibriumDescription = `High-carbon cast iron structure containing transformed ledeburite eutectic colonies and massive cementite / graphite morphology.`;
      }
    }

    return {
      compositionC: C,
      temperatureC: T,
      regionName,
      stateCategory,
      phasesPresent,
      equilibriumDescription,
      liquidus: T_liquidus,
      solidus: T_solidus,
    };
  }, [compositionC, temperatureC]);

  const handleSelectPreset = (presetName: string) => {
    setSelectedPreset(presetName);
    const pr = FEC_ALLOY_PRESETS.find((p) => p.name === presetName);
    if (pr) {
      setCompositionC(pr.composition_wt_pct_C);
    }
  };

  return (
    <div id="phase-diagram-viewer" className="space-y-6 animate-fadeIn">
      {/* Top View Switcher */}
      <div className="flex items-center justify-between p-2 bg-[#090e18] rounded-2xl border border-[#162032] flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveView("calphad_solver")}
            className={`px-4 py-2 rounded-xl text-xs font-bold font-mono transition-all flex items-center gap-2 cursor-pointer ${
              activeView === "calphad_solver"
                ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-[0_0_15px_rgba(139,92,246,0.3)] border border-violet-400/50"
                : "text-slate-400 hover:text-white bg-slate-900/60 border border-slate-800"
            }`}
          >
            <Atom className="w-4 h-4 text-violet-300" />
            <span>CALPHAD Gibbs Energy & Scheil Engine</span>
            <span className="px-1.5 py-0.5 rounded bg-violet-400/20 text-violet-200 text-[9px]">
              Multi-System
            </span>
          </button>

          <button
            onClick={() => setActiveView("fe_c_diagram")}
            className={`px-4 py-2 rounded-xl text-xs font-bold font-mono transition-all flex items-center gap-2 cursor-pointer ${
              activeView === "fe_c_diagram"
                ? "bg-gradient-to-r from-sky-600 to-cyan-600 text-white shadow-[0_0_15px_rgba(56,189,248,0.3)] border border-sky-400/50"
                : "text-slate-400 hover:text-white bg-slate-900/60 border border-slate-800"
            }`}
          >
            <Compass className="w-4 h-4 text-sky-300" />
            <span>Fe-Fe₃C Equilibrium Phase Explorer</span>
            <span className="px-1.5 py-0.5 rounded bg-sky-400/20 text-sky-200 text-[9px]">
              Lever Rule
            </span>
          </button>
        </div>

        <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400 pr-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Thermodynamic Solver: Online</span>
        </div>
      </div>

      {activeView === "calphad_solver" ? (
        <CALPHADThermodynamicsLab />
      ) : (
        <div className="space-y-6">
          {/* Header Banner */}
          <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-sky-400 font-mono text-[10px] font-semibold uppercase tracking-widest">
                <Compass className="w-3.5 h-3.5 text-sky-400" />
                <span>Thermodynamic Equilibrium Phase Diagram Explorer</span>
              </div>
              <h2 className="text-lg font-extrabold text-white tracking-tight mt-0.5 flex items-center gap-2">
                <span>Iron-Carbon (Fe-Fe₃C) Binary Equilibrium Diagram</span>
                <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 text-[10px] font-mono border border-sky-500/40 font-normal">
                  CALPHAD Standard
                </span>
              </h2>
              <p className="text-xs text-slate-400 font-mono mt-0.5 max-w-3xl">
                Interactive phase boundaries, lever rule phase fraction calculator, invariant reaction points (Peritectic, Eutectic, Eutectoid), and real-time alloy composition probing.
              </p>
            </div>

            {/* System & Alloy Quick Selector */}
            <div className="flex items-center gap-2 overflow-x-auto p-1 bg-[#050810] rounded-xl border border-[#162032]">
              <span className="text-[10px] font-mono text-slate-500 uppercase px-2 whitespace-nowrap">
                Alloy Presets:
              </span>
              {FEC_ALLOY_PRESETS.slice(0, 4).map((pr) => (
                <button
                  key={pr.name}
                  onClick={() => handleSelectPreset(pr.name)}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-mono font-bold transition whitespace-nowrap ${
                    compositionC === pr.composition_wt_pct_C
                      ? "bg-sky-500/20 border border-sky-400/60 text-sky-300 shadow-[0_0_10px_rgba(56,189,248,0.2)]"
                      : "text-slate-400 hover:text-white hover:bg-white/[0.04] border border-transparent"
                  }`}
                >
                  {pr.name.split(" ")[0]} {pr.name.split(" ")[1]} ({pr.composition_wt_pct_C}%)
                </button>
              ))}
            </div>
          </div>

          {/* Main Grid: Interactive Canvas (Left) + Thermodynamic Analysis & Lever Rule (Right) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Interactive SVG Phase Diagram */}
        <div className="lg:col-span-8 bg-[#090e18] p-5 rounded-2xl border border-[#162032] space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#162032] pb-3">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-sky-400" />
              <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider">
                Fe - Fe₃C Phase Space (0 – 6.67 wt% C)
              </h3>
            </div>
            <div className="text-xs font-mono text-slate-400 flex items-center gap-3">
              <span>Probe: <strong className="text-sky-300">{compositionC.toFixed(2)} wt% C</strong>, <strong className="text-amber-300">{temperatureC}°C</strong></span>
              <span className="text-[10px] px-2 py-0.5 rounded bg-[#050810] border border-[#162032] text-slate-400">
                Click or drag on chart
              </span>
            </div>
          </div>

          {/* SVG Diagram Canvas */}
          <div className="relative overflow-hidden rounded-xl bg-[#050810] border border-[#162032] select-none">
            <svg
              ref={svgRef}
              viewBox="0 0 900 600"
              className="w-full h-auto cursor-crosshair"
              onPointerDown={handleSvgPointerDown}
              onPointerMove={handleSvgPointerMove}
              onPointerUp={handleSvgPointerUp}
            >
              <defs>
                {/* Gradients for Regions */}
                <linearGradient id="liquidGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#ef4444" stopOpacity="0.15" />
                </linearGradient>
                <linearGradient id="austeniteGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.15" />
                </linearGradient>
                <linearGradient id="ferriteGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.15" />
                </linearGradient>
                <linearGradient id="pearliteGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.08" />
                </linearGradient>
                <linearGradient id="ledeburiteGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.08" />
                </linearGradient>
                <linearGradient id="mushyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.1" />
                </linearGradient>
              </defs>

              {/* Grid Lines */}
              {/* Temperature Horizontal Grids */}
              {[400, 600, 727, 800, 912, 1000, 1147, 1200, 1400, 1493, 1538].map((t) => (
                <g key={t}>
                  <line
                    x1={margin.left}
                    y1={tToY(t)}
                    x2={margin.left + graphWidth}
                    y2={tToY(t)}
                    stroke={t === 727 || t === 1147 || t === 1493 ? "#38bdf8" : "#162032"}
                    strokeDasharray={t === 727 || t === 1147 || t === 1493 ? "4,4" : "none"}
                    strokeWidth={t === 727 || t === 1147 || t === 1493 ? 1.5 : 1}
                  />
                  <text
                    x={margin.left - 8}
                    y={tToY(t) + 4}
                    textAnchor="end"
                    fill={t === 727 || t === 1147 || t === 1493 ? "#38bdf8" : "#64748b"}
                    fontSize="10"
                    fontFamily="monospace"
                  >
                    {t}°C
                  </text>
                </g>
              ))}

              {/* Carbon Composition Vertical Grids */}
              {[0, 0.022, 0.76, 1.0, 2.14, 3.0, 4.30, 5.0, 6.0, 6.67].map((c) => (
                <g key={c}>
                  <line
                    x1={cToX(c)}
                    y1={margin.top}
                    x2={cToX(c)}
                    y2={margin.top + graphHeight}
                    stroke={c === 0.76 || c === 2.14 || c === 4.30 ? "#38bdf8" : "#162032"}
                    strokeDasharray={c === 0.76 || c === 2.14 || c === 4.30 ? "4,4" : "none"}
                    strokeWidth={c === 0.76 || c === 2.14 || c === 4.30 ? 1.5 : 1}
                  />
                  <text
                    x={cToX(c)}
                    y={margin.top + graphHeight + 18}
                    textAnchor="middle"
                    fill={c === 0.76 || c === 2.14 || c === 4.30 ? "#38bdf8" : "#64748b"}
                    fontSize="10"
                    fontFamily="monospace"
                  >
                    {c}%
                  </text>
                </g>
              ))}

              {/* --- PHASE DOMAINS POLYGONS --- */}
              {/* 1. Liquid Domain (Top) */}
              <path
                d={`M ${cToX(0)} ${tToY(1538)}
                    L ${cToX(0.51)} ${tToY(1493)}
                    L ${cToX(4.30)} ${tToY(1147)}
                    L ${cToX(6.67)} ${tToY(1227)}
                    L ${cToX(6.67)} ${tToY(1600)}
                    L ${cToX(0)} ${tToY(1600)} Z`}
                fill="url(#liquidGrad)"
                stroke="#ef4444"
                strokeWidth="1.5"
                onMouseEnter={() => setHoveredRegion("Liquid (L)")}
                onMouseLeave={() => setHoveredRegion(null)}
              />

              {/* 2. Austenite (γ) Single Phase Field */}
              <path
                d={`M ${cToX(0)} ${tToY(912)}
                    L ${cToX(0.09)} ${tToY(1394)}
                    L ${cToX(0.18)} ${tToY(1493)}
                    L ${cToX(2.14)} ${tToY(1147)}
                    L ${cToX(0.76)} ${tToY(727)}
                    L ${cToX(0.022)} ${tToY(727)}
                    L ${cToX(0)} ${tToY(912)} Z`}
                fill="url(#austeniteGrad)"
                stroke="#06b6d4"
                strokeWidth="1.5"
                onMouseEnter={() => setHoveredRegion("γ-Austenite (FCC)")}
                onMouseLeave={() => setHoveredRegion(null)}
              />

              {/* 3. Liquid + Austenite Mushy Field */}
              <path
                d={`M ${cToX(0.18)} ${tToY(1493)}
                    L ${cToX(0.51)} ${tToY(1493)}
                    L ${cToX(4.30)} ${tToY(1147)}
                    L ${cToX(2.14)} ${tToY(1147)} Z`}
                fill="url(#mushyGrad)"
                stroke="#f59e0b"
                strokeWidth="1"
                onMouseEnter={() => setHoveredRegion("Liquid + γ-Austenite")}
                onMouseLeave={() => setHoveredRegion(null)}
              />

              {/* 4. Liquid + Fe3C Field */}
              <path
                d={`M ${cToX(4.30)} ${tToY(1147)}
                    L ${cToX(6.67)} ${tToY(1227)}
                    L ${cToX(6.67)} ${tToY(1147)} Z`}
                fill="url(#mushyGrad)"
                stroke="#f59e0b"
                strokeWidth="1"
                onMouseEnter={() => setHoveredRegion("Liquid + Primary Fe3C")}
                onMouseLeave={() => setHoveredRegion(null)}
              />

              {/* 5. Austenite + Cementite Field (Above 727°C, 0.76% to 6.67%) */}
              <path
                d={`M ${cToX(0.76)} ${tToY(727)}
                    L ${cToX(2.14)} ${tToY(1147)}
                    L ${cToX(6.67)} ${tToY(1147)}
                    L ${cToX(6.67)} ${tToY(727)} Z`}
                fill="url(#ledeburiteGrad)"
                stroke="#8b5cf6"
                strokeWidth="1"
                onMouseEnter={() => setHoveredRegion("γ-Austenite + Fe3C")}
                onMouseLeave={() => setHoveredRegion(null)}
              />

              {/* 6. Ferrite + Austenite Intercritical Field (727°C to 912°C, C <= 0.76%) */}
              <path
                d={`M ${cToX(0)} ${tToY(912)}
                    L ${cToX(0.76)} ${tToY(727)}
                    L ${cToX(0.022)} ${tToY(727)} Z`}
                fill="url(#ferriteGrad)"
                stroke="#10b981"
                strokeWidth="1"
                onMouseEnter={() => setHoveredRegion("α-Ferrite + γ-Austenite")}
                onMouseLeave={() => setHoveredRegion(null)}
              />

              {/* 7. Sub-critical Hypoeutectoid Field (Ferrite + Pearlite) */}
              <path
                d={`M ${cToX(0)} ${tToY(727)}
                    L ${cToX(0.76)} ${tToY(727)}
                    L ${cToX(0.76)} ${tToY(400)}
                    L ${cToX(0)} ${tToY(400)} Z`}
                fill="url(#pearliteGrad)"
                stroke="#3b82f6"
                strokeWidth="1"
                onMouseEnter={() => setHoveredRegion("α-Ferrite + Pearlite")}
                onMouseLeave={() => setHoveredRegion(null)}
              />

              {/* 8. Sub-critical Hypereutectoid Field (Pearlite + Fe3C) */}
              <path
                d={`M ${cToX(0.76)} ${tToY(727)}
                    L ${cToX(2.14)} ${tToY(727)}
                    L ${cToX(2.14)} ${tToY(400)}
                    L ${cToX(0.76)} ${tToY(400)} Z`}
                fill="url(#pearliteGrad)"
                stroke="#3b82f6"
                strokeWidth="1"
                onMouseEnter={() => setHoveredRegion("Pearlite + Secondary Fe3C")}
                onMouseLeave={() => setHoveredRegion(null)}
              />

              {/* 9. Sub-critical Cast Iron Field (Pearlite + Ledeburite + Fe3C) */}
              <path
                d={`M ${cToX(2.14)} ${tToY(727)}
                    L ${cToX(6.67)} ${tToY(727)}
                    L ${cToX(6.67)} ${tToY(400)}
                    L ${cToX(2.14)} ${tToY(400)} Z`}
                fill="url(#ledeburiteGrad)"
                stroke="#8b5cf6"
                strokeWidth="1"
                onMouseEnter={() => setHoveredRegion("Transformed Ledeburite + Fe3C")}
                onMouseLeave={() => setHoveredRegion(null)}
              />

              {/* Invariant Reaction Labels & Points */}
              {/* Peritectic Point (0.18%, 1493°C) */}
              <circle cx={cToX(0.18)} cy={tToY(1493)} r="4" fill="#38bdf8" stroke="#fff" strokeWidth="1.5" />
              <text x={cToX(0.18) + 8} y={tToY(1493) - 6} fill="#38bdf8" fontSize="9" fontFamily="monospace" fontWeight="bold">
                Peritectic (1493°C, 0.18%)
              </text>

              {/* Eutectic Point (4.30%, 1147°C) */}
              <circle cx={cToX(4.30)} cy={tToY(1147)} r="4" fill="#a855f7" stroke="#fff" strokeWidth="1.5" />
              <text x={cToX(4.30) - 10} y={tToY(1147) - 8} fill="#a855f7" fontSize="9" fontFamily="monospace" fontWeight="bold">
                Eutectic / Ledeburite (1147°C, 4.30%)
              </text>

              {/* Eutectoid Point (0.76%, 727°C) */}
              <circle cx={cToX(0.76)} cy={tToY(727)} r="4" fill="#10b981" stroke="#fff" strokeWidth="1.5" />
              <text x={cToX(0.76) + 8} y={tToY(727) - 8} fill="#10b981" fontSize="9" fontFamily="monospace" fontWeight="bold">
                Eutectoid / Pearlite (727°C, 0.76%)
              </text>

              {/* Critical Line Labels */}
              <text x={cToX(0.35)} y={tToY(840)} fill="#06b6d4" fontSize="10" fontFamily="monospace" fontWeight="bold">
                A₃ Line
              </text>
              <text x={cToX(1.4)} y={tToY(960)} fill="#a855f7" fontSize="10" fontFamily="monospace" fontWeight="bold">
                Acm Line
              </text>
              <text x={cToX(3.5)} y={tToY(745)} fill="#38bdf8" fontSize="10" fontFamily="monospace" fontWeight="bold">
                A₁ (Eutectoid Isotherm: 727°C)
              </text>
              <text x={cToX(4.8)} y={tToY(1165)} fill="#f59e0b" fontSize="10" fontFamily="monospace" fontWeight="bold">
                Eutectic Isotherm (1147°C)
              </text>

              {/* Major Region Labels */}
              <text x={cToX(3.2)} y={tToY(1450)} fill="#ef4444" fontSize="14" fontFamily="monospace" fontWeight="bold" opacity="0.8">
                LIQUID (L)
              </text>
              <text x={cToX(0.9)} y={tToY(1000)} fill="#06b6d4" fontSize="13" fontFamily="monospace" fontWeight="bold" opacity="0.9">
                γ - AUSTENITE
              </text>
              <text x={cToX(3.8)} y={tToY(950)} fill="#8b5cf6" fontSize="12" fontFamily="monospace" fontWeight="bold" opacity="0.8">
                γ + Fe₃C (Cementite)
              </text>
              <text x={cToX(0.35)} y={tToY(560)} fill="#38bdf8" fontSize="11" fontFamily="monospace" fontWeight="bold" opacity="0.9">
                α + Pearlite
              </text>
              <text x={cToX(1.4)} y={tToY(560)} fill="#3b82f6" fontSize="11" fontFamily="monospace" fontWeight="bold" opacity="0.9">
                Pearlite + Fe₃C
              </text>
              <text x={cToX(4.2)} y={tToY(560)} fill="#a855f7" fontSize="11" fontFamily="monospace" fontWeight="bold" opacity="0.8">
                Transformed Ledeburite + Fe₃C
              </text>

              {/* --- ACTIVE PROBE MARKER & ISOTHERMAL / ISOPLETH TIE-LINES --- */}
              {/* Vertical Isopleth Cooling Line */}
              <line
                x1={cToX(compositionC)}
                y1={margin.top}
                x2={cToX(compositionC)}
                y2={margin.top + graphHeight}
                stroke="#38bdf8"
                strokeWidth="1.5"
                strokeDasharray="3,3"
                opacity="0.85"
              />

              {/* Horizontal Isotherm Probe Line */}
              <line
                x1={margin.left}
                y1={tToY(temperatureC)}
                x2={margin.left + graphWidth}
                y2={tToY(temperatureC)}
                stroke="#f59e0b"
                strokeWidth="1.5"
                strokeDasharray="3,3"
                opacity="0.85"
              />

              {/* Active Probe Intersection Target Marker */}
              <circle
                cx={cToX(compositionC)}
                cy={tToY(temperatureC)}
                r="7"
                fill="#f59e0b"
                stroke="#ffffff"
                strokeWidth="2"
                className="animate-pulse shadow-lg"
              />
              <circle
                cx={cToX(compositionC)}
                cy={tToY(temperatureC)}
                r="14"
                fill="none"
                stroke="#f59e0b"
                strokeWidth="1"
                opacity="0.6"
              />

              {/* Probe Floating Tooltip Tag */}
              <g transform={`translate(${Math.min(graphWidth - 120, cToX(compositionC) + 12)}, ${Math.max(margin.top + 20, tToY(temperatureC) - 10)})`}>
                <rect width="140" height="42" rx="6" fill="#090e18" stroke="#38bdf8" strokeWidth="1" opacity="0.95" />
                <text x="8" y="16" fill="#38bdf8" fontSize="10" fontFamily="monospace" fontWeight="bold">
                  {compositionC.toFixed(2)}% C, {temperatureC}°C
                </text>
                <text x="8" y="32" fill="#e2e8f0" fontSize="9" fontFamily="monospace">
                  {probeState.regionName.split(" ")[0]}
                </text>
              </g>

              {/* Axis Boundaries */}
              <line x1={margin.left} y1={margin.top} x2={margin.left} y2={margin.top + graphHeight} stroke="#475569" strokeWidth="1.5" />
              <line x1={margin.left} y1={margin.top + graphHeight} x2={margin.left + graphWidth} y2={margin.top + graphHeight} stroke="#475569" strokeWidth="1.5" />
              <line x1={margin.left + graphWidth} y1={margin.top} x2={margin.left + graphWidth} y2={margin.top + graphHeight} stroke="#475569" strokeWidth="1.5" />

              {/* Axis Titles */}
              <text x={margin.left + graphWidth / 2} y={margin.top + graphHeight + 45} textAnchor="middle" fill="#cbd5e1" fontSize="12" fontFamily="monospace" fontWeight="bold">
                Carbon Concentration (wt % C) ➔
              </text>
              <text
                x={-(margin.top + graphHeight / 2)}
                y={margin.left - 48}
                transform="rotate(-90)"
                textAnchor="middle"
                fill="#cbd5e1"
                fontSize="12"
                fontFamily="monospace"
                fontWeight="bold"
              >
                Temperature (°C) ➔
              </text>
            </svg>
          </div>

          {/* Sliders for Direct Composition & Temperature Control */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            {/* Carbon Composition Slider */}
            <div className="p-3.5 bg-[#050810] rounded-xl border border-[#162032] space-y-2">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-300 font-bold flex items-center gap-1.5">
                  <Percent className="w-3.5 h-3.5 text-sky-400" />
                  Carbon Composition (wt % C):
                </span>
                <span className="text-sky-400 font-extrabold text-sm">{compositionC.toFixed(2)} % C</span>
              </div>
              <input aria-label="Carbon Composition (wt % C)"
                type="range"
                min="0"
                max="6.67"
                step="0.01"
                value={compositionC}
                onChange={(e) => setCompositionC(parseFloat(e.target.value))}
                className="w-full accent-sky-400 cursor-pointer h-1.5 bg-[#162032] rounded-lg"
              />
              <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                <span>0.0% (Pure Fe)</span>
                <span>0.76% (Pearlite)</span>
                <span>2.14% (Max Steel)</span>
                <span>4.3% (Eutectic)</span>
                <span>6.67% (Fe₃C)</span>
              </div>
            </div>

            {/* Temperature Slider */}
            <div className="p-3.5 bg-[#050810] rounded-xl border border-[#162032] space-y-2">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-300 font-bold flex items-center gap-1.5">
                  <Thermometer className="w-3.5 h-3.5 text-amber-400" />
                  Isothermal Probe Temperature:
                </span>
                <span className="text-amber-400 font-extrabold text-sm">{temperatureC} °C</span>
              </div>
              <input aria-label="Isothermal Probe Temperature (°C)"
                type="range"
                min="400"
                max="1600"
                step="5"
                value={temperatureC}
                onChange={(e) => setTemperatureC(parseInt(e.target.value, 10))}
                className="w-full accent-amber-400 cursor-pointer h-1.5 bg-[#162032] rounded-lg"
              />
              <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                <span>400°C (Tempering)</span>
                <span>727°C (A₁)</span>
                <span>912°C (A₃)</span>
                <span>1147°C (Eutectic)</span>
                <span>1538°C (Liquid)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Thermodynamic State, Lever Rule Solver & Microstructure */}
        <div className="lg:col-span-4 space-y-5">
          {/* 1. Equilibrium Phase State at Probe */}
          <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] space-y-4">
            <div className="flex items-center justify-between border-b border-[#162032] pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider">
                  Equilibrium State Analysis
                </h3>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/30">
                {compositionC <= 2.14 ? "Steel Regime" : "Cast Iron Regime"}
              </span>
            </div>

            {/* Current Region Card */}
            <div className="p-3.5 bg-[#050810] rounded-xl border border-[#162032] space-y-1.5">
              <div className="text-[10px] font-mono text-slate-500 uppercase">Phase Region</div>
              <div className="text-base font-extrabold text-sky-400 font-mono">
                {probeState.regionName}
              </div>
              <div className="text-xs font-mono text-slate-300">
                {probeState.stateCategory}
              </div>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                {probeState.equilibriumDescription}
              </p>
            </div>

            {/* 2. Thermodynamic Lever Rule Phase Fractions */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-emerald-400 uppercase tracking-wider font-semibold flex items-center gap-1">
                  <Activity className="w-3.5 h-3.5" />
                  Lever Rule Phase Quantities (Weight %)
                </span>
                <span className="text-[10px] font-mono text-slate-500">Tie-Line Solver</span>
              </div>

              <div className="space-y-2">
                {probeState.phasesPresent.map((ph, idx) => (
                  <div key={idx} className="p-3 bg-[#050810] rounded-xl border border-[#162032] space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-white">{ph.name}</span>
                        <span className="text-[10px] text-slate-400">({ph.crystal})</span>
                      </div>
                      <span className="font-extrabold text-emerald-400 text-sm">
                        {ph.fractionPct}%
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full h-1.5 bg-[#162032] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-400 rounded-full transition-all duration-300"
                        style={{ width: `${ph.fractionPct}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                      <span>Phase Carbon Solubility:</span>
                      <span className="text-sky-300 font-semibold">{ph.compositionC}% C</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Critical Reaction Reference Table */}
            <div className="space-y-2 pt-2 border-t border-[#162032]">
              <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider font-semibold flex items-center gap-1">
                <BookOpen className="w-3.5 h-3.5 text-sky-400" />
                Three Invariant Isothermal Reactions
              </span>
              <div className="space-y-1.5 text-[11px] font-mono">
                {INVARIANT_REACTIONS.map((inv) => (
                  <div key={inv.name} className="p-2 bg-[#050810] rounded-lg border border-[#162032]">
                    <div className="flex items-center justify-between text-xs font-bold text-white">
                      <span>{inv.name}</span>
                      <span className="text-sky-400">{inv.temp_C}°C</span>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-0.5">{inv.reaction}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Preset Alloy Selector & Typical Microstructures */}
          <div className="bg-[#090e18] p-5 rounded-2xl border border-[#162032] space-y-3">
            <div className="flex items-center justify-between border-b border-[#162032] pb-2">
              <h4 className="text-xs font-bold text-white font-mono uppercase tracking-wider flex items-center gap-1.5">
                <Atom className="w-3.5 h-3.5 text-sky-400" />
                Alloy Class & Expected Morphology
              </h4>
            </div>

            <div>
              <label className="text-[11px] font-mono text-slate-400 block mb-1">
                Select Alloy Standard Preset:
              </label>
              <select aria-label="Select Alloy Standard Preset"
                value={selectedPreset}
                onChange={(e) => handleSelectPreset(e.target.value)}
                className="w-full px-3 py-2 bg-[#050810] border border-[#162032] text-sky-300 font-mono text-xs rounded-xl focus:outline-none focus:border-sky-400"
              >
                {FEC_ALLOY_PRESETS.map((pr) => (
                  <option key={pr.name} value={pr.name}>
                    {pr.name} ({pr.composition_wt_pct_C}% C) — {pr.class}
                  </option>
                ))}
              </select>
            </div>

            {(() => {
              const activePreset = FEC_ALLOY_PRESETS.find((p) => p.name === selectedPreset) || FEC_ALLOY_PRESETS[2];
              return (
                <div className="p-3 bg-[#050810] rounded-xl border border-[#162032] space-y-2 text-xs font-mono">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block">Classification</span>
                    <span className="text-sky-300 font-bold">{activePreset.class}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block">Expected Room-Temp Microstructure</span>
                    <span className="text-slate-300 text-[11px]">{activePreset.expectedRoomTempMicrostructure}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block">Common Applications</span>
                    <span className="text-slate-400 text-[11px]">{activePreset.typicalApplications}</span>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      </div>
    </div>
  )}
</div>
);
};
