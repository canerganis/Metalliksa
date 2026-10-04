/**
 * E-pH test-point presets, parser and reference electrode transformation utilities.
 * The presets are ILLUSTRATIVE scenarios: they cite no dataset, publication or laboratory record, so
 * they are not measured data (AGENTS.md: measured, literature, computed and synthetic data are kept
 * apart). Tabular CSV/TSV points a user loads are the only measured data the studio can show.
 */

import { ExperimentalEpHEntry, ExperimentalEpHTrajectoryPreset, ReferenceElectrode } from "../types/pourbaix";

export const REF_OFFSETS_VS_SHE: { [k in ReferenceElectrode]: number } = {
  SHE: 0.000,
  SCE: 0.241,
  "Ag/AgCl (3M KCl)": 0.207,
  "Ag/AgCl (Sat KCl)": 0.197,
  CSE: 0.316,
  MMS: 0.640,
};

/** Shown wherever preset points are drawn or listed. */
export const PRESET_POINTS_NOTE = "Preset points are illustrative scenarios, not measured data: no source is cited.";

export const EXPERIMENTAL_POURBAIX_PRESETS: ExperimentalEpHTrajectoryPreset[] = [
  {
    id: "fe_marine_crevice",
    name: "Carbon Steel (AISI 1018) — Seawater Occluded Crevice & Under-Deposit Corrosion",
    element: "Fe",
    description: "Illustrative scenario, not measured data (no source is cited): In-situ micro-electrode monitoring of carbon steel undergoing local acidification under marine fouling and subsequent impressed current cathodic protection (ICCP).",
    environmentSummary: "3.5 wt% NaCl Aerated Seawater (T = 25°C, [Cl⁻] = 19,000 ppm)",
    points: [
      {
        id: "fe_p1",
        name: "Stage 1: Bulk Aerated Seawater (Open Exposure)",
        pH: 8.2,
        potential_V: -0.42,
        refElectrode: "SCE",
        currentDensity_uA_cm2: 12.4,
        timeHours: 1.0,
        stageName: "Initial Passivation / Magnetite Nucleation",
        notes: "Freely corroding specimen forming dark green-rust / mixed oxide."
      },
      {
        id: "fe_p2",
        name: "Stage 2: Bio-Fouling Settlement & Diffusion Barrier",
        pH: 7.1,
        potential_V: -0.48,
        refElectrode: "SCE",
        currentDensity_uA_cm2: 24.8,
        timeHours: 48.0,
        stageName: "Oxygen Depletion Under Deposit",
        notes: "Dissolved oxygen diffusion blocked under slime layer; potential shifts negative."
      },
      {
        id: "fe_p3",
        name: "Stage 3: Occluded Crevice Autocatalytic Acidification",
        pH: 3.4,
        potential_V: -0.38,
        refElectrode: "SCE",
        currentDensity_uA_cm2: 185.0,
        timeHours: 120.0,
        stageName: "Active Crevice Dissolution",
        notes: "Fe²⁺ hydrolysis (Fe²⁺ + 2H₂O → Fe(OH)₂ + 2H⁺) drives severe local acidification and rapid active dissolution."
      },
      {
        id: "fe_p4",
        name: "Stage 4: Impressed Current Cathodic Protection (ICCP Activated)",
        pH: 8.8,
        potential_V: -1.05,
        refElectrode: "CSE",
        currentDensity_uA_cm2: 0.08,
        timeHours: 144.0,
        stageName: "Full Cathodic Immunity",
        notes: "Cathodic protection depressed potential below -0.85V vs CSE immunity criterion. Metal loss arrested."
      }
    ]
  },
  {
    id: "ss316l_pitting_hydrolysis",
    name: "Stainless Steel 316L — In-Situ Pit Acidification & Transpassive Scan",
    element: "Cr",
    description: "Illustrative scenario, not measured data (no source is cited): Micro-capillary chemical profiling inside single artificial pitting cell in 1M NaCl + potentiodynamic anodic polarizations.",
    environmentSummary: "1.0 M NaCl (35,500 ppm Cl⁻), Aerated Acid/Neutral, Ambient 25°C",
    points: [
      {
        id: "ss_p1",
        name: "Point A: Passive State in Neutral Brine",
        pH: 7.0,
        potential_V: +0.12,
        refElectrode: "Ag/AgCl (3M KCl)",
        currentDensity_uA_cm2: 0.15,
        timeHours: 2.0,
        stageName: "Stable Cr₂O₃ Passive Film",
        notes: "Low passive current density; nano-metric chromia barrier active."
      },
      {
        id: "ss_p2",
        name: "Point B: Pre-Pitting Metastable Current Spikes",
        pH: 6.2,
        potential_V: +0.48,
        refElectrode: "Ag/AgCl (3M KCl)",
        currentDensity_uA_cm2: 8.2,
        timeHours: 6.0,
        stageName: "Metastable Pitting Events",
        notes: "Chloride adsorption displaces oxygen; transient current transients observed."
      },
      {
        id: "ss_p3",
        name: "Point C: Deep Pit Nucleus Core (Local Acid Hydrolysis)",
        pH: 1.8,
        potential_V: +0.32,
        refElectrode: "Ag/AgCl (3M KCl)",
        currentDensity_uA_cm2: 4500.0,
        timeHours: 12.0,
        stageName: "Autocatalytic Stable Pit Growth",
        notes: "Cr³⁺ hydrolysis drives internal pit pH to 1.8 with 4.5 mA/cm² dissolution rate."
      },
      {
        id: "ss_p4",
        name: "Point D: Transpassive Anodic Over-Oxidation",
        pH: 7.0,
        potential_V: +1.25,
        refElectrode: "SHE",
        currentDensity_uA_cm2: 820.0,
        timeHours: 14.0,
        stageName: "Transpassive CrO₄²⁻ Formation",
        notes: "Oxidation of insoluble Cr(III) oxide to soluble hexavalent chromate (CrO₄²⁻)."
      }
    ]
  },
  {
    id: "al7075_exco_saline",
    name: "Aluminum AA7075-T651 — Atmospheric Salt Fog & Exfoliation Acidification",
    element: "Al",
    description: "Illustrative scenario, not measured data (no source is cited): ASTM G34 EXCO testing titration monitoring intergranular attack, pit nucleation, and alkaline caustic rinsing.",
    environmentSummary: "EXCO Solution (4.0 M NaCl + 0.5 M KNO₃ + 0.1 M HNO₃), T = 25°C",
    points: [
      {
        id: "al_p1",
        name: "Scan 1: Atmospheric Dry Passive State",
        pH: 6.5,
        potential_V: -0.65,
        refElectrode: "SHE",
        currentDensity_uA_cm2: 0.8,
        timeHours: 0.5,
        stageName: "Native Al₂O₃·3H₂O Barrier",
        notes: "Passivated surface in ambient air."
      },
      {
        id: "al_p2",
        name: "Scan 2: Acid Salt Fog Wetting (EXCO Immersion)",
        pH: 2.2,
        potential_V: -0.74,
        refElectrode: "SHE",
        currentDensity_uA_cm2: 320.0,
        timeHours: 4.0,
        stageName: "Severe Acid Intergranular Attack",
        notes: "Acidic dissolution of anodic η-phase (MgZn₂) precipitate along grain boundaries."
      },
      {
        id: "al_p3",
        name: "Scan 3: Occluded Pit Base (Severe Chloride Attack)",
        pH: 3.5,
        potential_V: -0.58,
        refElectrode: "SHE",
        currentDensity_uA_cm2: 850.0,
        timeHours: 24.0,
        stageName: "Autocatalytic Exfoliation Blistering",
        notes: "Hydrogen gas generation and voluminous Al(OH)₃ wedge grains apart."
      },
      {
        id: "al_p4",
        name: "Scan 4: Caustic Alkaline Degreasing Bath",
        pH: 12.8,
        potential_V: -1.35,
        refElectrode: "SHE",
        currentDensity_uA_cm2: 1200.0,
        timeHours: 25.0,
        stageName: "Amphoteric Aluminate Dissolution",
        notes: "Alkaline attack converting aluminum into soluble AlO₂⁻ aluminate."
      }
    ]
  },
  {
    id: "ti_biomed_saline",
    name: "Titanium Ti-6Al-4V — Orthopedic Implant in Simulated Body Fluid (SBF)",
    element: "Ti",
    description: "Illustrative scenario, not measured data (no source is cited): Electrochemical testing of surgical implant subjected to peri-implant inflammation and oxidative burst (H₂O₂).",
    environmentSummary: "Simulated Body Fluid (pH 7.4, 0.9% NaCl, 37°C physiological)",
    points: [
      {
        id: "ti_p1",
        name: "Baseline: Resting Bone Interface",
        pH: 7.4,
        potential_V: +0.15,
        refElectrode: "Ag/AgCl (3M KCl)",
        currentDensity_uA_cm2: 0.02,
        timeHours: 24.0,
        stageName: "Ultra-Stable TiO₂ Passivation",
        notes: "Zero detectable metal ion release; complete biocompatibility."
      },
      {
        id: "ti_p2",
        name: "Inflammation: Macrophage Oxidative Burst (H₂O₂ release)",
        pH: 5.2,
        potential_V: +0.68,
        refElectrode: "Ag/AgCl (3M KCl)",
        currentDensity_uA_cm2: 0.18,
        timeHours: 72.0,
        stageName: "Oxidative Potential Elevation",
        notes: "Inflammatory cytokines and peroxide elevate OCP without breaking TiO₂ barrier."
      },
      {
        id: "ti_p3",
        name: "Severe Infection: Local Acidosis with Fluoride Exposure",
        pH: 3.0,
        potential_V: -0.10,
        refElectrode: "Ag/AgCl (3M KCl)",
        currentDensity_uA_cm2: 4.5,
        timeHours: 120.0,
        stageName: "Acid Fluoride Stressing",
        notes: "Still within passive TiO₂ stability zone, slight current elevation."
      }
    ]
  },
  {
    id: "cu_potable_water",
    name: "Copper Plumbing Pipe — Potable Water Pitting & Blue Water Syndrome",
    element: "Cu",
    description: "Illustrative scenario, not measured data (no source is cited): Examination of cold potable water pipe pitting caused by high dissolved oxygen and sulfate/chloride ratio.",
    environmentSummary: "Municipal Drinking Water (pH 6.8 - 8.5, Aerated, 45 ppm Cl⁻)",
    points: [
      {
        id: "cu_p1",
        name: "Point 1: High Dissolved Oxygen Fresh Water",
        pH: 6.5,
        potential_V: +0.38,
        refElectrode: "SHE",
        currentDensity_uA_cm2: 45.0,
        timeHours: 12.0,
        stageName: "Active Cu²⁺ Dissolution (Blue Water)",
        notes: "Aerated acidic water dissolves copper into blue Cu²⁺ ions."
      },
      {
        id: "cu_p2",
        name: "Point 2: Stable Patina Formation (Cuprite Cu₂O)",
        pH: 8.4,
        potential_V: +0.22,
        refElectrode: "SHE",
        currentDensity_uA_cm2: 0.4,
        timeHours: 720.0,
        stageName: "Cu₂O / Malachite Protective Patina",
        notes: "Alkaline buffering precipitates protective reddish-brown Cu₂O layer."
      }
    ]
  }
];

/**
 * Parses user uploaded CSV/TSV experimental test data into typed EpHEntry list
 */
export function parseExperimentalEpHTable(rawText: string, defaultRef: ReferenceElectrode = "SHE"): {
  success: boolean;
  points: ExperimentalEpHEntry[];
  error?: string;
} {
  try {
    const lines = rawText.trim().split(/\r?\n/).filter((l) => l.trim().length > 0);
    if (lines.length === 0) {
      return { success: false, points: [], error: "Uploaded text is empty." };
    }

    const separator = lines[0].includes("\t") ? "\t" : lines[0].includes(";") ? ";" : ",";
    const headerLine = lines[0].toLowerCase();
    const headers = headerLine.split(separator).map((h) => h.trim().replace(/^["']|["']$/g, ""));

    // Find column indexes
    let phIdx = headers.findIndex((h) => h === "ph" || h.includes("ph"));
    let potIdx = headers.findIndex((h) => h.includes("pot") || h.includes("e_v") || h.includes("e (v)") || h === "e" || h === "v");
    let nameIdx = headers.findIndex((h) => h.includes("name") || h.includes("sample") || h.includes("point") || h.includes("id"));
    let refIdx = headers.findIndex((h) => h.includes("ref") || h.includes("electrode"));
    let iIdx = headers.findIndex((h) => h.includes("curr") || h.includes("icorr") || h.includes("i_") || h.includes("density") || h.includes("ua"));
    let timeIdx = headers.findIndex((h) => h.includes("time") || h.includes("hour") || h.includes("t_"));
    let stageIdx = headers.findIndex((h) => h.includes("stage") || h.includes("step") || h.includes("state"));
    let notesIdx = headers.findIndex((h) => h.includes("note") || h.includes("desc") || h.includes("comment"));

    let dataStartIndex = 0;
    if (phIdx !== -1 || potIdx !== -1) {
      // First line was indeed a header
      dataStartIndex = 1;
    } else {
      // No recognized headers: assume col 0 is pH, col 1 is E
      phIdx = 0;
      potIdx = 1;
      dataStartIndex = 0;
    }

    if (phIdx === -1) phIdx = 0;
    if (potIdx === -1) potIdx = 1;

    const points: ExperimentalEpHEntry[] = [];

    for (let i = dataStartIndex; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line || line.startsWith("#") || line.startsWith("//")) continue;

      const cols = line.split(separator).map((c) => c.trim().replace(/^["']|["']$/g, ""));
      if (cols.length <= Math.max(phIdx, potIdx)) continue;

      const phVal = parseFloat(cols[phIdx]);
      const potVal = parseFloat(cols[potIdx]);

      if (isNaN(phVal) || isNaN(potVal)) continue;

      const ptName = nameIdx !== -1 && cols[nameIdx] ? cols[nameIdx] : `Measured Pt #${points.length + 1}`;
      let refElec: ReferenceElectrode = defaultRef;
      if (refIdx !== -1 && cols[refIdx]) {
        const refStr = cols[refIdx].toUpperCase();
        if (refStr.includes("SCE")) refElec = "SCE";
        else if (refStr.includes("AG/AGCL") || refStr.includes("AGCL")) refElec = "Ag/AgCl (3M KCl)";
        else if (refStr.includes("CSE")) refElec = "CSE";
        else if (refStr.includes("MMS")) refElec = "MMS";
        else if (refStr.includes("SHE")) refElec = "SHE";
      }

      const currentDensity = iIdx !== -1 && cols[iIdx] && !isNaN(parseFloat(cols[iIdx])) ? parseFloat(cols[iIdx]) : undefined;
      const timeHours = timeIdx !== -1 && cols[timeIdx] && !isNaN(parseFloat(cols[timeIdx])) ? parseFloat(cols[timeIdx]) : undefined;
      const stageName = stageIdx !== -1 && cols[stageIdx] ? cols[stageIdx] : undefined;
      const notes = notesIdx !== -1 && cols[notesIdx] ? cols[notesIdx] : undefined;

      points.push({
        id: `custom_exp_${points.length + 1}_${Date.now()}`,
        name: ptName,
        pH: phVal,
        potential_V: potVal,
        refElectrode: refElec,
        currentDensity_uA_cm2: currentDensity,
        timeHours,
        stageName,
        notes,
      });
    }

    if (points.length === 0) {
      return { success: false, points: [], error: "No valid (pH, Potential) data rows found in input." };
    }

    return { success: true, points };
  } catch (err: any) {
    return { success: false, points: [], error: err.message || "Failed to parse CSV/TSV table." };
  }
}
