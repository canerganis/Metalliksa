import assert from "node:assert/strict";
import test from "node:test";
import type { MaterialSpec } from "../src/types";
import { MATERIALS_DATABASE } from "../src/data/materialsDatabase";
import {
  createPipelinePayloadFromMaterialSpec,
  deriveHardnessProfile,
  isNonAusteniticSteel,
  pipelineHardnessText,
} from "../src/utils/materialDataPipeline";

// deriveHardnessProfile used HV = 80 + 14.5 HRC and HRC = (HV - 80) / 14.5 for every alloy (HRC 34 -> 573 HV, E140: 336).
// It now uses the shared ASTM E140 interpolation for non-austenitic steels only and labels every estimate.
const derive = (baseMetal: string, hardness: string, microstructure?: string, name = "Test alloy", ys = 900) =>
  deriveHardnessProfile(name, "Test", baseMetal, ys, ys * 1.1, 200, 12, hardness, microstructure);

test("steel with a reported HRC: HV converted per ASTM E140 Table 1 (old: 80 + 14.5 HRC)", () => {
  const r = derive("Fe", "28 - 34 HRC (Quenched & Tempered @ 540°C)", "Tempered martensite");
  assert.equal(r.hardnessHRC, 34);
  assert.equal(r.hardnessHV, 336); // old 573
  assert.equal(r.hardnessHVSource, "converted-astm-e140");
  assert.match(r.hardnessProfile.description, /converted from 34 HRC per ASTM E140 Table 1 \(approximate\)/);
  assert.doesNotMatch(r.hardnessProfile.description, /experimental/);
});

test("non-steel with a reported HRC: no steel conversion and no yield-strength estimate (unavailable)", () => {
  const r = derive("Ti", "34 - 36 HRC (Mill Annealed)", "alpha-beta", "Ti-6Al-4V", 880);
  assert.equal(r.hardnessHRC, 36); // as reported
  // old 80 + 14.5 * 36 = 602, then the unsourced YS/3 + 35 = 328
  assert.equal(r.hardnessHV, null);
  assert.equal(r.hardnessHVSource, "unavailable");
  assert.equal(r.hardnessProfile.defaultHardnessHV, undefined);
  assert.match(r.hardnessProfile.description, /HV unavailable: no verified hardness-strength relation for this alloy class \(Titanium alloy\)/);
});

test("reported HV: HRC only for non-austenitic steels, never by the old linear formula", () => {
  const wc = derive("Other", "92 - 93.5 HRA / ~1600 HV30");
  assert.equal(wc.hardnessHV, 1600);
  assert.equal(wc.hardnessHRC, undefined); // old (1600 - 80) / 14.5 = 105 HRC
  assert.equal(wc.hardnessHVSource, "reported");
  const steel = derive("Fe", "392 HV", "martensite");
  assert.equal(steel.hardnessHRC, 40); // E140; old round(312 / 14.5) = 22
  const austenitic = derive("Fe", "392 HV", "Fully austenitic (FCC) equiaxed grains");
  assert.equal(austenitic.hardnessHRC, undefined);
  assert.equal(derive("Fe", "950 HV", "martensite").hardnessHRC, undefined); // above HV 940: unavailable
});

test("steel with a reported HRB: HV converted per ASTM E140 Table 2 (old: YS/3 + 35)", () => {
  const r = derive("Fe", "126 HBW / 71 HRB (Cold Drawn)", "ferrite-pearlite", "AISI 1018", 370);
  assert.equal(r.hardnessHV, 127); // E140 Table 2 row HRB 71 = 127 HV; old round(370 / 3 + 35) = 158
  assert.equal(r.hardnessHVSource, "converted-astm-e140");
  assert.match(r.hardnessProfile.description, /converted from 71 HRB per ASTM E140 Table 2 \(approximate\)/);
  // HBW 126 is below the Table 1 HBW range (226-634), so HRB is used; an in-range HBW alone converts via Table 1.
  const hbw = derive("Fe", "286 HBW", "tempered martensite");
  assert.equal(hbw.hardnessHV, 302); // Table 1 row HRC 30: HV 302 / HBW 286
  assert.match(hbw.hardnessProfile.description, /converted from 286 HBW per ASTM E140 Table 1/);
  // non-steels never use the steel tables
  assert.equal(derive("Al", "95 HBW / ~60 HRB").hardnessHV, null);
});

test("no usable hardness: steel-only Pavlina & Van Tyne (2008) yield estimate with C known, else unavailable", () => {
  const steel = (ys: number, c?: number) =>
    deriveHardnessProfile("Steel", "Alloy Steel", "Fe", ys, ys * 1.2, 205, 15, "", "tempered martensite", false, { Fe: 98, Mn: 0.8, ...(c === undefined ? {} : { C: c }) });
  const r = steel(600, 0.4);
  assert.equal(r.hardnessHV, 240); // (600 + 90.7) / 2.876 = 240.2; old round(600 / 3 + 35) = 235
  assert.equal(r.hardnessHVSource, "estimate-from-yield");
  assert.match(r.hardnessProfile.description, /HV 240 is an estimate from yield strength by inverting the Pavlina & Van Tyne \(2008\).*not measured/);
  // B1: a stainless composition without a hardness string is outside the data set
  const ph = deriveHardnessProfile("17-4PH", "Martensitic PH", "Fe", 1000, 1100, 197, 10, "", "martensite", false, { Fe: 74.5, Cr: 15.5, Ni: 4.5, Cu: 3.5, C: 0.05 });
  assert.equal(ph.hardnessHV, null);
  assert.match(ph.hardnessProfile.description, /HV unavailable: outside the regression's data set/);
  assert.equal(steel(600).hardnessHV, null); // carbon unknown
  assert.match(steel(600).hardnessProfile.description, /carbon content unknown/);
  assert.equal(steel(600, 1.0).hardnessHV, null); // hypereutectoid
  assert.equal(steel(2000, 0.4).hardnessHV, null); // above HV 632
});

test("predicted hardness strings are flagged as predictions", () => {
  const r = deriveHardnessProfile("Candidate", "Fe Formulated Alloy", "Fe", 900, 1000, 200, 12, "330 HV", undefined, true);
  assert.equal(r.hardnessHV, 330);
  assert.equal(r.hardnessHVSource, "estimate-predicted");
  assert.match(r.hardnessProfile.description, /predicted value, not a measurement/);
});

test("Materials Database path passes the composition: a steel without a hardness string gets the estimate", () => {
  const spec = {
    id: "synthetic-steel",
    name: "Synthetic low-alloy steel",
    category: "Alloy Steel",
    standard: "test",
    composition: { Fe: 97.4, C: { min: 0.38, max: 0.43 }, Mn: 0.9, Cr: 1.0, Mo: 0.2 },
    yieldStrength: 655,
    tensileStrength: 1020,
    youngsModulus: 205,
    density: 7.85,
    elongation: 18,
    hardness: "",
    microstructure: "tempered martensite",
  } as unknown as MaterialSpec;
  const p = createPipelinePayloadFromMaterialSpec(spec);
  assert.equal(p.hardnessHV, 259); // (655 + 90.7) / 2.876 = 259.3 (C midpoint 0.405)
  assert.equal(p.hardnessHVSource, "estimate-from-yield");
});

test("payload hardness text always states its basis; a reported hardness is shown when HV is unavailable", () => {
  assert.equal(pipelineHardnessText(null, "unavailable"), "HV unavailable");
  // Review S3: IN718 / Ti-6Al-4V rows read only "Unavailable" and hid the reported hardness
  assert.equal(pipelineHardnessText(null, "unavailable", "40 - 45 HRC (Fully Aged)"), "HV unavailable (reported: 40 - 45 HRC (Fully Aged))");
  // our own generated notes are not "reported" values
  assert.equal(pipelineHardnessText(null, "unavailable", "Unavailable: no verified hardness-strength relation for this alloy class (Nickel alloy)"), "HV unavailable");
  assert.equal(pipelineHardnessText(null, "unavailable", "Unavailable (no verified hardness-strength relation for this candidate)"), "HV unavailable");
  const in718 = MATERIALS_DATABASE.find((m) => /Inconel 718/.test(m.name))!;
  const p = createPipelinePayloadFromMaterialSpec(in718);
  assert.equal(pipelineHardnessText(p.hardnessHV, p.hardnessHVSource, p.hardness), `HV unavailable (reported: ${in718.hardness})`);
  assert.equal(pipelineHardnessText(344, "estimate-predicted"), "344 HV (estimate, not measured)");
  assert.equal(pipelineHardnessText(240, "estimate-from-yield"), "240 HV (estimate, not measured)");
  assert.equal(pipelineHardnessText(336, "converted-astm-e140"), "336 HV (converted, ASTM E140)");
  assert.equal(pipelineHardnessText(120, "reported"), "120 HV (reported)");
});

test("steel scope check", () => {
  assert.equal(isNonAusteniticSteel("Fe", "AISI 4140", "Alloy Steel", "Tempered martensite"), true);
  assert.equal(isNonAusteniticSteel("Fe", "AISI 316L Low-Carbon Austenitic Stainless Steel"), false);
  assert.equal(isNonAusteniticSteel("Fe", "2205 Duplex", "Stainless Steel", "~50% Austenite islands"), false);
  assert.equal(isNonAusteniticSteel("Ni", "Inconel 718"), false);
});
