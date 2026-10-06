import type { HardnessMaterialClass, HardnessScale } from "./hardnessConversion";

/**
 * Example MEASURED hardness inputs shared by the unit converter, the quick-conversion grid and Pocket Calculators.
 * The values are illustrative inputs (not sourced material data). Each preset carries the scale it is usually measured
 * in and its alloy class; only non-austenitic steels are converted (ASTM E140 tables), the others show the measured
 * value only. Notes never quote converted numbers.
 */
export interface HardnessPreset {
  name: string;
  value: number;
  scale: HardnessScale;
  cls: HardnessMaterialClass;
  note: string;
}

export const HARDNESS_PRESETS: ReadonlyArray<HardnessPreset> = [
  { name: "316L Annealed", value: 80, scale: "HRB", cls: "austenitic-steel", note: "Austenitic: measured HRB only" },
  { name: "Ti-6Al-4V Annealed", value: 34, scale: "HRC", cls: "titanium-alloy", note: "Titanium: measured HRC only" },
  { name: "Inconel 718 Aged", value: 44, scale: "HRC", cls: "nickel-alloy", note: "Nickel alloy: measured HRC only" },
  { name: "4140 Q&T", value: 35, scale: "HRC", cls: "non-austenitic-steel", note: "Quenched & tempered steel" },
  { name: "AerMet 100", value: 55, scale: "HRC", cls: "non-austenitic-steel", note: "Ultra-high-strength steel" },
  { name: "52100 Bearing Steel", value: 60, scale: "HRC", cls: "non-austenitic-steel", note: "Through-hardened steel" },
  { name: "M2 High-Speed Tool", value: 64, scale: "HRC", cls: "non-austenitic-steel", note: "Hardened tool steel" },
];
