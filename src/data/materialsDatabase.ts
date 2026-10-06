import { MaterialSpec } from "../types";

export const MATERIALS_DATABASE: MaterialSpec[] = [
  // --- CARBON STEELS ---
  {
    id: "aisi-1018",
    name: "AISI 1018 Low Carbon Steel",
    category: "Carbon Steel",
    standard: "ASTM A108 / UNS G10180 / EN 1.0401",
    composition: { C: 0.18, Mn: 0.75, P: 0.04, S: 0.05, Fe: 98.98 },
    yieldStrength: 370,
    tensileStrength: 440,
    elongation: 15,
    hardness: "126 HBW / 71 HRB (Cold Drawn)",
    density: 7.87,
    meltingRange: "1480 - 1530 °C",
    youngsModulus: 205,
    thermalConductivity: 51.9,
    thermalExpansion: 11.5,
    poissonRatio: 0.29,
    microstructure: "Ferrite matrix with dispersed colonies of lamellar pearlite (~20-25% pearlite area fraction).",
    heatTreatments: [
      { name: "Carburizing (Case Hardening)", temperature: "900 - 930 °C", cooling: "Oil or water quench + temper @ 180°C", resultingHardness: "58-62 HRC (Case), 20-25 HRC (Core)" },
      { name: "Normalizing", temperature: "890 - 920 °C", cooling: "Still air", resultingHardness: "130 HBW" },
      { name: "Annealing", temperature: "870 °C", cooling: "Furnace cool", resultingHardness: "115 HBW" }
    ],
    applications: ["Machined pins, shafts, spindles", "Carburized gears", "Weldments & fixtures", "Tie rods & bushings"],
    failureRisks: ["Low core hardenability in thick sections", "Susceptible to atmospheric corrosion if unpainted"]
  },
  {
    id: "aisi-1045",
    name: "AISI 1045 Medium Carbon Steel",
    category: "Carbon Steel",
    standard: "ASTM A29 / UNS G10450 / EN C45E / DIN 1.1191",
    composition: { C: 0.45, Mn: 0.75, P: 0.04, S: 0.05, Si: 0.20, Fe: 98.51 },
    yieldStrength: 530,
    tensileStrength: 625,
    elongation: 12,
    hardness: "179 HBW / 88 HRB (Normalized)",
    density: 7.85,
    meltingRange: "1450 - 1520 °C",
    youngsModulus: 206,
    thermalConductivity: 49.8,
    thermalExpansion: 11.7,
    poissonRatio: 0.29,
    microstructure: "Equiaxed ferrite grains (~45% area fraction) surrounded by lamellar pearlite colonies (~55%).",
    heatTreatments: [
      { name: "Induction Surface Hardening", temperature: "840 - 870 °C", cooling: "Water spray quench + 180°C temper", resultingHardness: "55-60 HRC (Surface case depth 1.5-3mm)" },
      { name: "Quench & Temper", temperature: "845 °C austenitize", cooling: "Oil quench, temper @ 550°C", resultingHardness: "25-30 HRC (Good toughness & yield)" },
      { name: "Normalizing", temperature: "870 °C", cooling: "Air cool", resultingHardness: "180 HBW" }
    ],
    applications: ["Axles, crankshafts & hydraulic rams", "Gears and drive pinions", "Studs, bolts & industrial machine spindles", "Railway components"],
    failureRisks: ["Prone to quench cracking in water on sharp fillets", "Low impact toughness at sub-zero temperatures"]
  },
  {
    id: "aisi-1095",
    name: "AISI 1095 High Carbon Spring Steel",
    category: "Carbon Steel",
    standard: "ASTM A684 / UNS G10950 / EN C90D",
    composition: { C: 0.95, Mn: 0.40, P: 0.03, S: 0.035, Si: 0.20, Fe: 98.385 },
    yieldStrength: 830,
    tensileStrength: 1040,
    elongation: 9,
    hardness: "50 - 55 HRC (Oil Quenched & Tempered)",
    density: 7.84,
    meltingRange: "1420 - 1500 °C",
    youngsModulus: 207,
    thermalConductivity: 44.0,
    thermalExpansion: 11.0,
    poissonRatio: 0.29,
    microstructure: "Near 100% fine lamellar pearlite with proeutectoid grain-boundary cementite network (hypereutectoid).",
    heatTreatments: [
      { name: "Austenitizing & Quench", temperature: "800 - 830 °C", cooling: "Agitated oil quench", resultingHardness: "64-66 HRC (As-quenched martensite)" },
      { name: "Spring Tempering", temperature: "400 - 450 °C", cooling: "Air cool", resultingHardness: "48-52 HRC (High elastic recovery)" },
      { name: "Blade Tempering", temperature: "200 - 230 °C", cooling: "Air cool", resultingHardness: "58-60 HRC" }
    ],
    applications: ["Coil springs & leaf springs", "Cutting blades, doctor blades & scalpels", "High-wear scraping edges", "Clutch discs"],
    failureRisks: ["Severe brittleness if under-tempered", "High decarburization risk in open furnace atmospheres"]
  },
  {
    id: "astm-a36",
    name: "ASTM A36 Structural Carbon Steel",
    category: "Carbon Steel",
    standard: "ASTM A36 / UNS K02600 / EN S235JR",
    composition: { C: 0.25, Mn: 0.90, P: 0.04, S: 0.05, Si: 0.25, Cu: 0.20, Fe: 98.31 },
    yieldStrength: 250,
    tensileStrength: 400,
    elongation: 23,
    hardness: "119 - 159 HBW / ~70 HRB",
    density: 7.85,
    meltingRange: "1425 - 1538 °C",
    youngsModulus: 200,
    thermalConductivity: 51.0,
    thermalExpansion: 12.0,
    poissonRatio: 0.26,
    microstructure: "Hot-rolled coarse equiaxed polygonal ferrite with interstitial pearlite colonies.",
    heatTreatments: [
      { name: "Hot Rolled (As-Received)", temperature: "N/A", cooling: "Air cool on runout table", resultingHardness: "135 HBW" },
      { name: "Stress Relief Weldment", temperature: "590 - 650 °C", cooling: "Furnace cool", resultingHardness: "Relieves weld residual stresses" }
    ],
    applications: ["Civil structural building beams & columns", "Bridge girders and trusses", "Base plates and industrial weldments", "Storage tanks and heavy equipment chassis"],
    failureRisks: ["Uncontrolled yield point variations across plate thickness", "Poor low-temperature Charpy V-notch impact energy"]
  },

  // --- ALLOY STEELS ---
  {
    id: "aisi-4140",
    name: "AISI 4140 Chromium-Molybdenum Steel",
    category: "Alloy Steel",
    standard: "ASTM A29 / UNS G41400 / 42CrMo4 / EN 1.7225",
    composition: { C: 0.40, Cr: 1.00, Mo: 0.20, Mn: 0.85, Si: 0.25, P: 0.035, S: 0.04, Fe: 97.225 },
    // Tensile values match the hardness label: oil quenched from 845 °C, tempered at
    // 540 °C (ASM Handbook Vol. 1: YS 986 / UTS 1075 MPa / 15.5 % / 311 HB). The earlier
    // 655 / 1020 / 18 were the normalized (870 °C) values under this Q&T label.
    yieldStrength: 986,
    tensileStrength: 1075,
    elongation: 15.5,
    hardness: "28 - 34 HRC (Quenched & Tempered @ 540°C)",
    density: 7.85,
    meltingRange: "1415 - 1510 °C",
    youngsModulus: 210,
    thermalConductivity: 42.6,
    thermalExpansion: 12.3,
    poissonRatio: 0.29,
    microstructure: "Tempered martensite with fine dispersed chromium/molybdenum carbides; uniform grain structure.",
    heatTreatments: [
      { name: "Austenitizing & Quench", temperature: "845 - 870 °C", cooling: "Agitated oil quench", resultingHardness: "54-58 HRC (As-quenched)" },
      { name: "Tempering (High Strength)", temperature: "480 °C", cooling: "Air cool", resultingHardness: "36-40 HRC" },
      { name: "Tempering (Toughness)", temperature: "600 °C", cooling: "Air cool", resultingHardness: "28-32 HRC" },
      { name: "Nitriding", temperature: "510 - 540 °C", cooling: "Gas/plasma", resultingHardness: "60-65 HRC (Surface case)" }
    ],
    applications: ["Crankshafts & connecting rods", "Oil & gas drill collars and BOPs", "High-stress axles and gears", "Heavy machinery studs"],
    failureRisks: ["Temper embrittlement if cooled slowly through 375-575°C", "Hydrogen induced cracking during plating without post-bake"]
  },
  {
    id: "aisi-4340",
    name: "AISI 4340 Nickel-Chromium-Molybdenum Steel",
    category: "Alloy Steel",
    standard: "ASTM A29 / UNS G43400 / 34CrNiMo6 / AMS 6414",
    composition: { C: 0.40, Ni: 1.85, Cr: 0.80, Mo: 0.25, Mn: 0.70, Si: 0.25, P: 0.025, S: 0.025, Fe: 95.7 },
    yieldStrength: 1300,
    tensileStrength: 1450,
    elongation: 12,
    hardness: "42 - 46 HRC (Oil Quenched & Tempered @ 425°C)",
    density: 7.85,
    meltingRange: "1420 - 1520 °C",
    youngsModulus: 210,
    thermalConductivity: 38.0,
    thermalExpansion: 11.2,
    poissonRatio: 0.29,
    microstructure: "High-toughness tempered martensite with multi-element solid solution strengthening from Nickel.",
    heatTreatments: [
      { name: "Austenitize", temperature: "830 - 860 °C", cooling: "Oil quench", resultingHardness: "56-59 HRC" },
      { name: "Double Tempering", temperature: "400 - 500 °C", cooling: "Air cool", resultingHardness: "43-48 HRC" }
    ],
    applications: ["Aircraft landing gear components", "Heavy-duty power transmission shafts", "Gun barrels & ordnance", "Motorsport driveline components"],
    failureRisks: ["Extreme sensitivity to hydrogen embrittlement above 40 HRC", "Quench cracking on sharp radii"]
  },
  {
    id: "300m-steel",
    name: "300M Ultra-High-Strength Modified 4340 Steel",
    category: "Alloy Steel",
    standard: "AMS 6417 / AMS 6419 / UNS K44220",
    composition: { C: 0.42, Si: 1.60, Ni: 1.80, Cr: 0.80, Mo: 0.40, V: 0.08, Mn: 0.75, Fe: 94.15 },
    yieldStrength: 1680,
    tensileStrength: 2020,
    elongation: 10,
    hardness: "52 - 55 HRC (Aero Quenched & Tempered)",
    density: 7.84,
    meltingRange: "1410 - 1515 °C",
    youngsModulus: 205,
    thermalConductivity: 36.5,
    thermalExpansion: 11.0,
    poissonRatio: 0.29,
    microstructure: "Silicon-stabilized ultra-fine lath martensite retarding cementite coarsening during tempering.",
    heatTreatments: [
      { name: "Austenitize & Oil Quench", temperature: "870 °C", cooling: "Agitated oil quench", resultingHardness: "58 HRC" },
      { name: "Double Temper", temperature: "300 - 320 °C (2x 2h)", cooling: "Air cool", resultingHardness: "53-55 HRC (>1900 MPa UTS)" }
    ],
    applications: ["Commercial & military aircraft landing gear main cylinders", "High-stress missile airframe actuators", "Helicopter rotor mast shafts", "Motorsport high-torque axles"],
    failureRisks: ["Catastrophic hydrogen embrittlement under cadmium or zinc electroplate", "Stress corrosion cracking in marine atmosphere"]
  },
  {
    id: "aisi-52100",
    name: "AISI 52100 High-Carbon Bearing Steel",
    category: "Alloy Steel",
    standard: "ASTM A295 / UNS G52986 / 100Cr6 / DIN 1.3505",
    composition: { C: 1.00, Cr: 1.50, Mn: 0.35, Si: 0.25, P: 0.025, S: 0.015, Fe: 96.86 },
    yieldStrength: 2030,
    tensileStrength: 2240,
    elongation: 5,
    hardness: "60 - 64 HRC (Martensitic Hardened)",
    density: 7.81,
    meltingRange: "1424 - 1500 °C",
    youngsModulus: 210,
    thermalConductivity: 46.6,
    thermalExpansion: 11.9,
    poissonRatio: 0.30,
    microstructure: "Fine spherical chromium carbides (M3C / M7C3) uniformly embedded in high-carbon tempered martensite.",
    heatTreatments: [
      { name: "Spheroidize Anneal", temperature: "780 - 800 °C", cooling: "Slow furnace cool (10°C/h)", resultingHardness: "190 HBW (Optimal machinability)" },
      { name: "Through Hardening", temperature: "830 - 860 °C", cooling: "Oil or salt bath quench", resultingHardness: "64 HRC" },
      { name: "Low-Temp Temper", temperature: "150 - 180 °C (2h)", cooling: "Air cool", resultingHardness: "61-63 HRC" }
    ],
    applications: ["Ball bearings and cylindrical roller bearings", "Hydraulic pump pistons & swash plates", "High-precision ball screws & linear guides", "Fuel injection nozzles"],
    failureRisks: ["Rolling contact fatigue (spalling / subsurface micro-cracks)", "White etching crack (WEC) formation under stray electrical currents"]
  },

  // --- TOOL & DIE STEELS ---
  {
    id: "aisi-d2",
    name: "AISI D2 High-Carbon High-Chromium Cold Work Tool Steel",
    category: "Tool Steel",
    standard: "ASTM A681 / UNS T30402 / DIN 1.2379 / X153CrMoV12",
    composition: { C: 1.55, Cr: 11.5, Mo: 0.80, V: 0.80, Si: 0.30, Mn: 0.35, Fe: 84.7 },
    yieldStrength: 1700,
    tensileStrength: 2100,
    elongation: 3,
    hardness: "58 - 62 HRC (Air Hardened & Double Tempered)",
    density: 7.70,
    meltingRange: "1370 - 1430 °C",
    youngsModulus: 210,
    thermalConductivity: 20.0,
    thermalExpansion: 10.4,
    poissonRatio: 0.28,
    microstructure: "High volume fraction of hard primary eutectic M7C3 chromium carbides embedded in high-carbon tempered martensite matrix.",
    heatTreatments: [
      { name: "Austenitizing", temperature: "1020 - 1040 °C", cooling: "Vacuum/Air cool", resultingHardness: "64-65 HRC" },
      { name: "Secondary Hardening Temper", temperature: "500 - 520 °C (2x)", cooling: "Air cool", resultingHardness: "60-62 HRC" },
      { name: "Sub-Zero Cryogenic Treatment", temperature: "-80 to -196 °C", cooling: "Prior to 2nd temper", resultingHardness: "Eliminates retained austenite" }
    ],
    applications: ["Blanking and stamping dies", "Shear blades and slitting cutters", "Thread rolling dies", "Wear-resistant tooling & shredder blades"],
    failureRisks: ["Carbide banding causing anisotropic toughness", "High residual retained austenite if not cryo-treated or double tempered"]
  },
  {
    id: "aisi-h13",
    name: "AISI H13 Chromium Hot-Work Tool Steel",
    category: "Tool Steel",
    standard: "ASTM A681 / UNS T20813 / DIN 1.2344 / X40CrMoV5-1",
    composition: { C: 0.40, Cr: 5.25, Mo: 1.35, V: 1.00, Si: 1.00, Mn: 0.40, Fe: 90.6 },
    yieldStrength: 1450,
    tensileStrength: 1750,
    elongation: 9,
    hardness: "46 - 52 HRC (Hot Work Hardened)",
    density: 7.80,
    meltingRange: "1425 - 1490 °C",
    youngsModulus: 215,
    thermalConductivity: 28.6,
    thermalExpansion: 11.5,
    poissonRatio: 0.28,
    microstructure: "Tempered martensite with fine secondary vanadium/molybdenum carbides (MC/M2C) resisting thermal softening up to 550°C.",
    heatTreatments: [
      { name: "Vacuum Austenitizing", temperature: "1010 - 1030 °C", cooling: "High-pressure gas quench (N2)", resultingHardness: "54-56 HRC" },
      { name: "Triple Tempering", temperature: "540 - 600 °C (3x 2h)", cooling: "Air cool", resultingHardness: "48-52 HRC (Optimal thermal fatigue resistance)" }
    ],
    applications: ["Aluminum & magnesium high-pressure die casting dies", "Hot extrusion dies & mandrels", "Plastic injection molds", "Hot forging punches & gripper dies"],
    failureRisks: ["Thermal shock heat checking (surface micro-crazing)", "Erosion by molten aluminum"]
  },
  {
    id: "aisi-m2",
    name: "AISI M2 High-Speed Steel (Molybdenum-Tungsten)",
    category: "Tool Steel",
    standard: "ASTM A600 / UNS T11302 / DIN 1.3343 / HS6-5-2C",
    composition: { C: 0.85, W: 6.30, Mo: 5.00, Cr: 4.15, V: 1.95, Si: 0.30, Mn: 0.30, Fe: 81.15 },
    yieldStrength: 2800,
    tensileStrength: 3250,
    elongation: 1.5,
    hardness: "63 - 66 HRC (Triple Tempered)",
    density: 8.16,
    meltingRange: "1370 - 1430 °C",
    youngsModulus: 220,
    thermalConductivity: 24.0,
    thermalExpansion: 11.2,
    poissonRatio: 0.28,
    microstructure: "Dense primary M6C and MC carbides in a red-hard tempered martensitic matrix retaining cutting hardness up to 600°C.",
    heatTreatments: [
      { name: "Salt Bath / Vacuum Hardening", temperature: "1190 - 1230 °C", cooling: "Salt quench @ 540°C then air cool", resultingHardness: "65-66 HRC" },
      { name: "Triple Secondary Tempering", temperature: "540 - 560 °C (3x 2h)", cooling: "Air cool", resultingHardness: "64-66 HRC (Peak secondary hardening)" }
    ],
    applications: ["Twist drills, taps, reamers & broaches", "Gear hobs and milling cutters", "Cold heading punches", "Woodworking router tooling"],
    failureRisks: ["Chipping under high vibrational vibration or interrupted cuts", "Decarburization if heated in non-protective atmospheres"]
  },

  // --- STAINLESS STEELS ---
  {
    id: "ss-304",
    name: "AISI 304 Austenitic Stainless Steel (18/8)",
    category: "Stainless Steel",
    standard: "ASTM A240 / UNS S30400 / EN 1.4301 / X5CrNi18-10",
    composition: { C: 0.07, Cr: 18.5, Ni: 8.5, Mn: 2.0, Si: 0.75, P: 0.045, S: 0.03, Fe: 70.105 },
    yieldStrength: 240,
    tensileStrength: 580,
    elongation: 55,
    hardness: "160 HBW / 82 HRB (Annealed)",
    density: 7.93,
    meltingRange: "1400 - 1450 °C",
    youngsModulus: 193,
    thermalConductivity: 16.2,
    thermalExpansion: 17.3,
    poissonRatio: 0.29,
    microstructure: "Fully austenitic (FCC) equiaxed grains with annealing twins; essentially non-magnetic.",
    heatTreatments: [
      { name: "Solution Annealing", temperature: "1010 - 1120 °C", cooling: "Rapid water quench", resultingHardness: "150-170 HBW (Dissolves chromium carbides)" }
    ],
    applications: ["Food & beverage processing equipment", "Architectural paneling & handrails", "Kitchenware & sinks", "Chemical containers & cryogenic vessels"],
    failureRisks: ["Intergranular corrosion (sensitization) if heated in 450-850°C window", "Pitting corrosion in marine/chloride environments"]
  },
  {
    id: "ss-316l",
    name: "AISI 316L Low-Carbon Austenitic Stainless Steel",
    category: "Stainless Steel",
    standard: "ASTM A240 / UNS S31603 / EN 1.4404 / X2CrNiMo17-12-2",
    composition: { C: 0.02, Cr: 17.0, Ni: 12.0, Mo: 2.5, Mn: 1.5, Si: 0.5, P: 0.03, S: 0.02, Fe: 66.43 },
    yieldStrength: 290,
    tensileStrength: 580,
    elongation: 50,
    hardness: "150 - 180 HBW / ~80 HRB (Solution Annealed)",
    density: 8.00,
    meltingRange: "1375 - 1400 °C",
    youngsModulus: 193,
    thermalConductivity: 16.3,
    thermalExpansion: 16.0,
    poissonRatio: 0.28,
    microstructure: "Fully austenitic (FCC) equiaxed grain structure with annealing twins; immune to sensitization.",
    heatTreatments: [
      { name: "Solution Annealing", temperature: "1040 - 1150 °C", cooling: "Rapid water quench or air blast", resultingHardness: "150 HBW (Recrystallized, pore-free)" }
    ],
    applications: ["Chemical process piping & reactors", "Marine hardware & offshore components", "Biomedical surgical implants", "Pharmaceutical & food processing"],
    failureRisks: ["Chloride Stress Corrosion Cracking (SCC) above 60°C", "Pitting corrosion in stagnant seawater", "Work hardens rapidly during machining"]
  },
  {
    id: "ss-17-4ph",
    name: "17-4 PH Precipitation Hardening Stainless Steel",
    category: "Stainless Steel",
    standard: "ASTM A564 / UNS S17400 / AISI 630 / EN 1.4542",
    composition: { C: 0.04, Cr: 16.5, Ni: 4.2, Cu: 3.5, Nb: 0.30, Mn: 0.70, Si: 0.50, Fe: 74.26 },
    yieldStrength: 1170,
    tensileStrength: 1310,
    elongation: 14,
    hardness: "40 - 45 HRC (H900 Peak Aged)",
    density: 7.75,
    meltingRange: "1404 - 1440 °C",
    youngsModulus: 196,
    thermalConductivity: 17.9,
    thermalExpansion: 10.8,
    poissonRatio: 0.27,
    microstructure: "Low-carbon martensite matrix strengthened by sub-microscopic coherent copper-rich precipitate clusters (ε-Cu).",
    heatTreatments: [
      { name: "Solution Treatment (Condition A)", temperature: "1040 °C for 0.5h", cooling: "Air or oil quench below 32°C", resultingHardness: "28-32 HRC (Lath martensite)" },
      { name: "Peak Aging (H900)", temperature: "480 °C (1h)", cooling: "Air cool", resultingHardness: "40-44 HRC (>1170 MPa yield)" },
      { name: "Overaging / High Toughness (H1150)", temperature: "620 °C (4h)", cooling: "Air cool", resultingHardness: "28-33 HRC (Superior SCC resistance)" }
    ],
    applications: ["Aerospace structural brackets & flap tracks", "Nuclear reactor control rod drive mechanisms", "Offshore valve shafts & marine pump impellers", "Paper mill equipment"],
    failureRisks: ["Hydrogen embrittlement in H900 condition in sour gas (H2S)", "Dimensional contraction during precipitation aging (~0.05%)"]
  },
  {
    id: "ss-2205-duplex",
    name: "2205 Duplex Stainless Steel (UNS S32205 / EN 1.4462)",
    category: "Stainless Steel",
    standard: "ASTM A240 / UNS S32205 / EN 1.4462 / X2CrNiMoN22-5-3",
    composition: { C: 0.02, Cr: 22.5, Ni: 5.5, Mo: 3.2, N: 0.18, Mn: 1.5, Si: 0.5, Fe: 66.6 },
    yieldStrength: 550,
    tensileStrength: 780,
    elongation: 30,
    hardness: "28 - 32 HRC (Solution Annealed)",
    density: 7.80,
    meltingRange: "1420 - 1470 °C",
    youngsModulus: 200,
    thermalConductivity: 19.0,
    thermalExpansion: 13.0,
    poissonRatio: 0.30,
    microstructure: "Balanced dual-phase microstructure (~50% Austenite islands embedded in ~50% Ferrite matrix). PREN ~35.",
    heatTreatments: [
      { name: "Solution Annealing", temperature: "1020 - 1100 °C", cooling: "Rapid water quench", resultingHardness: "Maintains optimal 50/50 phase balance and avoids sigma phase" }
    ],
    applications: ["Offshore oil & gas separation vessels", "Marine cargo tanks", "Flue gas desulfurization (FGD) scrubbers", "Pulp and paper digesters"],
    failureRisks: ["Sigma (σ) and Chi (χ) intermetallic phase precipitation between 600-900°C", "475°C spinodal decomposition embrittlement"]
  },

  // --- ALUMINUM ALLOYS ---
  {
    id: "al-6061-t6",
    name: "Aluminum 6061-T6 (Al-Mg-Si Structural Alloy)",
    category: "Aluminum Alloy",
    standard: "ASTM B221 / UNS A96061 / EN AW-6061",
    composition: { Al: 96.97, Mg: 1.0, Si: 0.6, Cu: 0.28, Cr: 0.20, Fe: 0.70, Zn: 0.25 },
    yieldStrength: 276,
    tensileStrength: 310,
    elongation: 12,
    hardness: "95 HBW / ~60 HRB",
    density: 2.70,
    meltingRange: "582 - 652 °C",
    youngsModulus: 68.9,
    thermalConductivity: 167.0,
    thermalExpansion: 23.2,
    poissonRatio: 0.33,
    microstructure: "FCC aluminum matrix with coherent β'' needle-like Mg2Si precipitates (1-2 nm) providing obstacle to dislocation glide.",
    heatTreatments: [
      { name: "Solution Heat Treatment", temperature: "530 °C", cooling: "Rapid cold water quench", resultingHardness: "Supersaturated Solid Solution (SSSS)" },
      { name: "Artificial Aging (T6)", temperature: "160 °C for 8-18 hrs", cooling: "Air cool", resultingHardness: "95 HBW (Peak yield strength)" }
    ],
    applications: ["Aerospace structural brackets & avionics chassis", "Bicycle frames & automotive subframes", "Marine fittings & railing", "Robotic arms & precision CNC fixtures"],
    failureRisks: ["Overaging and softening in heat-affected zone (HAZ) during welding", "Stress corrosion cracking in short transverse direction"]
  },
  {
    id: "al-7075-t6",
    name: "Aluminum 7075-T6 (Al-Zn-Mg-Cu Ultra High Strength)",
    category: "Aluminum Alloy",
    standard: "ASTM B209 / UNS A97075 / EN AW-7075",
    composition: { Al: 89.5, Zn: 5.6, Mg: 2.5, Cu: 1.6, Cr: 0.23, Fe: 0.40, Si: 0.17 },
    yieldStrength: 503,
    tensileStrength: 572,
    elongation: 11,
    hardness: "150 HBW / 87 HRB",
    density: 2.81,
    meltingRange: "477 - 635 °C",
    youngsModulus: 71.7,
    thermalConductivity: 130.0,
    thermalExpansion: 23.4,
    poissonRatio: 0.33,
    microstructure: "Dense dispersion of coherent GP zones and semi-coherent η' (MgZn2) plate-like precipitates in FCC Al matrix.",
    heatTreatments: [
      { name: "Solution Treatment", temperature: "465 - 480 °C", cooling: "Water quench", resultingHardness: "Soft state for forming" },
      { name: "Peak Aging (T6)", temperature: "120 °C for 24 hrs", cooling: "Air cool", resultingHardness: "Peak strength" },
      { name: "Overaging / Stabilization (T73)", temperature: "105°C / 8h + 175°C / 16h", cooling: "Air cool", resultingHardness: "Sacrifices ~10% strength for superior SCC resistance" }
    ],
    applications: ["Aircraft fuselage bulkheads and wing spars", "High-stress rock climbing carabiners", "Defense and missile airframes", "Precision military firearms receivers"],
    failureRisks: ["High susceptibility to Stress Corrosion Cracking (SCC) and Exfoliation corrosion in T6 temper", "Poor weldability"]
  },
  {
    id: "al-2024-t3",
    name: "Aluminum 2024-T3 (Al-Cu-Mg Damage Tolerant Aircraft Alloy)",
    category: "Aluminum Alloy",
    standard: "AMS 4037 / ASTM B209 / UNS A92024",
    composition: { Al: 92.5, Cu: 4.4, Mg: 1.5, Mn: 0.60, Fe: 0.50, Si: 0.50 },
    yieldStrength: 324,
    tensileStrength: 469,
    elongation: 18,
    hardness: "120 HBW / 75 HRB",
    density: 2.78,
    meltingRange: "502 - 638 °C",
    youngsModulus: 73.1,
    thermalConductivity: 121.0,
    thermalExpansion: 22.9,
    poissonRatio: 0.33,
    microstructure: "Naturally aged FCC aluminum matrix strengthened by coherent Cu-Mg GPB zones and S-phase (Al2CuMg) laths.",
    heatTreatments: [
      { name: "Solution Treat & Quench", temperature: "495 °C", cooling: "Cold water quench", resultingHardness: "W-temper (Instantly formable)" },
      { name: "Natural Aging (T3)", temperature: "Ambient (Room Temp) for 96+ hrs", cooling: "Air", resultingHardness: "Peak damage tolerance & fatigue resistance" }
    ],
    applications: ["Aircraft lower wing skins under cyclic tension", "Fuselage skin panels & shear webs", "Military transport truck structural ribs", "Aerospace rivets"],
    failureRisks: ["Severe galvanic & pitting corrosion if cladding (Alclad) is breached", "Unweldable by traditional fusion arc processes"]
  },
  {
    id: "alsi10mg-lpbf",
    name: "AlSi10Mg Additive Powder Alloy (LPBF T6)",
    category: "Aluminum Alloy",
    standard: "ASTM F3318 / AMS 4288 / EN 1706",
    composition: { Al: 89.3, Si: 10.0, Mg: 0.35, Fe: 0.20, Mn: 0.10, Ti: 0.05 },
    yieldStrength: 270,
    tensileStrength: 380,
    elongation: 8,
    hardness: "110 - 125 HBW",
    density: 2.67,
    meltingRange: "570 - 590 °C",
    youngsModulus: 70.0,
    thermalConductivity: 145.0,
    thermalExpansion: 21.5,
    poissonRatio: 0.33,
    microstructure: "Cellular dendritic sub-micron eutectic silicon network surrounding supersaturated primary α-Al cells.",
    heatTreatments: [
      { name: "Stress Relief (SR)", temperature: "300 °C for 2h", cooling: "Air cool", resultingHardness: "Eliminates LPBF residual stress, retains cellular Si" },
      { name: "Full T6 Cycle", temperature: "535°C / 1h (water quench) + 160°C / 6h", cooling: "Air cool", resultingHardness: "Spheroidizes Si network, precipitates β'' Mg2Si" }
    ],
    applications: ["3D printed lightweight heat exchangers", "Topology optimized aerospace bracketry", "Motorsport engine intake manifolds", "Space satellite structural brackets"],
    failureRisks: ["Anisotropic fatigue life due to layer boundary lack-of-fusion (LoF) defects", "Gas porosity from trapped argon/nitrogen"]
  },

  // --- COPPER ALLOYS ---
  {
    id: "cu-c11000",
    name: "C11000 Electrolytic Tough Pitch (ETP) Pure Copper",
    category: "Copper Alloy",
    standard: "ASTM B152 / UNS C11000 / CW004A / DIN 2.0060",
    composition: { Cu: 99.95, O: 0.04, Fe: 0.005, Pb: 0.005 },
    yieldStrength: 69,
    tensileStrength: 220,
    elongation: 45,
    hardness: "40 - 55 HRF / 45 HBW (Annealed)",
    density: 8.89,
    meltingRange: "1065 - 1083 °C",
    youngsModulus: 115,
    thermalConductivity: 390.0,
    thermalExpansion: 16.9,
    poissonRatio: 0.34,
    microstructure: "Equiaxed FCC copper grains with dispersed cuprous oxide (Cu2O) spheroids along grain boundaries.",
    heatTreatments: [
      { name: "Recrystallization Anneal", temperature: "400 - 650 °C", cooling: "Water quench or air cool", resultingHardness: "40 HRF (Maximum electrical conductivity 101% IACS)" }
    ],
    applications: ["Electrical busbars, switchgear & power cables", "Transformer windings and high-current contacts", "Semiconductor heat spreaders & cold plates", "Architectural roofing & gutters"],
    failureRisks: ["Hydrogen embrittlement if brazed or annealed above 370°C in reducing hydrogen gas (H2 + Cu2O -> H2O steam blisters)"]
  },
  {
    id: "cu-c26000",
    name: "C26000 Cartridge Brass (70/30 Alpha Brass)",
    category: "Copper Alloy",
    standard: "ASTM B19 / UNS C26000 / CW505L / CuZn30",
    composition: { Cu: 70.0, Zn: 29.9, Pb: 0.05, Fe: 0.05 },
    yieldStrength: 150,
    tensileStrength: 360,
    elongation: 65,
    hardness: "60 HRB / 75 HBW (Cold Rolled 1/4 Hard)",
    density: 8.53,
    meltingRange: "915 - 955 °C",
    youngsModulus: 110,
    thermalConductivity: 120.0,
    thermalExpansion: 19.9,
    poissonRatio: 0.35,
    microstructure: "Single-phase alpha (α) solid solution FCC brass with profound deep-drawing capability.",
    heatTreatments: [
      { name: "Deep Draw Anneal", temperature: "450 - 600 °C", cooling: "Water quench", resultingHardness: "Restores >60% ductility for multi-stage stamping" },
      { name: "Stress Relief Anneal", temperature: "260 °C (1h)", cooling: "Air cool", resultingHardness: "Prevents season cracking / ammonia SCC" }
    ],
    applications: ["Ammunition cartridge cases", "Musical instruments (trumpets, horns)", "Automotive radiator cores & thermostat bellows", "Plumbing fittings & decorative hardware"],
    failureRisks: ["Season cracking / Stress Corrosion Cracking (SCC) in presence of trace atmospheric ammonia or amines"]
  },
  {
    id: "cu-c17200",
    name: "C17200 Beryllium Copper (Alloy 25 High Strength)",
    category: "Copper Alloy",
    standard: "ASTM B194 / UNS C17200 / CW101C / AMS 4533",
    composition: { Cu: 97.55, Be: 1.90, Co: 0.20, Ni: 0.20, Fe: 0.15 },
    yieldStrength: 1250,
    tensileStrength: 1400,
    elongation: 6,
    hardness: "38 - 44 HRC (TH04 Peak Aged)",
    density: 8.25,
    meltingRange: "865 - 980 °C",
    youngsModulus: 131,
    thermalConductivity: 105.0,
    thermalExpansion: 17.8,
    poissonRatio: 0.30,
    microstructure: "Precipitation-hardened FCC copper matrix with dense coherent γ'' and γ' (CuBe) intermetallic disk precipitates.",
    heatTreatments: [
      { name: "Solution Anneal", temperature: "790 - 800 °C", cooling: "Rapid water quench", resultingHardness: "Soft A-temper (easy formability)" },
      { name: "Precipitation Age (HT)", temperature: "315 °C for 2-3 hrs", cooling: "Air cool", resultingHardness: "39-44 HRC (>1200 MPa yield, highest of any Cu alloy)" }
    ],
    applications: ["Non-sparking safety tools for explosive gas environments", "Aerospace electrical spring contacts & multi-pin sockets", "Downhole directional drilling MWD housings", "Plastic mold core cooling inserts"],
    failureRisks: ["Extreme inhalation toxicity of airborne beryllium dust during machining or grinding (requires HEPA ventilation)"]
  },
  {
    id: "cu-c93200",
    name: "C93200 SAE 660 High-Leaded Tin Bearing Bronze",
    category: "Copper Alloy",
    standard: "ASTM B505 / UNS C93200 / SAE 660 / RG7",
    composition: { Cu: 82.0, Sn: 7.0, Pb: 7.0, Zn: 3.0, Ni: 0.8, Fe: 0.20 },
    yieldStrength: 125,
    tensileStrength: 240,
    elongation: 15,
    hardness: "65 - 75 HBW",
    density: 8.93,
    meltingRange: "855 - 990 °C",
    youngsModulus: 100,
    thermalConductivity: 59.0,
    thermalExpansion: 18.0,
    poissonRatio: 0.34,
    microstructure: "Alpha copper-tin solid solution dendrites with fine globular lead particles dispersed in inter-dendritic channels.",
    heatTreatments: [
      { name: "Continuous Cast (As-Cast)", temperature: "N/A", cooling: "Water-cooled graphite die", resultingHardness: "70 HBW (Fine uniform lead distribution)" }
    ],
    applications: ["Journal bushings & sleeve bearings", "Wear plates and thrust washers for machine tools", "Pump impellers and hydraulic fittings", "Automotive starter bushings"],
    failureRisks: ["Lead segregation during slow sand casting", "Environmental restrictions on heavy lead content (RoHS exemptions required)"]
  },

  // --- TITANIUM ALLOYS ---
  {
    id: "ti-cp-grade2",
    name: "Titanium Grade 2 Commercially Pure (CP-Ti)",
    category: "Titanium Alloy",
    standard: "ASTM B265 / UNS R50400 / ISO 5832-2 / AMS 4902",
    composition: { Ti: 99.325, Fe: 0.30, O: 0.25, C: 0.08, N: 0.03, H: 0.015 },
    yieldStrength: 345,
    tensileStrength: 485,
    elongation: 24,
    hardness: "160 - 200 HBW / ~85 HRB",
    density: 4.51,
    meltingRange: "1665 - 1675 °C",
    youngsModulus: 103,
    thermalConductivity: 21.9,
    thermalExpansion: 8.6,
    poissonRatio: 0.37,
    microstructure: "Single-phase equiaxed alpha (α) HCP crystal structure with high chemical resistance.",
    heatTreatments: [
      { name: "Recrystallization Annealing", temperature: "650 - 700 °C for 1h", cooling: "Air cool", resultingHardness: "165 HBW" },
      { name: "Stress Relieving", temperature: "500 - 550 °C for 0.5h", cooling: "Air cool", resultingHardness: "Relieves cold forming stresses" }
    ],
    applications: ["Chemical process plate heat exchangers", "Flue gas desulfurization units", "Desalination plant piping", "Dental and cranial trauma plates"],
    failureRisks: ["Galling during sliding contact", "Creep above 300°C"]
  },
  {
    id: "ti-6al-4v",
    name: "Titanium Ti-6Al-4V (Grade 5 / Alpha-Beta Alloy)",
    category: "Titanium Alloy",
    standard: "ASTM B265 / UNS R56400 / AMS 4911 / ISO 5832-3",
    composition: { Ti: 89.49, Al: 6.0, V: 4.0, Fe: 0.25, O: 0.18, C: 0.05, N: 0.03 },
    yieldStrength: 880,
    tensileStrength: 950,
    elongation: 14,
    hardness: "34 - 36 HRC (Mill Annealed)",
    density: 4.43,
    meltingRange: "1604 - 1660 °C",
    youngsModulus: 114,
    thermalConductivity: 6.7,
    thermalExpansion: 8.6,
    poissonRatio: 0.34,
    microstructure: "Two-phase dual α (HCP, Al-stabilized) + β (BCC, V-stabilized) microstructure (bimodal equiaxed or lamellar Widmanstätten basketweave).",
    heatTreatments: [
      { name: "Mill Annealing", temperature: "700 - 785 °C for 2h", cooling: "Air cool", resultingHardness: "32-35 HRC" },
      { name: "Solution Treating & Aging (STA)", temperature: "955 °C + Quench, Age @ 540 °C", cooling: "Air cool", resultingHardness: "38-42 HRC (>1050 MPa yield)" }
    ],
    applications: ["Jet engine fan blades & compressor disks", "Orthopedic hip & knee prostheses", "High-performance aerospace fasteners", "Deep sea submersibles"],
    failureRisks: ["Oxygen/Nitrogen alpha-case embrittlement above 500°C", "Galling during sliding contact without surface treatment"]
  },
  {
    id: "ti-6242",
    name: "Ti-6Al-2Sn-4Zr-2Mo High-Temperature Near-Alpha Alloy",
    category: "Titanium Alloy",
    standard: "AMS 4919 / UNS R54620 / ASTM B348",
    composition: { Ti: 85.82, Al: 6.0, Sn: 2.0, Zr: 4.0, Mo: 2.0, Si: 0.08, Fe: 0.10 },
    yieldStrength: 930,
    tensileStrength: 1010,
    elongation: 13,
    hardness: "36 - 38 HRC (Duplex Annealed)",
    density: 4.54,
    meltingRange: "1650 - 1700 °C",
    youngsModulus: 114,
    thermalConductivity: 7.5,
    thermalExpansion: 9.0,
    poissonRatio: 0.32,
    microstructure: "Near-alpha microstructure with fine silicide precipitates offering creep resistance up to 540°C.",
    heatTreatments: [
      { name: "Duplex Anneal", temperature: "970 °C / 1h (Air cool) + 595 °C / 8h (Air cool)", cooling: "Air cool", resultingHardness: "Optimized creep rupture strength" }
    ],
    applications: ["Gas turbine high-pressure compressor blades & disks", "Afterburner duct assemblies", "Hypersonic missile skin panels", "Motorsport exhaust valves"],
    failureRisks: ["Hot salt stress corrosion cracking at sustained temperatures >400°C"]
  },

  // --- NICKEL SUPERALLOYS ---
  {
    id: "inconel-718",
    name: "Inconel 718 Nickel-Base Superalloy (Precipitation Hardened)",
    category: "Nickel Superalloy",
    standard: "AMS 5662 / UNS N07718 / ASTM B637",
    composition: { Ni: 53.0, Cr: 19.0, Fe: 18.46, Nb: 5.1, Mo: 3.0, Ti: 0.9, Al: 0.5, C: 0.04 },
    yieldStrength: 1100,
    tensileStrength: 1375,
    elongation: 15,
    hardness: "40 - 45 HRC (Fully Aged)",
    density: 8.19,
    meltingRange: "1260 - 1335 °C",
    youngsModulus: 205,
    thermalConductivity: 11.4,
    thermalExpansion: 13.0,
    poissonRatio: 0.29,
    microstructure: "FCC γ matrix strengthened by disc-shaped coherent γ'' (Ni3Nb body-centered tetragonal) and spherical γ' (Ni3(Al,Ti) L12) precipitates.",
    heatTreatments: [
      { name: "Solution Anneal", temperature: "980 °C for 1h", cooling: "Air/Water quench", resultingHardness: "Dissolves δ-phase (Ni3Nb orthorhombic)" },
      { name: "Double Aging Cycle", temperature: "720 °C / 8h, Furnace cool to 620 °C / 8h", cooling: "Air cool", resultingHardness: "42-45 HRC (Retains strength up to 650°C)" }
    ],
    applications: ["Gas turbine discs, blades & casing", "Rocket engine thrust chambers & turbopumps", "High-pressure subsea wellhead valves", "Nuclear reactor fuel assembly springs"],
    failureRisks: ["Thermal degradation above 650°C due to γ'' transformation into equilibrium acicular δ-phase", "Strain-age cracking during weld repair"]
  },
  {
    id: "inconel-625",
    name: "Inconel 625 Solid-Solution Strengthened Superalloy",
    category: "Nickel Superalloy",
    standard: "AMS 5599 / UNS N06625 / ASTM B443 / EN 2.4856",
    composition: { Ni: 61.4, Cr: 21.5, Mo: 9.0, Nb: 3.65, Fe: 4.0, Ti: 0.20, Al: 0.20, C: 0.05 },
    yieldStrength: 517,
    tensileStrength: 930,
    elongation: 45,
    hardness: "20 - 24 HRC (Annealed Grade 1)",
    density: 8.44,
    meltingRange: "1290 - 1350 °C",
    youngsModulus: 207,
    thermalConductivity: 9.8,
    thermalExpansion: 12.8,
    poissonRatio: 0.31,
    microstructure: "FCC austenitic matrix solid-solution strengthened by Molybdenum and Niobium with excellent weldability.",
    heatTreatments: [
      { name: "Mill Anneal (Grade 1)", temperature: "980 - 1050 °C", cooling: "Rapid air or water quench", resultingHardness: "Maximum corrosion & fatigue resistance" },
      { name: "Solution Anneal (Grade 2)", temperature: "1090 - 1200 °C", cooling: "Air cool", resultingHardness: "Coarser grain size for high-temp creep resistance >600°C" }
    ],
    applications: ["Subsea mooring cables & exhaust scrubbers", "Chemical reactor vessels & sour gas piping", "Aerospace thrust reverser exhaust systems", "Nuclear waste containment canisters"],
    failureRisks: ["Pitting in aggressive stagnant chlorine bleach environments", "Intermetallic Laves phase precipitation during prolonged exposure at 650-800°C"]
  },
  {
    id: "cmsx-4",
    name: "CMSX-4 Second Generation Single-Crystal Superalloy",
    category: "Nickel Superalloy",
    standard: "Aerospace Proprietary / AMS Specification",
    composition: { Ni: 61.7, Co: 9.0, Cr: 6.5, W: 6.0, Re: 3.0, Ta: 6.5, Al: 5.6, Ti: 1.0, Mo: 0.6, Hf: 0.1 },
    yieldStrength: 1050,
    tensileStrength: 1280,
    elongation: 18,
    hardness: "44 - 48 HRC (Post Homogenization & Aging)",
    density: 8.70,
    meltingRange: "1335 - 1380 °C",
    youngsModulus: 130, // [001] crystal orientation
    thermalConductivity: 12.0,
    thermalExpansion: 14.5,
    poissonRatio: 0.38,
    microstructure: "Single-crystal (SX) <001> aligned FCC γ matrix containing ~70% volume fraction cuboidal ordered γ' (Ni3(Al,Ta)) precipitates with Rhenium creep retardation.",
    heatTreatments: [
      { name: "Multi-Step Solutionize", temperature: "1280 - 1318 °C (graded 12h hold)", cooling: "Gas fan quench", resultingHardness: "Fully dissolves eutectic γ/γ' pools without incipient melting" },
      { name: "Primary Aging", temperature: "1140 °C for 4h", cooling: "Air cool", resultingHardness: "Precipitates uniform 0.4 µm cuboidal γ'" },
      { name: "Secondary Aging", temperature: "870 °C for 16h", cooling: "Air cool", resultingHardness: "Completes γ' packing fraction" }
    ],
    applications: ["High-pressure turbine (HPT) first-stage rotating blades in commercial jet engines", "Military combat fighter engine turbine vanes", "Heavy-duty industrial gas turbine hot-section airfoils"],
    failureRisks: ["High angle grain boundary defects (freckling during directional solidification)", "TCP phase (Topologically Close-Packed) precipitation after 10,000+ hours at 1000°C"]
  },

  // --- MAGNESIUM ALLOYS ---
  {
    id: "mg-az31b",
    name: "AZ31B Wrought Magnesium Alloy (Mg-Al-Zn)",
    category: "Magnesium Alloy",
    standard: "ASTM B107 / UNS M11311 / EN MB1001",
    composition: { Mg: 95.595, Al: 3.0, Zn: 1.0, Mn: 0.30, Si: 0.10, Fe: 0.005 },
    yieldStrength: 200,
    tensileStrength: 260,
    elongation: 15,
    hardness: "65 - 73 HBW",
    density: 1.77,
    meltingRange: "605 - 630 °C",
    youngsModulus: 45.0,
    thermalConductivity: 96.0,
    thermalExpansion: 26.0,
    poissonRatio: 0.35,
    microstructure: "HCP magnesium solid solution matrix with fine intermetallic Mg17Al12 particles (lightest structural metal).",
    heatTreatments: [
      { name: "Annealing (O-Temper)", temperature: "345 °C for 2h", cooling: "Air cool", resultingHardness: "Restores ductility for warm stamping (220-260°C)" }
    ],
    applications: ["Laptop & mobile electronic chassis", "Automotive steering wheel armatures & seat frames", "Aerospace electronics vibration dampening housings", "Lightweight motorsport intake ducting"],
    failureRisks: ["Severe galvanic corrosion when coupled to carbon steel or aluminum without insulating washers", "Flammability of fine machining chips"]
  },
  {
    id: "mg-we43",
    name: "WE43 Aerospace High-Temperature Rare-Earth Magnesium Alloy",
    category: "Magnesium Alloy",
    standard: "AMS 4427 / ASTM B80 / UNS M18430",
    // "RE" is not an element symbol (the CALPHAD solver refuses it as UNKNOWN_ELEMENT).
    // ASTM B80 WE43: Y 3.7-4.3, Nd 2.0-2.5, heavy rare earths (mainly Yb, Er, Dy, Gd;
    // split not specified) ~1, Zr >= 0.4, Mg balance. Nd is listed at its nominal 2.25;
    // the unspecified heavy-RE remainder is not itemised and sits in the Mg balance.
    composition: { Mg: 93.3, Y: 4.0, Nd: 2.25, Zr: 0.45 },
    yieldStrength: 195,
    tensileStrength: 280,
    elongation: 7,
    hardness: "85 - 90 HBW (T6)",
    density: 1.84,
    meltingRange: "540 - 640 °C",
    youngsModulus: 44.2,
    thermalConductivity: 51.0,
    thermalExpansion: 26.7,
    poissonRatio: 0.27,
    microstructure: "Fine-grained HCP Mg matrix with Yttrium/Neodymium precipitate phases (β', β1) resisting creep up to 250°C.",
    heatTreatments: [
      { name: "T6 Full Heat Treatment", temperature: "525 °C / 8h (water quench) + 250 °C / 16h", cooling: "Air cool", resultingHardness: "Peak strength and enhanced corrosion resistance" }
    ],
    applications: ["Helicopter transmission & gearbox casings", "Missile guidance system frames", "High-performance motorsport wheels", "Bio-absorbable orthopaedic bone screws"],
    failureRisks: ["Sensitive to surface pitting in salt fog without chemical conversion coating / anodizing"]
  },

  // --- REFRACTORY & SPECIALTY ---
  {
    id: "tantalum-grade1",
    name: "Tantalum Grade 1 Unalloyed (Corrosion & Bio-Inert)",
    category: "Refractory & Specialty",
    standard: "ASTM B365 / UNS R05200",
    composition: { Ta: 99.915, Nb: 0.05, O: 0.015, C: 0.01, N: 0.01 },
    yieldStrength: 165,
    tensileStrength: 240,
    elongation: 40,
    hardness: "90 - 120 HV10",
    density: 16.65,
    meltingRange: "2996 - 3017 °C",
    youngsModulus: 186,
    thermalConductivity: 57.4,
    thermalExpansion: 6.3,
    poissonRatio: 0.34,
    microstructure: "Body-Centered Cubic (BCC) high-purity single-phase refractory grain matrix with natural self-healing Ta2O5 dielectric passivating film.",
    heatTreatments: [
      { name: "High Vacuum Recrystallization", temperature: "1050 - 1300 °C (10⁻⁶ mbar)", cooling: "Vacuum furnace cool", resultingHardness: "Restores extreme ductility for deep drawing" }
    ],
    applications: ["Aggressive acid chemical reactor linings (hydrochloric, sulfuric, nitric)", "Tantalum electrolytic capacitors", "Surgical cranial plates & orthopedic trabecular metal implants", "Thermocouple protection wells for molten glass"],
    failureRisks: ["Extreme oxidation and catastrophic disintegration in air above 400°C (must be processed in high vacuum or inert argon)"]
  },

  // --- CERAMICS & CARBIDES ---
  {
    id: "wc-co",
    name: "Tungsten Carbide - 6% Cobalt (Cemented Carbide)",
    category: "Ceramic & Carbide",
    standard: "ISO K10-K20 / ASTM B777 / ANSI C-2",
    // 94 wt% WC written as its elements (stoichiometric WC, W 183.84 / C 12.011 g/mol,
    // W mass fraction 0.93867): W 88.235 + C 5.765 = 94.0 wt%. "WC" is a compound, not an
    // element symbol, so the CALPHAD solver refuses it (UNKNOWN_ELEMENT).
    composition: { W: 88.235, C: 5.765, Co: 6.0 },
    yieldStrength: 3500, // compressive
    tensileStrength: 1800, // transverse rupture strength (TRS)
    elongation: 0.2,
    hardness: "92 - 93.5 HRA / ~1600 HV30",
    density: 14.95,
    meltingRange: "2870 °C (WC phase)",
    youngsModulus: 630,
    thermalConductivity: 84.0,
    thermalExpansion: 5.4,
    poissonRatio: 0.22,
    microstructure: "Angular faceted hexagonal WC grains embedded in a thin ductile metallic Cobalt binder phase network.",
    heatTreatments: [
      { name: "Liquid Phase Sintering", temperature: "1380 - 1450 °C (Vacuum / HIP)", cooling: "Controlled furnace cool", resultingHardness: "Full densification with pore-free structure" }
    ],
    applications: ["CNC metal cutting inserts & endmills", "Mining drill bits & road milling teeth", "Wire drawing dies", "High-pressure fluid waterjet nozzles"],
    failureRisks: ["Catastrophic brittle fracture under impact shock", "Cobalt binder leaching in acidic environments (pH < 7)"]
  }
];
