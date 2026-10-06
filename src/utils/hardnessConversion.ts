// =====================================================================================================================
// Approximate hardness conversion for NON-AUSTENITIC STEELS by linear interpolation between published table values.
// Single shared implementation for the Unit Converter, the quick-conversion grid and the Pocket Calculators.
//
// These are ESTIMATES read from conversion tables, never measurements. Outside the tabulated range of a scale the
// result is reported as unavailable: no extrapolation and no clamping.
//
// Sources (public reproductions of the standards' tables; each column used here was cross-checked between the sources
// listed for it and agrees value for value unless noted):
//   ASTM E140 Table 1 (Rockwell C range, non-austenitic steels): HRC 20..68 -> HV and HK; HRC 20..59 -> HBW
//   (10 mm tungsten-carbide ball, 3000 kgf). Three sources, identical for all 49 rows:
//     [A] Laboratory Testing Inc., "Rockwell C Hardness Conversion"
//         https://labtesting.com/wp-content/uploads/2012/08/chart-hardness-c.pdf
//     [B] Anderson Laboratories, "Hardness conversion table ASTM E140 - Rockwell C range (non-austenitic steels)"
//         https://andersonlabs.com/wp-content/uploads/2021/12/ASTM-Hardness-Conversion-Table-Rockwell-C-Range.pdf
//     [C] Struers, "Hardness Conversion Table for Non-Austenitic Steels" (poster, hosted by UPC EPSEVG)
//         https://epsevg.upc.edu/ca/stl/posters/cem/hardness-conversion-poster.pdf
//     HBW above HRC 59 is printed in brackets by [B]/[C] (outside the ASTM E10 Brinell range) and blank in [A]: not used.
//   ASTM E140 Table 2 (Rockwell B range, non-austenitic steels): HRB 55..100 -> HV, HK and Brinell HB(S) (10 mm steel
//   ball, 3000 kgf). Two sources:
//     [D] Anderson Laboratories, "Hardness conversion table ASTM E140 - Rockwell B range (non-austenitic steels)"
//         https://andersonlabs.com/wp-content/uploads/2021/12/ASTM-Hardness-Conversion-Table-Rockwell-B-Range.pdf
//     [E] Micro Star 2000, "Approximate Hardness Conversion Numbers for Non-Austenitic Steels (Rockwell B Range)"
//         https://microstar2000.com/dat/files/345/MS002%20MS002%20Approximate%20Hardness%20Conversion%20Numbers%20for%20Non-Austenitic%20Steels%20Rockwell%20B.pdf
//     HV agrees for all 46 rows except HRB 84, where [D] prints 165 (the HRB 85 value) and [E] prints 162; 162 is used
//     ([D]'s own Brinell column, equal to HV everywhere else in that table, also gives 162). Below HRB 55 neither source
//     lists HV. Brinell column of Table 2 ("3000 kgf, 10 mm ball"; [E] labels it HBS): [D] and [E] agree on every row
//     except HRB 57-59, where [E] repeats its Knoop column (115/117/118) and [D] prints 103/104/106; those three rows
//     are left out (null) and interpolated between HRB 56 and 60. The column is kept as its own scale HBS (HV 100-240)
//     and is NOT merged with the Table 1 HBW column: the two tables do not join at their seam (HRB 99: HB 234 at
//     HV 234; HRC 20: HBW 226 at HV 238). The ball type is not the issue: [C] lists identical steel-ball (HBS30) and
//     carbide-ball (HBW30) values for HRC 20-48.
//   ISO 18265 Table A.1 (unalloyed and low-alloy steels, cast steel): tensile strength estimate Rm vs HV, HV 80..650.
//   Two sources, identical for all 80 rows:
//     [F] Bossard, "Hardness comparison table according to ISO 18265" (D.021)
//         https://assets.eu.ctfassets.net/0vp0u5uh75zd/qJZhIT2YBL03SKvQjX7lX/d2feb4f2658918253c3a4646b235ea7f/D021_TableStandards_Hardness_comparison_table_Sealing_EN_02_2022.pdf
//     [G] Gebr. Recknagel (stahlnetz.de), "Haertevergleichstabelle"
//         https://www.stahlnetz.de/files/de/general/Haertevergleichstabelle.pdf
//   Cross-check between the standards: the HRC values that [F] lists for HV 240..940 lie within 0.14 HRC of linear
//   interpolation in the E140 Table 1 anchors below.
//   Leeb (HLD): no public steel table was verified, so HLD is never converted.
// =====================================================================================================================

export type HardnessScale = "HRC" | "HV" | "HRB" | "HBW" | "HBS" | "HK" | "HLD";
export type HardnessField = HardnessScale | "Rm";

export const HARDNESS_CONVERSION_DISCLAIMER =
  "Approximate conversion for non-austenitic steels per ASTM E140 / ISO 18265 tables; not a substitute for direct testing.";
export const TENSILE_ESTIMATE_NOTE =
  "Rm estimate per ISO 18265 Table A.1 (unalloyed/low-alloy steels, HV 80-650); approximate, not a substitute for a tensile test.";
export const LEEB_UNAVAILABLE_NOTE = "Leeb (HLD) conversion unavailable: no verified conversion table.";
export const BRINELL_NOTE =
  "Brinell: HBW = 10 mm carbide ball, 3000 kgf (E140 Table 1, HRC 20-59); HB(S) = 10 mm steel ball, 3000 kgf (E140 Table 2, HV 100-240). The Struers table lists identical steel-ball and carbide-ball values for HRC 20-48; the two E140 tables do not join at HV 234-238, so they are shown separately.";

// [HRC, HV, HBW (null = not tabulated), HK] -- ASTM E140 Table 1 via [A][B][C]
const E140_TABLE1: ReadonlyArray<readonly [number, number, number | null, number]> = [
  [20, 238, 226, 251], [21, 243, 231, 256], [22, 248, 237, 261], [23, 254, 243, 266], [24, 260, 247, 272],
  [25, 266, 253, 278], [26, 272, 258, 284], [27, 279, 264, 290], [28, 286, 271, 297], [29, 294, 279, 304],
  [30, 302, 286, 311], [31, 310, 294, 318], [32, 318, 301, 326], [33, 327, 311, 334], [34, 336, 319, 342],
  [35, 345, 327, 351], [36, 354, 336, 360], [37, 363, 344, 370], [38, 372, 353, 380], [39, 382, 362, 391],
  [40, 392, 371, 402], [41, 402, 381, 414], [42, 412, 390, 426], [43, 423, 400, 438], [44, 434, 409, 452],
  [45, 446, 421, 466], [46, 458, 432, 480], [47, 471, 443, 495], [48, 484, 455, 510], [49, 498, 469, 526],
  [50, 513, 481, 542], [51, 528, 496, 558], [52, 544, 512, 576], [53, 560, 525, 594], [54, 577, 543, 612],
  [55, 595, 560, 630], [56, 613, 577, 650], [57, 633, 595, 670], [58, 653, 615, 690], [59, 674, 634, 710],
  [60, 697, null, 732], [61, 720, null, 754], [62, 746, null, 776], [63, 772, null, 799], [64, 800, null, 822],
  [65, 832, null, 846], [66, 865, null, 870], [67, 900, null, 895], [68, 940, null, 920],
];

// [HRB, HV, HB(S) (null = sources disagree, see above), HK] -- ASTM E140 Table 2 via [D][E]
const E140_TABLE2: ReadonlyArray<readonly [number, number, number | null, number]> = [
  [55, 100, 100, 112], [56, 101, 101, 114], [57, 103, null, 115], [58, 104, null, 117], [59, 106, null, 118],
  [60, 107, 107, 120], [61, 108, 108, 122], [62, 110, 110, 124], [63, 112, 112, 125], [64, 114, 114, 127],
  [65, 116, 116, 129], [66, 117, 117, 131], [67, 119, 119, 133], [68, 121, 121, 135], [69, 123, 123, 137],
  [70, 125, 125, 139], [71, 127, 127, 141], [72, 130, 130, 143], [73, 132, 132, 145], [74, 135, 135, 147],
  [75, 137, 137, 150], [76, 139, 139, 152], [77, 141, 141, 155], [78, 144, 144, 158], [79, 147, 147, 161],
  [80, 150, 150, 164], [81, 153, 153, 167], [82, 156, 156, 170], [83, 159, 159, 173], [84, 162, 162, 176],
  [85, 165, 165, 180], [86, 169, 169, 184], [87, 172, 172, 188], [88, 176, 176, 192], [89, 180, 180, 196],
  [90, 185, 185, 201], [91, 190, 190, 206], [92, 195, 195, 211], [93, 200, 200, 216], [94, 205, 205, 221],
  [95, 210, 210, 226], [96, 216, 216, 231], [97, 222, 222, 236], [98, 228, 228, 241], [99, 234, 234, 246],
  [100, 240, 240, 251],
];

// [HV, Rm MPa] -- ISO 18265 Table A.1 via [F][G]
const ISO18265_RM: ReadonlyArray<readonly [number, number]> = [
  [80, 255], [85, 270], [90, 285], [95, 305], [100, 320], [105, 335], [110, 350], [115, 370], [120, 385], [125, 400],
  [130, 415], [135, 430], [140, 450], [145, 465], [150, 480], [155, 495], [160, 510], [165, 530], [170, 545],
  [175, 560], [180, 575], [185, 595], [190, 610], [195, 625], [200, 640], [205, 660], [210, 675], [215, 690],
  [220, 705], [225, 720], [230, 740], [235, 755], [240, 770], [245, 785], [250, 800], [255, 820], [260, 835],
  [265, 850], [270, 865], [275, 880], [280, 900], [285, 915], [290, 930], [295, 950], [300, 965], [310, 995],
  [320, 1030], [330, 1060], [340, 1095], [350, 1125], [360, 1155], [370, 1190], [380, 1220], [390, 1255],
  [400, 1290], [410, 1320], [420, 1350], [430, 1385], [440, 1420], [450, 1455], [460, 1485], [470, 1520],
  [480, 1555], [490, 1595], [500, 1630], [510, 1665], [520, 1700], [530, 1740], [540, 1775], [550, 1810],
  [560, 1845], [570, 1880], [580, 1920], [590, 1955], [600, 1995], [610, 2030], [620, 2070], [630, 2105],
  [640, 2145], [650, 2180],
];

// Each scale as a strictly increasing (HV, value) anchor list; HV is the pivot for every conversion.
type Anchors = { hv: number[]; val: number[] };
const anchors = (pairs: ReadonlyArray<readonly [number, number]>): Anchors => ({
  hv: pairs.map((p) => p[0]),
  val: pairs.map((p) => p[1]),
});
const HRC_ANCHORS = anchors(E140_TABLE1.map((r) => [r[1], r[0]] as const));
const HBW_ANCHORS = anchors(
  E140_TABLE1.filter((r) => r[2] !== null).map((r) => [r[1], r[2] as number] as const)
);
const HRB_ANCHORS = anchors(E140_TABLE2.map((r) => [r[1], r[0]] as const));
const HBS_ANCHORS = anchors(
  E140_TABLE2.filter((r) => r[2] !== null).map((r) => [r[1], r[2] as number] as const)
);
// HK: Table 2 rows HRB 55..99 (HV 100..234) followed by Table 1 rows (HV 238..940); HRB 100 (HV 240, HK 251) overlaps
// HRC 20 (HV 238, HK 251) and is left out so the list stays strictly increasing.
const HK_ANCHORS = anchors([
  ...E140_TABLE2.filter((r) => r[0] < 100).map((r) => [r[1], r[3]] as const),
  ...E140_TABLE1.map((r) => [r[1], r[3]] as const),
]);
const RM_ANCHORS = anchors(ISO18265_RM);

type TabulatedScale = "HRC" | "HRB" | "HBW" | "HBS" | "HK";
const SCALE_ANCHORS: Record<TabulatedScale, Anchors> = {
  HRC: HRC_ANCHORS,
  HRB: HRB_ANCHORS,
  HBW: HBW_ANCHORS,
  HBS: HBS_ANCHORS,
  HK: HK_ANCHORS,
};

// Piecewise-linear interpolation in a strictly increasing list; null outside [xs[0], xs[last]].
function interpolate(x: number, xs: number[], ys: number[]): number | null {
  if (!Number.isFinite(x) || x < xs[0] || x > xs[xs.length - 1]) return null;
  for (let i = 0; i < xs.length - 1; i++) {
    if (x <= xs[i + 1]) {
      return ys[i] + ((ys[i + 1] - ys[i]) * (x - xs[i])) / (xs[i + 1] - xs[i]);
    }
  }
  return ys[ys.length - 1];
}

/** Unrounded table interpolation HV -> scale (null outside the tabulated range); for cross-checks and tests. */
export function interpolateSteelScaleFromHv(scale: TabulatedScale | "Rm", hv: number): number | null {
  const a = scale === "Rm" ? RM_ANCHORS : SCALE_ANCHORS[scale];
  return interpolate(hv, a.hv, a.val);
}

/** Verified input range of each scale (the tabulated range). HV also accepts 80..100 for the Rm estimate only. */
export const HARDNESS_VERIFIED_RANGES: Record<HardnessScale, { min: number; max: number } | null> = {
  HRC: { min: 20, max: 68 },
  HRB: { min: 55, max: 100 },
  HBW: { min: 226, max: 634 },
  HBS: { min: 100, max: 240 },
  HK: { min: 112, max: 920 },
  HV: { min: 80, max: 940 },
  HLD: null,
};

/** Default input when the user switches to a scale and the current value lies outside that scale's verified range. */
export const HARDNESS_SCALE_DEFAULT_INPUT: Record<HardnessScale, number> = {
  HRC: 35,
  HRB: 85,
  HV: 350,
  HBW: 320,
  HBS: 150,
  HK: 350,
  HLD: 600,
};

/** Value to keep after switching the input scale: unchanged when inside the new scale's range, else that scale's default. */
export function hardnessInputForScale(current: number, scale: HardnessScale): number {
  const r = HARDNESS_VERIFIED_RANGES[scale];
  if (r === null) return Number.isFinite(current) ? current : HARDNESS_SCALE_DEFAULT_INPUT[scale];
  return Number.isFinite(current) && current >= r.min && current <= r.max ? current : HARDNESS_SCALE_DEFAULT_INPUT[scale];
}

/** One wording for every surface when a converted value is missing. */
export const UNAVAILABLE_TEXT = "Unavailable";

export interface SteelHardnessConversion {
  inputScale: HardnessScale;
  inputValue: number;
  /** Converted values (the input scale echoes the input). null = unavailable; see `unavailable` for the reason. */
  HV: number | null;
  HRC: number | null;
  HRB: number | null;
  HBW: number | null;
  /** Brinell, 10 mm steel ball, 3000 kgf, from ASTM E140 Table 2 (HV 100-240). */
  HBS: number | null;
  HK: number | null;
  HLD: number | null;
  tensileRm_MPa: number | null;
  tensileRm_ksi: number | null;
  unavailable: Partial<Record<HardnessField, string>>;
  validRangeNote: string;
}

const round = (v: number, decimals: number) => Number(v.toFixed(decimals));
// Converted values are reported as whole numbers on every scale (Rockwell included): the tables themselves list whole
// HRC/HRB numbers. The measured input is echoed with one decimal (as entered, up to 0.1).
const DECIMALS: Record<HardnessScale, number> = { HV: 0, HRC: 0, HRB: 0, HBW: 0, HBS: 0, HK: 0, HLD: 0 };
const INPUT_DECIMALS: Record<HardnessScale, number> = { HV: 1, HRC: 1, HRB: 1, HBW: 1, HBS: 1, HK: 1, HLD: 1 };

const rangeText = (scale: HardnessScale) => {
  const r = HARDNESS_VERIFIED_RANGES[scale];
  return r ? `${scale} ${r.min}-${r.max}` : scale;
};

/** Convert a hardness value of a non-austenitic steel to the other scales (approximate, table interpolation). */
export function convertSteelHardness(value: number, fromScale: HardnessScale): SteelHardnessConversion {
  const out: SteelHardnessConversion = {
    inputScale: fromScale,
    inputValue: value,
    HV: null,
    HRC: null,
    HRB: null,
    HBW: null,
    HBS: null,
    HK: null,
    HLD: null,
    tensileRm_MPa: null,
    tensileRm_ksi: null,
    unavailable: {},
    validRangeNote: HARDNESS_CONVERSION_DISCLAIMER,
  };
  if (Number.isFinite(value)) out[fromScale] = round(value, INPUT_DECIMALS[fromScale]);

  // 1. input -> HV (the pivot)
  let hv: number | null = null;
  let inputNote: string | null = null;
  if (fromScale === "HLD") {
    inputNote = LEEB_UNAVAILABLE_NOTE;
  } else if (fromScale === "HV") {
    const r = HARDNESS_VERIFIED_RANGES.HV!;
    if (Number.isFinite(value) && value >= r.min && value <= r.max) hv = value;
    else inputNote = `Input outside verified range (${rangeText("HV")}): conversion unavailable.`;
  } else {
    const a = SCALE_ANCHORS[fromScale];
    hv = interpolate(value, a.val, a.hv);
    if (hv === null) inputNote = `Input outside verified range (${rangeText(fromScale)}): conversion unavailable.`;
  }

  // 2. HV -> every other scale, each with its own tabulated range
  const noPivotReason = fromScale === "HLD" ? LEEB_UNAVAILABLE_NOTE : "input outside verified range";
  const outsideReason = (scale: HardnessScale) =>
    hv === null ? noPivotReason : `outside verified range (${rangeText(scale)})`;
  if (fromScale !== "HV") {
    // hv came from a table, so it lies inside HV 100..940
    if (hv === null) out.unavailable.HV = outsideReason("HV");
    else out.HV = round(hv, DECIMALS.HV);
  }
  for (const scale of ["HRC", "HRB", "HBW", "HBS", "HK"] as const) {
    if (scale === fromScale) continue;
    const a = SCALE_ANCHORS[scale];
    const v = hv === null ? null : interpolate(hv, a.hv, a.val);
    if (v === null) out.unavailable[scale] = outsideReason(scale);
    else out[scale] = round(v, DECIMALS[scale]);
  }
  if (fromScale !== "HLD") out.unavailable.HLD = LEEB_UNAVAILABLE_NOTE;

  // 3. HV -> tensile strength estimate (ISO 18265 Table A.1)
  const rm = hv === null ? null : interpolate(hv, RM_ANCHORS.hv, RM_ANCHORS.val);
  if (rm === null) {
    out.unavailable.Rm = hv === null ? noPivotReason : "outside ISO 18265 Table A.1 range (HV 80-650)";
  } else {
    out.tensileRm_MPa = Math.round(rm);
    out.tensileRm_ksi = round(Math.round(rm) * 0.1450377, 1);
  }

  if (inputNote) out.validRangeNote = `${inputNote} ${HARDNESS_CONVERSION_DISCLAIMER}`;
  return out;
}

// ---------------------------------------------------------------------------------------------------------------------
// Alloy class gate. The tables above are for non-austenitic steels only; for any other class only the measured value is
// returned and every converted field is unavailable.
// ---------------------------------------------------------------------------------------------------------------------
export type HardnessMaterialClass =
  | "non-austenitic-steel"
  | "austenitic-steel"
  | "titanium-alloy"
  | "nickel-alloy"
  | "aluminium-alloy"
  | "hardmetal"
  | "other";

export const HARDNESS_MATERIAL_CLASSES: ReadonlyArray<{ id: HardnessMaterialClass; label: string }> = [
  { id: "non-austenitic-steel", label: "Non-austenitic steel (carbon, alloy, tool)" },
  { id: "austenitic-steel", label: "Austenitic stainless steel" },
  { id: "titanium-alloy", label: "Titanium alloy" },
  { id: "nickel-alloy", label: "Nickel alloy" },
  { id: "aluminium-alloy", label: "Aluminium alloy" },
  { id: "hardmetal", label: "Hardmetal / carbide (e.g. WC-Co)" },
  { id: "other", label: "Other / unknown alloy" },
];

// ASTM E140 also has tables for some other classes (e.g. nickel alloys, cartridge brass, austenitic stainless HB-HRB,
// wrought aluminium; per the review, not read here). Only the non-austenitic steel tables are implemented and verified,
// so the reason says "not implemented", not that no table exists.
export const NO_TABLE_FOR_CLASS = "Unavailable: no conversion table for this alloy class is implemented in this tool";

export const hardnessMaterialClassLabel = (c: HardnessMaterialClass) =>
  HARDNESS_MATERIAL_CLASSES.find((m) => m.id === c)?.label ?? c;

/**
 * Convert a measured hardness value for the given alloy class. Only "non-austenitic-steel" is converted (ASTM E140 /
 * ISO 18265 tables); for every other class the measured value is echoed and all converted fields are unavailable.
 */
export function convertHardness(
  value: number,
  fromScale: HardnessScale,
  materialClass: HardnessMaterialClass
): SteelHardnessConversion {
  if (materialClass === "non-austenitic-steel") return convertSteelHardness(value, fromScale);
  const out: SteelHardnessConversion = {
    inputScale: fromScale,
    inputValue: value,
    HV: null,
    HRC: null,
    HRB: null,
    HBW: null,
    HBS: null,
    HK: null,
    HLD: null,
    tensileRm_MPa: null,
    tensileRm_ksi: null,
    unavailable: {},
    validRangeNote: `${NO_TABLE_FOR_CLASS} (${hardnessMaterialClassLabel(materialClass)}). Only the measured ${fromScale} value is shown.`,
  };
  if (Number.isFinite(value)) out[fromScale] = round(value, INPUT_DECIMALS[fromScale]);
  for (const f of ["HV", "HRC", "HRB", "HBW", "HBS", "HK", "HLD", "Rm"] as const) {
    if (f !== fromScale) out.unavailable[f] = NO_TABLE_FOR_CLASS;
  }
  return out;
}

/**
 * Alloy class of a material record: Fe-base with an FCC (austenitic) structure is austenitic steel, other Fe-base is
 * treated as non-austenitic steel; Ti, Ni, Al map to their classes; everything else is "other" (not converted).
 */
export function hardnessMaterialClassOf(spec: { baseMetal?: string; crystalSystem?: string }): HardnessMaterialClass {
  switch (spec.baseMetal) {
    case "Fe":
      return spec.crystalSystem === "FCC" ? "austenitic-steel" : "non-austenitic-steel";
    case "Ti":
      return "titanium-alloy";
    case "Ni":
      return "nickel-alloy";
    case "Al":
      return "aluminium-alloy";
    default:
      return "other";
  }
}
