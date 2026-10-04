import assert from "node:assert/strict";
import test from "node:test";
import { deriveHardnessProfile, isNonAusteniticSteel } from "../src/utils/materialDataPipeline";

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

test("non-steel with a reported HRC: no steel conversion; HV is the labelled yield-strength estimate", () => {
  const r = derive("Ti", "34 - 36 HRC (Mill Annealed)", "alpha-beta", "Ti-6Al-4V", 880);
  assert.equal(r.hardnessHRC, 36); // as reported
  assert.equal(r.hardnessHV, Math.round(880 / 3 + 35)); // old 80 + 14.5 * 36 = 602
  assert.equal(r.hardnessHVSource, "estimate-from-yield");
  assert.match(r.hardnessProfile.description, /unverified estimate from yield strength/);
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

test("no usable hardness: yield-strength estimate, labelled", () => {
  const r = derive("Fe", "126 HBW / 71 HRB (Cold Drawn)", "ferrite-pearlite", "AISI 1018", 370);
  assert.equal(r.hardnessHV, Math.round(370 / 3 + 35));
  assert.equal(r.hardnessHVSource, "estimate-from-yield");
});

test("predicted hardness strings are flagged as predictions", () => {
  const r = deriveHardnessProfile("Candidate", "Fe Formulated Alloy", "Fe", 900, 1000, 200, 12, "330 HV", undefined, true);
  assert.equal(r.hardnessHV, 330);
  assert.equal(r.hardnessHVSource, "estimate-predicted");
  assert.match(r.hardnessProfile.description, /predicted value, not a measurement/);
});

test("steel scope check", () => {
  assert.equal(isNonAusteniticSteel("Fe", "AISI 4140", "Alloy Steel", "Tempered martensite"), true);
  assert.equal(isNonAusteniticSteel("Fe", "AISI 316L Low-Carbon Austenitic Stainless Steel"), false);
  assert.equal(isNonAusteniticSteel("Fe", "2205 Duplex", "Stainless Steel", "~50% Austenite islands"), false);
  assert.equal(isNonAusteniticSteel("Ni", "Inconel 718"), false);
});
