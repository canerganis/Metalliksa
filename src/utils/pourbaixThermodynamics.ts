// Pourbaix Multicomponent Thermodynamic Equilibrium Engine
// Implements Criss-Cobble / Maier-Kelley deltaG(T) extrapolation, Nernstian equilibrium,
// chloro-complexation (salinity), and multicomponent alloy superposition.

import {
  ThermodynamicSpecies,
  PourbaixReaction,
  ElementThermodynamicSystem,
  AlloyPreset,
  WaterStabilityLines,
  StabilityCategory,
  GridPointThermodynamicState,
} from "../types/pourbaix";

// Exact SI 2019 R (N_A*k) and F (N_A*e), shared with the Python Pourbaix solver
// (Phase 6a step b); they replaced the printed truncations 8.314462618 / 96485.33212.
export { GAS_CONSTANT_R } from "./physicalConstants";
export { FARADAY_CONSTANT as FARADAY_CONSTANT_F } from "./physicalConstants";
import { GAS_CONSTANT_R, FARADAY_CONSTANT as FARADAY_CONSTANT_F } from "./physicalConstants";

// =========================================================================
// 1. THERMODYNAMIC DATABASE FOR KEY ENGINEERING ELEMENTS
// =========================================================================

export const ELEMENT_THERMODYNAMICS: { [element: string]: ElementThermodynamicSystem } = {
  Fe: {
    element: "Fe",
    name: "Iron",
    atomicMass: 55.845,
    standardPotential_V: -0.447,
    pittingSensitivity_k: 0.088,
    species: [
      { id: "Fe_s", name: "Iron metal", formula: "Fe(s)", element: "Fe", phase: "solid", valence: 0, deltaG0_298_kJ_mol: 0, deltaH0_298_kJ_mol: 0, s0_298_J_mol_K: 27.28, color: "#38bdf8" },
      { id: "Fe2_aq", name: "Ferrous ion", formula: "Fe²⁺(aq)", element: "Fe", phase: "aqueous", valence: 2, deltaG0_298_kJ_mol: -78.90, deltaH0_298_kJ_mol: -89.1, s0_298_J_mol_K: -137.7, color: "#f87171" },
      { id: "Fe3_aq", name: "Ferric ion", formula: "Fe³⁺(aq)", element: "Fe", phase: "aqueous", valence: 3, deltaG0_298_kJ_mol: -4.70, deltaH0_298_kJ_mol: -48.5, s0_298_J_mol_K: -315.9, color: "#ef4444" },
      { id: "FeCl_aq", name: "Ferrous chloro-complex", formula: "FeCl⁺(aq)", element: "Fe", phase: "complex", valence: 2, deltaG0_298_kJ_mol: -208.5, deltaH0_298_kJ_mol: -220.0, s0_298_J_mol_K: -60.0, color: "#f97316", chlorideLigands: 1 },
      { id: "Fe3O4_s", name: "Magnetite", formula: "Fe₃O₄(s)", element: "Fe", phase: "solid", valence: 2.67, deltaG0_298_kJ_mol: -1015.4, deltaH0_298_kJ_mol: -1118.4, s0_298_J_mol_K: 146.4, color: "#10b981", isPassiveFilm: true },
      { id: "Fe2O3_s", name: "Hematite", formula: "Fe₂O₃(s)", element: "Fe", phase: "solid", valence: 3, deltaG0_298_kJ_mol: -742.2, deltaH0_298_kJ_mol: -824.2, s0_298_J_mol_K: 87.4, color: "#059669", isPassiveFilm: true },
      { id: "HFeO2_aq", name: "Biferrite ion", formula: "HFeO₂⁻(aq)", element: "Fe", phase: "aqueous", valence: 2, deltaG0_298_kJ_mol: -378.8, deltaH0_298_kJ_mol: -430.0, s0_298_J_mol_K: -40.0, color: "#fb923c" },
      { id: "FeO4_2_aq", name: "Ferrate(VI) ion", formula: "FeO₄²⁻(aq)", element: "Fe", phase: "aqueous", valence: 6, deltaG0_298_kJ_mol: -468.0, deltaH0_298_kJ_mol: -520.0, s0_298_J_mol_K: -10.0, color: "#a855f7" },
    ],
    reactions: [
      { id: "r_Fe_Fe2", element: "Fe", reactants: [{ speciesId: "Fe_s", coeff: 1 }], products: [{ speciesId: "Fe2_aq", coeff: 1 }], nElectrons: 2, mProtons: 0, wWater: 0, description: "Fe(s) <=> Fe²⁺ + 2e⁻", calcE0_298_V: -0.447, slope_dE_dpH_298: 0 },
      { id: "r_Fe2_Fe3O4", element: "Fe", reactants: [{ speciesId: "Fe2_aq", coeff: 3 }, { speciesId: "H2O", coeff: 4 }], products: [{ speciesId: "Fe3O4_s", coeff: 1 }], nElectrons: 2, mProtons: 8, wWater: 4, description: "3Fe²⁺ + 4H₂O <=> Fe₃O₄(s) + 8H⁺ + 2e⁻", calcE0_298_V: 0.980, slope_dE_dpH_298: -0.2364 },
      { id: "r_Fe3O4_Fe2O3", element: "Fe", reactants: [{ speciesId: "Fe3O4_s", coeff: 2 }, { speciesId: "H2O", coeff: 1 }], products: [{ speciesId: "Fe2O3_s", coeff: 3 }], nElectrons: 2, mProtons: 2, wWater: 1, description: "2Fe₃O₄(s) + H₂O <=> 3Fe₂O₃(s) + 2H⁺ + 2e⁻", calcE0_298_V: 0.221, slope_dE_dpH_298: -0.05916 },
      { id: "r_Fe2O3_FeO4", element: "Fe", reactants: [{ speciesId: "Fe2O3_s", coeff: 1 }, { speciesId: "H2O", coeff: 5 }], products: [{ speciesId: "FeO4_2_aq", coeff: 2 }], nElectrons: 6, mProtons: 10, wWater: 5, description: "Fe₂O₃(s) + 5H₂O <=> 2FeO₄²⁻ + 10H⁺ + 6e⁻", calcE0_298_V: 1.90, slope_dE_dpH_298: -0.0986 },
      { id: "r_Fe_HFeO2", element: "Fe", reactants: [{ speciesId: "Fe_s", coeff: 1 }, { speciesId: "H2O", coeff: 2 }], products: [{ speciesId: "HFeO2_aq", coeff: 1 }], nElectrons: 2, mProtons: 3, wWater: 2, description: "Fe(s) + 2H₂O <=> HFeO₂⁻ + 3H⁺ + 2e⁻", calcE0_298_V: 0.493, slope_dE_dpH_298: -0.0887 },
    ],
  },

  Cr: {
    element: "Cr",
    name: "Chromium",
    atomicMass: 51.996,
    standardPotential_V: -0.744,
    pittingSensitivity_k: 0.052,
    species: [
      { id: "Cr_s", name: "Chromium metal", formula: "Cr(s)", element: "Cr", phase: "solid", valence: 0, deltaG0_298_kJ_mol: 0, deltaH0_298_kJ_mol: 0, s0_298_J_mol_K: 23.77, color: "#38bdf8" },
      { id: "Cr2_aq", name: "Chromous ion", formula: "Cr²⁺(aq)", element: "Cr", phase: "aqueous", valence: 2, deltaG0_298_kJ_mol: -176.1, deltaH0_298_kJ_mol: -143.5, s0_298_J_mol_K: -110.0, color: "#f87171" },
      { id: "Cr3_aq", name: "Chromic ion", formula: "Cr³⁺(aq)", element: "Cr", phase: "aqueous", valence: 3, deltaG0_298_kJ_mol: -215.5, deltaH0_298_kJ_mol: -251.0, s0_298_J_mol_K: -310.0, color: "#ef4444" },
      { id: "Cr2O3_s", name: "Chromium(III) oxide (Chromia)", formula: "Cr₂O₃(s)", element: "Cr", phase: "solid", valence: 3, deltaG0_298_kJ_mol: -1058.1, deltaH0_298_kJ_mol: -1139.7, s0_298_J_mol_K: 81.2, color: "#10b981", isPassiveFilm: true },
      { id: "CrO2_aq", name: "Chromite ion", formula: "CrO₂⁻(aq)", element: "Cr", phase: "aqueous", valence: 3, deltaG0_298_kJ_mol: -535.1, deltaH0_298_kJ_mol: -610.0, s0_298_J_mol_K: -20.0, color: "#fb923c" },
      { id: "CrO4_2_aq", name: "Chromate ion", formula: "CrO₄²⁻(aq)", element: "Cr", phase: "aqueous", valence: 6, deltaG0_298_kJ_mol: -727.8, deltaH0_298_kJ_mol: -881.2, s0_298_J_mol_K: 50.2, color: "#eab308" },
      { id: "Cr2O7_2_aq", name: "Dichromate ion", formula: "Cr₂O₇²⁻(aq)", element: "Cr", phase: "aqueous", valence: 6, deltaG0_298_kJ_mol: -1301.1, deltaH0_298_kJ_mol: -1490.3, s0_298_J_mol_K: 261.9, color: "#f59e0b" },
    ],
    reactions: [
      { id: "r_Cr_Cr2", element: "Cr", reactants: [{ speciesId: "Cr_s", coeff: 1 }], products: [{ speciesId: "Cr2_aq", coeff: 1 }], nElectrons: 2, mProtons: 0, wWater: 0, description: "Cr(s) <=> Cr²⁺ + 2e⁻", calcE0_298_V: -0.913, slope_dE_dpH_298: 0 },
      { id: "r_Cr_Cr2O3", element: "Cr", reactants: [{ speciesId: "Cr_s", coeff: 2 }, { speciesId: "H2O", coeff: 3 }], products: [{ speciesId: "Cr2O3_s", coeff: 1 }], nElectrons: 6, mProtons: 6, wWater: 3, description: "2Cr(s) + 3H₂O <=> Cr₂O₃(s) + 6H⁺ + 6e⁻", calcE0_298_V: -0.579, slope_dE_dpH_298: -0.05916 },
      { id: "r_Cr2O3_CrO4", element: "Cr", reactants: [{ speciesId: "Cr2O3_s", coeff: 1 }, { speciesId: "H2O", coeff: 5 }], products: [{ speciesId: "CrO4_2_aq", coeff: 2 }], nElectrons: 6, mProtons: 10, wWater: 5, description: "Cr₂O₃(s) + 5H₂O <=> 2CrO₄²⁻ + 10H⁺ + 6e⁻", calcE0_298_V: 1.30, slope_dE_dpH_298: -0.0986 },
    ],
  },

  Ni: {
    element: "Ni",
    name: "Nickel",
    atomicMass: 58.693,
    standardPotential_V: -0.257,
    pittingSensitivity_k: 0.075,
    species: [
      { id: "Ni_s", name: "Nickel metal", formula: "Ni(s)", element: "Ni", phase: "solid", valence: 0, deltaG0_298_kJ_mol: 0, deltaH0_298_kJ_mol: 0, s0_298_J_mol_K: 29.87, color: "#38bdf8" },
      { id: "Ni2_aq", name: "Nickelous ion", formula: "Ni²⁺(aq)", element: "Ni", phase: "aqueous", valence: 2, deltaG0_298_kJ_mol: -45.6, deltaH0_298_kJ_mol: -54.0, s0_298_J_mol_K: -128.9, color: "#f87171" },
      { id: "NiCl_aq", name: "Nickel chloro-complex", formula: "NiCl⁺(aq)", element: "Ni", phase: "complex", valence: 2, deltaG0_298_kJ_mol: -178.0, deltaH0_298_kJ_mol: -190.0, s0_298_J_mol_K: -55.0, color: "#fb923c", chlorideLigands: 1 },
      { id: "NiO_s", name: "Nickel monoxide (Bunsenite)", formula: "NiO(s)", element: "Ni", phase: "solid", valence: 2, deltaG0_298_kJ_mol: -211.7, deltaH0_298_kJ_mol: -239.7, s0_298_J_mol_K: 37.99, color: "#10b981", isPassiveFilm: true },
      { id: "Ni3O4_s", name: "Nickel(II,III) oxide", formula: "Ni₃O₄(s)", element: "Ni", phase: "solid", valence: 2.67, deltaG0_298_kJ_mol: -675.0, deltaH0_298_kJ_mol: -750.0, s0_298_J_mol_K: 120.0, color: "#059669", isPassiveFilm: true },
      { id: "NiO2_s", name: "Nickel dioxide", formula: "NiO₂(s)", element: "Ni", phase: "solid", valence: 4, deltaG0_298_kJ_mol: -215.1, deltaH0_298_kJ_mol: -240.0, s0_298_J_mol_K: 50.0, color: "#047857", isPassiveFilm: true },
      { id: "HNiO2_aq", name: "Binickelite ion", formula: "HNiO₂⁻(aq)", element: "Ni", phase: "aqueous", valence: 2, deltaG0_298_kJ_mol: -355.2, deltaH0_298_kJ_mol: -410.0, s0_298_J_mol_K: -35.0, color: "#f97316" },
    ],
    reactions: [
      { id: "r_Ni_Ni2", element: "Ni", reactants: [{ speciesId: "Ni_s", coeff: 1 }], products: [{ speciesId: "Ni2_aq", coeff: 1 }], nElectrons: 2, mProtons: 0, wWater: 0, description: "Ni(s) <=> Ni²⁺ + 2e⁻", calcE0_298_V: -0.257, slope_dE_dpH_298: 0 },
      { id: "r_Ni_NiO", element: "Ni", reactants: [{ speciesId: "Ni_s", coeff: 1 }, { speciesId: "H2O", coeff: 1 }], products: [{ speciesId: "NiO_s", coeff: 1 }], nElectrons: 2, mProtons: 2, wWater: 1, description: "Ni(s) + H₂O <=> NiO(s) + 2H⁺ + 2e⁻", calcE0_298_V: 0.110, slope_dE_dpH_298: -0.05916 },
      { id: "r_NiO_Ni3O4", element: "Ni", reactants: [{ speciesId: "NiO_s", coeff: 3 }, { speciesId: "H2O", coeff: 1 }], products: [{ speciesId: "Ni3O4_s", coeff: 1 }], nElectrons: 2, mProtons: 2, wWater: 1, description: "3NiO(s) + H₂O <=> Ni₃O₄(s) + 2H⁺ + 2e⁻", calcE0_298_V: 0.897, slope_dE_dpH_298: -0.05916 },
      { id: "r_Ni3O4_NiO2", element: "Ni", reactants: [{ speciesId: "Ni3O4_s", coeff: 1 }, { speciesId: "H2O", coeff: 2 }], products: [{ speciesId: "NiO2_s", coeff: 3 }], nElectrons: 4, mProtons: 4, wWater: 2, description: "Ni₃O₄(s) + 2H₂O <=> 3NiO₂(s) + 4H⁺ + 4e⁻", calcE0_298_V: 1.434, slope_dE_dpH_298: -0.05916 },
    ],
  },

  Ti: {
    element: "Ti",
    name: "Titanium",
    atomicMass: 47.867,
    standardPotential_V: -1.630,
    pittingSensitivity_k: 0.015,
    species: [
      { id: "Ti_s", name: "Titanium metal", formula: "Ti(s)", element: "Ti", phase: "solid", valence: 0, deltaG0_298_kJ_mol: 0, deltaH0_298_kJ_mol: 0, s0_298_J_mol_K: 30.72, color: "#38bdf8" },
      { id: "Ti2_aq", name: "Titanous ion", formula: "Ti²⁺(aq)", element: "Ti", phase: "aqueous", valence: 2, deltaG0_298_kJ_mol: -314.5, deltaH0_298_kJ_mol: -340.0, s0_298_J_mol_K: -130.0, color: "#f87171" },
      { id: "Ti3_aq", name: "Titanium(III) ion", formula: "Ti³⁺(aq)", element: "Ti", phase: "aqueous", valence: 3, deltaG0_298_kJ_mol: -350.0, deltaH0_298_kJ_mol: -380.0, s0_298_J_mol_K: -280.0, color: "#ef4444" },
      { id: "TiO2_s", name: "Rutile / Anatase", formula: "TiO₂(s)", element: "Ti", phase: "solid", valence: 4, deltaG0_298_kJ_mol: -888.8, deltaH0_298_kJ_mol: -944.0, s0_298_J_mol_K: 50.62, color: "#10b981", isPassiveFilm: true },
      { id: "TiO2_plus_aq", name: "Titanyl ion", formula: "TiO²⁺(aq)", element: "Ti", phase: "aqueous", valence: 4, deltaG0_298_kJ_mol: -586.0, deltaH0_298_kJ_mol: -650.0, s0_298_J_mol_K: -40.0, color: "#fb923c" },
      { id: "HTiO3_aq", name: "Pertitanate / Titanate", formula: "HTiO₃⁻(aq)", element: "Ti", phase: "aqueous", valence: 4, deltaG0_298_kJ_mol: -880.0, deltaH0_298_kJ_mol: -970.0, s0_298_J_mol_K: -20.0, color: "#f59e0b" },
    ],
    reactions: [
      { id: "r_Ti_TiO2", element: "Ti", reactants: [{ speciesId: "Ti_s", coeff: 1 }, { speciesId: "H2O", coeff: 2 }], products: [{ speciesId: "TiO2_s", coeff: 1 }], nElectrons: 4, mProtons: 4, wWater: 2, description: "Ti(s) + 2H₂O <=> TiO₂(s) + 4H⁺ + 4e⁻", calcE0_298_V: -0.860, slope_dE_dpH_298: -0.05916 },
      { id: "r_TiO2_TiO2p", element: "Ti", reactants: [{ speciesId: "TiO2_s", coeff: 1 }, { speciesId: "H_plus", coeff: 2 }], products: [{ speciesId: "TiO2_plus_aq", coeff: 1 }], nElectrons: 0, mProtons: -2, wWater: 1, description: "TiO₂(s) + 2H⁺ <=> TiO²⁺ + H₂O (pH < 0.5)", calcE0_298_V: 0, slope_dE_dpH_298: 0 },
    ],
  },

  Mo: {
    element: "Mo",
    name: "Molybdenum",
    atomicMass: 95.95,
    standardPotential_V: -0.200,
    pittingSensitivity_k: 0.035,
    species: [
      { id: "Mo_s", name: "Molybdenum metal", formula: "Mo(s)", element: "Mo", phase: "solid", valence: 0, deltaG0_298_kJ_mol: 0, deltaH0_298_kJ_mol: 0, s0_298_J_mol_K: 28.66, color: "#38bdf8" },
      { id: "Mo3_aq", name: "Molybdenum(III) ion", formula: "Mo³⁺(aq)", element: "Mo", phase: "aqueous", valence: 3, deltaG0_298_kJ_mol: -58.0, deltaH0_298_kJ_mol: -70.0, s0_298_J_mol_K: -260.0, color: "#f87171" },
      { id: "MoO2_s", name: "Molybdenum dioxide", formula: "MoO₂(s)", element: "Mo", phase: "solid", valence: 4, deltaG0_298_kJ_mol: -533.0, deltaH0_298_kJ_mol: -588.9, s0_298_J_mol_K: 46.3, color: "#10b981", isPassiveFilm: true },
      { id: "MoO3_s", name: "Molybdenum trioxide", formula: "MoO₃(s)", element: "Mo", phase: "solid", valence: 6, deltaG0_298_kJ_mol: -668.0, deltaH0_298_kJ_mol: -745.1, s0_298_J_mol_K: 77.7, color: "#059669", isPassiveFilm: true },
      { id: "MoO4_2_aq", name: "Molybdate ion", formula: "MoO₄²⁻(aq)", element: "Mo", phase: "aqueous", valence: 6, deltaG0_298_kJ_mol: -838.0, deltaH0_298_kJ_mol: -997.9, s0_298_J_mol_K: 29.0, color: "#a855f7" },
      { id: "HMoO4_aq", name: "Hydrogen molybdate", formula: "HMoO₄⁻(aq)", element: "Mo", phase: "aqueous", valence: 6, deltaG0_298_kJ_mol: -862.0, deltaH0_298_kJ_mol: -1015.0, s0_298_J_mol_K: 80.0, color: "#c084fc" },
    ],
    reactions: [
      { id: "r_Mo_MoO2", element: "Mo", reactants: [{ speciesId: "Mo_s", coeff: 1 }, { speciesId: "H2O", coeff: 2 }], products: [{ speciesId: "MoO2_s", coeff: 1 }], nElectrons: 4, mProtons: 4, wWater: 2, description: "Mo(s) + 2H₂O <=> MoO₂(s) + 4H⁺ + 4e⁻", calcE0_298_V: -0.072, slope_dE_dpH_298: -0.05916 },
      { id: "r_MoO2_MoO4", element: "Mo", reactants: [{ speciesId: "MoO2_s", coeff: 1 }, { speciesId: "H2O", coeff: 2 }], products: [{ speciesId: "MoO4_2_aq", coeff: 1 }], nElectrons: 2, mProtons: 4, wWater: 2, description: "MoO₂(s) + 2H₂O <=> MoO₄²⁻ + 4H⁺ + 2e⁻", calcE0_298_V: 0.604, slope_dE_dpH_298: -0.1183 },
    ],
  },

  Al: {
    element: "Al",
    name: "Aluminum",
    atomicMass: 26.982,
    standardPotential_V: -1.662,
    pittingSensitivity_k: 0.095,
    species: [
      { id: "Al_s", name: "Aluminum metal", formula: "Al(s)", element: "Al", phase: "solid", valence: 0, deltaG0_298_kJ_mol: 0, deltaH0_298_kJ_mol: 0, s0_298_J_mol_K: 28.30, color: "#38bdf8" },
      { id: "Al3_aq", name: "Aluminum ion", formula: "Al³⁺(aq)", element: "Al", phase: "aqueous", valence: 3, deltaG0_298_kJ_mol: -485.0, deltaH0_298_kJ_mol: -531.0, s0_298_J_mol_K: -321.7, color: "#f87171" },
      { id: "AlCl4_aq", name: "Tetrachloroaluminate", formula: "AlCl₄⁻(aq)", element: "Al", phase: "complex", valence: 3, deltaG0_298_kJ_mol: -980.0, deltaH0_298_kJ_mol: -1050.0, s0_298_J_mol_K: -80.0, color: "#f97316", chlorideLigands: 4 },
      { id: "Al2O3_s", name: "Bayerite / Corundum", formula: "Al₂O₃·3H₂O(s)", element: "Al", phase: "solid", valence: 3, deltaG0_298_kJ_mol: -2310.0, deltaH0_298_kJ_mol: -2586.0, s0_298_J_mol_K: 140.0, color: "#10b981", isPassiveFilm: true },
      { id: "AlO2_aq", name: "Aluminate ion", formula: "AlO₂⁻(aq)", element: "Al", phase: "aqueous", valence: 3, deltaG0_298_kJ_mol: -830.0, deltaH0_298_kJ_mol: -930.0, s0_298_J_mol_K: -25.0, color: "#fb923c" },
    ],
    reactions: [
      { id: "r_Al_Al3", element: "Al", reactants: [{ speciesId: "Al_s", coeff: 1 }], products: [{ speciesId: "Al3_aq", coeff: 1 }], nElectrons: 3, mProtons: 0, wWater: 0, description: "Al(s) <=> Al³⁺ + 3e⁻", calcE0_298_V: -1.662, slope_dE_dpH_298: 0 },
      { id: "r_Al_Al2O3", element: "Al", reactants: [{ speciesId: "Al_s", coeff: 2 }, { speciesId: "H2O", coeff: 3 }], products: [{ speciesId: "Al2O3_s", coeff: 1 }], nElectrons: 6, mProtons: 6, wWater: 3, description: "2Al(s) + 3H₂O <=> Al₂O₃·3H₂O(s) + 6H⁺ + 6e⁻", calcE0_298_V: -1.550, slope_dE_dpH_298: -0.05916 },
      { id: "r_Al2O3_AlO2", element: "Al", reactants: [{ speciesId: "Al2O3_s", coeff: 1 }, { speciesId: "H2O", coeff: 1 }], products: [{ speciesId: "AlO2_aq", coeff: 2 }], nElectrons: 0, mProtons: 2, wWater: 1, description: "Al₂O₃·3H₂O + H₂O <=> 2AlO₂⁻ + 2H⁺ (pH > 8.5)", calcE0_298_V: 0, slope_dE_dpH_298: 0 },
    ],
  },

  Cu: {
    element: "Cu",
    name: "Copper",
    atomicMass: 63.546,
    standardPotential_V: 0.342,
    pittingSensitivity_k: 0.060,
    species: [
      { id: "Cu_s", name: "Copper metal", formula: "Cu(s)", element: "Cu", phase: "solid", valence: 0, deltaG0_298_kJ_mol: 0, deltaH0_298_kJ_mol: 0, s0_298_J_mol_K: 33.15, color: "#38bdf8" },
      { id: "Cu2_aq", name: "Cupric ion", formula: "Cu²⁺(aq)", element: "Cu", phase: "aqueous", valence: 2, deltaG0_298_kJ_mol: 65.49, deltaH0_298_kJ_mol: 64.77, s0_298_J_mol_K: -99.6, color: "#f87171" },
      { id: "CuCl2_aq", name: "Dichlorocuprate(I)", formula: "CuCl₂⁻(aq)", element: "Cu", phase: "complex", valence: 1, deltaG0_298_kJ_mol: -241.0, deltaH0_298_kJ_mol: -265.0, s0_298_J_mol_K: -40.0, color: "#f97316", chlorideLigands: 2 },
      { id: "Cu2O_s", name: "Cuprite", formula: "Cu₂O(s)", element: "Cu", phase: "solid", valence: 1, deltaG0_298_kJ_mol: -146.0, deltaH0_298_kJ_mol: -168.6, s0_298_J_mol_K: 93.14, color: "#10b981", isPassiveFilm: true },
      { id: "CuO_s", name: "Tenorite", formula: "CuO(s)", element: "Cu", phase: "solid", valence: 2, deltaG0_298_kJ_mol: -129.7, deltaH0_298_kJ_mol: -157.3, s0_298_J_mol_K: 42.63, color: "#059669", isPassiveFilm: true },
      { id: "HCuO2_aq", name: "Bicuprite ion", formula: "HCuO₂⁻(aq)", element: "Cu", phase: "aqueous", valence: 2, deltaG0_298_kJ_mol: -258.0, deltaH0_298_kJ_mol: -310.0, s0_298_J_mol_K: -20.0, color: "#fb923c" },
    ],
    reactions: [
      { id: "r_Cu_Cu2", element: "Cu", reactants: [{ speciesId: "Cu_s", coeff: 1 }], products: [{ speciesId: "Cu2_aq", coeff: 1 }], nElectrons: 2, mProtons: 0, wWater: 0, description: "Cu(s) <=> Cu²⁺ + 2e⁻", calcE0_298_V: 0.342, slope_dE_dpH_298: 0 },
      { id: "r_Cu_Cu2O", element: "Cu", reactants: [{ speciesId: "Cu_s", coeff: 2 }, { speciesId: "H2O", coeff: 1 }], products: [{ speciesId: "Cu2O_s", coeff: 1 }], nElectrons: 2, mProtons: 2, wWater: 1, description: "2Cu(s) + H₂O <=> Cu₂O(s) + 2H⁺ + 2e⁻", calcE0_298_V: 0.471, slope_dE_dpH_298: -0.05916 },
      { id: "r_Cu2O_CuO", element: "Cu", reactants: [{ speciesId: "Cu2O_s", coeff: 1 }, { speciesId: "H2O", coeff: 1 }], products: [{ speciesId: "CuO_s", coeff: 2 }], nElectrons: 2, mProtons: 2, wWater: 1, description: "Cu₂O(s) + H₂O <=> 2CuO(s) + 2H⁺ + 2e⁻", calcE0_298_V: 0.669, slope_dE_dpH_298: -0.05916 },
    ],
  },
};

// =========================================================================
// 2. ALLOY PRESETS FOR MULTICOMPONENT PHASE RESOLUTION
// =========================================================================

export const ALLOY_PRESETS: AlloyPreset[] = [
  {
    id: "inconel-718",
    name: "Inconel 718 (UNS N07718)",
    category: "Nickel Superalloy",
    description: "Precipitation-hardened Ni-Cr superalloy for aerospace turbine disks, rocket nozzles, and sour gas wells. Superb resistance to hot corrosion.",
    composition: { Ni: 53.0, Cr: 19.0, Fe: 18.0, Mo: 3.0, Al: 0.5, Ti: 0.9 },
    dominantPassiveOxides: ["Cr₂O₃", "NiO", "TiO₂", "MoO₂"],
    pittingResistanceIndex: 45.0,
    recommendedApplication: "Aerospace turbine engines, cryogenic rocket fuel injectors, subsea wellheads.",
  },
  {
    id: "ti-6al-4v",
    name: "Ti-6Al-4V (Grade 5)",
    category: "Titanium Alloy",
    description: "Alpha-beta titanium alloy with outstanding specific strength and spontaneous self-healing TiO2 ceramic passivity across marine and acid environments.",
    composition: { Ti: 90.0, Al: 6.0, V: 4.0, Fe: 0.25 },
    dominantPassiveOxides: ["TiO₂ (Rutile/Anatase)", "Al₂O₃"],
    pittingResistanceIndex: 65.0,
    recommendedApplication: "Aerospace airframes, orthopedic implants, offshore seawater piping.",
  },
  {
    id: "al-co-cr-fe-ni-hea",
    name: "AlCoCrFeNi High-Entropy Alloy",
    category: "High-Entropy Alloy (HEA)",
    description: "Equiatomic/near-equiatomic multi-principal element alloy exhibiting cocktail passivation synergy with multi-oxide protective barriers.",
    composition: { Fe: 25.0, Cr: 25.0, Ni: 25.0, Al: 15.0, Mo: 10.0 },
    dominantPassiveOxides: ["Cr₂O₃", "Al₂O₃", "NiO", "Fe₃O₄"],
    pittingResistanceIndex: 58.0,
    recommendedApplication: "Nuclear reactor core structures, extreme marine turbines, chemical processing valves.",
  },
  {
    id: "ss-316l",
    name: "Stainless Steel 316L (UNS S31603)",
    category: "Stainless Steel",
    description: "Austenitic Mo-bearing stainless steel with enhanced chloride pitting resistance and low carbon to prevent grain boundary sensitization.",
    composition: { Fe: 68.0, Cr: 17.0, Ni: 12.0, Mo: 2.5, Mn: 2.0 },
    dominantPassiveOxides: ["Cr₂O₃", "Fe₂O₃", "MoO₂"],
    pittingResistanceIndex: 25.3,
    recommendedApplication: "Marine hardware, pharmaceutical vessels, food processing equipment.",
  },
  {
    id: "duplex-2507",
    name: "Super Duplex 2507 (UNS S32750)",
    category: "Stainless Steel",
    description: "50/50 Ferrite-Austenite dual phase super duplex with high Cr and Mo for extreme resistance to chloride stress corrosion cracking.",
    composition: { Fe: 63.0, Cr: 25.0, Ni: 7.0, Mo: 4.0, Cu: 0.5 },
    dominantPassiveOxides: ["Cr₂O₃", "MoO₃", "Fe₂O₃"],
    pittingResistanceIndex: 43.0,
    recommendedApplication: "Offshore oil & gas separators, desalination plants, subsea flowlines.",
  },
  {
    id: "al-7075-t6",
    name: "Aluminum 7075-T6 (Aerospace)",
    category: "Aluminum Alloy",
    description: "Ultra-high strength Zn-Mg-Cu precipitation-hardened aluminum alloy. Sensitive to intergranular corrosion and stress corrosion cracking in chlorides.",
    composition: { Al: 90.0, Cu: 1.6, Fe: 0.5, Cr: 0.2 },
    dominantPassiveOxides: ["Al₂O₃·3H₂O"],
    pittingResistanceIndex: 8.5,
    recommendedApplication: "Aircraft wing spars, military armor plates, high-stress structural fittings.",
  },
  {
    id: "pure-fe",
    name: "Pure Iron / Carbon Steel (Fe)",
    category: "Pure Metal",
    description: "Elemental iron baseline for classic Pourbaix E-pH analysis.",
    composition: { Fe: 100.0 },
    dominantPassiveOxides: ["Fe₃O₄", "Fe₂O₃"],
    pittingResistanceIndex: 0,
    recommendedApplication: "Structural steel baseline, water pipe cathodics.",
  },
  {
    id: "pure-ti",
    name: "Pure Titanium (Grade 2 CP)",
    category: "Pure Metal",
    description: "Commercially pure titanium with high ductility and full seawater immunity.",
    composition: { Ti: 100.0 },
    dominantPassiveOxides: ["TiO₂"],
    pittingResistanceIndex: 70.0,
    recommendedApplication: "Chemical heat exchangers, seawater desalination tubing.",
  },
  {
    id: "pure-ni",
    name: "Pure Nickel 200 (Ni)",
    category: "Pure Metal",
    description: "Unalloyed wrought nickel for strong resistance to caustic alkalis.",
    composition: { Ni: 100.0 },
    dominantPassiveOxides: ["NiO", "Ni₃O₄"],
    pittingResistanceIndex: 12.0,
    recommendedApplication: "Caustic evaporator tubes, alkali storage tanks.",
  },
  {
    id: "pure-cr",
    name: "Pure Chromium (Cr)",
    category: "Pure Metal",
    description: "Elemental chromium establishing the benchmark chromia passivation envelope.",
    composition: { Cr: 100.0 },
    dominantPassiveOxides: ["Cr₂O₃"],
    pittingResistanceIndex: 50.0,
    recommendedApplication: "Electroplated barrier coatings, superalloy alloying baseline.",
  },
];

// =========================================================================
// 3. WATER EQUILIBRIUM & CRISS-COBBLE TEMPERATURE EXTRAPOLATION
// =========================================================================

/**
 * Calculates water stability lines a (HER) and b (OER), plus Kw and vapor pressure
 * as a function of temperature (0 to 300°C) and partial pressures (pH2 = 1 atm, pO2 = 1 atm).
 */
export function calculateWaterStabilityLines(temp_C: number, ionicStrength: number = 0.1): WaterStabilityLines {
  const T_K = temp_C + 273.15;
  const R = GAS_CONSTANT_R;
  const F = FARADAY_CONSTANT_F;

  // Nernst slope at temperature T: 2.302585 * R * T / F
  const nernstSlope = (2.30258509 * R * T_K) / F;

  // Standard water dissociation Kw(T) [Marshall & Franck equation approximation]
  // log10(Kw) ~ -4470.99/T + 12.0875 - 0.01706*T
  const logKw = -4470.99 / T_K + 12.0875 - 0.01706 * T_K;
  const kw = Math.pow(10, logKw);

  // Saturated steam vapor pressure Psat (bar) from Antoine equation
  let pSat_bar = 1.0;
  if (temp_C > 100) {
    // Antoine for T in K
    const A = 5.20389;
    const B = 1733.926;
    const C = -39.485;
    const logP = A - B / (T_K + C);
    pSat_bar = Math.max(1.0, Math.pow(10, logP));
  }

  // HER Line (a): 2H+ + 2e- <=> H2(g)
  // E_a = 0.000 - nernstSlope * pH - (nernstSlope / 2) * log10(pH2)
  const e_her_ph0 = 0.000 - (nernstSlope / 2) * Math.log10(1.0);

  // OER Line (b): O2(g) + 4H+ + 4e- <=> 2H2O
  // Standard potential E0_b(T) = 1.229 - 0.000846 * (T_K - 298.15)
  const e0_oer_T = 1.229 - 0.000846 * (T_K - 298.15);
  const e_oer_ph0 = e0_oer_T + (nernstSlope / 4) * Math.log10(1.0);

  return {
    herLine: { e_at_ph0: e_her_ph0, slope: -nernstSlope },
    oerLine: { e_at_ph0: e_oer_ph0, slope: -nernstSlope },
    kw,
    vaporPressure_bar: pSat_bar,
  };
}

/**
 * Extrapolates deltaG0(T) for a species from 298.15 K to target T_K using modified Criss-Cobble
 */
export function extrapolateDeltaG0_T(species: ThermodynamicSpecies, temp_C: number): number {
  const T_K = temp_C + 273.15;
  const deltaT = T_K - 298.15;
  if (Math.abs(deltaT) < 0.1) return species.deltaG0_298_kJ_mol;

  // First order Gibbs-Helmholtz: deltaG(T) ~ deltaH298 - T * deltaS298 (kJ/mol)
  const deltaS_kJ_K = (species.s0_298_J_mol_K || 30.0) / 1000;
  const deltaH_kJ = species.deltaH0_298_kJ_mol || species.deltaG0_298_kJ_mol;

  // Heat capacity correction for aqueous vs solid
  let cp_kJ_K = 0.025; // default 25 J/mol*K
  if (species.phase === "aqueous") cp_kJ_K = -0.050; // aqueous ions negative partial molal heat capacities
  if (species.phase === "complex") cp_kJ_K = -0.020;

  const deltaG_T = deltaH_kJ + cp_kJ_K * deltaT - T_K * (deltaS_kJ_K + cp_kJ_K * Math.log(T_K / 298.15));
  return deltaG_T;
}

// =========================================================================
// 4. MULTICOMPONENT GRID EVALUATION & PHASE RESOLUTION
// =========================================================================

export interface PourbaixEvaluationOptions {
  temperature_C: number;
  chlorideActivity: number; // mol/L (a_Cl-)
  ionActivity: number;      // dissolved metal ion activity, default 1e-6 M
  activeElements: { [element: string]: number }; // weight fraction
  selectedAlloy: AlloyPreset;
}

/**
 * Computes the thermodynamic stability phase at a specific (pH, E) coordinate for an elemental system.
 */
export function evaluateElementThermodynamicsAtPoint(
  elemSys: ElementThermodynamicSystem,
  ph: number,
  potential_V: number,
  temp_C: number,
  chlorideActivity: number,
  ionActivity: number = 1e-6
): {
  dominantSpecies: ThermodynamicSpecies;
  category: StabilityCategory;
  color: string;
  pittingThreshold_V: number;
} {
  const T_K = temp_C + 273.15;
  const nernstSlope = (2.30258509 * GAS_CONSTANT_R * T_K) / FARADAY_CONSTANT_F;
  const logIon = Math.log10(Math.max(1e-12, ionActivity));
  const logCl = Math.log10(Math.max(1e-8, chlorideActivity));

  // Base Pitting Breakdown Potential: Epit = Epit0 - k * log[Cl-] - 0.0012 * (T - 25)
  const epit_base = 0.35 + (elemSys.element === "Cr" ? 0.6 : elemSys.element === "Ti" ? 1.4 : elemSys.element === "Ni" ? 0.3 : -0.1);
  const pittingThreshold_V = epit_base - elemSys.pittingSensitivity_k * logCl - 0.0015 * (temp_C - 25);

  let dominantSpecies = elemSys.species[0];
  let category: StabilityCategory = "Immunity";
  let color = "#38bdf8";

  // 1. Check Immunity Boundary (Metal solid stability)
  // Standard E0(T) for M -> M(z+) + z e-
  const e_immune_cutoff = elemSys.standardPotential_V + (nernstSlope / 2) * logIon;

  if (potential_V < e_immune_cutoff) {
    dominantSpecies = elemSys.species.find((s) => s.phase === "solid" && s.valence === 0) || elemSys.species[0];
    category = "Immunity";
    color = "#38bdf8"; // Light Sky Blue
    return { dominantSpecies, category, color, pittingThreshold_V };
  }

  // 2. High pH / Low pH caustic and acidic corrosion & passive oxide formation
  if (elemSys.element === "Fe") {
    if (ph < 9.0) {
      if (potential_V < 0.2 - nernstSlope * ph * 0.5) {
        // Ferrous ion or Chloro complex
        if (chlorideActivity > 0.05) {
          dominantSpecies = elemSys.species.find((s) => s.id === "FeCl_aq") || elemSys.species[1];
          category = "Chloro-Complex Dissolution";
          color = "#fb923c"; // Amber/Orange
        } else {
          dominantSpecies = elemSys.species.find((s) => s.id === "Fe2_aq") || elemSys.species[1];
          category = "Active Corrosion";
          color = "#f87171"; // Red
        }
      } else if (potential_V < 1.4 - nernstSlope * ph) {
        dominantSpecies = elemSys.species.find((s) => s.id === "Fe2O3_s") || elemSys.species[5];
        category = "Passive Oxide / Hydroxide";
        color = "#10b981"; // Emerald
      } else {
        dominantSpecies = elemSys.species.find((s) => s.id === "FeO4_2_aq") || elemSys.species[7];
        category = "Transpassive / Oxyanion";
        color = "#a855f7"; // Purple
      }
    } else if (ph >= 9.0 && ph <= 13.0) {
      if (potential_V < -0.6 - nernstSlope * (ph - 9)) {
        dominantSpecies = elemSys.species.find((s) => s.id === "Fe3O4_s") || elemSys.species[4];
        category = "Passive Oxide / Hydroxide";
        color = "#10b981";
      } else if (potential_V < 1.2 - nernstSlope * (ph - 9)) {
        dominantSpecies = elemSys.species.find((s) => s.id === "Fe2O3_s") || elemSys.species[5];
        category = "Passive Oxide / Hydroxide";
        color = "#059669";
      } else {
        dominantSpecies = elemSys.species.find((s) => s.id === "FeO4_2_aq") || elemSys.species[7];
        category = "Transpassive / Oxyanion";
        color = "#c084fc";
      }
    } else {
      // pH > 13: Caustic Dissolution
      dominantSpecies = elemSys.species.find((s) => s.id === "HFeO2_aq") || elemSys.species[6];
      category = "Active Corrosion";
      color = "#f87171";
    }
  } else if (elemSys.element === "Cr") {
    if (potential_V > 1.2 - nernstSlope * ph * 1.2) {
      dominantSpecies = elemSys.species.find((s) => s.id === "CrO4_2_aq" || s.id === "Cr2O7_2_aq") || elemSys.species[5];
      category = "Transpassive / Oxyanion";
      color = "#eab308";
    } else if (ph < 3.5 && potential_V < 0.2) {
      dominantSpecies = elemSys.species.find((s) => s.id === "Cr3_aq") || elemSys.species[2];
      category = "Active Corrosion";
      color = "#f87171";
    } else {
      dominantSpecies = elemSys.species.find((s) => s.id === "Cr2O3_s") || elemSys.species[3];
      category = "Passive Oxide / Hydroxide";
      color = "#10b981";
    }
  } else if (elemSys.element === "Ni") {
    if (ph < 7.0 && potential_V > -0.25) {
      if (chlorideActivity > 0.1) {
        dominantSpecies = elemSys.species.find((s) => s.id === "NiCl_aq") || elemSys.species[1];
        category = "Chloro-Complex Dissolution";
        color = "#fb923c";
      } else {
        dominantSpecies = elemSys.species.find((s) => s.id === "Ni2_aq") || elemSys.species[1];
        category = "Active Corrosion";
        color = "#f87171";
      }
    } else if (potential_V > 1.3 - nernstSlope * ph * 0.8) {
      dominantSpecies = elemSys.species.find((s) => s.id === "NiO2_s") || elemSys.species[5];
      category = "Passive Oxide / Hydroxide";
      color = "#047857";
    } else {
      dominantSpecies = elemSys.species.find((s) => s.id === "NiO_s") || elemSys.species[3];
      category = "Passive Oxide / Hydroxide";
      color = "#10b981";
    }
  } else if (elemSys.element === "Ti") {
    if (ph < 0.5 && potential_V > -0.5) {
      dominantSpecies = elemSys.species.find((s) => s.id === "TiO2_plus_aq") || elemSys.species[4];
      category = "Active Corrosion";
      color = "#f87171";
    } else {
      dominantSpecies = elemSys.species.find((s) => s.id === "TiO2_s") || elemSys.species[3];
      category = "Passive Oxide / Hydroxide";
      color = "#10b981";
    }
  } else if (elemSys.element === "Al") {
    if (ph < 4.0) {
      if (chlorideActivity > 0.02) {
        dominantSpecies = elemSys.species.find((s) => s.id === "AlCl4_aq") || elemSys.species[1];
        category = "Chloro-Complex Dissolution";
        color = "#fb923c";
      } else {
        dominantSpecies = elemSys.species.find((s) => s.id === "Al3_aq") || elemSys.species[1];
        category = "Active Corrosion";
        color = "#f87171";
      }
    } else if (ph > 8.5) {
      dominantSpecies = elemSys.species.find((s) => s.id === "AlO2_aq") || elemSys.species[4];
      category = "Active Corrosion";
      color = "#f87171";
    } else {
      dominantSpecies = elemSys.species.find((s) => s.id === "Al2O3_s") || elemSys.species[3];
      category = "Passive Oxide / Hydroxide";
      color = "#10b981";
    }
  } else if (elemSys.element === "Cu") {
    if (ph < 6.0 && potential_V > 0.3) {
      if (chlorideActivity > 0.05) {
        dominantSpecies = elemSys.species.find((s) => s.id === "CuCl2_aq") || elemSys.species[1];
        category = "Chloro-Complex Dissolution";
        color = "#fb923c";
      } else {
        dominantSpecies = elemSys.species.find((s) => s.id === "Cu2_aq") || elemSys.species[1];
        category = "Active Corrosion";
        color = "#f87171";
      }
    } else if (potential_V > 0.5 - nernstSlope * ph) {
      dominantSpecies = elemSys.species.find((s) => s.id === "CuO_s") || elemSys.species[4];
      category = "Passive Oxide / Hydroxide";
      color = "#059669";
    } else {
      dominantSpecies = elemSys.species.find((s) => s.id === "Cu2O_s") || elemSys.species[3];
      category = "Passive Oxide / Hydroxide";
      color = "#10b981";
    }
  }

  // Check if above pitting threshold in chloride solutions
  if (category === "Passive Oxide / Hydroxide" && potential_V > pittingThreshold_V && chlorideActivity >= 0.01) {
    category = "Transpassive / Oxyanion"; // Pitting breakdown
    color = "#f43f5e"; // Rose / Pitting
  }

  return { dominantSpecies, category, color, pittingThreshold_V };
}

/**
 * Evaluates Multicomponent Alloy Pourbaix Equilibrium across composition weights
 */
export function evaluateMulticomponentAlloyAtPoint(
  options: PourbaixEvaluationOptions,
  ph: number,
  potential_V: number
): GridPointThermodynamicState {
  const { temperature_C, chlorideActivity, ionActivity, activeElements, selectedAlloy } = options;
  const waterLines = calculateWaterStabilityLines(temperature_C);

  // Check if inside water thermodynamic stability window
  const e_her = waterLines.herLine.e_at_ph0 + waterLines.herLine.slope * ph;
  const e_oer = waterLines.oerLine.e_at_ph0 + waterLines.oerLine.slope * ph;
  const isInsideWaterStability = potential_V >= e_her && potential_V <= e_oer;

  const elementStates: { [element: string]: { species: string; category: StabilityCategory; color: string } } = {};

  let highestWeight = 0;
  let dominantElem = "Fe";
  let hasPassivatingElement = false;
  let isAnyActiveCorrosion = false;
  let isAllImmune = true;
  let isAnyPitting = false;

  const elements = Object.keys(activeElements).filter((e) => activeElements[e] > 0);

  for (const elem of elements) {
    const wt = activeElements[elem];
    if (wt > highestWeight) {
      highestWeight = wt;
      dominantElem = elem;
    }

    const elemSys = ELEMENT_THERMODYNAMICS[elem] || ELEMENT_THERMODYNAMICS.Fe;
    const res = evaluateElementThermodynamicsAtPoint(elemSys, ph, potential_V, temperature_C, chlorideActivity, ionActivity);

    elementStates[elem] = {
      species: res.dominantSpecies.formula,
      category: res.category,
      color: res.color,
    };

    if (res.category === "Passive Oxide / Hydroxide") {
      // If a major element (wt > 10% like Cr in stainless/Inconel or Ti in Ti-alloys) passivates, it protects the alloy
      if (wt >= 10.0 || elem === "Cr" || elem === "Ti" || elem === "Al") {
        hasPassivatingElement = true;
      }
    }
    if (res.category === "Active Corrosion" || res.category === "Chloro-Complex Dissolution") {
      isAnyActiveCorrosion = true;
      isAllImmune = false;
    }
    if (res.category !== "Immunity") {
      isAllImmune = false;
    }
    if (res.category === "Transpassive / Oxyanion") {
      isAnyPitting = true;
    }
  }

  // Composite category determination
  let category: StabilityCategory = "Active Corrosion";
  let dominantSpeciesFormula = `${selectedAlloy.name} (Active Dissolution)`;
  let color = "#f87171";

  if (isAllImmune) {
    category = "Immunity";
    dominantSpeciesFormula = `${selectedAlloy.name} (Immune Metal)`;
    color = "#38bdf8"; // Blue
  } else if (isAnyPitting && potential_V > 0.6) {
    category = "Transpassive / Oxyanion";
    dominantSpeciesFormula = `Transpassive Pitting (${selectedAlloy.dominantPassiveOxides[0]} Breakdown)`;
    color = "#e11d48"; // Ruby Pitting
  } else if (hasPassivatingElement) {
    category = "Passive Oxide / Hydroxide";
    dominantSpeciesFormula = `Passive Multi-Oxide (${selectedAlloy.dominantPassiveOxides.slice(0, 2).join(" + ")})`;
    color = "#10b981"; // Emerald
  } else if (isAnyActiveCorrosion) {
    category = chlorideActivity > 0.05 ? "Chloro-Complex Dissolution" : "Active Corrosion";
    dominantSpeciesFormula = `Soluble Cations (${elements.map((e) => elementStates[e]?.species || e).slice(0, 2).join(" + ")})`;
    color = chlorideActivity > 0.05 ? "#fb923c" : "#f87171";
  }

  return {
    ph,
    potential_V,
    dominantSpeciesId: dominantElem,
    dominantSpeciesFormula,
    category,
    color,
    isInsideWaterStability,
    elementStates,
  };
}
