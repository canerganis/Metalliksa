import opticalTable4 from "../../data/benchmark/nist-amb2022-03-optical/table4-aggregate-v2.json";

export type MeltPoolLiteratureKind = "measured" | "asymptotic" | "no-measured-track";

export type MeltPoolLiteratureCase = {
  id: string;
  label: string;
  material: string;
  laserPower_W: number | null;
  scanSpeed_mm_s: number | null;
  beamDiameter_um: number | null;
  preheatTemp_C: number | null;
  layerThickness_um: number | null;
  hatchSpacing_um: number | null;
  publishedWidth_um: number | null;
  publishedDepth_um: number | null;
  widthStdDev_um?: number;
  depthStdDev_um?: number;
  measurementCount?: number;
  publishedRegime: "Conduction" | "Transition" | "Keyhole" | null;
  kind: MeltPoolLiteratureKind;
  processScope?: "bare-plate";
  beamDiameterDefinition?: "D4sigma";
  source: string;
  doi: string;
};

function nist718(
  id: string,
  label: string,
  power: number,
  speed: number,
  d4sigma: number,
  w: number,
  d: number,
  wStd: number,
  dStd: number,
): MeltPoolLiteratureCase {
  return {
    id,
    label,
    material: "Inconel 718",
    laserPower_W: power,
    scanSpeed_mm_s: speed,
    beamDiameter_um: d4sigma,
    preheatTemp_C: opticalTable4.experiment.substrateAndChamberTemperature_C,
    layerThickness_um: null,
    hatchSpacing_um: null,
    publishedWidth_um: w,
    publishedDepth_um: d,
    widthStdDev_um: wStd,
    depthStdDev_um: dStd,
    measurementCount: opticalTable4.measurement.countPerCondition,
    publishedRegime: null,
    kind: "measured",
    processScope: "bare-plate",
    beamDiameterDefinition: "D4sigma",
    source: "NIST AMB2022-03 measurement results Table 4 — local transcription of published aggregate measurements; AMMT bare plate; six cross-sections per condition",
    doi: opticalTable4.doi,
  };
}

function guo316l(
  id: string,
  label: string,
  power: number,
  speed: number,
  w: number,
  d: number,
  regime: "Conduction" | "Transition" | "Keyhole",
): MeltPoolLiteratureCase {
  return {
    id,
    label,
    material: "316L Stainless Steel",
    laserPower_W: power,
    scanSpeed_mm_s: speed,
    beamDiameter_um: 100,
    preheatTemp_C: 25,
    layerThickness_um: 50,
    hatchSpacing_um: 100,
    publishedWidth_um: w,
    publishedDepth_um: d,
    publishedRegime: regime,
    kind: "measured",
    source: "Guo et al., Micromachines 15(2):170 (2024) Table 3 experimental",
    doi: "10.3390/mi15020170",
  };
}

/** Measured single-track anchors, one labeled Rosenthal asymptotic, honest AlSi10Mg/Ti64 gaps. */
export const MELT_POOL_LITERATURE_CASES: MeltPoolLiteratureCase[] = [
  {
    id: "ti64-rosenthal-proof003",
    label: "Ti-6Al-4V Rosenthal asymptotic (not a micrograph)",
    material: "Ti-6Al-4V",
    laserPower_W: 200,
    scanSpeed_mm_s: 900,
    beamDiameter_um: 80,
    preheatTemp_C: 150,
    layerThickness_um: 30,
    hatchSpacing_um: 100,
    publishedWidth_um: 125,
    publishedDepth_um: 62.5,
    publishedRegime: "Transition",
    kind: "asymptotic",
    source: "Rosenthal 3D high-speed asymptotic (PROOF 003) — theory, not a measured track",
    doi: "10.1063/1.1712881",
  },
  {
    id: "ti64-no-measured-track",
    label: "Ti-6Al-4V — no measured track",
    material: "Ti-6Al-4V",
    laserPower_W: null,
    scanSpeed_mm_s: null,
    beamDiameter_um: null,
    preheatTemp_C: null,
    layerThickness_um: null,
    hatchSpacing_um: null,
    publishedWidth_um: null,
    publishedDepth_um: null,
    publishedRegime: null,
    kind: "no-measured-track",
    source: "Dilip 2017 depths in text lack matching tabulated width and T0. Do not digitize Fig. 6.",
    doi: "",
  },
  {
    id: "alsi10mg-no-measured-track",
    label: "AlSi10Mg — no measured track",
    material: "AlSi10Mg",
    laserPower_W: null,
    scanSpeed_mm_s: null,
    beamDiameter_um: null,
    preheatTemp_C: null,
    layerThickness_um: null,
    hatchSpacing_um: null,
    publishedWidth_um: null,
    publishedDepth_um: null,
    publishedRegime: null,
    kind: "no-measured-track",
    source: "No isolated single-track P–v–d–T0–W–D table. Sow 2022 hatch/cube melt pools not ingested; Piedra 2026 Table 3 has width without depth.",
    doi: "",
  },
  ...opticalTable4.cases.map(row => nist718(`nist-amb2022-03-${row.caseNumber}`,
    ({ "0": "IN718 NIST AMB2022-03 baseline", "1.1": "IN718 NIST spot 49 µm",
      "1.2": "IN718 NIST spot 82 µm", "2.1": "IN718 NIST 1200 mm/s",
      "2.2": "IN718 NIST 800 mm/s", "3.1": "IN718 NIST 325 W",
      "3.2": "IN718 NIST 245 W" } as Record<string, string>)[row.caseNumber],
    row.laserPower_W, row.scanSpeed_mm_s, row.beamDiameterD4sigma_um,
    row.widthMean_um, row.depthMean_um, row.widthStdDev_um, row.depthStdDev_um)),
  guo316l("guo-316l-n01", "316L Guo N01 (260 W, 0.52 m/s)", 260, 520, 114, 180, "Keyhole"),
  guo316l("guo-316l-n04", "316L Guo N04 (260 W, 1.47 m/s)", 260, 1470, 94, 61, "Conduction"),
  guo316l("guo-316l-n05", "316L Guo N05 (260 W, 2.20 m/s)", 260, 2200, 83, 41, "Conduction"),
  guo316l("guo-316l-n06", "316L Guo N06 (440 W, 1.47 m/s)", 440, 1470, 98, 104, "Keyhole"),
];

export const MEASURED_TRACK_INTAKE_FIELDS = [
  "material",
  "laserPower_W",
  "scanSpeed_mm_s",
  "beamDiameter_um",
  "preheatTemp_C",
  "width_um",
  "depth_um",
  "doi",
] as const;

export function regimeFamily(regime: string): "Conduction" | "Transition" | "Keyhole" {
  const r = regime.toLowerCase();
  if (r.includes("keyhole")) return "Keyhole";
  if (r.includes("transition")) return "Transition";
  return "Conduction";
}

export function relativeErrorPct(predicted: number, published: number): number {
  return (100 * (predicted - published)) / Math.max(1, published);
}

export function isLoadableLiteratureCase(c: MeltPoolLiteratureCase): boolean {
  return (
    c.processScope !== "bare-plate" &&
    c.kind !== "no-measured-track" &&
    c.laserPower_W != null &&
    c.scanSpeed_mm_s != null &&
    c.beamDiameter_um != null &&
    c.preheatTemp_C != null &&
    c.layerThickness_um != null &&
    c.hatchSpacing_um != null
  );
}

export function matchesLoadableLiteratureCase(
  c: MeltPoolLiteratureCase,
  material: string,
  process: {
    laserPower_W: number;
    scanSpeed_mm_s: number;
    beamDiameter_um: number;
    preheatTemp_C: number;
    layerThickness_um: number;
    hatchSpacing_um: number;
  },
): boolean {
  return isLoadableLiteratureCase(c) && material === c.material &&
    Math.abs(process.laserPower_W - c.laserPower_W!) < 1 &&
    Math.abs(process.scanSpeed_mm_s - c.scanSpeed_mm_s!) < 1 &&
    Math.abs(process.beamDiameter_um - c.beamDiameter_um!) < 0.1 &&
    Math.abs(process.preheatTemp_C - c.preheatTemp_C!) < 0.1 &&
    Math.abs(process.layerThickness_um - c.layerThickness_um!) < 0.1 &&
    Math.abs(process.hatchSpacing_um - c.hatchSpacing_um!) < 0.1;
}
