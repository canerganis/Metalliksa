import assert from "node:assert/strict";
import test from "node:test";
import {
  HYPOEUTECTOID_C_MAX_WT_PCT,
  PAVLINA_VAN_TYNE_2008,
  SPECIMEN_HARDNESS_NOT_LOADED_NOTE,
  estimateSpecimenHardnessHV,
  estimateSteelHvFromYield,
} from "../src/utils/hardnessStrengthEstimate";
import {
  MATERIAL_PRESETS,
  deriveProperties,
  migrateMaterialStoreState,
  useMaterialStore,
  withHardnessEstimate,
  type MaterialSpecimen,
} from "../src/store/useMaterialStore";
import { useMaterialSpecimenStore } from "../src/store/useMaterialSpecimenStore";
import type { PipelineMaterialPayload } from "../src/utils/materialDataPipeline";

// Transcribed by hand for this test from Pavlina & Van Tyne, J. Mater. Eng. Perform. 17 (2008) 888-893, Table 1
// (https://wpfiles.mines.edu/wp-content/uploads/aspprc/ResearchMaterials/Publications/386-Pavlina.pdf, PDF sha256
// F5E28CBCB1B11295F3D99C7C808A7475D3A81CD80E77E53D4F78B55885D8EE2F), rows "All data". Kept separate from the util constants on purpose.
const TABLE1_ALL_DATA = {
  yield: { constant: -90.7, coefficient: 2.876, r2: 0.9212, hvMin: 129, hvMax: 632, points: 165, standardError: 102 },
  tensile: { constant: -99.8, coefficient: 3.734, r2: 0.9347, hvMin: 129, hvMax: 592, points: 159, standardError: 112 },
};
// Abstract: yield strength "from approximately 300 MPa to over 1700 MPa".
const ABSTRACT_YS_LOW = 300;
const ABSTRACT_YS_HIGH = 1700;

const steel = { materialClass: "non-austenitic-steel" as const, carbonWtPct: 0.4 };

test("util constants equal the independently transcribed Table 1 'All data' rows", () => {
  const { yield: y, tensile: t } = PAVLINA_VAN_TYNE_2008;
  assert.equal(y.constant_MPa, TABLE1_ALL_DATA.yield.constant);
  assert.equal(y.coefficient, TABLE1_ALL_DATA.yield.coefficient);
  assert.equal(y.hvMin, TABLE1_ALL_DATA.yield.hvMin);
  assert.equal(y.hvMax, TABLE1_ALL_DATA.yield.hvMax);
  assert.equal(y.standardError_MPa, TABLE1_ALL_DATA.yield.standardError);
  assert.equal(t.constant_MPa, TABLE1_ALL_DATA.tensile.constant);
  assert.equal(t.coefficient, TABLE1_ALL_DATA.tensile.coefficient);
  assert.equal(t.hvMin, TABLE1_ALL_DATA.tensile.hvMin);
  assert.equal(t.hvMax, TABLE1_ALL_DATA.tensile.hvMax);
  assert.equal(t.standardError_MPa, TABLE1_ALL_DATA.tensile.standardError);
  assert.equal(HYPOEUTECTOID_C_MAX_WT_PCT, 0.76);
});

test("sign check: the negative constant reproduces the abstract's yield-strength span over the valid HV range", () => {
  // The PDF text extraction drops the minus glyph in Eq 4; Table 1 prints -90.7. With +90.7 the low end would be 461 MPa.
  const ys = (hv: number) => TABLE1_ALL_DATA.yield.constant + TABLE1_ALL_DATA.yield.coefficient * hv;
  assert.ok(ys(TABLE1_ALL_DATA.yield.hvMin) < ABSTRACT_YS_LOW, String(ys(129)));
  assert.ok(ys(TABLE1_ALL_DATA.yield.hvMax) > ABSTRACT_YS_HIGH, String(ys(632)));
  assert.ok(90.7 + 2.876 * 129 > ABSTRACT_YS_LOW + 100);
});

test("HV from yield strength inverts Table 1 Eq 4 exactly over HV 129-632", () => {
  for (let hv = 129; hv <= 632; hv++) {
    const ys = TABLE1_ALL_DATA.yield.constant + TABLE1_ALL_DATA.yield.coefficient * hv;
    const e = estimateSteelHvFromYield(ys, steel);
    assert.equal(e.hv, hv, `HV ${hv}`);
    assert.equal(e.status, "estimate-pavlina-van-tyne-2008");
  }
  // hand-computed anchors: (YS + 90.7) / 2.876
  assert.equal(estimateSteelHvFromYield(1000, steel).hv, 379); // 379.24; old YS/3.1 = 323
  assert.equal(estimateSteelHvFromYield(600, steel).hv, 240); // 240.16
  assert.equal(estimateSteelHvFromYield(951, steel).hv, 362); // 362.20 (maraging 300 preset); old 307
});

test("no extrapolation and no clamping outside HV 129-632", () => {
  assert.equal(estimateSteelHvFromYield(281, steel).hv, 129); // 129.25
  assert.equal(estimateSteelHvFromYield(280, steel).hv, null); // 128.89
  assert.equal(estimateSteelHvFromYield(1726, steel).hv, 632); // 631.68
  assert.equal(estimateSteelHvFromYield(1727, steel).hv, null); // 632.03
  assert.match(estimateSteelHvFromYield(2500, steel).note, /^Unavailable: yield strength 2500 MPa is outside the steel relation's range \(HV 129-632, yield strength about 280-1727 MPa\)/);
  assert.equal(estimateSteelHvFromYield(Number.NaN, steel).hv, null);
  assert.equal(estimateSteelHvFromYield(null, steel).hv, null);
});

test("alloy-class and carbon gates", () => {
  for (const cls of ["austenitic-steel", "titanium-alloy", "nickel-alloy", "aluminium-alloy", "hardmetal", "other"] as const) {
    const e = estimateSteelHvFromYield(900, { materialClass: cls, carbonWtPct: 0.1 });
    assert.equal(e.hv, null, cls);
    assert.equal(e.status, "unavailable");
    assert.match(e.note, /^Unavailable: no verified hardness-strength relation for this alloy class/);
  }
  assert.equal(estimateSteelHvFromYield(900, { materialClass: "non-austenitic-steel", carbonWtPct: 0.75 }).hv, 344);
  assert.equal(estimateSteelHvFromYield(900, { materialClass: "non-austenitic-steel", carbonWtPct: 0.76 }).hv, null);
  assert.match(estimateSteelHvFromYield(900, { materialClass: "non-austenitic-steel", carbonWtPct: undefined }).note, /carbon content unknown/);
});

test("estimate note names the source, the validity range and 'not measured'", () => {
  const e = estimateSteelHvFromYield(1000, steel);
  assert.match(e.note, /^≈ 379 HV: estimate from yield strength per Pavlina & Van Tyne \(2008\)/);
  assert.match(e.note, /HV 129-632/);
  assert.match(e.note, /not measured$/);
  assert.match(SPECIMEN_HARDNESS_NOT_LOADED_NOTE, /no measured hardness/);
});

test("units trap: Tabor's 3 needs HV in MPa (x 9.807), so YS/3.1 was neither Tabor nor the steel regression", () => {
  const taborFactorMPaPerHV = 9.807 / 3; // flow stress (MPa) per HV (kgf/mm2), H = 3 sigma in consistent units
  assert.ok(Math.abs(taborFactorMPaPerHV - 3.269) < 0.001);
  // the old rule HV = YS / 3.1 versus the regression at YS 1000 MPa: 323 vs 379 HV
  assert.notEqual(Math.round(1000 / 3.1), estimateSteelHvFromYield(1000, steel).hv);
});

test("material builder presets: only the non-austenitic hypoeutectoid steel gets an estimate", () => {
  const derived = Object.fromEntries(
    Object.entries(MATERIAL_PRESETS).map(([k, p]) => [k, deriveProperties(p.composition, p.name, p.base, { category: p.category })])
  );
  // old: in718 406 (YS/3.05), custom-ni 494, hastelloy-x 336, ti64 346 (YS/2.9), ss316l 210, alsi10mg 115, cocr-bio 380
  for (const k of ["in718", "custom-ni-superalloy", "hastelloy-x", "ti64-gr5", "ss316l", "alsi10mg", "cocr-bio"]) {
    assert.equal(derived[k].hardness_HV, null, k);
    assert.equal(derived[k].hardnessHVStatus, "unavailable", k);
    assert.match(derived[k].hardnessHVNote!, /^Unavailable: no verified hardness-strength relation/, k);
  }
  const m = derived["maraging300"];
  assert.equal(m.yieldStrength_25C_MPa, 951);
  assert.equal(m.hardness_HV, 362); // old round(951 / 3.1) = 307
  assert.equal(m.hardnessHVStatus, "estimate-pavlina-van-tyne-2008");
});

test("Si-free austenitic composition is classified FCC (was NaN -> BCC) and gets no steel estimate", () => {
  const d = deriveProperties({ Fe: 70, Cr: 18, Ni: 12 }, "Si-free 18-12", "Fe");
  assert.equal(d.xrd.crystalSystem, "FCC");
  assert.equal(d.hardness_HV, null);
  assert.match(d.hardnessHVNote!, /Austenitic stainless steel/);
});

test("persisted state before version 1 is recomputed; atomic-percent specimens are unavailable", () => {
  const p = MATERIAL_PRESETS["ti64-gr5"];
  const fresh = { id: "x", ...deriveProperties(p.composition, p.name, p.base), sourceTab: "t", lastModified: 0, isCustomModified: false } as MaterialSpecimen;
  const stale = { ...fresh, hardness_HV: 346, hardnessHVStatus: undefined, hardnessHVNote: undefined } as MaterialSpecimen;
  const migrated = migrateMaterialStoreState({ activeMaterialSpecimen: stale, activeSpecimen: stale, savedSpecimens: [stale] }, 0) as Record<string, any>;
  assert.equal(migrated.activeMaterialSpecimen.hardness_HV, null);
  assert.equal(migrated.activeSpecimen.hardness_HV, null);
  assert.equal(migrated.savedSpecimens[0].hardness_HV, null);
  const untouched = migrateMaterialStoreState({ activeMaterialSpecimen: stale }, 1) as Record<string, any>;
  assert.equal(untouched.activeMaterialSpecimen.hardness_HV, 346);
  const atPct = withHardnessEstimate({ ...fresh, unit: "at_pct" });
  assert.equal(atPct.hardness_HV, null);
  assert.match(atPct.hardnessHVNote!, /atomic-percent/);
});

test("both specimen stores publish the labelled estimate or Unavailable (old: YS/3.1 or the per-class rules)", () => {
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const target = new EventTarget();
  Object.defineProperty(globalThis, "window", { value: target, configurable: true });
  const payloads: PipelineMaterialPayload[] = [];
  target.addEventListener("metallix-pipeline-updated", (e) => payloads.push((e as CustomEvent<PipelineMaterialPayload>).detail));
  try {
    useMaterialSpecimenStore.getState().updateComposition({ Ni: 75, Cr: 25 }, "Ni fixture", "Ni");
    let p = payloads.at(-1)!;
    assert.equal(p.hardnessHV, null);
    assert.equal(p.hardnessHVSource, "unavailable");
    assert.match(p.hardness, /^Unavailable: no verified hardness-strength relation for this alloy class \(Nickel alloy\)/);

    useMaterialSpecimenStore.getState().updateComposition({ Fe: 97.6, C: 0.4, Mn: 0.8, Cr: 1.0, Mo: 0.2 }, "Steel fixture", "Fe");
    const s = useMaterialSpecimenStore.getState().activeSpecimen;
    p = payloads.at(-1)!;
    assert.equal(s.xrd.crystalSystem, "BCC");
    assert.equal(s.yieldStrength_25C_MPa, 509); // the store's own composition-based estimate
    assert.equal(p.hardnessHV, 209); // (509 + 90.7) / 2.876 = 208.5; old round(509 / 3.1) = 164
    assert.equal(p.hardnessHVSource, "estimate-from-yield");
    assert.match(p.hardness, /^≈ 209 HV: estimate from yield strength per Pavlina & Van Tyne \(2008\)/);

    useMaterialStore.getState().updateComposition({ Ti: 90, Al: 6, V: 4 }, "Ti fixture");
    p = payloads.at(-1)!;
    assert.equal(p.hardnessHV, null);
    assert.match(p.hardness, /Titanium alloy/);
  } finally {
    if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
    else delete (globalThis as { window?: unknown }).window;
  }
});

test("specimen-level estimator uses base metal + crystal system + wt% C", () => {
  assert.equal(estimateSpecimenHardnessHV({ baseMetal: "Fe", crystalSystem: "BCC", composition: { Fe: 98, C: 0.4 }, yieldStrength_MPa: 1000 }).hv, 379);
  assert.equal(estimateSpecimenHardnessHV({ baseMetal: "Fe", crystalSystem: "FCC", composition: { Fe: 70, C: 0.02 }, yieldStrength_MPa: 1000 }).hv, null);
  assert.equal(estimateSpecimenHardnessHV({ baseMetal: "Fe", crystalSystem: "BCC", composition: undefined, yieldStrength_MPa: 1000 }).hv, null);
});
