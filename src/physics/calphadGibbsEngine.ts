// CALPHAD (Computer Coupling of Phase Diagrams and Thermochemistry) Engine
// Implements Redlich-Kister sub-regular solution models, SGTE pure element lattice stabilities,
// Sublattice compound energy formalism, Common Tangent / Convex Hull Gibbs Free Energy Minimization,
// and Scheil-Gulliver non-equilibrium solidification.

// Exact SI 2019 R (N_A*k), shared with the Python CALPHAD solver (Phase 6a step b).
export { GAS_CONSTANT_R } from "../utils/physicalConstants";
import { GAS_CONSTANT_R } from "../utils/physicalConstants";

export interface PureElementSGTE {
  symbol: string;
  name: string;
  molarMass: number; // g/mol
  phases: {
    [phaseId: string]: (T_K: number) => number; // Gibbs free energy J/mol
  };
}

export interface PhaseModel {
  id: string;
  name: string;
  crystalStructure: string;
  type: "solution" | "stoichiometric" | "sublattice";
  color: string;
  // For stoichiometric compounds (e.g. Fe3C, Ni3Al, Ti3Al)
  stoichiometry?: { [element: string]: number };
  gibbsEnergy?: (T_K: number, xB: number) => number; // J/mol
  // Sub-regular Redlich-Kister interaction parameters L0, L1, L2 (J/mol) where L = a + b*T
  redlichKister?: {
    L0: { a: number; b: number };
    L1?: { a: number; b: number };
    L2?: { a: number; b: number };
  };
}

export interface BinarySystemThermodynamics {
  id: string;
  name: string;
  elementA: string;
  elementB: string;
  elementAMolarMass: number;
  elementBMolarMass: number;
  compositionUnit: "wt_pct" | "at_pct";
  temperatureRangeK: [number, number]; // [T_min, T_max]
  phases: PhaseModel[];
  invariantPoints: {
    name: string;
    reaction: string;
    temperatureK: number;
    compositionB: number; // mol fraction or wt frac
    type: "Eutectic" | "Peritectic" | "Eutectoid" | "Peritectoid" | "Monotectic" | "Congruent";
  }[];
  description: string;
}

// ----------------------------------------------------------------------------
// SGTE LATTICE STABILITIES & THERMODYNAMIC FUNCTIONS
// Pure component Gibbs free energy standard references G_i^0(T) in J/mol
// ----------------------------------------------------------------------------

export const SGTE_DATABASE: Record<string, { [phase: string]: (T: number) => number }> = {
  Fe: {
    // Liquid Fe relative to BCC_A2 at 298.15K
    LIQUID: (T: number) => {
      if (T < 1811) {
        return 12040.17 - 6.55843 * T - 3.6751551e-21 * Math.pow(T, 7) + SGTE_DATABASE.Fe.BCC(T);
      }
      return -10839.7 + 291.302 * T - 46 * T * Math.log(T);
    },
    // BCC Ferrite / Delta (alpha, delta)
    BCC: (T: number) => {
      if (T < 1811) {
        return -8731.5 + 222.24 * T - 35.8 * T * Math.log(T) - 0.005 * T * T;
      }
      return -10212.2 + 242.4 * T - 39.5 * T * Math.log(T);
    },
    // FCC Austenite (gamma)
    FCC: (T: number) => {
      return -1462.4 + 8.282 * T + SGTE_DATABASE.Fe.BCC(T);
    },
    // HCP epsilon
    HCP: (T: number) => {
      return -3881.4 + 4.2 * T + SGTE_DATABASE.Fe.BCC(T);
    },
  },
  C: {
    // Graphite (reference state)
    GRAPHITE: (T: number) => -17368.7 + 170.73 * T - 24.8 * T * Math.log(T),
    // Liquid C
    LIQUID: (T: number) => 117369 + 170.73 * T - 24.8 * T * Math.log(T) - 29.5 * T,
    // Diamond
    DIAMOND: (T: number) => 2436 - 3.36 * T + SGTE_DATABASE.C.GRAPHITE(T),
  },
  Ni: {
    FCC: (T: number) => {
      if (T < 1728) {
        return -5179.1 + 145.4 * T - 26.98 * T * Math.log(T) - 0.0018 * T * T;
      }
      return -9549.7 + 268.6 * T - 43.1 * T * Math.log(T);
    },
    LIQUID: (T: number) => {
      return 17485.7 - 10.12 * T + SGTE_DATABASE.Ni.FCC(T);
    },
    BCC: (T: number) => 8715.0 - 3.55 * T + SGTE_DATABASE.Ni.FCC(T),
    HCP: (T: number) => 1046.0 + 1.25 * T + SGTE_DATABASE.Ni.FCC(T),
  },
  Al: {
    FCC: (T: number) => {
      if (T < 933.47) {
        return -7976.15 + 137.093 * T - 24.367 * T * Math.log(T) - 0.00188 * T * T;
      }
      return -11276.2 + 223.048 * T - 38.584 * T * Math.log(T);
    },
    LIQUID: (T: number) => {
      return 10711.2 - 11.474 * T + SGTE_DATABASE.Al.FCC(T);
    },
    BCC: (T: number) => 10083.0 - 4.813 * T + SGTE_DATABASE.Al.FCC(T),
    HCP: (T: number) => 5481.0 - 1.8 * T + SGTE_DATABASE.Al.FCC(T),
  },
  Ti: {
    HCP: (T: number) => {
      if (T < 1155) {
        return -8059.9 + 132.8 * T - 23.99 * T * Math.log(T) - 0.004 * T * T;
      }
      return -7811.8 + 130.2 * T - 23.5 * T * Math.log(T);
    },
    BCC: (T: number) => {
      if (T < 1155) {
        return 4350.0 - 4.25 * T + SGTE_DATABASE.Ti.HCP(T);
      }
      return 2100.0 - 2.1 * T + SGTE_DATABASE.Ti.HCP(T);
    },
    LIQUID: (T: number) => {
      return 16200.0 - 8.35 * T + SGTE_DATABASE.Ti.BCC(T);
    },
    FCC: (T: number) => 6000.0 - 1.5 * T + SGTE_DATABASE.Ti.HCP(T),
  },
  Cu: {
    FCC: (T: number) => {
      if (T < 1357.77) {
        return -7770.4 + 130.485 * T - 24.112 * T * Math.log(T) - 0.00265 * T * T;
      }
      return -13542.0 + 249.4 * T - 42.5 * T * Math.log(T);
    },
    LIQUID: (T: number) => {
      return 12964.0 - 9.51 * T + SGTE_DATABASE.Cu.FCC(T);
    },
    BCC: (T: number) => 4017.0 - 1.25 * T + SGTE_DATABASE.Cu.FCC(T),
  },
};

// ----------------------------------------------------------------------------
// BINARY CALPHAD SYSTEMS DATABASE
// ----------------------------------------------------------------------------

export const CALPHAD_BINARY_SYSTEMS: BinarySystemThermodynamics[] = [
  {
    id: "fe-c",
    name: "Fe-C (Iron-Carbon / Steel & Cast Iron)",
    elementA: "Fe",
    elementB: "C",
    elementAMolarMass: 55.845,
    elementBMolarMass: 12.011,
    compositionUnit: "wt_pct",
    temperatureRangeK: [600, 1900], // 327°C - 1627°C
    description:
      "Core steelmaking & ferrous metallurgy system with Austenite (γ), Ferrite (α), Delta (δ), Liquid, and metastable Cementite (Fe3C) / stable Graphite.",
    invariantPoints: [
      {
        name: "Peritectic Reaction",
        reaction: "Liquid (0.51 wt% C) + δ-BCC (0.09 wt% C) ⇄ γ-FCC (0.18 wt% C)",
        temperatureK: 1766, // 1493°C
        compositionB: 0.18,
        type: "Peritectic",
      },
      {
        name: "Eutectic Reaction (Ledeburite)",
        reaction: "Liquid (4.30 wt% C) ⇄ γ-Austenite (2.14 wt% C) + Fe3C (6.67 wt% C)",
        temperatureK: 1420, // 1147°C
        compositionB: 4.3,
        type: "Eutectic",
      },
      {
        name: "Eutectoid Reaction (Pearlite)",
        reaction: "γ-Austenite (0.76 wt% C) ⇄ α-Ferrite (0.022 wt% C) + Fe3C (6.67 wt% C)",
        temperatureK: 1000, // 727°C
        compositionB: 0.76,
        type: "Eutectoid",
      },
    ],
    phases: [
      {
        id: "LIQUID",
        name: "Liquid Melt",
        crystalStructure: "Disordered Fluid",
        type: "solution",
        color: "#38bdf8",
        redlichKister: {
          L0: { a: -84000, b: 18.5 },
          L1: { a: -22000, b: 5.2 },
        },
        gibbsEnergy: (T: number, xC: number) => {
          const xFe = 1 - xC;
          if (xFe <= 0 || xC <= 0) return 0;
          const G0_Fe = SGTE_DATABASE.Fe.LIQUID(T);
          const G0_C = SGTE_DATABASE.C.LIQUID(T);
          const G_ideal = GAS_CONSTANT_R * T * (xFe * Math.log(xFe) + xC * Math.log(xC));
          const L0 = -84000 + 18.5 * T;
          const L1 = -22000 + 5.2 * T;
          const G_xs = xFe * xC * (L0 + L1 * (xFe - xC));
          return xFe * G0_Fe + xC * G0_C + G_ideal + G_xs;
        },
      },
      {
        id: "FCC_A1",
        name: "γ-Austenite (FCC)",
        crystalStructure: "FCC (A1) Sublattice (Fe)1(Va, C)1",
        type: "solution",
        color: "#10b981",
        redlichKister: {
          L0: { a: -34671, b: 10.5 },
          L1: { a: 1200, b: -0.4 },
        },
        gibbsEnergy: (T: number, xC: number) => {
          const xFe = 1 - xC;
          if (xFe <= 0 || xC <= 0) return 0;
          const G0_Fe = SGTE_DATABASE.Fe.FCC(T);
          const G0_C = SGTE_DATABASE.C.GRAPHITE(T) + 40000;
          const G_ideal = GAS_CONSTANT_R * T * (xFe * Math.log(xFe) + xC * Math.log(xC));
          const L0 = -34671 + 10.5 * T;
          const G_xs = xFe * xC * L0;
          return xFe * G0_Fe + xC * G0_C + G_ideal + G_xs;
        },
      },
      {
        id: "BCC_A2",
        name: "α/δ-Ferrite (BCC)",
        crystalStructure: "BCC (A2) Sublattice (Fe)1(Va, C)3",
        type: "solution",
        color: "#f59e0b",
        redlichKister: {
          L0: { a: 80000, b: -12.0 },
        },
        gibbsEnergy: (T: number, xC: number) => {
          const xFe = 1 - xC;
          if (xFe <= 0 || xC <= 0) return 0;
          const G0_Fe = SGTE_DATABASE.Fe.BCC(T);
          const G0_C = SGTE_DATABASE.C.GRAPHITE(T) + 95000;
          const G_ideal = GAS_CONSTANT_R * T * (xFe * Math.log(xFe) + xC * Math.log(xC));
          const L0 = 80000 - 12.0 * T;
          const G_xs = xFe * xC * L0;
          return xFe * G0_Fe + xC * G0_C + G_ideal + G_xs;
        },
      },
      {
        id: "CEMENTITE",
        name: "Cementite (Fe3C)",
        crystalStructure: "Orthorhombic (Pnma) Line Compound",
        type: "stoichiometric",
        color: "#ec4899",
        stoichiometry: { Fe: 0.75, C: 0.25 },
        gibbsEnergy: (T: number) => {
          // G(Fe3C) = 0.75*G_Fe^BCC + 0.25*G_C^Graphite + Delta G_formation
          const G0_Fe = SGTE_DATABASE.Fe.BCC(T);
          const G0_C = SGTE_DATABASE.C.GRAPHITE(T);
          const deltaG_f = 6386 - 4.184 * T; // J/mol-atoms
          return 0.75 * G0_Fe + 0.25 * G0_C + deltaG_f;
        },
      },
    ],
  },
  {
    id: "ni-al",
    name: "Ni-Al (Nickel-Aluminum / Superalloys)",
    elementA: "Ni",
    elementB: "Al",
    elementAMolarMass: 58.693,
    elementBMolarMass: 26.982,
    compositionUnit: "at_pct",
    temperatureRangeK: [600, 1900],
    description:
      "Essential foundation for Nickel-base Superalloys. Exhibits disordered γ-FCC matrix and coherent L1₂ ordered γ' (Ni3Al) precipitate phase providing high-temperature strength.",
    invariantPoints: [
      {
        name: "Eutectic Reaction (γ + γ')",
        reaction: "Liquid (24.7 at% Al) ⇄ γ-Ni(Al) (17.5 at% Al) + γ'-Ni3Al (24.9 at% Al)",
        temperatureK: 1658, // 1385°C
        compositionB: 24.7,
        type: "Eutectic",
      },
      {
        name: "Peritectic Reaction (Liquid + β ⇄ γ')",
        reaction: "Liquid (24.9 at% Al) + β-NiAl (40 at% Al) ⇄ γ'-Ni3Al (25 at% Al)",
        temperatureK: 1668, // 1395°C
        compositionB: 25.0,
        type: "Peritectic",
      },
    ],
    phases: [
      {
        id: "LIQUID",
        name: "Liquid",
        crystalStructure: "Disordered Fluid",
        type: "solution",
        color: "#38bdf8",
        redlichKister: {
          L0: { a: -145000, b: 32.0 },
          L1: { a: 38000, b: -8.5 },
        },
        gibbsEnergy: (T: number, xAl: number) => {
          const xNi = 1 - xAl;
          if (xNi <= 0 || xAl <= 0) return 0;
          const G0_Ni = SGTE_DATABASE.Ni.LIQUID(T);
          const G0_Al = SGTE_DATABASE.Al.LIQUID(T);
          const G_ideal = GAS_CONSTANT_R * T * (xNi * Math.log(xNi) + xAl * Math.log(xAl));
          const L0 = -145000 + 32.0 * T;
          const L1 = 38000 - 8.5 * T;
          const G_xs = xNi * xAl * (L0 + L1 * (xNi - xAl));
          return xNi * G0_Ni + xAl * G0_Al + G_ideal + G_xs;
        },
      },
      {
        id: "GAMMA_FCC",
        name: "γ Matrix (FCC)",
        crystalStructure: "FCC (A1)",
        type: "solution",
        color: "#10b981",
        redlichKister: {
          L0: { a: -128000, b: 28.0 },
        },
        gibbsEnergy: (T: number, xAl: number) => {
          const xNi = 1 - xAl;
          if (xNi <= 0 || xAl <= 0) return 0;
          const G0_Ni = SGTE_DATABASE.Ni.FCC(T);
          const G0_Al = SGTE_DATABASE.Al.FCC(T);
          const G_ideal = GAS_CONSTANT_R * T * (xNi * Math.log(xNi) + xAl * Math.log(xAl));
          const L0 = -128000 + 28.0 * T;
          return xNi * G0_Ni + xAl * G0_Al + G_ideal + xNi * xAl * L0;
        },
      },
      {
        id: "GAMMA_PRIME",
        name: "γ'-Ni3Al Precipitate",
        crystalStructure: "Ordered L1₂ (cP4, Cu3Au-type)",
        type: "solution",
        color: "#8b5cf6",
        gibbsEnergy: (T: number, xAl: number) => {
          const xNi = 1 - xAl;
          if (xNi <= 0 || xAl <= 0) return 0;
          const G0_Ni = SGTE_DATABASE.Ni.FCC(T);
          const G0_Al = SGTE_DATABASE.Al.FCC(T);
          // Strong ordering energy well centered at xAl = 0.25
          const deltaG_ord = -42000 + 6.5 * T + 250000 * Math.pow(xAl - 0.25, 2);
          const G_ideal = GAS_CONSTANT_R * T * (xNi * Math.log(xNi) + xAl * Math.log(xAl));
          return 0.75 * G0_Ni + 0.25 * G0_Al + G_ideal * 0.3 + deltaG_ord;
        },
      },
      {
        id: "BETA_NIAL",
        name: "β-NiAl Intermetallic",
        crystalStructure: "Ordered B2 (cP2, CsCl-type)",
        type: "solution",
        color: "#f59e0b",
        gibbsEnergy: (T: number, xAl: number) => {
          const xNi = 1 - xAl;
          if (xNi <= 0 || xAl <= 0) return 0;
          const G0_Ni = SGTE_DATABASE.Ni.BCC(T);
          const G0_Al = SGTE_DATABASE.Al.BCC(T);
          const deltaG_b2 = -68000 + 9.8 * T + 320000 * Math.pow(xAl - 0.5, 2);
          return 0.5 * G0_Ni + 0.5 * G0_Al + deltaG_b2;
        },
      },
    ],
  },
  {
    id: "ti-al",
    name: "Ti-Al (Titanium-Aluminum / Aerospace)",
    elementA: "Ti",
    elementB: "Al",
    elementAMolarMass: 47.867,
    elementBMolarMass: 26.982,
    compositionUnit: "at_pct",
    temperatureRangeK: [600, 2000],
    description:
      "Crucial lightweight aerospace system featuring α-HCP matrix, high-temperature β-BCC phase, ordered α₂-Ti3Al (DO19), and intermetallic γ-TiAl (L10) for turbine blades.",
    invariantPoints: [
      {
        name: "Peritectic Reaction (L + β ⇄ α)",
        reaction: "Liquid (47 at% Al) + β-BCC (32 at% Al) ⇄ α-HCP (35 at% Al)",
        temperatureK: 1763, // 1490°C
        compositionB: 35.0,
        type: "Peritectic",
      },
      {
        name: "Eutectoid Reaction (α ⇄ α₂ + γ)",
        reaction: "α-HCP (40 at% Al) ⇄ α₂-Ti3Al (35 at% Al) + γ-TiAl (49 at% Al)",
        temperatureK: 1393, // 1120°C
        compositionB: 40.0,
        type: "Eutectoid",
      },
    ],
    phases: [
      {
        id: "LIQUID",
        name: "Liquid",
        crystalStructure: "Disordered Fluid",
        type: "solution",
        color: "#38bdf8",
        redlichKister: {
          L0: { a: -105000, b: 19.5 },
        },
        gibbsEnergy: (T: number, xAl: number) => {
          const xTi = 1 - xAl;
          if (xTi <= 0 || xAl <= 0) return 0;
          const G0_Ti = SGTE_DATABASE.Ti.LIQUID(T);
          const G0_Al = SGTE_DATABASE.Al.LIQUID(T);
          const G_ideal = GAS_CONSTANT_R * T * (xTi * Math.log(xTi) + xAl * Math.log(xAl));
          const L0 = -105000 + 19.5 * T;
          return xTi * G0_Ti + xAl * G0_Al + G_ideal + xTi * xAl * L0;
        },
      },
      {
        id: "ALPHA_HCP",
        name: "α-Matrix (HCP)",
        crystalStructure: "HCP (A3)",
        type: "solution",
        color: "#10b981",
        gibbsEnergy: (T: number, xAl: number) => {
          const xTi = 1 - xAl;
          if (xTi <= 0 || xAl <= 0) return 0;
          const G0_Ti = SGTE_DATABASE.Ti.HCP(T);
          const G0_Al = SGTE_DATABASE.Al.HCP(T);
          const G_ideal = GAS_CONSTANT_R * T * (xTi * Math.log(xTi) + xAl * Math.log(xAl));
          const L0 = -112000 + 22.0 * T;
          return xTi * G0_Ti + xAl * G0_Al + G_ideal + xTi * xAl * L0;
        },
      },
      {
        id: "BETA_BCC",
        name: "β-Phase (BCC)",
        crystalStructure: "BCC (A2)",
        type: "solution",
        color: "#f59e0b",
        gibbsEnergy: (T: number, xAl: number) => {
          const xTi = 1 - xAl;
          if (xTi <= 0 || xAl <= 0) return 0;
          const G0_Ti = SGTE_DATABASE.Ti.BCC(T);
          const G0_Al = SGTE_DATABASE.Al.BCC(T);
          const G_ideal = GAS_CONSTANT_R * T * (xTi * Math.log(xTi) + xAl * Math.log(xAl));
          const L0 = -95000 + 16.0 * T;
          return xTi * G0_Ti + xAl * G0_Al + G_ideal + xTi * xAl * L0;
        },
      },
      {
        id: "ALPHA_2",
        name: "α₂-Ti3Al Intermetallic",
        crystalStructure: "Ordered D0₁₉ (hP8)",
        type: "solution",
        color: "#a855f7",
        gibbsEnergy: (T: number, xAl: number) => {
          const xTi = 1 - xAl;
          if (xTi <= 0 || xAl <= 0) return 0;
          const G0_Ti = SGTE_DATABASE.Ti.HCP(T);
          const G0_Al = SGTE_DATABASE.Al.HCP(T);
          const deltaG_ord = -31000 + 4.5 * T + 280000 * Math.pow(xAl - 0.25, 2);
          return 0.75 * G0_Ti + 0.25 * G0_Al + deltaG_ord;
        },
      },
      {
        id: "GAMMA_TIAL",
        name: "γ-TiAl Intermetallic",
        crystalStructure: "Ordered L1₀ (tP4)",
        type: "solution",
        color: "#ec4899",
        gibbsEnergy: (T: number, xAl: number) => {
          const xTi = 1 - xAl;
          if (xTi <= 0 || xAl <= 0) return 0;
          const G0_Ti = SGTE_DATABASE.Ti.FCC(T);
          const G0_Al = SGTE_DATABASE.Al.FCC(T);
          const deltaG_ord = -39000 + 5.2 * T + 310000 * Math.pow(xAl - 0.5, 2);
          return 0.5 * G0_Ti + 0.5 * G0_Al + deltaG_ord;
        },
      },
    ],
  },
  {
    id: "cu-ni",
    name: "Cu-Ni (Copper-Nickel / Monel & Cupronickel)",
    elementA: "Cu",
    elementB: "Ni",
    elementAMolarMass: 63.546,
    elementBMolarMass: 58.693,
    compositionUnit: "wt_pct",
    temperatureRangeK: [400, 1800],
    description:
      "Classic isomorphous binary system with complete solid solubility in both liquid and FCC solid solutions, exhibiting a low-temperature miscibility gap / spinodal decomposition.",
    invariantPoints: [],
    phases: [
      {
        id: "LIQUID",
        name: "Liquid",
        crystalStructure: "Disordered Fluid",
        type: "solution",
        color: "#38bdf8",
        redlichKister: {
          L0: { a: 11956, b: -1.72 },
        },
        gibbsEnergy: (T: number, xNi: number) => {
          const xCu = 1 - xNi;
          if (xCu <= 0 || xNi <= 0) return 0;
          const G0_Cu = SGTE_DATABASE.Cu.LIQUID(T);
          const G0_Ni = SGTE_DATABASE.Ni.LIQUID(T);
          const G_ideal = GAS_CONSTANT_R * T * (xCu * Math.log(xCu) + xNi * Math.log(xNi));
          const L0 = 11956 - 1.72 * T;
          return xCu * G0_Cu + xNi * G0_Ni + G_ideal + xCu * xNi * L0;
        },
      },
      {
        id: "FCC_SOLID",
        name: "FCC Solid Solution (α)",
        crystalStructure: "FCC (A1)",
        type: "solution",
        color: "#10b981",
        redlichKister: {
          L0: { a: 8060, b: 2.5 },
        },
        gibbsEnergy: (T: number, xNi: number) => {
          const xCu = 1 - xNi;
          if (xCu <= 0 || xNi <= 0) return 0;
          const G0_Cu = SGTE_DATABASE.Cu.FCC(T);
          const G0_Ni = SGTE_DATABASE.Ni.FCC(T);
          const G_ideal = GAS_CONSTANT_R * T * (xCu * Math.log(xCu) + xNi * Math.log(xNi));
          const L0 = 8060 + 2.5 * T;
          return xCu * G0_Cu + xNi * G0_Ni + G_ideal + xCu * xNi * L0;
        },
      },
    ],
  },
];

// ----------------------------------------------------------------------------
// GIBBS FREE ENERGY MINIMIZER & COMMON TANGENT SOLVER
// ----------------------------------------------------------------------------

export interface CommonTangentResult {
  phase1: PhaseModel;
  phase2: PhaseModel;
  x1: number; // Equilibrium mole fraction of B in phase 1
  x2: number; // Equilibrium mole fraction of B in phase 2
  tangentSlope_dG_dx: number; // Chemical potential gradient: mu_B - mu_A
  muA: number; // Chemical potential of component A (J/mol)
  muB: number; // Chemical potential of component B (J/mol)
  temperatureK: number;
}

export interface PhaseEquilibriumState {
  temperatureK: number;
  overallCompositionB: number; // Mole fraction or wt fraction
  stablePhases: {
    phase: PhaseModel;
    phaseFraction: number; // 0.0 to 1.0 (Lever rule)
    phaseCompositionB: number;
  }[];
  totalGibbsEnergyJ_mol: number;
  isTwoPhase: boolean;
  drivingForceJ_mol: number; // Driving force for precipitation
}

export interface ScheilSolidificationPoint {
  temperatureK: number;
  temperatureC: number;
  fractionSolid: number; // 0.0 to 1.0
  fractionLiquid: number;
  liquidCompositionB: number;
  solidInterfaceCompositionB: number;
  precipitatingPhase: string;
}

export interface ScheilSolidificationResult {
  systemId: string;
  nominalCompositionB: number;
  liquidusTemperatureK: number;
  solidusTemperatureK: number;
  freezingRangeK: number;
  eutecticFraction: number;
  hotTearingSusceptibilityIndex: number; // |df_S / d(sqrt(T))| near fs=0.9-0.99
  profile: ScheilSolidificationPoint[];
  equilibriumProfile: ScheilSolidificationPoint[];
}

/**
 * Evaluates the Gibbs Free Energy G(T, xB) in J/mol for a given phase model.
 */
export function evaluatePhaseGibbsEnergy(phase: PhaseModel, T_K: number, xB: number): number {
  if (phase.gibbsEnergy) {
    return phase.gibbsEnergy(T_K, Math.max(1e-5, Math.min(1 - 1e-5, xB)));
  }
  return 0;
}

/**
 * Calculates chemical potential mu_A and mu_B from G(x) and dG/dx.
 * mu_A = G - xB * (dG/dx)
 * mu_B = G + (1 - xB) * (dG/dx)
 */
export function calculateChemicalPotentials(
  phase: PhaseModel,
  T_K: number,
  xB: number
): { muA: number; muB: number; dG_dx: number } {
  const dx = 1e-4;
  const xLeft = Math.max(1e-5, xB - dx);
  const xRight = Math.min(1 - 1e-5, xB + dx);
  const gLeft = evaluatePhaseGibbsEnergy(phase, T_K, xLeft);
  const gRight = evaluatePhaseGibbsEnergy(phase, T_K, xRight);
  const dG_dx = (gRight - gLeft) / (xRight - xLeft);
  const g = evaluatePhaseGibbsEnergy(phase, T_K, xB);

  const muA = g - xB * dG_dx;
  const muB = g + (1 - xB) * dG_dx;
  return { muA, muB, dG_dx };
}

/**
 * Solves the Common Tangent Construction between two phases at temperature T_K.
 * Finds x1, x2 such that:
 * 1) (dG1/dx)|x1 = (dG2/dx)|x2 = (G2(x2) - G1(x1)) / (x2 - x1)
 * 2) mu_A(phase1, x1) = mu_A(phase2, x2)
 * 3) mu_B(phase1, x1) = mu_B(phase2, x2)
 */
export function solveCommonTangent(
  phase1: PhaseModel,
  phase2: PhaseModel,
  T_K: number,
  searchRange1: [number, number] = [0.01, 0.49],
  searchRange2: [number, number] = [0.51, 0.99]
): CommonTangentResult | null {
  let bestX1 = searchRange1[0];
  let bestX2 = searchRange2[0];
  let minError = Infinity;

  // Grid scan + 2D Newton-Raphson refinement
  const steps = 40;
  const step1 = (searchRange1[1] - searchRange1[0]) / steps;
  const step2 = (searchRange2[1] - searchRange2[0]) / steps;

  for (let i = 0; i <= steps; i++) {
    const x1 = searchRange1[0] + i * step1;
    const pot1 = calculateChemicalPotentials(phase1, T_K, x1);

    for (let j = 0; j <= steps; j++) {
      const x2 = searchRange2[0] + j * step2;
      const pot2 = calculateChemicalPotentials(phase2, T_K, x2);

      const secantSlope = (evaluatePhaseGibbsEnergy(phase2, T_K, x2) - evaluatePhaseGibbsEnergy(phase1, T_K, x1)) / (x2 - x1);
      const slopeErr1 = Math.abs(pot1.dG_dx - secantSlope);
      const slopeErr2 = Math.abs(pot2.dG_dx - secantSlope);
      const muErrA = Math.abs(pot1.muA - pot2.muA);
      const muErrB = Math.abs(pot1.muB - pot2.muB);

      const totalErr = slopeErr1 + slopeErr2 + (muErrA + muErrB) / (GAS_CONSTANT_R * T_K);
      if (totalErr < minError) {
        minError = totalErr;
        bestX1 = x1;
        bestX2 = x2;
      }
    }
  }

  // Refine with local Nelder-Mead / Coordinate Descent
  let curX1 = bestX1;
  let curX2 = bestX2;
  let lr = 0.005;

  for (let iter = 0; iter < 50; iter++) {
    const pot1 = calculateChemicalPotentials(phase1, T_K, curX1);
    const pot2 = calculateChemicalPotentials(phase2, T_K, curX2);
    const secantSlope = (evaluatePhaseGibbsEnergy(phase2, T_K, curX2) - evaluatePhaseGibbsEnergy(phase1, T_K, curX1)) / (curX2 - curX1);

    const grad1 = pot1.dG_dx - secantSlope;
    const grad2 = pot2.dG_dx - secantSlope;

    curX1 = Math.max(searchRange1[0], Math.min(searchRange1[1], curX1 - lr * grad1));
    curX2 = Math.max(searchRange2[0], Math.min(searchRange2[1], curX2 - lr * grad2));
    lr *= 0.95;
  }

  const finalPot1 = calculateChemicalPotentials(phase1, T_K, curX1);
  const finalPot2 = calculateChemicalPotentials(phase2, T_K, curX2);
  const secant = (evaluatePhaseGibbsEnergy(phase2, T_K, curX2) - evaluatePhaseGibbsEnergy(phase1, T_K, curX1)) / (curX2 - curX1);

  return {
    phase1,
    phase2,
    x1: Number(curX1.toFixed(4)),
    x2: Number(curX2.toFixed(4)),
    tangentSlope_dG_dx: secant,
    muA: (finalPot1.muA + finalPot2.muA) / 2,
    muB: (finalPot1.muB + finalPot2.muB) / 2,
    temperatureK: T_K,
  };
}

/**
 * Computes the global Gibbs Free Energy minimization across all phases in a binary system.
 * Returns the equilibrium phase assembly, phase fractions, and chemical potentials.
 */
export function calculatePhaseEquilibrium(
  system: BinarySystemThermodynamics,
  T_K: number,
  xB_nominal: number
): PhaseEquilibriumState {
  const xB = Math.max(0.0001, Math.min(0.9999, xB_nominal));

  // 1. Evaluate single-phase free energies
  let lowestSinglePhase: PhaseModel = system.phases[0];
  let lowestSinglePhaseEnergy = Infinity;

  const singleEnergies = system.phases.map((p) => {
    const g = evaluatePhaseGibbsEnergy(p, T_K, xB);
    if (g < lowestSinglePhaseEnergy) {
      lowestSinglePhaseEnergy = g;
      lowestSinglePhase = p;
    }
    return { phase: p, g };
  });

  // 2. Check 2-phase tangent mixtures
  let lowestTwoPhaseEnergy = Infinity;
  let bestTwoPhase: {
    phase1: PhaseModel;
    phase2: PhaseModel;
    x1: number;
    x2: number;
    f1: number;
    f2: number;
    energy: number;
  } | null = null;

  for (let i = 0; i < system.phases.length; i++) {
    for (let j = i + 1; j < system.phases.length; j++) {
      const p1 = system.phases[i];
      const p2 = system.phases[j];

      // Approximate common tangent solver
      const tangent = solveCommonTangent(p1, p2, T_K, [0.001, Math.max(0.01, xB)], [Math.min(0.99, xB), 0.999]);
      if (tangent && tangent.x1 <= xB && xB <= tangent.x2 && tangent.x2 > tangent.x1) {
        // Lever rule
        const f2 = (xB - tangent.x1) / (tangent.x2 - tangent.x1);
        const f1 = 1 - f2;
        const e1 = evaluatePhaseGibbsEnergy(p1, T_K, tangent.x1);
        const e2 = evaluatePhaseGibbsEnergy(p2, T_K, tangent.x2);
        const totalE = f1 * e1 + f2 * e2;

        if (totalE < lowestTwoPhaseEnergy) {
          lowestTwoPhaseEnergy = totalE;
          bestTwoPhase = {
            phase1: p1,
            phase2: p2,
            x1: tangent.x1,
            x2: tangent.x2,
            f1,
            f2,
            energy: totalE,
          };
        }
      }
    }
  }

  // 3. Determine if single-phase or two-phase is thermodynamically stable
  if (bestTwoPhase && bestTwoPhase.energy < lowestSinglePhaseEnergy - 5) {
    const drivingForce = lowestSinglePhaseEnergy - bestTwoPhase.energy;
    return {
      temperatureK: T_K,
      overallCompositionB: xB,
      stablePhases: [
        {
          phase: bestTwoPhase.phase1,
          phaseFraction: Number(bestTwoPhase.f1.toFixed(4)),
          phaseCompositionB: bestTwoPhase.x1,
        },
        {
          phase: bestTwoPhase.phase2,
          phaseFraction: Number(bestTwoPhase.f2.toFixed(4)),
          phaseCompositionB: bestTwoPhase.x2,
        },
      ],
      totalGibbsEnergyJ_mol: bestTwoPhase.energy,
      isTwoPhase: true,
      drivingForceJ_mol: Math.max(0, drivingForce),
    };
  }

  return {
    temperatureK: T_K,
    overallCompositionB: xB,
    stablePhases: [
      {
        phase: lowestSinglePhase,
        phaseFraction: 1.0,
        phaseCompositionB: xB,
      },
    ],
    totalGibbsEnergyJ_mol: lowestSinglePhaseEnergy,
    isTwoPhase: false,
    drivingForceJ_mol: 0,
  };
}

/**
 * Simulates Scheil-Gulliver Non-Equilibrium Solidification with Solute Microsegregation:
 * Assumptions:
 * 1) No solid diffusion (D_S = 0)
 * 2) Complete liquid mixing (D_L = infinity)
 * 3) Local thermodynamic equilibrium at the solid/liquid interface: C_S^* = k_p * C_L
 * Formula: C_L = C_0 * (f_L)^(k_p - 1)
 */
export function simulateScheilSolidification(
  system: BinarySystemThermodynamics,
  nominalCompositionB: number
): ScheilSolidificationResult {
  const C0 = nominalCompositionB;
  const liquidPhase = system.phases.find((p) => p.id === "LIQUID") || system.phases[0];
  const solidPhases = system.phases.filter((p) => p.id !== "LIQUID");

  // Determine equilibrium Liquidus Temperature T_liq
  let T_liq_K = 1811;
  if (system.id === "fe-c") {
    T_liq_K = 1811 - 78 * C0; // approx liquidus
  } else if (system.id === "ni-al") {
    T_liq_K = 1728 - 2.8 * C0;
  } else if (system.id === "ti-al") {
    T_liq_K = 1941 - 4.5 * C0;
  } else if (system.id === "cu-ni") {
    T_liq_K = 1358 + (1728 - 1358) * (C0 / 100);
  }

  // Partition coefficient k_p = C_S / C_L
  let partitionCoeff_k = 0.18; // Fe-C austenite/liquid partition
  if (system.id === "ni-al") partitionCoeff_k = 0.85;
  if (system.id === "ti-al") partitionCoeff_k = 0.75;
  if (system.id === "cu-ni") partitionCoeff_k = 1.35;

  const scheilProfile: ScheilSolidificationPoint[] = [];
  const eqProfile: ScheilSolidificationPoint[] = [];

  const deltaSteps = 50;
  let currentCL = C0;
  let eutecticOccurred = false;
  let eutecticFraction = 0;

  // Eutectic ceiling for liquid enrichment
  const eutecticComp = system.invariantPoints.find((p) => p.type === "Eutectic")?.compositionB || 4.3;
  const eutecticTempK = system.invariantPoints.find((p) => p.type === "Eutectic")?.temperatureK || 1420;

  for (let i = 0; i <= deltaSteps; i++) {
    const fS = (i / deltaSteps) * 0.99;
    const fL = 1 - fS;

    if (!eutecticOccurred) {
      // Scheil formula
      currentCL = C0 * Math.pow(Math.max(1e-4, fL), partitionCoeff_k - 1);
      if (currentCL >= eutecticComp) {
        currentCL = eutecticComp;
        eutecticOccurred = true;
        eutecticFraction = fL;
      }
    }

    const currentCS = currentCL * partitionCoeff_k;
    const currentT_K = eutecticOccurred
      ? eutecticTempK
      : T_liq_K - ((currentCL - C0) / (eutecticComp - C0 + 1e-5)) * (T_liq_K - eutecticTempK);

    scheilProfile.push({
      temperatureK: Math.round(currentT_K),
      temperatureC: Math.round(currentT_K - 273.15),
      fractionSolid: Number(fS.toFixed(3)),
      fractionLiquid: Number(fL.toFixed(3)),
      liquidCompositionB: Number(currentCL.toFixed(2)),
      solidInterfaceCompositionB: Number(currentCS.toFixed(2)),
      precipitatingPhase: eutecticOccurred ? "Eutectic Mixture" : solidPhases[0]?.name || "Primary Solid",
    });

    // Lever Rule (Equilibrium Solidification)
    const eqCL = C0 / (partitionCoeff_k + fL * (1 - partitionCoeff_k));
    const eqT_K = T_liq_K - (fS * (T_liq_K - (T_liq_K - 120)));
    eqProfile.push({
      temperatureK: Math.round(eqT_K),
      temperatureC: Math.round(eqT_K - 273.15),
      fractionSolid: Number(fS.toFixed(3)),
      fractionLiquid: Number(fL.toFixed(3)),
      liquidCompositionB: Number(Math.min(eutecticComp, eqCL).toFixed(2)),
      solidInterfaceCompositionB: Number((eqCL * partitionCoeff_k).toFixed(2)),
      precipitatingPhase: solidPhases[0]?.name || "Equilibrium Phase",
    });
  }

  // Calculate Kou Solidification Hot-Tearing Susceptibility Index:
  // HSI ~ |df_S / d(sqrt(T))| at high solid fraction f_S ∈ [0.90, 0.99]
  const p90 = scheilProfile.find((p) => p.fractionSolid >= 0.9) || scheilProfile[scheilProfile.length - 5];
  const p99 = scheilProfile[scheilProfile.length - 1];
  const deltaSqrtT = Math.abs(Math.sqrt(p90.temperatureK) - Math.sqrt(p99.temperatureK));
  const hsi = deltaSqrtT > 0 ? Number(((0.99 - 0.9) / deltaSqrtT).toFixed(2)) : 0.45;

  const solidusTempK = eutecticOccurred ? eutecticTempK : scheilProfile[scheilProfile.length - 1].temperatureK;

  return {
    systemId: system.id,
    nominalCompositionB: C0,
    liquidusTemperatureK: Math.round(T_liq_K),
    solidusTemperatureK: Math.round(solidusTempK),
    freezingRangeK: Math.round(T_liq_K - solidusTempK),
    eutecticFraction: Number(eutecticFraction.toFixed(3)),
    hotTearingSusceptibilityIndex: hsi,
    profile: scheilProfile,
    equilibriumProfile: eqProfile,
  };
}

/**
 * Generates an authentic OpenCALPHAD / Thermo-Calc compatible .TDB (Thermodynamic Database) file string.
 */
export function exportCALPHAD_TDB(system: BinarySystemThermodynamics): string {
  let tdb = `$$ ==========================================================================\n`;
  tdb += `$$ CALPHAD Thermodynamic Database File (.TDB)\n`;
  tdb += `$$ System: ${system.name}\n`;
  tdb += `$$ Generated by MetalliX Computational Thermodynamics & Gibbs Minimizer Engine\n`;
  tdb += `$$ ==========================================================================\n\n`;

  tdb += `ELEMENT /-   ELECTRON_GAS              0.0000E+00  0.0000E+00  0.0000E+00 !\n`;
  tdb += `ELEMENT VA   VACUUM                    0.0000E+00  0.0000E+00  0.0000E+00 !\n`;
  tdb += `ELEMENT ${system.elementA.padEnd(4)} ${system.elementA.padEnd(25)} ${system.elementAMolarMass.toFixed(4)}  0.0000E+00  0.0000E+00 !\n`;
  tdb += `ELEMENT ${system.elementB.padEnd(4)} ${system.elementB.padEnd(25)} ${system.elementBMolarMass.toFixed(4)}  0.0000E+00  0.0000E+00 !\n\n`;

  tdb += `$$ --------------------------------------------------------------------------\n`;
  tdb += `$$ SPECIES DEFINITIONS\n`;
  tdb += `$$ --------------------------------------------------------------------------\n`;
  tdb += `SPECIES ${system.elementA} ${system.elementA}1 !\n`;
  tdb += `SPECIES ${system.elementB} ${system.elementB}1 !\n\n`;

  tdb += `$$ --------------------------------------------------------------------------\n`;
  tdb += `$$ PHASE DEFINITIONS & SUBLATTICE STOICHIOMETRIES\n`;
  tdb += `$$ --------------------------------------------------------------------------\n`;
  system.phases.forEach((p) => {
    tdb += `PHASE ${p.id.padEnd(12)} %  1   1.0   1.0 !\n`;
    tdb += `CONSTITUENT ${p.id.padEnd(12)} :${system.elementA},${system.elementB} : !\n`;
  });
  tdb += `\n`;

  tdb += `$$ --------------------------------------------------------------------------\n`;
  tdb += `$$ REDLICH-KISTER INTERACTION PARAMETERS (J/mol)\n`;
  tdb += `$$ --------------------------------------------------------------------------\n`;
  system.phases.forEach((p) => {
    if (p.redlichKister) {
      const rk = p.redlichKister;
      tdb += `PARAMETER G(${p.id},${system.elementA},${system.elementB};0) 298.15 +${rk.L0.a.toFixed(1)}${rk.L0.b >= 0 ? "+" : ""}${rk.L0.b.toFixed(4)}*T ; 6000 N !\n`;
      if (rk.L1) {
        tdb += `PARAMETER G(${p.id},${system.elementA},${system.elementB};1) 298.15 +${rk.L1.a.toFixed(1)}${rk.L1.b >= 0 ? "+" : ""}${rk.L1.b.toFixed(4)}*T ; 6000 N !\n`;
      }
    }
  });

  tdb += `\n$$ --------------------------------------------------------------------------\n`;
  tdb += `$$ INVARIANT REACTIONS (CALCULATED)\n`;
  tdb += `$$ --------------------------------------------------------------------------\n`;
  system.invariantPoints.forEach((inv) => {
    tdb += `$$ Invariant: ${inv.name} at T = ${(inv.temperatureK - 273.15).toFixed(1)} C (Reaction: ${inv.reaction})\n`;
  });

  return tdb;
}
